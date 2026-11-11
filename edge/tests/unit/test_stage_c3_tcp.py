"""c3 TCP 模块单元测试：退避重连 / 心跳去重 / 半包粘包 / 状态机去重 / FakeSocket 联调。"""
from __future__ import annotations

import json
import threading
import time

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_sinks import DecodedSignal, SignalSink
from edge.interfaces.i_socket import ISocket
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.tcp.tcp_control_layer import LINK_DOWN, LINK_UP, TcpControlLayer
from edge.modules.tcp.tcp_heart_thread import TcpHeartThread
from edge.modules.tcp.tcp_reconnect_thread import TcpReconnectThread
from edge.tests.fakes.fake_socket import FakeSocket


## @brief 连接前 N 次失败的套接字，用于退避测试
class FlakySocket(ISocket):
    def __init__(self, failTimes: int = 0) -> None:
        ## @brief 还需失败的次数
        self.failTimes: int = failTimes
        ## @brief 已尝试次数
        self.attempts: int = 0
        ## @brief 是否已连接
        self.connected: bool = False
        ## @brief 是否已关闭
        self.closed: bool = False

    def connect(self) -> None:
        self.attempts += 1
        if self.attempts <= self.failTimes:
            raise EdgeError(ErrorCode.LINK_DOWN, "simulated connect fail")
        self.connected = True

    def recv(self) -> bytes:
        return b""

    def send(self, data: bytes) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


## @brief connect 先休眠再成功的套接字，用于制造可观测的 DOWN 窗口
class SlowConnectSocket(FakeSocket):
    def connect(self) -> None:
        time.sleep(0.15)
        super().connect()


## @brief 按序返回接收数据的套接字，用于半包/粘包测试
class SequenceSocket(ISocket):
    def __init__(self, chunks: list[bytes]) -> None:
        ## @brief 待返回的接收块
        self.chunks: list[bytes] = list(chunks)
        ## @brief 已发送帧记录
        self.sentFrames: list[bytes] = []
        ## @brief 是否已关闭
        self.closed: bool = False

    def connect(self) -> None:
        return None

    def recv(self) -> bytes:
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def send(self, data: bytes) -> bool:
        self.sentFrames.append(data)
        return True

    def close(self) -> None:
        self.closed = True


## @brief 可控状态读取器
class StateHolder:
    def __init__(self, state: str) -> None:
        ## @brief 当前状态
        self.state: str = state

    def get(self) -> str:
        return self.state


## @brief 记录回调的上游 Sink
class FakeUpstreamSink(SignalSink):
    def __init__(self) -> None:
        ## @brief 已解码信号
        self.signals: list[DecodedSignal] = []
        ## @brief 坏帧异常
        self.frameErrors: list[Exception] = []
        ## @brief 链路恢复次数
        self.linkUps: int = 0

    def onSignalDecoded(self, signal: DecodedSignal) -> None:
        self.signals.append(signal)

    def onFrameError(self, exception: Exception) -> None:
        self.frameErrors.append(exception)

    def onLinkDown(self, reason: str, source: str) -> None:
        return None

    def onLinkUp(self) -> None:
        self.linkUps += 1


## @brief 记录启停的假线程，用于状态机去重断言
class _FakeThread:
    def __init__(self, name: str, log: list[str]) -> None:
        ## @brief 线程名
        self._name: str = name
        ## @brief 启停日志
        self._log: list[str] = log

    def start(self) -> None:
        self._log.append(f"start:{self._name}")

    def stop(self) -> None:
        self._log.append(f"stop:{self._name}")


## @brief c3-1 退避序列注入且 interruptibleWait 可打断
def test_c3_1_reconnect_backoff_interruptible() -> None:
    socket = FlakySocket(failTimes=50)
    thread = TcpReconnectThread(socket, [0.1, 0.1, 0.1], None, onConnected=lambda: None)
    thread.start()
    time.sleep(0.02)
    thread.stop(timeout=1.0)
    # 必须在一次退避等待中被打断返回，而非死等 0.1*N
    assert not thread.is_alive()


## @brief c3-1 退避重连成功移交
def test_c3_1_reconnect_success() -> None:
    socket = FlakySocket(failTimes=2)
    connected: list[bool] = []
    thread = TcpReconnectThread(socket, [0.01, 0.01, 0.01], None,
                                onConnected=lambda: connected.append(True))
    thread.start()
    thread.join(timeout=1.0)
    assert socket.connected
    assert connected == [True]
    assert socket.attempts == 3


## @brief c3-2 非 UP 不发送、不触发回调
def test_c3_2_heart_non_up_returns_false() -> None:
    comm = TcpComm(FakeSocket(), 4096)
    failed: list[bool] = []
    heart = TcpHeartThread(comm, 0.01, lambda: {"type": "heartbeat"}, StateHolder(LINK_DOWN).get,
                           None, onHeartSendFailed=lambda: failed.append(True))
    assert heart.trySendHeartbeat() is False
    assert failed == []


## @brief 发送恒失败的 FakeSocket 子类
class FailingSendSocket(FakeSocket):
    def send(self, data: bytes) -> bool:
        return False


## @brief c3-2 UP 但发送失败经 runLoop 触发回调（去重由 transitionTo 返回值处理）
def test_c3_2_heart_send_failure_callback() -> None:
    socket = FailingSendSocket()
    comm = TcpComm(socket, 4096)
    failed: list[bool] = []
    heart = TcpHeartThread(comm, 0.01, lambda: {"type": "heartbeat"}, StateHolder(LINK_UP).get,
                           None, onHeartSendFailed=lambda: failed.append(True))
    heart.start()
    time.sleep(0.05)
    heart.stop(timeout=1.0)
    assert failed, "发送失败应经 runLoop 触发回调"


## @brief c3-3 半包/粘包切帧与超长帧
def test_c3_3_split_and_oversize() -> None:
    comm = TcpComm(FakeSocket(), maxFrameSize=20)
    # 粘包：两帧连在一块；半包：末尾无 \n
    sticky = b'{"a":1}\n{"b":2}\n{"c":'
    frames, rest = comm.splitFrames(sticky)
    assert frames == [b'{"a":1}', b'{"b":2}']
    assert rest == b'{"c":'
    # 超长帧
    big = b'{"x":"' + b'a' * 100 + b'"}\n'
    done, _ = comm.splitFrames(big)
    try:
        comm.decodeAndParse(done[0])
        raise AssertionError("应抛 FRAME_PARSE")
    except EdgeError as exc:
        assert exc.code == ErrorCode.FRAME_PARSE
    # 正常帧
    good, _ = comm.splitFrames(b'{"ok":true}\n')
    assert comm.decodeAndParse(good[0]) == {"ok": True}


## @brief c3-4 同态返回 False 实现去重
def test_c3_4_transitionTo_idempotent() -> None:
    layer = TcpControlLayer.__new__(TcpControlLayer)
    layer._linkState = LINK_DOWN
    layer._stateLock = threading.Lock()
    layer._logger = None
    assert layer.transitionTo(LINK_UP, "c", "s") is True
    assert layer.transitionTo(LINK_UP, "c", "s") is False


## @brief c3-4 并发宣告 DOWN 仅一次生效（返回值去重）
def test_c3_4_transitionTo_concurrent() -> None:
    layer = TcpControlLayer.__new__(TcpControlLayer)
    layer._linkState = LINK_UP
    layer._stateLock = threading.Lock()
    layer._logger = None
    log: list[str] = []
    layer._reconnect = _FakeThread("reconnect", log)  # type: ignore[assignment]
    layer._heart = _FakeThread("heart", log)  # type: ignore[assignment]
    layer._decode = _FakeThread("decode", log)  # type: ignore[assignment]

    def declare() -> None:
        if layer.transitionTo(LINK_DOWN, "x", "RECV"):
            layer._heart.stop()  # type: ignore[union-attr]
            layer._decode.stop()  # type: ignore[union-attr]
            layer._reconnect.start()  # type: ignore[union-attr]

    threads = [threading.Thread(target=declare) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert log.count("start:reconnect") == 1
    assert log.count("stop:heart") == 1
    assert log.count("stop:decode") == 1


## @brief c3-5 FakeSocket 联调：收帧→解码→上游回调，无禁词
def test_c3_5_fakesocket_integration() -> None:
    frame = {"type": "signal", "uptime_sec": 10, "software_version": "1.0"}
    payload = (json.dumps(frame) + "\n").encode("utf-8")
    socket = SequenceSocket(chunks=[payload, b""])  # 首块完整帧，次块空表示关闭
    upstream = FakeUpstreamSink()
    layer = TcpControlLayer(
        socket=socket,
        logger=None,
        backoffSeq=[0.01],
        maxFrameSize=4096,
        heartIntervalSec=10.0,
        buildHeartbeat=lambda: {"type": "heartbeat", "uptime_sec": 1,
                                "software_version": "1.0", "camera_status": []},
        upstreamSink=upstream,
    )
    layer.start()
    for _ in range(50):
        if upstream.signals:
            break
        time.sleep(0.01)
    layer.stop()
    assert upstream.signals, "应收到解码信号"
    assert upstream.signals[0]["type"] == "signal"
    assert socket.closed


## @brief c3-6 真实 onLinkDown 触发 UP→DOWN→再 UP（修复重连线程幂等无法重启）
def test_c3_x_relink_after_down() -> None:
    frame = {"type": "signal", "uptime_sec": 10, "software_version": "1.0"}
    payload = (json.dumps(frame) + "\n").encode("utf-8")
    socket = SlowConnectSocket(recvData=payload)  # connect 休眠 0.15s，制造可观测 DOWN 窗口
    upstream = FakeUpstreamSink()
    layer = TcpControlLayer(
        socket=socket,
        logger=None,
        backoffSeq=[0.01],
        maxFrameSize=4096,
        heartIntervalSec=10.0,
        buildHeartbeat=lambda: {"type": "heartbeat", "uptime_sec": 1,
                                "software_version": "1.0", "camera_status": []},
        upstreamSink=upstream,
    )
    try:
        layer.start()
        for _ in range(100):
            if upstream.signals:
                break
            time.sleep(0.01)
        assert layer.getState() == LINK_UP
        first = len(upstream.signals)
        # 直接调用真实 onLinkDown()，驱动链路进入 DOWN（重连线程正休眠连接，状态保持 DOWN）
        layer.onLinkDown("manual", "TEST")
        assert layer.getState() == LINK_DOWN
        # 等待重连线程重新 connect 并回到 UP，且重连后解码再次产出信号
        for _ in range(200):
            if layer.getState() == LINK_UP and len(upstream.signals) > first:
                break
            time.sleep(0.01)
        assert layer.getState() == LINK_UP
        assert len(upstream.signals) > first
    finally:
        layer.stop()
