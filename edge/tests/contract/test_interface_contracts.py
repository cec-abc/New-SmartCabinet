"""接口契约验证：全部 Fake 可实例化，并跑通每个接口方法。"""
from __future__ import annotations

import pytest

from edge.interfaces.i_camera import ICameraDevice
from edge.interfaces.i_config import IConfig
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_platform import IPlatformAdapter
from edge.interfaces.i_recognition_engine import IRecognitionEngine
from edge.interfaces.i_sinks import ICaptureSink, IRecognitionSink, SignalSink
from edge.interfaces.i_socket import ISocket
from edge.interfaces.i_thread import IThread
from edge.tests.fakes.fake_camera_device import FakeCameraDevice
from edge.tests.fakes.fake_config import FakeConfig
from edge.tests.fakes.fake_logger import FakeLogger
from edge.tests.fakes.fake_platform_adapter import FakePlatformAdapter
from edge.tests.fakes.fake_recognition_engine import FakeRecognitionEngine
from edge.tests.fakes.fake_sinks import FakeCaptureSink, FakeRecognitionSink, FakeSignalSink
from edge.tests.fakes.fake_socket import FakeSocket
from edge.tests.fakes.fake_thread import FakeThread


## @brief 全部 Fake 可实例化且满足对应接口契约
def testAllFakesSatisfyContracts() -> None:
    assert isinstance(FakeConfig(), IConfig)
    assert isinstance(FakeLogger(), ILogger)
    assert isinstance(FakeThread(), IThread)
    assert isinstance(FakeSocket(), ISocket)
    assert isinstance(FakeCameraDevice(), ICameraDevice)
    assert isinstance(FakeRecognitionEngine(), IRecognitionEngine)
    assert isinstance(FakePlatformAdapter(), IPlatformAdapter)
    assert isinstance(FakeSignalSink(), SignalSink)
    assert isinstance(FakeCaptureSink(), ICaptureSink)
    assert isinstance(FakeRecognitionSink(), IRecognitionSink)


## @brief 接口为抽象基类，不能直接实例化
def testInterfacesAreAbstract() -> None:
    with pytest.raises(TypeError):
        ILogger()  # type: ignore[abstract]


## @brief 日志 Fake 的四个对外方法均可调用并记录
def testFakeLoggerRecordsFourMethods() -> None:
    logger = FakeLogger()
    logger.rx("tcp", b"{}")
    logger.tx("tcp", {"type": "ack"})
    logger.info("tcp", "hello")
    logger.error("tcp", "boom", Exception("x"))
    assert logger.rxRecords == [("tcp", b"{}")]
    assert len(logger.txRecords) == 1
    assert logger.txRecords[0][0] == "tcp"
    assert logger.infoRecords == [("tcp", "hello")]
    assert logger.errorRecords[0][2] is not None


## @brief 逐个跑通其余 Fake 的方法，确认签名可用
def testAllFakeMethodsCallable() -> None:
    config = FakeConfig({"comm.port": 9000})
    assert config.get("comm", "port") == 9000
    assert config.get("comm", "missing", 1) == 1

    thread = FakeThread()
    thread.start()
    assert thread.isRunning()
    thread.stop(1.0)
    assert not thread.isRunning()
    assert thread.stopTimeouts == [1.0]

    socket = FakeSocket(b"frame")
    socket.connect()
    assert socket.recv() == b"frame"
    assert socket.send(b"ack") is True
    socket.close()
    assert socket.closed

    camera = FakeCameraDevice()
    camera.open()
    assert camera.readFrame() == b"frame"
    assert camera.getStatus()["opened"] is True
    camera.close()

    engine = FakeRecognitionEngine()
    engine.loadModel("model.onnx")
    assert engine.loadedPaths == ["model.onnx"]
    assert engine.infer(b"image") == []

    adapter = FakePlatformAdapter()
    assert adapter.joinPath("a", "b") == "a/b"
    assert adapter.newline() == "\n"
    assert "interrupt" in adapter.signalMap()
    assert adapter.monotonicClock() >= 0.0
    assert adapter.lockFile("edge.lock") is None
    assert adapter.lockCalls == ["edge.lock"]


## @brief 三个 Sink Fake 均能接收对应事件
def testAllSinkFakesCallable() -> None:
    signalSink = FakeSignalSink()
    signalSink.onSignalDecoded({"type": "recognize"})
    signalSink.onFrameError(Exception("bad frame"))
    signalSink.onLinkDown("timeout", "HEART")
    signalSink.onLinkUp()
    assert len(signalSink.signals) == 1
    assert len(signalSink.frameErrors) == 1
    assert signalSink.linkDownEvents == [("timeout", "HEART")]
    assert signalSink.linkUpCount == 1

    captureSink = FakeCaptureSink()
    captureSink.onCaptureSuccess(1, "left.jpg")
    captureSink.onCaptureError(1, Exception("capture"))
    assert captureSink.successEvents == [(1, "left.jpg")]
    assert len(captureSink.errorEvents) == 1

    recognitionSink = FakeRecognitionSink()
    recognitionSink.onRecognitionResult(1, {"type": "recognize_ack"}, "req-1")
    recognitionSink.onRecognitionError(1, Exception("infer"))
    assert recognitionSink.resultEvents[0][2] == "req-1"
    assert len(recognitionSink.errorEvents) == 1
