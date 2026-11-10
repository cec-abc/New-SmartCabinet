"""事件回调接口定义：信号、采集、识别三类 Sink。"""
from __future__ import annotations

from abc import ABC, abstractmethod

## @brief 解码后的信号帧
DecodedSignal = dict[str, object]

## @brief 业务应答帧
AckFrame = dict[str, object]


## @brief TCP 链路事件回调，实现方只做轻量分发或入队
class SignalSink(ABC):
    ## @brief 收到已解码信号
    #  @param signal 信号帧
    #  @return 无
    @abstractmethod
    def onSignalDecoded(self, signal: DecodedSignal) -> None:
        ...

    ## @brief 坏帧通知
    #  @param exception 帧解析异常
    #  @return 无
    @abstractmethod
    def onFrameError(self, exception: Exception) -> None:
        ...

    ## @brief 链路断开宣告；靠状态机返回值去重
    #  @param reason 断开原因
    #  @param source 宣告来源（如 RECV / HEART）
    #  @return 无
    @abstractmethod
    def onLinkDown(self, reason: str, source: str) -> None:
        ...

    ## @brief 链路恢复通知
    #  @return 无
    @abstractmethod
    def onLinkUp(self) -> None:
        ...


## @brief 采集事件回调，禁止在回调内执行阻塞 IO
class ICaptureSink(ABC):
    ## @brief 采集成功
    #  @param workerId 工作线程编号
    #  @param path 落盘路径
    #  @return 无
    @abstractmethod
    def onCaptureSuccess(self, workerId: int, path: str) -> None:
        ...

    ## @brief 采集失败
    #  @param workerId 工作线程编号
    #  @param exception 采集异常
    #  @return 无
    @abstractmethod
    def onCaptureError(self, workerId: int, exception: Exception) -> None:
        ...


## @brief 识别事件回调，禁止在回调内执行阻塞 IO
class IRecognitionSink(ABC):
    ## @brief 识别完成并已组好应答帧
    #  @param workerId 工作线程编号
    #  @param ack 应答帧
    #  @param requestId 上位机请求标识
    #  @return 无
    @abstractmethod
    def onRecognitionResult(self, workerId: int, ack: AckFrame, requestId: str) -> None:
        ...

    ## @brief 识别失败
    #  @param workerId 工作线程编号
    #  @param exception 推理异常
    #  @return 无
    @abstractmethod
    def onRecognitionError(self, workerId: int, exception: Exception) -> None:
        ...
