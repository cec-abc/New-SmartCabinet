"""USB 摄像头设备与工厂：按地址形态选后端，帧读取由注入回调承载。"""
from __future__ import annotations

from collections.abc import Callable

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import CameraStatus, FrameImage, ICameraDevice
from edge.interfaces.i_logger import ILogger

## @brief Windows 后端标识：索引 + CAP_DSHOW
BACKEND_DSHOW = "CAP_DSHOW"
## @brief Linux 后端标识：固定路径 + CAP_V4L2（上板前为骨架）
BACKEND_V4L2 = "CAP_V4L2"
## @brief Windows 摄像头索引个数上限（用于地址形态判定）
INDEX_CHARS = frozenset("0123456789")

## @brief 帧读取回调，真实采集后端由上层注入，本模块不引入硬件依赖
FrameReader = Callable[[], FrameImage | None]


## @brief 摄像头设备实现；帧来源与关闭动作全部构造注入
class CameraDevice(ICameraDevice):
    ## @brief 构造设备
    #  @param deviceAddr 设备地址：Windows 写索引、Linux 写 /dev/... 固定路径
    #  @param backend 后端标识
    #  @param frameReader 帧读取回调
    #  @param logger 可选日志器
    def __init__(self, deviceAddr: str, backend: str, frameReader: FrameReader,
                 logger: ILogger | None = None) -> None:
        ## @brief 设备地址
        self._deviceAddr: str = deviceAddr
        ## @brief 后端标识
        self._backend: str = backend
        ## @brief 帧读取回调
        self._frameReader: FrameReader = frameReader
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief 是否已打开
        self._opened: bool = False

    ## @brief 打开设备；Linux 后端上板前抛骨架异常（模块内，跨界前由调用方转业务异常）
    #  @return 无
    #  @raises NotImplementedError Linux 后端尚未实现时抛出
    def open(self) -> None:
        if self._backend == BACKEND_V4L2:
            # TODO: 上板后按固定路径接 CAP_V4L2 真实打开逻辑
            raise NotImplementedError("Linux 摄像头后端待上板实现")
        self._opened = True

    ## @brief 读取一帧
    #  @return 图像字节；暂无帧返回 None
    #  @raises EdgeError 设备未打开或读取器抛内置异常时抛出，code=CAPTURE
    def readFrame(self) -> FrameImage | None:
        if not self._opened:
            raise EdgeError(ErrorCode.CAPTURE, f"摄像头未打开: {self._deviceAddr}")
        try:
            return self._frameReader()
        except EdgeError:
            raise
        except (OSError, ValueError, TimeoutError) as error:
            ## 内置异常跨模块边界前统一转业务异常
            raise EdgeError(ErrorCode.CAPTURE, f"取图失败: {self._deviceAddr}: {error}") from error

    ## @brief 关闭设备
    #  @return 无
    def close(self) -> None:
        self._opened = False

    ## @brief 返回状态快照
    #  @return 状态字典
    def getStatus(self) -> CameraStatus:
        status: CameraStatus = {
            "deviceAddr": self._deviceAddr,
            "backend": self._backend,
            "opened": self._opened,
        }
        return status


## @brief 摄像头工厂；Windows 索引与 Linux 固定路径的寻址差异收敛在此
class CameraFactory:
    ## @brief 按地址形态创建设备
    #  @param deviceAddr 设备地址
    #  @param frameReader 帧读取回调
    #  @param logger 可选日志器
    #  @return 摄像头设备实例
    @staticmethod
    def createDevice(deviceAddr: str, frameReader: FrameReader,
                     logger: ILogger | None = None) -> CameraDevice:
        ## 纯数字视为 Windows 索引，其余视为 Linux 固定路径
        isIndex = bool(deviceAddr) and all(char in INDEX_CHARS for char in deviceAddr)
        backend = BACKEND_DSHOW if isIndex else BACKEND_V4L2
        return CameraDevice(deviceAddr, backend, frameReader, logger)
