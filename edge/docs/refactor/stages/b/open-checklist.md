# /stage b 开工清单（只读核对 · 落盘长表）

> 日期：2026-11-10。阶段 `b`（通用生命周期），状态 `pending`，前置 `a` = `done`。
> 本卡为开工核对产物：**未经用户点头**，配置期禁写 `edge/` 下任何 `.py` 仍然生效；
> 未改 `STAGE-STATE.md`、未改 L1、未改 spec 原文/PNG、未预建 `spec-digest.md` / `test-report.md`。
> 路径基准为工作区根 `f:\new zhineng`；`stages/b/` = `edge/docs/refactor/stages/b/`，
> `references/<file>` = `.codebuddy/skills/edge-refactor/references/<file>`（CODEBUDDY.md §0）。
> 用户当次指令（精简模式）：对话只出 15 行内确认卡 + 3 行要点，详细长表只落盘；不复述规则全文、不列口径差异。

## 1. 交付文件白名单

`implementer`（步骤 2）唯一可写集合；用户点头后，禁写 `.py` 仅对下表 `.py` 解除，本阶段许可不沿用。

| # | 路径（工作区根相对） | 操作 | 归属 / 验收项 | 依据 |
| --- | --- | --- | --- | --- |
| 1 | `edge/base/__init__.py` | 新建 `.py`（包标记） | `base/` 包结构 | L1 `整体重构方案.txt` §2 目录结构；`__init__.py` 豁免文件名唯一性 |
| 2 | `edge/base/base_thread.py` | 新建 `.py` | `b-1`、`b-2`、`b-3` | L1 §3 `base/` 段：`BaseThread(IThread)`、`stopEvent`、`start()` 幂等、`stop(timeout=3.0)` 置位+唤醒+join、`interruptibleWait(sec) -> bool`、抽象 `runLoop()` |
| 3 | `edge/base/base_service.py` | 新建 `.py` | `b-3`（关联 `b-1`/`b-2`） | L1 §3 `base/` 段：`BaseService` 生命周期三件套可多态 |
| 4 | `edge/tests/unit/` 新增 1 个单测文件 | 新增 `.py` | `b-1`~`b-3` | 阶段 0 开工裁决「补强单测落点固定 `edge/tests/unit/`，只新增文件、不改既有断言，后续阶段同理」；`HANDOFF-a.md` §8 第 3 条。L1 §5 `b` 行的 Demo 子类作为该单测文件内的测试替身，不另立文件 |
| 5 | `stages/b/spec-digest.md` | 新增 `.md`（五节） | 步骤 1 `spec-reader` | 不预建、不代写；须含命名裁决表 |
| 6 | `stages/b/test-report.md` | 新增 `.md`（六节） | 步骤 3 `test-writer` / 收尾必交物 | `test-visibility.mdc`：缺件 / 缺节 / ⑥ 无未覆盖项 / ④ 无可复现命令一律判红 |

只读引用（零改动，不计入白名单）：`edge/interfaces/i_thread.py`（L1）、`edge/exceptions.py`、`edge/pyproject.toml`、`edge/tests/contract/*`、`edge/tests/fakes/*`、`edge/tests/unit/` 既有两份单测、`stages/0/*`、`stages/a/*`、`HANDOFF-0.md` / `HANDOFF-a.md`、`edge/docs/spec/**` 原文与 PNG、`.codebuddy/rules/编码规范.mdc`。
存在性核对（只读）：`edge/base/` 当前不存在；`edge/tests/unit/` 已存在；`stages/` 下原仅有 `0/`、`a/`。

## 2. 验收项与必交物

措辞照抄 `references/stage-catalog.md` §2 阶段 b，不改写：

| 编号 | 验收项 |
| --- | --- |
| `b-1` | `stop()` 瞬间打断 `interruptibleWait` |
| `b-2` | join 超时强制返回 |
| `b-3` | 重复 `stop` 幂等且 `BaseService` 三件套可多态 |

必交物：`stages/b/test-report.md`（① 验收项→用例对照 / ② Fake 与边界 / ③ 用例表 / ④ 可复现命令与环境 / ⑤ 汇总 / ⑥ 未覆盖项及原因）、`stages/b/spec-digest.md`（五节）。
测试约定：每个测试函数上方一行中文注释标注验收项编号；禁止 `assert True` / `assert x` / `assert ... is not None` 空洞断言；禁止为变绿改被测代码；覆盖率采集按用户既有裁决不引入。

## 3. 对应 spec 资料（对应图）

`edge/docs/spec/INDEX.md` 逐文件登记中**没有「对应阶段 = b」的条目**：阶段 b 无专属图、无专属目录。

主资料（INDEX.md 中 `0~d` 条目，只读）：

| 路径 | 类型 | 本阶段用途 |
| --- | --- | --- |
| `edge/docs/spec/整体重构方案.txt` | 定稿文本（L1） | §2 目录结构、§3 `base/` 段、§4 依赖方向、§5 `b` 行（**主资料**） |
| `edge/docs/spec/编码规范规则.txt` | 定稿文本（L1） | 线程 / 生命周期 / 异常 / 命名硬约束全文 |
| `edge/docs/spec/整体流程/整合类图代码.txt` | 整合类图（PlantUML 源码） | 分层与依赖连线总览，只取语义 |
| `edge/docs/spec/整体流程/整合类图.png` | 整合类图位图 | 上条源码的位图，只取语义 |
| `edge/docs/spec/INDEX.md` | L3 索引（非图资产） | 逐文件登记的唯一权威 |

跨阶段语义参考（按 `references/diagram-index.md` §2 `b` 行「各模块图中的线程启停、`stopEvent` 片段」；**登记阶段均非 b**，只取语义、不作 b 专属资料）：

- `edge/docs/spec/整体流程/整体流程.txt` 第 1 段线程启停时机、第 3 段停机串行。
- `edge/docs/spec/TCP/断线重连/断线重连.txt` 退避等待的 `stopEvent` 可打断等待与停机拦截分支。
- `edge/docs/spec/整体流程/阶段5-7.png` 一键停机严格串行。
- `edge/docs/spec/日志/日志.txt` 停机清空队列与关句柄。

硬约束：不转录图中文字；图上方法名 / 类名不是 API，落地标识符按 NAMING_AUTHORITY 与 L1 §3；图中「阶段 0~7」是运行期业务时序编号，与 9 个实施阶段 `0/a/b/c1/c2/c3/c4/c5/d` 不是同一套；L1 与 spec 原文 / PNG 只读，禁重新渲染 / 重命名 / 覆盖。

## 4. 适用裁决

- **D-02**（stage-catalog.md 阶段 b 明列）：b 只实现通用生命周期基类；不预启任何业务线程，不引入 `linkState` / `transitionTo` / 心跳 / 解码 / 采集 / 识别线程，业务线程启停时机留 `c3` / `d`。
- **D-01 / D-03**：本阶段不涉及，但须复核不绕过（不新增自检接口或线程、不做能力降级、不实现 `seq` 去重 / `EventCache` / `PendingRequest`）。
- **NAMING_AUTHORITY**：文本 > 图、方案 A > 旧流程时序图、camelCase > 旧图 snake_case；`stopEvent` / `interruptibleWait` / `runLoop` / `isRunning` 等以 L1 §3 为准；`spec-digest.md` 必须给命名裁决表。
- **禁写解除**：仅在本卡经用户点头后、对第 1 节白名单内 `.py` 解除；阶段 a 的解除已失效、不沿用；白名单外 `.py`、L1 契约层、`edge/docs/spec/**` 原文与 PNG 仍一律禁写。
- **单测落点**：固定 `edge/tests/unit/`，只新增文件、不改既有断言；阶段 0 / a 的历史产物不倒改、不洗绿。
- **L1 baseline**：以 tag `stage-a-done` + `references/decisions.md` 附录 A + `HANDOFF-a.md` §4 为对比基线；已批准的 `test_phase0_foundation.py` typed wrapper 改动不重复判定，基线外新增 L1 改动仍须完整 diff + 用户批准。
- 写完 / 改完 Python 后调用 `python-code-review` 检视一次并沉淀，检视项按阶段逐步收敛。

## 5. 禁止事项

1. 点头前：不写 `edge/` 下任何 `.py`（含新建 / 补测），不改 `STAGE-STATE.md` 状态 / §3 复选框 / 证据栏，不预建 `stages/b/spec-digest.md` 与 `test-report.md`。
2. 白名单外 `.py` 一律禁写；L1 契约层（`整体重构方案.txt` / `编码规范规则.txt` / `编码规范.mdc` / `edge/interfaces/*.py` / `edge/exceptions.py` / `edge/pyproject.toml` / `edge/tests/contract/*`）禁自动修改，契约变更须先给完整 diff（前后 + 影响面 + 受影响测试/Fake）并等用户批准；`edge/docs/spec/**` 原文与 PNG 禁写，`INDEX.md` 只做同步登记。
3. 裸 `threading.Thread`、裸 `time.sleep` 禁止；周期等待只用 `interruptibleWait(sec) -> bool`；`base/` 禁止 import 任何业务模块（L1 §4 / 规则 03 §2）。
4. 不静默改既有测试断言、既有 Fake 契约、既有规则全文；不为让测试变绿改被测代码。
5. 不转录图中文字、不把图上方法名当 API、不混用两套阶段编号；不自行推断第四条裁决。
6. 最终 review 结论由用户本人签字；`stage-verifier` 只出举证表；任何 agent 不代签、不跳过人工闸门。

## 6. 确认开工后的四步编排（本卡不代为执行）

| 步 | 执行者 | 产物 | 准出 |
| --- | --- | --- | --- |
| 1 | `spec-reader` | `stages/b/spec-digest.md`（五节） | 禁止把图上方法名当 API、无转录、命名裁决表齐备 |
| 2 | `implementer` | 第 1 节白名单内实现 | 只改白名单，不写测试、不改 L1 / spec / 状态 |
| 3 | `test-writer` | `edge/tests/unit/` 新增单测 + `stages/b/test-report.md`（六节） | 六节齐备、用例带验收项编号、无空洞断言、无洗绿 |
| 闸门 | **用户本人** | 代码 review 签字 | 未签字不得进入步骤 4，不许代签 |
| 4 | `stage-verifier` | 举证表 | 只举证，不下最终结论、不代签 |

用户点头后由 `/stage` 记录 `pending → in_progress`；`/stage-done` 在必交物齐备、用户本人签字与 `contract-guard` 复核后才可推进状态。

## 7. L1 基线核验（`contract-guard` 只读 + 主 agent git 只读补证）

**结论**：相对基线 tag `stage-a-done` 的**新增 L1 改动 0 处**，判「L1 无变更（相对基线）」；基线自身登记的 1 处变更（`edge/tests/contract/test_phase0_foundation.py` 的 typed 装饰器 wrapper `windowsOnly`）为用户 2026-11-10 已批准项，按用户口径记「有变更 1 处，均为已批准基线项，不触发阻断」，不重复判为未批准 / 自动修改、不重复征询、不阻断阶段 b 开工。未批准的新增 L1 变更 0 项，无新 diff、无「等待批准」、无 `blocked`。

只读命令与真实输出片段（主 agent 执行，退出码 0）：

```
git tag -l stage-a-done                 -> stage-a-done
git cat-file -p stage-a-done            -> object 5666c06b69e5257b9845e3dd78239f9c644037ad / type commit
                                          tag stage-a-done（说明：首次经批准 L1 变更 baseline 见 decisions.md 附录 A）
git rev-parse "stage-a-done^{commit}" HEAD -> 5666c06b...（两次相同，tag 指向 HEAD）
git status --porcelain                  -> （空）
git diff --name-status stage-a-done HEAD -- edge/docs/spec .codebuddy/rules edge/interfaces edge/exceptions.py edge/pyproject.toml edge/tests/contract -> （空）
git diff --name-status stage-a-done      -- edge/docs/spec .codebuddy/rules edge/interfaces edge/exceptions.py edge/pyproject.toml edge/tests/contract -> （空）
```

`contract-guard` 静态核验补证：L1 契约层 17 个文件齐备（2 份定稿文本 + `编码规范.mdc` + `interfaces/` 9 个 + `exceptions.py` + `pyproject.toml` + `tests/contract/` 3 个）；已批准文件当前态与 `HANDOFF-a.md` §4 diff 的 b 侧逐行一致（`Callable` / `cast` / `windowsOnly` / 两处 `@windowsOnly("仅 Windows 验证")`，5 个既有用例函数体与断言零改动）；`edge/docs/spec/**` 枚举 37 文件 = 11 `.txt` + 25 PNG + `INDEX.md`，与 INDEX.md §1 登记一致，无缺失 / 重命名 / 新增；`edge/**/*.py` 30 个，与阶段 a 收尾 mypy `30 source files` 一致；`stages/` 下原仅 `0/`、`a/`。
D-01 / D-02 / D-03 绕过扫描：全库关键词仅命中 `i_sinks.py` 一条 L1 既有注释（状态机返回值去重，非 `seq` 去重），三条裁决均未被绕过。
证据边界：`contract-guard` 无命令执行能力，工作区 / 暂存区未提交改动、PNG 字节级哈希由其静态枚举 + 主 agent 上述 git 只读命令闭环；判定不编造输出。

## 8. 待确认与放行

- 待用户确认：**是否点头开工，并仅对第 1 节白名单内 `.py` 解除禁写（本阶段许可不沿用）**。其余按本卡既定口径执行，不另行征询。
- 未获点头：不写任何 `.py`、不推进状态、不创建 `stages/b/spec-digest.md` / `test-report.md`、不启动四步。
- 若后续发现未批准的 L1 新增变更：立即输出完整 diff 并阻断，等待用户批准。

## 9. 对话侧确认卡（≤15 行，2026-11-10 同步输出）

见本阶段对话回复；内容为白名单 / `b-1`~`b-3` / 禁止事项 / 对应图四项，外加 3 行要点（长表落盘路径、L1 基线结论、等待点头）。
