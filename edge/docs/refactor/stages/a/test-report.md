# a 阶段测试报告

> 必交物，六节齐备（格式参照 `edge/docs/refactor/stages/0/test-report.md`）。
> 本阶段目标：已有骨架「审读 + 契约一致性核验 + 补可举证单测」；验收项措辞照抄
> `.codebuddy/skills/edge-refactor/references/stage-catalog.md` §2 阶段 a，未改写。
> 新增用例文件：`edge/tests/unit/test_stage_a_contract_alignment.py`（11 个用例）；
> 既有 22 个用例（契约测试 10 + 阶段 0 补强 12）零改动、随全量 pytest 一并执行。

## ① 验收项 → 用例对照表

| 验收项编号 | 验收项 | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| `a-1` | `interfaces/` 零实现、零业务 import、全 camelCase、Doxygen 注释覆盖。 | 新增：`testInterfaceAbstractMethodBodiesCarryNoImplementation`、`testInterfaceMethodNamesAreAllCamelCase`、`testInterfaceModulesImportNoBusinessModules`、`testInterfaceDoxygenMarkersCovered`；文档举证：`edge/docs/refactor/stages/a/spec-digest.md` §2.3 逐文件审读表 | 单测 + 文档双重举证：9 个 `interfaces/` 文件逐文件核验四要素，31 个抽象方法体仅 `(None,)` 常量、10 个类公开方法名精确等于 L1 §3 表、AST + 运行时双证据零业务 import、`## @brief` 合计 47 处；④ 命令实测全量通过 |
| `a-2` | 8 个 Fake 与 8 个接口签名逐一对齐；`fake_logger.py` 的 `FrameData` 断裂有明确结论与处置。 | 新增：`testAllFakeMethodSignaturesAlignWithInterfaces`、`testAllFakesAreInstantiableSubclassesOfInterfaces`、`testFakeLoggerFrameDataBreakageIsResolved`；既有，未修改：`testAllFakesSatisfyContracts`、`testInterfacesAreAbstract`、`testFakeLoggerRecordsFourMethods`、`testAllFakeMethodsCallable`、`testAllSinkFakesCallable`；文档举证：`spec-digest.md` §2.4 | 31 对签名逐一对齐（`inspect.signature` 全等 + 参数名 / 返回注解锚定具体值）、10 个 Fake `isinstance`/`issubclass` 全成立；`FrameData` 断裂正式结论见 `spec-digest.md` §2.4：虚构类型导入、Fake 侧 5 行最小修复（阶段 0 B1 提前处置）、`i_logger.py` 零改动；阶段 a 按原措辞独立验收 |
| `a-3` | 契约测试可收集、可执行、通过；mypy（3.9 strict）通过。 | 新增：`testContractTestFunctionsAreCollectableAndExecutable`、`testMypyConfigTargetsPython39Strict`；既有契约测试 10 个 + 阶段 0 补强 12 个 | 两个契约模块各 5 个 `testXxx` 全部可收集 / 可执行，`windowsOnly` 签名参数恰 `("reason",)`；`pyproject.toml` 实测 `python_version = "3.9"` / `strict = true`；④ mypy `Success: no issues found in 30 source files`（退出码 0）、pytest `33 passed`（退出码 0） |
| `a-4` | 已知 9 处 Fake 字段类型标注缺口有结论（补齐或列入未覆盖项并说明）。 | 新增：`testNineFakeFieldAnnotationsAreExplicit`、`testNineFakeFieldsRetainConcreteInitialValues`；文档举证：`spec-digest.md` §2.6 / §5 | 按用户 2026-11-10 裁决**按 10 处口径收口**：原 9 处 + `fake_platform_adapter.py` L15 `self.lockResult: BinaryIO \| None = lockResult` 全部补齐，5 个 Fake 文件共 10 处；9 处 `ast.AnnAssign` 标注文本逐项精确、运行时初值与回调行为不变；`a-4` **不列入 ⑥ 未覆盖项** |

> 2026-11-10 用户明确批准并落地一份 L1 契约 diff（`edge/tests/contract/test_phase0_foundation.py` 新增 typed 装饰器 wrapper `windowsOnly`、两处 `@pytest.mark.skipif` 改为 `@windowsOnly`），不改 `edge/pyproject.toml`、不删用例、不加 skip 标记、不整体关闭错误码、不改既有断言。这是**首次经用户批准的 L1 变更**；用户要求收尾时登记进 `references/decisions.md` 与 handoff 作为后续 baseline 对比依据，本阶段**未收尾、未代做**。

## ② 使用了哪些 Fake、各自模拟什么边界

| Fake 名称 | 对应接口 | 模拟的边界 / 异常 | 为何本阶段需要 |
| --- | --- | --- | --- |
| `FakeConfig`（`fake_config.py`） | `IConfig` | 预设 `dict` 键值；`get(section, key)` 命中返回具体值、缺 key 走 `default` 分支 | `a-2` 通用 `get(section, key, default=None)` 签名与两分支可用；不触碰真实 `config.ini` |
| `FakeLogger`（`fake_logger.py`） | `ILogger` | `rx/tx/info/error` 四方法只记录调用；`error` 记录 `exception` 对象占位 | `a-2` 四方法签名对齐与 `FrameData` 断裂结论（现仅导入 `ILogger`）；不做真实磁盘 IO |
| `FakeThread`（`fake_thread.py`） | `IThread` | `startCount` / `stopTimeouts` / `running` 纯状态位，不创建线程 | `a-2` 三方法签名；`a-4` 字段标注补齐与运行时行为不变 |
| `FakeSocket`（`fake_socket.py`） | `ISocket` | 固定 `recvData` 帧、`send` 返回 `bool`、`connected` / `closed` 标志、`sentFrames` 记录 | `a-2` 四方法签名；`a-4` 字段标注补齐；不建立真实连接 |
| `FakeCameraDevice`（`fake_camera_device.py`） | `ICameraDevice` | 固定 `frame`、`opened` / `closed` 状态、`getStatus()` 返回 `{"opened": ...}` | `a-2` 四方法签名；`a-4` 字段标注补齐；不访问摄像头设备 |
| `FakeRecognitionEngine`（`fake_recognition_engine.py`） | `IRecognitionEngine` | `loadedPaths` 记录、`infer()` 返回空 `list[DetectionItem]` | `a-2` `loadModel` / `infer` 签名对齐；不加载模型、不触发推理 |
| `FakePlatformAdapter`（`fake_platform_adapter.py`） | `IPlatformAdapter` | `lockResult: BinaryIO \| None` 构造注入模拟锁占用 / 取锁成功；`lockCalls` 记录；路径 / 换行 / 信号 / 时钟全为内存固定值 | `a-2` 五方法签名；`a-4` 第 10 处字段级标注（按用户裁决补齐）；不触碰 `msvcrt` / `fcntl` |
| `FakeSignalSink` / `FakeCaptureSink` / `FakeRecognitionSink`（`fake_sinks.py`） | `SignalSink` / `ICaptureSink` / `IRecognitionSink` | 8 个回调只记录事件列表；`linkUpCount` 计数 | `a-2` 8 个 Sink 回调签名逐一对齐；`a-4` `linkUpCount` 标注补齐；不在回调内做阻塞 IO |

> 本阶段未新增接口，无需新增 Fake；8 个 `fake_*.py` 与 8 个 `i_*.py` 按文件对核验。`Fake` 侧仅 5 个文件发生字段类型标注补齐（共 10 处），方法签名与既有断言零改动。

## ③ 用例表

③ 表「实际」列统一引用本轮全量 `pytest -q` 真实输出 `................................. [100%]` / `33 passed in 0.32s`（33 个点全为 `.`，无 `F` / `E` / `s`）；本轮未采集 `-v` 逐用例 `PASSED [xx%]` 片段，**不编造**逐用例输出。既有用例按文件分组列 3 行。

| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| `test_interface_contracts.py` 5 个既有用例 | 8 类 Fake 实例、`ILogger()`、`rx/tx/info/error`、6 个 Fake 方法、3 个 Sink 回调 | `isinstance(FakeX(), IX)` 全成立、抽象方法抛 `TypeError`、四方法记录精确、Sink 事件列表精确 | 全量 `-q`：`33 passed in 0.32s`，5 个用例在 33 个 `.` 内 | 通过 |
| `test_phase0_foundation.py` 5 个既有用例 | `EdgeError`、平台工厂、Linux 锁骨架、双进程取锁 | 五码 `code.name`、`WindowsAdapter`、`EdgeError(CONFIG)`、`returncode == 0` | 全量 `-q`：`33 passed in 0.32s`，win32 下两条既有条件用例实际执行、跳过为 0 | 通过 |
| `test_stage0_error_and_lock_guards.py` 12 个既有用例 | 五码 `EdgeError`、`patch.object(sys, "platform", ...)`、`FakePlatformAdapter` + `io.BytesIO()` | 精确前缀、三平台分支、占锁 / 取锁 / 释放幂等 | 全量 `-q`：`33 passed in 0.32s`，12 个用例在 33 个 `.` 内 | 通过 |
| `testInterfaceAbstractMethodBodiesCarryNoImplementation`（新增，`a-1`） | 10 个接口 ABC 的 `__abstractmethods__` | `__isabstractmethod__ is True`、`co_consts == (None,)`、`checked` 恰 31、首尾项精确 | 全量 `-q`：`33 passed in 0.32s`；ruff `All checks passed!` | 通过 |
| `testInterfaceMethodNamesAreAllCamelCase`（新增，`a-1`） | 10 个接口类 `vars(cls)` | 公开方法名精确等于 L1 §3 表、无下划线 / 无首字母大写、`len(expected) == 10` | 全量 `-q`：`33 passed in 0.32s` | 通过 |
| `testInterfaceModulesImportNoBusinessModules`（新增，`a-1`） | 9 个 `interfaces/*.py` 源码 AST + `importlib` 模块对象 | import 清单逐文件精确匹配、无 `edge.platform` / `cv2` / `numpy` / `threading` 等业务前缀泄漏 | 全量 `-q`：`33 passed in 0.32s` | 通过 |
| `testInterfaceDoxygenMarkersCovered`（新增，`a-1`） | 9 个接口文件源码文本 | 逐文件 `## @brief` / `@param` / `@return` 计数精确、`totalBrief == 47`、模块 docstring 非空 | 全量 `-q`：`33 passed in 0.32s` | 通过 |
| `testAllFakeMethodSignaturesAlignWithInterfaces`（新增，`a-2`） | 31 对 `(接口类, Fake 类, 方法名, 参数名, 返回注解)` | `inspect.signature` 全等、参数名与返回注解锚定具体值、`aligned == 31`、8 个 `i_*.py` / 8 个 `fake_*.py` | 全量 `-q`：`33 passed in 0.32s` | 通过 |
| `testAllFakesAreInstantiableSubclassesOfInterfaces`（新增，`a-2`） | 10 组 `(Fake, 接口)` | `isinstance` / `issubclass` 全 `True`、`results == 10`、首项精确 | 全量 `-q`：`33 passed in 0.32s` | 通过 |
| `testFakeLoggerFrameDataBreakageIsResolved`（新增，`a-2`） | `edge.interfaces.i_logger` 模块、`fake_logger.py` 源码 AST、`FakeLogger()` | 模块无 `FrameData`、源码 `FrameData` 0 命中、导入恰 `["ILogger"]`、`rxRecords == [("tcp", b"{}")]`、`txRecords == [("tcp", b"ack")]` | 全量 `-q`：`33 passed in 0.32s` | 通过 |
| `testContractTestFunctionsAreCollectableAndExecutable`（新增，`a-3`） | 两个契约测试模块反射 + `windowsOnly` | 各模块恰 5 个 `testXxx`、共 10 个可调用、`windowsOnly` 参数恰 `("reason",)` | 全量 `-q`：`33 passed in 0.32s`；mypy `Success: no issues found in 30 source files` | 通过 |
| `testMypyConfigTargetsPython39Strict`（新增，`a-3`） | `edge/pyproject.toml` 文本行 | 恰 `python_version = "3.9"` 与 `strict = true` 各 1 行 | 全量 `-q`：`33 passed in 0.32s`；mypy 实跑退出码 0 | 通过 |
| `testNineFakeFieldAnnotationsAreExplicit`（新增，`a-4`） | 4 个 Fake 文件源码 AST | 9 处 `ast.AnnAssign` 标注文本逐项精确、`total == 9`、`len(expected) == 4` | 全量 `-q`：`33 passed in 0.32s`；ruff `All checks passed!` | 通过 |
| `testNineFakeFieldsRetainConcreteInitialValues`（新增，`a-4`） | `FakeCameraDevice` / `FakeSignalSink` / `FakeSocket` / `FakeThread` | `frame == b"frame"`、`opened is False`、`linkUpCount == 1`、`sentFrames == [b"ack"]`、`stopTimeouts == [1.0]` 等具体值 | 全量 `-q`：`33 passed in 0.32s` | 通过 |

> ③ 附注 1（新测试文件复核）：`edge/tests/unit/test_stage_a_contract_alignment.py` 共 11 个测试函数，全部 `-> None`；每个函数上方有 `# 对应验收项 a-x：...` 中文编号注释；无 `assert True` / `assert x` / `assert ... is not None` 空洞断言，均为具体值、计数、`inspect.signature`、`ast.AnnAssign`、`isinstance` / `issubclass` 精确断言；无 `@pytest.mark.*` 跳过标记；文件顶部唯一模块 docstring + `from __future__ import annotations`；常量 `EDGE_ROOT` / `INTERFACE_CLASSES` / `ALIGNMENT_CASES` 为 UPPER_SNAKE_CASE。用户 2026-11-10 已实测「33 passed / ruff 全过 / mypy 30 files、11 个用例、无空洞断言」，与主 agent 复跑一致。
> ③ 附注 2（第 10 处）：按用户 2026-11-10 追加裁决，`fake_platform_adapter.py` L15 `self.lockResult: BinaryIO \| None = lockResult` 一并补齐，按 **10 处口径收口**，裁决写入 `spec-digest.md` §5；用户明确「不重写已有测试」，故 `a-4` 既有单测仍锚定 9 处，第 10 处由实现改动、④ 三项工具链实跑与改动清单举证，**不作为 `a-4` 未覆盖项**。
> ③ 附注 3（历史事实）：`stages/0/test-report.md` 与 `HANDOFF-0.md` 记录的阶段 0 mypy 历史失败（`Found 2 errors in 1 file`、退出码 1）是当时真实输出，与本阶段全绿属两个时间点，**不倒改、不洗绿**。

## ④ 可复现的完整运行命令与运行环境

- 本次实际执行的三条命令（工作目录已为工作区根 `f:\new zhineng`）：

```
cd "f:\new zhineng" && python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider
cd "f:\new zhineng" && python -m ruff check edge
cd "f:\new zhineng" && python -m mypy --config-file edge/pyproject.toml --no-incremental
```

  - 若执行器工作目录已是 `f:\new zhineng`，等价形式为去掉 `cd "f:\new zhineng" && ` 前缀；`-c edge/pyproject.toml edge/tests` 的配置与路径限定**不可省**，否则从工作区根会误收集 `dual_crop_stitch/` 旧项目测试。
  - `-p no:cacheprovider` 避免写入 `.pytest_cache`；`--no-incremental` 不做 mypy 增量缓存；三条命令均为只读检查 + 内存态用例。

- 各条真实输出（本轮全量复跑，最终状态：10 处字段标注补齐 + 11 个新增用例）：

  - `python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider`：
    `.................................                                        [100%]` / `33 passed in 0.32s`，退出码 0。
  - `python -m ruff check edge`：`All checks passed!`，退出码 0。
  - `python -m mypy --config-file edge/pyproject.toml --no-incremental`：
    `edge/pyproject.toml: note: unused section(s): module = ['_pytest.*', 'pytest.*']`（`warn_unused_configs` 的 note，非错误）/ `Success: no issues found in 30 source files`，退出码 0。

- 时间点 A（2026-11-10，用户批准的 L1 diff 落地后立即实跑，29 个源文件 / 22 个用例，同为真实输出，与本轮并列保留、不互相覆盖）：

  - mypy：`edge/pyproject.toml: note: unused section(s): module = ['_pytest.*', 'pytest.*']` / `Success: no issues found in 29 source files`，退出码 0。
  - ruff：`All checks passed!`，退出码 0。
  - pytest：`...................... [100%]` / `22 passed in 0.29s`，退出码 0。

- 环境：

  - OS：`Windows-10-10.0.26200-SP0`（`platform win32`）；Python `3.10.8`，解释器 `C:\Users\Xiaojiu\AppData\Local\Programs\Python\Python310\python.exe`，`sys.prefix == sys.base_prefix` → **无独立 venv**。
  - 依赖：pytest `9.1.1`（pluggy `1.7.0`）、ruff `0.17.4`、mypy `1.20.2`；均通过 `python -m ...` 调用。上述版本号沿用 `stages/0/test-report.md` ④ 的实测记录，本轮未重新核验版本、不编造新数值。
  - 配置：`edge/pyproject.toml` 内 mypy `python_version = "3.9"` / `strict = true` / `files = ["edge"]`，pytest `pythonpath = ["."]`，ruff `target-version = "py39"` / `line-length = 100`。
  - 工作目录：`f:\new zhineng`（`CODEBUDDY.md` §0 路径基准）。

- 前置条件：

  - 8 个 Fake 与 11 个新增用例全为内存态，不占用端口、设备、真实锁文件；仅既有 `testSecondProcessCannotAcquireLock` 使用 `tempfile.TemporaryDirectory()` 建临时锁文件并在 `finally` 中释放。
  - 无 Fixture 文件、无 `conftest` 覆盖、无外部服务依赖；`main.py` / `app_init.py`（阶段 d）尚未建立，不影响本阶段收集与执行。
  - 阶段 0 B1 已修复 `fake_logger.py` 的 `FrameData` 导入，`test_interface_contracts.py` 的 `FakeLogger` 导入可在收集期通过。
  - 未采集代码覆盖率：未安装 / 未配置 `pytest-cov`、命令未带 `--cov`，按用户裁决不引入。

## ⑤ 汇总

| 通过 | 失败 | 跳过 | 总耗时 | 覆盖率 |
| --- | --- | --- | --- | --- |
| 33 | 0 | 0 | `0.32s`（本轮 `pytest -q`：`33 passed in 0.32s`） | 未采集（未安装 / 未配置 `pytest-cov`、命令未带 `--cov`）；不编造覆盖率数字，`a-1`~`a-4` 均有举证，未覆盖分支见 ⑥，不写「全部覆盖」 |

> ⑤ 附注：`33` = 既有 22（`test_interface_contracts.py` 5 + `test_phase0_foundation.py` 5 + `test_stage0_error_and_lock_guards.py` 12）+ 新增 11；`-q` 输出 33 个点全为 `.`，无 `F` / `E` / `s`，故跳过为 0。ruff `All checks passed!`、mypy `Success: no issues found in 30 source files` 均为退出码 0；mypy 的 `unused section(s)` 为 note 非错误。`a-4` 的 10 处字段标注已全部补齐，按用户裁决不列入 ⑥ 未覆盖项。用户本人实测 `33 passed` / ruff 全过 / mypy `Success（30 files）` 与本轮复跑一致。

## ⑥ 本阶段未覆盖项及原因

| 未覆盖的验收项 / 分支 | 原因 | 归属阶段 | 补测计划 |
| --- | --- | --- | --- |
| 真实麒麟 Linux / RK3588 上板分支与 `LinuxAdapter.lockFile` 的 `fcntl.flock` 真实实现 | 本阶段 `platform/` 分支仅由阶段 0 的 `patch.object(sys, "platform", ...)` 与 `FakePlatformAdapter` 构造注入覆盖，未在真实上板环境验证 `fcntl.flock` / `msvcrt` 缺席分支；`interfaces/` 与 Fake 本身不触碰系统资源 | `d`（上板 / 端到端） | 上板阶段补真实双进程取锁 / 占用失败用例与 `d-3` / `d-4` 端到端用例 |
| `PlatformFactory` 真实第三方 OS 分支 | win32 / linux / 其余平台三分支本阶段以 `patch.object(sys, "platform", ...)` 模拟，未在真实第三方 OS 上执行 | `d`（真实平台） | 保留平台无关模拟用例作为 else 分支常态举证，真实平台执行留待上板 |
| 代码覆盖率采集 | 未安装 / 未配置 `pytest-cov`，命令未带 `--cov`；按用户 2026-11-10 裁决不引入覆盖率采集，⑤ 如实写「未采集」 | 用户裁决 | 是否引入行 / 分支覆盖率采集由用户拍板；本阶段不以覆盖率数字替代逐项举证 |
| `patch.object(sys, "platform", ...)` 的规范适用边界 | `编码规范规则.txt` §4.5「全项目只有 PlatformFactory 允许出现 `sys.platform`」是否把测试侧 monkeypatch 目标视为受控例外，属平台分支收敛约束的解释空间；命名复核结论（不属 NAMING_AUTHORITY 管辖、无命名口径问题、只出结论不改上一阶段产物）已写入 `spec-digest.md` §2.7，本阶段不扩大范围、不下裁决 | 用户裁决 / 后续阶段 | 由用户明确该边界后，按裁决决定是否调整测试侧写法；本阶段不改上一阶段任何产物文件 |
| `i_sinks.py` 回调方法计数资料差异 | `stage-catalog.md` §0 #9 / #25 记「10 个抽象方法体 / 10 个回调签名」，L1 §3 与源码实际为 8 个回调方法（4 + 2 + 2）；`a-2` 已按 L1 / 源码的 8 个逐一对齐，结论不受影响 | L3 资料修订 / 用户裁决 | 是否修订 `stage-catalog.md` 措辞由用户决定；本阶段不改 L3、不改验收项定义 |
| 「首次经用户批准的 L1 变更」登记进 `references/decisions.md` 与 handoff | 用户明确该登记是**收尾动作**，作为后续 baseline 对比依据；本阶段停在人工闸门，未执行 `/stage-done` | 收尾（`/stage-done a`，人工闸门之后） | 用户 review 签字后，由 `memory-steward` 按 handoff 模板登记，并同步项目记忆 |

> ⑥ 未写「全部覆盖」；以上 6 行均为未覆盖项 / 待收敛事项及原因。`a-4` 的 10 处字段标注已按用户裁决全部补齐，**不列为未覆盖项**；第 10 处未纳入单测断言的说明见 ③ 附注 2（用户「不重写已有测试」，由实现改动 + ④ 工具链实跑举证）。人工闸门：本阶段停在 `test-writer` 之后、`stage-verifier`（步骤 4）之前，等待用户本人 review 并签字；本报告不含最终 review 结论。
