"""应用装配：只做 new + 注入 + 返回，不写业务流程。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from threading import Lock
from typing import cast

from edge.control.edge_control import (
    STOP_LOG,
    STOP_RECOGNITION,
    STOP_TCP,
    STOP_USB,
    AsyncHandler,
    EdgeControl,
    FailureFrameBuilder,
    ModuleWiring,
)
from edge.control.event_cache import CachedEvent, EventCache, FrameSender
from edge.infra.config_manager import IniConfigManager
from edge.infra.log_manager import LogManager
from edge.interfaces.i_camera import FrameImage, ICameraDevice
from edge.interfaces.i_config import IConfig
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.interfaces.i_socket import ISocket
from edge.modules.recognition.recognition_controller import RecognitionController
from edge.modules.recognition.recognition_utils import (
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
)
from edge.modules.recognition.recognition_yolo_engine import YoloEngine
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.tcp.tcp_control_layer import TcpControlLayer
from edge.modules.usb.usb_camera_device import CameraFactory
from edge.modules.usb.usb_controller import UsbController

## @brief 默认配置文件路径，由入口读取后注入各模块
DEFAULT_CONFIG_PATH: str = "config.ini"
## @brief 默认采集 worker 数（骨架占位，真实数量由配置注入）
DEFAULT_WORKER_COUNT: int = 4
## @brief 链路启动器（注入，便于测试替换线程启动）
LinkStarter = Callable[[TcpControlLayer], None]


## @brief 全部构造注入参数集合；app_init 不读全局状态、不做业务判断
@dataclass
class AssemblyParts:
    ## @brief 日志器
    logger: ILogger
    ## @brief 套接字
    socket: ISocket
    ## @brief 四组左右摄像头
    cameraPairs: list[tuple[ICameraDevice, ICameraDevice]]
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
    ## @brief 补发开关
    eventCacheEnabled: bool
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


## @brief 系统初始化：只初始化模块，不启采集/识别线程（D-02）
#  @param usb 采集门面
#  @param recognition 识别门面
#  @param logStarter 日志消费者启动器
#  @return 无
def initializeModules(usb: UsbController, recognition: RecognitionController,
                      logStarter: Callable[[], None]) -> None:
    logStarter()
    usb.init()
    recognition.init()


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
            return comm.send(comm.encodeFrame(frame))

    return sendFrame


## @brief 装配系统：new 三个门面 + EdgeControl，显式注入后返回
#  @param parts 全部构造注入参数
#  @return 控制层门面
def buildSystem(parts: AssemblyParts) -> EdgeControl:
    wiring = ModuleWiring()
    cache = EventCache(parts.eventCacheEnabled, parts.logger)
    control = EdgeControl(
        parts.logger, parts.asyncHandlers, wiring, cache,
        parts.frameSender, parts.failureFrameBuilder,
    )
    usb = UsbController(
        parts.cameraPairs, parts.captureDirs, control, parts.logger,
        parts.rollThreshold, parts.usageRatio, parts.clock,
    )
    recognition = RecognitionController(
        parts.engine, parts.modelPath, parts.recognitionDirs, control, parts.logger,
        parts.roiConfig, parts.classItemMap, parts.roiBindMap,
        parts.inferTimeoutSec, parts.timeoutRunner, parts.frameLoader,
    )
    tcp = TcpControlLayer(
        parts.socket, parts.logger, parts.backoffSeq, parts.maxFrameSize,
        parts.heartIntervalSec, parts.buildHeartbeat, control,
    )
    wiring.initializeModules = partial(initializeModules, usb, recognition, parts.logStarter)
    wiring.startLink = partial(parts.linkStarter, tcp)
    wiring.startCapture = usb.startCapture
    wiring.triggerRecognition = recognition.trigger
    wiring.stopActions = {
        STOP_USB: usb.stopCapture,
        STOP_RECOGNITION: recognition.stop,
        STOP_TCP: tcp.stop,
        STOP_LOG: parts.logStopper,
    }
    return control


## @brief 骨架占位帧；真实摄像头后端上板后替换
#  @return 空图像字节
def placeholderFrame() -> FrameImage | None:
    # TODO: 上板后按平台接 CAP_DSHOW / CAP_V4L2 真实取帧
    return b""


## @brief 骨架占位左右图；真实按采集目录读盘后替换
#  @param saveDir 采集目录
#  @param workerId 线程编号
#  @return 左右图像字节对
def placeholderFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
    # TODO: 上板后按 c4 落盘文件名实读左右两图
    return (b"", b"")


## @brief 骨架占位推理执行器；真实 3s 计时器上板后替换
#  @param task 推理闭包
#  @param timeoutSec 超时秒数
#  @return 检测结果列表
def directInference(task: Callable[[], list[DetectionItem]],
                    timeoutSec: float) -> list[DetectionItem]:
    # TODO: 上板后接真实 3s 超时计时器
    return task()


## @brief 骨架占位磁盘占用比例
#  @return 0.0
def zeroUsage() -> float:
    return 0.0


## @brief 骨架占位时间戳
#  @return 固定标签
def defaultStamp() -> str:
    return "stamp"


## @brief 默认心跳帧；camera_status 默认值属待裁决③，不混入 d
#  @return 心跳帧字典
def defaultHeartbeat() -> dict[str, object]:
    return {"type": "heartbeat", "uptime_sec": 0, "software_version": "edge-0.1.0"}


## @brief 默认失败帧；线上键名最终映射按 §2.10 协议注入后替换
#  @param workerId 线程编号
#  @param exception 业务异常
#  @return 失败应答帧
def defaultFailureFrame(workerId: int, exception: Exception) -> CachedEvent:
    return {"type": "error", "workerId": workerId, "message": str(exception)}


## @brief 真实 socket 尚未由 c3 落地前的骨架；上板后由 tcp/tcp_socket.py 替换
class SocketSkeleton(ISocket):
    ## @brief 连接骨架
    #  @return 无
    #  @raises NotImplementedError 上板前统一抛出
    def connect(self) -> None:
        # TODO: 上板后接真实 Windows / Linux socket 连接
        raise NotImplementedError("真实 socket 待上板实现")

    ## @brief 接收骨架
    #  @return 不返回
    #  @raises NotImplementedError 上板前统一抛出
    def recv(self) -> bytes:
        raise NotImplementedError("真实 socket 待上板实现")

    ## @brief 发送骨架
    #  @param data 待发送字节
    #  @return 不返回
    #  @raises NotImplementedError 上板前统一抛出
    def send(self, data: bytes) -> bool:
        raise NotImplementedError("真实 socket 待上板实现")

    ## @brief 关闭骨架
    #  @return 无
    def close(self) -> None:
        return None


## @brief 从 config.ini 读取参数并构造默认装配；真实设备键与处理器留上板注入
#  @param configPath 配置文件路径
#  @return 装配参数集合
def defaultParts(configPath: str = DEFAULT_CONFIG_PATH) -> AssemblyParts:
    config: IConfig = IniConfigManager.instance(configPath)
    logManager = LogManager.instance(
        str(config.get("log", "dir")),
        int(config.get("log", "max_file_size")),
        int(config.get("log", "mode")),
        float(config.get("log", "disk_free_threshold")),
        float(config.get("log", "queue_poll_sec")),
    )
    socket: ISocket = SocketSkeleton()
    maxFrameSize = int(config.get("tcp", "max_frame_size"))
    cameraPairs: list[tuple[ICameraDevice, ICameraDevice]] = [
        (CameraFactory.createDevice(str(index), placeholderFrame),
         CameraFactory.createDevice(str(index + DEFAULT_WORKER_COUNT), placeholderFrame))
        for index in range(1, DEFAULT_WORKER_COUNT + 1)
    ]
    return AssemblyParts(
        logger=logManager,
        socket=socket,
        cameraPairs=cameraPairs,
        captureDirs=cast(list[str], config.get("usb", "save_dirs")),
        recognitionDirs=cast(list[str], config.get("recognition", "save_dirs")),
        engine=YoloEngine(),
        modelPath=str(config.get("recognition", "model_path")),
        frameLoader=placeholderFrames,
        timeoutRunner=directInference,
        inferTimeoutSec=float(config.get("recognition", "infer_timeout_sec")),
        roiConfig=cast(RoiConfig, config.get("recognition", "roi_config", default={})),
        classItemMap=cast(ClassItemMap, config.get("recognition", "class_item_map", default={})),
        roiBindMap=cast(RoiBindMap, config.get("recognition", "roi_bind_map", default={})),
        rollThreshold=float(config.get("usb", "roll_threshold")),
        usageRatio=zeroUsage,
        clock=defaultStamp,
        backoffSeq=cast(list[float], config.get("tcp", "backoff_seq")),
        maxFrameSize=maxFrameSize,
        heartIntervalSec=float(config.get("tcp", "heart_interval_sec")),
        buildHeartbeat=defaultHeartbeat,
        eventCacheEnabled=bool(config.get("event_cache", "enabled")),
        asyncHandlers={},
        failureFrameBuilder=defaultFailureFrame,
        frameSender=buildFrameSender(TcpComm(socket, maxFrameSize, logManager)),
        linkStarter=startTcpLink,
        logStarter=logManager.start,
        logStopper=logManager.stop,
    )
