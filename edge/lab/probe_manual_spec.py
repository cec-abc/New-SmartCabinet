"""按硬件手册 AT-01M7000B 规格探测摄像头并用最高像素拍照。

手册关键点：图像传感器 48M 1/2"，原生 8000x6000@5fps；
UVC 协议中 MJPEG 支持 8000x6000/4000x3000/3840x2160 等高档，
YUY2 只支持到 1920x1080。因此必须显式设 FOURCC=MJPG 才能上到最高档。
结果 JSON 与最高像素照片写到 lab/outputs/camera1_manual_spec/。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2

## 目标摄像头设备号
DEVICE_ID: int = 1
## 输出目录
OUT_DIR: Path = Path(__file__).resolve().parent / "outputs" / "camera1_manual_spec"
## 手册 UVC/MJPEG 协议列出的全部分辨率档位（宽, 高）
MJPEG_MODES: list[tuple[int, int]] = [
    (8000, 6000), (4000, 3000), (3840, 2160), (2592, 1944),
    (2048, 1536), (1920, 1080), (1280, 720), (800, 600),
]
## 最高像素档（手册第一档）
MAX_MODE: tuple[int, int] = (8000, 6000)
## JPEG 保存质量
JPEG_QUALITY: int = 95


def openMjpeg(backend: int) -> object | None:
    """按后端打开设备并显式切到 MJPEG 格式。"""
    cap = cv2.VideoCapture(DEVICE_ID, backend)
    if not cap.isOpened():
        cap.release()
        return None
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    cap.set(cv2.CAP_PROP_FOURCC, float(fourcc))
    return cap


def probeMode(backend: int, width: int, height: int) -> dict[str, object]:
    """在指定分辨率下探测实际输出帧尺寸与耗时。"""
    cap = openMjpeg(backend)
    if cap is None:
        return {"request": [width, height], "opened": False}
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    actualFourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourccText = "".join(chr((actualFourcc >> shift) & 0xFF) for shift in (0, 8, 16, 24))
    readbackWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    readbackHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame = None
    start = time.monotonic()
    for _ in range(3):
        ok, current = cap.read()
        if ok and current is not None:
            frame = current
    elapsed = time.monotonic() - start
    cap.release()
    actualWidth = int(frame.shape[1]) if frame is not None else 0
    actualHeight = int(frame.shape[0]) if frame is not None else 0
    return {
        "request": [width, height],
        "opened": True,
        "fourcc": fourccText,
        "readback": [readbackWidth, readbackHeight],
        "actual": [actualWidth, actualHeight],
        "grabSeconds": round(elapsed, 3),
        "matched": actualWidth == width and actualHeight == height,
    }


def snapMax(backend: int, width: int, height: int) -> tuple[Path, tuple[int, int]] | None:
    """用最高像素档拍一张照片，返回路径与实际尺寸。"""
    cap = openMjpeg(backend)
    if cap is None:
        return None
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    cap.set(cv2.CAP_PROP_FOURCC, float(fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    frame = None
    for _ in range(4):
        ok, current = cap.read()
        if ok and current is not None:
            frame = current
    cap.release()
    if frame is None:
        return None
    path = OUT_DIR / f"max_{width}x{height}.jpg"
    cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    return path, (int(frame.shape[1]), int(frame.shape[0]))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    backends = [("CAP_MSMF", cv2.CAP_MSMF), ("CAP_DSHOW", cv2.CAP_DSHOW)]
    report: dict[str, object] = {"backends": []}
    for name, backend in backends:
        rows = [probeMode(backend, width, height) for width, height in MJPEG_MODES]
        report["backends"].append({"name": name, "modes": rows})
        print(f"=== {name} ===")
        for row in rows:
            print(f"  请求 {row['request']} -> 实际 {row.get('actual')} "
                  f"FOURCC={row.get('fourcc')} 匹配={row.get('matched')} "
                  f"耗时={row.get('grabSeconds')}s")

    photo: tuple[Path, tuple[int, int]] | None = None
    usedBackend = ""
    for name, backend in backends:
        photo = snapMax(backend, MAX_MODE[0], MAX_MODE[1])
        if photo is not None:
            usedBackend = name
            break
    if photo is None:
        print("最高像素档拍照失败")
        (OUT_DIR / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    path, size = photo
    report["photo"] = str(path)
    report["photoSize"] = list(size)
    report["photoBackend"] = usedBackend
    report["megapixels"] = round(size[0] * size[1] / 1_000_000, 2)
    (OUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PHOTO={path} size={size[0]}x{size[1]} = {report['megapixels']}MP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
