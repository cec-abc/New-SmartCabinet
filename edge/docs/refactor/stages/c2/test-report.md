# 阶段 c2 测试报告

> 极简口径（用户 2026-11-11）：保留六节标题与顺序，每节 ≤5 行、不写举证/检视长表；④ 真实命令与输出，⑥ 未覆盖项及原因（判红项，不省）。

## ① 验收项 → 用例对照表

- `c2-1` 唯一 BlockingQueue 异步消费、对外仅四方法 → `testILoggerExposesOnlyFourMethods`、`testSingleQueueAndAsyncConsumption`、`testLogModeRoutingMergedAndSplit`、`testBuildRecordEncodesDictAndBytes`、`testDirectoryCreationFailsFast`、`testInstanceIsDoubleCheckedSingleton`；覆盖。
- `c2-2` 跨天/超限滚动 + 磁盘清理 → `testRollOverAcrossDays`、`testRollOverOnSizeLimit`、`testDiskCleanupRemovesOldestFile`；覆盖。
- `c2-3` 停机清空队列并关句柄 → `testStopDrainsQueueAndClosesHandles`、`testStopWakesBlockedTake`；覆盖。
- `c2-4` `error(exception=e)` 自动附堆栈 → `testErrorAppendsStackTrace`；覆盖。

## ② 使用了哪些 Fake、各自模拟什么边界

- `FakeLogger`：仅用于 `inspect` 核验 `ILogger` 四方法签名与「零落盘」对照，断言 Fake 公开方法恰为 `error/info/rx/tx`；本阶段未修改任何 Fake。
- 其余 Fake 未用：被测对象就是 `ILogger` 真实实现，落盘用 `tmp_path` 真实文件；`config.ini`、端口、设备均未参与。

## ③ 用例表

- 12 个新增用例全部通过；输入：dict / bytes 负载、可控时钟跨天、`maxFileSize=1`、注入低磁盘比例、`EdgeError(CONFIG)`、未启动与已启动两种停机路径、8 路并发屏障。
- 预期均为具体值：`abstractNames == {rx,tx,info,error}`、`rxAnnotation == "dict[str, object] | bytes"`、`["RX","TX","INFO","ERROR","INFO"]`、`{"bytesHex": "0102"}`、文件名 `ALL_20261112_0002.log`、行数 `[0,1,1,1]`、`_removedCount == 1`、`ratioCalls == 2`、堆栈含 `CONFIG`/`配置缺失`/`testErrorAppendsStackTrace`。
- 实际输出 `63 passed in 1.17s`，与预期逐条一致；无空洞断言、无跳过标记、无为变绿改被测代码；测试函数上方均带验收项编号注释。

## ④ 可复现的完整运行命令与运行环境

- 工作目录 `f:\new zhineng`（PowerShell）：`python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider`；`python -m ruff check edge`；`python -m mypy --config-file edge/pyproject.toml --no-incremental`。
- 真实输出：pytest `63 passed in 1.17s`（0）；ruff `All checks passed!`（0）；mypy `Success: no issues found in 39 source files`（0，附 `unused section(s)` note 非错误）。
- 首轮如实：pytest `63 passed in 1.30s`；ruff `N812 Lowercase 'log_manager' imported as non-lowercase ... Found 1 error`（退出码 1），已在白名单内改测试文件 import 别名后复跑全绿；耗时波动并列保留，不互相覆盖。
- 环境：Windows / Python 3.10.8 / pytest 9.1.1 / ruff 0.17.4 / mypy 1.20.2；配置 `edge/pyproject.toml`（mypy 目标 3.9 strict）；前置条件：仅 pytest 自带 `tmp_path`，无外部 config.ini、端口或设备。

## ⑤ 汇总

- 通过 63 / 失败 0 / 跳过 0 / 总耗时 1.17s（含既有 51 例）；覆盖率采集按既有裁决不引入。
- `python-code-review` 极简检视一次：改动全在白名单内、构造注入/类型标注/Doxygen/异常转换/唯一队列/接口四方法合规，无 P0/P1/P2 阻断项；跨阶段遗留项见 ⑥；长表不落盘。
- 步骤 4 `stage-verifier` 未进入，停在人工闸门等用户本人 review 签字。

## ⑥ 本阶段未覆盖项及原因

- `app_init` 从真实 `config.ini` 读 logDir / maxFileSize / logMode / 阈值并注入、进程锁联动：归 `d`（装配与端到端），本阶段参数全部构造注入。
- 真实 `shutil.disk_usage`、平台路径/换行差异、麒麟 Linux / RK3588 上板：归 `d` 与上板；本阶段用注入比例回调与 `tmp_path` 隔离。
- `ILogger` 接入 TCP/USB/识别业务线程与一键停机严格串行：归 `c3`~`c5` 与 `d`；本阶段只交付日志门面。
- logMode 运行期热切换、有界队列入队阻塞策略、坏 JSON 记录容错：本轮无此契约，归 `d` 与上板；未写「全部覆盖」。
