"""探测设备号 1 摄像头的原生分辨率并拍照，仅在 lab 内运行。

原生分辨率按「硬件实际能输出的最大帧尺寸」判定：逐个候选分辨率重新打开摄像头、
set 后读一帧，读回帧尺寸等于候选值才算真正支持。结果 JSON 与照片写到
lab/outputs/camera1_probe/。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2

## 目标摄像头设备号
DEVICE_ID: int = 1
## 输出目录（相对本脚本）
OUT_DIR: Path = Path(__file__).resolve().parent / "outputs" / "camera1_probe"
## 常见摄像头分辨率候选（宽, 高），从低到高
CANDIDATES: list[tuple[int, int]] = [
    (640, 480),
    (800, 600),
    (1024, 768),
    (1280, 720),
    (1280, 960),
    (1600, 1200),
    (1920, 1080),
    (2048, 1536),
    (2592, 1944),
    (3840, 2160),
]
## 尝试的后端顺序：Windows 下 MSMF 改分辨率较可靠，DSHOW 兜底
BACKENDS: list[tuple[str, int]] = [
    ("CAP_MSMF", cv2.CAP_MSMF),
    ("CAP_DSHOW", cv2.CAP_DSHOW),
    ("CAP_ANY", cv2.CAP_ANY),
]


def openCapture(backend: int) -> object | None:
    """按指定后端打开设备，打不开返回 None。"""
    cap = cv2.VideoCapture(DEVICE_ID, backend)
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def readFrameSize(cap: object) -> tuple[int, int] | None:
    """读一帧并返回实际帧尺寸（宽, 高），读不到返回 None。"""
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    height, width = frame.shape[:2]
    return (int(width), int(height))


def snap(cap: object, path: Path) -> tuple[int, int] | None:
    """从已打开的摄像头读一帧并保存为 JPG，返回实际帧尺寸。"""
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    height, width = frame.shape[:2]
    cv2.imwrite(str(path), frame)
    return (int(width), int(height))


def probeBackend(name: str, backend: int) -> dict[str, object]:
    """对单一后端探测默认分辨率与真实支持的分辨率集合。"""
    result: dict[str, object] = {
        "backend": name,
        "opened": False,
        "default": None,
        "defaultFrame": None,
        "supported": [],
    }
    cap = openCapture(backend)
    if cap is None:
        return result
    result["opened"] = True
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    result["default"] = [width, height]
    result["defaultFrame"] = list(readFrameSize(cap) or (0, 0))
    cap.release()
    time.sleep(0.2)
    for candWidth, candHeight in CANDIDATES:
        cap = openCapture(backend)
        if cap is None:
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(candWidth))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(candHeight))
        size = readFrameSize(cap)
        cap.release()
        timcc.sleep(0.2)
        if size == (candWidth, candHeight):
            result["supported"].append([candWidth, candHeight])
    return result


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "deviceId": DEVICE_ID,
        "backends": [],
        "nativeMax": None,
        "photo": None,
        "photoSize": None,
    }
    for name, backend in BACKENDS:
        info = probeBackend(name, backend)
        report["backends"].append(info)
        print(f"[{name}] opened={info['opened']} default={info['default']} "
              f"frame={info['defaultFrame']} supported={info['supported']}")

    ## 原生最大 = 所有后端中真实支持的最大帧尺寸（面积最大）
    best: tuple[int, int] | None = None
    bestBackend: int = BACKENDS[0][1]
    for _name, backend in BACKENDS:
        info = [item for item in report["backends"] if item["backend"] == _name][0]
        for width, height in info["supported"]:
            if best is None or width * height > best[0] * best[1]:
                best = (int(width), int(height))
                bestBackend = backend
    if best is not None:
        report["nativeMax"] = list(best)
    print(f"NATIVE_MAX={best}")

    ## 拍照：优先用原生最大分辨率，设不上则用默认分辨率
    cap = openCapture(bestBackend)
    if cap is None:
        for _name, backend in BACKENDS:
            cap = openCapture(backend)
            if cap is not None:
                break
    if cap is None:
        print("NO_CAMERA 设备 1 在所有后端下都打不开")
        (OUT_DIR / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    if best is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(best[0]))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(best[1]))
    photoPath = OUT_DIR / "camera1_snap.jpg"
    photoSize = snap(cap, photoPath)
    cap.release()
    report["photo"] = str(photoPath)
    report["photoSize"] = list(photoSize) if photoSize else None
    (OUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PHOTO={photoPath} size={photoSize}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
