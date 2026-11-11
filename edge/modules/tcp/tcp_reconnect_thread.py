"""TCP 退避重连线程。"""
from __future__ import annotations

from collections.abc import Callable

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_socket import ISocket


## @brief 退避重连线程；连接成功后经回调移交，非 UP 期间唯一运行线程（D-02）
class TcpReconnectThread(BaseThread):
    ## @brief 构造重连线程
    #  @param socket 套接字实现（注入）
    #  @param backoffSeq 退避序列，构造注入，禁止读取配置
    #  @param logger 可选日志器
    #  @param onConnected 连接成功回调，移交控制权
    def __init__(self, socket: ISocket, backoffSeq: list[float], logger: ILogger | None,
                 onConnected: Callable[[], None]) -> None:
        super().__init__(name="TcpReconnect", logger=logger)
        ## @brief 注入的套接字
        self._socket: ISocket = socket
        ## @brief 退避序列
        self._backoffSeq: list[float] = backoffSeq
        ## @brief 连接成功回调
        self._onConnected: Callable[[], None] = onConnected

    ## @brief 主循环：失败按退避序列等待并重试，成功则重置退避并移交
    #  @return 无
    def runLoop(self) -> None:
        attempt = 0
        while self.isRunning():
            try:
                self._socket.connect()
            except EdgeError as exc:
                if self._logger is not None:
                    self._logger.error("TcpReconnect", f"连接失败 attempt={attempt}", exception=exc)
                if not self._waitBackoff(attempt):
                    return
                attempt = min(attempt + 1, len(self._backoffSeq) - 1)
                continue
            attempt = 0
            self._onConnected()
            return

    ## @brief 按当前尝试次数取退避秒数并打断式等待
    #  @param attempt 当前尝试序号
    #  @return 等待被打断返回 False
    def _waitBackoff(self, attempt: int) -> bool:
        index = min(attempt, len(self._backoffSeq) - 1)
        return self.interruptibleWait(self._backoffSeq[index])
