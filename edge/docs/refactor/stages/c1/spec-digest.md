# 阶段 c1 资料消化摘要（spec-digest）

> 极简口径（用户 2026-11-11）：保留五节标题，每节 1–3 行要点；图只取业务语义、不转录文字、不把图名当 API。

## 1. 本阶段资料清单

- 主资料（L1 只读）：`edge/docs/spec/整体重构方案.txt` §1/§2/§3 `infra/` 段/§5 `c1` 行、`编码规范规则.txt`；`edge/interfaces/i_config.py`、`i_logger.py`、`edge/exceptions.py`。
- 语义参考：`edge/docs/spec/配置文件接口/` 四份（图代码 txt + 类图/流程图/时序图 PNG）、`整体流程/整体流程.txt` 配置加载分支；`references/glossary.md` §3、`decisions.md`。

## 2. 关键语义

- Fail-Fast：文件缺失 / 解析失败一律抛 `EdgeError(CONFIG, ...)` 阻断启动；加载时一次性推断 int / float / bool / list / str 并存入「节 → 键 → 值」字典。
- `get(section, key, default=None)` 两分支：命中返回已推断值；缺失且无 default 抛 `EdgeError(CONFIG, ...)`，有 default 返回默认值并记 info；`instance()` 类变量 + 双检锁，普通构造仍可用于测试。
- 多值以逗号分隔推断为 list（元素递归推断），布尔字面量与数字分支互不吞并；路径与日志器构造注入，模块内不 import 业务模块。

## 3. 命名裁决表

- L1 接口表：`getValue(section, key)` → `get(section, key, default=None)`；`getInstance()` → `instance()`；`ConfigManager` → `IniConfigManager`；私有方法同样 camelCase。
- 文件名 `config_manager.py` 全局唯一且 snake_case，`__init__.py` 包标记豁免；严禁图上 snake_case / 专用 getter 落地。

## 4. 适用裁决与冲突点

- D-01 / D-02 / D-03 影响阶段均不含 c1，逐条复核不绕过（不新增自检接口/线程、不引入 `linkState` / `seq` 去重）；NAMING_AUTHORITY 适用。
- 图上专用 getter / `getInstance` / `getValue` / 旧 snake_case 与 L1 冲突：按 L1 + `glossary.md` §3 裁决，不改图、不改 L1；图中「阶段 0~7」为运行期时序，非 9 个实施阶段。

## 5. 待确认项

- 无；开工卡 2026-11-11 经用户点头，`edge/infra/__init__.py` 已确认保留，禁写 `.py` 仅对本阶段白名单解除、不沿用。
