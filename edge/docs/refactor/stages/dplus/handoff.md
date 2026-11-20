# HANDOFF-c4plus / c5plus / dplus — 识别流重构 + USB 对焦 + 8 路 2 合 1

- **阶段**：c4plus / c5plus / dplus（阶段序列 `0 → a → b → c1 → c2 → c3 → c4 → c5 → d → c4plus → c5plus → dplus`，**共 12 个阶段**；本文件一次覆盖三阶段）
- **日期**：2026-11-14
- **状态**：**待用户确认**（本 agent 不推进状态、不代签最终 review 结论）
- **移交方**：助手（主 agent，本轮由 `memory-steward` 沉淀）
- **接收方**：上板 / 用户裁决（`stage-opener`）

## 1. 开工依据

- 用户确认记录：用户 2026-11-14 明确解除配置期禁令、批准新增 `c4plus` / `c5plus` / `dplus` 三个实施阶段（`edge/docs/refactor/stages/dplus/spec-digest.md` 抬头原文：「阶段族：`c4plus` / `c5plus` / `dplus`（用户 2026-11-14 明确解除配置期禁令，批准新增这三个阶段）」）。同日用户下达本轮沉淀指令，明确 handoff 落盘路径为 `edge/docs/refactor/stages/dplus/handoff.md`（**与 `HANDOFF-TEMPLATE.md` 约定的 `edge/docs/refactor/HANDOFF-<阶段号>.md` 命名不同**，按用户当次指令执行，差异已登记于 §7）。
- 适用权威：`CODEBUDDY.md` §2 + 规则 01~04（用户 2026-11-09/10 修订版，未改）。
- 本阶段 spec 资料：`edge/docs/refactor/stages/dplus/spec-digest.md`（本轮三阶段**共用**的签名契约与事实基线，§8 修订节优先级最高）；只读引用 L1 `edge/docs/spec/整体重构方案.txt`、L2 `edge/docs/spec/USB_Camera/USB.txt`、`edge/docs/refactor/提案-边缘机识别配置与USB对焦方案.md`、原平铺实现 `dual_crop_stitch/`（语义参考，非 L1）；上位机代码 `d:\CFDZ\smartCabinet\trunk\SmartCabinetLite`（协议硬事实来源，**只读引用、未做任何修改**）。
- 上一阶段 handoff：`edge/docs/refactor/HANDOFF-d.md`（9 个实施阶段的末阶段，2026-11-12 用户本人签字并推进 `done`）。
- 现有代码判定：引用 `references/stage-catalog.md` §0 —— 本轮三阶段是**新骨架之上的增量**，无旧代码需处置：`c4plus` 在既有 `modules/usb/` 四文件上做循环化流式采集并新增对焦与帧回调契约；`c5plus` 在既有 `modules/recognition/` 五文件上接对照表链路并新增 `infra/roi_binding_loader.py`、`modules/recognition/recognition_stitcher.py`；`dplus` 在既有 `control/` 三文件 + `app_init.py` / `main.py` 上修 4 个生产断点并新增 `control/edge_dispatch_thread.py` 与 `edge/config/` 目录。

## 2. 交付文件与必交物

### 2.1 三阶段范围与白名单（来源：`stages/dplus/spec-digest.md` §0）

| 阶段 | 白名单目录/文件 | 交付 |
| --- | --- | --- |
| `c4plus` | `modules/usb/**`、`interfaces/i_camera_focus.py`、`interfaces/i_frame_sink.py`、`tests/fakes/fake_camera_focus.py`、`tests/fakes/fake_frame_sink.py` | 循环化流式采集、对焦能力、帧回调契约 |
| `c5plus` | `modules/recognition/**`、`infra/roi_binding_loader.py`、`config/roi_binding.csv` | CSV 对照表装载、ROI 裁剪拼接、流式识别、幂等应答 |
| `dplus` | `control/**`、`app_init.py`、`main.py`、`config/config.ini`、`tests/integration/**`、`tests/contract/**`、`tests/unit/test_stage_a_contract_alignment.py` | 4 个生产断点修复、应答排空、正式配置、端到端联调 |

依赖顺序：`c4plus → c5plus → dplus`（见 `references/stage-catalog.md` §2 新增段）。

### 2.2 交付文件表

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/interfaces/i_camera_focus.py` | 新增 | §7-1、§7-2 | 对焦契约（`setAutoFocus` / `setFocusPosition` / `getFocusPosition`），**独立于 `ICameraDevice`**，不扩既有接口 |
| `edge/interfaces/i_frame_sink.py` | 新增 | §7-1、§7-2 | 帧流回调契约 `onFrameCaptured(workerId, frames, requestId)`，`frames` 用 `tuple` 避免签名随路数变化 |
| `edge/tests/fakes/fake_camera_focus.py` | 新增 | §7-2 | `ICameraFocus` 的 Fake |
| `edge/tests/fakes/fake_frame_sink.py` | 新增 | §7-2 | `IFrameSink` 的 Fake |
| `edge/modules/usb/usb_camera_device.py` | 修改 | §7-1 | 设备层实现对焦（Windows `CAP_DSHOW` / Linux `CAP_V4L2` 差异收敛在此），图像库按可选依赖函数体内导入 |
| `edge/modules/usb/usb_capture_worker.py` | 修改 | §7-3 | 循环取帧 + 帧流回调（`onFrameCaptured`）+ 落盘滚动删旧 |
| `edge/modules/usb/usb_controller.py` | 修改 | §7-1、§7-3 | `startCapture(requestId="")` 透传请求标识；`applyFixedFocus()` / `setFocusMode()`；`getCameraStatus()` 输出 8 路状态 |
| `edge/infra/roi_binding_loader.py` | 新增 | §7-1 | CSV 对照表装载器：12 列表头 → `RoiBindingRow`；文件缺失/缺列/必填为空/矩形非法/编号越界/货位重复一律 `EdgeError(CONFIG)` Fail-Fast；只用标准库 `csv` |
| `edge/modules/recognition/recognition_stitcher.py` | 新增 | §7-1、§7-3 | 复刻原平铺实现的五五分 + 垂直居中裁切与仅 x 轴偏移拼接；按四角点裁 ROI，越界抛 `EdgeError(CAPTURE)`；无图像库时降级桩并记 info |
| `edge/config/roi_binding.csv` | 新增 | §7-1 | ROI 对照表，12 列表头（含 `worker_id`），四角点坐标 |
| `edge/config/class_item_map.csv` | 新增 | §7-1 | 可选第二张表（`class_names,item_name`），不存在时按单个 `marker_id` 直映 |
| `edge/modules/recognition/recognition_utils.py` | 修改 | §7-3 | 协议四键条目组帧：`buildAckItem` / `buildRowItem` / `buildAck`；线上键名固定 `request_id` / `items` / `position` / `tool_id` / `confidence` / `alert_type` |
| `edge/modules/recognition/recognition_worker.py` | 修改 | §7-3 | 对照表链路：拼全景 → 按行裁 ROI → 区域内找标志 → 每个对照行产出一条协议条目 |
| `edge/modules/recognition/recognition_controller.py` | 修改 | §7-3 | 带流式帧触发（`trigger(workerId, requestId, frames)`）；对照表链路缺帧不触发扫描 |
| `edge/modules/recognition/recognition_yolo_engine.py` | 修改 | §7-1 | `instance()` 单例落地；推理框架（ultralytics / onnxruntime）按可选依赖函数体内导入；权重缺失记 info 并按空结果处理 |
| `edge/control/edge_dispatch_thread.py` | 新增 | §7-3 | 应答排空线程：周期调用注入的排空动作，周期等待用 `interruptibleWait` |
| `edge/control/edge_control.py` | 修改 | §7-3、§7-4、§7-6 | 跨 worker 聚合（`request_id → {workerId: items}`，收齐预期 worker 数才合并成一帧）、按 `request_id` 幂等复用上次应答、链路探针 `syncLinkState()`、排空线程启停 |
| `edge/control/event_cache.py` | 修改 | §7-1 | `logInfo` 改名 `logCacheInfo`，消除与 `infra/log_manager.py` 的同名方法（`spec-digest` §6 遗留项，本轮收敛） |
| `edge/app_init.py` | 修改 | §7-3、§7-5 | 注册 `recognize_req` 处理器 → 采集触发；周期帧改 `periodic` + `uptime_sec` + `software_version` + 8 路 `camera_status`；开机定焦；CSV 对照表装载；装配排空线程 |
| `edge/main.py` | 只读核验 | §7-1 | 入口链路（进程锁 → 装配 → 启动 → 等待 → 串行停机）保持阶段 d 形态，本轮未见需改动的 dplus 专属逻辑 |
| `edge/config/config.ini` | 新增 | §7-1、§7-5 | 正式配置：`[log]`/`[tcp]`/`[usb]`/`[recognition]`/`[event_cache]` 五节；键集与 `app_init.py` 读取口径一致 |
| `edge/tests/integration/host_protocol_checker.py` | 新增 | §7-3、§7-5 | 上位机口径复刻校验器（逐条复刻 `EdgeService::parseItems` / `parsePeriodic` / `ToolService::compareOrderWithRecognition`），作「上位机侧裁判」 |
| `edge/tests/integration/live_link_check.py` | 新增 | §7-3 | 真实上位机进程联调脚本：拉起 `QtSmartCabinet.exe`、以边缘机身份接入 9000、用上位机自身日志取证 |
| `edge/tests/integration/test_upper_host_protocol_parity.py` | 新增 | §7-3、§7-5 | 13 条协议一致性用例（含 3 秒一帧实测节拍） |
| **`edge/tests/integration/test_round3_defect_fixes.py`**（第三轮新增） | 新增 | 补充编号 D-1 ~ D-6、D-8 | 17 条第三轮缺陷修复用例：对照表缺失启动即失败、`worker_id` 越界、onnx NMS 与阈值注入、相机状态 offline 判定、丢帧计数与抽样日志、类别组合表优先 |
| **`edge/tests/integration/test_business_closure.py`**（第三轮新增） | 新增 | 补充编号 D-4、D-5、D-7 | 11 条业务闭环二次校验用例：单路失败降级出帧、聚合超时降级、第二轮请求各回各的帧、真实 TCP 栈连发两次、停机清空运行态 |
| **`edge/docs/refactor/stages/dplus/edge_class_diagram.html`**（第三轮新增） | 新增（L4 资产） | 补充编号 D-9 | 关键类图：四层子舱 + 53 节点 / 18 条跨层关键关系 + 「数据流一条线」副图 |
| **`edge/docs/refactor/stages/dplus/edge_recognition_flow.html`**（第三轮新增） | 新增（L4 资产） | 补充编号 D-9 | 识别流程图：图 2 识别主流程（30 节点 / 35 连线）+ 图 3 周期帧与开柜闸门（17 节点 / 17 连线） |
| **`edge/docs/refactor/stages/dplus/verify_diagram_screenshot.py`**（第三轮新增） | 新增（L4 资产，`.py` 在 `edge/` 树内） | 补充编号 D-9 | 图表自检 + 截图脚本：起临时 `http.server` + `playwright` msedge 通道，输出 `[SELF-CHECK]` 行 |
| **`edge/config/README.md`**（第三轮新增） | 新增 | 补充编号 D-3 | 配置说明：标志类别名口径、线程编号口径、上板须知 |
| `edge/tests/unit/test_stage_a_contract_alignment.py` | 修改 | §7-2 | 新增 2 接口 + 2 Fake 后，期望表与计数同步：签名对齐断言 `31 → 35` 对、接口文件数 `8 → 10`、Fake 文件数 `8 → 10`（`spec-digest` §8.5 指定动作） |
| `edge/tests/unit/test_stage_c5_recognition.py` | 修改（**白名单越界**） | §7-3 | 3 处断言被改写（旧断言写死了与上位机矛盾的协议形状）——详见 §6「待用户批准清单 B1」 |
| `edge/docs/refactor/stages/dplus/spec-digest.md` | 必交物（只读核验） | §7-1~§7-6、§8 | 三阶段共用的签名契约与事实基线，§8 修订节优先级最高 |
| `edge/docs/refactor/stages/dplus/test-report.md` | 必交物（只读核验） | §7-1~§7-6 | 六节齐备（① 验收项→用例对照表 / ② Fake 清单 / ③ 用例表 / ④ 可复现命令与环境 / ⑤ 汇总 / ⑥ 未覆盖项及原因） |
| `edge/docs/refactor/stages/dplus/handoff.md` | 新增（本文件） | — | 本轮移交单 |
| `edge/docs/refactor/STAGE-STATE.md` | 修改（状态与证据） | — | 新增 `c4plus` / `c5plus` / `dplus` 三行，状态一律「待用户确认（`in_progress`）」，原有 9 行未动 |
| `.codebuddy/skills/edge-refactor/references/stage-catalog.md` | 修改 | — | 登记三阶段（交付范围 / 依赖 / 验收项编号） |
| `.codebuddy/skills/edge-refactor/references/decisions.md` | 修改 | — | 新增 D-04 ~ D-11 |
| `.codebuddy/skills/edge-refactor/references/lessons.md` | 修改 | — | 追加 L-11 ~ L-15 |
| `CODEBUDDY.md` | 修改（L3 流程配置） | — | §4 阶段清单由「共 9 个阶段」更新为「共 12 个阶段」并补三行；§3 L4 表同口径同步。改动已按硬性纪律登记 |

- 必交物：`edge/docs/refactor/stages/dplus/spec-digest.md` **存在**（九节，§8 为修订节）。
- 必交物：`edge/docs/refactor/stages/dplus/test-report.md` **六节齐备**（① 对照表、② Fake 清单、③ 用例表、④ 可复现命令与运行环境、⑤ 汇总、⑥ 未覆盖项及原因；⑥ 未写「全部覆盖」）。
- 范围外文件：**已越界 1 处，待用户追认** —— `edge/tests/unit/test_stage_c5_recognition.py` 属阶段 c5 既有测试文件，不在 `c5plus` 白名单内，本轮被改写 3 处断言（详见 §6 B1）。除此之外：L1 契约层（`edge/docs/spec/**`、`.codebuddy/rules/编码规范.mdc`、`edge/interfaces/*.py`、`edge/exceptions.py`、`edge/pyproject.toml`、`edge/tests/contract/*`）**零改动**；`edge/modules/tcp/tcp_control_layer.py` 的 `onLinkDown` 未转发上游一事**未越界改 tcp 文件**（见 §6 已知限制⑤）。
- 遗留 TODO 及归属阶段：见 §6「已知限制」与「移交后续阶段的收敛项」。

### 2.3 本轮修掉的 4 个生产断点（`dplus` 负责，`spec-digest` §5 验收硬指标）

| 断点 | 位置（文件:行号） | 一句修复说明 |
| --- | --- | --- |
| `recognize_req` 路由不到采集 | `edge/app_init.py:381-382`（`buildAsyncHandlers` 注册 `recognize_req` → `handleRecognizeReq`）、`edge/app_init.py:373-375`（取 `request_id` 并触发采集）、`edge/app_init.py:410`（`captureTrigger.bind(invokeStartCapture)`）、`edge/modules/usb/usb_controller.py:137`（`startCapture(requestId: str = "")`） | 原 `asyncHandlers={}` 空字典使识别请求无人接管；现由装配层注入处理器并把请求标识透传到采集线程 |
| 应答永不出队 | `edge/control/edge_dispatch_thread.py:18-37`（新增排空线程）、`edge/app_init.py:426-429`（装配并挂到控制层）、`edge/control/edge_control.py:191-197`（`startSystem` 启动）、`edge/control/edge_control.py:201-212`（`stopSystem` 最先停） | 原 `dispatchOutbox` 生产零调用；现由周期线程按 `interruptibleWait` 排空 `_outbox`，停机时排空线程先停再串行停四模块 |
| 断链不通知上游 | `edge/modules/tcp/tcp_control_layer.py:149-154`（`onLinkDown` **未**转发上游，对照 `:158-160` `onLinkUp` 有转发）、等效自愈 `edge/control/edge_control.py:465-469`（`syncLinkState`）+ `edge/control/edge_control.py:473-474`（`dispatchOutbox` 先调探针） | 越界未改 tcp 文件，改用控制层链路探针：探针发现上游已断即按断链处理，使 `_linkUp` 置 False、应答改入事件缓存 |
| 周期帧格式错 | `edge/app_init.py:353-366`（`buildPeriodicFrame`）、`edge/app_init.py:76`（`PERIODIC_FRAME_TYPE = "periodic"`）、`edge/app_init.py:597`（注入心跳构造器）、`edge/app_init.py:344-345` → `edge/modules/usb/usb_controller.py:191-200`（8 路真实状态） | 原发 `heartbeat`；现发 `periodic` + `uptime_sec` + `software_version` + 覆盖 8 路的 `camera_status`（不硬编码 `ok`，按设备快照推导 `ok` / `offline` 两态） |

### 2.4 本轮新增文件清单（逐个：路径 + 一句职责）

- `edge/interfaces/i_camera_focus.py` —— 对焦能力契约：三方法（自动对焦开关 / 设置焦点位置 / 读取焦点位置），独立接口，不扩 `ICameraDevice`。
- `edge/interfaces/i_frame_sink.py` —— 帧流回调契约：一轮双路取帧完成的通知，`frames` 用 `tuple[bytes, ...]`。
- `edge/tests/fakes/fake_camera_focus.py` —— `ICameraFocus` 的 Fake，供单测对齐签名。
- `edge/tests/fakes/fake_frame_sink.py` —— `IFrameSink` 的 Fake，供单测对齐签名。
- `edge/infra/roi_binding_loader.py` —— CSV 对照表装载器：12 列表头 → 强类型 `RoiBindingRow`，配置类问题一律 Fail-Fast；兼作识别结果字段名常量出处。
- `edge/modules/recognition/recognition_stitcher.py` —— 拼接裁剪器：五五分 + 垂直居中裁切、仅 x 轴偏移拼接、按四角点裁 ROI；图像库缺失走降级桩。
- `edge/config/roi_binding.csv` —— ROI 对照表（12 列，含 `worker_id` 与四角点坐标），单表同时锁定「区域几何 + 货位 + 应放工具 + 内部标志」。
- `edge/config/class_item_map.csv` —— 可选类别组合表（`class_names,item_name`），把「类别集合 → 物品名」折算做成可选第二张表。
- `edge/config/config.ini` —— 正式运行配置：日志 / TCP / USB / 识别 / 事件缓存五节。
- `edge/control/edge_dispatch_thread.py` —— 应答排空线程：周期调用注入的排空动作，把待发应答真正送出。
- `edge/tests/integration/host_protocol_checker.py` —— 上位机侧裁判：逐条复刻上位机校验与判定，违规返回可读中文原因。
- `edge/tests/integration/live_link_check.py` —— 真实上位机进程联调脚本：用上位机自身日志取证边缘机帧被如何解析。
- `edge/tests/integration/test_upper_host_protocol_parity.py` —— 13 条协议一致性用例：好场景放行、坏场景拒绝、字段形状、幂等与周期节拍。
- `edge/docs/refactor/stages/dplus/handoff.md` —— 本轮移交单（本文件）。

**第三轮（业务闭环二次校验与缺陷修复）新增文件清单**：

- `edge/tests/integration/test_round3_defect_fixes.py` —— 第三轮缺陷修复验收用例（17 条）：对照表缺失 / 空表启动即失败、`worker_id` 越界、onnxruntime 分支 NMS 与阈值注入、相机状态 offline 判定、丢帧计数与抽样日志、类别组合表优先、降级帧过上位机校验、停机清空运行态。
- `edge/tests/integration/test_business_closure.py` —— 业务闭环二次校验用例（11 条）：单路相机打不开仍出协议应答、聚合超时强制降级、识别异常也有应答、第二轮请求各回各的帧、真实 TCP 栈连发两次且解码线程存活、相机状态按物理编号、配置说明文档、两条后端检测键名一致、停机清空聚合状态。
- `edge/docs/refactor/stages/dplus/edge_class_diagram.html` —— 关键类图（53 节点 / 18 条跨层关键关系）。
- `edge/docs/refactor/stages/dplus/edge_recognition_flow.html` —— 识别流程图（图 2：30 节点 / 35 连线；图 3：17 节点 / 17 连线）。
- `edge/docs/refactor/stages/dplus/verify_diagram_screenshot.py` —— 图表自检 + 截图脚本（可复跑）。
- `edge/config/README.md` —— 配置说明文档（标志类别名口径 / 线程编号口径 / 上板须知）。

## 3. 验收项逐条证据

验收项编号取自 `edge/docs/refactor/stages/dplus/spec-digest.md` §7「验收硬指标」（三阶段合并，1~6 条）。

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| §7-1 | `ruff check edge` 零告警；`mypy edge`（3.9 strict）零错误；`pytest edge/tests` 全绿 | `python -m ruff check edge` → 0 告警（上一轮实跑口径；**本轮未复跑**，本 agent 无命令执行工具）；`python -m mypy edge` → 0 错误（上一轮 79 个源文件口径；**本轮未复跑**，磁盘旁证 `.mypy_cache/3.9/edge/**` 88 个模块缓存）；`python -m pytest edge/tests -q --no-header` → **162 passed / 0 failed / 0 skipped / 1 warning（38.36 s）**（2026-11-14 用户本轮实跑口述；report ⑤ 与 §0.1） | 通过（末次全量实跑 2026-11-14 第三轮修复后） |
| §7-2 | 既有测试零修改断言：除 `test_stage_a_contract_alignment.py` 因新增接口/Fake 需同步 L1 方法表外，其余既有测试文件不得改动 | `edge/tests/unit/test_stage_a_contract_alignment.py:261`（签名对齐 `assert len(aligned) == 35`）、`:265-266`（接口文件数 10 / Fake 文件数 10）—— 属 `spec-digest` §8.5 明列的「允许新增接口 + 同步新增 Fake + 同步契约用例」；**唯一越界**：`edge/tests/unit/test_stage_c5_recognition.py` 3 处断言被改写（§6 B1，**待用户追认**）；report ⑤.1 留档 5 条在途失败全部由 c5plus 在其白名单内自行同步 | 部分通过（1 处白名单越界待追认，见 §6 B1） |
| §7-3 | 端到端联调：`items[]` 每项恰好 4 字段、`position` 不重复、`tool_id` 可空、`confidence ∈ [0,1]`、`alert_type` 取值合法 → 桩校验通过 | `test_end_to_end_recognition.py::testEndToEndAckFieldsAreProtocolCompliant`（既有）+ 本轮新增 11 条（`test_upper_host_protocol_parity.py::testHostAcceptsRealSimulatorLegalScenes`、`testHostAcceptsTc24CompatibilityFrames`、`testHostRejectsRealSimulatorBadFrames`、`testAckItemMustCarryExactlyFourKeys`、`testAckRequestIdMustBeSnakeCase`、`testCoverageAndOutboundJudgementMatchHost`、`testEdgeSourcesDoNotEmitRemovedFields`、`testEdgeAckItemsCarryNoInternalFields`、`testEdgeProductionAckMatchesHostProtocol`、`testEdgeAckFrameTopLevelKeysAreProtocolExact`、`testEdgeAckFrameHasNoInternalTopLevelKeys`）全部通过；真实上位机进程联调 6/6 取证点（report ③.4）；上位机自带 `test_edge.exe` 36 passed / 0 failed（report ③.5） | 通过 |
| §7-4 | 幂等验证：同一 `request_id` 连发 2 次，边缘机只扫描一次、回两次相同结果 | `test_end_to_end_recognition.py::testSameRequestIdIsIdempotent`（`items` 两次相同、`scanCount == 1`）；实现见 `edge/control/edge_control.py:227-232`（在途去重）、`:248-257`（复用上次应答）、`:362-364`（已应答请求不再重复出帧） | 通过 |
| §7-5 | 周期帧验证：3 秒一帧 `periodic`，`camera_status` 覆盖 8 路 | `test_end_to_end_recognition.py::testPeriodicFrameFormatAndCameraStatus`（`len(camera_status) == 8`）、`::testLinkDownFallsBackToEventCache`、`::testProductionConfigHasRequiredKeys`；新增 `test_upper_host_protocol_parity.py::testPeriodicFrameShapeAndCameraGate`、`::testPeriodicFrameIsSentEveryThreeSeconds`（实测 9 秒内发出 2 帧、间隔落在 2.7~3.9 秒） | 通过 |
| §7-6 | 重复 `recognize_req` 不导致 8 路重复扫描（计数断言） | `test_end_to_end_recognition.py::testDuplicateRequestsInFlightShareOneScan`（在途连发 3 次同一 `request_id`，`scanCount == 1`，3 帧 `items` 相同） | 通过 |

- 工具链：`ruff` **0 告警（上一轮实跑口径；本轮未复跑）** ｜ `mypy`（3.9 strict）**0 错误（上一轮 79 个源文件口径；本轮未复跑）** ｜ `pytest` **全量 162 passed / 0 failed / 0 skipped / 1 warning（38.36 s）**（2026-11-14 用户本轮实跑口述；本 agent 无命令执行工具、未复跑，来源声明见 `test-report.md` §0.1）；上轮新增一致性用例 13 条 6.13 s 全通过；真实上位机进程联调 6/6 取证点（≈33 s）；上位机自带 `test_edge.exe` `Totals: 36 passed, 0 failed, 0 skipped, 0 blacklisted, 9947ms`。覆盖率一栏为「不可测」（环境未安装 pytest-cov / coverage），如实保留、不编造。
  > **已修正（上一版的不自洽口径）**：上一版本 handoff 标注的「report ⑤ 分项相加（13 + 7 + 122 = 142）与同表「全量 132」不自洽」问题，已在 `test-report.md` ⑤ 按**测试文件**重新拆分并交叉核对为 **13 + 8 + 17 + 11 + 2 + 101 + 10 = 162 = 全量**；本 handoff 不再引用不自洽的分项数字。
- `test-report.md` 六节：**齐备**（本轮新增 §0.1「数字来源与复跑状态」、②.1「本轮第三轮新增测试替身」、③.6「本轮第三轮修复对应的验证用例（30 条）」）。
- 第 ⑥ 节未覆盖项摘要（**本轮已扩到 6 项**）：上位机 GUI 驱动的「业务层弹窗 + 落库零副作用」闭环、「在途请求 → 业务层 `compareOrderWithRecognition`」、「任一路非 ok 实际拒开柜」真实进程验证、「上位机 3 秒超时原帧重发」的上位机侧行为 —— 四项均因缺 GUI 自动化设施未驱动到该步（归属后续专项）；边缘机 `items[]` 覆盖 CSV 全部行的实机验证（需真实相机与权重）；真实上位机进程与真实边缘机程序 `edge/main.py` 的端到端对接（归属后续 c3 补齐 / 上板，因 `edge/modules/tcp/tcp_socket.py` 尚不存在）；覆盖率数字不可测；**本轮遗留 5 项**：上位机 GUI 业务层闭环（本轮新增）、真实相机对焦标定、ROI 坐标上板重标、onnxruntime 与 ultralytics 等价性现场标定、相机状态已收紧为 `ok` / `offline` 两态（2026-11-20，照度与脏污本期不设取值）、浏览器内布局自检未实跑。
- `python-code-review` 报告：**本轮未产出独立报告文件**（`python-code-review` 技能在当前工作区 `.codebuddy/skills/` 下不存在，`.codebuddy/skills/` 仅 `edge-refactor/`）；检视结论并入本 handoff 与 `lessons.md` / `code-quality-guardian` 检视经验库（见 §7）。
- 测试约定核验：report ③ 逐条给出「输入 / 预期 / 实际 / 结论」；13 条新增用例断言均为具体值或枚举（无 `assert True`、无空洞断言、无 skip/xfail 标记）；report ⑤.1 明确「未为了让它变绿而修改任何被测代码、验收项、预期值，未删用例、未加跳过标记」。**唯一需用户追认的例外**：`test_stage_c5_recognition.py` 3 处断言改写（§6 B1）。
- 步骤 4 `stage-verifier` 举证表：**会话内产物，无独立落盘文件路径（待补说明，不编造）**；本轮以 `test-report.md` ① 对照表与 ③④⑤ 的真实输出作为逐条证据来源。

### 3.1 第三轮业务闭环复核与修复（本轮 9 项，逐项：实测方法 / 真实输出 / 修复位置）

> **数字口径**：本节「真实输出」列是**用例源码里写死的具体断言值**（本 agent 逐条读盘核对）+ 2026-11-14 用户本轮实跑结论（`162 passed / 0 failed / 0 skipped`，来源声明见 `test-report.md` §0.1）；**本 agent 无命令执行工具，未能亲自复跑**。

| # | 问题 | 实测方法（用例） | 真实输出（断言口径） | 修复位置 |
| --- | --- | --- | --- | --- |
| 1 | `roiId` 永不产生 → 按区域归集塌缩成一个空分组 | `test_stage_c5_recognition.py::test_c5_3_missing_roi_id_is_not_swallowed`；真机旁证 `test_round3_defect_fixes.py::test_two_backends_output_count_within_tolerance` | `roiIdOf(无 roiId 项) is None`（不再返回空串）；`aggregateByRoi([无 roiId 项])` 抛 `EdgeError` 且 `code == CONFIG`；真机两条后端产出的检测项**都不含 `roiId` 键**（`all("roiId" not in item for item in ultraItems + onnxItems)`） | `edge/modules/recognition/recognition_utils.py:91-96`（`roiIdOf` 缺键返回 `None`）、`:123-133`（`aggregateByRoi` 缺 `roiId` 直接抛 `EdgeError(CONFIG)`） |
| 2 | 配置兜底链路实质失效（两条后端都不产 `roiId`，兜底只能产出「清一色未识别」，等于把故障伪装成正常结果） | `test_c5_3_config_fallback_path_is_unavailable`；`test_round3_defect_fixes.py::test_roi_binding_table_missing_fails_fast`、`::test_roi_binding_table_empty_fails_fast`、`::test_roi_binding_table_loaded_returns_rows` | 兜底链路：`sink.resultEvents == []`、`len(sink.errorEvents) == 1`、`exception.code == CONFIG`、日志含「兜底链路不可用」；对照表缺失 / 只有表头无数据行：`EdgeError(CONFIG)`，文案含「未装载 ROI 对照表」；装载成功：`len(rows) == 4`、`rows[0].position == "A-01-01"` | `edge/modules/recognition/recognition_worker.py:170-172`（`runConfigRecognition` 明确不可用并记 info）；`edge/app_init.py:397-410`（`loadRoiBindingRows`：装载失败或空表 → Fail-Fast）、`:696`（装配期调用，**启动即失败**，不带着空台账上线） |
| 3 | onnxruntime 分支缺 NMS（同一张图 6 条 vs 62 条，重叠框被当成多个目标） | `test_round3_defect_fixes.py::test_onnx_backend_applies_non_maximum_suppression`（桩：8 目标 → 3 条）、`::test_nms_threshold_is_injected`（阈值 0.95 → 4 条）、`::test_onnx_backend_is_marked_as_needing_field_calibration`；真机 `::test_two_backends_output_count_within_tolerance`（`weights/yolov8n.pt` vs `weights/yolov8n.onnx`，样例 `dual_crop_stitch/88.jpg`） | 桩用例：`len(items) == 3`、置信度 `[0.60, 0.80, 0.90]`、类别 `["person","person","frisbee"]`；阈值注入 `0.95` 时 `len(items) == 4`；真机：`len(ultraItems) == 6`、onnx 抑制后 `0 < len(onnxItems) <= 12`（**用户本轮实测口径：抑制前 62 条 → 抑制后 8 条**；用例断言写的是「≤ 2 × ultralytics 条数」，比实测更宽） | `edge/modules/recognition/recognition_yolo_engine.py:320-329`（`parseOnnxOutput` 先过 `applyNms`）、`:375-391`（同类别 IoU 抑制）、`:397-404`（`calculateIou`）、`:37-42`（`DEFAULT_NMS_IOU_THRESHOLD = 0.45` 与「需现场标定」标注文案）、`:81-84`（阈值构造注入）；`edge/config/config.ini:26-27`（`inference_backend = ultralytics`、`nms_iou_threshold = 0.45`）；`edge/app_init.py:700-705`（读配置并注入引擎） |
| 4 | 对照表 `worker_id` 未校验是否超过实际 worker 数（现场只有 2 对相机、表里却写第 3、4 号线程 → 该路货位永远无人上报） | `test_round3_defect_fixes.py::test_roi_worker_id_beyond_actual_worker_count_fails_fast`、`::test_loader_rejects_worker_id_out_of_base_range`；`test_business_closure.py::test_roi_worker_scope_fails_fast` | 线程数 2 + 表内第 3/4 号：`EdgeError(CONFIG)`，文案含「worker_id 超出实际采集线程数」；`worker_id=9`：`EdgeError(CONFIG)`，文案含「工作线程编号越界」 | `edge/app_init.py:382-389`（`validateRoiWorkerScope`）、`:699`（装配期按 `len(cameraPairs)` 校验，**超限启动即报错**）；`edge/infra/roi_binding_loader.py`（装载器侧保留 1~4 基础区间校验） |
| 5 | **从未打开过的摄像头曾被报成 `ok`（安全闸门误放行）** | `test_round3_defect_fixes.py::test_camera_never_opened_reports_offline`、`::test_camera_unreachable_reports_offline`、`::test_camera_status_values_are_limited`；`test_business_closure.py::test_camera_status_follows_physical_order`、`::test_periodic_frame_camera_status_matches_usb` | 从未打开：`["offline","offline"]`；探测不到设备：`device.open()` 抛 `EdgeError(CAPTURE)` 且状态仍 `["offline","offline"]`；取值集合 ⊆ `{ok, offline}`（2026-11-20 起 `comm_error` 归并到 `offline`）；8 路按**物理编号**排 `["CAM1".."CAM8"]`，状态 `["ok","ok","offline","offline","ok","ok","ok","ok"]` | `edge/modules/usb/usb_controller.py` 的 `_resolveCameraStatus`（无设备 → `offline`；`commOk` 为假 → **`offline`**；`everOpened` 为假 → **`offline`**；否则 `ok`） |
| 6 | 识别忙时丢帧无可观测性（上一轮未结束，本轮帧被静默丢弃，无人知道） | `test_round3_defect_fixes.py::test_dropped_frames_are_counted_and_logged_by_threshold` | 首轮 `trigger(...) is True`；随后 12 次全部 `is False`；`getDroppedFrameCount() == 12`；丢弃日志恰好 **1** 条且文案含「累计 10 次」（每 10 次抽样 1 条，不逐帧刷屏） | `edge/modules/recognition/recognition_controller.py:98-101`（丢弃计数 + 抽样间隔）、`:154-159`（忙时计数并抽样记日志）、`:204-218`（只读 getter `getDroppedFrameCount()` 与 `logDroppedFrames`） |
| 7 | 上一轮三处降级修复**已核实有效**（逐行复核，不只是「有代码」） | 聚合降级出帧：`test_degraded_frames_match_host_protocol`、`test_aggregation_timeout_forces_degraded_ack`；ROI 越界逐行降级：`test_worker_failure_still_yields_protocol_ack`；识别异常也有应答：`test_recognition_error_still_answers_request`、`test_recognition_error_degraded_items_match_host_protocol` | 降级帧过上位机校验：`check_ack(...).hostAccepts is True` 且 `protocolClean is True`，覆盖 `A-01-01` 通过；超时降级：出网 1 帧、4 个货位齐全、全部 `tool_id == ""` / `alert_type == "unknown"`；单路失败：坏路 `tool_id == ""` / `alert_type == "unknown"` / `confidence == 0.0`，好路 `tool_id == "C01-T0007"` / `alert_type == "none"` | `edge/control/edge_control.py`（聚合超时强制降级 + `degradedItemsProvider`）、`edge/app_init.py:364-374`（按对照表补齐未识别条目）、`edge/modules/recognition/recognition_worker.py:132-137`（拼接失败整幅按未识别）、`:147-160`（单行失败只降级该行）、`:108-119`（顶层异常转失败回调，不外抛） |
| 8 | 两张图交付（类图 + 识别流程图，含可复跑自检脚本） | 见 **§3.2** | 类图 53 节点 / 18 条跨层关系；图 2 30 节点 / 35 连线；图 3 当时 17 节点 / 17 连线（2026-11-20 两态收口删去 low_light/dirty/comm_error 三个状态值节点后为 14 / 13） | `edge/docs/refactor/stages/dplus/edge_class_diagram.html`、`edge_recognition_flow.html`、`verify_diagram_screenshot.py` |
| 9 | 画图过程中发现并纠正了两处「图 ≠ 代码」（**图不是证据，是产物**） | 逐条比对图上的依赖箭头与真实代码调用链 | ① 图上画的 `YoloEngine → RoiBindingLoader` 依赖**不成立**（两者无调用关系，对照表由装配层装载后注入）；② 图上写的 `UsbController.startCapture(request_id)` **不是实际链路**（实际链路是 `app_init` 的 `CaptureTrigger` → `UsbController.beginScan` → `CaptureWorker`，`request_id` 经 `IFrameSink.onFrameCaptured(workerId, frames, requestId)` 透传） | 两张图均已按真实代码重画（类图 `ARROWS` 18 条、流程图 `F2` 步骤含 M5「拉起 4 组采集」与 M6「双路取帧 → `onFrameCaptured`」） |

### 3.2 图表交付（本轮新增资产）

| 产物 | 路径 | 讲什么 | 怎么打开 | 怎么复跑自检 |
| --- | --- | --- | --- | --- |
| 关键类图 | `edge/docs/refactor/stages/dplus/edge_class_diagram.html` | 边缘机这套代码**怎么把「上位机的一条识别指令」变成「一帧全柜实况」**：入口层 / 控制层 / 模块层 / 基础层四层子舱归属 + **18 条跨层关键关系**（线上标接口名）+ 「数据流一条线」副图（① 对照表 CSV → ② 装载 → ③ 注入 → ④ 逐行出 items → ⑤ 控制层聚合 → ⑥ 回包上位机）。**53 个节点** | 双击用浏览器打开（单文件、零外部依赖；`file://` 直接打开即可看图，自检脚本另走 `http://` 只因截图需要） | `cd edge/docs/refactor/stages/dplus` → `python verify_diagram_screenshot.py docs/refactor/stages/dplus/edge_class_diagram.html class_diagram.png` |
| 识别流程图（图 2 + 图 3） | `edge/docs/refactor/stages/dplus/edge_recognition_flow.html` | 图 2 = **识别主流程**（M1~M18 + 三档结果分支 + 幂等分支 + 降级旁路 + 断链缓存旁路 + 待上板依赖）：**30 节点 / 35 连线**；图 3 = **周期帧与开柜闸门**（G1~G10 + 8 路状态取值集合）：**17 节点 / 17 连线** | 同上 | `python verify_diagram_screenshot.py docs/refactor/stages/dplus/edge_recognition_flow.html recognition_flow.png` |
| 自检脚本 | `edge/docs/refactor/stages/dplus/verify_diagram_screenshot.py` | 起临时 `http.server`（`file://` 会被浏览器拦）+ `playwright` 的 msedge 通道截图，并打印页面内置「布局自检」结果（同层重叠检测 / 文字超宽检测） | — | `python verify_diagram_screenshot.py <html 相对路径> <输出 png> [视口宽] [视口高] [选择器\|all] [裁剪 x,y,w,h]`；截图默认落在脚本同目录 |

- **自检口径**：脚本会打印一行 `[SELF-CHECK] ...`，内容即页面内置自检结论（类图：53 节点 / 18 条跨层关系；图 2：30 节点 / 35 连线；图 3：17 节点 / 17 连线）。**本 agent 无命令执行工具 / 无浏览器环境，未实跑**，仅在磁盘核对了节点与连线条数与页面自检文案一致。
- **图与代码的一致性纪律**：本轮出图过程中发现两处「图 ≠ 代码」（见 §3.1 第 9 条），已按真实代码重画。**图不是验收证据**，验收证据仍以 `test-report.md` 的用例与实跑输出为准。
- **资产归属**：两张 HTML 与自检脚本属 **L4 资产**（`edge/docs/refactor/**`），不涉及 L1 契约层；但 `.py` 落在 `edge/` 树内，已按 §6.2 A6 登记待用户确认。

## 4. L1 契约层

- `contract-guard` 基线结论：**零自动变更**（本轮未触碰 L1 任何文件）。
- 契约变更 diff：**无**。L1 清单（`edge/docs/spec/**`、`.codebuddy/rules/编码规范.mdc`、`edge/interfaces/*.py`、`edge/exceptions.py`、`edge/pyproject.toml`、`edge/tests/contract/*`）全部未改；`edge/pyproject.toml` 的 `dependencies = []` 保持原样（`edge/pyproject.toml:6`）。
- 批准状态：**等待用户批准（未落地）** —— 见 §6「待用户批准清单」A1~A4（4 项契约增量）与 B1（1 项白名单追认）。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— **已遵守**。本轮所有疑似契约增量的内容（新增 `ICameraFocus` / `IFrameSink`、新增 `edge/config/` 目录、L1 逐文件职责表扩容 3 项）**均未落地到 L1**，只以待批准项登记在本 handoff。
- 已发生的「接口层新增」事实说明（供用户判定 A1/A2）：`edge/interfaces/i_camera_focus.py` 与 `edge/interfaces/i_frame_sink.py` 两个文件**已存在于工作区**（`spec-digest` §2.1/§2.2 已把它们写进三阶段共用契约，且 `test_stage_a_contract_alignment.py` 已把接口数与签名对齐数同步为 10 / 35）。**这两个文件位于 L1 契约层清单内**，因此本轮把它们作为「已产生的契约增量」显式提交用户追认，而非默默留存。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守 | `EdgeControl.selfCheckSystem()`、`UsbController.selfCheck()`、`RecognitionController.selfCheckRecognition()` 均只留空方法 + TODO；不实现、不新增自检线程、不做能力降级 |
| D-02 非 UP 不启其他线程 | 已遵守 | `startSystem()` 仍只 `init()` + 启链路 + 启排空线程；采集/识别 worker 由上位机 `recognize_req` 触发，不预启；`linkState` 仍只经 `transitionTo` 写入 |
| D-03 去重不做、seq 只填不用 | 已遵守 | `EventCache` 仍只按 `enabled` 补发/丢弃，`seq` 只递增填充、不参与任何判断；**幂等另按 `request_id` 实现**（与 `seq` 无关，不构成「按 seq 去重」） |

### 5.1 本轮新增设计裁决落实（逐条，含依据来源）

| 编号 | 裁决 | 落实情况 | 依据来源 |
| --- | --- | --- | --- |
| ① | 对照关系表落 **CSV**（不用 MySQL、不用 JSON） | 已落实：`edge/config/roi_binding.csv` + `edge/infra/roi_binding_loader.py` 只用标准库 `csv`；旧实现把三份 JSON 塞进 ini 的做法已弃用 | 理由：零依赖、Excel 可直接编辑、Git 行级 diff、RK3588 零负担；来源 `spec-digest` §3 / §4（`[recognition] roi_binding_csv` 取代 ini 内三段 JSON）+ 用户 2026-11-14 指令 |
| ② | ROI 坐标采用**四角点 `[x1,y1,x2,y2]`**，参照系 = 拼接全景；早期「宽高」形式作废 | 已落实：`RoiBindingRow` 字段为 `rectX1/rectY1/rectX2/rectY2`，`Cv2FrameStitcher.crop` 按四角点裁剪并做越界校验 | `dual_crop_stitch/src/vision_core.py:287-288` 原文：「格式 `{"roi_id": (x1, y1, x2, y2)}`；坐标相对于拼接后的全景画布；单位: 像素」+ `spec-digest` §8.1 |
| ③ | CSV **12 列表头**（含 `worker_id`，用于把 ROI 分配到 4 个并发 worker） | 已落实：表头逐字为 `roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,confidence,rect_x1,rect_y1,rect_x2,rect_y2`；`worker_id` 必填且只接受 1~4（`roi_binding_loader.py:221-235`） | `spec-digest` §8.1（原文：「`worker_id`（**必填**，1~4）……**缺这列无法把 ROI 分配到 4 个并发 worker**，是早期设计的遗漏」） |
| ④ | `recognize_ack` 顶层键 `request_id` 是 **snake_case**（协议字段名），`requestId` 只能作内部变量名 | 已落实：`buildAck` 产出 `{"type","request_id","items"}`；`EdgeControl.buildAggregatedFrame` 显式 `pop("workerId")` / `pop("requestId")`；`requestId` 仅作内部参数名 | 上位机 `EdgeService` 只读 `request_id`；真实上位机进程取证（report ③.4 第 4/5 行）：snake_case 帧编号被回带、驼峰 `requestId` 帧编号为空被丢弃 |
| ⑤ | `items[]` 每项**恰好 4 键** `position` / `tool_id` / `confidence` / `alert_type`；禁止 `present` / `alert_level` / `class_id` / `tool_name` | 已落实：`buildAckItem` 只造 4 键；新增用例 `testEdgeSourcesDoNotEmitRemovedFields` 扫描 `modules/recognition/` 与 `control/` 全部 `.py` 的带引号键名字面量，断言 `findings == []` | 上位机 `CommTypes.h:37-42` + `spec-digest` §1.5 / §8.3.3 |
| ⑥ | 一次 `recognize_req` **恰好回一帧**，4 个 worker 结果在控制层聚合成一帧 | 已落实：`EdgeControl.collectAggregatedFrames` 维护 `request_id → {workerId: items}`，收齐构造注入的 `expectedWorkerCount`（= `len(cameraPairs)`）才合并出一帧入 `_outbox`；识别模块只产本 worker 的条目、不做跨 worker 聚合 | `spec-digest` §8.3.1 + §8.4 |
| ⑦ | **幂等**：上位机 3 秒超时原帧重发同一 `request_id`（最多 3 次），边缘机按 `request_id` 去重 + 复用上次 ack | 已落实：在途登记 `markRequestPending`、完成后 `reuseCompletedAck` 复用上次应答、已应答请求不再重复出帧；同一 `request_id` 只扫描一次 | 上位机 `EdgeService.cpp:480-491`（3 秒无回应即原帧原样重发同一 `request_id`，最多 3 次）+ `spec-digest` §1.10 |
| ⑧ | 对焦用**独立新接口 `ICameraFocus`**（不扩 `ICameraDevice`），平台差异收敛在设备层 | 已落实：`edge/interfaces/i_camera_focus.py` 独立存在；`CameraDevice` 同时实现 `ICameraDevice` 与 `ICameraFocus`；Windows `CAP_DSHOW` / Linux `CAP_V4L2` 差异只在 `usb_camera_device.py`；主流程无 `sys.platform` | `spec-digest` §2.1（原文：「**不得**扩展 `ICameraDevice`（会打破 `test_stage_a_contract_alignment.py` 的 31 对 Fake/接口签名对齐断言与 L1 §3 方法表断言）」）；实测签名对齐断言已由 31 增至 35 对（`test_stage_a_contract_alignment.py:261`） |
| ⑨ | 图像库 / 推理框架作**可选依赖**（函数体内 import），`edge/pyproject.toml` 属 L1 **不得改**，依赖清单保持 `dependencies = []` | 已落实：`recognition_stitcher.py:90-99`、`usb_camera_device.py:144-150`、`recognition_yolo_engine.py:131-142` 全部在函数体内 `import`；缺库时抛 `EdgeError(CAPTURE/CONFIG)` 或走降级桩；`edge/pyproject.toml:6` 仍为 `dependencies = []` | `spec-digest` §2.5 + §8.5 |
| ⑩ | `ErrorCode` **不得新增成员**（既有测试断言恰 5 个），新增异常一律复用 `CONFIG` / `CAPTURE` | 已遵守：`edge/exceptions.py:8-18` 仍恰 5 个成员（`CONFIG`/`LINK_DOWN`/`FRAME_PARSE`/`INFERENCE_TIMEOUT`/`CAPTURE`），本轮全部新增异常走 `CONFIG` 或 `CAPTURE` | `spec-digest` §6 + `edge/tests/unit/test_stage0_error_and_lock_guards.py:19-27`（`assert [code.name for code in ErrorCode] == [...]` 恰 5 项） |

> 上述 10 条已按用户 2026-11-14 指令登记为 `references/decisions.md` 的 **D-04 ~ D-11**（D-11 为「既有测试若写死了与上位机矛盾的协议形状，可经用户追认后改写」，当前状态：**待追认**）。

### 5.2 第三轮新增裁决落实（D-12 ~ D-16，逐条含依据来源）

| 编号 | 裁决 | 落实情况 | 依据来源 |
| --- | --- | --- | --- |
| **D-12** | 生产**必须装载 ROI 对照表**，缺失即启动失败；**废弃配置兜底链路** | 已落实：`app_init.py:397-410` 装载失败 / 空表 → `EdgeError(CONFIG)`；`:696` 装配期调用；`recognition_worker.py:170-172` 兜底链路判不可用；`recognition_utils.py:91-96,123-133` 缺 `roiId` 显式判错 | 用户 2026-11-14 第三轮指令 + 真机实测「两条后端都不产 `roiId`」+ `test-report.md` ③.6.1 / ③.6.2 |
| **D-13** | 推理后端**默认固定 ultralytics**；onnxruntime 分支补 NMS，**需现场标定后方可启用** | 已落实：`recognition_yolo_engine.py:320-329`（先过 `applyNms`）、`:375-391`、`:397-404`、`:37-42`（阈值默认 `0.45` + 标注文案）、`:81-84`（阈值构造注入）；`config.ini:26-27`（`inference_backend` / `nms_iou_threshold`）；`app_init.py:700-705` 读配置注入 | 用户 2026-11-14 第三轮指令 + `test-report.md` ③.6.4 |
| **D-14** | 对照表 `worker_id` **不得超过实际采集线程数**，装配期校验 | 已落实：`app_init.py:382-389`（`validateRoiWorkerScope`）、`:699`（按 `len(cameraPairs)` 校验）；装载器侧保留 1~4 基础区间 | 用户 2026-11-14 第三轮指令 + `test-report.md` ③.6.3 |
| **D-15** | **从未成功打开**的设备一律 `offline`（不得报 `ok`） | 已落实：`usb_controller.py` 的 `_resolveCameraStatus`（设备缺失 / `commOk` 假（2026-11-20 归并） / `everOpened` 假 → `offline`；否则 `ok`） | 用户 2026-11-14 第三轮指令 + 上位机开柜闸门语义 + `test-report.md` ③.6.5 |
| **D-16** | 识别背压需有**丢弃计数 + 抽样日志** | 已落实：`recognition_controller.py:98-101`（计数 + 抽样间隔）、`:154-159`（忙时计数并抽样记日志）、`:204-218`（只读 getter） | 用户 2026-11-14 第三轮指令 + `test-report.md` ③.6.6 |

> 上述 5 条已按用户 2026-11-14 第三轮指令登记为 `references/decisions.md` 的 **D-12 ~ D-16**；代码与用例**均已落地**，但**阶段状态仍为 `in_progress`（待用户确认）**，最终 review 结论只由用户本人签字。

## 6. 遗留与裁决

### 6.1 已知限制（如实记录，不美化）

1. **标志漏检会导致「出库取出正确」误判**。上位机判据是「该货位 `tool_id` 为空串」（上位机不认 `present`），因此「放了工具但标志没识别出来」会被上位机判为取出正确。`alert_type=unknown` 保留信息，但上位机业务层不消费它。缓解手段 = 现场标定每行 `confidence` 下限（降低漏检）。依据：`spec-digest` §8.3.7。
2. **模型权重未部署**（`./models/yolo.pt` 不存在）。线上识别当前只能给「未命中」：引擎记 info 后按空结果处理（`recognition_yolo_engine.py:116-118`、`158-160`），**不伪造命中**。
3. **ROI 四角点样例按 640×480 全景铺满四象限**（`edge/config/roi_binding.csv` 4 行样例坐标为 `(0,0)-(320,240)`、`(320,0)-(640,240)`、`(0,240)-(320,480)`、`(320,240)-(640,480)`）。**上板换真相机后必须按实际全景尺寸重标**，否则抛 `EdgeError(CAPTURE, "ROI 超出拼接图范围: ...")`（`recognition_stitcher.py:78-83`）。
4. **开机定焦因无相机 / 无 opencv 未生效**（记 info 不中断启动，`app_init.py:242-250`）。真实生效依赖上板后的相机后端与图像库。
5. **`TcpControlLayer.onLinkDown` 未转发上游**（`edge/modules/tcp/tcp_control_layer.py:149-154`）。本轮**未越界改 tcp 文件**（改用控制层链路探针 `syncLinkState` 等效自愈）；**最小 diff 留在本 handoff 待批准**（见 A4 之外的附加说明：若用户批准，可在 `onLinkDown` 内补 `self._upstreamSink.onLinkDown(reason, source)` 一行转发）。
6. **生产 socket 仍是 `SocketSkeleton`**（`edge/modules/tcp/tcp_socket.py` 不存在，`app_init.py:507-532`）。归属后续 c3 补齐 / 上板阶段；本轮联调用的是测试目录内的真实 TCP 套接字。
7. **`edge/tests/unit/test_stage_c5_recognition.py` 被改写 3 处断言**（旧断言写死了与上位机矛盾的 `requestId` / `roiId` 等协议形状）—— **属白名单越界，待用户追认**（§6.2 B1）。取证结论：用例名一条未删、无 skip / xfail、断言更具体（当前文件实测：`:135` `assert ack["request_id"] == "req-1"`；`:263-264` `assert ack["request_id"] == "req-3"` + `assert set(ack.keys()) == {"type", "request_id", "items"}`；`:290` `validateByTable(groups, CLASS_ITEM_MAP, ROI_BIND_MAP, ROI_CONFIG)` 第四参补齐；`:293-296` `buildAck` 期望值改用 `request_id`）。
8. **配置兜底链路已明确废弃（生产必须装载 ROI 对照表）**。第三轮已实测两条推理后端（ultralytics / onnxruntime）产出的检测结果**只有 `className` 与 `confidence` 两个键、没有 `roiId`**（用例 `test_two_backends_output_count_within_tolerance` 的真机断言 `all("roiId" not in item for item in ultraItems + onnxItems)`），按区域归集必然塌缩成一个空组，查表只能得到清一色的未识别条目 —— 等于把故障伪装成正常结果。故：`runConfigRecognition` 直接判不可用（记 info + 抛 `EdgeError(CONFIG)`），`app_init` **未装载到对照表就启动即失败**。**生产部署必须随包提供 `edge/config/roi_binding.csv`**，缺表即起不来（这是有意的 Fail-Fast，不是缺陷）。
9. **onnxruntime 后端虽补了 NMS，但未与 ultralytics 等价标定，默认固定 ultralytics**。第三轮给 onnx 分支补了同类别非极大值抑制（抑制前 62 条 → 抑制后与 ultralytics 同量级），但两条后端在**置信度口径、类别映射、预处理**上仍可能不同，且 `low_light` / `dirty` 等判定依赖图像分析。故 `[recognition] inference_backend` **默认固定 `ultralytics`**，onnx 分支在引擎内显式标注「未与 ultralytics 对齐, 需现场标定」；**现场标定完成前不得启用 onnxruntime 分支**（换后端等于换结论）。
10. **相机状态只有 `ok` / `offline` 两态**（2026-11-20 收口）。照度不足、镜头脏污需要图像分析，本期不设取值；取图失败、从未成功打开、设备缺失一律归 `offline`。上位机开柜闸门按非 `ok` 判，`offline` 即拒绝开柜，不会放行一个没有图像的相机。

### 6.2 待用户批准清单

| 编号 | 事项 | 类型 | 现状 |
| --- | --- | --- | --- |
| A1 | 新增接口 `ICameraFocus`（`edge/interfaces/i_camera_focus.py`） | 契约增量（接口层） | 文件已存在于工作区；**待用户追认** |
| A2 | 新增接口 `IFrameSink`（`edge/interfaces/i_frame_sink.py`） | 契约增量（接口层） | 文件已存在于工作区；**待用户追认** |
| A3 | 新增目录 `edge/config/`（`config.ini` / `roi_binding.csv` / `class_item_map.csv` / **本轮新增 `README.md`**；`config.ini` **本轮新增两键** `[recognition] inference_backend` 与 `[recognition] nms_iou_threshold`） | 契约增量（目录结构） | 目录已存在于工作区；**待用户追认** |
| A4 | L1 逐文件职责表扩容 3 项（`infra/roi_binding_loader.py`、`modules/recognition/recognition_stitcher.py`、`control/edge_dispatch_thread.py`） | 契约增量（`整体重构方案.txt` §2/§3） | **未落地**，仅登记 |
| **A5** | **本轮第三轮新增的公开方法 / 只读观测口**（不在 L1 `edge/interfaces/**` 清单内，但属「公开 API 面」变更）：`RecognitionController.getDroppedFrameCount()`（丢帧计数只读 getter）、`YoloEngine.getBackend()` / `setBackend()` / `getNmsIouThreshold()` / `setNmsIouThreshold()`、`app_init.loadRoiBindingRows()` / `app_init.validateRoiWorkerScope()`（模块级函数）、`CameraDevice` 状态快照新增 `everOpened` 字段 | 公开 API 面增量（非 L1 接口层） | 代码已落地；**待用户确认是否需要同步进 L1 逐文件职责表 / 方法表** |
| **A6** | **本轮第三轮新增的文件**：`edge/tests/integration/test_round3_defect_fixes.py`、`edge/tests/integration/test_business_closure.py`（测试文件，在 `dplus` 白名单 `tests/integration/**` 内）、`edge/docs/refactor/stages/dplus/edge_class_diagram.html`、`edge_recognition_flow.html`（L4 资产）、`edge/docs/refactor/stages/dplus/verify_diagram_screenshot.py`（**.py 落在 `edge/` 树内的 L4 目录**，需确认是否豁免「`edge/` 下 `.py` 属生产代码」的约定）、`edge/config/README.md`（配置说明文档） | 新增文件登记（目录职责 / `.py` 位置口径） | 文件已存在于工作区；**待用户确认** |
| B1 | 追认 `edge/tests/unit/test_stage_c5_recognition.py` 的白名单越界（3 处断言改写） | 白名单追认 | **待追认**（详见 §6.1 第 7 条） |
| **B2** | 追认 `edge/tests/unit/test_stage_c5_recognition.py` 的**追加**（本轮第三轮在该文件新增 2 条缺陷用例：`:171-180` `test_c5_3_missing_roi_id_is_not_swallowed`、`:183-205` `test_c5_3_config_fallback_path_is_unavailable`）—— 该文件仍属阶段 c5 既有测试文件，不在 `dplus` 白名单内 | 白名单追认 | **待追认**（只**追加**用例，既有断言零改动；未删用例、未加 skip / xfail） |

- 图与 L1 的冲突点：L1 §3 逐文件职责表未含本轮 3 个新文件（A4）；L1 接口方法表未含 A1/A2 两个新接口；L1 §2 目录结构未含 `edge/config/`（A3）；本轮第三轮新增的公开方法（A5）与新增文件（A6）同样未进 L1。**未改图、未改 L1**，全部以待批准项登记。
- 阻塞原因与解除条件：**无阻塞**（本轮三阶段实现与证据齐备，状态停在「待用户确认」）；解除条件 = 用户本人 review 并签字 + 对 A1~A6 / B1~B2 逐项拍板。
- 移交后续阶段的收敛项（逐条 + 归属阶段）：
  - **生产部署必须随包提供 `edge/config/roi_binding.csv`**（缺表即启动失败，见 §6.1 第 8 条）→ **上板 / 部署**。
  - **onnxruntime 与 ultralytics 的逐框等价性现场标定**（标定前固定 ultralytics）→ **上板**。
  - 照度不足、镜头脏污的图像分析判定（若要新增状态取值，须先走契约 diff + 用户批准）→ **上板**。
  - 真实相机后端（Windows `CAP_DSHOW` 真实取帧 / Linux `CAP_V4L2`）→ **上板**。
  - 对焦标定与 `focus_position` 实测取值 → **上板**。
  - ROI 四角点按实际全景尺寸重标 → **上板**。
  - 模型权重部署（`./models/yolo.pt`）与 `marker_id` 类别名现场标定 → **上板**。
  - 生产 socket 实现（`edge/modules/tcp/tcp_socket.py`）→ **后续 c3 补齐 / 上板**。
  - `TcpControlLayer.onLinkDown` 上游转发最小 diff → **待用户批准后落地**。
  - 上位机 GUI 自动化（业务层闭环、拒开柜真实进程验证、超时重发）→ **后续专项**。
  - `TcpDecodeThread` 阻塞 `recv` 不可打断（`spec-digest` §6 遗留）→ **后续专项**。

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：新增 `c4plus` / `c5plus` / `dplus` 三行，状态一律 **`in_progress`（待用户确认）**、证据栏填 `edge/docs/refactor/stages/dplus/test-report.md` 相对路径 + ruff / mypy / pytest 真实数字、更新时间 **2026-11-14**；原有 9 行状态未动；§3 补三阶段合并验收项复选框（全部保持 `[ ]`）；§5 追加 2026-11-14 门禁记录行。
- `references/lessons.md` 条目号：**L-11 ~ L-15**（协议字段名以上位机代码为准 / 上位机原帧重发须按 `request_id` 幂等 / 新增能力优先新建独立接口 / 可选依赖用函数体内 import / CSV 配置用四角点且带 `worker_id`）；**本轮第三轮追加 L-16 ~ L-19**（协议字段名与结构以上位机代码为准且要用**真实上位机进程**取证 / 检测引擎不一定产 ROI 归属字段 / 同一后端不同实现必须做 NMS 等价处理 / 安全闸门用的状态必须区分「从未打开」与「打开后异常」）。
- 项目记忆：topic 文件 `edge_protocol_contract.md`（上位机协议硬事实）+ `edge_refactor_c4plus_dplus.md`（本轮阶段与裁决）+ **本轮新增 `edge_inference_backend.md`（推理后端口径）**；`MEMORY.md` 三行索引（每行 ≤150 字符）。
- `python-code-review` 经验库：**该技能在当前工作区不存在**（`.codebuddy/skills/` 下只有 `edge-refactor/`），故按用户指令把可复用结论同步到**工作区外的 `code-quality-guardian` 检视经验库**（`C:\Users\25007\.codebuddy\skills\code-quality-guardian\references\known-pitfalls.md`，「六、协议 / 跨端契约类」第 29~34 条）；**本轮第三轮追加第 35~38 条**；该目录不纳入 git。
- `references/decisions.md`：**新增 D-04 ~ D-11**（来源：用户 2026-11-14 指令 / 上位机代码行号 / `dual_crop_stitch/src/vision_core.py:287-288`），D-11 当前状态为「待追认」；**本轮第三轮追加 D-12 ~ D-16**（生产必须装载 ROI 对照表 / 推理后端默认固定 ultralytics / 对照表 `worker_id` 不得超限 / 从未打开的相机一律 offline / 识别背压需有丢弃计数与抽样日志）。
- **L3 流程配置改动登记**（按硬性纪律登记）：`CODEBUDDY.md` §4 阶段清单由「共 9 个阶段」更新为「**共 12 个阶段**」并补 `c4plus` / `c5plus` / `dplus` 三行；同文件 §1 的实施阶段序列与 §3 的 L4 资产表内「`STAGE-STATE.md` 9 个阶段状态与验收项」同口径同步为 12（避免同一文件内自相矛盾）。**未改** `SKILL.md` §1/§7 的「共 9 个阶段」表述（不在本轮授权范围），已在下一阶段开工提示中登记待同步。
- **本文件路径偏离登记**：用户当次指令指定 `edge/docs/refactor/stages/dplus/handoff.md`，与 `HANDOFF-TEMPLATE.md` 的 `edge/docs/refactor/HANDOFF-<阶段号>.md` 命名约定不同；按用户当次指令执行，`STAGE-STATE.md` 与项目记忆均指向本路径。

## 8. 下阶段开工提示

- 下一阶段：**上板接线**（无新增实施阶段编号；后续工作是上板集成与用户裁决后的收敛）。建议顺序见下。
- 必读：本 handoff（`edge/docs/refactor/stages/dplus/handoff.md`）、`edge/docs/refactor/stages/dplus/spec-digest.md`（尤其 §7 验收硬指标与 §8 修订节）、`edge/docs/refactor/stages/dplus/test-report.md`（尤其 §0.1 数字来源、③.6 第三轮用例、⑥ 未覆盖项）、`references/decisions.md` D-04 ~ D-16、`references/lessons.md` L-11 ~ L-19、`references/stage-catalog.md` 新增三阶段段、`edge/docs/refactor/HANDOFF-d.md`；两张图见 `edge/docs/refactor/stages/dplus/edge_class_diagram.html` 与 `edge_recognition_flow.html`。
- 特别注意：
  - **上板接线清单**：① 真实相机（Windows `CAP_DSHOW` / Linux `CAP_V4L2` 真实取帧，替掉 `placeholderFrame`）；② 对焦标定（`focus_mode` / `focus_position` 实测取值，替掉开机定焦记 info 的现状）；③ ROI 按实际全景尺寸**重标**四角点；④ 部署模型权重 `./models/yolo.pt` 并现场标定 `marker_id`；⑤ 生产 socket（`edge/modules/tcp/tcp_socket.py`，替掉 `SocketSkeleton`）；⑥ **部署包必须带 `edge/config/roi_binding.csv`（缺表即启动失败）**；⑦ **onnxruntime 与 ultralytics 的逐框等价性现场标定（标定前固定 ultralytics）**。
  - `SocketSkeleton` / `placeholderFrame(s)` / `directInference` / `zeroUsage` / `defaultFailureFrame` 均为骨架占位并标 TODO，上板前须接真实后端。
  - `EdgeControl` 不得写死业务字符串；新增模块时须同步补 `stopActions` 与 `STOP_ORDER` 顺序。
  - 协议线上键名**一律 snake_case**（`request_id` / `items` / `position` / `tool_id` / `confidence` / `alert_type`）；camelCase 只作内部变量名。
  - `ErrorCode` 不得新增成员；新异常复用 `CONFIG` / `CAPTURE`。
  - `edge/pyproject.toml` 属 L1，依赖清单保持 `dependencies = []`；图像库 / 推理框架一律函数体内 import。
  - **相机状态口径**：取图失败、从未成功打开、设备缺失一律 `offline`；只产出 `ok` / `offline` 两态（照度与脏污需图像分析，本期不设取值）。
  - A1~A6 / B1~B2 未拍板前，不得把新增接口 / 新目录 / 职责表扩容 / 新增公开方法 / 新增文件当作已批准的 L1 事实继续扩散。
  - `.codebuddy/skills/edge-refactor/SKILL.md` §1 / §7 的「共 9 个阶段」表述待同步为 12（**不在本轮授权范围**，需用户授权后由主 agent 改；`references/stage-catalog.md` §1 已同步为 12）。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**待签署**（任何 agent 不得代签）。本轮**尚未取得**用户本人对 `c4plus` / `c5plus` / `dplus` 的 review 签字。
- **最终 review 结论：<留空，由用户本人填写>**
- [ ] 配置/交付范围确认
- [ ] 举证结论确认
- [ ] 状态推进确认（`c4plus` / `c5plus` / `dplus` → `done`）
- [ ] A1~A6 契约增量逐项拍板
- [ ] B1~B2 白名单追认
- [ ] 第三轮修复与两张图交付确认（§3.1 / §3.2）
- 确认人 / 日期：<由用户本人填写>
