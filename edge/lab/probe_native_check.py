"""甄别摄像头真实原生分辨率：后端 set+read 会被软件缩放欺骗，改用图像细节对比。

同一静止场景在各档分辨率下拍图，做两项判定：
1) 各档统一缩到 640x360 后比清晰度（拉普拉斯方差），真原生细节最多、插值偏软；
2) 把最大档缩回次大档与直接拍摄的同尺寸图做 PSNR，像素级一致即为插值放大。
结果 JSON 与各档原图写到 lab/outputs/camera1_native_check/。
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

## 目标摄像头设备号
DEVICE_ID: int = 1
## 输出目录
OUT_DIR: Path = Path(__file__).resolve().parent / "outputs" / "camera1_native_check"
## 采集后端：DSHOW Reported 档位最全
BACKEND_NAME: str = "CAP_DSHOW"
BACKEND: int = cv2.CAP_DSHOW
## 待比较的分辨率档位（宽, 高）
CANDIDATES: list[tuple[int, int]] = [
    (640, 480), (1024, 768), (1280, 720), (1600, 1200),
    (1920, 1080), (2048, 1536), (2592, 1944), (3840, 2160),
]
## 统一比较尺寸（宽, 高）
COMPARE_SIZE: tuple[int, int] = (640, 360)
## JPEG 保存质量
JPEG_QUALITY: int = 95


def grab(width: int, height: int) -> tuple[np.ndarray | None, tuple[int, int]]:
    """在指定分辨率下拍一帧，返回图像与 set 后回读的宽高。"""
    cap = cv2.VideoCapture(DEVICE_ID, BACKEND)
    if not cap.isOpened():
        cap.release()
        return None, (0, 0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    readWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    readHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame: np.ndarray | None = None
    for _ in range(4):
        ok, current = cap.read()
        if ok and current is not None:
            frame = current
    cap.release()
    return frame, (readWidth, readHeight)


def sharpness(gray: np.ndarray) -> float:
    """灰度图的拉普拉斯方差，数值越大细节越锐利。"""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def psnr(left: np.ndarray, right: np.ndarray) -> float:
    """两张同尺寸灰度图的峰值信噪比，越大越接近同一张图。"""
    diff = left.astype(np.float64) - right.astype(np.float64)
    mse = float(np.mean(diff * diff))
    if mse <= 0.0:
        return 99.0
    return float(10.0 * np.log10(255.0 * 255.0 / mse))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    grays: dict[tuple[int, int], np.ndarray] = {}
    for width, height in CANDIDATES:
        frame, readback = grab(width, height)
        if frame is None:
            print(f"SKIP {width}x{height} 取帧失败")
            continue
        actualHeight, actualWidth = frame.shape[:2]
        path = OUT_DIR / f"frame_{width}x{height}.jpg"
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, COMPARE_SIZE, interpolation=cv2.INTER_AREA)
        row: dict[str, object] = {
            "request": [width, height],
            "readback": list(readback),
            "actual": [actualWidth, actualHeight],
            "jpegBytes": path.stat().st_size,
            "sharpnessFull": round(sharpness(gray), 2),
            "sharpnessNormalized": round(sharpness(small), 2),
        }
        rows.append(row)
        grays[(width, height)] = gray
        print(f"{width}x{height}: actual={actualWidth}x{actualHeight} "
              f"jpeg={row['jpegBytes']}B sharpFull={row['sharpnessFull']} "
              f"sharp640={row['sharpnessNormalized']}")

    ## 关键对比：把大档缩回小档，与直接拍的小档图比 PSNR
    comparisons: list[dict[str, object]] = []
    pairs: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((3840, 2160), (2592, 1944)),
        ((3840, 2160), (1920, 1080)),
        ((2592, 1944), (1920, 1080)),
        ((2048, 1536), (1600, 1200)),
        ((1920, 1080), (1280, 720)),
        ((1280, 720), (640, 480)),
    ]
    for big, smallKey in pairs:
        if big not in grays or smallKey not in grays:
            continue
        target = (grays[smallKey].shape[1], grays[smallKey].shape[0])
        resized = cv2.resize(grays[big], target, interpolation=cv2.INTER_AREA)
        score = psnr(resized, grays[smallKey])
        comparisons.append({"big": list(big), "small": list(smallKey),
                            "psnr": round(score, 2)})
        print(f"PSNR {big[0]}x{big[1]} -> {smallKey[0]}x{smallKey[1]}: {score:.2f} dB")

    payload = {"backend": BACKEND_NAME, "rows": rows, "comparisons": comparisons}
    (OUT_DIR / "native_check.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果: {OUT_DIR / 'native_check.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
