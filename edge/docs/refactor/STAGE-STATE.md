# STAGE-STATE.md — 重构阶段状态

> L4 运行态资产。本文件只记录**当前状态与证据**；阶段定义与验收项以 L1
> `edge/docs/spec/整体重构方案.txt` §5 与 `.codebuddy/skills/edge-refactor/references/stage-catalog.md` 为准。
> 路径一律以工作区根为基准（`CODEBUDDY.md` §0）；`stages/<id>/` = `edge/docs/refactor/stages/<id>/`。
> 生成日期：2026-11-10（流程配置期）。**共 9 个阶段，全部初始为 `pending`，未开工。**
> 配置期禁止写 `edge/` 下任何 `.py`；状态推进必须用户确认（规则 04）。

## 1. 状态定义

| 状态 | 含义 | 谁能改 |
| --- | --- | --- |
| `pending` | 未开工（初始态） | 初始生成 |
| `in_progress` | 用户已确认开工 | 用户确认后由 `/stage` 记录 |
| `done` | 验收全通过、用户本人签字、沉淀完成 | 用户确认后由 `/stage-done` 记录 |
| `blocked` | 阻塞，等待用户裁决 | 记录原因 + 等待用户 |

**当前阶段**：`c5`（`done`，2026-11-12 用户本人本条「我看过实现和 test-report.md 了，签字」并口述最终 review 结论，**同时**确认状态推进 `c5 → done`、不再另停一次；前置 0/a/b/c1/c2/c3/c4 均 `done`；步骤 4 举证与 `/stage-done c5` 收尾沉淀均已完成；最终结论按用户口述原文录入 `edge/docs/refactor/HANDOFF-c5.md` §9，注明「用户口述 2026-11-12」且不视为代签；下一阶段 `d` 待开工确认）
**前置门禁**：L1 契约层零自动变更；任何契约变更必须给 diff 并等用户批准。**L1 基线已变更一次且已获批准**：`edge/tests/contract/test_phase0_foundation.py` 的已批准 diff 登记在 `references/decisions.md` 附录 A 与 `HANDOFF-a.md` §4，后续 `contract-guard` 以 tag `stage-a-done` + 该附录为对比基线，不重复判定。
**必交物**：`edge/docs/refactor/stages/<id>/test-report.md`（六节）；缺件验收判红、不得收尾。
**人工闸门**：用户本人 review 代码并签字；`stage-verifier` 只举证，不代签。
**禁写解除（仅本阶段）**：阶段 c5 已收尾（2026-11-12），开工卡对白名单（`edge/modules/recognition/` 四文件 + `__init__.py` 包标记、`edge/tests/unit/test_stage_c5_recognition.py`）内 `.py` 的禁写解除**随阶段结束失效、不沿用**；`fake_recognition_engine.py` 只读复用、不在白名单；阶段 d 须重新经开工卡用户点头后才按白名单解除。白名单外 `.py`、L1 契约层、`edge/docs/spec/**` 原文与图片仍一律禁写。
**收尾状态：`done`**（阶段 0 记录：2026-11-10 执行 `/stage-done 0` 并经用户本人确认；最终 review 结论按用户口述原文录入 `HANDOFF-0.md` §9，注明「用户口述 2026-11-10」且不视为代签）。
**阶段 a 收尾状态：`done`**（2026-11-10 用户本人本条确认「阶段 a 验收通过，同意收尾」并同时确认状态推进 `a → done`；最终 review 结论按用户口述原文录入 `edge/docs/refactor/HANDOFF-a.md` §9，注明「用户口述 2026-11-10」且不视为代签；沉淀、git 提交与 annotated tag `stage-a-done` 均按用户指令完成）。

## 2. 阶段总表（共 9 个阶段）

| 阶段 | 交付范围 | 状态 | 验收项编号 | 必交物 | 证据 | 最后更新 |
| --- | --- | --- | --- | --- | --- | --- |
| `0` | 已有骨架：`exceptions.py` + `platform/` | `done` | `0-1`~`0-4` | `stages/0/test-report.md` | 必交物 `edge/docs/refactor/stages/0/test-report.md` 六节齐备（⑥ 6 行未覆盖项、未写「全部覆盖」）；`edge/docs/refactor/stages/0/spec-digest.md` 五节齐备含 `0-1` 审读表。工具链：pytest `22 passed`（报告 ④ 记 `0.21s`，收尾复核 `0.29s`，耗时波动）；ruff `All checks passed!`；mypy 既有 2 条 `untyped-decorator`、`Found 2 errors in 1 file (checked 29 source files)`、退出码 1（如实保留真实失败，不写「通过」）；collect-only `22 tests collected`、无 `FrameData` ImportError。举证表：`stage-verifier` 会话内产物，无独立落盘文件路径（待补说明，不编造）；步骤 4 完整举证表经用户确认、步骤 7 增量复核 7 项「仍成立」；结论摘要见 `edge/docs/refactor/HANDOFF-0.md` §3。`contract-guard` L1 零自动变更、无契约 diff、无需批准。用户本人 2026-11-10 review 代码并签字「我看过代码和 test-report.md 了，签字」并确认举证表。 | 2026-11-10 |
| `a` | 已有骨架：`interfaces/` + `tests/fakes/` | `done` | `a-1`~`a-4` | `stages/a/test-report.md` | 必交物 `edge/docs/refactor/stages/a/test-report.md` 六节齐备（③ 真实输出、④ 可复现命令与环境、⑥ 6 行未覆盖项及原因，未写「全部覆盖」）；`edge/docs/refactor/stages/a/spec-digest.md` 五节齐备含 `a-1` 审读表与 `a-2` 31 行签名核验表。工具链收尾复核：pytest `33 passed in 0.33s`（另有 `0.36s` / `0.32s` 实测，耗时波动，均真实）、ruff `All checks passed!`、mypy `Success: no issues found in 30 source files`（退出码均 0，附 `unused section(s)` note 非错误）；时间点 A（L1 diff 落地后）另记 `22 passed in 0.29s` / `29 source files`。`a-4` 按用户 2026-11-10 裁决按 10 处口径收口（5 个 Fake 共 10 处字段标注全部补齐），裁决写入 `spec-digest.md` §5。步骤 4 `stage-verifier` 举证表结论「证据齐备（a-1~a-4 逐条举证通过；无未通过项、无判红、无 blocked）」，会话内产物、无独立落盘路径（如实标注、不编造）。`python-code-review` 全量检视报告一次，改动均在白名单内、无空洞断言、不妨碍收尾，跨阶段遗留项已标归属（见 `HANDOFF-a.md` §3）。`contract-guard` 收尾结论「有变更 1 处 + 已由用户明确批准，不触发 blocked」：`edge/tests/contract/test_phase0_foundation.py` 的 typed 装饰器 diff 先经用户批准后落地，完整 diff 与 baseline 登记见 `HANDOFF-a.md` §4 与 `references/decisions.md` 附录 A；其余 L1 契约层与 spec 原文/PNG 零改动。用户本人 2026-11-10 review 并签字「我看过 test-report.md 了，签字」，口述最终结论「阶段 a 验收通过，同意收尾；⑥ 六项未覆盖项按归属留后续阶段，覆盖率不引入。」并同时确认状态推进 `done`（原文录入 `HANDOFF-a.md` §9，注明「用户口述 2026-11-10」、不视为代签）。沉淀：`HANDOFF-a.md`、lessons L-02 / L-03、项目记忆 topic、检视经验库、decisions 附录 A。 | 2026-11-10 |
| `b` | `base/base_thread.py`、`base_service.py` | `done` | `b-1`~`b-3` | `stages/b/test-report.md` | 2026-11-11 用户本人签字并同条确认推进 `done`；必交物 `stages/b/test-report.md` 六节齐备（④ 真实输出、⑥ 未覆盖项）、`spec-digest.md` 五节齐备、`stages/b/verification-evidence.md` 逐条举证 `b-1`~`b-3`；pytest `39 passed in 0.57s`、ruff `All checks passed!`、mypy `Success: no issues found in 34 source files`（退出码均 0）；`python-code-review` 收尾极简检视一次无阻断；`contract-guard` 相对 `stage-a-done` L1 零自动变更；沉淀 `HANDOFF-b.md`、lessons L-04、annotated tag `stage-b-done`，阶段 b 禁写解除不沿用；最终结论按用户口述 2026-11-11 原文录入 `HANDOFF-b.md` §9、不视为代签 | 2026-11-11 |
| `c1` | `infra/config_manager.py` | `done` | `c1-1`~`c1-4` | `stages/c1/test-report.md` | 2026-11-11 用户本人签字并同条确认推进 `done`（最终结论按口述原文录入 `HANDOFF-c1.md` §9、不视为代签）；必交物 `edge/docs/refactor/stages/c1/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 4 行未覆盖项及原因）、`spec-digest.md` 五节齐备、`verification-evidence.md` 步骤 4 举证表落盘（只举证不代签）；收尾复核 pytest `51 passed in 1.68s`（四步实跑 `0.63s`，耗时波动并列保留）、ruff `All checks passed!`、mypy `Success: no issues found in 37 source files`（退出码均 0）；`python-code-review` 极简检视一次、P2 非法 UTF-8 内置异常边界已在白名单内收敛并新增用例复跑全绿、P3 归 `d`；步骤 4 `stage-verifier` 举证齐备（无未通过、无判红、无 blocked）；`contract-guard` 复核相对 `stage-b-done` L1 零自动变更、已批准基线项不重复判定；沉淀 `HANDOFF-c1.md`、lessons L-05、项目记忆、检视经验库、annotated tag `stage-c1-done` | 2026-11-11 |
| `c2` | `infra/log_manager.py` | `done` | `c2-1`~`c2-4` | `stages/c2/test-report.md` | 2026-11-11 用户本人签字并同条确认推进 `done`（最终结论按口述原文录入 `HANDOFF-c2.md` §9、不视为代签）；必交物 `edge/docs/refactor/stages/c2/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 4 行未覆盖项及原因）、`spec-digest.md` 五节齐备、`verification-evidence.md` 步骤 4 举证表落盘（只举证不代签）；收尾复核 pytest `63 passed in 1.17s`（四步首轮 `1.30s`，耗时波动并列保留）、ruff `All checks passed!`、mypy `Success: no issues found in 39 source files`（退出码均 0，首轮 ruff N812 已在测试白名单内修正后复跑全绿）；`python-code-review` 收尾极简检视一次、无阻断项（P3 归 `d`）；步骤 4 `stage-verifier` 举证齐备（无未通过、无判红、无 blocked）；`contract-guard` 复核相对 `stage-c1-done` L1 零自动变更、已批准基线项不重复判定；沉淀 `HANDOFF-c2.md`、lessons L-06、项目记忆、检视经验库、annotated tag `stage-c2-done` | 2026-11-11 |
| `c3` | `modules/tcp/` 五个文件 | `done` | `c3-1`~`c3-5` | `stages/c3/test-report.md` | 2026-11-11 用户本人签字并同条确认推进 `done`（最终结论按口述原文录入 `HANDOFF-c3.md` §9、不视为代签）；必交物 `edge/docs/refactor/stages/c3/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 未覆盖项及原因，断线→重连循环改「已覆盖」）、`spec-digest.md` 五节齐备；收尾复核 pytest `9 passed in 0.58s`、ruff `All checks passed!`、mypy `Success: no issues found in 47 source files`（退出码均 0）；`python-code-review` 极简检视一次、无阻断项（P3 归 `d`）；步骤 4 `stage-verifier` 举证齐备（无未通过、无判红、无 blocked）；`contract-guard` 复核相对 `stage-c2-done` L1 零自动变更；沉淀 `HANDOFF-c3.md`、lessons L-07、检视经验库、annotated tag `stage-c3-done` | 2026-11-11 |
| `c4` | `modules/usb/` 四文件（含 `__init__.py`） | `done` | `c4-1`~`c4-4` | `stages/c4/test-report.md` | 2026-11-11 用户本人签字并同条确认推进 `done`（最终结论按口述原文录入 `HANDOFF-c4.md` §9、不视为代签）；开工前单独提交 `5f57056`（SKILL.md 收尾流程 push 规则变更，非 c4 产物）；必交物 `stages/c4/spec-digest.md` 五节、`stages/c4/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 六行未覆盖项及原因）；收尾复核 ruff `All checks passed!`、mypy `Success: no issues found in 52 source files`、pytest c4 `11 passed in 0.58s`（四步 `0.52s`）、全量 `83 passed in 2.01s`（四步 `1.70s`）、契约 `10 passed in 0.17s`（四步 `0.18s`），耗时波动并列保留；`python-code-review` 收尾极简检视一次、P1 Linux 骨架与 P2 滚动删旧均已在白名单内收敛并补举证用例、P3 归 `d`；步骤 4 `stage-verifier` 举证齐备（c4-1~c4-4 逐条通过、只举证不代签）；`contract-guard` 子代理两次不可用（API 不可达 / 无命令工具、返回「未判定」），L1 复核改由主 agent 只读 git 独立取证：相对 `stage-c3-done` 的 L1 pathspec diff 空、工作区 L1 diff 空、`edge/docs/spec/**` diff 空 → 零自动变更、无需批准，偏差如实记入 `HANDOFF-c4.md` §4；沉淀 `HANDOFF-c4.md`、lessons L-08、检视经验库、annotated tag `stage-c4-done`；阶段 c4 禁写解除不沿用 | 2026-11-11 |
| `c5` | `modules/recognition/` 四文件（含 `__init__.py`） | `done` | `c5-1`~`c5-4` | `stages/c5/test-report.md` | 2026-11-12 用户本人点头开工并确认记为 `in_progress`；白名单 `edge/modules/recognition/` 四文件 + `__init__.py` + `edge/tests/unit/test_stage_c5_recognition.py`，`fake_recognition_engine.py` 只读复用；`stages/c5/spec-digest.md` 五节、`stages/c5/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 7 行未覆盖项及原因）；四步实跑 ruff `All checks passed!`、mypy `Success: no issues found in 58 source files`、pytest c5 `11 passed in 0.08s` / 全量 `94 passed in 2.07s` / 契约 `10 passed in 0.16s`（退出码均 0）；`python-code-review` 写后极简检视一次、无阻断项（P3 静态文本断言归 `d`）；L1 基线：开工只读核验 `HEAD = stage-c4-done = f3e6a00`、L1 + spec 三段 diff 全空、工作区干净、8 tag → 零自动变更、无需批准（`contract-guard` 子代理无命令工具返回「未判定」，由主 agent 只读 git 补证，同 c4 §4）；写后复核工作区仅白名单新增 8 个文件 + 本文件修改、L1/spec 仍零改动；错放判定归属与协议口径张力按用户指令**只登记、不落地、不选边、待用户拍板**（`decisions.md` 原文未改，三条待裁决只落 `spec-digest.md` §5 与 `test-report.md` ⑥）；2026-11-12 用户本人签字「我看过实现和 test-report.md 了，签字」并**同时**确认状态推进 `c5 → done`、不再另停一次，最终结论按口述原文录入 `HANDOFF-c5.md` §9（注明「用户口述 2026-11-12」、不视为代签）；步骤 4 `stage-verifier` 只出举证表（落盘 `stages/c5/verification-evidence.md`、不含最终结论、不代签）；收尾复核 ruff `All checks passed!`、mypy `Success: no issues found in 58 source files`、pytest c5 `11 passed in 0.04s`（四步 `0.08s`）、全量 `94 passed in 1.91s`（四步 `2.07s`）、契约 `10 passed in 0.18s`（四步 `0.16s`），耗时波动并列保留；`python-code-review` 收尾极简检视一次、无阻断项（P3 归 `d`）；`contract-guard` 子代理无命令工具返回「未判定」，L1 复核改由主 agent 只读 git 独立取证零自动变更、如实记入 `HANDOFF-c5.md` §4；沉淀 `HANDOFF-c5.md`、lessons L-09、检视经验库（既有条目命中次数 2→3）、annotated tag `stage-c5-done`；阶段 c5 禁写解除不沿用 | 2026-11-12 |
| `d` | `control/` + `app_init.py` + `main.py` | `pending` | `d-1`~`d-4` | `stages/d/test-report.md` | — | 2026-11-10 |

> 说明：`0 / a` 在工作区已有实现与契约测试，但**已有文件不等于已验收**。
> 2026-11-10 判定 27 个 `.py` 为「符合新契约的骨架（非旧代码）」，故 0/a 目标是
> 「先把已有代码看懂、按契约审一遍、补上能说清楚的单测」，**不盲目重写、不以已有实现直接补验收**；
> 逐文件结论见 `references/stage-catalog.md` §0。

## 3. 验收项明细（全部 `[ ]`）

### 阶段 0 — 已有骨架：审读 + 契约核验 + 补可举证单测

- [ ] `0-1` 逐文件审读结论齐备，明确「新骨架 / 需修正」及依据
- [ ] `0-2` `EdgeError` 抛出 / 捕获与 `code.name` 日志格式正确
- [ ] `0-3` `PlatformFactory` Windows 返回 `WindowsAdapter`；Linux 分支 `NotImplementedError` + TODO
- [ ] `0-4` 双开取锁失败并立即退出；「进程锁无调用方」列入未覆盖项及原因

### 阶段 a — 已有骨架：审读 + 契约一致性核验 + 补可举证单测

- [ ] `a-1` `interfaces/` 零实现、零业务 import、全 camelCase、Doxygen 注释覆盖
- [ ] `a-2` 8 个 Fake 与 8 个接口签名逐一对齐；`fake_logger.py` 的 `FrameData` 断裂有结论与处置
- [ ] `a-3` 契约测试可收集、可执行、通过；mypy（3.9 strict）通过
- [ ] `a-4` 9 处 Fake 字段类型标注缺口有结论（补齐或列入未覆盖项并说明）

### 阶段 b — 通用生命周期

- [ ] `b-1` `stop()` 瞬间打断 `interruptibleWait`
- [ ] `b-2` join 超时强制返回
- [ ] `b-3` 重复 `stop` 幂等；`BaseService` 三件套可多态

### 阶段 c1 — 配置管理

- [ ] `c1-1` Fail-Fast：文件缺失抛 `EdgeError(CONFIG, ...)`
- [ ] `c1-2` 类型推断 int / float / bool / list / str
- [ ] `c1-3` `get(section, key, default=None)` 两分支
- [ ] `c1-4` `instance()` 双检锁，且普通构造可用于测试

### 阶段 c2 — 日志管理

- [ ] `c2-1` 唯一 BlockingQueue 异步消费，对外仅 `rx/tx/info/error`
- [ ] `c2-2` 跨天 / 超大小滚动 + 磁盘不足清理
- [ ] `c2-3` 停机清空队列并关闭 Writer 句柄
- [ ] `c2-4` `error(exception=e)` 自动附堆栈

### 阶段 c3 — TCP 模块

- [ ] `c3-1` 退避 `[1,2,4,8,16,30]` 构造注入且 `interruptibleWait` 可打断
- [ ] `c3-2` 心跳失败去重（非 UP 直接返回 `False`）
- [ ] `c3-3` 解码半包 / 粘包 + 超长帧处理
- [ ] `c3-4` `transitionTo(state, reason, source) -> bool` 并发宣告 DOWN 靠返回值去重
- [ ] `c3-5` `FakeSocket` 集成联调通过；`tcp/` 无禁词

### 阶段 c4 — USB 采集模块

- [ ] `c4-1` 4 线程并发拉起并立即返回（前置校验：已初始化且未采集中）
- [ ] `c4-2` 双路取图落盘
- [ ] `c4-3` 滚动删除（超 30% 删旧）
- [ ] `c4-4` 成功 / 失败回调互不影响；`FakeCamera` 联调通过

### 阶段 c5 — 识别模块

- [ ] `c5-1` 模型仅 `loadModel` 一次、`trigger` 立即返回
- [ ] `c5-2` 推理 3s 超时（构造注入）
- [ ] `c5-3` 空间归集 + 查表校验 + 组装 ack
- [ ] `c5-4` 回调上抛；纯函数留在 `recognition_utils.py`

### 阶段 d — 控制、装配与端到端

- [ ] `d-1` 事件分发按注入的 `asyncHandlers` 键（门面不感知业务字符串）
- [ ] `d-2` `EventCache` 按 `event_cache.enabled` 补发 / 丢弃；`seq` 只填不用
- [ ] `d-3` 一键停机严格串行 `USB → 识别 → TCP → 日志`；进程锁生效
- [ ] `d-4` Windows 端到端跑通

## 4. 全局门禁（每阶段收尾复核）

- [ ] `edge/docs/refactor/stages/<id>/spec-digest.md` 已由 `spec-reader` 产出
- [ ] **`edge/docs/refactor/stages/<id>/test-report.md` 六节齐备（缺件一律判红、不得收尾）**
- [ ] 测试函数上方有验收项编号注释；无空洞断言；无为变绿而改被测代码
- [ ] **用户本人已 review 代码并签字**（`stage-verifier` 只举证，不许代签）
- [ ] `ruff` / `mypy`（3.9 strict） / `pytest` + 契约测试证据齐备
- [ ] 写过或改过 Python → `python-code-review` 检视报告一次
- [ ] L1 契约层零自动变更（`contract-guard` 结论）
- [ ] D-01 / D-02 / D-03 逐条已遵守
- [ ] handoff 已产出、`lessons.md` 与项目记忆已按协议沉淀

## 5. 门禁记录

| 日期 | 阶段 | 事件 | 结论 | 用户确认 |
| --- | --- | --- | --- | --- |
| 2026-11-10 | 全部 | 流程配置初始化，9 阶段全 `pending` | 待用户确认配置清单 | 待确认 |
| 2026-11-10 | 0 / a | 27 个 `.py` 契约判定：新骨架、非旧代码 | 目标改为审读 + 契约核验 + 补可举证单测 | 待确认 |
| 2026-11-10 | 0 | 开工确认卡经用户点头，`pending → in_progress`；禁写 `.py` 仅对阶段 0 白名单解除且不沿用；A5 落点定为 `edge/tests/unit/`（只新增文件、不改既有断言，后续阶段同理）；资料口径按「阶段 0 / #22」 | L1 基线无变更（`git status --porcelain` 空、`git diff --name-status governance-v1 HEAD` 空、tag = HEAD = `a71d97f`）；四步执行中，人工闸门待用户本人签字 | 已确认（用户本人） |
| 2026-11-10 | 0 | 收尾事件：用户本人 review 代码并签字「我看过代码和 test-report.md 了，签字」并确认步骤 4 完整举证表；步骤 7 `stage-verifier` 增量复核 7 项「仍成立」；`contract-guard` 复核 L1 零自动变更；执行 `/stage-done 0` 收尾沉淀（handoff / STAGE-STATE 证据栏 / lessons L-01 / 项目记忆 / 检视经验库） | 必交物 `edge/docs/refactor/stages/0/test-report.md` 六节齐备，举证齐备；本 agent 不决定状态推进、不代签最终 review 结论；建议状态待用户确认推进 `done`，当前状态列保持 `in_progress`、§3 复选框保持 `[ ]` | 最终 review 结论留空，待用户本人填写 |
| 2026-11-10 | 0 | 用户本人确认「阶段 0 验收通过，状态推进为 done」，最终 review 结论按本条口述原文录入 `edge/docs/refactor/HANDOFF-0.md` §9（注明「用户口述 2026-11-10」，不视为代签）；三个复选框、确认人与日期一并填写；覆盖率不引入，保持现状 | 状态 `in_progress → done`；结论为用户本人本条口述、助手按原文照录，未代签；L1 契约层零自动变更结论不变 | 已确认（用户本人） |
| 2026-11-10 | a | 开工确认卡经用户点头，`pending → in_progress`；四项裁决：① `a-3` 选候选 A，先出 `edge/tests/contract/test_phase0_foundation.py` 完整 diff（变更前后 + 影响面 + 受影响测试/Fake）并停下等批准，批准后才动，禁删用例 / 加 skip 标记 / 整体关闭错误码，不改 `edge/pyproject.toml`；② `a-4` 9 处 Fake 字段类型标注在白名单内补齐，不列为未覆盖项；③ `patch.object(sys, "platform")` 只出复核结论写入 `edge/docs/refactor/stages/a/spec-digest.md`，不改上一阶段任何产物文件；④ 工作区 `HANDOFF-0.md` 未提交改动不处理、不算阶段 a 改动，收尾时随本阶段提交 | L1 基线无变更（按 L1 pathspec 的 `git diff --name-only governance-v1 HEAD`、`git diff --name-only governance-v1`、`git status --porcelain` 三段输出全空；`contract-guard` 静态核验 17 个契约文件齐备、无待批准契约 diff）；本轮仅记录状态并输出待批准 diff，四步待 diff 批准后启动；人工闸门待用户本人签字 | 已确认（用户本人） |
| 2026-11-10 | a | 用户本人明确批准 L1 完整 diff 并落地；追加裁决「第 10 处 `lockResult` 一并补齐字段级标注、按 10 处口径收口，不再纠结 9/10 差异」「不用重写测试，由主 agent 按六节模板直接补 `test-report.md`」；三项工具链全绿 | L1 diff 落地后立即实跑：pytest `22 passed in 0.29s`、ruff `All checks passed!`、mypy `Success: no issues found in 29 source files`（退出码均 0）；5 个 Fake 共 10 处字段标注补齐；必交物 `stages/a/test-report.md` 六节齐备；收尾复核 `33 passed` / mypy `30 source files` | 已确认（用户本人） |
| 2026-11-10 | a | 收尾事件：用户本人 review 并签字「我看过 test-report.md 了，签字」，口述最终 review 结论「阶段 a 验收通过，同意收尾；⑥ 六项未覆盖项按归属留后续阶段，覆盖率不引入。」并**同时确认状态推进 `a → done`**；步骤 4 `stage-verifier` 只出举证表（证据齐备、不含最终结论、不代签）；执行 `/stage-done a`：`python-code-review` 全量检视一次、`contract-guard` 复核（有变更 1 处 + 已批准、不阻断）、写 `HANDOFF-a.md`、更新本文件证据栏与状态、追加 lessons L-02 / L-03、登记 `references/decisions.md` 附录 A（首次经用户批准的 L1 变更 baseline）、同步项目记忆与检视经验库 | 必交物 `edge/docs/refactor/stages/a/test-report.md` 六节齐备；`a-1`~`a-4` 逐条举证通过；L1 变更先 diff 后批准再落地、硬要求已遵守；状态 `in_progress → done` 由用户本条明确确认，未另停一次；结论为用户本人本条口述、助手按原文照录，未代签；所有文档写入均在 git 提交之前完成 | 已确认（用户本人） |
| 2026-11-11 | c1 | 开工确认卡经用户点头，`pending → in_progress`；命名口径再钉：`get(section, key, default=None)` / `instance()`，禁 `getValue` / `getInstance` / snake_case，图只取 Fail-Fast、类型推断、default 两分支、双检锁语义；`edge/infra/__init__.py` 保留；禁写 `.py` 仅对本阶段白名单解除、不沿用；四步由主 agent 连续执行、极简文档 | `stages/c1/spec-digest.md` 五节、`stages/c1/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 未覆盖项及原因）；pytest `51 passed in 0.63s`、ruff `All checks passed!`、mypy `Success: no issues found in 37 source files`（退出码均 0）；`python-code-review` 极简检视一次、无阻断项；L1 基线相对 `stage-b-done` 无变更；步骤 4 未进入，停在人工闸门 | 开工已确认（用户本人）；代码 review 签字待用户本人 |
| 2026-11-11 | c1 | 收尾事件：用户本人 review 并签字「我看过实现和 test-report.md 了，签字」，口述最终 review 结论「阶段 c1 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」并**同时确认状态推进 `c1 → done`**；步骤 4 `stage-verifier` 只出举证表（落盘 `stages/c1/verification-evidence.md`，证据齐备、不含最终结论、不代签）；执行 `/stage-done c1`：`python-code-review` 极简检视一次、`contract-guard` 复核 L1 零自动变更、写 `HANDOFF-c1.md`、更新本文件证据栏与状态、追加 lessons L-05、同步项目记忆与检视经验库 | 必交物 `edge/docs/refactor/stages/c1/test-report.md` 六节齐备；`c1-1`~`c1-4` 逐条举证通过；状态 `in_progress → done` 由用户本条明确确认，未另停一次；结论为用户本人本条口述、助手按原文照录，未代签；所有文档写入均在 git 提交之前完成，`.codebuddy` 下 lessons.md 用 `git add -f` 精确纳入、不改 `.gitignore`；提交后打 annotated tag `stage-c1-done` | 已确认（用户本人） |
| 2026-11-11 | c2 | 开工确认卡经用户点头，`pending → in_progress`；API 口径钉死（ILogger 仅 `rx/tx/info/error` 四方法、`error(msg, exception=None)`、无 `init(config)`、不新增 `FrameData`、rx/tx 的 data = `dict[str, object] \| bytes`），图只取队列/logMode 路由/文件滚动/磁盘清理/停机清空队列语义、不把图上方法名当 API；极简文档不改任何规则文件；禁写 `.py` 仅对本阶段白名单解除、不沿用；四步由主 agent 连续执行 | `stages/c2/spec-digest.md` 五节、`stages/c2/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 未覆盖项及原因）；pytest `63 passed in 1.17s`、ruff `All checks passed!`、mypy `Success: no issues found in 39 source files`（退出码均 0，首轮 ruff N812 已在测试白名单内修正）；`python-code-review` 极简检视一次、无阻断项；L1 基线相对 `stage-c1-done` 无变更；四步完成、停在人工闸门 | 开工已确认（用户本人）；代码 review 签字待用户本人 |
| 2026-11-11 | c2 | 收尾事件：用户本人 review 并签字「我看过实现和 test-report.md 了，签字」，口述最终 review 结论「阶段 c2 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」并**同时确认状态推进 `c2 → done`**；步骤 4 `stage-verifier` 只出举证表（落盘 `stages/c2/verification-evidence.md`，证据齐备、不含最终结论、不代签）；执行 `/stage-done c2`：`python-code-review` 收尾极简检视一次、`contract-guard` 复核 L1 零自动变更、写 `HANDOFF-c2.md`、更新本文件证据栏与状态、追加 lessons L-06、同步项目记忆与检视经验库 | 必交物 `edge/docs/refactor/stages/c2/test-report.md` 六节齐备；`c2-1`~`c2-4` 逐条举证通过；状态 `in_progress → done` 由用户本条明确确认，未另停一次；结论为用户本人本条口述、助手按原文照录，未代签；所有文档写入均在 git 提交之前完成，用户明确的新补 docx 仅随提交纳入、不读取/不登记/不裁决，`.codebuddy` 下 lessons.md 用 `git add -f` 精确纳入、不改 `.gitignore`；提交后打 annotated tag `stage-c2-done`、确认 git status 干净 | 已确认（用户本人） |
| 2026-11-11 | c3 | 收尾事件：用户本人 review 并签字「我看过实现和 test-report.md 了，签字」，口述最终 review 结论「阶段 c3 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」并**同时确认状态推进 `c3 → done`**；步骤 4 `stage-verifier` 只出举证表（落盘 `HANDOFF-c3.md` §3，证据齐备、不含最终结论、不代签）；执行 `/stage-done c3`：`python-code-review` 收尾极简检视一次、`contract-guard` 复核 L1 零自动变更、写 `HANDOFF-c3.md`、更新本文件证据栏与状态、追加 lessons L-07、同步检视经验库 | 必交物 `edge/docs/refactor/stages/c3/test-report.md` 六节齐备；`c3-1`~`c3-5` 逐条举证通过（另含 c3-修复回归用例覆盖 UP→DOWN→再 UP）；状态 `in_progress → done` 由用户本条明确确认，未另停一次；结论为用户本人本条口述、助手按原文照录，未代签；所有文档写入均在 git 提交之前完成，`.codebuddy` 下 decisions.md / lessons.md / accumulated-lessons.md 用 `git add -f` 精确纳入、不改 `.gitignore`；提交后打 annotated tag `stage-c3-done`、确认 git status 干净 | 已确认（用户本人） |
| 2026-11-11 | c4 | 开工确认卡经用户点头，`pending → in_progress`；白名单为 `edge/modules/usb/` 四文件（用户补充 `__init__.py`，按 L1 §2）与 `edge/tests/unit/test_stage_c4_usb.py`，禁写 `.py` 仅对本阶段白名单解除、不沿用；开工前把 SKILL.md 收尾流程 push 规则变更用 `git add -f` 单独提交（`5f57056`，注明流程规则变更、非 c4 产物），工作区干净后进四步；自检按 D-01 只留空接口、不实现/不新增自检线程/不做能力降级，图上 snake_case 回调不作 API 按 L1 camelCase，`decisions.md` 待裁决三条按归属只登记不落地不裁定；四步由主 agent 连续执行、极简文档 | 必交物 `stages/c4/spec-digest.md` 五节、`stages/c4/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 未覆盖项及原因）；ruff `All checks passed!`、mypy `Success: no issues found in 52 source files`、pytest c4 `11 passed in 0.52s`、全量 `83 passed in 1.70s`、契约 `10 passed in 0.18s`；`python-code-review` 检视一次无阻断项；`contract-guard` 子代理 API 不可达，L1 基线改由主 agent 用只读 git 核验（相对 `stage-c3-done` 零变更）；四步完成、**停在人工闸门待用户本人签字**，未进步骤 4、未执行 `/stage-done c4` | 开工已确认（用户本人）；代码 review 签字待用户本人 |
| 2026-11-11 | c4 | 收尾事件：用户本人 review 并签字「我看过实现和 test-report.md 了，签字」，口述最终 review 结论「阶段 c4 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」并**同时确认状态推进 `c4 → done`**；步骤 4 `stage-verifier` 只出举证表（落盘 `HANDOFF-c4.md` §3，证据齐备、不含最终结论、不代签）；执行 `/stage-done c4`：`python-code-review` 收尾极简检视一次、`contract-guard` 子代理两次不可用（API 不可达 / 无命令工具），L1 复核改由主 agent 只读 git 独立取证零自动变更、写 `HANDOFF-c4.md`、更新本文件证据栏与状态、追加 lessons L-08、同步检视经验库 | 必交物 `edge/docs/refactor/stages/c4/test-report.md` 六节齐备；`c4-1`~`c4-4` 逐条举证通过；状态 `in_progress → done` 由用户本条明确确认，未另停一次；结论为用户本人本条口述、助手按原文照录，未代签；所有文档写入均在 git 提交之前完成，`.codebuddy` 下 lessons.md 用 `git add -f` 精确纳入、不改 `.gitignore`；提交后打 annotated tag `stage-c4-done`、`git push origin main` 与 `git push origin --tags`、确认 git status 干净与远端 tag 齐全 | 已确认（用户本人） |
| 2026-11-12 | c5 | 开工确认卡（2026-11-11 出，≤15 行）经用户点头，`pending → in_progress`；白名单 `edge/modules/recognition/` 四文件 + `__init__.py` 包标记 + `edge/tests/unit/test_stage_c5_recognition.py`，`fake_recognition_engine.py` 只读复用，禁写 `.py` 仅对本次白名单解除、不沿用；适用 D-01 / D-02、`trigger()` 内 NPU 并发限流仅留 TODO、图上 snake_case 回调不作 API 按 L1 camelCase、禁止跨模块 import `usb/`、禁止 Sink 回调内阻塞 IO、不改 L1 与 spec 原文；错放判定归属与协议「上位机比对判定」口径张力**只登记、不落地、不自行选边、待用户拍板**，`decisions.md` 原文不改，三条待裁决只落 `spec-digest.md` §5 与 `test-report.md` ⑥；四步由主 agent 连续执行、极简文档（④ 真实命令与输出、⑥ 未覆盖项及原因不省） | 必交物 `stages/c5/spec-digest.md` 五节、`stages/c5/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 7 行未覆盖项及原因）；ruff `All checks passed!`、mypy `Success: no issues found in 58 source files`、pytest c5 `11 passed in 0.08s`、全量 `94 passed in 2.07s`、契约 `10 passed in 0.16s`（退出码均 0）；`python-code-review` 写后极简检视一次无阻断项（P3 静态文本断言归 `d`）；`contract-guard` 子代理无命令执行工具返回「未判定」，L1 基线改由主 agent 只读 git 核验（`HEAD = stage-c4-done = f3e6a00`、三段 diff 全空、工作区干净、8 tag → 零自动变更），写后复核工作区仅白名单 8 个新文件 + 本文件修改、L1/spec 仍零改动；**四步完成、停在人工闸门待用户本人 review 签字**，未进步骤 4、未执行 `/stage-done c5`、未代签、未提交未打 tag | 开工已确认（用户本人）；代码 review 签字待用户本人 |
| 2026-11-12 | c5 | 收尾事件：用户本人 review 并签字「我看过实现和 test-report.md 了，签字」，口述最终 review 结论「阶段 c5 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」并**同时确认状态推进 `c5 → done`**；步骤 4 `stage-verifier` 只出举证表（落盘 `stages/c5/verification-evidence.md`，证据齐备、不含最终结论、不代签）；执行 `/stage-done c5`：`python-code-review` 收尾极简检视一次、`contract-guard` 子代理无命令工具返回「未判定」，L1 复核改由主 agent 只读 git 独立取证零自动变更（如实记入 `HANDOFF-c5.md` §4）、写 `HANDOFF-c5.md`、更新本文件证据栏与状态、追加 lessons L-09、同步检视经验库（既有条目命中次数 2→3） | 必交物 `edge/docs/refactor/stages/c5/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 7 行未覆盖项及原因）、`stages/c5/spec-digest.md` 五节齐备；`c5-1`~`c5-4` 逐条举证通过；状态 `in_progress → done` 由用户本条明确确认，未另停一次；结论为用户本人本条口述、助手按原文照录，未代签；所有文档写入均在 git 提交之前完成，`.codebuddy` 下 lessons.md 用 `git add -f` 精确纳入、不改 `.gitignore`；提交后打 annotated tag `stage-c5-done`、`git push origin main` 与 `git push origin --tags`、确认 git status 干净与远端 tag 齐全 | 已确认（用户本人） |

## 6. 使用协议

- 本文件由 `/stage`（只读核对）与 `/stage-done`（写入证据）驱动；状态由用户确认后推进。
- 验收项编号与措辞变更 = 阶段定义变更，须走 L1 diff + 用户批准；不得静默修改。
- 证据栏只记可复核内容（命令、输出、测试名、`test-report.md` 路径），不写「应该通过」。
- 阻塞时状态写 `blocked` 并在 §5 记录原因，等待用户裁决。
