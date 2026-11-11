# c3 阶段测试报告

## ① 验收项 → 用例对照表
| 验收项编号 | 验收项 | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| c3-1 | 退避 `[1,2,4,8,16,30]` 构造注入且 `interruptibleWait` 可打断 | test_c3_1_reconnect_backoff_interruptible / test_c3_1_reconnect_success | 通过 |
| c3-2 | 心跳失败去重、非 UP 返回 `False` | test_c3_2_heart_non_up_returns_false / test_c3_2_heart_send_failure_callback | 通过 |
| c3-3 | 解码半包/粘包 + 超长帧 | test_c3_3_split_and_oversize | 通过 |
| c3-4 | `transitionTo(state, reason, source) -> bool` 并发宣告 DOWN 靠返回值去重 | test_c3_4_transitionTo_idempotent / test_c3_4_transitionTo_concurrent | 通过 |
| c3-5 | `FakeSocket` 联调通过；`tcp/` 无禁词 | test_c3_5_fakesocket_integration + 禁词 grep | 通过 |
| c3-修复回归 | `onLinkDown` 后重连线程必须重建并回到 UP | test_c3_x_relink_after_down | 通过 |

## ② 使用了哪些 Fake、各自模拟什么边界
| Fake 名称 | 对应接口 | 模拟的边界 / 异常 | 为何本阶段需要 |
| --- | --- | --- | --- |
| FakeSocket | ISocket | 固定收发、连接恒成功 | 联调收帧→解码→上游回调端到端 |
| SlowConnectSocket | ISocket | connect 先休眠 0.15s 再成功，制造可观测 DOWN 窗口 | 回归用例验证 UP→DOWN→再 UP |
| FlakySocket | ISocket | connect 前 N 次抛 `LINK_DOWN` | 退避重连成功移交 |
| SequenceSocket | ISocket | recv 按序返回、末块空表对端关闭 | 半包/粘包与断线宣告 |
| FailingSendSocket | ISocket | send 恒返回 `False` | 心跳发送失败触发回调 |
| StateHolder | — | 可控 linkState 读取 | 心跳非 UP / UP 路径 |
| FakeUpstreamSink | SignalSink | 记录 `onSignalDecoded`/`onLinkUp` | 联调上游回调 |
| _FakeThread | — | 记录启停 | 状态机并发去重断言 |

## ③ 用例表
| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| test_c3_1_reconnect_backoff_interruptible | 50 次失败退避 | stop 在退避中被打断、线程退出 | 0.5s 内 `is_alive()==False` | 通过 |
| test_c3_1_reconnect_success | 前 2 次失败 | 第 3 次连接成功、回调、attempts=3 | 一致 | 通过 |
| test_c3_2_heart_non_up_returns_false | state=DOWN | `trySendHeartbeat()` 返回 `False`、不触发回调 | 一致 | 通过 |
| test_c3_2_heart_send_failure_callback | state=UP、send 失败 | runLoop 触发 `onHeartSendFailed` | `failed` 非空 | 通过 |
| test_c3_3_split_and_oversize | 粘包+半包+超长帧 | 切出 2 帧、剩半包；超长抛 `FRAME_PARSE`；正常帧解析 | 一致 | 通过 |
| test_c3_4_transitionTo_idempotent | 同态两次 | 首 `True`、次 `False` | 一致 | 通过 |
| test_c3_4_transitionTo_concurrent | 4 线程并发 DOWN | reconnect 仅启 1 次、heart/decode 各停 1 次 | `log.count==1` | 通过 |
| test_c3_5_fakesocket_integration | 完整帧+关闭 | 上游收到 `type=signal`、socket 关闭 | 一致 | 通过 |
| test_c3_x_relink_after_down | SlowConnectSocket(connect 休眠 0.15s) + 直接调用真实 `onLinkDown` | 首次 UP 且有信号；`onLinkDown` 后状态 DOWN，重连后回到 UP 且信号数再增 | 一致 | 通过 |

## ④ 可复现的完整运行命令与运行环境
- 解释器：项目解释器（pytest 会话头显示 `Python 3.10.8`，需已装 `ruff`/`mypy`/`pytest`）；本机未单独建 venv，用同一解释器即可，命令统一写 `python`。
- 命令（工作目录 `f:\new zhineng`，PowerShell / cmd 均可）：
  - `python -m ruff check edge\modules\tcp edge\tests\unit\test_stage_c3_tcp.py`
  - `python -m mypy edge`
  - `python -m pytest edge\tests\unit\test_stage_c3_tcp.py -v`
  - `findstr /R /I /M "config cv2 numpy vision_core IConfig" edge\modules\tcp\*.py`（空格分隔即 OR；无命中则无输出、退出码 1）
- 前置：无端口/设备占用；测试全部基于 Fake，无外部依赖。
- 真实输出（本次复跑）：
  - ruff：`All checks passed!`
  - mypy：`Success: no issues found in 47 source files`
  - pytest：`9 passed in 0.60s`（含新增 `test_c3_x_relink_after_down`）
  - 禁词 `findstr`：无输出（即 `edge\modules\tcp\*.py` 不含 `config`/`cv2`/`numpy`/`vision_core`/`IConfig`）

## ⑤ 汇总
| 通过 | 失败 | 跳过 | 总耗时 | 覆盖率 |
| --- | --- | --- | --- | --- |
| 9 | 0 | 0 | 0.60s | 未引入覆盖率门禁（沿用既有口径，不强制） |

## ⑥ 本阶段未覆盖项及原因
| 未覆盖的验收项 / 分支 | 原因 | 归属阶段 | 补测计划 |
| --- | --- | --- | --- |
| 真实退避序列 `[1,2,4,8,16,30]` 端到端计时 | 单元用极小序列+`interruptibleWait` 断言可打断，真实长计时非单元重点 | d（集成） | 集成/端到端补 |
| 心跳 runLoop 长周期真实发送 | 用 0.01s 周期+强制失败验证回调路径 | d | 端到端 |
| decode 多线程竞争 recv 缓冲 | 单线程 decode 已覆盖切帧；并发 recv 由 socket 实现保证 | d | 集成 |
| TcpControlLayer 真实断线→重连循环稳定性 | 已由 `test_c3_x_relink_after_down` 覆盖：真实 `onLinkDown` 后重连线程重建、回到 UP、解码恢复 | 已覆盖（c3 单测） | — |
| `python-code-review` 检视结论 | 四步内已执行，结论见本阶段检视报告 | 本阶段 | 收尾沉淀 |
