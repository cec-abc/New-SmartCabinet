---
description: 阶段开工（只读）：加载 edge-refactor 工作流，输出开工清单、L1 基线与四步执行编排，等待用户确认后才可动手
---

# /stage — 阶段开工

**参数**：阶段号 `0 | a | b | c1 | c2 | c3 | c4 | c5 | d`（共 9 个阶段）。
未提供时取 `edge/docs/refactor/STAGE-STATE.md` 中第一个 `pending` 阶段；
若目标阶段不是 `pending`，停止并报告现状，不自行推进。

本命令是**只读命令**：不写任何 `.py`、不改阶段状态、不改 spec、不改 L1 契约层。
下列四步是**用户确认开工之后**的执行编排，本命令只定义归属与准出条件，不代为执行。

## 1. 执行编排：四步 + 人工闸门

| 步 | 执行者 | 输入 | 产物 | 准出条件 |
| --- | --- | --- | --- | --- |
| 1 | `spec-reader` | `edge/docs/spec/INDEX.md` 本阶段条目、`edge/docs/spec/整体重构方案.txt`（只读）、`references/decisions.md`、`references/glossary.md` | `edge/docs/refactor/stages/<id>/spec-digest.md`（五节） | **禁止把图上方法名当 API**；命名已按 NAMING_AUTHORITY 映射；无转录图中文字 |
| 2 | `implementer` | 开工清单**白名单** + `spec-digest.md` | 白名单内实现文件 + 改动清单 | 只改白名单文件；不改 L1 / spec / 测试 / 状态；不写测试 |
| 3 | `test-writer` | 验收项编号与实现 | 测试代码 + `edge/docs/refactor/stages/<id>/test-report.md`（六节） | 六节齐备、用例注释带验收项编号、无空洞断言、无为变绿而改被测代码 |
| **人工闸门** | **用户本人** | 实现 + 测试 + `test-report.md` | **代码 review 签字** | **未签字不得进入步骤 4**；任何 agent 不得代签 |
| 4 | `stage-verifier` | 全部证据 | 验收举证表（**不含最终结论**） | 只出举证；最终 review 结论由用户本人签字 |

- 顺序固定，不跳步、不并行、不由同一 agent 兼任。
- 步骤 1~3 的产物落在 `edge/docs/refactor/stages/<id>/`；`test-report.md` 是收尾**必交物**，
  缺件验收一律判红、不得收尾（见 `.codebuddy/rules/test-visibility.mdc`）。
- `stage-verifier` 之后才是 `/stage-done` 的收尾与沉淀；`/stage-done` 不替代人工签字。

## 2. 执行步骤（本命令自身）

1. 加载 `.codebuddy/skills/edge-refactor/SKILL.md`，按其 §3「开工工作流」依次读取：
   `CODEBUDDY.md`（§0 路径基准、§2 权威、§4 阶段）、4 条 always 规则、
   `references/stage-catalog.md`（含 §0 现状判定）、`edge/docs/refactor/STAGE-STATE.md`、
   `references/decisions.md`、`references/diagram-index.md` → `edge/docs/spec/INDEX.md`、
   L1 相关条目、上阶段 handoff 与 `references/lessons.md`。
2. 按 description 判断是否加载 Agent Requested 规则
   `ref_spec_semantics.mdc`、`ref_legacy_mapping.mdc`、`test-visibility.mdc`。
3. 调用 `stage-opener` agent：产出本阶段开工清单（**含步骤 2 用的白名单**，只读）。
4. 调用 `contract-guard` agent：产出 L1 契约基线结论（只读）。
5. 汇总输出并**停下等待用户确认**。

## 3. 输出格式

```
阶段：<阶段号> ｜ 当前状态：<pending / 其他> ｜ 共 9 个阶段
一、交付文件白名单（路径 + 新增/修改 + 对应验收项编号）
二、验收项（逐条，编号与措辞来自 stage-catalog.md）
三、对应 spec 资料（路径以 edge/docs/spec/ 为基准）
四、适用裁决（D-01 / D-02 / D-03 中命中的编号 + 一句落地含义）
五、L1 契约基线：无变更 / 有变更 + 完整 diff（有变更即阻断）
六、四步执行编排与人工闸门（引用 §1，含各步产物路径）
七、禁止事项（本阶段 + 配置期通用）
八、待用户确认项（无则写「无」）
```

## 4. 绝对禁止

- 写 `edge/` 下任何 `.py`（配置期禁令，解除需用户明确下达）。
- 自动修改 L1 契约层；契约变更只能给 diff 并等用户批准。
- 修改 `edge/docs/spec/**` 原文或图片、修改 `.codebuddy/rules/编码规范.mdc`。
- 把 `STAGE-STATE.md` 状态改成 `in_progress` / `done`——只有用户确认后才可记录。
- 借「按图实现」绕过三条已定裁决；把图中文字转录进代码或文档；把图上方法名当 API。
- 跳过用户本人 review 签字直接让 `stage-verifier` 出结论；代用户签署最终 review 结论。
