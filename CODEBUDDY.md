# CODEBUDDY.md

> 本文件是工作区根的流程总览（≤120 行），只做索引与门禁，不复述规范全文。
> 工作区根 = 本文件所在目录；代码根 = `edge/`；本文件属于 **L3 流程配置**。

## 0. 路径基准（2026-11-10 已确认）

- **PyCharm 项目根 = 工作区根 `f:\new zhineng`**：`.idea/` 位于该目录，
  `new zhineng.iml` 的 content root 为 `$MODULE_DIR$`，`$PROJECT_DIR$` 即工作区根；
  `edge.iml` 只是同一项目下的附加 module。因此 `CODEBUDDY.md` 与 `.codebuddy/` 放在工作区根即可生效。
  若误把 `edge/` 单独打开成项目，配置不会生效，须重新打开 `f:\new zhineng`。
- **全部配置中的相对路径一律以工作区根为基准**：spec 写 `edge/docs/spec/...`，
  状态资产写 `edge/docs/refactor/...`，长资料写 `.codebuddy/skills/edge-refactor/references/...`。
  禁止混用 `docs/spec/...`（以 `edge/` 为基准）与 `edge/docs/spec/...`。
- 约定简写：`references/<file>` = `.codebuddy/skills/edge-refactor/references/<file>`；
  `stages/<id>/` = `edge/docs/refactor/stages/<id>/`。
- 唯一例外：`edge/docs/spec/INDEX.md` 表格内 `./...` 相对该索引文件自身（文件头已注明）。

## 1. 目标

把 `dual_crop_stitch/` 的平铺实现，按 2026-11-09 定稿的**方案 A**重构为 `edge/` 分层工程：
`main → app_init → control → modules/*/门面 → base/interfaces/platform/infra`。
Windows 先跑通，麒麟 Linux / RK3588 留骨架接口（`NotImplementedError` + TODO）上板再补；源码 + venv，不打包。
重构按固定实施阶段 `0 → a → b → c1 → c2 → c3 → c4 → c5 → d` 逐步递进，一阶段一验收。

## 2. 权威优先级（从高到低）

| 级别 | 内容 | 可否自动修改 |
| --- | --- | --- |
| 0 | 用户当次指令、已批准的契约 diff、新增/变更裁决 | — |
| 1 | **L1 契约层**（见 §3） | **禁止**；变更须先给 diff 并等用户批准 |
| 2 | `.codebuddy/rules/` 其余 always 规则（本次新增 4 条） | 仅按用户要求配置，不擅自放宽 |
| 3 | **L2 规格图资产**（`edge/docs/spec/**`） | 禁止；只读语义，不改原文/图片 |
| 4 | **L3 索引与流程配置**（`CODEBUDDY.md`、`INDEX.md`、skill/commands/agents） | 可维护，改动需登记进 handoff |
| 5 | **L4 状态与记忆**（`STAGE-STATE.md`、handoff、`lessons.md`、项目记忆） | 按门禁协议写入 |

裁决规则：**文本 > 图，方案 A > 旧流程时序图，camelCase > 旧图 snake_case**。
图中「阶段 0~7」是运行期业务时序编号，与实施阶段 `0~d` 无关，禁止混用。
详见规则 `01_naming_authority.mdc`（NAMING_AUTHORITY）与 `references/glossary.md`。

## 3. 四层资产索引

### L1 契约层（只读，变更需 diff + 批准）

| 资产 | 职责 |
| --- | --- |
| `edge/docs/spec/整体重构方案.txt` | 决策、目录、逐文件职责、依赖方向、阶段与验收的唯一权威 |
| `edge/docs/spec/编码规范规则.txt` | 编码/注释/异常/日志/线程/并发硬约束全文 |
| `.codebuddy/rules/编码规范.mdc` | 与上条同源的 always 规则（用户 2026-11-09 修订版），**保持原样** |
| `edge/interfaces/*.py` | 接口契约：零实现、零业务 import；新增接口须同步 `tests/fakes/` |
| `edge/exceptions.py` | 唯一 `EdgeError` + `ErrorCode` 枚举 |
| `edge/pyproject.toml` | mypy / ruff / pytest 工具链约束 |
| `edge/tests/contract/*` | 契约测试守卫：可新增用例，不得静默修改既有断言 |

### L2 规格图资产（只读语义）

| 资产 | 职责 |
| --- | --- |
| `edge/docs/spec/**/*.txt` | 类图 / 流程图 / 时序图源码，按模块表达运行期语义 |
| `edge/docs/spec/**/*.png` | 上述源码的位图快照，只取语义，不转录文字 |
| `edge/docs/spec/INDEX.md` | 逐文件登记（模块 / 图类型 / 对应阶段 / 关键语义），**L3 索引** |

### L3 流程配置（可维护）

| 资产 | 职责 |
| --- | --- |
| `CODEBUDDY.md` | 本文件：目标、路径基准、权威优先级、四层索引、阶段清单 |
| `.codebuddy/rules/0*.mdc` | 4 条 always：命名裁决 / 编码硬约束 / 依赖目录 / 阶段门禁与记忆 |
| `.codebuddy/rules/ref_*.mdc`、`test-visibility.mdc` | Agent Requested：资料路由、命名映射、测试透明化 |
| `.codebuddy/skills/edge-refactor/SKILL.md` | 阶段开工 / 收尾 / 沉淀工作流与 references 索引 |
| `.codebuddy/skills/edge-refactor/references/` | `decisions.md`、`glossary.md`、`diagram-index.md`、`stage-catalog.md`、`lessons.md` |
| `.codebuddy/commands/stage.md`、`stage-done.md` | 阶段开工 / 收尾命令 |
| `.codebuddy/agents/` | 7 个单一职责 agent：开工官 / 契约守卫 / 验收官 / 沉淀官 / 资料消化官 / 实现官 / 测试官 |

> always 规则共 **5 条**（新增 4 + 原有 `编码规范.mdc`），符合官方 3–5 条建议上限；
> `test-visibility.mdc` 为 Agent Requested，其强制力由规则 04 的收尾门禁兜底。

### L4 状态与记忆（按门禁写入）

| 资产 | 职责 |
| --- | --- |
| `edge/docs/refactor/STAGE-STATE.md` | 9 个阶段状态与验收项，初始全 `pending` |
| `edge/docs/refactor/HANDOFF-TEMPLATE.md` | 阶段移交模板；每阶段收尾产出一份 handoff |
| `edge/docs/refactor/stages/<id>/` | `spec-digest.md`（开工）+ `test-report.md`（收尾必交物） |
| `references/lessons.md` | 跨阶段可复用经验，不写一次性缺陷细节 |
| 项目记忆 `MEMORY.md` | 只存跨会话有效的裁决 / 反馈 / 项目背景 |

## 4. 阶段清单

**共 9 个阶段**：`0 / a / b / c1 / c2 / c3 / c4 / c5 / d`，顺序固定，不跳阶、不合并、不另起平行目录。

| 阶段 | 交付范围 | 一句话验收 |
| --- | --- | --- |
| `0` | 已有骨架：`exceptions.py` + `platform/` | 审读 + 契约核验 + 可举证单测；双开拿锁失败、`PlatformFactory` 分支 |
| `a` | 已有骨架：`interfaces/` + `tests/fakes/` | 审读 + 契约一致性核验 + 可举证单测；Fake 与接口一致、mypy 通过 |
| `b` | `base/base_thread.py`、`base_service.py` | `interruptibleWait` 瞬断、join 超时返回、重复 stop 幂等 |
| `c1` | `infra/config_manager.py` | Fail-Fast、类型推断、`get(default=)` 两分支、双检锁 |
| `c2` | `infra/log_manager.py` | 异步队列、滚动、停机清空、`error(exception=e)` |
| `c3` | `modules/tcp/` | 退避重连、心跳失败去重、半包粘包、`transitionTo` 并发去重 |
| `c4` | `modules/usb/` | 4 线程并发拉起并立即返回、落盘、滚动删除 |
| `c5` | `modules/recognition/` | 3s 超时、组帧、回调 |
| `d` | `control/` + `app_init.py` + `main.py` | 事件分发、EventCache 补发/丢弃、停机严格串行、Windows 端到端 |

0/a 的现有 27 个 `.py` 判定为**符合新契约的骨架（非旧代码）**，故目标是
「先把已有代码看懂、按契约审一遍、补上能说清楚的单测」，**不盲目重写、不以已有实现直接补验收**；
逐文件结论见 `references/stage-catalog.md` §0。阶段完整定义见 `references/stage-catalog.md` 与 `STAGE-STATE.md`。

## 5. 门禁速记

- 执行编排（四步 + 人工闸门）：`spec-reader` → `implementer` → `test-writer` →
  **用户本人 review 代码并签字** → `stage-verifier`；详见 `commands/stage.md`。
- 每阶段必交 `edge/docs/refactor/stages/<id>/test-report.md`（六节），缺件验收判红、不得收尾。
- `stage-verifier` 只出举证表；**最终 review 结论由用户本人签字，任何 agent 不许代签**。
- `/stage <阶段>`：只读开工核对；`/stage-done <阶段>`：验收 + 沉淀 + 状态推进。
- 未获用户确认不得把阶段改为 `in_progress` / `done`；本轮配置期状态全 `pending`。
- **硬要求：不得自动修改 L1 契约层；任何契约变更必须给 diff 并等用户批准。**
- 本轮配置期**禁止写入 `edge/` 下任何 `.py`**；只允许 `edge/docs/**` 的 `.md`。
- 写完/改完 Python 代码必须调用 `python-code-review` 检视一次并沉淀；检视项按阶段逐步收敛。
- 三条已定裁决（自检留空接口 / 非 UP 不启其他线程 / 去重不做且 seq 只填不用）见 `references/decisions.md`。
