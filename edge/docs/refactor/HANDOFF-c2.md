# HANDOFF-c2 — 日志管理（阶段 c2）

- **阶段**：`c2`（共 9 个阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d`）
- **日期**：2026-11-11
- **状态**：`done`（2026-11-11 用户本人本条「我看过实现和 test-report.md 了，签字」并口述最终 review 结论，**同时**确认状态推进 `c2 → done`、不再另停一次；结论按原文录入 §9，不视为代签）
- **移交方**：主 agent（按用户 2026-11-11 收尾指令连续完成步骤 4 举证与 `/stage-done c2` 全部文档写入；内容逐项按 `edge/docs/refactor/HANDOFF-TEMPLATE.md` 填写，不冒充 `memory-steward`）
- **接收方**：下一阶段开工（`stage-opener`），下一阶段为 `c3`

## 1. 开工依据

- 用户确认记录：2026-11-11「点头开工，c2 记为 in_progress，按开工卡白名单执行四步」；禁写 `.py` 仅对本次白名单解除、不沿用；四步由主 agent 连续执行、停在人工闸门等签字；对话只回 3 行。
- **API 口径钉死（用户 2026-11-11 当次指令）**：`ILogger` 仅 `rx / tx / info / error` 四方法，`error(msg, exception=None)`；不存在 `init(config)`，不得新增 `FrameData` 类型，`rx/tx` 的 `data` 就是 `dict[str, object] | bytes`。图只取「队列、logMode 路由、文件滚动、磁盘清理、停机清空队列」业务语义，不把图上方法名当 API。极简文档（`spec-digest.md` 五节各 1–3 行、`test-report.md` 六节各 ≤5 行，④ 真实命令与输出、⑥ 未覆盖项及原因不得省），不改任何规则文件。
- 适用权威：`CODEBUDDY.md` §2（用户当次指令 > L1 契约层 > 4 条 always 规则 > L2 图资产 > L3 流程配置 > L4 状态与记忆）+ 规则 `01`~`04`；`test-visibility.mdc`（Agent Requested，必交物与六节）；本阶段命中 `NAMING_AUTHORITY`，D-01 / D-02 / D-03 影响阶段均不含 c2。
- 本阶段 spec 资料（按 `edge/docs/spec/INDEX.md` §2.4 与 `references/diagram-index.md` §2，只列路径与图类型、不转录图中文字）：`日志/日志.txt`（类图 + 流程图 + 时序图源码）、`日志/日志类图.png`、`日志/流程图.png`、`日志/时序图.png`；`整体流程/整体流程.txt` 第 3 段停机时序与 `阶段5-7.png`；L1 只读 `整体重构方案.txt` §1/§3 `infra/` 段/§5 `c2` 行、`编码规范规则.txt` §4.4/§4.5/§5、`interfaces/i_logger.py`、`i_thread.py`、`exceptions.py`、`pyproject.toml`、`tests/contract/*`。
- 上一阶段 handoff：`edge/docs/refactor/HANDOFF-c1.md`（阶段 c1 `done`；§8 提示 c2 须重新经开工卡用户点头、L1 基线按 `stage-c1-done` + 附录 A + 该 handoff §4）。
- 现有代码判定：引 `references/stage-catalog.md` §0——27 个 `.py` 均为新契约风格骨架（非旧代码）；`edge/infra/` 在 c1 建立（`__init__.py` + `config_manager.py`），本阶段 `log_manager.py` 为**纯新增**实现，非审读已有骨架。

## 2. 交付文件与必交物

| 文件 | 操作 | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/infra/log_manager.py` | 新增（白名单） | `c2-1`~`c2-4` | `LogManager(ILogger)` + 类内 `instance()` 双检锁 + `LogExecutor(BaseThread)` + `LogFileWriter`；唯一 `Queue[str]`、异步消费、logMode 合并/分开路由、跨天/超限滚动、磁盘清理、停机清空队列并关句柄、`error(exception=e)` 自动附堆栈；所有阈值/时钟/磁盘比例构造注入 |
| `edge/tests/unit/test_stage_c2_log_manager.py` | 新增（白名单） | `c2-1`~`c2-4` | 12 个补强单测，只新增、既有断言零改动；可控时钟与注入磁盘比例回调保证确定性 |
| `edge/docs/refactor/stages/c2/spec-digest.md` | 新增（步骤 1 `spec-reader`） | `c2-1`~`c2-4` | 五节齐备，每节 1–3 行 |
| `edge/docs/refactor/stages/c2/test-report.md` | 新增（步骤 3 `test-writer`） | `c2-1`~`c2-4`（举证载体） | **必交物**，六节齐备、每节 ≤5 行；④ 真实命令与输出、⑥ 4 行未覆盖项及原因，未写「全部覆盖」 |
| `edge/docs/refactor/stages/c2/verification-evidence.md` | 新增（步骤 4 `stage-verifier`） | `c2-1`~`c2-4` | 举证表落盘；只举证、不下最终结论、不代签 |
| `edge/docs/refactor/STAGE-STATE.md` | 修改（L4） | 全局门禁 | §1 当前阶段 / 禁写解除、§2 c2 行状态与证据栏、§5 开工与收尾门禁记录 |
| `edge/docs/refactor/HANDOFF-c2.md` | 新增（本文件） | 全局门禁 | 按模板九节；§9 录入用户口述结论 |
| `.codebuddy/skills/edge-refactor/references/lessons.md` | 修改（L4） | 全局门禁 | 追加 L-06 |

只读核验对象（零改动）：L1 契约层 17 文件、`edge/docs/spec/**` 原文与 PNG、`edge/tests/fakes/*`、`edge/tests/contract/*`、`edge/base/*`、`edge/infra/config_manager.py`、`edge/platform/*`、`edge/docs/refactor/stages/{0,a,b,c1}/*`、`HANDOFF-{0,a,b,c1}.md`、`references/decisions.md`。

- 必交物：`stages/c2/spec-digest.md` **存在**（五节齐备）；`stages/c2/test-report.md` **六节齐备**（④ 可复现命令 + 真实输出，⑥ 未覆盖项及原因），非判红。
- 范围外文件：`edge/docs/spec/智能工具柜配置项通信协议_初稿.docx` 为工作区既有未跟踪文件，用户 2026-11-11 明确「不属于 c2 阶段产物，本阶段不读取、不登记、不裁决」，仅在收尾 git 提交时一并纳入以保持工作区干净；未登记进 `edge/docs/spec/INDEX.md`、未改任何 spec 原文/图片。其余无范围外改动。
- 遗留 TODO 及归属阶段：见 §6「移交后续阶段的收敛项」；本阶段无未决阻塞。

## 3. 验收项逐条证据

验收项措辞照抄 `references/stage-catalog.md` §2 阶段 c2（未改写）；逐条命令 + 输出 + 用例名的完整举证表见 `edge/docs/refactor/stages/c2/verification-evidence.md` §1（步骤 4，长表只落盘）。

| 编号 | 验收项 | 证据摘要（命令 + 输出 + 测试名 + test-report 对应节） | 举证结果 |
| --- | --- | --- | --- |
| `c2-1` | 唯一 BlockingQueue 异步消费、对外仅四方法 | pytest `63 passed in 1.17s`（收尾复核同值；四步首轮 `1.30s`）；`testILoggerExposesOnlyFourMethods`（`{rx,tx,info,error}`、`errorDefault is None`、`"dict[str, object] \| bytes"`、无 `init`、无 `FrameData`）、`testSingleQueueAndAsyncConsumption`（业务入队时文件内容 `[""]`、`qsize()==4`、停机后 `empty() is True`）、`testLogModeRoutingMergedAndSplit`（合并 1 个 / 分开 4 个 Writer）、`testBuildRecordEncodesDictAndBytes`、`testDirectoryCreationFailsFast`、`testInstanceIsDoubleCheckedSingleton`；`test-report.md` ① 第 1 行 / ③ / ④ | 已逐条举证 |
| `c2-2` | 跨天/超限滚动 + 磁盘清理 | 同上输出；`testRollOverAcrossDays`（`ALL_20261111_0001.log` / `ALL_20261112_0002.log`、day 序列 `["20261111","20261112","20261112"]`）、`testRollOverOnSizeLimit`（`maxFileSize=1`、4 文件、行数 `[0,1,1,1]`）、`testDiskCleanupRemovesOldestFile`（最旧文件删、`_removedCount == 1`、`ratioCalls == 2`）；`test-report.md` ① 第 2 行 / ③ / ④ | 已逐条举证 |
| `c2-3` | 停机清空队列并关句柄 | 同上输出；`testStopDrainsQueueAndClosesHandles`（`empty() is True`、句柄全 `closed is True`、`len==4`、重复 `stop` 幂等）、`testStopWakesBlockedTake`（`isRunning() is False`、`len==2`）；`test-report.md` ① 第 3 行 / ③ / ④ | 已逐条举证 |
| `c2-4` | `error(exception=e)` 自动附堆栈 | 同上输出；`testErrorAppendsStackTrace`（堆栈含 `Traceback (most recent call last)` / `CONFIG` / `配置缺失` / 用例名；无异常记录 `"stack" not in`）；`test-report.md` ① 第 4 行 / ③ / ④ | 已逐条举证 |

- 工具链（收尾复核真实输出，2026-11-11）：`python -m pytest -c edge/pyproject.toml edge/tests -q -p no:cacheprovider` → `63 passed in 1.17s`（退出码 0）；`python -m ruff check edge` → `All checks passed!`（0）；`python -m mypy --config-file edge/pyproject.toml --no-incremental` → `Success: no issues found in 39 source files`（0，附 `unused section(s)` note 非错误）。四步实跑另有 `63 passed in 1.30s` 与 ruff 首轮 `N812 Lowercase 'log_manager' imported as non-lowercase ... Found 1 error`（退出码 1）：已在测试白名单内改 import 别名后复跑全绿，首轮失败如实保留、不洗绿；耗时波动并列保留。含既有 51 例契约/单测全绿。
- 环境：Windows / Python 3.10.8 / pytest 9.1.1 / ruff 0.17.4 / mypy 1.20.2；配置 `edge/pyproject.toml`（mypy 目标 3.9 strict）；前置条件仅 pytest 自带 `tmp_path`，无外部 config.ini、端口或设备。
- `test-report.md` 六节：齐备（①/②/③/④/⑤/⑥）；第 ⑥ 节 4 行未覆盖项摘要：`app_init` 注入与进程锁联动（归 `d`）、真实 `disk_usage` / 平台路径与换行差异 / 上板（归 `d` 与上板）、`ILogger` 接入业务线程与一键停机串行（归 `c3`~`c5`/`d`）、logMode 热切换 / 有界队列阻塞策略 / 坏 JSON 容错（归 `d` 与上板）；覆盖率采集按用户裁决不引入。未写「全部覆盖」。
- `python-code-review` 报告（写完/改完 Python 后检视一次，模式：极简检视；报告随本 handoff 落盘，长表不进对话）：

  ## python 代码检视报告（阶段 c2 收尾）

  - 范围：`edge/infra/log_manager.py`、`edge/tests/unit/test_stage_c2_log_manager.py`（均为本阶段白名单内新增）。
  - 模式：极简检视（用户 2026-11-11 精简模式）；首轮四步阶段已检视一次（见 `test-report.md` ⑤），本轮为收尾复核。
  - 结论：改动全在白名单内；`from __future__ import annotations`、内置泛型、函数/字段/返回值全标注、`## @brief` / `#  @param` / `#  @return` / `#  @raises` 注释合规；`encodePayload` / `buildRecord` / `formatStackTrace` / `defaultDiskFreeRatio` / `rollIfNeeded` / `purgeOldFiles` / `consumeRecord` / `flushRecords` / `closeWriters` / `publishRecord` 全 camelCase，方法名全局不重复（`instance` / `start` / `stop` / `runLoop` / 四方法属接口与多态豁免）；常量 `UPPER_SNAKE_CASE`，`maxFileSize` / `logMode` / `diskFreeThreshold` / `queuePollSec` / `clock` / `diskFreeRatio` 一律构造注入、无魔鬼数字；`infra/` 只依赖标准库 + `edge.base` / `edge.exceptions` / `edge.interfaces`，无业务模块反向 import、不 import 配置模块；业务四方法只组 JSON 入队、无磁盘 IO，落盘在 `BaseThread` 子类后台线程；内置 `OSError` 在 `openHandle` / `__init__` 转 `EdgeError(CONFIG)`，写盘与删旧文件的 `OSError` 属必要容错（跳过本行/继续，不穿线程边界）；停机 `info` 统计入队同时唤醒阻塞 take，`flushRecords` 清空剩余、`closeWriters` 关句柄、重复 `stop` 幂等；12 个用例均有验收项编号注释、具体值断言、无空洞断言、无 skip、无为变绿改被测代码。**不妨碍收尾**；检视项按阶段收敛，不用问题清单阻断收尾。

  | 级别 | 位置 | 维度 | 现状证据 | 影响 | 改进建议 |
  | --- | --- | --- | --- | --- | --- |
  | P3 | `log_manager.py` `buildRecord()` | 方案取舍 | `json.dumps(..., default=str)` 把不可序列化对象退化为字符串 | 业务 payload 含自定义对象时信息有损，L1 未定义序列化细则 | 归 `d`（业务侧定义 payload 契约）；本阶段不改 L1、不改已验收实现 |
  | P3 | `test_stage_c2_log_manager.py` import 别名 | 工具链 | 首轮 `from edge.infra import log_manager as logManagerModule` 触发 ruff `N812` | 仅 lint 失败，无运行时影响 | **已在本阶段白名单内修复**：改用模块原名 `log_manager`，三项复跑全绿 |

  ### 未发现问题的维度

  耦合性（无跨模块反向 import）、Python 特有陷阱（无可变默认参数 / 晚绑定 / 裸 `threading.Thread` / 裸 `time.sleep`）、性能与资源（句柄 `close` 幂等、队列 `put` 无界不阻塞业务线程）、安全（无 `eval` / 路径穿越拼接 / 密钥硬编码）、并发与异步（唯一队列共享、`BaseThread` 停机置位 + join + 超时返回、`_stopLock` 保证幂等）、工程结构（改动全在白名单、文件名全局唯一且 snake_case）。

  ### 跨阶段遗留项（含归属）

  `app_init` 注入与 `ILogger` 接入业务线程、一键停机严格串行 → `c3`~`c5`/`d`；真实磁盘/平台差异/上板 → `d` 与上板；logMode 热切换、有界队列策略、坏 JSON 容错、payload 序列化细则 → `d` 与上板；覆盖率采集按用户裁决不引入。P3 首轮 lint 项已本阶段收敛，不移交。

  ### 下一步

  1. 本阶段无阻断项，不就地再改实现；P3 口径留 `d` 由业务侧收口。
  2. 收尾按用户指令继续 `contract-guard` 复核与沉淀，不另停一次。

  ### 经验沉淀

  - 技能经验库 `accumulated-lessons.md`：追加「检查项」条目（后台消费者线程停机须同时满足唤醒阻塞 take / 清空剩余 / 关句柄，并以入队时文件为空、停机后队列空且句柄关闭三类可观测证据举证）。
  - 项目记忆：更新 `feedback_stage_compact_mode.md`，登记用户 2026-11-11 c2 收尾口径（对话 3 行 = commit 号 / tag 名 / git status；非阶段产物随提交纳入但不读取/不登记/不裁决；完成后停下不执行任何阶段）。

- 测试约定核验：12 个新增用例均有一行验收项编号注释、全部 `-> None`；空洞断言 0 命中；既有 `edge/tests/contract/*`、`edge/tests/fakes/*` 断言 diff 为空；首轮 ruff N812 的修复链为「实跑发现 → 白名单内改测试 import 别名 → 三项复跑全绿」，如实记录、无洗绿。
- 步骤 4 `stage-verifier` 举证表结论（只举证、不含最终结论、不代签）：证据齐备（`c2-1`~`c2-4` 逐条可复核；必交物六节 + ④ 真实输出 + ⑥ 未覆盖项及原因齐备、不判红；工具链退出码均 0；D-01/D-02/D-03 无偏差；L1 无未批准变更、非 blocked；人工闸门已签署）；无未通过项、无判红、无 blocked。完整表落盘于 `stages/c2/verification-evidence.md`。

## 4. L1 契约层

- `contract-guard` 基线结论：**L1 零自动变更（相对最新收尾 tag `stage-c1-done`；已批准基线项不重复判定），不阻断 c2 收尾**（无 `blocked`）。收尾复核为只读静态核验，git 层由主 agent 只读补证。
- 证据：`git --no-pager tag -l stage-c1-done` → `stage-c1-done`；`git --no-pager diff --name-only stage-c1-done HEAD -- edge/docs/spec edge/interfaces edge/exceptions.py edge/pyproject.toml edge/tests/contract` 输出为空；`git status --porcelain` 仅 `M edge/docs/refactor/STAGE-STATE.md` 与白名单/阶段产物新增（`edge/docs/refactor/stages/c2/`、`edge/infra/log_manager.py`、`edge/tests/unit/test_stage_c2_log_manager.py`、沉淀资产、1 个既有未跟踪 docx），均非 L1。L1 17 文件齐备（2 定稿 txt + `编码规范.mdc` + 9 个 `interfaces/*.py` + `exceptions.py` + `pyproject.toml` + 3 个 `tests/contract/*`）；`edge/docs/spec/**` 11 `.txt` + 25 PNG 与 `INDEX.md` 登记吻合，零改/删/重命名；`.codebuddy/rules/编码规范.mdc` 由 status 全覆盖 + 静态只读补证无变更。
- 已批准基线项**已正确识别**：`test_phase0_foundation.py` 的 `windowsOnly` typed 装饰器（`decisions.md` 附录 A，2026-11-10 用户批准，基线已并入 `stage-c1-done`）当前源码与 `HANDOFF-a.md` §4 获批 diff 逐行一致；按 A.3 口径不重复报警、不判「未批准/自动修改」。
- 契约变更 diff：**无**；批准状态：**无需批准**；「等待批准」的契约 diff：**0**。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— 已遵守。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守（本阶段不涉及） | `log_manager.py` 无 `selfCheck` / `SelfChecker` / 能力降级分支 / 自检线程；日志目录不可创建一律 Fail-Fast 抛 `EdgeError(CONFIG)`，符合 D-01「初始化失败按 L1 Fail-Fast 处理」 |
| D-02 非 UP 不启其他线程 | 已遵守（本阶段不涉及） | 无 `linkState` / `transitionTo` / 心跳 / 解码线程；`LogExecutor` 继承 `BaseThread`，为日志后台消费线程，不属链路业务线程；裸 `threading.Thread` 0 命中 |
| D-03 去重不做、seq 只填不用 | 已遵守（本阶段不涉及） | 无 `seq` / `seenSeq` / `dedup` / `PendingRequest`；`Queue` 仅作异步缓冲，无去重缓存 |

> NAMING_AUTHORITY 本阶段命中（用户 2026-11-11 钉死 API 口径）：图上 `init(config)` / `getInstance()` / `enqueue()` / `rollFile()` 等只取语义，落地为 ILogger 四方法 + 类内 `instance()` + 构造注入参数；`LogExecutor` / `LogFileWriter` 留在 `infra/log_manager.py` 内不单列文件；私有方法同样 camelCase；`spec-digest.md` §3 命名裁决表齐备，实现与测试全局无 `init(config)`、无 `FrameData`、无旧图 snake_case API，旧图只取业务语义、不改图、不改 L1、不转录图中文字。

## 6. 遗留与裁决

- 图与 L1 的冲突点（均**未改图、未改 L1**）：日志类图的 `ILogger.init(config: IConfig)`、`IConfig` 专用 getter（`getLogDir` / `getMaxFileSize`）、`ConfigManager.getInstance` / `getConfig`、`LogExecutor` 单列文件与旧版 snake_case → L1 §3 接口表 + `glossary.md` §3；图中「阶段 0~7」是运行期业务时序编号，与 9 个实施阶段无关，未混用。
- 需用户拍板事项：**无**（用户 2026-11-11 已一次性确认开工、API 口径、极简文档口径；同日本条签字并确认状态推进 `done`，⑥ 未覆盖项按归属留后续阶段，不重新征询）。
- 阻塞原因与解除条件：**无**。
- 移交后续阶段的收敛项（逐条 + 归属阶段）：
  1. `app_init` 从真实 `config.ini` 读 logDir / maxFileSize / logMode / 阈值并注入 `LogManager`、进程锁联动 → `d`。
  2. `ILogger` 接入 TCP / USB / 识别业务线程、一键停机严格串行 `USB → 识别 → TCP → 日志` → `c3`~`c5` / `d`。
  3. 真实 `shutil.disk_usage`、平台路径/换行差异收敛到 `IPlatformAdapter`、麒麟 Linux / RK3588 上板 → `d` 与上板。
  4. logMode 运行期热切换、有界队列入队阻塞策略、坏 JSON 记录容错、payload 序列化细则 → `d` 与上板。
  5. 代码覆盖率采集 → 用户裁决明确**不引入**。

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：§1 当前阶段 `c2` = `done`、禁写解除行改为「阶段 c2 已收尾、许可不沿用」；§2 c2 行状态 `done` + 证据栏（填 `edge/docs/refactor/stages/c2/test-report.md`、`verification-evidence.md` 路径 + 工具链结果 + 步骤 4 举证 + 用户签字 + L1 零变更），最后更新时间 2026-11-11；§5 追加开工与收尾门禁事件；§3 复选框按项目惯例保持 `[ ]`。
- `references/lessons.md` 条目号：**L-06**（异步消费/落盘类模块的验收举证口径：业务线程只入队、后台线程落盘，须以「入队时文件为空 / 停机后队列空且句柄关闭」可观测证据举证；时钟、磁盘比例、阈值一律注入回调）。
- 项目记忆：更新 topic 文件 `feedback_stage_compact_mode.md`（type: feedback，追加用户 2026-11-11 c2 收尾口径：对话 3 行 = commit 号 / tag 名 / git status、长表只落盘、非阶段产物随提交纳入但不读取/不登记/不裁决、工作区保持干净、`.codebuddy` 用 `git add -f`、annotated tag、完成后停下不执行任何阶段）；`MEMORY.md` 索引行同步 c2 描述，写入前已查 `MEMORY.md` 去重（沿用既有条目、不新建同义 topic）。
- `python-code-review` 经验库：`C:\Users\Xiaojiu\.codebuddy\skills\python-code-review\references\accumulated-lessons.md` 追加一条「检查项」条目（后台消费者线程停机的唤醒 / 清空 / 关句柄三要素与可观测举证）。
- `references/decisions.md`：**未变更**（无新裁决；D-01 / D-02 / D-03 不变，附录 A 基线按 A.3 使用、不重复判定）。
- git：本阶段所有文档写入**均在提交之前完成**；`.codebuddy` 下 `lessons.md` 用 `git add -f` 精确纳入，不改 `.gitignore`；用户明确的新补 docx 仅随本次提交一并纳入、不读取/不登记/不裁决；提交后打 annotated tag `stage-c2-done` 并确认 `git status` 干净。

## 8. 下阶段开工提示

- 下一阶段：`c3`（`modules/tcp/` 五个文件；验收项 `c3-1`~`c3-5`：退避 `[1,2,4,8,16,30]` 构造注入且可打断、心跳失败去重与非 UP 返回 `False`、半包/粘包 + 超长帧、`transitionTo` 并发宣告 DOWN 靠返回值去重、`FakeSocket` 联调）。
- 必读：`edge/docs/refactor/HANDOFF-c2.md`（本 handoff）、`references/stage-catalog.md` 阶段 c3 段、`references/decisions.md`（**D-02 / D-03 在 c3 命中**，附录 A 的 L1 baseline）、`edge/docs/spec/TCP/断线重连/`、`周期心跳帧/`、`帧解码/` 九份资料（INDEX.md §2.5~2.7）、`references/lessons.md`（L-01~L-06）、`edge/docs/refactor/STAGE-STATE.md`。
- 特别注意：
  1. **阶段 c2 的禁写 `.py` 解除不沿用**：阶段 c3 须重新由开工卡经用户点头后才按白名单解除；L1 契约层与 `edge/docs/spec/**` 仍一律禁写。
  2. L1 基线以 tag `stage-c2-done` + `decisions.md` 附录 A + 本 handoff §4 为准，已批准项不重复判定；新增 L1 改动仍须 diff + 批准。
  3. 补强单测落点固定 `edge/tests/unit/`（只新增文件、不改任何既有断言）；`test-report.md` 六节为每阶段必交物，⑥ 必须列未覆盖项及原因、不写「全部覆盖」，④ 必须给可复现命令与真实输出。
  4. 工具链现状：mypy（3.9 strict）`Success: no issues found in 39 source files`、ruff `All checks passed!`、pytest `63 passed in 1.17s`（四步首轮 `1.30s`，耗时波动并列保留）。
  5. c3 模块内不得出现 `config` / `cv2` / `numpy` / `vision_core` 字样，所有退避、心跳周期、`maxFrameSize` 构造注入；`linkState` 只经 `transitionTo` 写入。
  6. 覆盖率采集用户明确**不引入**；`test-report.md` ⑥ 未覆盖项按归属留后续阶段，勿在 c3 重复征询。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**已签署**（2026-11-11 用户本人「我看过实现和 test-report.md 了，签字」；任何 agent 不得代签）。步骤 4 `stage-verifier` 已出举证表（落盘 `stages/c2/verification-evidence.md`，只举证、不含最终结论）。
- **最终 review 结论（用户口述 2026-11-11，按原文录入，不视为代签）**：「阶段 c2 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。」
  - 录入说明：本条为**用户本人本条口述**的最终结论，由助手按原文照录并注明「用户口述 2026-11-11」；**不视为代签**，任何 agent 不得代用户签署最终 review 结论。用户本条同时构成对状态推进 `c2 → done` 的确认，不再另停一次。
- [x] 配置/交付范围确认
- [x] 举证结论确认
- [x] 状态推进确认（`c2` → `done`）
- 确认人 / 日期：确认人 **用户本人（本条口述）** ｜ 日期 **2026-11-11**。
