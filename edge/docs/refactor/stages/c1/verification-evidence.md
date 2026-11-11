# 阶段 c1 步骤 4 举证表（只举证、不下最终结论、不代签）

> 长表只落盘（用户 2026-11-11 精简模式）；`stage-verifier` 会话内产物由主 agent 落盘。最终 review 结论由用户本人 2026-11-11 口述签字，见 `HANDOFF-c1.md` §9。

## 1. 验收项逐条举证

| 编号 | 原措辞 | 证据（命令 + 输出 + 用例名 + test-report 对应节） | 举证结果 |
| --- | --- | --- | --- |
| `c1-1` | Fail-Fast | `python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` → `51 passed in 0.63s`（四步实跑）/ 收尾复核 `51 passed in 1.68s`（退出码均 0）；用例 `testMissingConfigFileFailsFast`（`error.code == ErrorCode.CONFIG`、`code.name == "CONFIG"`、`[CONFIG] 配置文件缺失: <path>`）、`testMalformedIniFailsFast`、`testInvalidEncodingFailsFast`（非法 UTF-8 转 `EdgeError(CONFIG)`）、`testInstanceFailFastLeavesNoSingleton`；实现 `loadConfig()` 的 `is_file()` 与 `except (OSError, UnicodeError, configparser.Error)`；`test-report.md` ① 第 1 行 / ③ / ④ / ⑤ | 齐备 · 可复核 |
| `c1-2` | 类型推断 int/float/bool/list/str | 同上 pytest 输出；用例 `testValuesAreInferredToNativeTypes`（`9000` / `-12` / `3.5` / `True` / `False` / `["10.0.0.1","10.0.0.2"]` / `"edge_node"` 均为具体值断言）、`testInferValueBoundaryCases`（`"1"`→`1` 非 bool、`"TRUE"`→`True`、`"1e3"`→`1000.0`、`"inf"`/`"nan"` 回落字符串、`" 7 , 8 "`→`[7, 8]`）；实现 `inferValue()`；`test-report.md` ① 第 2 行 / ③ / ④ | 齐备 · 可复核 |
| `c1-3` | `get(default=None)` 两分支 | 同上 pytest 输出；用例 `testGetIgnoresDefaultWhenKeyExists`（命中返回 `9000` 且 `infoRecords == []`）、`testGetWithoutDefaultFailsFast`（`[CONFIG] 配置项缺失: [comm] absent`）、`testGetWithDefaultReturnsValueAndLogsInfo`（`8080` / `"fallback"` / falsy `0` 与恰好 3 条 info 记录）；实现 `get()`；`test-report.md` ① 第 3 行 / ③ / ④ | 齐备 · 可复核 |
| `c1-4` | `instance()` 双检锁且可直接构造用于测试 | 同上 pytest 输出；用例 `testPlainConstructorsAreIndependent`（两实例 `first is not second`、数据独立、实现 `IConfig`）、`testInstanceIsDoubleCheckedSingleton`（`Barrier(8)` + 8 路 `ThreadPoolExecutor`，`all(result is results[0])`、`_sharedInstance is results[0]`）、`testInstanceDoesNotDependOnPlainConstructor`、`testInstanceFailFastLeavesNoSingleton`；实现 `instance()` 类变量 + 双检锁；`test-report.md` ① 第 4 行 / ③ / ④ | 齐备 · 可复核 |

## 2. 必交物与工具链

- `stages/c1/test-report.md`：六节齐备；④ 3 条可复现命令 + 真实输出 + 退出码 + 环境与前置条件；⑥ 4 行未覆盖项及原因（含归属阶段，未写「全部覆盖」）；不判红。
- `stages/c1/spec-digest.md`：五节齐备；§3 命名裁决表 `getValue→get`、`getInstance→instance()`、`ConfigManager→IniConfigManager`；§5 待确认项「无」。
- 工具链（收尾复核真实输出）：pytest `51 passed in 1.68s`（0）；ruff `All checks passed!`（0）；mypy `Success: no issues found in 37 source files`（0，附 `unused section(s)` note 非错误）。四步实跑另有 `51 passed in 0.63s`，耗时波动并列保留、不互相覆盖。含既有 39 例契约/单测全绿。
- 测试约定：12 个用例均有验收项编号注释；无 `assert True` / `assert x` / `assert ... is not None` 空洞断言（8 处 `is True/False` 均断言具体值/类型/枚举码/对象同一性）；未删用例、未加 skip、未改预期值；非法 UTF-8 泄漏内置异常由检视发现后在白名单内修实现 + 新增用例并复跑全绿，属 `test-visibility.mdc` §3.3 允许路径、无洗绿。
- Fake 与契约一致性：既有 `edge/tests/fakes/*`、`edge/tests/contract/*`、L1 契约层 `git diff --name-status stage-b-done` 为空；`FakeLogger` 四方法与 `i_logger.py` 对齐，`IniConfigManager.get()` 与 `i_config.py` 签名一致；本阶段零改动。
- 三条裁决：D-01 / D-02 / D-03 影响阶段均不含 c1；`edge/infra/` 关键词扫描（`selfCheck` / `linkState` / `transitionTo` / `seq` / `dedup` / `threading.Thread` / `getValue` / `getInstance`）0 命中；NAMING_AUTHORITY 适用且已遵守。
- 人工闸门：用户本人 2026-11-11 签字「我看过实现和 test-report.md 了，签字」；最终结论由用户本人口述，不由本表填写。

## 3. 举证结论

证据齐备（`c1-1`~`c1-4` 逐条可复核；必交物六节 + ④ 真实输出 + ⑥ 未覆盖项及原因齐备、不判红；工具链退出码均 0；L1 无未批准变更、非 blocked；人工闸门已签署）。无未通过项、无判红、无 blocked。最终 review 结论留空，由用户本人签字填写。

**本表只举证、不下最终结论、不代签。**
