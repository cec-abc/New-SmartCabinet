# 0 阶段测试报告

## ① 验收项 → 用例对照表

| 验收项编号 | 验收项 | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| `0-1` | 逐文件审读结论齐备，明确「新骨架 / 需修正」及依据。 | 文档举证（非单测）：`edge/docs/refactor/stages/0/spec-digest.md` §2.2 逐文件审读结论与契约核验表 | 已由 spec-digest.md §2.2 举证（4 个骨架文件全部判「新骨架·达标、无需修正」，附逐文件行号依据） |
| `0-2` | `EdgeError` 抛出 / 捕获与 `code.name` 日志格式正确。 | 新增：`testErrorCodeEnumeratesFiveCodes`、`testEdgeErrorRaiseAndCatchCarriesExactCodeName`、`testEdgeErrorFormatsEveryCodeNamePrefix`；既有，未修改：`testEdgeErrorCarriesCodeName` | 单测已举证（3 新增 + 1 既有，④ 命令实测 PASSED）；五码成员名 / 整数值 / 抛捕 / 精确 `[CODE]` 前缀均有断言；未覆盖分支见 ⑥ |
| `0-3` | `PlatformFactory` Windows 返回 `WindowsAdapter`；Linux 分支 `NotImplementedError` + TODO。 | 新增：`testFactoryReturnsWindowsAdapterForWin32`、`testFactoryReturnsLinuxAdapterForLinux`、`testFactoryRejectsUnsupportedPlatformWithConfig`、`testLinuxLockSkeletonMarksTodoAndRaisesExactMessage`；既有，未修改：`testFactoryReturnsWindowsAdapter`、`testLinuxAdapterSkeletonRaises` | 单测已举证（4 新增 + 2 既有，实测 PASSED）；win32 / linux / 其余平台三分支与 TODO 骨架消息均有断言；真实 `fcntl.flock` 上板实现未覆盖，见 ⑥ |
| `0-4` | 双开取锁失败并立即退出；已知缺口「进程锁无调用方」写入未覆盖项及原因。 | 新增：`testAcquireOccupiedLockRaisesConfigViaFake`、`testAcquireConvertsSkeletonErrorPreservingCause`、`testAcquireOrExitExitsImmediatelyWithConfigMessage`、`testAcquireOrExitKeepsLockWhenAcquired`、`testReleaseIsIdempotentAndClosesHandle`；既有，未修改：`testLinuxSkeletonIsConvertedToEdgeError`、`testSecondProcessCannotAcquireLock` | 单测已举证（5 新增 + 2 既有，实测 PASSED）；占锁失败、内置异常转换、`sys.exit` 立即退出、成功分支、`release()` 幂等均有断言；已知缺口「进程锁无调用方」已按口径写入 ⑥ 第 2 行 |

> B1（`fake_logger.py` 一次性最小修复）不占 `0-1`~`0-4` 编号，仅作阶段 0 提前处置留痕，见 ⑥ 第 1 行。
> 新增用例文件：`edge/tests/unit/test_stage0_error_and_lock_guards.py`；既有契约测试 `edge/tests/contract/*` 的断言零改动。

## ② 使用了哪些 Fake、各自模拟什么边界

| Fake 名称 | 对应接口 | 模拟的边界 / 异常 | 为何本阶段需要 |
| --- | --- | --- | --- |
| `FakePlatformAdapter`（`edge/tests/fakes/fake_platform_adapter.py`，既有、未修改） | `IPlatformAdapter` | `lockFile()` 返回值由构造注入：传 `None` 模拟「锁文件已被占用 / 双开」，传可关闭的二进制句柄模拟「取锁成功」；`lockCalls` 记录调用路径；全程不触碰 `msvcrt` / `fcntl` 与真实锁文件 | 新增用例需在平台无关前提下稳定复现「占锁 → `EdgeError(CONFIG)`」「`acquireOrExit()` 立即 `sys.exit`」「`release()` 关闭句柄且幂等」，避免依赖真实 OS 分支与真实文件锁 |

> 如实说明：新增用例**仅**使用上表 1 个 Fake，未使用 `FakeLogger` 等其余 7 个 Fake；`LinuxAdapter` 是被测的真实骨架实现（非 Fake）；`io.BytesIO()` 是标准库内存二进制句柄（非 Fake），仅用于断言 `release()` 确实调用了 `close()`；`test_interface_contracts.py` 复用 Fake 的 5 个既有用例本阶段未改动、未作为新增用例的 Fake。本阶段未新增接口，故无需新增 Fake。

## ③ 用例表

| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| `testAllFakesSatisfyContracts`（既有，未修改） | 8 类 Fake 实例 | `isinstance(FakeX(), IX)` 全成立 | `-v`：`testAllFakesSatisfyContracts PASSED [  4%]`；10 条 `isinstance` 断言全通过 | 通过 |
| `testInterfacesAreAbstract`（既有，未修改） | 直接 `ILogger()` | 抛 `TypeError` | `-v`：`PASSED [  9%]`；`pytest.raises(TypeError)` 命中 | 通过 |
| `testFakeLoggerRecordsFourMethods`（既有，未修改） | `rx/tx/info/error` 各调用一次 | `rxRecords == [("tcp", b"{}")]`、`infoRecords == [("tcp", "hello")]` | `-v`：`PASSED [ 13%]`；4 个记录断言全通过 | 通过 |
| `testAllFakeMethodsCallable`（既有，未修改） | 6 个 Fake 的方法调用 | `config.get("comm", "port") == 9000`、`socket.send(b"ack") is True` | `-v`：`PASSED [ 18%]` | 通过 |
| `testAllSinkFakesCallable`（既有，未修改） | 3 个 Sink 事件回调 | `linkDownEvents == [("timeout", "HEART")]`、`linkUpCount == 1` | `-v`：`PASSED [ 22%]` | 通过 |
| `testEdgeErrorCarriesCodeName`（既有，未修改） | `EdgeError(ErrorCode.FRAME_PARSE, "坏帧")` | `.code is ErrorCode.FRAME_PARSE`、`"[FRAME_PARSE]" in str(error)` | `-v`：`PASSED [ 27%]`；`error.code.name == "FRAME_PARSE"` | 通过 |
| `testFactoryReturnsWindowsAdapter`（既有，未修改） | `PlatformFactory.create()`（真实 win32） | `isinstance(..., WindowsAdapter)` | `-v`：`PASSED [ 31%]`（win32 未触发 skip） | 通过 |
| `testLinuxAdapterSkeletonRaises`（既有，未修改） | `LinuxAdapter().lockFile("unused.lock")` | 抛 `NotImplementedError` | `-v`：`PASSED [ 36%]` | 通过 |
| `testLinuxSkeletonIsConvertedToEdgeError`（既有，未修改） | `ProcessFileLock(LinuxAdapter(), path).acquire()` | 抛 `EdgeError`，`.code is ErrorCode.CONFIG` | `-v`：`PASSED [ 40%]` | 通过 |
| `testSecondProcessCannotAcquireLock`（既有，未修改） | 主进程持锁 + 子进程取锁 + 临时锁文件 | `returncode == 0` 且 `"CONFIG" in stdout` | `-v`：`PASSED [ 45%]`（win32 未触发 skip） | 通过 |
| `testErrorCodeEnumeratesFiveCodes`（新增） | 迭代 `ErrorCode` | 成员名恰 5 项、整数值 `[1, 2, 3, 4, 5]` | `-v`：`PASSED [ 50%]`；实测 `['CONFIG', 'LINK_DOWN', 'FRAME_PARSE', 'INFERENCE_TIMEOUT', 'CAPTURE']`、`[1, 2, 3, 4, 5]`、`ErrorCode.CONFIG.value == 1` | 通过 |
| `testEdgeErrorRaiseAndCatchCarriesExactCodeName`（新增） | `raise EdgeError(ErrorCode.LINK_DOWN, "链路中断")` | 捕获后 `.code is LINK_DOWN`，`str == "[LINK_DOWN] 链路中断"` | `-v`：`PASSED [ 54%]`；实测 `error.args == ("[LINK_DOWN] 链路中断",)`、`error.code.name == "LINK_DOWN"` | 通过 |
| `testEdgeErrorFormatsEveryCodeNamePrefix`（新增） | 五码各构造 `EdgeError(code, "msg")` | `rendered` 恰 5 项且均为 `[CODE] msg` | `-v`：`PASSED [ 59%]`；实测 5 项等于 `["[CONFIG] msg", "[LINK_DOWN] msg", "[FRAME_PARSE] msg", "[INFERENCE_TIMEOUT] msg", "[CAPTURE] msg"]` | 通过 |
| `testFactoryReturnsWindowsAdapterForWin32`（新增） | `patch.object(sys, "platform", "win32")` | `type(...) is WindowsAdapter`、`newline() == "\r\n"` | `-v`：`PASSED [ 63%]`；实测精确类型为 `WindowsAdapter`、换行符 `"\r\n"` | 通过 |
| `testFactoryReturnsLinuxAdapterForLinux`（新增） | `patch.object(sys, "platform", "linux")` | `type(...) is LinuxAdapter`、`newline() == "\n"` | `-v`：`PASSED [ 68%]`；实测精确类型为 `LinuxAdapter` | 通过 |
| `testFactoryRejectsUnsupportedPlatformWithConfig`（新增） | `patch.object(sys, "platform", "freebsd")` | 抛 `EdgeError(CONFIG)`，`str == "[CONFIG] 不支持的平台: freebsd"` | `-v`：`PASSED [ 72%]`；实测 `error.code.name == "CONFIG"`、消息精确相等 | 通过 |
| `testLinuxLockSkeletonMarksTodoAndRaisesExactMessage`（新增） | `inspect.getsource(LinuxAdapter.lockFile)` + 调用 | `TODO` / `fcntl.flock` 源码各 1 次、抛异常消息精确 | `-v`：`PASSED [ 77%]`；单独探查命令实测 `TODO 1` / `FCNTL 1` / `RAISE 1`、`str(exc) == "Linux 文件锁待上板实现"` | 通过 |
| `testAcquireOccupiedLockRaisesConfigViaFake`（新增） | `FakePlatformAdapter(lockResult=None)` | `EdgeError(CONFIG)`、`lockCalls == ["edge_runtime.lock"]`、`lockHandle is None` | `-v`：`PASSED [ 81%]`；实测 `str(error) == "[CONFIG] 已有实例运行，进程锁获取失败"` | 通过 |
| `testAcquireConvertsSkeletonErrorPreservingCause`（新增） | `ProcessFileLock(LinuxAdapter(), path).acquire()` | `EdgeError(CONFIG)`，`__cause__` 为 `NotImplementedError` | `-v`：`PASSED [ 86%]`；实测 `str(error) == "[CONFIG] 平台文件锁尚未实现"`、`str(__cause__) == "Linux 文件锁待上板实现"` | 通过 |
| `testAcquireOrExitExitsImmediatelyWithConfigMessage`（新增） | `FakePlatformAdapter(lockResult=None)` + `acquireOrExit()` | 抛 `SystemExit`，`code` 为 `str` 且等于推导式精确值 | `-v`：`PASSED [ 90%]`；`sys.exit` 实参实测为 `"[CONFIG] [CONFIG] 已有实例运行，进程锁获取失败"`（见下方观察说明） | 通过 |
| `testAcquireOrExitKeepsLockWhenAcquired`（新增） | `FakePlatformAdapter(lockResult=io.BytesIO())` | 不抛 `SystemExit`、`lockHandle is handle` | `-v`：`PASSED [ 95%]`；实测 `handle.closed is False` | 通过 |
| `testReleaseIsIdempotentAndClosesHandle`（新增） | `acquire()` → `release()` ×2 | `handle.closed is True`、`lockHandle is None` | `-v`：`PASSED [100%]`；实测二次 `release()` 后仍为 `None`、`lockCalls == ["edge_runtime.lock"]` | 通过 |

> ③ 附注 1（静态检查，如实记录）：`python -m mypy --config-file edge/pyproject.toml` 输出 `Found 2 errors in 1 file (checked 29 source files)`，两条均为 `edge\tests\contract\test_phase0_foundation.py:26` / `:48` 的既有 `Untyped decorator makes function ... untyped  [untyped-decorator]`；`checked` 由基线 27 增至 29（新增 `unit/__init__.py` 与 `unit/test_stage0_error_and_lock_guards.py` 两个文件），**新增文件引入 0 个新错误**。该静态检查错误不是用例结论，故不占 ③ 表行，详见 ⑥ 第 4 行；本阶段不修、不洗绿。
> ③ 附注 2（观察说明，不下裁决）：`acquireOrExit()` 实测 `sys.exit` 实参为 `[CONFIG] [CONFIG] 已有实例运行，进程锁获取失败`，`[CONFIG]` 出现 2 次——一次来自 `acquireOrExit()` 内 `f"[{error.code.name}] {error}"` 拼接，一次来自 `EdgeError.__str__` 自带的 `[CODE]` 前缀。该用例以推导式 `f"[CONFIG] {EdgeError(ErrorCode.CONFIG, '已有实例运行，进程锁获取失败')}"` 作精确值断言，按实现现状举证；本阶段未改被测实现、未改预期、未下格式收敛结论。

## ④ 可复现的完整运行命令与运行环境

- 命令（**本次实际执行**，逐条独立运行；工作目录由工具默认的 `F:\PyCharm 2026.2.0.1` 切回工作区根）：

```
cd "f:\new zhineng" && python -m pytest -c edge/pyproject.toml edge/tests --collect-only -q -p no:cacheprovider
cd "f:\new zhineng" && python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider
cd "f:\new zhineng" && python -m pytest -c edge/pyproject.toml edge/tests -v -p no:cacheprovider
cd "f:\new zhineng" && python -m ruff check edge
cd "f:\new zhineng" && python -m mypy --config-file edge/pyproject.toml
```

  - 第 1、2、4、5 条为规定命令；第 3 条 `-v` 为附加取证命令，用于给 ③ 表提供逐用例 `PASSED [ xx%]` 真实输出片段。
  - 若执行器默认工作目录已为 `f:\new zhineng`，等价形式为去掉 `cd "f:\new zhineng" && ` 前缀，即 `python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` 等；`-c edge/pyproject.toml edge/tests` 的 `c` 参数与路径限定**不可省**。
  - shell 实测为 cmd.exe 语义（`&&` 可用、`;` 不可作命令分隔、`$PSVersionTable` 不可用），故未写 `cd /d`（在 PowerShell 包装层下 `Set-Location` 会因 `/d` 报参数错误）；目标与默认盘符同为 `F:`，同盘符 `cd "path"` 即可生效。
- 各条真实输出（新增用例后重跑）：
  - collect-only：`22 tests collected in 0.11s`（22 条用例全部在列，`test_interface_contracts.py` 的 5 个用例在列、无 `FrameData` ImportError）。
  - pytest `-q`：`...................... [100%]` / `22 passed in 0.21s`。
  - pytest `-v`：`platform win32 -- Python 3.10.8, pytest-9.1.1, pluggy-1.7.0`、`rootdir: f:\new zhineng\edge`、`configfile: pyproject.toml`、`collected 22 items`、22 行 `PASSED`、`============================= 22 passed in 0.28s ==============================`。
  - ruff：`All checks passed!`。
  - mypy：`edge\tests\contract\test_phase0_foundation.py:26: error: Untyped decorator makes function "testFactoryReturnsWindowsAdapter" untyped  [untyped-decorator]`；`edge\tests\contract\test_phase0_foundation.py:48: error: Untyped decorator makes function "testSecondProcessCannotAcquireLock" untyped  [untyped-decorator]`；`edge/pyproject.toml: note: unused section(s): module = ['_pytest.*', 'pytest.*']`（note 非错误）；`Found 2 errors in 1 file (checked 29 source files)`，退出码 1。
- 环境：
  - OS：`Windows-10-10.0.26200-SP0`（`platform.platform()` 实测）；`platform win32`（pytest 实测）。
  - Python：`3.10.8`，解释器 `C:\Users\Xiaojiu\AppData\Local\Programs\Python\Python310\python.exe`；`sys.prefix == sys.base_prefix` 实测为 `True` → **无独立 venv**，直接使用系统解释器，未激活任何虚拟环境。
  - 依赖：pytest `9.1.1`（pluggy `1.7.0`）、ruff `0.17.4`、mypy `1.20.2 (compiled: yes)`；均通过 `python -m ...` 调用。
  - 配置：`edge/pyproject.toml` 内 mypy `python_version = 3.9` / `strict = true` / `files = ["edge"]`，pytest `pythonpath = ["."]`，ruff `target-version = "py39"` / `line-length = 100`；pytest 实测 `rootdir: f:\new zhineng\edge`、`configfile: pyproject.toml`。
  - 工作目录：`f:\new zhineng`（`CODEBUDDY.md` §0 路径基准）。
- 前置条件：
  - 必须带 `-c edge/pyproject.toml edge/tests` 限定；不带时从工作区根会误收集 `dual_crop_stitch/` 旧项目测试（基线实测 136 个）且 rootdir 不对。
  - `edge/tests/fakes/fake_logger.py` 已按 B1 完成一次性最小修复（见 ⑥ 第 1 行），`test_interface_contracts.py` L16 的 `FakeLogger` 导入方可在收集期通过；否则契约测试收集期 ImportError 会阻断补测举证。
  - 新增用例不占用端口、设备或真实锁文件：`FakePlatformAdapter` + `io.BytesIO()` + `unittest.mock.patch.object` 全为内存态；仅既有 `testSecondProcessCannotAcquireLock` 使用 `tempfile.TemporaryDirectory()` 建临时锁文件并在 `finally` 中 `release()`。
  - `main.py` / `app_init.py`（阶段 d）尚未建立，不影响本阶段收集与执行；`pythonpath = ["."]` 使 `import edge` 生效。
  - `-p no:cacheprovider` 用于避免写入 `.pytest_cache`；本阶段没有 Fixture 文件、无 conftest 覆盖、无外部服务依赖。

## ⑤ 汇总

| 通过 | 失败 | 跳过 | 总耗时 | 覆盖率 |
| --- | --- | --- | --- | --- |
| 22 | 0 | 0 | `0.21s`（pytest `-q`：`22 passed in 0.21s`；附加 `-v` 取证为 `0.28s`） | 未采集代码覆盖率（未安装 / 未配置 `pytest-cov`、命令未带 `--cov`）；按验收项计 `0-1`~`0-4` 均有举证：`0-1` 文档举证、`0-2`/`0-3`/`0-4` 单测举证（12 新增 + 5 既有），未覆盖分支见 ⑥，不写「全部覆盖」 |

> ⑤ 附注：`22` 为全量 pytest 用例数 = 既有 10（`test_interface_contracts.py` 5 + `test_phase0_foundation.py` 5）+ 新增 12；既有 `@pytest.mark.skipif(os.name != "nt")` 两条在本机 win32 下均实际执行并 PASSED，故跳过为 0。另：ruff `All checks passed!`；mypy 存在 2 个**既有静态检查错误**（非用例失败），如实记录于 ③ 附注 1 与 ⑥ 第 4 行，未洗绿。

## ⑥ 本阶段未覆盖项及原因

| 未覆盖的验收项 / 分支 | 原因 | 归属阶段 | 补测计划 |
| --- | --- | --- | --- |
| **B1 提前处置留痕**：`edge/tests/fakes/fake_logger.py` 的 `FrameData` 断裂 | 该项**原属阶段 a 的 `a-2` / `a-3`**；因 `edge/tests/contract/test_interface_contracts.py` L16 导入 `FakeLogger` 导致**契约测试收集期 ImportError**、阻断阶段 0 补测举证，经用户授权**提前到阶段 0 做一次性最小修复**（只改 Fake 侧 5 行：删不存在的 `FrameData` 导入，`rxRecords` / `txRecords` 与 `rx` / `tx` 类型对齐 `dict[str, object] \| bytes`）；`edge/interfaces/i_logger.py` **零改动**（严禁新增 `FrameData` / 改接口签名），既有断言零改动；收口目标 pytest 可收集；阶段 a 仍按 `a-2` 原措辞独立验收 | `a`（`a-2` / `a-3`） | 本阶段仅验证 `test_interface_contracts.py` 5 个用例可收集且 PASSED（collect-only 22 条在列、无 ImportError）；阶段 a 按 `a-2` 原措辞独立验收 8 个 Fake 与 8 个接口签名逐一对齐，并对 `FrameData` 断裂给出正式结论 |
| `0-4` 已知缺口「进程锁无调用方」 | `main.py` / `app_init.py` 属阶段 d、尚未建立；本阶段只覆盖 `ProcessFileLock` 自身的 `acquire()` / `acquireOrExit()` / `release()` 与既有双进程取锁，未覆盖「进程启动第一件事拿锁」的端到端调用链，按 `stage-catalog.md` `0-4` 口径写入未覆盖项及原因 | `d` | 阶段 d 建立 `main.py` / `app_init.py` 后，在 `d-3`（一键停机 + 进程锁）与 `d-4`（Windows 端到端）补「启动首动作取锁 → 双开立即退出」的端到端用例 |
| `a-1`~`a-4`（interfaces / 其余 Fake / mypy 全绿 / 9 处 Fake 字段类型标注） | 本阶段验收范围仅 `0-1`~`0-4`；`interfaces/` 8 接口零实现核验、8 个 Fake 逐一签名对齐、`fake_config.py` 等 9 处 Fake 字段显式类型标注缺口、mypy 3.9 strict 全绿均属阶段 a，不在阶段 0 白名单内 | `a` | 阶段 a 逐项按 `a-1`~`a-4` 原措辞验收，并在白名单内补齐 Fake 字段标注与接口契约核验表 |
| **mypy 2 个错误（如实记录，未洗绿）** | `python -m mypy --config-file edge/pyproject.toml` 实测报 `edge\tests\contract\test_phase0_foundation.py:26` 与 `:48` 的 `Untyped decorator makes function ... untyped  [untyped-decorator]`（既有 `@pytest.mark.skipif`，pytest 9 在 `follow_imports = skip` 下装饰器为 `Any`）；该测试文件与 `edge/pyproject.toml` 均属 **L1 契约层 / 白名单外，禁写**，故本阶段不修；不得改既有断言、不得改配置、不得为变绿改被测代码。本次实测 `Found 2 errors in 1 file (checked 29 source files)`，新增 2 个文件引入 0 个新错误 | `a`（`a-3` 要求 mypy 3.9 strict 通过），或需用户裁决 L1 diff | 阶段 a 在白名单内修正，或由用户批准 L1 diff 后调整配置 / 既有装饰器写法，重跑 mypy 至 0 error；本阶段保留真实失败输出，不删除用例、不加跳过标记、不改预期 |
| `LinuxAdapter.lockFile` 的真实 `fcntl.flock` 上板实现 / `WindowsAdapter.lockFile` 在非 Windows 的真实 `msvcrt` 分支 | 本阶段以 `inspect.getsource` 断言 TODO 与 `fcntl.flock` 提示、以 `FakePlatformAdapter` 注入取锁结果，未在麒麟 / RK3588 上板环境验证真实 `fcntl.flock`，亦未在真实 Linux OS 上验证 `msvcrt` 缺席分支 | `d`（上板 / 端到端） | 上板阶段在白名单内补 `LinuxAdapter.lockFile` 的 `fcntl.flock(fd, LOCK_EX \| LOCK_NB)` 实现，并补真实双进程取锁 / 占用失败用例；`fcntl` 真实分支留待上板 |
| `PlatformFactory` 真实第三方 OS 分支 + 代码覆盖率 | 非 win32 / 非 linux 分支本阶段用 `patch.object(sys, "platform", "freebsd")` 模拟，未在真实第三方平台运行；此外未安装 `pytest-cov`、命令未带 `--cov`，未采集行 / 分支覆盖率数字 | `d`（真实平台）/ 用户裁决（是否引入覆盖率采集） | 保留平台无关模拟用例作为工厂 else 分支的常态举证；真实第三方平台执行与覆盖率采集由用户裁决是否在后续阶段引入，本阶段不以覆盖率数字替代举证 |
