# HANDOFF-d — 控制、装配与端到端

- **阶段**：d（共 9 个阶段，末阶段）
- **日期**：2026-11-12
- **状态**：done
- **移交方**：助手（主 agent）
- **接收方**：上板 / 后续裁决（`stage-opener`）

## 1. 开工依据

- 用户确认记录：2026-11-12 出开工确认卡（≤15 行），同日用户本人「点头开工，d 记为 in_progress，按开工卡白名单与验收项执行四步」，确认单测名 `test_stage_d_control.py`、`control/` 三文件按卡内白名单且为新建目录；EventCache 存废与协议口径张力按卡内登记为待拍板、不落地、不自行选边，三条待裁决按归属只登记，`decisions.md` 原文不改，错放判定与 `camera_status` 两组不混入 d；禁写 `.py` 仅对本次白名单解除、不沿用；四步由主 agent 连续执行、极简文档、停在人工闸门。同日用户本人 review 实现与 `test-report.md` 后签字「我看过实现和 test-report.md 了，签字」，并本条同时确认状态推进 `d → done`、不再另停一次。
- 适用权威：`CODEBUDDY.md` §2 + 规则 01~04（用户 2026-11-09/10 修订版）。
- 本阶段 spec 资料：`edge/docs/spec/整体流程/整体流程.txt`（INDEX §2.2，三段时序）、`整合类图代码.txt` / `整合类图.png`、`阶段0-3.png` / `阶段4-5.png` / `阶段5-7.png`、`edge/docs/spec/智能工具柜配置项通信协议_初稿.docx`（§2.10，只取线上键名）；只取语义、不转录图中文字。
- 上一阶段 handoff：`edge/docs/refactor/HANDOFF-c5.md`。
- 现有代码判定：引用 `references/stage-catalog.md` §0 — d 为**新模块** `edge/control/`（新建目录）与两个入口文件，无旧代码需处置；按 L1 §2 目录结构新建。

## 2. 交付文件与必交物

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/control/__init__.py` | 新增 | — | 包标记（新建目录） |
| `edge/control/edge_control.py` | 新增 | d-1、d-3、d-4 | `EdgeControl(BaseService, SignalSink, ICaptureSink, IRecognitionSink)`：`routeSignal` 按注入 `asyncHandlers` 分发、Sink 只入队/轻量转发、停机严格串行 |
| `edge/control/event_cache.py` | 新增 | d-2 | `EventCache`：DOWN 缓存、UP 按 `enabled` 补发/丢弃，`seq` 只填不用、无去重 |
| `edge/app_init.py` | 新增 | d-4 | `AssemblyParts` + `ModuleWiring` 装配接线，`buildSystem()` 只做 new + 注入 + 返回；`defaultParts()` 骨架注入 |
| `edge/main.py` | 新增 | d-3、d-4 | 第一件事 `ProcessFileLock.acquireOrExit()`，注册信号、启动、等待、停机；不用 `try/except` 包业务流程 |
| `edge/tests/unit/test_stage_d_control.py` | 新增 | d-1~d-4 | 17 用例，全部带验收项编号注释 |
| `edge/docs/refactor/stages/d/spec-digest.md` | 新增（必交物） | — | 五节齐备（含命名裁决表、三条待裁决按归属只登记） |
| `edge/docs/refactor/stages/d/test-report.md` | 新增（必交物） | — | 六节齐备（④ 真实命令与输出、⑥ 8 行未覆盖项及原因） |
| `edge/docs/refactor/stages/d/verification-evidence.md` | 新增（步骤 4 举证） | — | 只举证、不下最终结论、不代签 |
| `edge/docs/refactor/STAGE-STATE.md` | 修改（状态与证据） | — | d 行 `in_progress → done`、证据栏、§5 门禁记录 |
| `.codebuddy/skills/edge-refactor/references/lessons.md` | 修改（沉淀） | — | 追加 L-10 |

- 必交物：`edge/docs/refactor/stages/d/spec-digest.md` **存在（五节齐备）**
- 必交物：`edge/docs/refactor/stages/d/test-report.md` **六节齐备**（④ 可复现命令 + 环境 + 真实输出；⑥ 8 行未覆盖项及原因，未写「全部覆盖」）
- 范围外文件：**无**（L1 契约层、`edge/docs/spec/**` 原文/PNG、`references/decisions.md`、`编码规范.mdc` 均未改；三条待裁决只在 `spec-digest.md` §5 与 `test-report.md` ⑥ 按归属登记，不落地、不裁定）
- 遗留 TODO 及归属阶段：见 §6（全部按归属留后续阶段）

## 3. 验收项逐条证据（步骤 4 `stage-verifier` 举证表，只举证、不代签）

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| d-1 | `routeSignal` 按注入 `asyncHandlers` 键分发 | `pytest edge\tests\unit\test_stage_d_control.py -q` → `17 passed`；`test_d_1_route_signal_dispatches_injected_keys`（注入任意键命中、`reqId` 只提取一次）、`test_d_1_unknown_key_rejected_and_sink_forwards`（未注册键返回 `False`）、`test_d_1_l1_sink_contracts_and_camel_case`；report ①③ | 通过 |
| d-2 | `EventCache` 补发/丢弃且 `seq` 只填不用 | `test_d_2_cache_flush_when_enabled`（`flush == 3`、seq `[1,2,3]`）、`test_d_2_cache_discard_when_disabled`（`flush == 0`）、`test_d_2_seq_only_filled_never_used_for_dedup`（相同事件全补发、无 `seenSeq`）、`test_d_2_link_down_caches_and_link_up_flushes`、`test_d_2_dispatch_outbox_sends_when_up`；report ①③ | 通过 |
| d-3 | 一键停机严格串行 `USB → 识别 → TCP → 日志` + 进程锁 | `test_d_3_stop_system_strict_serial`（`trace == [USB, RECOGNITION, TCP, LOG]`）、`test_d_3_process_lock_fails_fast_before_assembly`（`SystemExit` 含 `CONFIG`、`partsCalled == []`）、`test_d_3_selfcheck_stub_d01`、`test_d_3_start_system_does_not_prestart_business_threads`；report ①③ | 通过 |
| d-4 | Windows 端到端 | `test_d_4_end_to_end_start_and_stop`（锁→装配→信号→启动→等待→停机→释放全链路）、`test_d_4_app_init_only_wires`、`test_d_4_main_has_no_try_except_business_flow`、`test_d_4_build_system_has_no_business_branches`、`test_d_4_platform_and_fake_contracts`；report ①③ | 通过 |
| 必交物齐备 | `spec-digest.md` 五节 / `test-report.md` 六节 | ① 对照表与 `d-1`~`d-4` 一一对应；④ 可复现命令 + 环境 + 真实输出；⑥ 8 行未覆盖项及原因；17 个测试函数全带编号注释，无 `assert True` / 裸断言 / skip 标记，③ 如实披露首轮 ruff/mypy 问题与检视中 3 处收敛 | 齐备、不判红 |
| 人工闸门 | 用户本人 review 签字 | 用户 2026-11-12 本条「我看过实现和 test-report.md 了，签字」；`stage-verifier` 只出本举证表、不填最终结论、不代签 | 齐备 |

- 工具链（收尾实跑）：`ruff` `All checks passed!` ｜ `mypy`（3.9 strict）`Success: no issues found in 64 source files` ｜ `pytest` d `17 passed in 0.63s`、全量 `111 passed in 2.10s`、契约 `10 passed in 0.17s`（退出码均 0）。四步内一组 `0.55s / 1.90s / 0.17s`，passed 数三项一致、耗时为不同次运行波动，如实并列保留。
- `test-report.md` 六节：**齐备**；第 ⑥ 节未覆盖项摘要：EventCache 存废张力（d 待用户拍板）、错放判定与 `camera_status` 两组（后续阶段）、真实 `config.ini` 与业务键注入、真实 socket/摄像头/rknn、真实 Windows 真机端到端、线上键名最终映射、真实 3s 计时器与读图、全链路真实线程并发（上板）。
- 测试约定核验：`## @brief 对应验收项 d-*` 编号注释齐全；无空洞断言（逐项具体值 / 枚举码 / 调用顺序）；首轮 ruff `I001`/`E501`/`N812` 与 mypy 2 处均为白名单内修正，检视中 3 处（模块名常量、魔法值、`-> None` 值断言）收敛后三项工具链复跑全绿，未改验收项 / 未改预期 / 未删用例 / 未为变绿改被测业务语义。

### python-code-review 报告（收尾极简检视一次，范围 `control/*.py` 3 文件 + `app_init.py` + `main.py` + 单测）

| 级别 | 位置 | 维度 | 证据 | 结论 |
| --- | --- | --- | --- | --- |
| P0 | `control/` / `app_init.py` | 依赖方向 | `control/` 仅依赖 `base/` / `interfaces/` / `exceptions.py` 与同模块；`app_init → control` + `app_init → modules/*`，无反向 import；`sys.platform` 仍只在 `PlatformFactory` | 通过 |
| P0 | `event_cache.py` / `edge_control.py` / `main.py` | 三条裁决 | D-01 空接口 + TODO；D-02 只 init + link；D-03 `seq` 只填不用、无 `seenSeq` / 去重分支；`enabled` 构造注入、模块不默认 | 通过 |
| P1 | `edge_control.py` Sink 回调 | 并发 / 边界 | 回调只入队 / 轻量转发，`dispatchOutbox()` 才发送；`stopSystem()` 严格串行由常量固定；`frameSender` 加锁组帧 | 通过 |
| P1 | `main.py` | 入口约束 | 第一件事 `acquireOrExit()`；无 `try/except`、无 `if not success:` 包业务流程；信号注册与退出等待构造注入 | 通过 |
| P2 | `app_init.py` | 可测试性 | `ModuleWiring` 装配期填充解决「门面需 Sink=EdgeControl、EdgeControl 需门面」的构造循环，无 `set_signal_sink` 式 setter；`defaultParts()` 骨架均标 TODO | 通过 |
| P3 | `test_d_4_*` | 测试脆弱性 | 两处 AST 源码结构断言属静态文本举证（经验库已登记同类），已有行为断言交叉证据 | 归上板，不阻断 |

- 未覆盖软维度：PyCharm IDE 报 `Unresolved reference 'edge'` 与 camelCase 命名 warning，属 IDE 源根/检查器与项目 camelCase 规范冲突，三项工具链全绿、`pyproject.toml` 属 L1 未改，不判为代码缺陷、不阻断收尾。
- 结论：无阻断项；检视中 3 处已在白名单内收敛并如实披露；跨阶段遗留项标归属（上板 / 用户裁决后），不阻断收尾。

## 4. L1 契约层

- `contract-guard` 基线结论：**零自动变更**（主 agent 只读 git 独立取证，见下）。子代理 `contract-guard` 本轮无命令执行工具，明确返回「**L1 状态：未判定**」，按「不采信他方转述、不编造结论」不引用其结论；与 c4/c5 同类偏差，c4 已记入 `HANDOFF-c4.md` §4、c5 已记入 `HANDOFF-c5.md` §4。
- 主 agent 取证：`git rev-parse HEAD` = `git rev-parse stage-c5-done^{commit}` = `a7178d2233e175fac0c04b919c9f030103e8482f`；L1 + `edge/docs/spec/` 相对基线 / 工作区 / 暂存区三段 `git diff --name-status` 全空；`git status --porcelain=v1 --untracked-files=all` 仅 d 白名单 8 个新文件 + `STAGE-STATE.md` 修改；`git tag --list` 9 个。附录 A 已批准基线项按「不重复判定」口径处理。
- 契约变更 diff：无。批准状态：无需批准。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— 已遵守（未触碰 L1 任何文件；`edge/docs/spec/**` 原文与 PNG 零改动）。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守 | `EdgeControl.selfCheckSystem()` 空方法 + TODO；不实现、不新增自检线程、不做能力降级；图上的自检旁路三分支不落地 |
| D-02 非 UP 不启其他线程 | 已遵守 | `startSystem()` 只调 `initializeModules` + `startLink`（tcp 只拉重连线程，UP 后由 c3 门面启心跳/解码）；不预启采集/识别 worker；`linkState` 仍只经 `transitionTo` 写入 |
| D-03 去重不做、seq 只填不用 | 已遵守 | `EventCache` 按 `enabled` 补发/丢弃，`seq` 只递增填充、不参与去重/排序/幂等；无 `seenSeq` / 去重缓存 / `PendingRequest` 重发；心跳帧由 tcp/ 内部直发、不经 `EventCache` |

## 6. 遗留与裁决

- 图与 L1 的冲突点：自检旁路 / 能力降级（不落地，D-01）、`config.getValue` 直连（改构造注入）、图上 `send_frame` 与 c3 未落地 `tcp_socket.py` 的缺口（改注入 `frameSender`，不改 c3 / 不改 L1）、「Edge 统一停心跳/启重连」与 c3 已收敛在 `TcpControlLayer.onLinkDown` 内的差异（d 层只做缓存开关，不重复宣告）、图上 snake_case 回调（不作 API，按 L1 camelCase，映射表见 `spec-digest.md` §2）、运行期「阶段 0~7」编号（非实施阶段）。**未改图、未改 L1**。
- 需用户拍板事项：**EventCache 存废（归 d）与 §2.10 外部协议 docx「边缘机不缓存任何业务数据、重发补发全是上位机行为」的口径张力** —— 用户 2026-11-12 明确「只登记、不落地、不自行选边、待我拍板」；本阶段按 L1 §1/§5 既定的「`event_cache.enabled` 开关做」落地中性机制（`enabled` 由上层注入、模块不默认、不写死），两种业务口径均不裁定、不落地、不选边。登记位置仅 `spec-digest.md` §5 与 `test-report.md` ⑥，`decisions.md` 原文未改。
- `decisions.md` 待裁决三条按归属**只登记、不落地、不自行裁定**：① EventCache 存废 → `d`（张力见上）；② 错放判定归属 → `c5`；③ `camera_status` 空接口默认值 +「连丢 5 条周期帧判离线」→ `c4/d`（两组按用户指令**不混入 d**，`defaultHeartbeat()` 不含 `camera_status`、不设默认值）。
- 阻塞原因与解除条件：无。
- 移交后续阶段的收敛项：真实 `config.ini` 参数读取与业务 `asyncHandlers` 键注入、真实 socket / 摄像头 / rknn 后端、真实 Windows 真机端到端、线上 JSON 键名最终映射、真实 3s 计时器与读图、全链路真实线程并发 → **上板 / 用户裁决后**；⑥ 未覆盖项按用户口述「按归属留后续阶段，覆盖率不引入」。

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：d 行 `in_progress → done`（用户本条同时确认推进、不再另停一次）、证据栏补收尾工具链与举证结论、§1 当前阶段、§5 门禁记录追加 2026-11-12 d 收尾行、时间 2026-11-12。
- `references/lessons.md` 条目号：**L-10**（构造循环用装配期 wiring 解耦；业务口径冲突只做中性机制、不替用户选边）。
- 项目记忆：**无**（本阶段无新增跨会话裁决或反馈；EventCache 张力按用户指令只在阶段产物登记、待拍板，不写入记忆；精简模式、签字口径、「不再另停一次」等已有 `feedback_stage_compact_mode.md` 等条目覆盖）。
- `python-code-review` 经验库：按维护规则更新既有「源码文本断言属脆弱断言」条目命中次数（3 → 4，补 d 阶段 AST 结构断言），不重复新增；位于工作区外，不纳入 git。
- `references/decisions.md`：**未变更**（无新 D-xx；三条待裁决只在阶段产物登记，不裁定）。

## 8. 下阶段开工提示

- 下一阶段：**无**（d 为 9 个实施阶段的末阶段）；后续工作为上板集成与用户裁决后的收敛，不再另起实施阶段目录。
- 必读：`edge/docs/refactor/HANDOFF-d.md`、`edge/docs/refactor/stages/d/test-report.md` ⑥、`references/decisions.md` 待裁决登记三条、`edge/docs/spec/INDEX.md` §2.10 协议 docx 键名。
- 特别注意：`SocketSkeleton` / `placeholderFrame(s)` / `directInference` / `zeroUsage` / `defaultFailureFrame` 均为骨架占位并标 TODO，上板前须接真实后端；`defaultParts()` 的 `asyncHandlers` 默认为空字典，业务键须由配置注入，`EdgeControl` 不得写死业务字符串；`ModuleWiring` 在 `buildSystem()` 装配期填充，新增模块时须同步补 `stopActions` 与 `STOP_ORDER` 顺序；EventCache 存废口径未拍板前不得自行选边。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**已签署**（用户本人 2026-11-12「我看过实现和 test-report.md 了，签字」）。
- **最终 review 结论（用户口述 2026-11-12，按原文录入，不视为代签）：**

  > 阶段 d 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。

- [x] 配置/交付范围确认
- [x] 举证结论确认
- [x] 状态推进确认（d → `done`）
- 确认人 / 日期：用户本人 / 2026-11-12
