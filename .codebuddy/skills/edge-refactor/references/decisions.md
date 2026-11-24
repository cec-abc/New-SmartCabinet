# decisions.md — 已定裁决

> 本文件是 L3 长资料，记录**用户已定裁决**。裁决优先级仅次于用户当次指令与 L1 契约层。
> 与 `edge/docs/spec/` 旧图冲突时，以 L1 + 本文件为准；不得反过来改图或改 L1。
> 新增/变更裁决必须由用户明确下达；写入本协议后同步项目记忆与 handoff。

## D-01 自检留空接口

**裁决**：自检逻辑本轮不实现，只留空接口与 TODO；不新增自检线程，不做能力降级分支。

- **冲突来源**：
  - `edge/docs/spec/整体流程/整体流程.txt` 第 1 段的 `SelfChecker.check_all()`、
    「部分失败 → 能力降级（IO 禁开锁 / 摄像头 offline / 模型拒识别）」分支。
  - `edge/docs/spec/USB_Camera/USB.txt` 的 `UsbController.selfCheck()`、
    `CaptureWorker.check_camera()` 预留节点与「阶段三 旁路自检流程」。
- **落地含义**：
  - 在非 L1 的门面内保留**空方法占位**（不执行 IO、不返回伪结果），配 `## @brief` 与 `TODO` 中文注释。
  - **L1 `interfaces/` 不新增自检方法**；若确需写入契约，走 L1 变更流程（diff + 用户批准）。
  - 不新建 `self_check*.py`、`checker/` 等文件或目录；不占用采集线程、识别线程与主线程。
  - 初始化失败仍按 L1 的 Fail-Fast / 记录日志 / 返回失败路径处理，不引入「能力降级」状态机。
- **影响阶段**：`0`（启动流程）、`c4`、`c5`、`d`（`app_init` 与模块 init）。
- **禁止**：以「图上有 SelfChecker」为由新增类、线程或接口；以自检结果控制模块启停。

## D-02 非 UP 不启其他线程

**裁决**：`linkState` 非 `UP` 时，不启动心跳、解码、采集、识别等业务线程；
唯一例外是把状态拉回 `UP` 的一次性重连线程。

- **冲突来源**：
  - 部分旧图在 `DOWN` / `CONNECTING` 阶段即出现心跳与解码线程，或在断线流程里
    「先启心跳再宣告 DOWN」。
  - `edge/docs/spec/整体流程/整体流程.txt` 已与裁决一致：
    「HeartThread 与 DecodeThread 此时不启动」「UP 后 心跳与 Decode 并行启动 再 onLinkUp」。
- **落地含义**：
  - 启动顺序固定：`TcpReconnectThread` → 连接成功 → `transitionTo(UP, ...)` →
    并行启 `HeartThread` 与 `DecodeThread` → 再 `onLinkUp()` → 由 `EdgeControl` 决定补发/丢弃。
  - DOWN 顺序固定：`transitionTo(DOWN, ...)` → 停心跳、停解码 → 重新拉起重连线程；
    并发宣告 DOWN 由 `transitionTo` 返回值去重。
  - `linkState` 只经 `transitionTo(state, reason, source) -> bool` 写入，禁止直接读写。
  - 非 UP 时 `sendHeartFrame` 直接返回 `False`，不触发底层 IO，也不顺带启线程。
- **影响阶段**：`c3`、`d`。
- **禁止**：在 `onLinkUp` 之前预启任何业务线程；让心跳线程兼任重连；在非 UP 状态下
  为「提前预热」启动采集/识别 worker。

## D-03 去重不做、seq 只填不用

**裁决**：补发去重逻辑不实现；协议帧 `seq` 只按递增填充，不参与去重、幂等或排序判断。

- **冲突来源**：
  - `edge/docs/spec/TCP/断线重连/断线重连.txt` 时序中的「查 `PendingRequest` 重发」
    与 `onLinkUp` 反复补报。
  - 旧流程图中把 `EventCache` 画成按 `seq` 去重的缓存队列。
  - L1 定稿已明确：「`event_cache.enabled` 开关做；协议帧预留 `seq` 只填不用；去重逻辑先不做」。
- **落地含义**：
  - `EventCache` 只负责 DOWN 期间缓存必须送达的事件（识别 ack、失败应答、主动通知）；
    UP 时按 `event_cache.enabled` 决定**补发或丢弃**；心跳帧不缓存。
  - 每条缓存事件带递增 `seq` 字段，仅作占位/填写；不建 `seenSeq`、幂等表、去重缓存。
  - `dedupCacheTtl` 等去重参数本轮不引入；规范中提及它只是「若将来引入必须构造注入」的示例。
  - 重发请求（`PendingRequest`）不在本轮实现。
- **影响阶段**：`c3`（协议帧组装）、`d`（`EventCache` / `EdgeControl`）。
- **禁止**：任何基于 `seq` 的比较、过滤、判重；把 `seq` 当业务幂等键；以「防止重复上报」为由
  新增去重逻辑（心跳失败去重仍按 L1 的 `transitionTo` 返回值处理，两者不是同一件事）。

## D-04 对照关系表落 CSV（12 列），不用 MySQL、不用 JSON

**裁决**：ROI / 货位 / 工具 的对照关系表一律落 **CSV** 文件（标准库 `csv` 解析，零第三方依赖），表头固定 12 列：
`roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,confidence,rect_x1,rect_y1,rect_x2,rect_y2`。
**不用 MySQL**（不引数据库、不引驱动）、**不用 JSON**（不可编辑、diff 差、Excel 打开不便）。

- **落地含义**：
  - 一行 = 一个 ROI，同时锁定「区域几何 + 对应货位 + 应放工具 + 内部标志」，改任一项必须改同一行，杜绝跨文件漂移。
  - `worker_id` **必填**（1~4）：缺这列无法把 ROI 分配到 4 个并发 worker。
  - 取代旧实现「三份 JSON 塞进 ini」（原实现读进来是 `list[str]` 而非 `dict`，靠 `cast` 静默掩盖）。
- **理由（用户 2026-11-14 指令）**：零依赖、Excel 可直接编辑、Git 行级 diff、RK3588 上零负担。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 指令 + `edge/docs/refactor/stages/dplus/spec-digest.md` §3 / §4 / §8.1。
- **禁止**：把对照表改回 JSON 或塞进 ini 字符串；引入数据库依赖；`worker_id` 留空。

## D-05 ROI 坐标用四角点，参照系为拼接全景

**裁决**：ROI 区域坐标一律用**四角点** `[x1, y1, x2, y2]`（左上 → 右下，像素），**参照系 = 拼接后的全景画布**；
早期的「左上角 + 宽高」（`rect_x/rect_y/rect_width/rect_height`）形式**作废**。

- **落地含义**：
  - CSV 列固定为 `rect_x1/rect_y1/rect_x2/rect_y2`，且 `x2 > x1`、`y2 > y1`，否则 Fail-Fast。
  - 裁剪时按四角点从全景图切片；ROI 越出全景范围抛 `EdgeError(CAPTURE, "ROI 超出拼接图范围: ...")`。
  - 拼接约定复刻原实现：五五分 + 垂直居中裁切、仅 x 轴偏移对齐、y 轴顶部对齐，无缩放 / 无插值 / 无融合。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14。
- **来源**：原实现 `dual_crop_stitch/src/vision_core.py:287-288` 原文（「格式 `{"roi_id": (x1, y1, x2, y2)}`；坐标相对于拼接后的全景画布；单位: 像素」）+ `stages/dplus/spec-digest.md` §8.1 / §8.2。
- **禁止**：改回宽高形式；把 ROI 坐标当成单路原图坐标；自创缩放 / 插值 / 融合的拼接算法。

## D-06 线上帧字段名用协议 snake_case（`request_id`），内部变量才用 camelCase

**裁决**：**线上协议帧的字段名一律以上位机代码为准**，`recognize_ack` 顶层键固定为
`{"type": "recognize_ack", "request_id": "<原样回带>", "items": [...]}`。
`requestId` 只能作**内部变量名 / 内部方法参数名**，**不得出现在任何出网帧里**。

- **落地含义**：
  - 内部 camelCase 命名规范（L1 编码规范）与线上协议键名（snake_case）是两套东西，不得互相套用。
  - 内部字段（`workerId` / `requestId` / `roiId` / `className` / `boundItem` / `item`）在组帧出口一律剔除。
  - `items[]` 每项**恰好 4 键**：`position` / `tool_id` / `confidence` / `alert_type`；
    禁止出现 `present`（已从协议删除）/ `alert_level` / `class_id` / `tool_name`。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 指令 + 上位机代码 `EdgeService.cpp`（只读 `request_id`）+ 真实上位机进程实测
  （snake_case 帧的请求编号被回带；驼峰 `requestId` 帧编号为空、被直接丢弃）+ `stages/dplus/spec-digest.md` §8.3.2 / §8.3.3。
- **禁止**：以「工程内部命名规范」为由改线上键名；让内部字段随帧上线；新增协议外键名。

## D-07 一次请求回一帧，跨 worker 聚合放控制层

**裁决**：一次 `recognize_req` **恰好回一帧** `recognize_ack`（不是每个 worker 一帧）；
4 个 worker 的结果**必须聚合成一帧**再发。聚合归属 **`control/edge_control.py`**（唯一协调者）。

- **落地含义**：
  - 控制层维护 `request_id → {workerId: items}`，收齐**构造注入的预期 worker 数**（= `len(cameraPairs)`）后合并成一帧入 `_outbox`。
  - 识别模块只负责「本 worker 的 ROI 行 → items」，**不负责跨 worker 聚合**（避免 `modules/` 之间耦合）。
  - 合并时 `position` 去重（重复保留第一条并记 error），条目按 `position` 排序。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 指令 + `stages/dplus/spec-digest.md` §8.3.1 / §8.4（上位机只认第一帧，多帧会触发「识别清单覆盖不全」弹窗并落告警）。
- **禁止**：每个 worker 各回一帧；识别模块内做跨 worker 聚合；把 `expectedWorkerCount` 写死在模块里。

## D-08 对焦用独立接口 `ICameraFocus`，不扩 `ICameraDevice`

**裁决**：对焦能力用**独立新接口** `ICameraFocus`（`setAutoFocus` / `setFocusPosition` / `getFocusPosition`），
**不得**扩展 `ICameraDevice`；平台差异（Windows `CAP_DSHOW` / Linux `CAP_V4L2`）**全部收敛在设备层**。

- **落地含义**：
  - 独立接口避免打破契约守卫 `test_stage_a_contract_alignment.py` 的 Fake/接口签名对齐断言（实测 31 → 35 对）与 L1 §3 方法表断言。
  - 新增接口必须**同步新增对应 Fake**（本轮新增 `FakeCameraFocus` / `FakeFrameSink`），接口数与 Fake 数同步为 10。
  - 设备实现类可同时实现 `ICameraDevice` 与 `ICameraFocus`；主流程不得出现 `sys.platform`。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 指令 + `stages/dplus/spec-digest.md` §2.1 / §2.2 / §8.5。
- **禁止**：给 `ICameraDevice` 增加对焦方法；给 `ICaptureSink` 增加方法；平台分支外泄到主流程。

## D-09 图像库 / 推理框架作可选依赖，pyproject 依赖清单保持为空

**裁决**：图像处理库（`cv2`）与推理框架（`ultralytics` / `onnxruntime`）一律作**可选依赖**，
在**函数体内 `import`**；`edge/pyproject.toml` 属 L1 **不得改**，依赖清单保持 `dependencies = []`。

- **落地含义**：
  - 缺库时按可降级路径处理：抛 `EdgeError(CAPTURE, "未安装图像处理库")` 或走降级桩并**如实记 info**，不静默、不伪造。
  - 可选依赖不写进 `pyproject.toml`，因此 `ruff` / `mypy`（3.9 strict）在无库环境下仍须全绿（导入处用 `# type: ignore` 标注）。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 指令 + `stages/dplus/spec-digest.md` §2.5 / §8.5 + L1 硬要求「不得自动修改 L1」。
- **禁止**：修改 `edge/pyproject.toml` 的依赖清单；在模块顶层 `import cv2`；缺库时伪造识别命中。

## D-10 `ErrorCode` 不得新增成员

**裁决**：`ErrorCode` **不得新增枚举成员**（既有测试断言恰 5 个：`CONFIG` / `LINK_DOWN` / `FRAME_PARSE` /
`INFERENCE_TIMEOUT` / `CAPTURE`）。本轮新增异常一律**复用** `CONFIG`（配置类）或 `CAPTURE`（图像/采集类）。

- **落地含义**：
  - 配置类问题（对照表缺失 / 缺列 / 必填为空 / 编号越界 / 货位重复 / 对焦模式非法）→ `CONFIG`。
  - 图像与采集类问题（图像库缺失 / 解码失败 / ROI 越界 / 拼接尺寸不一致 / 取图失败）→ `CAPTURE`。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 指令 + `stages/dplus/spec-digest.md` §6 + `edge/tests/unit/test_stage0_error_and_lock_guards.py:19-27`。
- **禁止**：新增 `ErrorCode` 成员；改既有成员名或整数值；为此改既有断言。

## D-11 既有测试若写死了与上位机矛盾的协议形状，可经用户追认后改写

**裁决**：既有测试文件中**写死了与上位机协议相矛盾的形状**（如线上帧顶层键写成驼峰 `requestId`、
条目形状多带内部字段）的断言，**必须经用户明确追认后**才可改写；改写时不得删用例、不得加 skip / xfail、
不得放宽断言，且必须逐处登记原断言、新断言与改写理由。

- **落地含义**：
  - 「允许同步」的三类例外（按 `stages/dplus/spec-digest.md` §8.5）：① 新增接口 + 同步新增 Fake + 同步契约用例期望表与计数；
    ② 本文件新增的 ROI 对照表表头用例随表头同步；③ 随实现签名变化同步的调用点。
  - 其余既有测试文件**不得改动**（`stages/dplus/spec-digest.md` §7 第 2 条）。
- **当前状态**：**待追认** —— `edge/tests/unit/test_stage_c5_recognition.py` 的 3 处断言改写（阶段 c5 既有测试文件，
  不在 `c5plus` 白名单内）已按「白名单越界」登记在 `edge/docs/refactor/stages/dplus/handoff.md` §6.2 B1，等待用户拍板。
- **影响阶段**：`c4plus`、`c5plus`、`dplus`。
- **生效日期**：2026-11-14（裁决本身生效；具体追认待用户下达）。
- **来源**：用户 2026-11-14 指令 + `stages/dplus/spec-digest.md` §7 第 2 条 / §8.5 + `stages/dplus/test-report.md` ⑤.1。
- **禁止**：以「让测试变绿」为由改既有断言；删用例；加 skip / xfail；改被测代码迁就旧断言；未经追认自行落地越界改写。

## D-12 生产必须装载 ROI 对照表，缺失即启动失败（废弃配置兜底链路）

**裁决**：边缘机生产运行**必须随包提供 ROI 对照表**（`edge/config/roi_binding.csv`）；
**未装载到对照表 → 启动即失败**（`EdgeError(CONFIG)`），**废弃**「配置兜底链路」（无对照表时靠 ini 里的
`roi_config` / `class_item_map` / `roi_bind_map` 查表识别的那条路径）。

- **落地含义**：
  - `app_init` 装配期装载对照表：装载失败或表里没有数据行 → 直接抛 `EdgeError(CONFIG)`，**不带着空台账上线**。
  - `RecognitionWorker.runConfigRecognition` 判**不可用**：记一条 info 并抛 `EdgeError(CONFIG)`，
    **不产出误导条目**（既不伪造命中，也不把故障伪装成「全是未识别」的正常结果）。
  - 检测结果缺 `roiId` 时，`aggregateByRoi` 直接抛 `EdgeError(CONFIG)`，**不静默塌缩成一个空分组**；
    `roiIdOf` 缺键返回 `None` 而不是空串（空串会让调用方以为「有一个空的 roi」）。
  - 部署包缺表 = 起不来，这是**有意的 Fail-Fast**，不是缺陷。
- **理由（实测依据）**：两条推理后端（ultralytics / onnxruntime）产出的检测结果**只有 `className` 与
  `confidence` 两个键、没有 `roiId`**；按区域归集必然塌缩成一个空组，查表只能得到清一色的未识别条目。
- **影响阶段**：`c5plus`、`dplus`（`recognition_utils.py` / `recognition_worker.py` / `app_init.py` 装配段）。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 第三轮修复指令 + `stages/dplus/test-report.md` ③.6.1 / ③.6.2
  （`test_c5_3_config_fallback_path_is_unavailable`、`test_roi_binding_table_missing_fails_fast`、
  `test_roi_binding_table_empty_fails_fast`、`test_roi_binding_table_loaded_returns_rows`）。
- **禁止**：恢复配置兜底链路；缺表时降级上线；缺 `roiId` 时静默吞掉或塞进空分组。

## D-13 推理后端默认固定 ultralytics；onnxruntime 分支补 NMS 但需现场标定后方可启用

**裁决**：推理后端**默认固定 `ultralytics`**；`onnxruntime` 分支已补**同类别非极大值抑制（NMS）**，
但在**完成与 ultralytics 的逐框等价性现场标定之前，不得启用**。

- **落地含义**：
  - `[recognition] inference_backend` 默认 `ultralytics`；`[recognition] nms_iou_threshold` 默认 `0.45`，
    NMS 阈值**构造注入**，模型加载后不允许改（避免同一模型前后结论不一致）。
  - onnx 分支的候选框**先按同类别做 NMS 再出结果**，避免同一张图上的重叠框被当成多个目标。
  - onnx 分支在引擎内显式标注「未与 ultralytics 对齐, 需现场标定」，并写进日志，避免误以为两者等价。
  - **换后端等于换结论**：置信度口径、类别映射、预处理不同，未标定前不得用 onnx 结果替代 ultralytics 结论。
- **影响阶段**：`c5plus`、`dplus`（`recognition_yolo_engine.py` / `config.ini` / `app_init.py` 装配段）。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 第三轮修复指令 + `stages/dplus/test-report.md` ③.6.4
  （`test_onnx_backend_applies_non_maximum_suppression`、`test_nms_threshold_is_injected`、
  `test_onnx_backend_is_marked_as_needing_field_calibration`、`test_two_backends_output_count_within_tolerance`）。
- **禁止**：默认切到 onnxruntime；未做 NMS 等价处理就对比两条后端的结果；把「条数同量级」当成「逐框等价」。

## D-14 对照表 `worker_id` 不得超过实际采集线程数，装配期校验

**裁决**：ROI 对照表里的 `worker_id` **不得超过实际采集线程数**；超限**装配期即报错**
（`EdgeError(CONFIG)`），**启动即失败**，不得带着「永远无人上报」的货位上线。

- **落地含义**：
  - 装配期以实际采集线程数（`len(cameraPairs)`）校验对照表每一行的 `worker_id`，超限即抛错。
  - 装载器侧保留 `worker_id` ∈ 1~4 的**基础区间**校验（表结构层面的硬约束）。
  - 两道校验职责不同：基础区间由装载器管（表写错），实际线程数由装配期管（现场相机数与表不一致）。
- **影响阶段**：`c5plus`、`dplus`（`app_init.py` 装配段 / `infra/roi_binding_loader.py`）。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 第三轮修复指令 + `stages/dplus/test-report.md` ③.6.3
  （`test_roi_worker_id_beyond_actual_worker_count_fails_fast`、`test_loader_rejects_worker_id_out_of_base_range`、
  `test_roi_worker_scope_fails_fast`）。
- **禁止**：运行时才丢弃超限行；把超限行静默归到最后一个 worker。

## D-15 相机状态判定：从未成功打开的设备一律 offline（避免上位机开柜闸门误放行）

**裁决**：相机状态判定**必须区分「从未成功打开」与「打开后异常」**：
**从未成功打开过的设备一律报 `offline`**，不许报 `ok`；无对应设备同样报 `offline`。

- **落地含义**：
  - 状态推导顺序：设备缺失 → `offline`；`commOk` 为假 → `comm_error`；`everOpened` 为假 → `offline`；
    否则 → `ok`。
  - **这是安全闸门语义**：上位机拿 `camera_status` 做开柜闸门（任一路非 `ok` 直接拒绝开柜），
    把「从未打开」误报成 `ok` 会让上位机**误放行开柜**。
  - 当前只产出 `ok` / `offline` / `comm_error` 三种状态；`low_light` / `dirty` 需图像分析，**待上板实现**，
    在此之前上位机开柜闸门只按这三种值判。
- **影响阶段**：`c4plus`、`dplus`（`modules/usb/usb_controller.py` 状态推导段 + 周期帧 `camera_status`）。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 第三轮修复指令 + `stages/dplus/test-report.md` ③.6.5
  （`test_camera_never_opened_reports_offline`、`test_camera_unreachable_reports_offline`、
  `test_camera_status_values_are_limited`、`test_camera_status_follows_physical_order`、
  `test_periodic_frame_camera_status_matches_usb`）。
- **禁止**：把「没打开过」与「打开过但取图失败」合并成同一状态；硬编码 `ok`；在未实现图像分析时产出
  `low_light` / `dirty`。

## D-16 识别背压需有丢弃计数与抽样日志（可观测性）

**裁决**：识别忙时丢弃帧**必须可观测**：累计**丢弃计数** + 按阈值的**抽样日志**；
不得静默丢帧，也不得逐帧刷屏。

- **落地含义**：
  - 同一 worker 上一轮扫描未结束时，本轮帧被丢弃并计数；提供**只读 getter** 供验收举证。
  - 日志按抽样间隔（默认每 10 次记 1 条）输出，避免逐帧刷屏把日志冲垮。
  - 验收必须带**计数断言**（触发 N 次 → 计数 == N、日志条数 == 抽样口径），不能只断言「触发返回 False」。
- **影响阶段**：`c5plus`（`modules/recognition/recognition_controller.py`）。
- **生效日期**：2026-11-14。
- **来源**：用户 2026-11-14 第三轮修复指令 + `stages/dplus/test-report.md` ③.6.6
  （`test_dropped_frames_are_counted_and_logged_by_threshold`）。
- **禁止**：丢帧无任何痕迹；逐帧打日志；把丢帧计进业务失败统计。

## D-17 由构造注入的上限，仍须受协议侧绝对硬顶钳制

**裁决**：帧长安全阈值、收包半包缓冲、待发应答队列等「由构造注入值参与计算的上限」，
一律**再受一个与对端协议对齐的绝对硬顶钳制**；注入值配错不得能把保护打穿。缓冲与队列必须有上限 + 超限策略，
不得内存无界。

- **落地含义**：
  - 帧长安全阈值 = `min(max(注入值 × 系数, 最小可用下限), 协议硬顶)`；本协议硬顶取上位机单帧上限（1 MB）的一半 `524288`，并保留最小可用下限避免注入过小算出 0。
  - 收包半包缓冲：对端一直不换行即无限攒 → 设累计上限（与单帧同量级），超限判链路异常并断链收敛。
  - 待发应答队列：链路长期断开即无限增长 → 设条数上限（本轮 `1024`），超限丢最旧并记一条日志（可观测），不静默吞掉。
  - 泛化：凡「对端有固定上限」的场合，注入值本身不是保护，协议硬顶才是最后一道；注入只用于调参，不用于定契约。
- **影响阶段**：2026-11-15 全模块整改（非编号阶段）；后续上板及所有涉及 TCP 收发 / 缓冲 / 出队的改动沿用。
- **生效日期**：2026-11-15。
- **来源**：用户 2026-11-15 沉淀指令（明确列明本条并指定登记 D-17 起）+ 全面代码检查与整改的代码读盘核实（`tcp_comm.py` 的 `HOST_SAFE_FRAME_LIMIT_BYTES` / `MAX_RECV_BUFFER_BYTES`、`tcp_decode_thread.py::reportBufferOverflow`、`edge_control.py` 的 `MAX_OUTBOX_FRAMES`）。
- **禁止**：以「阈值是构造注入的、可配」为由省略协议硬顶；让半包缓冲或待发队列无界；注入值配大后仍向对端发超其硬上限的帧；超限丢帧不记日志。

## D-18 停机不得触发重连；停机与断链是两条路径

**裁决**：`stop()` 停机路径**不得**因 socket 被关闭 / 解码线程读到空或异常而误判断链、反向拉起重连线程。
停机先迁移链路状态到 DOWN 且**不走 `onLinkDown`**；后台线程以 `isRunning()` 收敛。真断链（非停机）才转发上游。

- **落地含义**：
  - `stop()` = `transitionTo(DOWN, "stop", "STOP")`（只迁移状态，不触发重连分支）→ 串行停重连 / 心跳 / 解码三线程 → 关句柄。
  - 解码线程在停机指令已下达时，读到空 / `EdgeError` / 缓冲超限都**不再宣告断链**；正常运行时才 `onLinkDown`。
  - 真断链（非停机）仍按 D-02 拉起重连，并**转发 `upstreamSink.onLinkDown`**，使控制层立刻把应答改入事件缓存（只靠链路探针轮询会晚一个排空周期）。
  - **与 D-02 的边界**：D-02 管「断链 DOWN → 拉起一次性重连线程」，本条管「停机 stop → 绝不拉起任何线程」；两者是不同路径，本条不是对 D-02 的修改或放宽。
- **影响阶段**：2026-11-15 全模块整改（非编号阶段）；后续所有涉及线程启停 / 链路状态迁移的阶段沿用。
- **生效日期**：2026-11-15。
- **来源**：用户 2026-11-15 沉淀指令（明确列明本条）+ 代码读盘核实（`tcp_control_layer.py::stop()` 与 `onLinkDown`、`tcp_decode_thread.py` 三处 `isRunning()` 收敛）。
- **禁止**：让停机复用「异常 → 重连」分支；停机过程中拉起任何新线程；把「停机」与「断链」合并成同一入口；为真断链省事而不转发上游。

## D-19 数值范围校验必须先 `math.isfinite`，NaN 不是越界值

**裁决**：一切外部输入数值（配置阈值、协议字段、置信度下限等）的取值范围校验，
一律**先判有限（`math.isfinite`）再比上下界**；`x < lo or x > hi` 不构成完整数值校验。

- **落地含义**：
  - NaN 与任何数比较皆为假，`inf` 同理；纯上下界比较会把 NaN / inf 放进识别 / 判定链路。
  - 配置文本推断数值类型时同样：非有限值不认作 float，落回字符串语义。
  - 验收必须带「注入 NaN / inf 必须被判非法」的具体断言，不能只测正常值与两个边界值。
- **影响阶段**：2026-11-15 全模块整改（非编号阶段）；后续所有涉及配置 / 协议 / 数值判定的阶段沿用。
- **生效日期**：2026-11-15。
- **来源**：用户 2026-11-15 沉淀指令（明确列明本条）+ 代码读盘核实（`infra/roi_binding_loader.py::parseConfidence`、`infra/config_manager.py` 的 `math.isfinite`）。
- **禁止**：用纯上下界比较充当完整数值校验；让 NaN / inf 被当成合法数值参与业务判定；数值断言只覆盖正常值与边界值。

## D-20 删除断链补报功能（2026-11-16 用户裁决）

**裁决**：用户与测试沟通后确认，边缘计算机不需要断链暂存与恢复补报能力；**删除 `EventCache` 整套机制**；断链期间**不缓存**待上报事件，链路恢复后**不补发**。

- **落地含义**：
  - 不设补发开关、不建缓存队列；原 `control/event_cache.py` 与 `EdgeControl.onLinkDown` 中的「开 EventCache」职责一并删除。
  - **D-03 中「按 `enabled` 补发/丢弃」部分随之作废**；「`seq` 只填不用」因 `seq` 字段随缓存队列删除而自然消失，不再保留。
  - `onLinkDown` 统一决策收敛为「停心跳 / 停解码 / 启重连」，不再触发任何缓存或补发动作。
  - 心跳失败去重仍按 L1 的 `transitionTo` 返回值处理，与本裁决不是同一件事。
- **影响阶段**：`d`（追加变更说明，不改历史证据）、`dplus`。
- **生效日期**：2026-11-16。
- **来源**：用户 2026-11-16 裁决（与测试沟通后确认删除断链补报能力）；代码 / 测试 / SRS / L1 口径已同步。
- **禁止**：以「历史阶段曾验收 EventCache」为由恢复补发或缓存队列；改动任何已签字阶段的历史证据文件（含 `stages/d/test-report.md`、`stages/d/verification-evidence.md`、`HANDOFF-d.md`、`dplus/handoff.md`）。

## 裁决变更协议

1. 只有用户能新增、修改或撤销裁决；助手不得自行推断出「第四条裁决」。
2. 新裁决分配下一个编号 `D-xx`，写明：裁决内容、冲突来源、落地含义、影响阶段、禁止事项、生效日期。
3. 同步更新：本文件 → 项目记忆（跨会话有效）→ 受影响阶段的 handoff / 开工清单。
4. 裁决与 L1 冲突时**不改 L1**：输出 diff + 影响面，等用户明确批准后才落地。
5. 每次阶段开工复核本文件中相关裁决是否被绕过；收尾在 handoff 中逐条记录落实情况。
6. **本轮新增 D-04 ~ D-11（2026-11-14）的适用阶段一律为 `c4plus` / `c5plus` / `dplus`**；
   `D-04`~`D-10` 已落地，`D-11` 的具体追认待用户下达。
7. **2026-11-14 第三轮新增 D-12 ~ D-16**（生产必须装载 ROI 对照表 / 推理后端默认固定 ultralytics /
   对照表 `worker_id` 不得超限 / 从未打开的相机一律 offline / 识别背压需有丢弃计数与抽样日志）：
   适用阶段同为 `c4plus` / `c5plus` / `dplus`，**均已在工作区落地**（代码 + 用例），
   但**状态仍为 `in_progress`（待用户确认）**，最终 review 结论只由用户本人签字。
8. **2026-11-15 全面代码检查与整改新增 D-17 ~ D-19**（构造注入的上限仍须受协议硬顶 /
   停机不得触发重连 / 数值校验必须 `math.isfinite`）：由用户 2026-11-15 沉淀指令明确列明这三条并指定登记
   D-17 起、生效日期 2026-11-15，属**禁令型运行期红线**，影响阶段为「全模块整改（非编号阶段）+ 后续上板沿用」。
   三条与 D-01 ~ D-16 逐条比对**均不重复**（D-18 与 D-02 是断链 / 停机两条不同路径，已写明边界）。
   已同步 `references/lessons.md` L-21 / L-23 / L-22、项目记忆 `edge_runtime_hardening.md` 与 `edge_quality_campaign.md`；
   **按用户本轮边界未改 handoff / STAGE-STATE / 开工清单、不推进阶段状态、不代用户签字**。

## L1 定稿决策指针（不复制全文）

以下条目以 `edge/docs/spec/整体重构方案.txt` §1 为唯一权威，本文件只列条目名，便于开工索引：
目标环境 / Python 与类型标注 / 命名 / 注释 / 异常 / 单例 / 日志 / 进程锁 / NPU 并发 /
补发去重 / 部署 / 摄像头寻址 / `.so` / 引导文件。
阶段与目录定义见同文件 §2、§5；编码细则见 `edge/docs/spec/编码规范规则.txt`。

## 待裁决登记（c3 阶段登记，本轮不落地）

> 以下条目于 c3 开工经用户拍板「只登记、不落地、归指定阶段」，非 D-xx 裁决；落地前仍按现有实现与 L1 执行。

1. **EventCache 存废**：c3 不实现、不预留；归属阶段 **d**（`control/` + `event_cache.py`，按 `整体重构方案.txt` §5 落地）。
2. **错放判定归属**：帧内容是否「错放」的业务判定不在 tcp/ 做；归属阶段 **c5**（识别模块组装 ack 前校验）。
3. **`camera_status` 空接口默认值 + 「连丢 5 条周期帧判离线」**：两者均属**上位机侧判定**；`camera_status` 在 c3 出网心跳帧中按协议键名占位、默认值留待 c5/d 定义，**tcp/ 不混入 `linkState` 判定逻辑**；「连丢 5 条周期帧判离线」归 **c4/d**（采集/控制侧），与 `TcpControlLayer.linkState` 的 UP/DOWN 状态机严格区分、互不混淆。

## 附录 A — L1 契约变更基线（2026-11-10 用户批准，非新裁决）

> 本节是**用户 2026-11-10 明确指令**下登记的基线记录，**不是新的 D-xx 裁决**；D-01 / D-02 / D-03 不变，裁决变更协议「助手不得自行推断第四条裁决」继续有效。
> 用途：作为后续阶段 `contract-guard` 开工 / 收尾核验的**对比基线**，避免每阶段对同一已批准变更重复判定「未批准 / 自动修改」。

### A.1 生效与批准

- **生效日期**：2026-11-10（阶段 `a` 收尾）。
- **来源**：用户 2026-11-10 指令「批准这份 diff，落地执行……」及「收尾时把『首次经用户批准的 L1 变更』登记进 decisions.md 与 handoff，作为后续 baseline 对比依据，避免每阶段重复判定」。
- **流程**：先输出完整 diff（变更前后 + 影响面 + 受影响测试/Fake）→ 停下等批准 → 用户明确批准后落地 → 落地后立即实跑 mypy / ruff / pytest 三项并给真实输出 → 收尾登记 baseline。硬要求「不得自动修改 L1；契约变更必须给 diff 并等用户批准」已遵守。
- **基线 tag**：`stage-a-done`（annotated）。

### A.2 唯一已批准变更

- 文件：`edge/tests/contract/test_phase0_foundation.py`（L1 契约层 `edge/tests/contract/*`）。
- 内容：新增 `from collections.abc import Callable` / `from typing import cast`；新增 typed 装饰器 wrapper `windowsOnly(reason: str) -> Callable[[Callable[[], None]], Callable[[], None]]`（`cast` 包装 `pytest.mark.skipif`，条件 `os.name != "nt"` 与 reason 原样保留）；两处 `@pytest.mark.skipif(os.name != "nt", reason="仅 Windows 验证")` 改为 `@windowsOnly("仅 Windows 验证")`。
- 约束：既有 5 个 `testXxx` 用例函数体与断言零改动；`edge/pyproject.toml` 零改动；不删用例、不加 skip 标记、不整体关闭错误码、不为变绿改被测实现。
- 完整 diff：`edge/docs/refactor/HANDOFF-a.md` §4（逐行 `-` / `+` 原文）。
- 工具链证据：落地后立即实跑 mypy `Success: no issues found in 29 source files`、ruff `All checks passed!`、pytest `22 passed in 0.29s`；收尾复核 mypy `Success: no issues found in 30 source files`、ruff `All checks passed!`、pytest `33 passed`（退出码均 0）。阶段 0 报告的 mypy 历史失败不倒改、不洗绿。

### A.3 基线使用口径

1. 后续阶段 `contract-guard` 以 tag `stage-a-done` + 本附录 + `HANDOFF-a.md` §4 为对比基线：该文件相对此基线的**新增**改动才需要重新走 diff + 批准流程；基线中已批准的变更不再判为「未批准 / 自动修改」，也不重复输出「等待批准」或把收尾转为 `blocked`。
2. 其余 L1 契约层文件（`整体重构方案.txt` / `编码规范规则.txt` / `编码规范.mdc` / `interfaces/*.py` / `exceptions.py` / `pyproject.toml` / `tests/contract/*` 其余文件）与 `edge/docs/spec/**` 原文 / PNG 仍保持零自动变更；任何新增契约变更必须先给完整 diff 并等用户明确批准。
3. 本附录不改动 D-01 / D-02 / D-03 的内容、影响阶段与禁止事项；不分配新裁决编号。
4. 若用户后续撤销或变更本基线，须按「裁决变更协议」由用户明确下达，并同步本附录、handoff、项目记忆与 `STAGE-STATE.md`。
