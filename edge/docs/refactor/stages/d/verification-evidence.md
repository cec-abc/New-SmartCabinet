# d 步骤 4 举证表（stage-verifier 口径：只举证，不下最终结论、不代签）

## 必交物核验
| 必交物 | 结论 |
| --- | --- |
| `edge/docs/refactor/stages/d/spec-digest.md` | 五节齐备（① 范围与资料 / ② 命名裁决 / ③ 契约与接口 / ④ 裁决落实 / ⑤ 遗留与待裁决） |
| `edge/docs/refactor/stages/d/test-report.md` | 六节齐备：① 验收项→用例对照表、② Fake 表、③ 用例表、④ 可复现命令与环境（含真实输出）、⑤ 汇总、⑥ 未覆盖项及原因（8 行，未写「全部覆盖」） |

## 验收项逐条举证
| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| d-1 | `routeSignal` 按注入 `asyncHandlers` 键分发 | `pytest edge\tests\unit\test_stage_d_control.py -q` → `17 passed`；`test_d_1_route_signal_dispatches_injected_keys`（注入任意键 `alpha_probe`/`beta_probe` 命中、`reqId` 只提取一次）、`test_d_1_unknown_key_rejected_and_sink_forwards`（未注入键返回 `False` 并记 error）、`test_d_1_l1_sink_contracts_and_camel_case`（三个 L1 Sink + 无 snake_case）；report ①③ | 通过 |
| d-2 | `EventCache` 补发/丢弃且 `seq` 只填不用 | `test_d_2_cache_flush_when_enabled`（`flush == 3`、seq `[1,2,3]`）、`test_d_2_cache_discard_when_disabled`（`flush == 0`、零发送）、`test_d_2_seq_only_filled_never_used_for_dedup`（3 条相同事件全补发、无 `seenSeq`）、`test_d_2_link_down_caches_and_link_up_flushes`（DOWN 入缓存、UP 补发 2 条）、`test_d_2_dispatch_outbox_sends_when_up`（业务 `seq` 不被改写）；report ①③ | 通过 |
| d-3 | 一键停机严格串行 `USB → 识别 → TCP → 日志` + 进程锁 | `test_d_3_stop_system_strict_serial`（`trace == [USB, RECOGNITION, TCP, LOG]`）、`test_d_3_process_lock_fails_fast_before_assembly`（`SystemExit` 含 `CONFIG`、`partsCalled == []`）、`test_d_3_selfcheck_stub_d01`、`test_d_3_start_system_does_not_prestart_business_threads`；report ①③ | 通过 |
| d-4 | Windows 端到端 | `test_d_4_end_to_end_start_and_stop`（锁→装配→信号→启动→等待→停机→释放，`trace == [signals, log-start, link-start, wait, log-stop]`、`loadedPaths == ["model.bin"]`、`socket.closed True`）、`test_d_4_app_init_only_wires`、`test_d_4_main_has_no_try_except_business_flow`、`test_d_4_build_system_has_no_business_branches`、`test_d_4_platform_and_fake_contracts`；report ①③ | 通过 |
| 测试约定 | 编号注释 / 无空洞断言 / 无洗绿 | 17 个测试函数上方均带 `## @brief 对应验收项 d-x`；③ 具体值断言；首轮 ruff/mypy 问题与检视中 3 处收敛如实披露，均在白名单内修正后复跑全绿，未改验收项 / 预期 / 被测业务语义 | 齐备 |
| 人工闸门 | 用户本人 review 签字 | 用户 2026-11-12 本条「我看过实现和 test-report.md 了，签字」；最终结论由用户本人口述、本表不填结论、不代签 | 齐备 |

## 工具链（收尾复核实跑，退出码均 0）
- ruff：`All checks passed!`
- mypy（3.9 strict）：`Success: no issues found in 64 source files`
- pytest d：`17 passed in 0.63s`（四步 `0.55s`，耗时波动并列保留）
- pytest 全量：`111 passed in 2.10s`（四步 `1.90s`）
- pytest 契约：`10 passed in 0.17s`（四步 `0.17s`）

## L1 契约层（只读取证）
- `contract-guard` 子代理无命令执行工具，返回「未判定」（不采信为无变更、不编造结论）。
- 主 agent 只读 git 补证：`git rev-parse HEAD` = `git rev-parse stage-c5-done^{commit}` = `a7178d2233e175fac0c04b919c9f030103e8482f`；L1 + `edge/docs/spec/` 相对基线 / 工作区 / 暂存区三段 `git diff --name-status` 均空；`git tag --list` 9 个 → **零自动变更、无需批准**（附录 A 已批准基线不重复判定）。
- 本表只举证，最终 review 结论由用户本人签字。
