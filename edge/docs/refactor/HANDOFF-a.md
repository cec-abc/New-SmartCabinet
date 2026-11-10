# HANDOFF-a — 已有骨架：审读 + 契约一致性核验 + 补可举证单测

- **阶段**：`a`（共 9 个阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d`）
- **日期**：2026-11-10
- **状态**：`done`（2026-11-10 用户本人本条确认「阶段 a 验收通过，同意收尾」并同时确认状态推进 `a → done`；最终 review 结论见 §9，按用户口述原文录入，不视为代签）
- **移交方**：主 agent（按用户 2026-11-10 收尾指令一次性完成 `/stage-done a` 全部文档写入；内容逐项按 `edge/docs/refactor/HANDOFF-TEMPLATE.md` 填写，不冒充 `memory-steward`）
- **接收方**：下一阶段开工（`stage-opener`），下一阶段为 `b`

## 1. 开工依据

- 用户确认记录：2026-11-10「确认开工，阶段 a 记为 in_progress，按开工卡白名单执行四步」；四项裁决：① `a-3` 选候选 A，先出 `edge/tests/contract/test_phase0_foundation.py` 完整 diff（变更前后 + 影响面 + 受影响测试/Fake）并停下等批准，批准后才动，禁删用例 / 加 skip 标记 / 整体关闭错误码，不改 `edge/pyproject.toml`；② `a-4` 9 处 Fake 字段类型标注在白名单内补齐、不列为未覆盖项；③ `patch.object(sys, "platform")` 只出复核结论写入 `stages/a/spec-digest.md`、不改上一阶段任何产物文件；④ 工作区 `HANDOFF-0.md` 未提交改动不处理、不算阶段 a 改动，收尾时随本阶段提交。同日用户追加裁决：第 10 处 `lockResult`（`fake_platform_adapter.py` L15）一并补齐字段级标注，**按 10 处口径收口，不再纠结 9/10 差异**；用户明确「不用重写测试」，由主 agent 按六节模板直接补 `test-report.md`。
- 适用权威：2026-11-10 定稿 `governance-v1` 的 `CODEBUDDY.md` §2（用户当次指令 > L1 契约层 > 4 条 always 规则 > L2 图资产 > L3 流程配置 > L4 状态与记忆）+ 规则 `01_naming_authority.mdc` / `02_coding_hard_constraints.mdc` / `03_dependency_and_layout.mdc` / `04_stage_gate_and_memory.mdc`；`test-visibility.mdc`（Agent Requested，必交物与六节）。
- 本阶段 spec 资料（按 `edge/docs/spec/INDEX.md` §2 逐文件登记中「对应阶段」含 `a` 的条目，只列路径 + 图类型，**不转录图中文字**）：

  | 路径 | 图类型（INDEX.md 登记值） |
  | --- | --- |
  | `edge/docs/spec/整体重构方案.txt` | 定稿文本（**L1 契约层，只读**；§3 接口表为主资料） |
  | `edge/docs/spec/编码规范规则.txt` | 定稿文本（**L1 契约层，只读**） |
  | `edge/docs/spec/整体流程/整合类图代码.txt` | 整合类图（PlantUML 源码）—「抽象接口层」包只取语义 |
  | `edge/docs/spec/整体流程/整合类图.png` | 整合类图（位图渲染） |
  | `edge/docs/spec/INDEX.md` | L3 索引资产（逐文件登记唯一权威，非图资产） |

  未列入本阶段：`整体流程/整体流程.txt`、`阶段0-3.png`、`阶段4-5.png`、`阶段5-7.png` 及配置 / 日志 / TCP / USB_Camera / 识别各目录（对应阶段不含 `a`）。图中「阶段 0~7」是运行期业务时序编号，与 9 个实施阶段无关，禁止混用；`CONFIG-DIFF.patch` 是历史记录、非权威，未当资料读取。
- 上一阶段 handoff：`edge/docs/refactor/HANDOFF-0.md`（阶段 0 `done`，移交 `a` 的收敛项见其 §6 / §8）。
- 现有代码判定：引 `references/stage-catalog.md` §0——27 个 `.py` 全部判为「符合新契约的骨架（非旧代码）」，故目标为「先把已有代码看懂、按契约审一遍、补上能说清楚的单测」，**不盲目重写、不以已有实现直接补验收**；逐文件结论见 `edge/docs/refactor/stages/a/spec-digest.md` §2.3 / §2.4。

## 2. 交付文件与必交物

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/tests/contract/test_phase0_foundation.py` | **修改（L1 契约层，用户已批准 diff 后落地）** | `a-3` | 新增 typed 装饰器 wrapper `windowsOnly`、两处 `@pytest.mark.skipif` 改为 `@windowsOnly`；既有 5 个用例与断言零改动；完整 diff 与批准记录见 §4 |
| `edge/tests/fakes/fake_camera_device.py` | 修改（白名单内） | `a-4` | 3 处字段显式类型标注 |
| `edge/tests/fakes/fake_sinks.py` | 修改（白名单内） | `a-4` | 1 处（`linkUpCount`） |
| `edge/tests/fakes/fake_socket.py` | 修改（白名单内） | `a-4` | 3 处 |
| `edge/tests/fakes/fake_thread.py` | 修改（白名单内） | `a-4` | 2 处 |
| `edge/tests/fakes/fake_platform_adapter.py` | 修改（白名单内） | `a-4` | 第 10 处 `self.lockResult: BinaryIO \| None = lockResult`，按用户追加裁决纳入；**5 个 Fake 共 10 处** |
| `edge/tests/unit/test_stage_a_contract_alignment.py` | 新增 | `a-1`~`a-4` | 11 个补强单测，只新增文件、既有断言零改动；用户明确「不用重写测试」，收尾未改 |
| `edge/docs/refactor/stages/a/spec-digest.md` | 新增（步骤 1 `spec-reader`） | `a-1`~`a-4` | 五节齐备；§2.6 按 10 处口径收口，§5 第 1 条登记用户裁决 |
| `edge/docs/refactor/stages/a/test-report.md` | 新增（步骤 3，主 agent 按六节模板补写） | `a-1`~`a-4`（举证载体） | **必交物**，六节齐备；③ 真实输出、④ 可复现命令与环境、⑥ 6 行未覆盖项及原因，未写「全部覆盖」 |
| `edge/docs/refactor/STAGE-STATE.md` | 修改（L4 状态与证据） | 全局门禁 | §1 当前阶段 / 禁写解除 / 收尾状态、§2 阶段 a 证据栏与状态 `done`、§5 门禁记录 |
| `edge/docs/refactor/HANDOFF-a.md` | 新增（本文件） | 全局门禁 | 按模板九节；§4 登记首次经批准的 L1 变更 baseline，§9 录入用户口述结论 |
| `.codebuddy/skills/edge-refactor/references/decisions.md` | 修改（L3，用户明确指令） | 全局门禁 | 追加「附录 A：L1 契约变更基线」，**不新增 D-xx 裁决** |
| `.codebuddy/skills/edge-refactor/references/lessons.md` | 修改（L4） | 全局门禁 | 追加 L-02 / L-03 |

只读核验对象（零改动）：`edge/interfaces/` 9 文件（L1，`a-1` 逐文件审读结论「新骨架·达标、无需修正」）、`edge/exceptions.py`、`edge/pyproject.toml`、`edge/tests/contract/test_interface_contracts.py` 既有断言、`edge/docs/spec/**` 原文与 PNG、`.codebuddy/rules/编码规范.mdc`、`edge/tests/unit/test_stage0_error_and_lock_guards.py`（上一阶段产物）、`edge/docs/refactor/stages/0/*`（历史归档，不倒改、不洗绿）。

- 必交物：`edge/docs/refactor/stages/a/spec-digest.md` **存在**（五节齐备，含 `a-1` 逐文件审读表与 `a-2` 31 行签名核验表）。
- 必交物：`edge/docs/refactor/stages/a/test-report.md` **六节齐备**（① 验收项→用例对照 / ② 使用的 Fake / ③ 用例表 / ④ 可复现命令与真实输出 / ⑤ 汇总 / ⑥ 6 行未覆盖项及原因；未写「全部覆盖」），非判红。
- 范围外文件：`edge/docs/refactor/HANDOFF-0.md` 的未提交改动按用户裁决**不处理、不算阶段 a 改动**，仅在收尾 git 提交时随本阶段一并纳入（一行历史说明）；`CONFIG-DIFF.patch` 未读、未改。
- 遗留 TODO 及归属阶段：见 §6「移交后续阶段的收敛项」；本阶段无未决阻塞。

## 3. 验收项逐条证据

验收项措辞照抄 `references/stage-catalog.md` §2 阶段 a（未改写）：

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| `a-1` | `interfaces/` 零实现、零业务 import、全 camelCase、Doxygen 注释覆盖。 | 文档举证：`stages/a/spec-digest.md` §2.3 九文件逐文件审读表（零实现 / 零业务 import / camelCase / Doxygen 四要素附行号）；单测举证：`python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` → `33 passed in 0.33s`；新增 4 个用例 `testInterfaceAbstractMethodBodiesCarryNoImplementation`（31 个抽象方法 `co_consts == (None,)`）、`testInterfaceMethodNamesAreAllCamelCase`（10 个类公开方法名精确等于 L1 §3 表）、`testInterfaceModulesImportNoBusinessModules`（AST + 运行时双证据零业务 import）、`testInterfaceDoxygenMarkersCovered`（`totalBrief == 47`）；`test-report.md` ① 第 1 行 / ③ 表 / ④ | 已逐条举证（文档 + 单测）；步骤 4 `stage-verifier` 举证表判「通过」 |
| `a-2` | 8 个 Fake 与 8 个接口签名逐一对齐；`fake_logger.py` 的 `FrameData` 断裂有明确结论与处置。 | 文档举证：`spec-digest.md` §2.4 的 31 行签名逐一对齐核验表 + `FrameData` 断裂 5 点正式结论（虚构类型导入、Fake 侧 5 行最小修复 B1、`i_logger.py` 零改动）；单测：`testAllFakeMethodSignaturesAlignWithInterfaces`（31 对 `inspect.signature` 全等 + 参数名 / 返回注解锚定）、`testAllFakesAreInstantiableSubclassesOfInterfaces`（10 个 Fake `isinstance`/`issubclass`）、`testFakeLoggerFrameDataBreakageIsResolved`（`FrameData` 0 命中、导入恰 `["ILogger"]`、`rxRecords` 精确值）；既有 5 个契约用例零改动、一并执行；`test-report.md` ① 第 2 行 / ② Fake 表 / ③ 表 | 已逐条举证；步骤 4 判「通过」 |
| `a-3` | 契约测试可收集、可执行、通过；mypy（3.9 strict）通过。 | 命令 `python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` → `................................. [100%]` / `33 passed in 0.33s`（退出码 0）；`python -m mypy --config-file edge/pyproject.toml --no-incremental` → `edge/pyproject.toml: note: unused section(s): module = ['_pytest.*', 'pytest.*']`（note 非错误）/ `Success: no issues found in 30 source files`（退出码 0）；`python -m ruff check edge` → `All checks passed!`（退出码 0）。测试名：`testContractTestFunctionsAreCollectableAndExecutable`、`testMypyConfigTargetsPython39Strict` + 既有契约 10 / 阶段 0 补强 12；`test-report.md` ① 第 3 行 / ③ / ④ | 已逐条举证；步骤 4 判「通过」 |
| `a-4` | 已知 9 处 Fake 字段类型标注缺口有结论（补齐或列入未覆盖项并说明）。 | 用户 2026-11-10 裁决按 **10 处口径收口**：5 个 Fake 文件共 10 处字段级标注全部补齐（含第 10 处 `lockResult`），裁决写入 `spec-digest.md` §2.6 / §5；单测 `testNineFakeFieldAnnotationsAreExplicit`（9 处 `ast.AnnAssign` 标注文本逐项精确）、`testNineFakeFieldsRetainConcreteInitialValues`（初值与回调具体值）；第 10 处按用户「不重写测试」由实现改动 + ④ 三项工具链实跑 + 改动清单举证；`test-report.md` ① 第 4 行 / ③ 附注 2 / ④；⑥ 未列 `a-4` | 已逐条举证；步骤 4 判「通过」 |

- 工具链（收尾复核真实输出，2026-11-10）：`ruff` → `All checks passed!`（退出码 0）｜`mypy`（3.9 strict，`--no-incremental`）→ `Success: no issues found in 30 source files`（退出码 0，附 `unused section(s)` note 非错误）｜`pytest` + 契约测试 → `33 passed in 0.33s`（退出码 0，33 个点全为 `.`，跳过 0）。同一状态另有 `33 passed in 0.36s` / `0.32s` 两次实测，耗时波动，均为真实输出、如实保留。时间点 A（L1 diff 落地后立即实跑）为 `22 passed in 0.29s` / `Success: no issues found in 29 source files` / `All checks passed!`，与收尾态并列保留、不互相覆盖，详见 `test-report.md` ④。
- `test-report.md` 六节：齐备（① / ② / ③ / ④ / ⑤ / ⑥）；第 ⑥ 节 6 行未覆盖项摘要：真实麒麟 Linux / RK3588 上板与 `fcntl.flock`（归 `d`）、`PlatformFactory` 真实第三方 OS 分支（归 `d`）、覆盖率采集（用户裁决，不引入）、`patch.object(sys, "platform")` 规范适用边界（用户裁决 / 后续阶段）、`i_sinks.py` 回调计数资料差异（L3 资料修订 / 用户裁决）、「首次经用户批准的 L1 变更」登记进 `decisions.md` 与 handoff（收尾动作，本阶段已完成，见 §4 / §7）。未写「全部覆盖」；`a-4` 未列入。
- `python-code-review` 报告（写完/改完 Python 后检视一次，模式：全量检视）：

  ## python 代码检视报告（阶段 a 收尾）

  - 范围：`edge/tests/contract/test_phase0_foundation.py`（已批准 L1 diff）、`edge/tests/fakes/` 5 个文件（10 处字段标注）、`edge/tests/unit/test_stage_a_contract_alignment.py`（新增 11 用例）。
  - 结论：改动均在白名单内；命名 camelCase、类型标注齐备、`## @brief` / `#  @param` / `#  @return` 注释合规；新增 11 个用例全 `-> None`、有验收项编号注释、无 `assert True` / `assert x` / `assert ... is not None` 空洞断言、无跳过标记；`typed decorator wrapper` 把 `Any` 收口到一处 `cast`，未改 `pyproject.toml`、未删用例、未加 skip、未整体关闭错误码；L1 变更已获用户批准。**不妨碍收尾**；检视项按阶段收敛，不用问题清单阻断收尾。

  | 级别 | 位置 | 维度 | 现状证据 | 影响 | 改进建议 |
  | --- | --- | --- | --- | --- | --- |
  | P3 | `test_stage_a_contract_alignment.py` `testInterfaceDoxygenMarkersCovered` | 测试与可观测性 | 用 `source.count("## @brief")` / `@param` / `@return` 计数作具体值断言 | 注释措辞改写会误报，属静态文本举证而非行为正确性证据 | 后续阶段可补接口反射断言作交叉证据；归 `d` / 用户裁决，本阶段不改既有测试 |
  | P3 | `edge/tests/contract/test_interface_contracts.py` L55 | 测试与可观测性 | 既有 `assert ... is not None` 弱断言（阶段 0 既有断言，本阶段零改动） | 非本阶段引入，不影响 `a-1`~`a-4` 举证 | 归后续阶段 / 用户裁决，不在本阶段改既有断言、不洗绿 |

  ### 未发现问题的维度
  耦合性（无跨模块反向 import）、错误处理（无吞异常 / 裸 except）、Python 特有陷阱（无可变默认参数 / 晚绑定）、性能与资源、安全、并发与异步（本阶段无线程 / IO）、工程结构（改动全在白名单目录）。

  ### 跨阶段遗留项（含归属）
  真实 `fcntl.flock` 上板实现 → `d`；双 `[CONFIG]` 前缀格式 → `d`；`inspect.getsource` / 源码文本脆弱断言改行为断言 → `d`；`patch.object(sys, "platform")` 规范适用边界 → 用户裁决 / 后续阶段；`i_sinks.py` 计数资料措辞 → L3 资料修订 / 用户裁决；覆盖率采集 → 用户裁决（不引入）。

  ### 经验沉淀
  - 技能经验库 `accumulated-lessons.md`：更新「pytest 9 + mypy strict 下 untyped-decorator」条目（命中次数 2，补 typed wrapper 收敛方案与用户批准记录）、「脆弱源码文本断言」条目（命中次数 2，补注释标记计数判据）。
  - 项目记忆：新建 topic 文件登记「首次经批准的 L1 变更作为后续 baseline」裁决。

- 测试约定核验：11 个新增用例均有一行验收项编号注释、全部 `-> None`、空洞断言 0 命中（新增用例）、`@pytest.mark.*` 0 命中；既有 `edge/tests/contract/*` 断言 diff 为空；无为变绿而改被测代码（`git diff` 仅 10 处字段标注 + 1 处已批准 L1 装饰器）；`stage-verifier` 步骤 4 举证表结论「证据齐备（a-1~a-4 逐条举证通过；无未通过项、无判红、无 blocked）」，**只出举证、不含最终结论、不代签**（举证表为会话内产物，无独立落盘文件路径，如实标注、不编造）。

## 4. L1 契约层

- `contract-guard` 基线结论：**有变更 1 处，且已由用户本人 2026-11-10 明确批准**。唯一变更文件 `edge/tests/contract/test_phase0_foundation.py`，与批准 diff 一致、未发现夹带；其余 16 个 L1 契约文件与 `edge/docs/spec/**` 原文 / PNG 零改动；不存在其它待批准契约 diff。定性为「**已批准的契约变更**」，不是自动修改、不是未批准变更，**不触发 blocked / 等待批准**。该 agent 如实声明无命令执行能力、只做当前态静态核验；**git 层基线由主 agent 只读补证**：`git diff -- edge/tests/contract/test_phase0_foundation.py` 输出见下方完整 diff，`git status --short` 中 L1 仅该文件为 `M`。
- 契约变更 diff（**完整，作为后续 baseline 对比依据**）：

```diff
--- a/edge/tests/contract/test_phase0_foundation.py
+++ b/edge/tests/contract/test_phase0_foundation.py
@@ -5,7 +5,9 @@ import os
 import subprocess
 import sys
 import tempfile
+from collections.abc import Callable
 from pathlib import Path
+from typing import cast
 
 import pytest
 
@@ -14,6 +16,16 @@ from edge.platform.adapter import LinuxAdapter, PlatformFactory, WindowsAdapter
 from edge.platform.file_lock import ProcessFileLock
 
 
+## @brief 为 skipif 装饰器补齐类型，避免 follow_imports=skip 下装饰器被推断为 Any
+#  @param reason 跳过原因，原样传给 pytest.mark.skipif
+#  @return 带类型的 skipif 装饰器
+def windowsOnly(reason: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
+    return cast(
+        Callable[[Callable[[], None]], Callable[[], None]],
+        pytest.mark.skipif(os.name != "nt", reason=reason),
+    )
+
+
 ## @brief EdgeError 携带枚举码，字符串含 code.name 便于日志扫描
 def testEdgeErrorCarriesCodeName() -> None:
     error = EdgeError(ErrorCode.FRAME_PARSE, "坏帧")
@@ -23,7 +35,7 @@ def testEdgeErrorCarriesCodeName() -> None:
 
 
 ## @brief Windows 上工厂返回完整实现的适配器
-@pytest.mark.skipif(os.name != "nt", reason="仅 Windows 验证")
+@windowsOnly("仅 Windows 验证")
 def testFactoryReturnsWindowsAdapter() -> None:
     assert isinstance(PlatformFactory.create(), WindowsAdapter)
 
@@ -45,7 +57,7 @@ def testLinuxSkeletonIsConvertedToEdgeError() -> None:
 
 
 ## @brief 主进程持锁时，第二进程拿锁失败并报告 CONFIG
-@pytest.mark.skipif(os.name != "nt", reason="仅 Windows 验证")
+@windowsOnly("仅 Windows 验证")
 def testSecondProcessCannotAcquireLock() -> None:
     projectRoot = Path(__file__).resolve().parents[3]
     with tempfile.TemporaryDirectory() as tempDir:
```

  - **变更前后要点**：新增 `Callable` / `cast` 两个 import 与一个 typed wrapper；两处装饰器由 `@pytest.mark.skipif(os.name != "nt", reason="仅 Windows 验证")` 改为 `@windowsOnly("仅 Windows 验证")`；跳过条件 `os.name != "nt"` 与 reason 逐字保留在 wrapper 内，跳过行为不变。5 个既有 `testXxx` 函数体与断言零改动。
  - **影响面**：接口（无，L1 `interfaces/` 零改动）；测试（契约测试仍可收集 / 可执行 / 通过，`33 passed`）；Fake（零改动）；阶段（`a-3` 的 mypy 由阶段 0 遗留 2 个 `untyped-decorator` 转为 `Success: no issues found in 30 source files`）；规则（`edge/pyproject.toml` 零改动、未整体关闭错误码、未删用例、未加 skip 标记、未洗绿）。
- 批准状态：**已批准（附批准记录）** —— 用户 2026-11-10 在看到完整 diff（变更前后 + 影响面 + 受影响测试/Fake）后回复「批准这份 diff，落地执行。落地后立即实跑 mypy --no-incremental / ruff check edge / pytest 三项，给我真实输出……」，主 agent 才落地；落地后三项实跑全绿（时间点 A：`22 passed in 0.29s` / `Success: no issues found in 29 source files` / `All checks passed!`）。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— 已遵守（先 diff → 停下等批准 → 批准后落地 → 实跑验证）。
- **首次经用户批准的 L1 变更 baseline 登记（用户 2026-11-10 指令）**：本 §4 完整 diff + `.codebuddy/skills/edge-refactor/references/decisions.md`「附录 A」共同构成后续 baseline 对比依据。后续阶段 `contract-guard` 开工 / 收尾核验时，以基线 tag `stage-a-done` 与本附录为准：该文件相对此基线的**新增**改动才需要重新走 diff + 批准；基线中已批准的变更不再重复判为「未批准 / 自动修改」，避免每阶段重复判定。除本附录外的任何 L1 变更仍必须走完整 diff + 用户批准流程。
- 补充说明：`stages/0/test-report.md` 与 `HANDOFF-0.md` 记录的阶段 0 mypy 历史失败（`Found 2 errors in 1 file`、退出码 1）是当时真实输出，**不倒改、不洗绿**；与本阶段全绿属两个时间点的事实，并列保留。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守 | `interfaces/` 9 文件经逐文件审读（`spec-digest.md` §2.3）无自检方法 / 类 / 线程；本阶段未新增自检接口、未建 `self_check*.py` / `checker/`、未做能力降级；L1 `interfaces/` 零改动 |
| D-02 非 UP 不启其他线程 | 已遵守（本阶段不涉及） | 无 `linkState`、无心跳 / 解码 / 重连线程、无 `transitionTo`；`i_socket.py` / `i_thread.py` 仅接口定义、未启动线程；`spec-digest.md` §4.1 逐条登记，留 `c3` / `d` |
| D-03 去重不做、seq 只填不用 | 已遵守（本阶段不涉及） | 无协议帧组装、无 `EventCache` / `seq`、无基于序号的比较 / 过滤 / 判重；`spec-digest.md` §4.1 逐条登记，留 `c3` / `d` |

> NAMING_AUTHORITY 本阶段命中：`windowsOnly` 全库唯一、camelCase、参数与返回值全标注；旧图 snake_case 只取语义、不作 API；`spec-digest.md` §3 命名裁决表已给完整 L1 落地标识符。

## 6. 遗留与裁决

- 图与 L1 的冲突点（均**未改图、未改 L1**）：旧版 snake_case 标识符（全部图）→ NAMING_AUTHORITY；专用 getter / `getInstance` / `getValue` → L1 §3 接口表（`get(section, key, default=None)` / `instance()`）；自检 / 能力降级 / 自检线程 → D-01；非 UP 阶段出现心跳 / 解码线程 → D-02（留 `c3` / `d`）；`PendingRequest` 重发 / 按 `seq` 去重 → D-03（留 `c3` / `d`）；整合类图把 `ILogger` 画成仅 `info` / `error`、`IConfig` 画成 `getValue(section, key)` → 以 L1 §3 四方法 / 通用 `get` 为准；图中「阶段 0~7」是运行期业务时序编号，与 9 个实施阶段无关。
- 需用户拍板事项：**无**（用户 2026-11-10 已一次性确认开工、批准 L1 diff、按 10 处口径收口、不重写测试、覆盖率不引入、状态推进 `done`；`test-report.md` ⑥ 六项按归属留后续阶段，不重新征询）。
- 阻塞原因与解除条件：**无**。
- 移交后续阶段的收敛项（逐条 + 归属阶段）：
  1. 真实麒麟 Linux / RK3588 上板分支与 `LinuxAdapter.lockFile` 的 `fcntl.flock` 实现 → `d`。
  2. `PlatformFactory` 真实第三方 OS 分支执行 → `d`。
  3. 双 `[CONFIG]` 前缀格式收敛 → `d`（用户 2026-11-10 阶段 0 收尾裁决，未洗绿）。
  4. `inspect.getsource` / 源码文本脆弱断言改行为断言 → `d`。
  5. `0-4` 缺口「进程锁无调用方」与 `main.py` / `app_init.py` 端到端 → `d`。
  6. `patch.object(sys, "platform", ...)` 的规范适用边界解释空间 → 用户裁决 / 后续阶段（命名复核结论已在 `spec-digest.md` §2.7，不改上一阶段任何产物）。
  7. `i_sinks.py` 回调计数资料措辞（资料记 10 / 源码与 L1 为 8）→ L3 资料修订 / 用户裁决。
  8. 代码覆盖率采集 → 用户裁决（明确**不引入**）。
  9. `a-4` 第 10 处 `lockResult` 未纳入单测断言（用户「不重写已有测试」）→ 已由实现改动 + 工具链实跑 + 改动清单举证，**不作为 `a-4` 未覆盖项**；若后续用户要求可补单测，需重新授权。

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：§1 当前阶段 `a` = `done`、禁写解除行改为「阶段 a 已收尾、许可不沿用」、收尾状态行；§2 阶段 a 证据栏（填 `edge/docs/refactor/stages/a/test-report.md` 路径 + 工具链结果 + 步骤 4 举证 + 用户签字 + 已批准 L1 变更 + baseline 登记）、最后更新时间 2026-11-10；§5 追加开工与收尾门禁事件；§3 复选框按项目惯例保持 `[ ]`。
- `references/lessons.md` 条目号：**L-02**（经批准的 L1 契约变更应先 diff 后落地、收尾登记 baseline）、**L-03**（资料口径差异由用户一次裁决收口，不重写既有测试、由工具链举证）。
- 项目记忆：新建 topic 文件 `feedback_l1_approved_change_baseline.md`（type: feedback，登记 2026-11-10 用户裁决「首次经用户批准的 L1 变更登记进 decisions.md 与 handoff、作为后续 baseline 对比依据，避免每阶段重复判定」）+ `MEMORY.md` 追加一行索引；写入前已查 `MEMORY.md` 去重（无同义条目）。
- `python-code-review` 经验库：`C:\Users\Xiaojiu\.codebuddy\skills\python-code-review\references\accumulated-lessons.md` 已更新（untyped-decorator 条目命中次数 2 + typed wrapper 方案；脆弱源码文本断言条目命中次数 2 + 注释标记计数判据）。
- `references/decisions.md`：**追加「附录 A：L1 契约变更基线（2026-11-10 用户批准，非新裁决）」**，含完整 diff、批准记录、影响面、基线用途与「不新增 D-xx、D-01/02/03 不变」声明。**未新增 D-04**，裁决变更协议「助手不得自行推断第四条裁决」已遵守。
- git：本阶段所有文档写入**均在提交之前完成**；提交纳入 `HANDOFF-0.md` 的那行历史说明（用户裁决随本阶段提交），`.codebuddy` 下 `lessons.md` / `decisions.md` 用 `git add -f` 精确纳入，不改 `.gitignore`；提交后打 annotated tag `stage-a-done`。

## 8. 下阶段开工提示

- 下一阶段：`b`（`base/base_thread.py`、`base_service.py`；验收项 `b-1`~`b-3`）。
- 必读：`edge/docs/refactor/HANDOFF-a.md`（本 handoff）、`references/stage-catalog.md` 阶段 b 段、`references/decisions.md`（D-01 / D-02 适用项 + **附录 A 的 L1 baseline**）、`edge/docs/spec/INDEX.md` 阶段 b 资料、`references/lessons.md`（L-01~L-03）、`edge/docs/refactor/STAGE-STATE.md`。
- 特别注意：
  1. **阶段 a 的禁写 `.py` 解除不沿用**：阶段 b 须重新由开工卡经用户点头后才按白名单解除；L1 契约层与 `edge/docs/spec/**` 仍一律禁写。
  2. **L1 基线已变更一次且已获批准**：`contract-guard` 后续核验以 tag `stage-a-done` + `decisions.md` 附录 A + 本 handoff §4 为准，不再把基线中已批准的 `test_phase0_foundation.py` 改动重复判为未批准 / 自动修改；新增的 L1 改动仍须 diff + 批准。
  3. 补强单测落点固定 `edge/tests/unit/`（只新增文件、不改任何既有断言）；`test-report.md` 六节为每阶段必交物，⑥ 必须列未覆盖项、不写「全部覆盖」。
  4. `a-4` 已按 10 处口径收口、5 个 Fake 共 10 处字段标注全部补齐；既有 11 个阶段 a 补强单测用户明确「不重写」，后续不得擅自改动。
  5. 工具链现状：mypy（3.9 strict）`Success: no issues found in 30 source files`、ruff 全过、pytest `33 passed`；阶段 0 的 mypy 历史失败记录不倒改、不洗绿。
  6. 覆盖率采集用户明确**不引入**；`test-report.md` ⑥ 六项未覆盖项按归属留后续阶段，勿在阶段 b 重复征询。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**已签署**（2026-11-10 用户本人「我看过 test-report.md 了，签字」；任何 agent 不得代签）。步骤 4 `stage-verifier` 已出完整举证表（只举证、不含最终结论）。
- **最终 review 结论（用户口述 2026-11-10，按原文录入，不视为代签）**：「阶段 a 验收通过，同意收尾；⑥ 六项未覆盖项按归属留后续阶段，覆盖率不引入。」
  - 录入说明：本条为**用户本人本条口述**的最终结论，由助手按原文照录并注明「用户口述 2026-11-10」；**不视为代签**，任何 agent 不得代用户签署最终 review 结论。用户本条同时构成对状态推进 `a → done` 的确认，不再另停一次。
- [x] 配置/交付范围确认
- [x] 举证结论确认
- [x] 状态推进确认（`a` → `done`）
- 确认人 / 日期：确认人 **用户本人（本条口述）** ｜ 日期 **2026-11-10**。
