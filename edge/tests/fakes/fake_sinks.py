"""三类事件回调接口的 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_sinks import (
    AckFrame,
    DecodedSignal,
    ICaptureSink,
    IRecognitionSink,
    SignalSink,
)


## @brief 记录 TCP 链路事件的 Sink Fake
class FakeSignalSink(SignalSink):
    ## @brief 构造 Fake
    def __init__(self) -> None:
        ## @brief 已解码信号记录
        self.signals: list[DecodedSignal] = []
        ## @brief 坏帧异常记录
        self.frameErrors: list[Exception] = []
        ## @brief 断链宣告记录
        self.linkDownEvents: list[tuple[str, str]] = []
        ## @brief 链路恢复次数
        self.linkUpCount: int = 0

    ## @brief 记录已解码信号
    #  @param signal 信号帧
    #  @return 无
    def onSignalDecoded(self, signal: DecodedSignal) -> None:
        self.signals.append(signal)

    ## @brief 记录坏帧异常
    #  @param exception 帧解析异常
    #  @return 无
    def onFrameError(self, exception: Exception) -> None:
        self.frameErrors.append(exception)

    ## @brief 记录断链宣告
    #  @param reason 断开原因
    #  @param source 宣告来源
    #  @return 无
    def onLinkDown(self, reason: str, source: str) -> None:
        self.linkDownEvents.append((reason, source))

    ## @brief 记录链路恢复
    #  @return 无
    def onLinkUp(self) -> None:
        self.linkUpCount += 1


## @brief 记录采集事件的 Sink Fake
class FakeCaptureSink(ICaptureSink):
    ## @brief 构造 Fake
    def __init__(self) -> None:
        ## @brief 成功事件记录
        self.successEvents: list[tuple[int, str]] = []
        ## @brief 失败异常记录
        self.errorEvents: list[tuple[int, Exception]] = []

    ## @brief 记录采集成功
    #  @param workerId 工作线程编号
    #  @param path 落盘路径
    #  @return 无
    def onCaptureSuccess(self, workerId: int, path: str) -> None:
        self.successEvents.append((workerId, path))

    ## @brief 记录采集失败
    #  @param workerId 工作线程编号
    #  @param exception 采集异常
    #  @return 无
    def onCaptureError(self, workerId: int, exception: Exception) -> None:
        self.errorEvents.append((workerId, exception))


## @brief 记录识别事件的 Sink Fake
class FakeRecognitionSink(IRecognitionSink):
    ## @brief 构造 Fake
    def __init__(self) -> None:
        ## @brief 结果事件记录
        self.resultEvents: list[tuple[int, AckFrame, str]] = []
        ## @brief 失败异常记录
        self.errorEvents: list[tuple[int, Exception]] = []

    ## @brief 记录识别结果
    #  @param workerId 工作线程编号
    #  @param ack 应答帧
    #  @param requestId 上位机请求标识
    #  @return 无
    def onRecognitionResult(self, workerId: int, ack: AckFrame, requestId: str) -> None:
        self.resultEvents.append((workerId, ack, requestId))

    ## @brief 记录识别失败
    #  @param workerId 工作线程编号
    #  @param exception 推理异常
    #  @return 无
    def onRecognitionError(self, workerId: int, exception: Exception) -> None:
        self.errorEvents.append((workerId, exception))
