"""lab 拼接调参工具：脱离生产代码，用两张图片试不同拼接方式与对齐参数。

只读图片、只写输出目录，不依赖 edge.modules 等生产模块；参数全部来自 JSON 配置。
用法：
    python edge/lab/stitch_tuning_lab.py                     # 按默认配置出一张
    python edge/lab/stitch_tuning_lab.py --sweep             # 批量出多参数对比
    python edge/lab/stitch_tuning_lab.py --config 自定义.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

## 允许从任意目录直接运行：把工程根加入模块搜索路径
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

## @file edge/lab/stitch_tuning_lab.py
## @brief lab 拼接调参：比例切分、垂直对齐、重叠羽化三种模式的独立试验工具
## @author 袁燕

DEFAULT_CONFIG: Path = Path(__file__).resolve().parent / "stitch_tuning.json"
DEFAULT_OUTPUT_DIR: Path = Path(__file__).resolve().parent / "outputs" / "stitch_tuning"


## @brief 读取 JSON 配置
#  @param path 配置文件路径
#  @return 配置字典
def loadConfig(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        loaded = json.load(stream)
    if not isinstance(loaded, dict):
        raise ValueError("配置根节点必须是对象")
    return loaded


## @brief 读图片
#  @param path 图片路径
#  @return BGR 数组
def loadImage(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"图片无法读取: {path}")
    return image


## @brief 垂直平移：正值为下移，负值为上移，空出的区域填白
#  @param image 源图
#  @param offsetY 垂直偏移像素
#  @return 平移后的图，尺寸不变
def shiftVertical(image: np.ndarray, offsetY: int) -> np.ndarray:
    if offsetY == 0:
        return image.copy()
    result = np.full_like(image, 255)
    height, width = image.shape[:2]
    if offsetY > 0:
        srcStart, dstStart = 0, offsetY
        copyHeight = min(height, height - offsetY)
    else:
        srcStart, dstStart = -offsetY, 0
        copyHeight = min(height, height + offsetY)
    if copyHeight > 0:
        result[dstStart:dstStart + copyHeight] = image[srcStart:srcStart + copyHeight]
    return result


## @brief 比例切分拼接：左图取右侧 ratio 宽，右图取左侧 1-ratio 宽，全景宽固定
#  @param left 左图
#  @param right 右图
#  @param ratio 左图占比 0~1
#  @param leftY 左图垂直偏移
#  @param rightY 右图垂直偏移
#  @return 拼接图
def stitchByRatio(left: np.ndarray, right: np.ndarray, ratio: float,
                  leftY: int, rightY: int) -> np.ndarray:
    width = left.shape[1]
    leftShifted = shiftVertical(left, leftY)
    rightShifted = shiftVertical(right, rightY)
    leftWidth = int(width * ratio)
    rightWidth = width - leftWidth
    leftCrop = leftShifted[:, width - leftWidth:width]
    rightCrop = rightShifted[:, 0:rightWidth]
    return np.hstack((leftCrop, rightCrop))


## @brief 整图重叠羽化拼接：两图横向叠放，重叠区按 alpha 渐变混合
#  @param left 左图
#  @param right 右图
#  @param overlap 重叠宽度像素
#  @param leftY 左图垂直偏移
#  @param rightY 右图垂直偏移
#  @return 拼接图
def stitchWithBlend(left: np.ndarray, right: np.ndarray, overlap: int,
                    leftY: int, rightY: int) -> np.ndarray:
    leftShifted = shiftVertical(left, leftY)
    rightShifted = shiftVertical(right, rightY)
    height = leftShifted.shape[0]
    totalWidth = leftShifted.shape[1] + rightShifted.shape[1] - overlap
    canvas = np.full((height, totalWidth, 3), 255, dtype=np.uint8)
    lw = leftShifted.shape[1]
    canvas[:, :lw] = leftShifted
    for offset in range(overlap):
        alpha = offset / max(1, overlap - 1)
        leftPixel = leftShifted[:, lw - overlap + offset].astype(np.float32)
        rightPixel = rightShifted[:, offset].astype(np.float32)
        canvas[:, lw - overlap + offset] = (
            leftPixel * (1 - alpha) + rightPixel * alpha
        ).astype(np.uint8)
    canvas[:, lw:] = rightShifted[:, overlap:]
    return canvas


## @brief 配准拼接：SIFT 求单应性矩阵，把右图变换到左图坐标系后融合
#  @param left 左图
#  @param right 右图
#  @param matchRatio 特征匹配距离比阈值
#  @param ransacThreshold RANSAC 重投影误差阈值
#  @param manualDx 手动追加水平位移
#  @param manualDy 手动追加垂直位移
#  @return (拼接图, 诊断文本)
def stitchWithAlign(left: np.ndarray, right: np.ndarray, matchRatio: float,
                    ransacThreshold: float, manualDx: int,
                    manualDy: int) -> tuple[np.ndarray, str]:
    detector = cv2.SIFT_create(nfeatures=5000)
    grayLeft = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
    grayRight = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
    keyLeft, descLeft = detector.detectAndCompute(grayLeft, None)
    keyRight, descRight = detector.detectAndCompute(grayRight, None)
    if descLeft is None or descRight is None:
        raise ValueError("特征点不足，无法配准")
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    rawMatches = matcher.knnMatch(descLeft, descRight, k=2)
    goodMatches = [
        match for match, second in rawMatches
        if match.distance < matchRatio * second.distance
    ]
    if len(goodMatches) < 4:
        raise ValueError(f"有效匹配点不足: {len(goodMatches)}")
    source = np.float32([keyLeft[m.queryIdx].pt for m in goodMatches]).reshape(-1, 1, 2)
    target = np.float32([keyRight[m.trainIdx].pt for m in goodMatches]).reshape(-1, 1, 2)
    matrix, mask = cv2.findHomography(
        source, target, cv2.RANSAC, ransacThreshold,
    )
    inliers = int(mask.sum()) if mask is not None else 0
    if matrix is None or inliers < 4:
        raise ValueError(f"单应性估计失败: inliers={inliers}")
    ## 矩阵把左图映射到右图坐标系；这里要右图映射到左图，取逆矩阵
    inverse = np.linalg.inv(matrix)
    inverse[0, 2] += manualDx
    inverse[1, 2] += manualDy
    height, width = left.shape[:2]
    warpedRight = cv2.warpPerspective(right, inverse, (width, height))
    ## 重叠区判定：两图都非白的地方取均值，避免生硬接缝
    leftMask = np.any(left < 245, axis=2)
    rightMask = np.any(warpedRight < 245, axis=2)
    overlap = leftMask & rightMask
    canvas = left.copy()
    canvas[overlap] = (
        left[overlap].astype(np.float32) * 0.5
        + warpedRight[overlap].astype(np.float32) * 0.5
    ).astype(np.uint8)
    canvas[~leftMask & rightMask] = warpedRight[~leftMask & rightMask]
    diagnostic = (
        f"matchRatio={matchRatio} ransac={ransacThreshold} "
        f"good={len(goodMatches)} inliers={inliers} manualDx={manualDx} manualDy={manualDy}"
    )
    return canvas, diagnostic


## @brief 手动四点配准：用现场标定的四对对应点求透视变换，适合纹理少的场景
#  @param left 左图
#  @param right 右图
#  @param leftPoints 左图上的四个点 [[x,y], ...]
#  @param rightPoints 右图上对应的四个点 [[x,y], ...]
#  @return 配准融合后的图
def stitchWithManualPoints(left: np.ndarray, right: np.ndarray,
                           leftPoints: list[list[int]],
                           rightPoints: list[list[int]]) -> np.ndarray:
    if len(leftPoints) != 4 or len(rightPoints) != 4:
        raise ValueError("手动配准需要左右各四个对应点")
    source = np.float32(leftPoints).reshape(-1, 1, 2)
    target = np.float32(rightPoints).reshape(-1, 1, 2)
    transform = cv2.getPerspectiveTransform(source, target)
    inverse = np.linalg.inv(transform)
    height, width = left.shape[:2]
    warpedRight = cv2.warpPerspective(right, inverse, (width, height))
    leftMask = np.any(left < 245, axis=2)
    rightMask = np.any(warpedRight < 245, axis=2)
    overlap = leftMask & rightMask
    canvas = left.copy()
    canvas[overlap] = (
        left[overlap].astype(np.float32) * 0.5
        + warpedRight[overlap].astype(np.float32) * 0.5
    ).astype(np.uint8)
    canvas[~leftMask & rightMask] = warpedRight[~leftMask & rightMask]
    return canvas


## @brief 生成带坐标网格的参考图，方便现场读取四对对应点
#  @param left 左图
#  @param right 右图
#  @param path 输出路径
def saveGridReference(left: np.ndarray, right: np.ndarray, path: Path) -> None:
    step = 40
    for image in (left, right):
        height, width = image.shape[:2]
        for x in range(0, width, step):
            cv2.line(image, (x, 0), (x, height), (0, 0, 255), 1)
            cv2.putText(image, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX,
                        0.35, (0, 0, 255), 1)
        for y in range(0, height, step):
            cv2.line(image, (0, y), (width, y), (0, 0, 255), 1)
            cv2.putText(image, str(y), (2, y + 12), cv2.FONT_HERSHEY_SIMPLEX,
                        0.35, (0, 0, 255), 1)
    cv2.imwrite(str(path), np.hstack((left, right)))


## @brief 镜像配准拼接：右图水平翻转后按平移量对齐左图，重叠区融合
#  @param left 左图
#  @param right 右图
#  @param dx 翻转后右图的水平位移（负值左移）
#  @param dy 翻转后右图的垂直位移（负值上移）
#  @return (拼接图, 重叠区像素数)
def stitchWithMirror(left: np.ndarray, right: np.ndarray,
                     dx: int, dy: int) -> tuple[np.ndarray, int]:
    flipped = cv2.flip(right, 1)
    height, width = left.shape[:2]
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    aligned = cv2.warpAffine(
        flipped, matrix, (width, height),
        flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255),
    )
    leftMask = np.any(left < 245, axis=2)
    rightMask = np.any(aligned < 245, axis=2)
    overlap = leftMask & rightMask
    canvas = left.copy()
    canvas[overlap] = (
        left[overlap].astype(np.float32) * 0.5
        + aligned[overlap].astype(np.float32) * 0.5
    ).astype(np.uint8)
    canvas[~leftMask & rightMask] = aligned[~leftMask & rightMask]
    return canvas, int(overlap.sum())


## @brief 两路完整并排：左图在左、右图在右，不做翻转不做融合，两样物体各自完整
#  @param left 左图
#  @param right 右图
#  @return 并排图
def stitchSideBySide(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    height = max(left.shape[0], right.shape[0])
    canvas = np.full(
        (height, left.shape[1] + right.shape[1], 3), 255, dtype=np.uint8,
    )
    canvas[:left.shape[0], :left.shape[1]] = left
    canvas[:right.shape[0], left.shape[1]:] = right
    return canvas


## @brief 按货位各取一路：左图取剪刀区、右图取杯子区，拼成含两样物体的图
#  @param left 左图
#  @param right 右图
#  @param leftRect 左图要保留的矩形 (x1,y1,x2,y2)
#  @param rightRect 右图要保留的矩形 (x1,y1,x2,y2)
#  @return 拼接图
def stitchPickTwo(left: np.ndarray, right: np.ndarray,
                  leftRect: list[int], rightRect: list[int]) -> np.ndarray:
    lx1, ly1, lx2, ly2 = leftRect
    rx1, ry1, rx2, ry2 = rightRect
    leftPart = left[ly1:ly2, lx1:lx2]
    rightPart = right[ry1:ry2, rx1:rx2]
    height = max(leftPart.shape[0], rightPart.shape[0])
    canvas = np.full(
        (height, leftPart.shape[1] + rightPart.shape[1], 3), 255, dtype=np.uint8,
    )
    canvas[:leftPart.shape[0], :leftPart.shape[1]] = leftPart
    canvas[:rightPart.shape[0], leftPart.shape[1]:] = rightPart
    return canvas


## @brief 主流程
#  @return 退出码
def main() -> int:
    parser = argparse.ArgumentParser(description="lab 拼接调参工具")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="JSON 配置路径")
    parser.add_argument("--sweep", action="store_true", help="批量出多比例对比图")
    args = parser.parse_args()

    config = loadConfig(Path(args.config))
    outputDir = Path(config.get("outputDir", str(DEFAULT_OUTPUT_DIR)))
    outputDir.mkdir(parents=True, exist_ok=True)
    left = loadImage(Path(config["leftImage"]))
    right = loadImage(Path(config["rightImage"]))
    leftY = int(config.get("leftY", 0))
    rightY = int(config.get("rightY", 0))

    if args.sweep:
        for ratio in config.get("sweepRatios", [0.3, 0.4, 0.5, 0.6, 0.7]):
            result = stitchByRatio(left, right, float(ratio), leftY, rightY)
            name = f"ratio_{int(float(ratio) * 100)}.png"
            cv2.imwrite(str(outputDir / name), result)
            print(f"saved {outputDir / name} shape={result.shape}")
        return 0

    mode = str(config.get("mode", "ratio"))
    if mode == "ratio":
        result = stitchByRatio(left, right, float(config.get("ratio", 0.5)), leftY, rightY)
    elif mode == "blend":
        result = stitchWithBlend(
            left, right, int(config.get("overlap", 160)), leftY, rightY,
        )
    elif mode == "align":
        result, diagnostic = stitchWithAlign(
            left, right,
            float(config.get("matchRatio", 0.7)),
            float(config.get("ransacThreshold", 4.0)),
            int(config.get("manualDx", 0)),
            int(config.get("manualDy", 0)),
        )
        print(diagnostic)
    elif mode == "manual":
        result = stitchWithManualPoints(
            left, right,
            config.get("leftPoints", []),
            config.get("rightPoints", []),
        )
    elif mode == "mirror":
        result, overlapPixels = stitchWithMirror(
            left, right,
            int(config.get("mirrorDx", 0)),
            int(config.get("mirrorDy", 0)),
        )
        print(f"mirror overlap pixels={overlapPixels}")
    elif mode == "sidebyside":
        result = stitchSideBySide(left, right)
    elif mode == "picktwo":
        result = stitchPickTwo(
            left, right,
            config.get("leftRect", [0, 0, left.shape[1], left.shape[0]]),
            config.get("rightRect", [0, 0, right.shape[1], right.shape[0]]),
        )
    elif mode == "grid":
        saveGridReference(left, right, outputDir / "grid_reference.png")
        print(f"saved {outputDir / 'grid_reference.png'}")
        return 0
    else:
        raise ValueError(f"未知拼接模式: {mode}")
    name = str(config.get("outputName", f"result_{mode}.png"))
    cv2.imwrite(str(outputDir / name), result)
    print(f"saved {outputDir / name} shape={result.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
