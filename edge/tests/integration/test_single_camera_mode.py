"""单摄与内置摄像头模式用例：全部用 Fake 或占位帧源，不接真实摄像头也能跑。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest

from edge.app_init import (
    CAPTURE_MODE_AUTO,
    CAPTURE_MODE_DUAL,
    CAPTURE_MODE_SINGLE,
    MAX_CAMERA_INDEX_COUNT,
    SINGLE_CAMERA_INDEX_COUNT,
    buildCameraGroups,
    directInference,
    normalizeRoiWorkerIds,
    resolveCaptureMode,
)


def placeholderFrames(_saveDir: str, _workerId: int):
    return (b"", b"")
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingLoader, RoiBindingRow
from edge.interfaces.i_camera import ICameraDevice
from edge.interfaces.i_sinks import AckFrame
from edge.modules.recognition.recognition_stitcher import (
    DEGRADED_SEPARATOR,
    Cv2FrameStitcher,
    DegradedFrameStitcher,
)
from edge.modules.recognition.recognition_utils import (
    ALERT_TYPE_FIELD,
    ALERT_UNKNOWN,
    POSITION_FIELD,
    AckItem,
)
from edge.modules.recognition.recognition_worker import RecognitionWorker
from edge.modules.usb.usb_camera_device import FRAME_SOURCE_CAMERA, CameraFactory
from edge.modules.usb.usb_capture_worker import CaptureWorker
from edge.modules.usb.usb_controller import (
    CAMERA_STATUS_OK,
    DEFAULT_CAMERA_COUNT,
    UsbController,
)
from edge.tests.fakes.fake_camera_device import FakeCameraDevice
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_recognition_engine import FakeRecognitionEngine
from edge.tests.fakes.fake_sinks import FakeCaptureSink

## @file edge/tests/integration/test_single_camera_mode.py
## @brief 单摄与内置摄像头模式用例：模式判定、单路装配、拼接分支、清单覆盖、无图像库时降级出帧
## @author 边缘计算项目

# 验收项编号 SC-1~SC-6 对应本次开工清单的 6 条覆盖点，编号只用于本文件用例对照。

## @brief 工程自带的 ROI 对照表路径
SINGLE_ROI_CSV_PATH: Path = (
    Path(__file__).resolve().parents[2] / "config" / "roi_binding.csv"
)
## @brief 对照表样例行数
SINGLE_ROI_ROW_COUNT: int = 4
## @brief 占位帧字节，内容不重要，只要能原样传下去
SINGLE_FRAME_BYTES: bytes = b"single-placeholder-frame"
## @brief 双摄左路帧字节
SINGLE_LEFT_BYTES: bytes = b"left-frame"
## @brief 双摄右路帧字节
SINGLE_RIGHT_BYTES: bytes = b"right-frame"
## @brief 用例里的占用比例阈值
SINGLE_ROLL_THRESHOLD: float = 0.3
## @brief 用例里的推理超时秒数
SINGLE_INFER_TIMEOUT_SEC: float = 3.0
## @brief 用例里固定的文件名时间戳
SINGLE_FIXED_STAMP: str = "stamp"
## @brief 落盘验证用的文件名时间戳
SINGLE_FILE_STAMP: str = "sc6"
## @brief 单摄唯一一路的编号
SINGLE_CAMERA_ID: str = "CAM1"


## @brief 装载工程自带的 4 行 ROI 对照表
#  @return 对照表行列表
def readSingleCameraRoiRows() -> list[RoiBindingRow]:
    return RoiBindingLoader(FakeLogger()).load(str(SINGLE_ROI_CSV_PATH))


## @brief 占用比例恒为 0，表示不触发滚动删旧
#  @return 0.0
def singleQuietDisk() -> float:
    return 0.0


## @brief 返回固定文件名时间戳，避免依赖真实时钟
#  @return 固定标签
def singleFixedStamp() -> str:
    return SINGLE_FIXED_STAMP


## @brief 构造 1 路单摄的采集门面
#  @param groups 单摄设备组，长度 1
#  @param saveDir 落盘目录
#  @return 采集门面
def makeSingleCameraController(groups: list[tuple[ICameraDevice, ...]],
                               saveDir: Path) -> UsbController:
    return UsbController(
        groups, [str(saveDir)], FakeCaptureSink(), FakeLogger(),
        SINGLE_ROLL_THRESHOLD, singleQuietDisk, singleFixedStamp,
        cameraCount=SINGLE_CAMERA_INDEX_COUNT,
    )


## @brief 忽略识别结果回调
#  @param workerId 线程编号
#  @param ack 识别应答帧
#  @param requestId 请求标识
#  @return 无
def ignoreSingleWorkerResult(workerId: int, ack: AckFrame, requestId: str) -> None:
    return None


## @brief 忽略识别失败回调
#  @param workerId 线程编号
#  @param exception 失败异常
#  @return 无
def ignoreSingleWorkerError(workerId: int, exception: Exception) -> None:
    return None


## @brief 忽略采集成功回调
#  @param workerId 线程编号
#  @param path 采集目录
#  @return 无
def ignoreSingleCaptureSuccess(workerId: int, path: str) -> None:
    return None


## @brief 用单摄 worker 跑一遍对照表识别，直接取清单，不启动线程
#  @param rows 已归一到 worker 1 的对照表行
#  @param saveDir 识别目录
#  @return 识别清单
def buildSingleCameraItems(rows: list[RoiBindingRow], saveDir: Path) -> list[AckItem]:
    worker = RecognitionWorker(
        1, "req-single-0001", str(saveDir),
        FakeRecognitionEngine([]), FakeLogger(),
        ignoreSingleWorkerResult, ignoreSingleWorkerError,
        {}, {}, {}, SINGLE_INFER_TIMEOUT_SEC,
        directInference, placeholderFrames,
        rows, DegradedFrameStitcher(), (SINGLE_FRAME_BYTES,),
    )
    return worker.runTableRecognition()


## @brief 验收项 SC-1：auto + 1 路判单摄、auto + 偶数路判双摄，single / dual 强制值生效
def testSc1AutoAndForcedModesResolveAsExpected() -> None:
    assert resolveCaptureMode(
        CAPTURE_MODE_AUTO, SINGLE_CAMERA_INDEX_COUNT,
    ) == CAPTURE_MODE_SINGLE
    for count in (2, 4, 6, MAX_CAMERA_INDEX_COUNT):
        assert resolveCaptureMode(CAPTURE_MODE_AUTO, count) == CAPTURE_MODE_DUAL
    ## 强制单摄：不论路数奇偶，每个索引各自成一组
    for count in (1, 3, MAX_CAMERA_INDEX_COUNT):
        assert resolveCaptureMode(CAPTURE_MODE_SINGLE, count) == CAPTURE_MODE_SINGLE
    ## 强制双摄：偶数路放行
    for count in (2, 4, MAX_CAMERA_INDEX_COUNT):
        assert resolveCaptureMode(CAPTURE_MODE_DUAL, count) == CAPTURE_MODE_DUAL


## @brief 验收项 SC-1：auto + 奇数路（≥3）、非法模式、dual + 1 路、路数越界都报 CONFIG
def testSc1OddAndIllegalModesRaiseConfigError() -> None:
    for count in (3, 5, 7):
        with pytest.raises(EdgeError) as odd:
            resolveCaptureMode(CAPTURE_MODE_AUTO, count)
        assert odd.value.code == ErrorCode.CONFIG
    with pytest.raises(EdgeError) as illegal:
        resolveCaptureMode("turbo", 2)
    assert illegal.value.code == ErrorCode.CONFIG
    with pytest.raises(EdgeError) as dualOnOne:
        resolveCaptureMode(CAPTURE_MODE_DUAL, SINGLE_CAMERA_INDEX_COUNT)
    assert dualOnOne.value.code == ErrorCode.CONFIG
    for badCount in (0, MAX_CAMERA_INDEX_COUNT + 1):
        with pytest.raises(EdgeError) as outOfRange:
            resolveCaptureMode(CAPTURE_MODE_AUTO, badCount)
        assert outOfRange.value.code == ErrorCode.CONFIG


## @brief 验收项 SC-2：1 路索引装配后 init 不再报「采集配置不完整」，能拉起 1 个 worker
def testSc2OneIndexInitsAndStartsOneWorker(tmp_path: Path) -> None:
    devices: list[ICameraDevice] = [FakeCameraDevice(SINGLE_FRAME_BYTES)]
    mode = resolveCaptureMode(CAPTURE_MODE_AUTO, len(devices))
    groups = buildCameraGroups(devices, mode)
    assert mode == CAPTURE_MODE_SINGLE
    assert len(groups) == SINGLE_CAMERA_INDEX_COUNT
    assert len(groups[0]) == SINGLE_CAMERA_INDEX_COUNT
    controller = makeSingleCameraController(groups, tmp_path)
    ## init 不抛 CONFIG 就是这条要证的事实：1 组相机配 1 个目录算配置完整
    controller.init()
    assert controller.getWorkers() == []
    assert controller.startCapture() is True
    assert len(controller.getWorkers()) == 1
    assert controller.isCapturing() is True
    controller.stopCapture()
    assert controller.isCapturing() is False


## @brief 验收项 SC-3：单摄 camera_status 只报 CAM1 一路，能打开时是 ok，不是整柜 8 路
def testSc3SingleCameraStatusReportsOneOkEntry(tmp_path: Path) -> None:
    devices: list[ICameraDevice] = [FakeCameraDevice(SINGLE_FRAME_BYTES)]
    groups = buildCameraGroups(devices, resolveCaptureMode(CAPTURE_MODE_AUTO, len(devices)))
    controller = makeSingleCameraController(groups, tmp_path)
    controller.init()
    status = controller.getCameraStatus()
    assert len(status) == SINGLE_CAMERA_INDEX_COUNT
    assert len(status) != DEFAULT_CAMERA_COUNT
    assert [str(item.get("camera_id")) for item in status] == [SINGLE_CAMERA_ID]
    assert [str(item.get("status")) for item in status] == [CAMERA_STATUS_OK]


## @brief 验收项 SC-4：单摄 1 帧原样返回；双摄 2 帧仍进拼接分支，不回退成单摄
def testSc4SingleFrameReturnedAsIsAndDualStillStitches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plain = Cv2FrameStitcher()
    ## 双摄会先载入图像库再走五五分与 x 轴拼接；用哨兵异常顶掉图像处理，不依赖 cv2
    entered: list[int] = []

    def fakeLoadImageLibraries() -> tuple[Any, Any]:
        entered.append(1)
        raise EdgeError(ErrorCode.CAPTURE, "进入双摄拼接分支")

    monkeypatch.setattr(plain, "loadImageLibraries", fakeLoadImageLibraries)
    assert plain.stitch((SINGLE_FRAME_BYTES,)) is SINGLE_FRAME_BYTES
    assert entered == []
    with pytest.raises(EdgeError, match="进入双摄拼接分支"):
        plain.stitch((SINGLE_LEFT_BYTES, SINGLE_RIGHT_BYTES))
    assert entered == [1]

    degraded = DegradedFrameStitcher()
    assert degraded.stitch((SINGLE_FRAME_BYTES,)) is SINGLE_FRAME_BYTES
    joined = degraded.stitch((SINGLE_LEFT_BYTES, SINGLE_RIGHT_BYTES))
    assert joined == DEGRADED_SEPARATOR.join((SINGLE_LEFT_BYTES, SINGLE_RIGHT_BYTES))
    assert joined != SINGLE_LEFT_BYTES


## @brief 验收项 SC-5：ROI 对照表 4 行归一到 worker 1 后全部进 items，货位不丢不重复
def testSc5AllFourRoiRowsLandInItems(tmp_path: Path) -> None:
    rows = readSingleCameraRoiRows()
    assert len(rows) == SINGLE_ROI_ROW_COUNT
    normalized = normalizeRoiWorkerIds(rows, SINGLE_CAMERA_INDEX_COUNT, FakeLogger())
    assert len(normalized) == len(rows)
    assert all(row.workerId == SINGLE_CAMERA_INDEX_COUNT for row in normalized)
    assert [row.roiId for row in normalized] == [row.roiId for row in rows]
    items = buildSingleCameraItems(normalized, tmp_path)
    assert len(items) == SINGLE_ROI_ROW_COUNT
    positions = [str(item[POSITION_FIELD]) for item in items]
    assert set(positions) == {row.position for row in rows}
    assert len(positions) == len(set(positions))
    assert [str(item[ALERT_TYPE_FIELD]) for item in items] == [ALERT_UNKNOWN] * len(rows)
