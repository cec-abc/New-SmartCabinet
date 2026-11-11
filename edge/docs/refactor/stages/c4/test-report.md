# c4 阶段测试报告

## ① 验收项 → 用例对照表
| 验收项编号 | 验收项 | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| c4-1 | 4 线程并发拉起并立即返回（前置校验：已初始化且未采集中） | test_c4_1_four_workers_fork_and_return_immediately / test_c4_1_guard_before_init / test_c4_1_init_fails_fast_on_missing_dir / test_c4_1_selfcheck_stub_d01 | 通过 |
| c4-2 | 双路取图落盘 | test_c4_2_dual_frames_saved / test_c4_2_camera_factory_addressing / test_c4_2_linux_skeleton_converted_before_boundary | 通过 |
| c4-3 | 滚动删除（超 30% 删旧） | test_c4_3_roll_deletes_oldest / test_c4_3_roll_still_over_threshold_logs_error | 通过 |
| c4-4 | 成功 / 失败回调互不影响；`FakeCamera` 联调通过 | test_c4_4_success_error_callbacks_isolated / test_c4_4_fake_camera_contract | 通过 |

## ② 使用了哪些 Fake、各自模拟什么边界
| Fake 名称 | 对应接口 | 模拟的边界 / 异常 | 为何本阶段需要 |
| --- | --- | --- | --- |
| FakeCameraDevice | ICameraDevice | 固定帧、`opened`/`closed` 句柄标记 | 双路落盘与联调，不依赖真实摄像头 |
| BarrierCamera | ICameraDevice | 左路取图阻塞在 5 方屏障 | 举证 4 个 worker 确已并发拉起且主线程未被阻塞 |
| FailingCamera | ICameraDevice | `readFrame` 恒抛 `OSError` | 举证内置异常跨边界转 `EdgeError(CAPTURE)`、单路失败不影响其他 worker |
| FakeCaptureSink | ICaptureSink | 记录 `onCaptureSuccess` / `onCaptureError` | 回调互不影响的具体值断言 |
| FakeLogger | ILogger | 记录 `info` / `error` 调用 | 举证「删后仍超阈值记 error 但不中断」 |
| 注入的 `usageRatio` / `clock` | — | 占用比例序列、固定时间戳 | 滚动删旧与文件名在 `tmp_path` 内确定性举证，不读真实磁盘/时钟 |

## ③ 用例表
| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| test_c4_1_four_workers_fork_and_return_immediately | 4 组设备，左路阻塞在 Barrier(5) | startCapture 立即返回、4 worker 存活、无成功回调；重复拉起抛 CONFIG；放行后 4 条成功回调 | `11 passed`，elapsed < 1.0s，successEvents 的 workerId = [1,2,3,4] | 通过 |
| test_c4_1_guard_before_init | 未 init 调 startCapture | 抛 EdgeError(CONFIG)、零 worker | `[CONFIG] USB 未初始化或已在采集中`、getWorkers() == [] | 通过 |
| test_c4_1_init_fails_fast_on_missing_dir | 不存在的目录 | 抛 EdgeError(CONFIG) | `[CONFIG] USB 采集目录不可写` | 通过 |
| test_c4_1_selfcheck_stub_d01 | 调 selfCheck() | 无线程、无 IO、无能力降级 | 零副作用断言通过 | 通过 |
| test_c4_2_dual_frames_saved | 左右帧 b"LEFT-BYTES" / b"RIGHT-BYTES" | 两个 jpg 落盘且内容分别一致、句柄关闭、1 条成功回调 | 文件内容逐字节一致、`successEvents == [(1, str(tmp_path))]` | 通过 |
| test_c4_2_camera_factory_addressing | "0" 与 "/dev/cam_left" | 前者 DSHOW 可读帧，后者 V4L2 骨架抛 NotImplementedError | `BACKEND_DSHOW` / `BACKEND_V4L2` 与 `"Linux 摄像头后端待上板实现"` 均匹配 | 通过 |
| test_c4_2_linux_skeleton_converted_before_boundary | Linux 骨架设备进采集流程 | Sink 收到 EdgeError(CAPTURE) 而非内置异常 | `errorEvents[0]` workerId=1、`code == ErrorCode.CAPTURE` | 通过 |
| test_c4_3_roll_deletes_oldest | 3 个旧文件（mtime 递增）+ 2 个新帧，阈值 0.3 | 删最旧 2 个、比例回落到 0.3 停止、新帧保留 | old0/old1 不存在，old2 与左右新帧存在，1 条成功回调 | 通过 |
| test_c4_3_roll_still_over_threshold_logs_error | 占用比例恒 0.9 | 旧文件删尽、新帧受保护、记 CAPTURE error、成功回调不受影响 | `errorRecords` 含 CAPTURE，`successEvents == 1`，`errorEvents == []` | 通过 |
| test_c4_4_success_error_callbacks_isolated | 4 组，第 3 组左路失败 | 成功 workerId = [1,2,4]、失败 1 条且 workerId=3、所有注入设备已关闭 | 逐项具体值断言通过 | 通过 |
| test_c4_4_fake_camera_contract | FakeCameraDevice 经 ICameraDevice 引用 | 四方法签名一致 | open/readFrame/getStatus/close 行为一致 | 通过 |

- 四步内迭代链（如实披露）：首轮 ruff `F821`、mypy `func-returns-value` + `name-defined`、pytest `2 failed`；均为测试侧笔误与 `-> None` 值断言（L-04），在白名单内修正并新增 Linux 骨架跨界用例后复跑全绿；未改验收项、未改预期、未为变绿改被测代码。

## ④ 可复现的完整运行命令与运行环境
- 命令（工作目录 `f:\new zhineng`，PowerShell / cmd 均可）：
  - `python -m ruff check edge`
  - `python -m mypy edge`
  - `python -m pytest edge\tests\unit\test_stage_c4_usb.py -v`
  - `python -m pytest edge\tests -q`
  - `python -m pytest edge\tests\contract -q`
- 环境：`platform win32 -- Python 3.10.8, pytest-9.1.1, pluggy-1.7.0`；解释器 `C:\Users\Xiaojiu\AppData\Local\Programs\Python\Python310\python.exe`；`rootdir: F:\new zhineng\edge`、`configfile: pyproject.toml`（`pythonpath = ["."]`、`testpaths = ["edge/tests"]`、mypy `python_version = 3.9` / `strict = true`）；本机未单独建 venv，同一解释器即可。
- 前置条件：无摄像头/端口/网络占用；全部测试基于 `tmp_path` + Fake + 注入回调，无外部依赖。
- 真实输出（本次最终复跑）：
  - ruff：`All checks passed!`
  - mypy：`Success: no issues found in 52 source files`
  - pytest c4：`11 passed in 0.52s`
  - pytest 全量：`83 passed in 1.70s`
  - 契约测试：`10 passed in 0.18s`
- L1 基线（开工只读核验，contract-guard 子代理 API 不可达，改由主 agent 用 git 只读命令核验）：相对 `stage-c3-done` 的 L1 pathspec diff 为空、工作区 L1 diff 为空、`edge/docs/spec/**` diff 为空；`git status --porcelain` 在单独提交后为空。HEAD 相对基线仅多 `5f57056`（`.codebuddy/skills/edge-refactor/SKILL.md` 收尾流程文字，属 L3 流程规则变更、用户已单独提交，非 L1 变更）。
- `python-code-review` 检视报告（简版，范围：`edge/modules/usb/*.py` 4 文件 + `test_stage_c4_usb.py`）：
  - P0/D-01/D-02/D-03：`usb/` 仅依赖 base/interfaces/exceptions，无跨模块反向 import；`selfCheck()` 为空接口、无自检线程、无能力降级；init 不预启线程；无 `seq`/去重逻辑 → 通过。
  - P1 / 边界：`readFrame` 与 `runLoop` 顶层把 `OSError`/`ValueError`/`TimeoutError`/`NotImplementedError` 统一转 `EdgeError(CAPTURE)`，内置异常不穿越模块边界；Linux 骨架按 L1 §1 为 `NotImplementedError + TODO`（首版曾直接抛 EdgeError，检视后修正并补举证用例）→ 已在白名单内收敛。
  - P2 / 可观测性：滚动删旧保护本轮新帧（沿用 L-06 外部依赖注入与可观测举证口径），删后仍超阈值记 error 不中断；`removedCount` 供举证 → 通过。
  - P3 / 遗留：真实 V4L2/CAP_DSHOW 后端、`shutil.disk_usage` 真实比例、按 workerId 触发识别 → 归 `c5 / d`，本阶段不阻断。
  - 结论：无阻断项，跨阶段遗留已标归属。

## ⑤ 汇总
| 通过 | 失败 | 跳过 | 总耗时 | 覆盖率 |
| --- | --- | --- | --- | --- |
| 11（c4）/ 83（全量）/ 10（契约） | 0 | 0 | c4 `0.52s`；全量 `1.70s` | 未引入覆盖率门禁（沿用既有口径，不强制） |

## ⑥ 本阶段未覆盖项及原因
| 未覆盖的验收项 / 分支 | 原因 | 归属阶段 | 补测计划 |
| --- | --- | --- | --- |
| 真实 V4L2 / CAP_DSHOW 采集后端 | L1 §1 定「上板再补」，本阶段以注入 `frameReader` + FakeCamera 举证接口行为 | d（上板/端到端） | 接入真实设备后补集成用例 |
| 真实磁盘占用比例（`shutil.disk_usage`）与跨天滚动 | 由 `usageRatio` 注入回调确定性举证，避免依赖真实磁盘状态 | d | 端到端补 |
| 按 workerId 触发识别、成功回调下游链路 | 依赖 `modules/recognition/` 与 `control/`，尚未交付 | c5 / d | 阶段 c5 联调、d 端到端 |
| `camera_status` 空接口默认值 +「连丢 5 条周期帧判离线」 | `decisions.md` 待裁决登记第 3 条归 c4/d，用户本轮裁定「只登记、不落地、不自行裁定」 | c4 / d（待用户裁决） | 待用户明确裁决后按归属补 |
| 采集线程自停（self-join）与重复 `stopCapture` 并发 | 本阶段由门面主线程统一停机，未覆盖 worker 自停路径 | d（一键停机串行） | 停机集成补 |
| 真实平台路径分隔符 / 换行差异 | 路径差异收敛在 `CameraFactory` 地址形态与 `pathlib`，未上板验证 | d | 麒麟/RK3588 上板补 |
