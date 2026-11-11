"""TCP 周期心跳线程。"""
from __future__ import annotations

from collections.abc import Callable

from edge.base.base_thread import BaseThread
from edge.interfaces.i_logger import ILogger
from edge.modules.tcp.tcp_comm import TcpComm


## @brief 周期心跳线程；非 UP 不发送，发送失败经回调去重宣告 DOWN
class TcpHeartThread(BaseThread):
    ## @brief 构造心跳线程
    #  @param comm 通信封装（注入）
    #  @param heartIntervalSec 心跳周期秒，构造注入
    #  @param buildHeartbeat 出网心跳帧构造器，键名按协议原文
    #  @param getState 读取链路状态的函数（写入仅经 transitionTo，此处只读）
    #  @param logger 可选日志器
    #  @param onHeartSendFailed 发送失败回调
    def __init__(self, comm: TcpComm, heartIntervalSec: float,
                 buildHeartbeat: Callable[[], dict[str, object]],
                 getState: Callable[[], str], logger: ILogger | None,
                 onHeartSendFailed: Callable[[], None]) -> None:
        super().__init__(name="TcpHeart", logger=logger)
        ## @brief 通信封装
        self._comm: TcpComm = comm
        ## @brief 心跳周期秒
        self._heartIntervalSec: float = heartIntervalSec
        ## @brief 心跳帧构造器
        self._buildHeartbeat: Callable[[], dict[str, object]] = buildHeartbeat
        ## @brief 状态读取函数
        self._getState: Callable[[], str] = getState
        ## @brief 发送失败回调
        self._onHeartSendFailed: Callable[[], None] = onHeartSendFailed

    ## @brief 单次心跳发送；非 UP 直接返回 False，发送失败返回 False
    #  @return 发送成功返回 True
    def trySendHeartbeat(self) -> bool:
        if self._getState() != "UP":
            return False
        return self._comm.send(self._comm.encodeFrame(self._buildHeartbeat()))

    ## @brief 主循环：周期等待、非 UP 跳过、发送失败触发回调
    #  @return 无
    def runLoop(self) -> None:
        while self.isRunning():
            if not self.interruptibleWait(self._heartIntervalSec):
                return
            if self._getState() != "UP":
                continue
            if not self._comm.send(self._comm.encodeFrame(self._buildHeartbeat())):
                self._onHeartSendFailed()
