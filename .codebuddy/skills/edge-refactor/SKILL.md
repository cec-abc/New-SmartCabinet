---
name: edge-refactor
description: RK3588 边缘计算重构流程技能。重构阶段开工、收尾、沉淀时必须使用；规定开工读什么、收尾写什么、沉淀怎么写、什么绝对不能自动改。长资料只通过 references/ 索引按需加载，本文件不重复其内容。
---

# edge-refactor

## 1. 适用边界

- 适用于方案 A 实施阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d`（**共 9 个阶段**）的开工、收尾与沉淀。
- 同时适用于配置期（只做流程配置，不写 `edge/` 下 `.py`）与实现期（按已确认范围写代码）。
- 不适用于：写单个函数、回答概念问题、与阶段无关的临时调试。
- 触发命令：`/stage <阶段>`、`/stage-done <阶段>`。
- 路径一律以工作区根为基准（见 `CODEBUDDY.md` §0）：`references/<file>` 与
  `stages/<id>/` 是两个约定简写，不另起 `docs/spec/...` 基准。

## 2. 工作流总览

```
开工（只读） → 用户确认 → 四步执行 → 人工闸门（用户签字） → 收尾（验收 + 记录） → 沉淀 → 用户确认状态
```

四步与闸门由 `commands/stage.md` 编排：`spec-reader` → `implementer` → `test-writer`
→ **用户本人 review 并签字** → `stage-verifier`。
任一步缺用户确认，就停在那一步；不推测、不代用户批准。

## 3. 开工工作流：开工读什么

按顺序读，不跳步：

1. `CODEBUDDY.md` §0 路径基准、§2 权威优先级、§4 阶段清单。
2. always 规则 `01_naming_authority.mdc` / `02_coding_hard_constraints.mdc` /
   `03_dependency_and_layout.mdc` / `04_stage_gate_and_memory.mdc`；按 description 判断是否加载
   Agent Requested 规则 `ref_spec_semantics.mdc`、`ref_legacy_mapping.mdc`、`test-visibility.mdc`。
3. `references/stage-catalog.md` → 本阶段交付范围与验收项（含 §0 现状判定）。
4. `edge/docs/refactor/STAGE-STATE.md` → 当前状态；只有 `pending` 才具备开工条件。
5. `references/decisions.md` → 本阶段适用的裁决。
6. `references/diagram-index.md` → 再按它指向 `edge/docs/spec/INDEX.md` 定位本阶段 spec 资料。
7. L1 契约层中与本阶段相关的条目（**只读**，不修改）。
8. 上一阶段 handoff 与 `references/lessons.md`。

产出（只输出，不写文件）：

- **开工清单**：交付文件白名单、验收项、对应 spec 资料、适用裁决、明确禁止事项。
- **L1 基线**：`无变更` 或 `有变更 + 完整 diff`；有变更即阻断，转入等待批准。
- **待确认项**：必须用户拍板的问题；没有就写「无」。

开工阶段禁止：写任何 `.py`、改 `STAGE-STATE` 状态、改 spec、改 L1。

## 4. 收尾工作流：收尾写什么

前置：用户已确认开工、四步执行完毕、**用户本人已 review 代码并签字**、验收项可逐条举证。

1. 确认 `edge/docs/refactor/stages/<id>/test-report.md` 存在且六节齐备；
   **缺件即验收判红、不得收尾**（见 `test-visibility.mdc`）。
2. 跑 `ruff` / `mypy`（3.9 strict） / `pytest` 与契约测试，保留命令与输出。
3. 写过或改过 Python → 调用 `python-code-review` 检视一次，输出报告，
   标明跨阶段遗留项及归属阶段；不得用问题清单阻断收尾。
4. 调用 `contract-guard` 复核 L1 **零自动变更**；若确需契约变更，
   附 diff 并**保持「等待批准」状态**，不得落地。
5. 调用 `stage-verifier`：**只出举证表**，不下最终 review 结论、不代用户签字。
6. 调用 `memory-steward`：按 `edge/docs/refactor/HANDOFF-TEMPLATE.md` 写 handoff、
   更新 `STAGE-STATE.md` 证据栏与更新时间（状态标「待用户确认」）、追加 `lessons.md`、
   写入项目记忆与检视经验库。
7. 本地提交并打 annotated tag 之后，推送远端：`git push origin main` 与 `git push origin --tags`
   （推全部 tag）。推不动如实报告并停下；不 force、不改 git 配置、不重写历史。
8. 输出收尾结论并**停下等待用户确认**；确认后才把状态改为 `done`。

写入边界：只写 L3 / L4 资产与本阶段已确认范围内的实现文件；不写 L1、不写 spec 原文/图片。

## 5. 沉淀工作流：沉淀怎么写

1. `references/lessons.md`：按模板追加一条，字段「阶段 / 触发 / 结论 / 是否上升为规则或记忆」；
   只写可复用结论，不写一次性缺陷细节。
2. 项目记忆：仅存跨会话有效的用户裁决、反馈、项目背景。先查 `MEMORY.md` 去重，
   再建独立 topic 文件 + 一行索引；相对日期换算成绝对日期。
3. `python-code-review` 经验库：按该技能第 6 步更新。
4. 新裁决或裁决变更：更新 `references/decisions.md`（编号、生效日期、影响阶段、来源），
   并同步项目记忆与受影响的开工清单。
5. 冲突处理：记忆或文档与当前文件不一致时，以当前观察为准，更新或删除旧条目。

不写入记忆：代码结构、路径清单、架构快照、git 历史、一次性缺陷、临时进度；
已写在 `CODEBUDDY.md` / rules / spec 的内容不重复。

## 6. 什么绝对不能自动改

1. **L1 契约层任何文件**（清单见 `CODEBUDDY.md` §3、规则 01 §2）。
   任何契约变更必须先给完整 diff（变更前后 + 影响面 + 受影响测试/Fake）并等用户明确批准。
2. `edge/docs/spec/**` 的原文与图片；`edge/docs/spec/INDEX.md` 只做同步登记，不改原始资料。
3. `.codebuddy/rules/编码规范.mdc`（用户 2026-11-09 修订版）全文。
4. 阶段序列、验收项定义、`STAGE-STATE.md` 的状态；未经用户确认不得推进。
5. 配置期不得写 `edge/` 下任何 `.py`；缺 `test-report.md` 不得收尾。
6. 不得借「按图实现」绕过三条已定裁决；不得把图中文字转录进代码或文档；
   不得把图上方法名当 API。
7. 不得静默改既有规则全文、既有测试断言、既有 Fake 契约；不得为让测试变绿而改被测代码。
8. **不得代用户签署最终 review 结论**；最终结论只由用户本人签字。

## 7. references 索引（只做索引，内容不在此重复）

| 文件 | 职责 | 何时读 |
| --- | --- | --- |
| `references/decisions.md` | 三条已定裁决、裁决变更协议、L1 决策指针 | 每次开工；图与 L1 冲突时 |
| `references/glossary.md` | 术语定义与旧图 snake_case → L1 camelCase 映射 | 读旧图、做命名裁决时 |
| `references/diagram-index.md` | 按阶段 / 图类型检索 spec 资料的路由 | 需定位某张图或某段语义时 |
| `references/stage-catalog.md` | 9 个阶段的交付范围、依赖、验收项与现有代码判定 | 开工、出验收证据、写 STAGE-STATE |
| `references/lessons.md` | 跨阶段可复用经验的模板与已有条目 | 收尾沉淀、下次开工前 |

逐文件资料登记的唯一权威是 `edge/docs/spec/INDEX.md`；本技能不复制其内容。

## 8. 命令与 agent 对应

| 命令 / 环节 | 调用 agent | 职责 |
| --- | --- | --- |
| `/stage` 开工核对 | `stage-opener`、`contract-guard` | 开工清单 + L1 基线（只读） |
| 步骤 1 | `spec-reader` | 读图读方案 → `stages/<id>/spec-digest.md` |
| 步骤 2 | `implementer` | 只改开工清单白名单文件 |
| 步骤 3 | `test-writer` | 测试代码 + `stages/<id>/test-report.md` |
| **人工闸门** | **用户本人** | review 代码并签字；未签字不得进入下一步 |
| 步骤 4 / `/stage-done` | `stage-verifier`、`contract-guard`、`memory-steward` | 只出举证 + L1 复核 + 沉淀 |

七个 agent 定义在 `.codebuddy/agents/`，各自单一职责，不得互相代劳。
