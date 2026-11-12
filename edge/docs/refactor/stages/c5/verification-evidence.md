# c5 步骤 4 举证表（stage-verifier 口径：只举证，不下最终结论、不代签）

## 必交物核验
| 必交物 | 结论 |
| --- | --- |
| `edge/docs/refactor/stages/c5/spec-digest.md` | 五节齐备（① 范围与资料 / ② 命名裁决 / ③ 契约与接口 / ④ 裁决落实 / ⑤ 遗留与待裁决） |
| `edge/docs/refactor/stages/c5/test-report.md` | 六节齐备：① 验收项→用例对照表、② Fake 表、③ 用例表、④ 可复现命令与环境（含真实输出）、⑤ 汇总、⑥ 未覆盖项及原因（7 行，未写「全部覆盖」） |

## 验收项逐条举证
| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| c5-1 | 模型仅 `loadModel` 一次、`trigger` 立即返回 | `pytest edge\tests\unit\test_stage_c5_recognition.py -q` → `11 passed`；`test_c5_1_load_once_and_trigger_returns_immediately`（`loadedPaths == ["model.bin"]`、elapsed < 1.0s、忙时 `False`）、`test_c5_1_guard_before_init_and_invalid_worker_id`、`test_c5_1_selfcheck_stub_d01`、`test_c5_1_yolo_engine_instance_and_single_load`；report ①③ | 通过 |
| c5-2 | 推理 3s 超时（构造注入） | `test_c5_2_timeout_injected_and_mapped`（`seen == [3.0]`、`EdgeError(INFERENCE_TIMEOUT)`、日志含异常码）、`test_c5_2_timeout_sec_is_configurable`（`seen == [0.25]` 证明非硬编码）；report ①③ | 通过 |
| c5-3 | 空间归集 + 查表校验 + 组 ack | `test_c5_3_aggregate_lookup_and_build_ack`（ack 三条 items 逐项具体值、`requestId`/`type`/`workerId` 断言）、`test_c5_3_pure_functions_behavior`（拼接 / ROI / 归集 / 查表 / 组帧输出确定）；report ①③ | 通过 |
| c5-4 | 回调上抛、纯函数留在 `recognition_utils.py` | `test_c5_4_callbacks_isolated_and_exception_upcast`（成功 id `[1]`、失败 id=2、`code == CAPTURE`）、`test_c5_4_pure_functions_only_in_utils_and_no_cross_module_import`（5 个纯函数只在 utils、无 usb/tcp/control import）、`test_c5_4_fake_engine_contract_and_camel_case_sink`；report ①③ | 通过 |
| 测试约定 | 编号注释 / 无空洞断言 / 无洗绿 | 11 个测试函数上方均带 `## @brief 对应验收项 c5-x`；③ 具体值断言；四步首轮全绿、无失败迭代链，未改验收项 / 预期 / 被测代码 | 齐备 |
| 人工闸门 | 用户本人 review 签字 | 用户 2026-11-12 本条「我看过实现和 test-report.md 了，签字」；最终结论由用户本人口述、本表不填结论、不代签 | 齐备 |

## 工具链（收尾复核实跑，退出码均 0）
- ruff：`All checks passed!`
- mypy（3.9 strict）：`Success: no issues found in 58 source files`
- pytest c5：`11 passed in 0.04s`（四步 `0.08s`，耗时波动并列保留）
- pytest 全量：`94 passed in 1.91s`（四步 `2.07s`）
- pytest 契约：`10 passed in 0.18s`（四步 `0.16s`）

## L1 契约层（只读取证）
- `contract-guard` 子代理无命令执行工具，返回「未判定」（不采信为无变更、不编造结论）。
- 主 agent 只读 git 补证：`git rev-parse HEAD` = `git rev-parse stage-c4-done^{commit}` = `f3e6a0043669024d5cd7dc49f11c6059d258a6f5`；`git log --oneline stage-c4-done..HEAD` 空；L1 + `edge/docs/spec/` 相对基线 / 工作区 / 暂存区三段 `git diff --name-status` 均空；`git ls-files --others --exclude-standard -- edge` 仅 c5 白名单 8 个新文件；`git tag --list` 8 个 → **零自动变更、无需批准**（附录 A 已批准基线不重复判定）。
- 本表只举证，最终 review 结论由用户本人签字。
