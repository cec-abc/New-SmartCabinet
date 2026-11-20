"""摄像头对焦接口定义。"""
from __future__ import annotations

from abc import ABC, abstractmethod

## @file edge/interfaces/i_camera_focus.py
## @brief 摄像头对焦接口契约：自动对焦开关、设备绝对焦点位置与变焦位置
## @author 边缘计算项目


## @brief 摄像头对焦契约；自动对焦开关与焦点位置统一收敛在此
class ICameraFocus(ABC):
    ## @brief 开关自动对焦
    #  @param enabled True 开自动对焦，False 关自动对焦
    #  @return 无
    @abstractmethod
    def setAutoFocus(self, enabled: bool) -> None:
        ...

    ## @brief 设置焦点位置
    #  @param position 设备绝对焦点值，合法范围由设备层常量约束，越界按配置错误拒绝
    #  @return 无
    @abstractmethod
    def setFocusPosition(self, position: float) -> None:
        ...

    ## @brief 读取当前焦点位置
    #  @return 设备绝对焦点值
    @abstractmethod
    def getFocusPosition(self) -> float:
        ...

    ## @brief 设置设备绝对变焦位置
    #  @param position 变焦位置，合法范围由设备层常量约束，越界按配置错误拒绝
    #  @return 无
    @abstractmethod
    def setZoomPosition(self, position: float) -> None:
        ...

    ## @brief 读取当前变焦位置
    #  @return 变焦位置
    @abstractmethod
    def getZoomPosition(self) -> float:
        ...
