# HANDOFF-c4 — USB 采集模块

- **阶段**：c4（共 9 个阶段）
- **日期**：2026-11-11
- **状态**：done
- **移交方**：助手（主 agent）
- **接收方**：下一阶段开工（`stage-opener` → c5）

## 1. 开工依据

- 用户确认记录：2026-11-11 用户「点头开工，c4 记为 in_progress」，签开工卡白名单（`edge/modules/usb/` 三文件 + `edge/tests/unit/` 一个单测）与已拍板裁决；同条补充 `edge/modules/usb/__init__.py`（新建包标记，按 L1 §2 目录结构），其余按卡内不变；开工前把 `.codebuddy/skills/edge-refactor/SKILL.md` 收尾流程改动用 `git add -f` 单独提交（`5f57056`，注明「流程规则变更、非 c4 产物」），工作区干净后进四步。同日用户 review 实现与 `test-report.md` 后签字「我看过实现和 test-report.md 了，签字」，并本条同时确认状态推进 `c4 → done`、不再另停一次。
- 适用权威：`CODEBUDDY.md` §2 + 规则 01~04（用户 2026-11-09/10 修订版）。
- 本阶段 spec 资料：`edge/docs/spec/USB_Camera/USB.txt`（INDEX §2.8，类图 / 流程图 / 时序图源码）、`edge/docs/spec/USB_Camera/*.png`（迭代快照）、`edge/docs/spec/整体流程/阶段4-5.png`（只列路径与图类型，不转录图中文字）。
- 上一阶段 handoff：`edge/docs/refactor/HANDOFF-c3.md`。
- 现有代码判定：引用 `references/stage-catalog.md` §0 — c4 为**新模块** `edge/modules/usb/`，无旧代码需处置。

## 2. 交付文件与必交物

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/modules/usb/__init__.py` | 新增 | — | 包标记（用户补充，按 L1 §2 目录结构） |
| `edge/modules/usb/usb_controller.py` | 新增 | c4-1、c4-4 | `UsbController(BaseService)`：init 校验目录、`startCapture` 前置校验后并发拉起并立即返回、`selfCheck` 空接口、Sink 轻量转发 |
| `edge/modules/usb/usb_capture_worker.py` | 新增 | c4-2、c4-3、c4-4 | `CaptureWorker(BaseThread)`：双路取图落盘、超阈值删旧（保护本轮新帧）、成功/失败回调互不影响 |
| `edge/modules/usb/usb_camera_device.py` | 新增 | c4-2 | `CameraDevice(ICameraDevice)` + `CameraFactory`：按地址形态选后端，Linux 骨架 `NotImplementedError + TODO`，内置异常跨边界转 `EdgeError(CAPTURE)` |
| `edge/tests/unit/test_stage_c4_usb.py` | 新增 | c4-1~c4-4 | 11 用例，全部带验收项编号注释 |
| `edge/docs/refactor/stages/c4/spec-digest.md` | 新增（必交物） | — | 五节齐备（含命名裁决表、三条待裁决按归属只登记） |
| `edge/docs/refactor/stages/c4/test-report.md` | 新增（必交物） | — | 六节齐备（④ 真实命令与输出、⑥ 六行未覆盖项及原因） |
| `edge/docs/refactor/STAGE-STATE.md` | 修改（状态与证据） | — | c4 行 `in_progress → done`、证据栏、§5 门禁记录 |
| `.codebuddy/skills/edge-refactor/references/lessons.md` | 修改（沉淀） | — | 追加 L-08 |

- 必交物：`edge/docs/refactor/stages/c4/spec-digest.md` **存在（五节齐备）**
- 必交物：`edge/docs/refactor/stages/c4/test-report.md` **六节齐备**（第 ⑥ 节六行未覆盖项、未写「全部覆盖」）
- 范围外文件：**无**（L1 契约层、`edge/docs/spec/**` 原文/PNG、`references/decisions.md`、`编码规范.mdc` 均未改；三条待裁决只在 `spec-digest.md` §5 与 `test-report.md` ⑥ 按归属登记，不落地、不裁定）
- 遗留 TODO 及归属阶段：见 §6（全部按归属留后续阶段）

## 3. 验收项逐条证据（步骤 4 `stage-verifier` 举证表，只举证、不代签）

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| c4-1 | 4 线程并发拉起并立即返回（前置校验：已初始化且未采集中） | `pytest edge\tests\unit\test_stage_c4_usb.py -q` → `11 passed in 0.58s`；`test_c4_1_four_workers_fork_and_return_immediately`（Barrier(5) + `len(workers)==4` + `elapsed<1.0` + 成功 id `[1,2,3,4]`）、`test_c4_1_guard_before_init`、`test_c4_1_init_fails_fast_on_missing_dir`、`test_c4_1_selfcheck_stub_d01`；report ① / ③ | 通过 |
| c4-2 | 双路取图落盘 | `test_c4_2_dual_frames_saved`（左右帧逐字节 `b"LEFT-BYTES"` / `b"RIGHT-BYTES"`）、`test_c4_2_camera_factory_addressing`（DSHOW / V4L2 后端）、`test_c4_2_linux_skeleton_converted_before_boundary`（`EdgeError(CAPTURE)`）；全量 `83 passed in 2.01s` | 通过 |
| c4-3 | 滚动删除（超 30% 删旧） | `test_c4_3_roll_deletes_oldest`（注入 `usageRatio`，删最旧 2 个、比例回落 0.3 停止、新帧保留）、`test_c4_3_roll_still_over_threshold_logs_error`（`errorRecords` 含 CAPTURE、成功回调仍 1 条）；report ③ | 通过 |
| c4-4 | 成功 / 失败回调互不影响；`FakeCamera` 联调通过 | `test_c4_4_success_error_callbacks_isolated`（成功 id `[1,2,4]`、失败 1 条 id=3、`code==CAPTURE`、`all(camera.closed)`）、`test_c4_4_fake_camera_contract`；契约 `10 passed in 0.17s` | 通过 |
| 必交物齐备 | `spec-digest.md` 五节 / `test-report.md` 六节 | ① 对照表与 `c4-1`~`c4-4` 一一对应；④ 可复现命令+环境+真实输出；⑥ 六行未覆盖项及原因；11 个测试函数全带编号注释，无 `assert True` / 裸断言 / skip 标记，③ 如实披露首轮 `F821`、`func-returns-value`、`2 failed` 及白名单内修正 | 齐备、不判红 |
| 人工闸门 | 用户本人 review 签字 | 用户 2026-11-11 本条「我看过实现和 test-report.md 了，签字」；`stage-verifier` 只出本举证表、不填最终结论、不代签 | 齐备 |

- 工具链（收尾实跑）：`ruff` `All checks passed!` ｜ `mypy`（3.9 strict）`Success: no issues found in 52 source files` ｜ `pytest` c4 `11 passed in 0.58s`、全量 `83 passed in 2.01s`、契约 `10 passed in 0.17s`（退出码均 0）。四步内一组 `0.52s / 1.70s / 0.18s`，passed 数三项一致、耗时为不同次运行波动，如实并列保留。
- `test-report.md` 六节：**齐备**；第 ⑥ 节未覆盖项摘要：真实 V4L2/CAP_DSHOW 后端（归 d）、真实磁盘比例与跨天滚动（归 d）、按 workerId 触发识别（归 c5/d）、`camera_status` 默认值 + 连丢 5 帧判离线（归 c4/d 待裁决，本阶段只登记）、采集线程自停与重复 `stopCapture` 并发（归 d）、真实平台路径差异（归 d）。
- 测试约定核验：`## @brief c4-*` 编号注释齐全；无空洞断言（曾有一处 `or True` 占位，已在白名单内替换为具体值断言）；③ 与 ④ 如实披露首轮失败与 Linux 骨架首版直抛 `EdgeError` 的修正，未改验收项 / 未改预期 / 未删用例 / 无为变绿而改被测代码。

### python-code-review 报告（收尾极简检视一次，范围 `usb/*.py` 四文件 + 单测文件）

| 级别 | 位置 | 维度 | 证据 | 结论 |
| --- | --- | --- | --- | --- |
| P0 | `usb/` 全部 | 依赖方向 / 禁词 | 仅 import `base/`、`interfaces/`、`exceptions.py`；无 `modules/tcp/`、`recognition/`、`control/`，无 `sys.platform`、无 `cv2` 依赖 | 通过 |
| P0 | `usb_controller.selfCheck` | D-01 | 空方法 + TODO，无自检线程、无能力降级；`test_c4_1_selfcheck_stub_d01` 举证 | 通过 |
| P1 | `usb_camera_device.open` | 异常边界 | 首版 Linux 骨架直抛 `EdgeError`，检视发现与 L1 §1「骨架 `NotImplementedError + TODO`」及规范 4.4 口径不一致；已在白名单内改为 `NotImplementedError + TODO`，并新增 `test_c4_2_linux_skeleton_converted_before_boundary` 举证跨边界前转 `EdgeError(CAPTURE)`，三项工具链复跑全绿 | 已当阶段收敛 |
| P1 | `usb_capture_worker.runLoop` | 并发 / 容错 | `except EdgeError` / `except Exception` 分级转业务异常，`finally` 关闭双路句柄，单线程失败不波及他线程 | 通过 |
| P2 | `checkRollStorage` | 数据保护 / 可观测 | 首版会把本轮刚落盘的新帧一并删除；已加 `_currentFiles` 排除本轮产出，`usageRatio` / `clock` / `frameReader` 全部构造注入，阈值分支在 `tmp_path` 内确定性举证（沿用 L-06 口径） | 已当阶段收敛 |
| P2 | 测试侧 | mypy strict | `-> None` 方法不可作值断言（L-04），改断言零副作用；`f"old{i}"` 笔误已修 | 通过 |
| P3 | 真实后端 / 停机路径 | 跨阶段 | 真实 V4L2、真实磁盘比例、worker 自停与重复 `stopCapture` 并发 | 归 `c5 / d`，不阻断 |

- 未覆盖软维度：PyCharm IDE 报 `Unresolved reference 'edge'` 与 camelCase 命名 warning，属 IDE 源根/检查器与项目 camelCase 规范冲突，三项工具链全绿、`pyproject.toml` 属 L1 未改，不判为代码缺陷、不阻断收尾。
- 结论：无阻断项；两条 P1/P2 已在本阶段白名单内收敛并如实披露，跨阶段遗留标归属。

## 4. L1 契约层

- `contract-guard` 基线结论：**零自动变更**（主 agent 只读 git 独立取证，见下）。子代理 `contract-guard` 本轮两次不可用：第一次 API 不可达（`getaddrinfo ENOTFOUND copilot.tencent.com`），第二次实例仅有 `Read/Grep/Glob`、无命令执行工具，按「不要重试其他工具」返回「**L1 状态：未判定**」，明确不产出「无变更」结论、不采信他方转述。故**不引用子代理结论**，改由主 agent 用 git 只读命令取证并如实披露这一偏差。
- 主 agent 取证：`git diff --name-status stage-c3-done HEAD -- <L1 pathspec>`（空）、工作区 L1 `git diff --name-status -- <L1 pathspec>`（空）、`git diff --name-status HEAD -- edge/docs/spec`（空）。HEAD 相对基线仅多 `5f57056`，只含 `.codebuddy/skills/edge-refactor/SKILL.md` 收尾流程 push 规则文字（L3 流程规则，用户明确单独提交并注明非 c4 产物），非 L1 变更。附录 A 已批准基线项按「不重复判定」口径处理。
- 契约变更 diff：无。批准状态：无需批准。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— 已遵守（未触碰 L1 任何文件；`edge/docs/spec/**` 原文与 PNG 零改动）。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守 | `UsbController.selfCheck()` 空方法 + TODO；不实现、不新增自检线程、不做能力降级；`CaptureWorker` 不设 `checkCamera`；init 失败按 Fail-Fast 抛 `EdgeError(CONFIG)` |
| D-02 非 UP 不启其他线程 | 已遵守 | 本模块不感知 `linkState`；`init()` 只校验目录，唯一拉起点为 `startCapture()` 前置校验后并发 `start()`，无预热线程 |
| D-03 去重不做、seq 只填不用 | 已遵守 | 全模块无 `seq` / 去重 / 幂等逻辑；每次拉起新建 worker 实例（沿用 L-07，绕开 `BaseThread.start()` 幂等） |

## 6. 遗留与裁决

- 图与 L1 的冲突点：自检旁路 / 能力降级三分支（不落地，D-01）、`config.getValue` 直连（改构造注入）、图上 snake_case 回调（`read_frame` / `on_capture_success` 等不作 API，按 L1 camelCase，映射表见 `spec-digest.md` §2）、`startCaptureTask` → `startCapture`、开工卡 `camera_device.py` → 按 L1 §2 + glossary §3.2 落地 `usb_camera_device.py`（目录对齐，非契约变更）。**未改图、未改 L1**。
- 需用户拍板事项：**无**。
- `decisions.md` 待裁决登记三条按归属**只登记、不落地、不自行裁定**：① EventCache 存废 → `d`；② 错放判定归属 → `c5`；③ `camera_status` 空接口默认值 +「连丢 5 条周期帧判离线」→ `c4/d`（上位机侧判定，与 `linkState` 严格区分，本阶段不实现、不设默认值）。仅登记于 `spec-digest.md` §5 与 `test-report.md` ⑥，`decisions.md` 原文未改。
- 阻塞原因与解除条件：无。
- 移交后续阶段的收敛项：真实 V4L2/CAP_DSHOW 后端、真实磁盘占用比例与跨天滚动、真实平台路径差异 → **d**；按 workerId 触发识别 → **c5/d**；采集线程自停与重复 `stopCapture` 并发、一键停机串行 → **d**；⑥ 未覆盖项按用户口述「按归属留后续阶段，覆盖率不引入」。

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：c4 行 `in_progress → done`（用户本条同时确认推进、不再另停一次）、证据栏补收尾工具链与举证结论、§1 当前阶段、§5 门禁记录追加 2026-11-11 c4 开工行与收尾行、时间 2026-11-11。
- `references/lessons.md` 条目号：**L-08**（滚动删旧须排除本轮新帧 + `NotImplementedError` 骨架跨界转换）。
- 项目记忆：**无**（本阶段无新增跨会话裁决或反馈；精简模式、签字口径、「不再另停一次」等已有 `feedback_stage_compact_mode.md` 等条目覆盖，不重复存代码细节）。
- `python-code-review` 经验库：已追加一条「滚动删旧须保护本轮新帧 + 外部依赖注入回调」检查项至全局 `references/accumulated-lessons.md`（位于工作区外，不纳入 git、不重复存两份）。
- `references/decisions.md`：**未变更**（无新 D-xx；三条待裁决只在阶段产物登记，不裁定）。

## 8. 下阶段开工提示

- 下一阶段：**c5**（`modules/recognition/` 四个文件）。
- 必读：`edge/docs/refactor/HANDOFF-c5.md`（待生成）、`references/stage-catalog.md` c5 段、`decisions.md` 命中裁决、`edge/docs/spec/INDEX.md` §2.9 与 `阶段4-5.png`。
- 特别注意：c5 需按 workerId 触发识别，c4 成功回调上报的是**采集目录**路径（非单文件路径），双路文件名固定 `w{id}_left_{stamp}.jpg` / `w{id}_right_{stamp}.jpg`；`camera_status` 默认值与「连丢 5 条周期帧判离线」仍属 c4/d 待裁决登记、未落地，c5 不得自行裁定；沿用 L-07「每次拉起新建线程实例」与 L-08「外部依赖注入回调」。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**已签署**（用户本人 2026-11-11「我看过实现和 test-report.md 了，签字」）。
- **最终 review 结论（用户口述 2026-11-11，按原文录入，不视为代签）：**

  > 阶段 c4 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。

- [x] 配置/交付范围确认
- [x] 举证结论确认
- [x] 状态推进确认（c4 → `done`）
- 确认人 / 日期：用户本人 / 2026-11-11
