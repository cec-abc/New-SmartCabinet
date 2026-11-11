# c4 USB 采集模块 spec-digest

## ① 范围与资料
- 交付 `edge/modules/usb/` 四文件：`__init__.py`（包标记）、`usb_controller.py`、`usb_capture_worker.py`、`usb_camera_device.py`；补强单测 `edge/tests/unit/test_stage_c4_usb.py`。
- 语义来源：INDEX §2.8 `USB_Camera/USB.txt`（类图 / 流程图 / 时序图）+ 整体流程 `阶段4-5.png`；图上文字不转录，只取并发调度、双路取图、滚动删旧、回调互不影响四段语义。
- 验收项 `c4-1`~`c4-4` 以 `stage-catalog.md` c4 段为准；文件命名按 L1 `整体重构方案.txt` §2 目录结构。

## ② 命名裁决（图上 snake_case 不作 API）
| 旧图标识符 | 落地标识符 | 依据 |
| --- | --- | --- |
| `config.getValue('usb.save_dir_1~4')` | 构造注入 `saveDirs` / `cameraPairs` | 模块内不 import 配置，上层注入 |
| `read_frame` / `get_status` | `readFrame` / `getStatus` | L1 §3 `ICameraDevice` 接口表 |
| `on_capture_success` / `on_capture_error` | `onCaptureSuccess` / `onCaptureError` | L1 §3 `ICaptureSink` 接口表 |
| `on_worker_success` / `on_worker_error` | 门面内 `onWorkerSuccess` / `onWorkerError` | 非 L1 接口，按 camelCase |
| `_fetch_and_save` / `_check_roll_storage` | `fetchAndSave` / `checkRollStorage` | 私有方法同样 camelCase |
| `startCaptureTask` / `stopCapture` | `startCapture` / `stopCapture` | L1 门面职责 |
| `selfCheck` / `check_camera` | 仅 `UsbController.selfCheck()` 空方法 + TODO | 裁决 D-01，不新增自检线程 |
| `CameraDevice` / `CameraFactory` | 同名，落 `usb_camera_device.py` | L1 §2 目录结构 + glossary §3.2 |
- 开工卡曾写 `camera_device.py`；按 L1 §2 与 glossary §3.2 落地为 **`usb_camera_device.py`**（目录对齐，非契约变更，不自行裁定）。
- 自检旁路、`SelfChecker`、能力降级三分支：不落地，不新增线程/状态机。

## ③ 契约与接口
- 依赖：`base/base_service.py` + `base/base_thread.py`、`interfaces/i_camera.py`（`ICameraDevice` / `FrameImage` / `CameraStatus`）、`i_sinks.py`（`ICaptureSink`）、`i_logger.py`、`exceptions.py`；`modules/usb/` 不 import `modules/tcp/`、`modules/recognition/`、`control/`。
- 线程全部继承 `BaseThread`；Sink 回调只做轻量转发，落盘与滚动删旧都在采集线程内完成。
- 地址寻址：Windows 配置写索引、Linux 写 `/dev/cam_left` 固定路径；差异由 `CameraFactory` 按地址形态选后端标识，全模块不出现 `sys.platform`、不引入 `cv2` 依赖，Linux 真实后端留 `NotImplementedError` + TODO，跨边界前转 `EdgeError(CAPTURE)`。
- 构造注入：`rollThreshold`（超 30% 删旧）、`usageRatio`（占用比例提供器）、`clock`（文件名时间戳）、`frameReader`（帧读取器）、4 组设备与 4 个目录；模块内零配置读取、零魔鬼数字。

## ④ 裁决落实
- **D-01**：`UsbController.selfCheck()` 只留空方法 + TODO，不执行 IO、不返回伪结果、不新增自检线程；`CaptureWorker` 不设 `checkCamera`；初始化失败仍按 Fail-Fast 抛 `EdgeError(CONFIG)`，不引入能力降级。
- **D-02**：本模块不感知 `linkState`；`init()` 只校验路径并实例化，唯一拉起点是 `startCapture()` 前置校验（已初始化且未采集中）后并发 `start()`，不在初始化阶段预热任何线程。
- **D-03**：本模块不涉及协议帧 `seq` 与补发去重；每次拉起新建 worker 实例（沿用 L-07，绕开 `BaseThread.start()` 幂等）。

## ⑤ 遗留与待裁决
- `decisions.md`「待裁决登记」三条按归属**只登记、不落地、不自行裁定**：① EventCache 存废 → **d**；② 错放判定归属 → **c5**；③ `camera_status` 空接口默认值 +「连丢 5 条周期帧判离线」→ **c4/d**（上位机侧判定，与 `linkState` 严格区分，本阶段不实现、不设默认值）。
- 真实 V4L2/CAP_DSHOW 采集、真实磁盘占用统计、按 workerId 触发识别 → 归 **c5 / d**（本阶段以 Fake + 注入提供器举证）。
- 图与 L1 冲突点：自检旁路、能力降级、`config.getValue` 直连、snake_case 回调，均按 ② ④ 处理，不改图、不改 L1。
