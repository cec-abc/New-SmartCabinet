"""应用装配：只做 new + 注入 + 返回，不写业务流程。"""
from __future__ import annotations

import atexit
import inspect
import math
import shutil
import struct
import sys
import zlib
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from threading import BoundedSemaphore, Event, Lock
from time import monotonic
from typing import Any

from edge.control.edge_control import (
    DEFAULT_AGGREGATION_TIMEOUT_SEC,
    STOP_LOG,
    STOP_RECOGNITION,
    STOP_TCP,
    STOP_USB,
    WIRE_REQUEST_ID_KEY,
    AsyncHandler,
    CachedEvent,
    DegradedItemsProvider,
    EdgeControl,
    FailureFrameBuilder,
    FrameSender,
    ModuleWiring,
)
from edge.control.edge_dispatch_thread import EdgeDispatchThread
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.config_manager import IniConfigManager
from edge.infra.log_manager import LogManager
from edge.infra.roi_binding_loader import (
    DEFAULT_CONFIDENCE,
    RoiBindingLoader,
    RoiBindingRow,
)
from edge.interfaces.i_camera import FrameImage, ICameraDevice
from edge.interfaces.i_config import IConfig
from edge.interfaces.i_frame_sink import IFrameSink
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.interfaces.i_sinks import DecodedSignal, ICaptureSink
from edge.interfaces.i_socket import ISocket
from edge.modules.recognition.recognition_controller import RecognitionController
from edge.modules.recognition.recognition_stitcher import (
    FrameStitcher,
    buildFrameStitcher,
)
from edge.modules.recognition.recognition_utils import (
    ALERT_UNKNOWN,
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
    buildAckItem,
)
from edge.modules.recognition.recognition_yolo_engine import (
    DEFAULT_BACKEND as DEFAULT_INFERENCE_BACKEND,
)
from edge.modules.recognition.recognition_yolo_engine import (
    DEFAULT_NMS_IOU_THRESHOLD,
    YoloEngine,
)
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.tcp.tcp_control_layer import LINK_UP, TcpControlLayer
from edge.modules.tcp.tcp_socket import TcpSocket
from edge.modules.usb.usb_camera_device import (
    FRAME_SOURCE_CAMERA,
    FRAME_SOURCE_PLACEHOLDER,
    FRAME_SOURCES,
    CameraFactory,
    quietImageLibraryLog,
)
from edge.modules.usb.usb_controller import UsbController

## @file edge/app_init.py
## @brief 应用装配：只做 new + 注入 + 返回，不写业务流程
## @author 袁燕

## @brief 边缘机工程目录；本文件所在目录，即 edge/
EDGE_MODULE_DIR: Path = Path(__file__).resolve().parent
## @brief 仓库根目录；边缘机工程目录的上一级
REPO_ROOT_DIR: Path = EDGE_MODULE_DIR.parent
## @brief 默认配置文件路径，按边缘机工程目录自锚定，与运行时工作目录无关
DEFAULT_CONFIG_PATH: str = str(EDGE_MODULE_DIR / "config" / "config.ini")
## @brief 配置文件所在的固定位置，报错信息里给用户指路用
CONFIG_FILE_HINT: str = "edge/config/config.ini"
## @brief 类别组合表文件名，与 ROI 对照表同目录
CLASS_ITEM_MAP_FILE_NAME: str = "class_item_map.csv"
## @brief 骨架占位图的宽，单位像素
PLACEHOLDER_FRAME_WIDTH: int = 640
## @brief 骨架占位图的高，单位像素
PLACEHOLDER_FRAME_HEIGHT: int = 480
## @brief 骨架占位图的灰度值
PLACEHOLDER_FRAME_GRAY: int = 200
## @brief 链路启动器（注入，便于测试替换线程启动）
LinkStarter = Callable[[TcpControlLayer], None]
## @brief 识别请求的信号键（协议原文）
RECOGNIZE_REQ_TYPE: str = "recognize_req"
## @brief 周期帧类型（协议原文 periodic，不是 heartbeat）
PERIODIC_FRAME_TYPE: str = "periodic"
## @brief 软件版本号，写入周期帧
SOFTWARE_VERSION: str = "edge-0.1.0"
## @brief 应答排空周期秒
DEFAULT_DISPATCH_INTERVAL_SEC: float = 0.2
## @brief 采集门面构造参数名：对焦模式
USB_FOCUS_MODE_PARAM: str = "focusMode"
## @brief 采集门面构造器类型；是否接受扩展参数由构造签名探测决定
UsbBuilder = Callable[..., UsbController]
## @brief 摄像头可达性探测的尝试次数
CAMERA_PROBE_ATTEMPTS: int = 2
## @brief 摄像头可达性探测两次尝试之间的等待秒数
CAMERA_PROBE_RETRY_SEC: float = 0.2
## @brief 日志模块名
MODULE_NAME: str = "AppInit"
## @brief 采集模式配置项名称
CAPTURE_MODE_KEY: str = "capture_mode"
## @brief 帧来源配置项名称
FRAME_SOURCE_KEY: str = "frame_source"
## @brief 自动模式：1 路走单摄，偶数路走双摄，奇数路（3 及以上）明确报错
CAPTURE_MODE_AUTO: str = "auto"
## @brief 强制双摄模式
CAPTURE_MODE_DUAL: str = "dual"
## @brief 强制单摄模式
CAPTURE_MODE_SINGLE: str = "single"
## @brief 合法采集模式取值
CAPTURE_MODES: tuple[str, ...] = (
    CAPTURE_MODE_AUTO, CAPTURE_MODE_DUAL, CAPTURE_MODE_SINGLE,
)
## @brief 采集落盘开关键名；关闭时采集帧只走内存回调、不写单图
SAVE_FRAMES_KEY: str = "save_frames"
## @brief 拼接全景落盘开关键名；开启时每组全景写入识别目录供调试标 ROI
SAVE_PANORAMA_KEY: str = "save_panorama"
## @brief 逐路焦点配置键名；8 个值按 CAM1~CAM8 顺序
FOCUS_POSITIONS_KEY: str = "focus_positions"
## @brief 逐路变焦配置键名；8 个值按 CAM1~CAM8 顺序
ZOOM_POSITIONS_KEY: str = "zoom_positions"
## @brief 定焦后镜头稳定等待毫秒数配置键名
FOCUS_STABLE_MS_KEY: str = "focus_stable_ms"
## @brief 逐路光学配置的默认路数，与整柜相机数一致
OPTICAL_VALUE_COUNT: int = 8
## @brief 层模式配置项名称；单层=工装单抽屉 2 路相机，多层=常态 8 路相机
LAYER_MODE_KEY: str = "layer_mode"
## @brief 多层（默认）：按 camera_indices 实际路数分组为多个 worker
LAYER_MODE_MULTI: str = "multi"
## @brief 单层（工装测试）：只取前 2 路相机，强制构成 1 个双摄 worker
LAYER_MODE_SINGLE: str = "single"
## @brief 合法层模式取值
LAYER_MODES: tuple[str, ...] = (LAYER_MODE_MULTI, LAYER_MODE_SINGLE)
## @brief 单摄模式的相机索引个数
SINGLE_CAMERA_INDEX_COUNT: int = 1
## @brief camera_indices 允许的最小个数
MIN_CAMERA_INDEX_COUNT: int = 1
## @brief camera_indices 允许的最大个数
MAX_CAMERA_INDEX_COUNT: int = 8
## @brief 相机索引配置项名称
CAMERA_INDICES_KEY: str = "camera_indices"
## @brief 对照表工作线程编号的下界，编号从 1 起
MIN_WORKER_ID: int = 1
## @brief 双摄一组的相机台数
DUAL_CAMERA_PAIR_SIZE: int = 2
## @brief 占位图 PNG 的位深，灰度图固定 8 位
PLACEHOLDER_PNG_BIT_DEPTH: int = 8
## @brief 占位图 PNG 的压缩级别，取标准库最高级
PLACEHOLDER_PNG_COMPRESSION_LEVEL: int = 9
## @brief PNG 校验和按 32 位无符号数取值
PNG_CRC32_MASK: int = 0xFFFFFFFF
## @brief 识别查表配置：识别改走 ROI 对照表文件，装配时固定传空字典
EMPTY_ROI_CONFIG: RoiConfig = {}
## @brief 类别到物品名映射：识别改走对照表文件，装配时固定传空字典
EMPTY_CLASS_ITEM_MAP: ClassItemMap = {}
## @brief ROI 到物品名绑定：识别改走对照表文件，装配时固定传空字典
EMPTY_ROI_BIND_MAP: RoiBindMap = {}


## @brief 未绑定采集门面时的占位动作
#  @param requestId 请求标识
#  @return 恒为 False
def rejectCaptureRequest(requestId: str) -> bool:
    return False


## @brief 未绑定摄像头状态时的占位读取
#  @return 空列表
def emptyCameraStatus() -> list[dict[str, object]]:
    return []


## @brief 采集触发句柄：装配期绑定真实采集门面，业务期只调用
class CaptureTrigger:
    ## @brief 构造；未绑定时触发恒失败
    #  @return 无
    def __init__(self) -> None:
        ## @brief 绑定的采集动作
        self._action: Callable[[str], bool] = rejectCaptureRequest

    ## @brief 绑定采集动作
    #  @param action 采集动作（注入）
    #  @return 无
    def bind(self, action: Callable[[str], bool]) -> None:
        self._action = action

    ## @brief 触发一次扫描
    #  @param requestId 上位机请求标识
    #  @return 触发成功返回 True
    def triggerCapture(self, requestId: str) -> bool:
        return self._action(requestId)


## @brief 摄像头状态句柄：装配期绑定真实采集门面，业务期只调用
class CameraStatusHandle:
    ## @brief 构造；未绑定时返回空状态列表
    #  @return 无
    def __init__(self) -> None:
        ## @brief 绑定的状态读取动作
        self._reader: Callable[[], list[dict[str, object]]] = emptyCameraStatus

    ## @brief 绑定状态读取动作
    #  @param reader 状态读取动作（注入）
    #  @return 无
    def bindReader(self, reader: Callable[[], list[dict[str, object]]]) -> None:
        self._reader = reader

    ## @brief 读取摄像头状态
    #  @return 摄像头状态列表
    def readStatus(self) -> list[dict[str, object]]:
        return self._reader()


## @brief 未绑定识别能力时的空应答出口占位
#  @param requestId 请求标识
#  @return 无
def ignoreEmptyAck(requestId: str) -> None:
    return None


## @brief 识别能力句柄：装配期判定可用性并绑定空清单应答出口，业务期只查询与触发
class RecognitionCapability:
    ## @brief 构造；默认识别能力可用
    #  @return 无
    def __init__(self) -> None:
        ## @brief 识别能力是否可用
        self._available: bool = True
        ## @brief 空清单应答出口，装配期绑定控制层
        self._emptyAckEmitter: Callable[[str], None] = ignoreEmptyAck

    ## @brief 标记识别能力不可用；进程照常启动，识别请求只回空清单
    #  @return 无
    def markUnavailable(self) -> None:
        self._available = False

    ## @brief 查询识别能力是否可用
    #  @return 可用返回 True
    def isAvailable(self) -> bool:
        return self._available

    ## @brief 绑定空清单应答出口
    #  @param emitter 空应答发送动作（注入）
    #  @return 无
    def bindEmptyAckEmitter(self, emitter: Callable[[str], None]) -> None:
        self._emptyAckEmitter = emitter

    ## @brief 按识别可用性决定请求出口：不可用回空清单，可用则触发采集
    #  @param requestId 上位机请求标识
    #  @param trigger 采集触发句柄（注入）
    #  @return 无
    def routeCapture(self, requestId: str, trigger: CaptureTrigger) -> None:
        if not self._available:
            ## 识别能力不可用时立刻回空清单，让上位机马上看到结果而非干等重发超时
            self._emptyAckEmitter(requestId)
            return
        trigger.triggerCapture(requestId)


## @brief 全部构造注入参数集合；app_init 不读全局状态、不做业务判断
@dataclass
class AssemblyParts:
    ## @brief 日志器
    logger: ILogger
    ## @brief 套接字
    socket: ISocket
    ## @brief 每个采集线程的相机组，单摄 1 路、双摄 2 路
    cameraPairs: Sequence[tuple[ICameraDevice, ...]]
    ## @brief 采集目录
    captureDirs: list[str]
    ## @brief 识别目录
    recognitionDirs: list[str]
    ## @brief 推理引擎
    engine: IRecognitionEngine
    ## @brief 模型路径
    modelPath: str
    ## @brief 左右图读取器
    frameLoader: FrameLoader
    ## @brief 推理超时执行器
    timeoutRunner: TimeoutRunner
    ## @brief 推理超时秒数
    inferTimeoutSec: float
    ## @brief ROI 配置
    roiConfig: RoiConfig
    ## @brief 类别映射
    classItemMap: ClassItemMap
    ## @brief ROI 绑定表
    roiBindMap: RoiBindMap
    ## @brief 滚动删旧阈值
    rollThreshold: float
    ## @brief 磁盘占用比例提供器
    usageRatio: Callable[[], float]
    ## @brief 时间戳提供器
    clock: Callable[[], str]
    ## @brief 退避序列
    backoffSeq: list[float]
    ## @brief 单帧字节上限
    maxFrameSize: int
    ## @brief 心跳周期秒
    heartIntervalSec: float
    ## @brief 心跳帧构造器
    buildHeartbeat: Callable[[], dict[str, object]]
    ## @brief 注入的信号键到处理器映射
    asyncHandlers: dict[str, AsyncHandler]
    ## @brief 失败应答构造器
    failureFrameBuilder: FailureFrameBuilder
    ## @brief 帧发送器
    frameSender: FrameSender
    ## @brief 链路启动器
    linkStarter: LinkStarter
    ## @brief 日志消费者启动器
    logStarter: Callable[[], None]
    ## @brief 日志消费者停机器
    logStopper: Callable[[], None]
    ## @brief 摄像头索引列表（8 路）
    cameraIndices: list[int] = field(default_factory=list)
    ## @brief 按相机索引排序的设备列表
    cameraDevices: list[ICameraDevice] = field(default_factory=list)
    ## @brief 对焦模式：auto 或 fixed
    focusMode: str = "fixed"
    ## @brief 焦点位置（旧单值字段，保留兼容；新装配用 focusPositions）
    focusPosition: float = 0.0
    ## @brief 逐路焦点位置，下标 = 物理路号 - 1
    focusPositions: list[float] = field(default_factory=list)
    ## @brief 逐路变焦位置，下标 = 物理路号 - 1
    zoomPositions: list[float] = field(default_factory=list)
    ## @brief 定焦后镜头稳定等待毫秒数
    focusStableMs: int = 200
    ## @brief ROI 对照表路径
    roiBindingCsv: str = ""
    ## @brief ROI 对照表行，装配期装载后注入识别门面
    roiBindingRows: list[RoiBindingRow] | None = None
    ## @brief 类别组合到物品名映射，装配期装载后注入识别门面
    classItemComboMap: dict[frozenset[str], str] | None = None
    ## @brief 拼接裁剪器，装配期构造后注入识别门面
    stitcher: FrameStitcher | None = None
    ## @brief 采集触发句柄，装配期绑定真实采集门面
    captureTrigger: CaptureTrigger = field(default_factory=CaptureTrigger)
    ## @brief 摄像头状态句柄，装配期绑定真实采集门面
    cameraStatus: CameraStatusHandle = field(default_factory=CameraStatusHandle)
    ## @brief 识别能力句柄，装配期判定对照表是否装载成功
    recognitionCapability: RecognitionCapability = field(
        default_factory=RecognitionCapability,
    )
    ## @brief 应答排空周期秒
    dispatchIntervalSec: float = DEFAULT_DISPATCH_INTERVAL_SEC
    ## @brief 聚合等待上限秒数，超过该时长仍未收齐就降级出帧
    aggregationTimeoutSec: float = DEFAULT_AGGREGATION_TIMEOUT_SEC
    ## @brief 配置里的 capture_mode 原值
    captureMode: str = CAPTURE_MODE_AUTO
    ## @brief 装配期判定的最终采集模式：single 或 dual
    resolvedCaptureMode: str = CAPTURE_MODE_DUAL
    ## @brief 帧来源：camera 真取帧，placeholder 用占位图
    frameSource: str = FRAME_SOURCE_PLACEHOLDER
    ## @brief 置信度门槛单一来源值，装配期读配置后注入识别门面
    confidenceThreshold: float = DEFAULT_CONFIDENCE
    ## @brief 缺框检测项是否拒识；生产装配为真，测试构造默认假
    requireBox: bool = False


## @brief 系统初始化：只初始化模块，不启采集/识别线程
#  @param usb 采集门面
#  @param recognition 识别门面
#  @param logStarter 日志消费者启动器
#  @param logger 日志器
#  @return 无
def initializeModules(usb: UsbController, recognition: RecognitionController,
                      logStarter: Callable[[], None], logger: ILogger) -> None:
    logStarter()
    usb.init()
    reportCameraProbeSummary(usb, logger)
    recognition.init()


## @brief 打印一行相机探测摘要；现场没接相机时给一句明白话，不再刷图像处理库的原生警告
#  @param usb 采集门面
#  @param logger 日志器，摘要与采集失败信息写入滚动日志
#  @return 无
def reportCameraProbeSummary(usb: UsbController, logger: ILogger) -> None:
    addresses = usb.getUnreachableAddresses()
    if not addresses:
        return
    indexes = "、".join(addresses)
    logger.info(
        "app_init",
        f"相机打开失败：索引 {indexes}；本机没接相机属正常现象，周期帧照发",
    )


## @brief 默认链路启动器：只拉起 TCP 重连线程
#  @param tcp 通信门面
#  @return 无
def startTcpLink(tcp: TcpControlLayer) -> None:
    tcp.start()


## @brief 构造加锁的帧发送器；出网键名由调用方按协议原文组装
#  @param comm TCP 通信封装
#  @return 帧发送器
def buildFrameSender(comm: TcpComm) -> FrameSender:
    sendLock = Lock()

    ## @brief 加锁组帧并发送
    #  @param frame 已按协议键名组装的帧
    #  @return 发送结果
    def sendFrame(frame: CachedEvent) -> bool:
        with sendLock:
            try:
                return comm.send(comm.encodeFrame(frame))
            except Exception:
                ## 组帧/发送异常不能穿透到排空线程顶层，否则该线程死亡后再无人发应答；
                ## 返回 False 交给链路断开逻辑处理
                return False

    return sendFrame


## @brief 应答排空动作：把待发应答送出，条数由控制层自行统计
#  @param control 控制层门面
#  @return 无
def drainOutbox(control: EdgeControl) -> None:
    control.dispatchOutbox()


## @brief 链路就绪探针：读通信门面的链路状态，供控制层感知断链
#  @param tcp 通信门面
#  @return 链路就绪返回 True
def probeLinkUp(tcp: TcpControlLayer) -> bool:
    return tcp.getState() == LINK_UP


## @brief 把配置值判成开关键；兼容布尔与字符串两种口径
#  @param value 配置原值，可能是 bool 或字符串
#  @return false/0/off/no/空值判关闭，其余判开启
def flagEnabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("false", "0", "off", "no", "")


## @brief 读取整型配置；非法值转业务异常，避免内置异常穿越装配边界
#  @param config 配置读取门面
#  @param section 配置节名
#  @param key 配置键名
#  @param default 缺失时的默认值
#  @return 整型配置值
#  @raises EdgeError 值无法转成整数时抛出，code=CONFIG
def readInt(config: IConfig, section: str, key: str, default: int | None = None) -> int:
    value = config.get(section, key, default=default)
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise EdgeError(
            ErrorCode.CONFIG, f"配置项 {section}.{key} 应为整数，实际为 {value!r}",
        ) from error


## @brief 读取浮点配置；非法值转业务异常，避免内置异常穿越装配边界
#  @param config 配置读取门面
#  @param section 配置节名
#  @param key 配置键名
#  @param default 缺失时的默认值
#  @return 浮点配置值
#  @raises EdgeError 值无法转成浮点数时抛出，code=CONFIG
def readFloat(config: IConfig, section: str, key: str,
              default: float | None = None) -> float:
    value = config.get(section, key, default=default)
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise EdgeError(
            ErrorCode.CONFIG, f"配置项 {section}.{key} 应为数值，实际为 {value!r}",
        ) from error
    if not math.isfinite(result):
        ## nan/inf 会让阈值比较失效或产出非法 JSON，按配置错误阻断启动
        raise EdgeError(
            ErrorCode.CONFIG, f"配置项 {section}.{key} 必须是有限数值，实际为 {value!r}",
        )
    return result


## @brief 探测采集门面构造函数是否接受指定参数
#  @param paramName 参数名
#  @return 接受返回 True
def usbControllerAccepts(paramName: str) -> bool:
    return paramName in inspect.signature(UsbController.__init__).parameters


## @brief 调用采集门面的启动采集接口；请求标识原样透传给采集线程
#  @param usb 采集门面
#  @param requestId 上位机请求标识
#  @return 触发成功返回 True
def invokeStartCapture(usb: UsbController, requestId: str) -> bool:
    return usb.beginScan(requestId)


## @brief 无参采集触发适配：供只关心开始采集的旧接线使用
#  @param usb 采集门面
#  @return 无
def startCaptureWithoutRequest(usb: UsbController) -> None:
    usb.startCapture()


## @brief 构造采集门面；先探测构造签名，再决定是否传对焦与路数参数
#  @param parts 全部构造注入参数
#  @param sink 采集事件回调（注入）
#  @param frameSink 帧流回调（注入，为空表示只落盘）
#  @return 采集门面
def buildUsbController(parts: AssemblyParts, sink: ICaptureSink,
                       frameSink: IFrameSink | None = None) -> UsbController:
    builder: UsbBuilder = UsbController
    if usbControllerAccepts(USB_FOCUS_MODE_PARAM):
        return builder(
            parts.cameraPairs, parts.captureDirs, sink, parts.logger,
            parts.rollThreshold, parts.usageRatio, parts.clock,
            focusMode=parts.focusMode,
            focusPositions=parts.focusPositions,
            zoomPositions=parts.zoomPositions,
            focusStableMs=parts.focusStableMs,
            cameraCount=len(parts.cameraIndices),
            frameSink=frameSink,
        )
    return builder(
        parts.cameraPairs, parts.captureDirs, sink, parts.logger,
        parts.rollThreshold, parts.usageRatio, parts.clock,
    )


## @brief 读取摄像头真实状态；状态取自采集门面的相机状态查询，不做硬编码
#  @param usb 采集门面
#  @return 摄像头状态列表
def readCameraStatus(usb: UsbController) -> list[dict[str, object]]:
    return usb.getCameraStatus()


## @brief 构造降级条目提供器：某路采集线程失败时按对照表补齐未识别条目
#  @param rows ROI 对照表行
#  @return 降级条目提供器
def buildDegradedItemsProvider(rows: list[RoiBindingRow]) -> DegradedItemsProvider:
    ## @brief 按线程编号产出该线程归属的未识别条目
    #  @param workerId 采集线程编号
    #  @return 未识别条目列表
    def provideDegradedItems(workerId: int) -> list[object]:
        return [
            buildAckItem(row.position, "", 0.0, ALERT_UNKNOWN)
            for row in rows if row.workerId == workerId
        ]

    return provideDegradedItems


## @brief 校验对照表的采集线程编号不超过实际采集线程数
#  @param rows ROI 对照表行
#  @param workerCount 实际采集线程数
#  @return 无
#  @raises EdgeError 线程编号超出实际采集线程数时抛出，code=CONFIG
def validateRoiWorkerScope(rows: list[RoiBindingRow], workerCount: int) -> None:
    for row in rows:
        if row.workerId > workerCount:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"对照表 worker_id 超出实际采集线程数: {row.roiId} 归属 "
                f"worker_id={row.workerId}, 实际采集线程数 {workerCount}",
            )


## @brief 采集分组没有登记货位时记一条说明；这些分组的相机会白开
#  @param rows ROI 对照表行
#  @param workerCount 实际采集线程数
#  @param logger 日志器
#  @return 无
#  @note 没有货位的分组照样占用一路相机去采集与识别，却不会产出任何清单条目，
#        现场只看周期帧会以为这几路在正常工作，所以启动时就说清楚哪几路是白开的。
def reportUnassignedCameraGroups(rows: list[RoiBindingRow], workerCount: int,
                                 logger: ILogger) -> None:
    assigned = {row.workerId for row in rows}
    emptyGroups = [
        workerId for workerId in range(MIN_WORKER_ID, workerCount + 1)
        if workerId not in assigned
    ]
    if not emptyGroups:
        return
    groupText = "、".join(f"第{workerId}组" for workerId in emptyGroups)
    logger.error(
        MODULE_NAME,
        f"相机分组 {groupText} 在对照表里没有货位，这几路相机的采集与识别是白做的；"
        "请在 ROI 对照表里补上这些分组的货位行，或从 camera_indices 里去掉对应相机",
    )


## @brief 装载 ROI 对照表；装载不到就启动即失败，不让识别链路带着空台账上线
#  @param loader 对照表装载器（注入）
#  @param csvPath 对照表文件路径
#  @return 对照表行列表
#  @raises EdgeError 对照表缺失、为空或装载失败时抛出，code=CONFIG
def loadRoiBindingRows(loader: RoiBindingLoader, csvPath: str) -> list[RoiBindingRow]:
    try:
        rows = loader.load(csvPath)
    except EdgeError as error:
        raise EdgeError(
            ErrorCode.CONFIG,
            f"未装载 ROI 对照表，无法识别: {csvPath}；原因 {error}",
        ) from error
    if not rows:
        raise EdgeError(
            ErrorCode.CONFIG,
            f"未装载 ROI 对照表，无法识别: {csvPath}",
        )
    return rows


## @brief 构造周期帧构造器；按协议输出 periodic 帧，并带上实时的摄像头状态列表
#  @param cameraStatusProvider 摄像头状态提供器（注入）
#  @param startedAt 进程启动时刻（单调时钟秒）
#  @param softwareVersion 软件版本号
#  @return 周期帧构造器
def buildPeriodicFrame(
    cameraStatusProvider: Callable[[], list[dict[str, object]]],
    startedAt: float,
    softwareVersion: str,
) -> Callable[[], dict[str, object]]:
    ## @brief 组装一帧周期帧：帧类型、启动秒数、软件版本与实时摄像头状态
    #  @return 周期帧字典
    def buildPeriodic() -> dict[str, object]:
        return {
            "type": PERIODIC_FRAME_TYPE,
            "uptime_sec": int(monotonic() - startedAt),
            "software_version": softwareVersion,
            "camera_status": cameraStatusProvider(),
        }

    return buildPeriodic


## @brief 识别请求处理器：取协议 request_id，识别能力不可用时立即回空清单应答
#  @param signal 已解码信号帧
#  @param trigger 采集触发句柄（注入）
#  @param capability 识别能力句柄（注入）
#  @return 无
def handleRecognizeReq(signal: DecodedSignal, trigger: CaptureTrigger,
                       capability: RecognitionCapability) -> None:
    requestId = str(signal.get(WIRE_REQUEST_ID_KEY, ""))
    capability.routeCapture(requestId, trigger)


## @brief 构造注入的信号键到处理器映射；识别请求走采集触发句柄
#  @param trigger 采集触发句柄（注入）
#  @param capability 识别能力句柄（注入）
#  @return 信号键到处理器映射
def buildAsyncHandlers(trigger: CaptureTrigger,
                       capability: RecognitionCapability) -> dict[str, AsyncHandler]:
    return {
        RECOGNIZE_REQ_TYPE: partial(handleRecognizeReq, trigger=trigger,
                                    capability=capability),
    }


## @brief 识别能力不可用时的空清单应答出口；只入队，发送由应答排空线程负责
#  @param control 控制层门面
#  @param requestId 上位机请求标识
#  @return 无
def emitEmptyAck(control: EdgeControl, requestId: str) -> None:
    control.completeWithEmptyAck(requestId)


## @brief 装配系统：new 三个门面 + EdgeControl，显式注入后返回
#  @param parts 全部构造注入参数
#  @return 控制层门面
def buildSystem(parts: AssemblyParts) -> EdgeControl:
    wiring = ModuleWiring()
    control = EdgeControl(
        parts.logger, parts.asyncHandlers, wiring,
        parts.frameSender, parts.failureFrameBuilder,
        expectedWorkerCount=len(parts.cameraPairs),
        degradedItemsProvider=buildDegradedItemsProvider(parts.roiBindingRows or []),
        aggregationTimeoutSec=parts.aggregationTimeoutSec,
    )
    usb = buildUsbController(parts, control, control)
    recognition = RecognitionController(
        parts.engine, parts.modelPath, parts.recognitionDirs, control, parts.logger,
        parts.roiConfig, parts.classItemMap, parts.roiBindMap,
        parts.inferTimeoutSec, parts.timeoutRunner, parts.frameLoader,
        roiBindingRows=parts.roiBindingRows,
        stitcher=parts.stitcher if parts.stitcher is not None
        else buildFrameStitcher(parts.logger),
        classItemComboMap=parts.classItemComboMap,
        capabilityAvailable=parts.recognitionCapability.isAvailable(),
        confidenceThreshold=parts.confidenceThreshold,
        rollThreshold=parts.rollThreshold, usageRatio=parts.usageRatio,
        requireBox=parts.requireBox,
    )
    tcp = TcpControlLayer(
        parts.socket, parts.logger, parts.backoffSeq, parts.maxFrameSize,
        parts.heartIntervalSec, parts.buildHeartbeat,
        control,
    )
    parts.captureTrigger.bind(partial(invokeStartCapture, usb))
    parts.cameraStatus.bindReader(partial(readCameraStatus, usb))
    parts.recognitionCapability.bindEmptyAckEmitter(partial(emitEmptyAck, control))
    wiring.initializeModules = partial(
        initializeModules, usb, recognition, parts.logStarter, parts.logger,
    )
    wiring.startLink = partial(parts.linkStarter, tcp)
    wiring.startCapture = partial(startCaptureWithoutRequest, usb)
    wiring.triggerRecognition = recognition.trigger
    wiring.triggerRecognitionByFrames = recognition.trigger
    wiring.droppedFrameCountProbe = recognition.getDroppedFrameCount
    wiring.linkUpProbe = partial(probeLinkUp, tcp)
    wiring.stopActions = {
        STOP_USB: usb.stopCapture,
        STOP_RECOGNITION: recognition.stop,
        STOP_TCP: tcp.stop,
        STOP_LOG: parts.logStopper,
    }
    dispatchThread = EdgeDispatchThread(
        partial(drainOutbox, control), parts.logger, parts.dispatchIntervalSec,
    )
    control.attachDispatchThread(dispatchThread)
    return control


## @brief 占位帧提供器；设备没有真实图像可用时读取纯灰占位图
#  @return 可解码的占位图像字节
def placeholderFrame() -> FrameImage | None:
    # TODO: 接入真实摄像头后，这里改为按平台读取一帧真实图像
    return buildPlaceholderFrameBytes()


## @brief 生成一张纯灰占位图；用标准库直接拼 PNG，保证无相机时也能跑通拼接与裁剪
#  @return PNG 图像字节
def buildPlaceholderFrameBytes() -> bytes:
    raw = b"".join(
        b"\x00" + bytes([PLACEHOLDER_FRAME_GRAY]) * PLACEHOLDER_FRAME_WIDTH
        for _ in range(PLACEHOLDER_FRAME_HEIGHT)
    )
    header = (
        struct.pack(">II", PLACEHOLDER_FRAME_WIDTH, PLACEHOLDER_FRAME_HEIGHT)
        + bytes([PLACEHOLDER_PNG_BIT_DEPTH, 0, 0, 0, 0])
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + buildPngChunk(b"IHDR", header)
        + buildPngChunk(
            b"IDAT", zlib.compress(raw, PLACEHOLDER_PNG_COMPRESSION_LEVEL),
        )
        + buildPngChunk(b"IEND", b"")
    )


## @brief 拼一个 PNG 数据块；长度与校验和按 PNG 规范填写
#  @param tag 数据块类型
#  @param data 数据块内容
#  @return 数据块字节
def buildPngChunk(tag: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(tag + data) & PNG_CRC32_MASK
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", checksum)


## @brief 左右图读取占位提供器；流式帧入口已接管取图，这里保持空实现
#  @param saveDir 采集目录
#  @param workerId 线程编号
#  @return 左右图像字节对
def placeholderFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
    # TODO: 需要按目录回放历史落盘图时，这里改为实读两张落盘图
    return (b"", b"")


## @brief 推理执行线程池最大并发数；按采集 worker 数量级设定，避免慢推理无限堆积
INFERENCE_POOL_MAX_WORKERS: int = 4
## @brief 推理执行线程池；模块级复用，超时后后台推理继续跑完但不再占用调用方
_INFERENCE_POOL: ThreadPoolExecutor | None = None
## @brief 线程池访问锁，保证首次调用时只建一个池
_INFERENCE_POOL_LOCK: Lock = Lock()
## @brief 推理在途闸门；容量为池大小，防止高频超时下无界排队积压
_INFERENCE_GATE: BoundedSemaphore | None = None


## @brief 取推理执行线程池与在途闸门，首次调用时创建并登记进程退出清理
#  @return 线程池与闸门的二元组
def inferencePool() -> tuple[ThreadPoolExecutor, BoundedSemaphore]:
    global _INFERENCE_POOL, _INFERENCE_GATE
    pool = _INFERENCE_POOL
    gate = _INFERENCE_GATE
    if pool is None or gate is None:
        with _INFERENCE_POOL_LOCK:
            pool = _INFERENCE_POOL
            gate = _INFERENCE_GATE
            if pool is None or gate is None:
                pool = ThreadPoolExecutor(
                    max_workers=INFERENCE_POOL_MAX_WORKERS,
                    thread_name_prefix="InferenceTimeout",
                )
                ## 闸门容量与池大小一致：在途推理达上限时拒绝新提交，杜绝无界排队
                gate = BoundedSemaphore(INFERENCE_POOL_MAX_WORKERS)
                ## 进程退出时不等待在途推理，避免慢推理拖住停机
                atexit.register(pool.shutdown, wait=False, cancel_futures=True)
                _INFERENCE_POOL = pool
                _INFERENCE_GATE = gate
    return pool, gate


## @brief 在超时上限内执行推理闭包；超时或并发已满抛 TimeoutError 由识别层转业务异常
#  @param task 推理闭包
#  @param timeoutSec 超时秒数，不大于 0 时直接执行不做限时
#  @return 检测结果列表
#  @raises TimeoutError 推理超时或在途推理已达上限
def directInference(task: Callable[[], list[DetectionItem]],
                    timeoutSec: float) -> list[DetectionItem]:
    if timeoutSec <= 0:
        return task()
    pool, gate = inferencePool()
    if not gate.acquire(blocking=False):
        ## 在途已满时快速失败，不排队、不积压；调用方按超时降级处理
        raise TimeoutError("在途推理已达上限")
    future: Future[list[DetectionItem]] | None = None

    ## @brief 任务结束（完成/异常/取消）时归还闸门名额
    #  @param finished 已结束的任务
    #  @return 无
    def releaseGate(finished: Future[list[DetectionItem]]) -> None:
        gate.release()

    try:
        future = pool.submit(task)
        future.add_done_callback(releaseGate)
        return future.result(timeout=timeoutSec)
    except FutureTimeoutError as error:
        ## 超时后取消尚未开始排队的任务；已在执行的推理无法强停，交由线程池收尾
        if future is not None:
            future.cancel()
        raise TimeoutError(f"推理超过 {timeoutSec}s") from error
    except BaseException:
        ## 提交或执行期间的非超时异常也要归还名额，避免闸门泄漏
        if future is None:
            gate.release()
        raise


## @brief 磁盘占用比例占位提供器；返回 0.0 表示不做滚动删旧，供测试用
#  @return 0.0
def zeroUsage() -> float:
    return 0.0


## @brief 磁盘占用缓存有效期秒；滚动删除每轮多次读取，节流避免高频系统调用
DISK_USAGE_CACHE_TTL_SEC: float = 5.0


## @brief 真实磁盘占用比例提供器；按各保存目录所在磁盘的已用比例取最大值
#  @param dirs 保存目录列表，取其中所在磁盘的最高占用比例
#  @param cacheTtlSec 缓存有效期秒，期内复用上次的占用比例
#  @return 0.0~1.0 的已用比例；目录不可用时按 0.0 处理，不阻断业务
def diskUsageRatio(dirs: Sequence[str],
                   cacheTtlSec: float = DISK_USAGE_CACHE_TTL_SEC) -> Callable[[], float]:
    cachedRatio: float = 0.0
    cachedAt: float = -cacheTtlSec

    def readUsage() -> float:
        nonlocal cachedRatio, cachedAt
        now = monotonic()
        if now - cachedAt < cacheTtlSec:
            ## 缓存有效期内直接返回，避免每轮采集对多目录重复系统调用
            return cachedRatio
        ratios: list[float] = []
        for directory in dirs:
            path = Path(directory)
            root = path if path.is_dir() else path.parent
            try:
                usage = shutil.disk_usage(str(root))
            except OSError:
                ## 目录或磁盘暂时不可读时跳过，本轮不做滚动删除，不中断采集
                continue
            if usage.total > 0:
                ratios.append(usage.used / usage.total)
        cachedRatio = max(ratios, default=0.0)
        cachedAt = now
        return cachedRatio

    return readUsage


## @brief 落盘文件名序号的补零位数
STAMP_SEQUENCE_DIGITS: int = 6
## @brief 落盘文件名序号锁；多个采集线程共用同一个时间戳提供器，取号要串行
STAMP_SEQUENCE_LOCK: Lock = Lock()
## @brief 落盘文件名序号，每取一次加一
STAMP_SEQUENCE: int = 0


## @brief 给每轮采集取一个不重复的文件名序号，避免后一张图把前一张覆盖掉
#  @return 补零后的递增序号
def defaultStamp() -> str:
    global STAMP_SEQUENCE
    with STAMP_SEQUENCE_LOCK:
        STAMP_SEQUENCE += 1
        return str(STAMP_SEQUENCE).zfill(STAMP_SEQUENCE_DIGITS)


## @brief 默认失败帧；按内部错误帧形状组装，出网守卫会拦下这种帧型
#  @param workerId 线程编号
#  @param exception 业务异常
#  @return 失败应答帧
def defaultFailureFrame(workerId: int, exception: Exception) -> CachedEvent:
    return {"type": "error", "workerId": workerId, "message": str(exception)}


## @brief 按相机索引顺序创建设备列表
#  @param cameraIndices 相机索引列表
#  @param logger 可选日志器，设备层用它记对焦下发说明
#  @param frameSource 帧来源：camera 真取帧，placeholder 用注入占位图
#  @return 设备列表
def buildCameraDevices(cameraIndices: list[int],
                       logger: ILogger | None = None,
                       frameSource: str = FRAME_SOURCE_PLACEHOLDER) -> list[ICameraDevice]:
    return [
        CameraFactory.createDevice(
            str(index), placeholderFrame,
            logger=logger,
            frameSource=frameSource,
            ## 真实取帧时由设备 open 自己确认在位，不再另开一次探测句柄
            reachabilityProbe=(
                None if frameSource == FRAME_SOURCE_CAMERA
                else buildCameraReachabilityProbe(str(index))
            ),
        )
        for index in cameraIndices
    ]


## @brief 构造摄像头可达性探测；探测真的打开一次设备并发图，确认这路相机在位
#  @param deviceAddr 设备地址
#  @return 探测回调，返回该路设备是否真的可用
def buildCameraReachabilityProbe(deviceAddr: str) -> Callable[[], bool]:
    ## @brief 执行一次可达性探测
    #  @return 该路设备可用返回 True
    def probe() -> bool:
        return probeCameraReachability(deviceAddr)

    return probe


## @brief 探测一路摄像头是否真的可用；打开失败或发不出图都算不可用
#  @param deviceAddr 设备地址
#  @return 可用返回 True
#  @raises EdgeError 图像处理库缺失时抛出，code=CAPTURE
def probeCameraReachability(deviceAddr: str) -> bool:
    imageLibrary = loadImageLibrary()
    try:
        index = int(deviceAddr)
    except ValueError:
        ## 非数字地址是 Linux 固定路径，Windows 图像处理库按索引寻址，探测不到
        return False
    ## 打开相机这一小段压掉图像处理库的原生日志，现场没接相机时不再刷误导性的警告
    with quietImageLibraryLog():
        ## Windows 用 DirectShow 后端按索引寻址；麒麟等平台没有该常量时用默认后端
        dshowBackend = getattr(imageLibrary, "CAP_DSHOW", None)
        capture = (
            imageLibrary.VideoCapture(index, dshowBackend)
            if dshowBackend is not None
            else imageLibrary.VideoCapture(index)
        )
        try:
            if not capture.isOpened():
                return False
            for _attempt in range(CAMERA_PROBE_ATTEMPTS):
                ok, frame = capture.read()
                if ok and frame is not None:
                    return True
                ## 首帧可能因设备刚起流而失败，等一下再试
                Event().wait(CAMERA_PROBE_RETRY_SEC)
            return False
        finally:
            capture.release()


## @brief 载入图像处理库；缺库时无法确认摄像头可达，按采集异常阻断
#  @return 图像处理库模块
#  @raises EdgeError 库缺失时抛出，code=CAPTURE
def loadImageLibrary() -> Any:
    try:
        ## 图像处理库是可选依赖，只能在函数体内导入
        import cv2  # type: ignore
    except ImportError as error:
        raise EdgeError(
            ErrorCode.CAPTURE, "未安装图像处理库 opencv-python, 无法确认摄像头可达",
        ) from error
    return cv2


## @brief 按左右两半拆分设备列表，构成每个 worker 的双路设备
#  @param devices 按相机索引排序的设备列表
#  @return 双路设备列表
def buildCameraPairs(devices: list[ICameraDevice]) -> list[tuple[ICameraDevice, ICameraDevice]]:
    half = len(devices) // DUAL_CAMERA_PAIR_SIZE
    return [(devices[index], devices[index + half]) for index in range(half)]


## @brief 判定最终采集模式
#  @param configuredMode 配置里的 capture_mode
#  @param indexCount camera_indices 的个数
#  @return single 或 dual
#  @raises EdgeError 索引个数越界、模式非法或无法两两配对时抛出，code=CONFIG
#  @note 各取值行为：
#        auto   —— 1 路走单摄；偶数路双摄（五五分前后配对）；奇数路（3 及以上）明确报错，
#                  不静默丢路，也不把某一路悄悄改成单摄。
#        dual   —— 强制双摄，要求偶数且至少 2 路；1 路或奇数路报错。
#        single —— 强制单摄，每个索引单独成一个单摄 worker（N 路即 N 个 worker），
#                  每台相机出一帧全景，不拼接，任何一路都不丢。
def resolveCaptureMode(configuredMode: str, indexCount: int) -> str:
    if configuredMode not in CAPTURE_MODES:
        raise EdgeError(ErrorCode.CONFIG, f"capture_mode 非法: {configuredMode}")
    if not MIN_CAMERA_INDEX_COUNT <= indexCount <= MAX_CAMERA_INDEX_COUNT:
        raise EdgeError(
            ErrorCode.CONFIG,
            f"camera_indices 个数应在 {MIN_CAMERA_INDEX_COUNT}~"
            f"{MAX_CAMERA_INDEX_COUNT} 之间, 实得 {indexCount}",
        )
    if configuredMode == CAPTURE_MODE_SINGLE:
        return CAPTURE_MODE_SINGLE
    if indexCount == SINGLE_CAMERA_INDEX_COUNT:
        if configuredMode == CAPTURE_MODE_DUAL:
            raise EdgeError(ErrorCode.CONFIG, "dual 模式至少需要 2 路相机索引")
        return CAPTURE_MODE_SINGLE
    if indexCount % 2 != 0:
        raise EdgeError(
            ErrorCode.CONFIG,
            f"{configuredMode} 模式下 {indexCount} 路相机索引无法两两配对; "
            "请改成偶数路, 或设 capture_mode = single",
        )
    return CAPTURE_MODE_DUAL


## @brief 计算采集线程数：单摄每个索引一组，双摄每两个索引一组
#  @param indexCount camera_indices 的个数
#  @param mode resolveCaptureMode 的结果
#  @return 采集线程数
def resolveGroupCount(indexCount: int, mode: str) -> int:
    if mode == CAPTURE_MODE_SINGLE:
        return indexCount
    return indexCount // 2


## @brief 按最终模式把设备列表切成每个 worker 一组
#  @param devices 按相机索引排序的设备列表
#  @param mode resolveCaptureMode 的结果
#  @return 设备组列表，单摄组 1 路、双摄组 2 路
def buildCameraGroups(devices: list[ICameraDevice],
                      mode: str) -> list[tuple[ICameraDevice, ...]]:
    groups: list[tuple[ICameraDevice, ...]] = []
    if mode == CAPTURE_MODE_SINGLE:
        for device in devices:
            groups.append((device,))
        return groups
    for left, right in buildCameraPairs(devices):
        groups.append((left, right))
    return groups


## @brief 把逐路光学配置归一成 8 个浮点值；单值广播成 8 份，缺项按 0 补齐
#  @param raw 配置原值，可能是逗号字符串、列表、元组或单个数字
#  @param key 配置键名，用于错误信息定位
#  @return 长度为 OPTICAL_VALUE_COUNT 的浮点列表，下标 = 物理路号 - 1
#  @raises EdgeError 取值非法或个数既不是 1 也不是 8 时抛出，code=CONFIG
def normalizeOpticalValues(raw: object, key: str) -> list[float]:
    if isinstance(raw, bool):
        raise EdgeError(ErrorCode.CONFIG, f"{key} 取值非法: {raw}")
    if isinstance(raw, (int, float)):
        values: list[object] = [raw]
    elif isinstance(raw, str):
        values = [part.strip() for part in raw.split(",") if part.strip()]
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        raise EdgeError(ErrorCode.CONFIG, f"{key} 取值非法: {raw}")
    if len(values) == 1:
        values = values * OPTICAL_VALUE_COUNT
    if len(values) != OPTICAL_VALUE_COUNT:
        raise EdgeError(
            ErrorCode.CONFIG,
            f"{key} 应为 1 个或 {OPTICAL_VALUE_COUNT} 个值，实际 {len(values)} 个",
        )
    result: list[float] = []
    for value in values:
        try:
            result.append(float(str(value)))
        except (TypeError, ValueError) as error:
            raise EdgeError(ErrorCode.CONFIG, f"{key} 取值非法: {value}") from error
    return result


## @brief 把配置里的 camera_indices 归一成整数列表
#  @param raw 配置读取到的原值，单路时是 int，多路时是 list
#  @return 相机索引列表
#  @raises EdgeError 取值非法时抛出，code=CONFIG
def normalizeCameraIndices(raw: object) -> list[int]:
    if isinstance(raw, bool):
        raise EdgeError(ErrorCode.CONFIG, f"camera_indices 取值非法: {raw}")
    if isinstance(raw, int):
        values: list[object] = [raw]
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        raise EdgeError(ErrorCode.CONFIG, f"camera_indices 取值非法: {raw}")
    indices: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise EdgeError(ErrorCode.CONFIG, f"相机索引必须是整数: {value}")
        if value < 0:
            raise EdgeError(ErrorCode.CONFIG, f"相机索引不能为负: {value}")
        indices.append(value)
    return indices


## @brief 把配置里的多值项归一成字符串列表
#  @param raw 配置读取到的原值，单值时是 str，多值时是 list
#  @return 字符串列表
#  @raises EdgeError 取值非法时抛出，code=CONFIG
def normalizePathList(raw: object) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        values: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                raise EdgeError(ErrorCode.CONFIG, f"目录配置项非法: {item}")
            values.append(item)
        return values
    raise EdgeError(ErrorCode.CONFIG, f"目录配置项非法: {raw}")


## @brief 把配置里的退避序列归一成秒数列表，元素逐个转成浮点数
#  @param raw 配置读取到的原值，单值或逗号切出的多值列表
#  @return 秒数列表，元素都是浮点数
#  @raises EdgeError 取值不是数值或为空时抛出，code=CONFIG
def normalizeBackoffSeq(raw: object) -> list[float]:
    if isinstance(raw, bool):
        raise EdgeError(ErrorCode.CONFIG, f"退避序列取值非法: {raw}")
    if isinstance(raw, (int, float)):
        items: list[object] = [raw]
    elif isinstance(raw, (list, tuple)) and raw:
        items = list(raw)
    else:
        raise EdgeError(ErrorCode.CONFIG, f"退避序列取值非法: {raw}")
    seconds: list[float] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise EdgeError(ErrorCode.CONFIG, f"退避秒数必须是数值: {item}")
        seconds.append(float(item))
    return seconds


## @brief 把 ROI 对照表行的 workerId 归一到实际采集线程数内
#  @param rows 装配前装载的对照表行
#  @param groupCount 实际采集线程数（相机组数）
#  @param logger 日志器，归并发生时记一条 info
#  @return 归一后的新行列表，行数与货位覆盖不变
#  @note 装配时归并，现场换摄像头不必改对照表；单摄时所有行归到 1 号线程，
#        应答清单仍覆盖对照表全部货位。双摄 4 组时原编号 1~4 不变，不产生日志。
def normalizeRoiWorkerIds(rows: list[RoiBindingRow], groupCount: int,
                          logger: ILogger) -> list[RoiBindingRow]:
    if groupCount < 1:
        raise EdgeError(ErrorCode.CONFIG, f"实际采集线程数非法: {groupCount}")
    normalized: list[RoiBindingRow] = []
    changed = 0
    for row in rows:
        workerId = min(max(row.workerId, MIN_WORKER_ID), groupCount)
        if workerId != row.workerId:
            changed += 1
            normalized.append(replace(row, workerId=workerId))
        else:
            normalized.append(row)
    if changed:
        logger.info(
            MODULE_NAME,
            f"已按实际采集线程数归并 ROI 归属: 归并 {changed} 行, "
            f"实际采集线程数 {groupCount}, 货位总数 {len(normalized)} 保持不变",
        )
    return normalized


## @brief 让采集/识别目录数量与采集线程数一致，不足时按同类目录补齐
#  @param dirs 配置里解析好的目录列表
#  @param groupCount 实际采集线程数
#  @return 与线程数等长的目录列表
def fitSaveDirs(dirs: list[str], groupCount: int) -> list[str]:
    if len(dirs) >= groupCount:
        return dirs[:groupCount]
    fitted = list(dirs)
    base = Path(fitted[-1]).parent if fitted else Path(".")
    for index in range(len(fitted) + 1, groupCount + 1):
        fitted.append(str(base / f"w{index}"))
    return fitted


## @brief 把边缘机工程目录从模块搜索路径里摘掉
#  @return 无
#  @note 本目录下的 platform 包会遮蔽标准库的 platform 模块；
#        在本目录里启动时，图像处理库与数值计算库导入标准库 platform 会取到本包，
#        导致导入失败。摘掉本目录后，标准库与第三方库都能正常导入，
#        而 edge 包自身靠包路径定位，不依赖模块搜索路径。
def detachEdgeModuleDirFromSearchPath() -> None:
    currentDir = Path.cwd()
    kept: list[str] = []
    for item in sys.path:
        target = Path(item) if item else currentDir
        try:
            resolved = target.resolve()
        except OSError:
            ## 路径无法解析时退回原路径比较，保持与 EDGE_MODULE_DIR 的判定可用
            resolved = target
        if resolved == EDGE_MODULE_DIR:
            continue
        kept.append(item)
    sys.path[:] = kept


## @brief 相对路径的候选解析位置：运行时工作目录、边缘机工程目录、仓库根目录
#  @param rawPath 配置里写的相对路径
#  @return 候选绝对路径列表，按优先级排列
def configPathCandidates(rawPath: str) -> list[Path]:
    return [
        Path.cwd() / rawPath,
        EDGE_MODULE_DIR / rawPath,
        REPO_ROOT_DIR / rawPath,
    ]


## @brief 解析配置文件路径；绝对路径直接用，相对路径逐级查找
#  @param rawPath 配置文件路径
#  @return 解析后的配置文件绝对路径
#  @raises EdgeError 各级候选都找不到配置文件时抛出，code=CONFIG
def resolveConfigFilePath(rawPath: str) -> str:
    if not rawPath:
        raise EdgeError(
            ErrorCode.CONFIG, f"配置文件路径为空；请在 {CONFIG_FILE_HINT} 配置",
        )
    candidate = Path(rawPath)
    if candidate.is_absolute():
        if candidate.is_file():
            return str(candidate)
        raise EdgeError(
            ErrorCode.CONFIG,
            f"配置文件缺失: {rawPath}；请在 {CONFIG_FILE_HINT} 配置",
        )
    for option in configPathCandidates(rawPath):
        if option.is_file():
            return str(option)
    raise EdgeError(
        ErrorCode.CONFIG,
        f"配置文件缺失: {rawPath}；请在 {CONFIG_FILE_HINT} 配置",
    )


## @brief 解析配置里的路径；绝对路径直接用，相对路径逐级查找
#  @param rawPath 配置里写的路径
#  @return 解析后的绝对路径；各级都不存在时按边缘机工程目录给出待创建位置
#  @note 相对路径的三个候选位置依次是运行时工作目录、边缘机工程目录、仓库根目录
def resolveConfigPath(rawPath: str) -> str:
    if not rawPath:
        return rawPath
    candidate = Path(rawPath)
    if candidate.is_absolute():
        return str(candidate)
    for option in configPathCandidates(rawPath):
        if option.exists():
            return str(option)
    ## 各级候选都不存在时按边缘机工程目录给出位置，运行目录由装配阶段创建
    return str(EDGE_MODULE_DIR / rawPath)


## @brief 创建运行期目录；日志目录、采集目录与识别目录逐项建好
#  @param logDir 日志目录
#  @param captureDirs 采集目录列表
#  @param recognitionDirs 识别目录列表
#  @return 无
#  @raises EdgeError 目录创建失败时抛出，code=CONFIG
def ensureRuntimeDirs(logDir: str, captureDirs: list[str],
                       recognitionDirs: list[str]) -> None:
    for rawPath in [logDir, *captureDirs, *recognitionDirs]:
        if not rawPath:
            continue
        try:
            Path(rawPath).mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise EdgeError(
                ErrorCode.CONFIG, f"运行目录创建失败: {rawPath}",
            ) from error


## @brief 装载 ROI 对照表并允许降级；装载不到只记错误日志，进程照常启动
#  @param loader 对照表装载器（注入）
#  @param csvPath 对照表文件路径
#  @param logger 日志器（注入）
#  @return 对照表行列表；装载不到时为空列表
def loadRoiBindingRowsLenient(loader: RoiBindingLoader, csvPath: str,
                              logger: ILogger) -> list[RoiBindingRow]:
    try:
        return loadRoiBindingRows(loader, csvPath)
    except EdgeError as error:
        ## 现场识别清单给不出时按降级处理：进程照常起来，周期帧照发
        logger.error(
            MODULE_NAME,
            f"识别能力不可用：未装载 ROI 对照表: {csvPath}；原因 {error}",
        )
        return []


## @brief 采集布局：配置解析出的目录、相机索引与最终采集模式；只读不改运行期状态
@dataclass
class CaptureLayout:
    ## @brief 日志目录
    logDir: str
    ## @brief 与采集线程数等长的采集目录
    captureDirs: list[str]
    ## @brief 与采集线程数等长的识别目录
    recognitionDirs: list[str]
    ## @brief 相机索引列表
    cameraIndices: list[int]
    ## @brief 配置里的 capture_mode 原值
    captureMode: str
    ## @brief 帧来源：camera 真取帧，placeholder 用占位图
    frameSource: str
    ## @brief 判定后的最终采集模式：single 或 dual
    resolvedMode: str


## @brief 运行基础设施：日志器单例、套接字与单帧字节上限
@dataclass
class Infrastructure:
    ## @brief 日志器单例
    logManager: LogManager
    ## @brief 套接字
    socket: ISocket
    ## @brief 单帧字节上限
    maxFrameSize: int


## @brief 识别装配输入：相机设备与分组、三个句柄、对照表行与推理参数
@dataclass
class RecognitionInputs:
    ## @brief 按相机索引排序的设备列表
    cameraDevices: list[ICameraDevice]
    ## @brief 按最终模式切好的设备组
    cameraPairs: list[tuple[ICameraDevice, ...]]
    ## @brief 摄像头状态句柄
    cameraStatus: CameraStatusHandle
    ## @brief 采集触发句柄
    captureTrigger: CaptureTrigger
    ## @brief 识别能力句柄
    recognitionCapability: RecognitionCapability
    ## @brief 进程启动时刻（单调时钟秒）
    startedAt: float
    ## @brief ROI 对照表路径（配置原值）
    roiBindingCsv: str
    ## @brief 装配期装载并归并后的对照表行
    roiBindingRows: list[RoiBindingRow]
    ## @brief 类别组合到物品名映射
    classItemComboMap: dict[frozenset[str], str]
    ## @brief 推理后端名称
    inferenceBackend: str
    ## @brief 同类别非极大值抑制的 IoU 阈值
    nmsIouThreshold: float
    ## @brief 置信度门槛单一来源值，装配期读配置
    confidenceThreshold: float = DEFAULT_CONFIDENCE


## @brief 读采集布局：目录、相机索引、采集模式与帧来源，判定最终模式并把目录补足到线程数
#  @param config 配置读取门面（注入）
#  @return 解析好的采集布局
#  @raises EdgeError 帧来源非法、采集模式非法或索引个数越界时抛出，code=CONFIG
def readCaptureLayout(config: IConfig) -> CaptureLayout:
    logDir = resolveConfigPath(str(config.get("log", "dir")))
    configuredCaptureDirs = [
        resolveConfigPath(item)
        for item in normalizePathList(config.get("usb", "save_dirs"))
    ]
    configuredRecognitionDirs = [
        resolveConfigPath(item)
        for item in normalizePathList(config.get("recognition", "save_dirs"))
    ]
    ## 相机配置：索引、模式、帧来源三项决定单摄/双摄与是否真取帧
    cameraIndices = normalizeCameraIndices(config.get("usb", CAMERA_INDICES_KEY))
    layerMode = str(config.get("usb", LAYER_MODE_KEY, default=LAYER_MODE_MULTI))
    if layerMode not in LAYER_MODES:
        raise EdgeError(ErrorCode.CONFIG, f"layer_mode 非法: {layerMode}")
    if layerMode == LAYER_MODE_SINGLE:
        ## 工装单层测试：只取前 2 路相机，强制构成 1 个双摄 worker
        ## 其余链路（周期帧 / 识别 / 聚合）一字不动
        cameraIndices = cameraIndices[:DUAL_CAMERA_PAIR_SIZE]
    captureMode = str(config.get(
        "usb", CAPTURE_MODE_KEY, default=CAPTURE_MODE_AUTO,
    ))
    frameSource = str(config.get(
        "usb", FRAME_SOURCE_KEY, default=FRAME_SOURCE_CAMERA,
    ))
    if frameSource not in FRAME_SOURCES:
        raise EdgeError(ErrorCode.CONFIG, f"frame_source 非法: {frameSource}")
    resolvedMode = resolveCaptureMode(captureMode, len(cameraIndices))
    groupCount = resolveGroupCount(len(cameraIndices), resolvedMode)
    captureDirs = fitSaveDirs(configuredCaptureDirs, groupCount)
    recognitionDirs = fitSaveDirs(configuredRecognitionDirs, groupCount)
    ## 存图开关：关闭时把对应目录置空串，下游靠 bool(saveDir) 自动跳过落盘与滚动删旧。
    ## 缺键时按开启处理，保持既有配置行为不变；显式 false 才关闭。
    if not flagEnabled(config.get("usb", SAVE_FRAMES_KEY, default=True)):
        captureDirs = [""] * len(captureDirs)
    if not flagEnabled(config.get("recognition", SAVE_PANORAMA_KEY, default=True)):
        recognitionDirs = [""] * len(recognitionDirs)
    return CaptureLayout(
        logDir=logDir,
        captureDirs=captureDirs,
        recognitionDirs=recognitionDirs,
        cameraIndices=cameraIndices,
        captureMode=captureMode,
        frameSource=frameSource,
        resolvedMode=resolvedMode,
    )


## @brief 建运行基础设施：建好运行目录，创建日志器单例与套接字，读出单帧字节上限
#  @param config 配置读取门面（注入）
#  @param layout 已解析的采集布局
#  @return 日志器、套接字与帧长上限
def buildInfrastructure(config: IConfig, layout: CaptureLayout) -> Infrastructure:
    ensureRuntimeDirs(layout.logDir, layout.captureDirs, layout.recognitionDirs)
    logManager = LogManager.instance(
        layout.logDir,
        readInt(config, "log", "max_file_size"),
        readInt(config, "log", "mode"),
        readFloat(config, "log", "disk_free_threshold"),
        readFloat(config, "log", "queue_poll_sec"),
    )
    socket: ISocket = TcpSocket(
        str(config.get("tcp", "host")),
        readInt(config, "tcp", "port"),
        readFloat(config, "tcp", "connect_timeout_sec"),
        readFloat(config, "tcp", "recv_timeout_sec"),
    )
    maxFrameSize = readInt(config, "tcp", "max_frame_size")
    return Infrastructure(logManager=logManager, socket=socket, maxFrameSize=maxFrameSize)


## @brief 备识别装配输入：建相机设备与三个句柄，装载对照表、切分设备组并读出推理参数
#  @param config 配置读取门面（注入）
#  @param layout 已解析的采集布局
#  @param infra 运行基础设施
#  @return 识别侧装配输入
#  @raises EdgeError 对照表按生产要求装载失败或编号超限时抛出，code=CONFIG
def buildRecognitionInputs(config: IConfig, layout: CaptureLayout,
                           infra: Infrastructure) -> RecognitionInputs:
    cameraDevices = buildCameraDevices(
        layout.cameraIndices, infra.logManager, layout.frameSource,
    )
    cameraStatus = CameraStatusHandle()
    captureTrigger = CaptureTrigger()
    recognitionCapability = RecognitionCapability()
    startedAt = monotonic()
    roiBindingCsv = str(config.get("recognition", "roi_binding_csv"))
    roiBindingPath = resolveConfigPath(roiBindingCsv)
    confidenceThreshold = readFloat(
        config, "recognition", "min_confidence", default=DEFAULT_CONFIDENCE,
    )
    loader = RoiBindingLoader(
        infra.logManager, confidenceThreshold=confidenceThreshold,
    )
    requireRoiBinding = flagEnabled(config.get(
        "recognition", "require_roi_binding", default=False,
    ))
    if requireRoiBinding:
        ## 生产环境要求：装载不到对照表就启动即失败
        roiBindingRows = loadRoiBindingRows(loader, roiBindingPath)
    else:
        ## 现场与联调时：装载不到就降级，进程照常启动，周期帧照发
        roiBindingRows = loadRoiBindingRowsLenient(loader, roiBindingPath, infra.logManager)
    if not roiBindingRows:
        recognitionCapability.markUnavailable()
    classItemComboMap = loadClassItemComboMap(loader, roiBindingPath)
    cameraPairs = buildCameraGroups(cameraDevices, layout.resolvedMode)
    ## 装配时把对照表每行的线程编号归并到实际采集线程数内，现场换摄像头无需改对照表
    roiBindingRows = normalizeRoiWorkerIds(roiBindingRows, len(cameraPairs), infra.logManager)
    validateRoiWorkerScope(roiBindingRows, len(cameraPairs))
    reportUnassignedCameraGroups(roiBindingRows, len(cameraPairs), infra.logManager)
    inferenceBackend = str(config.get(
        "recognition", "inference_backend", default=DEFAULT_INFERENCE_BACKEND,
    ))
    nmsIouThreshold = readFloat(
        config, "recognition", "nms_iou_threshold", default=DEFAULT_NMS_IOU_THRESHOLD,
    )
    return RecognitionInputs(
        cameraDevices=cameraDevices,
        cameraPairs=cameraPairs,
        cameraStatus=cameraStatus,
        captureTrigger=captureTrigger,
        recognitionCapability=recognitionCapability,
        startedAt=startedAt,
        roiBindingCsv=roiBindingCsv,
        roiBindingRows=roiBindingRows,
        classItemComboMap=classItemComboMap,
        inferenceBackend=inferenceBackend,
        nmsIouThreshold=nmsIouThreshold,
        confidenceThreshold=confidenceThreshold,
    )


## @brief 收口构造装配参数；配置里剩余的运行参数仍在本函数的构造表达式中按原顺序读取
#  @param config 配置读取门面（注入）
#  @param layout 已解析的采集布局
#  @param infra 运行基础设施
#  @param inputs 识别侧装配输入
#  @return 装配参数集合
def assembleParts(config: IConfig, layout: CaptureLayout,
                  infra: Infrastructure, inputs: RecognitionInputs) -> AssemblyParts:
    return AssemblyParts(
        logger=infra.logManager,
        socket=infra.socket,
        cameraPairs=inputs.cameraPairs,
        captureDirs=layout.captureDirs,
        recognitionDirs=layout.recognitionDirs,
        engine=YoloEngine.instance(
            infra.logManager, inputs.inferenceBackend, inputs.nmsIouThreshold,
        ),
        modelPath=resolveConfigPath(str(config.get("recognition", "model_path"))),
        frameLoader=placeholderFrames,
        timeoutRunner=directInference,
        inferTimeoutSec=readFloat(config, "recognition", "infer_timeout_sec"),
        roiConfig=EMPTY_ROI_CONFIG,
        classItemMap=EMPTY_CLASS_ITEM_MAP,
        roiBindMap=EMPTY_ROI_BIND_MAP,
        rollThreshold=readFloat(config, "usb", "roll_threshold"),
        usageRatio=diskUsageRatio(layout.captureDirs + layout.recognitionDirs),
        clock=defaultStamp,
        confidenceThreshold=inputs.confidenceThreshold,
        ## 生产口径：检测结果须带位置框，缺框按未识别
        requireBox=True,
        backoffSeq=normalizeBackoffSeq(config.get("tcp", "backoff_seq")),
        maxFrameSize=infra.maxFrameSize,
        heartIntervalSec=readFloat(config, "tcp", "heart_interval_sec"),
        buildHeartbeat=buildPeriodicFrame(
            inputs.cameraStatus.readStatus, inputs.startedAt, SOFTWARE_VERSION,
        ),
        asyncHandlers=buildAsyncHandlers(inputs.captureTrigger, inputs.recognitionCapability),
        failureFrameBuilder=defaultFailureFrame,
        frameSender=buildFrameSender(TcpComm(infra.socket, infra.maxFrameSize, infra.logManager)),
        linkStarter=startTcpLink,
        logStarter=infra.logManager.start,
        logStopper=infra.logManager.stop,
        cameraIndices=layout.cameraIndices,
        cameraDevices=inputs.cameraDevices,
        focusMode=str(config.get("usb", "focus_mode")),
        focusPositions=normalizeOpticalValues(
            config.get("usb", FOCUS_POSITIONS_KEY, default=0.0), FOCUS_POSITIONS_KEY,
        ),
        zoomPositions=normalizeOpticalValues(
            config.get("usb", ZOOM_POSITIONS_KEY, default=0.0), ZOOM_POSITIONS_KEY,
        ),
        focusStableMs=readInt(config, "usb", FOCUS_STABLE_MS_KEY, default=200),
        roiBindingCsv=inputs.roiBindingCsv,
        roiBindingRows=inputs.roiBindingRows,
        classItemComboMap=inputs.classItemComboMap,
        stitcher=buildFrameStitcher(infra.logManager),
        captureTrigger=inputs.captureTrigger,
        cameraStatus=inputs.cameraStatus,
        recognitionCapability=inputs.recognitionCapability,
        aggregationTimeoutSec=readFloat(
            config, "recognition", "aggregation_timeout_sec",
            default=DEFAULT_AGGREGATION_TIMEOUT_SEC,
        ),
        captureMode=layout.captureMode,
        resolvedCaptureMode=layout.resolvedMode,
        frameSource=layout.frameSource,
    )


## @brief 从 config.ini 读取参数并构造默认装配；相机模式、帧来源、ROI 归属都由此配置驱动
#  @param configPath 配置文件路径
#  @return 装配参数集合
def defaultParts(configPath: str = DEFAULT_CONFIG_PATH) -> AssemblyParts:
    ## 装配顺序固定：解析配置 → 读采集布局 → 建运行基础设施 → 备识别输入 → 收口构造
    ## 先摘掉工程目录，避免本目录下的 platform 包遮蔽标准库模块
    detachEdgeModuleDirFromSearchPath()
    resolvedConfigPath = resolveConfigFilePath(configPath)
    config: IConfig = IniConfigManager.instance(resolvedConfigPath)
    layout = readCaptureLayout(config)
    infra = buildInfrastructure(config, layout)
    if isinstance(config, IniConfigManager):
        ## 日志器在 buildInfrastructure 才创建，此刻注入以补记此前所有默认值提示
        config.setLogger(infra.logManager)
    inputs = buildRecognitionInputs(config, layout, infra)
    return assembleParts(config, layout, infra, inputs)


## @brief 装载可选的类别组合表；文件不存在时不装，也不报错
#  @param loader 对照表装载器（注入）
#  @param roiBindingPath ROI 对照表路径
#  @return 类别组合到物品名映射，文件不存在时为空字典
def loadClassItemComboMap(loader: RoiBindingLoader,
                           roiBindingPath: str) -> dict[frozenset[str], str]:
    comboPath = Path(roiBindingPath).parent / CLASS_ITEM_MAP_FILE_NAME
    if not comboPath.is_file():
        return {}
    return loader.loadClassItemMap(str(comboPath))
