"""外部交互日志取证：真实 TCP 桩加日志器，逐帧核对 RX / TX 的接线、内容与折叠口径。"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from threading import Event
from time import monotonic
from typing import cast

from edge.app_init import buildPeriodicFrame
from edge.infra.log_manager import LOG_MODE_MERGED, LOG_MODE_SPLIT, LogManager
from edge.interfaces.i_sinks import DecodedSignal, SignalSink
from edge.modules.recognition.recognition_utils import buildAck, buildAckItem
from edge.modules.tcp.tcp_comm import (
    IO_LOG_FULL_FRAME_BYTES,
    RX_MODULE_NAME,
    TX_MODULE_NAME,
    TcpComm,
    buildIoLogPayload,
)
from edge.modules.tcp.tcp_decode_thread import TcpDecodeThread
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_socket import FakeSocket
from edge.tests.integration.fake_host import FakeHost, HostFrame
from edge.tests.integration.tcp_client_socket import TcpClientSocket

## @file edge/tests/integration/test_external_io_log.py
## @brief 外部交互日志取证：RX / TX 接线、字段一致、大帧折叠、两种日志模式落盘
## @author 边缘计算项目

## @brief 与正式配置一致的单帧字节上限
MAX_FRAME_SIZE: int = 1024 * 1024
## @brief 取证用日志文件字节上限
LOG_FILE_SIZE: int = 1024 * 1024
## @brief 日志消费线程取队列超时秒，取证里调快以便尽快落盘
LOG_POLL_SEC: float = 0.02
## @brief 磁盘清理阈值，取 0 表示取证期间不清理历史文件
LOG_DISK_THRESHOLD: float = 0.0
## @brief 等待桩上位机接入的最长秒数
CLIENT_WAIT_SEC: float = 5.0
## @brief 等待一处条件成立的最长秒数
CONDITION_WAIT_SEC: float = 5.0
## @brief 取证用请求标识
REQUEST_ID: str = "req-io-log-0001"
## @brief 100 货位场景的货位数量
POSITION_COUNT: int = 100


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


## @brief 造出指定数量的协议条目
#  @param count 货位数量
#  @return 协议条目列表
def buildPositionItems(count: int) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index in range(count):
        items.append(
            buildAckItem(
                f"A-{index // 10 + 1:02d}-{index % 10 + 1:02d}",
                f"C01-T{index:04d}", 0.93, "none",
            ),
        )
    return items


## @brief 取证用 8 路相机状态
#  @return 8 路状态列表
def ioTestCameraStatus() -> list[dict[str, object]]:
    return [
        {"camera_id": f"CAM{index}", "status": "ok"} for index in range(1, 9)
    ]


## @brief 只记录解码信号与坏帧的 Sink，回调里不做任何网络 IO
class RecordingSink(SignalSink):
    ## @brief 构造记录器
    def __init__(self) -> None:
        ## @brief 已解码信号
        self.signals: list[DecodedSignal] = []
        ## @brief 坏帧异常
        self.frameErrors: list[Exception] = []

    ## @brief 记录解码信号
    #  @param signal 信号帧
    #  @return 无
    def onSignalDecoded(self, signal: DecodedSignal) -> None:
        self.signals.append(signal)

    ## @brief 记录坏帧异常
    #  @param exception 解析异常
    #  @return 无
    def onFrameError(self, exception: Exception) -> None:
        self.frameErrors.append(exception)

    ## @brief 链路断开宣告，取证里无需处理
    #  @param reason 断开原因
    #  @param source 宣告来源
    #  @return 无
    def onLinkDown(self, reason: str, source: str) -> None:
        return None

    ## @brief 链路恢复通知，取证里无需处理
    #  @return 无
    def onLinkUp(self) -> None:
        return None


## @brief 构造并启动一个独立日志器，落盘目录由取证传入
#  @param logDir 日志目录
#  @param mode 合并 / 分开模式
#  @return 已启动的日志器
def startLogManager(logDir: Path, mode: int) -> LogManager:
    manager = LogManager(
        str(logDir), LOG_FILE_SIZE, mode, LOG_DISK_THRESHOLD, LOG_POLL_SEC,
    )
    manager.start()
    return manager


## @brief 读出某个前缀下的全部日志行，逐行还原成字典
#  @param logDir 日志目录
#  @param prefix 文件名前缀
#  @return 日志记录列表
def readLogRecords(logDir: Path, prefix: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(logDir.glob(f"{prefix}_*.log")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(cast(dict[str, object], json.loads(line)))
    return records


## @brief 对应验收：真实 TCP 桩上收发一帧各恰好记一条，字段一致、周期帧有 TX、不重复、可读
def test_single_io_frames_are_logged_exactly_once() -> None:
    host = FakeHost()
    port = host.start()
    clientSocket = TcpClientSocket("127.0.0.1", port)
    logger = FakeLogger()
    comm = TcpComm(clientSocket, MAX_FRAME_SIZE, logger)
    sink = RecordingSink()
    decode = TcpDecodeThread(comm, sink, logger)
    try:
        clientSocket.connect()
        assert host.waitClient(CLIENT_WAIT_SEC) is True
        decode.start()

        reqFrame: HostFrame = {
            "type": "recognize_req",
            "request_id": REQUEST_ID,
            "timestamp": 1700000000000,
        }
        host.sendFrame(reqFrame)
        assert waitUntil(lambda: bool(sink.signals), CONDITION_WAIT_SEC) is True

        ackFrame = buildAck(REQUEST_ID, buildPositionItems(2))
        assert comm.send(comm.encodeFrame(ackFrame)) is True
        assert host.waitFrameOfType("recognize_ack", CONDITION_WAIT_SEC) is not None

        periodicFrame = buildPeriodicFrame(
            ioTestCameraStatus, monotonic(), "edge-io-log-test",
        )()
        assert comm.send(comm.encodeFrame(periodicFrame)) is True
        assert host.waitFrameOfType("periodic", CONDITION_WAIT_SEC) is not None

        ## 一帧入网恰好一条接收日志，完整字段与原始帧一致
        assert len(logger.rxRecords) == 1
        assert logger.rxRecords[0][0] == RX_MODULE_NAME
        rxPayload = cast(dict[str, object], logger.rxRecords[0][1])
        assert rxPayload["type"] == "recognize_req"
        assert rxPayload["request_id"] == REQUEST_ID
        assert rxPayload["timestamp"] == 1700000000000
        assert isinstance(rxPayload["frameBytes"], int)

        ## 发送方向：识别应答恰好一条、周期帧恰好一条，同一帧不多条
        assert all(record[0] == TX_MODULE_NAME for record in logger.txRecords)
        txPayloads = [
            cast(dict[str, object], record[1]) for record in logger.txRecords
        ]
        acks = [
            payload for payload in txPayloads if payload.get("type") == "recognize_ack"
        ]
        periodics = [
            payload for payload in txPayloads if payload.get("type") == "periodic"
        ]
        assert len(acks) == 1
        assert len(periodics) == 1
        assert acks[0]["request_id"] == REQUEST_ID
        assert periodics[0]["type"] == "periodic"

        ## 负载是可读字典，不是字节或十六进制，序列化成单行无裸换行
        for payload in [rxPayload, *txPayloads]:
            text = json.dumps(payload, ensure_ascii=False)
            assert "bytesHex" not in text
            assert "\n" not in text
    finally:
        decode.stop(1.0)
        clientSocket.close()
        host.stop()


## @brief 对应验收：100 货位大帧只记折叠摘要，仍带发送方向标识、条数与字节数
def test_large_ack_frame_is_folded_in_log(tmp_path: Path) -> None:
    logDir = tmp_path / "folded"
    manager = startLogManager(logDir, LOG_MODE_MERGED)
    comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, manager)
    try:
        ack = buildAck(REQUEST_ID, buildPositionItems(POSITION_COUNT))
        payload = comm.encodeFrame(ack)
        assert payload != b""
        assert len(payload) > IO_LOG_FULL_FRAME_BYTES
    finally:
        manager.stop(2.0)

    records = [
        record for record in readLogRecords(logDir, "ALL") if record["type"] == "TX"
    ]
    assert len(records) == 1
    record = records[0]
    assert record["module"] == TX_MODULE_NAME
    assert "timestamp" in record
    body = cast(dict[str, object], record["payload"])
    assert body["type"] == "recognize_ack"
    assert body["request_id"] == REQUEST_ID
    assert body["folded"] is True
    assert body["itemsCount"] == POSITION_COUNT
    assert cast(int, body["frameBytes"]) > IO_LOG_FULL_FRAME_BYTES
    assert len(cast(list[object], body["itemsPreview"])) == 3
    assert "items" not in body
    assert "折叠" in str(body["note"])
    text = json.dumps(record, ensure_ascii=False)
    assert "bytesHex" not in text
    assert "\n" not in text


## @brief 对应验收：合并与分开两种模式下 RX / TX 都能落盘，分开模式各进各的文件
def test_rx_and_tx_land_in_both_log_modes(tmp_path: Path) -> None:
    cases: tuple[tuple[str, int], ...] = (
        ("merged", LOG_MODE_MERGED),
        ("split", LOG_MODE_SPLIT),
    )
    for tag, mode in cases:
        logDir = tmp_path / tag
        manager = startLogManager(logDir, mode)
        comm = TcpComm(FakeSocket(), MAX_FRAME_SIZE, manager)
        try:
            comm.encodeFrame(buildAck(REQUEST_ID, buildPositionItems(2)))
            manager.rx(
                RX_MODULE_NAME,
                buildIoLogPayload(
                    {"type": "recognize_req", "request_id": REQUEST_ID}, 64,
                ),
            )
        finally:
            manager.stop(2.0)

        if mode == LOG_MODE_MERGED:
            mergedRecords = readLogRecords(logDir, "ALL")
            assert any(record["type"] == "RX" for record in mergedRecords)
            assert any(record["type"] == "TX" for record in mergedRecords)
            ioRecords = [
                record for record in mergedRecords
                if record["type"] in ("RX", "TX")
            ]
        else:
            rxLines = readLogRecords(logDir, "RX")
            txLines = readLogRecords(logDir, "TX")
            assert rxLines and all(record["type"] == "RX" for record in rxLines)
            assert txLines and all(record["type"] == "TX" for record in txLines)
            infoLines = readLogRecords(logDir, "INFO")
            assert not any(
                record["type"] in ("RX", "TX") for record in infoLines
            )
            ioRecords = [*rxLines, *txLines]
        assert len(ioRecords) == 2
        for record in ioRecords:
            assert "module" in record
            assert "timestamp" in record
            assert "payload" in record
            assert "bytesHex" not in json.dumps(record, ensure_ascii=False)


## @brief 对应验收：小帧负载保留完整字段，大帧按注入阈值折叠成可读摘要
def test_build_io_log_payload_full_and_folded() -> None:
    small: dict[str, object] = {
        "type": "recognize_req", "request_id": REQUEST_ID,
        "timestamp": 1700000000000,
    }
    full = buildIoLogPayload(small, 120)
    assert full["type"] == "recognize_req"
    assert full["request_id"] == REQUEST_ID
    assert full["timestamp"] == 1700000000000
    assert full["frameBytes"] == 120
    assert "folded" not in full
    assert "bytesHex" not in json.dumps(full, ensure_ascii=False)
    assert "\n" not in json.dumps(full, ensure_ascii=False)

    large = buildAck(REQUEST_ID, buildPositionItems(POSITION_COUNT))
    folded = buildIoLogPayload(large, 8192, threshold=1024)
    assert folded["type"] == "recognize_ack"
    assert folded["request_id"] == REQUEST_ID
    assert folded["folded"] is True
    assert folded["itemsCount"] == POSITION_COUNT
    assert folded["frameBytes"] == 8192
    assert len(cast(list[object], folded["itemsPreview"])) == 3
    assert "items" not in folded
    assert not any(isinstance(value, bytes) for value in folded.values())
    assert "bytesHex" not in json.dumps(folded, ensure_ascii=False)
    assert "\n" not in json.dumps(folded, ensure_ascii=False)
