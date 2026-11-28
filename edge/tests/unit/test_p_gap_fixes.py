"""5 个 P 级缺口修复的验收单测：推理超时/磁盘占用/故障归类/坏帧计数/默认提示。"""
## @file edge/tests/unit/test_p_gap_fixes.py
## @brief 5 个 P 级缺口修复的验收单测
## @author 袁燕
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from edge.app_init import (
    diskUsageRatio,
    directInference,
    zeroUsage,
)
from edge.control.edge_control import CachedEvent, EdgeControl, FailureFrameBuilder, ModuleWiring
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.config_manager import IniConfigManager
from edge.interfaces.i_recognition_engine import DetectionItem
from edge.tests.fakes.fake_logger import FakeLogger

## @brief 超时用例的等待秒数
SLOW_TASK_SEC: float = 0.3
## @brief 超时用例的上限秒数，须小于等待秒数
SHORT_TIMEOUT_SEC: float = 0.05


## @brief 固定失败应答构造器
#  @param workerId 线程编号
#  @param exception 业务异常
#  @return 失败应答帧
def fixedFailure(workerId: int, exception: Exception) -> CachedEvent:
    return {"type": "error", "workerId": workerId, "message": str(exception)}


## @brief 空发送器，只接收不计数
#  @param frame 待发帧
#  @return 无
def silentSender(frame: CachedEvent) -> None:
    return None


## @brief 构造控制层用于验收断言
#  @param logger 注入日志器
#  @param handlers 注入信号处理器
#  @return 控制层实例
def buildControl(logger: FakeLogger,
                 handlers: dict[str, Callable[[dict[str, object]], None]] | None = None,
                 ) -> EdgeControl:
    return EdgeControl(
        logger, handlers or {}, ModuleWiring(), silentSender, fixedFailure,
    )


## @brief A1-a：慢推理在超时上限内抛 TimeoutError，不拖到任务结束
def test_a1_inference_timeout_raises_on_slow_task() -> None:
    import time

    def slowTask() -> list[DetectionItem]:
        time.sleep(SLOW_TASK_SEC)
        return []

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        directInference(slowTask, SHORT_TIMEOUT_SEC)
    ## 超时须远早于慢任务耗时，紧阈值避免负载下"超时后才返回"也通过
    assert time.monotonic() - started < SHORT_TIMEOUT_SEC * 3


## @brief A1-b：快推理在超时上限内正常返回结果
def test_a1_inference_returns_fast_task() -> None:
    result = directInference(lambda: [], SHORT_TIMEOUT_SEC)
    assert result == []


## @brief A1-d：在途推理达上限时排队等待，不拒绝新请求
def test_a1_inference_gate_waits_when_full() -> None:
    import time

    from edge.app_init import INFERENCE_POOL_MAX_WORKERS, inferencePool

    ## 排空闸门：模块级池跨用例共享，前序用例的后台推理可能仍占用名额；
    ## 反复非阻塞取满再全部归还，闸门恢复满额后本用例才有确定的起步状态
    _, gate = inferencePool()
    for _ in range(60):
        acquired = 0
        while gate.acquire(blocking=False):
            acquired += 1
        for _ in range(acquired):
            gate.release()
        if acquired == INFERENCE_POOL_MAX_WORKERS:
            break
        time.sleep(0.05)

    ## @brief 慢于超时的推理：调用方超时返回后后台仍占闸门名额
    #  @return 检测结果列表
    def slowTask() -> list[DetectionItem]:
        time.sleep(0.5)
        return []

    ## 用短超时让调用方快速返回，后台任务继续占用闸门
    for _ in range(INFERENCE_POOL_MAX_WORKERS):
        with pytest.raises(TimeoutError):
            directInference(slowTask, 0.02)

    ## 闸门已满时下一次提交排队等待，直到超时而非立即拒绝
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        directInference(lambda: [], 0.02)
    elapsed = time.monotonic() - started
    assert elapsed >= 0.01, f"应排队等待而非立即拒绝，实际 {elapsed:.3f}s"

    ## 等待后台慢任务结束归还闸门，避免干扰后续用例
    time.sleep(0.6)


## @brief A1-c：超时上限非正数时直接执行，不建线程池也不限时
def test_a1_nonpositive_timeout_runs_directly() -> None:
    called = []

    def task() -> list[DetectionItem]:
        called.append(1)
        return []

    assert directInference(task, 0) == []
    assert called == [1]


## @brief A2-a：磁盘占用提供器按 used/total 计算，且缓存期内不再重复系统调用
def test_a2_disk_usage_ratio_computes_and_caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    calls = []

    ## @brief 固定磁盘用量，返回 used=1/total=4
    #  @param path 查询路径
    #  @return 模拟的磁盘用量
    def fakeDiskUsage(path: str) -> SimpleNamespace:
        calls.append(path)
        return SimpleNamespace(total=4, used=1, free=3)

    monkeypatch.setattr("edge.app_init.shutil.disk_usage", fakeDiskUsage)
    readUsage = diskUsageRatio([str(tmp_path)], cacheTtlSec=60.0)
    assert readUsage() == 0.25
    assert readUsage() == 0.25
    assert len(calls) == 1, "缓存有效期内只应系统调用一次"


## @brief A2-b：不可读目录容错，返回 0.0 不抛异常
def test_a2_disk_usage_ratio_unreadable_dir() -> None:
    ratio = diskUsageRatio([str(Path("/nonexistent/path/for/edge/test"))])()
    assert ratio == 0.0


## @brief A2-c：默认零占用提供器仍可用于测试注入
def test_a2_zero_usage_still_available() -> None:
    assert zeroUsage() == 0.0


## @brief A5：处理器内置异常归入 CONFIG，日志带错误码且降级帧照常产出
def test_a5_unexpected_exception_classified_as_config() -> None:
    logger = FakeLogger()

    def boom(signal: dict[str, object]) -> None:
        raise ValueError("bad handler state")

    control = buildControl(logger, {"probe": boom})
    assert control.routeSignal({"type": "probe", "requestId": "req-a5"}) is True
    errors = [rec for rec in logger.errorRecords if "未预期异常" in rec[1]]
    assert len(errors) == 1, "未预期异常必须记一条 error 日志"
    assert "CONFIG" in errors[0][1], "日志文本须体现归类错误码 CONFIG"
    assert isinstance(errors[0][2], EdgeError)
    assert errors[0][2].code == ErrorCode.CONFIG
    ## 保留原始异常作为 cause，便于排障
    assert isinstance(errors[0][2].__cause__, ValueError)
    ## 归类错误的同时仍产出降级应答，不中断上位机指令接收
    assert control.getOutboxCount() >= 1


## @brief A6-a：FRAME_PARSE 坏帧计数递增，观测口可读
def test_a6_frame_parse_error_increments_counter() -> None:
    control = buildControl(FakeLogger())
    before = control.getFrameErrorCount()
    control.onFrameError(EdgeError(ErrorCode.FRAME_PARSE, "bad json"))
    control.onFrameError(EdgeError(ErrorCode.FRAME_PARSE, "bad type"))
    assert control.getFrameErrorCount() == before + 2


## @brief A6-b：非 FRAME_PARSE 错误经同一回调不计数
def test_a6_non_parse_error_not_counted() -> None:
    control = buildControl(FakeLogger())
    before = control.getFrameErrorCount()
    control.onFrameError(EdgeError(ErrorCode.LINK_DOWN, "link closed"))
    control.onFrameError(ValueError("plain error"))
    assert control.getFrameErrorCount() == before


## @brief A7：延迟注入日志器后，默认值提示被补记
def test_a7_set_logger_replays_default_hints(tmp_path: Path) -> None:
    configPath = tmp_path / "config.ini"
    configPath.write_text("[comm]\n", encoding="utf-8")
    config = IniConfigManager(str(configPath))
    logger = FakeLogger()

    assert config.get("comm", "port", default=9000) == 9000
    assert logger.infoRecords == [], "未注入日志器前不应输出"

    config.setLogger(logger)
    assert any("使用默认值 9000" in rec[1] for rec in logger.infoRecords)


## @brief A7-b：注入日志器后新发生的默认值提示实时记录
def test_a7_set_logger_logs_live_defaults(tmp_path: Path) -> None:
    configPath = tmp_path / "config.ini"
    configPath.write_text("[comm]\n", encoding="utf-8")
    logger = FakeLogger()
    config = IniConfigManager(str(configPath))
    config.setLogger(logger)

    assert config.get("comm", "port", default=9000) == 9000
    assert any("使用默认值 9000" in rec[1] for rec in logger.infoRecords)


## @brief 自查1：深度嵌套 JSON 转 FRAME_PARSE，不抛裸 RecursionError
def test_deep_json_becomes_frame_parse() -> None:
    from edge.modules.tcp.tcp_comm import TcpComm
    from edge.tests.fakes.fake_socket import FakeSocket

    comm = TcpComm(FakeSocket(), 1024 * 1024)
    deep = ("[" * 2000 + "]" * 2000).encode("utf-8")
    with pytest.raises(EdgeError) as exc:
        comm.decodeAndParse(deep)
    assert exc.value.code == ErrorCode.FRAME_PARSE


## @brief 自查2：超长 request_id 按坏帧拒绝
def test_overlong_request_id_rejected() -> None:
    import json

    from edge.modules.tcp.tcp_comm import MAX_REQUEST_ID_CHARS, TcpComm
    from edge.tests.fakes.fake_socket import FakeSocket

    comm = TcpComm(FakeSocket(), 1024 * 1024)
    raw = json.dumps({"type": "recognize_req", "request_id": "x" * (MAX_REQUEST_ID_CHARS + 1)})
    with pytest.raises(EdgeError) as exc:
        comm.decodeAndParse(raw.encode("utf-8"))
    assert exc.value.code == ErrorCode.FRAME_PARSE


## @brief 自查3：NaN 置信度按 0.0 处理，不产出非法 JSON 数值
def test_nan_confidence_is_zero() -> None:
    from edge.modules.recognition.recognition_utils import buildAckItem

    item = buildAckItem("A-01-02", "tool-1", float("nan"), "none")
    assert item["confidence"] == 0.0


## @brief 自查4：空 request_id 的信号被丢弃，不触发业务处理
def test_empty_request_id_signal_dropped() -> None:
    logger = FakeLogger()
    seen = []

    def handler(signal: dict[str, object]) -> None:
        seen.append(signal)

    control = buildControl(logger, {"probe": handler})
    assert control.routeSignal({"type": "probe"}) is True
    assert seen == []
    assert any("缺少请求标识" in rec[1] for rec in logger.errorRecords)


## @brief 自查5：ROI 负坐标或超上限坐标按 CONFIG 拒绝
def test_roi_out_of_range_rejected(tmp_path: Path) -> None:
    from edge.infra.roi_binding_loader import RoiBindingLoader

    header = (
        "roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,"
        "confidence,rect_x1,rect_y1,rect_x2,rect_y2\n"
    )
    badRow = "roi-1,1,D1,A-01-02,t1,,m1,0.85,0,0,99999,99999\n"
    csvPath = tmp_path / "bad.csv"
    csvPath.write_text(header + badRow, encoding="utf-8")
    with pytest.raises(EdgeError) as exc:
        RoiBindingLoader(FakeLogger()).load(str(csvPath))
    assert exc.value.code == ErrorCode.CONFIG


## @brief 自查6：停机后的迟到连接回调不得把链路翻回 UP
def test_on_connected_after_stop_keeps_down() -> None:
    from edge.modules.tcp.tcp_comm import LINK_DOWN
    from edge.modules.tcp.tcp_control_layer import TcpControlLayer
    from edge.tests.fakes.fake_socket import FakeSocket

    layer = TcpControlLayer(
        FakeSocket(), FakeLogger(), [1.0], 1024, 3.0,
        lambda: {"type": "periodic"},
    )
    layer.stop()
    ## stop 之后再触发连接成功回调，模拟 stop 与重连线程并发的迟到分支
    layer._onConnected()
    assert layer.getState() == LINK_DOWN
    assert layer._heart is None
    assert layer._decode is None


## @brief 自查7：stopSystem 单步异常仍继续其余步骤并清空运行态
def test_stop_system_survives_step_error() -> None:
    from functools import partial

    from edge.control.edge_control import STOP_ORDER, STOP_USB

    logger = FakeLogger()
    wiring = ModuleWiring()
    control = EdgeControl(logger, {}, wiring, silentSender, fixedFailure)
    seen = []

    ## @brief 在 USB 步抛异常，其余步骤仅记录
    #  @return 无
    def boom() -> None:
        raise RuntimeError("stop failed")

    for step in STOP_ORDER:
        wiring.stopActions[step] = boom if step == STOP_USB else partial(seen.append, step)
    control.onRecognitionResult(1, {"type": "ack"}, "req-stop")
    assert control.getAggregationCount() >= 0

    with pytest.raises(RuntimeError):
        control.stopSystem()
    assert seen == list(STOP_ORDER[1:]), "单步异常后其余步骤仍须执行"
    assert control.getStopTrace() == list(STOP_ORDER), "停机轨迹须完整"
    assert control.getOutboxCount() == 0, "运行态须在 finally 中清空"


## @brief 自查8：managedRun 在业务异常时仍停机并释放进程锁
def test_managed_run_releases_on_error(tmp_path: Path) -> None:
    from edge.main import managedRun

    class FakeLock:
        def __init__(self) -> None:
            self.released = False

        def release(self) -> None:
            self.released = True

    lock = FakeLock()
    events = []
    with pytest.raises(ValueError):
        with managedRun(lock, lambda: events.append("stop")):
            raise ValueError("boom")
    assert events == ["stop"]
    assert lock.released is True


## @brief 自查9：confidenceOf 把 nan 检测判 0，不误判为正常命中
def test_confidence_of_nan_is_zero() -> None:
    from edge.modules.recognition.recognition_utils import confidenceOf

    item = {"className": "wrench", "confidence": float("nan"), "box": [0, 0, 10, 10]}
    assert confidenceOf(item) == 0.0


## @brief 自查10：ROI 负坐标按 CONFIG 拒绝
def test_roi_negative_coordinate_rejected(tmp_path: Path) -> None:
    from edge.infra.roi_binding_loader import RoiBindingLoader

    header = (
        "roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,"
        "confidence,rect_x1,rect_y1,rect_x2,rect_y2\n"
    )
    badRow = "roi-1,1,D1,A-01-02,t1,,m1,0.85,-1,0,320,240\n"
    csvPath = tmp_path / "neg.csv"
    csvPath.write_text(header + badRow, encoding="utf-8")
    with pytest.raises(EdgeError) as exc:
        RoiBindingLoader(FakeLogger()).load(str(csvPath))
    assert exc.value.code == ErrorCode.CONFIG


## @brief 自查11：未知帧型超长 type 日志被截断，不把整串写进日志
def test_unknown_type_log_truncated() -> None:
    from edge.control.edge_control import MAX_LOG_TEXT_CHARS

    logger = FakeLogger()
    control = buildControl(logger)
    longType = "z" * 500
    assert control.routeSignal({"type": longType}) is False
    errors = [rec for rec in logger.errorRecords if "未注册" in rec[1]]
    assert len(errors) == 1
    assert longType not in errors[0][1]
    assert "z" * MAX_LOG_TEXT_CHARS in errors[0][1]


## @brief 裁决1：组合识别取最低置信度，单项高分不得带过整组合
def test_match_marker_uses_min_confidence() -> None:
    from edge.modules.recognition.recognition_utils import matchMarker

    comboMap: dict[frozenset[str], str] = {
        frozenset({"hammer", "red_label"}): "mk_8822",
    }
    detected, confidence = matchMarker(
        [
            {"className": "hammer", "confidence": 0.95},
            {"className": "red_label", "confidence": 0.51},
            {"className": "background_junk", "confidence": 0.70},
        ],
        "mk_8822", comboMap,
    )
    assert detected is True
    ## 取组合内最低 0.51；杂物类不参与，不拉低也不抬高
    assert confidence == 0.51


## @brief 裁决1-b：组合各项都高置信时仍判正常，min 不误伤
def test_match_marker_min_keeps_high_confidence() -> None:
    from edge.modules.recognition.recognition_utils import (
        buildRowItem, matchMarker,
    )
    from edge.infra.roi_binding_loader import RoiBindingRow

    comboMap: dict[frozenset[str], str] = {
        frozenset({"hammer", "red_label"}): "mk_8822",
    }
    detected, confidence = matchMarker(
        [
            {"className": "hammer", "confidence": 0.95},
            {"className": "red_label", "confidence": 0.92},
        ],
        "mk_8822", comboMap,
    )
    row = RoiBindingRow(
        roiId="r1", workerId=1, drawerId="A", position="A-01-02",
        toolId="T1", requiredType="hammer", markerId="mk_8822", confidence=0.85,
        rectX1=0, rectY1=0, rectX2=100, rectY2=100,
    )
    assert detected is True
    assert confidence == 0.92
    assert buildRowItem(row, detected, confidence)["alert_type"] == "none"


## @brief 裁决3：装配字段默认宽松、生产装配显式开启缺框拒识
def test_require_box_defaults() -> None:
    from dataclasses import fields

    from edge.app_init import AssemblyParts, defaultParts

    field = next(f for f in fields(AssemblyParts) if f.name == "requireBox")
    assert field.default is False, "测试构造默认兼容旧格式"
    assert defaultParts().requireBox is True, "生产装配显式开启缺框拒识"


## @brief 防护1：货位坐标超出全景时判错配，合法局部ROI不误报
def test_canvas_roi_mismatch() -> None:
    from edge.modules.recognition.recognition_utils import canvasRoiMismatch
    from edge.infra.roi_binding_loader import RoiBindingRow

    row = RoiBindingRow(
        roiId="r1", workerId=1, drawerId="A", position="A-01-01",
        toolId="T1", requiredType="t", markerId="mk", confidence=0.85,
        rectX1=0, rectY1=0, rectX2=320, rectY2=240,
    )
    assert canvasRoiMismatch((640, 480), [row]) == "", "合法坐标不应告警"
    assert "超出全景" in canvasRoiMismatch((300, 240), [row]), "坐标超界须告警"
    assert canvasRoiMismatch(None, [row]) == "", "无法解析全景时跳过"
    ## 局部小ROI、只标柜子一部分是合法场景，不因画布大而误报
    small = RoiBindingRow(
        roiId="r2", workerId=1, drawerId="A", position="A-01-02",
        toolId="T2", requiredType="t", markerId="mk", confidence=0.85,
        rectX1=0, rectY1=0, rectX2=200, rectY2=200,
    )
    assert canvasRoiMismatch((1280, 720), [small]) == ""


## @brief 防护2：整帧全未知记 error 并累计，正常/空柜不误报
def test_all_unknown_warning() -> None:
    logger = FakeLogger()
    control = buildControl(logger)
    unknownItems = [
        {"position": "A-01-01", "tool_id": "", "confidence": 0.0, "alert_type": "unknown"},
        {"position": "A-01-02", "tool_id": "", "confidence": 0.0, "alert_type": "unknown"},
    ]
    frame = control.buildAggregatedFrame({}, "req-all-unknown", unknownItems)
    assert control.getAllUnknownCount() == 1
    assert any("全为未识别" in rec[1] for rec in logger.errorRecords)
    assert frame is not None

    ## 真实空柜（tool_id 空但告警 none）不告警
    control.buildAggregatedFrame({}, "req-empty-cabinet", [
        {"position": "A-01-01", "tool_id": "", "confidence": 0.0, "alert_type": "none"},
    ])
    assert control.getAllUnknownCount() == 1, "空柜不应计入全未知告警"
