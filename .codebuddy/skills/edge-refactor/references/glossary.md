# glossary.md — 术语与命名映射

> L3 长资料。裁决原则见 always 规则 `01_naming_authority.mdc`（NAMING_AUTHORITY）；
> 本文件提供术语定义与旧图标识符的可查映射，不改动 L1、不改动 spec 原文。

## 1. 资产分层术语

| 术语 | 定义 |
| --- | --- |
| 方案 A | 2026-11-09 用户定稿的完整重构方案，载体 `edge/docs/spec/整体重构方案.txt` |
| L1 契约层 | 不可自动修改的权威：方案 A、编码规范规则、`编码规范.mdc`、`edge/interfaces/*.py`、`edge/exceptions.py`、`edge/pyproject.toml`、`edge/tests/contract/*` |
| L2 规格图资产 | `edge/docs/spec/**` 的 mermaid / PlantUML 源码与 PNG，只提供运行期语义 |
| L3 流程配置 | `CODEBUDDY.md`、rules / skills / commands / agents、`edge/docs/spec/INDEX.md` |
| L4 状态与记忆 | `STAGE-STATE.md`、handoff、`lessons.md`、项目记忆 |
| NAMING_AUTHORITY | 标识符裁决顺序：L1 接口方法表 → 编码规范命名规则 → 其余按 camelCase 转换；旧图标识符不具裁决权 |
| 实施阶段 | `0 / a / b / c1 / c2 / c3 / c4 / c5 / d`，方案 A 的落地与验收单位 |
| 运行期业务时序阶段 | `阶段0-3 / 4-5 / 5-7` 等，旧时序图对业务流程的编号；**与实施阶段无关** |
| 阶段门禁 | 开工只读核对、收尾逐条举证、状态须用户确认才可推进的一整套约束 |
| handoff | 每阶段收尾按 `edge/docs/refactor/HANDOFF-TEMPLATE.md` 产出的移交记录 |

## 2. 核心机制术语

| 术语 | 定义 |
| --- | --- |
| 门面（Facade） | `TcpControlLayer` / `UsbController` / `RecognitionController`，模块唯一下发出口，只依赖 `interfaces/i_sinks.py` |
| Sink 回调契约 | `SignalSink` / `ICaptureSink` / `IRecognitionSink`，由 `EdgeControl` 实现；回调只做轻量分发或入队 |
| `transitionTo(state, reason, source) -> bool` | `TcpControlLayer` 唯一链路状态写入口，加锁并返回是否真正发生迁移；用于并发宣告 DOWN 去重 |
| `linkState` | `DOWN / CONNECTING / UP` 三态；见裁决 D-02，非 UP 不启其他线程 |
| `interruptibleWait(sec) -> bool` | `BaseThread` 的可打断周期等待，`False` 表示收到停止指令；禁止裸 `time.sleep` |
| `EventCache` | DOWN 期间缓存必达事件，UP 时按 `event_cache.enabled` 补发或丢弃；心跳帧不缓存；见裁决 D-03 |
| `asyncHandlers` | 注入 `TcpControlLayer` / 事件分发的字典键集合；门面不得感知具体业务字符串 |
| Fail-Fast | 配置文件缺失、`get` 无默认值且缺 key → 抛 `EdgeError(CONFIG, ...)` 并阻断启动 |
| 构造注入 | 所有超时、周期、上限、退避序列均由上层从 `config.ini` 读取后传入构造函数；模块内不 import 配置模块 |
| Fake | `tests/fakes/` 中与 `interfaces/` 契约一致的实现；新增接口须同步新增 |
| `EdgeError` / `ErrorCode` | 全项目唯一业务异常类 + 枚举（CONFIG / LINK_DOWN / FRAME_PARSE / INFERENCE_TIMEOUT / CAPTURE） |
| 三条已定裁决 | D-01 自检留空接口、D-02 非 UP 不启其他线程、D-03 去重不做且 seq 只填不用，详见 `decisions.md` |

## 3. 旧图标识符 → L1 落地标识符

原则：L1 `整体重构方案.txt` §3 的接口方法表是唯一裁决源；表中未列的按 camelCase 转换，
并满足「方法名全局不重复」「文件名全局唯一」。**不改图、不改 L1、不转录图中文字。**

### 3.1 接口与方法

| 旧图 | 落地 | 依据 |
| --- | --- | --- |
| `getValue(section, key)` | `get(section, key, default=None)` | L1 接口表 `IConfig` |
| `getLogDir` / `getMaxFileSize` / `getTcpPort` / `getReconnectBackoff` | 统一走 `get(section, key, default=None)` | L1 只保留通用 getter |
| `getInstance()` | `instance()` | 类内类变量 + 双检锁，不用单例基类 |
| `route_signal` | `routeSignal` | 只识别注入的 `asyncHandlers` 键 |
| `send_frame` / `sendHeartFrame` | `sendFrame` / `sendHeartFrame` | `sendHeartFrame` 已符合 camelCase |
| `read_frame` / `get_status` | `readFrame` / `getStatus` | L1 接口表 `ICameraDevice` |
| `load_model` | `loadModel` | L1 接口表 `IRecognitionEngine` |
| `on_capture_success` / `on_capture_error` | `onCaptureSuccess` / `onCaptureError` | L1 接口表 `ICaptureSink` |
| `on_recognition_result` / `on_recognition_error` | `onRecognitionResult` / `onRecognitionError` | L1 接口表 `IRecognitionSink` |
| `on_link_down` / `on_link_up` | `onLinkDown` / `onLinkUp` | L1 接口表 `SignalSink` |
| `on_worker_success` / `on_worker_error` / `on_worker_result` | 门面内 `onWorkerSuccess` 等 | 非 L1 接口，按 camelCase；注意方法名全局不重复 |
| `handle_capture_result` / `handle_capture_error` / `handle_frame_error` / `handle_link_down` | 走 Sink 回调，不新增 handler 方法 | 避免与 L1 回调契约平行 |
| `startCaptureTask` / `stopCapture` | `startCapture` / `stopCapture` | L1 门面职责 |
| `triggerRecognition` / `stopRecognition` | `trigger` / `stop` | L1 门面职责；`trigger` 内留 NPU 并发限流 TODO |
| `_split_frames` / `_decode_and_parse` / `_report_signal` / `_report_error` | `splitFrames` / `decodeAndParse` / `reportSignal` / `reportError` | 私有方法同样 camelCase |
| `_fetch_and_save` / `_check_roll_storage` / `_load_images` / `_crop_and_merge` / `_draw_roi` / `_build_ack` | `fetchAndSave` / `checkRollStorage` / `loadImages` / `cropAndMerge` / `drawRoi` / `buildAck` | 同上；纯函数候选留在 `recognition_utils.py` |
| `crop_and_merge` / `draw_roi` | `cropAndMerge` / `drawRoi` | 全局方法名不重复，注意与 worker 私有方法区分 |
| `_wait_backoff` / `_reset_backoff` / `_connect` / `_on_connected` / `_on_disconnect` | `waitBackoff` / `resetBackoff` / `connect` / `onConnected` / `onLinkDown` | L1 门面职责；状态写入统一 `transitionTo` |
| `notify_state_change` / `set_signal_sink` | 不落地（前者）/ 构造注入（后者） | 状态经 `transitionTo`；sink 注入不设 setter |
| `waitNextTick` / `buildFrameData` / `sendFrameAndReport` | 保持 camelCase | 已符合规范 |
| `selfCheck` / `SelfChecker.check_all` / `check_camera` | 空方法占位 + TODO，不实现 | 裁决 D-01 |

### 3.2 类与文件

| 旧图 | 落地 | 依据 |
| --- | --- | --- |
| `ConfigManager` / `FileConfig` | `IniConfigManager`（`infra/config_manager.py`） | 方案 A 目录 |
| `Socket` | `TcpSocket(ISocket)`（`modules/tcp/tcp_socket.py`） | 方案 A 目录 |
| `CaptureWorker` | `CaptureWorker`（`modules/usb/usb_capture_worker.py`） | 类名保留，文件名带模块前缀 |
| `CameraDevice` / `CameraFactory` | 同名（`modules/usb/usb_camera_device.py`） | 方案 A 目录 |
| `YoloEngine` | 同名（`modules/recognition/recognition_yolo_engine.py`） | 类内 `instance()` |
| `RecognitionUtils` | `recognition_utils.py` 中的纯函数 | 未来整体下沉 `.so` 的候选 |
| `LogExecutor` / `LogFileWriter` | `infra/log_manager.py` 内的实现 | 方案 A 不单列文件 |
| `EdgeControl`（大控制层） | `EdgeControl`（`control/edge_control.py`） | 唯一跨 ≥2 模块的协调者 |
| `SelfChecker` / `PendingRequest` | 不落地 | 裁决 D-01 / D-03 |

### 3.3 流程概念差异

| 旧图概念 | 本轮处理 | 依据 |
| --- | --- | --- |
| 「能力降级」三分支 | 不实现 | 裁决 D-01 |
| 旁路自检线程 | 不实现 | 裁决 D-01 |
| DOWN / CONNECTING 阶段的心跳、解码线程 | 不启动 | 裁决 D-02 |
| `PendingRequest` 重发 | 不实现 | 裁决 D-03 |
| `EventCache` 按 `seq` 去重 | `seq` 只填不用 | 裁决 D-03 |
| 逐级「抛异常」跨越模块边界 | 跨边界前转 `EdgeError` | 编码规范 4.4 |
| 模块内直接 `config.getValue(...)` | 参数构造注入，模块内不 import 配置 | 编码规范 4.1 / 4.3 |

## 4. 使用口径

- 遇到表中没有的旧标识符：按 §3 开头三原则裁决，并把新映射补进本文件的表（记入 handoff）。
- 图里的中文说明文字**不转录**进代码注释或文档；只提炼语义。
- 若映射会改变 L1 接口签名或新增接口 → 属于契约变更，走 diff + 用户批准，不得直接落地。
