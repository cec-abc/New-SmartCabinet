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

## 裁决变更协议

1. 只有用户能新增、修改或撤销裁决；助手不得自行推断出「第四条裁决」。
2. 新裁决分配下一个编号 `D-xx`，写明：裁决内容、冲突来源、落地含义、影响阶段、禁止事项、生效日期。
3. 同步更新：本文件 → 项目记忆（跨会话有效）→ 受影响阶段的 handoff / 开工清单。
4. 裁决与 L1 冲突时**不改 L1**：输出 diff + 影响面，等用户明确批准后才落地。
5. 每次阶段开工复核三条裁决是否被绕过；收尾在 handoff 中逐条记录落实情况。

## L1 定稿决策指针（不复制全文）

以下条目以 `edge/docs/spec/整体重构方案.txt` §1 为唯一权威，本文件只列条目名，便于开工索引：
目标环境 / Python 与类型标注 / 命名 / 注释 / 异常 / 单例 / 日志 / 进程锁 / NPU 并发 /
补发去重 / 部署 / 摄像头寻址 / `.so` / 引导文件。
阶段与目录定义见同文件 §2、§5；编码细则见 `edge/docs/spec/编码规范规则.txt`。

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
