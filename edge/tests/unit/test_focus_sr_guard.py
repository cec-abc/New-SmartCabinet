"""8 路逐路定焦需求测试守护：指令顺序、逐路不串位、首帧定焦屏障、失败日志级别。"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from edge.modules.usb.usb_capture_worker import CaptureWorker
from edge.modules.usb.usb_controller import UsbController
from edge.tests.fakes.fake_camera_focus import FakeCameraFocus
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_sinks import FakeCaptureSink

## @file edge/tests/unit/test_focus_sr_guard.py
## @brief 8 路定焦修复的行为守护：指令顺序、逐路取值、首帧屏障与失败日志级别
## @author 袁燕


## @brief 忽略采集成功回调
#  @param _workerId 线程编号
#  @param _path 采集目录
#  @return 无
def _ignoreSuccess(_workerId: int, _path: str) -> None:
    return None


## @brief 忽略采集失败回调
#  @param _workerId 线程编号
#  @param _error 业务异常
#  @return 无
def _ignoreError(_workerId: int, _error: Exception) -> None:
    return None


## @brief 构造已打开的单路定焦控制器
#  @param focusValue 本路焦点位置
#  @param zoomValue 本路变焦位置
#  @param logger 可选日志器
#  @return 控制器与设备二元组
def _fixedController(focusValue: float, zoomValue: float,
                     logger: FakeLogger | None = None
                     ) -> tuple[UsbController, FakeCameraFocus]:
    device = FakeCameraFocus()
    device.open()
    controller = UsbController(
        [(device,)], [""], FakeCaptureSink(), logger,
        0.3, lambda: 0.0, lambda: "stamp",
        focusMode="fixed", focusPositions=[focusValue], zoomPositions=[zoomValue],
    )
    return controller, device


## SR_FOCUS_06：fixed 模式按「先关自动对焦→再设焦点→最后设变焦」的顺序下发
def testFocusCommandOrderAutoOffThenFocusThenZoom() -> None:
    """验收点：focusCommands 必须严格为 autoFocus(0.0)→focusPosition→zoomPosition。"""
    controller, device = _fixedController(0.42, 0.75)
    controller.applyFixedFocus()
    assert device.focusCommands == [
        ("autoFocus", 0.0),
        ("focusPosition", 0.42),
        ("zoomPosition", 0.75),
    ], "对焦指令顺序错误：必须先关自动对焦，再设焦点与变焦"


## SR_FOCUS_05：fixed 模式锁定后自动对焦必须保持关闭、焦点落在配置值
def testFixedModeKeepsAutoFocusDisabled() -> None:
    """验收点：定焦下发后 autoFocus=False 且设备焦点等于配置值。"""
    controller, device = _fixedController(0.63, 0.20)
    controller.applyFixedFocus()
    assert device.autoFocus is False, "fixed 模式必须关闭自动对焦"
    assert device.getFocusPosition() == 0.63, "焦点应锁定到配置值"


## SR_FOCUS_01 / SR_FOCUS_02：8 路逐路取值不串位，变焦也按物理路号下发
def testPerCameraNoIndexDrift() -> None:
    """验收点：pairs=(0,4)(1,5)(2,6)(3,7) 时每路拿本路焦点与变焦，不受组内下标影响。"""
    focusValues = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    zoomValues = [8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    devices = [FakeCameraFocus() for _ in range(8)]
    pairs = [(devices[0], devices[4]), (devices[1], devices[5]),
             (devices[2], devices[6]), (devices[3], devices[7])]
    controller = UsbController(
        pairs, [str(Path("unused"))] * 4, FakeCaptureSink(), FakeLogger(),
        0.3, lambda: 0.0, lambda: "stamp",
        focusMode="fixed", focusPositions=focusValues, zoomPositions=zoomValues,
    )
    for device in devices:
        device.open()
    controller.applyFixedFocus()
    for index, device in enumerate(devices):
        assert device.getFocusPosition() == focusValues[index], f"CAM{index + 1} 焦点错位"
        assert device.getZoomPosition() == zoomValues[index], f"CAM{index + 1} 变焦错位"
        assert ("focusPosition", focusValues[index]) in device.focusCommands
        assert ("zoomPosition", zoomValues[index]) in device.focusCommands


## SR_FOCUS_13 / spec-digest §8.5：设备未开导致对焦未生效只记 info，不得记 error
def testFocusFailedLogsInfoNotError() -> None:
    """验收点：F-02 修复后对焦失败是如实上报的 info 日志，不中断启动、不记 error。"""
    device = FakeCameraFocus()  # 未 open，getStatus()['opened'] 为 False
    logger = FakeLogger()
    controller = UsbController(
        [(device,)], [""], FakeCaptureSink(), logger,
        0.3, lambda: 0.0, lambda: "stamp",
        focusMode="fixed", focusPositions=[0.5], zoomPositions=[0.5],
    )
    controller.applyFixedFocus()
    assert logger.errorRecords == [], "对焦未生效只记 info，不得记 error"
    infoMessages = [msg for _module, msg in logger.infoRecords]
    assert infoMessages, "对焦未生效应留一条说明日志"
    assert any("对焦" in msg or "定焦" in msg or "未生效" in msg for msg in infoMessages), \
        f"说明日志应点明对焦未生效，实际：{infoMessages}"


## SR_FOCUS_07 / F-01：定焦屏障放行前不得取首帧，放行后才开始 captureOnce
def testFocusGateBlocksFirstFrameUntilApplied(monkeypatch: pytest.MonkeyPatch) -> None:
    """验收点：worker 在 focusGate 放行前 readFrame 计数为 0，放行后才取帧。"""
    gateEntered = threading.Event()
    releaseGate = threading.Event()
    frameCalls: list[int] = [0]

    def focusGate() -> bool:
        gateEntered.set()
        ## 阻塞到测试放行，模拟「本组定焦尚未下发完毕」
        releaseGate.wait(timeout=5.0)
        return True

    camera = FakeCameraFocus()
    originalReadFrame = camera.readFrame

    def countingReadFrame() -> bytes | None:
        frameCalls[0] += 1
        return originalReadFrame()

    monkeypatch.setattr(camera, "readFrame", countingReadFrame)
    worker = CaptureWorker(
        1, (camera,), "", None, _ignoreSuccess, _ignoreError,
        1.0, lambda: 0.0, lambda: "stamp", "req-focus-guard", focusGate=focusGate,
    )
    worker.start()
    try:
        assert gateEntered.wait(timeout=5.0), "worker 应在取首帧前调用 focusGate"
        assert frameCalls[0] == 0, "定焦屏障未放行前不得调用 readFrame"
        releaseGate.set()
        deadline = time.monotonic() + 5.0
        while frameCalls[0] == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert frameCalls[0] > 0, "屏障放行后应开始取首帧"
    finally:
        releaseGate.set()
        worker.stop(timeout=2.0)


## SR_FOCUS_09：focusStableMs 以毫秒存储，交给 interruptibleWait 时换算为秒
def testFocusStableMsConvertedToSeconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """验收点：focusStableMs=250 时 interruptibleWait 收到 0.25 秒而非 250 秒。"""
    camera = FakeCameraFocus()
    worker = CaptureWorker(
        1, (camera,), "", None, _ignoreSuccess, _ignoreError,
        1.0, lambda: 0.0, lambda: "stamp", focusStableMs=250,
    )
    waits: list[float] = []

    def fakeWait(sec: float) -> bool:
        waits.append(sec)
        return False  # 模拟收到停机指令，立即退出首帧流程

    monkeypatch.setattr(worker, "interruptibleWait", fakeWait)
    worker.runLoop()
    assert worker._focusStableMs == 250, "worker 应原样保存毫秒值"
    assert waits == [0.25], "等待秒数应为 250/1000=0.25"
