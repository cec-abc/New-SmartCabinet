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

**当前阶段**：`0`（`done`，2026-11-10 用户本人确认验收通过并录入最终 review 结论）
**前置门禁**：L1 契约层零自动变更；任何契约变更必须给 diff 并等用户批准。
**必交物**：`edge/docs/refactor/stages/<id>/test-report.md`（六节）；缺件验收判红、不得收尾。
**人工闸门**：用户本人 review 代码并签字；`stage-verifier` 只举证，不代签。
**禁写解除（仅本阶段）**：2026-11-10 开工卡经用户点头后，仅对阶段 0 白名单内 `.py` 解除；白名单外 `.py`、L1 契约层、`edge/docs/spec/**` 原文与图片仍一律禁写；**本许可不沿用**至阶段 a 及之后。
**收尾状态：`done`**（2026-11-10 执行 `/stage-done 0` 收尾沉淀并经用户本人确认验收通过；最终 review 结论按用户口述原文录入 `edge/docs/refactor/HANDOFF-0.md` §9，注明「用户口述 2026-11-10」且不视为代签；状态推进经用户明确确认）。

## 2. 阶段总表（共 9 个阶段）

| 阶段 | 交付范围 | 状态 | 验收项编号 | 必交物 | 证据 | 最后更新 |
| --- | --- | --- | --- | --- | --- | --- |
| `0` | 已有骨架：`exceptions.py` + `platform/` | `done` | `0-1`~`0-4` | `stages/0/test-report.md` | 必交物 `edge/docs/refactor/stages/0/test-report.md` 六节齐备（⑥ 6 行未覆盖项、未写「全部覆盖」）；`edge/docs/refactor/stages/0/spec-digest.md` 五节齐备含 `0-1` 审读表。工具链：pytest `22 passed`（报告 ④ 记 `0.21s`，收尾复核 `0.29s`，耗时波动）；ruff `All checks passed!`；mypy 既有 2 条 `untyped-decorator`、`Found 2 errors in 1 file (checked 29 source files)`、退出码 1（如实保留真实失败，不写「通过」）；collect-only `22 tests collected`、无 `FrameData` ImportError。举证表：`stage-verifier` 会话内产物，无独立落盘文件路径（待补说明，不编造）；步骤 4 完整举证表经用户确认、步骤 7 增量复核 7 项「仍成立」；结论摘要见 `edge/docs/refactor/HANDOFF-0.md` §3。`contract-guard` L1 零自动变更、无契约 diff、无需批准。用户本人 2026-11-10 review 代码并签字「我看过代码和 test-report.md 了，签字」并确认举证表。 | 2026-11-10 |
| `a` | 已有骨架：`interfaces/` + `tests/fakes/` | `pending` | `a-1`~`a-4` | `stages/a/test-report.md` | — | 2026-11-10 |
| `b` | `base/base_thread.py`、`base_service.py` | `pending` | `b-1`~`b-3` | `stages/b/test-report.md` | — | 2026-11-10 |
| `c1` | `infra/config_manager.py` | `pending` | `c1-1`~`c1-4` | `stages/c1/test-report.md` | — | 2026-11-10 |
| `c2` | `infra/log_manager.py` | `pending` | `c2-1`~`c2-4` | `stages/c2/test-report.md` | — | 2026-11-10 |
| `c3` | `modules/tcp/` 五个文件 | `pending` | `c3-1`~`c3-5` | `stages/c3/test-report.md` | — | 2026-11-10 |
| `c4` | `modules/usb/` 三个文件 | `pending` | `c4-1`~`c4-4` | `stages/c4/test-report.md` | — | 2026-11-10 |
| `c5` | `modules/recognition/` 四个文件 | `pending` | `c5-1`~`c5-4` | `stages/c5/test-report.md` | — | 2026-11-10 |
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

## 6. 使用协议

- 本文件由 `/stage`（只读核对）与 `/stage-done`（写入证据）驱动；状态由用户确认后推进。
- 验收项编号与措辞变更 = 阶段定义变更，须走 L1 diff + 用户批准；不得静默修改。
- 证据栏只记可复核内容（命令、输出、测试名、`test-report.md` 路径），不写「应该通过」。
- 阻塞时状态写 `blocked` 并在 §5 记录原因，等待用户裁决。
