"""识别模型引擎：类内单例、模型单次加载与推理纯函数入口。"""
from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine

## @brief 推理函数注入类型
InferFunc = Callable[[FrameImage], list[DetectionItem]]


## @brief CPU 占位推理；真实 rknn 调用留上板切换点
#  @param image 图像字节
#  @return 空结果列表
def emptyInfer(image: FrameImage) -> list[DetectionItem]:
    # TODO: 上板后替换为 rknn 推理，保持纯函数入参出参不变
    return []


## @brief YOLO 引擎；instance() 双检锁，普通构造仍可用于测试
class YoloEngine(IRecognitionEngine):
    ## @brief 全局唯一实例
    _shared: YoloEngine | None = None
    ## @brief 双检锁
    _sharedLock: Lock = Lock()

    ## @brief 构造引擎
    #  @param inferFunc 注入的推理函数，默认 CPU 占位
    def __init__(self, inferFunc: InferFunc | None = None) -> None:
        ## @brief 注入的推理函数
        self._inferFunc: InferFunc = inferFunc if inferFunc is not None else emptyInfer
        ## @brief 已加载的模型路径，供验收举证
        self.loadedPaths: list[str] = []
        ## @brief 模型是否已加载，保证仅一次
        self._modelLoaded: bool = False

    ## @brief 取全局唯一实例；双检锁避免并发重复构造
    #  @return 引擎单例
    @classmethod
    def instance(cls) -> YoloEngine:
        shared = cls._shared
        if shared is None:
            with cls._sharedLock:
                shared = cls._shared
                if shared is None:
                    shared = cls()
                    cls._shared = shared
        return shared

    ## @brief 加载模型，同一实例仅生效一次
    #  @param path 模型路径
    #  @return 无
    def loadModel(self, path: str) -> None:
        if self._modelLoaded:
            return
        # TODO: rknn 模型加载切换点，当前只记录路径不读真实权重
        self.loadedPaths.append(path)
        self._modelLoaded = True

    ## @brief 执行推理；未加载模型按配置错误阻断
    #  @param image 图像字节
    #  @return 检测结果列表
    #  @raises EdgeError 模型未加载时 code=CONFIG
    def infer(self, image: FrameImage) -> list[DetectionItem]:
        if not self._modelLoaded:
            raise EdgeError(ErrorCode.CONFIG, "模型未加载")
        return list(self._inferFunc(image))
