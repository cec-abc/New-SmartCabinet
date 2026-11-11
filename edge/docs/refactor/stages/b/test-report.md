# 阶段 b 测试报告

> 极简口径（用户 2026-11-10）：保留六节标题与顺序，每节 ≤5 行、不放大表格；④ 真实输出，⑥ 未覆盖项及原因。

## ① 验收项 → 用例对照表

- `b-1` `stop()` 瞬间打断 `interruptibleWait` → `testStopInterruptsInterruptibleWaitImmediately`、`testInterruptibleWaitReturnsTrueWithoutStopSignal`、`testRunLoopExceptionBecomesEdgeErrorInLogger`；覆盖。
- `b-2` join 超时强制返回 → `testStopReturnsAfterJoinTimeout`；覆盖。
- `b-3` 重复 `stop` 幂等且 `BaseService` 三件套可多态 → `testRepeatedStopIsIdempotent`、`testBaseServiceLifecycleIsPolymorphic`；覆盖。

## ② 使用了哪些 Fake、各自模拟什么边界

- `FakeLogger`：记录 `error(module, msg, exception)`，模拟线程顶层内置异常转 `EdgeError(ErrorCode.CONFIG)` 的日志边界。
- 其余 Fake 未用：本阶段只测通用生命周期基类，无 socket / camera / engine / sink 交互；`FakeThread` 不替代真实线程（会掩盖 join 与唤醒时序）。

## ③ 用例表

- 6 个用例全部通过；输入为 `Event` / 等待秒数 / join 超时，预期为具体值（`elapsed < 0.8`、`< 1.0`、`is_alive()`、`rounds == []`、`calls == [...]`、`errorRecords` 1 条）。
- 实际输出：`39 passed in 0.57s`（全量 pytest，含既有 33 例）；结论「通过」；无空洞断言、无跳过标记、无为变绿改被测代码。

## ④ 可复现的完整运行命令与运行环境

- 工作目录 `f:\new zhineng`（cmd）：`python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider`、`python -m ruff check edge`、`python -m mypy --config-file edge/pyproject.toml --no-incremental`。
- 真实输出：pytest `39 passed in 0.57s`（退出码 0）；ruff `All checks passed!`（0）；mypy `Success: no issues found in 34 source files`（0，附 `unused section(s)` note 非错误）。
- 环境：Windows / Python 3.10.8 / pytest 9.1.1 / ruff 0.17.4 / mypy 1.20.2；配置 `edge/pyproject.toml`；无设备、端口、配置文件等前置条件。

## ⑤ 汇总

- 通过 39 / 失败 0 / 跳过 0 / 总耗时 0.57s；覆盖率采集按既有裁决不引入。
- `python-code-review` 检视一次（极简）：改动全在白名单内，camelCase / 类型标注 / Doxygen 注释合规，无空洞断言、无 `base/` 反向 import；首轮 ruff E501 ×2、mypy `func-returns-value` ×1 已修正并复跑全绿，无阻断项。

## ⑥ 本阶段未覆盖项及原因

- 真实业务线程（心跳 / 解码 / 采集 / 识别）启停与 `stopEvent` 打断：本阶段只交付通用基类，归 `c3` / `c4` / `c5`。
- 线程顶层异常的业务错误码细分（现用 `ErrorCode.CONFIG` 兜底）、`LogManager` 异步队列与停机统计落盘：归 `c2` / `c3` / `d`。
- 真实麒麟 Linux / RK3588 上板、并发 `start()` 竞态压测、`BaseService` 子类在 control 层多态联调：归 `d`；覆盖率采集按用户裁决不引入。
