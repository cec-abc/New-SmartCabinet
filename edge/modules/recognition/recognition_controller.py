"""识别模块门面：模型单次加载、按 workerId 触发并立即返回、回调轻量转接。"""
from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from edge.base.base_service import BaseService
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingRow
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import IRecognitionEngine
from edge.interfaces.i_sinks import AckFrame, IRecognitionSink
from edge.modules.recognition.recognition_modes import RECOGNITION_MODE_STITCH
from edge.modules.recognition.recognition_stitcher import FrameStitcher
from edge.modules.recognition.recognition_utils import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
)
from edge.modules.recognition.recognition_worker import (
    DEFAULT_PANORAMA_ROLL_THRESHOLD,
    RecognitionWorker,
)

## @file edge/modules/recognition/recognition_controller.py
## @brief 识别模块门面：模型单次加载、按 workerId 触发流式扫描并立即返回
## @author 袁燕

## @brief 日志模块名
MODULE_NAME = "RecognitionController"
## @brief 丢帧日志的抽样间隔，每累计到该倍数才记一条日志
DEFAULT_DROPPED_FRAME_LOG_INTERVAL: int = 10


## @brief 识别门面；识别指令唯一下发出口，只依赖 i_sinks.py 回调契约
class RecognitionController(BaseService):
    ## @brief 构造门面
    #  @param engine 推理引擎（注入）
    #  @param modelPath 模型路径（注入，模块内不读配置）
    #  @param saveDirs 每个 workerId 对应的采集目录（注入）
    #  @param sink 识别事件回调（注入）
    #  @param logger 可选日志器
    #  @param roiConfig ROI 配置（注入）
    #  @param classItemMap 类别映射（注入）
    #  @param roiBindMap ROI 绑定表（注入）
    #  @param inferTimeoutSec 推理超时秒数（构造注入）
    #  @param timeoutRunner 推理超时执行器（注入）
    #  @param frameLoader 左右图读取器（注入）
    #  @param roiBindingRows ROI 对照表行（注入，为空表示降级为按 ROI 配置识别的备用链路）
    #  @param stitcher 拼接裁剪器（注入）
    #  @param classItemComboMap 类别组合到物品名映射（注入）
    #  @param droppedFrameLogInterval 丢帧日志抽样间隔（构造注入）
    #  @param capabilityAvailable 识别能力是否可用；对照表缺失时为假，只回空清单
    #  @param confidenceThreshold 置信度门槛，默认取模块常量（配置可覆盖）
    #  @param rollThreshold 全景图滚动删旧占用阈值（构造注入）
    #  @param usageRatio 磁盘占用比例提供器（注入，便于确定性举证）
    #  @param requireBox 为真时缺框检测项拒识，默认假兼容旧格式与测试桩
    #  @return 无
    def __init__(self, engine: IRecognitionEngine, modelPath: str,
                 saveDirs: list[str], sink: IRecognitionSink, logger: ILogger | None,
                 roiConfig: RoiConfig, classItemMap: ClassItemMap,
                 roiBindMap: RoiBindMap, inferTimeoutSec: float,
                 timeoutRunner: TimeoutRunner, frameLoader: FrameLoader,
                 roiBindingRows: list[RoiBindingRow] | None = None,
                 stitcher: FrameStitcher | None = None,
                 classItemComboMap: dict[frozenset[str], str] | None = None,
                 droppedFrameLogInterval: int = DEFAULT_DROPPED_FRAME_LOG_INTERVAL,
                 capabilityAvailable: bool = True,
                 confidenceThreshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 rollThreshold: float = DEFAULT_PANORAMA_ROLL_THRESHOLD,
                 usageRatio: Callable[[], float] | None = None,
                 requireBox: bool = False,
                 recognitionMode: str = RECOGNITION_MODE_STITCH,
                 cropRects: dict[int, tuple[float, float, float, float]] | None = None,
                 drawRoiOverlay: bool = False,
                 ) -> None:
        ## @brief 推理引擎
        self._engine: IRecognitionEngine = engine
        ## @brief 模型路径
        self._modelPath: str = modelPath
        ## @brief 采集目录列表
        self._saveDirs: list[str] = saveDirs
        ## @brief 识别事件回调
        self._sink: IRecognitionSink = sink
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief ROI 配置
        self._roiConfig: RoiConfig = roiConfig
        ## @brief 类别映射
        self._classItemMap: ClassItemMap = classItemMap
        ## @brief ROI 绑定表
        self._roiBindMap: RoiBindMap = roiBindMap
        ## @brief 推理超时秒数
        self._inferTimeoutSec: float = inferTimeoutSec
        ## @brief 推理超时执行器
        self._timeoutRunner: TimeoutRunner = timeoutRunner
        ## @brief 左右图读取器
        self._frameLoader: FrameLoader = frameLoader
        ## @brief ROI 对照表行，为空表示降级为按 ROI 配置识别的备用链路
        self._roiBindingRows: list[RoiBindingRow] | None = roiBindingRows
        ## @brief 拼接裁剪器
        self._stitcher: FrameStitcher | None = stitcher
        ## @brief 类别组合到物品名映射
        self._classItemComboMap: dict[frozenset[str], str] = (
            classItemComboMap if classItemComboMap is not None else {}
        )
        ## @brief 是否已初始化
        self._inited: bool = False
        ## @brief 模型是否已加载，保证仅一次
        self._modelLoaded: bool = False
        ## @brief 并发触发锁
        self._triggerLock: Lock = Lock()
        ## @brief 当前 worker 实例（每次触发新建）
        self._workers: dict[int, RecognitionWorker] = {}
        ## @brief 因上一轮扫描未结束而被丢弃的帧轮数
        self._droppedFrameCount: int = 0
        ## @brief 丢帧日志抽样间隔，避免逐帧刷屏
        self._droppedFrameLogInterval: int = max(1, droppedFrameLogInterval)
        ## @brief 识别能力是否可用；对照表缺失时为假，识别请求只回空清单
        self._capabilityAvailable: bool = capabilityAvailable
        ## @brief 置信度门槛，缺省值与上位机判据一致，配置可覆盖
        self._confidenceThreshold: float = confidenceThreshold
        ## @brief 全景图滚动删旧占用阈值
        self._rollThreshold: float = rollThreshold
        ## @brief 磁盘占用比例提供器，None 时由 worker 按不触发删旧处理
        self._usageRatio: Callable[[], float] | None = usageRatio
        ## @brief 缺框检测项是否拒识；生产装配注入真
        self._requireBox: bool = requireBox
        ## @brief 识别模式：stitch=拼接全景推理；crop=每路裁剪独立识别
        self._recognitionMode: str = recognitionMode
        ## @brief 每路裁剪矩形，键=路号（1~8），值=归一化 (x1,y1,x2,y2)
        self._cropRects: dict[int, tuple[float, float, float, float]] = (
            cropRects if cropRects is not None else {}
        )
        ## @brief 调试存图是否叠加绘制 ROI 矩形框与货位标识
        self._drawRoiOverlay: bool = drawRoiOverlay

    ## @brief 初始化：校验配置并仅加载一次模型，Fail-Fast 不引入能力降级
    #  @return 无
    #  @raises EdgeError 配置不完整或模型加载失败时 code=CONFIG
    def init(self) -> None:
        if not self._modelPath or not self._saveDirs:
            raise EdgeError(ErrorCode.CONFIG, "识别配置不完整")
        if not self._capabilityAvailable:
            ## 识别能力不可用时跳过模型加载；进程照常启动，周期帧照发
            self._inited = True
            if self._logger is not None:
                self._logger.error(
                    MODULE_NAME,
                    "识别能力不可用：未装载 ROI 对照表，跳过模型加载，"
                    "识别请求只回空清单",
                )
            return
        if not self._modelLoaded:
            try:
                self._engine.loadModel(self._modelPath)
            except EdgeError:
                raise
            except Exception as error:
                raise EdgeError(ErrorCode.CONFIG, f"模型加载失败: {error}") from error
            self._modelLoaded = True
        self._inited = True
        if self._logger is not None:
            message = f"识别初始化完成, 模型 {self._modelPath}"
            self._logger.info(MODULE_NAME, message)

    ## @brief 生命周期启动：只做初始化，不预启任何 worker（裁决 D-02）
    #  @return 无
    def start(self) -> None:
        self.init()

    ## @brief 生命周期停止：中断全部识别线程并清空实例
    #  @return 无
    def stop(self) -> None:
        with self._triggerLock:
            workers = list(self._workers.values())
            self._workers = {}
        for worker in workers:
            worker.stop()

    ## @brief 前置校验后拉起对应 worker 并立即返回，不等待子线程
    #  @param workerId 工作线程编号
    #  @param requestId 上位机请求标识
    #  @param frames 本轮流式帧，左路在前；对照表链路必须带帧
    #  @return 成功拉起返回 True；未初始化、编号非法、缺帧或 worker 忙返回 False
    def trigger(self, workerId: int, requestId: str,
                frames: tuple[bytes, ...] = ()) -> bool:
        # TODO: NPU 并发限流，实测后加信号量
        if not self._capabilityAvailable:
            ## 识别能力不可用时不拉起扫描线程，避免白跑一轮取图与推理
            self.logRecognitionInfo("识别能力不可用, 不触发扫描")
            return False
        with self._triggerLock:
            if not self._inited or workerId < 1 or workerId > len(self._saveDirs):
                self.logRecognitionError(
                    EdgeError(ErrorCode.CONFIG, f"识别触发参数非法: {workerId}"),
                )
                return False
            if self._roiBindingRows is not None and not frames:
                ## 对照表链路只认流式帧，没有帧就没有可识别内容，不触发扫描
                self.logRecognitionInfo(f"对照表链路缺少帧, 跳过 worker-{workerId} 扫描")
                return False
            active = self._workers.get(workerId)
            if active is not None and active.isRunning():
                ## 上一轮扫描还没结束，本轮帧直接丢弃，保证同一线程不并发推理
                self._droppedFrameCount += 1
                self.logDroppedFrames(workerId)
                return False
            ## 每次触发新建实例（L-07），绕开 BaseThread.start 同一实例只启动一次的限制
            worker = self.buildRecognitionWorker(workerId, requestId, frames)
            self._workers[workerId] = worker
        worker.start()
        if self._logger is not None:
            self._logger.info(MODULE_NAME, f"已拉起 worker-{workerId}")
        return True

    ## @brief 自检预留空接口（裁决 D-01）；带模块前缀规避与 c4 全局重名
    #  @return 无
    def selfCheckRecognition(self) -> None:
        # TODO: 自检逻辑后续实现时另起独立线程，不占用识别线程与主线程
        return None

    ## @brief worker 成功回调：只做轻量转发，禁止在此执行阻塞 IO
    #  @param workerId 工作线程编号
    #  @param ack 应答帧
    #  @param requestId 上位机请求标识
    #  @return 无
    def onRecognitionWorkerResult(self, workerId: int, ack: AckFrame,
                                  requestId: str) -> None:
        self._sink.onRecognitionResult(workerId, ack, requestId)

    ## @brief worker 失败回调：只做轻量转发，不影响其他线程
    #  @param workerId 工作线程编号
    #  @param exception 业务异常
    #  @return 无
    def onRecognitionWorkerError(self, workerId: int, exception: Exception) -> None:
        self._sink.onRecognitionError(workerId, exception)

    ## @brief 供验收举证读取当前 worker 映射
    #  @return workerId 到线程实例的快照
    def getActiveWorkers(self) -> dict[int, RecognitionWorker]:
        with self._triggerLock:
            return dict(self._workers)

    ## @brief 供验收举证读取被丢弃的帧轮数
    #  @return 累计丢弃次数
    #  @note 计数在触发锁内累加，这里也在同一把锁里读，保证读到的是一轮完整累加后的值
    def getDroppedFrameCount(self) -> int:
        with self._triggerLock:
            return self._droppedFrameCount

    ## @brief 丢帧日志出口；按抽样间隔记一条，避免逐帧刷屏
    #  @param workerId 线程编号
    #  @return 无
    def logDroppedFrames(self, workerId: int) -> None:
        if self._droppedFrameCount % self._droppedFrameLogInterval != 0:
            return
        self.logRecognitionInfo(
            f"worker-{workerId} 上一轮扫描未结束, 本轮帧已丢弃 "
            f"累计 {self._droppedFrameCount} 次",
        )

    ## @brief 新建本轮识别线程实例
    #  @param workerId 工作线程编号
    #  @param requestId 上位机请求标识
    #  @param frames 本轮流式帧，左路在前
    #  @return 识别线程
    def buildRecognitionWorker(self, workerId: int, requestId: str,
                               frames: tuple[bytes, ...]) -> RecognitionWorker:
        return RecognitionWorker(
            workerId, requestId, self._saveDirs[workerId - 1],
            self._engine, self._logger,
            self.onRecognitionWorkerResult, self.onRecognitionWorkerError,
            self._roiConfig, self._classItemMap, self._roiBindMap,
            self._inferTimeoutSec, self._timeoutRunner, self._frameLoader,
            self._roiBindingRows, self._stitcher, frames, self._classItemComboMap,
            confidenceThreshold=self._confidenceThreshold,
            rollThreshold=self._rollThreshold, usageRatio=self._usageRatio,
            requireBox=self._requireBox,
            recognitionMode=self._recognitionMode,
            cropRect=self._cropRects.get(workerId),
            drawRoiOverlay=self._drawRoiOverlay,
        )

    ## @brief 统一的错误日志出口，异常码使用 code.name
    #  @param error 业务异常
    #  @return 无
    def logRecognitionError(self, error: EdgeError) -> None:
        if self._logger is not None:
            message = f"识别门面 {error.code.name}: {error}"
            self._logger.error(MODULE_NAME, message, exception=error)

    ## @brief 普通信息日志出口，用于说明为什么没有触发扫描
    #  @param message 日志内容
    #  @return 无
    def logRecognitionInfo(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(MODULE_NAME, message)
