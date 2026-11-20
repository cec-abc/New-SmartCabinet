"""摄像头对焦接口 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_camera import CameraStatus, FrameImage, ICameraDevice
from edge.interfaces.i_camera_focus import ICameraFocus

## @file edge/tests/fakes/fake_camera_focus.py
## @brief 摄像头对焦接口 Fake：记录对焦指令并兼作设备桩
## @author 边缘计算项目


## @brief 记录对焦指令、不碰硬件的摄像头 Fake；同时实现设备契约便于注入采集门面
class FakeCameraFocus(ICameraDevice, ICameraFocus):
    ## @brief 构造 Fake
    #  @param frame readFrame 固定返回的图像字节
    #  @param focusPosition 预设设备绝对焦点位置
    def __init__(self, frame: FrameImage | None = b"frame",
                 focusPosition: float = 0.0) -> None:
        ## @brief 预设图像帧
        self.frame: FrameImage | None = frame
        ## @brief 是否已打开
        self.opened: bool = False
        ## @brief 是否已关闭
        self.closed: bool = False
        ## @brief 是否成功打开过
        self.everOpened: bool = False
        ## @brief 通信是否正常
        self.commOk: bool = True
        ## @brief 自动对焦开关
        self.autoFocus: bool = True
        ## @brief 当前设备绝对焦点位置
        self.focusPosition: float = focusPosition
        ## @brief 当前变焦位置
        self.zoomPosition: float = 0.0
        ## @brief 对焦与变焦指令记录，元素为（指令名, 参数）
        self.focusCommands: list[tuple[str, float]] = []

    ## @brief 记录打开动作
    #  @return 无
    def open(self) -> None:
        self.opened = True
        self.everOpened = True

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
        status: CameraStatus = {
            "opened": self.opened,
            "everOpened": self.everOpened,
            "commOk": self.commOk,
            "focusPosition": self.focusPosition,
        }
        return status

    ## @brief 记录自动对焦开关指令
    #  @param enabled True 开自动对焦，False 关自动对焦
    #  @return 无
    def setAutoFocus(self, enabled: bool) -> None:
        self.autoFocus = enabled
        self.focusCommands.append(("autoFocus", 1.0 if enabled else 0.0))

    ## @brief 记录焦点位置指令
    #  @param position 设备绝对焦点位置
    #  @return 无
    def setFocusPosition(self, position: float) -> None:
        self.focusPosition = position
        self.focusCommands.append(("focusPosition", position))

    ## @brief 返回当前设备绝对焦点位置
    #  @return 焦点位置
    def getFocusPosition(self) -> float:
        return self.focusPosition

    ## @brief 记录变焦位置指令
    #  @param position 变焦位置
    #  @return 无
    def setZoomPosition(self, position: float) -> None:
        self.zoomPosition = position
        self.focusCommands.append(("zoomPosition", position))

    ## @brief 返回当前变焦位置
    #  @return 变焦位置
    def getZoomPosition(self) -> float:
        return self.zoomPosition
