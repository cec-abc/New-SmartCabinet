# 阶段 b 步骤 4 举证表（只举证、不下最终结论、不代签）

> 用户极简口径：不产举证长表，本表只落盘；最终 review 结论由用户本人 2026-11-11 签字，见 `HANDOFF-b.md` §9。

- `b-1`：`python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` → `39 passed in 0.57s`；用例 `testStopInterruptsInterruptibleWaitImmediately`（`elapsed < 0.8`、`rounds == []`、`is_alive() is False`）、`testInterruptibleWaitReturnsTrueWithoutStopSignal`（True→False）、`testRunLoopExceptionBecomesEdgeErrorInLogger`（`errorRecords` 1 条、`ErrorCode.CONFIG`）；`test-report.md` ① 第 1 行 / ③ / ④。
- `b-2`：同命令 `39 passed`；用例 `testStopReturnsAfterJoinTimeout`（`stop(0.2)` 后 `elapsed < 1.0`、`is_alive() is True`，释放后 `is_alive() is False`）；`test-report.md` ① 第 2 行 / ③ / ④。
- `b-3`：同命令 `39 passed`；用例 `testRepeatedStopIsIdempotent`（三次 stop + 重复 start 后 `is_alive() is False`、`rounds == []`）、`testBaseServiceLifecycleIsPolymorphic`（`calls == ["init","start","stop"]`）；`test-report.md` ① 第 3 行 / ③ / ④。
- 必交物：`stages/b/test-report.md` 六节齐备（④ 可复现命令与真实输出、⑥ 3 行未覆盖项及原因，未写「全部覆盖」）；`stages/b/spec-digest.md` 五节齐备；`open-checklist.md` 保留、不追加、不作为必交物。
- 工具链：pytest `39 passed in 0.57s`、ruff `All checks passed!`、mypy `Success: no issues found in 34 source files`（退出码均 0）；既有契约测试与 8 个 Fake 零改动、无新增接口。
- 测试约定：6 个用例均有验收项编号注释；无 `assert True` / `assert x` / `assert ... is not None`；未删用例、未加 skip、未为变绿改被测实现。
- 本表只核对证据齐备性，不下最终 review 结论、不代签；最终结论由用户本人本条口述并录入 `HANDOFF-b.md` §9。
