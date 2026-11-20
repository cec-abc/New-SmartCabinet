"""把采集帧率与推理耗时的实测数据汇总成矩阵表（Markdown + CSV）。

数据源：outputs/capture_fps/fps.json 与 outputs/yolo_infer/infer.json。
输出到 outputs/pipeline_matrix.md 与 .csv。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

BASE: Path = Path(__file__).resolve().parent / "outputs"
FPS_JSON: Path = BASE / "capture_fps" / "fps.json"
INFER_JSON: Path = BASE / "yolo_infer" / "infer.json"
OUT_MD: Path = BASE / "pipeline_matrix.md"
OUT_CSV: Path = BASE / "pipeline_matrix.csv"

## 手册标称 fps：键为 "宽x高"，(MJPEG, YUY2)，None 表示该编码不支持该档
MANUAL_FPS: dict[str, tuple[int | None, int | None]] = {
    "8000x6000": (5, None),
    "4000x3000": (15, None),
    "3840x2160": (30, None),
    "2592x1944": (20, None),
    "2048x1536": (20, None),
    "1920x1080": (30, 5),
    "1280x720": (30, None),
    "800x600": (20, 20),
    "640x480": (None, 20),
}


def main() -> int:
    fpsRows = json.loads(FPS_JSON.read_text(encoding="utf-8"))
    inferRows = json.loads(INFER_JSON.read_text(encoding="utf-8"))
    ultralyticsMs: float | None = None
    onnxMs: float | None = None
    for row in inferRows:
        if not row.get("available"):
            continue
        if row["backend"] == "ultralytics":
            ultralyticsMs = float(row["avgMsPerInfer"])
        if row["backend"] == "onnxruntime":
            onnxMs = float(row["avgMsPerInfer"])

    headers = [
        "采集档位", "像素(MP)", "实测编码", "手册MJPEG fps", "手册YUY2 fps",
        "实测fps", "单帧采集ms", "推理输入", "推理ms(本机CPU)", "采+推合计ms",
    ]
    table: list[list[str]] = [headers]
    for row in fpsRows:
        if not row.get("opened"):
            continue
        width, height = row["request"]
        key = f"{width}x{height}"
        manual = MANUAL_FPS.get(key, (None, None))
        fourcc = str(row.get("fourcc", "")).strip() or "?"
        inferMs = ultralyticsMs if ultralyticsMs is not None else 0.0
        captureMs = float(row.get("msPerFrame") or 0.0)
        total = captureMs + inferMs
        table.append([
            key,
            str(row.get("megapixels", "")),
            fourcc,
            str(manual[0] if manual[0] is not None else "-"),
            str(manual[1] if manual[1] is not None else "-"),
            str(row.get("fps", "")),
            str(row.get("msPerFrame", "")),
            "640x640(ultralytics)",
            f"{inferMs:.1f}" if ultralyticsMs is not None else "-",
            f"{total:.1f}",
        ])

    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle).writerows(table)

    lines = ["# 采集速率与 YOLOv8n 推理时间矩阵", ""]
    lines.append("> 采集为单路 Windows / CAP_DSHOW 实测；推理为本机 CPU 实测，")
    lines.append("> 生产默认 ultralytics + 640 输入，推理耗时不随采集像素变化。")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in table[1:]:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append(f"- onnxruntime CPU 推理（onnx 权重输入实测 1280x1280）：{onnxMs} ms/帧")
    lines.append(f"- ultralytics CPU 推理（imgsz=640）：{ultralyticsMs} ms/帧")
    lines.append("- RK3588 NPU（rknn/int8，yolov8n 640）需上板实测，典型量级 15~40 ms。")
    lines.append("- 拼接为双摄两路采集，USB2.0 共享带宽，两路同时采集时单路 fps 会进一步下降。")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"写出: {OUT_MD}")
    print(f"写出: {OUT_CSV}")
    for row in table:
        print(" | ".join(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
