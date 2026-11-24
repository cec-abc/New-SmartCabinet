# 实现契约（主文档）— 识别流重构 + USB 对焦 + 8 路 2 合 1

> 阶段族：`c4plus` / `c5plus` / `dplus`（用户 2026-11-14 明确解除配置期禁令，批准新增这三个阶段）。
> 本文件是三阶段共用的**签名契约与事实基线**，各阶段 spec-digest 的"全局契约"节一律以本文件为准。
> 权威事实来源：上位机代码 `d:\CFDZ\smartCabinet\trunk\SmartCabinetLite`（下称"上位机"）+ `edge/docs/spec/整体重构方案.txt`（L1）+ `dual_crop_stitch/`（原平铺实现，语义参考）。

## 0. 阶段划分与文件白名单

| 阶段 | 白名单目录/文件 | 交付 |
| --- | --- | --- |
| `c4plus` | `modules/usb/**`、`interfaces/i_camera_focus.py`、`interfaces/i_frame_sink.py`、`tests/fakes/fake_camera_focus.py`、`tests/fakes/fake_frame_sink.py` | 循环化流式采集、对焦能力、帧回调契约 |
| `c5plus` | `modules/recognition/**`、`infra/roi_binding_loader.py`、`config/roi_binding.csv` | CSV 对照表装载、ROI 裁剪拼接、流式识别、幂等应答 |
| `dplus` | `control/**`、`app_init.py`、`main.py`、`config/config.ini`、`tests/integration/**`、`tests/contract/**`、`tests/unit/test_stage_a_contract_alignment.py` | 4 个生产断点修复、应答排空、正式配置、端到端联调 |

**白名单外任何文件一律不得改。** 跨阶段需求写在本文 §6 遗留清单，标明归属阶段。

## 1. 上位机协议硬事实（写代码时必须逐字遵守）

1. **角色**：上位机是 TCP 服务端监听 `9000`，**边缘机是客户端**去连。
2. **分帧**：一行一个紧凑 JSON + `\n`；单帧上限 `1 MB`（`CommTypes.h:20`）。超长上位机会**直接断链**。
3. **`recognize_req`**（上位机→边缘机）**只有 3 字段**：`{"type":"recognize_req","request_id":"req-<ms>-<seq>","timestamp":<ms>}`（`EdgeService.cpp:284-287`）。
4. **`recognize_ack`**（边缘机→上位机）：`{"type":"recognize_ack","request_id":"<原样回带>","items":[...]}`。
5. **`items[]` 每项恰好 4 字段**（`CommTypes.h:37-42`、`EdgeService.cpp:68-100`）：
   - `position`：非空字符串（货位号，如 `A-01-05`），**不得重复**
   - `tool_id`：字符串，**允许空串**（空串 = 该货位无工具 / 无法识别）
   - `confidence`：数值，`0.0 ≤ v ≤ 1.0`
   - `alert_type`：可省略（按 `none` 兼容）；一旦带上必须是 `none| misplaced| unknown| missing| low_confidence` 五者之一
   - **禁止发送** `present`（已从协议删除）、`alert_level`、`class_id`、`tool_name`（上位机不消费，多余字段虽被忽略但不得出现）。
6. **回报范围**：本机组**全部已登记货位**，一项一货位不重复；非在库货位 `tool_id` 置空但**行不得省略**；空 `items` 会被上位机判"识别清单覆盖不全"并弹窗 + 落告警（`ToolService.cpp:120-134,394-416`）。
7. **出库"取出正确"的判据 = 该货位 `tool_id` 为空串**（上位机不认 `present`）。
8. **周期帧** `periodic`（**不是** `heartbeat`），3 秒一帧：`{"type":"periodic","uptime_sec":<int>,"software_version":"<str>","camera_status":[{"camera_id":"CAM1","status":"ok"},...]}`。`status` 取值 `ok|offline`（取图失败归并到 `offline`）；空数组合法（自检可缺席）。
9. **上位机离线判定**：TCP 断开立即离线；周期帧停发 15 秒离线。
10. **幂等要求**：上位机 3 秒无回应即**原帧原样重发同一 `request_id`**，最多 3 次（约 9 秒，`EdgeService.cpp:480-491`）。**边缘机必须对同一 `request_id` 只做一次扫描，重复请求回同一结果。**

## 2. 全局新增接口契约（三阶段共用，禁止各自改名）

### 2.1 `edge/interfaces/i_camera_focus.py`（新增）

```python
class ICameraFocus(ABC):
    @abstractmethod
    def setAutoFocus(self, enabled: bool) -> None: ...
    @abstractmethod
    def setFocusPosition(self, position: float) -> None: ...
    @abstractmethod
    def getFocusPosition(self) -> float: ...
```

- **不得**扩展 `ICameraDevice`（会打破 `test_stage_a_contract_alignment.py` 的 31 对 Fake/接口签名对齐断言与 L1 §3 方法表断言）。
- 对焦平台差异（Windows CAP_DSHOW / Linux v4l2）**全部收敛在 `modules/usb/usb_camera_device.py`**，主流程不得出现 `sys.platform`。

### 2.2 `edge/interfaces/i_frame_sink.py`（新增）

```python
class IFrameSink(ABC):
    @abstractmethod
    def onFrameCaptured(self, workerId: int, frames: tuple[bytes, ...], requestId: str) -> None: ...
```

- `frames` 用 `tuple` 而非固定 2 元素，避免接口签名随路数变化。
- **不得**给 `ICaptureSink` 增加方法（同上契约测试约束）；落盘成功/失败仍走既有 `ICaptureSink`。

### 2.3 `edge/control/edge_dispatch_thread.py`（新增）

```python
class EdgeDispatchThread(BaseThread):
    def __init__(self, dispatchAction: Callable[[], None], logger: ILogger,
                 pollIntervalSec: float) -> None: ...
    def runLoop(self) -> None: ...
```

- 职责单一：周期调用 `dispatchAction()`（即 `EdgeControl.dispatchOutbox`），直到收到停止指令。
- 周期等待必须用 `interruptibleWait`，禁止裸 `time.sleep`。

### 2.4 `edge/infra/roi_binding_loader.py`（新增）

```python
@dataclass(frozen=True)
class RoiBindingRow:
    roiId: str
    drawerId: str
    position: str
    toolId: str
    requiredType: str
    markerId: str
    confidence: float
    rectX: int
    rectY: int
    rectWidth: int
    rectHeight: int

class RoiBindingLoader:
    def __init__(self, logger: ILogger) -> None: ...
    def load(self, csvPath: str) -> list[RoiBindingRow]: ...
```

- **类型定义放在 `infra/`**，因为 `modules/` → `infra/` 是允许方向，反向不允许；`modules/recognition/recognition_utils.py` 内既有的 `RoiBindMap`/`ClassItemMap`/`RoiConfig` **类型不改**，loader 结果在装配层转换过去。
- 只用标准库 `csv`，零第三方依赖；文件缺失 / 列缺失 / 必填列为空 → `EdgeError(ErrorCode.CONFIG, ...)` Fail-Fast。

### 2.5 `edge/modules/recognition/recognition_stitcher.py`（新增）

```python
class FrameStitcher(ABC):
    @abstractmethod
    def stitch(self, frames: tuple[bytes, ...]) -> bytes: ...
    def crop(self, image: bytes, roi: RoiBindingRow) -> bytes: ...
```

- 图像库（`cv2`）**可选依赖**：在函数体内 `import`，缺失时抛 `EdgeError(ErrorCode.CAPTURE, "未安装图像处理库")`；**禁止**改 `edge/pyproject.toml`（L1）。
- 双路拼接约定：**水平拼接，左图在左、右图在右**；右图 ROI 的 x 坐标需加上左图宽度（由 stitcher 内部完成，调用方只给"拼接图坐标系"的矩形）。
- `recognition_utils.py` 保持"纯函数"定位：拼接/裁剪的具体实现放 stitcher，原 `cropAndMerge`/`drawRoi` 保留但降级为占位并注明新路径。

## 3. `edge/config/roi_binding.csv` 表结构（单一事实来源）

表头**必须**逐字为：

```
roi_id,drawer_id,position,tool_id,required_type,marker_id,confidence,rect_x,rect_y,rect_width,rect_height
```

| 列 | 含义 | 必填 | 说明 |
| --- | --- | --- | --- |
| `roi_id` | ROI 区域唯一标识 | 是 | 与识别模块 ROI 编号一致 |
| `drawer_id` | 所属抽屉/柜组 | 是 | 如 `A-01` |
| `position` | 物理货位号 | 是 | 与上位机 `items[].position` 同格式，如 `A-01-05` |
| `tool_id` | 该货位**应放**的工具编号 | 否 | 如 `C01-T0007`；**留空 = 该货位不登记工具**（回包 `tool_id` 置空串） |
| `required_type` | 该货位应放的工具类型名 | 否 | 供人工核对与错放提示 |
| `marker_id` | 该 ROI 内训练出的**特殊标志**类别名 | 是 | 识别到该标志才能确定本 ROI 对应的货位 |
| `confidence` | 标志匹配置信度下限 | 否 | 默认 `0.85`（与上位机 `RECOG_MIN_CONFIDENCE` 对齐） |
| `rect_x/rect_y/rect_width/rect_height` | ROI 在**拼接图**中的矩形（像素） | 是 | 左上角 + 宽高；宽高必须 > 0 |

**强捆绑语义**：一行 = 一个 ROI，同时锁定「区域几何 + 对应货位 + 应放工具 + 内部标志」，改任一项都必须改同一行，杜绝跨文件漂移。

**识别链路**：拼接图 → 按 `rect_*` 裁出 ROI → 在 ROI 内检测 `marker_id` → 命中则该 ROI 的 `position` 与 `tool_id` 已知 → 回包 `items` 追加 `{position, tool_id, confidence, alert_type}`；未命中标志 → 该 ROI **不产出 item**（或按需产出 `tool_id=""` + `alert_type="unknown"`），二选一由 `c5plus` 在 spec-digest 固定。

## 4. `edge/config/config.ini`（新增，仓库当前缺失导致启动即失败）

必须提供以下节与键（键名与现有 `app_init.py` 读取口径一致）：

```ini
[log]
dir = ./logs
max_file_size = 1048576
mode = 1
disk_free_threshold = 0.3
queue_poll_sec = 0.2

[tcp]
max_frame_size = 1048576
backoff_seq = [1,2,4,8,16,30]
heart_interval_sec = 3

[usb]
save_dirs = [./capture/w1,./capture/w2,./capture/w3,./capture/w4]
roll_threshold = 0.3
camera_indices = [1,2,3,4,5,6,7,8]
focus_mode = fixed
focus_position = 0.0

[recognition]
save_dirs = [./recog/w1,./recog/w2,./recog/w3,./recog/w4]
model_path = ./models/yolo.pt
infer_timeout_sec = 3.0
roi_binding_csv = ./config/roi_binding.csv

[event_cache]
enabled = true
```

- `[usb] focus_mode` 取 `auto|fixed`；`focus_position` 为归一化焦点位置（`0.0`~`1.0`），开机由 `UsbController.applyFixedFocus()` 应用。
- `[recognition] roi_binding_csv` 指向 CSV 路径，取代原先塞在 ini 里的 `roi_config` / `class_item_map` / `roi_bind_map` 三个 JSON 字符串（**原实现读进来是 `list[str]` 而非 `dict`，靠 `cast` 静默掩盖，是定时炸弹**）。

## 5. 必须修掉的 4 个生产断点（`dplus` 负责，验收硬指标）

| 断点 | 位置 | 修法 |
| --- | --- | --- |
| `recognize_req` 路由不到采集 | `app_init.py` `asyncHandlers={}` | 注册 `recognize_req` handler → `usb.startCapture(request_id)` |
| 应答永不出队 | `control/edge_control.py` `dispatchOutbox` 生产零调用 | 新增 `EdgeDispatchThread` 周期排空，并在 `startSystem` 时启动、`stopSystem` 时先停 |
| 断链不通知上游 | `modules/tcp/tcp_control_layer.py` `onLinkDown` 未转发 | 转发 `upstreamSink.onLinkDown(reason, source)`，使 `_linkUp` 正确置 False、应答改入缓存 |
| 周期帧格式错 | `app_init.py` `defaultHeartbeat` 发 `heartbeat` | 改为 `periodic` + `uptime_sec` + `software_version` + 8 路 `camera_status` |

**外加必改**：周期帧 `camera_status` 必须真实反映 8 路摄像头状态（`ok|offline`，取图失败归 `offline`），上位机拿它做**开柜闸门**（任一路非 `ok` 直接拒绝开柜），不能硬编码 `ok`。

## 6. 遗留与归属（跨阶段，不得在当前阶段顺手扩范围）

| 事项 | 归属 |
| --- | --- |
| `TcpDecodeThread` 阻塞 `recv` 不可打断（`stop()` 只能等 join 超时） | 后续专项（socket 超时 + select） |
| `EventCache` / `_outbox` / `_requestId` / `_linkUp` 无锁 | `dplus` 内加锁（8 路并发必需） |
| `ErrorCode` 恰好 5 成员，`test_stage0_error_and_lock_guards.py:19` 断言 | **不得新增枚举成员**；复用 `CAPTURE` / `CONFIG` |
| `infra/log_manager.py` 与 `control/event_cache.py` 同名方法 `logInfo`（违反方法名全局不重复） | `dplus` 顺手改名其一 |
| `YoloEngine.instance()` 从未被调用（双检锁形同虚设） | `c5plus` 内统一走 `instance()` |
| `dual_crop_stitch/config.ini` 的 `[crop]/[stitch]/[yolo]/[business]` 真实参数 | `c5plus` 参考 `dual_crop_stitch` 实现细节后定稿 |

## 7. 验收硬指标（三阶段合并）

1. `ruff check edge` 零告警；`mypy edge`（3.9 strict）零错误；`pytest edge/tests` 全绿。
2. **既有测试零修改断言**：除 `test_stage_a_contract_alignment.py` 因新增接口/Fake 需同步 L1 方法表外，其余既有测试文件**不得改动**。
3. 端到端联调（`tests/integration/`）：Python 桩上位机监听 9000 → 边缘机连上 → 桩发 `recognize_req` → 边缘机回 `recognize_ack`，`items[]` 每项**恰好 4 字段**、`position` 不重复、`tool_id` 可空、`confidence ∈ [0,1]`、`alert_type` 取值合法 → 桩校验通过。
4. **幂等验证**：同一 `request_id` 连发 2 次，边缘机只扫描一次、回两次相同结果。
5. **周期帧验证**：3 秒一帧 `periodic`，`camera_status` 覆盖 8 路。
6. 重复 `recognize_req` 不导致 8 路重复扫描（计数断言）。

---

## 8. 修订（2026-11-14，依据 `dual_crop_stitch/` 原实现实测 + c4plus/dplus 实施反馈）

> 本节优先级高于 §2/§3 中与之冲突的早期表述。依据：`d:\CFDZ\BYJSJ\New-SmartCabinet\dual_crop_stitch\config.ini`、`src/vision_core.py`、`src/tcp_comm.py`（原平铺实现实测）。

### 8.1 ROI 坐标格式修正（早期 §3 的 `rect_x/rect_y/rect_width/rect_height` **作废**）

原实现的 ROI 是**矩形四角点 `[x1, y1, x2, y2]`**（左上→右下，像素，参照系=**拼接后的全景画布**），不是"宽高"形式。
`vision_core.py:287-288` 原文："roi_defs 手动定义的 ROI 字典；格式 {"roi_id": (x1, y1, x2, y2)}；坐标相对于拼接后的全景画布；单位: 像素"。

**CSV 表头最终版（12 列，逐字）**：

```
roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,confidence,rect_x1,rect_y1,rect_x2,rect_y2
```

新增列说明：
- `worker_id`（**必填**，1~4）：该 ROI 归属哪个采集 worker（= 哪一对摄像头）。**缺这列无法把 ROI 分配到 4 个并发 worker**，是早期设计的遗漏。
- `rect_x1/rect_y1/rect_x2/rect_y2`：拼接全景画布上的矩形四角点，`x2 > x1` 且 `y2 > y1`。
- 其余列语义同 §3。

### 8.2 裁切与拼接的真实算法（必须复刻，不得自创）

- **裁切**（`vision_core.py:86-137`，"五五分 + 垂直居中"）：
  - 左摄取**右半幅**：`leftImage[leftYStart : leftYStart + cropHeight, leftW - cropWidth : leftW]`
  - 右摄取**左半幅**：`rightImage[rightYStart : rightYStart + cropHeight, 0 : cropWidth]`
  - `leftYStart = (leftH - cropHeight) // 2`（各自按自己的高居中）
  - `cropWidth = 0` 时自动 = 原图宽 `// 2`；`cropHeight = 0` 时自动 = 两图高的**较小值**
- **拼接**（`vision_core.py:140-194`）：**仅 x 轴偏移对齐，y 轴顶部对齐**；**无 resize / 无缩放 / 无插值 / 无单应性 / 无融合**。
  - `offsetA = 0`；`offsetB = refX_A - refX_B`；画布黑底，**后贴覆盖前贴**（先 A 后 B）
  - `canvasW = max(offsetA + imgW, offsetB + imgW) - xMin`；`canvasH = imgH`
  - 拼接点为空时自动算 `[左半幅宽, 0]`（即全景左半来自一台、右半来自另一台）
- **参照系**：ROI 坐标相对**拼接全景**，不是单路原图。

### 8.3 `recognize_ack` 组帧规则（c5plus 定稿，**覆盖早期 §1 的表述**）

1. **一次 `recognize_req` 恰好回一帧** `recognize_ack`（**不是**每个 worker 一帧）。4 个 worker 的结果必须**聚合成一帧**再发，否则上位机只认第一帧 → 覆盖不全 → 弹"识别清单覆盖不全"并落告警。
2. 帧顶层键：`{"type": "recognize_ack", "request_id": "<原样回带>", "items": [...]}`。
   **`request_id` 是 snake_case（协议字段名）**；早期 §2 中 edge 内部用的 `requestId` 只能作为内部变量名，**不得出现在线上帧里**。
3. `items[]` 每项**恰好 4 个键**：`position`、`tool_id`、`confidence`、`alert_type`。
   **禁止**出现 `roiId` / `className` / `item` / `boundItem` / `workerId` / `requestId` 等 edge 内部字段。
4. **items 必须覆盖 CSV 的全部行**，一行不漏（上位机要求"非在库货位 `tool_id` 置空但行不得省略"；空 `items` 会被上位机判覆盖不全）。
5. `alert_type` 产出规则（组合识别取最低置信度；检测结果须带位置框，缺框按未识别）：

| 情形 | `tool_id` | `confidence` | `alert_type` |
| --- | --- | --- | --- |
| 命中标志且置信度 ≥ 该行 `confidence` 下限 | CSV 的 `tool_id`（可为空串） | 实际检测置信度（组合取参与匹配各项最低值） | `none` |
| 命中标志但置信度 < 下限 | CSV 的 `tool_id` | 实际检测置信度（组合取参与匹配各项最低值） | `low_confidence` |
| 未命中标志 | `""`（空串） | `0.0` | `unknown` |
| 检测项缺位置框（生产口径） | `""`（空串） | `0.0` | `unknown`（按未识别） |
| CSV 行 `tool_id` 本身为空（该货位不登记工具） | `""` | 实际检测置信度（若命中） | `none` |

6. `position` 在 items 内**不得重复**；CSV 内 `position` 重复 → `EdgeError(ErrorCode.CONFIG, ...)` Fail-Fast。
7. **已知限制（如实记录，不得隐瞒）**：出库项"取出正确"的上位机判据是"`tool_id` 为空串"，因此"放了工具但标志没识别出来"会被上位机判为取出正确。`alert_type=unknown` 能保留信息但上位机业务层不消费它。缓解手段是降低漏检（提高 `confidence` 下限前的实测标定），此限制写入 handoff 与测试报告。

### 8.4 聚合归属

- 聚合在 **`control/edge_control.py`**（唯一协调者）：维护 `request_id → {workerId: items}`，收满**构造注入的预期 worker 数**后合并成一帧入 `_outbox`。
- 识别模块只负责"本 worker 的 ROI 行 → items"，**不负责跨 worker 聚合**（避免 `modules/` 之间耦合）。
- `expectedWorkerCount` 由装配层按 `len(cameraPairs)` 注入。

### 8.5 已裁决事项（c4plus/dplus 实施反馈）

| 事项 | 裁决 |
| --- | --- |
| `UsbController.startCapture(requestId: str = "")` 带默认值 | **接受**。既有 `test_stage_c4_usb.py` 有 9 处无参调用，该测试文件不可改；带默认值不影响 `usb.startCapture(request_id)` 行为。 |
| `cv2.CAP_PROP_FOCUS_ABSOLUTE` 本机不存在（OpenCV 4.13.0） | **接受**实现方的兼容写法：优先绝对焦点属性、缺失退回 `CAP_PROP_FOCUS`；自动对焦用 `CAP_PROP_AUTOFOCUS`。 |
| `frameSink` 未注入导致帧回调不生效 | **c5plus 必须解决**：`app_init` 把 `frameSink` 注入为控制层，识别走流式帧入口，不再只落盘。 |
| `applyFixedFocus()` 未在启动期调用 | **c5plus 必须接上**：启动时调用；因缺 opencv / 设备未开而失败时**记 info 不中断启动**（不 Fail-Fast，如实上报不造假）。 |
| `edge/config/config.ini` 与 §4 模板的 3 处值偏差 | **以 `app_init.py` 现有读取口径为准**（`[log] mode` 是 int；`disk_free_threshold` 是剩余空间比例；列表值不带方括号，因为 `inferValue` 遇逗号切 list，带方括号会得到脏值）。键集仍与 §4 一致。 |
| `test_stage_a_contract_alignment.py` 的"接口 8 个 / Fake 8 个"计数断言 | **c5plus 同步**：新增 `i_camera_focus` / `i_frame_sink` 两个接口与两个 Fake 后，期望表与计数必须同步（这是"允许新增接口 + 同步新增 Fake + 同步契约用例"的规定动作，不是"静默修改既有断言"）。 |
| `edge/modules/tcp/tcp_socket.py` 不存在（生产 socket 仍是 `SocketSkeleton`） | 归属后续 c3 补齐/上板阶段；本轮联调用测试目录内的真实 TCP 套接字。 |
| `TcpControlLayer.onLinkDown` 不转发上游 | 已在控制层用链路探针 `syncLinkState` 等效自愈；最小 diff 留在 handoff 待批准，不越界改 tcp 文件。 |

### 8.6 `class_item_map`（可选第二张表）

原实现有"类别组合 → 物品名"表（`{"person,surfboard": "滑板人偶"}`，键按 `,` 拆分转 `frozenset`，顺序无关）。
新设计主用 `marker_id` 单标志直映，**类别组合表降级为可选**：
- 若存在 `edge/config/class_item_map.csv`（表头 `class_names,item_name`），则 ROI 内检测到的**类别集合**先折算成物品名再比对；组合命中时置信度取参与匹配各项的**最低值**，防止单个高置信类别带过整组合；
- 不存在则按单个 `marker_id` 直映。
- 两者都不得影响 `items[]` 的 4 字段协议形状，只影响 `tool_id` 的取值判定。
