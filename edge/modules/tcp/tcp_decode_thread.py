"""TCP 帧解码线程。"""
from __future__ import annotations

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import SignalSink
from edge.modules.tcp.tcp_comm import TcpComm


## @brief 帧解码线程；处理半包/粘包与超长帧，解码后分发至 Sink
class TcpDecodeThread(BaseThread):
    ## @brief 构造解码线程
    #  @param comm 通信封装（注入）
    #  @param sink 信号回调（门面自身实现 SignalSink）
    #  @param logger 可选日志器
    def __init__(self, comm: TcpComm, sink: SignalSink, logger: ILogger | None) -> None:
        super().__init__(name="TcpDecode", logger=logger)
        ## @brief 通信封装
        self._comm: TcpComm = comm
        ## @brief 信号回调
        self._sink: SignalSink = sink

    ## @brief 主循环：recv 累积缓冲、\n 切帧、超长/坏帧丢弃并继续、断线经 Sink 宣告
    #  @return 无
    def runLoop(self) -> None:
        buffer = b""
        while self.isRunning():
            try:
                data = self._comm.recv()
            except EdgeError as exc:
                self._sink.onFrameError(exc)
                self._sink.onLinkDown("recv error", "RECV")
                return
            if not data:
                self._sink.onLinkDown("recv empty", "RECV")
                return
            buffer += data
            frames, buffer = self._comm.splitFrames(buffer)
            for raw in frames:
                try:
                    decoded = self._comm.decodeAndParse(raw)
                except EdgeError as exc:
                    self._sink.onFrameError(exc)
                    continue
                self._sink.onSignalDecoded(decoded)
