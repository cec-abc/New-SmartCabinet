# STAGE-STATE.md — 重构阶段状态

> L4 运行态资产。本文件只记录**当前状态与证据**；阶段定义与验收项以 L1
> `edge/docs/spec/整体重构方案.txt` §5 与 `.codebuddy/skills/edge-refactor/references/stage-catalog.md` 为准。
> 路径一律以工作区根为基准（`CODEBUDDY.md` §0）；`stages/<id>/` = `edge/docs/refactor/stages/<id>/`。
> 生成日期：2026-11-10（流程配置期）。**共 12 个阶段**：原 9 个实施阶段（`0`/`a`/`b`/`c1`/`c2`/`c3`/`c4`/`c5`/`d`）均已 `done`；
> 2026-11-14 用户批准新增 `c4plus` / `c5plus` / `dplus` 三个实施阶段，当前状态 `in_progress`（**待用户确认**，最终 review 结论只由用户本人签字）。
> 配置期禁止写 `edge/` 下任何 `.py`；状态推进必须用户确认（规则 04）。

## 1. 状态定义

| 状态 | 含义 | 谁能改 |
| --- | --- | --- |
| `pending` | 未开工（初始态） | 初始生成 |
| `in_progress` | 用户已确认开工 | 用户确认后由 `/stage` 记录 |
| `done` | 验收全通过、用户本人签字、沉淀完成 | 用户确认后由 `/stage-done` 记录 |
| `blocked` | 阻塞，等待用户裁决 | 记录原因 + 等待用户 |

**当前阶段**：`c4plus` / `c5plus` / `dplus`（**`in_progress`，待用户确认**）。2026-11-14 用户明确解除配置期禁令、批准新增这三个实施阶段（三阶段共用 `edge/docs/refactor/stages/dplus/spec-digest.md` 为签名契约与事实基线，§8 修订节优先级最高）；原 9 个实施阶段（`0`/`a`/`b`/`c1`/`c2`/`c3`/`c4`/`c5`/`d`）均 `done`（`d` 于 2026-11-12 用户本人本条「我看过实现和 test-report.md 了，签字」并口述最终 review 结论、同时确认状态推进 `d → done`；最终结论按用户口述原文录入 `edge/docs/refactor/HANDOFF-d.md` §9，注明「用户口述 2026-11-12」且不视为代签）。**本轮三阶段：用户本人 review 签字尚未取得，状态一律保持 `in_progress`，最终 review 结论只由用户本人填写，助手不代签、不推进 `done`。**)
**前置门禁**：L1 契约层零自动变更；任何契约变更必须给 diff 并等用户批准。**L1 基线已变更一次且已获批准**：`edge/tests/contract/test_phase0_foundation.py` 的已批准 diff 登记在 `references/decisions.md` 附录 A 与 `HANDOFF-a.md` §4，后续 `contract-guard` 以 tag `stage-a-done` + 该附录为对比基线，不重复判定。
**必交物**：`edge/docs/refactor/stages/<id>/test-report.md`（六节）；缺件验收判红、不得收尾。
**人工闸门**：用户本人 review 代码并签字；`stage-verifier` 只举证，不代签。
**禁写解除（仅本阶段）**：阶段 d 已收尾（2026-11-12），开工卡对白名单（`edge/control/` 三文件含 `__init__.py`、`edge/app_init.py`、`edge/main.py`、`edge/tests/unit/test_stage_d_control.py`）内 `.py` 的禁写解除**随阶段结束失效、不沿用**。白名单外 `.py`、L1 契约层、`edge/docs/spec/**` 原文与图片仍一律禁写；后续如需改 `.py` 须另行经用户明确授权。
**收尾状态：`done`**（阶段 0 记录：2026-11-10 执行 `/stage-done 0` 并经用户本人确认；最终 review 结论按用户口述原文录入 `HANDOFF-0.md` §9，注明「用户口述 2026-11-10」且不视为代签）。
**阶段 a 收尾状态：`done`**（2026-11-10 用户本人本条确认「阶段 a 验收通过，同意收尾」并同时确认状态推进 `a → done`；最终 review 结论按用户口述原文录入 `edge/docs/refactor/HANDOFF-a.md` §9，注明「用户口述 2026-11-10」且不视为代签；沉淀、git 提交与 annotated tag `stage-a-done` 均按用户指令完成）。

## 2. 阶段总表（共 12 个阶段）

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
| `d` | `control/` 三文件（含 `__init__.py`） + `app_init.py` + `main.py` | `done` | `d-1`~`d-4` | `stages/d/test-report.md` | 2026-11-12 用户本人点头开工并确认记为 `in_progress`；白名单 `edge/control/` 三文件（新建目录）+ `edge/app_init.py` + `edge/main.py` + `edge/tests/unit/test_stage_d_control.py`；`stages/d/spec-digest.md` 五节、`stages/d/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 8 行未覆盖项及原因）；四步实跑 ruff `All checks passed!`、mypy `Success: no issues found in 64 source files`、pytest d `17 passed in 0.55s` / 全量 `111 passed in 1.90s` / 契约 `10 passed in 0.17s`（退出码均 0）；`python-code-review` 写后极简检视一次、无阻断项（P3 AST 结构断言归上板）；L1 基线开工只读核验 `HEAD = stage-c5-done = a7178d2`、L1 + spec 三段 diff 全空、工作区干净、本地与远端 9 tag → 零自动变更、无需批准（`contract-guard` 子代理无命令工具返回「未判定」，由主 agent 只读 git 补证，同 c4/c5 §4）；D-01 / D-02 / D-03 全部复核；EventCache 存废与协议口径张力按用户指令**只登记、不落地、不选边、待用户拍板**（`decisions.md` 原文未改，三条待裁决只落 `spec-digest.md` §5 与 `test-report.md` ⑥，错放判定与 `camera_status` 两组不混入 d）；2026-11-12 用户本人签字「我看过实现和 test-report.md 了，签字」并**同时**确认状态推进 `d → done`、不再另停一次，最终结论按口述原文录入 `HANDOFF-d.md` §9（注明「用户口述 2026-11-12」、不视为代签）；步骤 4 `stage-verifier` 只出举证表（落盘 `stages/d/verification-evidence.md`、不含最终结论、不代签）；收尾复核 ruff `All checks passed!`、mypy `Success: no issues found in 64 source files`、pytest d `17 passed in 0.63s`（四步 `0.55s`）、全量 `111 passed in 2.10s`（四步 `1.90s`）、契约 `10 passed in 0.17s`（四步 `0.17s`），耗时波动并列保留；`python-code-review` 收尾极简检视一次、无阻断项（P3 AST 结构断言归上板）；`contract-guard` 子代理无命令工具返回「未判定」，L1 复核改由主 agent 只读 git 独立取证零自动变更、如实记入 `HANDOFF-d.md` §4；沉淀 `HANDOFF-d.md`、lessons L-10、检视经验库（既有条目命中次数 3→4）、annotated tag `stage-d-done`；阶段 d 禁写解除不沿用 | 2026-11-12 |
| `c4plus` | `modules/usb/**` + `interfaces/i_camera_focus.py` + `interfaces/i_frame_sink.py` + `tests/fakes/fake_camera_focus.py` + `tests/fakes/fake_frame_sink.py`（循环化流式采集、对焦能力、帧回调契约） | `in_progress`（待用户确认） | `spec-digest` §7-1、§7-2（与 c5plus/dplus 合并验收，编号见 `stages/dplus/spec-digest.md` §7） | `stages/dplus/test-report.md` | 必交物 `edge/docs/refactor/stages/dplus/test-report.md` 六节齐备（① 验收项→用例对照表 / ② Fake 清单 / ③ 用例表含真实上位机进程取证与第三轮 30 条 / ④ 可复现命令与环境 / ⑤ 汇总 / ⑥ 未覆盖项及原因）；`edge/docs/refactor/stages/dplus/spec-digest.md` 九节齐备，§8 修订节优先级最高。工具链（2026-11-14 **第三轮修复后**末次全量实跑）：pytest **162 passed / 0 failed / 0 skipped / 1 warning**（38.36 s）、ruff **0 告警**（上一轮口径，本轮未复跑）、mypy **0 错误**（上一轮 79 个源文件口径，本轮未复跑）；新增一致性用例 13 条全通过（6.13 s）；真实上位机进程联调 **6/6 取证点**；上位机自带 `test_edge.exe` **36 passed / 0 failed**；覆盖率「不可测」（环境无 pytest-cov），如实保留。接口签名对齐断言 31 → **35** 对、接口文件数 8 → **10**、Fake 文件数 8 → **10**（`test_stage_a_contract_alignment.py:261,265-266`）。**第三轮修复**：相机状态判定改为「从未成功打开一律 `offline`」（`usb_controller.py:307-319`），安全闸门不再误放行。**用户本人 review 签字未取得**，最终 review 结论留空；`edge/docs/refactor/stages/dplus/handoff.md` §9 待签。 | 2026-11-14 |
| `c5plus` | `modules/recognition/**` + `infra/roi_binding_loader.py` + `config/roi_binding.csv`（CSV 对照表装载、ROI 裁剪拼接、流式识别、幂等应答） | `in_progress`（待用户确认） | `spec-digest` §7-1、§7-3（与 c4plus/dplus 合并验收） | `stages/dplus/test-report.md` | 同上必交物与工具链数字（pytest **162 passed** / ruff 0 告警 / mypy 0 错误）。ROI 对照表 12 列表头（含 `worker_id`，四角点 `rect_x1/rect_y1/rect_x2/rect_y2`）；`items[]` 恰好 4 键由 `testAckItemMustCarryExactlyFourKeys` 等新用例举证。**第三轮修复 4 项**：缺 `roiId` 显式判错（`recognition_utils.py:91-96,123-133`）、配置兜底链路明确不可用（`recognition_worker.py:170-172`）、onnxruntime 分支补同类别 NMS 且阈值构造注入（`recognition_yolo_engine.py:320-329,375-391`）、识别背压有丢弃计数与抽样日志（`recognition_controller.py:98-101,154-159,204-218`）。**已知限制如实登记**：模型权重 `./models/yolo.pt` 未部署、线上只给「未命中」不伪造命中；ROI 样例按 640×480 铺满四象限，上板须按实际全景尺寸重标；onnxruntime 未与 ultralytics 等价标定，默认固定 ultralytics；`edge/tests/unit/test_stage_c5_recognition.py` 3 处断言改写 + 第三轮追加 2 条用例属**白名单越界、待用户追认**（B1 / B2）。**用户本人 review 签字未取得**。 | 2026-11-14 |
| `dplus` | `control/**` + `app_init.py` + `main.py` + `config/config.ini` + `tests/integration/**` + `tests/contract/**` + `tests/unit/test_stage_a_contract_alignment.py`（4 个生产断点修复、应答排空、正式配置、端到端联调、第三轮业务闭环二次校验） | `in_progress`（待用户确认） | `spec-digest` §7-1、§7-3、§7-4、§7-5、§7-6（与 c4plus/c5plus 合并验收；补充编号 D-1 ~ D-9 见 `stages/dplus/test-report.md` ①） | `stages/dplus/test-report.md` | 同上必交物与工具链数字（pytest **162 passed** / ruff 0 告警 / mypy 0 错误）。4 个生产断点已修：`recognize_req` 路由（`app_init.py:381-382,373-375`）、应答排空（`edge_dispatch_thread.py:18-37` + `edge_control.py:191-212`）、断链自愈（`edge_control.py:465-469` 链路探针；`tcp_control_layer.py:149-154` 未转发上游，越界未改、最小 diff 待批准）、周期帧改 `periodic`（`app_init.py:353-366,76,597`）。幂等（§7-4）、周期帧 3 秒一帧 + 8 路 `camera_status`（§7-5）、重复请求只扫描一次（§7-6）均有对应用例通过。**第三轮修复 5 项**：未装载 ROI 对照表 → 启动即 Fail-Fast（`app_init.py:397-410,696`）、对照表 `worker_id` 超限 → 装配期报错（`app_init.py:382-389,699`）、新增配置键 `[recognition] inference_backend` / `nms_iou_threshold`（`config.ini:26-27`）、降级出帧 / ROI 越界逐行降级 / 识别异常也有应答三处降级**已复核有效**（`recognition_worker.py:108-119,132-137,147-160`）、两张图交付（`edge_class_diagram.html` 53 节点 / 18 关系；`edge_recognition_flow.html` 图 2 30 节点 / 35 连线、图 3 17 节点 / 17 连线；自检脚本 `verify_diagram_screenshot.py`）。**待用户批准**：A1 `ICameraFocus`、A2 `IFrameSink`、A3 `edge/config/`、A4 L1 逐文件职责表扩容 3 项、**A5 第三轮新增公开方法**、**A6 第三轮新增文件**；B1 / **B2** 白名单追认。**用户本人 review 签字未取得**。 | 2026-11-14 |

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

### 阶段 c4plus / c5plus / dplus — 识别流重构 + USB 对焦 + 8 路 2 合 1（三阶段合并验收）

> 验收项编号取自 `edge/docs/refactor/stages/dplus/spec-digest.md` §7「验收硬指标」（措辞照抄不改写）；三阶段共用同一套编号，逐条证据见 `edge/docs/refactor/stages/dplus/test-report.md` ① 与 `edge/docs/refactor/stages/dplus/handoff.md` §3。

- [ ] `§7-1` `ruff check edge` 零告警；`mypy edge`（3.9 strict）零错误；`pytest edge/tests` 全绿。
- [ ] `§7-2` **既有测试零修改断言**：除 `test_stage_a_contract_alignment.py` 因新增接口/Fake 需同步 L1 方法表外，其余既有测试文件**不得改动**。（例外：`test_stage_c5_recognition.py` 3 处断言改写属白名单越界，**待用户追认 B1**）
- [ ] `§7-3` 端到端联调（`tests/integration/`）：Python 桩上位机监听 9000 → 边缘机连上 → 桩发 `recognize_req` → 边缘机回 `recognize_ack`，`items[]` 每项**恰好 4 字段**、`position` 不重复、`tool_id` 可空、`confidence ∈ [0,1]`、`alert_type` 取值合法 → 桩校验通过。
- [ ] `§7-4` **幂等验证**：同一 `request_id` 连发 2 次，边缘机只扫描一次、回两次相同结果。
- [ ] `§7-5` **周期帧验证**：3 秒一帧 `periodic`，`camera_status` 覆盖 8 路。
- [ ] `§7-6` 重复 `recognize_req` 不导致 8 路重复扫描（计数断言）。

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
| 2026-11-12 | d | 开工确认卡（≤15 行）经用户点头，`pending → in_progress`；白名单 `edge/control/` 三文件（新建目录：`edge_control.py` / `event_cache.py` / `__init__.py`）+ `edge/app_init.py` + `edge/main.py` + `edge/tests/unit/test_stage_d_control.py`，禁写 `.py` 仅对本次白名单解除、不沿用；D-01 / D-02 / D-03 全部复核，`routeSignal` 按注入 `asyncHandlers` 分发、门面不写死业务字符串，`seq` 只填不用、禁止按 seq 去重，一键停机严格串行 `USB → 识别 → TCP → 日志`、进程锁生效，`app_init.py` 只做 new + 注入 + 返回、`main()` 不用 try/except 包业务流程；EventCache 存废与协议「边缘机不缓存任何业务数据、重发补发全是上位机行为」张力**只登记、不落地、不自行选边、待用户拍板**，`decisions.md` 原文不改，三条待裁决只落 `spec-digest.md` §5 与 `test-report.md` ⑥，错放判定与 `camera_status` 两组不混入 d；四步由主 agent 连续执行、极简文档（④ 真实命令与输出、⑥ 未覆盖项及原因不省） | 必交物 `stages/d/spec-digest.md` 五节、`stages/d/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 8 行未覆盖项及原因）；ruff `All checks passed!`、mypy `Success: no issues found in 64 source files`、pytest d `17 passed in 0.55s`、全量 `111 passed in 1.90s`、契约 `10 passed in 0.17s`（退出码均 0）；`python-code-review` 写后极简检视一次无阻断项（P3 AST 结构断言归上板），检视中收敛 3 处并复跑全绿；`contract-guard` 子代理无命令执行工具返回「未判定」，L1 基线改由主 agent 只读 git 核验（`HEAD = stage-c5-done = a7178d2`、三段 diff 全空、工作区干净、本地与远端 9 tag → 零自动变更）；**四步完成、停在人工闸门待用户本人 review 签字**，未进步骤 4、未执行 `/stage-done d`、未代签、未提交未打 tag | 开工已确认（用户本人）；代码 review 签字待用户本人 |
| 2026-11-12 | d | 收尾事件：用户本人 review 并签字「我看过实现和 test-report.md 了，签字」，口述最终 review 结论「阶段 d 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」并**同时确认状态推进 `d → done`**；步骤 4 `stage-verifier` 只出举证表（落盘 `stages/d/verification-evidence.md`，证据齐备、不含最终结论、不代签）；执行 `/stage-done d`：`python-code-review` 收尾极简检视一次、`contract-guard` 子代理无命令工具返回「未判定」，L1 复核改由主 agent 只读 git 独立取证零自动变更（如实记入 `HANDOFF-d.md` §4）、写 `HANDOFF-d.md`、更新本文件证据栏与状态、追加 lessons L-10、同步检视经验库（既有条目命中次数 3→4） | 必交物 `edge/docs/refactor/stages/d/test-report.md` 六节齐备（④ 真实命令与输出、⑥ 8 行未覆盖项及原因）、`stages/d/spec-digest.md` 五节齐备；`d-1`~`d-4` 逐条举证通过；状态 `in_progress → done` 由用户本条明确确认，未另停一次；结论为用户本人本条口述、助手按原文照录，未代签；所有文档写入均在 git 提交之前完成，`.codebuddy` 下 lessons.md 用 `git add -f` 精确纳入、不改 `.gitignore`；提交后打 annotated tag `stage-d-done`、`git push origin main` 与 `git push origin --tags`、确认 git status 干净与远端 tag 齐全；9 个实施阶段全部 `done`，完成后停下、不执行任何阶段 | 已确认（用户本人） |
| 2026-11-14 | c4plus / c5plus / dplus | 用户 2026-11-14 明确解除配置期禁令、批准新增这三个实施阶段（`stages/dplus/spec-digest.md` 抬头原文）；三阶段落地后执行 `/stage-done`：核验必交物（`stages/dplus/spec-digest.md` 九节 + `stages/dplus/test-report.md` 六节齐备，⑥ 未覆盖项如实登记）→ 写 `edge/docs/refactor/stages/dplus/handoff.md`（按 `HANDOFF-TEMPLATE.md` 九节结构；文件名按用户当次指令，与模板 `HANDOFF-<阶段号>.md` 命名约定不同，已登记）→ 更新本文件证据栏与时间 → 追加 lessons L-11~L-15 → 更新 `references/decisions.md` D-04~D-11 → 更新 `references/stage-catalog.md` 三阶段段 → 更新 `CODEBUDDY.md` §4 阶段清单（9 → 12 阶段，补三行，L3 改动已登记）→ 写项目记忆两个 topic + `MEMORY.md` 索引 → 同步工作区外 `code-quality-guardian` 检视经验库 | 工具链（2026-11-14 末次全量实跑）：pytest **132 passed / 0 failed / 0 skipped**（22.39 s）、ruff **0 告警**、mypy **0 错误（79 个源文件）**；新增一致性用例 13 条全通过；真实上位机进程联调 **6/6 取证点**；上位机自带 `test_edge.exe` **36 passed / 0 failed**；覆盖率不可测（环境无 pytest-cov）如实录。L1 契约层零改动；4 项契约增量（`ICameraFocus` / `IFrameSink` / `edge/config/` / L1 逐文件职责表扩容 3 项）与 1 项白名单追认（`test_stage_c5_recognition.py`）**均未落地**，以待批准项登记在 handoff §6.2。**状态一律 `in_progress`（待用户确认），未推进 `done`、未代签最终 review 结论**（handoff §9 留空待用户本人填写） | 开工已确认（用户本人）；**代码 review 签字待用户本人**；A1~A4 / B1 待用户拍板 |

| 2026-11-14 | c4plus / c5plus / dplus | **第三轮：业务闭环二次校验 + 缺陷修复 + 两张图交付**；用户指令本轮产出同步进既有资产并补齐裁决与经验（沉淀官 `memory-steward`） | 必交物 `stages/dplus/test-report.md` 六节齐备并已更新（新增 §0.1 数字来源与复跑状态、②.1 第三轮测试替身、③.6 第三轮 30 条用例、① 补充编号 D-1 ~ D-9、⑤ 自洽分项、⑥ 扩到 12 行未覆盖项）；`stages/dplus/handoff.md` 已更新（新增 §3.1 第三轮 9 项复核、§3.2 图表交付、§6.1 已知限制第 8~10 条、§6.2 待批准清单扩到 A1~A6 / B1~B2）；工具链：pytest **162 passed / 0 failed / 0 skipped / 1 warning**（38.36 s，用户本轮实跑口述；本 agent 无命令执行工具未复跑，已在 `test-report.md` §0.1 如实标注）→ 磁盘独立复核 162 个测试函数（unit 103 + integration 49 + contract 10）、全库无 `parametrize` / `skip` / `xfail`；ruff / mypy **本轮未复跑**（磁盘旁证 `.ruff_cache/0.17.5/`、`.mypy_cache/3.9/edge/**` 88 模块缓存）。第三轮修复 9 项逐条有对应用例（`test_round3_defect_fixes.py` 17 条 + `test_business_closure.py` 11 条 + `test_stage_c5_recognition.py` 追加 2 条 = 30 条，与 132 → 162 增量自洽）；两张图节点 / 连线计数读盘核对一致（53/18、30/35、17/17）。L1 契约层零改动；裁决追加 **D-12 ~ D-16**、经验追加 **L-16 ~ L-19**、项目记忆 3 个 topic 同步。**状态一律 `in_progress`（待用户确认），未推进 `done`、未代签最终 review 结论**（handoff §9 留空待用户本人填写） | 开工已确认（用户本人）；**代码 review 签字待用户本人**；A1~A6 / B1~B2 待用户拍板 |

## 6. 使用协议

- 本文件由 `/stage`（只读核对）与 `/stage-done`（写入证据）驱动；状态由用户确认后推进。
- 验收项编号与措辞变更 = 阶段定义变更，须走 L1 diff + 用户批准；不得静默修改。
- 证据栏只记可复核内容（命令、输出、测试名、`test-report.md` 路径），不写「应该通过」。
- 阻塞时状态写 `blocked` 并在 §5 记录原因，等待用户裁决。

## 7. 变更记录（仅追加，不改历史状态与证据）

### 2026-11-16 变更记录 — 删除断链补报功能

- **事项**：用户 2026-11-16 裁决删除「断链补报」能力（见 `references/decisions.md` D-20：断链期间不缓存待上报事件、恢复后不补发，删除 `EventCache` 整套机制）。代码端、测试端、SRS 与 L1 口径（`整体重构方案.txt` / `编码规范规则.txt`）已同步，另同步 `.codebuddy/rules/03_dependency_and_layout.mdc`、`ref_spec_semantics.mdc`、`ref_legacy_mapping.mdc`。
- **历史证据处置**：阶段 `d` 的 `d-2` 原验收项（`EventCache` 按 `event_cache.enabled` 补发/丢弃、`seq` 只填不用）及其举证材料作为**历史快照保留**，原文一律不改；该证据**不再作为当前实现依据**，当前实现以 D-20 为准。
- **状态不变**：本次变更记录**不改变任何已签字阶段的状态** —— `d = done` 及其签字记录原文保持不动，`c4plus/c5plus/dplus` 仍为 `in_progress`（待用户确认）；不代用户签字、不推进任何阶段。
- **L2 图资产冲突登记**：以下规格图源码仍保留 `EventCache 补发` 描述，与 D-20 冲突；按 `01_naming_authority` §4「不改图、不改 L1，冲突写入 handoff」，本轮**不修改图源码**，仅登记待后续阶段重绘：`整体流程/整体流程.txt`、`整体流程/整合类图代码.txt`、`TCP/断线重连/断线重连.txt`、`TCP/周期心跳帧/心跳帧.txt`。图只表达历史语义，当前实现以 D-20 与 L1 为准。
- **生效日期**：2026-11-16（用户裁决）。

### 2026-11-16 变更记录 — 日志磁盘余量口径统一

- **事项**：用户指出需规"磁盘余量不足时停止写入"不合适，要求改为余量低时删旧文件保留新文件。查证发现代码本已实现删旧（`purgeOldFiles`），但阈值是 0.1（设计图为 30%）、且只在滚动时触发；需求文档是唯一写"停止写入"的地方。
- **落地**：阈值统一为 0.3（`config.ini` / `README.md` / dplus `spec-digest.md` 旧值 1048576 一并纠正）；清理触发从"仅滚动"改为"每次写入检查"（`log_manager.py:164`），新增 c2-2 用例 `testDiskCleanupWithoutRoll`；SRS `SR_0302_FUNC_CONF_02` 及采集/硬件资源节改为删旧口径，重新生成 docx 并 Word 刷域（30 页）。
- **历史证据**：阶段 c2/dplus 既有验收证据原文保留不改，本次作为新增变更记录。
- **验证**：全量 pytest 275 通过 / 6 历史基线失败（Linux 骨架漂移，与本次无关）；最终 docx 直读"停止写入/停止落盘" 0 命中、新表述各 3 处。

### 2026-11-20 变更记录 — 摄像机状态收紧为 ok/offline 两态

- **事项**：用户 2026-11-20 裁决摄像机状态只保留 `ok` / `offline` 两态，`low_light`（照度不足）/`dirty`（镜头脏污）不好判断故不设取值。取图失败（原 `comm_error`）归并到 `offline`——不可用相机绝不能报 `ok`，否则开柜闸门误放行。
- **落地**：`edge/modules/usb/usb_controller.py` 删三态以上常量、`_resolveCameraStatus` 全路径只产出两态；协议校验 `host_protocol_checker.py` / `fake_host.py` 的 `CAMERA_STATUS_VALUES` 从五值收紧为两值；`test_round3_defect_fixes.py` 三态断言、`test_upper_host_protocol_parity.py` dirty 闸门用例等价改 offline；同步 `config/README.md`、新人指南、dplus 四件套文档与流程图。
- **需规同步**：①上位机 SRS（`SmartCabinetLite/docs/智能工具柜管理系统-软件需求规格说明.docx`）三处五态枚举改两态，ZIP 级精确替换 + 段落级 diff 确认只 3 处变化 + 黄色段守恒 + Word COM 刷域（74 页）+ 实开核验；改前备份 `temp/SRS_改前备份_20261120.docx`。②边缘机 SRS 最新正式版 `edge/docs/spec/智能工具柜边缘计算机软件-软件需求规格说明_V2.06_需求完善修订.docx` 六处状态口径改两态（含 P230「取图失败报通信异常」改为归掉线，消除与新口径矛盾），逐处断言 + 段落级 diff 确认只 6 处变化 + 采集模式"三种"2 处未误改 + Word COM 刷域（34 页）+ 实开核验；改前备份 `temp/边缘机SRS_V206_改前备份_20261120.docx`。历史版本 V2.01~V2.05 与 temp 无版本号副本作为历史快照保持未动。
- **L1 契约层**：0 个 L1 文件改动（五态字面值均不在 L1；未把状态提升为 Literal/枚举类型）。`host_protocol_checker.py` 虽是协议校验语义，但按路径属 `tests/integration/` 非 L1；协议口径变更按用户当次指令执行。
- **验证**：全量 pytest 304 passed / 1 skipped；本次改动 5 个 Python 文件 ruff 全绿；全库 Python 旧状态字面值 0 命中；独立审核 Agent 复核并补齐 3 处文档收尾（code-review-report 遗留项、图计数注记）。
- **状态不变**：本次变更不改变任何已签字阶段状态——`d = done` 不动，`c4plus/c5plus/dplus` 仍 `in_progress`（待用户 review 签字）；不代签、不推进 `done`。
- **上位机侧待同步（另行，属另一工程）**：`SmartCabinetLite/src/comm/CommTypes.h`、`EdgeService.h/.cpp` 注释仍列五态字面值，`tools/EdgeSimulator` 8 路下拉仍可选旧三态；闸门逻辑"非 ok 即拦"天然兼容两态、无需改。本次只改需规，上位机 C++ 代码与模拟器下拉列为建议同步项，未擅自跨工程修改。
- **生效日期**：2026-11-20（用户裁决）。

### 2026-11-20 变更记录 — 代码/需规一致性自查整改 + 补图 + 生产上线清单

- **事项**：用户 2026-11-20 要求按建议补流程图、处理自查发现的真问题、出生产上线准备清单、跑遗产测试、需规需求化并多 Agent 协同审查。
- **自查结论**（3 路并行 + 独立审核复核）：9 条能力需求 5 条完全匹配、4 条部分匹配、0 条未实现；摄像机两态 SRS 与代码逐字一致。初查 15 条差异复核为 **5 真问题 / 2 误报 / 8 需修正表述**。
- **代码整改**：①置信度门槛改为配置项 `recognition.min_confidence`（单一来源，贯通 config→app_init→loader/Controller→Worker→buildConfigItem/validateByTable，CSV 每行可覆盖）；②识别侧补 `rollPanoramaStorage` 全景图滚动删旧（P0361/P0369）；③`tcp_comm.py` 白名单注释修正、区分本软件发出的两种帧与上位机可识别全集；④新增 3 条单测 `test_config_single_source.py`。改动均非 L1，L1 契约层与 `docs/spec` 原文零改动。
- **需规完善（边缘机 SRS V2.06）**：①补 3 张灰阶流程图（整体数据流 / 链路建立与重连 / 周期上报），用 `SEQ 图` 域自动编号，图 1~11 连续；②需求化语言修正 27 处（去"降级"黑话 6 处、写死数值改配置口径、去脚本名/库名等实现细节、停机 3 秒矛盾统一为"按配置给定的等待上限依次停止"、采集模式对齐"单路/两两配对"）；③ZIP 级精确替换 + 逐处断言 + Word COM 刷域 + 独立进程实开 36 页正常。改前备份 `temp/边缘机SRS_V206_补图前备份.docx` 与 `temp/边缘机SRS_V206_需求化前备份.docx`。
- **测试**：全量 pytest **307 passed / 1 skipped**（+3 新测试）；改动文件 ruff 全绿；真机遗产测试 `layer_dual_cam_verify.py` 用设备 0/1 实跑 **C01~C10 全 PASS**（取帧/拼接/ROI/四键 items/三键 ack/幂等），结果 `edge/lab/outputs/layer_verify_realtime/result.json`。
- **生产上线清单**：新增 `edge/docs/refactor/生产上线准备清单.md`（A 数据文件 / B 现场标定配置 / C 代码未到位项 / D 上线前测试 / E 麒麟上板 + 最小上线集 + 三条红旗），多 Agent 梳理并逐条附证据与"不补的后果"。
- **状态不变**：不改变任何已签字阶段状态；`d = done` 不动，`c4plus/c5plus/dplus` 仍 `in_progress`（待用户 review 签字），不代签、不推进 `done`。
- **生效日期**：2026-11-20（用户指令）。

### 2026-11-20 变更记录 — 需规四项修订 + 生产数据准备操作手册

- **事项**：用户 2026-11-20 提出 4 项需规问题（FOCUS 章需求化+补图、图7留白、表14格式内容、注释章精简）并要求把生产数据准备步骤写成新人可懂的 Word 手册。
- **需规修订（边缘机 SRS V2.06，最终 43 页）**：
  1. 3.2.3.3 FOCUS 章需求化：删除数组下标/采集单元/属性名/单位换算/Fail-Fast 等设计化表述，逐段改为"软件应/必须"可验证需求；补第 12 张图"相机对焦参数配置流程图"。
  2. 图 7 周期上报、图 4 整体数据流：原内容偏右（节点全在 col=1），改为 col=0 并收窄画布使其水平居中；图 6 链路图高度收紧。举一反三核查全部 11 图，仅此两图有偏侧问题。
  3. 表 14 重建：4 列改为"需求编号/需求说明/优先顺序/关键程度"，补齐全部 14 个真实需求 ID（9 能力+2 接口+3 关键特性），修正错误描述、统一"关键程度"术语、消除病句。
  4. 6.注释章：9 条精简为 2 条（边缘计算机、对焦），删其余 7 条。
  - 图号 SEQ 域自动重排 1~12 连续；Word COM 刷域；交付版 python 精确核验全绿（12 图、FOCUS 旧表述 0、注释 2 条、表14 ID 14/14、病句 0、两态保持）。
- **新增手册**：`edge/docs/refactor/边缘机生产数据准备操作手册.docx`（8 页/247 段/4 表，Word 实开正常）。按 6 步白话写：连上位机改 IP→逐路调焦→拍全景并在图上标货位四角点→填 roi_binding.csv 12 列→填 class_item_map.csv→验证上线；含常见问题表与上线核对清单；去 AI 味检查 0 命中。
- **验证**：终审 Agent 复核（无 docx 工具，仅能看图与脚本证据）；主 Agent 对交付版做 Python 精确断言全部通过；手册 Word 实开 8 页正常。
- **状态不变**：不改变任何已签字阶段状态；`d = done` 不动，`c4plus/c5plus/dplus` 仍 `in_progress`（待用户 review 签字），不代签、不推进 `done`。
- **生效日期**：2026-11-20（用户指令）。
