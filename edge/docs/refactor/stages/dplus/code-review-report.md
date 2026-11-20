# dplus 全面代码检视报告（落盘件）

> 整理：袁燕
>
> **本报告不代用户签字，最终 review 结论由用户本人填写**（见文末「最终 review 结论」留白）。
> 本报告只做事实整理与可追溯登记，不下验收结论、不改阶段状态、不产出 handoff。
>
> 数字口径：最终门禁 `pytest edge/tests -q` = 298 passed / 1 warning、`pytest edge/tests/integration -q` = 91 passed / 1 warning、
> `python -m ruff check edge` = `All checks passed!`、`python -m mypy edge` = `Success: no issues found in 95 source files`，
> 由主 Agent 与最终独立审查 Agent 各自实跑；上位机自带 `build/tests/Debug/test_edge.exe` = 36 passed / 0 failed（编译产物仍在盘）。
> 本报告「改前」一列与各组整改结论引自最终独立审查 Agent 的编码卫生对比表；「改后」可复核项均给出文件:行号。

---

## 1. 整改组织方式

本轮整改按 4 组并行 + 主 Agent 补位 + 2 个专项 + 独立审查的方式推进：

| 单位 | 职责范围 | 交付 |
| --- | --- | --- |
| A 组（基础设施） | `infra/**`、`platform/**`、异常与配置装载 | CSV 畸形输入、数值校验、注释 |
| B 组（通信控制） | `modules/tcp/**`、`control/**` | 帧长硬顶、缓冲与队列有界、停机/断链路径 |
| C 组（采集识别） | `modules/usb/**`、`modules/recognition/**` | 保全成果、清理死代码 |
| D 组（装配配置文档测试） | `app_init.py`、`config/**`、`docs/**`、`tests/**` | 类型标注、文档配置对齐、补覆盖用例 |
| 主 Agent | 2 个红灯 | 测试替身契约、子进程编码 |
| E 专项（注释治理） | 全库注释与文件头 | 黑话清理、历史痕迹清理、补文件头 |
| F 专项（`defaultParts` 拆分） | `app_init.py` 装配段 | 拆长函数、提取数据类与函数 |
| 最终独立审查 Agent | 全库复核 | 12 条待收敛项、编码卫生改前改后对比表、质量门禁复跑 |

---

## 2. 各组修掉的真缺陷清单

### A 组（基础设施）

| 缺陷 | 修法 | 可复核位置 |
| --- | --- | --- |
| CSV 畸形输入（编码异常、解析出错、字段含控制字符）被当成普通空值吞掉 | 统一转成 `EdgeError(CONFIG)`，启动即判错 | `edge/infra/roi_binding_loader.py:172-182`（控制字符检查 + `except (csv.Error, UnicodeError, OSError)` 转业务异常） |
| 数值范围只比上下界，NaN / inf 会因「与任何数比较都为假」被放进识别判定 | 先 `math.isfinite` 再比上下界 | `edge/infra/roi_binding_loader.py:276-287`（`parseConfidence`）、`edge/infra/config_manager.py`（配置文本类型推断）；裁决见 `references/decisions.md` D-19 |
| 注释缺信息量 / 有历史痕迹 | 改为白话说明 | 组内文件注释 |

### B 组（通信控制）

| 缺陷 | 修法 | 可复核位置 |
| --- | --- | --- |
| 帧长阈值只由构造注入值参与计算，注入值配错可把保护打穿 | 再钳一个与对端协议对齐的绝对硬顶：上位机单帧上限 1 MB 的一半 = **524288** | `edge/modules/tcp/tcp_comm.py:35-37`（`HOST_FRAME_MAX_BYTES = 1024*1024`、`HOST_SAFE_FRAME_LIMIT_BYTES = //2`）；裁决 D-17 |
| 收包半包缓冲（对端一直不换行）无上限、内存无界 | 设累计上限，超限判链路异常并断链收敛 | `edge/modules/tcp/tcp_comm.py:43`（`MAX_RECV_BUFFER_BYTES`）、`edge/modules/tcp/tcp_decode_thread.py`（缓冲超限上报） |
| 待发应答队列（链路长期断开）无上限 | 条数上限 1024，超限丢最旧并记一条日志 | `edge/control/edge_control.py:43,664-670`（`MAX_OUTBOX_FRAMES` 与丢弃日志） |
| 停机时被关闭的 socket 触发「异常 → 重连」，停机路径反向拉起线程 | 停机先 `transitionTo(DOWN, "stop", "STOP")` 且不走 `onLinkDown`；解码线程以 `isRunning()` 收敛 | `edge/modules/tcp/tcp_control_layer.py`（`stop()` / `onLinkDown`）、`tcp_decode_thread.py` 三处收敛；裁决 D-18 |
| 真断链不转发上游，控制层要等一个排空周期才把应答改入事件缓存 | 真断链（非停机）转发 `upstreamSink.onLinkDown` | 同上；裁决 D-18 |

### C 组（采集识别）

| 缺陷 | 修法 | 说明 |
| --- | --- | --- |
| 8 个文件已有成果可能被整改误伤 | 保全 8 文件成果，只做必要修正 | 采集识别链路（相机状态判定、丢帧可观测性等）保持第三轮修复结论 |
| 死代码残留 | 以「五道闸」逐条判定后清理 | 引用审查、调用链、类型、测试覆盖、协议字段五道判定，确认无引用才清理 |

### D 组（装配配置文档测试）

| 缺陷 | 修法 | 可复核位置 |
| --- | --- | --- |
| 6 处 `cast` 掩盖真实类型（配置读进来是 `list[str]` 却当 `dict` 用） | 去掉类型掩盖，改为真实读取与判错 | `edge/app_init.py` 装配段、`edge/infra/roi_binding_loader.py`；当前生产代码 `cast(` 读盘命中 0 |
| 文档与正式配置不一致 | 对齐 `config.ini`、`roi_binding.csv`、`config/README.md` 与文档 | `edge/tests/unit/test_dplus_config_doc_parity.py`（3 处 `parametrize`） |
| 新增安全阈值 / 装配约束缺覆盖 | 补覆盖用例 | `edge/tests/unit/test_dplus_assembly_guards.py`（7 处 `parametrize`）、契约与集成用例 |

### E 专项（注释治理）

- 黑话 **72 → 9**：把未解释的内部简称替换成白话（剩余 9 处中的 3 处在**生产运行时文案**，见第 6 节，本轮不动）。
- 历史痕迹 **1 → 0**：清掉「上一版 / 历史」等旧过程措辞。
- 补 **24** 个文件头（`## @file` / `## @brief` / `## @author`）。本轮 G 组另按开工清单补了 5 个非 L1 文件头（见第 7 节）。

### F 专项（拆 `defaultParts`）

- `defaultParts` 由 **121 行 → 10 行**：`edge/app_init.py:1430-1442` 现在只做「摘搜索路径 → 解析配置 → 读布局 → 建基础设施 → 备识别输入 → 收口构造」六步委派。
- 提出 **3 个数据类**（`CaptureLayout` / `Infrastructure` / `RecognitionInputs`，`app_init.py:1195-1226` 起）+ **4 个函数**（`readCaptureLayout` / `buildInfrastructure` / `buildRecognitionInputs` / `assembleParts`）。
- **签名与 42 字段未变**：`assembleParts` 仍是 `AssemblyParts` 的 42 个显式赋值（`app_init.py:1377-1427`），`dispatchIntervalSec` 走数据类默认值，合计 43 个字段（`app_init.py:265-354`）。

---

## 3. 两个红灯的根因与修法

| 红灯 | 根因 | 修法 |
| --- | --- | --- |
| 相机状态用例失败 | 测试替身把「是否成功打开过」写成 `everOpened = opened or closed`，「关闭过但从未打开成功」也被算成打开过，与真实设备契约不一致 | **修替身，不动断言**：替身的 `everOpened` 只在 `open()` 成功时置 True（`edge/tests/integration/test_business_closure.py:124-134`）；真实设备同样口径（`edge/modules/usb/usb_camera_device.py:127-128,149-150`），门面按 `everOpened` 判离线（`usb_controller.py:427-429`）。裁决 D-15 |
| 子进程中文提示乱码导致用例失败 | 拉起子进程时没有指定 IO 编码，Windows 默认代码页把 UTF-8 中文提示打乱 | 给子进程设 `PYTHONIOENCODING=utf-8`，父进程同编码读取（`edge/tests/integration/test_dplus_real_process_lock.py:46-47`） |

两条都属于「替身 / 测试环境与真实契约不一致」，**没有改既有断言、没有改预期值、没有删用例**。

---

## 4. 质量门禁证据

| 门禁 | 真实输出 | 来源 |
| --- | --- | --- |
| `python -m ruff check edge` | `All checks passed!` | 主 Agent 与最终独立审查 Agent 各自实跑 |
| `python -m mypy edge`（3.9 strict） | `Success: no issues found in 95 source files` | 同上 |
| `python -m pytest edge/tests -q` | `298 passed / 1 warning` | 同上 |
| `python -m pytest edge/tests/integration -q` | `91 passed / 1 warning` | 同上 |
| 上位机自带 `build/tests/Debug/test_edge.exe` | `Totals: 36 passed, 0 failed, 0 skipped, 0 blacklisted, 9947ms` | 编译产物仍在盘（本轮读盘确认） |
| 实跑启动 | 进程存活；周期帧连续三帧间隔 ≈ **3.01 秒**；日志 `RX 1 / TX 65` | `logs/ALL_20261115_0001.log`：共 140 行，RX 1 行、TX 65 行；`periodic` 时间戳 01:41:52.112256 → 01:41:55.118473 → 01:41:58.119399 |

环境：Python 3.9.7、`pytest 6.2.4`、ruff 0.17.5、mypy 1.19.1。`pytest 6.2.4` 低于 `edge/pyproject.toml:12` 声明的 `pytest>=7.4,<9`，`pythonpath` 配置项不被识别，故两次门禁各带 1 条 `PytestConfigWarning`；仓库根已在 `sys.path`，不影响用例收集。该项登记为「环境对齐遗留项，需用户批准后升级或改 L1」（见 `test-report.md` ④）。

---

## 5. 编码卫生改前 → 改后对比

引自最终独立审查 Agent 的编码卫生对比表；「改后」列经本轮读盘复核（生产 `.py`，不含 `tests/` 与 `docs/` 脚本，共 47 个文件）：

| 项 | 改前 | 改后 | 本轮复核 |
| --- | --- | --- | --- |
| 生产代码 `print` | 11 | 0 | 读盘命中 0 |
| 生产代码 `time.sleep` | 7 | 0 | 读盘命中 0 |
| 生产代码 `cast(` | 6 | 0 | 读盘命中 0 |
| 裸 `except:` | 0 | 0（恒 0） | 读盘命中 0 |
| `TODO` | — | 15（合理保留） | 本轮按「生产 `.py`」口径读盘命中 12；与审查表 15 的差额来自统计范围（审查表口径含测试目录 / 文档脚本）。均为上板前待办，属合理保留，未清理 |

---

## 6. 残留风险与遗留项（12 条中未在本轮收敛的，逐条归属阶段）

| 项 | 为什么本轮不动 | 归属阶段 |
| --- | --- | --- |
| `@file` 头两种位置并存 | 统一位置要动 13 个 L1 文件（`interfaces/**`、`exceptions.py`、`tests/contract/**`），本轮铁律禁止改 L1；本轮只补了 5 个非 L1 | 后续注释治理（统一口径需用户批准；L1 部分须 diff + 批准） |
| 生产运行时文案含 3 处黑话 | 改运行时输出文案属改业务 `.py` 逻辑，本轮禁止 | 后续文案治理（需用户批准） |
| 验收项编号注释覆盖 110/298 | 批量补注释要动既有测试，属 `test-writer` 职责 | 后续测试注释治理（需开工清单） |
| `close_ack` 无生产构造点 | 该帧由 IO 板一侧产生，边缘机不回；当前只在协议常量 / Fake / 用例中出现 | 上板（IO 板侧协议实现） |
| L1 目录 2 个新增接口文件待用户追认 | `i_camera_focus.py` / `i_frame_sink.py` 属 L1 契约层，禁止自动改 | 用户追认（L1 契约变更：diff + 批准） |
| 上位机 GUI 业务闭环 | 需 GUI 自动化驱动「登录 → 建单 → 开柜 → 关柜」，本阶段无该设施 | 后续专项（上位机 GUI 自动化） |
| 真机对焦标定 | 无真机可标 `focus_mode` / `focus_position` | 上板 |
| ROI 四角点上板重标 | 换真相机后全景尺寸变化，样例坐标需重标 | 上板 |
| onnx 后端等价性标定 | 两条后端逐框一致性未标定，默认固定 `ultralytics` | 上板 / 现场标定 |
| 相机状态取值 | 2026-11-20 收口为 `ok` / `offline` 两态：取图失败归并到 `offline`，照度与脏污本期不设取值 | 已收口（两态）；将来新增状态须走契约 diff + 批准 |
| 附：pytest 环境对齐遗留项（④ 已登记，非 12 条内） | 6.2.4 与声明区间偏差，升级或改 L1 均需批准 | 用户批准后升级 pytest 或改 L1 声明 |

上表「12 条中未收敛」共 10 项（`@file` 头位置 / 运行时文案黑话 / 验收项编号注释 / `close_ack` / L1 两接口 / GUI 闭环 / 对焦标定 / ROI 重标 / onnx 标定 / 相机状态取值——该项已于 2026-11-20 收口为两态），均逐条注明归属阶段；pytest 版本偏差为 ④ 环境段另登记的遗留项。另有浏览器内布局自检未实跑（需 playwright + msedge 通道），归属「后续具备环境时」，见 `test-report.md` ⑥「本轮遗留 6」。

---

## 7. 本轮（G 组收口）4 项交付对照

| 交付 | 内容 | 收敛了 12 条里的哪部分 |
| --- | --- | --- |
| 1 | 更新 `test-report.md`：162 → 298 / 补 integration 91；ruff/mypy「未复跑」→ 真实实跑输出；`parametrize` 零命中 → 10 处；`tcp_socket.py` 尚不存在 → 已落地；④ 补版本偏差与环境对齐遗留项；⑥ 逐条列明未收敛项归属 | 陈旧数字与不实陈述、版本偏差登记 |
| 2 | 补 5 个非 L1 文件头（`platform/__init__.py`、`platform/adapter.py`、`platform/file_lock.py`、`__init__.py`、`verify_diagram_screenshot.py`），纯注释、零逻辑改动 | 18 个缺 `## @file` 中的非 L1 部分（13 个 L1 不动） |
| 3 | `test_camera_mapping_chain.py` 的 `assert rows` 改成 3 条具体值/长度断言（行数 = 4、`workerId` 序列、`position` 序列），比原来更强 | 空洞断言 |
| 4 | 本报告落盘 | 「检视报告缺落盘件」 |

### 7.1 交付 3 空洞断言：改前 → 改后全文与理由

文件 `edge/tests/integration/test_camera_mapping_chain.py`，函数 `testEveryPositionHasExactlyOneOwningWorker()`。

**改前**（`assert rows` 只判「非空」，不校验任何业务语义，违反 `test-visibility.mdc §3.2`）：

```python
    assert len(pairs) == WORKER_COUNT
    assert rows
    assert all(1 <= row.workerId <= WORKER_COUNT for row in rows)
```

**改后**（3 条具体值 / 长度断言，逐项核 `workerId` 与物理货位编号对应；后面既有的 `assert all(...)` 原样保留）：

```python
    assert len(pairs) == WORKER_COUNT
    assert len(rows) == WORKER_COUNT, (
        f"对照表应有 {WORKER_COUNT} 行货位，与 4 组采集线程一一对应，实际 {len(rows)} 行"
    )
    assert [row.workerId for row in rows] == list(range(1, WORKER_COUNT + 1)), (
        "对照表各行应依次归属第 1~4 组采集线程"
    )
    assert [row.position for row in rows] == [
        "A-01-01", "A-01-02", "A-01-03", "A-01-04",
    ], "货位编号应与相机映射链的物理顺序一致"
    assert all(1 <= row.workerId <= WORKER_COUNT for row in rows)
```

**理由**：`assert rows` 只要列表非空就通过，哪怕只有 1 行、货位错乱、线程编号重复也不会失败。改后把「8 路相机 → 4 组采集线程 → 4 个货位」这条映射链落成 3 条可核对的具体值断言（行数 = 4、`workerId = [1,2,3,4]`、`position = [A-01-01 … A-01-04]`），只增不减、比原来更强。期望值来自正式对照表 `edge/config/roi_binding.csv` 的 4 行（`worker_id` 1~4、`position` A-01-01~04），不是凭空写死。这是**修正空洞断言**，被测代码零改动、其它既有断言零改动、无「为变绿而改被测代码」。定向实跑 `python -m pytest edge/tests/integration/test_camera_mapping_chain.py -q` = `5 passed, 1 warning`（warning 为 `pythonpath` 版本偏差）。

本轮**未改** L1 契约层、未改任何业务 `.py` 逻辑、未改既有测试断言（交付 3 除外，且为加强）、未改 `config/**` / `README.md` / `STAGE-STATE.md` / `handoff.md`。

---

## 最终 review 结论（留白，由用户本人填写）

> 本报告只整理事实与可追溯证据，**不代用户签字**。最终 review 结论、是否推进阶段状态、是否批准上文各遗留项的处置路径，均由用户本人填写。
