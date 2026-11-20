"""帧流回调接口定义。"""
from __future__ import annotations

from abc import ABC, abstractmethod

## @file edge/interfaces/i_frame_sink.py
## @brief 帧流回调接口契约：一轮双路取帧完成的通知
## @author 边缘计算项目


## @brief 帧流事件回调契约；实现方只做轻量分发或入队，禁止在回调内阻塞
class IFrameSink(ABC):
    ## @brief 一轮双路取帧完成
    #  @param workerId 工作线程编号
    #  @param frames 本轮取到的帧，左路在前
    #  @param requestId 上位机请求标识
    #  @return 无
    @abstractmethod
    def onFrameCaptured(self, workerId: int, frames: tuple[bytes, ...], requestId: str) -> None:
        ...
