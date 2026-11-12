"""d 控制、装配与端到端单元测试：事件分发 / 缓存补发 / 停机串行 / 进程锁。"""
from __future__ import annotations

import ast
from collections.abc import Callable
from functools import partial
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, cast

from edge.app_init import AssemblyParts, buildSystem, defaultParts
from edge.control.edge_control import (
    STOP_LOG,
    STOP_ORDER,
    STOP_RECOGNITION,
    STOP_TCP,
    STOP_USB,
    AsyncHandler,
    EdgeControl,
    FailureFrameBuilder,
    ModuleWiring,
)
from edge.control.event_cache import CachedEvent, EventCache, FrameSender
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import FrameImage, ICameraDevice
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.interfaces.i_sinks import DecodedSignal, ICaptureSink, IRecognitionSink, SignalSink
from edge.modules.recognition.recognition_utils import (
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
)
from edge.modules.tcp.tcp_control_layer import TcpControlLayer
from edge.platform.file_lock import DEFAULT_LOCK_FILE_NAME
from edge.tests.fakes.fake_camera_device import FakeCameraDevice
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_platform_adapter import FakePlatformAdapter
from edge.tests.fakes.fake_recognition_engine import FakeRecognitionEngine
from edge.tests.fakes.fake_sinks import FakeRecognitionSink
from edge.tests.fakes.fake_socket import FakeSocket

## @brief 注入的模型路径
TEST_MODEL_PATH: str = "model.bin"
## @brief 注入的推理超时秒数
TEST_TIMEOUT_SEC: float = 3.0
## @brief 注入的滚动删旧阈值
TEST_ROLL_THRESHOLD: float = 0.3
## @brief 注入的单帧字节上限
TEST_MAX_FRAME_SIZE: int = 1024
## @brief 注入的心跳周期秒
TEST_HEART_SEC: float = 3.0


## @brief 固定左右图读取器
#  @param saveDir 采集目录
#  @param workerId 线程编号
#  @return 左右图像字节对
def fixedFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
    return (b"LEFT", b"RIGHT")


## @brief 直接执行推理，不施加真实等待
#  @param task 推理闭包
#  @param timeoutSec 注入的超时秒数
#  @return 检测结果列表
def directRunner(task: Callable[[], list[DetectionItem]],
                 timeoutSec: float) -> list[DetectionItem]:
    return task()


## @brief 固定磁盘占用比例
#  @return 0.0
def quietDisk() -> float:
    return 0.0


## @brief 固定文件名时间戳
#  @return 固定标签
def fixedStamp() -> str:
    return "stamp"


## @brief 固定心跳帧
#  @return 心跳帧字典
def fixedHeartbeat() -> dict[str, object]:
    return {"type": "heartbeat", "uptime_sec": 0}


## @brief 固定失败应答构造器
#  @param workerId 线程编号
#  @param exception 业务异常
#  @return 失败应答帧
def fixedFailure(workerId: int, exception: Exception) -> CachedEvent:
    return {"type": "error", "workerId": workerId, "message": str(exception)}


## @brief 空动作
#  @return 无
def noAction() -> None:
    return None


## @brief 空链路启动器
#  @param tcp 通信门面
#  @return 无
def noLinkStart(tcp: TcpControlLayer) -> None:
    return None


## @brief 记录帧的发送器
class RecordingSender:
    ## @brief 构造发送器
    def __init__(self) -> None:
        ## @brief 已发送帧
        self.frames: list[CachedEvent] = []

    ## @brief 记录并返回发送成功
    #  @param frame 待发送帧
    #  @return True
    def send(self, frame: CachedEvent) -> bool:
        self.frames.append(frame)
        return True


## @brief 记录调用轨迹的处理器集合
class CallTrace:
    ## @brief 构造轨迹
    def __init__(self) -> None:
        ## @brief 调用记录
        self.events: list[str] = []

    ## @brief 追加一条记录
    #  @param label 记录标签
    #  @return 无
    def record(self, label: str) -> None:
        self.events.append(label)


## @brief 构造完备注入的装配参数（全 Fake，不启真实线程/网络/设备）
#  @param root 临时目录
#  @param sender 帧发送器
#  @param logger 日志 Fake
#  @param handlers 注入的分发表
#  @param enabled 补发开关
#  @param linkStarter 链路启动器
#  @param logStarter 日志启动器
#  @param logStopper 日志停机器
#  @return 装配参数
def makeParts(root: Path, sender: RecordingSender, logger: FakeLogger,
              handlers: dict[str, AsyncHandler] | None = None,
              enabled: bool = True,
              linkStarter: Callable[[TcpControlLayer], None] | None = None,
              logStarter: Callable[[], None] | None = None,
              logStopper: Callable[[], None] | None = None) -> AssemblyParts:
    dirs = [root / f"worker{index}" for index in range(1, 5)]
    for saveDir in dirs:
        saveDir.mkdir(exist_ok=True)
    pairs: list[tuple[ICameraDevice, ICameraDevice]] = [
        (FakeCameraDevice(b"L"), FakeCameraDevice(b"R")) for _ in range(4)
    ]
    engine: IRecognitionEngine = FakeRecognitionEngine(
        [{"roiId": "r1", "className": "tool"}],
    )
    roiConfig: RoiConfig = {"r1": 1}
    classItemMap: ClassItemMap = {"tool": "wrench"}
    roiBindMap: RoiBindMap = {"r1": "wrench"}
    frameLoader: FrameLoader = fixedFrames
    timeoutRunner: TimeoutRunner = directRunner
    failureBuilder: FailureFrameBuilder = fixedFailure
    frameSender: FrameSender = sender.send
    return AssemblyParts(
        logger=logger,
        socket=FakeSocket(),
        cameraPairs=pairs,
        captureDirs=[str(saveDir) for saveDir in dirs],
        recognitionDirs=[str(saveDir) for saveDir in dirs],
        engine=engine,
        modelPath=TEST_MODEL_PATH,
        frameLoader=frameLoader,
        timeoutRunner=timeoutRunner,
        inferTimeoutSec=TEST_TIMEOUT_SEC,
        roiConfig=roiConfig,
        classItemMap=classItemMap,
        roiBindMap=roiBindMap,
        rollThreshold=TEST_ROLL_THRESHOLD,
        usageRatio=quietDisk,
        clock=fixedStamp,
        backoffSeq=[1.0, 2.0, 4.0],
        maxFrameSize=TEST_MAX_FRAME_SIZE,
        heartIntervalSec=TEST_HEART_SEC,
        buildHeartbeat=fixedHeartbeat,
        eventCacheEnabled=enabled,
        asyncHandlers=handlers if handlers is not None else {},
        failureFrameBuilder=failureBuilder,
        frameSender=frameSender,
        linkStarter=linkStarter if linkStarter is not None else noLinkStart,
        logStarter=logStarter if logStarter is not None else noAction,
        logStopper=logStopper if logStopper is not None else noAction,
    )


## @brief 构造独立控制层（不入 buildSystem），用于分发与停机单测
#  @param logger 日志 Fake
#  @param sender 帧发送器
#  @param handlers 注入的分发表
#  @param enabled 补发开关
#  @return 控制层与接线二元组
def makeControl(logger: FakeLogger, sender: RecordingSender,
                handlers: dict[str, AsyncHandler] | None = None,
                enabled: bool = True) -> tuple[EdgeControl, ModuleWiring]:
    wiring = ModuleWiring()
    cache = EventCache(enabled, logger)
    control = EdgeControl(
        logger, handlers if handlers is not None else {}, wiring, cache,
        sender.send, fixedFailure,
    )
    return control, wiring


## @brief 对应验收项 d-1：routeSignal 按注入键分发，门面不写死业务字符串
def test_d_1_route_signal_dispatches_injected_keys(tmp_path: Path) -> None:
    seen: list[DecodedSignal] = []
    handlers: dict[str, AsyncHandler] = {
        "alpha_probe": lambda signal: seen.append(signal),
        "beta_probe": lambda signal: seen.append(signal),
    }
    control, _ = makeControl(FakeLogger(), RecordingSender(), handlers)
    signal: DecodedSignal = {"type": "alpha_probe", "requestId": "req-1"}

    assert control.routeSignal(signal) is True
    assert seen == [signal]
    assert control.getRequestId() == "req-1"
    assert control.getHandlerKeys() == ["alpha_probe", "beta_probe"]
    assert control.routeSignal({"type": "beta_probe", "requestId": "req-2"}) is True
    assert len(seen) == 2
    assert control.getRequestId() == "req-2"


## @brief 对应验收项 d-1：未注册键不分发并记 error；Sink 只做轻量转发
def test_d_1_unknown_key_rejected_and_sink_forwards(tmp_path: Path) -> None:
    seen: list[DecodedSignal] = []
    logger = FakeLogger()
    control, _ = makeControl(logger, RecordingSender(), {
        "alpha_probe": lambda signal: seen.append(signal),
    })

    assert control.routeSignal({"type": "not_injected"}) is False
    assert seen == []
    assert any("未注册" in record[1] for record in logger.errorRecords)
    control.onSignalDecoded({"type": "alpha_probe", "requestId": "req-3"})
    assert len(seen) == 1
    assert control.getRequestId() == "req-3"


## @brief 对应验收项 d-1：三个 L1 Sink 契约与 camelCase 命名（snake_case 不作 API）
def test_d_1_l1_sink_contracts_and_camel_case(tmp_path: Path) -> None:
    control, _ = makeControl(FakeLogger(), RecordingSender())
    assert isinstance(control, SignalSink)
    assert isinstance(control, ICaptureSink)
    assert isinstance(control, IRecognitionSink)
    assert hasattr(control, "routeSignal")
    assert not hasattr(control, "route_signal")
    assert not hasattr(control, "on_recognition_result")
    assert hasattr(control, "onRecognitionResult")
    assert not hasattr(control, "on_capture_success")
    assert hasattr(control, "onCaptureSuccess")


## @brief 对应验收项 d-2：enabled=true 按入队顺序补发，seq 只填不用
def test_d_2_cache_flush_when_enabled(tmp_path: Path) -> None:
    sender = RecordingSender()
    logger = FakeLogger()
    cache = EventCache(True, logger)
    for index in range(3):
        cache.cacheEvent({"type": "ack", "index": index})

    assert cache.isEnabled() is True
    assert cache.pendingCount() == 3
    assert [event["seq"] for event in cache.pendingEvents()] == [1, 2, 3]
    assert cache.flush(sender.send) == 3
    assert [frame["index"] for frame in sender.frames] == [0, 1, 2]
    assert cache.pendingCount() == 0
    assert any("补发 3 条" in record[1] for record in logger.infoRecords)


## @brief 对应验收项 d-2：enabled=false 丢弃缓存，发送器零调用
def test_d_2_cache_discard_when_disabled(tmp_path: Path) -> None:
    sender = RecordingSender()
    logger = FakeLogger()
    cache = EventCache(False, logger)
    cache.cacheEvent({"type": "ack"})
    cache.cacheEvent({"type": "ack"})

    assert cache.flush(sender.send) == 0
    assert sender.frames == []
    assert cache.pendingCount() == 0
    assert any("丢弃断线期间 2 条" in record[1] for record in logger.infoRecords)


## @brief 对应验收项 d-2 / D-03：重复事件不去重，无 seenSeq / seq 比较逻辑
def test_d_2_seq_only_filled_never_used_for_dedup(tmp_path: Path) -> None:
    sender = RecordingSender()
    cache = EventCache(True)
    same: CachedEvent = {"type": "ack", "item": "wrench"}
    cache.cacheEvent(same)
    cache.cacheEvent(same)
    cache.cacheEvent(same)

    assert cache.pendingCount() == 3
    assert [event["seq"] for event in cache.pendingEvents()] == [1, 2, 3]
    assert cache.flush(sender.send) == 3
    assert len(sender.frames) == 3
    assert not hasattr(cache, "seenSeq")
    assert not hasattr(cache, "_seenSeq")


## @brief 对应验收项 d-2：DOWN 期间入缓存、UP 时补发，发送只发生在非回调上下文
def test_d_2_link_down_caches_and_link_up_flushes(tmp_path: Path) -> None:
    sender = RecordingSender()
    control, _ = makeControl(FakeLogger(), sender, enabled=True)
    control.onLinkDown("recv empty", "RECV")
    assert control.isLinkUp() is False

    control.onRecognitionResult(1, {"type": "recognize_ack", "items": []}, "req-1")
    control.onCaptureError(2, EdgeError(ErrorCode.CAPTURE, "采集失败"))
    assert sender.frames == []
    assert control.getOutboxCount() == 2
    assert control.dispatchOutbox() == 2
    assert sender.frames == []

    control.onLinkUp()
    assert control.isLinkUp() is True
    assert len(sender.frames) == 2
    assert sender.frames[0]["type"] == "recognize_ack"
    assert sender.frames[1]["type"] == "error"
    assert control.getOutboxCount() == 0


## @brief 对应验收项 d-2：UP 时 dispatchOutbox 直发，不进缓存
def test_d_2_dispatch_outbox_sends_when_up(tmp_path: Path) -> None:
    sender = RecordingSender()
    control, _ = makeControl(FakeLogger(), sender, enabled=False)
    control.onLinkUp()
    control.onRecognitionResult(1, {"type": "ack", "seq": 99}, "req-1")
    assert control.dispatchOutbox() == 1
    assert len(sender.frames) == 1
    ## 业务 payload 自带的 seq 不被改写或用于判重
    assert sender.frames[0]["seq"] == 99


## @brief 对应验收项 d-3：一键停机严格串行 USB → RECOGNITION → TCP → LOG
def test_d_3_stop_system_strict_serial(tmp_path: Path) -> None:
    logger = FakeLogger()
    trace = CallTrace()
    control, wiring = makeControl(logger, RecordingSender())
    for step in STOP_ORDER:
        wiring.stopActions[step] = partial(trace.record, step)

    control.stopSystem()

    assert tuple(STOP_ORDER) == (STOP_USB, STOP_RECOGNITION, STOP_TCP, STOP_LOG)
    assert trace.events == [STOP_USB, STOP_RECOGNITION, STOP_TCP, STOP_LOG]
    assert control.getStopTrace() == [STOP_USB, STOP_RECOGNITION, STOP_TCP, STOP_LOG]
    assert any("停机统计 顺序=USB-RECOGNITION-TCP-LOG" in record[1]
               for record in logger.infoRecords)


## @brief 对应验收项 d-3 / D-01：自检只留空接口、不启线程、不做能力降级
def test_d_3_selfcheck_stub_d01(tmp_path: Path) -> None:
    logger = FakeLogger()
    control, wiring = makeControl(logger, RecordingSender())
    control.selfCheckSystem()
    assert control.getStopTrace() == []
    assert control.getOutboxCount() == 0
    wiring.initializeModules()
    assert control.getStopTrace() == []
    assert logger.infoRecords == []


## @brief 对应验收项 d-3 / D-02：startSystem 只初始化模块 + 拉链路，不预启采集/识别
def test_d_3_start_system_does_not_prestart_business_threads(tmp_path: Path) -> None:
    logger = FakeLogger()
    trace = CallTrace()
    control, wiring = makeControl(logger, RecordingSender())
    wiring.initializeModules = lambda: trace.record("init")
    wiring.startLink = lambda: trace.record("link")
    wiring.startCapture = lambda: trace.record("capture")
    wiring.triggerRecognition = lambda workerId, requestId: False

    control.startSystem()

    assert trace.events == ["init", "link"]
    assert control.isLinkUp() is False


## @brief 对应验收项 d-3：进程锁失败时 main() 第一件事退出，不装配、不启动
def test_d_3_process_lock_fails_fast_before_assembly(tmp_path: Path) -> None:
    from edge import main

    partsCalled: list[str] = []
    adapter = FakePlatformAdapter(lockResult=None)

    def partsProvider() -> AssemblyParts:
        partsCalled.append("parts")
        return makeParts(tmp_path, RecordingSender(), FakeLogger())

    try:
        main.main(
            partsProvider=partsProvider,
            signalRegistrar=lambda event: None,
            exitWaiter=noAction,
            adapterProvider=lambda: adapter,
        )
        raise AssertionError("锁获取失败应退出进程")
    except SystemExit as error:
        assert "CONFIG" in str(error)

    assert adapter.lockCalls == [DEFAULT_LOCK_FILE_NAME]
    assert partsCalled == []


## @brief 对应验收项 d-4：Windows 端到端装配 → 启动 → 等待 → 串行停机 → 释放锁
def test_d_4_end_to_end_start_and_stop(tmp_path: Path) -> None:
    from edge import main

    logger = FakeLogger()
    sender = RecordingSender()
    trace = CallTrace()
    engine = FakeRecognitionEngine([{"roiId": "r1", "className": "tool"}])
    parts = makeParts(
        tmp_path, sender, logger,
        linkStarter=lambda tcp: trace.record("link-start"),
        logStarter=lambda: trace.record("log-start"),
        logStopper=lambda: trace.record("log-stop"),
    )
    parts.engine = engine
    lockHandle = cast(BinaryIO, BytesIO())
    adapter = FakePlatformAdapter(lockResult=lockHandle)

    main.main(
        partsProvider=lambda: parts,
        signalRegistrar=lambda event: trace.record("signals"),
        exitWaiter=lambda: trace.record("wait"),
        adapterProvider=lambda: adapter,
    )

    assert adapter.lockCalls == [DEFAULT_LOCK_FILE_NAME]
    assert trace.events == ["signals", "log-start", "link-start", "wait", "log-stop"]
    assert engine.loadedPaths == [TEST_MODEL_PATH]
    socket = cast(FakeSocket, parts.socket)
    assert socket.closed is True
    assert any("系统启动完成" in record[1] for record in logger.infoRecords)
    assert any("停机统计 顺序=USB-RECOGNITION-TCP-LOG" in record[1]
               for record in logger.infoRecords)
    assert lockHandle.closed is True


## @brief 对应验收项 d-4：app_init 只做 new + 注入 + 返回，不启线程、不读业务帧
def test_d_4_app_init_only_wires(tmp_path: Path) -> None:
    logger = FakeLogger()
    sender = RecordingSender()
    handlers: dict[str, AsyncHandler] = {"alpha_probe": lambda signal: None}
    parts = makeParts(tmp_path, sender, logger, handlers)
    trace = CallTrace()
    parts.linkStarter = lambda tcp: trace.record("link")
    parts.logStarter = lambda: trace.record("log")

    control = buildSystem(parts)

    assert isinstance(control, EdgeControl)
    assert trace.events == []
    engine = cast(FakeRecognitionEngine, parts.engine)
    assert engine.loadedPaths == []
    assert sender.frames == []
    assert control.getHandlerKeys() == ["alpha_probe"]


## @brief 对应验收项 d-4：main() 不用 try/except 或 if not success 包业务流程
def test_d_4_main_has_no_try_except_business_flow() -> None:
    from edge import main

    source = Path(main.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    mainNode = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    assert not any(isinstance(node, ast.Try) for node in ast.walk(mainNode))
    assert not any(isinstance(node, ast.If) for node in mainNode.body)
    calls = [
        node.func.attr for node in ast.walk(mainNode)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert "acquireOrExit" in calls
    assert calls.index("acquireOrExit") < calls.index("startSystem")


## @brief 对应验收项 d-4：app_init 的 buildSystem 无业务分支（纯装配）
def test_d_4_build_system_has_no_business_branches() -> None:
    from edge import app_init

    source = Path(app_init.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    buildNode = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "buildSystem"
    )
    assert not any(isinstance(node, (ast.If, ast.For, ast.While, ast.Try))
                   for node in ast.walk(buildNode))
    assert callable(defaultParts)


## @brief 对应验收项 d-4：defaultParts 真实 Windows 平台分支与 Sink Fake 契约
def test_d_4_platform_and_fake_contracts() -> None:
    from edge.platform.adapter import PlatformFactory, WindowsAdapter

    ## FakePlatformAdapter 只在 Windows 返回完整实现，构造注入分支按平台工厂裁决
    adapter = PlatformFactory.create()
    if isinstance(adapter, WindowsAdapter):
        assert adapter.newline() == "\r\n"
    sink = FakeRecognitionSink()
    assert isinstance(sink, IRecognitionSink)
    assert hasattr(sink, "onRecognitionResult")
    assert not hasattr(sink, "on_recognition_result")
    logger: ILogger = FakeLogger()
    assert callable(logger.error)
