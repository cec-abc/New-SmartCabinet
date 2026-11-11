"""c4 USB 采集模块单元测试：并发拉起 / 双路落盘 / 滚动删旧 / 回调互不影响。"""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from threading import Barrier

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import FrameImage, ICameraDevice
from edge.modules.usb.usb_camera_device import BACKEND_DSHOW, BACKEND_V4L2, CameraFactory
from edge.modules.usb.usb_controller import UsbController
from edge.tests.fakes.fake_camera_device import FakeCameraDevice
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_sinks import FakeCaptureSink

## @brief 滚动删旧阈值（构造注入）
TEST_ROLL_THRESHOLD: float = 0.3
## @brief 预置旧文件的固定 mtime 基准
OLD_MTIME_BASE: int = 1_000_000


## @brief 占用比例恒为 0，表示不触发删旧
#  @return 0.0
def quietDisk() -> float:
    return 0.0


## @brief 固定文件名时间戳，避免依赖真实时钟
#  @return 固定标签
def fixedStamp() -> str:
    return "stamp"


## @brief 左路设备：4 个 worker 全部到达屏障才放行，用于举证并发拉起
class BarrierCamera(FakeCameraDevice):
    def __init__(self, frame: FrameImage | None, barrier: Barrier) -> None:
        super().__init__(frame)
        ## @brief 并发屏障
        self.barrier: Barrier = barrier

    def readFrame(self) -> FrameImage | None:
        self.barrier.wait(timeout=3.0)
        return self.frame


## @brief 取图恒抛内置异常的设备，用于举证跨边界转 EdgeError
class FailingCamera(FakeCameraDevice):
    def readFrame(self) -> FrameImage | None:
        raise OSError("simulated capture failure")


## @brief 构造完备注入的门面
#  @param cameraPairs 设备组
#  @param saveDirs 目录列表
#  @param sink 采集回调
#  @param logger 可选日志器
#  @param usageRatio 占用比例提供器
#  @param rollThreshold 删旧阈值
#  @return 采集门面
def makeController(
    cameraPairs: list[tuple[ICameraDevice, ICameraDevice]],
    saveDirs: list[Path],
    sink: FakeCaptureSink,
    logger: FakeLogger | None = None,
    usageRatio: Callable[[], float] | None = None,
    rollThreshold: float = TEST_ROLL_THRESHOLD,
) -> UsbController:
    return UsbController(
        cameraPairs,
        [str(saveDir) for saveDir in saveDirs],
        sink,
        logger,
        rollThreshold,
        usageRatio if usageRatio is not None else quietDisk,
        fixedStamp,
    )


## @brief 创建 4 个采集目录
#  @param root 临时根路径
#  @return 目录列表
def makeSaveDirs(root: Path) -> list[Path]:
    dirs: list[Path] = [root / f"worker{i}" for i in range(1, 5)]
    for saveDir in dirs:
        saveDir.mkdir()
    return dirs


## @brief c4-1 4 线程并发拉起、startCapture 立即返回、采集中重复拉起被拒
def test_c4_1_four_workers_fork_and_return_immediately(tmp_path: Path) -> None:
    barrier = Barrier(5)
    pairs: list[tuple[ICameraDevice, ICameraDevice]] = [
        (BarrierCamera(b"LEFT", barrier), FakeCameraDevice(b"RIGHT")) for _ in range(4)
    ]
    sink = FakeCaptureSink()
    controller = makeController(pairs, makeSaveDirs(tmp_path), sink)
    controller.init()
    assert controller.getWorkers() == []

    started = time.monotonic()
    controller.startCapture()
    elapsed = time.monotonic() - started

    ## 4 个 worker 都卡在屏障上（第 5 个参与者未到），证明并发拉起且主线程未被阻塞
    workers = controller.getWorkers()
    assert len(workers) == 4
    assert elapsed < 1.0, f"startCapture 不应等待子线程，实测 {elapsed:.3f}s"
    assert all(worker.is_alive() for worker in workers)
    assert sink.successEvents == []
    assert controller.isCapturing()

    ## 前置校验：已在采集中，重复拉起抛 CONFIG
    try:
        controller.startCapture()
        raise AssertionError("重复 startCapture 应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG

    ## 主线程作为第 5 个参与者放行，全部 worker 完成采集后停机
    barrier.wait(timeout=3.0)
    controller.stopCapture()
    assert len(sink.successEvents) == 4
    assert sorted(item[0] for item in sink.successEvents) == [1, 2, 3, 4]
    assert not controller.isCapturing()


## @brief c4-1 前置校验：未初始化不得拉起任何线程
def test_c4_1_guard_before_init(tmp_path: Path) -> None:
    pairs: list[tuple[ICameraDevice, ICameraDevice]] = [
        (FakeCameraDevice(), FakeCameraDevice())
    ]
    controller = makeController(pairs, [tmp_path], FakeCaptureSink())
    try:
        controller.startCapture()
        raise AssertionError("未 init 应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG
    assert controller.getWorkers() == []


## @brief c4-1 初始化 Fail-Fast：目录不存在即抛 CONFIG，不做能力降级
def test_c4_1_init_fails_fast_on_missing_dir(tmp_path: Path) -> None:
    pairs: list[tuple[ICameraDevice, ICameraDevice]] = [
        (FakeCameraDevice(), FakeCameraDevice())
    ]
    controller = makeController(pairs, [tmp_path / "missing"], FakeCaptureSink())
    try:
        controller.init()
        raise AssertionError("目录缺失应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG


## @brief c4-1 / D-01 自检只留空接口：不启线程、不做 IO、不做能力降级
def test_c4_1_selfcheck_stub_d01(tmp_path: Path) -> None:
    pairs: list[tuple[ICameraDevice, ICameraDevice]] = [
        (FakeCameraDevice(), FakeCameraDevice())
    ]
    controller = makeController(pairs, [tmp_path], FakeCaptureSink())
    ## selfCheck() 返回 None，按 L-04 不作为值断言，改验无状态副作用
    controller.selfCheck()
    assert controller.getWorkers() == []
    assert not controller.isCapturing()


## @brief c4-2 双路取图落盘：左右帧分别写入专属目录并关闭句柄
def test_c4_2_dual_frames_saved(tmp_path: Path) -> None:
    left = FakeCameraDevice(b"LEFT-BYTES")
    right = FakeCameraDevice(b"RIGHT-BYTES")
    sink = FakeCaptureSink()
    controller = makeController([(left, right)], [tmp_path], sink)
    controller.init()
    controller.startCapture()
    controller.stopCapture()

    leftFile = tmp_path / "w1_left_stamp.jpg"
    rightFile = tmp_path / "w1_right_stamp.jpg"
    assert leftFile.read_bytes() == b"LEFT-BYTES"
    assert rightFile.read_bytes() == b"RIGHT-BYTES"
    assert left.opened and left.closed
    assert right.opened and right.closed
    assert sink.successEvents == [(1, str(tmp_path))]
    assert sink.errorEvents == []


## @brief c4-2 设备寻址：Windows 索引走 DSHOW，Linux 固定路径为骨架且转 EdgeError
def test_c4_2_camera_factory_addressing() -> None:
    windowsDevice = CameraFactory.createDevice("0", lambda: b"frame")
    assert windowsDevice.getStatus()["backend"] == BACKEND_DSHOW
    windowsDevice.open()
    assert windowsDevice.readFrame() == b"frame"

    linuxDevice = CameraFactory.createDevice("/dev/cam_left", lambda: b"frame")
    assert linuxDevice.getStatus()["backend"] == BACKEND_V4L2
    try:
        linuxDevice.open()
        raise AssertionError("Linux 骨架应抛 NotImplementedError")
    except NotImplementedError as error:
        assert str(error) == "Linux 摄像头后端待上板实现"


## @brief c4-2 内置骨架异常跨模块边界前转 EdgeError(CAPTURE)，不上抛到 Sink
def test_c4_2_linux_skeleton_converted_before_boundary(tmp_path: Path) -> None:
    linuxDevice = CameraFactory.createDevice("/dev/cam_left", lambda: b"frame")
    sink = FakeCaptureSink()
    controller = makeController([(linuxDevice, FakeCameraDevice(b"R"))], [tmp_path], sink)
    controller.init()
    controller.startCapture()
    controller.stopCapture()

    assert sink.successEvents == []
    assert len(sink.errorEvents) == 1
    workerId, exception = sink.errorEvents[0]
    assert workerId == 1
    assert isinstance(exception, EdgeError)
    assert exception.code == ErrorCode.CAPTURE


## @brief c4-3 占用超 30% 时按最旧顺序删图，删到阈值内即停
def test_c4_3_roll_deletes_oldest(tmp_path: Path) -> None:
    oldFiles = [tmp_path / f"old{i}.jpg" for i in range(3)]
    for index, oldFile in enumerate(oldFiles):
        oldFile.write_bytes(b"old")
        stamp = OLD_MTIME_BASE + index
        os.utime(oldFile, (stamp, stamp))

    def currentRatio() -> float:
        return len(list(tmp_path.glob("*.jpg"))) / 10.0

    sink = FakeCaptureSink()
    controller = makeController(
        [(FakeCameraDevice(b"L"), FakeCameraDevice(b"R"))],
        [tmp_path], sink, usageRatio=currentRatio,
    )
    controller.init()
    controller.startCapture()
    controller.stopCapture()

    ## 初始 5 个文件（3 旧 + 2 新）→ 删 2 个最旧后剩 3 个，比例 0.3 停止
    assert not oldFiles[0].exists()
    assert not oldFiles[1].exists()
    assert oldFiles[2].exists()
    assert (tmp_path / "w1_left_stamp.jpg").exists()
    assert (tmp_path / "w1_right_stamp.jpg").exists()
    assert len(sink.successEvents) == 1
    assert sink.errorEvents == []


## @brief c4-3 删后仍超阈值：记 error 但不中断，成功回调照常上抛
def test_c4_3_roll_still_over_threshold_logs_error(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"old{index}.jpg").write_bytes(b"old")

    def saturatedDisk() -> float:
        return 0.9

    logger = FakeLogger()
    sink = FakeCaptureSink()
    controller = makeController(
        [(FakeCameraDevice(b"L"), FakeCameraDevice(b"R"))],
        [tmp_path], sink, logger=logger, usageRatio=saturatedDisk,
    )
    controller.init()
    controller.startCapture()
    controller.stopCapture()

    ## 旧文件删尽后比例仍超阈值：本轮新帧受保护、记 error、成功回调不受影响
    assert not list(tmp_path.glob("old*.jpg"))
    assert (tmp_path / "w1_left_stamp.jpg").exists()
    assert (tmp_path / "w1_right_stamp.jpg").exists()
    assert any("CAPTURE" in record[1] for record in logger.errorRecords)
    assert len(sink.successEvents) == 1
    assert sink.errorEvents == []


## @brief c4-4 单路失败不影响其他 worker；内置异常跨边界转 EdgeError；FakeCamera 联调通过
def test_c4_4_success_error_callbacks_isolated(tmp_path: Path) -> None:
    normalCameras: list[FakeCameraDevice] = []
    pairs: list[tuple[ICameraDevice, ICameraDevice]] = []
    for index in range(4):
        left = FakeCameraDevice(b"L")
        right = FakeCameraDevice(b"R")
        if index == 2:
            ## 第 3 组左路换成失败设备，只把实际注入的右路计入句柄核验
            pairs.append((FailingCamera(), right))
            normalCameras.append(right)
        else:
            pairs.append((left, right))
            normalCameras.extend([left, right])

    sink = FakeCaptureSink()
    controller = makeController(pairs, makeSaveDirs(tmp_path), sink)
    ## 图上 snake_case 回调不作 API
    assert not hasattr(sink, "on_capture_success")
    assert hasattr(sink, "onCaptureSuccess")

    controller.init()
    controller.startCapture()
    controller.stopCapture()

    assert sorted(item[0] for item in sink.successEvents) == [1, 2, 4]
    assert len(sink.errorEvents) == 1
    workerId, exception = sink.errorEvents[0]
    assert workerId == 3
    assert isinstance(exception, EdgeError)
    assert exception.code == ErrorCode.CAPTURE
    assert all(camera.closed for camera in normalCameras)


## @brief c4-4 Fake 契约一致性：FakeCameraDevice 与 ICameraDevice 四方法逐一对齐
def test_c4_4_fake_camera_contract() -> None:
    device: ICameraDevice = FakeCameraDevice(b"payload")
    device.open()
    assert device.readFrame() == b"payload"
    assert device.getStatus()["opened"] is True
    device.close()
    assert isinstance(device, FakeCameraDevice)
    assert device.closed is True
