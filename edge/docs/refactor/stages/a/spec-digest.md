# 阶段 a 资料消化摘要（spec-digest）

> 产出：`/stage a` 步骤 1，由 `spec-reader` 生成；**本文件是本步骤唯一写入物**。
> 全部路径以工作区根为基准（CODEBUDDY.md §0）；spec 资料路径统一写 `edge/docs/spec/...`。
> 本摘要只表达语义与裁决：不写实现、不写测试、不写 `test-report.md`、不改 `STAGE-STATE.md`、
> 不改 `edge/docs/spec/**` 与 L1、不改 `references/decisions.md`、不改验收项定义、不改状态。
> 旧图标识符只作命名裁决输入，**不作 API**；PNG 只取语义，不转录图中文字。
> 图中「阶段 0~7」是运行期业务时序编号，与 9 个实施阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d` 无关，禁止混用。
> `edge/docs/refactor/CONFIG-DIFF.patch` 是历史记录、非权威，本步骤**未读、未作为任何依据**。

## 1. 本阶段资料清单

筛取口径：`edge/docs/spec/INDEX.md` §2「逐文件登记」中「对应阶段」含 `a` 的条目（L1 两项与整合类图源码 / 位图均为 `0~d`，含 `a`），叠加 `.codebuddy/skills/edge-refactor/references/diagram-index.md` §2 阶段 `a` 行「先读：同文件 §3 接口表 / 再看：整合类图代码.txt 的『抽象接口层』包」。下表图类型取自 `INDEX.md` 登记值；「取用范围」只写语义，不转录图中文字。

| 路径 | 图类型 | 权威级别 | 本阶段取用范围 / 语义 |
| --- | --- | --- | --- |
| `edge/docs/spec/整体重构方案.txt` | 定稿文本 | **L1 契约层（只读）** | **本阶段主资料**：§3「interfaces/（阶段 a）」接口方法表与逐文件职责、§1 决策一览、§4 依赖方向、§5 阶段 a 验收；命名与接口的唯一裁决源 |
| `edge/docs/spec/编码规范规则.txt` | 定稿文本 | **L1 契约层（只读）** | §1 语言与类型标注、§2 命名、§3 Doxygen 注释、§4.4 异常与日志、§8 文件与模块边界（含「tests/fakes/ 中的 Fake 必须与 interfaces/ 契约一致」）；审读与核验基线 |
| `edge/docs/spec/整体流程/整合类图代码.txt` | 整合类图（PlantUML 源码） | L2 语义参考 | **仅「抽象接口层」包**：三类回调契约 / 配置契约 / 日志契约的结构与依赖语义；其中标识符为旧版 snake_case，只作 §3 命名裁决输入，不提供命名与接口定义 |
| `edge/docs/spec/整体流程/整合类图.png` | 整合类图（位图渲染） | L2 语义参考 | 上条源码的位图；仅作「核心控制层 / 抽象接口层 / 业务模块 / 基础设施层」分层与正交连线语义参考，不转录文字 |
| `edge/docs/spec/INDEX.md` | L3 索引资产（非图资产） | L3 索引 | 逐文件登记的唯一权威，用于筛取本阶段资料与图类型；§2.1 / §2.2 登记值即上表来源 |

**未列入本阶段**：`edge/docs/spec/整体流程/整体流程.txt`（对应阶段 `0 / c3 / c4 / c5 / d`）、`阶段0-3.png`（`0 / c3 / d`）、`阶段4-5.png` / `阶段5-7.png`，以及配置文件接口 / 日志 / TCP / USB_Camera / 识别各目录——按 `INDEX.md`「对应阶段」均不含 `a`，留待各自阶段消化。上述 `整体流程.txt` 与 `阶段*.png` 中的「阶段 0~7」是运行期业务时序编号，**不是**实施阶段 `0~d`。

**辅助资料（L3 流程配置 / L4 状态与记忆 / 只读核验对象，非 `edge/docs/spec/**` 图资产，故不登记图类型）**：
- `.codebuddy/skills/edge-refactor/references/decisions.md`（D-01 / D-02 / D-03 全文）
- `.codebuddy/skills/edge-refactor/references/glossary.md`（术语与旧图 → L1 标识符映射）
- `.codebuddy/skills/edge-refactor/references/diagram-index.md`（§2 阶段检索、§4 已知冲突点）
- `.codebuddy/skills/edge-refactor/references/stage-catalog.md`（§0 27 文件判定、§2 阶段 a 验收项 `a-1`~`a-4`）
- `.codebuddy/rules/01_naming_authority.mdc`（NAMING_AUTHORITY 裁决顺序与 L1 保护）
- `edge/docs/refactor/HANDOFF-0.md`（上一阶段 handoff）
- `edge/docs/refactor/STAGE-STATE.md`（阶段 a 开工卡四项裁决记录，只读）
- `edge/docs/refactor/stages/0/spec-digest.md` `§2.3`、`stages/0/test-report.md` `⑥`（B1 修复前状态与留痕，只读）
- 只读审读的源码/测试原件：`edge/interfaces/` 9 文件、`edge/tests/fakes/` 9 文件、`edge/tests/contract/test_interface_contracts.py`、`edge/tests/contract/test_phase0_foundation.py`、`edge/tests/unit/test_stage0_error_and_lock_guards.py`

## 2. 关键语义

### 2.1 运行期行为、状态与异常路径

阶段 a 的落地范围是**接口契约层**（`edge/interfaces/` 8 个 `i_*.py` + `__init__.py`）及其**测试替身**（`edge/tests/fakes/` 8 个 `fake_*.py` + `__init__.py`）。运行期行为：接口全部是 `abc.ABC` 抽象契约，零实现、零业务 import，只声明方法签名与不透明数据类型别名（`FrameImage`、`CameraStatus`、`SignalMapping`、`DetectionItem`、`DecodedSignal`、`AckFrame`）；真实行为由 `infra/` `modules/` `control/` 的实现类在运行期注入并多态实现——`ILogger` 实现类必须异步消费、不得在调用线程阻塞落盘；Sink 回调（信号 / 采集 / 识别三类）只做轻量分发或入队、禁止回调内阻塞 IO；平台差异（路径 / 换行 / 信号 / 时钟 / 文件锁）全部收敛到 `IPlatformAdapter`；`ISocket.send` 用返回值表达失败、链路断由状态机感知。状态：接口层本身**无状态、无逻辑、无状态机**；Fake 在测试期只记录调用与预设返回值（固定帧、固定推理结果、构造注入的锁返回值、标志位），不触碰硬件 / 真实连接 / 真实文件锁 / 真实线程，用于 `isinstance(Fake*, I*)` 与逐方法签名可用的契约一致性核验。异常路径：接口层不抛异常、不定义异常类型；全项目业务异常统一为 `ErrorCode` 五码 + 唯一 `EdgeError`（阶段 0 骨架，非本阶段改动对象）；Fake 的异常边界由构造注入模拟（如 `lockFile() -> None` 代表锁被占用）。按裁决 D-01，`interfaces/` 不新增自检接口 / 类 / 线程（§4.1）。

### 2.2 本阶段目标与验收项措辞（照抄 `stage-catalog.md` §2 阶段 a，不改写）

- **阶段标题 / 目标口径**：「已有骨架：审读 + 契约一致性核验 + 补可举证单测」。按用户已确认口径与 `stage-catalog.md` §0：现有 27 个 `.py` 全部判为**新契约风格骨架（非旧代码）**，因此**不启用「按新契约重写或迁移」**；目标是「把已有代码看懂、按契约审一遍、补上能说清楚的单测」，**不盲目重写、不以已有实现直接补验收**。已有文件一律不等于已验收。
- **验收项编号与措辞逐字照抄**（不改写、不增删）：

| 编号 | 验收项（`stage-catalog.md` §2 阶段 a 原文） |
| --- | --- |
| `a-1` | `interfaces/` 零实现、零业务 import、全 camelCase、Doxygen 注释覆盖。 |
| `a-2` | 8 个 Fake 与 8 个接口签名逐一对齐；`fake_logger.py` 的 `FrameData` 断裂有明确结论与处置。 |
| `a-3` | 契约测试可收集、可执行、通过；mypy（3.9 strict）通过。 |
| `a-4` | 已知 9 处 Fake 字段类型标注缺口有结论（补齐或列入未覆盖项并说明）。 |

- **现状 / 目标 / 交付 / 适用裁决 / 禁止（同段原文，逐字引用）**：
  - 现状：「`interfaces/` 8 接口实质达标；`tests/fakes/` 8 个 Fake 形式上齐备但契约一致性不成立（#22）。」
  - 目标：「把已有代码看懂、按契约审一遍、补上能说清楚的单测；不盲目重写、不直接补验收。」
  - 交付：「`stages/a/spec-digest.md`、契约核验表、Fake / 契约测试修正（白名单内）、`stages/a/test-report.md`。」
  - 适用裁决：「D-01（`interfaces/` 不新增自检接口）、NAMING_AUTHORITY。」
  - 禁止：「静默改既有接口签名或既有测试断言；新增接口不同步 Fake；为让测试变绿而改被测代码。」

### 2.3 `a-1` — `interfaces/` 9 文件逐文件审读结论表

已逐个打开源码原件核实（非转述 `stage-catalog.md` §0 判定），行号指各文件当前内容。四要素逐文件给依据：① 零实现（抽象方法体一律 `...`，无逻辑分支）② 零业务 import（仅 `__future__` / `abc` / `typing` 及接口层内部引用）③ 全 camelCase（方法名）④ Doxygen 注释覆盖（`## @brief` / `# @param` / `# @return`）。9 个文件均属 **L1 契约层，只读禁改**；结论一律「新骨架·达标、无需修正」，条件性白名单对 `interfaces/` 不触发。

| 文件 | 结论 | 零实现 | 零业务 import | camelCase | Doxygen 覆盖 | 契约核验对照 |
| --- | --- | --- | --- | --- | --- | --- |
| `edge/interfaces/__init__.py` | 新骨架·达标，无需修正 | 全文仅 L1 包 docstring + L2 `from __future__ import annotations`，无类、无方法、无语句 | 无任何 import 业务模块 | N/A（无标识符） | N/A（仅唯一一段 `"""模块说明"""`，无其余注释对象） | L1 §3「全部为 `abc.ABC`，零实现、零 import 业务模块」；§4「interfaces/ 不 import 任何实现」 |
| `edge/interfaces/i_camera.py` | 新骨架·达标，无需修正 | L14 `ICameraDevice(ABC)`；L18 `open` / L24 `readFrame` / L30 `close` / L36 `getStatus`，四者 L17/L23/L29/L35 均 `@abstractmethod`、方法体 L19/L25/L31/L37 均 `...` | L2 `__future__`、L4 `abc`；L7 `FrameImage = bytes` / L10 `CameraStatus = dict[str, object]` 为类型别名，非实现 | `open` / `readFrame` / `close` / `getStatus` 全 camelCase | L1 docstring；L6/L9 别名、L13 类、L15/L21/L27/L33 各方法均有 `## @brief` + `# @return`（L11/L12、L22、L28、L34 等） | L1 §3 `ICameraDevice`「open() / readFrame() / close() / getStatus()」 |
| `edge/interfaces/i_config.py` | 新骨架·达标，无需修正 | L9 `IConfig(ABC)`；L16 `get(section, key, default=None) -> Any`，L15 `@abstractmethod`、体 L17 `...` | L2 `__future__`、L4 `abc`、L5 `typing.Any`（初版保留 `Any` 为 §7/编码规范 §7 允许） | `get` | L1 docstring；L8 类、L10~14 方法注释（`## @brief` + 三 `@param` + `@return`） | L1 §3 `IConfig`「get(section, key, default=None) -> Any」 |
| `edge/interfaces/i_logger.py` | 新骨架·达标，无需修正 | L8 `ILogger(ABC)`；L14 `rx` / L22 `tx` / L30 `info` / L39 `error`，四者均 `@abstractmethod` + `...` | L2 `__future__`、L4 `abc` | `rx` / `tx` / `info` / `error` 全 camelCase | L1 docstring；L7 类、L9/L17/L25/L33 各方法注释齐全 | L1 §3 `ILogger`「rx(module, data) / tx(module, data) / info(module, msg) / error(module, msg, exception=None)」；**全文 L1~41 未定义 `FrameData`**（§2.4 结论依据） |
| `edge/interfaces/i_platform.py` | 新骨架·达标，无需修正 | L12 `IPlatformAdapter(ABC)`；L17 `joinPath` / L23 `newline` / L29 `signalMap` / L35 `monotonicClock` / L42 `lockFile`，五者均 `@abstractmethod` + `...` | L2 `__future__`、L4 `abc`、L5 `typing.BinaryIO`；L8 `SignalMapping` 别名 | 五方法全 camelCase | L1 docstring；L7 别名、L11 类、L13/L21/L26/L32/L38 各方法注释齐全 | L1 §3 `IPlatformAdapter`「joinPath / newline / signalMap / monotonicClock / lockFile」；编码规范 §4.5 平台差异收敛 |
| `edge/interfaces/i_recognition_engine.py` | 新骨架·达标，无需修正 | L13 `IRecognitionEngine(ABC)`；L18 `loadModel` / L25 `infer`，均 `@abstractmethod` + `...` | L2 `__future__`、L4 `abc`、**L6 `from edge.interfaces.i_camera import FrameImage`（接口层内部引用，非实现模块 import）**；L9 `DetectionItem` 别名 | `loadModel` / `infer` | L1 docstring；L8 别名、L12 类、L14/L21 方法注释齐全 | L1 §3 `IRecognitionEngine`「loadModel(path) / infer(image) -> list（纯函数，为 rknn / .so 预留）」；L1 §4「interfaces/ 不 import 任何实现」——依赖同层接口类型别名，不违反 |
| `edge/interfaces/i_sinks.py` | 新骨架·达标，无需修正 | L14 `SignalSink`（L19/L26/L34/L40 四方法）、L45 `ICaptureSink`（L51/L59 两方法）、L64 `IRecognitionSink`（L71/L79 两方法），共 **8 个** `@abstractmethod`、体均 `...` | L2 `__future__`、L4 `abc`；L7 `DecodedSignal` / L10 `AckFrame` 别名 | 8 方法全 camelCase（含 `requestId`） | L1 docstring；L6/L9 别名、L13/L44/L63 类、各方法注释齐全 | L1 §3 `SignalSink` / `ICaptureSink` / `IRecognitionSink` 共 8 个回调方法；编码规范 §5「回调只做轻量分发或入队」 |
| `edge/interfaces/i_socket.py` | 新骨架·达标，无需修正 | L8 `ISocket(ABC)`；L12 `connect` / L18 `recv` / L25 `send` / L31 `close`，均 `@abstractmethod` + `...` | L2 `__future__`、L4 `abc` | 四方法全 camelCase | L1 docstring；L7 类、L9/L15/L21/L28 各方法注释齐全 | L1 §3 `ISocket`「connect() / recv() / send(data) / close()；setOption 不进接口」；`send -> bool` |
| `edge/interfaces/i_thread.py` | 新骨架·达标，无需修正 | L8 `IThread(ABC)`；L12 `start` / L19 `stop(timeout: float = 3.0)` / L25 `isRunning`，均 `@abstractmethod` + `...` | L2 `__future__`、L4 `abc` | 三方法全 camelCase | L1 docstring；L7 类、L9/L15/L22 各方法注释齐全 | L1 §3 `IThread`「start() / stop(timeout=3.0) / isRunning()」；`i_socket.py` / 本文件只是**接口定义**，非线程实现，不触发 D-02 |

**汇总结论（供 `implementer` 直接采信）**：9 文件全部满足 `a-1` 四要素，**零实现、零业务 import、全 camelCase、Doxygen 注释覆盖**；`i_recognition_engine.py` L6 的 `FrameImage` 引用是接口层内部依赖（同属 L1、非实现），已如实登记。`interfaces/` 一律**不得改动**（D-01 + L1 保护 + 阶段 a 白名单不含 `interfaces/`）。

### 2.4 `a-2` — 8 接口 × 8 Fake 签名逐一对齐核验表 + `FrameData` 断裂正式结论

核验口径：按 **8 个 `i_*.py` 接口文件 ↔ 8 个 `fake_*.py` Fake 文件** 配对；`i_sinks.py` / `fake_sinks.py` 内含 3 组 Sink ABC ↔ Fake 类，逐一列出。签名以 L1 §3 接口表 + 两端源码原件为准（均已打开核实）。下表中 `\|` 表示类型联合符。

| 接口文件 / 类 | 方法 | 接口签名（源码） | Fake 文件 / 类 | Fake 实现签名（源码） | 结论 |
| --- | --- | --- | --- | --- | --- |
| `i_config.py` `IConfig` | `get` | `get(self, section: str, key: str, default: Any = None) -> Any`（L16） | `fake_config.py` `FakeConfig`（L10） | `get(self, section: str, key: str, default: Any = None) -> Any`（L24） | 对齐 |
| `i_logger.py` `ILogger` | `rx` | `rx(self, module: str, data: dict[str, object] \| bytes) -> None`（L14） | `fake_logger.py` `FakeLogger`（L8） | `rx(self, module: str, data: dict[str, object] \| bytes) -> None`（L24） | 对齐 |
| `i_logger.py` `ILogger` | `tx` | `tx(self, module: str, data: dict[str, object] \| bytes) -> None`（L22） | `fake_logger.py` | `tx(self, module: str, data: dict[str, object] \| bytes) -> None`（L31） | 对齐 |
| `i_logger.py` `ILogger` | `info` | `info(self, module: str, msg: str) -> None`（L30） | `fake_logger.py` | `info(self, module: str, msg: str) -> None`（L38） | 对齐 |
| `i_logger.py` `ILogger` | `error` | `error(self, module: str, msg: str, exception: Exception \| None = None) -> None`（L39） | `fake_logger.py` | `error(self, module: str, msg: str, exception: Exception \| None = None) -> None`（L46） | 对齐 |
| `i_thread.py` `IThread` | `start` | `start(self) -> None`（L12） | `fake_thread.py` `FakeThread`（L8） | `start(self) -> None`（L20） | 对齐 |
| `i_thread.py` `IThread` | `stop` | `stop(self, timeout: float = 3.0) -> None`（L19） | `fake_thread.py` | `stop(self, timeout: float = 3.0) -> None`（L27） | 对齐 |
| `i_thread.py` `IThread` | `isRunning` | `isRunning(self) -> bool`（L25） | `fake_thread.py` | `isRunning(self) -> bool`（L33） | 对齐 |
| `i_socket.py` `ISocket` | `connect` | `connect(self) -> None`（L12） | `fake_socket.py` `FakeSocket`（L8） | `connect(self) -> None`（L23） | 对齐 |
| `i_socket.py` `ISocket` | `recv` | `recv(self) -> bytes`（L18） | `fake_socket.py` | `recv(self) -> bytes`（L28） | 对齐 |
| `i_socket.py` `ISocket` | `send` | `send(self, data: bytes) -> bool`（L25） | `fake_socket.py` | `send(self, data: bytes) -> bool`（L34） | 对齐 |
| `i_socket.py` `ISocket` | `close` | `close(self) -> None`（L31） | `fake_socket.py` | `close(self) -> None`（L40） | 对齐 |
| `i_camera.py` `ICameraDevice` | `open` | `open(self) -> None`（L18） | `fake_camera_device.py` `FakeCameraDevice`（L8） | `open(self) -> None`（L21） | 对齐 |
| `i_camera.py` `ICameraDevice` | `readFrame` | `readFrame(self) -> FrameImage \| None`（L24） | `fake_camera_device.py` | `readFrame(self) -> FrameImage \| None`（L26） | 对齐 |
| `i_camera.py` `ICameraDevice` | `close` | `close(self) -> None`（L30） | `fake_camera_device.py` | `close(self) -> None`（L31） | 对齐 |
| `i_camera.py` `ICameraDevice` | `getStatus` | `getStatus(self) -> CameraStatus`（L36） | `fake_camera_device.py` | `getStatus(self) -> CameraStatus`（L36） | 对齐 |
| `i_recognition_engine.py` `IRecognitionEngine` | `loadModel` | `loadModel(self, path: str) -> None`（L18） | `fake_recognition_engine.py` `FakeRecognitionEngine`（L9） | `loadModel(self, path: str) -> None`（L21） | 对齐 |
| `i_recognition_engine.py` `IRecognitionEngine` | `infer` | `infer(self, image: FrameImage) -> list[DetectionItem]`（L25） | `fake_recognition_engine.py` | `infer(self, image: FrameImage) -> list[DetectionItem]`（L27） | 对齐 |
| `i_platform.py` `IPlatformAdapter` | `joinPath` | `joinPath(self, *parts: str) -> str`（L17） | `fake_platform_adapter.py` `FakePlatformAdapter`（L10） | `joinPath(self, *parts: str) -> str`（L22） | 对齐 |
| `i_platform.py` `IPlatformAdapter` | `newline` | `newline(self) -> str`（L23） | `fake_platform_adapter.py` | `newline(self) -> str`（L27） | 对齐 |
| `i_platform.py` `IPlatformAdapter` | `signalMap` | `signalMap(self) -> SignalMapping`（L29） | `fake_platform_adapter.py` | `signalMap(self) -> SignalMapping`（L32） | 对齐 |
| `i_platform.py` `IPlatformAdapter` | `monotonicClock` | `monotonicClock(self) -> float`（L35） | `fake_platform_adapter.py` | `monotonicClock(self) -> float`（L37） | 对齐 |
| `i_platform.py` `IPlatformAdapter` | `lockFile` | `lockFile(self, filePath: str) -> BinaryIO \| None`（L42） | `fake_platform_adapter.py` | `lockFile(self, filePath: str) -> BinaryIO \| None`（L43） | 对齐 |
| `i_sinks.py` `SignalSink` | `onSignalDecoded` | `onSignalDecoded(self, signal: DecodedSignal) -> None`（L19） | `fake_sinks.py` `FakeSignalSink`（L14） | `onSignalDecoded(self, signal: DecodedSignal) -> None`（L29） | 对齐 |
| `i_sinks.py` `SignalSink` | `onFrameError` | `onFrameError(self, exception: Exception) -> None`（L26） | `fake_sinks.py` `FakeSignalSink` | `onFrameError(self, exception: Exception) -> None`（L35） | 对齐 |
| `i_sinks.py` `SignalSink` | `onLinkDown` | `onLinkDown(self, reason: str, source: str) -> None`（L34） | `fake_sinks.py` `FakeSignalSink` | `onLinkDown(self, reason: str, source: str) -> None`（L42） | 对齐 |
| `i_sinks.py` `SignalSink` | `onLinkUp` | `onLinkUp(self) -> None`（L40） | `fake_sinks.py` `FakeSignalSink` | `onLinkUp(self) -> None`（L47） | 对齐 |
| `i_sinks.py` `ICaptureSink` | `onCaptureSuccess` | `onCaptureSuccess(self, workerId: int, path: str) -> None`（L51） | `fake_sinks.py` `FakeCaptureSink`（L52） | `onCaptureSuccess(self, workerId: int, path: str) -> None`（L64） | 对齐 |
| `i_sinks.py` `ICaptureSink` | `onCaptureError` | `onCaptureError(self, workerId: int, exception: Exception) -> None`（L59） | `fake_sinks.py` `FakeCaptureSink` | `onCaptureError(self, workerId: int, exception: Exception) -> None`（L71） | 对齐 |
| `i_sinks.py` `IRecognitionSink` | `onRecognitionResult` | `onRecognitionResult(self, workerId: int, ack: AckFrame, requestId: str) -> None`（L71） | `fake_sinks.py` `FakeRecognitionSink`（L76） | `onRecognitionResult(self, workerId: int, ack: AckFrame, requestId: str) -> None`（L89） | 对齐 |
| `i_sinks.py` `IRecognitionSink` | `onRecognitionError` | `onRecognitionError(self, workerId: int, exception: Exception) -> None`（L79） | `fake_sinks.py` `FakeRecognitionSink` | `onRecognitionError(self, workerId: int, exception: Exception) -> None`（L96） | 对齐 |

**`FrameData` 断裂——正式结论（按 `a-2` 原措辞独立验收，不因「已修好」跳过）**：

1. **断裂事实（修复前状态，依据 `stage-catalog.md` §0 #22、`stages/0/spec-digest.md` §2.3、`HANDOFF-0.md` §2）**：`edge/tests/fakes/fake_logger.py` 原有 `from edge.interfaces.i_logger import FrameData, ILogger`，并用 `FrameData` 标注 `rxRecords` / `txRecords` 与 `rx` / `tx` 的 `data` 参数；而 `edge/interfaces/i_logger.py` 全文（L1~41）**未定义 `FrameData`**，L1 §3 接口表亦无此类型，全库不存在 → 必然 `ImportError`，并经 `edge/tests/contract/test_interface_contracts.py` L16 `from edge.tests.fakes.fake_logger import FakeLogger` 使契约测试**收集期**即失败。
2. **定性**：`FrameData` 是**虚构类型导入导致的 Fake 侧契约断裂**，不是 API 变更。L1 §3 `tcp_heart_thread.py` 中的 `buildFrameData()` 是组帧**方法名**，不构成 `FrameData` **类型**定义依据，两者不可混同（`stages/0/spec-digest.md` §2.3 已澄清）。处置方向只能是「Fake 向 L1 既有签名对齐」，**严禁**反向往 `i_logger.py` 新增 `FrameData` 或改接口签名（L1 保护 + NAMING_AUTHORITY）。
3. **处置（阶段 0 已完成，B1）**：经用户授权提前到阶段 0 做**一次性 5 行最小修复**——删除不存在的 `FrameData` 导入，`rxRecords` / `txRecords` 与 `rx` / `tx` 类型对齐 `dict[str, object] \| bytes`；`edge/interfaces/i_logger.py` **零改动**，既有断言零改动。留痕见 `stages/0/test-report.md` ⑥ 第 1 行、`HANDOFF-0.md` §2 / §6。
4. **现状复核（本步骤读源码原件）**：`fake_logger.py` L4 现为 `from edge.interfaces.i_logger import ILogger`（已无 `FrameData`）；L12 / L14 记录列表显式标注 `list[tuple[str, dict[str, object] \| bytes]]`，L24 / L31 `data: dict[str, object] \| bytes`，与 `i_logger.py` L14 / L22 完全一致；`test_interface_contracts.py` 的 `FakeLogger` 导入不再触发 `ImportError`，`testAllFakesSatisfyContracts` 的 `isinstance(FakeLogger(), ILogger)` 具备可收集前提。
5. **阶段 a 独立验收结论**：B1 处置方向正确、现状 8 Fake 与 8 接口签名逐一对齐（上表 31 行全「对齐」）；`FrameData` 断裂**有明确结论与处置**（虚构类型、Fake 侧对齐、L1 零改动、已在阶段 0 提前修复并留痕）。阶段 a 仍按 `a-2` 原措辞**独立举证**（契约测试可收集 / 可执行 / 通过由 `a-3` 承接），不得因「已修好」跳过；不追加任何 L1 改动。

### 2.5 `a-3` — 首次经用户批准的 L1 契约 diff（如实记录，不洗绿、不改 `decisions.md`）

**事实（2026-11-10 用户已确认，本 `spec-reader` 只读审读、未自行执行任何验证命令）**：用户已明确批准一份 **L1 契约 diff**，并由主 agent 落地于 `edge/tests/contract/test_phase0_foundation.py`——新增 typed 装饰器 wrapper `windowsOnly(reason: str) -> Callable[[Callable[[], None]], Callable[[], None]]`（以 `cast` 包装 `pytest.mark.skipif`），替换两处 `@pytest.mark.skipif(os.name != "nt", reason=...)` 为 `@windowsOnly("仅 Windows 验证")`，**不改 `edge/pyproject.toml`**。这是**首次经用户批准的 L1 变更**。

- **现状与 diff 一致性（读源码原件核实）**：`test_phase0_foundation.py` L19~21 为 `windowsOnly` 的 `## @brief` / `@param` / `@return` 注释、L22~26 为 `windowsOnly` 定义（`cast` + `pytest.mark.skipif`）、L38 与 L60 为两处 `@windowsOnly("仅 Windows 验证")`；原 `@pytest.mark.skipif(...)` 两处已不在；5 个 `testXxx` 用例（`testEdgeErrorCarriesCodeName` L30、`testFactoryReturnsWindowsAdapter` L39、`testLinuxAdapterSkeletonRaises` L44、`testLinuxSkeletonIsConvertedToEdgeError` L50、`testSecondProcessCannotAcquireLock` L61）及其既有断言**保持不变**。
- **口径（用户要求如实记录）**：「**不改 L1 之外的既有断言、不洗绿**」——本次变更范围严格限定在该 L1 文件的装饰器写法，未改 `edge/tests/unit/` 补强单测、未改 Fake、未改 `test_interface_contracts.py` 既有断言；未删用例、未加跳过标记、未整体关闭错误码、未为让测试变绿而改被测代码。
- **落地后主 agent 实跑结果（用户确认、如实照录）**：mypy `Success: no issues found in 29 source files`（退出码 0；附 note `unused section(s): module = ['_pytest.*', 'pytest.*']`，note 非错误）、ruff `All checks passed!`、pytest `22 passed in 0.29s`。
- **阶段 0 历史失败不倒改、不洗绿**：`stages/0/test-report.md` ④ / ③ 附注 1 / ⑥ 第 4 行与 `HANDOFF-0.md` §3 记录的 mypy `Found 2 errors in 1 file (checked 29 source files)`（`:26` / `:48` 两条 `untyped-decorator`、退出码 1）是**阶段 0 收尾时**的真实输出；与本次 L1 diff 落地后的 mypy 全绿属**两个不同时间点**的事实，二者并存、如实保留，**不倒改、不洗绿**。
- **登记要求（收尾动作，本摘要不执行）**：用户要求**收尾时**把这一「首次经用户批准的 L1 变更」登记进 `.codebuddy/skills/edge-refactor/references/decisions.md` 与 handoff，作为后续 baseline 对比依据。本 `spec-reader` **不自行修改 `decisions.md` / handoff / `STAGE-STATE.md`**；`STAGE-STATE.md` §1 / §2 / §5 中「L1 契约 diff 待批准后启动四步」为**开工卡时**快照，与用户本次确认「diff 其后已获批准并落地」是时间先后关系，本摘要只记录事实、不改状态。
- `a-3` 的「契约测试可收集、可执行、通过」另由步骤 3 `test-writer` 在 `stages/a/test-report.md` 举证，本摘要不写测试、不出举证表。

### 2.6 `a-4` — 10 处 Fake 字段类型标注缺口逐处清单（2026-11-10 用户裁决按 10 处口径收口）

**用户裁决口径（2026-11-10）**：开工卡第 ② 项为「`a-4` **9 处 Fake 字段类型标注在白名单内补齐，不列为未覆盖项**」；同日用户追加裁决「**第 10 处 `lockResult`（`fake_platform_adapter.py` L15）一并补齐字段级标注，按 10 处口径收口，不再纠结 9/10 差异**」。合并口径：下表 9 处 + 第 10 处 = **10 处全部补齐**，`stages/a/test-report.md` ⑥ 不将其列入未覆盖项；`a-4` 验收项措辞仍按 §2.2 照抄，不改写、不改验收项定义。按 `编码规范规则.txt` §1「`__init__` 入参、类字段、私有方法同样适用」与 §8，补齐方式为在字段赋值处加显式类型标注，不改方法签名、不改既有断言、不改 `interfaces/`。

| # | 文件 | 字段（行号） | 当前写法 | 应补类型 | 依据（构造参数 / 用法） |
| --- | --- | --- | --- | --- | --- |
| 1 | `edge/tests/fakes/fake_camera_device.py` | `self.frame`（L13） | `self.frame = frame` | `FrameImage \| None` | L11 构造参数 `frame: FrameImage \| None = b"frame"`；L26 `readFrame` 返回 `FrameImage \| None` |
| 2 | `edge/tests/fakes/fake_camera_device.py` | `self.opened`（L15） | `self.opened = False` | `bool` | L22 `open()` 置 `True`、L37 `getStatus()` 以 `{"opened": self.opened}` 读出；`stage-catalog.md` §0 #20 明确点名 |
| 3 | `edge/tests/fakes/fake_camera_device.py` | `self.closed`（L17） | `self.closed = False` | `bool` | L32 `close()` 置 `True` |
| 4 | `edge/tests/fakes/fake_sinks.py` | `self.linkUpCount`（L24） | `self.linkUpCount = 0` | `int` | L48 `onLinkUp()` 做 `+= 1`；`stage-catalog.md` §0 #25 明确点名 |
| 5 | `edge/tests/fakes/fake_socket.py` | `self.recvData`（L13） | `self.recvData = recvData` | `bytes` | L11 构造参数 `recvData: bytes = b""`；L29 `recv()` 返回 `bytes` |
| 6 | `edge/tests/fakes/fake_socket.py` | `self.connected`（L17） | `self.connected = False` | `bool` | L24 `connect()` 置 `True` |
| 7 | `edge/tests/fakes/fake_socket.py` | `self.closed`（L19） | `self.closed = False` | `bool` | L41 `close()` 置 `True`；`test_interface_contracts.py` L76 断言 `socket.closed` |
| 8 | `edge/tests/fakes/fake_thread.py` | `self.startCount`（L12） | `self.startCount = 0` | `int` | L21 `start()` 做 `+= 1`；`stage-catalog.md` §0 #27 明确点名 |
| 9 | `edge/tests/fakes/fake_thread.py` | `self.running`（L16） | `self.running = False` | `bool` | L22 / L29 置 `True` / `False`，L34 `isRunning()` 返回；`stage-catalog.md` §0 #27 明确点名 |
| 10 | `edge/tests/fakes/fake_platform_adapter.py` | `self.lockResult`（L15） | `self.lockResult = lockResult` | `BinaryIO \| None` | L13 构造参数 `lockResult: BinaryIO \| None = None`；L45 `lockFile()` 返回该值；按 2026-11-10 用户追加裁决纳入 |

分布：5 个 Fake 文件共 10 处（`fake_camera_device.py` 3、`fake_sinks.py` 1、`fake_socket.py` 3、`fake_thread.py` 2、`fake_platform_adapter.py` 1）。其余 Fake 字段已带显式标注（`fake_config.py` L15/L17、`fake_logger.py` L12/L14/L16/L18、`fake_platform_adapter.py` L17 `lockCalls`、`fake_recognition_engine.py` L14/L16、`fake_sinks.py` 其余 7 处、`fake_socket.py` L15、`fake_thread.py` L14），**不在补齐范围**。

> **计数口径收口（2026-11-10 用户裁决，不再纠结 9/10 差异）**：按「源码中所有 `self.<字段>` 赋值处无冒号标注」的逐字段严格口径枚举为 10 处；资料 `stage-catalog.md` §0 #23 把 `fake_platform_adapter.py` 记为「`lockResult` 显式标注」是因其构造参数 L13 已标注，故原开工卡按资料口径记 9 处。用户 2026-11-10 明确裁决按 **10 处**口径收口、第 10 处一并补齐字段级标注；差异不再作为待确认项，裁决同步登记于 §5 第 1 条。`a-4` 结论「白名单内补齐、不列为未覆盖项」保持不变；既有补强单测不重写（用户 2026-11-10 指令），第 10 处由实现改动、工具链实跑与改动清单举证。

### 2.7 用户指定复核结论（第 4 条裁决）：`patch.object(sys, "platform", ...)` 命名口径

**用法事实（读 `edge/tests/unit/test_stage0_error_and_lock_guards.py` 源码原件）**：L7 `from unittest.mock import patch`；L64 `with patch.object(sys, "platform", "win32"):`（`testFactoryReturnsWindowsAdapterForWin32`）、L73 `with patch.object(sys, "platform", "linux"):`（`testFactoryReturnsLinuxAdapterForLinux`）、L83 `with patch.object(sys, "platform", "freebsd"):`（`testFactoryRejectsUnsupportedPlatformWithConfig`）。三处均为在 win32 主机上对 CPython 标准库 `sys` 模块属性 `platform` 做运行时 monkeypatch，以驱动被测 `PlatformFactory.create()` 的三条分支；是阶段 0 已由用户本人签字验收的 `0-3` 补强单测（`HANDOFF-0.md` §3 / §9、`stages/0/test-report.md` ③）。

- **是否属 NAMING_AUTHORITY 管辖：否**。`.codebuddy/rules/01_naming_authority.mdc` §3 管辖的是「**所有落到 `.py` 的标识符**」（类名 / 方法名 / 变量名 / 参数名），裁决顺序为 L1 §3 接口表 → 编码规范 §2 命名规则 → camelCase 转换。而这里的 `"platform"` 是**标准库 `sys` 模块既有属性名的字符串字面量**（`patch.object` 的 target 实参），既不是本项目定义的方法 / 变量 / 参数 / 类标识符，也不是待按 camelCase 转换的旧图标识符；NAMING_AUTHORITY 不改写第三方 / 标准库标识符，也不把字符串常量当方法名裁决。
- **是否存在口径问题**：**命名维度不存在**——不存在「应改成 camelCase」或「与 L1 接口表冲突」的命名口径问题，`"platform"` 必须保持标准库原样拼写，任何改写都会使 patch 失效。复核中另识别到一处**不同维度**的解释空间：`编码规范规则.txt` §4.5「全项目只有 PlatformFactory 允许出现 `sys.platform`」若按「任何对 `sys.platform` 的引用（含测试侧 monkeypatch 目标）」的最严格字面解释，测试侧这三处打桩是否算受控例外——这属于「平台分支收敛约束的适用边界」，**不是命名问题**，本复核不对此下裁决、不扩大范围（见 §5 第 2 条）。
- **结论落点**：仅写入本 `edge/docs/refactor/stages/a/spec-digest.md`；「**只出结论，不改上一阶段任何产物文件**」——不改 `edge/tests/unit/test_stage0_error_and_lock_guards.py`、不改 `stages/0/*`、不改阶段 0 handoff / test-report / STAGE-STATE；不作为阶段 a 的「需修正」项，不触发任何 `.py` 白名单改动。命名结论本身不自行选边、不扩大范围。

## 3. 命名裁决表

依据本阶段 L2 资料（`edge/docs/spec/整体流程/整合类图代码.txt`「抽象接口层」包）中出现的旧图标识符，逐项给出 L1 落地口径。裁决顺序按 **NAMING_AUTHORITY（本阶段命中）**：L1 §3 接口方法表 → 编码规范 §2 命名规则 → 其余按 camelCase 转换；旧图标识符不具裁决权。「L1 落地标识符」列均给出完整落地签名（含参数类型与返回值），**无留空、无照抄图名**；图只表达语义，不提供命名与接口定义（不改图、不改 L1）。

| 图上标识符（抽象接口层包） | L1 落地标识符 | 依据 |
| --- | --- | --- |
| `IConfig.getValue(section, key) : Any` | `IConfig.get(self, section: str, key: str, default: Any = None) -> Any` | L1 §3 接口表 `IConfig`；`glossary.md` §3.1；专用 getter 一律收敛为通用 `get`，图上无 `default` 形参以 L1 为准 |
| `ILogger.info(msg) : void` | `ILogger.info(self, module: str, msg: str) -> None` | L1 §3 接口表 `ILogger` 恰 `rx / tx / info / error` 四方法；图上仅列 2 个方法属语义子集，且 L1 带 `module` 形参 |
| `ILogger.error(msg) : void` | `ILogger.error(self, module: str, msg: str, exception: Exception \| None = None) -> None` | 同上；L1 §1「error 可选附堆栈」，落地带 `exception=None` |
| `SignalSink.onSignalDecoded(signal) : void` | `SignalSink.onSignalDecoded(self, signal: DecodedSignal) -> None` | L1 §3 接口表 `SignalSink`；`i_sinks.py` L19；图已是 camelCase，落地按 L1 补类型与 `-> None` |
| `SignalSink.onFrameError(exception) : void` | `SignalSink.onFrameError(self, exception: Exception) -> None` | L1 §3 接口表 `SignalSink`；`i_sinks.py` L26 |
| `SignalSink.onLinkDown(reason, source) : void` | `SignalSink.onLinkDown(self, reason: str, source: str) -> None` | L1 §3 接口表 `SignalSink`；`i_sinks.py` L34；断链靠 `transitionTo` 返回值去重（D-02，留 `c3` / `d`） |
| `SignalSink.onLinkUp() : void` | `SignalSink.onLinkUp(self) -> None` | L1 §3 接口表 `SignalSink`；`i_sinks.py` L40 |
| `ICaptureSink.on_capture_success(workerId, path) : void` | `ICaptureSink.onCaptureSuccess(self, workerId: int, path: str) -> None` | L1 §3 接口表 `ICaptureSink`；`i_sinks.py` L51；`glossary.md` §3.1 / `01_naming_authority.mdc` §3 |
| `ICaptureSink.on_capture_error(workerId, exception) : void` | `ICaptureSink.onCaptureError(self, workerId: int, exception: Exception) -> None` | L1 §3 接口表 `ICaptureSink`；`i_sinks.py` L59 |
| `IRecognitionSink.on_recognition_result(workerId, ack, request_id) : void` | `IRecognitionSink.onRecognitionResult(self, workerId: int, ack: AckFrame, requestId: str) -> None` | L1 §3 接口表 `IRecognitionSink`；`i_sinks.py` L71；`request_id → requestId` 按编码规范 §2 camelCase |
| `IRecognitionSink.on_recognition_error(workerId, exception) : void` | `IRecognitionSink.onRecognitionError(self, workerId: int, exception: Exception) -> None` | L1 §3 接口表 `IRecognitionSink`；`i_sinks.py` L79 |
| 抽象接口层包外的代表性旧名（同一张整合类图）`route_signal` / `send_frame` / `read_frame` / `get_status` / `load_model` / `getInstance` / `_split_frames` | `routeSignal(type)` / `sendFrame` / `readFrame()` / `getStatus()` / `loadModel(path)` / `instance()` / `splitFrames` | L1 §3 + `glossary.md` §3.1 / §3.2 + `01_naming_authority.mdc` §3；属后续阶段落地口径登记，**不构成阶段 a 的实现清单** |
| `SelfChecker.check_all()` / `selfCheck()` / `check_camera()` | 不落地 → 非 L1 门面内空方法占位 + 中文 `TODO`；**`interfaces/` 不新增自检方法 / 类 / 线程** | 裁决 **D-01**；`glossary.md` §3.1 / §3.2（`SelfChecker` / `PendingRequest` 均不落地） |

> 图与 L1 的**签名差异**（属「图只表达语义」的已知冲突，处理口径见 §4.2）：整合类图「抽象接口层」包把 `ILogger` 画成仅 `info` / `error` 两个方法、`IConfig` 画成 `getValue(section, key)` 无 `default`，而 L1 §3 接口表为 `ILogger` 四方法（带 `module` 形参）、`IConfig.get(section, key, default=None)`；一律以 L1 接口表为准，不改图、不改 L1。

## 4. 适用裁决与冲突点

### 4.1 三条裁决逐条复核 + NAMING_AUTHORITY

| 裁决 / 规则 | 影响阶段（`decisions.md`） | 阶段 a 复核结论 |
| --- | --- | --- |
| **D-01 自检留空接口** | `0` / `c4` / `c5` / `d`（阶段 a 适用项：`interfaces/` 不新增自检接口） | **本阶段命中**。`interfaces/` 8 接口与包标记 9 文件经逐文件审读（§2.3）**无自检方法 / 类 / 线程**：不新增自检接口、不建 `self_check*.py` / `checker/`、不占任何线程、不做能力降级；初始化失败仍走 L1 的 Fail-Fast / 记录日志 / 返回失败路径。结论：`interfaces/` 保持零改动，D-01 不被绕过 |
| **D-02 非 UP 不启其他线程** | `c3` / `d` | **本阶段不涉及（逐条登记，留 `c3` / `d`）**。阶段 a 无 `linkState`、无心跳 / 解码 / 重连线程、无 `transitionTo`；`i_socket.py` / `i_thread.py` 只是**接口定义**，不是线程 / 连接实现，不启动任何线程。仅作开工复核留痕 |
| **D-03 去重不做、seq 只填不用** | `c3` / `d` | **本阶段不涉及（逐条登记，留 `c3` / `d`）**。阶段 a 无协议帧组装、无 `EventCache`、无 `seq`、无补发 / 去重逻辑，不引入任何基于序号的比较或过滤。仅作开工复核留痕 |
| **NAMING_AUTHORITY** | 全阶段 | **本阶段命中**。§3 命名裁决表按「L1 §3 接口表 → 编码规范 §2 → camelCase」逐项落地；旧图 snake_case 不作 API；`interfaces/` 现有方法名（§2.3）全部合规，无需改名；L1 契约层受 `01_naming_authority.mdc` §2 保护，不得自动修改 |

### 4.2 图与 L1 的已知冲突点（按 `diagram-index.md` §4 逐条登记，不改图、不改 L1）

| 冲突 | 图中出处（路径以工作区根为基准） | 裁决 / 处理口径 |
| --- | --- | --- |
| 自检 / 能力降级 / 自检线程 | `edge/docs/spec/整体流程/整体流程.txt` 第 1 段、`edge/docs/spec/USB_Camera/USB.txt` 预留节点与旁路自检 | **D-01**：不新增自检类 / 线程 / 接口，`interfaces/` 不新增自检方法；本阶段不落地 |
| 非 UP 阶段出现心跳、解码线程 | 部分 TCP 图与断线分支 | **D-02**（L1 整体流程第 1 段与本裁决一致）；本阶段不涉及，留 `c3` / `d` |
| `PendingRequest` 重发、按 `seq` 去重 | `edge/docs/spec/TCP/断线重连/断线重连.txt` 时序、`EventCache` 补报段 | **D-03**；本阶段不涉及，留 `c3` / `d` |
| 专用 getter、`getInstance`、`getValue` | 配置与日志类图（含本阶段「抽象接口层」包 `IConfig.getValue`） | **L1 §3 接口表 + `glossary.md` §3**：`getValue → get(section, key, default=None)`、`getInstance → instance()`；见 §3 裁决表 |
| 旧版 snake_case 标识符 | 全部图（含本阶段「抽象接口层」包 `on_capture_success` 等） | **NAMING_AUTHORITY**：一律映射为 L1 既有接口或 camelCase；不改图、不改 L1 |
| 「阶段 0~7」编号 | 整体流程三段时序 | 运行期业务时序编号，与 9 个实施阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d` 无关，禁止混用（§1 已声明） |

### 4.3 本步骤口径与「不改文件」声明

- 本摘要**只记录事实与裁决**，不写实现、不写测试、不写 `test-report.md`、不改 `STAGE-STATE.md`、不改 `edge/docs/spec/**`、不改 L1、不改 `references/decisions.md` / handoff / 验收项定义；`a-3` 的「收尾时登记 `decisions.md` 与 handoff」是用户下达的**后续动作**，本摘要不代做（§2.5）。
- `edge/docs/refactor/CONFIG-DIFF.patch` 为历史记录、非权威，未读、未作依据；逐文件资料登记唯一权威为 `edge/docs/spec/INDEX.md`。
- 阶段 0 报告里的 mypy 历史失败、B1 留痕、`0-1`~`0-4` 证据一律**不倒改、不洗绿**；阶段 a 白名单只覆盖 `edge/tests/fakes/*` 条件性修改与 `edge/tests/unit/` 新建补强单测（`STAGE-STATE.md` §1），阶段 0 旧许可不沿用。
- 图中文字未转录进本摘要任何段落；`整合类图.png` 仅取分层语义。

## 5. 待确认项

以下为**口径边界与用户裁决登记，不阻断阶段 a 四步推进**；`a-1`~`a-4` 结论与措辞、B1 处置、`a-3` L1 diff 事实、`patch.object` 命名复核结论均按用户已确认口径执行，不重新征询。第 1 条已由用户 2026-11-10 裁决收口，不再作为待确认项。

1. **`a-4` 白名单边界（用户 2026-11-10 裁决：按 10 处口径收口）**：用户明确「**第 10 处 `lockResult`（`edge/tests/fakes/fake_platform_adapter.py` L15）一并补齐字段级标注，按 10 处口径收口，不再纠结 9/10 差异**」。据此：§2.6 表格 9 处 + 第 10 处 = **10 处全部补齐**，第 10 处落地为 `self.lockResult: BinaryIO | None = lockResult`（构造参数 L13 已带同类标注）；`a-4` 结论「白名单内补齐、不列为未覆盖项」不变，验收项措辞不改。差异已收口，**不再提请确认、不选边**；既有补强单测按用户指令不重写，第 10 处由实现改动、工具链实跑与改动清单举证。
2. **`patch.object(sys, "platform", ...)` 复核中顺带识别的规范适用边界（非命名结论本身）**：`编码规范规则.txt` §4.5「全项目只有 PlatformFactory 允许出现 `sys.platform`」是否把测试侧 `patch.object(sys, "platform", ...)`（阶段 0 已签字验收的 `0-3` 用例）视为受控例外，属「平台分支收敛约束」的解释空间。§2.7 已按用户委托范围只出**命名结论**（不属 NAMING_AUTHORITY 管辖、无命名口径问题、只出结论不改上一阶段任何产物文件），不对此下裁决、不扩大范围；如用户需明确该边界请拍板。
3. **`i_sinks.py` 回调方法计数口径**：`stage-catalog.md` §0 #9 / #25 记「三个 Sink ABC、10 个抽象方法体 / 10 个回调签名」，而 L1 §3 接口表与 `edge/interfaces/i_sinks.py` 源码实际为 **8 个**回调方法（`SignalSink` 4 + `ICaptureSink` 2 + `IRecognitionSink` 2）。§2.4 的 `a-2` 核验按 L1 / 源码的 8 个逐一对齐，结论不受影响；L1 §3 共列 10 个**接口类**分布在 8 个 `i_*.py` 文件，「8 个接口 × 8 个 Fake」按**文件对**。资料中「10」的计数差异如实登记，是否修订 `stage-catalog.md` 措辞由用户决定；本摘要不改 L3、不改验收项定义。

除以上 3 条口径边界外，**无其他需用户拍板事项**：资料齐备、无缺失、无未决阻断矛盾；不自行补全、不选边、不改任何既有产物文件。
