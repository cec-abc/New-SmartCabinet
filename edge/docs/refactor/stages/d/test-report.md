# d 阶段测试报告

## ① 验收项 → 用例对照表
| 验收项编号 | 验收项 | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| d-1 | `routeSignal` 按注入 `asyncHandlers` 键分发 | test_d_1_route_signal_dispatches_injected_keys / test_d_1_unknown_key_rejected_and_sink_forwards / test_d_1_l1_sink_contracts_and_camel_case | 通过 |
| d-2 | `EventCache` 补发/丢弃且 `seq` 只填不用 | test_d_2_cache_flush_when_enabled / test_d_2_cache_discard_when_disabled / test_d_2_seq_only_filled_never_used_for_dedup / test_d_2_link_down_caches_and_link_up_flushes / test_d_2_dispatch_outbox_sends_when_up | 通过 |
| d-3 | 一键停机严格串行 `USB → 识别 → TCP → 日志` + 进程锁 | test_d_3_stop_system_strict_serial / test_d_3_selfcheck_stub_d01 / test_d_3_start_system_does_not_prestart_business_threads / test_d_3_process_lock_fails_fast_before_assembly | 通过 |
| d-4 | Windows 端到端 | test_d_4_end_to_end_start_and_stop / test_d_4_app_init_only_wires / test_d_4_main_has_no_try_except_business_flow / test_d_4_build_system_has_no_business_branches / test_d_4_platform_and_fake_contracts | 通过 |

## ② 使用了哪些 Fake、各自模拟什么边界
| Fake 名称 | 对应接口 | 模拟的边界 / 异常 | 为何本阶段需要 |
| --- | --- | --- | --- |
| FakeLogger | ILogger | 记录 `info` / `error` 及 `exception` | 停机统计、补发/丢弃、未注册键的具体值断言 |
| FakeSocket | ISocket | 固定收发、`closed` 句柄标记 | 装配端到端与 TCP 停机举证，不建真实连接 |
| FakeCameraDevice | ICameraDevice | 固定帧、不触碰设备 | 四路采集装配，不依赖真实摄像头 |
| FakeRecognitionEngine | IRecognitionEngine | 固定检测结果、`loadedPaths` | 识别装配与「buildSystem 不加载模型」举证 |
| FakePlatformAdapter | IPlatformAdapter | `lockResult=None` 模拟锁占用 / `BytesIO` 模拟持锁 | 进程锁生效与释放，不依赖真实 msvcrt |
| FakeRecognitionSink | IRecognitionSink | 回调命名反射 | snake_case 不作 API 的交叉证据 |
| 注入 `RecordingSender` / `CallTrace` / 各回调 | — | 记录发送帧与调用顺序 | 分发、补发、停机串行、app_init 纯装配的确定性举证 |
| `WindowsAdapter` / `PlatformFactory`（真） | IPlatformAdapter | Windows 换行符 `\r\n` | d-4 Windows 平台分支举证 |

## ③ 用例表
| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| test_d_1_route_signal_dispatches_injected_keys | 注入键 `alpha_probe` / `beta_probe` | 命中返回 True、requestId 只提取一次、键表一致 | `seen == [signal]`、`req-1 → req-2`、`getHandlerKeys() == [alpha_probe, beta_probe]` | 通过 |
| test_d_1_unknown_key_rejected_and_sink_forwards | 未注入键 / `onSignalDecoded` | 返回 False、记 error、Sink 转发 | error 含「未注册」、`onSignalDecoded` 后 seen 1 条、`req-3` | 通过 |
| test_d_1_l1_sink_contracts_and_camel_case | EdgeControl 反射 | 三个 L1 Sink 实例、camelCase、无 snake_case | 三 `isinstance` 成立，无 `route_signal` / `on_recognition_result` / `on_capture_success` | 通过 |
| test_d_2_cache_flush_when_enabled | enabled=True、3 条缓存 | 补发 3 条、seq `1,2,3`、顺序保持、清空 | `flush == 3`、`[0,1,2]`、info 含「补发 3 条」 | 通过 |
| test_d_2_cache_discard_when_disabled | enabled=False、2 条缓存 | 丢弃、发送器零调用 | `flush == 0`、`frames == []`、info 含「丢弃断线期间 2 条」 | 通过 |
| test_d_2_seq_only_filled_never_used_for_dedup | 3 条完全相同事件 | 不去重、seq 递增、无 seenSeq | `pendingCount == 3`、seq `[1,2,3]`、补发 3 条、无 `_seenSeq` | 通过 |
| test_d_2_link_down_caches_and_link_up_flushes | DOWN → 结果/失败入队 → UP | DOWN 不直发、入缓存；UP 补发 2 条 | `sender.frames == []` → `dispatchOutbox() == 2` → UP 后 2 条（ack + error） | 通过 |
| test_d_2_dispatch_outbox_sends_when_up | UP、`{"seq": 99}` | 直发且不改写业务 seq | 1 条、`seq == 99` | 通过 |
| test_d_3_stop_system_strict_serial | 4 个记录型 stop 动作 | 严格串行轨迹 | `trace.events == [USB, RECOGNITION, TCP, LOG]`、info「停机统计 顺序=USB-RECOGNITION-TCP-LOG」 | 通过 |
| test_d_3_selfcheck_stub_d01 | `selfCheckSystem()` | 无副作用、不启线程 | 零停机轨迹、零队列、`logger.infoRecords == []` | 通过 |
| test_d_3_start_system_does_not_prestart_business_threads | `startSystem()` | 只 init + link，不启采集/识别 | `trace.events == ["init","link"]`、`isLinkUp() is False` | 通过 |
| test_d_3_process_lock_fails_fast_before_assembly | `lockResult=None` | 第一件事退出、不装配 | `SystemExit` 含 `CONFIG`、`lockCalls == [edge_runtime.lock]`、`partsCalled == []` | 通过 |
| test_d_4_end_to_end_start_and_stop | `main()` + 注入 Fake 装配 | 锁→装配→信号→启动→等待→停机→释放 | `trace == [signals, log-start, link-start, wait, log-stop]`、`loadedPaths == ["model.bin"]`、`socket.closed True`、锁句柄 `closed True` | 通过 |
| test_d_4_app_init_only_wires | `buildSystem(parts)` | 只 new + 注入 + 返回 | route 未被调、`trace.events == []`、`loadedPaths == []`、`frames == []` | 通过 |
| test_d_4_main_has_no_try_except_business_flow | AST 解析 `main()` | 无 Try / 无 If 语句、锁先于启动 | 断言成立、`acquireOrExit` 索引 < `startSystem` | 通过 |
| test_d_4_build_system_has_no_business_branches | AST 解析 `buildSystem()` | 无 If/For/While/Try | 断言成立、`defaultParts` 可调用 | 通过 |
| test_d_4_platform_and_fake_contracts | `PlatformFactory.create()` | Windows 返回 `WindowsAdapter`、换行 `\r\n` | 分支内断言成立、Sink Fake 反射通过 | 通过 |

- 迭代链（如实披露）：首轮 ruff `I001`×2 / `E501`×1 / `N812`×4，mypy `Cannot infer type of lambda` ×1 与 `ISocket has no attribute closed` ×1；均为白名单内的 import 排序、行宽、模块别名、循环 lambda 默认参数与类型收窄问题，修正后复跑全绿；写后检视再收敛 3 处（模块名常量、默认 worker 数魔法值、`-> None` 值断言），三项工具链复跑仍全绿。未改验收项、未改预期、未删用例、未为变绿改被测代码的业务语义。

## ④ 可复现的完整运行命令与运行环境
- 命令（工作目录 `f:\new zhineng`，PowerShell）：
  - `python -m ruff check edge`
  - `python -m mypy edge`
  - `python -m pytest edge\tests\unit\test_stage_d_control.py -v`
  - `python -m pytest edge\tests -q`
  - `python -m pytest edge\tests\contract -q`
- 环境：`platform win32 -- Python 3.10.8, pytest-9.1.1, pluggy-1.7.0`；解释器 `C:\Users\Xiaojiu\AppData\Local\Programs\Python\Python310\python.exe`；`rootdir: F:\new zhineng\edge`、`configfile: pyproject.toml`（`pythonpath=["."]`、`testpaths=["edge/tests"]`、mypy `python_version=3.9` / `strict=true`）；未单独建 venv。
- 前置条件：无摄像头 / 模型 / 网络 / 端口占用；`tmp_path` 建四个 worker 目录，锁句柄用 `BytesIO` 模拟，信号注册与退出等待全部注入，不触碰真实设备与进程信号。
- 真实输出（本次最终复跑，退出码均 0）：
  - ruff：`All checks passed!`
  - mypy：`Success: no issues found in 64 source files`
  - pytest d：`17 passed in 0.55s`（`-v` 首轮 `17 passed in 2.24s`，耗时波动并列保留）
  - pytest 全量：`111 passed in 1.90s`（另一次 `111 passed in 1.97s`）
  - pytest 契约：`10 passed in 0.17s`（另一次 `10 passed in 0.18s`）
- L1 基线（开工只读核验）：`contract-guard` 子代理无命令执行工具、返回「未判定」（不采信为无变更），改由主 agent 只读 git 取证：`git rev-parse HEAD` = `git rev-parse stage-c5-done^{commit}` = `a7178d2233e175fac0c04b919c9f030103e8482f`；`git log --oneline stage-c5-done..HEAD` 空；`git status --porcelain=v1 --untracked-files=all` 空；L1 + `edge/docs/spec/` 相对基线 / 工作区 / 暂存区三段 `git diff --name-status` 均空；本地 9 tag，`git -c http.connectTimeout=5 ls-remote --tags origin` 远端 9 tag 齐全 → **L1 零自动变更、无需批准**（附录 A 已批准基线不重复判定）。
- `python-code-review` 检视报告（写后一次，范围 `control/*.py` 3 文件 + `app_init.py` + `main.py` + 单测）：
  - P0：`control/` 仅依赖 `base/` / `interfaces/` / `exceptions.py` 与同模块，无 `modules/*` 反向 import；`main.py` 唯一出现 `sys.platform` 的判断仍在 `PlatformFactory` 内；`app_init → control`、`app_init → modules/*` 方向正确 → 通过。
  - P0 / 裁决：D-01 `selfCheckSystem()` 空接口 + TODO；D-02 `startSystem()` 只 init + link；D-03 `seq` 只填不用、无 `seenSeq` / 去重分支；`EventCache.enabled` 由上层注入、模块不默认 → 通过。
  - P1：`EdgeControl` 的 Sink 回调只入队 / 轻量转发，`dispatchOutbox()` 才发送；`main()` 无 `try/except` 与 `if not success:`；`frameSender` 加锁组帧 → 通过。
  - P2：`defaultParts()` 的 `SocketSkeleton` / 占位回调均标 `TODO` 并登记 ⑥；`ModuleWiring` 装配期填充解决门面与 Sink 的构造循环，避免 `set_signal_sink` 式 setter → 通过。
  - P3：`test_d_4_*` 两处 AST 源码结构断言属静态文本举证（经验库已登记脆弱断言），已有行为断言交叉证据 → 归上板，不阻断。
  - 结论：无阻断项；检视中收敛的 3 处（模块名常量、魔法值、`-> None` 值断言）已在白名单内修正并复跑全绿。

## ⑤ 汇总
| 通过 | 失败 | 跳过 | 总耗时 | 覆盖率 |
| --- | --- | --- | --- | --- |
| 17（d）/ 111（全量）/ 10（契约） | 0 | 0 | d `0.55s`；全量 `1.90s`；契约 `0.17s` | 未引入覆盖率门禁（沿用既有口径） |

## ⑥ 本阶段未覆盖项及原因
| 未覆盖的验收项 / 分支 | 原因 | 归属阶段 | 补测计划 |
| --- | --- | --- | --- |
| EventCache 存废口径（归 d）与协议「边缘机不缓存任何业务数据、重发补发全是上位机行为」的张力 | 用户本轮明确「只登记、不落地、不自行选边、待我拍板」；本阶段只落地 `enabled` 注入的中性机制，两种业务口径均不裁定 | d（**待用户拍板**） | 用户裁决后按归属补；`decisions.md` 原文未改 |
| 错放判定归属（待裁决②）、`camera_status` 默认值 + 连丢 5 条周期帧判离线（待裁决③） | 用户明确「两组按归属留后续阶段、不混入 d」；`defaultHeartbeat()` 不含 `camera_status`，不设默认值 | c5 / c4/d（后续阶段） | 按归属阶段与用户裁决补 |
| 真实 `config.ini` 参数读取与真实业务 `asyncHandlers` 键注入 | 本轮 `defaultParts()` 只给骨架默认值与空分发表；按协议「门面不写死业务字符串」，键由上层配置注入 | 上板 / 用户裁决后 | 接入真实配置后补集成用例 |
| 真实 `ISocket` / 摄像头后端 / rknn 推理（`tcp_socket.py` 未在 c3 白名单落地） | 本轮以 `SocketSkeleton` + `NotImplementedError + TODO` 骨架、`FakeSocket` 联调，不建真实连接 | 上板 | 真实后端落地后补端到端集成用例 |
| 真实 Windows 进程端到端（真机网络 / 四路摄像头 / 模型 / 进程信号） | 本轮用 Fake + 注入回调跑通装配→启动→分发→缓存→停机→释放锁全链路，避免真实线程与设备 | 上板 | 真机部署后补端到端用例 |
| 线上 JSON 键名最终映射、失败应答帧协议结构 | §2.10 协议 docx 只取键名语义；`defaultFailureFrame` / `fixedFailure` 为占位，不自行裁定 | 上板 / 用户裁决后 | 协议定稿后补键名断言 |
| 真实 3s 推理计时器、按采集目录实读左右图、真实磁盘占用与滚动删旧 | `directInference` / `placeholderFrames` / `zeroUsage` 为骨架占位，沿用 c4/c5 注入口径 | 上板 | 真实实现落地后补 |
| 采集成功→识别触发→ack 回传的全链路真实线程并发 | 真实业务线程与网络未接入，本轮以 wiring 注入的 Fake 回调举证编排顺序 | 上板 | 端到端集成补 |
