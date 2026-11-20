"""相机映射链用例：8 路相机 -> 4 组采集线程 -> ROI 对照表货位 的归属固化。

复刻依据（只读引用上位机工程 d:/CFDZ/smartCabinet/trunk/SmartCabinetLite）：

- tools/EdgeSimulator/EdgeSimulator.cpp:108-128：上位机配套模拟器按位置把 8 路相机
  编为 CAM1..CAM8，告警里显示的就是这个编号（EdgeService.cpp:253-262）。
- src/comm/EdgeService.cpp:239-247：上位机只按 camera_id 字符串判 ok 与非 ok；
  编号对不上会让现场定位错位，所以边缘机的编号口径必须与模拟器一致。

边缘机侧口径（edge/config/README.md 第三、七节）：

- camera_indices 的**顺序**决定物理编号：第 N 个索引对应周期帧里的 CAM{N}；
- 左路相机排在前、右路相机排在后，第 N 号采集线程拿"左路第 N 台 + 右路第 N 台"。
"""
from __future__ import annotations

from pathlib import Path
from typing import cast

from edge.app_init import (
    DEFAULT_CONFIG_PATH,
    buildCameraDevices,
    buildCameraPairs,
    reportUnassignedCameraGroups,
)
from edge.infra.config_manager import IniConfigManager
from edge.infra.roi_binding_loader import RoiBindingLoader, RoiBindingRow
from edge.modules.usb.usb_controller import UsbController
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_sinks import FakeCaptureSink

## @file edge/tests/integration/test_camera_mapping_chain.py
## @brief 相机映射链用例：8 路到 4 组再到货位的归属与编号口径固化
## @author 边缘计算项目

## @brief 整柜相机路数
CAMERA_COUNT: int = 8
## @brief 采集线程数，等于相机对数
WORKER_COUNT: int = 4
## @brief 上位机配套模拟器使用的相机编号序列，按物理位置稳定编号
EXPECTED_CAMERA_IDS: tuple[str, ...] = (
    "CAM1", "CAM2", "CAM3", "CAM4", "CAM5", "CAM6", "CAM7", "CAM8",
)
## @brief 样例全景画布宽高，与 edge/config/README.md 第二节一致
PANORAMA_WIDTH: int = 640
## @brief 样例全景画布高
PANORAMA_HEIGHT: int = 480
## @brief 对照表路径
ROI_CSV_PATH: Path = Path(__file__).resolve().parents[2] / "config" / "roi_binding.csv"


## @brief 读正式配置里的相机索引顺序
#  @return 相机索引列表
def readCameraIndices() -> list[int]:
    config = IniConfigManager.instance(DEFAULT_CONFIG_PATH)
    return cast(list[int], config.get("usb", "camera_indices"))


## @brief 读正式对照表
#  @return 对照表行列表
def readRoiRows() -> list[RoiBindingRow]:
    return RoiBindingLoader(FakeLogger()).load(str(ROI_CSV_PATH))


## @brief 构造一个只用来查编号顺序的采集门面
#  @param pairs 相机对
#  @return 采集门面
def buildStatusOnlyController(
    pairs: list[tuple[object, object]],
) -> UsbController:
    return UsbController(
        cast(list, pairs), ["./output/capture/w1", "./output/capture/w2",
                            "./output/capture/w3", "./output/capture/w4"],
        FakeCaptureSink(), FakeLogger(), 0.3, lambda: 0.0, lambda: "stamp",
        cameraCount=CAMERA_COUNT,
    )


## @brief 相机索引顺序决定物理编号：第 N 个索引就是 CAM{N}
def testCameraIndicesOrderDefinesPhysicalNumbering() -> None:
    """设备列表按 camera_indices 顺序生成，周期帧里的编号也按这个顺序排。"""
    cameraIndices = readCameraIndices()
    devices = buildCameraDevices(cameraIndices, FakeLogger())

    assert len(devices) == CAMERA_COUNT
    assert [str(device.getStatus().get("deviceAddr")) for device in devices] == [
        str(index) for index in cameraIndices
    ]

    pairs = buildCameraPairs(devices)
    controller = buildStatusOnlyController(cast(list, pairs))
    cameraStatus = controller.getCameraStatus()

    assert len(cameraStatus) == CAMERA_COUNT
    assert [str(entry.get("camera_id")) for entry in cameraStatus] == list(
        EXPECTED_CAMERA_IDS
    )


## @brief 第 N 号采集线程拿左路第 N 台与右路第 N 台两台相机
def testWorkerTakesLeftNthAndRightNthCamera() -> None:
    """分组口径：前半段是左路，后半段是右路，同序号配成一对。"""
    cameraIndices = readCameraIndices()
    devices = buildCameraDevices(cameraIndices, FakeLogger())
    pairs = buildCameraPairs(devices)

    assert len(pairs) == WORKER_COUNT
    for workerIndex, (left, right) in enumerate(pairs):
        workerId = workerIndex + 1
        assert str(left.getStatus().get("deviceAddr")) == str(cameraIndices[workerId - 1])
        assert str(right.getStatus().get("deviceAddr")) == str(
            cameraIndices[WORKER_COUNT + workerId - 1]
        )


## @brief 对照表每个货位都有归属，没有线程编号越界，四组全部有货位
def testEveryPositionHasExactlyOneOwningWorker() -> None:
    """台账与相机对数必须一致，不能有货位没人认领，也不能有线程编号越界。"""
    cameraIndices = readCameraIndices()
    devices = buildCameraDevices(cameraIndices, FakeLogger())
    pairs = buildCameraPairs(devices)
    rows = readRoiRows()

    assert len(pairs) == WORKER_COUNT
    assert len(rows) == WORKER_COUNT, (
        f"对照表应有 {WORKER_COUNT} 行货位，与 4 组采集线程一一对应，实际 {len(rows)} 行"
    )
    assert [row.workerId for row in rows] == list(range(1, WORKER_COUNT + 1)), (
        "对照表各行应依次归属第 1~4 组采集线程"
    )
    assert [row.position for row in rows] == [
        "A-01-01", "A-01-02", "A-01-03", "A-01-04",
    ], "货位编号应与相机映射链的物理顺序一致"
    assert all(1 <= row.workerId <= WORKER_COUNT for row in rows)

    positions = [row.position for row in rows]
    assert len(positions) == len(set(positions))

    ownersByWorker: dict[int, list[str]] = {
        workerId: [] for workerId in range(1, WORKER_COUNT + 1)
    }
    for row in rows:
        ownersByWorker[row.workerId].append(row.position)
    for workerId in range(1, WORKER_COUNT + 1):
        assert ownersByWorker[workerId], f"第{workerId}组没有货位，这组相机是白开的"


## @brief 对照表里的 ROI 矩形必须落在本组拼接全景的画布内
def testRoiRectanglesFitInsideWorkerPanorama() -> None:
    """ROI 参照系是本组自己的拼接全景，越界的行会在裁剪时报越界。"""
    rows = readRoiRows()
    for row in rows:
        assert 0 <= row.rectX1 < row.rectX2 <= PANORAMA_WIDTH
        assert 0 <= row.rectY1 < row.rectY2 <= PANORAMA_HEIGHT


## @brief 有分组没货位时必须说清楚哪几路相机是白开的
def testUnassignedCameraGroupIsReported() -> None:
    """没有货位的分组照样占用相机，必须在日志里点名。"""
    logger = FakeLogger()
    rows = readRoiRows()
    keepWorkerRows = [
        row for row in rows if row.workerId < WORKER_COUNT
    ]

    reportUnassignedCameraGroups(rows, WORKER_COUNT, logger)
    assert logger.errorRecords == []

    reportUnassignedCameraGroups(keepWorkerRows, WORKER_COUNT, logger)
    assert len(logger.errorRecords) == 1
    assert "白做" in logger.errorRecords[0][1]
    assert f"第{WORKER_COUNT}组" in logger.errorRecords[0][1]
