# 边缘计算机：识别配置持久化 + USB 对焦 方案提案

> 本文档为配置期提案（L4 状态资产），描述"USB 视频流 → 切割合并 → 识别 → 本地对照表匹配"的全新业务流，
> 以及 ROI↔位置↔标志 强绑定关系的轻量持久化方案、USB 自动/手动定焦设计。
> 代码实现需在配置期解除后，按阶段门禁落地，不在本文档范围内（本文档不写 .py）。

## 0. 需求解码（来自袁总语音口误还原）

| 语音原文 | 真实含义 |
| --- | --- |
| ai 文件 | **ini 文件**：所有标量配置落到 `config.ini` |
| 买烧烤 | **MySQL**：明确**不使用**重量级数据库 |
| 建筑队的对应关系 | **映射/绑定关系**：位置↔类型、ROI↔标志 的强绑定 |
| 100 个 loi | **100 个 ROI 区域**（每个抽屉/货位一组 ROI） |
| 切割合并识别 | 从视频流**切出各 ROI 区域** + 多路/多帧**合并**后送识别 |
| 自由化的 Excel | 对照关系表用**轻量表格式**持久化（CSV/Excel 均可读可改） |

## 1. 配置持久化方案（推荐）

### 1.1 总原则

- **标量参数** → `config.ini`（沿用现有 `IniConfigManager`，符合"配置从 ini 读取后注入"铁律）。
- **对照关系表**（表格型、强绑定、需业务/新人可改） → **CSV 文件**（零依赖、Git 可追踪、Excel 可直接打开编辑）。
- **不使用 MySQL**（您明确要求）。CSV 是"轻量且易持久化"的最佳折中：纯 Python `csv` 模块读写，业务人员用 Excel 改完直接保存，无第三方重依赖，RK3588 上也零负担。

### 1.2 文件布局

```
edge/
  config.ini                 # 标量：摄像头索引、对焦模式/位置、识别超时、阈值、CSV 路径
  config/
    roi_binding.csv          # ROI↔位置↔标志 强绑定主表（单一事实来源）
```

`config.ini` 新增小节（示例）：

```ini
[usb]
camera_pairs = 4
focus_mode = fixed          ; auto | fixed
focus_position = 0.0        ; 归一化焦点位置，开机自动定焦到此
capture_dirs = ./capture
recognition_dirs = ./recog

[recognition]
infer_timeout_sec = 3.0
roi_binding_csv = ./config/roi_binding.csv
```

### 1.3 `roi_binding.csv` 表结构（核心）

两个关系（ROI→位置→类型、ROI→标志）是**强捆绑**，合并为一张表，避免两张表 drift：

| 列 | 含义 | 示例 |
| --- | --- | --- |
| `roi_id` | ROI 区域唯一标识 | `roi_001` |
| `drawer_id` | 所属抽屉/货位组 | `A-01` |
| `position` | 该 ROI 对应的物理位置（与整机位置格式一致 `A-01-02`） | `A-01-02` |
| `required_type` | 该位置**必须存放**的工具类型 | `9#开口扳手` |
| `marker_id` | 该 ROI 内由训练得到的**特殊标志**标识 | `mk_8821` |
| `confidence` | 标志匹配置信度下限（可选） | `0.85` |

> 强绑定含义：`roi_id` 同时锁定"它对应哪个物理位置 + 该位置该放什么类型 + 它内部的特殊标志是什么"。
> 三者任一变更都必须同表同行修改，杜绝"位置改了标志没改"的不一致。

### 1.4 为何不用 MySQL / 不用 JSON

- **MySQL**：重量级、需服务、需建表建视图、边缘机无必要；您已明确排除。
- **JSON**：表格型数据用 JSON 数组表达，业务人员手写易错、Diff 不友好、Excel 打不开。
- **CSV**：表格天然形态、Excel 原生可读写、Git 行级 diff、零依赖。被选为持久化事实来源。

## 2. 业务流程图（SVG）

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640" font-family="Microsoft YaHei, sans-serif">
  <defs>
    <linearGradient id="node" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#3a6ea5"/><stop offset="1" stop-color="#284e75"/>
    </linearGradient>
    <linearGradient id="gray" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#9aa7b8"/><stop offset="1" stop-color="#7a8aa0"/>
    </linearGradient>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6 Z" fill="#444"/>
    </marker>
    <style>
      .box{fill:url(#node);stroke:#1f3a5a;stroke-width:1.5;rx:10;ry:10;}
      .gbox{fill:url(#gray);stroke:#5a6a7a;stroke-width:1.5;rx:10;ry:10;}
      .t{fill:#fff;font-size:13px;text-anchor:middle;dominant-baseline:central;}
      .edge{stroke:#444;stroke-width:1.5;fill:none;}
    </style>
  </defs>

  <!-- 列1: 上位机 -->
  <rect class="box" x="30" y="270" width="150" height="60" rx="10"/>
  <text class="t" x="105" y="300">上位机下发</text>
  <text class="t" x="105" y="300" font-size="0"></text>
  <text class="t" x="105" y="285">上位机下发</text>
  <text class="t" x="105" y="305">recognize_req</text>

  <!-- 列2: EdgeControl -->
  <rect class="box" x="230" y="270" width="150" height="60" rx="10"/>
  <text class="t" x="305" y="285">EdgeControl</text>
  <text class="t" x="305" y="305">routeSignal</text>

  <!-- 列3: USB 拉流 -->
  <rect class="box" x="430" y="120" width="160" height="60" rx="10"/>
  <text class="t" x="510" y="135">UsbController</text>
  <text class="t" x="510" y="155">startCapture(reqId)</text>
  <rect class="box" x="430" y="200" width="160" height="60" rx="10"/>
  <text class="t" x="510" y="215">4 路摄像头</text>
  <text class="t" x="510" y="235">视频流 grab</text>

  <!-- 列4: 切ROI+合并 -->
  <rect class="box" x="430" y="300" width="160" height="60" rx="10"/>
  <text class="t" x="510" y="315">切 ROI 区域</text>
  <text class="t" x="510" y="335">+ 多路合并帧</text>

  <!-- 列5: 识别 -->
  <rect class="box" x="630" y="300" width="160" height="60" rx="10"/>
  <text class="t" x="710" y="315">Recognition</text>
  <text class="t" x="710" y="335">trigger+Yolo</text>

  <!-- 列6: 查表匹配 -->
  <rect class="box" x="630" y="400" width="160" height="60" rx="10"/>
  <text class="t" x="710" y="415">查 roi_binding.csv</text>
  <text class="t" x="710" y="435">ROI→位置→类型→标志</text>

  <!-- 列7: 回包 -->
  <rect class="box" x="630" y="510" width="160" height="60" rx="10"/>
  <text class="t" x="710" y="525">EdgeControl</text>
  <text class="t" x="710" y="545">enqueue+dispatch</text>

  <rect class="box" x="830" y="510" width="110" height="60" rx="10"/>
  <text class="t" x="885" y="540">TCP 发</text>
  <text class="t" x="885" y="540" font-size="11">recognize_ack</text>

  <!-- USB 对焦 旁路 -->
  <rect class="gbox" x="430" y="20" width="200" height="60" rx="10"/>
  <text class="t" x="530" y="35">开机定焦(灰=待上板)</text>
  <text class="t" x="530" y="55">applyFixedFocus()</text>
  <text class="t" x="530" y="55" font-size="10">读 config.ini[usb]focus_position</text>

  <!-- 配置持久化 底栏 -->
  <rect class="gbox" x="430" y="580" width="320" height="40" rx="8"/>
  <text class="t" x="590" y="600" font-size="11">持久化：config.ini(标量) + roi_binding.csv(对照表)</text>

  <!-- 连线 -->
  <path class="edge" d="M180,300 H230" marker-end="url(#arrow)"/>
  <path class="edge" d="M380,300 V285 H430" marker-end="url(#arrow)"/>
  <path class="edge" d="M510,180 V200" marker-end="url(#arrow)"/>
  <path class="edge" d="M510,260 V300" marker-end="url(#arrow)"/>
  <path class="edge" d="M590,330 H630" marker-end="url(#arrow)"/>
  <path class="edge" d="M710,360 V400" marker-end="url(#arrow)"/>
  <path class="edge" d="M710,460 V510" marker-end="url(#arrow)"/>
  <path class="edge" d="M790,540 H830" marker-end="url(#arrow)"/>
  <path class="edge" d="M530,80 V120" marker-end="url(#arrow)" stroke-dasharray="4"/>
</svg>
```

**流程要点**：上位机 `recognize_req` → `EdgeControl.routeSignal` → `UsbController.startCapture(reqId)` 拉起 4 路视频流 → 每路**切出 ROI 区域 + 多路合并帧** → `RecognitionController.trigger(workerId, frame, reqId)` 跑 YOLO → 空间归集后**查 `roi_binding.csv`**（ROI→位置→类型→标志）→ 比对出全柜实况 → `enqueueFrame` → `dispatchOutbox` → TCP 回 `recognize_ack`。USB 定焦在开机时旁路完成。

## 3. USB 对焦设计

| 项 | 设计 |
| --- | --- |
| 自动对焦（已有） | `UsbCameraDevice` 维持自动对焦能力 |
| 手动定焦 | 新增 `setManualFocus(position: float)` / `fixFocus(position: float)` |
| 开机定焦 | 新增 `applyFixedFocus()`：构造后读 `config.ini[usb].focus_position`，调用 `fixFocus` 锁死焦点 |
| 配置 | `[usb] focus_mode = auto\|fixed`、`focus_position = 0.0`（归一化或步进，待上板定标） |
| 平台差异 | Windows（DirectShow）与 Linux/RK3588（v4l2/UVC）对焦指令不同 → 收敛到 `IPlatformAdapter`/设备层，主流程不感知 |
| 状态 | 上板前 Windows 侧先留 `NotImplementedError` + TODO 骨架（符合"平台差异收敛到适配层"铁律） |

## 4. 识别流改造（相对现有 placeholder 实现）

现有 `app_init.placeholderFrames` 是从磁盘读图占位；上板目标改为**从 USB 视频流直接取帧**：

1. `UsbCaptureWorker` 由"采图落盘"改为"采图 → 回调 `onFrameCaptured(workerId, frame)`"直接把帧交给识别，减少磁盘 IO。
2. 新增**切 ROI + 合并**环节：按 `RoiConfig`（由 `roi_binding.csv` 注入）从帧中裁出各 ROI 区域，多路帧合并为一次识别输入。
3. `RecognitionController.trigger(workerId, frame, requestId)` 入参由"路径"改为"帧对象"，`RecognitionWorker` 跑 YOLO → 空间归集 → **查 `RoiBindMap`**（已由 CSV 装载）。
4. 比对结果（位置是否放对类型、标志是否匹配）组装 `recognize_ack`。

> 注意：现有 `RoiBindMap` / `ClassItemMap` / `RoiConfig` 类型已存在于 `recognition_utils`，本方案只把它们的**数据来源从 `config.ini` 切换到 `roi_binding.csv`**，类型与接口不动，改动面小。

## 5. 模块 API 设计（对齐 L1 camelCase 契约）

| 模块 | 新增/改造 | 方法（camelCase） |
| --- | --- | --- |
| `UsbCameraDevice` | 改造 | `setManualFocus(pos)` / `fixFocus(pos)` / `applyFixedFocus()` / `focusMode`(构造注入) |
| `UsbController` / `UsbCaptureWorker` | 改造 | 流式帧回调 `onFrameCaptured(workerId, frame)`，替代落盘读图 |
| `RecognitionController` | 改造 | `trigger(workerId, frame, requestId)` 入参改帧 |
| `RoiBindingLoader`（新增，infra/util） | 新增 | `load(csvPath) -> RoiBindMap` 读 CSV 装配已有类型 |
| `IniConfigManager` | 改造 | 新增 `[usb]` / `[recognition]` 小节读取 |

所有新增标识符遵守：类 `PascalCase`、方法/变量 `camelCase`、常量 `UPPER_SNAKE_CASE`、文件 snake_case 全局唯一。

## 6. 新人可维护性要点

- **单一事实来源**：`roi_binding.csv` 一处改全链路生效，禁止在代码里硬编码位置/类型/标志。
- **配置与代码分离**：所有可调参数（焦点、超时、ROI 绑定）全在 `config.ini` / `roi_binding.csv`，新人改配置不动代码。
- **强绑定同行**：ROI 的位置、类型、标志写在 CSV 同一行，避免跨表不一致。
- **注释三要素**：每个函数 `@brief` / `@param` / `@return`，白话无黑话，禁止历史痕迹（遵守袁总注释铁律）。
- **平台差异收敛**：对焦/摄像头指令只在设备层与 `IPlatformAdapter`，主流程零 `sys.platform` 判断。

## 7. 实施分阶段建议（受配置期门禁约束）

本提案超出原 9 阶段（0~d）范围，建议作为**新增阶段**落地，且必须在配置期解除后：

| 新阶段 | 交付范围 |
| --- | --- |
| `c4+` USB 对焦 | `UsbCameraDevice` 对焦方法 + `config.ini[usb]` + 开机定焦 |
| `c5+` 流识别 | 流式帧回调 + 切 ROI/合并 + `trigger(帧)` + CSV 装载 `RoiBindMap` |
| `d+` 配置持久化 | `roi_binding.csv` 读写 + `RoiBindingLoader` + 路由接通识别比对 |

> 落地前须先解决既有 stage d 已发现的生产路径断点（`dispatchOutbox` 未调用、`startCapture` 未接线、`routeSignal` 未路由 `recognize_req`），否则新流程仍跑不通。

---
*本文档为提案（L4），不修改任何 L1 契约与现有代码；代码实现待配置期解除并按阶段门禁执行。*
