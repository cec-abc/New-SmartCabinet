"""帧流回调接口 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_frame_sink import IFrameSink

## @file edge/tests/fakes/fake_frame_sink.py
## @brief 帧流回调接口 Fake：记录帧事件
## @author 边缘计算项目


## @brief 记录帧流事件的 Sink Fake
class FakeFrameSink(IFrameSink):
    ## @brief 构造 Fake
    def __init__(self) -> None:
        ## @brief 帧事件记录，元素为（线程编号, 帧元组, 请求标识）
        self.frameEvents: list[tuple[int, tuple[bytes, ...], str]] = []

    ## @brief 记录一轮取帧完成
    #  @param workerId 工作线程编号
    #  @param frames 本轮取到的帧
    #  @param requestId 上位机请求标识
    #  @return 无
    def onFrameCaptured(self, workerId: int, frames: tuple[bytes, ...], requestId: str) -> None:
        self.frameEvents.append((workerId, frames, requestId))
