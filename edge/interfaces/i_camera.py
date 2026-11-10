"""摄像头设备接口定义。"""
from __future__ import annotations

from abc import ABC, abstractmethod

## @brief 图像数据以不透明字节承载，便于后续纯函数下沉 .so
FrameImage = bytes

## @brief 设备状态快照，键由具体设备实现约定
CameraStatus = dict[str, object]


## @brief 摄像头设备契约；Windows 走索引、Linux 走固定路径由工厂决定
class ICameraDevice(ABC):
    ## @brief 打开设备
    #  @return 无
    @abstractmethod
    def open(self) -> None:
        ...

    ## @brief 读取一帧
    #  @return 图像字节；暂无帧时返回 None
    @abstractmethod
    def readFrame(self) -> FrameImage | None:
        ...

    ## @brief 关闭设备
    #  @return 无
    @abstractmethod
    def close(self) -> None:
        ...

    ## @brief 查询设备状态
    #  @return 状态快照
    @abstractmethod
    def getStatus(self) -> CameraStatus:
        ...
