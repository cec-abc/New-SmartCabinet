"""本轮新增单测：逐路对焦/变焦、全图推理恰好一次、ROI 位置判定、存图开关、单层布局开关。

对应需求 SR_0302_FUNC_FOCUS_08 / PANO_09 / KEY_PERF_3 的可观测口径，
以及 dplus §7-3（items 四键）、§7-6（重复请求不重复扫描）的补充举证。
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from edge.app_init import (
    LAYER_MODE_SINGLE,
    flagEnabled,
    normalizeOpticalValues,
    readCaptureLayout,
)
from edge.exceptions import EdgeError
from edge.infra.roi_binding_loader import RoiBindingLoader
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.modules.recognition.recognition_stitcher import Cv2FrameStitcher
from edge.modules.recognition.recognition_utils import isBoxFullyInsideRoi
from edge.modules.recognition.recognition_worker import RecognitionWorker
from edge.modules.usb.usb_controller import UsbController
from edge.tests.fakes.fake_camera_focus import FakeCameraFocus
from edge.tests.fakes.fake_config import FakeConfig
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_sinks import FakeCaptureSink

## @file edge/tests/unit/test_dplus_flow_and_switches.py
## @brief 全流程关键环节、逐路对焦变焦与新增开关的单测
## @author 袁燕

## @brief 工程根
EDGE_ROOT: Path = Path(__file__).resolve().parents[2]
## @brief ROI 对照表路径
ROI_CSV: Path = EDGE_ROOT / "config" / "roi_binding.csv"
## @brief 联调采集目录列表
CAPTURE_DIRS: list[str] = [
    "./output/capture/w1", "./output/capture/w2",
    "./output/capture/w3", "./output/capture/w4",
]
## @brief 联调识别目录列表
RECOG_DIRS: list[str] = [
    "./output/recog/w1", "./output/recog/w2",
    "./output/recog/w3", "./output/recog/w4",
]


## @brief 计数识别引擎：记录 infer 调用次数，返回空检测（不伪造命中）
class CountingEngine(IRecognitionEngine):
    ## @brief 构造
    def __init__(self) -> None:
        self.inferCount = 0
        self.lastImage: object = None

    ## @brief 加载模型：本计数桩无需真实权重
    #  @param path 模型路径
    #  @return 无
    def loadModel(self, path: str) -> None:
        return None

    ## @brief 推理并记录次数
    #  @param image 图像字节
    #  @return 空检测结果（本用例只计数，不依赖命中）
    def infer(self, image: object) -> list[DetectionItem]:
        self.inferCount += 1
        self.lastImage = image
        return []


## 对应性能需求：真实 worker 的 runTableRecognition 对全景只推理一次，不随 ROI 行数放大
def testInferenceCalledOnceRegardlessOfRoiRows() -> None:
    from dataclasses import replace

    import cv2
    import numpy as np

    logger = FakeLogger()
    base = RoiBindingLoader(logger).load(str(ROI_CSV))[0]
    ## 人为造 3 行同属 worker 1 的 ROI，验证多行位置判定不会放大推理次数
    rows = [
        replace(base, roiId="t1", workerId=1, position="T-01", rectX1=0,
                rectY1=0, rectX2=100, rectY2=100),
        replace(base, roiId="t2", workerId=1, position="T-02", rectX1=100,
                rectY1=0, rectX2=200, rectY2=100),
        replace(base, roiId="t3", workerId=1, position="T-03", rectX1=0,
                rectY1=100, rectX2=100, rectY2=200),
    ]
    ## 造一对占位双帧，交给真实拼接器拼出全景
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", frame)
    assert ok
    fakeFrame = bytes(encoded.tobytes())
    engine = CountingEngine()
    stitcher = Cv2FrameStitcher(logger)

    def timeoutRunner(task: Callable[[], list[DetectionItem]],
                      timeout: float) -> list[DetectionItem]:
        return task()

    worker = RecognitionWorker(
        1, "req-once", "", engine, logger,
        lambda wid, ack, rid: None, lambda wid, err: None,
        {}, {}, {}, 3.0, timeoutRunner, lambda d, i: (fakeFrame, fakeFrame),
        roiBindingRows=rows, stitcher=stitcher, frames=(fakeFrame, fakeFrame),
    )
    items = worker.runTableRecognition()
    assert len(items) == len(rows), "每行 ROI 都应产出一条清单"
    assert engine.inferCount == 1, "真实全图链路只应推理一次，ROI 位置判定不触发额外推理"


## 对应 §7-3/位置判定：框完全落入 ROI 才命中，越界一像素即不命中
def testBoxFullyInsideRoiStrictGeometry() -> None:
    row = RoiBindingLoader(FakeLogger()).load(str(ROI_CSV))[0]
    assert isBoxFullyInsideRoi(
        (row.rectX1, row.rectY1, row.rectX2, row.rectY2), row,
    ) is True
    assert isBoxFullyInsideRoi(
        (row.rectX1 - 1, row.rectY1, row.rectX2, row.rectY2), row,
    ) is False
    assert isBoxFullyInsideRoi(None, row) is False


## 对应存图开关：flagEnabled 兼容布尔与字符串两种口径
@pytest.mark.parametrize("value,expected", [
    (True, True), (False, False),
    ("true", True), ("false", False),
    ("0", False), ("1", True), ("off", False), ("", False),
])
def testFlagEnabledHandlesBoolAndString(value: object, expected: bool) -> None:
    assert flagEnabled(value) is expected


## 对应存图开关：save_frames=false 时采集目录被置空，落盘自动短路
def testSaveFramesFalseClearsCaptureDirs() -> None:
    config = FakeConfig({
        "log.dir": "./logs",
        "usb.save_dirs": CAPTURE_DIRS,
        "recognition.save_dirs": RECOG_DIRS,
        "usb.camera_indices": [1, 2, 3, 4, 5, 6, 7, 8],
        "usb.capture_mode": "auto",
        "usb.frame_source": "placeholder",
        "usb.layer_mode": "multi",
        "usb.save_frames": False,
        "recognition.save_panorama": False,
    })
    layout = readCaptureLayout(config)
    assert layout.captureDirs == ["", "", "", ""], "关采集落盘时目录应全置空"
    assert layout.recognitionDirs == ["", "", "", ""], "关全景落盘时目录应全置空"


## 对应存图开关：两个开关独立，只关采集落盘不影响全景目录
def testSaveSwitchesAreIndependent() -> None:
    config = FakeConfig({
        "log.dir": "./logs",
        "usb.save_dirs": CAPTURE_DIRS,
        "recognition.save_dirs": RECOG_DIRS,
        "usb.camera_indices": [1, 2, 3, 4, 5, 6, 7, 8],
        "usb.capture_mode": "auto",
        "usb.frame_source": "placeholder",
        "usb.layer_mode": "multi",
        "usb.save_frames": False,
        "recognition.save_panorama": True,
    })
    layout = readCaptureLayout(config)
    assert layout.captureDirs == ["", "", "", ""]
    assert all(layout.recognitionDirs), "全景落盘开启时识别目录应保留"


## 对应单层开关：layer_mode=single 只取前 2 路、构成 1 个 worker
def testSingleLayerModeTruncatesToTwoCamerasOneWorker() -> None:
    config = FakeConfig({
        "log.dir": "./logs",
        "usb.save_dirs": CAPTURE_DIRS,
        "recognition.save_dirs": RECOG_DIRS,
        "usb.camera_indices": [1, 2, 3, 4, 5, 6, 7, 8],
        "usb.capture_mode": "auto",
        "usb.frame_source": "placeholder",
        "usb.layer_mode": LAYER_MODE_SINGLE,
        "usb.save_frames": False,
        "recognition.save_panorama": False,
    })
    layout = readCaptureLayout(config)
    assert len(layout.cameraIndices) == 2, "单层模式只取前 2 路"
    assert len(layout.captureDirs) == 1, "单层模式只有 1 个 worker"


## 对应焦点能力：8 值配置解析、单值广播、非法个数拒绝
def testNormalizeOpticalValuesEightSingleAndInvalid() -> None:
    eight = normalizeOpticalValues("1,2,3,4,5,6,7,8", "focus_positions")
    assert eight == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    assert normalizeOpticalValues(5.0, "focus_positions") == [5.0] * 8
    with pytest.raises(EdgeError):
        normalizeOpticalValues("1,2,3", "focus_positions")
    with pytest.raises(EdgeError):
        normalizeOpticalValues([1, 2], "focus_positions")


## 对应焦点能力：8 个值逐路下发，下标 = 路号 - 1，CAM5~8 不错位
def testPerCameraFocusZoomUsePhysicalIndex() -> None:
    focusValues = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
    zoomValues = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    devices = [FakeCameraFocus() for _ in range(8)]
    ## worker 配对 (CAM1,CAM5)...，与生产 buildCameraPairs 一致
    pairs = [(devices[0], devices[4]), (devices[1], devices[5]),
             (devices[2], devices[6]), (devices[3], devices[7])]
    controller = UsbController(
        pairs, [str(Path("unused"))] * 4, FakeCaptureSink(), FakeLogger(),
        0.3, lambda: 0.0, lambda: "stamp",
        focusMode="fixed", focusPositions=focusValues, zoomPositions=zoomValues,
    )
    ## 只让设备看起来已打开，便于下发
    for device in devices:
        device.open()
    controller.applyFixedFocus()
    for index, device in enumerate(devices):
        ## 下标铁律：第 index 个设备（CAM{index+1}）拿第 index 个值
        assert device.getFocusPosition() == focusValues[index], f"CAM{index + 1} 焦点错位"
        assert device.getZoomPosition() == zoomValues[index], f"CAM{index + 1} 变焦错位"
