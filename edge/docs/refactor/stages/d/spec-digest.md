# d 控制、装配与端到端 spec-digest

## ① 范围与资料
- 交付 `edge/control/` 三文件（`__init__.py` 包标记、`edge_control.py`、`event_cache.py`，新建目录）+ `edge/app_init.py` + `edge/main.py`；补强单测 `edge/tests/unit/test_stage_d_control.py`。
- 语义来源：INDEX §2.2 `整体流程/整体流程.txt`（三段时序）/`整合类图代码.txt`/`整合类图.png`/`阶段0-3|4-5|5-7.png`、§2.10 协议 docx（只取线上键名）；只取事件分发、EventCache 补发/丢弃、一键停机串行、进程锁四段语义，不转录图中文字。
- 验收项 `d-1`~`d-4` 以 `stage-catalog.md` d 段为准，原措辞不改；文件命名按 L1 `整体重构方案.txt` §2 目录结构。

## ② 命名裁决（图上 snake_case 不作 API）
| 旧图标识符 | 落地标识符 | 依据 |
| --- | --- | --- |
| `route_signal` | `routeSignal` | NAMING_AUTHORITY；只识别注入的 `asyncHandlers` 字典键 |
| `on_capture_success` / `on_capture_error` | `onCaptureSuccess` / `onCaptureError` | L1 §3 `ICaptureSink` 接口表 |
| `on_recognition_result` / `on_recognition_error` | `onRecognitionResult` / `onRecognitionError` | L1 §3 `IRecognitionSink` 接口表 |
| `on_link_down` / `on_link_up` | `onLinkDown` / `onLinkUp` | L1 §3 `SignalSink` 接口表 |
| `send_frame` | 构造注入 `frameSender` 回调 | c3 未落地 `tcp_socket.py` / `sendFrame`，d 不改既有模块；由装配层用 `TcpComm` 加锁封装 |
| `startSystem` / `stopSystem` / `stopRecognition` | `startSystem` / `stopSystem`（停机回调按 L1 的 `stop`） | L1 门面职责 + glossary §3.1 |
| `SelfChecker.check_all` / `getInstance` / `getValue` | `selfCheckSystem()` 空方法 + TODO / `instance()` / `get()` | 裁决 D-01；`instance()` 由 infra 既有实现提供 |
| `set_signal_sink` | 不落地，全部构造注入 | glossary §3.1 |
- Sink 回调同名属 L1 接口契约的多态实现（与 c3 门面、既有 Fake 一致），非新标识符。
- 「阶段 0~7」是运行期业务时序编号，与实施阶段 `0~d` 无关，禁止混用。

## ③ 契约与接口
- `EdgeControl(BaseService, SignalSink, ICaptureSink, IRecognitionSink)`：`routeSignal(signal) -> bool` 按注入 `asyncHandlers` 键分发，门面不写死业务字符串（`recognize` / `version_query` 等）；未命中记 error 返回 `False`。
- 依赖：`base/`、`interfaces/i_sinks.py`、`i_logger.py`、`exceptions.py`、同模块 `event_cache.py`；`control/` 通过注入的 `ModuleWiring`（装配期填充的协作回调）指挥三个门面，不反向 import `modules/*`，由 `app_init.py` 完成真实门面的 new 与绑定 —— 解决「门面需 Sink=EdgeControl、EdgeControl 需门面」的构造循环，依赖方向仍为 `app_init → control`、`app_init → modules/*`，无跨模块反向依赖。
- Sink 回调只做轻量入队：识别 ack / 失败应答进入内部 outbox，`dispatchOutbox()` 由调用方在非回调上下文统一发送（UP 直发 / DOWN 入 `EventCache`），重活不在回调内做阻塞 IO。
- `EventCache`：`enabled` 构造注入（由上层读 `event_cache.enabled` 传入）；DOWN 期间缓存必达事件，UP 时按 `enabled` 补发或丢弃；每条带递增 `seq` 只填不用，不建 `seenSeq` / 幂等表 / 去重缓存，禁止任何基于 `seq` 的比较过滤；心跳帧由 tcp/ 内部直发、不经 EdgeControl，故不缓存。
- `app_init.py`：`AssemblyParts` 数据类承载全部构造注入，`buildSystem(parts)` 只做 new + 注入 + 返回；`main.py` 第一件事 `ProcessFileLock.acquireOrExit()`（内部 `sys.exit`），不用 `try/except` 或 `if not success:` 包业务流程；平台差异只在 `PlatformFactory`。
- 构造注入：`eventCacheEnabled` / `asyncHandlers` / `failureFrameBuilder` / `frameSender` / `logStopper` / `signalRegistrar` / `waitForExit` / 三模块全部阈值与回调，模块内零配置读取、零魔鬼数字。

## ④ 裁决落实
- **D-01**：`EdgeControl.selfCheckSystem()` 只留空方法 + TODO，不实现自检、不新增自检线程、不做能力降级；图上的自检旁路三分支不落地。
- **D-02**：`startSystem()` 只调 `initializeModules` + `startLink`（tcp 只拉重连线程，UP 后才由 c3 门面启心跳/解码），不预启采集/识别 worker；`linkState` 仍只经 c3 的 `transitionTo` 写入，d 层不读写。
- **D-03**：`EventCache` 按 `enabled` 补发/丢弃，`seq` 只递增填充、不参与去重/排序/幂等；`EventCache` 与 `EdgeControl` 均无 `seq` 比较、无 `seenSeq`、无 `PendingRequest` 重发；`stopSystem` 严格串行 `USB → RECOGNITION → TCP → LOG` 由模块常量固定顺序，不并行。

## ⑤ 遗留与待裁决
- `decisions.md`「待裁决登记」三条按归属**只登记、不落地、不自行裁定**：① EventCache 存废 → **d**（见下张力）；② 错放判定归属 → **c5**；③ `camera_status` 空接口默认值 + 连丢 5 条周期帧判离线 → **c4/d**，两组按用户指令**不混入 d**。`decisions.md` 原文不改。
- **须用户拍板（不选边）**：① EventCache 存废归 d，与 §2.10 外部协议 docx「边缘机不缓存任何业务数据、重发补发全是上位机行为」存在口径张力；本阶段按 L1 `整体重构方案.txt` §1/§5 既定的「`event_cache.enabled` 开关做」落地中性机制（`enabled` 由上层注入、模块不默认、不写死），两种业务口径均不裁定、不落地、不选边，仅登记待用户拍板。
- 图与 L1 冲突点：自检旁路 / 能力降级（D-01）、`config.getValue` 直连（改构造注入）、图上 `send_frame` 与 c3 未落地 `tcp_socket.py` 的缺口（改注入 `frameSender`，不改 c3 / 不改 L1）、「Edge 统一停心跳/启重连」与 c3 已收敛在 `TcpControlLayer.onLinkDown` 内的差异（d 层只做缓存开关，不重复宣告）、运行期「阶段 0~7」编号；均未改图、未改 L1。
- 遗留按归属：真实 `config.ini` 参数读取、真实 socket / 摄像头 / rknn 后端、真实 Windows 进程端到端（真机/网络）、线上 JSON 键名最终映射、协议 docx 两组待裁决 → **上板 / 用户裁决后**；本阶段以 Fake + 注入回调做确定性举证。
