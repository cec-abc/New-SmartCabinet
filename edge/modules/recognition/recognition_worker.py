"""识别工作线程：读图、拼接、画 ROI、超时推理、归集校验、组帧与回调。"""
from __future__ import annotations

from collections.abc import Callable

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.interfaces.i_sinks import AckFrame
from edge.modules.recognition.recognition_utils import (
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
    aggregateByRoi,
    buildAck,
    cropAndMerge,
    drawRoi,
    validateByTable,
)

## @brief 日志模块名
MODULE_NAME = "RecognitionWorker"
## @brief 结果回调类型
ResultCallback = Callable[[int, AckFrame, str], None]
## @brief 失败回调类型
ErrorCallback = Callable[[int, Exception], None]


## @brief 识别线程；单轮完成读图到回调后静默退出，异常只影响本线程
class RecognitionWorker(BaseThread):
    ## @brief 构造识别线程
    #  @param workerId 线程编号
    #  @param requestId 上位机请求标识
    #  @param saveDir 该 worker 的采集目录（注入）
    #  @param engine 推理引擎（注入）
    #  @param logger 可选日志器
    #  @param onResult 结果回调，只做轻量上抛
    #  @param onError 失败回调，只做轻量上抛
    #  @param roiConfig ROI 配置（注入）
    #  @param classItemMap 类别映射（注入）
    #  @param roiBindMap ROI 绑定表（注入）
    #  @param inferTimeoutSec 推理超时秒数（构造注入）
    #  @param timeoutRunner 推理超时执行器（注入）
    #  @param frameLoader 左右图读取器（注入）
    def __init__(self, workerId: int, requestId: str, saveDir: str,
                 engine: IRecognitionEngine, logger: ILogger | None,
                 onResult: ResultCallback, onError: ErrorCallback,
                 roiConfig: RoiConfig, classItemMap: ClassItemMap,
                 roiBindMap: RoiBindMap, inferTimeoutSec: float,
                 timeoutRunner: TimeoutRunner, frameLoader: FrameLoader) -> None:
        super().__init__(name=f"RecognitionWorker-{workerId}", logger=logger)
        ## @brief 线程编号
        self._workerId: int = workerId
        ## @brief 上位机请求标识
        self._requestId: str = requestId
        ## @brief 采集目录
        self._saveDir: str = saveDir
        ## @brief 推理引擎
        self._engine: IRecognitionEngine = engine
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief 结果回调
        self._onResult: ResultCallback = onResult
        ## @brief 失败回调
        self._onError: ErrorCallback = onError
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

    ## @brief 单轮识别主流程；顶层异常转失败回调，不外抛、不波及其他线程
    #  @return 无
    def runLoop(self) -> None:
        try:
            left, right = self._frameLoader(self._saveDir, self._workerId)
            merged = cropAndMerge(left, right)
            marked = drawRoi(merged, self._roiConfig)
            items = self.runInference(marked)
            groups = aggregateByRoi(items)
            ackItems, misses = validateByTable(
                groups, self._classItemMap, self._roiBindMap,
            )
            for miss in misses:
                self.logFailure(EdgeError(ErrorCode.CONFIG, f"查表未命中: {miss}"))
            ack = buildAck(self._workerId, self._requestId, ackItems)
            self.emitResult(ack)
        except EdgeError as error:
            self.emitFailure(error)
        except Exception as error:
            ## 读图等内置异常跨线程边界前统一转业务异常
            self.emitFailure(EdgeError(ErrorCode.CAPTURE, f"识别流程异常: {error}"))

    ## @brief 施加注入的超时上限执行推理；超时与内置异常统一转业务异常
    #  @param image 已标记 ROI 的图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 推理超时或失败时 code=INFERENCE_TIMEOUT
    def runInference(self, image: FrameImage) -> list[DetectionItem]:
        try:
            return self._timeoutRunner(
                lambda: self._engine.infer(image), self._inferTimeoutSec,
            )
        except EdgeError:
            raise
        except TimeoutError as error:
            raise EdgeError(
                ErrorCode.INFERENCE_TIMEOUT, f"推理超过 {self._inferTimeoutSec}s",
            ) from error
        except Exception as error:
            raise EdgeError(ErrorCode.INFERENCE_TIMEOUT, f"推理失败: {error}") from error

    ## @brief 成功回调：只做轻量上抛，禁止在此执行阻塞 IO
    #  @param ack 应答帧
    #  @return 无
    def emitResult(self, ack: AckFrame) -> None:
        if self._logger is not None:
            message = f"worker-{self._workerId} 识别完成"
            self._logger.info(MODULE_NAME, message)
        self._onResult(self._workerId, ack, self._requestId)

    ## @brief 失败回调：记录异常码后轻量上抛
    #  @param error 业务异常
    #  @return 无
    def emitFailure(self, error: EdgeError) -> None:
        self.logFailure(error)
        self._onError(self._workerId, error)

    ## @brief 统一的错误日志出口，异常码使用 code.name
    #  @param error 业务异常
    #  @return 无
    def logFailure(self, error: EdgeError) -> None:
        if self._logger is not None:
            message = f"worker-{self._workerId} 失败 {error.code.name}"
            self._logger.error(MODULE_NAME, message, exception=error)
