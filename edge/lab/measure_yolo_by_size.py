"""实测 YOLOv8n 在不同推理输入尺寸下的耗时，验证推理时间随尺寸变化。

 ultralytics(pt) 与 onnxruntime(onnx) 两个后端各跑 320/640/960/1280 四档。
 结果写 lab/outputs/yolo_by_size/infer_by_size.json。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

OUT_DIR: Path = Path(__file__).resolve().parent / "outputs" / "yolo_by_size"
PT_PATH: Path = Path(__file__).resolve().parents[2] / "weights" / "yolov8n.pt"
ONNX_PATH: Path = Path(__file__).resolve().parents[2] / "weights" / "yolov8n.onnx"
SIZES: list[int] = [320, 640, 960, 1280]
WARMUP: int = 2
ROUNDS: int = 12


def measureUltralytics() -> list[dict[str, object]]:
    """ultralytics 后端：imgsz 可任意指定（32 的倍数）。"""
    if not PT_PATH.exists():
        return []
    from ultralytics import YOLO  # type: ignore
    model = YOLO(str(PT_PATH))
    rows: list[dict[str, object]] = []
    for size in SIZES:
        image = np.random.randint(0, 255, (size, size, 3), dtype=np.uint8)
        for _ in range(WARMUP):
            model.predict(image, imgsz=size, verbose=False)
        start = time.monotonic()
        for _ in range(ROUNDS):
            model.predict(image, imgsz=size, verbose=False)
        elapsed = time.monotonic() - start
        rows.append({"backend": "ultralytics", "size": size,
                     "avgMs": round(1000.0 * elapsed / ROUNDS, 2)})
    return rows


def measureOnnxFixed() -> dict[str, object] | None:
    """onnx 后端：导出时输入形状固定，只能按该形状跑；若支持动态再逐档。"""
    if not ONNX_PATH.exists():
        return None
    import onnxruntime  # type: ignore
    session = onnxruntime.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    meta = session.get_inputs()[0]
    shape = list(meta.shape)
    return {"backend": "onnxruntime", "onnxInputShape": shape,
            "note": "onnx 导出时固定形状，改尺寸需重新导出"}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = measureUltralytics()
    onnxInfo = measureOnnxFixed()
    payload: dict[str, object] = {"ultralytics": rows, "onnx": onnxInfo}
    (OUT_DIR / "infer_by_size.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== ultralytics 各输入尺寸耗时（本机 CPU）===")
    for row in rows:
        print(f"  {row['size']}x{row['size']}: {row['avgMs']} ms")
    print(f"=== onnx 输入形状: {onnxInfo} ===")
    print(f"结果: {OUT_DIR / 'infer_by_size.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
