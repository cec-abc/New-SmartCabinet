"""按比例裁剪图片并识别：lab 独立测试工具，不依赖生产装配与 TCP 链路。

把裁剪后的图片保存到工程根目录，再用生产 YoloEngine 对裁剪图推理并打印结果。
用法：
    python edge/lab/crop_and_recognize.py
    python edge/lab/crop_and_recognize.py --image edge/lab/outputs/layer_verify/right.jpg --ratio 0.3 --side left
    python edge/lab/crop_and_recognize.py --image 自定义.jpg --ratio 0.9 --side right --output-dir .
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

## @file edge/lab/crop_and_recognize.py
## @brief 按比例裁剪图片、保存裁剪图到根目录、并对裁剪图执行 YOLO 识别
## @author 袁燕

from edge.infra.roi_binding_loader import DETECTION_CLASS_FIELD
from edge.modules.recognition.recognition_utils import (
    DETECTION_BOX_FIELD,
    DETECTION_CONFIDENCE_FIELD,
)
from edge.modules.recognition.recognition_yolo_engine import YoloEngine

DEFAULT_IMAGE: Path = PROJECT_ROOT / "edge/lab/outputs/layer_verify/left.jpg"
DEFAULT_WEIGHT: Path = PROJECT_ROOT / "weights/yolov8n.pt"
DEFAULT_OUTPUT_DIR: Path = PROJECT_ROOT


## @brief 静默日志器：只实现生产契约的四个方法，不写日志文件
class SilentLogger:
    ## @brief 收帧日志（空实现）
    def rx(self, module: str, data: object) -> None:
        pass

    ## @brief 发帧日志（空实现）
    def tx(self, module: str, data: object) -> None:
        pass

    ## @brief 普通信息日志（空实现）
    def info(self, module: str, msg: str) -> None:
        pass

    ## @brief 错误日志（空实现）
    def error(self, module: str, msg: str, exception: Exception | None = None) -> None:
        pass


## @brief 解析命令行参数
#  @return 参数命名空间
def parseArgs() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按比例裁剪图片并识别")
    parser.add_argument("--image", default=str(DEFAULT_IMAGE), help="输入图片路径")
    parser.add_argument(
        "--ratio", type=float, default=0.9,
        help="裁剪比例 0~1：side=right 表示保留右侧该比例，side=left 表示保留左侧该比例",
    )
    parser.add_argument(
        "--side", choices=("left", "right"), default="right",
        help="裁剪方向：right=保留右侧，left=保留左侧",
    )
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUTPUT_DIR),
        help="裁剪图保存目录，默认工程根目录",
    )
    parser.add_argument("--weight", default=str(DEFAULT_WEIGHT), help="模型权重路径")
    parser.add_argument(
        "--conf", type=float, default=0.25,
        help="推理置信度门槛，默认 0.25（扫描口径，非业务 0.85 门槛）",
    )
    return parser.parse_args()


## @brief 按比例裁剪图片
#  @param image 原图数组
#  @param ratio 保留比例 0~1
#  @param side 裁剪方向：left 保留左侧、right 保留右侧
#  @return 裁剪后的图
#  @raises ValueError 比例越界时抛出
def cropByRatio(image: np.ndarray, ratio: float, side: str) -> np.ndarray:
    if not 0 < ratio <= 1:
        raise ValueError(f"裁剪比例必须在 (0,1] 区间: {ratio}")
    height, width = image.shape[:2]
    cropWidth = max(1, int(width * ratio))
    if side == "right":
        return image[:, width - cropWidth:width]
    return image[:, 0:cropWidth]


## @brief 把图片编码成 PNG 字节，供生产引擎推理
#  @param image 图片数组
#  @return PNG 字节
def encodePng(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("裁剪图编码失败")
    return bytes(encoded.tobytes())


## @brief 把检测结果整理成可打印的字典
#  @param detections 生产引擎检测结果
#  @return 结果列表
def formatDetections(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "className": detection.get(DETECTION_CLASS_FIELD),
            "confidence": round(float(detection.get(DETECTION_CONFIDENCE_FIELD, 0)), 4),
            "box": [round(float(value), 1) for value in detection.get(DETECTION_BOX_FIELD, [])],
        }
        for detection in detections
    ]


## @brief 主流程：裁剪、保存、识别、输出
#  @return 退出码
def main() -> int:
    args = parseArgs()
    source = Path(args.image)
    image = cv2.imread(str(source))
    if image is None:
        print(f"图片读取失败: {source}")
        return 1

    cropped = cropByRatio(image, args.ratio, args.side)
    outputDir = Path(args.output_dir)
    outputDir.mkdir(parents=True, exist_ok=True)
    stem = f"{source.stem}_crop_{args.side}_{int(args.ratio * 100)}"
    savedPath = outputDir / f"{stem}.png"
    cv2.imwrite(str(savedPath), cropped)
    print(f"裁剪图已保存: {savedPath}")
    print(f"原图尺寸={image.shape[1]}x{image.shape[0]} 裁剪尺寸={cropped.shape[1]}x{cropped.shape[0]}")

    logger = SilentLogger()
    engine = YoloEngine.instance(logger, backend="ultralytics", confThreshold=args.conf)
    engine.loadModel(args.weight)
    detections = engine.infer(encodePng(cropped))
    results = formatDetections(detections)
    print(f"识别结果 {len(results)} 条:")
    for result in results:
        print(f"  {result['className']} conf={result['confidence']} box={result['box']}")

    resultPath = outputDir / f"{stem}_result.json"
    resultPath.write_text(
        json.dumps(
            {
                "source": str(source.resolve()),
                "ratio": args.ratio,
                "side": args.side,
                "savedImage": str(savedPath.resolve()),
                "confidenceThreshold": args.conf,
                "detections": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"识别结果已保存: {resultPath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
