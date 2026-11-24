"""TCP 帧解码线程。"""
from __future__ import annotations

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import SignalSink
from edge.modules.tcp.tcp_comm import (
    MAX_RECV_BUFFER_BYTES,
    RX_MODULE_NAME,
    TcpComm,
    buildIoLogPayload,
    countEmptyLines,
)

## @file edge/modules/tcp/tcp_decode_thread.py
## @brief TCP 帧解码线程：收字节、按换行切帧、逐帧解码并转发
## @author 袁燕


## @brief 坏帧日志采样间隔；连续坏帧时每 N 帧记一条，避免日志洪泛撑爆队列
BAD_FRAME_LOG_INTERVAL: int = 64


## @brief 帧解码线程；处理半包/粘包与超长帧，解码后分发至 Sink
class TcpDecodeThread(BaseThread):
    ## @brief 构造解码线程
    #  @param comm 通信封装（注入）
    #  @param sink 信号回调（门面自身实现 SignalSink）
    #  @param logger 可选日志器
    #  @return 无
    def __init__(self, comm: TcpComm, sink: SignalSink, logger: ILogger | None) -> None:
        super().__init__(name="TcpDecode", logger=logger)
        ## @brief 通信封装
        self._comm: TcpComm = comm
        ## @brief 信号回调
        self._sink: SignalSink = sink
        ## @brief 坏帧累计计数，用于日志采样；计数本身由控制层独立维护
        self._badFrameCount: int = 0

    ## @brief 主循环：收数据、切帧、分发；停机、断链或缓冲超限时收敛退出
    #  @return 无
    def runLoop(self) -> None:
        buffer = b""
        while self.isRunning():
            chunk = self.readNextChunk()
            if chunk is None:
                return
            if not chunk:
                ## 接收超时是正常轮询节拍，确认没收到停机指令再等下一批
                if not self.isRunning():
                    return
                continue
            buffer += chunk
            buffer = self.dispatchFrames(buffer)
            if self.reportBufferOverflow(len(buffer)):
                return

    ## @brief 读一段接收数据；把超时、断链与停机三种情况收敛成一个返回值
    #  @return 收到数据返回字节；超时返回空字节；该退出返回 None
    #  @note 内置 TimeoutError 只在 tcp 模块内部当轮询节拍，不转成业务异常；
    #       真正断链才转成 EdgeError(LINK_DOWN) 并在这里宣告。
    def readNextChunk(self) -> bytes | None:
        try:
            data = self._comm.recv()
        except TimeoutError:
            return b""
        except EdgeError as exc:
            ## 停机指令已下达时不再宣告断链，避免停机过程又把重连线程拉起来
            if not self.isRunning():
                return None
            self._sink.onFrameError(exc)
            self._sink.onLinkDown("recv error", "RECV")
            return None
        if not data:
            if not self.isRunning():
                return None
            self._sink.onLinkDown("recv empty", "RECV")
            return None
        return data

    ## @brief 检查切帧后剩余的半包是否超过上限；超限时记日志并请求断链收敛
    #  @param bufferBytes 剩余缓冲字节数
    #  @return 超限返回 True
    #  @note 一直收不到换行的异常数据会把缓冲撑大，这里按协议单帧量级设上限。
    def reportBufferOverflow(self, bufferBytes: int) -> bool:
        if bufferBytes <= MAX_RECV_BUFFER_BYTES:
            return False
        if self._logger is not None:
            self._logger.error(
                RX_MODULE_NAME,
                f"接收缓冲 {bufferBytes} 字节超过上限 {MAX_RECV_BUFFER_BYTES}, 判定链路异常",
            )
        if self.isRunning():
            self._sink.onLinkDown("recv buffer overflow", "RECV")
        return True

    ## @brief 对缓冲切帧并逐帧解码分发；返回未凑完整的剩余缓冲
    #  @param buffer 当前接收缓冲
    #  @return 剩余未完整数据
    def dispatchFrames(self, buffer: bytes) -> bytes:
        emptyCount = countEmptyLines(buffer)
        frames, rest = self._comm.splitFrames(buffer)
        if emptyCount and self._logger is not None:
            ## 空行是协议容忍的多余换行，切帧层已忽略，这里记一条说明日志
            self._logger.info(
                RX_MODULE_NAME,
                f"收到 {emptyCount} 个空行, 已忽略, 不计为接收帧",
            )
        for raw in frames:
            self.dispatchOneFrame(raw)
        return rest

    ## @brief 解码并分发单帧；坏帧记说明日志并上报，不中断接收循环
    #  @param raw 单帧原始字节
    #  @return 无
    def dispatchOneFrame(self, raw: bytes) -> None:
        try:
            decoded = self._comm.decodeAndParse(raw)
        except EdgeError as exc:
            self._badFrameCount += 1
            if (self._logger is not None
                    and (self._badFrameCount - 1) % BAD_FRAME_LOG_INTERVAL == 0):
                ## 坏帧进不了正常接收流程；按固定间隔采样记录，
                ## 避免坏帧洪泛把日志队列撑爆。计数由上游 onFrameError 独立维护
                self._logger.error(
                    RX_MODULE_NAME,
                    f"坏帧已丢弃 累计={self._badFrameCount} 字节数={len(raw)} "
                    f"异常码={exc.code.name} 原因={exc}",
                )
            self._sink.onFrameError(exc)
            return
        if self._logger is not None:
            self._logger.rx(RX_MODULE_NAME, buildIoLogPayload(decoded, len(raw)))
        self._sink.onSignalDecoded(decoded)
