---
description: 阶段收尾：核验必交 test-report.md 与用户本人签字、验收举证、检视与 L1 复核，产出 handoff 与沉淀，等待用户确认 done
---

# /stage-done — 阶段收尾

**参数**：阶段号 `0 | a | b | c1 | c2 | c3 | c4 | c5 | d`（共 9 个阶段）。
未提供时取 `edge/docs/refactor/STAGE-STATE.md` 中最后一个 `in_progress` 阶段；
找不到则停止并报告，不自行选择阶段。

前置：用户已确认开工、四步执行完毕、**用户本人已 review 代码并签字**、
`edge/docs/refactor/stages/<id>/test-report.md` 六节齐备、验收项可逐条举证。

## 执行步骤

1. 加载 `.codebuddy/skills/edge-refactor/SKILL.md`，按其 §4「收尾工作流」执行。
2. **必交物核验**：确认 `test-report.md` 存在且六节齐备（见 `.codebuddy/rules/test-visibility.mdc`）。
   **缺件 / 六节不全 / 第 ⑥ 节无未覆盖项及原因 / 第 ④ 节无可复现命令 → 验收一律判红、立即停止，不得收尾。**
3. **人工闸门核验**：确认用户本人 review 签字在位；未签字立即停止，任何 agent 不得代签。
4. 收集证据：`ruff`、`mypy`（3.9 strict）、`pytest` + 契约测试的命令与输出。
5. 本阶段写过/改过 Python → 调用 `python-code-review` 检视一次，输出报告，
   标明跨阶段遗留项及归属阶段；不得用问题清单阻断收尾。
6. 调用 `contract-guard` agent：复核 L1 **零自动变更**；若确需契约变更，
   附 diff 并保持「等待批准」，不得落地。
7. 调用 `stage-verifier` agent：**只出举证表**，不下最终 review 结论、不代签。
8. 调用 `memory-steward` agent：按 `edge/docs/refactor/HANDOFF-TEMPLATE.md` 写 handoff、
   更新 `STAGE-STATE.md` 证据栏与更新时间（状态标「待用户确认」）、追加 `lessons.md`、
   写入项目记忆与检视经验库；handoff 必须记录 `test-report.md` 路径。
9. 输出收尾结论并**停下等待用户确认**；确认后才把状态改为 `done`。

## 输出格式

```
阶段：<阶段号>（共 9 个阶段）｜ 建议状态：待用户确认 / blocked
一、必交物：edge/docs/refactor/stages/<id>/test-report.md ｜ 六节齐备 / 判红
             edge/docs/refactor/stages/<id>/spec-digest.md ｜ 存在 / 缺失
二、验收项逐条：编号 ｜ 证据（命令 + 输出 + 测试名）｜ 举证结果（通过 / 未通过）
三、工具链：ruff / mypy / pytest 结果
四、python-code-review 报告结论 + 跨阶段遗留项（含归属阶段）
五、L1 契约基线：零自动变更 / 有变更 + diff（等待批准，未落地）
六、三条裁决落实：D-01 / D-02 / D-03 逐条「已遵守 / 有偏差 + 说明」
七、人工闸门：用户本人 review 签字 ｜ 已签署 / 待签署（不许代签）
八、沉淀记录：handoff 路径、STAGE-STATE 更新、lessons 条目号、记忆写入项
九、最终 review 结论：<留空，由用户本人签字填写>
十、阻塞项与待用户确认项
```

## 绝对禁止

- 自动修改 L1 契约层；契约变更必须给 diff 并等用户明确批准。
- **代用户签署最终 review 结论**，或在未签字时给出「验收通过」结论。
- 缺 `test-report.md` 仍收尾；静默把状态改为 `done`；静默改验收项、spec 原文/图片或既有规则全文。
- 无证据写「通过」；跳过 `python-code-review`；跳过 L1 复核。
- 把一次性缺陷、代码结构、路径清单、临时进度写进项目记忆。
- 配置期写 `edge/` 下任何 `.py`。
