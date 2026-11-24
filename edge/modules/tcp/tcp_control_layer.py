"""TCP 控制模块门面：链路状态机、退避重连、心跳与解码编排。"""
from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from edge.base.base_service import BaseService
from edge.base.base_thread import BaseThread
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import DecodedSignal, SignalSink
from edge.interfaces.i_socket import ISocket
from edge.modules.tcp.tcp_comm import LINK_DOWN, LINK_UP, TcpComm
from edge.modules.tcp.tcp_decode_thread import TcpDecodeThread
from edge.modules.tcp.tcp_heart_thread import TcpHeartThread
from edge.modules.tcp.tcp_reconnect_thread import TcpReconnectThread

## @file edge/modules/tcp/tcp_control_layer.py
## @brief TCP 控制模块门面：链路状态机、退避重连、心跳与解码编排
## @author 袁燕

## @brief 停止单个线程时等待其退出的最长秒数
## @note 配置里的接收超时是 0.5 秒，比这里短，stop() 能在一个轮询周期内收敛；
##       重连退避最长 30 秒，靠 interruptibleWait 被停止事件唤醒，不受此值限制。
THREAD_STOP_TIMEOUT_SEC: float = 3.0


## @brief TCP 控制模块门面；唯一经 transitionTo 写入 linkState，并发宣告靠返回值去重
class TcpControlLayer(BaseService, SignalSink):
    ## @brief 上游回调的类级默认值；用 __new__ 手工构造的取证对象也不会缺这个字段
    _upstreamSink: SignalSink | None = None

    ## @brief 构造门面
    #  @param socket 套接字（注入）
    #  @param logger 日志器（注入，可为空）
    #  @param backoffSeq 退避序列（注入，禁止读配置）
    #  @param maxFrameSize 单帧字节上限（注入）
    #  @param heartIntervalSec 心跳周期秒（注入）
    #  @param buildHeartbeat 心跳帧构造器（出网键名按协议原文）
    #  @param upstreamSink 上游回调，默认空
    #  @return 无
    def __init__(self, socket: ISocket, logger: ILogger | None, backoffSeq: list[float],
                 maxFrameSize: int, heartIntervalSec: float,
                 buildHeartbeat: Callable[[], dict[str, object]],
                 upstreamSink: SignalSink | None = None) -> None:
        ## @brief 注入的套接字
        self._socket: ISocket = socket
        ## @brief 注入的日志器
        self._logger: ILogger | None = logger
        ## @brief 退避序列（构造注入，禁止读配置）
        self._backoffSeq: list[float] = backoffSeq
        ## @brief 单帧字节上限（构造注入）
        self._maxFrameSize: int = maxFrameSize
        ## @brief 心跳周期秒（构造注入）
        self._heartIntervalSec: float = heartIntervalSec
        ## @brief 心跳帧构造器（出网键名按协议原文）
        self._buildHeartbeat: Callable[[], dict[str, object]] = buildHeartbeat
        ## @brief 通信封装
        self._comm: TcpComm = TcpComm(socket, maxFrameSize, logger)
        ## @brief 上游回调；类型由类级声明给出
        self._upstreamSink = upstreamSink
        ## @brief 链路状态，仅经 transitionTo 写入
        self._linkState: str = LINK_DOWN
        ## @brief 停机标志；置位后拒绝再迁移到 UP，防止停机与重连成功回调竞态
        self._stopping: bool = False
        ## @brief 状态锁
        self._stateLock: Lock = Lock()
        ## @brief 当前重连线程（每次拉起新建实例，绕开 BaseThread.start 同一实例只启动一次的限制）
        self._reconnect: TcpReconnectThread | None = None
        ## @brief 当前心跳线程（每次拉起新建实例）
        self._heart: TcpHeartThread | None = None
        ## @brief 当前解码线程（每次拉起新建实例）
        self._decode: TcpDecodeThread | None = None

    ## @brief 读取链路状态（只读入口，写入仅经 transitionTo）
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留；
    #       读也走同一把状态锁，保证与写入看到的始终是同一个值。
    #  @return 当前状态字符串
    def getState(self) -> str:
        with self._stateLock:
            return self._linkState

    ## @brief 启动：新建并重连线程（D-02 非 UP 不启其他线程）
    #  @return 无
    def start(self) -> None:
        with self._stateLock:
            ## 重新启动时清除停机标志，允许再次迁移到 UP
            self._stopping = False
        self._reconnect = self._buildReconnect()
        self._reconnect.start()

    ## @brief 停机：先把链路标成断开，再严格串行停止全部线程并关闭套接字
    #  @return 无
    #  @note 停机后 getState() 必须回到 DOWN，否则控制层的链路探针会认为链路仍通，
    #       继续往已关闭的套接字直发应答。这里只迁移状态，不走 onLinkDown，
    #       避免停机过程中又把重连线程拉起来。
    def stop(self) -> None:
        with self._stateLock:
            ## 先置停机标志，重连成功回调据此拒绝迁移到 UP
            self._stopping = True
        self.transitionTo(LINK_DOWN, "stop", "STOP")
        self._haltThread(self._reconnect)
        self._haltThread(self._heart)
        self._haltThread(self._decode)
        self._comm.close()

    ## @brief 原子迁移链路状态；同态返回 False 实现并发去重
    #  @param state 目标状态
    #  @param reason 迁移原因
    #  @param source 宣告来源
    #  @return 状态发生变更返回 True
    def transitionTo(self, state: str, reason: str, source: str) -> bool:
        with self._stateLock:
            ## 停机后拒绝迁移到 UP，避免重连回调把已停链路翻回可用
            ## getattr 兼容按类直接构造、未走 __init__ 的定向测试对象
            if getattr(self, "_stopping", False) and state == LINK_UP:
                return False
            if state == self._linkState:
                return False
            self._linkState = state
        if self._logger is not None:
            self._logger.info("TcpControl", f"link {state} reason={reason} source={source}")
        return True

    ## @brief 重连成功回调：原子迁移 UP 并拉起线程，停机置位期间不启动
    #  @return 无
    #  @note 状态迁移、停机检查、线程装配与启动全在同一把锁内，彻底消除 stop
    #        与本回调之间的检查-使用窗口；BaseThread.start 只起线程不回调，锁内安全。
    #        上游通知放到锁外，避免回调重入本层锁
    def _onConnected(self) -> None:
        with self._stateLock:
            if self._stopping or self._linkState == LINK_UP:
                return
            self._linkState = LINK_UP
            heart = self._buildHeart()
            decode = self._buildDecode()
            self._heart = heart
            self._decode = decode
            heart.start()
            decode.start()
        if self._logger is not None:
            self._logger.info("TcpControl", "link UP reason=connected source=RECONNECT")
        self.onLinkUp()

    ## @brief 心跳发送失败回调：宣告 DOWN（去重由返回值处理）
    #  @return 无
    def _onHeartFailed(self) -> None:
        self.onLinkDown("heart send failed", "HEART")

    ## @brief 新建重连线程实例（每次拉起均新建，绕开 BaseThread.start 同一实例只启动一次的限制）
    #  @return 重连线程
    def _buildReconnect(self) -> TcpReconnectThread:
        return TcpReconnectThread(self._socket, self._backoffSeq, self._logger,
                                  onConnected=self._onConnected)

    ## @brief 新建心跳线程实例
    #  @return 心跳线程
    def _buildHeart(self) -> TcpHeartThread:
        return TcpHeartThread(self._comm, self._heartIntervalSec, self._buildHeartbeat,
                              self.getState, self._logger,
                              onHeartSendFailed=self._onHeartFailed)

    ## @brief 新建解码线程实例
    #  @return 解码线程
    def _buildDecode(self) -> TcpDecodeThread:
        return TcpDecodeThread(self._comm, self, self._logger)

    ## @brief 停止线程；调用线程即被停线程时 BaseThread.stop 的 self-join 抛 RuntimeError，
    #        此时 stopEvent 已置位，线程将在 runLoop 退出条件满足后自行结束，予以吞掉
    #  @param thread 待停线程
    #  @return 无
    def _haltThread(self, thread: BaseThread | None) -> None:
        if thread is None:
            return
        try:
            thread.stop(THREAD_STOP_TIMEOUT_SEC)
        except RuntimeError:
            pass

    ## @brief 链路断开宣告；并发去重后停止心跳解码、新建重连线程并通知上游（D-02）
    #  @param reason 断开原因
    #  @param source 宣告来源
    #  @return 无
    #  @note 断链必须转发上游，控制层才能立刻停止向已断开的连接直发应答；
    #       只靠链路探针轮询会晚一个排空周期，期间应答会直发到已断开的连接。
    def onLinkDown(self, reason: str, source: str) -> None:
        if self.transitionTo(LINK_DOWN, reason, source):
            self._haltThread(self._heart)
            self._haltThread(self._decode)
            self._reconnect = self._buildReconnect()
            self._reconnect.start()
            if self._upstreamSink is not None:
                self._upstreamSink.onLinkDown(reason, source)

    ## @brief 链路恢复通知，转发上游
    #  @return 无
    def onLinkUp(self) -> None:
        if self._upstreamSink is not None:
            self._upstreamSink.onLinkUp()

    ## @brief 解码信号转发上游
    #  @param signal 信号帧
    #  @return 无
    def onSignalDecoded(self, signal: DecodedSignal) -> None:
        if self._upstreamSink is not None:
            self._upstreamSink.onSignalDecoded(signal)

    ## @brief 坏帧通知转发上游
    #  @param exception 解析异常
    #  @return 无
    def onFrameError(self, exception: Exception) -> None:
        if self._upstreamSink is not None:
            self._upstreamSink.onFrameError(exception)
