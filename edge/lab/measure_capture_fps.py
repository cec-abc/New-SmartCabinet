"""实测 AT-01M7000B 各分辨率档的连续采集帧率（MJPEG / CAP_DSHOW）。

每档连续抓 N 帧算平均 fps 与单帧耗时，结果写 lab/outputs/capture_fps/。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2

DEVICE_ID: int = 1
OUT_DIR: Path = Path(__file__).resolve().parent / "outputs" / "capture_fps"
MODES: list[tuple[int, int]] = [
    (8000, 6000), (4000, 3000), (3840, 2160), (2592, 1944),
    (2048, 1536), (1920, 1080), (1280, 720), (800, 600), (640, 480),
]
SAMPLE_FRAMES: int = 10
WARMUP_FRAMES: int = 2


def measure(width: int, height: int) -> dict[str, object]:
    """连续抓 SAMPLE_FRAMES 帧，返回实测 fps 与单帧耗时。"""
    cap = cv2.VideoCapture(DEVICE_ID, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        return {"request": [width, height], "opened": False}
    cap.set(cv2.CAP_PROP_FOURCC, float(cv2.VideoWriter_fourcc(*"MJPG")))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourccText = "".join(chr((fourcc >> shift) & 0xFF) for shift in (0, 8, 16, 24))
    readback: tuple[int, int] = (
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )
    for _ in range(WARMUP_FRAMES):
        cap.read()
    start = time.monotonic()
    got = 0
    for _ in range(SAMPLE_FRAMES):
        ok, frame = cap.read()
        if ok and frame is not None:
            got += 1
    elapsed = time.monotonic() - start
    cap.release()
    fps = got / elapsed if elapsed > 0 else 0.0
    return {
        "request": [width, height],
        "opened": True,
        "fourcc": fourccText,
        "readback": list(readback),
        "frames": got,
        "elapsedSeconds": round(elapsed, 3),
        "fps": round(fps, 2),
        "msPerFrame": round(1000.0 / fps, 1) if fps > 0 else None,
        "megapixels": round(width * height / 1_000_000, 2),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [measure(width, height) for width, height in MODES]
    (OUT_DIR / "fps.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'档位':<14}{'像素':>8}{'FOURCC':>8}{'回读':>14}{'fps':>8}{'单帧ms':>9}")
    for row in rows:
        if not row["opened"]:
            print(f"{row['request']} 打不开")
            continue
        req = f"{row['request'][0]}x{row['request'][1]}"
        read = f"{row['readback'][0]}x{row['readback'][1]}"
        print(f"{req:<14}{row['megapixels']:>8}{row['fourcc']:>8}"
              f"{read:>14}{row['fps']:>8}{str(row['msPerFrame']):>9}")
    print(f"结果: {OUT_DIR / 'fps.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
