"""端到端联调用例：桩上位机 + 真实 TCP 栈，覆盖回包字段、同一请求只处理一次、周期帧与重复扫描。"""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from threading import Event
from time import monotonic
from typing import cast

from edge.app_init import (
    CaptureTrigger,
    RecognitionCapability,
    buildAsyncHandlers,
    buildPeriodicFrame,
    drainOutbox,
)
from edge.control.edge_control import (
    STOP_LOG,
    STOP_RECOGNITION,
    STOP_TCP,
    STOP_USB,
    CachedEvent,
    EdgeControl,
    FrameSender,
    ModuleWiring,
)
from edge.control.edge_dispatch_thread import EdgeDispatchThread
from edge.interfaces.i_sinks import AckFrame
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.tcp.tcp_control_layer import LINK_UP, TcpControlLayer
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.integration.fake_host import FakeHost, HostFrame
from edge.tests.integration.tcp_client_socket import TcpClientSocket

## @file edge/tests/integration/test_end_to_end_recognition.py
## @brief 端到端联调用例：桩上位机加真实 TCP 栈，覆盖回包字段、同一请求只处理一次、周期帧与重复扫描
## @author 边缘计算项目

## @brief 联调单帧字节上限，与上位机一致
MAX_FRAME_SIZE: int = 1024 * 1024
## @brief 联调应答排空周期秒
DISPATCH_INTERVAL_SEC: float = 0.05
## @brief 联调周期帧间隔秒，比生产值短以便用例快速完成
HEART_INTERVAL_SEC: float = 0.3
## @brief 等待边缘机接入的最长秒数
CLIENT_WAIT_SEC: float = 5.0
## @brief 等待回包的最长秒数
ACK_WAIT_SEC: float = 5.0
## @brief 等待链路状态变化的最长秒数
LINK_WAIT_SEC: float = 5.0
## @brief 联调摄像头状态序列，8 路
TEST_CAMERA_STATUSES: tuple[str, ...] = ("ok", "ok", "ok", "ok", "ok", "ok", "ok", "ok")
## @brief 正式配置文件路径
CONFIG_PATH: Path = Path(__file__).resolve().parents[2] / "config" / "config.ini"
## @brief ROI 对照表路径
ROI_CSV_PATH: Path = Path(__file__).resolve().parents[2] / "config" / "roi_binding.csv"
## @brief 契约要求的 ROI 对照表表头，十二列，与 spec-digest §8.1 逐字一致
ROI_CSV_HEADER: str = (
    "roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,"
    "confidence,rect_x1,rect_y1,rect_x2,rect_y2"
)


## @brief 空动作；联调里不需要真实模块的停机步骤
#  @return 无
def noAction() -> None:
    return None


## @brief 等待条件成立；用可打断等待代替裸 sleep
#  @param condition 条件函数
#  @param timeoutSec 最长等待秒数
#  @return 条件成立返回 True
def waitUntil(condition: Callable[[], bool], timeoutSec: float) -> bool:
    deadline = monotonic() + timeoutSec
    while monotonic() < deadline:
        if condition():
            return True
        Event().wait(0.02)
    return condition()


## @brief 联调摄像头状态提供器：按状态序列给出 8 路状态
#  @return 状态列表
def testCameraStatus() -> list[dict[str, object]]:
    return [
        {"camera_id": f"CAM{index + 1}", "status": status}
        for index, status in enumerate(TEST_CAMERA_STATUSES)
    ]


## @brief 构造协议形状的识别应答：items 每项恰好 4 字段
#  @param requestId 请求标识
#  @return 应答帧
def buildProtocolAck(requestId: str) -> AckFrame:
    items: list[dict[str, object]] = [
        {
            "position": "A-01-01",
            "tool_id": "C01-T0007",
            "confidence": 0.93,
            "alert_type": "none",
        },
        {
            "position": "A-01-02",
            "tool_id": "",
            "confidence": 0.0,
            "alert_type": "missing",
        },
    ]
    return {"type": "recognize_ack", "request_id": requestId, "items": items}


## @brief 帧发送器：按协议组帧并经真实 TCP 发出
#  @param comm 通信封装
#  @return 帧发送器
def buildTestFrameSender(comm: TcpComm) -> FrameSender:
    def sendFrame(frame: CachedEvent) -> bool:
        return comm.send(comm.encodeFrame(frame))

    return sendFrame


## @brief 失败应答构造器：联调用最小实现
#  @param workerId 线程编号
#  @param exception 业务异常
#  @return 失败应答帧
def buildTestFailureFrame(workerId: int, exception: Exception) -> CachedEvent:
    return {"type": "error", "workerId": workerId, "message": str(exception)}


## @brief 联调扫描桩：记录扫描次数，可延迟完成识别以模拟请求在途
class ScanStub:
    ## @brief 构造扫描桩
    #  @param control 控制层门面
    def __init__(self, control: EdgeControl) -> None:
        ## @brief 控制层门面
        self._control: EdgeControl = control
        ## @brief 扫描次数，用于断言重复请求不重复扫描
        self.scanCount: int = 0
        ## @brief 已收到但未完成识别的请求标识
        self.pendingRequestId: str = ""
        ## @brief 是否延迟完成识别
        self.deferCompletion: bool = False

    ## @brief 触发一次扫描
    #  @param requestId 请求标识
    #  @return 恒为 True
    def triggerScan(self, requestId: str) -> bool:
        self.scanCount += 1
        if self.deferCompletion:
            self.pendingRequestId = requestId
            return True
        self.completeScan(requestId)
        return True

    ## @brief 识别触发回调：产出协议形状的应答
    #  @param workerId 线程编号
    #  @param requestId 请求标识
    #  @return 恒为 True
    def triggerRecognition(self, workerId: int, requestId: str) -> bool:
        self.completeScan(requestId)
        return True

    ## @brief 完成扫描并把应答交回控制层
    #  @param requestId 请求标识
    #  @return 无
    def completeScan(self, requestId: str) -> None:
        self._control.onRecognitionResult(1, buildProtocolAck(requestId), requestId)


## @brief 构造联调边缘机：真实 TCP 栈 + 真实控制层 + 桩采集与识别
#  @param hostAddress 桩上位机地址
#  @param hostPort 桩上位机端口
#  @return 控制层与扫描桩二元组
def buildEdgeUnderTest(hostAddress: str,
                       hostPort: int) -> tuple[EdgeControl, ScanStub]:
    logger = FakeLogger()
    clientSocket = TcpClientSocket(hostAddress, hostPort)
    comm = TcpComm(clientSocket, MAX_FRAME_SIZE, logger)
    trigger = CaptureTrigger()
    wiring = ModuleWiring()
    control = EdgeControl(
        logger, buildAsyncHandlers(trigger, RecognitionCapability()), wiring,
        buildTestFrameSender(comm), buildTestFailureFrame,
    )
    scanStub = ScanStub(control)
    trigger.bind(scanStub.triggerScan)
    tcp = TcpControlLayer(
        clientSocket, logger, [0.05], MAX_FRAME_SIZE, HEART_INTERVAL_SEC,
        buildPeriodicFrame(testCameraStatus, monotonic(), "edge-test-0.1.0"), control,
    )
    wiring.initializeModules = noAction
    wiring.startLink = tcp.start
    wiring.startCapture = noAction
    wiring.triggerRecognition = scanStub.triggerRecognition
    wiring.linkUpProbe = partial(lambda tcpLayer: tcpLayer.getState() == LINK_UP, tcp)
    wiring.stopActions = {
        STOP_USB: noAction,
        STOP_RECOGNITION: noAction,
        STOP_TCP: tcp.stop,
        STOP_LOG: noAction,
    }
    dispatchThread = EdgeDispatchThread(
        partial(drainOutbox, control), logger, DISPATCH_INTERVAL_SEC,
    )
    control.attachDispatchThread(dispatchThread)
    return control, scanStub


## @brief 起一套桩上位机与联调边缘机，返回三者供用例驱动
#  @return 桩上位机、控制层与扫描桩
def startEdgeUnderTest() -> tuple[FakeHost, EdgeControl, ScanStub]:
    host = FakeHost()
    port = host.start()
    control, scanStub = buildEdgeUnderTest("127.0.0.1", port)
    control.startSystem()
    return host, control, scanStub


## @brief 对应验收项 3：端到端回包字段合法，桩上位机校验通过
def testEndToEndAckFieldsAreProtocolCompliant() -> None:
    host, control, scanStub = startEdgeUnderTest()
    try:
        assert host.waitClient(CLIENT_WAIT_SEC) is True
        host.sendRecognizeReq("req-e2e-0001")

        ack = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)

        assert ack is not None
        assert host.validateAck(ack) == []
        assert str(ack.get("request_id")) == "req-e2e-0001"
        assert scanStub.scanCount == 1
    finally:
        control.stopSystem()
        host.stop()


## @brief 对应验收项 4：同一 request_id 连发两次，只扫描一次并回两次相同结果
def testSameRequestIdIsIdempotent() -> None:
    host, control, scanStub = startEdgeUnderTest()
    try:
        assert host.waitClient(CLIENT_WAIT_SEC) is True
        host.sendRecognizeReq("req-dup-0001")
        firstAck = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)
        host.sendRecognizeReq("req-dup-0001")
        secondAck = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)

        assert firstAck is not None
        assert secondAck is not None
        assert firstAck["items"] == secondAck["items"]
        assert scanStub.scanCount == 1
    finally:
        control.stopSystem()
        host.stop()


## @brief 对应验收项 6：请求在途时重复下发同一 request_id，不重复触发 8 路扫描
def testDuplicateRequestsInFlightShareOneScan() -> None:
    host = FakeHost()
    port = host.start()
    control, scanStub = buildEdgeUnderTest("127.0.0.1", port)
    scanStub.deferCompletion = True
    control.startSystem()
    try:
        assert host.waitClient(CLIENT_WAIT_SEC) is True
        for _index in range(3):
            host.sendRecognizeReq("req-dup-0002")

        assert waitUntil(lambda: scanStub.scanCount == 1, ACK_WAIT_SEC) is True
        scanStub.completeScan(scanStub.pendingRequestId)

        acks: list[HostFrame] = []
        for _index in range(3):
            frame = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)
            assert frame is not None
            acks.append(frame)

        assert scanStub.scanCount == 1
        assert all(frame["items"] == acks[0]["items"] for frame in acks)
    finally:
        control.stopSystem()
        host.stop()


## @brief 对应验收项 5：周期帧为 periodic，含 uptime_sec / software_version 与 8 路摄像头状态
def testPeriodicFrameFormatAndCameraStatus() -> None:
    host, control, _scanStub = startEdgeUnderTest()
    try:
        assert host.waitClient(CLIENT_WAIT_SEC) is True

        frame = host.waitFrameOfType("periodic", ACK_WAIT_SEC)

        assert frame is not None
        assert host.validatePeriodic(frame) == []
        assert str(frame.get("type")) == "periodic"
        assert len(cast(list[object], frame.get("camera_status"))) == 8
    finally:
        control.stopSystem()
        host.stop()


## @brief 对应验收项 5：正式配置文件键齐全，周期 3 秒、8 路相机、4 组采集与识别目录
def testProductionConfigHasRequiredKeys() -> None:
    from edge.infra.config_manager import IniConfigManager

    config = IniConfigManager(str(CONFIG_PATH))

    assert int(config.get("tcp", "heart_interval_sec")) == 3
    assert int(config.get("tcp", "max_frame_size")) == 1048576
    assert cast(list[int], config.get("usb", "camera_indices")) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert len(cast(list[str], config.get("usb", "save_dirs"))) == 4
    assert len(cast(list[str], config.get("recognition", "save_dirs"))) == 4
    assert str(config.get("usb", "focus_mode")) == "fixed"
    assert len(cast(list[float], config.get("usb", "focus_positions"))) == 8
    assert len(cast(list[float], config.get("usb", "zoom_positions"))) == 8
    assert int(config.get("usb", "focus_stable_ms")) == 200
    assert str(config.get("recognition", "roi_binding_csv")).endswith("roi_binding.csv")


## @brief 对应验收项 5：ROI 对照表表头与契约逐字一致，样例数据 4 行
def testRoiBindingHeaderMatchesContract() -> None:
    lines = ROI_CSV_PATH.read_text(encoding="utf-8").splitlines()

    assert lines[0] == ROI_CSV_HEADER
    assert len(lines) == 5
    for line in lines[1:]:
        fields = line.split(",")
        assert len(fields) == 12
        assert fields[1] in ("1", "2", "3", "4")
        assert fields[3].startswith("A-01-")
        assert fields[4].startswith("C01-T")
        assert fields[6].startswith("mk_")
