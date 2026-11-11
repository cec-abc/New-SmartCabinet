# 阶段 c2 步骤 4 举证表（只举证、不下最终结论、不代签）

> 长表只落盘（用户 2026-11-11 精简模式）；`stage-verifier` 会话内产物由主 agent 落盘。最终 review 结论由用户本人 2026-11-11 口述签字，见 `HANDOFF-c2.md` §9。

## 1. 验收项逐条举证

| 编号 | 原措辞 | 证据（命令 + 输出 + 用例名 + test-report 对应节） | 举证结果 |
| --- | --- | --- | --- |
| `c2-1` | 唯一 BlockingQueue 异步消费、对外仅四方法 | `python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` → `63 passed in 1.17s`（0，首轮 `1.30s`）；用例 `testILoggerExposesOnlyFourMethods`（`{"rx","tx","info","error"}`、`"dict[str, object] \| bytes"`、`errorDefault is None`、无 `init`、无 `FrameData`）、`testSingleQueueAndAsyncConsumption`（`qsize()==4`、业务入队时文件内容为 `[""]`、停机后 `empty() is True`）、`testLogModeRoutingMergedAndSplit`（合并 1 个 Writer / 分开 4 个）、`testBuildRecordEncodesDictAndBytes`（`{"bytesHex": "0102"}`）、`testDirectoryCreationFailsFast`（`[CONFIG] 日志目录不可用`）、`testInstanceIsDoubleCheckedSingleton`（8 路屏障同一对象）；实现仅 1 处 `Queue(...)`，`LogExecutor` 接收注入队列；`test-report.md` ① 第 1 行 / ③ / ④ | 齐备 · 可复核 |
| `c2-2` | 跨天/超限滚动 + 磁盘清理 | 同上 pytest 输出；用例 `testRollOverAcrossDays`（文件名 `ALL_20261111_0001.log` / `ALL_20261112_0002.log`、`day` 序列 `["20261111","20261112","20261112"]`）、`testRollOverOnSizeLimit`（`maxFileSize=1`、4 个文件、行数 `[0,1,1,1]`）、`testDiskCleanupRemovesOldestFile`（低比例回调、最旧文件被删、`_removedCount == 1`、`ratioCalls == 2`）；`test-report.md` ① 第 2 行 / ③ / ④ | 齐备 · 可复核 |
| `c2-3` | 停机清空队列并关句柄 | 同上 pytest 输出；用例 `testStopDrainsQueueAndClosesHandles`（`empty() is True`、句柄全 `closed is True`、`len==4`、重复 `stop` 幂等）、`testStopWakesBlockedTake`（`isRunning() is False`、`len==2`）；`test-report.md` ① 第 3 行 / ③ / ④ | 齐备 · 可复核 |
| `c2-4` | `error(exception=e)` 自动附堆栈 | 同上 pytest 输出；用例 `testErrorAppendsStackTrace`（堆栈含 `Traceback (most recent call last)` / `CONFIG` / `配置缺失` / 用例名；无异常记录 `"stack" not in`）；`test-report.md` ① 第 4 行 / ③ / ④ | 齐备 · 可复核 |

## 2. 必交物与工具链

- `stages/c2/test-report.md`：六节齐备；④ 3 条可复现命令 + 真实输出 + 退出码 + 环境（Windows / Python 3.10.8 / pytest 9.1.1 / ruff 0.17.4 / mypy 1.20.2）与前置条件；⑥ 4 行未覆盖项及原因（含归属阶段，未写「全部覆盖」）；不判红。
- `stages/c2/spec-digest.md`：五节齐备；§3 命名裁决表（图上 `init(config)` / `getInstance` / `enqueue` / `rollFile` 只取语义，落地为 ILogger 四方法 + 类内 `instance()` + 构造注入）；§5 待确认项「无」。
- 工具链（收尾复核真实输出）：pytest `63 passed in 1.17s`（0）；ruff `All checks passed!`（0）；mypy `Success: no issues found in 39 source files`（0，附 `unused section(s)` note 非错误）。四步首轮另有 `63 passed in 1.30s` 与 ruff `N812 Lowercase 'log_manager' imported as non-lowercase ... Found 1 error`（退出码 1），已在测试白名单内改 import 别名后复跑全绿；耗时波动与首轮失败并列保留、不互相覆盖。含既有 51 例契约/单测全绿。
- 测试约定：12 个用例均有验收项编号注释（`c2-1`×6、`c2-2`×3、`c2-3`×2、`c2-4`×1）；无 `assert True` / 裸变量断言 / skip 标记；断言均为具体值、枚举码、文件行数、计数与对象同一性；未删用例、未改预期值、未改被测实现（N812 修正落在测试文件 import 别名）。
- Fake 与契约一致性：既有 `edge/tests/fakes/*`、`edge/tests/contract/*`、L1 契约层相对 `stage-c1-done` 的 `git diff --name-only` 为空；`FakeLogger` 四方法与 `i_logger.py` 对齐，本阶段零改动。
- 三条裁决：D-01 影响 `0/c4/c5/d`、D-02 `c3/d`、D-03 `c3/d`，均不含 c2；`log_manager.py` 无 `selfCheck` / `linkState` / `dedup` / `seenSeq` / 裸 `threading.Thread`（继承 `BaseThread`）；NAMING_AUTHORITY 适用且已遵守。
- 人工闸门：用户本人 2026-11-11 签字「我看过实现和 test-report.md 了，签字」；最终结论由用户本人口述，不由本表填写。

## 3. 举证结论

证据齐备（`c2-1`~`c2-4` 逐条可复核；必交物六节 + ④ 真实输出 + ⑥ 未覆盖项及原因齐备、不判红；工具链退出码均 0；`contract-guard` 相对 `stage-c1-done` L1 零自动变更、已批准基线项不重复判定、非 blocked；人工闸门已签署）。无未通过项、无判红、无 blocked。最终 review 结论留空，由用户本人签字填写。

**本表只举证、不下最终结论、不代签。**
