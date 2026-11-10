# diagram-index.md — 图资料检索视图

> L3 长资料。**逐文件登记的唯一权威是 `edge/docs/spec/INDEX.md`**（36 份原始资料：11 `.txt` + 25 PNG），
> 本文件不复制那张表，只提供按图类型 / 阶段的检索视图与解读口径。
> **全部路径以工作区根为基准**（`CODEBUDDY.md` §0），统一写 `edge/docs/spec/...`。
> 图片只取语义，不转录图中文字；命名裁决见 `glossary.md`，冲突裁决见 `decisions.md`。

## 1. 图类型与载体

| 图类型 | 载体（路径以工作区根为基准） | 主要用途 |
| --- | --- | --- |
| 类图 | 各模块目录 `.txt` 的 `classDiagram` / PlantUML 段 + 对应 PNG | 类职责、字段、实现/组合/注入关系 |
| 流程图 | 各模块目录 `.txt` 的 `flowchart TD` 段 + 对应 PNG | 分支、异常路径、循环边界 |
| 时序图 | 各模块目录 `.txt` 的 `sequenceDiagram` 段 + 对应 PNG | 跨对象调用顺序、并发与停机时序 |
| 整合类图 | `edge/docs/spec/整体流程/整合类图代码.txt` + `edge/docs/spec/整体流程/整合类图.png` | 全系统分层与正交连线总览（旧版 snake_case） |
| 阶段时序 | `edge/docs/spec/整体流程/阶段0-3.png`、`edge/docs/spec/整体流程/阶段4-5.png`、`edge/docs/spec/整体流程/阶段5-7.png` | 运行期业务全流程分段 |
| PNG 快照 | 各模块 `deepseek_mermaid_YYYYMMDD_*.png` | 上述三类图的迭代渲染；文件名日期/哈希不承载语义 |

**解读口径**：每个模块目录恰好 1 个 `.txt` + 3 张 PNG，对应该 `.txt` 内的类图 / 流程图 / 时序图三段。
抽样核验（`edge/docs/spec/TCP/周期心跳帧/`）确认该组为类图 `fe70d4`、时序图 `1e53dc`、流程图 `b7cc81`；
其余目录的哈希命名不做逐张类型断言，一律以同目录 `.txt` 为准。

## 2. 按实施阶段检索（共 9 个阶段）

| 阶段 | 先读 | 再看 |
| --- | --- | --- |
| `0` | `edge/docs/spec/整体重构方案.txt` §1/§2 | `edge/docs/spec/整体流程/整体流程.txt` 第 1 段（启动与首连） |
| `a` | 同文件 §3 接口表 | `edge/docs/spec/整体流程/整合类图代码.txt` 的「抽象接口层」包 |
| `b` | 同文件 §3 `base/` 段 | 各模块图中的线程启停、`stopEvent` 片段 |
| `c1` | `edge/docs/spec/配置文件接口/` 全部 | `edge/docs/spec/整体流程/整体流程.txt` 的配置加载分支 |
| `c2` | `edge/docs/spec/日志/` 全部 | 停机时序中的 `LogManager.stop()` 段 |
| `c3` | `edge/docs/spec/TCP/断线重连/`、`edge/docs/spec/TCP/周期心跳帧/`、`edge/docs/spec/TCP/帧解码/` | `edge/docs/spec/整体流程/阶段0-3.png`、`edge/docs/spec/整体流程/阶段5-7.png` |
| `c4` | `edge/docs/spec/USB_Camera/` 全部 | `edge/docs/spec/整体流程/阶段4-5.png` 上半段 |
| `c5` | `edge/docs/spec/识别/` 全部 | `edge/docs/spec/整体流程/阶段4-5.png` 下半段 |
| `d` | `edge/docs/spec/整体流程/整合类图代码.txt`、`edge/docs/spec/整体流程/阶段5-7.png` | 全部模块图中的 Sink 回调与停机片段 |

## 3. 按图类型检索常用语义

| 想确认什么 | 去哪找（路径以工作区根为基准） |
| --- | --- |
| 首连 / UP 后启线程顺序 | `edge/docs/spec/整体流程/整体流程.txt` 第 1 段；裁决 D-02 |
| 退避序列与可打断等待 | `edge/docs/spec/TCP/断线重连/断线重连.txt` 流程图 / 时序图 |
| 心跳失败去重与非 UP 行为 | `edge/docs/spec/TCP/周期心跳帧/心跳帧.txt` 流程图 / 时序图 |
| 半包粘包与超长帧 | `edge/docs/spec/TCP/帧解码/帧解码.txt` 流程图 |
| 并发拉起 worker 并立即返回 | `edge/docs/spec/USB_Camera/USB.txt` 流程图；`edge/docs/spec/整体流程/阶段4-5.png` |
| 推理 3s 超时与组 ack | `edge/docs/spec/识别/识别.txt` 流程图 / 时序图 |
| 异步队列、logMode 路由、滚动 | `edge/docs/spec/日志/日志.txt` 流程图 / 时序图 |
| 配置类型推断与 Fail-Fast | `edge/docs/spec/配置文件接口/配置文件图代码.txt` 流程图 / 时序图 |
| 一键停机严格串行 | `edge/docs/spec/整体流程/整体流程.txt` 第 3 段；`edge/docs/spec/整体流程/阶段5-7.png` |

## 4. 图与 L1 的已知冲突点（不改图，写 handoff）

| 冲突 | 图中出处（路径以工作区根为基准） | 裁决 |
| --- | --- | --- |
| 自检 / 能力降级 / 自检线程 | `edge/docs/spec/整体流程/整体流程.txt` 第 1 段、`edge/docs/spec/USB_Camera/USB.txt` 预留节点与旁路自检 | D-01 |
| 非 UP 阶段出现心跳、解码线程 | 部分 TCP 图与断线分支 | D-02（L1 整体流程第 1 段与本裁决一致） |
| `PendingRequest` 重发、按 `seq` 去重 | `edge/docs/spec/TCP/断线重连/断线重连.txt` 时序、`EventCache` 补报段 | D-03 |
| 专用 getter、`getInstance`、`getValue` | 配置与日志类图 | L1 接口表 + `glossary.md` §3 |
| 旧版 snake_case 标识符 | 全部图 | NAMING_AUTHORITY |
| 「阶段 0~7」编号 | 整体流程三段时序 | 运行期业务时序，非 9 个实施阶段 |

## 5. 维护口径

- 新增/删除 spec 资料后：先更新 `edge/docs/spec/INDEX.md`，再按本文件 §2/§3 更新检索视图，并记入 handoff。
- 禁止重新渲染、重命名或覆盖任何 PNG；禁止把图中文字抄进 `.py` 注释。
- 本文件与 `INDEX.md` 不一致时，以 `INDEX.md` 为准并修正本文件。
- `spec-reader` 按本视图定位资料后，产出 `edge/docs/refactor/stages/<id>/spec-digest.md`，
  其中「L1 落地标识符」列不得照抄图名。
