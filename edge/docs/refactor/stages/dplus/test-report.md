# dplus 阶段测试报告

> **结论：证据齐备**（仅指本阶段测试证据齐备；最终验收结论由用户本人签字，agent 不代签）
>
> 测量基准时间：2026-11-14（**第三轮修复 + 两张图交付**后的最后一次全量实跑，见 ⑤）
> 测量基准代码：`d:\CFDZ\BYJSJ\New-SmartCabinet` 工作区未提交状态，HEAD = `9a8d0a0`
> （含 c4plus / c5plus / dplus 三批并发落地 + **第三轮业务闭环二次校验与缺陷修复**的工作区改动）
> 报告人：test-writer（只写测试与证据，不改被测代码、不改验收项、不改状态）
> 本轮追加沉淀：memory-steward（只更新证据与新增章节，不改被测代码、不改验收项、不改状态）
>
> ### 0.1 本轮数字的来源与复跑状态（如实标注，不掩饰）
>
> | 项 | 真实输出 / 读盘事实 | 来源与复跑状态 |
> | --- | --- | --- |
> | `python -m ruff check edge` | `All checks passed!` | 最终门禁：**主 Agent 与最终独立审查 Agent 各自实跑**；两方输出一致 |
> | `python -m mypy edge` | `Success: no issues found in 95 source files` | 同上：主 Agent 与最终独立审查 Agent 各自实跑；两方输出一致 |
> | `python -m pytest edge/tests -q` | **298 passed / 0 failed / 0 skipped / 1 warning** | 最终门禁：主 Agent 与最终独立审查 Agent 各自实跑 |
> | `python -m pytest edge/tests/integration -q` | **91 passed / 0 failed / 0 skipped / 1 warning** | 同上：主 Agent 与最终独立审查 Agent 各自实跑 |
> | 上位机自带 `build/tests/Debug/test_edge.exe` | **36 passed / 0 failed**（`Totals: 36 passed, 0 failed, 0 skipped, 0 blacklisted, 9947ms`） | 编译产物仍在盘（本轮读盘确认），实跑输出见 ③.5 |
> | 磁盘事实复核 | 全库 `parametrize` **10 处**（`test_dplus_assembly_guards.py` 7 处 + `test_dplus_config_doc_parity.py` 3 处），均为正常参数化用例、无 `skip` / `xfail` 掩盖；`AssemblyParts` **43 字段**（42 个显式赋值 + `dispatchIntervalSec` 走 dataclass 默认值）；真实 TCP 客户端 `edge/modules/tcp/tcp_socket.py` **已落地** | 读盘核对：`edge/tests/unit/test_dplus_assembly_guards.py:128,149,201,236,275,282,412`、`edge/tests/unit/test_dplus_config_doc_parity.py:100,124,192`、`edge/app_init.py:265-354`、`edge/modules/tcp/tcp_socket.py:1-131` |
> | 图自检数字（53 节点 / 18 关系；30 节点 / 35 连线；17 节点 / 17 连线） | **读盘逐条计数** `edge_class_diagram.html` 的 `NODES` / `ARROWS` 与 `edge_recognition_flow.html` 的 `F2.nodes/edges`、`F3.nodes/edges` 数组条目 | 已在磁盘独立核对 |
>
> > **口径说明**：本报告 ③ 的用例明细与 ⑤ 的分项表中的 `162 passed`、`132 → 162`、`38.36 s` 等是 **2026-11-14 第三轮修复阶段**的实测留档（当时全量 162），作为 L4 历史证据保留、不静默改写；**当前最终门禁**以上表 `298 passed / 1 warning`、`91 passed / 1 warning`、`All checks passed!`、`95 source files` 为准，由主 Agent 与最终独立审查 Agent 各自实跑，⑤ 汇总与结论的「全量」口径已同步。凡未亲自执行的命令只写已发生事实与来源，不写未经证实的推测结论；上表即为本报告当前数字的全部来源声明。

---

## ① 验收项 → 用例对照表

验收项编号取自 `edge/docs/refactor/stages/dplus/spec-digest.md` §7「验收硬指标」第 3~6 条，措辞照抄不改写。

| 验收项编号 | 验收项 | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| 3 | 端到端联调（`tests/integration/`）：Python 桩上位机监听 9000 → 边缘机连上 → 桩发 `recognize_req` → 边缘机回 `recognize_ack`，`items[]` 每项**恰好 4 字段**、`position` 不重复、`tool_id` 可空、`confidence ∈ [0,1]`、`alert_type` 取值合法 → 桩校验通过。 | `test_end_to_end_recognition.py::testEndToEndAckFieldsAreProtocolCompliant`；本阶段新增 `test_upper_host_protocol_parity.py::testHostAcceptsRealSimulatorLegalScenes`、`::testHostAcceptsTc24CompatibilityFrames`、`::testHostRejectsRealSimulatorBadFrames`、`::testAckItemMustCarryExactlyFourKeys`、`::testAckRequestIdMustBeSnakeCase`、`::testCoverageAndOutboundJudgementMatchHost`、`::testEdgeSourcesDoNotEmitRemovedFields`、`::testEdgeAckItemsCarryNoInternalFields`、`::testEdgeProductionAckMatchesHostProtocol`、`::testEdgeAckFrameTopLevelKeysAreProtocolExact`、`::testEdgeAckFrameHasNoInternalTopLevelKeys` | 已覆盖（新增 11 条 + 既有 1 条，全部通过） |
| 4 | **幂等验证**：同一 `request_id` 连发 2 次，边缘机只扫描一次、回两次相同结果。 | `test_end_to_end_recognition.py::testSameRequestIdIsIdempotent` | 已覆盖（既有用例通过；本阶段未新增，幂等属控制层 c5/dplus 既有能力） |
| 5 | **周期帧验证**：3 秒一帧 `periodic`，`camera_status` 覆盖 8 路。 | `test_end_to_end_recognition.py::testPeriodicFrameFormatAndCameraStatus`、`::testLinkDownFallsBackToEventCache`、`::testProductionConfigHasRequiredKeys`；本阶段新增 `test_upper_host_protocol_parity.py::testPeriodicFrameShapeAndCameraGate`、`::testPeriodicFrameIsSentEveryThreeSeconds` | 已覆盖（新增 2 条含「3 秒一帧」实测节拍；既有 3 条中 2 条通过） |
| 6 | 重复 `recognize_req` 不导致 8 路重复扫描（计数断言）。 | `test_end_to_end_recognition.py::testDuplicateRequestsInFlightShareOneScan` | 已覆盖（既有用例通过） |

**补充编号 D-1 ~ D-9（本轮第三轮修复引入；此编号仅用于本表，不是 `references/decisions.md` 的 `D-xx` 裁决编号）**

| 补充编号 | 验收项（本轮修复引入） | 对应用例名 | 覆盖结论 |
| --- | --- | --- | --- |
| D-1 | 检测结果缺 `roiId` 必须**显式判错**，不得静默塌缩成一个空分组（`roiIdOf` 返回 `None`，`aggregateByRoi` 抛 `EdgeError(CONFIG)`） | `test_stage_c5_recognition.py::test_c5_3_missing_roi_id_is_not_swallowed` | 已覆盖（新增 1 条，通过） |
| D-2 | **配置兜底链路明确废弃**：未装载 ROI 对照表 → **启动即 Fail-Fast**（`EdgeError(CONFIG)`），不得带着空台账上线 | `test_stage_c5_recognition.py::test_c5_3_config_fallback_path_is_unavailable`；`test_round3_defect_fixes.py::test_roi_binding_table_missing_fails_fast`、`::test_roi_binding_table_empty_fails_fast`、`::test_roi_binding_table_loaded_returns_rows` | 已覆盖（新增 4 条，通过） |
| D-3 | **同一后端不同实现必须等价**：onnxruntime 分支须做同类别 NMS（IoU 阈值构造注入），默认后端固定 `ultralytics`，onnx 分支显式标注「需现场标定」 | `test_round3_defect_fixes.py::test_onnx_backend_applies_non_maximum_suppression`、`::test_nms_threshold_is_injected`、`::test_onnx_backend_is_marked_as_needing_field_calibration`、`::test_two_backends_output_count_within_tolerance`；`test_business_closure.py::test_two_inference_backends_share_detection_keys` | 已覆盖（新增 5 条，通过） |
| D-4 | 对照表 `worker_id` **不得超过实际采集线程数**，装配期校验 | `test_round3_defect_fixes.py::test_roi_worker_id_beyond_actual_worker_count_fails_fast`、`::test_loader_rejects_worker_id_out_of_base_range`；`test_business_closure.py::test_roi_worker_scope_fails_fast` | 已覆盖（新增 3 条，通过） |
| D-5 | 相机状态判定：**从未成功打开过的设备一律 `offline`**；状态取值只允许 `ok` / `offline` 两态（取图失败归并到 `offline`，避免上位机开柜闸门误放行） | `test_round3_defect_fixes.py::test_camera_never_opened_reports_offline`、`::test_camera_unreachable_reports_offline`、`::test_camera_status_values_are_limited`；`test_business_closure.py::test_camera_status_follows_physical_order`、`::test_periodic_frame_camera_status_matches_usb` | 已覆盖（新增 5 条，通过） |
| D-6 | 识别背压需**有丢弃计数与抽样日志**（可观测性，不得静默丢帧） | `test_round3_defect_fixes.py::test_dropped_frames_are_counted_and_logged_by_threshold` | 已覆盖（新增 1 条，通过） |
| D-7 | 业务闭环降级**不丢货位**：聚合超时降级出帧 / 单路失败降级补齐 / 识别异常也有应答 / 第二轮请求各回各的帧 / 停机清空运行态 | `test_round3_defect_fixes.py::test_degraded_frames_match_host_protocol`、`::test_recognition_error_degraded_items_match_host_protocol`、`::test_stop_clears_runtime_state`；`test_business_closure.py::test_worker_failure_still_yields_protocol_ack`、`::test_aggregation_timeout_forces_degraded_ack`、`::test_recognition_error_still_answers_request`、`::test_second_request_gets_its_own_ack`、`::test_real_tcp_serves_two_requests_and_keeps_decode_thread`、`::test_stop_system_clears_aggregation_state` | 已覆盖（新增 9 条，通过） |
| D-8 | 类别组合表优先于单标志直映（两张表并存不打架） | `test_round3_defect_fixes.py::test_class_item_map_takes_priority_over_single_marker` | 已覆盖（新增 1 条，通过） |
| D-9 | 图表交付与**可复跑自检**（两张 HTML + 自检脚本），且图必须与真实代码一致 | `edge/docs/refactor/stages/dplus/verify_diagram_screenshot.py`（非 pytest 用例，见 ③.6 说明与 ④.2 第 7 组命令）；类图 53 节点 / 18 条跨层关系、图 2 30 节点 / 35 连线、图 3 17 节点 / 17 连线 | 已覆盖（读盘计数核对通过；本 agent 未实跑浏览器自检，见 0.1） |

> 补充说明：验收项 3 的「桩校验通过」在本阶段被拆成两层分别取证——
> ① **上位机代码逻辑复刻校验**（`host_protocol_checker.py` 逐条复刻上位机 `EdgeService::parseItems`）+ 上位机自带编译产物 `test_edge.exe` 实跑互证；
> ② **真实上位机进程联调**（`live_link_check.py` 拉起真实 `QtSmartCabinet.exe`，以边缘机身份接入 9000 端口，用上位机自己的日志取证）。
> 两者结论与差异详见 ③ 与 ⑥。

---

## ② 使用了哪些 Fake、各自模拟什么边界

| Fake 名称 | 对应接口 | 模拟的边界 / 异常 | 为何本阶段需要 |
| --- | --- | --- | --- |
| `edge/tests/integration/fake_host.py::FakeHost` | 桩上位机（无接口，直接实现协议收发） | 监听临时端口、按 `\n` 切帧、`validateAck` / `validatePeriodic` 校验 | 验收项 3/4/6 的桩上位机侧；既有件，本阶段复用不改 |
| `edge/tests/integration/tcp_client_socket.py::TcpClientSocket` | `edge/interfaces/i_socket.py::ISocket` | 真实 TCP 客户端套接字，连接失败转 `EdgeError(LINK_DOWN)` | 让联调走真实网络栈，而不是内存管道 |
| `edge/tests/fakes/fake_recognition_engine.py::FakeRecognitionEngine` | `edge/interfaces/i_recognition_engine.py::IRecognitionEngine` | 返回预设检测项、不做真实推理 | 驱动真实 `RecognitionWorker` 组帧路径，隔离模型依赖 |
| `edge/tests/fakes/fake_logger.py::FakeLogger` | `edge/interfaces/i_logger.py::ILogger` | 记录日志、不落盘 | 联调不产生磁盘垃圾 |
| **`edge/tests/integration/test_upper_host_protocol_parity.py::FrameRecorderSocket`（本阶段新增）** | `edge/interfaces/i_socket.py::ISocket` | 记录每次出网帧字节与单调时刻，发送恒成功 | 验收项 5「3 秒一帧」必须实测节拍，不能只断言配置值 |
| **`edge/tests/integration/host_protocol_checker.py`（本阶段新增，作为「上位机侧裁判」）** | 非 Fake：逐条复刻上位机 `EdgeService::parseItems` / `parsePeriodic` / `ToolService::compareOrderWithRecognition` 的校验与判定 | 违规返回可读中文原因（区分「上位机拒收」与「协议不容但上位机忽略」） | 验收项 3/5 需要一个上位机口径的裁判；上位机是 GUI 程序且 `parseItems` 在匿名命名空间内不可单独调用，故按源码逐条复刻并用上位机自带二进制互证 |
| **真实上位机进程 `build/Debug/QtSmartCabinet.exe`（真实进程，非 Fake）** | 上位机 `EdgeService` / `EdgeLink` 全量真实代码 | 真实 TCP 服务端、真实 MySQL 连库、真实日志落盘 | 唯一能证明「真实上位机收到了我们的帧并按协议解析」的证据来源 |

### 2.1 本轮第三轮新增的测试替身（均在测试目录内，不进入生产代码）

| 替身名称 | 所在文件 | 模拟的边界 / 异常 | 为何本轮需要 |
| --- | --- | --- | --- |
| `BlockingStitcher` | `edge/tests/integration/test_round3_defect_fixes.py:60` | 拼图时阻塞在 `Barrier` 上 | 制造「识别线程忙」的确定性场景，用于举证丢帧计数与抽样日志（D-6） |
| `FakeArray` | `edge/tests/integration/test_round3_defect_fixes.py:100` | 二维数组桩：形状 / 转置 / 二维切片 | 模拟 onnxruntime 输出张量（形状与真机一致），使 NMS 可在无真机时确定性举证（D-3） |
| `buildFakeArrayLibrary` | `edge/tests/integration/test_round3_defect_fixes.py:142` | 数值计算库桩，只提供 `argmax` | 同上 |
| `RecordingCaptureSink` / `buildCaptureSink` | `edge/tests/integration/test_round3_defect_fixes.py:154-170` | 采集成功 / 失败回调，只记录不落盘 | 驱动真实 `UsbController` 取相机状态而不产生磁盘垃圾（D-5） |
| `StubStitcher` / `MarkerEngine` / `StubCamera` | `edge/tests/integration/test_business_closure.py:67-120` | 拼接裁剪固定字节、样例标志全命中、指定设备序号打开失败 | 构造「某一路相机打不开」的业务闭环场景（D-7） |
| `FakeHost` / `TcpClientSocket`（既有件，本轮复用） | `edge/tests/integration/fake_host.py`、`tcp_client_socket.py` | 桩上位机、真实 TCP 客户端 | D-7 的「真实 TCP 栈上连续两次请求」用例走真实网络栈 |


---

## ③ 用例表

### 3.1 上位机侧裁判校验器（新增 `host_protocol_checker.py`）复刻的上位机规则

| 序号 | 上位机源码位置 | 复刻的规则 | 复刻函数 |
| --- | --- | --- | --- |
| R1 | `src/comm/EdgeService.cpp:401-408` | `items` 缺失或不是数组 → 整帧拒绝 | `check_items` |
| R2 | `src/comm/EdgeService.cpp:62-65` | `items` 元素不是对象 | `check_items` |
| R3 | `src/comm/EdgeService.cpp:68-72` | `position` 缺失、为空或不是字符串 | `check_items` |
| R4 | `src/comm/EdgeService.cpp:73-77` | `tool_id` 缺失或不是字符串（空串合法） | `check_items` |
| R5 | `src/comm/EdgeService.cpp:78-87` | `confidence` 缺失/非数值；`0 ≤ v ≤ 1` | `check_items` |
| R6 | `src/comm/EdgeService.cpp:88-94` | `alert_type` 缺席按 `none` 兼容；带上必须是枚举内字符串 | `check_items` |
| R7 | `src/comm/EdgeService.cpp:95-100` | 同一 `position` 重复上报 | `check_items` |
| R8 | `src/comm/EdgeService.cpp:389-396` | `recognize_ack` 的 `request_id` 必须是 snake_case 且与在途请求配对 | `check_ack` |
| R9 | `src/comm/EdgeService.cpp:118-132` | `periodic` 帧形状（`uptime_sec` / `software_version` / `camera_status`） | `check_periodic` |
| R10 | `src/comm/EdgeService.cpp:239-247` | `allCamerasOk()` 开柜闸门：任一路非 `ok` 即拒开柜 | `check_periodic`（notes） |
| R11 | `src/comm/CommTypes.h:37-42` + `spec-digest §1.5` | `items[]` 每项恰好 4 键；`present`/`alert_level`/`class_id`/`tool_name` 禁止上线 | `check_items`（extraKeys） |
| R12 | `src/services/ToolService.cpp:115-218` | 清单覆盖口径；出库「取出正确」判据 = `tool_id` 为空串 | `check_coverage` / `judgeOutbound` / `judgeInbound` |

### 3.2 新增一致性用例（`test_upper_host_protocol_parity.py`，13 条）

| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| `testHostAcceptsRealSimulatorLegalScenes` | 上位机模拟器 7 个内置合法场景的真实 items（正常/有借有还/空清单/错放/未知物/置信度不足/missing） | 校验器全部判通过，无结构错误、无多余字段 | `errors == ()`、`extraKeys == ()`，7 个场景全过 | 通过 |
| `testHostAcceptsTc24CompatibilityFrames` | TC-24-12 缺 `alert_type`、TC-24-14 带 `present`、TC-24-15 空货位 `tool_id=""`、TC-23E 顶层多带 `extra` | 上位机全部放行；`present` 只进 extraKeys 不进 errors | 4 帧全部 `hostAccepts is True`；`present` 命中 `extraKeys` | 通过 |
| `testHostRejectsRealSimulatorBadFrames` | 13 条上位机明确拒绝的非法帧（TC-24-01/02/03/04/07/08/09/10/11/13/16/17 + `confidence=-1`） | 全部判失败，且错误文案与上位机**逐字一致** | 13 条 `hostAccepts is False`，`errors` 与期望元组完全相等 | 通过 |
| `testAckItemMustCarryExactlyFourKeys` | 4 字段基线项 / 带 `present` 项 / 缺 `alert_type` 项 | 基线干净；`present` 单列为协议多余字段；缺 `alert_type` 仍合规 | `extraKeys == ("第1项携带协议禁止字段 present",)`，其余为空 | 通过 |
| `testAckRequestIdMustBeSnakeCase` | 驼峰 `requestId` 帧 / 缺 `request_id` 帧 / `request_id` 不匹配帧 | 三种都必须判失败并点名 `request_id` | 三条均 `hostAccepts is False`，错误文案含 `request_id` | 通过 |
| `testPeriodicFrameShapeAndCameraGate` | 8 路全 ok 周期帧 / CAM3=offline 周期帧 / `status="broken"` 周期帧 | 全 ok 判闸门放行；offline 判闸门拒绝并点名 `CAM3(offline)`；非法 status 判错 | 三条断言全部成立 | 通过 |
| `testPeriodicFrameIsSentEveryThreeSeconds` | 生产配置 `heart_interval_sec`，真实 `TcpHeartThread` + 记录型套接字 | 配置值 = 3.0；9 秒内至少 2 帧；两帧间隔落在 2.7~3.9 秒；帧形状合规 | 配置 = 3.0；发出 2 帧；间隔落在区间内；`check_periodic` 无错 | 通过 |
| `testCoverageAndOutboundJudgementMatchHost` | 空清单 / 少报一个货位 / 全量清单；出库与入库判据各 3 例 | 空清单判覆盖不全；少报点名缺失货位；出库按 `tool_id` 空串判取出正确 | 全部断言成立 | 通过 |
| `testEdgeSourcesDoNotEmitRemovedFields` | 扫描 `edge/modules/recognition/`、`edge/control/` 全部 `.py` 的带引号键名字面量 | 不得出现 `present` / `alert_level` / `class_id` / `tool_name` | `findings == []` | 通过 |
| `testEdgeAckItemsCarryNoInternalFields` | 扫描 `edge/modules/recognition/` 的带引号键名字面量 | `items[]` 不得带 `roiId` / `className` / `item` / `boundItem` | `findings == []`（c5plus 落地后） | 通过 |
| `testEdgeProductionAckMatchesHostProtocol` | 真实 `RecognitionWorker.runLoop()` 跑一轮，捕获其产出的应答帧 | 该帧必须被上位机校验器放行，且无协议外字段 | `hostAccepts is True`、`protocolClean is True` | 通过 |
| `testEdgeAckFrameTopLevelKeysAreProtocolExact` | 同上 | 顶层键恰好 `{type, request_id, items}`；`request_id` 原样回带 | `set(ack.keys()) == {"type","request_id","items"}`，`request_id == "req-sim-0001"` | 通过 |
| `testEdgeAckFrameHasNoInternalTopLevelKeys` | 扫描识别模块的顶层内部键名字面量 | 不得出现 `requestId` / `workerId` | `findings == []`（c5plus 落地后） | 通过 |

### 3.3 既有联调用例（`test_end_to_end_recognition.py`，本阶段未修改）

| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| `testEndToEndAckFieldsAreProtocolCompliant` | 桩上位机 → 真实 TCP → 边缘机回 `recognize_ack` | 桩校验通过、`request_id` 匹配、只扫描 1 次 | `validateAck(ack) == []`、`request_id == "req-e2e-0001"`、`scanCount == 1` | 通过 |
| `testSameRequestIdIsIdempotent` | 同一 `request_id` 连发 2 次 | 只扫描 1 次、回 2 次相同结果 | `items` 两次相同、`scanCount == 1` | 通过 |
| `testDuplicateRequestsInFlightShareOneScan` | 请求在途时连发 3 次同一 `request_id` | 只触发 1 次扫描，回 3 帧相同结果 | `scanCount == 1`，3 帧 `items` 相同 | 通过 |
| `testPeriodicFrameFormatAndCameraStatus` | 真实 TCP 上的周期帧 | `type=periodic`、8 路 `camera_status`、桩校验通过 | `validatePeriodic(frame) == []`、`len(camera_status) == 8` | 通过 |
| `testLinkDownFallsBackToEventCache` | 上位机断链后再发请求 | 应答出队但入事件缓存 | `getOutboxCount() == 0`、`cache.pendingCount() == 1` | 通过 |
| `testProductionConfigHasRequiredKeys` | `edge/config/config.ini` | 周期 3 秒、8 路相机索引、4 组目录等键齐全 | 全部键值断言成立 | 通过 |
| `testRoiBindingHeaderMatchesContract` | `edge/config/roi_binding.csv` 表头 | 表头 = 12 列契约（`roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,confidence,rect_x1,rect_y1,rect_x2,rect_y2`） | c5plus 按 spec-digest §8.1 把表头同步为 12 列后，本用例断言的列名、列数、列下标全部对齐 | 通过（c5plus 已同步，见 ⑤ 留档表） |

### 3.4 真实上位机进程联调（`live_link_check.py`，6 个取证点）

执行对象：`D:\CFDZ\smartCabinet\trunk\SmartCabinetLite\build\Debug\QtSmartCabinet.exe`（Debug x64，Qt 6.5.3）
上位机日志由上位机自己写到临时目录（`SC_LOG_DIR` 环境变量指向 `%TEMP%\edge_live_host_*`），**未向上位机工程写入任何文件**。

| 取证点 | 发送的帧 | 上位机真实日志 | 结论 |
| --- | --- | --- | --- |
| 上位机在 9000 端口监听 | — | `[EdgeLink] listening on port 9000` | 通过 |
| 边缘机已连上上位机 | TCP 连接 | `[EdgeLink] client connected "::ffff:127.0.0.1" id= 3045963220144` | 通过 |
| 上位机收到并解析 `periodic` | `{"type":"periodic","uptime_sec":1,"software_version":"edge-live-0.1.0","camera_status":[CAM1..CAM8 ok]}`（408 字节） | `[EdgeLink] 收到帧 type= "periodic" 字节= 408 id= 3045963220144` | 通过 |
| `request_id` 用 snake_case 才被上位机读到 | `{"type":"recognize_ack","request_id":"req-live-0001","items":[{position,tool_id,confidence,alert_type}]}`（159 字节） | `[EdgeService] 丢弃帧 # 1 : "req-live-0001"` —— 编号被回带，证明上位机读到了 `request_id` | 通过 |
| 驼峰 `requestId` 上位机读不到 | 同上但键名写 `requestId`（158 字节） | `[EdgeService] 丢弃帧 # 2 : ""` —— 编号为空，证明上位机**不读** `requestId` | 通过 |
| 未知 `type` 按协议 3.6-② 丢弃 | `{"type":"weird_type","request_id":"req-live-0001"}`（54 字节） | `[EdgeService] 丢弃帧 # 3 未知type: "weird_type"` | 通过 |

取证点命中 **6/6**。

### 3.5 上位机自带编译产物（真实上位机代码，`build/tests/Debug/test_edge.exe`）

这是**上位机自己的**单元测试二进制（编译自真实 `EdgeService` / `EdgeSimulator` 源码），用于给「上位机认不认这个帧」提供权威判据。

| 用例名 | 输入 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| `TestEdge::structure_validFramesPassed` | 5 帧（正常 / 空清单 / 缺 `alert_type` / 带历史 `present` / 空 `tool_id`） | 全部放行 | 5 次「识别回应已配对」 | 通过 |
| `TestEdge::structure_badFramesRejected` | 13 帧非法结构 | 全部拒绝并写明原因，零个成功信号 | 13 条 `识别清单结构校验失败`，文案与本阶段校验器**逐字一致** | 通过 |
| `TestEdge::structure_fieldValuesParsed` | 字段齐全帧 + 缺 `alert_type` 帧 | 按原值解析，缺席按 `none` | 2 条，`alertType` 默认 `none` | 通过 |
| `TestEdge::alertTypes_sharedEnumAcceptedByHost` | 5 个 `alert_type` 枚举值逐个 | 5 个都被上位机接受 | 5 次配对成功 | 通过 |
| `TestEdge::recognize_fullGroupWithEmptySlots` / `recognize_fullGroupLargeFrame` | 6 条 / 107 条全柜清单；货位重复 | 整帧放行；重复货位整帧拒绝 | 6 条与 107 条放行；重复时「第108项货位 A-01-01 重复上报」 | 通过 |
| 其余用例 | 摄像头闸门、离线拒发、3.6-③ 去重、开箱回应、未知 type 丢弃等 | 全部符合协议 | `Totals: 36 passed, 0 failed, 0 skipped, 0 blacklisted, 9947ms` | 通过 |

### 3.6 本轮第三轮修复对应的验证用例（新增 30 条，随全量实跑 162 通过）

> **本节数字口径**：下表「断言值」列是**用例源码里写死的具体期望值**（逐条读盘核对，非编造）；「结论」列的「通过」来自 2026-11-14 第三轮全量实跑 `162 passed / 0 failed / 0 skipped`（该轮历史留档），并已由**主 Agent 与最终独立审查 Agent 各自实跑的当前最终门禁** `pytest edge/tests -q` = `298 passed / 1 warning`、`pytest edge/tests/integration -q` = `91 passed / 1 warning` 复核（来源声明见 0.1）。
> 30 = 17（`test_round3_defect_fixes.py`）+ 11（`test_business_closure.py`）+ 2（`test_stage_c5_recognition.py` 缺陷用例），与第三轮 132 → 162 的增量自洽（历史留档；当前全量为 298 passed，见 0.1 与 ⑤）。

#### 3.6.1 缺陷 1 —— `roiId` 永不产生 / 兜底链路失效（2 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_c5_3_missing_roi_id_is_not_swallowed` | 检测项 `{"className":"tool","confidence":0.9}`（无 `roiId`）；另一项带 `roiId:"r1"` | 缺 `roiId` 不被静默吞掉；按区域归集时直接判配置错 | `roiIdOf(无 roiId 项) is None`；`roiIdOf({"roiId":"r1",...}) == "r1"`；`aggregateByRoi([无 roiId 项])` 抛 `EdgeError` 且 `error.code == ErrorCode.CONFIG` | 通过 |
| `test_c5_3_config_fallback_path_is_unavailable` | 对照表行传 `None`（走配置兜底链路） | 兜底链路**不可用**，不产误导条目，只产 1 条配置错误 | `sink.resultEvents == []`；`len(sink.errorEvents) == 1`；`workerId == 1`；`exception.code == ErrorCode.CONFIG`；日志含「兜底链路不可用」 | 通过 |

#### 3.6.2 缺陷 2 —— 对照表缺失必须启动即失败（3 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_roi_binding_table_missing_fails_fast` | 不存在的 CSV 路径 | 装配期判配置错 | `error.code == ErrorCode.CONFIG`；错误文案含「未装载 ROI 对照表」 | 通过 |
| `test_roi_binding_table_empty_fails_fast` | 只有 12 列表头、无数据行的 CSV | 装配期判配置错 | `error.code == ErrorCode.CONFIG`；文案含「未装载 ROI 对照表」 | 通过 |
| `test_roi_binding_table_loaded_returns_rows` | 随工程发布的 `edge/config/roi_binding.csv` | 装载成功并拿到 4 行 | `len(rows) == 4`；`rows[0].position == "A-01-01"` | 通过 |

#### 3.6.3 缺陷 3 —— `worker_id` 越界（3 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_roi_worker_id_beyond_actual_worker_count_fails_fast` | 对照表行 + 实际采集线程数 `2`（现场只有 2 对相机，表里写了第 3、4 号线程） | 装配期判配置错 | `error.code == ErrorCode.CONFIG`；文案含「worker_id 超出实际采集线程数」 | 通过 |
| `test_loader_rejects_worker_id_out_of_base_range` | `worker_id=9` 的 CSV | 装载器侧保留 1~4 基础区间校验 | `error.code == ErrorCode.CONFIG`；文案含「工作线程编号越界」 | 通过 |
| `test_roi_worker_scope_fails_fast` | 对照表行 + 实际线程数 `WORKER_COUNT - 1` | 装配期判配置错 | `error.code == ErrorCode.CONFIG` | 通过 |

#### 3.6.4 缺陷 4 —— onnxruntime 分支缺 NMS（5 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_onnx_backend_applies_non_maximum_suppression` | 8 个目标（两个高度重叠、远处两个、一个低置信、其余极低分） | 重叠框被抑制，条数与置信度收敛 | `len(items) == 3`；`sorted(confidence) == [0.60, 0.80, 0.90]`；`className == ["person","person","frisbee"]` | 通过 |
| `test_nms_threshold_is_injected` | 同一组输入，阈值注入 `0.95` | 阈值是构造注入项，放宽后重叠框都保留 | `engine.getNmsIouThreshold() == 0.95`；`len(items) == 4` | 通过 |
| `test_onnx_backend_is_marked_as_needing_field_calibration` | 引擎 + `FakeLogger` | onnx 分支显式标注「需现场标定」 | `ONNX_BACKEND_CALIBRATION_NOTE` 含「标定」；`logger.infoRecords` 中至少 1 条含「标定」 | 通过 |
| `test_two_backends_output_count_within_tolerance` | 真机对比：`weights/yolov8n.pt`（ultralytics）+ `weights/yolov8n.onnx`（onnxruntime），样例图 `dual_crop_stitch/88.jpg` | 抑制前 onnx 出 62 条，抑制后必须落到与 ultralytics 同量级 | `len(ultraItems) == 6`；`0 < len(onnxItems) <= len(ultraItems) * 2`；两条后端产出的检测项**都不含 `roiId` 键** | 通过（`62 → 8` 条的实测口径记于 handoff §3.1 第 3 条） |
| `test_two_inference_backends_share_detection_keys` | 两条后端各造 1 个检测结果 | 两条后端产出的键名一致 | 两边 `sorted(keys()) == ["className","confidence"]` 且两边相等 | 通过 |

#### 3.6.5 缺陷 5 —— 相机状态把「从未打开」报成 `ok`（5 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_camera_never_opened_reports_offline` | 2 路真实 `CameraDevice`（从未打开） | 一律 `offline` | `status == ["offline","offline"]` | 通过 |
| `test_camera_unreachable_reports_offline` | `reachabilityProbe` 返回 `False` 的设备 | 打开抛采集错，状态仍 `offline` | `device.open()` 抛 `EdgeError` 且 `code == ErrorCode.CAPTURE`；`status == ["offline","offline"]` | 通过 |
| `test_camera_status_values_are_limited` | 1 组相机对 | 状态取值只允许 2 种 | `set(status) <= {"ok","offline"}`；`camera_id == ["CAM1","CAM2"]` | 通过 |
| `test_camera_status_follows_physical_order` | 8 路相机，第 2、3 组打不开 | 状态按**物理编号**排，不按采集线程顺序交错 | `camera_id == ["CAM1".."CAM8"]`；`status == ["ok","ok","offline","offline","ok","ok","ok","ok"]` | 通过 |
| `test_periodic_frame_camera_status_matches_usb` | `buildSystem(parts)` 装配后读周期帧状态来源 | 周期帧里的状态与采集门面物理顺序一致 | `len(statuses) == 8`；`camera_id == ["CAM1".."CAM8"]` | 通过 |

#### 3.6.6 缺陷 6 —— 识别忙时丢帧无可观测性（1 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_dropped_frames_are_counted_and_logged_by_threshold` | 第 1 轮识别阻塞在 `Barrier`，随后连续触发 12 次 | 有丢弃计数；日志按阈值抽样不逐帧刷屏 | 第 1 次 `trigger(...) is True`；后续 12 次 `is False`；`getDroppedFrameCount() == 12`；丢弃日志条数 `== 1` 且文案含「累计 10 次」 | 通过 |

#### 3.6.7 缺陷 7 —— 降级与闭环（第 8 条中的 9 条：降级 6 条 + 停机 2 条 + 组合表 1 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_degraded_frames_match_host_protocol` | 聚合等待上限 `0.1 s` 到点、无 worker 上报 | 自动降级出帧，且帧形状过上位机校验 | 出网 `recognize_ack` 恰好 1 帧；`check_ack(...).hostAccepts is True`；`.protocolClean is True`；`check_coverage(items, ["A-01-01"]).hostAccepts is True` | 通过 |
| `test_recognition_error_degraded_items_match_host_protocol` | 某 worker 报 `EdgeError(INFERENCE_TIMEOUT)` | 失败帧与降级应答帧都出网，应答帧仍合规 | `recognize_ack` 恰好 1 帧；`hostAccepts is True`；`len(items) == 1`；覆盖 `A-01-01` 通过 | 通过 |
| `test_worker_failure_still_yields_protocol_ack` | 2 组相机中第 2 组打不开 | 整轮仍产出协议形状的应答，坏路降级、好处正常 | 顶层键 `== {"type","request_id","items"}`；`positions == ["A-01-01","A-01-02","A-01-03","A-01-04"]`；坏路 `tool_id == ""` / `alert_type == "unknown"` / `confidence == 0.0`；好路 `tool_id == "C01-T0007"` / `alert_type == "none"`；`check_ack` 与 `check_coverage` 均通过 | 通过 |
| `test_aggregation_timeout_forces_degraded_ack` | 聚合等待上限 `0.2 s` 到点 | 请求不悬着不回，降级帧覆盖全部货位 | 出网 1 帧；顶层 3 键；`positions` 4 条齐全；全部 `tool_id == ""`、`alert_type == "unknown"`；`check_ack` 通过 | 通过 |
| `test_recognition_error_still_answers_request` | 3 路正常 + 1 路抛推理超时 | 失败那一路降级补齐后清单仍覆盖全部货位 | `positions == ["A-01-01","A-01-02","A-01-03","A-01-04"]`；降级条 `tool_id == ""` / `alert_type == "unknown"`；`check_ack` 通过 | 通过 |
| `test_second_request_gets_its_own_ack` | 连续两次不同 `request_id` | 第二个请求拿到自己的应答 | 两次应答的 `request_id` 分别为 `req-second-0001` / `req-second-0002`；第二次 `check_ack` 通过 | 通过 |
| `test_real_tcp_serves_two_requests_and_keeps_decode_thread` | 真实 TCP 栈上连续两次请求 | 两次都拿到应答，解码线程不被业务异常打穿 | 两个 `request_id` 各回一帧且 `check_ack` 通过；`TcpDecode` 存活线程数 `== 1` | 通过 |
| `test_stop_clears_runtime_state` / `test_stop_system_clears_aggregation_state` | 停机前有在途请求 / 聚合中间态 / 待发应答 | 停机后不残留运行态 | 停机前 `getPendingRequestCount() == 1`、`getAggregationCount() == 1`、`getOutboxCount() == 1`；停机后三项归 `0`，`getCompletedAckCount() == 0` | 通过 |
| `test_class_item_map_takes_priority_over_single_marker` | 类别组合表 `{person,surfboard} → 滑板人偶` | 组合命中优先；组合查不到退回单标志直映；名字对不上不误判 | 组合命中 `detected is True` 且 `confidence == 0.83`（组合取最低值，原 0.91 为 person/surfboard 中较高者）；单标志 `detected is True` 且 `confidence == 0.88`；名字对不上 `detected is False` | 通过 |

#### 3.6.8 配置说明文档（1 条）

| 用例名 | 输入 | 预期 | 断言值（用例源码口径） | 结论 |
| --- | --- | --- | --- | --- |
| `test_config_readme_documents_marker_and_worker_rules` | `edge/config/README.md` | 配置说明写清标志类别名口径与线程编号口径 | 文本含 `marker_id`、`类别名`、`worker_id`、`上板` 四个关键字 | 通过 |

#### 3.6.9 图表自检（非 pytest 用例）

| 对象 | 方法 | 实际（读盘计数，本 agent 独立核对） | 结论 |
| --- | --- | --- | --- |
| `edge/docs/refactor/stages/dplus/edge_class_diagram.html` | 逐条数 `NODES` / `ARROWS` 数组条目 | `NODES` **53** 条、`ARROWS` **18** 条（页面自检文案亦按这两个数组长度输出） | 通过（节点/关系计数与页面内置自检口径一致） |
| `edge/docs/refactor/stages/dplus/edge_recognition_flow.html` | 逐条数 `F2.nodes/edges`、`F3.nodes/edges` | 图 2 **30** 节点 / **35** 连线；图 3 **17** 节点 / **17** 连线 | 通过 |
| `edge/docs/refactor/stages/dplus/verify_diagram_screenshot.py` | 读脚本源码 | 起临时 `http.server`（`file://` 会被浏览器拦）+ `playwright` msedge 通道截图 + 打印页面「布局自检」结果 | 脚本存在且逻辑完整；**本 agent 未实跑**（无命令执行工具 / 无浏览器环境），浏览器内自检结果待具备环境时复跑 |

---

## ④ 可复现的完整运行命令与运行环境

### 4.1 运行环境

| 项 | 值 |
| --- | --- |
| OS | Windows 11（`platform.platform()` = `Windows-10-10.0.26300-SP0`），win32 |
| Python | 3.9.7（MSC v.1916 64-bit），`D:\Anaconda3\python.exe`（**无独立 venv**，直接用 Anaconda 基础环境） |
| pytest | 6.2.4（与 `edge/pyproject.toml:12` 声明的 `pytest>=7.4,<9` **存在版本偏差**：本机 6.2.4 低于声明下界。因此 `[tool.pytest.ini_options]` 的 `pythonpath` 配置项不被识别，每次运行打印 `PytestConfigWarning: Unknown config option: pythonpath` —— 这就是最终门禁 `298 passed, 1 warning` 与 `91 passed, 1 warning` 里那条 warning 的来源。用例仍能收集执行：仓库根已在 `sys.path`（`edge/` 与 `edge/tests/` 都有 `__init__.py`，pytest 自动把仓库根插入 `sys.path`），该告警**不影响用例收集与通过数**。处置见本节末尾「环境对齐遗留项」登记） |
| ruff | 0.17.5 |
| mypy | 1.19.1（compiled: yes），`python_version = 3.9`、`strict = true` |
| 覆盖率工具 | **未安装**（无 pytest-cov / coverage），故 ⑤ 的覆盖率一栏填「不可测」 |
| 工作目录 | `d:\CFDZ\BYJSJ\New-SmartCabinet`（仓库根） |
| 上位机工具链 | Qt 6.5.3 + MSVC 2019（`test_edge.exe` 自报），Debug x64；上位机工程**只读引用，未做任何修改** |
| MySQL | `127.0.0.1:3306` / 库 `smart_cabinet` / `root:root`（上位机 `build/Debug/system.ini` 已配）；驱动 `MySQL ODBC 8.0 Unicode Driver`（64 位）已安装 |
| 上位机启动耗时 | 实测从进程启动到进入事件循环约 16 秒（连库 → 建页 → 起人脸相机 → 加载人脸模型）；`live_link_check.py` 以日志标志 `showEvent` 判定就绪，不做探测式连接 |
| 推理后端依赖（本轮第三轮新增用例需要） | `test_two_backends_output_count_within_tolerance` 用 `importlib.util.find_spec` 断言 `ultralytics` 与 `onnxruntime` **存在**；本 agent 无命令执行工具，**未能核实本机是否已安装这两个包**。权重 `weights/yolov8n.pt`（6.25 MB）、`weights/yolov8n.onnx`（12.74 MB）与样例图 `dual_crop_stitch/88.jpg` **已在磁盘核实存在** |
| 图表自检依赖 | `playwright`（`chromium.launch(channel="msedge")`）+ 临时 `python -m http.server`；本轮**未实跑**（无命令执行工具 / 无浏览器环境），浏览器内「布局自检」结果待具备环境时复跑 |

> **环境对齐遗留项（需用户批准，本轮不落地）**：本机 `pytest 6.2.4` 与 `edge/pyproject.toml:12` 声明的 `pytest>=7.4,<9` 存在版本偏差，导致 `pythonpath` ini 选项不被识别、每次运行打印 `PytestConfigWarning: Unknown config option: pythonpath`。因仓库根已在 `sys.path`（见上表 pytest 行），用例收集与执行不受影响，298 / 91 两次门禁各带 1 条该 warning，与用例结论无关。收敛路径二选一，**均需用户批准后方可实施**：① 把本机 pytest 升级到 `>=7.4,<9`（则 `pythonpath` 生效、warning 消失）；② 若须维持 6.2.4，则由用户批准修改 L1 `edge/pyproject.toml` 的声明或移除该项。本轮不动 L1、不擅自升级环境，仅如实登记。归属：环境对齐遗留项。

### 4.2 完整命令

```bat
:: 1) 静态检查（全量 edge）
cd /d d:\CFDZ\BYJSJ\New-SmartCabinet
python -m ruff check edge
python -m mypy edge

:: 2) 新增协议一致性用例（13 条，约 6.2 秒）
python -m pytest edge/tests/integration/test_upper_host_protocol_parity.py -v --no-header

:: 3) 全量测试套件
python -m pytest edge/tests -q --no-header

:: 4) 真实上位机进程联调（拉起 QtSmartCabinet.exe，约 33 秒）
python -m edge.tests.integration.live_link_check
::    可选：指定其它上位机可执行文件
python -m edge.tests.integration.live_link_check "D:\path\to\QtSmartCabinet.exe"

:: 5) 上位机自带编译产物（真实上位机代码，权威判据）
::    QTest 是 WIN32 程序无控制台，用 -o 落文件再读
python -c "import subprocess,os,tempfile;out=os.path.join(tempfile.gettempdir(),'test_edge_results.txt');subprocess.run([r'd:\CFDZ\smartCabinet\trunk\SmartCabinetLite\build\tests\Debug\test_edge.exe','-o',out+',txt'],cwd=os.path.dirname(out))"
type %TEMP%\test_edge_results.txt

::: 6) 本轮第三轮新增用例（28 条）
python -m pytest edge/tests/integration/test_round3_defect_fixes.py -v --no-header
python -m pytest edge/tests/integration/test_business_closure.py -v --no-header
python -m pytest edge/tests/unit/test_stage_c5_recognition.py -v --no-header

::: 7) 图表自检 + 截图（需 playwright + msedge 通道；脚本自起 http.server）
cd /d d:\CFDZ\BYJSJ\New-SmartCabinet\edge\docs\refactor\stages\dplus
python verify_diagram_screenshot.py docs/refactor/stages/dplus/edge_class_diagram.html class_diagram.png
python verify_diagram_screenshot.py docs/refactor/stages/dplus/edge_recognition_flow.html recognition_flow.png
:::    脚本会打印 [SELF-CHECK] 一行，即页面内置自检结论（类图：53 节点 / 18 条跨层关系；
:::    图 2：30 节点 / 35 连线；图 3：17 节点 / 17 连线）
```

### 4.3 前置条件

- `edge/config/config.ini` 与 `edge/config/roi_binding.csv` 必须存在（周期帧节拍用例与 ROI 表头用例依赖）。
- 真实上位机联调需要：上位机已编译（`build/Debug/QtSmartCabinet.exe`）、MySQL 在跑、`build/Debug/system.ini` 的数据库段可用、9000 端口未被占用。
- `live_link_check.py` 会把上位机日志重定向到 `%TEMP%\edge_live_host_*`，**不会**向上位机工程目录写日志；运行结束后上位机进程由脚本终止。
- 联调副作用（如实记录）：上位机在边缘机断链瞬间会向 `smart_cabinet` 库写一条「与边缘计算机通信中断」告警（`AlertDAO::insertAlert`），这是上位机自身的正常行为，非本次测试引入的缺陷。

---

## ⑤ 汇总

**当前全量口径（最终门禁，由主 Agent 与最终独立审查 Agent 各自实跑，输出见 0.1）**：`pytest edge/tests -q` = **298 passed / 0 failed / 0 skipped / 1 warning**，`pytest edge/tests/integration -q` = **91 passed / 0 failed / 0 skipped / 1 warning**。
**分项表口径**：下表与 3.6 的分项仍是 **2026-11-14 第三轮**按测试文件拆分的历史留档（分项相加 13 + 8 + 17 + 11 + 2 + 101 + 10 = 162，与当时全量 162 自洽），作为 L4 证据保留、不静默改写；第三轮之后的 E/F 组整改与全模块整改新增用例、以及 10 处正常 `parametrize` 参数化，使当前收集数由 162 增至 298，本轮不逐文件重列 298 的分项（避免臆造），故历史分项不与当前 298 相加核对。
（说明：上一版 ⑤ 的分项 13 + 7 + 122 = 142 与全量 132 **不自洽**，该口径错误已在 `handoff.md` §3 标注；本版已按实际文件重新拆分并交叉核对。）

| 范围 | 通过 | 失败 | 跳过 | 总耗时 | 覆盖率 |
| --- | --- | --- | --- | --- | --- |
| **本轮第三轮新增** `test_round3_defect_fixes.py`（17 条） | 17 | 0 | 0 | 见全量 | 不可测（环境无 pytest-cov） |
| **本轮新增** `test_business_closure.py`（11 条，业务闭环二次校验） | 11 | 0 | 0 | 见全量 | 不可测 |
| **本轮新增** `test_stage_c5_recognition.py` 缺陷用例（2 条） | 2 | 0 | 0 | 见全量 | 不可测 |
| 上轮新增 `test_upper_host_protocol_parity.py`（13 条） | 13 | 0 | 0 | 6.13 s（上轮实测） | 不可测 |
| 既有 `test_end_to_end_recognition.py`（8 条） | 8 | 0 | 0 | 见全量 | 不可测 |
| 既有 `edge/tests/unit/**` 其余用例（9 个文件扣除上表 2 条） | 101 | 0 | 0 | 见全量 | 不可测 |
| 既有 `edge/tests/contract/**`（2 个文件） | 10 | 0 | 0 | 见全量 | 不可测 |
| **全量 `python -m pytest edge/tests -q`**（最终门禁） | **298** | **0** | **0** | 1 warning | 不可测（环境无 pytest-cov） |
| **全量 `python -m pytest edge/tests/integration -q`**（最终门禁） | **91** | **0** | **0** | 1 warning | 不可测（环境无 pytest-cov） |
| `python -m ruff check edge`（主 Agent 与最终独立审查 Agent 各自实跑） | `All checks passed!` | — | — | — | — |
| `python -m mypy edge`（主 Agent 与最终独立审查 Agent 各自实跑） | `Success: no issues found in 95 source files` | — | — | — | — |
| 真实上位机进程联调 `live_link_check.py`（6 取证点） | 6 | 0 | 0 | ≈33 s | 不适用 |
| 上位机自带 `test_edge.exe`（36 条，编译产物仍在盘） | 36 | 0 | 0 | 9947 ms | 不适用 |

**按目录交叉核对（读盘逐文件统计测试函数，与上表互为印证）**：

| 目录 | 测试函数数 | 拆分口径 |
| --- | --- | --- |
| `edge/tests/unit/**`（9 个文件） | 103 | = 本轮新增 2 + 既有 101 |
| `edge/tests/integration/**`（4 个文件） | 49 | = 本轮新增 17 + 11 + 上轮 13 + 既有 8 |
| `edge/tests/contract/**`（2 个文件） | 10 | = 既有 10 |
| **合计（第三轮历史留档）** | **162** | **= 当时全量通过数 162；当前最终门禁 298 passed / 91 passed 见本节开头与 0.1** |

- 增量自洽（第三轮历史留档）：上轮全量 132 → 第三轮全量 162，**增量 30 = 17 + 11 + 2**（当时新增用例数，见 ③.6）；当前最终门禁为 298 passed / 91 passed（见本节开头与 0.1）。
- 全库 `parametrize` **10 处**（`edge/tests/unit/test_dplus_assembly_guards.py:128,149,201,236,275,282,412` 共 7 处、`edge/tests/unit/test_dplus_config_doc_parity.py:100,124,192` 共 3 处），均为正常参数化用例，无 `pytest.mark.skip` / `xfail` 掩盖（仅 `edge/tests/contract/test_phase0_foundation.py` 有 1 个 `skipif` 辅助装饰器，Windows 下条件不成立）；故当前「收集数 = 通过数 = 298」成立。
- **数字来源**：当前 `298 passed / 1 warning`（`pytest edge/tests -q`）、`91 passed / 1 warning`（`pytest edge/tests/integration -q`）、`All checks passed!`（ruff）、`Success: no issues found in 95 source files`（mypy）均由主 Agent 与最终独立审查 Agent 各自实跑，输出见 0.1；第三轮历史值 `162 passed, 1 warning in 38.36s` 与「162 个测试函数」为 2026-11-14 留档、不改写。磁盘另行核对的可验证侧面为「10 处 `parametrize` / 无 `skip`、`xfail` 掩盖 / `tcp_socket.py` 已落地 / `AssemblyParts` 43 字段」，行号见 0.1。

### 5.1 全量套件的失败情况

**最终状态：0 失败。**

上轮（第一、二轮）撰写期间（13:53 → 14:00）c5plus 并发落地，全量失败数经历 5 条 → 3 条 → 1 条 → **0 条**，全部由 c5plus 在其白名单内自行同步，本阶段**未**修改任何被测代码、验收项、预期值，未删用例、未加跳过标记。过程中观察到的失败与其归属如下（留档以便追溯）：

| 曾经的失败用例 | 失败原因 | 归属 | 最终处置 |
| --- | --- | --- | --- |
| `test_end_to_end_recognition.py::testRoiBindingHeaderMatchesContract` | c5plus 按 `spec-digest §8.1` 把 ROI 对照表表头改成 12 列（新增 `worker_id`，`rect_*` 改四角点），该用例仍断言旧 11 列表头。实测差异：<br>`- roi_id,drawer_id,position,tool_id,required_type,marker_id,confidence,rect_x,rect_y,rect_width,rect_height`<br>`+ roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,confidence,rect_x1,rect_y1,rect_x2,rect_y2` | c5plus | 已由 c5plus 同步 |
| `test_stage_a_contract_alignment.py::testInterfaceModulesImportNoBusinessModules` | c4plus 新增 `i_camera_focus.py` / `i_frame_sink.py`，接口文件数由 8 变 10，期望表未同步 | c5plus（`spec-digest §8.5` 指定） | 已由 c5plus 同步 |
| `test_stage_a_contract_alignment.py::testAllFakeMethodSignaturesAlignWithInterfaces` | 同上，`assert len(list(INTERFACES_DIR.glob("i_*.py"))) == 8` 现为 10 | c5plus（同上） | 已由 c5plus 同步 |
| `test_stage_c5_recognition.py::test_c5_3_aggregate_lookup_and_build_ack` | c5plus 改了 `buildAck` 签名（`(workerId, requestId, items)` → `(requestId, items)`），该用例仍用旧签名并断言 `ack["requestId"]` | c5plus | 已由 c5plus 同步 |
| `test_stage_c5_recognition.py::test_c5_3_pure_functions_behavior` | c5plus 改了 `validateByTable` 签名（新增 `roiConfig` 参数），该用例仍用旧签名 | c5plus | 已由 c5plus 同步 |

> 本阶段**未**为了让它变绿而修改任何被测代码、验收项、预期值，也未删用例或加跳过标记。以上失败全部属于 c5plus 并发落地过程中的在途不一致。
>
> **第三轮未观察到失败（历史留档）**：当时全量 `162 passed / 0 failed / 0 skipped`。当时新增 30 条用例**没有一条**依赖改写既有断言取得通过——新增用例全部落在**新文件**（`test_round3_defect_fixes.py`、`test_business_closure.py`）与**既有文件的追加用例**（`test_stage_c5_recognition.py` 的 2 条）上，既有断言零改动。当前最终门禁 `pytest edge/tests -q` = `298 passed / 0 failed / 0 skipped / 1 warning`（来源见 0.1 与 ⑤）。
>
> 本报告**当前数字**以主 Agent 与最终独立审查 Agent 各自实跑的最终门禁为准（`298 passed, 1 warning`；`integration 91 passed, 1 warning`）；`162 passed, 1 warning in 38.36s` 为 2026-11-14 第三轮历史留档、不静默改写（口径说明见 0.1）。若之后继续改动，以最后一次实跑为准。

---

## ⑥ 本阶段未覆盖项及原因

| 未覆盖的验收项 / 分支 | 原因 | 归属阶段 | 补测计划 |
| --- | --- | --- | --- |
| 验收项 3 中「真实上位机业务层弹窗 + 落库零副作用」的端到端闭环 | 上位机的识别核对流程必须**登录 → 建出入库单 → 开柜 → 关柜**才会发起 `recognize_req`；本阶段无 GUI 自动化设施，人工驱动成本与误操作风险过高，故未驱动到该步。已用两条替代路径覆盖同一判据：上位机自带 `test_edge.exe`（真实 `parseItems` 代码）对好/坏帧的权威判定；以及真实上位机进程对线上帧的真实解析日志 | 后续专项（上位机 GUI 自动化） | 具备 GUI 自动化后，补一条「上位机发起真实 `recognize_req` → 边缘机回帧 → 上位机 `recognizeFinished` 放行 / `recognizeFailed` 拒绝并零写库」的闭环用例 |
| 验收项 3 中「上位机在途请求存在时收到合法 `recognize_ack` → 走业务层 `compareOrderWithRecognition`」 | 同上：上位机没有在途识别请求时，`onFrameReceived` 在 `m_pending.contains(id)` 处直接丢弃，`parseItems` 与业务比对都不会被调用。真实进程的联调证据止于「编号被正确回带」 | 后续专项（上位机 GUI 自动化） | 同上 |
| 验收项 5 中「任一路摄像头非 ok 时上位机实际拒开柜」的**真实进程**验证 | 开柜闸门在 `EdgeService::requestOpen()` 内触发，只能由上位机界面发起开柜动作，本阶段未驱动到该步。协议形状与闸门结论已由 `check_periodic` 单测覆盖，并被上位机自带 `test_edge.exe::cameraGate_requestOpenBlockedWhenAbnormal` 独立验证通过 | 后续专项（上位机 GUI 自动化） | GUI 自动化后补一条「周期帧含 offline 路 → 上位机点开柜 → 弹『以下摄像头状态异常，禁止开柜』」用例 |
| 验收项 4/6 中「上位机 3 秒超时原帧重发同一 `request_id`」的**上位机侧**重发行为 | 上位机超时重发由 `EdgeService::onScanTimeout` 驱动，需要上位机侧存在在途请求（同上，受 GUI 限制）；边缘机侧的幂等（同一 `request_id` 只扫描一次、回相同结果）已由既有 `testSameRequestIdIsIdempotent` 与 `testDuplicateRequestsInFlightShareOneScan` 覆盖通过 | 后续专项（上位机 GUI 自动化） | GUI 自动化后补一条「上位机不回应 → 3 秒后原帧重发 → 边缘机回同一结果」的闭环用例 |
| 边缘机 `items[]` 覆盖「CSV 全部行、一行不漏」的实机验证 | 需要 `c5plus` 的 ROI 对照表装载与识别链路完全落地并有真实图片；本阶段无真实相机与模型权重产出 | c5plus 后续 | c5plus 落地后，在有相机与权重的机器上补一条「items 覆盖 CSV 全部行、`position` 与 CSV 一一对应」的实机用例 |
| 真实上位机进程与**真实边缘机程序**（`edge/main.py`）的端到端对接 | 真实 TCP 客户端 `edge/modules/tcp/tcp_socket.py` **已落地**（`TcpSocket` 实现 `ISocket`，`connect`/`recv`/`send`/`close` 与超时、断链语义收敛在该文件，`edge/modules/tcp/tcp_socket.py:30-131`），生产入口不再依赖骨架；**剩余上板项为 IO 板侧 `close_ack` 构造与真机对焦标定**（`close_ack` 目前只在协议常量、Fake 与测试用例中出现，无生产构造点，见 `test_open_ack_protocol_parity.py:13`）。本阶段联调用的是边缘机的**协议产出侧**（同一 `TcpComm` + `TcpControlLayer` + `RecognitionWorker` 组帧路径）与真实上位机对接 | 上板阶段（IO 板侧 `close_ack` 构造、真机对焦标定、真实进程联调） | 上板补齐 `close_ack` 构造与对焦标定后，把 `live_link_check.py` 换成拉起 `edge/main.py` 进程直连真实上位机 |
| 覆盖率数字 | 环境未安装 pytest-cov / coverage，无法给出覆盖率 | — | 需要量化时安装 pytest-cov 后补跑 |
| **本轮遗留 1**：上位机 **GUI 业务层闭环**（`recognize_req` 由上位机界面发起 → 业务层 `compareOrderWithRecognition` → 放行 / 拒绝 + 落库零副作用） | 第三轮把边缘机侧的业务闭环补齐并全部用例化（`test_business_closure.py` 11 条 + `test_round3_defect_fixes.py` 17 条），但**上位机侧仍需 GUI 自动化**才能驱动到「登录 → 建单 → 开柜 → 关柜」这一步；本阶段无 GUI 自动化设施 | 后续专项（上位机 GUI 自动化） | 具备 GUI 自动化后，补一条「上位机界面发起真实 `recognize_req` → 边缘机回帧 → 上位机放行 / 拒绝并零写库」的闭环用例 |
| **本轮遗留 2**：**真实相机对焦标定**（`focus_mode` / `focus_position` 的实测取值） | 开机定焦因无相机 / 无 opencv 只记 info（`app_init.py` 开机定焦段）；对焦参数没有真机可标 | 上板 | 上板接真实相机后，标定 `auto` / `fixed` 两模式与 `focus_position` 取值，并回填 `config.ini` |
| **本轮遗留 3**：**ROI 坐标上板重标** | `edge/config/roi_binding.csv` 的 4 行样例坐标按 640×480 全景铺满四象限（`(0,0)-(320,240)`、`(320,0)-(640,240)`、`(0,240)-(320,480)`、`(320,240)-(640,480)`）；换真相机后全景尺寸变化，越界会抛 `EdgeError(CAPTURE, "ROI 超出拼接图范围: ...")` | 上板 | 上板后按实际全景尺寸重标四角点 |
| **本轮遗留 4**：**onnxruntime 后端与 ultralytics 的等价性现场标定** | 第三轮已补 NMS（抑制前 62 条 → 抑制后落到与 ultralytics 同量级，用例断言 `len(ultraItems) == 6` 且 `0 < len(onnxItems) <= 2 * len(ultraItems)`），并把 onnx 分支显式标注为「需现场标定」；但**两条后端的逐框一致性尚未标定**（不同实现的置信度口径、类别映射、预处理不同），故默认后端固定 `ultralytics` | 上板 / 现场标定 | 现场用同一批图对比两条后端的逐框结果，标定后再考虑放开 `inference_backend` 配置 |
| **本轮遗留 5**：`low_light` / `dirty` 两个相机状态**当前不产出** | 这两个状态需要图像分析（照度、镜头脏污），当时实现产出 `ok` / `offline` / `comm_error` 三种；上位机开柜闸门按非 `ok` 判。**2026-11-20 变更**：状态取值收紧为 `ok` / `offline` 两态，`comm_error` 归并到 `offline`，`low_light` / `dirty` 不再设协议取值 | 已收口（2026-11-20） | 若将来上板图像分析能力，须走契约 diff + 用户批准后再增加状态取值 |
| **本轮遗留 6**：**浏览器内布局自检**未在本 agent 侧实跑 | 图的节点 / 关系计数已在磁盘核对（类图 53 / 18；图 2 30 / 35；图 3 当时 17 / 17，2026-11-20 两态收口删去 3 个状态值节点后为 14 / 13），但页面「布局自检」（同层重叠检测、文字超宽检测）需 playwright + msedge 通道实跑；本 agent 无命令执行工具 / 无浏览器环境 | 后续具备环境时 | 执行 ④.2 的第 7 组命令，打印 `[SELF-CHECK]` 一行确认 |
| **最终审查 12 条·未收敛 1**：`@file` 头两种位置并存 | 全库 `## @file` 头有的在模块 docstring 之后、有的在 import 块之后；本轮只按开工清单补了 5 个非 L1 文件（放在 docstring 之后、`from __future__` 之前），其余 13 个属 L1（`interfaces/**`、`exceptions.py`、`tests/contract/**`）**禁止改**。统一全库位置要动 L1 契约层 | 后续注释治理（统一口径需用户批准；L1 部分须 diff + 批准） | 用户批准统一口径后另立白名单，逐文件对齐位置 |
| **最终审查 12 条·未收敛 2**：生产运行时文案含 3 处黑话 | E 组已把注释黑话 72→9、历史痕迹 1→0；剩余 3 处落在**运行时输出文案**里，替换它们属改业务 `.py` 逻辑，本轮铁律禁止改任何业务 `.py` 逻辑 | 后续文案治理（需用户批准改运行时文案） | 用户批准后逐条替换运行时文案并复跑门禁 |
| **最终审查 12 条·未收敛 3**：验收项编号注释覆盖 110/298 | 按 `test-visibility.mdc §3.1`，每个测试函数上方需一行「对应验收项」注释；全库读盘命中 **110** 处，未覆盖 298 个用例中的其余部分；批量补注释要动既有测试，属 `test-writer` 职责 | 后续测试注释治理（test-writer，需开工清单） | 立白名单后按验收项编号逐文件补齐 |
| **最终审查 12 条·未收敛 4**：`close_ack` 无生产构造点 | `close_ack` 是关柜信号、由 IO 板一侧产生，边缘机不回（`test_open_ack_protocol_parity.py:13`）；当前只在协议常量、Fake、测试用例里出现（`tcp_comm.py:20` 为帧类型白名单），没有生产构造点 | 上板 / IO 板侧协议实现 | 与 IO 板联调时确定归属并补构造点 |
| **最终审查 12 条·未收敛 5**：L1 目录 2 个新增接口文件待用户追认 | `edge/interfaces/i_camera_focus.py`、`edge/interfaces/i_frame_sink.py` 是 c4plus 新增接口，属 L1 契约层，本轮禁止改；契约增量须用户 diff + 批准 | 用户追认（L1 契约变更流程） | 输出 diff 与影响面，用户批准后在 decisions / handoff 登记 |
| **最终审查 12 条·未收敛 6**：上位机 GUI 业务闭环 | 需上位机 GUI 自动化驱动「登录 → 建单 → 开柜 → 关柜」，本阶段无该设施（详见本表「本轮遗留 1」） | 后续专项（上位机 GUI 自动化） | 具备 GUI 自动化后补端到端闭环用例 |
| **最终审查 12 条·未收敛 7**：真机对焦标定 | `focus_mode` / `focus_position` 无真机可标（详见「本轮遗留 2」） | 上板 | 上板接真实相机后标定并回填 `config.ini` |
| **最终审查 12 条·未收敛 8**：ROI 四角点上板重标 | `roi_binding.csv` 4 行样例坐标按 640×480 铺满四象限，换真相机后需重标（详见「本轮遗留 3」） | 上板 | 上板后按实际全景尺寸重标四角点 |
| **最终审查 12 条·未收敛 9**：onnx 后端等价性标定 | 已补 NMS 并标注「需现场标定」，两条后端逐框一致性未标定（详见「本轮遗留 4」） | 上板 / 现场标定 | 现场同批图逐框对比后再考虑放开 `inference_backend` |
| **最终审查 12 条·未收敛 10**：`low_light` / `dirty` 状态未产出 | 需图像分析能力；**2026-11-20 变更**：已把状态取值收紧为 `ok` / `offline` 两态并从协议移除这两个值（详见「本轮遗留 5」），本项随之收口 | 已收口（2026-11-20） | 将来增加状态须走契约 diff + 用户批准 |
| **附：环境对齐遗留项（④ 已登记，非 12 条内）** | 本机 `pytest 6.2.4` 与 `pyproject.toml:12` 的 `pytest>=7.4,<9` 有版本偏差，本轮已在 ④ 如实登记、未升级也未改 L1 | 用户批准后升级 pytest 或改 L1 声明 | 见 ④ 环境段「环境对齐遗留项」 |

**12 条待收敛项的收敛对照（本轮）**：本轮 4 项交付只收敛其中低风险、不涉 L1、不改业务逻辑的部分——陈旧数字与「未复跑 / 零命中 / 尚不存在」等不实陈述（交付 1）、5 个**非 L1** 文件头（交付 2，L1 的 13 个不动）、1 处空洞断言（交付 3）、检视报告落盘件（交付 4）；上表「未收敛 1~10」及 `close_ack` / L1 接口 / GUI / 上板标定等逐条列明归属阶段，**本轮一律不动**。收敛明细与残留风险另见同目录 `code-review-report.md`。

### 结论（证据齐备性判定）

**证据齐备。** 依据：

1. `dplus/spec-digest.md` §7 第 3、4、5、6 条验收项**全部**有对应用例且有真实命令输出支撑（新增 13 条一致性用例 + 既有 5 条联调用例，实测输出见 ③ 与 ④）。
2. 上位机侧的判据来自**两路独立证据**：上位机自带编译产物 `test_edge.exe`（真实 `EdgeService::parseItems` 代码，`Totals: 36 passed, 0 failed`）与本阶段逐条复刻的 `host_protocol_checker.py`，二者在 13 条非法帧的错误文案上**逐字一致**。
3. 真实上位机**进程**联调已跑通并取到 6/6 取证点（上位机监听 9000、边缘机接入、周期帧被解析、`request_id` 必须是 snake_case、未知 type 按 3.6-② 丢弃）。
4. 全量套件当前最终门禁 **298 passed / 0 failed / 0 skipped / 1 warning**（`pytest edge/tests -q`）、**91 passed / 0 failed / 0 skipped / 1 warning**（`pytest edge/tests/integration -q`），由主 Agent 与最终独立审查 Agent 各自实跑（输出见 0.1）；第三轮历史口径 132 → 162、增量 30 = 17 + 11 + 2 作为 L4 留档保留（见 ⑤）。上轮撰写期间观察到的 5 条在途失败（均为 c5plus 并发落地导致）已由 c5plus 自行同步，本阶段未做任何「洗绿」处理。
5. **第三轮修复的 9 项**逐项有对应用例（补充编号 D-1 ~ D-9，见 ①）并全部随全量实跑通过（明细见 ③.6）；其中 4 项在**真实代码路径**上取证（对照表缺失启动即失败、`worker_id` 越界启动即失败、从未打开的相机判 `offline`、丢帧计数与抽样日志），不是只测桩。
6. 两张图的节点 / 关系计数在磁盘核对一致（类图 53 节点 / 18 条跨层关系；图 2 30 节点 / 35 连线；图 3 17 节点 / 17 连线），自检脚本在库可复跑。
7. **如实标注**：当前 298 / 91 / `All checks passed!` / `95 source files` 四项均由主 Agent 与最终独立审查 Agent 各自实跑，输出见 0.1；`162 / 38.36 s` 为 2026-11-14 第三轮历史留档、不改写。磁盘另行独立核对「10 处 `parametrize`、无 `skip` / `xfail` 掩盖、`tcp_socket.py` 已落地、`AssemblyParts` 43 字段」等可验证侧面，均有文件:行号支撑（见 0.1）；0.1 已标明每项数字的来源与复跑状态，未写任何未经证实的推测结论。

> 本结论只陈述「测试证据是否齐备」。**最终验收结论由用户本人签字**，本 agent 不代签、不改阶段状态、不产出 handoff。
