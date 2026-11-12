# HANDOFF-c5 — 识别模块

- **阶段**：c5（共 9 个阶段）
- **日期**：2026-11-12
- **状态**：done
- **移交方**：助手（主 agent）
- **接收方**：下一阶段开工（`stage-opener` → d）

## 1. 开工依据

- 用户确认记录：2026-11-11 出开工确认卡（≤15 行），2026-11-12 用户本人「点头开工，c5 记为 in_progress，按开工卡白名单与验收项执行四步」，确认单测名 `test_stage_c5_recognition.py`、四文件 + `__init__.py` 按卡内白名单、`fake_recognition_engine.py` 只读复用；错放判定与协议口径张力按卡内登记为待拍板、不落地、不自行选边；`decisions.md` 原文不改，三条待裁决只落 `spec-digest.md` §5 与 `test-report.md` ⑥；禁写 `.py` 仅对本次白名单解除、不沿用；四步由主 agent 连续执行、极简文档、停在人工闸门。
- 适用权威：`CODEBUDDY.md` §2 + 规则 01~04（用户 2026-11-09/10 修订版）。
- 本阶段 spec 资料：`edge/docs/spec/识别/识别.txt`（INDEX §2.9，类图 / 流程图 / 时序图源码）、`edge/docs/spec/识别/*.png`（3 张迭代快照）、`edge/docs/spec/整体流程/阶段4-5.png`（下半段）、`edge/docs/spec/智能工具柜配置项通信协议_初稿.docx`（§2.10，只取线上键名）；只取语义、不转录图中文字。
- 上一阶段 handoff：`edge/docs/refactor/HANDOFF-c4.md`。
- 现有代码判定：引用 `references/stage-catalog.md` §0 — c5 为**新模块** `edge/modules/recognition/`，无旧代码需处置；按 L1 §2 目录结构新建五文件。

## 2. 交付文件与必交物

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/modules/recognition/__init__.py` | 新增 | — | 包标记 |
| `edge/modules/recognition/recognition_controller.py` | 新增 | c5-1、c5-4 | `RecognitionController(BaseService)`：init 单次加载模型、`trigger` 前置校验后立即返回、限流仅 TODO、`selfCheckRecognition()` 空接口、Sink 轻量转发 |
| `edge/modules/recognition/recognition_worker.py` | 新增 | c5-2、c5-3、c5-4 | `RecognitionWorker(BaseThread)`：读图→拼接→画 ROI→超时推理→归集→查表→组 ack→回调，内置异常转 `EdgeError` |
| `edge/modules/recognition/recognition_yolo_engine.py` | 新增 | c5-1 | `YoloEngine(IRecognitionEngine)` 类内 `instance()` 双检锁、`loadModel` 幂等、rknn 切换点留 TODO |
| `edge/modules/recognition/recognition_utils.py` | 新增 | c5-3、c5-4 | 5 个纯函数：`cropAndMerge` / `drawRoi` / `aggregateByRoi` / `validateByTable` / `buildAck` |
| `edge/tests/unit/test_stage_c5_recognition.py` | 新增 | c5-1~c5-4 | 11 用例，全部带验收项编号注释 |
| `edge/tests/fakes/fake_recognition_engine.py` | 只读复用 | c5-1、c5-3、c5-4 | 白名单外，未修改 |
| `edge/docs/refactor/stages/c5/spec-digest.md` | 新增（必交物） | — | 五节齐备（含命名裁决表、三条待裁决按归属只登记） |
| `edge/docs/refactor/stages/c5/test-report.md` | 新增（必交物） | — | 六节齐备（④ 真实命令与输出、⑥ 7 行未覆盖项及原因） |
| `edge/docs/refactor/stages/c5/verification-evidence.md` | 新增（步骤 4 举证） | — | 只举证、不下最终结论、不代签 |
| `edge/docs/refactor/STAGE-STATE.md` | 修改（状态与证据） | — | c5 行 `in_progress → done`、证据栏、§5 门禁记录 |
| `.codebuddy/skills/edge-refactor/references/lessons.md` | 修改（沉淀） | — | 追加 L-09 |

- 必交物：`edge/docs/refactor/stages/c5/spec-digest.md` **存在（五节齐备）**
- 必交物：`edge/docs/refactor/stages/c5/test-report.md` **六节齐备**（④ 可复现命令 + 环境 + 真实输出；⑥ 7 行未覆盖项及原因，未写「全部覆盖」）
- 范围外文件：**无**（L1 契约层、`edge/docs/spec/**` 原文/PNG、`references/decisions.md`、`编码规范.mdc` 均未改；三条待裁决只在 `spec-digest.md` §5 与 `test-report.md` ⑥ 按归属登记，不落地、不裁定）
- 遗留 TODO 及归属阶段：见 §6（全部按归属留后续阶段）

## 3. 验收项逐条证据（步骤 4 `stage-verifier` 举证表，只举证、不代签）

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| c5-1 | 模型仅 `loadModel` 一次、`trigger` 立即返回 | `pytest edge\tests\unit\test_stage_c5_recognition.py -q` → `11 passed`；`test_c5_1_load_once_and_trigger_returns_immediately`（`loadedPaths == ["model.bin"]`、Barrier 举证 `elapsed < 1.0s`、忙时返回 `False`）、`test_c5_1_guard_before_init_and_invalid_worker_id`、`test_c5_1_selfcheck_stub_d01`、`test_c5_1_yolo_engine_instance_and_single_load`；report ①③ | 通过 |
| c5-2 | 推理 3s 超时（构造注入） | `test_c5_2_timeout_injected_and_mapped`（`seen == [3.0]`、Sink 收 `EdgeError(INFERENCE_TIMEOUT)`、日志含异常码）、`test_c5_2_timeout_sec_is_configurable`（`seen == [0.25]` 证明非硬编码）；report ①③ | 通过 |
| c5-3 | 空间归集 + 查表校验 + 组 ack | `test_c5_3_aggregate_lookup_and_build_ack`（ack 三条 items 逐项具体值、`type` / `requestId` / `workerId` 断言、未命中记 CONFIG error 不中断）、`test_c5_3_pure_functions_behavior`；report ①③ | 通过 |
| c5-4 | 回调上抛、纯函数留在 `recognition_utils.py` | `test_c5_4_callbacks_isolated_and_exception_upcast`（成功 id `[1]`、失败 id=2、`code == CAPTURE`）、`test_c5_4_pure_functions_only_in_utils_and_no_cross_module_import`（5 个纯函数只在 utils、无 usb/tcp/control 反向 import）、`test_c5_4_fake_engine_contract_and_camel_case_sink`；report ①③ | 通过 |
| 必交物齐备 | `spec-digest.md` 五节 / `test-report.md` 六节 | ① 对照表与 `c5-1`~`c5-4` 一一对应；④ 可复现命令 + 环境 + 真实输出；⑥ 7 行未覆盖项及原因；11 个测试函数全带编号注释，无 `assert True` / 裸断言 / skip 标记，③ 如实披露「首轮全绿、无失败迭代链」 | 齐备、不判红 |
| 人工闸门 | 用户本人 review 签字 | 用户 2026-11-12 本条「我看过实现和 test-report.md 了，签字」；`stage-verifier` 只出本举证表、不填最终结论、不代签 | 齐备 |

- 工具链（收尾实跑）：`ruff` `All checks passed!` ｜ `mypy`（3.9 strict）`Success: no issues found in 58 source files` ｜ `pytest` c5 `11 passed in 0.04s`、全量 `94 passed in 1.91s`、契约 `10 passed in 0.18s`（退出码均 0）。四步内一组 `0.08s / 2.07s / 0.16s`，passed 数三项一致、耗时为不同次运行波动，如实并列保留。
- `test-report.md` 六节：**齐备**；第 ⑥ 节未覆盖项摘要：真实 3s 计时器与 rknn 推理（d / 上板）、真实图像拼接画 ROI（d / 上板）、按采集目录实读左右图（d）、错放判定归属张力（c5 待用户拍板）、EventCache 存废（d）、`camera_status` 默认值 + 连丢 5 帧判离线（c4/d 待裁决）、线上键名映射 / 下游链路 / 停机串行（d）。
- 测试约定核验：`## @brief 对应验收项 c5-*` 编号注释齐全；无空洞断言（逐项具体值 / 枚举码 / 回调次数）；四步首轮全绿，未改验收项 / 未改预期 / 未删用例 / 未为变绿改被测代码。

### python-code-review 报告（收尾极简检视一次，范围 `recognition/*.py` 五文件 + 单测文件）

| 级别 | 位置 | 维度 | 证据 | 结论 |
| --- | --- | --- | --- | --- |
| P0 | `recognition/` 全部 | 依赖方向 / 禁词 | 仅 import `base/`、`interfaces/`、`exceptions.py` 与同模块；无 `modules/usb/`、`modules/tcp/`、`control/`，无 `sys.platform`、无 `cv2` / `numpy`；测试静态断言覆盖 | 通过 |
| P0 | `selfCheckRecognition` / `trigger` | D-01 / D-02 / NPU TODO | 空方法 + TODO，无自检线程、无能力降级；init 只加载模型不预启线程；`trigger` 内限流仅 `# TODO`，无信号量 | 通过 |
| P1 | `runLoop` / `runInference` / `init` | 异常边界 | `TimeoutError`→`INFERENCE_TIMEOUT`、`OSError`→`CAPTURE`、模型加载失败→`CONFIG`，内置异常跨边界前统一转 `EdgeError`，日志用 `code.name` | 通过 |
| P2 | 全模块 | 可测试性 | `inferTimeoutSec` / `timeoutRunner` / `frameLoader` / 三张查表 / `modelPath` 全构造注入（沿用 L-06 / L-08），3s 超时与跨边界异常可确定性举证 | 通过 |
| P3 | `test_c5_4` | 测试脆弱性 | 用 `read_text` 断言源码文本（纯函数只在 utils / 无跨模块 import），属静态文本举证（经验库已登记同类坏味道），已有行为断言交叉证据 | 归 `d`，不阻断 |

- 未覆盖软维度：PyCharm IDE 报 `Unresolved reference 'edge'` 与 camelCase 命名 warning，属 IDE 源根/检查器与项目 camelCase 规范冲突，三项工具链全绿、`pyproject.toml` 属 L1 未改，不判为代码缺陷、不阻断收尾。
- 结论：无阻断项；本阶段无新增可复用检视规律（均为 L-05~L-08 应用），经验库仅按维护规则更新已有条目命中次数，不重复沉淀。

## 4. L1 契约层

- `contract-guard` 基线结论：**零自动变更**（主 agent 只读 git 独立取证，见下）。子代理 `contract-guard` 本轮无命令执行工具，明确返回「**L1 状态：未判定**」，按「不采信他方转述、不编造结论」不引用其结论；与 c3/c4 同类偏差，c4 已记入 `HANDOFF-c4.md` §4。
- 主 agent 取证：`git rev-parse HEAD` = `git rev-parse stage-c4-done^{commit}` = `f3e6a0043669024d5cd7dc49f11c6059d258a6f5`；`git log --oneline stage-c4-done..HEAD` 空；L1 + `edge/docs/spec/` 相对基线 / 工作区 / 暂存区三段 `git diff --name-status` 全空；`git ls-files --others --exclude-standard -- edge` 仅 c5 白名单 8 个新文件；`git tag --list` 8 个。附录 A 已批准基线项按「不重复判定」口径处理。
- 契约变更 diff：无。批准状态：无需批准。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— 已遵守（未触碰 L1 任何文件；`edge/docs/spec/**` 原文与 PNG 零改动）。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守 | `selfCheckRecognition()` 空方法 + TODO；不实现、不新增自检线程、不做能力降级；init 失败按 Fail-Fast 抛 `EdgeError(CONFIG)` |
| D-02 非 UP 不启其他线程 | 已遵守 | 本模块不感知 `linkState`；`init()` 只加载模型，唯一拉起点为 `trigger()` 前置校验后 `start()`，无预热线程 |
| D-03 去重不做、seq 只填不用 | 已遵守 | 全模块无 `seq` / 去重 / 幂等逻辑；每次触发新建 worker 实例（沿用 L-07，绕开 `BaseThread.start()` 幂等） |

## 6. 遗留与裁决

- 图与 L1 的冲突点：自检旁路 / 能力降级（不落地，D-01）、`config.getValue` 直连（改构造注入）、图上 snake_case 回调（`load_model` / `on_recognition_result` / `on_worker_result` 等不作 API，按 L1 camelCase，映射表见 `spec-digest.md` §2）、`triggerRecognition` / `stopRecognition` → `trigger` / `stop`、运行期「阶段 0~7」编号（非实施阶段）。**未改图、未改 L1**。
- 需用户拍板事项：**「错放判定归属」与 §2.10 外部协议 docx「错放由上位机比对判定」的口径张力** —— 用户 2026-11-12 明确「只登记、不落地、不自行选边、待我拍板」；`decisions.md` 待裁决② 登记归 c5，本阶段两种口径均不落地，`validateByTable` 只查表并把 `className` / `item` / `boundItem` 原样带入应答、不比较不判错放。登记位置仅 `spec-digest.md` §5 与 `test-report.md` ⑥，`decisions.md` 原文未改。
- `decisions.md` 待裁决三条按归属**只登记、不落地、不自行裁定**：① EventCache 存废 → `d`；② 错放判定归属 → `c5`（张力见上）；③ `camera_status` 空接口默认值 +「连丢 5 条周期帧判离线」→ `c4/d`（上位机侧判定，与 `linkState` 严格区分，本阶段不实现、不设默认值）。
- 阻塞原因与解除条件：无。
- 移交后续阶段的收敛项：真实 rknn / 3s 计时器、真实图像拼接画框（`.so`）、按采集目录实读左右图、线上 JSON 键名最终映射、按 workerId 触发的下游链路、一键停机严格串行 → **d / 上板**；⑥ 未覆盖项按用户口述「按归属留后续阶段，覆盖率不引入」。

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：c5 行 `in_progress → done`（用户本条同时确认推进、不再另停一次）、证据栏补收尾工具链与举证结论、§1 当前阶段、§5 门禁记录追加 2026-11-12 c5 开工行与收尾行、时间 2026-11-12。
- `references/lessons.md` 条目号：**L-09**（业务判定归属未拍板时只做数据带出、不选边；超时/读图/查表全构造注入）。
- 项目记忆：**无**（本阶段无新增跨会话裁决或反馈；错放张力按用户指令只在阶段产物登记、待拍板，不写入记忆；精简模式、签字口径、「不再另停一次」等已有 `feedback_stage_compact_mode.md` 等条目覆盖）。
- `python-code-review` 经验库：按维护规则更新既有「源码文本断言属脆弱断言」条目命中次数（2 → 3），不重复新增；位于工作区外，不纳入 git。
- `references/decisions.md`：**未变更**（无新 D-xx；三条待裁决只在阶段产物登记，不裁定）。

## 8. 下阶段开工提示

- 下一阶段：**d**（`control/` + `app_init.py` + `main.py`）。
- 必读：`edge/docs/refactor/HANDOFF-c5.md`、`references/stage-catalog.md` d 段、`decisions.md` 命中裁决（D-01 / D-02 / D-03 全部复核）、`edge/docs/spec/INDEX.md` §2.2 与 `阶段5-7.png`。
- 特别注意：`RecognitionController.trigger(workerId, requestId) -> bool` 是识别指令唯一入口，返回 `False` 表示未初始化 / 编号非法 / worker 忙；`IRecognitionSink` 的 `onRecognitionResult(workerId, ack, requestId)` 上抛的 ack 由 `buildAck` 组装（保留字段 `type` / `requestId` / `workerId`）；`YoloEngine.instance()` 与类内 `loadModel` 幂等供 `app_init.py` 装配；NPU 并发限流仍为 `# TODO`，不得在 d 阶段借「按图实现」落地；错放判定张力仍待用户拍板，d 阶段不得自行选边。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**已签署**（用户本人 2026-11-12「我看过实现和 test-report.md 了，签字」）。
- **最终 review 结论（用户口述 2026-11-12，按原文录入，不视为代签）：**

  > 阶段 c5 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。

- [x] 配置/交付范围确认
- [x] 举证结论确认
- [x] 状态推进确认（c5 → `done`）
- 确认人 / 日期：用户本人 / 2026-11-12
