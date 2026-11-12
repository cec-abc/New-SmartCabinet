"""识别模块门面：模型单次加载、按 workerId 触发并立即返回、回调轻量转接。"""
from __future__ import annotations

from threading import Lock

from edge.base.base_service import BaseService
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import IRecognitionEngine
from edge.interfaces.i_sinks import AckFrame, IRecognitionSink
from edge.modules.recognition.recognition_utils import (
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
)
from edge.modules.recognition.recognition_worker import RecognitionWorker

## @brief 日志模块名
MODULE_NAME = "RecognitionController"


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
    def __init__(self, engine: IRecognitionEngine, modelPath: str,
                 saveDirs: list[str], sink: IRecognitionSink, logger: ILogger | None,
                 roiConfig: RoiConfig, classItemMap: ClassItemMap,
                 roiBindMap: RoiBindMap, inferTimeoutSec: float,
                 timeoutRunner: TimeoutRunner, frameLoader: FrameLoader) -> None:
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
        ## @brief 是否已初始化
        self._inited: bool = False
        ## @brief 模型是否已加载，保证仅一次
        self._modelLoaded: bool = False
        ## @brief 并发触发锁
        self._triggerLock: Lock = Lock()
        ## @brief 当前 worker 实例（每次触发新建）
        self._workers: dict[int, RecognitionWorker] = {}

    ## @brief 初始化：校验配置并仅加载一次模型，Fail-Fast 不引入能力降级
    #  @return 无
    #  @raises EdgeError 配置不完整或模型加载失败时 code=CONFIG
    def init(self) -> None:
        if not self._modelPath or not self._saveDirs:
            raise EdgeError(ErrorCode.CONFIG, "识别配置不完整")
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
    #  @return 成功拉起返回 True；未初始化、编号非法或 worker 忙返回 False
    def trigger(self, workerId: int, requestId: str) -> bool:
        # TODO: NPU 并发限流，实测后加信号量
        with self._triggerLock:
            if not self._inited or workerId < 1 or workerId > len(self._saveDirs):
                self.logRecognitionError(
                    EdgeError(ErrorCode.CONFIG, f"识别触发参数非法: {workerId}"),
                )
                return False
            active = self._workers.get(workerId)
            if active is not None and active.isRunning():
                self.logRecognitionError(
                    EdgeError(ErrorCode.CONFIG, f"worker-{workerId} 正忙"),
                )
                return False
            ## 每次触发新建实例（L-07），绕开 BaseThread.start 的启动幂等
            worker = self.buildRecognitionWorker(workerId, requestId)
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

    ## @brief 供验收举证查询指定 worker 是否运行中
    #  @param workerId 工作线程编号
    #  @return 运行中返回 True
    def isWorkerBusy(self, workerId: int) -> bool:
        with self._triggerLock:
            worker = self._workers.get(workerId)
        return worker is not None and worker.isRunning()

    ## @brief 新建本轮识别线程实例
    #  @param workerId 工作线程编号
    #  @param requestId 上位机请求标识
    #  @return 识别线程
    def buildRecognitionWorker(self, workerId: int, requestId: str) -> RecognitionWorker:
        return RecognitionWorker(
            workerId, requestId, self._saveDirs[workerId - 1],
            self._engine, self._logger,
            self.onRecognitionWorkerResult, self.onRecognitionWorkerError,
            self._roiConfig, self._classItemMap, self._roiBindMap,
            self._inferTimeoutSec, self._timeoutRunner, self._frameLoader,
        )

    ## @brief 统一的错误日志出口，异常码使用 code.name
    #  @param error 业务异常
    #  @return 无
    def logRecognitionError(self, error: EdgeError) -> None:
        if self._logger is not None:
            message = f"识别门面 {error.code.name}: {error}"
            self._logger.error(MODULE_NAME, message, exception=error)
