# 阶段 0 资料消化摘要（spec-digest）

> 产出：`/stage 0` 步骤 1，由 `spec-reader` 生成；**本文件是本步骤唯一写入物**。
> 阶段 0 为首个实施阶段，**无上一阶段 handoff**；`references/lessons.md` §3 当前为空库，无可复用经验输入。
> 全部路径以工作区根为基准（CODEBUDDY.md §0），spec 资料统一写 `edge/docs/spec/...`。
> 本摘要只表达语义与裁决：不写实现、不写测试、不写 `test-report.md`、不改 `STAGE-STATE.md`、不改验收项定义、不改状态。
> PNG 只取语义，不转录图中文字；旧图标识符只作裁决输入，不当作 API。

## 1. 本阶段资料清单

筛取口径：`edge/docs/spec/INDEX.md` §2「逐文件登记」中「对应阶段」含 `0` 的条目，叠加 `references/diagram-index.md` §2 阶段 `0` 行的「先读 / 再看」。下表路径统一为 `edge/docs/spec/...`，图类型取自 `INDEX.md` 登记值；「取用范围」只写语义，不转录图中文字。

| 路径 | 图类型 | 本阶段取用范围 / 语义 |
| --- | --- | --- |
| `edge/docs/spec/整体重构方案.txt` | 定稿文本（L1 契约层，只读） | §1 决策一览、§2 目录结构、§3 接口方法表与逐文件职责、§5 阶段 0 验收；本阶段命名与接口的唯一裁决源 |
| `edge/docs/spec/编码规范规则.txt` | 定稿文本（L1 契约层，只读） | §2 命名、§3 注释、§4.4 异常与日志、§4.5 单例与进程约束、§8 模块边界；审读 4 个骨架的核验基线 |
| `edge/docs/spec/整体流程/整体流程.txt` | 时序图（mermaid 源码，3 段） | **仅第 1 段（启动与首连）**；取启动流程的裁决结论，见 §2.1 / §4 |
| `edge/docs/spec/整体流程/整合类图代码.txt` | 整合类图（PlantUML 源码） | 全系统分层与正交连线的结构语义；标识符为旧版 snake_case，仅作命名裁决输入 |
| `edge/docs/spec/整体流程/整合类图.png` | 整合类图（位图渲染） | 上条源码的位图；仅作模块分层与依赖连线语义参考，不转录文字 |
| `edge/docs/spec/整体流程/阶段0-3.png` | 阶段时序 | 启动、配置日志、模块初始化、退避首连、UP 后启心跳与解码的运行期分段语义；其中「阶段 0~3」为业务时序编号 |
| `edge/docs/spec/INDEX.md` | L3 索引资产（非图资产） | 逐文件登记的唯一权威，用于筛取本阶段资料与图类型 |

**未列入本阶段**：`阶段4-5.png`、`阶段5-7.png`（对应阶段 c3/c4/c5/d），以及配置文件接口 / 日志 / TCP / USB_Camera / 识别各目录（对应阶段 c1~c5），按 `INDEX.md`「对应阶段」不含 `0`，留待各自阶段消化。

**辅助资料（L3 流程配置，非 `edge/docs/spec/**` 图资产，故不登记图类型）**：
- `.codebuddy/skills/edge-refactor/references/decisions.md`（D-01 / D-02 / D-03 裁决全文）
- `.codebuddy/skills/edge-refactor/references/glossary.md`（术语与旧图 → L1 标识符映射）
- `.codebuddy/skills/edge-refactor/references/diagram-index.md`（§2 阶段检索、§4 已知冲突点）
- `.codebuddy/skills/edge-refactor/references/stage-catalog.md`（§0 27 文件判定、§2 阶段 0 验收项 `0-1`~`0-4`）
- `.codebuddy/skills/edge-refactor/references/lessons.md`（§3 空库，已核实）
- `CODEBUDDY.md` §0/§2（路径基准与权威优先级）

> 「图中阶段 0~7」是运行期业务时序编号，与 9 个实施阶段 `0 / a / b / c1 / c2 / c3 / c4 / c5 / d` 不是同一套编号，**禁止混用**（INDEX.md 文件头、glossary.md §1、diagram-index.md §4 三处一致）。

## 2. 关键语义

### 2.1 运行期行为、状态与异常路径

阶段 0 的落地范围是异常契约与平台/进程锁骨架（`edge/exceptions.py` + `edge/platform/`）。运行期职责：进程启动的第一件事是取得单文件锁以阻止双开与端口占用；平台适配由唯一工厂按运行平台选择——Windows 返回完整实现（非阻塞文件锁、换行符、信号映射、单调时钟），Linux 返回留待上板的骨架实现；锁句柄由锁对象持有至显式释放。状态：锁对象只有「未持锁 / 持锁」两态（句柄是否为 `None`），平台适配器自身无状态机；全项目业务异常收敛为 `ErrorCode` 五码与唯一 `EdgeError`，日志侧用 `code.name` 输出异常码。异常路径：锁文件已被占用 → 适配器返回 `None` → `acquire()` 抛 `EdgeError(CONFIG)`；Linux 骨架抛出的 `NotImplementedError` 在跨模块边界前转为 `EdgeError(CONFIG)`；`acquireOrExit()` 捕获业务异常后立即 `sys.exit`；不受支持的平台由工厂直接抛 `EdgeError(CONFIG)`；`release()` 重复调用安全。「启动不引入自检、不做能力降级」按裁决 D-01 执行（§4）。`整体流程.txt` 第 1 段描述的是横跨多个实施阶段的运行期业务时序总览（启动装配、首连、周期上报、指令解析），本阶段只取其启动流程的裁决结论，其余语义不落地；`main.py` / `app_init.py` 属阶段 d、尚未建立，故「进程锁无调用方」是阶段 d 的既有缺口，不是阶段 0 的「需修正」项，按 `stage-catalog.md` `0-4` 口径写入未覆盖项及原因（由 `test-report.md` 处理，本摘要不改验收项定义）。

### 2.2 阶段 0 逐文件审读结论与契约核验表（验收项 `0-1` 举证材料）

已逐个打开源码原件核实（非转述 `stage-catalog.md` §0 判定），行号指各文件当前内容。`edge/exceptions.py` 属 L1 契约层，**只读审读、绝对禁改**；`platform/` 三个文件属条件性白名单，仅当明确判「需修正 + 依据」时 `implementer` 才做最小修正。

| 文件 | 结论 | 可复核依据（行号 / 关键事实） | 契约核验对照 |
| --- | --- | --- | --- |
| `edge/exceptions.py` | **新骨架·达标，无需修正**（L1 契约层，只读禁改） | L1 唯一 `"""模块说明"""`、L2 `from __future__ import annotations`；L8 `ErrorCode(IntEnum)`，L10~18 恰五码 `CONFIG / LINK_DOWN / FRAME_PARSE / INFERENCE_TIMEOUT / CAPTURE`；L22 唯一 `class EdgeError(Exception)`；L26~29 `__init__(code, message)` 内 `super().__init__(f"[{code.name}] {message}")` 且 `self.code: ErrorCode`；全文无逻辑分支、无业务 import、无旧式泛型 | L1 §3「ErrorCode(IntEnum) + EdgeError 一个类，无逻辑；新增异常只加枚举值，不改类结构」；L1 §5「EdgeError 抛 / 捕 / 日志格式正确」；编码规范 §4.4「异常码用 `code.name`」 |
| `edge/platform/__init__.py` | **新骨架·达标，无需修正** | 全文仅 L1 包 docstring + L2 `from __future__ import annotations`，无任何实现、无 `sys.platform` 分支泄漏、无 import 业务模块 | L1 §2 目录结构列有 `platform/__init__.py`；编码规范 §4.5「平台差异全部收敛到 IPlatformAdapter」；§8「零实现、零 import 业务模块」边界 |
| `edge/platform/adapter.py` | **新骨架·达标，无需修正** | L15 `WindowsAdapter(IPlatformAdapter)`：L19 `joinPath` / L24 `newline` / L29 `signalMap`（返回 `i_platform.py` L8 定义的 `SignalMapping`）/ L36 `monotonicClock` / L42 `lockFile`，L43+L52 `msvcrt.locking` 非阻塞锁，L53~55 占用返回 `None`；L60 `LinuxAdapter`：L86~88 `lockFile` 抛 `NotImplementedError` 且 L87 有 `fcntl.flock` 上板 TODO；L92 `PlatformFactory`，L97 `create()`，L99 / L102 / L104 为全文（亦为全项目）唯一 `sys.platform` 出现处，L100 `win32 → WindowsAdapter`、L103 `linux → LinuxAdapter`、L104 其余平台 `EdgeError(CONFIG)`；全 camelCase + Doxygen 注释 | L1 §3「WindowsAdapter / LinuxAdapter（骨架 NotImplementedError + TODO）/ PlatformFactory；全项目唯一出现 sys.platform 的地方」；L1 §5「Windows 返回 WindowsAdapter，Linux 分支 NotImplementedError」；编码规范 §4.5「全项目只有 PlatformFactory 允许出现 sys.platform」；`stage-catalog.md` `0-3` 与 `test_phase0_foundation.py` L32~44 已按「LinuxAdapter.lockFile 抛内置异常 + acquire 转 EdgeError」两层分别举证 |
| `edge/platform/file_lock.py` | **新骨架·达标，无需修正** | L11 `DEFAULT_LOCK_FILE_NAME`（UPPER_SNAKE_CASE 常量）；L15 `ProcessFileLock`，L19 构造注入 `adapter` + `lockFilePath`；L30~38 `acquire()`：L33~35 捕获 `NotImplementedError` 转 `EdgeError(CONFIG)`、`from error` 保留因果，L36~37 句柄为 `None` 时抛 `EdgeError(CONFIG)`，L38 持有句柄；L42~46 `acquireOrExit()` 内 L46 `sys.exit`（供 main 第一件事调用）；L50~53 `release()` 幂等 | L1 §3「进程单文件锁；Windows msvcrt.locking，Linux fcntl.flock 骨架；拿不到锁 → 抛 EdgeError(CONFIG) → main.py 退出」；L1 §5「双开拿锁失败」；编码规范 §4.4「内置异常（含 NotImplementedError）不得穿越模块边界，跨边界前转 EdgeError」、§4.5「main.py 第一件事获取进程单文件锁」 |

**汇总结论（供 `implementer` 直接采信）**：以上 4 个文件**全部判为「新骨架·达标、无需修正」**，与 `stage-catalog.md` §0 判定（#1、#12~#14）一致且经源码原件复核。因此**条件性白名单不触发**：`implementer` 在阶段 0 **不得改动** `edge/exceptions.py` 与 `edge/platform/` 三个文件。阶段 0 唯一授权的实现侧改动是 §2.3 的 `fake_logger.py` 一次性最小修复（B1），不涉及上述 4 个文件。

### 2.3 B1 契约口径说明（Fake 侧类型对齐，**不是 API 变更**）

- **已核实事实**：`edge/tests/fakes/fake_logger.py` L4 为 `from edge.interfaces.i_logger import FrameData, ILogger`，且 L12 / L14 用 `FrameData` 标注记录列表、L24 / L31 用 `FrameData` 标注 `rx` / `tx` 的 `data` 参数；而 `edge/interfaces/i_logger.py` 全文（L1~L41）**未定义 `FrameData`**，其 `rx`（L14）与 `tx`（L22）的落地参数类型均为 `dict[str, object] | bytes`。即 `FrameData` 全库不存在，该导入必然 ImportError。
- **定性**：这是 **Fake 侧类型对齐**的依据——把 Fake 的导入与标注对齐到 `ILogger` 既有签名，**不是 API 变更**。`edge/interfaces/i_logger.py` 属 L1 契约层，**严禁往其中新增 `FrameData`，严禁改接口签名**；L1 §3 接口表 `ILogger` 恰 `rx / tx / info / error(method, msg, exception=None)` 四方法，不因此扩充。
- **连带影响**：`edge/tests/contract/test_interface_contracts.py` L16 `from edge.tests.fakes.fake_logger import FakeLogger` 使契约测试在**收集期**即失败；`stage-catalog.md` §0 #18 备注亦登记该连带阻断。这直接阻断阶段 0 的补测举证，故需提前解除。
- **归属与授权**：该项原属阶段 a 的 `a-2`（Fake 与接口签名对齐）/ `a-3`（契约测试可收集、可执行、通过）；因上述收集期 ImportError 阻断阶段 0 补测，**经用户授权提前到阶段 0 做一次性最小修复**（范围仅限 `edge/tests/fakes/fake_logger.py`：去掉不存在的 `FrameData` 导入、把 `rxRecords` / `txRecords` 与 `rx` / `tx` 参数类型对齐到 `dict[str, object] | bytes`）。须在 `stages/0/test-report.md` **第 ⑥ 节留痕**（本摘要不写该文件）。
- **口径澄清**：L1 §3 `tcp_heart_thread.py` 中的 `buildFrameData()` 是组帧**方法名**，不构成 `FrameData` **类型**的定义依据；两者不可混同，`i_logger.py` 中从未存在该类型。

### 2.4 补强单测落点（用户已拍板口径，非待确认）

补强单测（A5）落点定为 `edge/tests/unit/`，**新建文件、不改任何既有断言，后续阶段同理**。现有 `edge/tests/contract/test_phase0_foundation.py`（5 个 `testXxx`）与 `test_interface_contracts.py` 的既有断言一律保持原样；阶段 0 的可举证单测以新增文件形式落在 `edge/tests/unit/`。

## 3. 命名裁决表

依据本阶段资料（整合类图为全系统结构、整体流程第 1 段为启动时序）中出现的旧图标识符，逐项给出 L1 落地口径。裁决顺序按 NAMING_AUTHORITY：L1 §3 接口方法表 → 编码规范 §2 命名规则 → 其余按 camelCase 转换；旧图标识符不具裁决权。**本阶段实际落地的仅 `exceptions.py` / `platform/`（无对外方法名争议），下表其余行是对后续阶段的命名口径登记，不构成阶段 0 的实现清单**。「L1 落地标识符」列均给出明确落地口径，无留空、无照抄图名。

| 图上标识符 | L1 落地标识符 | 依据 |
| --- | --- | --- |
| `getValue(section, key)` | `get(section, key, default=None) -> Any` | L1 §3 接口表 `IConfig`；`glossary.md` §3.1；专用 getter 一律收敛为通用 `get` |
| `getInstance()`（配置 / 日志 / 引擎单例） | `instance()`（各类内类变量 + 双检锁） | L1 §1「删除 BaseSingleton；各自类内写 `instance()`」；编码规范 §4.5；`glossary.md` §3.1 |
| `route_signal(signal)` | `routeSignal(type)` | L1 §3 `control/edge_control.py`「按注入的 `asyncHandlers` 字典分发」；NAMING_AUTHORITY camelCase |
| `send_frame(frame)` | `sendFrame` | L1 §3 `tcp_control_layer.py`「`sendFrame` 加锁发送」；`glossary.md` §3.1 |
| `set_signal_sink(sink)` | 不落地 → 构造注入 `SignalSink`，状态变更统一走 `transitionTo(state, reason, source) -> bool` | L1 §3「注入的 SignalSink」「原子状态机」；`glossary.md` §3.1「sink 注入不设 setter」 |
| `on_capture_success` / `on_capture_error` | `onCaptureSuccess(workerId, path)` / `onCaptureError(workerId, exception)` | L1 §3 接口表 `ICaptureSink`；`glossary.md` §3.1 |
| `on_recognition_result` / `on_recognition_error` | `onRecognitionResult(workerId, ack, requestId)` / `onRecognitionError(workerId, exception)` | L1 §3 接口表 `IRecognitionSink`；`glossary.md` §3.1 |
| `on_worker_success` / `on_worker_error` / `on_worker_result` | 门面内 `onWorkerSuccess` / `onWorkerError` / `onWorkerResult` | 非 L1 接口，按 camelCase 转换；须满足「方法名全局不重复」（编码规范 §2）；`glossary.md` §3.1 |
| `_split_frames` / `_decode_and_parse` / `_report_signal` / `_report_error` | `splitFrames` / `decodeAndParse` / `reportSignal` / `reportError` | L1 §3 `tcp_decode_thread.py`「半包 / 粘包 `splitFrames`」；编码规范 §2「私有方法同样 camelCase」；`glossary.md` §3.1 |
| `read_frame()` / `get_status()` | `readFrame()` / `getStatus()` | L1 §3 接口表 `ICameraDevice`；`glossary.md` §3.1 |
| `load_model()` | `loadModel(path)` | L1 §3 接口表 `IRecognitionEngine`；`glossary.md` §3.1 |
| `_crop_and_merge` / `draw_roi` 等纯函数 | `cropAndMerge` / `drawRoi`（留在 `recognition_utils.py`） | L1 §3 `recognition_utils.py` 纯函数候选；`glossary.md` §3.1 / §3.2 |
| `SelfChecker.check_all()` / `selfCheck()` / `check_camera()` | 不落地 → 门面内空方法占位 `selfCheck()` + 中文 `TODO`；`interfaces/` 不新增自检方法 | 裁决 **D-01**；`glossary.md` §3.1 / §3.2（`SelfChecker` / `PendingRequest` 均不落地） |

## 4. 适用裁决与冲突点

### 4.1 三条裁决逐条登记复核

| 裁决 | 影响阶段（`decisions.md`） | 阶段 0 复核结论 |
| --- | --- | --- |
| **D-01 自检留空接口** | `0`（启动流程）、`c4`、`c5`、`d` | **本阶段命中**。启动流程不引入自检；自检只留空方法 + `TODO`，不做能力降级分支；`interfaces/` 不新增自检方法。阶段 0 交付物（`exceptions.py` + `platform/`）本身不含自检逻辑，无需新增类 / 线程 / 接口，也不占用任何线程；`interfaces/` 属阶段 a，本阶段不改动。结论：不触发自检相关实现，`SelfChecker.check_all()` 与能力降级均不落地 |
| **D-02 非 UP 不启其他线程** | `c3`、`d` | **本阶段不涉及**（逐条登记）。阶段 0 无 `linkState`、无心跳 / 解码 / 重连线程、无 `transitionTo`，亦不 `import` 线程或 socket；本阶段不新增任何线程。仅作开工复核留痕，落地留待 c3 / d |
| **D-03 去重不做、seq 只填不用** | `c3`（协议帧组装）、`d`（`EventCache` / `EdgeControl`） | **本阶段不涉及**（逐条登记）。阶段 0 无协议帧组装、无 `EventCache`、无 `seq`、无补发/去重逻辑；本阶段不引入任何基于序号的比较或过滤。仅作开工复核留痕，落地留待 c3 / d |

### 4.2 已知冲突点与处理口径

| 冲突点 | 图中 / 资料出处 | 处理口径 |
| --- | --- | --- |
| 启动自检与能力降级 | `edge/docs/spec/整体流程/整体流程.txt` 第 1 段的 `SelfChecker.check_all()` 与「部分失败 → 能力降级」分支 | **D-01 不落地**：不新增自检类 / 线程 / 接口，不建 `self_check*.py` / `checker/`，不以自检结果控制模块启停；初始化失败仍走 L1 的 Fail-Fast / 记录日志 / 返回失败路径，不引入能力降级状态机 |
| 旧图 snake_case、专用 `getter` / `getInstance` / `getValue` | `edge/docs/spec/整体流程/整合类图代码.txt`、`edge/docs/spec/整体流程/整体流程.txt` 第 1 段、配置与日志类图 | **NAMING_AUTHORITY / L1 §3 接口表**：一律映射为 camelCase 或 L1 既有接口（见 §3）；不改图、不改 L1；`getInstance → instance()`、`getValue → get(section, key, default=None)`，专用 getter 收敛为通用 `get` |
| 图与 L1 的阶段编号体系 | 整体流程三段时序的「阶段 0~7」 | 图中「阶段 0~7」是**运行期业务时序编号**，与 9 个实施阶段 `0~d` **无关，禁止混用**；本摘要所称「阶段 0」一律指实施阶段 0 |

### 4.3 资料差异口径（用户已拍板，不列为待确认）

- **L1 内部小标题与 §5 冲突**：`edge/docs/spec/整体重构方案.txt` §3 中 `platform/` 小标题误写「阶段 b」，与 §5「阶段 0 → `exceptions.py` + `platform/file_lock.py` + `platform/adapter.py` 骨架」不一致。**按 §5 阶段 0 口径**，`platform/` 归阶段 0；`interfaces/（阶段 a）`、`base/（阶段 b）` 小标题不受影响。本摘要 §2.2 的审读范围即据此确定。
- **`stage-catalog.md` §0 编号笔误**：#18 备注「import `FakeLogger` 会被 #21 连带阻断」中的「#21」（`fake_config.py`）实为 **#22 `fake_logger.py`**。**按「阶段 0 / #22」口径**理解 B1 断裂点（见 §2.3）；#21 本身无断裂。
- **补强单测落点**：见 §2.4（用户已拍板），同属已定口径，不重新征询。

## 5. 待确认项

**无。**

（已识别的两处资料差异与 B1 提前修复、单测落点均按用户已拍板口径写入 §4.3 / §2.3 / §2.4，不在此重复列为待拍板项；资料齐备、无缺失、无未决矛盾，不自行补全、不选边。）
