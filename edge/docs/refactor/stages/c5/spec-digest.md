# c5 识别模块 spec-digest

## ① 范围与资料
- 交付 `edge/modules/recognition/` 五文件：`__init__.py`（包标记）、`recognition_controller.py`、`recognition_worker.py`、`recognition_yolo_engine.py`、`recognition_utils.py`；补强单测 `edge/tests/unit/test_stage_c5_recognition.py`；`fake_recognition_engine.py` 只读复用。
- 语义来源：INDEX §2.9 `识别/识别.txt`（类图 / 流程图 / 时序图）+ 3 张 PNG、`整体流程/阶段4-5.png` 下半段；§2.10 协议 docx 只取线上键名。只取「模型单次加载 / 按 workerId 触发并立即返回 / 读图拼接画 ROI / 3s 超时 / 空间归集查表 / 组 ack / 回调」语义，不转录图中文字。
- 验收项 `c5-1`~`c5-4` 以 `stage-catalog.md` c5 段为准，原措辞不改；文件命名按 L1 `整体重构方案.txt` §2 目录结构。

## ② 命名裁决（图上 snake_case 不作 API）
| 旧图标识符 | 落地标识符 | 依据 |
| --- | --- | --- |
| `load_model` / `getValue("recognition.model_path")` | `loadModel` / 构造注入 `modelPath` | L1 §3 `IRecognitionEngine` 接口表；模块内不 import 配置 |
| `crop_and_merge` / `draw_roi` / `_build_ack` | `cropAndMerge` / `drawRoi` / `buildAck`（纯函数，落 `recognition_utils.py`） | glossary §3.1 / L1 §3 c5 段 |
| `on_recognition_result` / `on_recognition_error` | `onRecognitionResult` / `onRecognitionError` | L1 §3 `IRecognitionSink` 接口表 |
| `on_worker_result` / `on_worker_error` | 门面内 `onRecognitionWorkerResult` / `onRecognitionWorkerError` | 非 L1 接口，按 camelCase；带模块前缀规避全局重名 |
| `triggerRecognition` / `stopRecognition` | `trigger` / `stop` | L1 门面职责；`trigger` 内留 NPU 并发限流 TODO |
| `getInstance` / `selfCheck` | `instance()`（双检锁）/ `selfCheckRecognition()` 空方法 + TODO | L1 §1 单例口径 / 裁决 D-01；带前缀规避与 c4 `selfCheck` 重名 |
| `_load_images` / `_infer` / `_aggregate_roi` / `_validate` | 注入 `frameLoader`、`runInference`、`aggregateByRoi`、`validateByTable` | 私有方法同样 camelCase，外部依赖构造注入（L-06 / L-08） |
- 图上「三大优先级判定」「打印校验报告」等文字不转录；查表校验只做类别映射与 ROI 绑定查表，**不判定错放**（见 ⑤）。

## ③ 契约与接口
- 依赖：`base/base_service.py` + `base/base_thread.py`、`interfaces/i_sinks.py`（`IRecognitionSink` / `AckFrame`）、`i_recognition_engine.py`、`i_camera.py`（`FrameImage`）、`i_logger.py`、`exceptions.py`；`modules/recognition/` 不 import `modules/usb/`、`modules/tcp/`、`control/`，门面只依赖 `i_sinks.py`。
- 线程全部继承 `BaseThread`；Sink 回调只做轻量转发，读图、拼接、推理、归集、组帧都在识别线程内完成；`inferTimeoutSec`、`timeoutRunner`、`frameLoader`、`roiConfig`、`classItemMap`、`roiBindMap`、`modelPath`、`saveDirs` 全部构造注入，模块内零配置读取、零魔鬼数字、零 `sys.platform` / `cv2` / `numpy`。
- `YoloEngine(IRecognitionEngine)` 类内 `instance()` 双检锁、普通构造可用于测试；`loadModel` 同实例幂等（仅一次），真实 rknn 加载 / 推理留 `TODO` 切换点；纯函数集中 `recognition_utils.py`，为 `.so` 下沉预留。

## ④ 裁决落实
- **D-01**：`selfCheckRecognition()` 只留空方法 + TODO，不执行 IO、不返回伪结果、不新增自检线程；初始化 / 模型加载失败按 Fail-Fast 抛 `EdgeError(CONFIG)`，不引入「识别不可用」能力降级。
- **D-02**：本模块不感知 `linkState`；`init()` 只加载模型、不预启任何 worker，唯一拉起点是 `trigger()` 前置校验后 `start()` 并立即返回，不预热线程。
- **c5 专属 / D-03**：`trigger()` 内 NPU 并发限流仅留 `# TODO`，不落地信号量；本模块不产生协议帧 `seq`、不做去重；每次触发新建 worker 实例（沿用 L-07）。

## ⑤ 遗留与待裁决
- `decisions.md`「待裁决登记」三条按归属**只登记、不落地、不自行裁定**：① EventCache 存废 → **d**；② 错放判定归属 → **c5**；③ `camera_status` 空接口默认值 +「连丢 5 条周期帧判离线」→ **c4/d**。`decisions.md` 原文不改。
- **须用户拍板（不选边）**：② 登记「错放业务判定归 c5（识别模块组 ack 前校验）」，与 §2.10 外部协议 docx「错放由上位机比对判定」存在口径张力；本阶段两种口径均不落地，`validateByTable` 只查表并把 `className` / `item` / `boundItem` 原样带入应答、不比较不判错放，是否由边缘侧判定留待用户拍板。
- 遗留按归属：真实 rknn / 3s 计时器、线上 JSON 键名最终映射、真实图像拼接画框（`.so`）、按采集目录实读左右图、一键停机串行 → **d / 上板**；真实磁盘与平台差异 → **d**。
- 图与 L1 冲突点：自检旁路、能力降级、`config.getValue` 直连、snake_case 回调、运行期「阶段 0~7」编号，均按 ②④ 处理，不改图、不改 L1。
