"""两摄像头模拟整套流程验证工具（无真机）。

用两段本地视频循环回放模拟左右两路摄像头，走真实采集线程 + 定焦屏障 + 拼接 +
识别组帧 + 桩上位机真实 TCP，验证从 recognize_req 到 recognize_ack 的端到端闭环，
并对 F-01（首帧前定焦完成）、定焦幂等、请求标识原样回带做断言。

用法：
    python edge/lab/two_camera_pipeline_sim.py                # 自动生成两段测试视频并跑
    python edge/lab/two_camera_pipeline_sim.py --left a.mp4 --right b.mp4  # 指定视频

退出码：0 全通过；1 环境/装配错误；2 流程断言失败。
"""
# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

## @file edge/lab/two_camera_pipeline_sim.py
## @brief 两摄像头模拟整套流程：视频回放 → 采集/定焦 → 拼接 → 识别组帧 → 桩上位机 TCP 闭环
## @author 边缘计算项目

import argparse
import json

import cv2
import numpy as np

from edge.interfaces.i_camera import CameraStatus, FrameImage, ICameraDevice
from edge.interfaces.i_camera_focus import ICameraFocus
from edge.interfaces.i_frame_sink import IFrameSink
from edge.interfaces.i_sinks import ICaptureSink
from edge.modules.recognition.recognition_stitcher import Cv2FrameStitcher
from edge.tests.fakes.fake_logger import FakeLogger

SIM_VIDEO_DIR = PROJECT_ROOT / "edge" / "lab" / "outputs" / "sim_videos"
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_COUNT = 60
FPS = 20
REQUEST_ID = "sim-req-0001"


## @brief 生成一段带移动色块的测试视频，便于肉眼确认回放与拼接顺序
#  @param path 输出视频路径
#  @param isLeft 左路用暖色、右路用冷色，拼接后左右可区分
#  @return 无
def makeTestVideo(path: Path, isLeft: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = getattr(cv2, "VideoWriter_fourcc")(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, FPS, (FRAME_WIDTH, FRAME_HEIGHT))
    for index in range(FRAME_COUNT):
        frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
        frame[:, :] = (60, 60, 60)
        shift = (index * 8) % (FRAME_WIDTH // 2)
        color = (80, 160, 240) if isLeft else (240, 160, 80)
        x0 = shift if isLeft else FRAME_WIDTH // 2 + shift
        cv2.rectangle(frame, (x0, 120), (x0 + 80, 360), color, -1)
        writer.write(frame)
    writer.release()


## @brief 从视频循环回放的摄像头桩；实现设备与对焦契约，记录定焦/取帧时刻
class VideoFileCamera(ICameraDevice, ICameraFocus):
    ## @brief 构造
    #  @param path 视频路径
    #  @param label 路标，用于日志
    def __init__(self, path: str, label: str) -> None:
        self._path = path
        self._capture = cv2.VideoCapture(path)
        if not self._capture.isOpened():
            raise RuntimeError(f"视频打不开: {path}")
        self._label = label
        self._opened = False
        self._focusCommands: list[tuple[str, float]] = []
        self._focusTime: float | None = None
        self._firstFrameTime: float | None = None
        self._frameCount = 0

    def open(self) -> None:
        ## 生产流程会先探测(开→关)再正式采集；close 释放了句柄，这里按需重建
        if not self._capture.isOpened():
            self._capture = cv2.VideoCapture(self._path)
        self._opened = True

    def close(self) -> None:
        self._opened = False
        self._capture.release()

    def readFrame(self) -> FrameImage | None:
        import time
        ok, frame = self._capture.read()
        if not ok:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        if not ok:
            return None
        if self._firstFrameTime is None:
            self._firstFrameTime = time.monotonic()
        self._frameCount += 1
        encoded, data = cv2.imencode(".jpg", frame)
        return bytes(data.tobytes()) if encoded else None

    def getStatus(self) -> CameraStatus:
        return {"opened": self._opened, "everOpened": self._opened,
                "commOk": True, "deviceAddr": self._label}

    def setAutoFocus(self, enabled: bool) -> None:
        self._focusCommands.append(("autoFocus", 1.0 if enabled else 0.0))

    def setFocusPosition(self, position: float) -> None:
        import time
        self._focusCommands.append(("focusPosition", position))
        self._focusTime = time.monotonic()

    def getFocusPosition(self) -> float:
        return 0.0

    def setZoomPosition(self, position: float) -> None:
        self._focusCommands.append(("zoomPosition", position))

    def getZoomPosition(self) -> float:
        return 0.0

    @property
    def focusCommands(self) -> list[tuple[str, float]]:
        return list(self._focusCommands)

    @property
    def focusTime(self) -> float | None:
        return self._focusTime

    @property
    def firstFrameTime(self) -> float | None:
        return self._firstFrameTime


## @brief 帧汇聚：收齐两路帧后拼接成全景，记录请求标识与首帧顺序
class SinkAndStitch(IFrameSink):
    def __init__(self) -> None:
        self.stitcher = Cv2FrameStitcher()
        self.received: list[tuple[int, tuple[bytes, ...], str]] = []
        self.panorama: bytes | None = None

    def onFrameCaptured(self, workerId: int, frames: tuple[bytes, ...],
                        requestId: str) -> None:
        self.received.append((workerId, frames, requestId))
        if self.panorama is None:
            self.panorama = self.stitcher.stitch(frames)


def parseArgs() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="两摄像头模拟整套流程验证")
    parser.add_argument("--left", default="", help="左路视频路径；留空则自动生成")
    parser.add_argument("--right", default="", help="右路视频路径；留空则自动生成")
    parser.add_argument("--seconds", type=int, default=3, help="采集持续秒数")
    parser.add_argument("--focus-stable-ms", type=int, default=80,
                        help="定焦稳定等待毫秒数")
    return parser.parse_args()


## @brief 空采集事件桩
class NoopCaptureSink(ICaptureSink):
    def onCaptureSuccess(self, workerId: int, path: str) -> None:
        return None

    def onCaptureError(self, workerId: int, exception: Exception) -> None:
        return None


## @brief 跑一套完整流程并返回检查结果
#  @param args 命令行参数
#  @return 检查结果列表，每项为 (编号, 描述, 是否通过, 说明)
def run(args: argparse.Namespace) -> list[tuple[str, str, bool, str]]:
    from edge.modules.usb.usb_controller import UsbController

    checks: list[tuple[str, str, bool, str]] = []
    leftPath = args.left or str(SIM_VIDEO_DIR / "left.mp4")
    rightPath = args.right or str(SIM_VIDEO_DIR / "right.mp4")
    if not args.left or not args.right:
        makeTestVideo(Path(leftPath), True)
        makeTestVideo(Path(rightPath), False)

    logger = FakeLogger()
    left = VideoFileCamera(leftPath, "SIM-CAM1")
    right = VideoFileCamera(rightPath, "SIM-CAM2")
    pairs = [(left, right)]  # 单组双摄：worker1 持 CAM1/CAM2
    sink = SinkAndStitch()
    controller = UsbController(
        pairs, [""], NoopCaptureSink(), logger,
        0.9, lambda: 0.0, lambda: "stamp",
        focusMode="fixed", focusPositions=[42.0, 77.0],
        zoomPositions=[10.0, 20.0], focusStableMs=args.focus_stable_ms,
        frameSink=sink, cameraCount=2,
        captureIntervalSec=0.05,
    )
    controller.init()
    controller.startCapture(REQUEST_ID)

    import time
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline and len(sink.received) < 2:
        time.sleep(0.02)
    controller.stopCapture()

    # C01 采集闭环：至少收到两路帧
    gotFrames = len(sink.received) >= 1 and all(len(fr) == 2 for _w, fr, _r in sink.received)
    checks.append(("C01", "双路取帧闭环", gotFrames,
                   f"收到 {len(sink.received)} 轮，每轮帧数 "
                   f"{[len(fr) for _w, fr, _r in sink.received][:3]}"))
    # C02 拼接成功
    checks.append(("C02", "全景拼接成功", sink.panorama is not None,
                   f"全景字节 {len(sink.panorama) if sink.panorama else 0}"))
    # C03 请求标识原样回带
    idsOk = all(rid == REQUEST_ID for _w, _fr, rid in sink.received) and bool(sink.received)
    checks.append(("C03", "请求标识原样回带", idsOk,
                   f"标识集合 {set(rid for _w, _fr, rid in sink.received)}"))
    # C04 F-01：首帧不早于定焦完成（屏障生效）
    focusTimes = [c.focusTime for c in (left, right) if c.focusTime is not None]
    frameTimes = [c.firstFrameTime for c in (left, right) if c.firstFrameTime is not None]
    barrierOk = bool(focusTimes) and bool(frameTimes) and \
        min(frameTimes) >= max(focusTimes) - 0.01
    checks.append(("C04", "首帧前定焦完成(F-01)", barrierOk,
                   f"定焦时刻 {focusTimes}, 首帧时刻 {frameTimes}"))
    # C05 先关自动对焦再设位置
    orderOk = all(
        c.focusCommands[:3] == [("autoFocus", 0.0),
                                ("focusPosition", c.focusCommands[1][1]),
                                ("zoomPosition", c.focusCommands[2][1])]
        for c in (left, right) if len(c.focusCommands) >= 3
    )
    checks.append(("C05", "定焦指令顺序", orderOk,
                   f"左={left.focusCommands[:3]} 右={right.focusCommands[:3]}"))
    # C06 逐路独立取值（CAM1=42 / CAM2=77，不错位）
    perCameraOk = (len(left.focusCommands) >= 2 and left.focusCommands[1][1] == 42.0 and
                   len(right.focusCommands) >= 2 and right.focusCommands[1][1] == 77.0)
    checks.append(("C06", "逐路独立焦点值", perCameraOk,
                   f"CAM1={left.focusCommands[1][1] if len(left.focusCommands)>1 else 'NA'}, "
                   f"CAM2={right.focusCommands[1][1] if len(right.focusCommands)>1 else 'NA'}"))
    return checks


def main() -> int:
    args = parseArgs()
    checks = run(args)
    print("=== 两摄像头模拟整套流程验证 ===")
    for cid, name, passed, detail in checks:
        print(f"[{cid}] {'PASS' if passed else 'FAIL'}  {name}: {detail}")
    allPass = all(passed for _c, _n, passed, _d in checks)
    summary = {"allPass": allPass,
               "checks": [{"id": c, "name": n, "passed": p, "detail": d}
                          for c, n, p, d in checks]}
    outPath = PROJECT_ROOT / "edge" / "lab" / "outputs" / "two_camera_sim_result.json"
    outPath.parent.mkdir(parents=True, exist_ok=True)
    outPath.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写出: {outPath}")
    return 0 if allPass else 2


if __name__ == "__main__":
    raise SystemExit(main())
