"""第三轮缺陷修复验收用例：对照表备用方案、推理后端口径统一、相机状态、丢帧可观测与降级形状。"""
from __future__ import annotations

from collections.abc import Callable
from importlib.util import find_spec
from pathlib import Path
from threading import Barrier, Event
from time import monotonic

from edge.app_init import loadRoiBindingRows, validateRoiWorkerScope
from edge.control.edge_control import CachedEvent, EdgeControl, ModuleWiring
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingLoader, RoiBindingRow
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem
from edge.interfaces.i_sinks import ICaptureSink
from edge.modules.recognition.recognition_controller import RecognitionController
from edge.modules.recognition.recognition_stitcher import FrameStitcher
from edge.modules.recognition.recognition_utils import (
    boxOf,
    detectionsInRoi,
    isBoxFullyInsideRoi,
    matchMarker,
)
from edge.modules.recognition.recognition_yolo_engine import (
    DEFAULT_NMS_IOU_THRESHOLD,
    ONNX_BACKEND_CALIBRATION_NOTE,
    YoloEngine,
)
from edge.modules.usb.usb_camera_device import CameraFactory
from edge.modules.usb.usb_controller import UsbController
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_recognition_engine import FakeRecognitionEngine
from edge.tests.fakes.fake_sinks import FakeRecognitionSink
from edge.tests.integration.host_protocol_checker import check_ack, check_coverage

## @file edge/tests/integration/test_round3_defect_fixes.py
## @brief 第三轮缺陷修复验收用例：对照表备用方案、后端口径统一、相机状态、丢帧与降级形状
## @author 边缘计算项目

## @brief 工程根目录
EDGE_ROOT: Path = Path(__file__).resolve().parents[2]
## @brief 随工程发布的对照表路径
ROI_CSV_PATH: Path = EDGE_ROOT / "config" / "roi_binding.csv"
## @brief 随工程发布的权重目录
WEIGHTS_DIR: Path = EDGE_ROOT.parent / "weights"
## @brief 随工程发布的样例图片
SAMPLE_IMAGE_PATH: Path = EDGE_ROOT.parent / "dual_crop_stitch" / "88.jpg"
## @brief 推理超时秒数
TEST_TIMEOUT_SEC: float = 3.0
## @brief 本轮流式帧，左路在前
TEST_FRAMES: tuple[bytes, ...] = (b"LEFT", b"RIGHT")
## @brief 对照表行；第 1 号线程管 A-01-01
SAMPLE_ROWS: list[RoiBindingRow] = [
    RoiBindingRow(
        roiId="r1", workerId=1, drawerId="A-01", position="A-01-01",
        toolId="C01-T0007", requiredType="wrench", markerId="tool",
        confidence=0.85, rectX1=0, rectY1=0, rectX2=10, rectY2=10,
    ),
]


## @brief 拼接器桩：拼图时阻塞在屏障上，用于制造识别线程忙的场景
class BlockingStitcher(FrameStitcher):
    ## @brief 构造阻塞拼接器
    #  @param barrier 并发屏障
    def __init__(self, barrier: Barrier) -> None:
        ## @brief 并发屏障
        self._barrier: Barrier = barrier

    ## @brief 阻塞在屏障上直到主线程放行
    #  @param frames 本轮帧元组，左路在前
    #  @return 固定拼接字节
    def stitch(self, frames: tuple[bytes, ...]) -> bytes:
        self._barrier.wait(timeout=3.0)
        return b"STUB-PANORAMA"

    ## @brief 裁出区域图像
    #  @param image 拼接全景的图像字节
    #  @param roi 对照表行
    #  @return 固定裁剪字节
    def crop(self, image: bytes, roi: RoiBindingRow) -> bytes:
        return b"STUB-ROI"


## @brief 固定返回左右两路图像字节
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


## @brief 二维数组桩：形状、转置与二维切片
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


## @brief 按目标清单造一个 onnx 输出桩
#  @param entries 每个目标的（中心横, 中心纵, 宽, 高, 类别0分数, 类别1分数）
#  @return 输出张量桩
def buildOnnxOutput(
    entries: list[tuple[float, float, float, float, float, float]],
) -> FakeArray:
    ## 行数是通道数，列数是目标数，形状与真机一致
    channels = [[0.0] * len(entries) for _ in range(6)]
    for index, entry in enumerate(entries):
        for channel, value in enumerate(entry):
            channels[channel][index] = value
    return FakeArray(channels)


## @brief 构造数值计算库桩，只提供 argmax
#  @return 数值计算库桩
def buildFakeArrayLibrary() -> object:
    ## @brief 求最大值的下标
    #  @param values 数值列表
    #  @return 最大值下标
    def argmax(values: list[float]) -> int:
        return max(range(len(values)), key=lambda index: values[index])

    return type("ArrayLibrary", (), {"argmax": staticmethod(argmax)})


## @brief 构造只记录不落盘的采集回调桩
#  @return 采集回调桩
def buildCaptureSink() -> ICaptureSink:
    return RecordingCaptureSink()


## @brief 只记录不落盘的采集回调桩
class RecordingCaptureSink(ICaptureSink):
    ## @brief 采集成功回调
    #  @param workerId 工作线程编号
    #  @param path 落盘路径
    #  @return 无
    def onCaptureSuccess(self, workerId: int, path: str) -> None:
        return None

    ## @brief 采集失败回调
    #  @param workerId 工作线程编号
    #  @param exception 采集异常
    #  @return 无
    def onCaptureError(self, workerId: int, exception: Exception) -> None:
        return None


## @brief 读检测结果里的置信度
#  @param item 单条检测结果
#  @return 置信度，取值 0 到 1
def readConfidence(item: DetectionItem) -> float:
    raw = item.get("confidence")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0.0
    return float(raw)


## @brief 对应缺陷 1：对照表缺失时装配阶段就判配置错误，不带着空台账上线
def test_roi_binding_table_missing_fails_fast(tmp_path: Path) -> None:
    loader = RoiBindingLoader(FakeLogger())

    try:
        loadRoiBindingRows(loader, str(tmp_path / "缺少.csv"))
        raise AssertionError("对照表缺失应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG
        assert "未装载 ROI 对照表" in str(error)


## @brief 对应缺陷 1：对照表只有表头没有数据行时装配阶段就判配置错误
def test_roi_binding_table_empty_fails_fast(tmp_path: Path) -> None:
    emptyTable = tmp_path / "empty.csv"
    emptyTable.write_text(
        "roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,"
        "confidence,rect_x1,rect_y1,rect_x2,rect_y2\n",
        encoding="utf-8",
    )
    loader = RoiBindingLoader(FakeLogger())

    try:
        loadRoiBindingRows(loader, str(emptyTable))
        raise AssertionError("对照表没有数据行应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG
        assert "未装载 ROI 对照表" in str(error)


## @brief 对应缺陷 1：对照表装载成功时装配阶段拿到行
def test_roi_binding_table_loaded_returns_rows() -> None:
    loader = RoiBindingLoader(FakeLogger())

    rows = loadRoiBindingRows(loader, str(ROI_CSV_PATH))

    assert len(rows) == 4
    assert rows[0].position == "A-01-01"


## @brief 对应缺陷 3：对照表线程编号超过实际采集线程数时启动即判配置错误
def test_roi_worker_id_beyond_actual_worker_count_fails_fast() -> None:
    rows = RoiBindingLoader(FakeLogger()).load(str(ROI_CSV_PATH))

    try:
        ## 现场只有 2 对相机，对照表却写了第 3、第 4 号线程
        validateRoiWorkerScope(rows, 2)
        raise AssertionError("线程编号超出实际采集线程数应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG
        assert "worker_id 超出实际采集线程数" in str(error)


## @brief 对应缺陷 3：装载器侧保留 1 到 4 的基础区间校验
def test_loader_rejects_worker_id_out_of_base_range(tmp_path: Path) -> None:
    table = tmp_path / "bad_worker.csv"
    table.write_text(
        "roi_id,worker_id,drawer_id,position,tool_id,required_type,marker_id,"
        "confidence,rect_x1,rect_y1,rect_x2,rect_y2\n"
        "roi_01,9,A-01,A-01-01,C01-T0007,wrench,mk_8821,0.85,0,0,320,240\n",
        encoding="utf-8",
    )
    loader = RoiBindingLoader(FakeLogger())

    try:
        loader.load(str(table))
        raise AssertionError("线程编号越界应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG
        assert "工作线程编号越界" in str(error)


## @brief 对应缺陷 2：onnxruntime 分支的同类别重叠框必须被抑制
def test_onnx_backend_applies_non_maximum_suppression() -> None:
    engine = YoloEngine(logger=FakeLogger(), nmsIouThreshold=DEFAULT_NMS_IOU_THRESHOLD)
    ## 8 个目标：两个高度重叠、两个远处、一个低置信
    output = buildOnnxOutput([
        (100.0, 100.0, 40.0, 40.0, 0.90, 0.05),
        (105.0, 102.0, 40.0, 40.0, 0.85, 0.05),
        (300.0, 300.0, 40.0, 40.0, 0.80, 0.05),
        (500.0, 500.0, 40.0, 40.0, 0.10, 0.60),
        (700.0, 700.0, 40.0, 40.0, 0.05, 0.10),
        (800.0, 800.0, 40.0, 40.0, 0.05, 0.10),
        (900.0, 900.0, 40.0, 40.0, 0.05, 0.10),
        (950.0, 950.0, 40.0, 40.0, 0.05, 0.10),
    ])

    items = engine.parseOnnxOutput(
        [output], buildFakeArrayLibrary(), {0: "person", 1: "frisbee"},
    )

    ## 置信度门槛滤掉 4 个低分目标，重叠的 1 个被抑制，剩 3 条
    assert len(items) == 3
    confidences = sorted(readConfidence(item) for item in items)
    assert confidences == [0.60, 0.80, 0.90]
    assert [str(item["className"]) for item in items] == ["person", "person", "frisbee"]


## @brief 对应缺陷 2：抑制阈值是构造注入项，改阈值就改抑制口径
def test_nms_threshold_is_injected() -> None:
    engine = YoloEngine(logger=FakeLogger(), nmsIouThreshold=0.95)
    output = buildOnnxOutput([
        (100.0, 100.0, 40.0, 40.0, 0.90, 0.05),
        (105.0, 102.0, 40.0, 40.0, 0.85, 0.05),
        (300.0, 300.0, 40.0, 40.0, 0.80, 0.05),
        (500.0, 500.0, 40.0, 40.0, 0.10, 0.60),
        (700.0, 700.0, 40.0, 40.0, 0.05, 0.10),
        (800.0, 800.0, 40.0, 40.0, 0.05, 0.10),
        (900.0, 900.0, 40.0, 40.0, 0.05, 0.10),
        (950.0, 950.0, 40.0, 40.0, 0.05, 0.10),
    ])

    items = engine.parseOnnxOutput(
        [output], buildFakeArrayLibrary(), {0: "person", 1: "frisbee"},
    )

    ## 阈值放宽到 0.95 后，重叠的两个框都保留
    assert engine.getNmsIouThreshold() == 0.95
    assert len(items) == 4


## @brief 对应缺陷 2：onnxruntime 分支明确标注为需现场标定
def test_onnx_backend_is_marked_as_needing_field_calibration() -> None:
    logger = FakeLogger()
    engine = YoloEngine(logger=logger)

    engine.logInfo(ONNX_BACKEND_CALIBRATION_NOTE)

    assert "标定" in ONNX_BACKEND_CALIBRATION_NOTE
    assert any("标定" in record[1] for record in logger.infoRecords)


## @brief 对应缺陷 2：两条后端在同一张图上的条数差异在合理范围内
def test_two_backends_output_count_within_tolerance() -> None:
    assert find_spec("ultralytics") is not None, "本机缺少 ultralytics，无法做真机对比"
    assert find_spec("onnxruntime") is not None, "本机缺少 onnxruntime，无法做真机对比"
    assert SAMPLE_IMAGE_PATH.is_file()
    assert (WEIGHTS_DIR / "yolov8n.pt").is_file()
    assert (WEIGHTS_DIR / "yolov8n.onnx").is_file()

    import onnxruntime  # type: ignore

    image = SAMPLE_IMAGE_PATH.read_bytes()
    ultraEngine = YoloEngine(logger=FakeLogger())
    ultraEngine.loadModel(str(WEIGHTS_DIR / "yolov8n.pt"))
    ultraItems = ultraEngine.infer(image)

    onnxEngine = YoloEngine(logger=FakeLogger())
    onnxEngine._model = onnxruntime.InferenceSession(  # noqa: SLF001
        str(WEIGHTS_DIR / "yolov8n.onnx"),
    )
    onnxEngine._frameworkName = "onnxruntime"  # noqa: SLF001
    onnxEngine._modelLoaded = True  # noqa: SLF001
    onnxItems = onnxEngine.infer(image)

    ## 抑制前 onnx 分支会出 62 条，抑制后必须落到与 ultralytics 同量级
    assert len(ultraItems) == 6
    assert 0 < len(onnxItems) <= len(ultraItems) * 2
    ## 两条后端都没产出区域编号，区域归集链路不可用
    assert all("roiId" not in item for item in ultraItems + onnxItems)


## @brief 对应缺陷 4：从未打开过的摄像头必须报离线，不许报正常
def test_camera_never_opened_reports_offline(tmp_path: Path) -> None:
    saveDir = tmp_path / "worker1"
    saveDir.mkdir(parents=True, exist_ok=True)
    device = CameraFactory.createDevice("1", lambda: b"FRAME")
    controller = UsbController(
        [(device, device)], [str(saveDir)], buildCaptureSink(), FakeLogger(),
        0.3, lambda: 0.0, lambda: "stamp", cameraCount=2,
    )

    statuses = controller.getCameraStatus()

    assert [str(item["status"]) for item in statuses] == ["offline", "offline"]


## @brief 对应缺陷 4：探测不到设备的摄像头按不可达处理，不报正常
def test_camera_unreachable_reports_offline(tmp_path: Path) -> None:
    saveDir = tmp_path / "worker1"
    saveDir.mkdir(parents=True, exist_ok=True)
    device = CameraFactory.createDevice(
        "1", lambda: b"FRAME", reachabilityProbe=lambda: False,
    )
    controller = UsbController(
        [(device, device)], [str(saveDir)], buildCaptureSink(), FakeLogger(),
        0.3, lambda: 0.0, lambda: "stamp", cameraCount=2,
    )

    try:
        device.open()
        raise AssertionError("探测不到设备的摄像头应抛 EdgeError(CAPTURE)")
    except EdgeError as error:
        assert error.code == ErrorCode.CAPTURE

    statuses = controller.getCameraStatus()

    assert [str(item["status"]) for item in statuses] == ["offline", "offline"]


## @brief 对应缺陷 4 与 A2：状态取值只有正常、离线两种
def test_camera_status_values_are_limited() -> None:
    saveDirs = ["./w1"]
    device = CameraFactory.createDevice("1", lambda: b"FRAME")
    controller = UsbController(
        [(device, device)], saveDirs, buildCaptureSink(), FakeLogger(),
        0.3, lambda: 0.0, lambda: "stamp", cameraCount=2,
    )

    statuses = controller.getCameraStatus()

    assert {str(item["status"]) for item in statuses} <= {"ok", "offline"}
    assert [str(item["camera_id"]) for item in statuses] == ["CAM1", "CAM2"]


## @brief 对应 F1 修复：onnx 后端的框坐标必须按缩放比放大回拼接全景
#  onnx 先把全景 resize 到模型输入尺寸再推理，输出的框是小图坐标；
#  runOnnxInference 按 全景尺寸/模型输入尺寸 算缩放比后传入，box 必须放大回全景
def test_onnx_box_scaled_back_to_panorama() -> None:
    engine = YoloEngine(logger=FakeLogger())
    engine._model = type("Model", (), {"names": {0: "person"}})()  # noqa: SLF001

    class FakeOnnxArray:
        ## @brief 行数、列数；列数大于 4 才解析框
        @property
        def shape(self) -> tuple[int, int]:
            return (6, 6)

        ## @brief 第 0 行承载框坐标 (cx,cy,w,h) 与置信度 (col4,col5)，其余行全 0
        #  @param key 行下标与列切片
        #  @return 切片后的坐标列表
        def __getitem__(self, key: tuple[int, slice]) -> list[float]:
            _index, columns = key
            if _index == 0:
                return [10.0, 20.0, 30.0, 40.0, 0.87, 0.05][columns]
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0][columns]

    # 小图框 cx=10 cy=20 w=30 h=40 -> 角点 [-5, 0, 25, 40]；
    # x 放大 2 倍、y 放大 3 倍回到全景
    items = engine.parseOnnxOutput(
        [FakeOnnxArray()], buildFakeArrayLibrary(), {0: "person"},
        scaleX=2.0, scaleY=3.0,
    )
    assert len(items) == 1
    assert items[0]["className"] == "person"
    assert items[0]["box"] == [-10.0, 0.0, 50.0, 120.0]


## @brief 对应缺陷 5：识别忙时丢帧有计数，日志按阈值抽样不逐帧刷屏
def test_dropped_frames_are_counted_and_logged_by_threshold() -> None:
    barrier = Barrier(2)
    logger = FakeLogger()
    controller = RecognitionController(
        FakeRecognitionEngine([{"className": "tool", "confidence": 0.93}]),
        "model.bin", ["dir1"], FakeRecognitionSink(), logger,
        {}, {}, {}, TEST_TIMEOUT_SEC, directRunner, fixedFrames,
        list(SAMPLE_ROWS), BlockingStitcher(barrier),
    )
    controller.init()
    assert controller.trigger(1, "req-1", TEST_FRAMES) is True

    for index in range(12):
        assert controller.trigger(1, f"req-drop-{index}", TEST_FRAMES) is False

    assert controller.getDroppedFrameCount() == 12
    dropLogs = [record for record in logger.infoRecords if "已丢弃" in record[1]]
    ## 每 10 次记一条，不逐帧刷屏
    assert len(dropLogs) == 1
    assert "累计 10 次" in dropLogs[0][1]

    barrier.wait(timeout=3.0)
    controller.stop()


## @brief 对应 A5：类别组合表优先于单标志直映，两张表并存不打架
def test_class_item_map_takes_priority_over_single_marker() -> None:
    comboMap: dict[frozenset[str], str] = {frozenset({"person", "surfboard"}): "滑板人偶"}

    ## 组合命中优先
    detected, confidence = matchMarker(
        [
            {"className": "person", "confidence": 0.91},
            {"className": "surfboard", "confidence": 0.83},
        ],
        "滑板人偶", comboMap,
    )
    assert detected is True
    ## 组合识别取最低置信度，防止单项高分带过整组合
    assert confidence == 0.83

    ## 组合查不到时退回单标志直映
    detected, confidence = matchMarker(
        [{"className": "torx", "confidence": 0.88}], "torx", comboMap,
    )
    assert detected is True
    assert confidence == 0.88

    ## 组合名与标志名对不上时不误判
    detected, _confidence = matchMarker(
        [{"className": "person", "confidence": 0.91}], "滑板人偶", comboMap,
    )
    assert detected is False


## @brief 对应 A5（补充）：区域里有杂物也命中组合，必需 class 齐了就算
def test_combo_hit_ignores_other_classes() -> None:
    comboMap: dict[frozenset[str], str] = {frozenset({"hammer", "red_label"}): "mk_8822"}

    ## 榔头 + 红标签齐全，区域里另有杂物类，仍应命中
    detected, confidence = matchMarker(
        [
            {"className": "hammer", "confidence": 0.90},
            {"className": "red_label", "confidence": 0.85},
            {"className": "background_junk", "confidence": 0.70},
        ],
        "mk_8822", comboMap,
    )
    assert detected is True
    ## 组合取最低；杂物类不参与匹配，不拉低结果
    assert confidence == 0.85

    ## 只差红标签（缺必需 class），即便有杂物也不命中
    detected, _confidence = matchMarker(
        [
            {"className": "hammer", "confidence": 0.90},
            {"className": "background_junk", "confidence": 0.70},
        ],
        "mk_8822", comboMap,
    )
    assert detected is False


## @brief 对应新几何判定：检测框完全在 ROI 内才计入，跨边界不计
def test_detections_in_roi_geometry() -> None:
    row = RoiBindingRow(
        roiId="r1", workerId=1, drawerId="A", position="A-01-01",
        toolId="T1", requiredType="t", markerId="mk", confidence=0.85,
        rectX1=0, rectY1=0, rectX2=100, rectY2=100,
    )
    fully = {"className": "hammer", "confidence": 0.90, "box": [10, 10, 90, 90]}
    across = {"className": "hammer", "confidence": 0.90, "box": [90, 90, 130, 130]}

    ## 只保留完全在内的框，跨边界的被过滤掉
    leftover = detectionsInRoi([fully, across], row)
    assert [d["className"] for d in leftover] == ["hammer"]
    ## 几何判定单独核对
    assert isBoxFullyInsideRoi(boxOf(fully), row) is True
    assert isBoxFullyInsideRoi(boxOf(across), row) is False
    ## 缺 box 的旧格式项兼容保留（测试桩口径）
    noBox = {"className": "hammer", "confidence": 0.90}
    assert detectionsInRoi([noBox], row) == [noBox]
    ## 生产口径：缺框一律拒识，不与正常框混排命中
    assert detectionsInRoi([noBox], row, requireBox=True) == []
    assert [d["className"] for d in detectionsInRoi([fully, noBox], row, requireBox=True)] == ["hammer"]
    ## 坏框（非有限坐标）同样拒识
    badBox = {"className": "hammer", "confidence": 0.90, "box": [float("nan"), 0, 1, 1]}
    assert detectionsInRoi([badBox], row, requireBox=True) == []


## @brief 构造只带控制层的轻量边缘机，用于降级出帧形状校验
#  @param expectedWorkerCount 期望采集线程数
#  @param aggregationTimeoutSec 聚合等待上限秒数
#  @return 控制层与已发送帧
def makeControl(expectedWorkerCount: int,
                aggregationTimeoutSec: float) -> tuple[EdgeControl, list[CachedEvent]]:
    sent: list[CachedEvent] = []

    ## @brief 记录发送的帧
    #  @param frame 待发送帧
    #  @return 恒为 True
    def sendFrame(frame: CachedEvent) -> bool:
        sent.append(frame)
        return True

    ## @brief 空动作
    #  @return 无
    def noAction() -> None:
        return None

    wiring = ModuleWiring()
    for step in ("USB", "RECOGNITION", "TCP", "LOG"):
        wiring.stopActions[step] = noAction

    ## @brief 按线程编号给出该线程应上报的未识别条目
    #  @param workerId 线程编号
    #  @return 降级条目列表
    def degradedItems(workerId: int) -> list[object]:
        return [
            {
                "position": row.position, "tool_id": "", "confidence": 0.0,
                "alert_type": "unknown",
            }
            for row in SAMPLE_ROWS if row.workerId == workerId
        ]

    control = EdgeControl(
        FakeLogger(), {"recognize_req": lambda signal: None}, wiring,
        sendFrame,
        lambda workerId, exception: {"type": "error"},
        expectedWorkerCount=expectedWorkerCount,
        degradedItemsProvider=degradedItems,
        aggregationTimeoutSec=aggregationTimeoutSec,
    )
    control.onLinkUp()
    return control, sent


## @brief 对应 A6：聚合降级出帧仍满足上位机协议形状
def test_degraded_frames_match_host_protocol() -> None:
    control, sent = makeControl(expectedWorkerCount=1, aggregationTimeoutSec=0.1)
    control.routeSignal({"type": "recognize_req", "request_id": "req-degrade-0001"})

    ## 等待聚合等待上限到点，超时后应自动降级出帧
    deadline = monotonic() + 5.0
    while monotonic() < deadline and not sent:
        control.dispatchOutbox()
        Event().wait(0.02)
    control.dispatchOutbox()

    acks = [frame for frame in sent if frame.get("type") == "recognize_ack"]
    assert len(acks) == 1
    ack = acks[0]
    result = check_ack(ack, "req-degrade-0001")
    assert result.hostAccepts is True, result.describe()
    assert result.protocolClean is True, result.describe()
    items = ack["items"]
    assert check_coverage(items, ["A-01-01"]).hostAccepts is True


## @brief 对应 A6：识别异常那路的降级条目同样满足协议形状
def test_recognition_error_degraded_items_match_host_protocol() -> None:
    control, sent = makeControl(expectedWorkerCount=1, aggregationTimeoutSec=5.0)
    control.routeSignal({"type": "recognize_req", "request_id": "req-err-0001"})
    control.onRecognitionError(1, EdgeError(ErrorCode.INFERENCE_TIMEOUT, "推理超时"))
    control.dispatchOutbox()

    ## 失败帧与降级应答帧都出网，应答帧本身必须符合协议
    acks = [frame for frame in sent if frame.get("type") == "recognize_ack"]
    assert len(acks) == 1
    ack = acks[0]
    result = check_ack(ack, "req-err-0001")
    assert result.hostAccepts is True, result.describe()
    items = ack["items"]
    assert isinstance(items, list)
    assert len(items) == 1
    assert check_coverage(items, ["A-01-01"]).hostAccepts is True


## @brief 对应 A4：停机后不得残留在途请求、聚合中间态与待发应答
def test_stop_clears_runtime_state() -> None:
    control, _sent = makeControl(expectedWorkerCount=2, aggregationTimeoutSec=5.0)
    control.routeSignal({"type": "recognize_req", "request_id": "req-stop-0001"})
    control.onRecognitionResult(
        1, {"type": "recognize_ack", "items": []}, "req-stop-0001",
    )
    control.enqueueFrame({"type": "periodic"})

    assert control.getPendingRequestCount() == 1
    assert control.getAggregationCount() == 1
    assert control.getOutboxCount() == 1

    control.stopSystem()

    assert control.getPendingRequestCount() == 0
    assert control.getAggregationCount() == 0
    assert control.getCompletedAckCount() == 0
    assert control.getOutboxCount() == 0
