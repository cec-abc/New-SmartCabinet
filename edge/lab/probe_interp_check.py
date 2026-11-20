"""判定 2592x1944 / 3840x2160 是否为从 1920x1080 插值放大。

把直拍的 1920x1080 用三次插值放大到各档尺寸，与直拍同尺寸图比：
若"放大图缩回 640x360 的清晰度"接近或超过"直拍图"，说明大档只是插值，
没有额外真实细节；若直拍图明显更锐利，说明该档有独立传感器细节。
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

SRC_DIR: Path = Path(__file__).resolve().parent / "outputs" / "camera1_native_check"
COMPARE_SIZE: tuple[int, int] = (640, 360)


def load(name: str) -> np.ndarray | None:
    path = SRC_DIR / name
    data = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return data


def sharpAt640(gray: np.ndarray) -> float:
    small = cv2.resize(gray, COMPARE_SIZE, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(small, cv2.CV_64F).var())


def main() -> int:
    base = load("frame_1920x1080.jpg")
    if base is None:
        print("缺少 1920x1080 基准图")
        return 1
    print(f"直拍 1920x1080 缩到 640 的清晰度: {sharpAt640(base):.2f}")
    for name, width, height in [
        ("frame_2592x1944.jpg", 2592, 1944),
        ("frame_3840x2160.jpg", 3840, 2160),
    ]:
        direct = load(name)
        if direct is None:
            print(f"缺少 {name}")
            continue
        upscaled = cv2.resize(base, (width, height), interpolation=cv2.INTER_CUBIC)
        directSharp = sharpAt640(direct)
        upSharp = sharpAt640(upscaled)
        diff = np.abs(direct.astype(np.float64) - upscaled.astype(np.float64))
        meanAbs = float(np.mean(diff))
        print(f"{width}x{height}: 直拍缩640清晰度={directSharp:.2f}, "
              f"1080p放大缩640清晰度={upSharp:.2f}, "
              f"直拍/放大={directSharp / upSharp if upSharp else 0:.3f}, "
              f"平均像素差={meanAbs:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
