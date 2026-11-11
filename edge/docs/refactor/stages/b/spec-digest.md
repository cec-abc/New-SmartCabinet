# 阶段 b 资料消化摘要（spec-digest）

> 极简口径（用户 2026-11-10）：保留五节标题，每节 1–3 行要点；不转录资料、不做逐行审读表。

## 1. 本阶段资料清单

- 主资料（L1 只读）：`edge/docs/spec/整体重构方案.txt` §2 目录结构、§3 `base/` 段、§4 依赖方向、§5 `b` 行；`edge/docs/spec/编码规范规则.txt` §5 线程与生命周期。
- 语义参考：`整体流程/整合类图代码.txt`+`.png`、`整体流程.txt` 启停段、`TCP/断线重连/断线重连.txt`、`日志/日志.txt`、`阶段5-7.png`；`INDEX.md` 无「对应阶段 = b」条目，即本阶段无专属图。
- 图只取线程启停与停机语义，不转录图中文字；图中运行期「阶段 0~7」与 9 个实施阶段不是同一套编号。

## 2. 关键语义

- `BaseThread(IThread)`：`stopEvent`、`start()` 幂等、`stop(timeout=3.0)` 置位 → 唤醒 → join → 超时强制返回、`interruptibleWait(sec) -> bool`、抽象 `runLoop()`。
- `BaseService`：`init/start/stop` 三件套可多态；`base/` 不 import 业务模块，只做通用生命周期、不预启业务线程。

## 3. 命名裁决表

- 落地标识符以 L1 §3 为准：`stopEvent` / `interruptibleWait` / `runLoop` / `isRunning` / `init` / `start` / `stop`；旧图 snake_case 只作语义输入，不作 API。
- 文件名 `base_thread.py`、`base_service.py` 全局唯一且 snake_case；`__init__.py` 为包标记，豁免文件名唯一性。

## 4. 适用裁决与冲突点

- D-02：只做通用基类，不引入 `linkState` / `transitionTo`、不预启心跳 / 解码 / 采集 / 识别线程；D-01 / D-03 复核不绕过。
- NAMING_AUTHORITY；禁写 `.py` 解除仅对本阶段白名单生效且不沿用；单测落点 `edge/tests/unit/`；L1 基线 `stage-a-done` 已批准项不重复判定。

## 5. 待确认项

- 无；开工卡已经用户点头，按白名单与四步编排执行。
