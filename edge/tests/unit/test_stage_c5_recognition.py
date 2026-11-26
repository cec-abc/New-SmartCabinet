"""c5 识别模块单元测试：单次加载 / 立即返回 / 3s 超时 / 归集查表 / 组帧 / 回调。"""
## @file edge/tests/unit/test_stage_c5_recognition.py
## @brief c5 识别模块单元测试：单次加载 / 立即返回 / 3s 超时 / 归集查表 / 组帧 / 回调
## @author 袁燕
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from threading import Barrier

from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingRow
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.modules.recognition import recognition_utils
from edge.modules.recognition.recognition_controller import RecognitionController
from edge.modules.recognition.recognition_stitcher import FrameStitcher
from edge.modules.recognition.recognition_utils import (
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
    buildAck,
    cropAndMerge,
    drawRoi,
    roiIdOf,
)
from edge.modules.recognition.recognition_yolo_engine import YoloEngine
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_recognition_engine import FakeRecognitionEngine
from edge.tests.fakes.fake_sinks import FakeRecognitionSink

## @brief 注入的模型路径
TEST_MODEL_PATH: str = "model.bin"
## @brief 注入的推理超时秒数（验收项 c5-2）
TEST_TIMEOUT_SEC: float = 3.0
## @brief 注入的 ROI 配置，区域编号到货位号
ROI_CONFIG: RoiConfig = {"r1": "A-01-01", "r2": "A-01-02"}
## @brief 注入的类别映射表
CLASS_ITEM_MAP: ClassItemMap = {"tool": "wrench"}
## @brief 注入的 ROI 绑定表
ROI_BIND_MAP: RoiBindMap = {"r1": "wrench", "r2": "wrench"}
## @brief 注入的 4 个采集目录
SAVE_DIRS: list[str] = ["dir1", "dir2", "dir3", "dir4"]
## @brief 注入的对照表行；第 1 号线程管 A-01-01，第 2 号线程管 A-01-02
ROI_ROWS: list[RoiBindingRow] = [
    RoiBindingRow(
        roiId="r1", workerId=1, drawerId="A-01", position="A-01-01",
        toolId="C01-T0007", requiredType="wrench", markerId="tool",
        confidence=0.85, rectX1=0, rectY1=0, rectX2=10, rectY2=10,
    ),
    RoiBindingRow(
        roiId="r2", workerId=2, drawerId="A-01", position="A-01-02",
        toolId="C01-T0008", requiredType="hammer", markerId="tool",
        confidence=0.85, rectX1=10, rectY1=0, rectX2=20, rectY2=10,
    ),
]
## @brief 本轮流式帧，左路在前
TEST_FRAMES: tuple[bytes, ...] = (b"LEFT", b"RIGHT")


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


## @brief 拼接器桩：拼图时阻塞在屏障上，用于举证 trigger 立即返回
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


## @brief 拼接器桩：按帧内容决定拼图成败，用于举证一路失败不影响另一路
class SelectiveFailingStitcher(FrameStitcher):
    ## @brief 拼接本轮两路帧；左路是坏帧时抛内置异常
    #  @param frames 本轮帧元组，左路在前
    #  @return 固定拼接字节
    def stitch(self, frames: tuple[bytes, ...]) -> bytes:
        if frames and frames[0] == b"BAD":
            raise OSError("simulated stitch failure")
        return b"STUB-PANORAMA"

    ## @brief 裁出区域图像
    #  @param image 拼接全景的图像字节
    #  @param roi 对照表行
    #  @return 固定裁剪字节
    def crop(self, image: bytes, roi: RoiBindingRow) -> bytes:
        return b"STUB-ROI"


## @brief 直接执行推理，不施加真实等待
#  @param task 推理闭包
#  @param timeoutSec 注入的超时秒数
#  @return 检测结果列表
def directRunner(task: Callable[[], list[DetectionItem]],
                 timeoutSec: float) -> list[DetectionItem]:
    return task()


## @brief 固定返回左右两路图像字节
#  @param saveDir 采集目录
#  @param workerId 线程编号
#  @return 左右图像字节对
def fixedFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
    return (b"LEFT", b"RIGHT")


## @brief 构造完备注入的识别门面
#  @param engine 推理引擎
#  @param sink 识别回调
#  @param logger 可选日志器
#  @param frameLoader 左右图读取器
#  @param timeoutRunner 推理超时执行器
#  @param inferTimeoutSec 注入的超时秒数
#  @param saveDirs 采集目录列表
#  @param roiBindingRows ROI 对照表行；传 None 表示降级为按 ROI 配置识别的备用链路
#  @param stitcher 拼接裁剪器
#  @return 识别门面
def makeController(
    engine: IRecognitionEngine,
    sink: FakeRecognitionSink,
    logger: FakeLogger | None = None,
    frameLoader: FrameLoader | None = None,
    timeoutRunner: TimeoutRunner | None = None,
    inferTimeoutSec: float = TEST_TIMEOUT_SEC,
    saveDirs: list[str] | None = None,
    roiBindingRows: list[RoiBindingRow] | None = None,
    stitcher: FrameStitcher | None = None,
) -> RecognitionController:
    return RecognitionController(
        engine, TEST_MODEL_PATH,
        saveDirs if saveDirs is not None else list(SAVE_DIRS),
        sink, logger, ROI_CONFIG, CLASS_ITEM_MAP, ROI_BIND_MAP,
        inferTimeoutSec,
        timeoutRunner if timeoutRunner is not None else directRunner,
        frameLoader if frameLoader is not None else fixedFrames,
        ROI_ROWS if roiBindingRows is None else roiBindingRows,
        stitcher if stitcher is not None else StubStitcher(),
    )


## @brief 检测结果缺区域编号时按 None 显式暴露，不静默塌缩
def test_c5_3_missing_roi_id_is_not_swallowed() -> None:
    assert roiIdOf({"className": "tool", "confidence": 0.9}) is None
    assert roiIdOf({"roiId": "r1", "className": "tool"}) == "r1"


## @brief 对应缺陷 1：按 ROI 配置识别的备用链路不可用，明确报配置错误且不产出误导条目
def test_c5_3_config_fallback_path_is_unavailable() -> None:
    items: list[DetectionItem] = [{"className": "tool", "confidence": 0.93}]
    sink = FakeRecognitionSink()
    logger = FakeLogger()
    ## 对照表行传空表示降级为按 ROI 配置识别的备用链路
    controller = RecognitionController(
        FakeRecognitionEngine(items), TEST_MODEL_PATH, list(SAVE_DIRS),
        sink, logger, ROI_CONFIG, CLASS_ITEM_MAP, ROI_BIND_MAP,
        TEST_TIMEOUT_SEC, directRunner, fixedFrames,
        None, StubStitcher(),
    )
    controller.init()
    assert controller.trigger(1, "req-fallback", TEST_FRAMES) is True
    controller.stop()

    assert sink.resultEvents == []
    assert len(sink.errorEvents) == 1
    workerId, exception = sink.errorEvents[0]
    assert workerId == 1
    assert isinstance(exception, EdgeError)
    assert exception.code == ErrorCode.CONFIG
    assert any("兜底链路不可用" in record[1] for record in logger.infoRecords)


## @brief 对应验收项 c5-1：模型仅 loadModel 一次、trigger 立即返回、忙时拒绝、放行后回调
def test_c5_1_load_once_and_trigger_returns_immediately() -> None:
    barrier = Barrier(2)
    items: list[DetectionItem] = [{"className": "tool", "confidence": 0.93}]
    engine = FakeRecognitionEngine(items)
    sink = FakeRecognitionSink()
    controller = makeController(engine, sink, stitcher=BlockingStitcher(barrier))

    controller.init()
    controller.init()
    assert engine.loadedPaths == [TEST_MODEL_PATH]
    assert controller.getActiveWorkers() == {}

    started = time.monotonic()
    assert controller.trigger(1, "req-1", TEST_FRAMES) is True
    elapsed = time.monotonic() - started
    assert elapsed < 1.0, f"trigger 不应等待子线程，实测 {elapsed:.3f}s"
    workers = controller.getActiveWorkers()
    assert list(workers) == [1]
    assert workers[1].isRunning()
    assert sink.resultEvents == []
    assert controller.trigger(1, "req-2", TEST_FRAMES) is False

    barrier.wait(timeout=3.0)
    controller.stop()
    assert len(sink.resultEvents) == 1
    workerId, ack, requestId = sink.resultEvents[0]
    assert workerId == 1
    assert requestId == "req-1"
    assert ack["type"] == "recognize_ack"
    assert ack["request_id"] == "req-1"
    assert sink.errorEvents == []


## @brief 对应验收项 c5-1：未 init 与 workerId 越界均不得拉起线程
def test_c5_1_guard_before_init_and_invalid_worker_id() -> None:
    engine = FakeRecognitionEngine()
    sink = FakeRecognitionSink()
    controller = makeController(engine, sink)

    assert controller.trigger(1, "req", TEST_FRAMES) is False
    assert controller.getActiveWorkers() == {}
    assert engine.loadedPaths == []

    controller.init()
    assert controller.trigger(5, "req", TEST_FRAMES) is False
    assert controller.trigger(0, "req", TEST_FRAMES) is False
    assert controller.getActiveWorkers() == {}
    assert sink.errorEvents == []


## @brief 对应验收项 c5-1 / D-01：自检只留空接口，不启线程、不做 IO、不做能力降级
def test_c5_1_selfcheck_stub_d01() -> None:
    controller = makeController(FakeRecognitionEngine(), FakeRecognitionSink())
    controller.selfCheckRecognition()
    assert controller.getActiveWorkers() == {}
    assert not hasattr(controller, "on_capture_success")


## @brief 对应验收项 c5-1：YoloEngine 双检锁单例、loadModel 重复调用结果一致、普通构造可测
def test_c5_1_yolo_engine_instance_and_single_load() -> None:
    assert YoloEngine.instance() is YoloEngine.instance()

    plain = YoloEngine()
    plain.loadModel("m1")
    plain.loadModel("m2")
    assert plain.loadedPaths == ["m1"]
    assert plain.infer(b"img") == []

    fresh = YoloEngine()
    try:
        fresh.infer(b"img")
        raise AssertionError("未加载模型应抛 EdgeError(CONFIG)")
    except EdgeError as error:
        assert error.code == ErrorCode.CONFIG


## @brief 对应验收项 c5-2：3s 超时构造注入，TimeoutError 转 EdgeError(INFERENCE_TIMEOUT)
def test_c5_2_timeout_injected_and_mapped() -> None:
    seen: list[float] = []

    ## @brief 模拟推理超时，记录注入的超时秒数
    #  @param task 推理闭包
    #  @param timeoutSec 注入的超时秒数
    #  @return 不返回，恒抛 TimeoutError
    def timingOutRunner(task: Callable[[], list[DetectionItem]],
                        timeoutSec: float) -> list[DetectionItem]:
        seen.append(timeoutSec)
        raise TimeoutError("simulated inference timeout")

    items: list[DetectionItem] = [{"className": "tool", "confidence": 0.93}]
    sink = FakeRecognitionSink()
    logger = FakeLogger()
    controller = makeController(
        FakeRecognitionEngine(items), sink, logger=logger,
        timeoutRunner=timingOutRunner,
    )
    controller.init()
    assert controller.trigger(1, "req-t", TEST_FRAMES) is True
    controller.stop()

    assert seen == [TEST_TIMEOUT_SEC]
    ## 超时按行降级：该货位判未识别，应答照常给出，不整轮失败
    assert len(sink.resultEvents) == 1
    assert sink.errorEvents == []
    ack = sink.resultEvents[0][1]
    assert ack["items"] == [
        {"position": "A-01-01", "tool_id": "", "confidence": 0.0,
         "alert_type": "unknown"},
    ]
    assert any("INFERENCE_TIMEOUT" in record[1] for record in logger.errorRecords)


## @brief 对应验收项 c5-2：超时秒数由构造注入，非硬编码，不同值透传到执行器
def test_c5_2_timeout_sec_is_configurable() -> None:
    seen: list[float] = []

    ## @brief 记录注入的超时秒数并正常执行推理
    #  @param task 推理闭包
    #  @param timeoutSec 注入的超时秒数
    #  @return 检测结果列表
    def recordingRunner(task: Callable[[], list[DetectionItem]],
                        timeoutSec: float) -> list[DetectionItem]:
        seen.append(timeoutSec)
        return task()

    items: list[DetectionItem] = [{"className": "tool", "confidence": 0.93}]
    sink = FakeRecognitionSink()
    controller = makeController(
        FakeRecognitionEngine(items), sink,
        timeoutRunner=recordingRunner, inferTimeoutSec=0.25,
    )
    controller.init()
    assert controller.trigger(1, "req", TEST_FRAMES) is True
    controller.stop()

    assert seen == [0.25]
    assert len(sink.resultEvents) == 1
    assert sink.errorEvents == []


## @brief 对应验收项 c5-3：对照表链路每个对照行出一条协议条目，标志命中才算数
def test_c5_3_aggregate_lookup_and_build_ack() -> None:
    items: list[DetectionItem] = [{"className": "tool", "confidence": 0.93}]
    sink = FakeRecognitionSink()
    logger = FakeLogger()
    controller = makeController(FakeRecognitionEngine(items), sink, logger=logger)
    controller.init()
    assert controller.trigger(2, "req-3", TEST_FRAMES) is True
    controller.stop()

    assert len(sink.resultEvents) == 1
    workerId, ack, requestId = sink.resultEvents[0]
    assert workerId == 2
    assert requestId == "req-3"
    assert ack["type"] == "recognize_ack"
    assert ack["request_id"] == "req-3"
    assert set(ack.keys()) == {"type", "request_id", "items"}
    ackItems = ack["items"]
    assert isinstance(ackItems, list)
    ## 条目恰好四个键：货位号、工具编号、置信度、告警类型
    assert ackItems == [
        {"position": "A-01-02", "tool_id": "C01-T0008", "confidence": 0.93,
         "alert_type": "none"},
    ]
    assert sink.errorEvents == []


## @brief 对应验收项 c5-3：纯函数行为确定、相同输入产生相同输出
def test_c5_3_pure_functions_behavior() -> None:
    merged = cropAndMerge(b"L", b"R")
    assert merged == b"L||R"
    assert drawRoi(merged, {"r1": 1}) == b"L||R#ROI#r1=1"

    ackItems = [
        {"position": "A-01-01", "tool": "扳手", "confidence": 0.93, "alert_type": "none"},
    ]
    assert buildAck("req-9", ackItems) == {
        "type": "recognize_ack", "request_id": "req-9",
        "items": ackItems,
    }


## @brief 对应验收项 c5-4：成功 / 失败回调互不影响，内置异常跨边界转 EdgeError
def test_c5_4_callbacks_isolated_and_exception_upcast() -> None:
    items: list[DetectionItem] = [{"className": "tool", "confidence": 0.93}]
    sink = FakeRecognitionSink()
    controller = makeController(
        FakeRecognitionEngine(items), sink, stitcher=SelectiveFailingStitcher(),
    )
    controller.init()
    ## 第 2 号线程的拼接抛内置异常，第 1 号线程正常
    assert controller.trigger(1, "r1", TEST_FRAMES) is True
    assert controller.trigger(2, "r2", (b"BAD", b"RIGHT")) is True
    controller.stop()

    assert [item[0] for item in sink.resultEvents] == [1]
    assert len(sink.errorEvents) == 1
    workerId, exception = sink.errorEvents[0]
    assert workerId == 2
    assert isinstance(exception, EdgeError)
    ## 识别层兜底异常统一归为推理失败，而非相机采集失败（CAPTURE 仅留给采集层）
    assert exception.code == ErrorCode.INFERENCE_TIMEOUT


## @brief 对应验收项 c5-4：纯函数只在 utils 定义，且全模块无跨模块反向 import
def test_c5_4_pure_functions_only_in_utils_and_no_cross_module_import() -> None:
    packageDir = Path(recognition_utils.__file__).parent
    fileNames = (
        "recognition_controller.py", "recognition_worker.py",
        "recognition_utils.py", "recognition_yolo_engine.py",
    )
    sources = {
        name: (packageDir / name).read_text(encoding="utf-8") for name in fileNames
    }
    for source in sources.values():
        assert "edge.modules.usb" not in source
        assert "edge.modules.tcp" not in source
        assert "edge.control" not in source
        assert "sys.platform" not in source

    utilsSource = sources["recognition_utils.py"]
    for pureName in (
        "cropAndMerge", "drawRoi", "buildAck",
    ):
        assert f"def {pureName}" in utilsSource
        assert f"def {pureName}" not in sources["recognition_worker.py"]
        assert f"def {pureName}" not in sources["recognition_controller.py"]


## @brief 对应验收项 c5-4：FakeEngine 只读复用且与接口一致；图上 snake_case 不作 API
def test_c5_4_fake_engine_contract_and_camel_case_sink() -> None:
    items: list[DetectionItem] = [{"roiId": "r1", "className": "tool"}]
    fake = FakeRecognitionEngine(items)
    engine: IRecognitionEngine = fake
    engine.loadModel(TEST_MODEL_PATH)
    assert fake.loadedPaths == [TEST_MODEL_PATH]
    assert engine.infer(b"img") == items

    sink = FakeRecognitionSink()
    assert not hasattr(sink, "on_recognition_result")
    assert hasattr(sink, "onRecognitionResult")
    assert not hasattr(sink, "on_recognition_error")
    assert hasattr(sink, "onRecognitionError")
