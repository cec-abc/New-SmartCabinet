"""USB 摄像头设备与工厂：按地址形态选后端，对焦与变焦指令收敛在设备层。"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Event, Lock
from typing import Any

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import CameraStatus, FrameImage, ICameraDevice
from edge.interfaces.i_camera_focus import ICameraFocus
from edge.interfaces.i_logger import ILogger

## @file edge/modules/usb/usb_camera_device.py
## @brief USB 摄像头设备与工厂：按地址形态选后端，对焦指令收敛在设备层
## @author 袁燕

## @brief Windows 后端标识：索引 + CAP_DSHOW
BACKEND_DSHOW = "CAP_DSHOW"
## @brief Linux 后端标识：固定路径 + CAP_V4L2（麒麟 / RK3588 真实后端）
BACKEND_V4L2 = "CAP_V4L2"
## @brief Windows 摄像头索引个数上限（用于地址形态判定）
INDEX_CHARS = frozenset("0123456789")
## @brief 设备绝对焦点位置下限
FOCUS_POSITION_MIN: float = 0.0
## @brief 设备绝对焦点位置上限，以现场实测为准
FOCUS_POSITION_MAX: float = 125.0
## @brief 设备绝对变焦位置下限
ZOOM_POSITION_MIN: float = 0.0
## @brief 设备绝对变焦位置上限，以现场实测为准
ZOOM_POSITION_MAX: float = 1020.0
## @brief 日志模块名
MODULE_NAME: str = "UsbCameraDevice"
## @brief 图像处理库静默日志级别：0 表示不输出原生日志
IMAGE_LIBRARY_LOG_LEVEL_SILENT: int = 0
## @brief 打开相机动作的串行锁：保证临时压日志期间不被并发打开穿插
CAMERA_OPEN_LOCK: Lock = Lock()
## @brief 帧来源：真实相机，open 时建采集句柄，readFrame 真取帧并编码
FRAME_SOURCE_CAMERA: str = "camera"
## @brief 帧来源：占位图，走注入的帧读取器，不碰硬件
FRAME_SOURCE_PLACEHOLDER: str = "placeholder"
## @brief 合法帧来源取值
FRAME_SOURCES: tuple[str, ...] = (FRAME_SOURCE_CAMERA, FRAME_SOURCE_PLACEHOLDER)
## @brief 真实抓帧的 JPEG 编码后缀
JPEG_EXTENSION: str = ".jpg"
## @brief 真实取图重试次数：设备刚起流时首帧可能未就绪
REAL_CAPTURE_ATTEMPTS: int = 3
## @brief 真实取图两次尝试之间的等待秒数
REAL_CAPTURE_RETRY_SEC: float = 0.05
## @brief 真实抓帧重试共用的等待对象；只做短超时等待，不置位，也不参与线程停机
RETRY_WAIT_EVENT: Event = Event()

## @brief 帧读取回调，真实采集后端由上层注入，本模块不引入硬件依赖
FrameReader = Callable[[], "FrameImage | None"]
## @brief 对焦属性写入回调，参数为（属性号, 属性值）
FocusPropertySetter = Callable[[int, float], None]
## @brief 可达性探测回调；返回 True 表示设备真的能打开并发图
ReachabilityProbe = Callable[[], bool]


## @brief 载入图像处理库的日志级别接口；缺库或缺接口时返回 None
#  @return 日志接口模块；不可用时返回 None
def _loadImageLibraryLogging() -> Any | None:
    try:
        ## 图像处理库是可选依赖，只能在函数体内导入
        from cv2.utils import logging  # type: ignore
        return logging
    except (ImportError, AttributeError):
        ## 没装图像处理库或该版本没有日志接口时不压日志，缺库问题由调用方按业务异常上报
        return None


## @brief 打开相机的动作期间压掉图像处理库的原生日志
#  @return 上下文管理器；进入期间图像处理库不输出原生日志，退出后恢复原日志级别
#  @note 只覆盖“打开相机”这一小段，识别推理阶段的图像处理库日志照常可见；
#        取级别、设级别、恢复级别都在同一把锁内，不会与别的打开动作穿插
@contextmanager
def quietImageLibraryLog() -> Iterator[None]:
    imageLogging = _loadImageLibraryLogging()
    if imageLogging is None:
        yield
        return
    with CAMERA_OPEN_LOCK:
        previousLevel: int = imageLogging.getLogLevel()
        try:
            imageLogging.setLogLevel(IMAGE_LIBRARY_LOG_LEVEL_SILENT)
            yield
        finally:
            ## 恢复动作自己报错时不能盖掉打开相机的真实异常；日志级别只影响原生日志
            ## 是否输出，不影响图像采集结果，所以这里只吞掉恢复自身的异常
            try:
                imageLogging.setLogLevel(previousLevel)
            except Exception:
                pass


## @brief 摄像头设备实现；帧来源、关闭动作与对焦、变焦写入全部构造注入
class CameraDevice(ICameraDevice, ICameraFocus):
    ## @brief 构造设备
    #  @param deviceAddr 设备地址：Windows 写索引、Linux 写 /dev/... 固定路径
    #  @param backend 后端标识
    #  @param frameReader 帧读取回调，占位帧源时使用
    #  @param logger 可选日志器
    #  @param focusPropertySetter 对焦属性写入回调，持有真实采集句柄的上层注入
    #  @param reachabilityProbe 可达性探测回调，为空表示不探测，设备可达性无法确认
    #  @param frameSource 帧来源：camera 用真实采集句柄取帧，placeholder 用注入的读取器
    #  @return 无
    def __init__(self, deviceAddr: str, backend: str, frameReader: FrameReader,
                 logger: ILogger | None = None,
                 focusPropertySetter: FocusPropertySetter | None = None,
                 reachabilityProbe: ReachabilityProbe | None = None,
                 frameSource: str = FRAME_SOURCE_PLACEHOLDER) -> None:
        ## @brief 设备地址
        self._deviceAddr: str = deviceAddr
        ## @brief 后端标识
        self._backend: str = backend
        ## @brief 帧读取回调
        self._frameReader: FrameReader = frameReader
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief 对焦属性写入回调
        self._focusPropertySetter: FocusPropertySetter | None = focusPropertySetter
        ## @brief 可达性探测回调
        self._reachabilityProbe: ReachabilityProbe | None = reachabilityProbe
        ## @brief 帧来源
        self._frameSource: str = frameSource
        ## @brief 真实采集句柄；占位帧源时恒为 None
        self._capture: Any | None = None
        ## @brief 是否已打开
        self._opened: bool = False
        ## @brief 是否成功打开过，关闭后仍保留，供状态快照判断离线与否
        self._everOpened: bool = False
        ## @brief 通信是否正常，取图失败后置否
        self._commOk: bool = True
        ## @brief 是否成功取到过图像
        self._everCaptured: bool = False
        ## @brief 当前设备绝对焦点位置
        self._focusPosition: float = FOCUS_POSITION_MIN
        ## @brief 当前设备绝对变焦位置
        self._zoomPosition: float = ZOOM_POSITION_MIN
        ## @brief 是否已成功下发过对焦指令，供状态快照判断对焦是否生效
        self._focusApplied: bool = False

    ## @brief 打开设备；真实帧源时建立采集句柄，探测到设备不可达时按采集失败阻断
    #  @return 无
    #  @raises EdgeError 设备不可达或未装图像处理库时抛出，code=CAPTURE
    def open(self) -> None:
        self.confirmReachable()
        if self._frameSource == FRAME_SOURCE_CAMERA:
            self.openDeviceCapture()
        self._opened = True
        self._everOpened = True

    ## @brief 探测设备是否真的可达；探测不到就按不可达处理
    #  @return 无
    #  @raises EdgeError 设备不可达时抛出，code=CAPTURE
    def confirmReachable(self) -> None:
        probe = self._reachabilityProbe
        if probe is None:
            ## 没配探测回调时无法确认可达性，按原骨架行为放行
            return
        if not probe():
            raise EdgeError(
                ErrorCode.CAPTURE, f"相机打开失败: {self._deviceAddr}",
            )

    ## @brief 建立真实采集句柄；Linux 走固定路径 + CAP_V4L2，Windows 走数字索引 + CAP_DSHOW
    #  @return 无
    #  @raises EdgeError 未装图像处理库、地址非法或打开失败时抛出，code=CAPTURE
    def openDeviceCapture(self) -> None:
        imageLibrary = self._loadImageLibrary()
        if self._backend == BACKEND_V4L2:
            ## 麒麟 / RK3588：设备地址形如 /dev/video0，按节点 + V4L2 后端打开
            with quietImageLibraryLog():
                capture = imageLibrary.VideoCapture(self._deviceAddr, imageLibrary.CAP_V4L2)
            if not capture.isOpened():
                capture.release()
                raise EdgeError(ErrorCode.CAPTURE, f"摄像头打开失败: {self._deviceAddr}")
            self.releaseDeviceCapture()
            self._capture = capture
            return
        try:
            index = int(self._deviceAddr)
        except ValueError as error:
            raise EdgeError(
                ErrorCode.CAPTURE, f"真实采集需要数字索引: {self._deviceAddr}",
            ) from error
        ## 打开相机这一小段压掉图像处理库的原生日志，没接相机时也不刷屏
        with quietImageLibraryLog():
            capture = imageLibrary.VideoCapture(index, imageLibrary.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            raise EdgeError(ErrorCode.CAPTURE, f"摄像头打开失败: {self._deviceAddr}")
        self.releaseDeviceCapture()
        self._capture = capture

    ## @brief 读取一帧；真实帧源抓真相机帧并编码为 JPEG，占位帧源走注入读取器
    #  @return 图像字节；占位帧源暂无帧返回 None
    #  @raises EdgeError 设备未打开、抓帧失败或读取器抛内置异常时抛出，code=CAPTURE
    def readFrame(self) -> FrameImage | None:
        if not self._opened:
            raise EdgeError(ErrorCode.CAPTURE, f"摄像头未打开: {self._deviceAddr}")
        if self._frameSource == FRAME_SOURCE_CAMERA:
            return self.grabDeviceFrame()
        try:
            frame = self._frameReader()
        except EdgeError:
            ## 帧读取器已经报了业务异常，同样把该路记成通信异常，状态里不许报正常
            self._commOk = False
            raise
        except Exception as error:
            ## 帧读取器抛出的任何内置异常都在模块内转业务异常，并置通信异常
            self._commOk = False
            raise EdgeError(ErrorCode.CAPTURE, f"取图失败: {self._deviceAddr}: {error}") from error
        if frame is None:
            ## 取不到图像说明这路已经不出图，按通信异常处理，不许继续报正常
            self._commOk = False
            return None
        self._everCaptured = True
        return frame

    ## @brief 真实抓一帧并编码成 JPEG 字节；抓不到就明确报错，不静默返回空
    #  @return JPEG 图像字节
    #  @raises EdgeError 句柄未就绪、抓帧失败或编码失败时抛出，code=CAPTURE
    def grabDeviceFrame(self) -> FrameImage:
        imageLibrary = self._loadImageLibrary()
        capture = self._capture
        if capture is None:
            raise EdgeError(ErrorCode.CAPTURE, f"采集句柄未就绪: {self._deviceAddr}")
        frame: Any | None = None
        try:
            for _attempt in range(REAL_CAPTURE_ATTEMPTS):
                grabbed, raw = capture.read()
                if grabbed and raw is not None:
                    frame = raw
                    break
                ## 首帧可能因设备刚起流而失败，短等一下再试；复用等待对象，不每帧新建
                RETRY_WAIT_EVENT.wait(REAL_CAPTURE_RETRY_SEC)
            if frame is None:
                self._commOk = False
                raise EdgeError(ErrorCode.CAPTURE, f"取图失败: {self._deviceAddr}")
            encodedOk, encoded = imageLibrary.imencode(JPEG_EXTENSION, frame)
        except EdgeError:
            raise
        except (OSError, ValueError, RuntimeError) as error:
            ## 图像处理库抛出的内置异常不跨模块边界，统一转业务异常
            self._commOk = False
            raise EdgeError(ErrorCode.CAPTURE, f"取图失败: {self._deviceAddr}: {error}") from error
        if not encodedOk:
            self._commOk = False
            raise EdgeError(ErrorCode.CAPTURE, f"帧编码失败: {self._deviceAddr}")
        self._everCaptured = True
        return bytes(encoded.tobytes())

    ## @brief 释放真实采集句柄，重复调用安全
    #  @return 无
    def releaseDeviceCapture(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    ## @brief 关闭设备；真实帧源同时释放采集句柄
    #  @return 无
    def close(self) -> None:
        self.releaseDeviceCapture()
        self._opened = False

    ## @brief 返回状态快照
    #  @return 状态字典
    def getStatus(self) -> CameraStatus:
        status: CameraStatus = {
            "deviceAddr": self._deviceAddr,
            "backend": self._backend,
            "frameSource": self._frameSource,
            "opened": self._opened,
            "everOpened": self._everOpened,
            "commOk": self._commOk,
            "everCaptured": self._everCaptured,
            "focusPosition": self._focusPosition,
            "focusApplied": self._focusApplied,
        }
        return status

    ## @brief 开关自动对焦；Windows 侧走图像处理库的自动对焦属性
    #  @param enabled True 开自动对焦，False 关自动对焦
    #  @return 无
    #  @raises EdgeError 未装图像处理库或指令下发失败时抛出，code=CAPTURE
    def setAutoFocus(self, enabled: bool) -> None:
        if not self._opened:
            ## 设备还没打开，对焦指令下不去，这里只记一条说明并跳过，不另开采集句柄
            self._logDeviceInfo(f"设备未打开，无法下发对焦: {self._deviceAddr}")
            return
        imageLibrary = self._loadImageLibrary()
        self._setCameraControlProperty(
            imageLibrary.CAP_PROP_AUTOFOCUS,
            1.0 if enabled else 0.0,
            "自动对焦",
        )
        self._focusApplied = True

    ## @brief 设置设备绝对焦点位置；Windows 侧走图像处理库的绝对焦点属性
    #  @param position 设备绝对焦点值，范围由 FOCUS_POSITION_MIN/MAX 约束（0~125，实测为准）
    #  @return 无
    #  @raises EdgeError 位置越界、未装图像处理库或指令下发失败时抛出，code=CONFIG / CAPTURE
    def setFocusPosition(self, position: float) -> None:
        if position < FOCUS_POSITION_MIN or position > FOCUS_POSITION_MAX:
            raise EdgeError(ErrorCode.CONFIG, f"焦点位置越界: {position}")
        if not self._opened:
            ## 设备还没打开，对焦指令下不去，这里只记一条说明并跳过，不另开采集句柄
            self._logDeviceInfo(f"设备未打开，无法下发对焦: {self._deviceAddr}")
            return
        imageLibrary = self._loadImageLibrary()
        self._setCameraControlProperty(
            self._focusPositionPropertyId(imageLibrary),
            position,
            "对焦",
        )
        self._focusPosition = min(max(position, FOCUS_POSITION_MIN), FOCUS_POSITION_MAX)
        self._focusApplied = True

    ## @brief 读取当前设备绝对焦点位置
    #  @return 设备绝对焦点值
    def getFocusPosition(self) -> float:
        return min(max(self._focusPosition, FOCUS_POSITION_MIN), FOCUS_POSITION_MAX)

    ## @brief 设置设备绝对变焦位置；改变视野范围，多数定焦 USB 摄像头硬件不支持
    #  @param position 设备绝对变焦值，合法范围由 ZOOM_POSITION_MIN/MAX 约束（0~1020，以实测为准）
    #  @return 无
    #  @raises EdgeError 位置越界、未装图像处理库或指令下发失败时抛出，code=CONFIG / CAPTURE
    def setZoomPosition(self, position: float) -> None:
        if position < ZOOM_POSITION_MIN or position > ZOOM_POSITION_MAX:
            raise EdgeError(ErrorCode.CONFIG, f"变焦位置越界: {position}")
        if not self._opened:
            ## 设备还没打开，变焦指令下不去，这里只记一条说明并跳过，不另开采集句柄
            self._logDeviceInfo(f"设备未打开，无法下发变焦: {self._deviceAddr}")
            return
        imageLibrary = self._loadImageLibrary()
        self._setCameraControlProperty(self._zoomPositionPropertyId(imageLibrary), position, "变焦")
        self._zoomPosition = min(max(position, ZOOM_POSITION_MIN), ZOOM_POSITION_MAX)

    ## @brief 读取当前设备绝对变焦位置
    #  @return 变焦位置
    def getZoomPosition(self) -> float:
        return min(max(self._zoomPosition, ZOOM_POSITION_MIN), ZOOM_POSITION_MAX)

    ## @brief 取变焦位置属性号；该版本图像处理库缺变焦属性时明确报错，由调用方先探测能力
    #  @param imageLibrary 图像处理库模块
    #  @return 属性号
    #  @raises EdgeError 图像处理库没有变焦属性时抛出，code=CAPTURE
    def _zoomPositionPropertyId(self, imageLibrary: Any) -> int:
        zoomId = getattr(imageLibrary, "CAP_PROP_ZOOM", None)
        if zoomId is not None:
            return int(zoomId)
        raise EdgeError(ErrorCode.CAPTURE, "该图像处理库不支持变焦属性 CAP_PROP_ZOOM")

    ## @brief 载入图像处理库；未安装时按可选依赖缺失抛业务异常
    #  @return 图像处理库模块
    #  @raises EdgeError 未安装图像处理库时抛出，code=CAPTURE
    def _loadImageLibrary(self) -> Any:
        try:
            ## 图像处理库是可选依赖，只能在函数体内导入
            import cv2  # type: ignore
        except ImportError as error:
            raise EdgeError(ErrorCode.CAPTURE, "未安装图像处理库 opencv-python") from error
        return cv2

    ## @brief 取焦点位置属性号；优先绝对焦点属性，版本缺该属性时退回相对焦点属性
    #  @param imageLibrary 图像处理库模块
    #  @return 属性号
    def _focusPositionPropertyId(self, imageLibrary: Any) -> int:
        absoluteId = getattr(imageLibrary, "CAP_PROP_FOCUS_ABSOLUTE", None)
        if absoluteId is not None:
            return int(absoluteId)
        return int(imageLibrary.CAP_PROP_FOCUS)

    ## @brief 写入控制属性（对焦 / 变焦通用）；优先用注入能力，缺失时临时开采集句柄下发
    #  @param propertyId 属性号
    #  @param value 属性值
    #  @param controlName 控制名标签：仅用于报错文案，说明正在下发的是哪一种控制
    #  @return 无
    #  @raises EdgeError 索引非法、设备打不开或指令下发失败时抛出，code=CONFIG / CAPTURE
    def _setCameraControlProperty(self, propertyId: int, value: float, controlName: str) -> None:
        if self._focusPropertySetter is not None:
            ## 上层持有真实采集句柄时由上层写属性，设备层不再另开句柄
            self._focusPropertySetter(propertyId, value)
            return
        if self._capture is not None:
            ## 已经握着真实采集句柄，直接写它，避免对同一路相机再开一个句柄
            if not bool(self._capture.set(propertyId, value)):
                raise EdgeError(ErrorCode.CAPTURE, f"{controlName}指令下发失败: {self._deviceAddr}")
            return
        if self._frameSource == FRAME_SOURCE_PLACEHOLDER:
            ## 占位帧源没有真实采集句柄；为它去开一次真相机，在没接相机的现场会
            ## 长时间卡住采集线程。这里明确判失败，由门面汇总成一条控制未生效日志
            raise EdgeError(
                ErrorCode.CAPTURE,
                f"占位帧源没有真实采集句柄, 无法下发{controlName}: {self._deviceAddr}",
            )
        imageLibrary = self._loadImageLibrary()
        try:
            index = int(self._deviceAddr)
        except ValueError as error:
            raise EdgeError(ErrorCode.CONFIG, f"摄像头索引非法: {self._deviceAddr}") from error
        applied: bool = False
        ## 设备已经打开才走到这里，这时临时开一个采集句柄下发控制；
        ## 打开动作压掉原生日志，现场没接相机时也不刷屏
        with quietImageLibraryLog():
            capture = imageLibrary.VideoCapture(index, imageLibrary.CAP_DSHOW)
            try:
                if not capture.isOpened():
                    raise EdgeError(ErrorCode.CAPTURE, f"摄像头打开失败: {self._deviceAddr}")
                applied = bool(capture.set(propertyId, value))
            finally:
                capture.release()
        if not applied:
            raise EdgeError(ErrorCode.CAPTURE, f"{controlName}指令下发失败: {self._deviceAddr}")

    ## @brief 记一条设备级说明日志
    #  @param message 日志内容
    #  @return 无
    def _logDeviceInfo(self, message: str) -> None:
        if self._logger is None:
            return
        self._logger.info(MODULE_NAME, message)


## @brief 摄像头工厂；Windows 索引与 Linux 固定路径的寻址差异收敛在此
class CameraFactory:
    ## @brief 按地址形态创建设备
    #  @param deviceAddr 设备地址
    #  @param frameReader 帧读取回调
    #  @param logger 可选日志器
    #  @param focusPropertySetter 对焦属性写入回调
    #  @param reachabilityProbe 可达性探测回调，为空表示不探测
    #  @param frameSource 帧来源：camera 真取帧，placeholder 用注入读取器
    #  @return 摄像头设备实例
    @staticmethod
    def createDevice(deviceAddr: str, frameReader: FrameReader,
                    logger: ILogger | None = None,
                    focusPropertySetter: FocusPropertySetter | None = None,
                    reachabilityProbe: ReachabilityProbe | None = None,
                    frameSource: str = FRAME_SOURCE_PLACEHOLDER) -> CameraDevice:
        ## 纯数字视为 Windows 索引，其余视为 Linux 固定路径
        isIndex = bool(deviceAddr) and all(char in INDEX_CHARS for char in deviceAddr)
        backend = BACKEND_DSHOW if isIndex else BACKEND_V4L2
        if frameSource not in FRAME_SOURCES:
            raise EdgeError(ErrorCode.CONFIG, f"帧来源配置非法: {frameSource}")
        return CameraDevice(
            deviceAddr, backend, frameReader, logger, focusPropertySetter,
            reachabilityProbe, frameSource,
        )
