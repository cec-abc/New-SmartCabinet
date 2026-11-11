# 阶段 c2 资料消化摘要（spec-digest）

> 极简口径（用户 2026-11-11）：五节标题，每节 1–3 行；图只取业务语义，不转录文字、不把图名当 API。

## 1. 本阶段资料清单

- L1 只读：`整体重构方案.txt` §1/§3 `infra/` 段/§5 `c2` 行、`编码规范规则.txt`、`interfaces/i_logger.py`、`i_thread.py`、`exceptions.py`、`pyproject.toml`。
- 语义参考：`edge/docs/spec/日志/` 四份、`整体流程/整体流程.txt` 停机段；`glossary.md` §3、`decisions.md`、`HANDOFF-c1.md` §8。

## 2. 关键语义

- 唯一阻塞队列：业务线程只组带 type/时间戳的 JSON 入队立刻返回；后台线程 take 后按 logMode 路由（合并 / 分开）落盘。
- Writer 跨天或超大小滚动；滚动时磁盘剩余比例低于注入阈值则删最旧文件；停机清空队列剩余并依次关句柄。
- `error(exception=e)` 自动附堆栈；四方法之外无 `init(config)`，rx/tx 的 data 为 `dict[str, object] | bytes`。

## 3. 命名裁决表

- 图上 `init(config)` / `getInstance()` / `enqueue()` / `rollFile()` 等只作语义，落地为 ILogger 四方法 + 类内 `instance()` + 构造注入参数；私有方法同样 camelCase。
- `LogExecutor` / `LogFileWriter` 留在 `infra/log_manager.py` 内不单列文件；文件名 snake_case 且全局唯一。

## 4. 适用裁决与冲突点

- D-01 / D-02 / D-03 影响阶段均不含 c2，逐条复核不绕过；NAMING_AUTHORITY 适用。
- 图与 L1 冲突（`init(config)`、`IConfig` 专用 getter、旧 snake_case、无 `FrameData`）以 L1 接口表为准；不改图、不改 L1，图中「阶段 0~7」为运行期时序。

## 5. 待确认项

- 无；开工卡 2026-11-11 经用户点头，API 口径已钉死，禁写 `.py` 仅对本阶段白名单解除、不沿用。
