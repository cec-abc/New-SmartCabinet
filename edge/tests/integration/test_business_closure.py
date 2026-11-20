"""业务流程走通二次校验用例：降级出帧、换轮扫描、解码线程存活、相机状态与配置校验。"""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from threading import Event
from time import monotonic

from edge.app_init import (
    AssemblyParts,
    CaptureTrigger,
    RecognitionCapability,
    buildAsyncHandlers,
    buildSystem,
    validateRoiWorkerScope,
)
from edge.control.edge_control import CachedEvent, EdgeControl, ModuleWiring
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingLoader, RoiBindingRow
from edge.interfaces.i_camera import FrameImage, ICameraDevice
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.modules.recognition.recognition_stitcher import FrameStitcher
from edge.modules.recognition.recognition_utils import (
    ClassItemMap,
    RoiBindMap,
    RoiConfig,
)
from edge.modules.recognition.recognition_yolo_engine import YoloEngine
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.usb.usb_controller import UsbController
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_socket import FakeSocket
from edge.tests.integration.fake_host import FakeHost
from edge.tests.integration.host_protocol_checker import check_ack, check_coverage
from edge.tests.integration.tcp_client_socket import TcpClientSocket

## @file edge/tests/integration/test_business_closure.py
## @brief 业务流程走通二次校验用例：降级出帧、换轮扫描、解码线程存活、相机状态与配置校验
## @author 边缘计算项目

## @brief 工程根目录下的配置文件目录
CONFIG_DIR: Path = Path(__file__).resolve().parents[2] / "config"
## @brief ROI 对照表路径
ROI_CSV_PATH: Path = CONFIG_DIR / "roi_binding.csv"
## @brief 配置说明文档路径
CONFIG_README_PATH: Path = CONFIG_DIR / "README.md"
## @brief 等待应答的最长秒数
ACK_WAIT_SEC: float = 5.0
## @brief 等待上位机接入的最长秒数
CLIENT_WAIT_SEC: float = 5.0
## @brief 联调单帧字节上限
MAX_FRAME_SIZE: int = 1024 * 1024
## @brief 联调周期帧间隔秒
HEART_INTERVAL_SEC: float = 0.3
## @brief 采集线程数，与对照表行数一致
WORKER_COUNT: int = 4
## @brief 相机路数，整柜 8 路
CAMERA_COUNT: int = 8
## @brief 样例标志类别名
SAMPLE_MARKERS: tuple[str, ...] = ("mk_8821", "mk_8822", "mk_8823", "mk_8824")
## @brief 样例命中置信度
SAMPLE_CONFIDENCE: float = 0.93


## @brief 拼接器桩：拼图与裁剪都返回固定字节，不依赖图像处理库
class StubStitcher(FrameStitcher):
    ## @brief 拼接本轮两路帧
    #  @param frames 本轮帧元组，左路在前
    #  @return 固定拼接字节
    def stitch(self, frames: tuple[bytes, ...]) -> bytes:
        return b"STUB-PANORAMA"

    ## @brief 裁出区域图像
    #  @param image 拼接全景的图像字节
    #  @param roi 对照表行
    #  @return 固定裁剪字节
    def crop(self, image: bytes, roi: RoiBindingRow) -> bytes:
        return b"STUB-ROI"


## @brief 引擎桩：对样例标志类别全部命中
class MarkerEngine(IRecognitionEngine):
    ## @brief 构造引擎桩
    def __init__(self) -> None:
        ## @brief 已加载的模型路径
        self.loadedPaths: list[str] = []

    ## @brief 记录模型加载
    #  @param path 模型文件路径
    #  @return 无
    def loadModel(self, path: str) -> None:
        self.loadedPaths.append(path)

    ## @brief 返回全部样例标志的检测结果
    #  @param image 图像字节
    #  @return 检测结果列表
    def infer(self, image: FrameImage) -> list[DetectionItem]:
        return [
            {"className": marker, "confidence": SAMPLE_CONFIDENCE}
            for marker in SAMPLE_MARKERS
        ]


## @brief 相机桩：可指定打开失败，并按设备序号给出状态
class StubCamera(ICameraDevice):
    ## @brief 构造相机桩
    #  @param index 设备序号，用于区分物理编号
    #  @param frame 取图返回的图像字节
    #  @param openFails 打开是否直接失败
    def __init__(self, index: int, frame: FrameImage = b"FRAME",
                 openFails: bool = False) -> None:
        ## @brief 设备序号
        self.index: int = index
        ## @brief 取图返回的图像字节
        self.frame: FrameImage = frame
        ## @brief 打开是否直接失败
        self.openFails: bool = openFails
        ## @brief 是否已打开
        self.opened: bool = False
        ## @brief 是否已关闭
        self.closed: bool = False
        ## @brief 是否成功打开过；与真实设备一致，关闭过但从未打开成功仍为 False
        self.everOpened: bool = False

    ## @brief 打开设备；按桩配置决定是否失败
    #  @return 无
    #  @raises EdgeError 桩配置为打开失败时抛出，code=CAPTURE
    def open(self) -> None:
        if self.openFails:
            raise EdgeError(ErrorCode.CAPTURE, f"桩相机打开失败 {self.index}")
        self.opened = True
        self.everOpened = True

    ## @brief 读取一帧
    #  @return 图像字节
    def readFrame(self) -> FrameImage | None:
        return self.frame

    ## @brief 关闭设备
    #  @return 无
    def close(self) -> None:
        self.opened = False
        self.closed = True

    ## @brief 返回状态快照
    #  @return 状态字典
    def getStatus(self) -> dict[str, object]:
        return {
            "deviceAddr": f"cam{self.index + 1}",
            "opened": self.opened,
            "everOpened": self.everOpened,
            "commOk": True,
        }


## @brief 记录帧的发送器
class RecordingSender:
    ## @brief 构造发送器
    def __init__(self) -> None:
        ## @brief 已发送帧
        self.frames: list[CachedEvent] = []

    ## @brief 记录发送并返回成功
    #  @param frame 待发送帧
    #  @return 恒为 True
    def send(self, frame: CachedEvent) -> bool:
        self.frames.append(frame)
        return True


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


## @brief 空动作；链路启动器要接一个通信门面参数
#  @param tcpLayer 通信门面
#  @return 无
def noLinkStart(tcpLayer: object) -> None:
    return None


## @brief 空动作
#  @return 无
def noAction() -> None:
    return None


## @brief 固定左右图读取器
#  @param saveDir 采集目录
#  @param workerId 线程编号
#  @return 左右图像字节对
def fixedFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
    return (b"LEFT", b"RIGHT")


## @brief 直接执行推理，不施加真实等待
#  @param task 推理闭包
#  @param timeoutSec 超时秒数
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


## @brief 构造四组相机对；指定序号的那组左相机打开即失败
#  @param failingPairs 打开即失败的相机对序号集合
#  @return 相机对列表
def buildCameraPairs(
    failingPairs: tuple[int, ...] = (),
) -> list[tuple[ICameraDevice, ICameraDevice]]:
    pairs: list[tuple[ICameraDevice, ICameraDevice]] = []
    for index in range(WORKER_COUNT):
        left = StubCamera(index, openFails=index in failingPairs)
        right = StubCamera(index + WORKER_COUNT)
        pairs.append((left, right))
    return pairs


## @brief 读取随工程发布的 ROI 对照表
#  @return 对照表行列表
def loadSampleRows() -> list[RoiBindingRow]:
    return RoiBindingLoader(FakeLogger()).load(str(ROI_CSV_PATH))


## @brief 构造降级条目提供器：按对照表行给出未识别条目
#  @param rows 对照表行
#  @return 降级条目提供器
def buildSampleDegradedProvider(
    rows: list[RoiBindingRow],
) -> Callable[[int], list[object]]:
    def provideItems(workerId: int) -> list[object]:
        return [
            {
                "position": row.position,
                "tool_id": "",
                "confidence": 0.0,
                "alert_type": "unknown",
            }
            for row in rows if row.workerId == workerId
        ]

    return provideItems


## @brief 构造装配参数；采集与识别目录落在临时目录内
#  @param root 临时根路径
#  @param failingPairs 打开即失败的相机对序号集合
#  @return 装配参数
def makeParts(root: Path, failingPairs: tuple[int, ...] = ()) -> AssemblyParts:
    dirs = [root / f"worker{index}" for index in range(1, WORKER_COUNT + 1)]
    for saveDir in dirs:
        saveDir.mkdir(parents=True, exist_ok=True)
    trigger = CaptureTrigger()
    rows = loadSampleRows()
    return AssemblyParts(
        logger=FakeLogger(),
        socket=FakeSocket(),
        cameraPairs=buildCameraPairs(failingPairs),
        captureDirs=[str(saveDir) for saveDir in dirs],
        recognitionDirs=[str(saveDir) for saveDir in dirs],
        engine=MarkerEngine(),
        modelPath="model.bin",
        frameLoader=fixedFrames,
        timeoutRunner=directRunner,
        inferTimeoutSec=3.0,
        roiConfig=RoiConfig({}),
        classItemMap=ClassItemMap({}),
        roiBindMap=RoiBindMap({}),
        rollThreshold=0.3,
        usageRatio=quietDisk,
        clock=fixedStamp,
        backoffSeq=[0.05],
        maxFrameSize=MAX_FRAME_SIZE,
        heartIntervalSec=HEART_INTERVAL_SEC,
        buildHeartbeat=lambda: {"type": "periodic"},
        asyncHandlers=buildAsyncHandlers(trigger, RecognitionCapability()),
        failureFrameBuilder=lambda workerId, exception: {
            "type": "error", "workerId": workerId, "message": str(exception),
        },
        frameSender=lambda frame: True,
        linkStarter=noLinkStart,
        logStarter=noAction,
        logStopper=noAction,
        cameraIndices=list(range(1, CAMERA_COUNT + 1)),
        roiBindingRows=rows,
        classItemComboMap={},
        stitcher=StubStitcher(),
        captureTrigger=trigger,
    )


## @brief 装配一套带真实采集与识别模块、并接入桩上位机的边缘机
#  @param root 临时根路径
#  @param failingPairs 打开即失败的相机对序号集合
#  @return 桩上位机与控制层
def startLinkedEdge(
    root: Path,
    failingPairs: tuple[int, ...] = (),
) -> tuple[FakeHost, EdgeControl]:
    host = FakeHost()
    port = host.start()
    parts = makeParts(root, failingPairs)
    clientSocket = TcpClientSocket("127.0.0.1", port)
    parts.socket = clientSocket
    comm = TcpComm(clientSocket, MAX_FRAME_SIZE, parts.logger)

    def sendFrame(frame: CachedEvent) -> bool:
        return comm.send(comm.encodeFrame(frame))

    parts.frameSender = sendFrame
    parts.linkStarter = lambda tcpLayer: tcpLayer.start()
    control = buildSystem(parts)
    control.startSystem()
    assert host.waitClient(CLIENT_WAIT_SEC) is True
    return host, control


## @brief 构造只带控制层的轻量边缘机，用于聚合与超时用例
#  @param expectedWorkerCount 期望采集线程数
#  @param aggregationTimeoutSec 聚合等待上限秒数
#  @return 控制层与帧记录器
def makeControl(expectedWorkerCount: int,
                aggregationTimeoutSec: float) -> tuple[EdgeControl, RecordingSender]:
    sender = RecordingSender()
    wiring = ModuleWiring()
    for step in ("USB", "RECOGNITION", "TCP", "LOG"):
        wiring.stopActions[step] = noAction
    rows = loadSampleRows()
    control = EdgeControl(
        FakeLogger(), {"recognize_req": lambda signal: None}, wiring,
        sender.send,
        lambda workerId, exception: {"type": "error"},
        expectedWorkerCount=expectedWorkerCount,
        degradedItemsProvider=buildSampleDegradedProvider(rows),
        aggregationTimeoutSec=aggregationTimeoutSec,
    )
    ## 链路就绪后应答才会直发，否则只进待发队列
    control.onLinkUp()
    return control, sender


## @brief 从记录帧里挑出识别应答
#  @param frames 已发送帧
#  @param requestId 期望的请求标识
#  @return 匹配的应答帧；没有则返回 None
def pickAck(frames: list[CachedEvent], requestId: str) -> CachedEvent | None:
    for frame in frames:
        if frame.get("type") == "recognize_ack" and frame.get("request_id") == requestId:
            return frame
    return None


## @brief 反复排空待发应答直到拿到目标应答
#  @param control 控制层
#  @param sender 帧记录器
#  @param requestId 期望的请求标识
#  @param timeoutSec 最长等待秒数
#  @return 应答帧；超时返回 None
def waitAck(control: EdgeControl, sender: RecordingSender,
            requestId: str, timeoutSec: float) -> CachedEvent | None:
    deadline = monotonic() + timeoutSec
    while monotonic() < deadline:
        control.dispatchOutbox()
        ack = pickAck(sender.frames, requestId)
        if ack is not None:
            return ack
        Event().wait(0.02)
    control.dispatchOutbox()
    return pickAck(sender.frames, requestId)


## @brief 对应验收项：某一路相机打不开时，本轮仍产出协议形状的降级应答
def test_worker_failure_still_yields_protocol_ack(tmp_path: Path) -> None:
    host, control = startLinkedEdge(tmp_path, failingPairs=(2,))
    try:
        host.sendRecognizeReq("req-fail-0001")

        ack = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)

        assert ack is not None
        assert set(ack.keys()) == {"type", "request_id", "items"}
        items = ack["items"]
        assert isinstance(items, list)
        positions = [str(item["position"]) for item in items]
        assert positions == ["A-01-01", "A-01-02", "A-01-03", "A-01-04"]
        failedItem = items[2]
        assert failedItem["tool_id"] == ""
        assert failedItem["alert_type"] == "unknown"
        assert failedItem["confidence"] == 0.0
        healthyItem = items[0]
        assert healthyItem["tool_id"] == "C01-T0007"
        assert healthyItem["alert_type"] == "none"
        assert check_ack(ack, "req-fail-0001").hostAccepts is True
        assert check_coverage(items, positions).hostAccepts is True
    finally:
        control.stopSystem()
        host.stop()


## @brief 对应验收项：第二个识别请求仍能拿到自己的应答，不因采集已在运行而失败
def test_second_request_gets_its_own_ack(tmp_path: Path) -> None:
    host, control = startLinkedEdge(tmp_path)
    try:
        host.sendRecognizeReq("req-second-0001")
        firstAck = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)
        assert firstAck is not None
        assert str(firstAck.get("request_id")) == "req-second-0001"

        host.sendRecognizeReq("req-second-0002")
        secondAck = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)

        assert secondAck is not None
        assert str(secondAck.get("request_id")) == "req-second-0002"
        assert check_ack(secondAck, "req-second-0002").hostAccepts is True
    finally:
        control.stopSystem()
        host.stop()


## @brief 对应验收项：真实 TCP 栈上连续两次识别请求都拿到应答，解码线程不被业务异常打穿
def test_real_tcp_serves_two_requests_and_keeps_decode_thread(tmp_path: Path) -> None:
    host, control = startLinkedEdge(tmp_path)
    try:
        host.sendRecognizeReq("req-tcp-0001")
        firstAck = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)
        assert firstAck is not None
        assert str(firstAck.get("request_id")) == "req-tcp-0001"

        host.sendRecognizeReq("req-tcp-0002")
        secondAck = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)
        assert secondAck is not None
        assert str(secondAck.get("request_id")) == "req-tcp-0002"
        assert check_ack(secondAck, "req-tcp-0002").hostAccepts is True

        decodeThreads = [
            thread for thread in threading.enumerate()
            if thread.name == "TcpDecode" and thread.is_alive()
        ]
        assert len(decodeThreads) == 1
    finally:
        control.stopSystem()
        host.stop()


## @brief 对应验收项：聚合等待上限到点后强制降级出帧，请求不会悬着不回
def test_aggregation_timeout_forces_degraded_ack() -> None:
    control, sender = makeControl(expectedWorkerCount=WORKER_COUNT,
                                  aggregationTimeoutSec=0.2)
    control.routeSignal({"type": "recognize_req", "request_id": "req-timeout-0001"})
    assert control.getOutboxCount() == 0

    ack = waitAck(control, sender, "req-timeout-0001", ACK_WAIT_SEC)

    assert ack is not None
    assert set(ack.keys()) == {"type", "request_id", "items"}
    items = ack["items"]
    assert isinstance(items, list)
    positions = [str(item["position"]) for item in items]
    assert positions == ["A-01-01", "A-01-02", "A-01-03", "A-01-04"]
    assert all(item["tool_id"] == "" for item in items)
    assert all(item["alert_type"] == "unknown" for item in items)
    assert check_ack(ack, "req-timeout-0001").hostAccepts is True


## @brief 对应验收项：识别线程抛异常时该请求也有形状合法的应答
def test_recognition_error_still_answers_request() -> None:
    control, sender = makeControl(expectedWorkerCount=WORKER_COUNT,
                                  aggregationTimeoutSec=5.0)
    control.routeSignal({"type": "recognize_req", "request_id": "req-err-0001"})
    for workerId in (1, 3, 4):
        control.onRecognitionResult(
            workerId,
            {"type": "recognize_ack", "items": buildWorkerItems(workerId)},
            "req-err-0001",
        )
    control.onRecognitionError(2, EdgeError(ErrorCode.INFERENCE_TIMEOUT, "推理超时"))

    ack = waitAck(control, sender, "req-err-0001", ACK_WAIT_SEC)

    assert ack is not None
    items = ack["items"]
    assert isinstance(items, list)
    ## 其余三路已回，失败那一路降级补齐后清单仍覆盖全部货位
    positions = [str(item["position"]) for item in items]
    assert positions == ["A-01-01", "A-01-02", "A-01-03", "A-01-04"]
    degraded = items[1]
    assert degraded["tool_id"] == ""
    assert degraded["alert_type"] == "unknown"
    assert check_ack(ack, "req-err-0001").hostAccepts is True


## @brief 构造某个采集线程上报的正常条目
#  @param workerId 采集线程编号
#  @return 协议条目列表
def buildWorkerItems(workerId: int) -> list[dict[str, object]]:
    rows = [row for row in loadSampleRows() if row.workerId == workerId]
    return [
        {
            "position": row.position,
            "tool_id": row.toolId,
            "confidence": SAMPLE_CONFIDENCE,
            "alert_type": "none",
        }
        for row in rows
    ]


## @brief 对应验收项：相机状态编号与物理编号一致，不按采集线程顺序交错
def test_camera_status_follows_physical_order(tmp_path: Path) -> None:
    pairs = buildCameraPairs(failingPairs=(2, 3))
    saveDirs = [tmp_path / f"worker{index}" for index in range(1, WORKER_COUNT + 1)]
    for saveDir in saveDirs:
        saveDir.mkdir(parents=True, exist_ok=True)
    controller = UsbController(
        pairs,
        [str(saveDir) for saveDir in saveDirs],
        type("Sink", (), {
            "onCaptureSuccess": lambda *args: None,
            "onCaptureError": lambda *args: None,
        })(),
        FakeLogger(), 0.3, quietDisk, fixedStamp,
    )
    controller.init()

    statuses = controller.getCameraStatus()

    assert [str(item["camera_id"]) for item in statuses] == [
        f"CAM{index + 1}" for index in range(CAMERA_COUNT)
    ]
    assert [str(item["status"]) for item in statuses] == [
        "ok", "ok", "offline", "offline", "ok", "ok", "ok", "ok",
    ]


## @brief 对应验收项：对照表线程编号超过实际采集线程数时启动即判配置错误
def test_roi_worker_scope_fails_fast() -> None:
    rows = loadSampleRows()

    try:
        validateRoiWorkerScope(rows, WORKER_COUNT - 1)
        raise AssertionError("线程编号超出实际采集线程数应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG


## @brief 对应验收项：配置说明标注了标志类别名口径与线程编号口径
def test_config_readme_documents_marker_and_worker_rules() -> None:
    text = CONFIG_README_PATH.read_text(encoding="utf-8")

    assert "marker_id" in text
    assert "类别名" in text
    assert "worker_id" in text
    assert "上板" in text


## @brief 对应验收项：两条推理后端产出的检测结果键名一致
def test_two_inference_backends_share_detection_keys() -> None:
    engine = YoloEngine(logger=FakeLogger())
    engine._model = type("Model", (), {"names": {0: "person"}})()  # noqa: SLF001
    ultralyticsItems = engine.parseUltralyticsResults(buildFakeUltralyticsResult())
    onnxItems = engine.parseOnnxOutput(
        [buildFakeOnnxOutput()], buildFakeArrayLibrary(), {0: "person"},
    )

    assert len(ultralyticsItems) == 1
    assert len(onnxItems) == 1
    assert sorted(ultralyticsItems[0].keys()) == ["box", "className", "confidence"]
    assert sorted(onnxItems[0].keys()) == ["box", "className", "confidence"]
    assert sorted(ultralyticsItems[0].keys()) == sorted(onnxItems[0].keys())


## @brief 构造 ultralytics 推理结果桩
#  @return 推理结果桩
def buildFakeUltralyticsResult() -> object:
    ## @brief 框集合桩
    class FakeBoxes:
        ## @brief 类别编号
        cls: list[int] = [0]

        ## @brief 置信度
        conf: list[float] = [0.91]

        ## @brief 检测框像素坐标，相对输入图；解析时需要
        xyxy: list[list[float]] = [[10.0, 20.0, 30.0, 40.0]]

        ## @brief 框数量
        #  @return 恒为 1
        def __len__(self) -> int:
            return 1

    ## @brief 单帧结果桩
    class FakeFrame:
        ## @brief 框集合
        boxes: FakeBoxes = FakeBoxes()

    ## @brief 结果列表桩
    class FakeResults:
        ## @brief 取第一帧
        #  @param index 索引
        #  @return 单帧结果
        def __getitem__(self, index: int) -> object:
            return FakeFrame()

        ## @brief 判非空
        #  @return 恒为 True
        def __bool__(self) -> bool:
            return True

    return FakeResults()


## @brief 构造 onnx 输出桩：一行一目标，类别分数在下标 4 之后
#  @return 输出张量桩
def buildFakeOnnxOutput() -> object:
    ## @brief 最小二维数组桩
    class FakeArray:
        ## @brief 构造数组桩
        #  @param rows 行数据
        def __init__(self, rows: list[list[float]]) -> None:
            ## @brief 行数据
            self.rows: list[list[float]] = rows

        ## @brief 行列数
        #  @return 形状元组
        @property
        def shape(self) -> tuple[int, int]:
            return (len(self.rows), len(self.rows[0]) if self.rows else 0)

        ## @brief 转置
        #  @return 转置后的数组桩
        def transpose(self) -> FakeArray:
            return FakeArray([list(column) for column in zip(*self.rows)])

        ## @brief 取二维切片
        #  @param key 行下标与列切片
        #  @return 切片结果
        def __getitem__(self, key: tuple[int, slice]) -> list[float]:
            index, columns = key
            return self.rows[index][columns]

    ## @brief 输出形状与真机一致：类别数加 4 行、目标数列，转置后每行一个目标
    rows = [[0.0] * 84 for _ in range(6)]
    rows[4][0] = 0.87
    rows[5][0] = 0.05
    return FakeArray(rows)


## @brief 构造数值计算库桩，只提供 argmax
#  @return 数值计算库桩
def buildFakeArrayLibrary() -> object:
    ## @brief 求最大值的下标
    #  @param values 数值列表
    #  @return 最大值下标
    def argmax(values: list[float]) -> int:
        return max(range(len(values)), key=lambda index: values[index])

    return type("ArrayLibrary", (), {"argmax": staticmethod(argmax)})


## @brief 周期帧里的摄像头状态必须与采集门面的物理顺序一致
def test_periodic_frame_camera_status_matches_usb(tmp_path: Path) -> None:
    parts = makeParts(tmp_path)
    buildSystem(parts)
    statuses = parts.cameraStatus.readStatus()

    assert len(statuses) == CAMERA_COUNT
    assert [str(item["camera_id"]) for item in statuses] == [
        f"CAM{index + 1}" for index in range(CAMERA_COUNT)
    ]


## @brief 停机后不得残留聚合中间态，避免长时间运行内存只涨不落
def test_stop_system_clears_aggregation_state() -> None:
    control, _sender = makeControl(expectedWorkerCount=WORKER_COUNT,
                                   aggregationTimeoutSec=5.0)
    control.routeSignal({"type": "recognize_req", "request_id": "req-stop-0001"})
    control.onRecognitionResult(1, {"type": "recognize_ack", "items": []},
                                "req-stop-0001")

    assert control.getPendingRequestCount() == 1
    assert control.getAggregationCount() == 1

    control.stopSystem()

    assert control.getPendingRequestCount() == 0
    assert control.getAggregationCount() == 0
    assert control.getCompletedAckCount() == 0
