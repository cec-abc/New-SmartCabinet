# dual_crop_stitch

极简双摄「图像切割 + 左右拼接」工具，纯 OpenCV + numpy。无 argparse、无 YOLO、无单应性、无标定、无融合。

## 运行

1. 用编辑器打开 `main.py`，修改顶部「运行配置」区：
   - `LEFT_IMAGE_PATH` / `RIGHT_IMAGE_PATH`：左右原图路径
   - `CROP_WIDTH` / `CROP_HEIGHT`：设为 `0` 即自动（五五分：宽=原图宽//2，高=两图较小高）
2. 右键 `main.py` → Run（无命令行依赖）。
3. 输出在 `output/`：`crop_left.jpg`（左摄右半）、`crop_right.jpg`（右摄左半）、`stitch.jpg`（拼接还原）。

## 说明

- 五五分切割时 `stitch.jpg` 与原图逐像素一致。
- `CROP_WIDTH` 大于原图宽会返回失败并正常退出（退出码 0）。
- `stitch_images` 的 `stitchPoints` 支持 float，内部 `int(round())`，后贴覆盖前贴。

## 验收要点

- 1280×720 原图对，`CROP_WIDTH=640, CROP_HEIGHT=720` → 两张 640×720 + 一张 1280×720。
- `CROP_WIDTH=900`（>宽/2）→ 拼接宽 1280，中间重叠区后贴覆盖，无报错。
- `CROP_WIDTH=1400`（>原图宽）→ 返回失败，log「裁剪宽超过图像宽」，正常退出。
- `CROP_WIDTH=0` → 自动五五分跑通。
