"""识别工作线程：拼全景推理一次，按对照表逐行做框-区域位置判定，产出协议四键条目并回调。"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingRow
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.interfaces.i_sinks import AckFrame
from edge.modules.recognition.recognition_modes import (
    DEFAULT_RECOGNITION_MODE,
    RECOGNITION_MODE_CROP,
)
from edge.modules.recognition.recognition_stitcher import FrameStitcher
from edge.modules.recognition.recognition_utils import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    AckItem,
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
    buildAck,
    buildRowItem,
    canvasRoiMismatch,
    detectionsInRoi,
    matchMarker,
)

## @file edge/modules/recognition/recognition_worker.py
## @brief 识别工作线程：拼全景推理一次，按对照表逐行位置判定，产出协议应答并回调
## @author 袁燕


## @brief 日志模块名
MODULE_NAME = "RecognitionWorker"
## @brief 全景图滚动删旧占用阈值缺省值，与采集侧 roll_threshold 同口径
DEFAULT_PANORAMA_ROLL_THRESHOLD: float = 0.3
## @brief 全景图滚动删旧扫描的文件名模式
PANORAMA_GLOB_PATTERN: str = "*_panorama_*.png"
## @brief 结果回调类型
ResultCallback = Callable[[int, AckFrame, str], None]
## @brief 失败回调类型
ErrorCallback = Callable[[int, Exception], None]


## @brief 占用比例恒为 0 的缺省提供器，表示不触发滚动删旧
#  @return 0.0
def neverUsage() -> float:
    return 0.0


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
    #  @param roiBindingRows ROI 对照表行（注入，为空表示降级为按 ROI 配置识别的备用链路）
    #  @param stitcher 拼接裁剪器（注入）
    #  @param frames 本轮流式帧，左路在前（注入）
    #  @param classItemComboMap 类别组合到物品名映射（注入）
    #  @param confidenceThreshold 置信度门槛，默认取模块常量（配置可覆盖）
    #  @param rollThreshold 全景图滚动删旧占用阈值（构造注入）
    #  @param usageRatio 磁盘占用比例提供器（注入，便于确定性举证）
    #  @param requireBox 为真时缺框检测项拒识，默认假兼容旧格式与测试桩
    #  @return 无
    def __init__(self, workerId: int, requestId: str, saveDir: str,
                 engine: IRecognitionEngine, logger: ILogger | None,
                 onResult: ResultCallback, onError: ErrorCallback,
                 roiConfig: RoiConfig, classItemMap: ClassItemMap,
                 roiBindMap: RoiBindMap, inferTimeoutSec: float,
                 timeoutRunner: TimeoutRunner, frameLoader: FrameLoader,
                 roiBindingRows: list[RoiBindingRow] | None = None,
                 stitcher: FrameStitcher | None = None,
                 frames: tuple[bytes, ...] = (),
                 classItemComboMap: dict[frozenset[str], str] | None = None,
                 confidenceThreshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 rollThreshold: float = DEFAULT_PANORAMA_ROLL_THRESHOLD,
                 usageRatio: Callable[[], float] | None = None,
                 requireBox: bool = False,
                 recognitionMode: str = DEFAULT_RECOGNITION_MODE,
                 cropRect: tuple[float, float, float, float] | None = None,
                 ) -> None:
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
        ## @brief ROI 对照表行，为空表示降级为按 ROI 配置识别的备用链路
        self._roiBindingRows: list[RoiBindingRow] | None = roiBindingRows
        ## @brief 拼接裁剪器
        self._stitcher: FrameStitcher | None = stitcher
        ## @brief 本轮流式帧，左路在前
        self._frames: tuple[bytes, ...] = frames
        ## @brief 类别组合到物品名映射
        self._classItemComboMap: dict[frozenset[str], str] = (
            classItemComboMap if classItemComboMap is not None else {}
        )
        ## @brief 置信度门槛，缺省值与上位机判据一致，配置可覆盖
        self._confidenceThreshold: float = confidenceThreshold
        ## @brief 全景图滚动删旧占用阈值
        self._rollThreshold: float = rollThreshold
        ## @brief 磁盘占用比例提供器，None 时按不触发删旧处理
        self._usageRatio: Callable[[], float] = (
            usageRatio if usageRatio is not None else neverUsage
        )
        ## @brief 缺框检测项是否拒识；生产装配注入真，测试桩默认假
        self._requireBox: bool = requireBox
        ## @brief 识别模式：stitch=拼接全景推理；crop=本路按归一化矩形裁剪后识别
        self._recognitionMode: str = recognitionMode
        ## @brief 本路裁剪矩形（归一化 0~1）；None 表示全图不裁
        self._cropRect: tuple[float, float, float, float] | None = cropRect
        ## @brief 存图文件名里的环节标签：拼接模式 panorama、裁剪模式 crop
        self._imageTag: str = (
            "crop" if recognitionMode == RECOGNITION_MODE_CROP else "panorama"
        )
        ## @brief 本轮存图删旧计数，供验收举证与现场排查
        self.removedPanoramaCount: int = 0

    ## @brief 单轮识别主流程；顶层异常转失败回调，不外抛、不波及其他线程
    #  @return 无
    def runLoop(self) -> None:
        try:
            if self._recognitionMode == RECOGNITION_MODE_CROP:
                items = self.runCropRecognition()
            elif self._roiBindingRows is None:
                items = self.runConfigRecognition()
            else:
                items = self.runTableRecognition()
            self.emitResult(buildAck(self._requestId, items))
        except EdgeError as error:
            self.emitFailure(error)
        except Exception as error:
            ## 识别链路任意非业务异常跨线程边界前统一转推理类失败；
            ## CAPTURE 仅留给相机采集层使用，避免采集失败被误标成识别失败
            self.emitFailure(EdgeError(ErrorCode.INFERENCE_TIMEOUT, f"识别流程异常: {error}"))

    ## @brief 对照表链路：拼全景、按行裁区域、区域内找标志，每个对照行出一条协议条目
    #  @return 协议条目列表
    #  @raises EdgeError 未装配拼接器时抛出，code=CONFIG
    def runTableRecognition(self) -> list[AckItem]:
        stitcher = self._stitcher
        if stitcher is None:
            raise EdgeError(ErrorCode.CONFIG, "未装配拼接裁剪器, 无法走对照表识别")
        rows = [
            row for row in (self._roiBindingRows or [])
            if row.workerId == self._workerId
        ]
        try:
            panorama = stitcher.stitch(self._frames)
        except EdgeError as error:
            ## 拼接失败时整幅都认不出，逐行按未识别上报，保证清单不缺货位
            self.logFailure(error)
            return [buildRowItem(row, False, 0.0) for row in rows]
        self.savePanoramaIfEnabled(panorama)
        ## 尺寸护栏：坐标基准与真实全景明显错配时按未识别降级并记错，避免静默全空清单
        mismatch = canvasRoiMismatch(stitcher.panoramaSize(panorama), rows)
        if mismatch:
            self.logFailure(EdgeError(ErrorCode.CAPTURE, mismatch))
            return [buildRowItem(row, False, 0.0) for row in rows]
        try:
            detections = self.runInference(panorama)   # 全图推理一次，得到带框检测
        except EdgeError as error:
            self.logFailure(error)
            return [buildRowItem(row, False, 0.0) for row in rows]
        items: list[AckItem] = []
        for row in rows:
            items.append(self.recognizeRow(detections, row))
        return items

    ## @brief 裁剪模式识别：本路单帧按归一化矩形裁剪，推理一次后按对照表逐行判定
    #  @return 协议条目列表
    #  @raises EdgeError 未装配图像处理器或帧为空时抛出，code=CONFIG/CAPTURE
    def runCropRecognition(self) -> list[AckItem]:
        stitcher = self._stitcher
        if stitcher is None:
            raise EdgeError(ErrorCode.CONFIG, "未装配图像处理器, 无法走裁剪识别")
        if not self._frames:
            raise EdgeError(ErrorCode.CAPTURE, "裁剪识别收到的帧为空")
        rows = [
            row for row in (self._roiBindingRows or [])
            if row.workerId == self._workerId
        ]
        cropped = self.cropFrame(stitcher)
        self.savePanoramaIfEnabled(cropped)
        ## 尺寸护栏：对照矩形与本路裁剪图尺寸明显错配时按未识别降级并记错
        mismatch = canvasRoiMismatch(stitcher.panoramaSize(cropped), rows)
        if mismatch:
            self.logFailure(EdgeError(ErrorCode.CAPTURE, mismatch))
            return [buildRowItem(row, False, 0.0) for row in rows]
        detections = self.runInference(cropped)
        return [self.recognizeRow(detections, row) for row in rows]

    ## @brief 按归一化矩形裁剪本路帧；未配置矩形时原样返回全图字节
    #  @param stitcher 图像处理器（复用其解码编码能力）
    #  @return 裁剪后的图像字节
    #  @raises EdgeError 帧解码失败时抛出，code=CAPTURE
    def cropFrame(self, stitcher: FrameStitcher) -> FrameImage:
        imageLibrary, arrayLibrary = stitcher.loadImageLibraries()
        image = stitcher.decodeImage(imageLibrary, arrayLibrary, self._frames[0])
        if self._cropRect is None:
            return self._frames[0]
        height, width = image.shape[:2]
        x1, y1, x2, y2 = self._cropRect
        piece = image[
            int(y1 * height):int(y2 * height),
            int(x1 * width):int(x2 * width),
        ]
        return stitcher.encodeImage(imageLibrary, piece)

    ## @brief 调试存图：本 worker 目录非空时写全景字节，并按占用阈值滚动删旧；失败只记日志不挡识别
    #  @param panorama 拼接后的全景图像字节
    #  @return 无
    def savePanoramaIfEnabled(self, panorama: FrameImage) -> None:
        saveDir = self._saveDir
        if not saveDir:
            return
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            target = Path(saveDir) / f"w{self._workerId}_{self._imageTag}_{stamp}.png"
            target.write_bytes(panorama)
            self.rollPanoramaStorage(target)
        except Exception as error:
            ## 调试存图失败不影响识别主流程：任何异常都只记日志，绝不向外抛
            self.logFailure(EdgeError(ErrorCode.CAPTURE, f"全景存图失败: {error}"))

    ## @brief 占用超阈值时按最旧顺序删全景图；删后仍超阈值记 error 但不中断识别
    #  @param protected 本轮刚写入的全景文件，删旧时跳过，避免误删本轮结果
    #  @return 无
    #  @note 各 worker 写各自目录；按修改时间与文件名排序，删旧时容忍文件已被并发删走
    def rollPanoramaStorage(self, protected: Path) -> None:
        if self._usageRatio() <= self._rollThreshold:
            return
        candidates: list[tuple[float, str, Path]] = []
        for path in Path(self._saveDir).glob(f"*_{self._imageTag}_*.png"):
            if path == protected:
                continue
            try:
                modified = path.stat().st_mtime
            except OSError:
                ## 别的线程刚把这个旧文件删走了，跳过即可
                continue
            candidates.append((modified, path.name, path))
        candidates.sort(key=lambda entry: (entry[0], entry[1]))
        for _modified, _name, candidate in candidates:
            if self._usageRatio() <= self._rollThreshold:
                break
            try:
                candidate.unlink()
            except OSError:
                ## 单个旧文件删除失败或已被别的线程删掉，都不影响本轮识别
                continue
            self.removedPanoramaCount += 1
        if self._usageRatio() > self._rollThreshold:
            self.logFailure(EdgeError(ErrorCode.CAPTURE, "全景滚动删除后仍超阈值"))

    ## @brief 单行识别：在全图检测结果里筛出完全落在 ROI 内的项，再匹配标志
    #  @param detections 全图推理得到的检测结果（带 box 字段）
    #  @param row 对照表行
    #  @return 协议条目；单行无命中按未识别上报，不牵连其他行
    def recognizeRow(self, detections: list[DetectionItem], row: RoiBindingRow) -> AckItem:
        inRoi = detectionsInRoi(detections, row, requireBox=self._requireBox)
        if not inRoi:
            return buildRowItem(row, False, 0.0)
        detected, confidence = matchMarker(
            inRoi, row.markerId, self._classItemComboMap,
        )
        return buildRowItem(row, detected, confidence)

    ## @brief 按 ROI 配置识别的备用链路：当前架构下不可用，记一条说明后直接抛配置错误
    #  @return 无；本方法不产出条目，调用后必然抛出业务异常
    #  @raises EdgeError 该备用链路不可用时抛出，code=CONFIG
    #  @note 前置条件：推理引擎必须能直接输出 roiId，区域归集与查表才有意义。
    #        实测两条后端（ultralytics / onnxruntime）产出的检测结果只有
    #        className 与 confidence 两个键，没有 roiId，按区域归集必然塌缩成一个空组，
    #        查表只能得到清一色的未识别条目，等于把故障伪装成正常结果。
    #        因此本链路直接判不可用，改为提示装载 ROI 对照表走对照表链路。
    def runConfigRecognition(self) -> list[AckItem]:
        self.logInfo("配置兜底链路不可用, 请装载 ROI 对照表")
        raise EdgeError(ErrorCode.CONFIG, "配置兜底链路不可用, 请装载 ROI 对照表")

    ## @brief 施加注入的超时上限执行推理；超时与内置异常统一转业务异常
    #  @param image 已标记 ROI 的图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 推理超时或失败时 code=INFERENCE_TIMEOUT
    #  @note 计时动作在注入的 timeoutRunner 里做：装配方若注入不计时、只直接执行推理的
    #        执行器，本层不会另外计时。超时异常会沿 recognizeRow 逐行降级，
    #        本轮跑完线程自然退出，可被 stop 回收
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

    ## @brief 普通信息日志出口，用于说明某条链路为什么不产出结果
    #  @param message 日志内容
    #  @return 无
    def logInfo(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(MODULE_NAME, f"worker-{self._workerId} {message}")
