# HANDOFF-b — 通用生命周期（阶段 b）
## 1. 依据与状态：`/stage b` 开工卡 2026-11-10 经用户点头（`b` → `in_progress`），2026-11-11 用户本人签字并同时确认推进 `b → done`；共 9 阶段，前置 `a=done`。
## 2. 交付与必交物：白名单 `edge/base/{__init__,base_thread,base_service}.py` 与 `edge/tests/unit/test_stage_b_lifecycle.py`；`stages/b/spec-digest.md`（五节）、`stages/b/test-report.md`（六节，④ 可复现命令与真实输出、⑥ 3 行未覆盖项及原因）；`open-checklist.md` 保留、不追加、不作为必交物。
## 3. 验收证据：`b-1`~`b-3` 逐条举证见 `stages/b/verification-evidence.md`；pytest `39 passed in 0.57s`、ruff `All checks passed!`、mypy `Success: no issues found in 34 source files`（退出码均 0）；`python-code-review` 收尾极简检视一次：改动全在白名单、类型与 Doxygen 注释合规、无空洞断言、无 `base/` 反向 import，首轮 ruff E501×2 与 mypy `func-returns-value`×1 已修正并复跑全绿（IDE 7 条 PEP8/camelCase 注释误报不影响权威工具链），无阻断项。
## 4. L1 契约层：`contract-guard` 复核相对基线 tag `stage-a-done` 零自动变更（L1 pathspec 与 `edge/docs/spec/**` 原文/PNG 的 `git diff --name-status` 两段输出均空，tag 与 HEAD 同为 `5666c06`）；唯一已批准变更仍是 `decisions.md` 附录 A 的 `windowsOnly` diff，无新 diff、无待批准项。
## 5. 三条裁决：D-01 / D-03 本阶段不涉及且未绕过（`edge/base/` 关键词扫描 0 命中）；D-02 只交付通用基类，未启业务线程、未引入 `linkState` / `transitionTo`。
## 6. 遗留与裁决：`test-report.md` ⑥ 未覆盖项按归属留 `c2` / `c3` / `c4` / `c5` / `d`（异常码细分、日志落盘、业务线程启停、上板与 control 多态联调），覆盖率不引入；无待拍板事项、无阻塞。
## 7. 沉淀记录：`references/lessons.md` 追加 L-04 一行；`STAGE-STATE.md` 仅改 `b` 行状态与证据；本文件与 `stages/b/verification-evidence.md` 均在 git 提交之前写完；提交纳入 `open-checklist.md`，`.codebuddy` 下 lessons.md 用 `git add -f` 精确纳入、不改 `.gitignore`；提交后打 annotated tag `stage-b-done`。
## 8. 下阶段开工提示：下一阶段 `c1`（`infra/config_manager.py`，`c1-1`~`c1-4`）；阶段 b 的禁写 `.py` 解除随收尾失效、不沿用，c1 须重新经开工卡用户点头；L1 基线仍按 `stage-a-done` + 附录 A + 本 handoff §4。
## 9. 用户本人 review 与签字：用户本人 2026-11-11 签字「我看过实现和 test-report.md 了，签字」；最终 review 结论（**用户口述 2026-11-11**，按原文录入，**不视为代签**）：「阶段 b 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」本条同时构成状态推进 `b → done` 的确认，未另停一次。
