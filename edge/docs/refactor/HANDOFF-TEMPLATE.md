# HANDOFF-TEMPLATE.md — 阶段移交模板

> L4 模板。每阶段收尾复制本模板为 `edge/docs/refactor/HANDOFF-<阶段号>.md` 并逐项填写；
> 不允许留空字段，无内容写「无」；证据不足写「待补」并说明原因，不得编造。
> 路径一律以工作区根为基准（`CODEBUDDY.md` §0）；`stages/<id>/` = `edge/docs/refactor/stages/<id>/`。
> 由 `memory-steward` 在 `/stage-done` 中产出；产出后不改 L1、不改 spec、不改验收项定义。
> **必交物**：`stages/<id>/spec-digest.md` 与 `stages/<id>/test-report.md`；缺 `test-report.md` 验收判红、不得收尾。

```markdown
# HANDOFF-<阶段号> — <阶段名称>

- **阶段**：<0 | a | b | c1 | c2 | c3 | c4 | c5 | d>（共 9 个阶段）
- **日期**：<YYYY-MM-DD>
- **状态**：<待用户确认 / done / blocked>
- **移交方**：<agent / 助手>
- **接收方**：下一阶段开工（`stage-opener`）

## 1. 开工依据

- 用户确认记录：<何时、以何种表述确认开工>
- 适用权威：<CODEBUDDY.md §2 + 规则 01~04 的版本/日期>
- 本阶段 spec 资料：<路径，来自 edge/docs/spec/INDEX.md；只列路径与图类型，不转录内容>
- 上一阶段 handoff：<路径 / 无>
- 现有代码判定：<引用 stage-catalog.md §0；新骨架 / 旧代码及处置>

## 2. 交付文件与必交物

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |

- 必交物：`edge/docs/refactor/stages/<id>/spec-digest.md` <存在 / 缺失>
- 必交物：`edge/docs/refactor/stages/<id>/test-report.md` <六节齐备 / 判红>
- 范围外文件：<无 / 列出并说明为何未动>
- 遗留 TODO 及归属阶段：<逐条；无则写「无」>

## 3. 验收项逐条证据

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |

- 工具链：`ruff` <结果> ｜ `mypy`（3.9 strict）<结果> ｜ `pytest` + 契约测试 <结果>
- `test-report.md` 六节：<齐备 / 缺节编号>；第 ⑥ 节未覆盖项摘要：<内容>
- `python-code-review` 报告：<结论 + 跨阶段遗留项及归属阶段>
- 测试约定核验：<验收项编号注释 / 无空洞断言 / 无为变绿而改被测代码>

## 4. L1 契约层

- `contract-guard` 基线结论：<零自动变更 / 有变更>
- 契约变更 diff：<无 / 完整 diff + 影响面 + 是否已获批准>
- 批准状态：<无需批准 / 等待用户批准（未落地） / 已批准（附批准记录）>
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— <已遵守 / 说明偏差>

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | <已遵守 / 有偏差> | <说明> |
| D-02 非 UP 不启其他线程 | <已遵守 / 有偏差> | <说明> |
| D-03 去重不做、seq 只填不用 | <已遵守 / 有偏差> | <说明> |

## 6. 遗留与裁决

- 图与 L1 的冲突点：<逐条；标明未改图、未改 L1；无则写「无」>
- 需用户拍板事项：<逐条；无则写「无」>
- 阻塞原因与解除条件：<无 / 说明>
- 移交后续阶段的收敛项：<逐条 + 归属阶段>

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：<证据栏 / test-report 路径 / 时间 / 待确认状态>
- `references/lessons.md` 条目号：<L-xx / 无>
- 项目记忆：<topic 文件名 + MEMORY.md 索引行 / 无>
- `python-code-review` 经验库：<已更新 / 本阶段未写 Python>
- `references/decisions.md`：<未变更 / 新增 D-xx（附用户指令来源）>

## 8. 下阶段开工提示

- 下一阶段：<阶段号>
- 必读：<本 handoff 路径、stage-catalog 对应段、decisions.md 命中裁决、INDEX.md 对应资料>
- 特别注意：<边界 / 已知坑 / 未批准事项>

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前
- 代码 review 签字：<已签署 / 待签署>（任何 agent 不得代签）
- **最终 review 结论：<留空，由用户本人填写>**
- [ ] 配置/交付范围确认
- [ ] 举证结论确认
- [ ] 状态推进确认（<阶段号> → `done`）
- 确认人 / 日期：<由用户本人填写>
```
