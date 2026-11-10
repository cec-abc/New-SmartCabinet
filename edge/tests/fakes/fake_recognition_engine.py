"""推理引擎接口 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine


## @brief 返回固定结果、不做真实推理的引擎 Fake
class FakeRecognitionEngine(IRecognitionEngine):
    ## @brief 构造 Fake
    #  @param items infer 固定返回的结果列表
    def __init__(self, items: list[DetectionItem] | None = None) -> None:
        ## @brief 预设推理结果
        self.items: list[DetectionItem] = items if items is not None else []
        ## @brief 已加载的模型路径
        self.loadedPaths: list[str] = []

    ## @brief 记录模型加载
    #  @param path 模型文件路径
    #  @return 无
    def loadModel(self, path: str) -> None:
        self.loadedPaths.append(path)

    ## @brief 返回预设推理结果
    #  @param image 图像字节
    #  @return 检测结果列表
    def infer(self, image: FrameImage) -> list[DetectionItem]:
        return self.items
