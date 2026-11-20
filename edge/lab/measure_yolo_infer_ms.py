"""实测 yolov8n 在 640x640 输入下的推理耗时（onnxruntime CPU / ultralytics）。

结果写 lab/outputs/yolo_infer/infer.json。注意：本机 CPU 数值只供量级参考，
RK3588 部署走 NPU 换 rknn 后端，实际耗时要上板实测。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

OUT_DIR: Path = Path(__file__).resolve().parent / "outputs" / "yolo_infer"
ONNX_PATH: Path = Path(__file__).resolve().parents[2] / "weights" / "yolov8n.onnx"
PT_PATH: Path = Path(__file__).resolve().parents[2] / "weights" / "yolov8n.pt"
IMG_SIZE: int = 640
WARMUP: int = 3
ROUNDS: int = 20


def makeInput() -> np.ndarray:
    """构造一张 640x640 的 BGR 随机图，避免读盘 IO 混进推理计时。"""
    image = np.random.randint(0, 255, (IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
    return image


def measureOnnx() -> dict[str, object]:
    """onnxruntime CPU 后端计时。"""
    if not ONNX_PATH.exists():
        return {"backend": "onnxruntime", "available": False, "error": "缺 onnx 权重"}
    try:
        import onnxruntime  # type: ignore
    except ImportError as error:
        return {"backend": "onnxruntime", "available": False, "error": str(error)}
    session = onnxruntime.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    inputMeta = session.get_inputs()[0]
    name = inputMeta.name
    shape = list(inputMeta.shape)
    height = int(shape[2]) if len(shape) >= 4 else IMG_SIZE
    width = int(shape[3]) if len(shape) >= 4 else IMG_SIZE
    tensor = np.random.rand(1, 3, height, width).astype(np.float32)
    for _ in range(WARMUP):
        session.run(None, {name: tensor})
    start = time.monotonic()
    for _ in range(ROUNDS):
        session.run(None, {name: tensor})
    elapsed = time.monotonic() - start
    avgMs = 1000.0 * elapsed / ROUNDS
    return {
        "backend": "onnxruntime",
        "available": True,
        "provider": "CPUExecutionProvider",
        "model": str(ONNX_PATH),
        "modelInput": [height, width],
        "rounds": ROUNDS,
        "avgMsPerInfer": round(avgMs, 2),
        "fpsCeiling": round(1000.0 / avgMs, 2),
    }


def measureUltralytics() -> dict[str, object]:
    """ultralytics 后端计时；没有 pt 权重则跳过。"""
    if not PT_PATH.exists():
        return {"backend": "ultralytics", "available": False, "error": "缺 pt 权重"}
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as error:
        return {"backend": "ultralytics", "available": False, "error": str(error)}
    model = YOLO(str(PT_PATH))
    image = makeInput()
    for _ in range(WARMUP):
        model.predict(image, imgsz=IMG_SIZE, verbose=False)
    start = time.monotonic()
    for _ in range(ROUNDS):
        model.predict(image, imgsz=IMG_SIZE, verbose=False)
    elapsed = time.monotonic() - start
    avgMs = 1000.0 * elapsed / ROUNDS
    return {
        "backend": "ultralytics",
        "available": True,
        "model": str(PT_PATH),
        "imgsz": IMG_SIZE,
        "rounds": ROUNDS,
        "avgMsPerInfer": round(avgMs, 2),
        "fpsCeiling": round(1000.0 / avgMs, 2),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [measureOnnx(), measureUltralytics()]
    (OUT_DIR / "infer.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in rows:
        print(row)
    print(f"结果: {OUT_DIR / 'infer.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
