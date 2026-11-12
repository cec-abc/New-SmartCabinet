# c5 阶段测试报告

## ① 验收项 → 用例对照表
| 验收项编号 | 验收项 | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| c5-1 | 模型仅 `loadModel` 一次、`trigger` 立即返回 | test_c5_1_load_once_and_trigger_returns_immediately / test_c5_1_guard_before_init_and_invalid_worker_id / test_c5_1_selfcheck_stub_d01 / test_c5_1_yolo_engine_instance_and_single_load | 通过 |
| c5-2 | 推理 3s 超时（构造注入） | test_c5_2_timeout_injected_and_mapped / test_c5_2_timeout_sec_is_configurable | 通过 |
| c5-3 | 空间归集 + 查表校验 + 组 ack | test_c5_3_aggregate_lookup_and_build_ack / test_c5_3_pure_functions_behavior | 通过 |
| c5-4 | 回调上抛、纯函数留在 `recognition_utils.py` | test_c5_4_callbacks_isolated_and_exception_upcast / test_c5_4_pure_functions_only_in_utils_and_no_cross_module_import / test_c5_4_fake_engine_contract_and_camel_case_sink | 通过 |

## ② 使用了哪些 Fake、各自模拟什么边界
| Fake 名称 | 对应接口 | 模拟的边界 / 异常 | 为何本阶段需要 |
| --- | --- | --- | --- |
| FakeRecognitionEngine（只读复用，白名单外） | IRecognitionEngine | 固定检测结果、`loadedPaths` 记录加载次数 | 模型单次加载与组帧举证，不依赖真实 rknn |
| FakeRecognitionSink | IRecognitionSink | 记录 `onRecognitionResult` / `onRecognitionError` | 回调上抛、成功/失败互不影响的具体值断言 |
| FakeLogger | ILogger | 记录 `info` / `error` 及 `exception` | 举证「查表未命中记 error 不中断」「超时异常码 INFERENCE_TIMEOUT」 |
| 注入 `timeoutRunner` / `frameLoader` | — | 抛 `TimeoutError` / 抛 `OSError` / Barrier 并发阻塞 | 3s 超时、内置异常跨边界转换、trigger 立即返回，全部确定性举证 |
| 注入 `classItemMap` / `roiBindMap` / `roiConfig` | — | 命中、未命中、ROI 未绑定 | 空间归集与查表校验不依赖真实查表文件 |

## ③ 用例表
| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| test_c5_1_load_once_and_trigger_returns_immediately | 两次 init、Barrier(2) 阻塞读图、trigger(1) | 仅 1 次 loadModel、trigger 立即返回、忙时返回 False、放行后 1 条结果 | `engine.loadedPaths == ["model.bin"]`、`elapsed < 1.0s`、workers 键 `[1]`、`requestId == "req-1"` | 通过 |
| test_c5_1_guard_before_init_and_invalid_worker_id | 未 init、workerId=5 / 0 | 返回 False、零 worker、零模型加载 | `trigger(5/0) is False`、`getActiveWorkers() == {}`、`loadedPaths == []` | 通过 |
| test_c5_1_selfcheck_stub_d01 | 调 `selfCheckRecognition()` | 无线程、无 IO、无能力降级 | `getActiveWorkers() == {}`、无 `on_capture_success` | 通过 |
| test_c5_1_yolo_engine_instance_and_single_load | instance() 两次、loadModel 两次、未加载先 infer | 同一实例、只记录首个路径、未加载抛 CONFIG | `instance() is instance()`、`loadedPaths == ["m1"]`、`code == CONFIG` | 通过 |
| test_c5_2_timeout_injected_and_mapped | runner 抛 TimeoutError、注入 3.0s | 收到 3.0、`EdgeError(INFERENCE_TIMEOUT)`、无结果回调 | `seen == [3.0]`、`errorEvents` 1 条且 `code == INFERENCE_TIMEOUT`、日志含 INFERENCE_TIMEOUT | 通过 |
| test_c5_2_timeout_sec_is_configurable | 注入 0.25s | 秒数透传、正常出结果 | `seen == [0.25]`、`resultEvents` 1 条 | 通过 |
| test_c5_3_aggregate_lookup_and_build_ack | 3 条检测（r1 命中/未命中、r2 未绑定） | ack 三条 items 具体值、未命中记 CONFIG error 但不判错放 | `ackItems` 三条逐项相等、`requestId == "req-3"`、`errorEvents == []` | 通过 |
| test_c5_3_pure_functions_behavior | 固定字节与检测结果 | 拼接/ROI/归集/查表/组帧输出确定 | `b"L||R"`、`b"L||R#ROI#r1=1"`、`misses == ["r1/ghost"]`、ack 字典相等 | 通过 |
| test_c5_4_callbacks_isolated_and_exception_upcast | worker 2 读图抛 OSError | worker 1 成功、worker 2 上抛 `EdgeError(CAPTURE)` | `resultEvents` 的 id `[1]`、`errorEvents` 1 条 id=2、`code == CAPTURE` | 通过 |
| test_c5_4_pure_functions_only_in_utils_and_no_cross_module_import | 读取四个实现文件源码 | 5 个纯函数只在 utils 定义、无 usb/tcp/control/sys.platform import | 四条静态断言全部通过 | 通过 |
| test_c5_4_fake_engine_contract_and_camel_case_sink | FakeEngine 经接口引用、Sink 反射 | 接口一致、无 snake_case 回调 | `loadedPaths == ["model.bin"]`、`infer` 结果相等、`hasattr(onRecognitionResult)` | 通过 |

- 迭代链（如实披露）：首轮即为全绿，无失败/无洗绿/未改验收项/未改预期/未删用例；未修改任何被测代码以适配测试。

## ④ 可复现的完整运行命令与运行环境
- 命令（工作目录 `f:\new zhineng`，PowerShell）：
  - `python -m ruff check edge`
  - `python -m mypy edge`
  - `python -m pytest edge\tests\unit\test_stage_c5_recognition.py -v`
  - `python -m pytest edge\tests -q`
  - `python -m pytest edge\tests\contract -q`
- 环境：`platform win32 -- Python 3.10.8, pytest-9.1.1, pluggy-1.7.0`；解释器 `C:\Users\Xiaojiu\AppData\Local\Programs\Python\Python310\python.exe`；`rootdir: F:\new zhineng\edge`、`configfile: pyproject.toml`（`pythonpath=["."]`、`testpaths=["edge/tests"]`、mypy `python_version=3.9` / `strict=true`）；未单独建 venv。
- 前置条件：无摄像头 / 模型文件 / 端口占用；全部用例基于 Fake + 注入回调 + `Barrier`，无外部依赖、无真实磁盘读图。
- 真实输出（本次实跑，退出码 0）：
  - ruff：`All checks passed!`
  - mypy：`Success: no issues found in 58 source files`
  - pytest c5：`11 passed in 0.08s`（11 个用例逐条 `PASSED`，见 `-v` 输出）
  - pytest 全量：`94 passed in 2.07s`
  - pytest 契约：`10 passed in 0.16s`
- L1 基线（开工只读核验）：`contract-guard` 子代理无命令执行工具、返回「未判定」（不采信为无变更），改由主 agent 只读 git 取证：`git rev-parse HEAD` = `git rev-parse stage-c4-done^{commit}` = `f3e6a0043669024d5cd7dc49f11c6059d258a6f5`；`git log --oneline stage-c4-done..HEAD` 空；`git status --porcelain=v1 --untracked-files=all` 空；L1 + `edge/docs/spec/` 相对基线 / 未暂存 / 已暂存三段 `git diff --name-status` 均空；`git tag --list` 8 个 → **L1 零自动变更、无需批准**（附录 A 已批准基线不重复判定）。
- `python-code-review` 检视报告（写后一次，范围 `recognition/*.py` 5 文件 + 单测）：
  - P0：`recognition/` 仅依赖 base/interfaces/exceptions 与同模块，无 usb/tcp/control 反向 import（测试静态断言覆盖）；D-01 空接口、D-02 不预启线程、NPU 限流仅 TODO、camelCase 命名 → 通过。
  - P1：`runLoop` / `init` / `runInference` 顶层把 `TimeoutError` / `OSError` / 内置异常转 `EdgeError`（INFERENCE_TIMEOUT / CAPTURE / CONFIG），日志用 `code.name`，内置异常不穿越边界 → 通过。
  - P2：`inferTimeoutSec` / `timeoutRunner` / `frameLoader` / 三张查表 / `modelPath` 全构造注入（沿用 L-06 / L-08），3s 超时可确定性举证 → 通过。
  - P3：`test_c5_4` 用源码文本断言「纯函数只在 utils / 无跨模块 import」，属静态文本举证（经验库已登记为脆弱断言），已有行为断言交叉证据 → 归 `d` 收敛，不阻断。
  - 结论：无阻断项；本阶段无新增可复用检视规律（均为 L-05~L-08 应用），经验库不重复沉淀，收尾同步。

## ⑤ 汇总
| 通过 | 失败 | 跳过 | 总耗时 | 覆盖率 |
| --- | --- | --- | --- | --- |
| 11（c5）/ 94（全量）/ 10（契约） | 0 | 0 | c5 `0.08s`；全量 `2.07s`；契约 `0.16s` | 未引入覆盖率门禁（沿用既有口径） |

## ⑥ 本阶段未覆盖项及原因
| 未覆盖的验收项 / 分支 | 原因 | 归属阶段 | 补测计划 |
| --- | --- | --- | --- |
| 真实 3s 计时器与真实 rknn 推理 | 本轮按 L1「NPU 并发先不做」只注入 `timeoutRunner` / `emptyInfer` 骨架，CPU 占位 + TODO 切换点 | d / 上板 | 接入 rknn 后补真实超时集成用例 |
| 真实图像拼接 / ROI 画框（`.so` 下沉） | `FrameImage` 为不透明字节，纯函数只做确定性标记，真实 cv2 处理留 `.so` | d / 上板 | 纯函数下沉后补图像级断言 |
| 按采集目录实读左右两图（`w{id}_left/right_{stamp}.jpg`） | `frameLoader` 构造注入，不依赖 c4 落盘真实文件与时间戳 | d（端到端） | USB → 识别联动时补集成用例 |
| 错放业务判定的归属口径（c5 组 ack 前校验 ↔ 协议「上位机比对判定」） | `decisions.md` 待裁决② 归 c5，与 §2.10 协议口径存在张力；用户本轮明确「只登记、不落地、不自行选边、待我拍板」 | c5（**待用户拍板**） | 用户裁决后按归属补；本阶段 `validateByTable` 只查表、不比较不判错放 |
| EventCache 存废（待裁决①） | 按归属只登记、不落地、不裁定 | d | 用户裁决后按归属补 |
| `camera_status` 空接口默认值 +「连丢 5 条周期帧判离线」（待裁决③） | 上位机侧判定，按归属只登记、不落地、不裁定 | c4 / d（待用户裁决） | 用户裁决后按归属补 |
| 线上 JSON 键名最终映射、按 workerId 触发的下游链路、一键停机串行 | 依赖 `control/` 与 `main.py`，尚未交付 | d | 端到端补 |
