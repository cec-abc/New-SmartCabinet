"""上行协议合规用例：把边缘机真正上线的每一帧按上位机口径逐帧判一遍。

判据来源（上位机工程只读引用，不做任何修改）：
- src/comm/EdgeService.cpp:362-465  帧型分发；认不出的 type 丢弃并计数
- src/comm/EdgeService.cpp:55-111   parseItems 五条校验
- src/comm/EdgeService.cpp:118-132  parsePeriodic
- src/comm/EdgeLink.cpp:156-192     按行切帧；单帧超上限直接断链
- src/comm/CommTypes.h:14-74        单帧上限与字段定义

口径：
1. 上行帧型清单从生产源码里扫出来，不手写清单，避免清单与代码走偏；
2. 清单里每个帧型要么上位机认识（能上线），要么被出网守卫拦下（空字节不上网）；
3. 帧大小按出网字节实测，100 货位场景必须留在安全阈值内；
4. 识别失败只允许一帧合法应答上线，失败帧不得污染上位机的丢弃计数。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from time import monotonic
from typing import cast

from edge.app_init import buildPeriodicFrame


def defaultFailureFrame(workerId: int, exception: Exception):
    return {"type": "error", "workerId": workerId, "message": str(exception)}
from edge.control.edge_control import CachedEvent, EdgeControl, ModuleWiring
from edge.exceptions import EdgeError, ErrorCode
from edge.modules.recognition.recognition_utils import buildAck, buildAckItem
from edge.modules.tcp import tcp_comm
from edge.modules.tcp.tcp_comm import TcpComm
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_socket import FakeSocket
from edge.tests.integration import host_protocol_checker
from edge.tests.integration.fake_host import FakeHost, HostFrame
from edge.tests.integration.host_protocol_checker import (
    check_ack,
    check_frame_size,
    check_frame_type,
    check_periodic,
)
from edge.tests.integration.tcp_client_socket import TcpClientSocket

## @file edge/tests/integration/test_uplink_protocol_compliance.py
## @brief 上行协议合规用例：上行帧清单、帧大小、失败路径与请求标识逐条判定
## @author 边缘计算项目

## @brief 边缘机源码根目录
EDGE_ROOT: Path = Path(__file__).resolve().parents[2]
## @brief 扫描上行帧型清单的源码目标；只扫生产代码，不扫用例
SCAN_TARGETS: tuple[str, ...] = ("app_init.py", "control", "modules")
## @brief 帧型常量：名字以 TYPE 或 TYPES 结尾、值是字符串的模块级常量
FRAME_TYPE_CONSTANT_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*[A-Z][A-Z_0-9]*_?TYPES?\s*:\s*str\s*=\s*\"([^\"]+)\"",
    re.MULTILINE,
)
## @brief 帧型集合常量：名字以 TYPES 结尾、值是字符串集合的模块级常量
FRAME_TYPE_SET_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*[A-Z][A-Z_0-9]*_?TYPES\s*:\s*frozenset\[str\]\s*=\s*frozenset\(\{([^}]*)\}\)",
    re.MULTILINE,
)
## @brief 内联写出的帧型字面量
FRAME_TYPE_INLINE_PATTERN: re.Pattern[str] = re.compile(
    r"\"type\"\s*:\s*\"([^\"]+)\"",
)
## @brief 联调单帧字节上限，与上位机一致
MAX_FRAME_SIZE: int = 1024 * 1024
## @brief 出网单帧安全阈值：上位机上限的一半，留一倍余量
SAFE_FRAME_LIMIT: int = MAX_FRAME_SIZE // 2
## @brief 全柜实况场景的货位数量
POSITION_COUNT: int = 100
## @brief 用例用的请求标识
REQUEST_ID: str = "req-uplink-0001"
## @brief 等待桩上位机接入的最长秒数
CLIENT_WAIT_SEC: float = 5.0
## @brief 等待回包的最长秒数
ACK_WAIT_SEC: float = 5.0
## @brief 停机步骤名，与控制层的 STOP_ORDER 一致
STOP_STEPS: tuple[str, ...] = ("USB", "RECOGNITION", "TCP", "LOG")
## @brief 空动作；联调里不需要真实模块的停机步骤
#  @return 无
def noAction() -> None:
    return None


## @brief 收集要扫描的生产源码文件
#  @return 文件列表
def collectScanFiles() -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        targetPath = EDGE_ROOT / target
        if targetPath.is_dir():
            files.extend(sorted(targetPath.rglob("*.py")))
        elif targetPath.is_file():
            files.append(targetPath)
    return files


## @brief 扫出生产源码里的全部上行帧型
#  @return 帧型列表，已排序
def scanUplinkFrameTypes() -> list[str]:
    found: set[str] = set()
    for path in collectScanFiles():
        text = path.read_text(encoding="utf-8")
        found.update(FRAME_TYPE_CONSTANT_PATTERN.findall(text))
        for body in FRAME_TYPE_SET_PATTERN.findall(text):
            found.update(re.findall(r"\"([^\"]+)\"", body))
        found.update(FRAME_TYPE_INLINE_PATTERN.findall(text))
    return sorted(found)


## @brief 造出指定数量的协议条目
#  @param positionCount 货位数量
#  @return 协议条目列表
def buildPositionItems(positionCount: int) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index in range(positionCount):
        drawer = index // 10 + 1
        slot = index % 10 + 1
        items.append(
            buildAckItem(
                f"A-{drawer:02d}-{slot:02d}", f"C01-T{index:04d}", 0.93, "none",
            ),
        )
    return items


## @brief 构造控制层，帧发送器走真实 TCP 出网口
#  @param comm 通信封装
#  @return 控制层与交给帧发送器的帧记录
def buildControlUnderTest(comm: TcpComm) -> tuple[EdgeControl, list[CachedEvent]]:
    handed: list[CachedEvent] = []

    ## @brief 把帧交给真实出网口
    #  @param frame 待发送帧
    #  @return 发送结果
    def frameSender(frame: CachedEvent) -> bool:
        handed.append(frame)
        return comm.send(comm.encodeFrame(frame))

    wiring = ModuleWiring()
    for step in STOP_STEPS:
        wiring.stopActions[step] = noAction
    control = EdgeControl(
        FakeLogger(), {"recognize_req": lambda signal: None}, wiring,
        frameSender, defaultFailureFrame,
        expectedWorkerCount=1,
        degradedItemsProvider=lambda workerId: [
            buildAckItem("A-01-01", "", 0.0, "unknown"),
        ],
    )
    control.onLinkUp()
    return control, handed


## @brief 出网守卫的白名单必须与上位机校验器的白名单逐项一致
def test_wire_guard_allow_list_matches_host_checker() -> None:
    assert (
        tcp_comm.HOST_RECOGNIZED_FRAME_TYPES
        == host_protocol_checker.HOST_RECOGNIZED_FRAME_TYPES
    ), (
        "出网守卫的白名单与上位机认识的帧型不一致："
        f"{sorted(tcp_comm.HOST_RECOGNIZED_FRAME_TYPES)} vs "
        f"{sorted(host_protocol_checker.HOST_RECOGNIZED_FRAME_TYPES)}"
    )


## @brief 上行帧型清单里每一帧型：上位机认识的能上线，不认识的必须被拦下
def test_every_uplink_frame_type_is_known_or_blocked() -> None:
    frameTypes = scanUplinkFrameTypes()
    assert frameTypes, "上行帧型清单不应为空"

    comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, FakeLogger())
    for frameType in frameTypes:
        frame: dict[str, object] = {"type": frameType}
        hostResult = check_frame_type(frame)
        payload = comm.encodeFrame(frame)
        if frameType in host_protocol_checker.HOST_RECOGNIZED_FRAME_TYPES:
            assert hostResult.hostAccepts is True, hostResult.describe()
            assert payload != b"", (
                f"上位机认识的帧型 {frameType} 被出网守卫误拦，不该上线失败"
            )
        else:
            assert hostResult.hostAccepts is False, hostResult.describe()
            assert payload == b"", (
                f"上位机不认识的帧型 {frameType} 仍被放上线，"
                "会污染上位机的丢弃计数"
            )


## @brief 真实上行帧逐帧过上位机校验器：周期帧与识别应答帧都判通过
def test_production_uplink_frames_pass_host_checker() -> None:
    comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, FakeLogger())

    periodic = buildPeriodicFrame(
        lambda: [{"camera_id": f"CAM{index}", "status": "ok"} for index in range(1, 9)],
        monotonic() - 60,
        "edge-0.1.0",
    )()
    periodicPayload = comm.encodeFrame(periodic)
    assert periodicPayload != b""
    periodicFrame = cast(HostFrame, json.loads(periodicPayload[:-1].decode("utf-8")))
    assert check_frame_type(periodicFrame).hostAccepts is True
    periodicResult = check_periodic(periodicFrame)
    assert periodicResult.errors == (), periodicResult.describe()

    ack = buildAck(REQUEST_ID, buildPositionItems(POSITION_COUNT))
    ackPayload = comm.encodeFrame(ack)
    assert ackPayload != b""
    ackFrame = cast(HostFrame, json.loads(ackPayload[:-1].decode("utf-8")))
    assert check_frame_type(ackFrame).hostAccepts is True
    ackResult = check_ack(ackFrame, REQUEST_ID)
    assert ackResult.hostAccepts is True, ackResult.describe()
    assert ackResult.protocolClean is True, ackResult.describe()


## @brief 100 货位的全柜实况帧必须留在安全阈值内，且不触发上位机断链
def test_hundred_position_frame_fits_safe_limit() -> None:
    comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, FakeLogger())
    ack = buildAck(REQUEST_ID, buildPositionItems(POSITION_COUNT))

    payload = comm.encodeFrame(ack)

    assert len(payload) <= SAFE_FRAME_LIMIT, (
        f"100 货位帧 {len(payload)} 字节超出安全阈值 {SAFE_FRAME_LIMIT}"
    )
    sizeResult = check_frame_size(len(payload))
    assert sizeResult.hostAccepts is True, sizeResult.describe()
    frame = cast(HostFrame, json.loads(payload[:-1].decode("utf-8")))
    assert len(cast(list[object], frame.get("items"))) == POSITION_COUNT


## @brief 识别失败只上线一帧合法应答；失败帧不上线，不污染上位机丢弃计数
def test_recognition_failure_sends_only_one_legal_ack() -> None:
    host = FakeHost()
    port = host.start()
    clientSocket = TcpClientSocket("127.0.0.1", port)
    comm = TcpComm(clientSocket, MAX_FRAME_SIZE, FakeLogger())
    control, handed = buildControlUnderTest(comm)
    try:
        clientSocket.connect()
        assert host.waitClient(CLIENT_WAIT_SEC) is True

        control.routeSignal({"type": "recognize_req", "request_id": REQUEST_ID})
        control.onRecognitionError(1, EdgeError(ErrorCode.INFERENCE_TIMEOUT, "推理超时"))
        control.dispatchOutbox()

        ack = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)
        assert ack is not None, "识别失败后应回一帧合法应答"
        ackResult = check_ack(ack, REQUEST_ID)
        assert ackResult.hostAccepts is True, ackResult.describe()
        assert ackResult.protocolClean is True, ackResult.describe()

        ## 线上只应有这一帧；失败帧由出网守卫拦下
        assert len(host.receivedRawLines()) == 1, (
            f"线上多出帧：{[line[:60] for line in host.receivedRawLines()]}"
        )
        assert host.dropCount() == 0, (
            f"上位机丢弃计数被污染：{host.droppedFrames()}"
        )
        ## 控制层仍把失败帧交给帧发送器，出网口再把它拦下
        assert [str(frame.get("type")) for frame in handed] == [
            "error", "recognize_ack",
        ]
    finally:
        control.stopSystem()
        host.stop()


## @brief 请求标识原样回带，不改写、不截断、不转义
def test_request_id_is_echoed_verbatim() -> None:
    comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, FakeLogger())
    rawId = 'req-1700000000000-1"\\一 号'

    payload = comm.encodeFrame(buildAck(rawId, buildPositionItems(3)))

    assert payload != b""
    frame = cast(HostFrame, json.loads(payload[:-1].decode("utf-8")))
    assert frame.get("request_id") == rawId
    assert check_ack(frame, rawId).hostAccepts is True


## @brief 出网帧体内不得出现裸换行或裸控制字符，否则上位机按行切帧会切碎
def test_encoded_frame_has_no_raw_newline() -> None:
    comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, FakeLogger())
    frames: list[dict[str, object]] = [
        buildPeriodicFrame(
            lambda: [{"camera_id": f"CAM{index}", "status": "ok"} for index in range(1, 9)],
            monotonic() - 60,
            "edge-0.1.0",
        )(),
        buildAck(REQUEST_ID, buildPositionItems(POSITION_COUNT)),
        defaultFailureFrame(1, EdgeError(ErrorCode.CAPTURE, "采集失败\n带换行")),
    ]
    for frame in frames:
        payload = comm.encodeFrame(frame)
        if not payload:
            ## 被出网守卫拦下的帧没有字节上线，不参与裸字符检查
            continue
        body = payload[:-1]
        assert b"\n" not in body, f"帧体含裸换行：{body[:120]!r}"
        assert not any(byte < 0x20 for byte in body), f"帧体含裸控制字符：{body[:120]!r}"
        assert payload.endswith(b"\n")


## @brief 清单大到超限时裁剪出帧，绝不把上位机踢下线
def test_oversized_frame_is_trimmed_instead_of_dropped() -> None:
    logger = FakeLogger()
    comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, logger)
    ack = buildAck(REQUEST_ID, buildPositionItems(20000))

    payload = comm.encodeFrame(ack)

    assert payload != b"", "超限帧应裁剪后上线，不能整帧丢掉"
    assert len(payload) <= SAFE_FRAME_LIMIT, (
        f"裁剪后仍超安全阈值：{len(payload)} > {SAFE_FRAME_LIMIT}"
    )
    assert check_frame_size(len(payload)).hostAccepts is True
    frame = cast(HostFrame, json.loads(payload[:-1].decode("utf-8")))
    items = cast(list[object], frame.get("items"))
    assert 0 < len(items) < 20000, f"裁剪后条目数异常：{len(items)}"
    ackResult = check_ack(frame, REQUEST_ID)
    assert ackResult.hostAccepts is True, ackResult.describe()
    assert any("裁剪" in record[1] for record in logger.errorRecords), (
        "裁剪必须留日志，便于现场追溯"
    )
