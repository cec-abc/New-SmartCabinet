"""推理引擎接口定义；推理保持纯函数形态，为 rknn / .so 预留切换点。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from edge.interfaces.i_camera import FrameImage

## @brief 单条检测结果，键含类别、置信度与框坐标
DetectionItem = dict[str, object]


## @brief 推理引擎契约；控制层永远留在 Python 侧
class IRecognitionEngine(ABC):
    ## @brief 加载模型；同一实例只加载一次
    #  @param path 模型文件路径
    #  @return 无
    @abstractmethod
    def loadModel(self, path: str) -> None:
        ...

    ## @brief 对单张图执行推理
    #  @param image 图像字节
    #  @return 检测结果列表
    @abstractmethod
    def infer(self, image: FrameImage) -> list[DetectionItem]:
        ...
