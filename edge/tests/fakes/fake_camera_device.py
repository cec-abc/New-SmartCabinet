"""摄像头设备接口 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_camera import CameraStatus, FrameImage, ICameraDevice


## @brief 返回固定帧、不访问硬件的摄像头 Fake
class FakeCameraDevice(ICameraDevice):
    ## @brief 构造 Fake
    #  @param frame readFrame 固定返回的图像字节
    def __init__(self, frame: FrameImage | None = b"frame") -> None:
        ## @brief 预设图像帧
        self.frame = frame
        ## @brief 是否已打开
        self.opened = False
        ## @brief 是否已关闭
        self.closed = False

    ## @brief 记录打开动作
    #  @return 无
    def open(self) -> None:
        self.opened = True

    ## @brief 返回预设帧
    #  @return 图像字节或 None
    def readFrame(self) -> FrameImage | None:
        return self.frame

    ## @brief 记录关闭动作
    #  @return 无
    def close(self) -> None:
        self.closed = True

    ## @brief 返回状态快照
    #  @return 状态字典
    def getStatus(self) -> CameraStatus:
        status: CameraStatus = {"opened": self.opened}
        return status
