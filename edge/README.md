# 边缘机启动与配置说明

本文件是边缘机（智能工具柜上位机的边缘侧）的**开机手册**。
现场只需要看这一份：怎么启动、配置改哪里、怎么看周期帧在发、出问题怎么办。

---

## 一、先讲清楚一件事：边缘机没有图形界面

**边缘机是后台服务进程，没有 GUI，也没有"启动按钮"。**

上位机那侧才是带界面的程序。边缘机这边一旦进程起来，它就在后台持续运行，
按固定周期（默认 3 秒）往上位机发一帧 `periodic` 周期帧，
上位机靠这帧判断"边缘机还活着"，并用帧里的 `camera_status` 做开柜闸门。

所以"看不到界面"是**设计如此，不是故障**。判断边缘机是否正常，看两处：

| 看什么 | 怎么看 | 正常表现 |
| --- | --- | --- |
| 进程是否活着 | 任务管理器 / `tasklist` | 有 `python.exe` 进程在跑 |
| 周期帧是否在发 | 上位机侧收帧 / 本文第五节的观察工具 | 每 3 秒一帧 `periodic` |

---

## 二、两种启动方式

### 2.1 方式一：双击 `edge/run_edge.bat`（推荐现场用）

1. 双击 `edge\run_edge.bat`。
2. 弹出的黑色窗口里会先打印工作目录、配置文件位置、日志目录。
3. 窗口**不要关**，它就是边缘机进程本体；关窗口等于停机。
4. 要停机，在这个窗口里按 `Ctrl+C`。

脚本做了两件关键事：

- 自动 `cd /d "%~dp0.."` 切到**仓库根目录**（`import edge` 需要仓库根在模块搜索路径里）；
- 执行 `python -m edge.main` 拉起边缘机。

前置条件：命令行里有 `python`（Python 3.9 或以上）。脚本会先检查，
没有就提示装 Python 并退出。

### 2.2 方式二：命令行启动

**必须在仓库根目录执行**（`edge/` 的上一级）：

```
cd d:\CFDZ\BYJSJ\New-SmartCabinet
python -m edge.main
```

如果确实要在 `edge/` 目录里跑，需要把仓库根加进模块搜索路径：

```
cd d:\CFDZ\BYJSJ\New-SmartCabinet\edge
set PYTHONPATH=d:\CFDZ\BYJSJ\New-SmartCabinet
python -m edge.main
```

两种方式的**配置查找结果完全一致**：配置文件永远按"边缘机工程目录"定位，
不随你在哪个目录敲命令而变。

> `python edge\main.py` 这种写法**不行**：脚本目录会成为模块搜索路径首位，
> 找不到 `edge` 包，报 `ModuleNotFoundError: No module named 'edge'`。

---

## 三、配置文件在哪儿、每个键什么意思

主配置：`edge/config/config.ini`。
同目录下还有两个 CSV（`roi_binding.csv` 识别台账、`class_item_map.csv` 类别组合表），
它们的字段含义见 `edge/config/README.md`。

**配置文件自身**固定在工程目录内的 `edge/config/config.ini`，从仓库根启动还是从
`edge/` 目录启动，读到的都是同一份文件，不受启动时工作目录影响。

配置文件里写的**相对路径**（日志目录、落盘目录、对照表路径）按下面的顺序查找已存在的位置：

1. 运行时工作目录；
2. 边缘机工程目录（`edge/`）；
3. 仓库根目录；
4. 三处都没有时按 `edge/` 给出待创建位置，运行目录由程序启动时自动建。

第 1 项就是工作目录，所以工作目录下若恰好有同名目录，会优先用工作目录下的那个；
这是现场排查日志落在哪一路时要先看的一处。`dir = ./logs` 在默认启动方式
（`run_edge.bat` 切到仓库根）下落在本表第 1 项，也就是仓库根下的 `logs/`。

### 3.1 `[tcp]` 链路与周期帧

| 键 | 当前值 | 含义 |
| --- | --- | --- |
| `host` | `127.0.0.1` | **上位机**的地址。边缘机是客户端去连，上位机是服务端监听这个端口 |
| `port` | `9000` | 上位机监听端口，改成现场上位机实际监听的端口 |
| `connect_timeout_sec` | `5.0` | 连上位机的超时秒数，超时按退避序列重连 |
| `recv_timeout_sec` | `0.5` | 单次收包超时秒数。超时是正常轮询节拍，不算断链 |
| `max_frame_size` | `1048576` | 单帧字节上限，超限的坏帧丢弃并记日志 |
| `safe_frame_limit_bytes` | `524288` | 出网单帧安全阈值字节数，只裁剪清单不触发断链 |
| `backoff_seq` | `1,2,4,8,16,30` | 断链重连退避序列，单位秒 |
| `heart_interval_sec` | `3` | **周期帧发送间隔**，默认 3 秒 |

### 3.2 `[log]` 日志

| 键 | 当前值 | 含义 |
| --- | --- | --- |
| `dir` | `./logs` | 日志目录，程序自动创建。文件名形如 `ALL_20261114_0001.log` |
| `max_file_size` | `1048576` | 单个日志文件字节上限，超限滚动 |
| `mode` | `1` | `1` 合并成一个文件，`0` 按类型分开（`RX` / `TX` / `INFO` / `ERROR` 四个文件） |
| `disk_free_threshold` | `0.3` | 剩余空间低于该比例时删除最旧日志文件，保留最新文件 |
| `queue_poll_sec` | `0.2` | 日志消费线程的取队列超时秒数 |

### 3.3 `[usb]` 采集与相机

| 键 | 当前值 | 含义 |
| --- | --- | --- |
| `save_dirs` | `./output/capture/w1..w4` | 4 组采集线程各自的落盘目录，程序自动创建 |
| `roll_threshold` | `0.3` | 落盘目录占用比例超阈值就删旧图 |
| `camera_indices` | `1,2,3,4,5,6,7,8` | 相机索引列表，**顺序即物理编号**，左路在前右路在后 |
| `capture_mode` | `auto` | 采集模式：`auto` 按 `camera_indices` 个数自动判（1 路单摄不拼接、偶数路双摄两两拼接、奇数路 ≥3 报错）；`single` 强制单摄，每个索引各成一组；`dual` 强制双摄，要求偶数且至少 2 路 |
| `layer_mode` | `multi` | 分组方式：`multi` 按 `camera_indices` 实际路数分组（8 路 = 4 个 worker）；`single` 只取前 2 路 = 1 个 worker，供单层工装测试 |
| `save_frames` | `false` | 采集帧是否逐路落盘：生产口径 `false`（只走内存回调、不写图）；调试期设 `true` 存单图。关闭时不要求采集目录存在。旧配置若没有此键，按关闭处理（生产口径） |
| `focus_mode` | `fixed` | `fixed` 锁定焦点，`auto` 自动对焦。**在相机打开成功之后下发**，见下方说明 |
| `focus_positions` | `0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0` | 8 路逐路焦点值，按 CAM1~CAM8 顺序、逗号隔开，**第 N 个值对应 CAM N**。填 1 个值表示 8 路共用；单位设备绝对值（上限 125），用 `lab/manual_focus_test.py --device N` 逐路实测 |
| `zoom_positions` | `0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0` | 8 路逐路变焦值，顺序与下标规则同上；上限 1020，同样逐路实测 |
| `focus_stable_ms` | `200` | 定焦下发后等镜头稳定的毫秒数；程序内部转成秒传给可打断等待，收到停机指令立即返回 |

> **对焦什么时候生效**：定焦指令是**相机打开成功之后**才下发的。
> 上位机发起一次扫描、采集线程把相机打开的那一刻，程序才给 8 路相机逐路下发
> `focus_positions[N]` / `zoom_positions[N]`（N = 路号 − 1）；开机时相机还没打开，
> 对焦指令必然下不去，所以程序**不在启动期下对焦**。四组相机全部就绪才统一下发，
> 下发后等 `focus_stable_ms` 毫秒让镜头稳定，再取首帧——定焦不占用识别时间窗。
>
> **下标铁律**：第 N 个配置值对应 CAM N。CAM5~8 虽在 worker 内是第二路，
> 但取值用第 5~8 个值，绝不能按 worker 内下标 0/1 取，否则会拿到 CAM1~4 的值。
>
> 下发结果只记**一条**汇总日志：成功是 `8 路相机对焦已下发，模式 fixed`，
> 失败是 `8 路相机对焦未生效：原因`，不会逐路刷屏。
> 相机没打开导致的下发失败会在汇总原因里写明是哪几路。

### 3.4 `[recognition]` 识别

| 键 | 当前值 | 含义 |
| --- | --- | --- |
| `save_dirs` | `./output/recog/w1..w4` | 4 组识别线程各自的目录，程序自动创建 |
| `save_panorama` | `false` | 是否存拼接后的全景大图：生产口径 `false`（只在内存识别、不写图）；调试标定设 `true`，把每组全景写进对应识别目录，供人工标 ROI |
| `model_path` | `./weights/yolov8n.rknn` | 模型权重路径（正式交付为 RKNN 量化权重） |
| `infer_timeout_sec` | `3.0` | 单次推理超时上限 |
| `roi_binding_csv` | `./config/roi_binding.csv` | ROI 对照表路径 |
| `require_roi_binding` | `true` | **是否强制装载 ROI 对照表**，见下一节 |
| `aggregation_timeout_sec` | `5.0` | 一次全柜扫描的聚合等待上限，超时按降级出帧 |
| `inference_backend` | `rknn` | 推理后端；正式交付固定 RKNN，换后端需重新标定 |
| `nms_iou_threshold` | `0.45` | 同类别非极大值抑制的重叠阈值 |
| `min_confidence` | `0.85` | 置信度门槛，单一来源；roi_binding.csv 每行 confidence 可覆盖 |
| `recognition_mode` | `crop` | 识别模式：`stitch`=左右拼全景推理一次（原口径）；`crop`=每路按比例裁剪后独立识别（8 路单摄配套） |
| `crop_cam1` | `0.10,0.00,1.00,1.00` | CAM1 裁剪矩形，归一化 0~1（x1,y1,x2,y2，相对该路画面）；`0,0,1,1`=全图不裁 |
| `crop_cam2` | `0.00,0.00,0.30,1.00` | CAM2 裁剪矩形，含义同上；键缺省=全图不裁 |
| `crop_cam3` | `0.00,0.00,1.00,1.00` | CAM3 裁剪矩形，含义同上 |
| `crop_cam4` | `0.00,0.00,1.00,1.00` | CAM4 裁剪矩形，含义同上 |
| `crop_cam5` | `0.10,0.00,1.00,1.00` | CAM5 裁剪矩形，含义同上 |
| `crop_cam6` | `0.00,0.00,0.30,1.00` | CAM6 裁剪矩形，含义同上 |
| `crop_cam7` | `0.00,0.00,1.00,1.00` | CAM7 裁剪矩形，含义同上 |
| `crop_cam8` | `0.00,0.00,1.00,1.00` | CAM8 裁剪矩形，含义同上 |
| `dedup_strategy` | `best_confidence` | 汇总去重策略：`first`=重复货位保留首条（原口径）；`best_confidence`=同货位取置信度高者 |

### 3.5 `require_roi_binding`：识别清单给不出来怎么办

**现场识别清单暂时给不出来时，把 `require_roi_binding` 保持为 `false`。** 此时：

- 对照表缺失或为空 → **不阻断启动**，记一条 error 级日志
  `识别能力不可用：未装载 ROI 对照表`，进程照常起来；
- 周期帧**照发**，`camera_status` 如实反映相机在位情况；
- 收到识别请求 → 立刻回一帧 `{"type":"recognize_ack","request_id":"...","items":[]}`，
  上位机马上弹"识别清单为空/覆盖不全"告警，**不用干等 3 秒 × 3 次重发、9 秒后才报超时**。

正式上线、要求"必须带完整台账上线"时，把它改成 `true`：
装载不到对照表就**启动即失败**，防止带病运行。

> `camera_status` 一律如实上报。没打开的相机报 `offline`，不会为了让上位机放行开柜而报 `ok`。

### 3.6 上位机下发的指令与边缘机回应

当前边缘机链路**只注册 `recognize_req` 一种下行请求**，收到即回 `recognize_ack`：
一次请求只回一帧，清单覆盖全部已登记货位。
**不回应的后果是上位机等满 3 秒 × 3 次重发后报超时**，界面上的功能等于不可用。

`open_req` / `open_ack` 尚未在边缘机链路中落地：未注册的信号只记一条日志、不回应。
开柜与 IO 板状态由上位机侧处理，不在本软件的职责范围内。
出网帧只有 `periodic` 与 `recognize_ack` 两种。

---

## 四、日志在哪、怎么看

- 目录：`logs/`（仓库根下），文件名形如 `ALL_20261114_0001.log`；
- 一行一条 JSON，字段是 `type`（`RX` / `TX` / `INFO` / `ERROR`）、`module`、`timestamp`、`payload`；
- 出错时 `stack` 字段带完整堆栈。

排查问题的三个关键字：

| 想找什么 | 搜什么 |
| --- | --- |
| 配置有没有读对 | `ROI 对照表装载完成`、`识别初始化完成` |
| 链路通没通 | `link UP`、`连接失败` |
| 识别能力在不在 | `识别能力不可用` |
| 哪几路相机没在位 | `相机打开失败`（消息里带相机索引） |
| 对焦有没有生效 | `对焦已下发`、`对焦未生效` |

---

## 四·补、外部交互日志怎么看（RX / TX）

边缘机与上位机之间收发的**每一帧**都会记一条日志，方向用大写 `RX` / `TX` 区分，模块名一眼看出方向：

| 记录 `type` | `module` | 含义 | 触发位置 |
| --- | --- | --- | --- |
| `RX` | `TcpRx` | 收到上位机下发的一整帧 | `edge/modules/tcp/tcp_decode_thread.py`：`recv` 到一整行、切帧并解析成功后记一条 |
| `TX` | `TcpTx` | 发给上位机的一整帧 | `edge/modules/tcp/tcp_comm.py` 的 `encodeFrame`：帧编成出网字节时记一条 |

- 周期帧（每 3 秒一帧 `periodic`）也是外部交互，会记 `TX`；它和 `recognize_ack` 都从 `encodeFrame` 这个唯一出网口出去，所以**一帧恰好一条 `TX`，不会重复**；入网一侧同理，一帧恰好一条 `RX`。
- 帧型不被上位机识别、被出网守卫拦下时不记 `TX`，另有一条 `ERROR` 写明拦截原因；坏帧、空行在解码侧只记 `INFO`，不硬凑成 `RX`。
- `payload` 里是**解析后的帧字典**，不是字节、不是十六进制，原样保留 `type` / `request_id` / `items` 等字段，另加 `frameBytes`（帧体字节数，不含行尾换行），便于排查帧大小。
- 每行一条单行 JSON，帧体里没有裸换行；只有出错时才多一个 `stack` 字段。

日志落在哪：

| `[log] mode` | `RX` 落到 | `TX` 落到 | `INFO` / `ERROR` 落到 |
| --- | --- | --- | --- |
| `1`（默认，合并） | `logs/ALL_20261114_0001.log` | 同一个 `ALL_*.log` | 同一个 `ALL_*.log` |
| `0`（按类型分文件） | `logs/RX_20261114_0001.log` | `logs/TX_20261114_0001.log` | `logs/INFO_*.log` / `logs/ERROR_*.log` |

两种模式下 `RX` / `TX` 都能落盘；文件名里的日期、流水号按天和滚动序号变化，前缀 `ALL` / `RX` / `TX` / `INFO` / `ERROR` 不变。

一行长什么样（真实日志原文，`mode=1`）：

```
{"type": "RX", "module": "TcpRx", "timestamp": "2026-11-14T22:44:28.730019", "day": "20261114", "payload": {"type": "recognize_req", "request_id": "req-real-io-0001", "timestamp": 1700000000001, "frameBytes": 87}}
{"type": "RX", "module": "TcpRx", "timestamp": "2026-11-14T22:44:28.733477", "day": "20261114", "payload": {"type": "recognize_req", "request_id": "req-real-io-0002", "timestamp": 1700000000002, "frameBytes": 87}}
{"type": "TX", "module": "TcpTx", "timestamp": "2026-11-14T22:44:28.826362", "day": "20261114", "payload": {"type": "recognize_ack", "request_id": "req-real-io-0002", "items": [{"position": "A-01-01", "tool_id": "", "confidence": 0.0, "alert_type": "unknown"}, {"position": "A-01-02", "tool_id": "", "confidence": 0.0, "alert_type": "unknown"}, {"position": "A-01-03", "tool_id": "", "confidence": 0.0, "alert_type": "unknown"}, {"position": "A-01-04", "tool_id": "", "confidence": 0.0, "alert_type": "unknown"}], "frameBytes": 370}}
{"type": "TX", "module": "TcpTx", "timestamp": "2026-11-14T22:44:31.744501", "day": "20261114", "payload": {"type": "periodic", "uptime_sec": 14, "software_version": "edge-0.1.0", "camera_status": [{"camera_id": "CAM1", "status": "offline"}, {"camera_id": "CAM2", "status": "offline"}, {"camera_id": "CAM3", "status": "offline"}, {"camera_id": "CAM4", "status": "offline"}, {"camera_id": "CAM5", "status": "offline"}, {"camera_id": "CAM6", "status": "offline"}, {"camera_id": "CAM7", "status": "offline"}, {"camera_id": "CAM8", "status": "offline"}], "frameBytes": 405}}
```

> 上面前两条是上位机下发的识别请求，第三条是识别应答，第四条是周期帧。`RX` 里的 `request_id` 与上位机下发完全一致，`TX` 应答里的 `request_id` 原样回带；用 `request_id` 一搜就能把一次请求的收帧和回帧对起来。周期帧那条每 3 秒出现一次，时间戳连起来看就知道链路一直活着。

大帧折叠规则（避免逐帧全量把日志撑大）：

- 阈值 **4096 字节**，常量是 `edge/modules/tcp/tcp_comm.py` 的 `IO_LOG_FULL_FRAME_BYTES`，调用方也可注入 `threshold`。
- `frameBytes` ≤ 阈值：`payload` 保留**帧的完整字段**；
- `frameBytes` > 阈值：`payload` 只留摘要——`type` / `request_id` / `itemsCount`（清单条数）/ `itemsPreview`（前 3 条）/ `frameBytes` / `folded: true` / `note`（"清单已折叠，日志仅保留前若干条摘要"），**不落完整清单**，但这条记录仍然是 `type: "TX"`，方向标识不丢。
- 100 货位的 `recognize_ack` 约 8KB，会触发折叠；周期帧每帧只有几百字节，保持全量记录。

100 货位大帧折叠后的真实日志原文：

```
{"type": "TX", "module": "TcpTx", "timestamp": "2026-11-14T22:45:36.757923", "day": "20261114", "payload": {"type": "recognize_ack", "request_id": "req-real-100", "itemsCount": 100, "itemsPreview": [{"position": "A-01-01", "tool_id": "C01-T0000", "confidence": 0.93, "alert_type": "none"}, {"position": "A-01-02", "tool_id": "C01-T0001", "confidence": 0.93, "alert_type": "none"}, {"position": "A-01-03", "tool_id": "C01-T0002", "confidence": 0.93, "alert_type": "none"}], "frameBytes": 8362, "folded": true, "note": "清单已折叠，日志仅保留前若干条摘要"}}
```

> `note` 里的"出网守卫日志"指 `TcpComm` 在出网口记的 `ERROR` 级日志（`单帧超安全阈值 ... 清单裁剪为 ...`、`上行帧型 ... 不被上位机识别`），以及上位机侧实际收到的完整帧。日志这边只留摘要，需要逐条核对清单时去这两处看。

排查示例：

| 想查什么 | 怎么搜 |
| --- | --- |
| 上位机说没收到应答 | 搜 `"module": "TcpTx"` 且 `request_id` 等于该请求；没有这条就是没出网，再看 `ERROR` 里的拦截原因 |
| 应答清单对不上 | 看该 `TX` 的 `frameBytes`：超 4096 会被折叠，`itemsCount` 是原始条数，逐条清单去出网守卫日志或上位机收帧处核对 |
| 链路是不是一直活着 | 搜 `"type": "periodic"` 的 `TX`，看时间戳是否每 3 秒一条 |
| 上位机到底发了什么 | 搜 `"module": "TcpRx"`，每条对应上位机下发的一整帧 |
| 帧大小异常 | 直接看 `frameBytes`，它不含行尾换行，与上位机按行切帧的口径一致 |

---

## 五、怎么看周期帧在发（联调观察工具）

工程里带了一个**桩上位机**，起在上位机该在的端口上，边缘机连上来后
逐帧打印收到的周期帧并统计到达节奏。

**第一步**：在仓库根目录起观察工具（它监听 127.0.0.1:9000，和 `config.ini` 的 `tcp.port` 一致）：

```
cd d:\CFDZ\BYJSJ\New-SmartCabinet
python -m edge.tests.integration.watch_periodic
```

输出长这样：

```
[观察] 桩上位机监听 127.0.0.1:9000
[观察] 等待边缘机接入；请在另一个窗口运行 edge/run_edge.bat
[观察] 边缘机已接入，开始接收周期帧
[19:22:05.191] periodic  距上帧 -  距上周期帧 -  CAM1=offline ... CAM8=offline
          原始帧 {"type": "periodic", "uptime_sec": 6, "software_version": "edge-0.1.0", "camera_status": [...]}
          上位机侧校验 通过，8 路 camera_status 齐全
[19:22:08.207] periodic  距上帧 3.00s  距上周期帧 3.00s  CAM1=offline ... CAM8=offline
[观察] 最近 10 秒收到 3 帧周期帧, 平均间隔 3.00 秒
```

**第二步**：另开一个窗口，双击 `edge\run_edge.bat` 启动边缘机。

**第三步**：看观察工具的输出。正常表现是**每 3 秒一帧 `periodic`**，
`camera_status` 覆盖 `CAM1` 到 `CAM8` 全部 8 路。

按 `Ctrl+C` 退出观察工具。

可选参数：

```
python -m edge.tests.integration.watch_periodic [端口] [观察时长秒] [req]
```

- 端口：默认 `9000`；
- 观察时长秒：默认 `0`，表示一直观察到 `Ctrl+C`；
- `req`：接入后额外发一帧识别请求，用来观察应答帧。

另有 `python -m edge.tests.integration.recognize_ack_probe`，
用真实 ROI 对照表加假引擎走一遍识别链路，打印一帧带清单的应答，供协议联调核对。

---

## 五·补、用笔记本内置摄像头联调

现场还没接 8 路相机、手边只有笔记本自带摄像头时，不用改代码，只改一行配置就能把采集链路跑起来。

**第一步：只改这一行**

打开 `edge/config/config.ini`，把 `[usb]` 段的 `camera_indices` 改成 `0`
（内置摄像头通常是索引 0），`capture_mode` 保持现场值不用动：

```ini
[usb]
camera_indices = 0
capture_mode = auto
```

`capture_mode = auto` 看到只有 1 路，会自动进**单摄模式**：这一帧不拼接、不裁半幅，
原图本身就是识别用的全景，4 个 worker 缩成 1 个 worker，落盘在 `edge/output/capture/w1/`。

**第二步：看周期帧**

`camera_status` 只报 1 路 `CAM1`，如实上报，不为了凑满 8 路而虚报：
相机打开成功就是 `ok`，没打开就是 `offline`。周期帧仍是每 3 秒一帧，其余字段和 8 路时一样。

**第三步：ROI 四角点要对得上**

`edge/config/roi_binding.csv` 里的四角点样例是按 **640×480** 标定的
（`rect_x2` 最大 640、`rect_y2` 最大 480）。单摄不拼接，全景就是这一帧原图，
内置摄像头恰好是 640×480 时四角点正好对得上；**换成别的分辨率要按新原图尺寸重新标定四角点**，
否则裁剪会越界或框错位置。对照表 4 行货位在单摄下会全部归一到 worker 1，
`recognize_ack` 的 `items[]` 仍是 4 条，货位不重复、不丢失。

**实测证据**（笔记本内置摄像头，`camera_indices = 0`）：

- 落盘 `edge/output/capture/w1/` 下的单摄图是 **40,618 字节真 JPEG**（占位 PNG 只有 925 字节），
  证明确实抓到了真帧而不是占位图；
- 周期帧里只有 `CAM1=ok` 一路，没有多余路数、没有报错；
- 周期帧间隔 **3.00 秒**一帧；一次联调里日志 `RX` 1 条、`TX` 7 条（含周期帧与 `recognize_ack`）。

> 落盘文件名里的后缀是逐轮递增的序号，持续采集时后一张不会覆盖前一张。

**回到现场 8 路**：把 `camera_indices` 改回下面这行即可，这是现场默认，别留着 `0` 上现场：

```ini
camera_indices = 1,2,3,4,5,6,7,8
```

---

## 六、常见故障

### 6.1 `ModuleNotFoundError: No module named 'edge'`

**原因**：不在仓库根目录跑。

**处理**：在仓库根目录执行 `python -m edge.main`；或直接双击 `edge\run_edge.bat`；
或在 `edge/` 目录跑时先 `set PYTHONPATH=<仓库根>`。

### 6.2 `[CONFIG] 配置文件缺失: ...；请在 edge/config/config.ini 配置`

**原因**：`edge/config/config.ini` 不存在，或配置路径被写成了绝对路径但指向别处。

**处理**：确认 `edge\config\config.ini` 在位。默认配置路径固定指向 `edge/config/config.ini`；
若换成相对路径，则按运行时工作目录 → `edge/` → 仓库根的顺序逐级查找，三处都没有才报这个错；
若换成绝对路径，则直接查这个绝对路径是否存在，不再回退到上面三级。

### 6.3 `[CONFIG] 已有实例运行，进程锁获取失败`

**原因**：已经有一个边缘机在跑。进程锁文件是 `edge_runtime.lock`，放在**启动时的工作目录**。

**处理**：先找到并停掉旧实例（任务管理器结束对应 `python.exe`，或在旧窗口按 `Ctrl+C`），
再启动新的。**不要**直接删锁文件，进程还在跑时删了也拦不住重复启动。

### 6.4 周期帧发不出去：上位机侧看不到帧

按顺序查：

1. 上位机有没有在 `tcp.host:tcp.port` 上监听？边缘机是**客户端**，上位机不监听就连不上；
2. 日志里有没有 `link UP`？没有就是没连上，日志里有 `连接失败` 和退避重试记录；
3. 日志里有没有 `识别能力不可用`？有的话是 ROI 对照表没装载，
   按 3.6 的口径处理；这**不影响**周期帧发送，只影响识别应答；
4. 防火墙有没有放行该端口。

### 6.5 `识别能力不可用：未装载 ROI 对照表`

**原因**：`roi_binding_csv` 指的路径没有表，或表只有表头没有数据行。

**处理**：现场联调口径保持 `require_roi_binding = false`，程序降级运行、周期帧照发；
生产上线口径改成 `true`，此时会启动即失败，逼着把台账补齐。

### 6.6 相机全是 `offline`

**原因**：相机没接好，或者 `camera_indices` 的取值与现场实际编号对不上。

**处理**：`camera_indices` 的**顺序**决定 `CAM1` 到 `CAM8` 的物理编号，
**取值**直接作为设备索引使用。现场按 1 起编号就填 `1..8`，
按 0 起编号就填 `0..7`，填错会一直报 `offline`。

### 6.7 `AttributeError: module 'platform' has no attribute 'python_implementation'`

**原因**：`edge/platform/` 这个包名与 Python 标准库 `platform` 冲突，从 `edge/` 目录启动时遮蔽了标准库。

**处理**：已彻底修复——该包重命名为 `edge/runtime_platform/`（类名 `PlatformFactory`/`ProcessFileLock` 不变），
导入改为 `from edge.runtime_platform.adapter import ...`、`from edge.runtime_platform.file_lock import ...`，
不再与标准库同名。PyCharm 调试 main.py 也不再触发此错误。
历史上若在旧版本遇到，临时规避是在仓库根目录跑或按 2.2 设 `PYTHONPATH`。

### 6.8 启动窗口出现 `cv::VideoCapture::open VIDEOIO(DSHOW)` 警告

**原因**：本机没接相机，或者 `camera_indices` 的索引跟现场实际编号对不上。
图像处理库打不开设备时会往窗口里吐一行原生日志，看着像故障，其实只是"没插相机"。

**处理**：程序已经在"打开相机"这一小段把图像处理库的原生日志压掉了，
启动窗口**不会再刷这一串警告**，只留一行我们自己的话：

```
[边缘机] 相机打开失败：索引 1、2、3、4、5、6、7、8；本机没接相机属正常现象，周期帧照发，详细原因见 logs/ 下的日志文件
```

没接相机是**正常现象**：周期帧照发，`camera_status` 里这 8 路如实报 `offline`，
上位机按 `offline` 拒绝开柜，不会误开柜。接上相机后这一行就不会出现。

每一路的失败原因（含相机索引）在 `logs/` 下的日志文件里，搜 `相机打开失败` 就能定位是哪一路；
识别推理阶段的图像处理库日志不受影响，照常可见。

### 6.9 上位机点开柜，弹"IO 板未接入，边缘机未执行开柜指令"

**原因**：边缘机收到了开柜指令，但 IO 板还没接入，没法真的去开锁，所以按失败回应，
把真实原因透传给上位机。**这是如实上报，不是故障**，上位机弹的就是边缘机给的原因。

**处理**：IO 板接入后，`edge/app_init.py` 里的开柜回应改成真实执行结果即可；
在那之前，上位机的开柜功能整体不可用，但识别与核对链路不受影响。

### 6.10 切到内置摄像头后采集没落盘

**原因**：采集是**按需触发**的。边缘机启动后只发周期帧，不会主动抓图；
只有收到上位机的 `recognize_req` 才拉起采集线程抓帧落盘。
只盯着周期帧看，`edge/output/capture/w1/` 里一直是空的，这不是相机没接上。

**处理**：用观察工具带 `req` 参数，接入后主动发一帧识别请求触发采集：

```
python -m edge.tests.integration.watch_periodic 9000 0 req
```

触发后再去 `edge/output/capture/w1/` 找新落盘的 JPEG。

---

## 七、目录与文件职责速查

```
仓库根/
├─ edge/                     边缘机工程根
│  ├─ main.py                进程入口：拿进程锁 → 装配 → 启动 → 等退出 → 严格串行停机
│  ├─ app_init.py            装配层：读配置、建单例、注入三个门面与控制层
│  ├─ run_edge.bat           一键启动脚本（双击即可）
│  ├─ README.md              本文件
│  ├─ config/                配置目录
│  │  ├─ config.ini          运行参数
│  │  ├─ roi_binding.csv     ROI 对照表（识别台账）
│  │  ├─ class_item_map.csv  类别组合到物品名的映射
│  │  └─ README.md           配置件字段说明
│  ├─ interfaces/            接口契约（零实现）
│  ├─ base/                  通用线程与生命周期基类
│  ├─ runtime_platform/      平台适配与进程锁（避免与标准库platform同名）
│  ├─ infra/                 配置管理、日志管理、ROI 对照表装载
│  ├─ modules/
│  │  ├─ tcp/                通信：套接字、控制层、重连、心跳、解码
│  │  ├─ usb/                采集：门面、采集线程、摄像头设备
│  │  └─ recognition/        识别：门面、识别线程、拼接裁剪、推理引擎
│  ├─ control/               控制层：信号分发、应答排空
│  └─ tests/                 测试与联调工具
│     └─ integration/        桩上位机、周期帧观察工具、识别应答取证脚本
├─ weights/                  模型权重
├─ logs/                     运行日志（自动创建）
└─ edge_runtime.lock         进程锁文件（自动创建）
```

| 想知道 | 看哪个文件 |
| --- | --- |
| 进程怎么起来的 | `edge/main.py`、`edge/app_init.py` |
| 帧怎么组、怎么切的 | `edge/modules/tcp/tcp_comm.py` |
| 周期帧里装了什么 | `edge/app_init.py` 的 `buildPeriodicFrame` |
| 相机状态怎么判的 | `edge/modules/usb/usb_controller.py` 的 `getCameraStatus` |
| 识别清单怎么算的 | `edge/modules/recognition/recognition_worker.py`、`recognition_utils.py` |
| 协议帧长什么样 | `edge/interfaces/i_sinks.py`、`edge/control/edge_control.py` |
