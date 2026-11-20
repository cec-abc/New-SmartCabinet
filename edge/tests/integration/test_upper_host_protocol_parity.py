"""上位机协议一致性用例：用真实上位机样例帧做基线，校验器判定必须与上位机一致。

样例来源（上位机工程只读引用，不做任何修改）：
- tools/EdgeSimulator/EdgeSimulator.cpp:316-401  内置场景的真实 items 构造（合法帧 7 条）
- tools/EdgeSimulator/EdgeSimulator.cpp:178-296  结构错场景（非法帧）
- tools/EdgeSimulator/接口测试方案.txt:112-159    TC-24 系列 17 条结构校验
- tools/EdgeSimulator/接口测试方案.txt:176-178    TC-23E 协议外字段容错
- src/comm/EdgeService.cpp:55-111                 上位机 parseItems 的五条校验规则
- src/comm/EdgeService.cpp:118-132                上位机 parsePeriodic
- src/services/ToolService.cpp:115-218            上位机业务层比对口径

期望错误文案与上位机真实日志逐字一致，依据上位机自带测试二进制
build/tests/Debug/test_edge.exe 的实跑输出（structure_badFramesRejected 用例）。
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from threading import Event
from time import monotonic
from typing import cast

from edge.app_init import buildPeriodicFrame
from edge.infra.config_manager import IniConfigManager
from edge.infra.roi_binding_loader import RoiBindingRow
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem
from edge.interfaces.i_sinks import AckFrame
from edge.interfaces.i_socket import ISocket
from edge.modules.recognition.recognition_stitcher import FrameStitcher
from edge.modules.recognition.recognition_worker import RecognitionWorker
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.tcp.tcp_heart_thread import TcpHeartThread
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_recognition_engine import FakeRecognitionEngine
from edge.tests.integration.host_protocol_checker import (
    ProtocolFrame,
    ProtocolItem,
    check_ack,
    check_coverage,
    check_items,
    check_periodic,
    judgeInbound,
    judgeOutbound,
)

## @file edge/tests/integration/test_upper_host_protocol_parity.py
## @brief 上位机协议一致性用例：真实样例帧基线 + 边缘机线上帧合规扫描
## @author 边缘计算项目

## @brief 边缘机源码根目录
EDGE_ROOT: Path = Path(__file__).resolve().parents[2]
## @brief 需要扫描的边缘机源码目录（相对 edge/），对应任务的"ack 构造路径"范围
SCAN_DIRECTORIES: tuple[str, ...] = ("modules/recognition", "control")
## @brief 产出 items[] 的唯一源码文件
ACK_ITEM_SOURCE: Path = Path("modules/recognition/recognition_utils.py")
## @brief 协议禁止上线的历史字段：精确匹配带引号的键名字面量，不误报 className 等标识符
REMOVED_FIELD_PATTERN: re.Pattern[str] = re.compile(
    r"""["'](present|alert_level|class_id|tool_name)["']""",
)
## @brief 边缘内部字段：只允许做内部变量名，不得进入线上 items[]
INTERNAL_ITEM_FIELD_PATTERN: re.Pattern[str] = re.compile(
    r"""["'](roiId|className|item|boundItem)["']""",
)
## @brief 顶层帧里的边缘内部字段
INTERNAL_FRAME_FIELD_PATTERN: re.Pattern[str] = re.compile(
    r"""["'](workerId|requestId)["']""",
)
## @brief 样例帧统一使用的请求编号
SAMPLE_REQUEST_ID: str = "req-sim-0001"
## @brief 识别线程用的采集目录（不落盘，只作占位）
SAMPLE_SAVE_DIR: str = "./capture/w1"
## @brief 识别线程用的 ROI 配置
SAMPLE_ROI_CONFIG: dict[str, object] = {"roi1": "A-01-05"}
## @brief 识别线程用的类别映射表
SAMPLE_CLASS_ITEM_MAP: dict[str, str] = {"torx": "C01-T0007"}
## @brief 识别线程用的 ROI 绑定表
SAMPLE_ROI_BIND_MAP: dict[str, str] = {"roi1": "C01-T0007"}
## @brief 识别线程用的对照表行；生产链路按对照表逐行出条目
SAMPLE_ROI_ROWS: list[RoiBindingRow] = [
    RoiBindingRow(
        roiId="roi1", workerId=1, drawerId="A-01", position="A-01-05",
        toolId="C01-T0007", requiredType="wrench", markerId="torx",
        confidence=0.85, rectX1=0, rectY1=0, rectX2=10, rectY2=10,
    ),
]
## @brief 识别线程的超时秒数
SAMPLE_INFER_TIMEOUT_SEC: float = 3.0
## @brief 正式配置文件路径
CONFIG_PATH: Path = Path(__file__).resolve().parents[2] / "config" / "config.ini"
## @brief 周期帧节拍用例允许的间隔下限秒（生产值 3 秒，放宽调度抖动）
CADENCE_LOWER_SEC: float = 2.7
## @brief 周期帧节拍用例允许的间隔上限秒
CADENCE_UPPER_SEC: float = 3.9
## @brief 周期帧节拍用例等待两帧的最长秒数
CADENCE_WAIT_SEC: float = 9.0
## @brief 联调单帧字节上限，与上位机一致
MAX_FRAME_SIZE: int = 1024 * 1024


## @brief 记录出网帧与发送时刻的套接字 Fake
class FrameRecorderSocket(ISocket):
    ## @brief 构造记录器
    #  @return 无
    def __init__(self) -> None:
        ## @brief 已发出的原始帧字节
        self.sentFrames: list[bytes] = []
        ## @brief 每次发送的单调时刻
        self.sentTimes: list[float] = []

    ## @brief 建立连接；节拍用例不需要真实连接
    #  @return 无
    def connect(self) -> None:
        return None

    ## @brief 阻塞接收；节拍用例不需要接收
    #  @return 空字节
    def recv(self) -> bytes:
        return b""

    ## @brief 发送并记录
    #  @param data 待发送字节
    #  @return 恒为 True
    def send(self, data: bytes) -> bool:
        self.sentFrames.append(data)
        self.sentTimes.append(monotonic())
        return True

    ## @brief 关闭连接
    #  @return 无
    def close(self) -> None:
        return None


## @brief 构造一个协议形状的识别项
#  @param position 货位号
#  @param toolId 工具编号，空串表示该货位无工具
#  @param confidence 置信度
#  @param alertType 告警类型；None 表示不带 alert_type 字段
#  @return 识别项
def makeItem(position: str, toolId: str, confidence: float,
             alertType: str | None = "none") -> ProtocolItem:
    item: ProtocolItem = {
        "position": position,
        "tool_id": toolId,
        "confidence": confidence,
    }
    if alertType is not None:
        item["alert_type"] = alertType
    return item


## @brief 构造一个 recognize_ack 帧
#  @param items 识别清单
#  @param requestId 请求编号
#  @return 应答帧
def makeAck(items: list[object], requestId: str = SAMPLE_REQUEST_ID) -> ProtocolFrame:
    return {
        "type": "recognize_ack",
        "request_id": requestId,
        "items": items,
    }


## @brief 读盘式左右图读取器，返回固定字节
#  @param saveDir 采集目录
#  @param workerId 线程编号
#  @return 左右图像字节对
def fixedFrames(saveDir: str, workerId: int) -> tuple[FrameImage, FrameImage]:
    return (b"LEFT", b"RIGHT")


## @brief 直接执行推理，不施加超时
#  @param task 推理闭包
#  @param timeoutSec 超时秒数
#  @return 检测结果列表
def directRunner(task: Callable[[], list[DetectionItem]],
                timeoutSec: float) -> list[DetectionItem]:
    return task()


## @brief 拼接器桩：拼图与裁剪都返回固定字节，不依赖图像处理库
class SampleStitcher(FrameStitcher):
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


## @brief 跑一次真实识别线程，捕获它产出的应答帧
#  @param detections 推理引擎返回的检测结果
#  @return 生产代码实际组出的应答帧
def runProductionAck(detections: list[DetectionItem]) -> ProtocolFrame:
    captured: list[ProtocolFrame] = []

    ## @brief 成功回调：记录生产代码产出的应答帧
    #  @param workerId 线程编号
    #  @param ack 应答帧
    #  @param requestId 请求编号
    #  @return 无
    def onResult(workerId: int, ack: AckFrame, requestId: str) -> None:
        captured.append(cast(ProtocolFrame, dict(ack)))

    ## @brief 失败回调：识别线程失败直接让用例失败
    #  @param workerId 线程编号
    #  @param exception 业务异常
    #  @return 无
    def onError(workerId: int, exception: Exception) -> None:
        raise AssertionError(f"识别线程失败: {exception}")

    worker = RecognitionWorker(
        1, SAMPLE_REQUEST_ID, SAMPLE_SAVE_DIR,
        FakeRecognitionEngine(detections), FakeLogger(),
        onResult, onError,
        SAMPLE_ROI_CONFIG, SAMPLE_CLASS_ITEM_MAP, SAMPLE_ROI_BIND_MAP,
        SAMPLE_INFER_TIMEOUT_SEC, directRunner, fixedFrames,
        SAMPLE_ROI_ROWS, SampleStitcher(),
    )
    ## 直接执行线程主循环：与线程启动后执行的代码路径完全相同，只是改为同步调用
    worker.runLoop()
    assert len(captured) == 1
    return captured[0]


## @brief 扫描源码目录，返回命中的键名字面量位置
#  @param relativeDirs 相对 edge/ 的源码目录
#  @param pattern 匹配模式
#  @return 命中描述列表；每条形如 "相对路径:行号 键名"
def scanSourceLiterals(relativeDirs: tuple[str, ...],
                        pattern: re.Pattern[str]) -> list[str]:
    findings: list[str] = []
    for relativeDir in relativeDirs:
        for path in sorted((EDGE_ROOT / relativeDir).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                relative = path.relative_to(EDGE_ROOT).as_posix()
                findings.append(f"{relative}:{line} 键名 {match.group(1)}")
    return findings


## @brief 对应验收项 3：上位机内置合法场景帧，校验器必须全部判通过
def testHostAcceptsRealSimulatorLegalScenes() -> None:
    legalScenes: list[tuple[str, list[object]]] = [
        ("正常清单（2条样例）", [
            makeItem("A-01-05", "C01-T0007", 0.93),
            makeItem("A-02-01", "C01-T0012", 0.88),
        ]),
        ("有借有还（3.3-①）", [
            makeItem("A-01-05", "", 0.91),
            makeItem("A-01-06", "C01-T0012", 0.91),
        ]),
        ("无变化·空清单（3.3-②）", []),
        ("错放告警（3.3-③）", [
            makeItem("A-02-01", "C01-T0012", 0.88, "misplaced"),
        ]),
        ("未知物告警", [
            makeItem("A-01-06", "", 0.71, "unknown"),
        ]),
        ("置信度不足告警", [
            makeItem("A-01-05", "C01-T0007", 0.55, "low_confidence"),
        ]),
        ("缺失告警 missing", [
            makeItem("A-01-05", "C01-T0007", 0.0, "missing"),
        ]),
    ]

    for sceneName, items in legalScenes:
        result = check_ack(makeAck(items), SAMPLE_REQUEST_ID)

        assert result.hostAccepts is True, f"{sceneName} 应被上位机放行: {result.describe()}"
        assert result.errors == (), f"{sceneName} 不应有结构错误: {result.errors}"
        assert result.extraKeys == (), f"{sceneName} 不应有多余字段: {result.extraKeys}"


## @brief 对应验收项 3：TC-24-12/14/15 与 TC-23E 兼容帧，校验器必须判上位机放行
def testHostAcceptsTc24CompatibilityFrames() -> None:
    ## TC-24-12：缺 alert_type，上位机按 none 兼容
    noAlertItem = makeItem("A-01-05", "C01-T0007", 0.93, None)
    noAlertResult = check_ack(makeAck([noAlertItem]), SAMPLE_REQUEST_ID)
    assert noAlertResult.hostAccepts is True
    assert noAlertResult.errors == ()

    ## TC-24-14：多带历史字段 present，上位机忽略（但协议禁止上线，见另一条用例）
    legacyItem = makeItem("A-01-05", "C01-T0007", 0.93)
    legacyItem["present"] = True
    legacyResult = check_ack(makeAck([legacyItem]), SAMPLE_REQUEST_ID)
    assert legacyResult.hostAccepts is True
    assert legacyResult.errors == ()
    assert any("present" in text for text in legacyResult.extraKeys)

    ## TC-24-15：空货位 tool_id 为空串且该行仍在清单中
    emptySlot = makeItem("A-01-06", "", 0.0)
    emptySlotResult = check_ack(makeAck([emptySlot]), SAMPLE_REQUEST_ID)
    assert emptySlotResult.hostAccepts is True
    assert emptySlotResult.errors == ()

    ## TC-23E：顶层多带协议外字段，上位机忽略
    extraFrame = makeAck([])
    extraFrame["extra"] = 1
    extraResult = check_ack(extraFrame, SAMPLE_REQUEST_ID)
    assert extraResult.hostAccepts is True
    assert extraResult.errors == ()


## @brief 对应验收项 3：上位机明确拒绝的非法帧，校验器必须全部判失败且文案逐字一致
def testHostRejectsRealSimulatorBadFrames() -> None:
    badFrames: list[tuple[str, list[object], tuple[str, ...]]] = [
        ("TC-24-01 缺 items", [], ("items 字段缺失或不是数组",)),
        ("TC-24-02 items 是对象非数组", [], ("items 字段缺失或不是数组",)),
        ("TC-24-17 items 元素是字符串", ["A-01-05"], ("第1项不是对象",)),
        ("TC-24-03 item 缺 position", [
            {"tool_id": "C01-T0007", "confidence": 0.9, "alert_type": "none"},
        ], ("第1项 position 缺失、为空或不是字符串",)),
        ("TC-24-04 position 是数字", [
            {"position": 12345, "tool_id": "C01-T0007", "confidence": 0.9, "alert_type": "none"},
        ], ("第1项 position 缺失、为空或不是字符串",)),
        ("TC-24-07 item 缺 tool_id", [
            {"position": "A-01-05", "confidence": 0.9, "alert_type": "none"},
        ], ("第1项 tool_id 缺失或不是字符串",)),
        ("TC-24-08 tool_id 是数字", [
            {"position": "A-01-05", "tool_id": 12345, "confidence": 0.9, "alert_type": "none"},
        ], ("第1项 tool_id 缺失或不是字符串",)),
        ("TC-24-09 item 缺 confidence", [
            {"position": "A-01-05", "tool_id": "C01-T0007", "alert_type": "none"},
        ], ("第1项 confidence 缺失或不是数值",)),
        ("TC-24-10 confidence 是字符串", [
            {"position": "A-01-05", "tool_id": "C01-T0007", "confidence": "0.9",
             "alert_type": "none"},
        ], ("第1项 confidence 缺失或不是数值",)),
        ("TC-24-11 confidence=99 超出 0~1", [
            {"position": "A-01-05", "tool_id": "C01-T0007", "confidence": 99,
             "alert_type": "none"},
        ], ("第1项 confidence=99 超出 0~1",)),
        ("confidence=-1 超出 0~1", [
            {"position": "A-01-05", "tool_id": "C01-T0007", "confidence": -1,
             "alert_type": "none"},
        ], ("第1项 confidence=-1 超出 0~1",)),
        ("TC-24-13 alert_type 不在枚举内", [
            {"position": "A-01-05", "tool_id": "C01-T0007", "confidence": 0.9,
             "alert_type": "banana"},
        ], ("第1项 alert_type 不是字符串或不在协议枚举内",)),
        ("TC-24-16 同一货位重复上报两条", [
            makeItem("A-01-05", "C01-T0007", 0.93),
            makeItem("A-01-05", "C01-T0099", 0.93),
        ], ("第2项货位 A-01-05 重复上报",)),
    ]

    for frameName, items, expectedErrors in badFrames:
        if frameName == "TC-24-01 缺 items":
            frame: ProtocolFrame = {
                "type": "recognize_ack", "request_id": SAMPLE_REQUEST_ID,
            }
        elif frameName == "TC-24-02 items 是对象非数组":
            frame = {
                "type": "recognize_ack", "request_id": SAMPLE_REQUEST_ID,
                "items": {"position": "A-01-05", "tool_id": "C01-T0007"},
            }
        else:
            frame = makeAck(items)

        result = check_ack(frame, SAMPLE_REQUEST_ID)

        assert result.hostAccepts is False, f"{frameName} 应被上位机拒绝"
        assert result.errors == expectedErrors, (
            f"{frameName} 错误文案应与上位机一致: 实际 {result.errors}"
        )


## @brief 对应验收项 3：items 每项恰好 4 字段，协议外字段单列而不与结构错混淆
def testAckItemMustCarryExactlyFourKeys() -> None:
    item = makeItem("A-01-05", "C01-T0007", 0.93)
    assert set(item.keys()) == {"position", "tool_id", "confidence", "alert_type"}

    cleanResult = check_items([item])
    assert cleanResult.errors == ()
    assert cleanResult.extraKeys == ()

    legacyItem = dict(item)
    legacyItem["present"] = True
    legacyResult = check_items([legacyItem])
    assert legacyResult.errors == ()
    assert legacyResult.extraKeys == ("第1项携带协议禁止字段 present",)

    noAlertItem = dict(item)
    del noAlertItem["alert_type"]
    noAlertResult = check_items([noAlertItem])
    assert noAlertResult.errors == ()
    assert noAlertResult.protocolClean is True


## @brief 对应验收项 3：request_id 是 snake_case，驼峰 requestId 上位机读不到
def testAckRequestIdMustBeSnakeCase() -> None:
    camelFrame: ProtocolFrame = {
        "type": "recognize_ack",
        "requestId": SAMPLE_REQUEST_ID,
        "items": [makeItem("A-01-05", "C01-T0007", 0.93)],
    }
    camelResult = check_ack(camelFrame, SAMPLE_REQUEST_ID)

    assert camelResult.hostAccepts is False
    assert any("request_id" in text for text in camelResult.errors)

    missingFrame: ProtocolFrame = {
        "type": "recognize_ack",
        "items": [makeItem("A-01-05", "C01-T0007", 0.93)],
    }
    missingResult = check_ack(missingFrame, SAMPLE_REQUEST_ID)

    assert missingResult.hostAccepts is False
    assert any("request_id" in text for text in missingResult.errors)

    wrongIdFrame = makeAck([makeItem("A-01-05", "C01-T0007", 0.93)], "req-other-9999")
    wrongIdResult = check_ack(wrongIdFrame, SAMPLE_REQUEST_ID)

    assert wrongIdResult.hostAccepts is False
    assert any("request_id 与期望不符" in text for text in wrongIdResult.errors)


## @brief 对应验收项 5：周期帧形状与上位机开柜闸门结论
def testPeriodicFrameShapeAndCameraGate() -> None:
    allOkFrame: ProtocolFrame = {
        "type": "periodic",
        "uptime_sec": 10,
        "software_version": "edge-0.1.0",
        "camera_status": [
            {"camera_id": f"CAM{index}", "status": "ok"} for index in range(1, 9)
        ],
    }
    okResult = check_periodic(allOkFrame)

    assert okResult.errors == ()
    assert any("闸门放行" in note for note in okResult.notes)

    offlineFrame: ProtocolFrame = {
        "type": "periodic",
        "uptime_sec": 11,
        "software_version": "edge-0.1.0",
        "camera_status": [
            {"camera_id": f"CAM{index}", "status": "ok"} for index in range(1, 9)
        ],
    }
    offlineStatus = cast(list[object], offlineFrame["camera_status"])
    cast(ProtocolItem, offlineStatus[2])["status"] = "offline"
    offlineResult = check_periodic(offlineFrame)

    assert offlineResult.errors == ()
    assert any("CAM3(offline)" in note for note in offlineResult.notes)
    assert any("拒绝" in note for note in offlineResult.notes)

    badFrame: ProtocolFrame = {
        "type": "periodic",
        "uptime_sec": 12,
        "software_version": "edge-0.1.0",
        "camera_status": [{"camera_id": "CAM1", "status": "broken"}],
    }
    badResult = check_periodic(badFrame)

    assert badResult.hostAccepts is False
    assert any("状态非法" in text for text in badResult.errors)


## @brief 对应验收项 5：生产配置下周期帧 3 秒一帧，且每帧形状合规
def testPeriodicFrameIsSentEveryThreeSeconds() -> None:
    config = IniConfigManager(str(CONFIG_PATH))
    intervalSec = float(config.get("tcp", "heart_interval_sec"))
    assert intervalSec == 3.0

    recorder = FrameRecorderSocket()
    comm = TcpComm(recorder, MAX_FRAME_SIZE, FakeLogger())
    heart = TcpHeartThread(
        comm, intervalSec,
        buildPeriodicFrame(
            lambda: [{"camera_id": f"CAM{index}", "status": "ok"} for index in range(1, 9)],
            monotonic(), "edge-cadence-0.1.0",
        ),
        lambda: "UP", FakeLogger(), lambda: None,
    )
    heart.start()
    try:
        deadline = monotonic() + CADENCE_WAIT_SEC
        while monotonic() < deadline and len(recorder.sentFrames) < 2:
            Event().wait(0.05)
    finally:
        heart.stop(1.0)

    assert len(recorder.sentFrames) == 2, (
        f"9 秒内应发出至少 2 帧周期帧，实发 {len(recorder.sentFrames)} 帧"
    )
    gap = recorder.sentTimes[1] - recorder.sentTimes[0]
    assert CADENCE_LOWER_SEC <= gap <= CADENCE_UPPER_SEC, (
        f"周期帧间隔实测 {gap:.3f}s，应约 {intervalSec}s"
    )

    frame = json.loads(recorder.sentFrames[0].decode("utf-8"))
    result = check_periodic(cast(ProtocolFrame, frame))
    assert result.errors == ()
    assert any("闸门放行" in note for note in result.notes)


## @brief 对应验收项 3：覆盖口径与出库取出正确判据，复刻上位机业务层
def testCoverageAndOutboundJudgementMatchHost() -> None:
    emptyResult = check_coverage([], ["A-01-05", "A-01-06"])

    assert emptyResult.hostAccepts is False
    assert any("覆盖不全" in text for text in emptyResult.errors)

    partialResult = check_coverage([makeItem("A-01-05", "C01-T0007", 0.93)], ["A-01-05", "A-01-06"])

    assert partialResult.hostAccepts is False
    assert any("A-01-06" in text for text in partialResult.errors)

    fullResult = check_coverage(
        [makeItem("A-01-05", "C01-T0007", 0.93), makeItem("A-01-06", "", 0.0)],
        ["A-01-05", "A-01-06"],
    )

    assert fullResult.hostAccepts is True

    items = [makeItem("A-01-05", "", 0.0), makeItem("A-01-06", "C01-T0007", 0.93)]
    assert judgeOutbound(items, "A-01-05") == "取出正确"
    assert judgeOutbound(items, "A-01-06") == "货位上仍有C01-T0007"
    assert judgeOutbound(items, "A-09-09") == "识别清单未回报该货位，仅提示，不判取出正确"
    assert judgeInbound(items, "A-01-06", "C01-T0007") == "放入正确"
    assert judgeInbound(items, "A-01-06", "C01-T0009") == "货位上为C01-T0007"


## @brief 对应验收项 3：边缘机源码不得出现被删字段（present / alert_level / class_id / tool_name）
def testEdgeSourcesDoNotEmitRemovedFields() -> None:
    findings = scanSourceLiterals(SCAN_DIRECTORIES, REMOVED_FIELD_PATTERN)

    assert findings == [], (
        f"边缘机 ack 构造路径出现协议已删字段: {findings}"
    )


## @brief 对应验收项 3：边缘机 items[] 不得携带内部字段 roiId / className / item / boundItem
def testEdgeAckItemsCarryNoInternalFields() -> None:
    findings = scanSourceLiterals((ACK_ITEM_SOURCE.parent.as_posix(),), INTERNAL_ITEM_FIELD_PATTERN)

    assert findings == [], (
        f"边缘机 items[] 仍携带内部字段: {findings}"
    )


## @brief 对应验收项 3：边缘机识别线程产出的应答帧必须符合上位机协议
def testEdgeProductionAckMatchesHostProtocol() -> None:
    ## 真实推理后端产出的检测结果只有类别名与置信度，没有区域编号
    detections: list[DetectionItem] = [{"className": "torx", "confidence": 0.93}]
    ack = runProductionAck(detections)

    result = check_ack(ack, SAMPLE_REQUEST_ID)

    assert result.hostAccepts is True, (
        f"边缘机产出的应答帧应被上位机放行: {result.describe()}"
    )
    assert result.protocolClean is True, (
        f"边缘机产出的应答帧不得带协议外字段: {result.describe()}"
    )


## @brief 对应验收项 3：边缘机应答帧顶层键只允许 type / request_id / items
def testEdgeAckFrameTopLevelKeysAreProtocolExact() -> None:
    ## 真实推理后端产出的检测结果只有类别名与置信度，没有区域编号
    detections: list[DetectionItem] = [{"className": "torx", "confidence": 0.93}]
    ack = runProductionAck(detections)

    assert set(ack.keys()) == {"type", "request_id", "items"}, (
        f"边缘机应答帧顶层键应恰好为 type/request_id/items，实际 {sorted(ack.keys())}"
    )
    assert str(ack.get("request_id")) == SAMPLE_REQUEST_ID

    items = cast(list[object], ack.get("items"))
    assert len(items) == 1
    item = cast(ProtocolItem, items[0])
    assert set(item.keys()) == {"position", "tool_id", "confidence", "alert_type"}, (
        f"边缘机 items 每项应恰好 4 字段，实际 {sorted(item.keys())}"
    )


## @brief 对应验收项 3：边缘机应答帧顶层不得出现 workerId / requestId 键名
def testEdgeAckFrameHasNoInternalTopLevelKeys() -> None:
    ## 扫描范围只取识别模块（应答帧组帧处）。
    ## control/edge_control.py:30 的 REQUEST_ID_KEY="requestId" 是内部取号备用常量，
    ## 只被 extractRequestId 读取、从不写入线上帧，不属于组帧路径，故不在本断言范围。
    findings = scanSourceLiterals(
        (ACK_ITEM_SOURCE.parent.as_posix(),), INTERNAL_FRAME_FIELD_PATTERN,
    )

    assert findings == [], (
        f"边缘机应答帧顶层仍带内部键名: {findings}"
    )
