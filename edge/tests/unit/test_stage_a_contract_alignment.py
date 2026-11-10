"""阶段 a 补强单测：接口契约四要素、Fake 签名对齐、FrameData 处置、9 处字段标注。"""
from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any

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

## @brief edge/ 包根目录（本文件位于 edge/tests/unit/，parents[2] 即 edge/）
EDGE_ROOT: Path = Path(__file__).resolve().parents[2]
INTERFACES_DIR: Path = EDGE_ROOT / "interfaces"
FAKES_DIR: Path = EDGE_ROOT / "tests" / "fakes"

## @brief 10 个接口 ABC 类，分布于 8 个 i_*.py 文件（i_sinks.py 含 3 个）
INTERFACE_CLASSES: tuple[Any, ...] = (
    ICameraDevice,
    IConfig,
    ILogger,
    IPlatformAdapter,
    IRecognitionEngine,
    SignalSink,
    ICaptureSink,
    IRecognitionSink,
    ISocket,
    IThread,
)

## @brief a-2 的 31 对签名逐一对齐表：(接口类, Fake 类, 方法名, 参数名, 返回注解字符串)
ALIGNMENT_CASES: tuple[tuple[Any, Any, str, tuple[str, ...], str], ...] = (
    (IConfig, FakeConfig, "get", ("self", "section", "key", "default"), "Any"),
    (ILogger, FakeLogger, "rx", ("self", "module", "data"), "None"),
    (ILogger, FakeLogger, "tx", ("self", "module", "data"), "None"),
    (ILogger, FakeLogger, "info", ("self", "module", "msg"), "None"),
    (ILogger, FakeLogger, "error", ("self", "module", "msg", "exception"), "None"),
    (IThread, FakeThread, "start", ("self",), "None"),
    (IThread, FakeThread, "stop", ("self", "timeout"), "None"),
    (IThread, FakeThread, "isRunning", ("self",), "bool"),
    (ISocket, FakeSocket, "connect", ("self",), "None"),
    (ISocket, FakeSocket, "recv", ("self",), "bytes"),
    (ISocket, FakeSocket, "send", ("self", "data"), "bool"),
    (ISocket, FakeSocket, "close", ("self",), "None"),
    (ICameraDevice, FakeCameraDevice, "open", ("self",), "None"),
    (ICameraDevice, FakeCameraDevice, "readFrame", ("self",), "FrameImage | None"),
    (ICameraDevice, FakeCameraDevice, "close", ("self",), "None"),
    (ICameraDevice, FakeCameraDevice, "getStatus", ("self",), "CameraStatus"),
    (
        IRecognitionEngine, FakeRecognitionEngine, "loadModel",
        ("self", "path"), "None",
    ),
    (
        IRecognitionEngine, FakeRecognitionEngine, "infer",
        ("self", "image"), "list[DetectionItem]",
    ),
    (
        IPlatformAdapter, FakePlatformAdapter, "joinPath",
        ("self", "parts"), "str",
    ),
    (
        IPlatformAdapter, FakePlatformAdapter, "newline",
        ("self",), "str",
    ),
    (
        IPlatformAdapter, FakePlatformAdapter, "signalMap",
        ("self",), "SignalMapping",
    ),
    (
        IPlatformAdapter, FakePlatformAdapter, "monotonicClock",
        ("self",), "float",
    ),
    (
        IPlatformAdapter, FakePlatformAdapter, "lockFile",
        ("self", "filePath"), "BinaryIO | None",
    ),
    (SignalSink, FakeSignalSink, "onSignalDecoded", ("self", "signal"), "None"),
    (SignalSink, FakeSignalSink, "onFrameError", ("self", "exception"), "None"),
    (SignalSink, FakeSignalSink, "onLinkDown", ("self", "reason", "source"), "None"),
    (SignalSink, FakeSignalSink, "onLinkUp", ("self",), "None"),
    (
        ICaptureSink, FakeCaptureSink, "onCaptureSuccess",
        ("self", "workerId", "path"), "None",
    ),
    (
        ICaptureSink, FakeCaptureSink, "onCaptureError",
        ("self", "workerId", "exception"), "None",
    ),
    (
        IRecognitionSink, FakeRecognitionSink, "onRecognitionResult",
        ("self", "workerId", "ack", "requestId"), "None",
    ),
    (
        IRecognitionSink, FakeRecognitionSink, "onRecognitionError",
        ("self", "workerId", "exception"), "None",
    ),
)


## @brief 反射断言 31 个抽象方法体只有隐式 None 常量（零实现、无逻辑分支）
# 对应验收项 a-1：interfaces/ 零实现
def testInterfaceAbstractMethodBodiesCarryNoImplementation() -> None:
    checked: list[str] = []
    for cls in INTERFACE_CLASSES:
        for methodName in sorted(cls.__abstractmethods__):
            method = getattr(cls, methodName)
            assert method.__isabstractmethod__ is True
            assert method.__code__.co_consts == (None,)
            checked.append(f"{cls.__name__}.{methodName}")
    assert len(checked) == 31
    assert checked[0] == "ICameraDevice.close"
    assert checked[-1] == "IThread.stop"


## @brief 断言每个接口类的公开方法名精确等于 L1 §3 表，且无下划线 / 无首字母大写
# 对应验收项 a-1：全 camelCase
def testInterfaceMethodNamesAreAllCamelCase() -> None:
    expected: dict[str, tuple[str, ...]] = {
        "ICameraDevice": ("close", "getStatus", "open", "readFrame"),
        "IConfig": ("get",),
        "ILogger": ("error", "info", "rx", "tx"),
        "IPlatformAdapter": ("joinPath", "lockFile", "monotonicClock", "newline", "signalMap"),
        "IRecognitionEngine": ("infer", "loadModel"),
        "SignalSink": ("onFrameError", "onLinkDown", "onLinkUp", "onSignalDecoded"),
        "ICaptureSink": ("onCaptureError", "onCaptureSuccess"),
        "IRecognitionSink": ("onRecognitionError", "onRecognitionResult"),
        "ISocket": ("close", "connect", "recv", "send"),
        "IThread": ("isRunning", "start", "stop"),
    }
    for cls in INTERFACE_CLASSES:
        public = tuple(
            sorted(
                name
                for name in vars(cls)
                if not name.startswith("_") and callable(getattr(cls, name))
            )
        )
        assert public == expected[cls.__name__], cls.__name__
        violations = [name for name in public if "_" in name or name[0].isupper()]
        assert violations == [], cls.__name__
    assert len(expected) == 10


## @brief AST 逐文件 import 清单 + 运行时模块对象反射双证据，断言零业务 import
# 对应验收项 a-1：零业务 import
def testInterfaceModulesImportNoBusinessModules() -> None:
    expected: dict[str, list[str]] = {
        "__init__": ["__future__"],
        "i_camera": ["__future__", "abc"],
        "i_config": ["__future__", "abc", "typing"],
        "i_logger": ["__future__", "abc"],
        "i_platform": ["__future__", "abc", "typing"],
        "i_recognition_engine": ["__future__", "abc", "edge.interfaces.i_camera"],
        "i_sinks": ["__future__", "abc"],
        "i_socket": ["__future__", "abc"],
        "i_thread": ["__future__", "abc"],
    }
    businessPrefixes: tuple[str, ...] = (
        "edge.platform",
        "edge.infra",
        "edge.modules",
        "edge.control",
        "cv2",
        "numpy",
        "configparser",
        "vision_core",
        "argparse",
        "threading",
    )
    assert sorted(path.stem for path in INTERFACES_DIR.glob("*.py")) == sorted(expected)
    for stem, modules in expected.items():
        source = (INTERFACES_DIR / f"{stem}.py").read_text(encoding="utf-8")
        imports: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert sorted(imports) == modules, stem
        assert [name for name in imports if name.startswith(businessPrefixes)] == [], stem
        fullName = "edge.interfaces" if stem == "__init__" else f"edge.interfaces.{stem}"
        module = importlib.import_module(fullName)
        leaked = [
            name
            for name, value in vars(module).items()
            if inspect.ismodule(value) and value.__name__.startswith(businessPrefixes)
        ]
        assert leaked == [], fullName


## @brief 逐文件断言 Doxygen 标记具体计数与模块 docstring（注释不在 AST 中，故用源码计数）
# 对应验收项 a-1：Doxygen 注释覆盖
def testInterfaceDoxygenMarkersCovered() -> None:
    expected: dict[str, tuple[int, int, int]] = {
        "__init__": (0, 0, 0),
        "i_camera": (7, 0, 4),
        "i_config": (2, 3, 1),
        "i_logger": (5, 9, 4),
        "i_platform": (7, 2, 5),
        "i_recognition_engine": (4, 2, 2),
        "i_sinks": (13, 13, 8),
        "i_socket": (5, 1, 4),
        "i_thread": (4, 1, 3),
    }
    totalBrief = 0
    for stem, (brief, param, ret) in expected.items():
        source = (INTERFACES_DIR / f"{stem}.py").read_text(encoding="utf-8")
        assert source.count("## @brief") == brief, stem
        assert source.count("@param") == param, stem
        assert source.count("@return") == ret, stem
        assert (ast.get_docstring(ast.parse(source)) or "") != "", stem
        totalBrief += brief
    assert totalBrief == 47


## @brief 31 对方法逐一比较 inspect.signature，参数名与返回注解同时锚定具体值
# 对应验收项 a-2：8 个 Fake 与 8 个接口签名逐一对齐
def testAllFakeMethodSignaturesAlignWithInterfaces() -> None:
    aligned: list[str] = []
    for iface, fake, method, params, returnAnnotation in ALIGNMENT_CASES:
        ifaceSig = inspect.signature(getattr(iface, method))
        fakeSig = inspect.signature(getattr(fake, method))
        assert tuple(ifaceSig.parameters) == params, f"{iface.__name__}.{method}"
        assert ifaceSig.return_annotation == returnAnnotation, f"{iface.__name__}.{method}"
        assert fakeSig == ifaceSig, f"{iface.__name__}.{method}"
        aligned.append(f"{iface.__name__}.{method}")
    assert len(aligned) == 31
    assert aligned[0] == "IConfig.get"
    assert aligned[-1] == "IRecognitionSink.onRecognitionError"
    assert len({case[1] for case in ALIGNMENT_CASES}) == 10
    assert len(list(INTERFACES_DIR.glob("i_*.py"))) == 8
    assert len(list(FAKES_DIR.glob("fake_*.py"))) == 8


## @brief 10 个 Fake 均可实例化且 isinstance / issubclass 对应接口契约
# 对应验收项 a-2：8 个 Fake 与 8 个接口签名逐一对齐
def testAllFakesAreInstantiableSubclassesOfInterfaces() -> None:
    pairs: tuple[tuple[Any, Any], ...] = (
        (FakeConfig, IConfig),
        (FakeLogger, ILogger),
        (FakeThread, IThread),
        (FakeSocket, ISocket),
        (FakeCameraDevice, ICameraDevice),
        (FakeRecognitionEngine, IRecognitionEngine),
        (FakePlatformAdapter, IPlatformAdapter),
        (FakeSignalSink, SignalSink),
        (FakeCaptureSink, ICaptureSink),
        (FakeRecognitionSink, IRecognitionSink),
    )
    results: list[str] = []
    for fake, iface in pairs:
        instance = fake()
        assert isinstance(instance, iface) is True
        assert issubclass(fake, iface) is True
        results.append(f"{fake.__name__}:{iface.__name__}")
    assert len(results) == 10
    assert results[0] == "FakeConfig:IConfig"


## @brief FrameData 断裂结论与处置：L1 未定义、Fake 只导入 ILogger、四方法可调用并记录
# 对应验收项 a-2：fake_logger.py 的 FrameData 断裂有明确结论与处置
def testFakeLoggerFrameDataBreakageIsResolved() -> None:
    iLoggerModule = importlib.import_module("edge.interfaces.i_logger")
    assert [name for name in vars(iLoggerModule) if name == "FrameData"] == []
    fakeLoggerSource = (FAKES_DIR / "fake_logger.py").read_text(encoding="utf-8")
    assert fakeLoggerSource.count("FrameData") == 0
    imported: list[str] = []
    for node in ast.walk(ast.parse(fakeLoggerSource)):
        if isinstance(node, ast.ImportFrom) and node.module == "edge.interfaces.i_logger":
            imported.extend(alias.name for alias in node.names)
    assert imported == ["ILogger"]
    logger = FakeLogger()
    assert isinstance(logger, ILogger) is True
    logger.rx("tcp", b"{}")
    logger.tx("tcp", b"ack")
    assert logger.rxRecords == [("tcp", b"{}")]
    assert logger.txRecords == [("tcp", b"ack")]
    assert inspect.signature(ILogger.rx) == inspect.signature(FakeLogger.rx)


## @brief 反射收集两个契约测试模块的 10 个 testXxx，并核验 windowsOnly typed wrapper 签名
# 对应验收项 a-3：契约测试可收集、可执行、通过
def testContractTestFunctionsAreCollectableAndExecutable() -> None:
    expected: dict[str, list[str]] = {
        "edge.tests.contract.test_interface_contracts": [
            "testAllFakeMethodsCallable",
            "testAllFakesSatisfyContracts",
            "testAllSinkFakesCallable",
            "testFakeLoggerRecordsFourMethods",
            "testInterfacesAreAbstract",
        ],
        "edge.tests.contract.test_phase0_foundation": [
            "testEdgeErrorCarriesCodeName",
            "testFactoryReturnsWindowsAdapter",
            "testLinuxAdapterSkeletonRaises",
            "testLinuxSkeletonIsConvertedToEdgeError",
            "testSecondProcessCannotAcquireLock",
        ],
    }
    count = 0
    for moduleName, names in expected.items():
        module = importlib.import_module(moduleName)
        collected = sorted(
            name
            for name, _ in inspect.getmembers(module, inspect.isfunction)
            if name.startswith("test")
        )
        assert collected == names, moduleName
        for name in names:
            assert callable(getattr(module, name)) is True
            count += 1
    assert count == 10
    foundation = importlib.import_module("edge.tests.contract.test_phase0_foundation")
    windowsOnly = getattr(foundation, "windowsOnly")
    assert tuple(inspect.signature(windowsOnly).parameters) == ("reason",)


## @brief 固定 mypy 3.9 strict 配置口径；通过与否由报告 ④ 的 mypy 工具链实跑举证
# 对应验收项 a-3：mypy（3.9 strict）通过
def testMypyConfigTargetsPython39Strict() -> None:
    lines = (EDGE_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    pythonVersion = [line.strip() for line in lines if line.strip().startswith("python_version")]
    strict = [line.strip() for line in lines if line.strip().startswith("strict")]
    assert pythonVersion == ['python_version = "3.9"']
    assert strict == ["strict = true"]


## @brief AST 断言 9 处字段为 AnnAssign（显式类型标注）且标注文本逐项等于具体值
# 对应验收项 a-4：已知 9 处 Fake 字段类型标注缺口有结论（已补齐）
def testNineFakeFieldAnnotationsAreExplicit() -> None:
    expected: dict[str, dict[str, str]] = {
        "fake_camera_device": {
            "frame": "FrameImage | None",
            "opened": "bool",
            "closed": "bool",
        },
        "fake_sinks": {"linkUpCount": "int"},
        "fake_socket": {"recvData": "bytes", "connected": "bool", "closed": "bool"},
        "fake_thread": {"startCount": "int", "running": "bool"},
    }
    total = 0
    for stem, fields in expected.items():
        source = (FAKES_DIR / f"{stem}.py").read_text(encoding="utf-8")
        annotated: dict[str, str] = {}
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.AnnAssign):
                target = node.target
                if isinstance(target, ast.Attribute):
                    owner = target.value
                    if isinstance(owner, ast.Name) and owner.id == "self":
                        annotated[target.attr] = ast.unparse(node.annotation)
        for fieldName, annotation in fields.items():
            assert annotated.get(fieldName) == annotation, f"{stem}.{fieldName}"
            total += 1
    assert total == 9
    assert len(expected) == 4


## @brief 9 处字段补齐后运行时初值与回调行为不变（具体值 / 枚举 / 回调次数）
# 对应验收项 a-4：已知 9 处 Fake 字段类型标注缺口有结论（已补齐）
def testNineFakeFieldsRetainConcreteInitialValues() -> None:
    camera = FakeCameraDevice()
    assert camera.frame == b"frame"
    assert camera.opened is False
    assert camera.closed is False
    camera.open()
    status = camera.getStatus()
    assert len(status) == 1
    assert status["opened"] is True
    camera.close()
    assert camera.closed is True

    signalSink = FakeSignalSink()
    assert signalSink.linkUpCount == 0
    signalSink.onLinkUp()
    assert signalSink.linkUpCount == 1

    socket = FakeSocket()
    assert socket.recvData == b""
    assert socket.connected is False
    assert socket.closed is False
    socket.connect()
    socket.send(b"ack")
    socket.close()
    assert socket.sentFrames == [b"ack"]
    assert socket.connected is True
    assert socket.closed is True

    thread = FakeThread()
    assert thread.startCount == 0
    assert thread.running is False
    thread.start()
    assert thread.startCount == 1
    assert thread.running is True
    thread.stop(1.0)
    assert thread.stopTimeouts == [1.0]
    assert thread.running is False
