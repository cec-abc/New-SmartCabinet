"""c5 识别模块单元测试：单次加载 / 立即返回 / 3s 超时 / 归集查表 / 组帧 / 回调。"""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from threading import Barrier

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.modules.recognition import recognition_utils
from edge.modules.recognition.recognition_controller import RecognitionController
from edge.modules.recognition.recognition_utils import (
    ClassItemMap,
    FrameLoader,
    RoiBindMap,
    RoiConfig,
    TimeoutRunner,
    aggregateByRoi,
    buildAck,
    cropAndMerge,
    drawRoi,
    validateByTable,
)
from edge.modules.recognition.recognition_yolo_engine import YoloEngine
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_recognition_engine import FakeRecognitionEngine
from edge.tests.fakes.fake_sinks import FakeRecognitionSink

## @brief 注入的模型路径
TEST_MODEL_PATH: str = "model.bin"
## @brief 注入的推理超时秒数（验收项 c5-2）
TEST_TIMEOUT_SEC: float = 3.0
## @brief 注入的 ROI 配置
ROI_CONFIG: RoiConfig = {"r1": 1}
## @brief 注入的类别映射表
CLASS_ITEM_MAP: ClassItemMap = {"tool": "wrench"}
## @brief 注入的 ROI 绑定表
ROI_BIND_MAP: RoiBindMap = {"r1": "wrench"}
## @brief 注入的 4 个采集目录
SAVE_DIRS: list[str] = ["dir1", "dir2", "dir3", "dir4"]


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
#  @return 识别门面
def makeController(
    engine: IRecognitionEngine,
    sink: FakeRecognitionSink,
    logger: FakeLogger | None = None,
    frameLoader: FrameLoader | None = None,
    timeoutRunner: TimeoutRunner | None = None,
    inferTimeoutSec: float = TEST_TIMEOUT_SEC,
    saveDirs: list[str] | None = None,
) -> RecognitionController:
    return RecognitionController(
        engine, TEST_MODEL_PATH,
        saveDirs if saveDirs is not None else list(SAVE_DIRS),
        sink, logger, ROI_CONFIG, CLASS_ITEM_MAP, ROI_BIND_MAP,
        inferTimeoutSec,
        timeoutRunner if timeoutRunner is not None else directRunner,
        frameLoader if frameLoader is not None else fixedFrames,
    )


## @brief 构造带并发屏障的读图器，用于举证 trigger 立即返回
#  @param barrier 并发屏障
#  @return 左右图读取器
def makeBlockingLoader(barrier: Barrier) -> FrameLoader:
    ## @brief 阻塞在屏障上直到主线程放行
    #  @param saveDir 采集目录
    #  @param workerId 线程编号
    #  @return 左右图像字节对
    def blockingFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
        barrier.wait(timeout=3.0)
        return (b"LEFT", b"RIGHT")

    return blockingFrames


## @brief 对应验收项 c5-1：模型仅 loadModel 一次、trigger 立即返回、忙时拒绝、放行后回调
def test_c5_1_load_once_and_trigger_returns_immediately() -> None:
    barrier = Barrier(2)
    items: list[DetectionItem] = [{"roiId": "r1", "className": "tool"}]
    engine = FakeRecognitionEngine(items)
    sink = FakeRecognitionSink()
    controller = makeController(engine, sink, frameLoader=makeBlockingLoader(barrier))

    controller.init()
    controller.init()
    assert engine.loadedPaths == [TEST_MODEL_PATH]
    assert controller.getActiveWorkers() == {}

    started = time.monotonic()
    assert controller.trigger(1, "req-1") is True
    elapsed = time.monotonic() - started
    assert elapsed < 1.0, f"trigger 不应等待子线程，实测 {elapsed:.3f}s"
    workers = controller.getActiveWorkers()
    assert list(workers) == [1]
    assert workers[1].isRunning()
    assert sink.resultEvents == []
    assert controller.trigger(1, "req-2") is False

    barrier.wait(timeout=3.0)
    controller.stop()
    assert len(sink.resultEvents) == 1
    workerId, ack, requestId = sink.resultEvents[0]
    assert workerId == 1
    assert requestId == "req-1"
    assert ack["type"] == "recognize_ack"
    assert sink.errorEvents == []


## @brief 对应验收项 c5-1：未 init 与 workerId 越界均不得拉起线程
def test_c5_1_guard_before_init_and_invalid_worker_id() -> None:
    engine = FakeRecognitionEngine()
    sink = FakeRecognitionSink()
    controller = makeController(engine, sink)

    assert controller.trigger(1, "req") is False
    assert controller.getActiveWorkers() == {}
    assert engine.loadedPaths == []

    controller.init()
    assert controller.trigger(5, "req") is False
    assert controller.trigger(0, "req") is False
    assert controller.getActiveWorkers() == {}
    assert sink.errorEvents == []


## @brief 对应验收项 c5-1 / D-01：自检只留空接口，不启线程、不做 IO、不做能力降级
def test_c5_1_selfcheck_stub_d01() -> None:
    controller = makeController(FakeRecognitionEngine(), FakeRecognitionSink())
    controller.selfCheckRecognition()
    assert controller.getActiveWorkers() == {}
    assert not hasattr(controller, "on_capture_success")


## @brief 对应验收项 c5-1：YoloEngine 双检锁单例、loadModel 幂等、普通构造可测
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

    items: list[DetectionItem] = [{"roiId": "r1", "className": "tool"}]
    sink = FakeRecognitionSink()
    logger = FakeLogger()
    controller = makeController(
        FakeRecognitionEngine(items), sink, logger=logger,
        timeoutRunner=timingOutRunner,
    )
    controller.init()
    assert controller.trigger(1, "req-t") is True
    controller.stop()

    assert seen == [TEST_TIMEOUT_SEC]
    assert sink.resultEvents == []
    assert len(sink.errorEvents) == 1
    workerId, exception = sink.errorEvents[0]
    assert workerId == 1
    assert isinstance(exception, EdgeError)
    assert exception.code == ErrorCode.INFERENCE_TIMEOUT
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

    items: list[DetectionItem] = [{"roiId": "r1", "className": "tool"}]
    sink = FakeRecognitionSink()
    controller = makeController(
        FakeRecognitionEngine(items), sink,
        timeoutRunner=recordingRunner, inferTimeoutSec=0.25,
    )
    controller.init()
    assert controller.trigger(1, "req") is True
    controller.stop()

    assert seen == [0.25]
    assert len(sink.resultEvents) == 1
    assert sink.errorEvents == []


## @brief 对应验收项 c5-3：空间归集 + 查表校验 + 组 ack；未命中记 error 但不中断
def test_c5_3_aggregate_lookup_and_build_ack() -> None:
    items: list[DetectionItem] = [
        {"roiId": "r1", "className": "tool"},
        {"roiId": "r1", "className": "ghost"},
        {"roiId": "r2", "className": "tool"},
    ]
    sink = FakeRecognitionSink()
    logger = FakeLogger()
    controller = makeController(FakeRecognitionEngine(items), sink, logger=logger)
    controller.init()
    assert controller.trigger(2, "req-3") is True
    controller.stop()

    assert len(sink.resultEvents) == 1
    workerId, ack, requestId = sink.resultEvents[0]
    assert workerId == 2
    assert requestId == "req-3"
    assert ack["type"] == "recognize_ack"
    assert ack["requestId"] == "req-3"
    assert ack["workerId"] == 2
    ackItems = ack["items"]
    assert isinstance(ackItems, list)
    ## 错放与否不判定：r2 未绑定仍原样带出 item=wrench / boundItem=unknown，待用户拍板
    assert ackItems == [
        {"roiId": "r1", "className": "tool", "item": "wrench", "boundItem": "wrench"},
        {"roiId": "r1", "className": "ghost", "item": "unknown", "boundItem": "wrench"},
        {"roiId": "r2", "className": "tool", "item": "wrench", "boundItem": "unknown"},
    ]
    assert any("CONFIG" in record[1] for record in logger.errorRecords)
    assert sink.errorEvents == []


## @brief 对应验收项 c5-3：纯函数行为确定、相同输入产生相同输出
def test_c5_3_pure_functions_behavior() -> None:
    merged = cropAndMerge(b"L", b"R")
    assert merged == b"L||R"
    assert drawRoi(merged, {"r1": 1}) == b"L||R#ROI#r1=1"

    items: list[DetectionItem] = [
        {"roiId": "r1", "className": "tool"},
        {"roiId": "r1", "className": "ghost"},
        {"roiId": "r2", "className": "tool"},
    ]
    groups = aggregateByRoi(items)
    assert sorted(groups) == ["r1", "r2"]
    assert len(groups["r1"]) == 2
    ackItems, misses = validateByTable(groups, CLASS_ITEM_MAP, ROI_BIND_MAP)
    assert misses == ["r1/ghost"]
    assert len(ackItems) == 3
    assert buildAck(3, "req-9", ackItems) == {
        "type": "recognize_ack", "requestId": "req-9", "workerId": 3,
        "items": ackItems,
    }


## @brief 对应验收项 c5-4：成功 / 失败回调互不影响，内置异常跨边界转 EdgeError
def test_c5_4_callbacks_isolated_and_exception_upcast() -> None:
    ## @brief 第 2 个 worker 读图抛内置异常，其余正常
    #  @param saveDir 采集目录
    #  @param workerId 线程编号
    #  @return 左右图像字节对
    def selectiveFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
        if workerId == 2:
            raise OSError("simulated read failure")
        return (b"LEFT", b"RIGHT")

    items: list[DetectionItem] = [{"roiId": "r1", "className": "tool"}]
    sink = FakeRecognitionSink()
    controller = makeController(
        FakeRecognitionEngine(items), sink, frameLoader=selectiveFrames,
    )
    controller.init()
    assert controller.trigger(1, "r1") is True
    assert controller.trigger(2, "r2") is True
    controller.stop()

    assert [item[0] for item in sink.resultEvents] == [1]
    assert len(sink.errorEvents) == 1
    workerId, exception = sink.errorEvents[0]
    assert workerId == 2
    assert isinstance(exception, EdgeError)
    assert exception.code == ErrorCode.CAPTURE


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
        "cropAndMerge", "drawRoi", "aggregateByRoi", "validateByTable", "buildAck",
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
