"""裁剪识别模式用例：配置解析护栏、单帧裁剪识别链路、去重策略择优。

对应八路独立裁剪识别改造：recognition_mode=crop、crop_camN 归一化矩形、
dedup_strategy=best_confidence。全部用 Fake 桩，不依赖真实相机与模型。
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from edge.app_init import parseCropRects
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingRow
from edge.modules.recognition.recognition_modes import (
    RECOGNITION_MODE_CROP,
    RECOGNITION_MODE_STITCH,
)
from edge.modules.recognition.recognition_worker import RecognitionWorker
from edge.modules.recognition.recognition_stitcher import Cv2FrameStitcher
from edge.tests.fakes.fake_logger import FakeLogger


## @brief 构造一条第 1 路的 ROI 对照行，矩形落在 320x480 裁剪图左上区域
#  @param position 货位号
#  @param markerId 该货位的标志类别名
#  @return 对照表行
def makeRow(position: str = "A-01-01", markerId: str = "scissors") -> RoiBindingRow:
    return RoiBindingRow(
        roiId=f"roi_{position}", workerId=1, drawerId="A-01", position=position,
        toolId="C01-T0007", requiredType="", markerId=markerId, confidence=0.5,
        rectX1=0, rectY1=0, rectX2=300, rectY2=280,
    )


## @brief 构造一张左上角有亮块的 640x480 蓝底测试图并编码成 PNG 字节
#  @return PNG 图像字节
def makeFrameBytes() -> bytes:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[40:200, 40:260] = (255, 255, 255)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return bytes(encoded.tobytes())


## @brief 静默推理引擎桩：记录收到的图像尺寸，返回空检测
class FakeEngine:
    def __init__(self) -> None:
        self.receivedSizes: list[tuple[int, int]] = []

    ## @brief 记录输入图像宽高并返回空检测结果
    #  @param image 图像字节
    #  @return 空检测列表
    def infer(self, image: bytes) -> list[dict]:
        decoded = cv2.imdecode(
            np.frombuffer(bytearray(image), dtype=np.uint8), cv2.IMREAD_COLOR,
        )
        self.receivedSizes.append((decoded.shape[1], decoded.shape[0]))
        return []

    ## @brief 加载模型（桩空实现）
    #  @param path 权重路径
    #  @return 无
    def loadModel(self, path: str) -> None:
        pass


def makeWorker(cropRect: tuple[float, float, float, float] | None,
               drawRoiOverlay: bool = False) -> RecognitionWorker:
    return RecognitionWorker(
        1, "req-crop-001", "", FakeEngine(), FakeLogger(),
        lambda *args: None, lambda *args: None,
        {}, {}, {}, 3.0, lambda task, timeout: task(), lambda *args: (b"", b""),
        roiBindingRows=[makeRow()],
        stitcher=Cv2FrameStitcher(FakeLogger()),
        frames=(makeFrameBytes(),),
        recognitionMode=RECOGNITION_MODE_CROP,
        cropRect=cropRect,
        drawRoiOverlay=drawRoiOverlay,
    )


def testParseCropRectsAcceptsListAndMissing() -> None:
    """逗号值被配置管理器推断成 list，解析须兼容 list；缺省键等价全图。"""

    class FakeConfig:
        ## @brief 按键返回预制值，未登记的键返回空串
        #  @param section 配置节
        #  @param key 配置键
        #  @param default 缺省值
        #  @return 预制值或缺省值
        def get(self, section: str, key: str, default: object = None) -> object:
            data = {
                "crop_cam1": [0.1, 0.0, 1.0, 1.0],
                "crop_cam2": "0.0,0.0,0.3,1.0",
            }
            return data.get(key, default)

    rects = parseCropRects(FakeConfig())  # type: ignore[arg-type]
    assert rects[1] == (0.1, 0.0, 1.0, 1.0)
    assert rects[2] == (0.0, 0.0, 0.3, 1.0)
    assert 3 not in rects


def testParseCropRectsRejectsMalformed() -> None:
    """矩形越界或畸形时启动即判配置错误，不静默放行。"""

    class FakeConfig:
        ## @brief 按键返回非法矩形
        #  @param section 配置节
        #  @param key 配置键
        #  @param default 缺省值
        #  @return 预制值或缺省值
        def get(self, section: str, key: str, default: object = None) -> object:
            return {"crop_cam1": [0.5, 0.0, 0.2, 1.0]}.get(key, default)

    with pytest.raises(EdgeError) as info:
        parseCropRects(FakeConfig())  # type: ignore[arg-type]
    assert info.value.code == ErrorCode.CONFIG


def testCropRecognitionCutsFrameByRatio() -> None:
    """crop 模式按归一化矩形裁图后推理：引擎收到裁剪图尺寸而非原图尺寸。"""
    worker = makeWorker((0.5, 0.0, 1.0, 1.0))
    items = worker.runCropRecognition()
    engine = worker._engine
    assert len(items) == 1 and items[0]["alert_type"] == "unknown"
    assert engine.receivedSizes == [(320, 480)]


def testCropRecognitionWithoutRectUsesFullFrame() -> None:
    """未配置裁剪矩形时整图送推理，等价不裁剪。"""
    worker = makeWorker(None)
    worker.runCropRecognition()
    engine = worker._engine
    assert engine.receivedSizes == [(640, 480)]


def testStitchModeStillInferenceOnceOnPanorama() -> None:
    """stitch 模式不受影响：双摄帧仍拼全景推理一次。"""
    left = makeFrameBytes()
    right = makeFrameBytes()
    worker = RecognitionWorker(
        1, "req-stitch-001", "", FakeEngine(), FakeLogger(),
        lambda *args: None, lambda *args: None,
        {}, {}, {}, 3.0, lambda task, timeout: task(), lambda *args: (b"", b""),
        roiBindingRows=[makeRow()],
        stitcher=Cv2FrameStitcher(FakeLogger()),
        frames=(left, right),
        recognitionMode=RECOGNITION_MODE_STITCH,
    )
    items = worker.runTableRecognition()
    assert items
    engine = worker._engine
    assert engine.receivedSizes == [(640, 480)]


def testRoiOverlayDrawsRectAndKeepsSize() -> None:
    """绘制开关开启：存图叠加 ROI 框与货位标识，尺寸不变、字节变化。"""
    worker = makeWorker(None, drawRoiOverlay=True)
    original = makeFrameBytes()
    drawn = worker.renderRoiOverlayOnImage(original)
    assert drawn != original
    decoded = cv2.imdecode(
        np.frombuffer(bytearray(drawn), dtype=np.uint8), cv2.IMREAD_COLOR,
    )
    assert decoded.shape[:2] == (480, 640)


def testRoiOverlayOffReturnsOriginal() -> None:
    """绘制开关关闭：存图字节原样返回，不多不少。"""
    worker = makeWorker(None, drawRoiOverlay=False)
    original = makeFrameBytes()
    assert worker.renderRoiOverlayOnImage(original) == original
