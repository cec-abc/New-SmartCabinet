"""TCP 控制模块门面：链路状态机、退避重连、心跳与解码编排。"""
from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from edge.base.base_service import BaseService
from edge.base.base_thread import BaseThread
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import DecodedSignal, SignalSink
from edge.interfaces.i_socket import ISocket
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.tcp.tcp_decode_thread import TcpDecodeThread
from edge.modules.tcp.tcp_heart_thread import TcpHeartThread
from edge.modules.tcp.tcp_reconnect_thread import TcpReconnectThread

## @brief 链路就绪状态
LINK_UP = "UP"
## @brief 链路断开状态
LINK_DOWN = "DOWN"


## @brief TCP 控制模块门面；唯一经 transitionTo 写入 linkState，并发宣告靠返回值去重
class TcpControlLayer(BaseService, SignalSink):
    ## @brief 构造门面
    #  @param socket 套接字（注入）
    #  @param logger 日志器（注入，可为空）
    #  @param backoffSeq 退避序列（注入，禁止读配置）
    #  @param maxFrameSize 单帧字节上限（注入）
    #  @param heartIntervalSec 心跳周期秒（注入）
    #  @param buildHeartbeat 心跳帧构造器（出网键名按协议原文）
    #  @param upstreamSink 上游回调，默认空
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
        ## @brief 上游回调
        self._upstreamSink: SignalSink | None = upstreamSink
        ## @brief 链路状态，仅经 transitionTo 写入
        self._linkState: str = LINK_DOWN
        ## @brief 状态锁
        self._stateLock: Lock = Lock()
        ## @brief 当前重连线程（每次拉起新建实例，绕开 BaseThread.start 幂等）
        self._reconnect: TcpReconnectThread | None = None
        ## @brief 当前心跳线程（每次拉起新建实例）
        self._heart: TcpHeartThread | None = None
        ## @brief 当前解码线程（每次拉起新建实例）
        self._decode: TcpDecodeThread | None = None

    ## @brief 读取链路状态（只读入口，写入仅经 transitionTo）
    #  @return 当前状态字符串
    def getState(self) -> str:
        return self._linkState

    ## @brief 启动：新建并重连线程（D-02 非 UP 不启其他线程）
    #  @return 无
    def start(self) -> None:
        self._reconnect = self._buildReconnect()
        self._reconnect.start()

    ## @brief 停机：严格串行停止全部线程并关闭套接字
    #  @return 无
    def stop(self) -> None:
        if self._reconnect is not None:
            self._reconnect.stop()
        if self._heart is not None:
            self._heart.stop()
        if self._decode is not None:
            self._decode.stop()
        self._comm.close()

    ## @brief 原子迁移链路状态；同态返回 False 实现并发去重
    #  @param state 目标状态
    #  @param reason 迁移原因
    #  @param source 宣告来源
    #  @return 状态发生变更返回 True
    def transitionTo(self, state: str, reason: str, source: str) -> bool:
        with self._stateLock:
            if state == self._linkState:
                return False
            self._linkState = state
        if self._logger is not None:
            self._logger.info("TcpControl", f"link {state} reason={reason} source={source}")
        return True

    ## @brief 重连成功回调：迁移 UP、新建心跳与解码线程、通知上游
    #  @return 无
    def _onConnected(self) -> None:
        if self.transitionTo(LINK_UP, "connected", "RECONNECT"):
            self._heart = self._buildHeart()
            self._decode = self._buildDecode()
            self._heart.start()
            self._decode.start()
            self.onLinkUp()

    ## @brief 心跳发送失败回调：宣告 DOWN（去重由返回值处理）
    #  @return 无
    def _onHeartFailed(self) -> None:
        self.onLinkDown("heart send failed", "HEART")

    ## @brief 新建重连线程实例（每次拉起均新建，绕开 BaseThread.start 幂等）
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
            thread.stop()
        except RuntimeError:
            pass

    ## @brief 链路断开宣告；并发去重后停止心跳解码并新建重连线程（D-02）
    #  @param reason 断开原因
    #  @param source 宣告来源
    #  @return 无
    def onLinkDown(self, reason: str, source: str) -> None:
        if self.transitionTo(LINK_DOWN, reason, source):
            self._haltThread(self._heart)
            self._haltThread(self._decode)
            self._reconnect = self._buildReconnect()
            self._reconnect.start()

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
