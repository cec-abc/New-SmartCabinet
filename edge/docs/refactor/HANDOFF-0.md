# HANDOFF-0 — 已有骨架：审读 + 契约核验 + 补可举证单测

- **阶段**：`0`（共 9 个阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d`）
- **日期**：2026-11-10
- **状态**：`done`（2026-11-10 用户本人确认「阶段 0 验收通过，同意收尾」；最终 review 结论见 §9，按用户口述原文录入，不视为代签）
- **移交方**：`memory-steward`（沉淀官 agent）
- **接收方**：下一阶段开工（`stage-opener`），下一阶段为 `a`

## 1. 开工依据

- 用户确认记录：2026-11-10「确认开工，阶段 0 记为 `in_progress`，按开工卡白名单执行四步；A5 补强单测放 `edge/tests/unit/`（新建，只新增文件，不改任何既有断言），后续阶段同理；其余按开工卡默认口径，人工闸门处停下等我签字」。
- 适用权威：2026-11-10 定稿 `governance-v1` 的 `CODEBUDDY.md` §2（权威优先级：用户当次指令 > L1 契约层 > 4 条 always 规则 > L2 图资产 > L3 索引/流程配置 > L4 状态与记忆）+ 规则 `01_naming_authority.mdc` / `02_coding_hard_constraints.mdc` / `03_dependency_and_layout.mdc` / `04_stage_gate_and_memory.mdc`（即规则 01~04）。
- 本阶段 spec 资料：按 `edge/docs/spec/INDEX.md` §2「逐文件登记」中「对应阶段」含 `0` 的条目，只列路径 + 图类型，**不转录图中文字**（下表路径统一写工作区根基准 `edge/docs/spec/...`）：

  | 路径 | 图类型（INDEX.md 登记值） |
  | --- | --- |
  | `edge/docs/spec/整体重构方案.txt` | 定稿文本（L1 契约层，只读） |
  | `edge/docs/spec/编码规范规则.txt` | 定稿文本（L1 契约层，只读） |
  | `edge/docs/spec/整体流程/整体流程.txt` | 时序图（mermaid 源码，3 段） |
  | `edge/docs/spec/整体流程/整合类图代码.txt` | 整合类图（PlantUML 源码） |
  | `edge/docs/spec/整体流程/整合类图.png` | 整合类图（位图渲染） |
  | `edge/docs/spec/整体流程/阶段0-3.png` | 阶段时序 |
  | `edge/docs/spec/INDEX.md` | L3 索引资产（非图资产，逐文件登记唯一权威） |

  未列入本阶段：`阶段4-5.png`、`阶段5-7.png` 及配置/日志/TCP/USB_Camera/识别各目录（对应阶段不含 `0`）。图中「阶段 0~7」是运行期业务时序编号，与 9 个实施阶段无关，禁止混用。
- 上一阶段 handoff：无（阶段 0 为首个实施阶段；`references/lessons.md` §3 收尾前为空库）。
- 现有代码判定：引 `references/stage-catalog.md` §0——27 个 `.py` 全部判为「符合新契约的骨架（非旧代码）」，故目标为「先把已有代码看懂、按契约审一遍、补上能说清楚的单测」，**不盲目重写、不以已有实现直接补验收**；逐文件结论见 `stages/0/spec-digest.md` §2.2。

## 2. 交付文件与必交物

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/tests/fakes/fake_logger.py` | 修改（白名单内实现侧） | 不占 `0-1`~`0-4`（`test-report.md` ⑥ 第 1 行留痕） | B1 一次性最小修复 5 行：删不存在的 `FrameData` 导入，`rxRecords`/`txRecords` 与 `rx`/`tx` 类型对齐既有 `ILogger` 签名；原属阶段 a 的 `a-2`/`a-3`，因收集期 ImportError 阻断阶段 0 补测，经用户授权提前处置；`i_logger.py` 零改动、既有断言零改动 |
| `edge/tests/unit/__init__.py` | 新增 | 支撑 `0-2`~`0-4`（新增用例可收集） | 新建 `unit/` 包标记，A5 落点，不改任何既有断言 |
| `edge/tests/unit/test_stage0_error_and_lock_guards.py` | 新增 | `0-2` / `0-3` / `0-4` | 12 个新增用例，均有一行验收项编号注释、全 `-> None`、无 `@pytest.mark.*`、无空洞断言 |
| `edge/docs/refactor/stages/0/spec-digest.md` | 新增 | `0-1` | 步骤 1 `spec-reader` 产出，五节齐备，含 `0-1` 逐文件审读表 |
| `edge/docs/refactor/stages/0/test-report.md` | 新增 | `0-1`~`0-4`（举证载体） | 步骤 3 `test-writer` 产出，六节齐备（① L3 / ② L15 / ③ L23 / ④ L53 / ⑤ L87 / ⑥ L95） |
| `edge/docs/refactor/STAGE-STATE.md` | 修改（L4 状态与证据） | 全局门禁 / 证据栏 | 更新阶段 0 证据栏、§1 收尾状态行、§5 门禁记录一行；状态列保持 `in_progress` |

只读核验对象（条件性白名单**未触发**，均判「新骨架·达标、无需修正」）：`edge/exceptions.py`（L1 契约层，只读禁改）+ `edge/platform/__init__.py` / `edge/platform/adapter.py` / `edge/platform/file_lock.py`；逐文件行号依据见 `stages/0/spec-digest.md` §2.2。

- 必交物：`edge/docs/refactor/stages/0/spec-digest.md` **存在**（五节齐备，含 `0-1` 逐文件审读表）。
- 必交物：`edge/docs/refactor/stages/0/test-report.md` **六节齐备**（① 验收项→用例对照表 / ② 使用的 Fake / ③ 用例表 / ④ 五条可复现命令 + 环境 / ⑤ 汇总 / ⑥ 6 行未覆盖项及原因；⑥ 未写「全部覆盖」，未覆盖分支如实登记），非判红。
- 范围外文件：无（`edge/interfaces/*`、`edge/tests/contract/*`、`edge/pyproject.toml`、`edge/docs/spec/**`、`INDEX.md`、4 条 always 规则均零改动）。
- 遗留 TODO 及归属阶段：`a`（B1 的 `a-2` 独立验收、mypy 2 个既有错误 `a-3`、`a-1`~`a-4`、`patch.object(sys, "platform", ...)` 命名口径复核、`FrameData` 断裂正式结论）；`d`（双 `[CONFIG]` 前缀、`inspect.getsource` 脆弱断言改行为断言、`0-4` 缺口「进程锁无调用方」、真实 `fcntl.flock` 上板、上板后端到端）；用户裁决（是否引入覆盖率采集）。逐条详见 §6。

## 3. 验收项逐条证据

验收项措辞照抄 `references/stage-catalog.md` §2（未改写）：

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| `0-1` | 逐文件审读结论齐备，明确「新骨架 / 需修正」及依据。 | 文档举证（非单测），无执行命令；输出 = `edge/docs/refactor/stages/0/spec-digest.md` §2.2 逐文件审读结论与契约核验表，4 个骨架文件（`exceptions.py`、`platform/__init__.py`、`adapter.py`、`file_lock.py`）全判「新骨架·达标、无需修正」并附逐文件行号依据；测试名 = 无（文档举证）；`test-report.md` ① 对照表 `0-1` 行 | 已逐条举证（文档）；结论待用户本人最终 review |
| `0-2` | `EdgeError` 抛出 / 捕获与 `code.name` 日志格式正确。 | 命令 `python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider`（及附加 `-v` 取证）→ 输出 `22 passed in 0.21s` / `-v` 逐用例 `PASSED`；测试名：新增 `testErrorCodeEnumeratesFiveCodes`、`testEdgeErrorRaiseAndCatchCarriesExactCodeName`、`testEdgeErrorFormatsEveryCodeNamePrefix`，既有未修改 `testEdgeErrorCarriesCodeName`；`test-report.md` ③ 对应行 + ① 对照表 `0-2` 行（五码成员名/整数值/抛捕/精确 `[CODE]` 前缀均有断言） | 已逐条举证（单测）；结论待用户本人最终 review |
| `0-3` | `PlatformFactory` Windows 返回 `WindowsAdapter`；Linux 分支 `NotImplementedError` + TODO。 | 命令同上 → 输出 `22 passed` / `-v` 逐用例 `PASSED`；测试名：新增 `testFactoryReturnsWindowsAdapterForWin32`、`testFactoryReturnsLinuxAdapterForLinux`、`testFactoryRejectsUnsupportedPlatformWithConfig`、`testLinuxLockSkeletonMarksTodoAndRaisesExactMessage`，既有未修改 `testFactoryReturnsWindowsAdapter`、`testLinuxAdapterSkeletonRaises`；`test-report.md` ③ 对应行 + ① 对照表 `0-3` 行（win32/linux/其余平台三分支与 TODO 骨架消息均有断言；真实 `fcntl.flock` 上板未覆盖见 ⑥） | 已逐条举证（单测）；结论待用户本人最终 review |
| `0-4` | 双开取锁失败并立即退出；已知缺口「进程锁无调用方」写入未覆盖项及原因。 | 命令同上 → 输出 `22 passed` / `-v` 逐用例 `PASSED`；测试名：新增 `testAcquireOccupiedLockRaisesConfigViaFake`、`testAcquireConvertsSkeletonErrorPreservingCause`、`testAcquireOrExitExitsImmediatelyWithConfigMessage`、`testAcquireOrExitKeepsLockWhenAcquired`、`testReleaseIsIdempotentAndClosesHandle`，既有未修改 `testLinuxSkeletonIsConvertedToEdgeError`、`testSecondProcessCannotAcquireLock`；`test-report.md` ③ 对应行 + ① 对照表 `0-4` 行；已知缺口「进程锁无调用方」已按口径写入 `test-report.md` ⑥ 第 2 行（归属 `d`） | 已逐条举证（单测）；结论待用户本人最终 review |

- 工具链：`pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` → `22 passed in 0.29s`（`test-report.md` ④ 记 `0.21s`，耗时波动；两条均为真实输出、如实保留）；`python -m ruff check edge` → `All checks passed!`；`python -m mypy --config-file edge/pyproject.toml --no-incremental` → **既有 2 条 `untyped-decorator`**（`edge/tests/contract/test_phase0_foundation.py:26` / `:48`）、`Found 2 errors in 1 file (checked 29 source files)`、退出码 1 —— **如实保留真实失败输出，不写「通过」**，本阶段不修、不洗绿（按用户裁决留阶段 a）；collect-only `python -m pytest -c edge/pyproject.toml edge/tests --collect-only -q -p no:cacheprovider` → `22 tests collected in 0.11s`，22 条用例全部在列、无 `FrameData` ImportError。完整可复现的五条命令（含 `cd` 前缀 / `python -m` 形式）与前置条件见 `test-report.md` ④。
  - 环境：`Windows-10-10.0.26200-SP0`（`platform win32`）／系统 Python `3.10.8`（`sys.prefix == sys.base_prefix`，无独立 venv）／pytest `9.1.1`（pluggy `1.7.0`）／ruff `0.17.4`／mypy `1.20.2`；mypy 目标 `python_version = 3.9`、`strict = true`；工作目录 `f:\new zhineng`（`CODEBUDDY.md` §0 路径基准）。
  - 工具链证据来源：`test-report.md` ④（五条实测命令与输出）+ 步骤 4 `stage-verifier` 完整举证表（经用户确认）+ 步骤 7 `stage-verifier` 增量复核（7 项「仍成立」）。举证表为会话内产物，**无独立落盘文件路径**，如实标注、不编造路径。
- `test-report.md` 六节：齐备（① / ② / ③ / ④ / ⑤ / ⑥）；第 ⑥ 节未覆盖项摘要（6 行）：B1 提前处置留痕（归 `a` 的 `a-2`/`a-3`）、`0-4` 缺口「进程锁无调用方」（归 `d`）、`a-1`~`a-4`（归 `a`）、mypy 2 个既有错误（归 `a` 的 `a-3` 或需用户裁决 L1 diff）、`LinuxAdapter.lockFile` 真实 `fcntl.flock` 上板实现与 `msvcrt` 真实分支（归 `d`）、`PlatformFactory` 真实第三方 OS 分支与代码覆盖率（归 `d` / 用户裁决）；未写「全部覆盖」，未采集覆盖率数字（未安装/未配置 `pytest-cov`）。
- `python-code-review` 报告：**本阶段改动均在白名单内、命名/类型标注/注释合规、无空洞断言、L1 零改动；不妨碍收尾**。跨阶段遗留项（含归属）：mypy 2 个既有 `untyped-decorator` 错误 → `a`（`a-3`）；双 `[CONFIG]` 前缀 → `d`；`inspect.getsource` 脆弱断言 → `d`（上板实现落地后改行为断言）；测试侧 `patch.object(sys, "platform", ...)` 命名口径 → `a` 复核；`0-4` 缺口「进程锁无调用方」 → `d`；`a-1`~`a-4` → `a`；真实 `fcntl.flock` 上板 → `d`；覆盖率采集 → 用户裁决。报告须标明「**检视项按阶段收敛，不得用问题清单阻断收尾**」。
- 测试约定核验：12 个新增用例均有一行验收项编号注释、全部 `-> None`、空洞断言 0 命中、`@pytest.mark.*` 0 命中、无为变绿而改被测代码（`edge/tests/contract/*` 既有断言 diff 为空）；既有 `@pytest.mark.skipif` 两条在本机 win32 下实际执行并 `PASSED`、跳过为 0。

## 4. L1 契约层

- `contract-guard` 基线结论：**L1 契约层零自动变更**。`fake_logger.py` 5 行修复属阶段 0 白名单 Fake 侧、非 L1；`edge/interfaces/i_logger.py` 与 `edge/tests/contract/*` 零改动；两项用户裁决（mypy 2 个老错误留阶段 a、双 `[CONFIG]` 前缀留阶段 d）均未导致 L1 改动；结论为「无契约 diff、无需用户批准、不阻断」。
- 契约变更 diff：无。
- 批准状态：无需批准。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— 已遵守。如实注明：**基线差异由主 agent 只读 git 举证**（`git status --porcelain` 空、`git diff --name-status governance-v1 HEAD` 空、tag = HEAD = `a71d97f`），`contract-guard` 如实声明其**无命令执行能力**、仅做当前态静态核验，基线举证来自主 agent。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守 | 启动流程不引入自检 / 自检线程 / 能力降级；`interfaces/` 未新增自检方法；`edge/platform/` 内 Grep 自检 / 线程 0 命中；阶段 0 交付物（`exceptions.py` + `platform/`）不含自检逻辑；`stages/0/spec-digest.md` §4.1 已逐条登记，`SelfChecker.check_all()` 与能力降级均不落地 |
| D-02 非 UP 不启其他线程 | 已遵守 | 本阶段不涉及：无 `linkState`、无心跳 / 解码 / 重连线程、无 `transitionTo`、不 import 线程或 socket；`stages/0/spec-digest.md` §4.1 已逐条登记，不落地，留待 `c3` / `d` |
| D-03 去重不做、seq 只填不用 | 已遵守 | 本阶段不涉及：无协议帧组装、无 `EventCache`、无 `seq`、无补发/去重逻辑；`stages/0/spec-digest.md` §4.1 已逐条登记，不落地，留待 `c3` / `d` |

## 6. 遗留与裁决

- 图与 L1 的冲突点（均**未改图、未改 L1**）：
  - `edge/docs/spec/整体流程/整体流程.txt` 第 1 段的 `SelfChecker.check_all()` 与「部分失败 → 能力降级」分支 → 按 **D-01 不落地**（不新增自检类/线程/接口，不建 `self_check*.py`/`checker/`，不以自检结果控制模块启停；初始化失败仍走 L1 的 Fail-Fast / 记录日志 / 返回失败路径）。
  - 旧图 snake_case、`getInstance` / `getValue` 等专用 getter → 按 **NAMING_AUTHORITY**：一律映射为 camelCase 或 L1 既有接口（`getInstance → instance()`、`getValue → get(section, key, default=None)`），见 `stages/0/spec-digest.md` §3；不改图、不改 L1。
  - 图中「阶段 0~7」是**运行期业务时序编号**，与 9 个实施阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d` 无关，**禁止混用**。
- 两处资料差异（按用户已拍板口径，不列为待确认）：L1 `整体重构方案.txt` §3 小标题 `platform/（阶段 b）` 与 §5 冲突 → **按 §5 阶段 0**（`platform/` 归阶段 0）；`references/stage-catalog.md` §0 #18 备注「#21」实为 **#22 `fake_logger.py`**（#21 `fake_config.py` 本身无断裂）。
- **用户两项裁决原文要点（2026-11-10 阶段 0 收尾）**：
  - (a)「**mypy 那 2 个老错误不动 L1，留到阶段 a 处理**」 → 归属阶段 `a`（`a-3`）；`edge/tests/contract/test_phase0_foundation.py` 与 `edge/pyproject.toml` 属 L1 契约层 / 白名单外、禁写，**不洗绿、不改被测实现、不改预期**，保留真实失败输出，不删用例、不加跳过标记。
  - (b)「**双 `[CONFIG]` 前缀算小瑕疵，留到阶段 d 修，本阶段不改**」 → 归属阶段 `d`；`acquireOrExit()` 实测 `sys.exit` 实参为 `[CONFIG] [CONFIG] 已有实例运行，进程锁获取失败`，新增用例以推导式作精确值断言按实现现状举证，**不洗绿、不改被测实现、不改预期**，未下格式收敛结论。
- B1 提前处置原因：该项原属阶段 a 的 `a-2` / `a-3`，因 `edge/tests/contract/test_interface_contracts.py` 导入 `FakeLogger` 导致**契约测试收集期 ImportError**、阻断阶段 0 补测举证，经用户授权提前到阶段 0 做一次性最小修复（只改 Fake 侧 5 行，不触碰 L1 接口）；**阶段 a 仍按 `a-2` 原措辞独立验收** 8 个 Fake 与 8 个接口签名逐一对齐，并对 `FrameData` 断裂给出正式结论。留痕见 `test-report.md` ⑥ 第 1 行。
- 需用户拍板事项：无（两处资料差异与两项遗留归属、B1 提前修复、单测落点均按用户已拍板口径写入，不重新征询）。
- 阻塞原因与解除条件：无。
- 移交后续阶段的收敛项（逐条 + 归属阶段）：mypy 2 个既有 `untyped-decorator` 错误 → `a`（`a-3`）；`a-1`~`a-4`（interfaces / 其余 Fake / mypy 全绿 / 9 处 Fake 字段类型标注）→ `a`；B1 的 `a-2` 独立验收 + `FrameData` 断裂正式结论 → `a`；测试侧 `patch.object(sys, "platform", ...)` 命名口径复核 → `a`；双 `[CONFIG]` 前缀 → `d`；`inspect.getsource` 脆弱断言改行为断言 → `d`；`0-4` 缺口「进程锁无调用方」 → `d`；真实 `fcntl.flock` 上板 / `msvcrt` 真实分支 → `d`；真实第三方 OS 分支执行 → `d`；是否引入覆盖率采集 → 用户裁决。

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：证据栏（填 `edge/docs/refactor/stages/0/test-report.md` 路径 + 工具链结果 + 举证表结论摘要 + 用户签字记录）、最后更新时间 2026-11-10、§1 追加「收尾状态：待用户确认推进 `done`」行、§5 追加收尾门禁事件一行；状态列保持 `in_progress`，§3 复选框保持 `[ ]`。
- `references/lessons.md` 条目号：**L-01 ｜ 2026-11-10 ｜ 阶段 0**。
- 项目记忆：新建 topic 文件 `project_stage0_leftovers.md`（type: project，记录 2026-11-10 两项遗留归属裁决）+ `MEMORY.md` 追加一行索引。
- `python-code-review` 经验库：`C:\Users\Xiaojiu\.codebuddy\skills\python-code-review\references\accumulated-lessons.md` 已更新（追加 3 条抽象规律 / 判据，类别 `检查项` / `项目约定` / `坏味道`）。
- `references/decisions.md`：**未变更**（用户未下达新的 D-xx 裁决；`decisions.md` 裁决变更协议禁止助手自行推断「第四条裁决」，故不新增 D-04，也不改既有 D-01 / D-02 / D-03）。

## 8. 下阶段开工提示

- 下一阶段：`a`（已有骨架：`interfaces/` + `tests/fakes/`）。
- 必读：`edge/docs/refactor/HANDOFF-0.md`（本 handoff）、`references/stage-catalog.md` 阶段 a 段（含 §0 现状判定）、`references/decisions.md`（命中裁决 D-01 与 `a` 段适用项）、`edge/docs/spec/INDEX.md` 阶段 a 资料、`references/lessons.md`（新增 L-01）、`edge/docs/refactor/STAGE-STATE.md`。
- 特别注意：
  1. **阶段 0 的禁写 `.py` 解除不沿用**：仅对阶段 0 白名单生效；阶段 a 须重新由开工卡经用户点头后才按白名单解除，L1 契约层与 `edge/docs/spec/**` 仍一律禁写。
  2. A5 补强单测落点 `edge/tests/unit/`（新建文件、只新增文件、不改任何既有断言，后续阶段同理）。
  3. B1（`fake_logger.py`）已提前处置，但 **`a-2` 仍按原措辞独立验收** 8 个 Fake 与 8 个接口签名逐一对齐，并对 `FrameData` 断裂给出正式结论；不得因「已修好」跳过。
  4. mypy 2 个既有 `untyped-decorator` 错误归 `a-3`（用户裁决「不动 L1，留阶段 a」），**未批准任何 L1 diff**；阶段 a 在白名单内修正，或由用户批准 L1 diff 后调整，本 handoff 不代表批准。
  5. `edge/docs/refactor/CONFIG-DIFF.patch` 是历史记录、非权威，**不得当资料读**；逐文件资料登记唯一权威为 `edge/docs/spec/INDEX.md`。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**已签署**（2026-11-10 用户本人「我看过代码和 test-report.md 了，签字」；任何 agent 不得代签）。步骤 4 完整举证表亦经用户确认，步骤 7 `stage-verifier` 增量复核 7 项「仍成立」。
- **最终 review 结论（用户口述 2026-11-10，按原文录入，不视为代签）**：「阶段 0 验收通过，同意收尾；mypy 既有 2 错留阶段 a，双 [CONFIG] 前缀留阶段 d。」
  - 录入说明：本条为**用户本人本条口述**的最终结论，由助手按原文照录并注明「用户口述 2026-11-10」；**不视为代签**，任何 agent 不得代用户签署最终 review 结论。
- [x] 配置/交付范围确认
- [x] 举证结论确认
- [x] 状态推进确认（`0` → `done`）
- 确认人 / 日期：确认人 **用户本人（本条口述）** ｜ 日期 **2026-11-10**。
