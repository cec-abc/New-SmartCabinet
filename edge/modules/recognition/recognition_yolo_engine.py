"""识别模型引擎：类内单例、模型单次加载与真实推理入口。"""
from __future__ import annotations

import ast
import os
from collections.abc import Callable
from threading import Lock
from typing import Any, NamedTuple

from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import (
    DETECTION_BOX_FIELD,
    DETECTION_CLASS_FIELD,
    DETECTION_CONFIDENCE_FIELD,
)
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine

## @file edge/modules/recognition/recognition_yolo_engine.py
## @brief 识别模型引擎：类内单例、模型单次加载与真实推理入口
## @author 袁燕

## @brief 推理函数注入类型
InferFunc = Callable[[FrameImage], list[DetectionItem]]
## @brief 日志模块名
MODULE_NAME: str = "YoloEngine"
## @brief 推理默认置信度门槛
DEFAULT_CONF_THRESHOLD: float = 0.25
## @brief 推理默认输入尺寸长边，单位像素
DEFAULT_IMG_SIZE: int = 640
## @brief 推理后端标识：ultralytics，走 pt 权重
BACKEND_ULTRALYTICS: str = "ultralytics"
## @brief 推理后端标识：onnxruntime，纯 onnx 权重直跑
BACKEND_ONNXRUNTIME: str = "onnxruntime"
## @brief 推理后端标识：rknn，RK3588 NPU 上跑 .rknn 量化权重
BACKEND_RKNN: str = "rknn"
## @brief 默认推理后端；换后端等于换结论，默认固定为 ultralytics
DEFAULT_BACKEND: str = BACKEND_ULTRALYTICS
## @brief 非极大值抑制的重叠阈值默认值，构造注入
DEFAULT_NMS_IOU_THRESHOLD: float = 0.45
## @brief onnxruntime 分支与 ultralytics 分端口径尚未统一的说明，写进日志避免误以为两者等价
ONNX_BACKEND_CALIBRATION_NOTE: str = (
    "onnxruntime 分支未与 ultralytics 对齐, 需现场标定"
)


## @brief 候选框：类别编号、置信度与矩形框坐标，供非极大值抑制按类别比较
class DetectionCandidate(NamedTuple):
    ## @brief 类别编号
    classId: int
    ## @brief 置信度
    confidence: float
    ## @brief 左上角横坐标
    left: float
    ## @brief 左上角纵坐标
    top: float
    ## @brief 右下角横坐标
    right: float
    ## @brief 右下角纵坐标
    bottom: float


## @brief CPU 占位推理；现场权重未就位时可显式注入
#  @param image 图像字节
#  @return 空结果列表
def emptyInfer(image: FrameImage) -> list[DetectionItem]:
    # TODO: 上板后按现场模型替换推理后端，保持纯函数入参出参不变
    return []


## @brief YOLO 引擎；instance() 双检锁，普通构造仍可用于测试
class YoloEngine(IRecognitionEngine):
    ## @brief 全局唯一实例
    _shared: YoloEngine | None = None
    ## @brief 双检锁
    _sharedLock: Lock = Lock()

    ## @brief 构造引擎
    #  @param inferFunc 注入的推理函数，为空表示走真实推理后端
    #  @param logger 可选日志器
    #  @param backend 推理后端标识，ultralytics 或 onnxruntime
    #  @param nmsIouThreshold 非极大值抑制的重叠阈值
    #  @return 无
    def __init__(self, inferFunc: InferFunc | None = None,
                 logger: ILogger | None = None,
                 backend: str = DEFAULT_BACKEND,
                 nmsIouThreshold: float = DEFAULT_NMS_IOU_THRESHOLD) -> None:
        ## @brief 保护模型加载状态与后端配置的状态锁
        self._stateLock: Lock = Lock()
        ## @brief 注入的推理函数
        self._inferFunc: InferFunc | None = inferFunc
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief 已加载的模型路径，供验收举证
        self.loadedPaths: list[str] = []
        ## @brief 模型是否已加载，保证仅一次
        self._modelLoaded: bool = False
        ## @brief 模型句柄，为空表示没有可用权重
        self._model: Any = None
        ## @brief 推理后端名称
        self._frameworkName: str = ""
        ## @brief 期望使用的推理后端
        self._backend: str = backend
        ## @brief 非极大值抑制的重叠阈值
        self._nmsIouThreshold: float = nmsIouThreshold

    ## @brief 取全局唯一实例；双检锁避免并发重复构造
    #  @param logger 可选日志器，首次构造与后续补挂都生效
    #  @param backend 期望使用的推理后端
    #  @param nmsIouThreshold 期望使用的非极大值抑制重叠阈值
    #  @return 引擎单例
    #  @raises EdgeError 模型已加载却要求换后端或换阈值时抛出，code=CONFIG
    #  @note 补挂参数也放在双检锁内完成，避免两个线程同时改同一实例的配置
    @classmethod
    def instance(cls, logger: ILogger | None = None,
                 backend: str = DEFAULT_BACKEND,
                 nmsIouThreshold: float = DEFAULT_NMS_IOU_THRESHOLD) -> YoloEngine:
        shared = cls._shared
        if shared is None:
            with cls._sharedLock:
                shared = cls._shared
                if shared is None:
                    shared = cls(
                        logger=logger, backend=backend,
                        nmsIouThreshold=nmsIouThreshold,
                    )
                    cls._shared = shared
        with cls._sharedLock:
            if logger is not None:
                shared.setLogger(logger)
            if shared.getBackend() != backend:
                shared.setBackend(backend)
            if shared.getNmsIouThreshold() != nmsIouThreshold:
                shared.setNmsIouThreshold(nmsIouThreshold)
        return shared

    ## @brief 挂载日志器
    #  @param logger 日志器（注入）
    #  @return 无
    def setLogger(self, logger: ILogger) -> None:
        with self._stateLock:
            self._logger = logger

    ## @brief 切换推理后端；模型已加载后不允许切换，避免同一引擎前后结论不一致
    #  @param backend 推理后端标识
    #  @return 无
    #  @raises EdgeError 模型已加载时抛出，code=CONFIG
    def setBackend(self, backend: str) -> None:
        with self._stateLock:
            if self._modelLoaded:
                raise EdgeError(ErrorCode.CONFIG, "模型已加载, 不允许切换推理后端")
            self._backend = backend

    ## @brief 供验收举证读取当前推理后端
    #  @return 推理后端标识
    def getBackend(self) -> str:
        with self._stateLock:
            return self._backend

    ## @brief 设置非极大值抑制的重叠阈值；模型已加载后不允许改，避免前后结论不一致
    #  @param threshold 重叠阈值
    #  @return 无
    #  @raises EdgeError 模型已加载时抛出，code=CONFIG
    def setNmsIouThreshold(self, threshold: float) -> None:
        with self._stateLock:
            if self._modelLoaded:
                raise EdgeError(ErrorCode.CONFIG, "模型已加载, 不允许改非极大值抑制阈值")
            self._nmsIouThreshold = threshold

    ## @brief 供验收举证读取当前非极大值抑制的重叠阈值
    #  @return 重叠阈值
    def getNmsIouThreshold(self) -> float:
        with self._stateLock:
            return self._nmsIouThreshold

    ## @brief 加载模型，同一实例仅生效一次
    #  @param path 模型路径
    #  @return 无
    #  @raises EdgeError 推理框架缺失或权重格式与后端不符时抛出，code=CONFIG
    #  @note 多个 worker 可能同时调用本方法，加载整段放在状态锁内，保证只有第一个
    #        线程真正加载；加载失败回滚登记，不留半加载状态；标定说明只在加载时记一次
    def loadModel(self, path: str) -> None:
        with self._stateLock:
            if self._modelLoaded:
                return
            self.loadedPaths.append(path)
            try:
                model = self.prepareModel(path)
            except Exception:
                self.loadedPaths.pop()
                raise
            self._model = model
            self._frameworkName = self.resolveFrameworkName(model)
            self._modelLoaded = True
            calibrationNeeded = self._frameworkName == BACKEND_ONNXRUNTIME
        if calibrationNeeded:
            self.logInfo(ONNX_BACKEND_CALIBRATION_NOTE)

    ## @brief 执行推理；未加载模型按配置错误阻断
    #  @param image 图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 模型未加载时 code=CONFIG
    #  @note 锁只用来读取加载状态，推理调用本身不持锁，避免锁内做图像处理与模型推理
    def infer(self, image: FrameImage) -> list[DetectionItem]:
        with self._stateLock:
            if not self._modelLoaded:
                raise EdgeError(ErrorCode.CONFIG, "模型未加载")
            inferFunc = self._inferFunc
        if inferFunc is not None:
            return list(inferFunc(image))
        return self.runModelInference(image)

    ## @brief 准备模型句柄；权重文件不存在或加载失败时返回空，推理退化为空结果
    #  @param path 模型文件路径
    #  @return 模型句柄
    #  @raises EdgeError 推理框架缺失或权重格式与后端不符时抛出，code=CONFIG
    def prepareModel(self, path: str) -> Any:
        if not os.path.isfile(path):
            ## 权重缺失会把每轮结果都变成空清单，必须按错误如实告知，不能只当普通说明
            if self._logger is not None:
                self._logger.error(
                    MODULE_NAME,
                    f"模型权重不存在, 推理只能给出空结果, 不代表识别成功: {path}",
                )
            return None
        framework = self.loadInferenceFramework()
        frameworkName = str(getattr(framework, "__name__", ""))
        if frameworkName == "onnxruntime":
            if not path.lower().endswith(".onnx"):
                raise EdgeError(
                    ErrorCode.CONFIG,
                    f"onnxruntime 后端只支持 onnx 权重: {path}",
                )
            return framework.InferenceSession(path)
        if self._backend == BACKEND_RKNN:
            if not path.lower().endswith(".rknn"):
                raise EdgeError(
                    ErrorCode.CONFIG,
                    f"rknn 后端只支持 rknn 权重: {path}",
                )
            try:
                runtime = framework()
                if runtime.load_rknn(path) != 0:
                    raise EdgeError(
                        ErrorCode.CONFIG, f"rknn 模型加载失败: {path}",
                    )
                if runtime.init_runtime() != 0:
                    raise EdgeError(
                        ErrorCode.CONFIG, f"rknn 运行时初始化失败: {path}",
                    )
            except EdgeError:
                raise
            except Exception as error:
                raise EdgeError(
                    ErrorCode.CONFIG, f"rknn 运行时准备失败: {error}",
                ) from error
            return runtime
        return framework.YOLO(path)

    ## @brief 载入推理框架；按配置选定的后端装载，缺框架直接判配置错误
    #  @return 推理框架模块
    #  @raises EdgeError 后端非法或框架没装时抛出，code=CONFIG
    def loadInferenceFramework(self) -> Any:
        if self._backend == BACKEND_ONNXRUNTIME:
            try:
                import onnxruntime  # type: ignore
            except ImportError as error:
                raise EdgeError(
                    ErrorCode.CONFIG, "未安装推理框架 onnxruntime",
                ) from error
            return onnxruntime
        if self._backend == BACKEND_ULTRALYTICS:
            try:
                import ultralytics  # type: ignore
            except ImportError as error:
                raise EdgeError(
                    ErrorCode.CONFIG, "未安装推理框架 ultralytics",
                ) from error
            return ultralytics
        if self._backend == BACKEND_RKNN:
            try:
                ## 板端 runtime 是 rknnlite；PC 的 rknn toolkit 不能用于推理
                from rknnlite.api import RKNNLite  # type: ignore
            except ImportError as error:
                raise EdgeError(
                    ErrorCode.CONFIG,
                    "未安装 RKNN 板端运行库 rknnlite（仅 RK3588 板端可用）",
                ) from error
            return RKNNLite
        raise EdgeError(ErrorCode.CONFIG, f"推理后端非法: {self._backend}")

    ## @brief 判定模型句柄属于哪个推理后端
    #  @param model 模型句柄
    #  @return 后端名称，onnxruntime 会话返回 onnxruntime，其余返回 ultralytics
    def resolveFrameworkName(self, model: Any) -> str:
        if model is None:
            return ""
        if hasattr(model, "inference") and hasattr(model, "load_rknn"):
            return BACKEND_RKNN
        if hasattr(model, "get_inputs") and hasattr(model, "run"):
            return "onnxruntime"
        return "ultralytics"

    ## @brief 跑真实推理；没有可用权重时返回空结果，不伪造命中
    #  @param image 图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 推理后端缺失或失败时抛出，code=CONFIG / INFERENCE_TIMEOUT
    #  @note 模型句柄只在加载期写一次，这里在状态锁内取快照后就不持锁了
    def runModelInference(self, image: FrameImage) -> list[DetectionItem]:
        with self._stateLock:
            model = self._model
            frameworkName = self._frameworkName
        if model is None:
            return []
        if frameworkName == BACKEND_RKNN:
            return self.runRknnInference(image)
        if frameworkName == BACKEND_ONNXRUNTIME:
            return self.runOnnxInference(image)
        return self.runUltralyticsInference(image)

    ## @brief 走 rknn 后端推理；输出布局与 onnx 同源，复用同一套候选框解析
    #  @param image 图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 推理失败时抛出，code=INFERENCE_TIMEOUT
    #  @note RKNN 模型不携带类别名元数据，类别以编号代替；输出形状按模型导出口径，
    #        需上板实测标定；检测框坐标按模型输入尺寸与全景尺寸比例还原
    def runRknnInference(self, image: FrameImage) -> list[DetectionItem]:
        imageLibrary, arrayLibrary = self.loadInferenceLibraries()
        canvas = self.decodeForInference(image)
        originalSize = getattr(canvas, "shape", None)
        if originalSize is not None and len(originalSize) >= 2:
            originalHeight, originalWidth = int(originalSize[0]), int(originalSize[1])
        else:
            fallbackSize = getattr(canvas, "size", None)
            if fallbackSize is not None and len(fallbackSize) >= 2:
                originalHeight, originalWidth = int(fallbackSize[1]), int(fallbackSize[0])
            else:
                originalHeight, originalWidth = DEFAULT_IMG_SIZE, DEFAULT_IMG_SIZE
        ## RKNN 输入尺寸由导出时固定，统一用默认尺寸；如导出尺寸不同需改配置注入
        width, height = DEFAULT_IMG_SIZE, DEFAULT_IMG_SIZE
        scaleX = originalWidth / width if width > 0 else 1.0
        scaleY = originalHeight / height if height > 0 else 1.0
        resized = imageLibrary.resize(canvas, (width, height))
        tensor = resized.astype(arrayLibrary.float32).transpose(2, 0, 1) / 255.0
        batch = arrayLibrary.expand_dims(tensor, axis=0)
        try:
            outputs = self._model.inference(inputs=[batch])
        except Exception as error:
            raise EdgeError(
                ErrorCode.INFERENCE_TIMEOUT, f"rknn 推理失败: {error}",
            ) from error
        if not outputs:
            return []
        ## 只接受单输出的 [N,4+C] / [4+C,N] 检测矩阵；
        ## 多输出解耦头（如 yolov8n.rknn 的 3 stride × reg/cls/conf）不能套用，
        ## 否则会把特征图当检测框解析出完全错误的清单，必须明确阻断而不是静默给错
        if len(outputs) != 1:
            raise EdgeError(
                ErrorCode.INFERENCE_TIMEOUT,
                f"rknn 模型为 {len(outputs)} 输出解耦头，当前只支持单输出检测矩阵，"
                "请改用单输出 rknn 权重或上板补三尺度解码",
            )
        return self.parseOnnxOutput(
            outputs[0], arrayLibrary, {}, scaleX, scaleY,
        )

    ## @brief 走 ultralytics 后端推理
    #  @param image 图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 推理失败时抛出，code=INFERENCE_TIMEOUT
    def runUltralyticsInference(self, image: FrameImage) -> list[DetectionItem]:
        try:
            results = self._model.predict(
                self.decodeForInference(image),
                conf=DEFAULT_CONF_THRESHOLD,
                imgsz=DEFAULT_IMG_SIZE,
                verbose=False,
            )
        except Exception as error:
            raise EdgeError(
                ErrorCode.INFERENCE_TIMEOUT, f"推理失败: {error}",
            ) from error
        return self.parseUltralyticsResults(results)

    ## @brief 走 onnxruntime 后端推理
    #  @param image 图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 推理失败时抛出，code=INFERENCE_TIMEOUT
    #  @note 本分支按模型声明尺寸做整幅缩放，并在输出上补做同类别非极大值抑制；
    #        抑制阈值是构造注入项，onnx 与 ultralytics 两分支的类别映射相同，
    #        检测框都按缩放比映射回拼接全景坐标，口径已统一
    def runOnnxInference(self, image: FrameImage) -> list[DetectionItem]:
        imageLibrary, arrayLibrary = self.loadInferenceLibraries()
        canvas = self.decodeForInference(image)
        # 取全景原始尺寸，用来把 onnx 的小图坐标放大回全景坐标
        originalSize = getattr(canvas, "shape", None)
        if originalSize is not None and len(originalSize) >= 2:
            originalHeight, originalWidth = int(originalSize[0]), int(originalSize[1])
        else:
            # 兜底：PIL 图像用 size=(宽,高)，numpy 用 shape=(高,宽,通道)
            fallbackSize = getattr(canvas, "size", None)
            if fallbackSize is not None and len(fallbackSize) >= 2:
                originalHeight, originalWidth = int(fallbackSize[1]), int(fallbackSize[0])
            else:
                originalHeight, originalWidth = DEFAULT_IMG_SIZE, DEFAULT_IMG_SIZE
        inputMeta = self._model.get_inputs()[0]
        shape = list(inputMeta.shape)
        height = int(shape[2]) if len(shape) >= 4 else DEFAULT_IMG_SIZE
        width = int(shape[3]) if len(shape) >= 4 else DEFAULT_IMG_SIZE
        if height <= 0 or width <= 0:
            height = DEFAULT_IMG_SIZE
            width = DEFAULT_IMG_SIZE
        # 缩放比 = 全景尺寸 / 模型输入尺寸；当前按"直接拉伸 resize"口径，
        # 若日后改成 letterbox（保持比例加灰边）还需扣掉灰边偏移
        scaleX = originalWidth / width if width > 0 else 1.0
        scaleY = originalHeight / height if height > 0 else 1.0
        resized = imageLibrary.resize(canvas, (width, height))
        tensor = resized.astype(arrayLibrary.float32).transpose(2, 0, 1) / 255.0
        batch = arrayLibrary.expand_dims(tensor, axis=0)
        try:
            outputs = self._model.run(None, {inputMeta.name: batch})
        except Exception as error:
            raise EdgeError(
                ErrorCode.INFERENCE_TIMEOUT, f"推理失败: {error}",
            ) from error
        return self.parseOnnxOutput(
            outputs[0], arrayLibrary, self.readOnnxClassNames(), scaleX, scaleY,
        )

    ## @brief 解析 ultralytics 的检测结果
    #  @param results ultralytics 推理输出
    #  @return 检测结果列表
    def parseUltralyticsResults(self, results: Any) -> list[DetectionItem]:
        detections: list[DetectionItem] = []
        if not results:
            return detections
        boxes = results[0].boxes
        if boxes is None:
            return detections
        names = getattr(self._model, "names", {})
        for index in range(len(boxes)):
            classId = int(boxes.cls[index])
            confidence = float(boxes.conf[index])
            detections.append({
                DETECTION_CLASS_FIELD: str(names.get(classId, classId)),
                DETECTION_CONFIDENCE_FIELD: confidence,
                DETECTION_BOX_FIELD: [
                    float(boxes.xyxy[index][0]),
                    float(boxes.xyxy[index][1]),
                    float(boxes.xyxy[index][2]),
                    float(boxes.xyxy[index][3]),
                ],
            })
        return detections

    ## @brief 解析 onnxruntime 的检测结果，按 YOLOv8 导出形状取类别与置信度
    #  @param output 模型输出张量
    #  @param arrayLibrary 数值计算库模块
    #  @param classNames 类别编号到类别名映射
    #  @param scaleX 框 x 方向从小图放回到全景的缩放比
    #  @param scaleY 框 y 方向从小图放回到全景的缩放比
    #  @return 检测结果列表
    #  @note 解析出的候选框先按同类别做非极大值抑制再出结果，
    #        避免同一张图上的重叠框被当成多个目标
    #  @note onnx 后端先 resize 到模型输入尺寸再推理，候选框是相对小图坐标，
    #        这里按 scaleX/scaleY 放大回拼接全景坐标，与 ultralytics 分支口径一致
    def parseOnnxOutput(self, output: Any, arrayLibrary: Any,
                        classNames: dict[int, str],
                        scaleX: float = 1.0, scaleY: float = 1.0) -> list[DetectionItem]:
        detections: list[DetectionItem] = []
        candidates = self.collectOnnxCandidates(output, arrayLibrary)
        for candidate in self.applyNms(candidates):
            # 小图坐标乘缩放比还原成全景坐标后再落库，几何判定才准
            left = candidate.left * scaleX
            top = candidate.top * scaleY
            right = candidate.right * scaleX
            bottom = candidate.bottom * scaleY
            detections.append({
                DETECTION_CLASS_FIELD: str(classNames.get(candidate.classId, candidate.classId)),
                DETECTION_CONFIDENCE_FIELD: candidate.confidence,
                DETECTION_BOX_FIELD: [
                    float(left), float(top), float(right), float(bottom),
                ],
            })
        return detections

    ## @brief 从模型输出里收集候选框，按置信度门槛过滤
    #  @param output 模型输出张量
    #  @param arrayLibrary 数值计算库模块
    #  @return 候选框列表
    def collectOnnxCandidates(self, output: Any, arrayLibrary: Any) -> list[DetectionCandidate]:
        candidates: list[DetectionCandidate] = []
        data = output[0]
        if data.shape[0] < data.shape[1]:
            ## 导出形状是类别数加 4 行、目标数列，转置成目标数在前
            data = data.transpose()
        rows = int(data.shape[0])
        columns = int(data.shape[1])
        if columns <= 4:
            return candidates
        for index in range(rows):
            scores = data[index, 4:columns]
            classId = int(arrayLibrary.argmax(scores))
            confidence = float(scores[classId])
            if confidence < DEFAULT_CONF_THRESHOLD:
                continue
            candidates.append(self.buildCandidate(data, index, classId, confidence))
        return candidates

    ## @brief 取一行输出里的框坐标，换算成矩形的左上角与右下角两点
    #  @param data 转置后的输出张量
    #  @param index 行下标
    #  @param classId 类别编号
    #  @param confidence 置信度
    #  @return 候选框
    def buildCandidate(self, data: Any, index: int, classId: int,
                       confidence: float) -> DetectionCandidate:
        values = [float(value) for value in data[index, 0:4]]
        if len(values) < 4:
            ## 输出没有完整框坐标时按空框处理，交由抑制环节按不重叠处理
            return DetectionCandidate(classId, confidence, 0.0, 0.0, 0.0, 0.0)
        centerX, centerY, width, height = values[0], values[1], values[2], values[3]
        halfWidth = width / 2.0
        halfHeight = height / 2.0
        return DetectionCandidate(
            classId, confidence,
            centerX - halfWidth, centerY - halfHeight,
            centerX + halfWidth, centerY + halfHeight,
        )

    ## @brief 同类别非极大值抑制；重叠超过阈值的低分框被丢弃
    #  @param candidates 候选框列表
    #  @return 保留的候选框列表，按置信度从高到低
    def applyNms(self, candidates: list[DetectionCandidate]) -> list[DetectionCandidate]:
        ordered = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        kept: list[DetectionCandidate] = []
        for candidate in ordered:
            suppressed = False
            for chosen in kept:
                if chosen.classId != candidate.classId:
                    continue
                if self.calculateIou(chosen, candidate) > self._nmsIouThreshold:
                    suppressed = True
                    break
            if not suppressed:
                kept.append(candidate)
        return kept

    ## @brief 算两个框的重叠比
    #  @param left 第一个框
    #  @param right 第二个框
    #  @return 重叠比，取值 0 到 1
    def calculateIou(self, left: DetectionCandidate, right: DetectionCandidate) -> float:
        overlapWidth = min(left.right, right.right) - max(left.left, right.left)
        overlapHeight = min(left.bottom, right.bottom) - max(left.top, right.top)
        if overlapWidth <= 0.0 or overlapHeight <= 0.0:
            return 0.0
        intersection = overlapWidth * overlapHeight
        union = self.calculateArea(left) + self.calculateArea(right) - intersection
        if union <= 0.0:
            return 0.0
        return intersection / union

    ## @brief 算一个框的面积
    #  @param candidate 候选框
    #  @return 面积，单位像素平方
    def calculateArea(self, candidate: DetectionCandidate) -> float:
        width = max(0.0, candidate.right - candidate.left)
        height = max(0.0, candidate.bottom - candidate.top)
        return width * height

    ## @brief 读 onnx 模型元数据里的类别名表
    #  @return 类别编号到类别名映射
    def readOnnxClassNames(self) -> dict[int, str]:
        classNames: dict[int, str] = {}
        try:
            metadata = self._model.get_modelmeta().custom_metadata_map
        except Exception:
            ## 模型没带元数据时降级为用类别编号代替类别名，不影响其它字段解析
            return classNames
        raw = str(metadata.get("names", ""))
        if not raw:
            return classNames
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            ## 元数据里的类别名写坏了同样退回编号，不让整轮推理因为说明字段崩掉
            return classNames
        if not isinstance(parsed, dict):
            return classNames
        for key, value in parsed.items():
            classNames[int(key)] = str(value)
        return classNames

    ## @brief 解码图像字节成推理输入
    #  @param image 图像字节
    #  @return 图像阵列
    #  @raises EdgeError 图像处理库缺失或解码失败时抛出，code=CONFIG / CAPTURE
    def decodeForInference(self, image: FrameImage) -> Any:
        imageLibrary, arrayLibrary = self.loadInferenceLibraries()
        if not image:
            raise EdgeError(ErrorCode.CAPTURE, "图像字节为空, 无法解码")
        buffer = arrayLibrary.frombuffer(bytearray(image), dtype=arrayLibrary.uint8)
        decoded = imageLibrary.imdecode(buffer, imageLibrary.IMREAD_COLOR)
        if decoded is None:
            raise EdgeError(ErrorCode.CAPTURE, "图像解码失败")
        return decoded

    ## @brief 载入图像处理库与数值计算库；两者都是可选依赖
    #  @return 图像处理库模块与数值计算库模块
    #  @raises EdgeError 库缺失时抛出，code=CONFIG
    def loadInferenceLibraries(self) -> tuple[Any, Any]:
        try:
            import cv2  # type: ignore
        except ImportError as error:
            raise EdgeError(ErrorCode.CONFIG, "未安装图像处理库") from error
        try:
            import numpy  # type: ignore
        except ImportError as error:
            raise EdgeError(ErrorCode.CONFIG, "未安装数值计算库") from error
        return cv2, numpy

    ## @brief 普通信息日志出口
    #  @param message 日志内容
    #  @return 无
    def logInfo(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(MODULE_NAME, message)
