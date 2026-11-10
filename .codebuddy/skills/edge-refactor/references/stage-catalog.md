# stage-catalog.md — 阶段清单与验收定义

> L3 长资料。阶段序列、交付范围与验收项的**唯一权威是 L1 `edge/docs/spec/整体重构方案.txt` §3/§5**；
> 本文件是开工/验收时使用的工作副本，不替代 L1，变更阶段定义须走 L1 diff + 用户批准。
> 运行态见 `edge/docs/refactor/STAGE-STATE.md`，本文件不记录状态。
> 路径一律以工作区根为基准（`CODEBUDDY.md` §0）；`references/<file>`、`stages/<id>/` 为约定简写。

## 0. 现有 27 个 `.py` 契约判定（2026-11-10）

判定口径：以方案 A 分层、`编码规范.mdc` 命名/注释/类型标注、`edge/interfaces/` 契约一致性为准。
**结论：27/27 均为新契约风格骨架，无旧代码**（26 项达标 + 1 项契约断裂）；
全部 27 个文件在唯一 `"""模块说明"""` 后第 2 行都有 `from __future__ import annotations`，
全局无 `ConfigManager` / `LogExecutor` / `threading.Thread` / `argparse` / 旧式 `typing` 泛型 /
`configparser` / `cv2` / `numpy` / `vision_core` 命中。

| # | 路径（相对工作区根） | 结论 | 证据要点 |
| --- | --- | --- | --- |
| 1 | `edge/exceptions.py` | 新骨架 | `ErrorCode(IntEnum)` 五码 + 唯一 `EdgeError`，`code.name` |
| 2 | `edge/__init__.py` | 新骨架 | 仅包 docstring + future import |
| 3 | `edge/interfaces/__init__.py` | 新骨架 | 声明零实现零业务依赖，无实现 import |
| 4 | `edge/interfaces/i_camera.py` | 新骨架 | `ICameraDevice(ABC)` 四抽象方法体 `...` |
| 5 | `edge/interfaces/i_config.py` | 新骨架 | `get(section, key, default=None) -> Any`，仅 abc + Any |
| 6 | `edge/interfaces/i_logger.py` | 新骨架 | `ILogger` 恰 `rx/tx/info/error` 四方法，**未定义 `FrameData`** |
| 7 | `edge/interfaces/i_platform.py` | 新骨架 | `joinPath/newline/signalMap/monotonicClock/lockFile` 全抽象 |
| 8 | `edge/interfaces/i_recognition_engine.py` | 新骨架 | `loadModel/infer`，仅依赖 `i_camera.FrameImage` |
| 9 | `edge/interfaces/i_sinks.py` | 新骨架 | 三个 Sink ABC、10 个抽象方法体 `...` |
| 10 | `edge/interfaces/i_socket.py` | 新骨架 | `connect/recv/send/close`，`send -> bool`，无 `setOption` |
| 11 | `edge/interfaces/i_thread.py` | 新骨架 | `stop(timeout=3.0)` / `isRunning()`，Doxygen 注释齐全 |
| 12 | `edge/platform/__init__.py` | 新骨架 | 包标记，无平台分支泄漏 |
| 13 | `edge/platform/adapter.py` | 新骨架 | `WindowsAdapter/LinuxAdapter/PlatformFactory`，`sys.platform` 仅在 `create()` |
| 14 | `edge/platform/file_lock.py` | 新骨架 | `acquireOrExit()` 内 `sys.exit`，`NotImplementedError` 转 `EdgeError(CONFIG)` |
| 15 | `edge/tests/__init__.py` | 新骨架 | 声明 unit/contract/integration/fakes 分层 |
| 16 | `edge/tests/contract/__init__.py` | 新骨架 | 包标记 |
| 17 | `edge/tests/contract/test_phase0_foundation.py` | 新骨架 | 5 个 `testXxx` 覆盖异常码、平台分支、双开取锁 |
| 18 | `edge/tests/contract/test_interface_contracts.py` | 新骨架 | `assert isinstance(Fake*, I*)`；但 import `FakeLogger` 会被 #21 连带阻断 |
| 19 | `edge/tests/fakes/__init__.py` | 新骨架 | 声明与 interfaces 契约同步 |
| 20 | `edge/tests/fakes/fake_camera_device.py` | 新骨架 | 四方法签名对齐；`self.opened` 未显式标类型 |
| 21 | `edge/tests/fakes/fake_config.py` | 新骨架 | `get` 签名一致，`values: dict[str, Any]` |
| 22 | `edge/tests/fakes/fake_logger.py` | **新骨架·契约断裂** | 第 4 行 `from edge.interfaces.i_logger import FrameData, ILogger`，`FrameData` 全库不存在 → 必然 ImportError |
| 23 | `edge/tests/fakes/fake_platform_adapter.py` | 新骨架 | 5 方法签名一致，`lockResult` 显式标注 |
| 24 | `edge/tests/fakes/fake_recognition_engine.py` | 新骨架 | `loadModel/infer` 与接口一致，`list[DetectionItem]` |
| 25 | `edge/tests/fakes/fake_sinks.py` | 新骨架 | 10 个回调签名逐一对齐；`linkUpCount` 未显式标类型 |
| 26 | `edge/tests/fakes/fake_socket.py` | 新骨架 | `send() -> bool`、`recv() -> bytes` |
| 27 | `edge/tests/fakes/fake_thread.py` | 新骨架 | `stop(timeout=3.0)` 一致；`startCount/running` 未显式标类型 |

**总体**：不是「按新契约搭好的完整骨架」，而是**只到阶段 0/a 的干净半成品**——
`base/`、`infra/`、`modules/*/`、`control/`、`main.py`、`app_init.py`、`tests/unit`、`tests/integration` 全部缺席（约 20 个计划文件）。
已知硬伤：`fake_logger.py` 的 `FrameData` 导入使契约测试收集期失败；另有 9 处 Fake 字段缺显式类型标注；
`main.py` 不存在，进程锁「第一件事拿锁」无调用方。

**对 0/a 目标的影响**：因判定为**新骨架而非旧代码**，不启用「按新契约重写或迁移」；
按用户口径改为「先把已有代码看懂、按契约审一遍、补上能说清楚的单测」，
**不盲目重写、不以已有实现直接补验收**。若后续复核发现某文件实为旧代码，则该文件单独转入
「按新契约重写或迁移」并给 diff 等批准。已有文件一律不等于已验收。

## 1. 序列与依赖

**共 9 个阶段**：`0 → a → b → c1 → c2 → c3 → c4 → c5 → d`。

- 严格串行推进，不跳阶、不合并；`c1` 与 `c2` 同属 infra 但按序验收。
- 一次只做已确认范围内的文件；范围外留 TODO 并标明归属阶段。
- 检视项按阶段逐步收敛，不得用问题清单阻断当前阶段开工。
- 验收项编号 `<阶段>-<序号>` 供 `test-report.md` ① 对照表与测试函数注释引用。

## 2. 阶段明细

### 阶段 0 — 已有骨架：审读 + 契约核验 + 补可举证单测

- **现状**：`exceptions.py` + `platform/` 均为新骨架（判定表 #1、#12~#14），`main.py` / `app_init.py` 尚未建立。
- **目标**：先把已有代码看懂、按 L1 契约逐条审一遍、补上能说清楚的单测；不盲目重写、不直接补验收。
- **交付**：`stages/0/spec-digest.md`（逐文件审读结论与契约核验表）、补强单测、`stages/0/test-report.md`；
  实现文件仅在白名单内按需修正。
- **验收项**：
  - `0-1` 逐文件审读结论齐备，明确「新骨架 / 需修正」及依据。
  - `0-2` `EdgeError` 抛出 / 捕获与 `code.name` 日志格式正确。
  - `0-3` `PlatformFactory` Windows 返回 `WindowsAdapter`；Linux 分支 `NotImplementedError` + TODO。
  - `0-4` 双开取锁失败并立即退出；已知缺口「进程锁无调用方」写入未覆盖项及原因。
- **适用裁决**：D-01（启动流程不引入自检）。
- **禁止**：`main()` 用 `try/except` 包业务流程；除 `PlatformFactory` 外出现 `sys.platform`。

### 阶段 a — 已有骨架：审读 + 契约一致性核验 + 补可举证单测

- **现状**：`interfaces/` 8 接口实质达标；`tests/fakes/` 8 个 Fake 形式上齐备但契约一致性不成立（#22）。
- **目标**：把已有代码看懂、按契约审一遍、补上能说清楚的单测；不盲目重写、不直接补验收。
- **交付**：`stages/a/spec-digest.md`、契约核验表、Fake / 契约测试修正（白名单内）、`stages/a/test-report.md`。
- **验收项**：
  - `a-1` `interfaces/` 零实现、零业务 import、全 camelCase、Doxygen 注释覆盖。
  - `a-2` 8 个 Fake 与 8 个接口签名逐一对齐；`fake_logger.py` 的 `FrameData` 断裂有明确结论与处置。
  - `a-3` 契约测试可收集、可执行、通过；mypy（3.9 strict）通过。
  - `a-4` 已知 9 处 Fake 字段类型标注缺口有结论（补齐或列入未覆盖项并说明）。
- **适用裁决**：D-01（`interfaces/` 不新增自检接口）、NAMING_AUTHORITY。
- **禁止**：静默改既有接口签名或既有测试断言；新增接口不同步 Fake；为让测试变绿而改被测代码。

### 阶段 b — 通用生命周期

- **交付**：`edge/base/base_thread.py`、`edge/base/base_service.py`。
- **验收项**：`b-1` `stop()` 瞬间打断 `interruptibleWait`；`b-2` join 超时强制返回；
  `b-3` 重复 `stop` 幂等且 `BaseService` 三件套可多态。
- **适用裁决**：D-02；**禁止**裸 `threading.Thread`、裸 `time.sleep`、`base/` import 业务模块。

### 阶段 c1 — 配置管理

- **交付**：`edge/infra/config_manager.py`。
- **验收项**：`c1-1` Fail-Fast；`c1-2` 类型推断 int/float/bool/list/str；
  `c1-3` `get(default=None)` 两分支；`c1-4` `instance()` 双检锁且可直接构造用于测试。
- **适用裁决**：NAMING_AUTHORITY；**禁止**模块内 import 配置模块、业务模块直连配置单例。

### 阶段 c2 — 日志管理

- **交付**：`edge/infra/log_manager.py`。
- **验收项**：`c2-1` 唯一 BlockingQueue 异步消费、对外仅四方法；`c2-2` 跨天/超限滚动 + 磁盘清理；
  `c2-3` 停机清空队列并关句柄；`c2-4` `error(exception=e)` 自动附堆栈。
- **禁止**：业务线程内磁盘 IO 阻塞；`LogManager` 之外另建队列。

### 阶段 c3 — TCP 模块

- **交付**：`edge/modules/tcp/` 五个文件 + `integration` 联调。
- **验收项**：`c3-1` 退避 `[1,2,4,8,16,30]` 构造注入且可打断；`c3-2` 心跳失败去重、非 UP 返回 `False`；
  `c3-3` 半包/粘包 + 超长帧；`c3-4` `transitionTo` 并发宣告 DOWN 靠返回值去重；`c3-5` `FakeSocket` 联调。
- **适用裁决**：**D-02**、**D-03**、NAMING_AUTHORITY（不感知业务字符串）。
- **禁止**：`tcp/` 下 `config/cv2/numpy/vision_core`；直接读写 `linkState`。

### 阶段 c4 — USB 采集模块

- **交付**：`edge/modules/usb/` 三个文件 + `FakeCamera` 联调。
- **验收项**：`c4-1` 4 线程并发拉起并立即返回；`c4-2` 双路取图落盘；`c4-3` 超 30% 滚动删旧；
  `c4-4` 成功/失败回调互不影响。
- **适用裁决**：**D-01**（自检留空接口）、D-02；**禁止** Sink 回调内阻塞 IO、跨模块 import `recognition/`。

### 阶段 c5 — 识别模块

- **交付**：`edge/modules/recognition/` 四个文件 + `FakeEngine` 联调。
- **验收项**：`c5-1` 模型仅 `loadModel` 一次、`trigger` 立即返回；`c5-2` 推理 3s 超时（构造注入）；
  `c5-3` 空间归集 + 查表校验 + 组 ack；`c5-4` 回调上抛、纯函数留在 `recognition_utils.py`。
- **适用裁决**：D-01、D-02、`trigger()` 内 NPU 并发限流仅留 TODO。

### 阶段 d — 控制、装配与端到端

- **交付**：`edge/control/edge_control.py`、`event_cache.py`、`edge/app_init.py`、`edge/main.py`。
- **验收项**：`d-1` `routeSignal` 按注入 `asyncHandlers` 键分发；`d-2` `EventCache` 补发/丢弃且 `seq` 只填不用；
  `d-3` 一键停机严格串行 `USB → 识别 → TCP → 日志` + 进程锁；`d-4` Windows 端到端。
- **适用裁决**：**D-01 / D-02 / D-03 全部复核**。
- **禁止**：`app_init.py` 写业务逻辑；`main()` 用 `try/except` 包业务流程；实现按 `seq` 去重。

## 3. 每阶段通用门禁

| 环节 | 必做 |
| --- | --- |
| 开工 | 读 `CODEBUDDY.md`、4 条 always 规则、本文件（含 §0）、`STAGE-STATE.md`、`decisions.md`、`diagram-index.md`；`contract-guard` 核验 L1 基线 |
| 步骤 1 | `spec-reader` 产出 `stages/<id>/spec-digest.md`（禁止把图上方法名当 API） |
| 步骤 2 | `implementer` 只改开工清单白名单文件 |
| 步骤 3 | `test-writer` 产出测试 + `stages/<id>/test-report.md`（六节，见 `test-visibility.mdc`） |
| **人工闸门** | **用户本人 review 代码并签字**；未签字不得进入步骤 4 |
| 步骤 4 | `stage-verifier` 只出举证表；最终 review 结论由用户签字，不许代签 |
| 收尾 | `ruff` / `mypy` / `pytest` + 契约测试证据；`python-code-review` 一次；handoff；`STAGE-STATE` 证据栏；沉淀 |
| 判红 | **缺 `test-report.md` 或六节不全 → 验收一律判红、不得收尾** |
| 状态 | 用户确认后才可把 `pending → in_progress → done`；阻塞写 `blocked` + 原因 |

## 4. 阶段定义变更

- 改交付范围、验收项、阶段顺序 = L1 契约变更：输出 diff + 影响面，等用户明确批准。
- 批准后同步本文件、`STAGE-STATE.md`、项目记忆与所有已完成阶段的 handoff 引用。
