# 阶段 c1 测试报告

> 极简口径（用户 2026-11-11）：保留六节标题与顺序，每节 ≤5 行、不写举证长表 / 检视长表；④ 真实命令与输出，⑥ 未覆盖项及原因（判红项，不省）。

## ① 验收项 → 用例对照表

- `c1-1` Fail-Fast → `testMissingConfigFileFailsFast`、`testMalformedIniFailsFast`、`testInvalidEncodingFailsFast`、`testInstanceFailFastLeavesNoSingleton`；覆盖。
- `c1-2` 类型推断 int/float/bool/list/str → `testValuesAreInferredToNativeTypes`、`testInferValueBoundaryCases`；覆盖。
- `c1-3` `get(default=None)` 两分支 → `testGetIgnoresDefaultWhenKeyExists`、`testGetWithoutDefaultFailsFast`、`testGetWithDefaultReturnsValueAndLogsInfo`；覆盖。
- `c1-4` `instance()` 双检锁且可直接构造用于测试 → `testPlainConstructorsAreIndependent`、`testInstanceIsDoubleCheckedSingleton`、`testInstanceDoesNotDependOnPlainConstructor`、`testInstanceFailFastLeavesNoSingleton`；覆盖。

## ② 使用了哪些 Fake、各自模拟什么边界

- `FakeLogger`：记录 `info(module, msg)` 与 `error(module, msg, exception)`，用于断言「缺 key 有 default 记 info」的 module 名、消息文本与恰好 3 条记录，避免真实落盘。
- `FakeConfig` 未用：本阶段被测对象就是 `IConfig` 真实实现，改用真实 INI 临时文件；Fake 与接口签名一致性由既有契约测试守卫，本阶段不改 Fake。

## ③ 用例表

- 12 个新增用例全部通过；输入为临时 INI（含缺文件、无节头、非法 UTF-8、五类值、缺节/缺键、falsy default、8 路并发屏障）。
- 预期均为具体值：`9000` / `-12` / `3.5` / `True` / `False` / `["10.0.0.1","10.0.0.2"]` / `"edge_node"` / `8080` / `"[CONFIG] 配置项缺失: [comm] absent"` / `infoRecords == [...]` / 8 路结果同一对象。
- 实际输出 `51 passed in 0.63s`，与预期逐条一致；无空洞断言、无跳过标记、无为变绿改被测代码；测试函数上方均带验收项编号注释。

## ④ 可复现的完整运行命令与运行环境

- 工作目录 `f:\new zhineng`（PowerShell）：`python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider`；`python -m ruff check edge`；`python -m mypy --config-file edge/pyproject.toml --no-incremental`。
- 真实输出：pytest `51 passed in 0.63s`（退出码 0）；ruff `All checks passed!`（0）；mypy `Success: no issues found in 37 source files`（0，附 `unused section(s)` note 非错误）。
- 环境：Windows / Python 3.10.8 / pytest 9.1.1 / ruff 0.17.4 / mypy 1.20.2；配置 `edge/pyproject.toml`（mypy 目标 3.9 strict）；前置条件：仅 pytest 自带 `tmp_path`，无外部 config.ini、端口或设备。

## ⑤ 汇总

- 通过 51 / 失败 0 / 跳过 0 / 总耗时 0.63s（含既有 39 例）；覆盖率采集按既有裁决不引入。
- `python-code-review` 极简检视一次：改动全在白名单内、`get` / `instance()` / camelCase 与 Doxygen 注释合规、模块内不 import 业务模块；发现非法 UTF-8 会泄漏内置异常，已在白名单内补 `UnicodeError` 转换并新增用例，复跑三项全绿，无阻断项。

## ⑥ 本阶段未覆盖项及原因

- `app_init` 从真实 `config.ini` 读路径并注入 `IConfig`、业务模块按注入取值、进程锁联动：归 `d`（装配与端到端），本阶段只交付配置门面。
- `LogManager` 异步队列、`info` 真实落盘与 `error(exception=e)` 附堆栈：现用 `FakeLogger`，归 `c2`。
- 配置运行期热重载 / 非 UTF-8 编码兼容、跨平台路径分隔符差异（现由 `Path` 承载）：本轮无此契约，归 `d` 与上板。
- 8 路屏障并发只验证双检锁唯一性，非高并发压测；真实麒麟 Linux / RK3588 上板与覆盖率采集按裁决不引入，归 `d`。
