# HANDOFF-c3 — TCP 模块

- **阶段**：c3
- **日期**：2026-11-11
- **状态**：done
- **移交方**：助手（主 agent）
- **接收方**：下一阶段开工（`stage-opener` → c4）

## 1. 开工依据

- 用户确认记录：2026-11-11 用户「点头开工，c3 记为 in_progress」签开工卡白名单（tcp_control_layer.py / test_stage_c3_tcp.py，必要时 tcp_comm.py）与已拍板裁决，四步由主 agent 连续执行；同日用户 review 代码与 `test-report.md` 后签字「我看过实现和 test-report.md 了，签字」，并本条同时确认状态推进 `c3 → done`、不再另停一次。
- 适用权威：`CODEBUDDY.md` §2 + 规则 01~04（用户 2026-11-09/10 修订版）。
- 本阶段 spec 资料：`edge/docs/spec/` 下 TCP 三类图与协议 `智能工具柜配置项通信协议_初稿.docx`（路径见 `edge/docs/spec/INDEX.md`；只列路径与图类型，不转录内容）。
- 上一阶段 handoff：`edge/docs/refactor/HANDOFF-c2.md`。
- 现有代码判定：引用 `references/stage-catalog.md` §0 — c3 为**新模块** `edge/modules/tcp/` 五个文件，无旧代码需处置。

## 2. 交付文件与必交物

| 文件 | 操作（新增 / 修改 / 只读核验） | 对应验收项编号 | 说明 |
| --- | --- | --- | --- |
| `edge/modules/tcp/tcp_comm.py` | 新增 | c3-3 | `TcpComm`：socket 适配 + 切帧 + 超长帧 `FRAME_PARSE` |
| `edge/modules/tcp/tcp_reconnect_thread.py` | 新增 | c3-1 | 退避重连 + `interruptibleWait` 可打断 |
| `edge/modules/tcp/tcp_heart_thread.py` | 新增 | c3-2 | 非 UP 返回 `False`、发送失败回调 |
| `edge/modules/tcp/tcp_decode_thread.py` | 新增 | c3-3 | 半包/粘包解码 + recv 空 → `onLinkDown` |
| `edge/modules/tcp/tcp_control_layer.py` | 新增 | c3-1~c3-5、c3-修复回归 | 状态机门面：`start/stop/transitionTo/onLinkDown`（**每次拉起新建线程实例**） |
| `edge/tests/unit/test_stage_c3_tcp.py` | 新增 | c3-1~c3-5、c3-修复回归 | 9 用例（含 `test_c3_x_relink_after_down` 回归） |
| `edge/docs/refactor/stages/c3/spec-digest.md` | 新增（必交物） | — | 五节齐备 |
| `edge/docs/refactor/stages/c3/test-report.md` | 新增（必交物） | — | 六节齐备（④ 真实命令与输出、⑥ 未覆盖项及原因） |
| `edge/docs/spec/INDEX.md` | 修改（仅登记） | — | 新增 docx 契约一行；**不改 spec 原文/PNG/docx** |
| `.codebuddy/skills/edge-refactor/references/decisions.md` | 修改（仅登记） | — | 新增 c3 待裁决登记段（EventCache/错放/camera_status 归属），不落地 |

- 必交物：`edge/docs/refactor/stages/c3/spec-digest.md` **存在（五节齐备）**
- 必交物：`edge/docs/refactor/stages/c3/test-report.md` **六节齐备**
- 范围外文件：无（L1 契约层、`edge/docs/spec/**` 原文/PNG/docx、`STAGE-STATE` 状态均未改）
- 遗留 TODO 及归属阶段：见 §6（全部按归属留后续阶段）

## 3. 验收项逐条证据

| 编号 | 验收项 | 证据（命令 + 输出 + 测试名 + test-report 对应用例） | 举证结果 |
| --- | --- | --- | --- |
| c3-1 | 退避 `[1,2,4,8,16,30]` 构造注入 + `interruptibleWait` 可打断 | `backoffSeq=[0.01]` 构造注入；`test_c3_1_reconnect_backoff_interruptible`（0.5s 内 `is_alive()==False`）、`test_c3_1_reconnect_success`（attempts==3） | 通过 |
| c3-2 | 心跳失败去重 / 非 UP 返回 `False` | `test_c3_2_heart_non_up_returns_false`（`trySendHeartbeat() is False`、`failed==[]`）、`test_c3_2_heart_send_failure_callback`（`failed` 非空） | 通过 |
| c3-3 | 半包/粘包切帧 + 超长帧 | `test_c3_3_split_and_oversize`（切出 2 帧/剩半包/`FRAME_PARSE` 抛出） | 通过 |
| c3-4 | `transitionTo(state,reason,source)->bool` 并发 DOWN 靠返回值去重 | `test_c3_4_transitionTo_idempotent`（首 `True` 次 `False`）、`test_c3_4_transitionTo_concurrent`（4 线程并发仅 1 次生效） | 通过 |
| c3-5 | `FakeSocket` 联调通过；`tcp/` 无禁词 | `test_c3_5_fakesocket_integration`（收 `type=signal` 且 `socket.closed`）；`findstr` 禁词零命中 | 通过 |
| c3-修复回归 | `onLinkDown` 后重连线程必须重建并回到 UP | `test_c3_x_relink_after_down`（直接调用真实 `onLinkDown`；状态 `DOWN→UP` 且重连后解码信号再增） | 通过 |

- 工具链：`ruff` `All checks passed!` ｜ `mypy`（3.9 strict）`Success: no issues found in 47 source files` ｜ `pytest` `9 passed in 0.58s`（收尾复跑；四步首轮 `0.60s`，耗时波动并列保留）｜ 禁词 `findstr /R /I /M "config cv2 numpy vision_core IConfig" edge\modules\tcp\*.py` 无输出（退出码 1 = 无命中）。
- `test-report.md` 六节：**齐备**；第 ⑥ 节未覆盖项摘要：真实退避序列端到端计时（归 d）、心跳长周期真实发送（归 d）、decode 多线程竞争 recv 缓冲（归 d）、断线→重连循环稳定性（**本次已由 `test_c3_x_relink_after_down` 覆盖**，记为已覆盖）；`python-code-review` 报告：见下；测试约定核验：`@brief c3-*` 编号注释齐全、无空洞断言、无为变绿而改被测代码。

### python-code-review 报告（c3 新增 6 个 .py）

- 范围：`edge/modules/tcp/*`（5 文件）+ `edge/tests/unit/test_stage_c3_tcp.py`
- 模式：聚焦扫描（禁词 + D-01/02/03 + 并发去重 + 容错边界 + 构造注入）

| 级别 | 位置 | 维度 | 证据 | 结论 |
|------|------|------|------|------|
| P0 | 全部 `tcp/` | 禁词 | grep 无 `config`/`cv2`/`numpy`/`vision_core`/`IConfig` | 通过 |
| P0 | `tcp_control_layer.transitionTo` | 原子去重 | 锁内同态返回 `False`；并发 4 线程测试仅 1 次生效 | 通过 |
| P1 | `tcp_control_layer.start/onLinkDown/_onConnected` | D-02 非 UP 不启线程 | `start()` 仅拉重连；UP 后 `_onConnected` 才启心跳+解码；`onLinkDown` 停心跳解码+**新建**重连 | 通过 |
| P1 | `tcp_comm` / 各线程 | 魔鬼数字 | `maxFrameSize`/`backoffSeq`/`heartIntervalSec` 全构造注入，模块内零配置 import | 通过 |
| P1 | `tcp_decode` | 异常边界 | 超长帧 `raise EdgeError(FRAME_PARSE)`；`BaseThread` 顶层转 `EdgeError` 不穿越 | 通过 |
| P2 | `tcp_control_layer._haltThread` | 错误处理 | 自停线程 `stop()` 抛 `RuntimeError`（`self-join`）经 `try/except` 吞掉；`stopEvent` 已置位，线程将自行退出 | 通过（必要且最小） |
| P2 | 各线程 `runLoop`/`interruptibleWait` | 并发 | 重连线程**每次新建实例**绕开 `BaseThread.start` 的 `_hasStarted` 幂等，避免 `onLinkDown` 后无法重启 | 通过 |
| P3 | `decode` recv 空 → `onLinkDown` | 可选优化 | 真实 socket 断线闭环留 d 端到端补 | 留 d |

- 未覆盖软维度：通信层 `recv`/`connect` 异常兜底属规则允许的健壮性保留项，已按规不洗绿。
- 下一步：无需改码；一条可复用经验「重连/重启类线程每次拉起须新建实例」沉淀 `lessons.md` L-07 与检视经验库；用户签字后进入收尾沉淀。

## 4. L1 契约层

- `contract-guard` 基线结论：**零自动变更**（c3 全部交付文件仅依赖 L1 既有契约 `interfaces`/`exceptions`/`base` 与 stdlib、白名单内 `edge.modules.tcp` 及 `edge.tests.fakes`，禁词全局零命中）。
- 契约变更 diff：无。
- 批准状态：无需批准。
- 硬要求复核：**不得自动修改 L1；任何契约变更必须给 diff 并等用户批准** —— 已遵守（未触碰 L1 任何文件）。

## 5. 三条已定裁决落实

| 裁决 | 落实情况 | 说明 |
| --- | --- | --- |
| D-01 自检留空接口 | 已遵守 | `tcp_decode` 解码结果经 `onSignalDecoded` 上抛，未私自补业务判定；`camera_status` 仅按协议键名占位 |
| D-02 非 UP 不启其他线程 | 已遵守 | `start()` 仅拉重连线程；`transitionTo(UP)` 后才由 `_onConnected` 启心跳+解码 |
| D-03 去重不做、seq 只填不用 | 已遵守 | `transitionTo` 返回值去重，并发宣告靠 `False`；未实现 seq 消费 |

## 6. 遗留与裁决

- 图与 L1 的冲突点：无（图语义已转 L1 契约语言，未改图、未改 L1）。
- 需用户拍板事项：无（c3 待裁决登记段已在 `decisions.md` 标「只登记、不落地、归指定阶段」）。
- 阻塞原因与解除条件：无。
- 移交后续阶段的收敛项：
  - 真实退避序列 `[1,2,4,8,16,30]` 端到端计时 → 归 **d（集成）**
  - 心跳 `runLoop` 长周期真实发送 → 归 **d**
  - decode 多线程竞争 recv 缓冲 → 归 **d**（socket 实现保证）
  - `camera_status` 空接口默认值 + 「连丢 5 条周期帧判离线」 → 归 **c5 / d**（上位机侧判定，不动 `linkState`）

## 7. 沉淀记录

- `edge/docs/refactor/STAGE-STATE.md` 更新：c3 行 `pending → done`、证据栏补工具链与举证结论、§5 门禁记录追加 2026-11-11 c3 收尾行、时间 2026-11-11。
- `references/lessons.md` 条目号：**L-07**（重连/重启类线程每次拉起须新建实例）。
- 项目记忆：无（本阶段为修复实现，沉淀已入 `lessons.md` 与检视经验库，不重复存代码细节）。
- `python-code-review` 经验库：可复用结论已沉淀至本仓库 `references/lessons.md` L-07（重连/重启类线程每次拉起须新建实例）；全局 skill 的 `accumulated-lessons.md` 位于本仓库写范围之外，本次未改（经验不重复存两份）。
- `references/decisions.md`：未变更裁决；仅新增 c3 待裁决登记段（不落地）。

## 8. 下阶段开工提示

- 下一阶段：**c4**（`modules/usb/` 三个文件）。
- 必读：`edge/docs/refactor/HANDOFF-c4.md`（待生成）、`references/stage-catalog.md` c4 段、`decisions.md` 命中裁决、`edge/docs/spec/INDEX.md` 对应资料。
- 特别注意：c4 为 4 线程并发采集，沿用本阶段「非 UP 不启线程 + 状态机去重」范式；`camera_status` 业务判定仍在 c5/d，tcp 层不混入。

## 9. 用户本人 review 与签字

- 人工闸门位置：`test-writer` 之后、`stage-verifier` 之前。
- 代码 review 签字：**已签署**（用户本人 2026-11-11「我看过实现和 test-report.md 了，签字」）。
- **最终 review 结论（用户口述 2026-11-11，按原文录入，不视为代签）：**

  > 阶段 c3 验收通过，同意收尾；⑥ 未覆盖项按归属留后续阶段，覆盖率不引入。

- [x] 配置/交付范围确认
- [x] 举证结论确认
- [x] 状态推进确认（c3 → `done`）
- 确认人 / 日期：用户本人 / 2026-11-11
