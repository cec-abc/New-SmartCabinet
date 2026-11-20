"""D 组新增单测：对照表畸形输入、装配层数值归一与降级口径、周期帧字段。

覆盖既有用例没有逐项验证的 loader 分支，以及本轮去掉 cast 后的真实类型转换。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from edge import app_init
from edge.app_init import buildCameraGroups, normalizeCameraIndices
from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingLoader
from edge.interfaces.i_camera import ICameraDevice
from edge.tests.fakes.fake_camera_device import FakeCameraDevice
from edge.tests.fakes.fake_logger import FakeLogger

## @file edge/tests/unit/test_dplus_assembly_guards.py
## @brief 对照表畸形输入、数值归一、双口径降级与协议帧字段的回归用例
## @author 袁燕

## @brief ROI 对照表十二列表头
HEADER: str = (
    "roi_id,worker_id,drawer_id,position,tool_id,required_type,"
    "marker_id,confidence,rect_x1,rect_y1,rect_x2,rect_y2"
)
## @brief 一条合法的对照表数据行
GOOD_ROW: str = "roi_01,1,A-01,A-01-01,C01-T0007,wrench,mk_8821,0.85,0,0,320,240"


## @brief 在临时目录写一份 ROI 对照表
#  @param tmpPath 临时目录
#  @param header 表头文本
#  @param rows 数据行文本列表
#  @param encoding 文件编码，默认 UTF-8
#  @return 写出的 CSV 路径
def writeRoiCsv(tmpPath: Path, header: str, rows: list[str],
                encoding: str = "utf-8") -> Path:
    path = tmpPath / "roi_binding.csv"
    path.write_text("\n".join([header, *rows]) + "\n", encoding=encoding)
    return path


## @brief 断言 loader 装载时抛出 CONFIG 配置错误，且消息含指定片段
#  @param loader 对照表装载器
#  @param csvPath 对照表路径
#  @param fragment 期望出现在异常消息里的片段
#  @return 无
def assertConfigFailure(loader: RoiBindingLoader, csvPath: Path,
                        fragment: str) -> None:
    with pytest.raises(EdgeError) as caught:
        loader.load(str(csvPath))
    assert caught.value.code is ErrorCode.CONFIG
    assert fragment in str(caught.value)


# --------------------------------------------------------------- 正常装载基线

## @brief 合法十二列表头与四行数据可正常装载
#  @param tmp_path pytest 临时目录
#  @return 无
def testValidTableLoadsFourRows(tmp_path: Path) -> None:
    rows = [GOOD_ROW] + [
        f"roi_0{index},1,A-01,A-01-0{index},C01-T000{index},wrench,"
        f"mk_882{index},0.85,0,0,320,240"
        for index in range(2, 5)
    ]
    path = writeRoiCsv(tmp_path, HEADER, rows)
    result = RoiBindingLoader(FakeLogger()).load(str(path))
    assert len(result) == 4
    assert result[0].position == "A-01-01"
    assert result[0].markerId == "mk_8821"


## @brief 表头带 UTF-8 BOM 时仍能按列名正确装载
#  @param tmp_path pytest 临时目录
#  @return 无
def testUtf8BomHeaderStillLoads(tmp_path: Path) -> None:
    path = writeRoiCsv(tmp_path, HEADER, [GOOD_ROW], encoding="utf-8-sig")
    result = RoiBindingLoader(FakeLogger()).load(str(path))
    assert len(result) == 1
    assert result[0].roiId == "roi_01"


# --------------------------------------------------------------- 文件与表头畸形

## @brief 对照表文件不存在时判 CONFIG 并写明路径
#  @param tmp_path pytest 临时目录
#  @return 无
def testMissingTableFailsFast(tmp_path: Path) -> None:
    with pytest.raises(EdgeError) as caught:
        RoiBindingLoader(FakeLogger()).load(str(tmp_path / "missing.csv"))
    assert caught.value.code is ErrorCode.CONFIG
    assert "对照表文件不存在" in str(caught.value)


## @brief 缺少必填列时判 CONFIG 并列出缺的列名
#  @param tmp_path pytest 临时目录
#  @return 无
def testMissingRequiredColumnFailsFast(tmp_path: Path) -> None:
    header = HEADER.replace("marker_id,", "")
    path = writeRoiCsv(tmp_path, header, [GOOD_ROW])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "对照表缺少列")


## @brief 只有表头没有数据行时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
def testHeaderOnlyTableFailsFast(tmp_path: Path) -> None:
    path = writeRoiCsv(tmp_path, HEADER, [])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "没有数据行")


# --------------------------------------------------------------- 数据行畸形

## @brief 必填列留空时判 CONFIG 并写明列名
#  @param tmp_path pytest 临时目录
#  @return 无
@pytest.mark.parametrize(
    "row,column",
    [
        ("roi_01,1,A-01,A-01-01,C01-T0007,wrench,,0.85,0,0,320,240", "marker_id"),
        (",1,A-01,A-01-01,C01-T0007,wrench,mk_8821,0.85,0,0,320,240", "roi_id"),
        ("roi_01,1,,A-01-01,C01-T0007,wrench,mk_8821,0.85,0,0,320,240", "drawer_id"),
        ("roi_01,1,A-01,,C01-T0007,wrench,mk_8821,0.85,0,0,320,240", "position"),
    ],
)
def testEmptyRequiredCellFailsFast(tmp_path: Path, row: str, column: str) -> None:
    path = writeRoiCsv(tmp_path, HEADER, [row])
    with pytest.raises(EdgeError) as caught:
        RoiBindingLoader(FakeLogger()).load(str(path))
    assert caught.value.code is ErrorCode.CONFIG
    assert "必填列为空" in str(caught.value)
    assert column in str(caught.value)


## @brief 矩形右下角不大于左上角时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
@pytest.mark.parametrize(
    "row",
    [
        "roi_01,1,A-01,A-01-01,C01-T0007,wrench,mk_8821,0.85,0,0,0,240",
        "roi_01,1,A-01,A-01-01,C01-T0007,wrench,mk_8821,0.85,0,0,320,0",
        "roi_01,1,A-01,A-01-01,C01-T0007,wrench,mk_8821,0.85,320,0,0,240",
    ],
)
def testInvalidRectangleFailsFast(tmp_path: Path, row: str) -> None:
    path = writeRoiCsv(tmp_path, HEADER, [row])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "矩形非法")


## @brief 货位号重复时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
def testDuplicatePositionFailsFast(tmp_path: Path) -> None:
    duplicate = GOOD_ROW.replace("roi_01", "roi_02")
    path = writeRoiCsv(tmp_path, HEADER, [GOOD_ROW, duplicate])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "货位重复")


## @brief 线程编号不是数字时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
def testNonNumericWorkerIdFailsFast(tmp_path: Path) -> None:
    row = GOOD_ROW.replace(",1,A-01", ",abc,A-01")
    path = writeRoiCsv(tmp_path, HEADER, [row])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "工作线程编号非法")


## @brief 线程编号超出 1 到 4 的基础区间时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
def testWorkerIdBeyondBaseRangeFailsFast(tmp_path: Path) -> None:
    row = GOOD_ROW.replace(",1,A-01", ",9,A-01")
    path = writeRoiCsv(tmp_path, HEADER, [row])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "工作线程编号越界")


## @brief 置信度不是数字时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
def testNonNumericConfidenceFailsFast(tmp_path: Path) -> None:
    row = GOOD_ROW.replace(",0.85,", ",low,")
    path = writeRoiCsv(tmp_path, HEADER, [row])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "置信度非法")


## @brief 置信度超出 0 到 1 时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
@pytest.mark.parametrize("value", ["1.5", "-0.1"])
def testConfidenceOutOfRangeFailsFast(tmp_path: Path, value: str) -> None:
    row = GOOD_ROW.replace(",0.85,", f",{value},")
    path = writeRoiCsv(tmp_path, HEADER, [row])
    assertConfigFailure(RoiBindingLoader(FakeLogger()), path, "置信度越界")


## @brief 坐标不是整数时判 CONFIG 并写明列名
#  @param tmp_path pytest 临时目录
#  @return 无
def testNonNumericRectCoordinateFailsFast(tmp_path: Path) -> None:
    row = GOOD_ROW.replace(",0.85,0,0,320,240", ",0.85,nope,0,320,240")
    path = writeRoiCsv(tmp_path, HEADER, [row])
    with pytest.raises(EdgeError) as caught:
        RoiBindingLoader(FakeLogger()).load(str(path))
    assert caught.value.code is ErrorCode.CONFIG
    assert "坐标非法" in str(caught.value)
    assert "rect_x1" in str(caught.value)


## @brief 置信度留空时按 0.85 缺省值装载
#  @param tmp_path pytest 临时目录
#  @return 无
def testEmptyConfidenceUsesDefault(tmp_path: Path) -> None:
    row = GOOD_ROW.replace(",0.85,", ",,")
    path = writeRoiCsv(tmp_path, HEADER, [row])
    result = RoiBindingLoader(FakeLogger()).load(str(path))
    assert result[0].confidence == 0.85


# --------------------------------------------------------------- 类别组合表

## @brief 类别组合表必填列为空时判 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
@pytest.mark.parametrize(
    "row",
    [
        '"person,surfboard",',
        ',"滑板人偶"',
    ],
)
def testClassItemMapEmptyRequiredCellFailsFast(tmp_path: Path, row: str) -> None:
    path = tmp_path / "class_item_map.csv"
    path.write_text("class_names,item_name\n" + row + "\n", encoding="utf-8")
    with pytest.raises(EdgeError) as caught:
        RoiBindingLoader(FakeLogger()).loadClassItemMap(str(path))
    assert caught.value.code is ErrorCode.CONFIG
    assert "类别组合表必填列为空" in str(caught.value)


## @brief 类别组合按逗号拆成集合，顺序无关
#  @param tmp_path pytest 临时目录
#  @return 无
def testClassItemMapSplitsNamesIntoFrozenSet(tmp_path: Path) -> None:
    path = tmp_path / "class_item_map.csv"
    path.write_text('class_names,item_name\n"person,surfboard",滑板人偶\n',
                    encoding="utf-8")
    mapping = RoiBindingLoader(FakeLogger()).loadClassItemMap(str(path))
    assert mapping[frozenset({"person", "surfboard"})] == "滑板人偶"


# --------------------------------------------------------------- 退避序列归一

## @brief 整数字面量归一成浮点秒数列表，元素都是 float
#  @return 无
def testBackoffSeqConvertsIntsToFloats() -> None:
    result = app_init.normalizeBackoffSeq([1, 2, 4, 8, 16, 30])
    assert result == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
    assert all(type(value) is float for value in result)


## @brief 配置里只写一个数值时也能归一成单元素列表
#  @return 无
@pytest.mark.parametrize("raw,expected", [(3, [3.0]), (2.5, [2.5])])
def testBackoffSeqAcceptsSingleNumber(raw: object, expected: list[float]) -> None:
    assert app_init.normalizeBackoffSeq(raw) == expected


## @brief 退避序列取值畸形时判 CONFIG 并写明原因
#  @return 无
@pytest.mark.parametrize(
    "raw,fragment",
    [
        (True, "取值非法"),
        ("1,2,3", "取值非法"),
        ([], "取值非法"),
        (None, "取值非法"),
        ([1, "2"], "必须是数值"),
        ([1, True], "必须是数值"),
    ],
)
def testBackoffSeqRejectsMalformedValues(raw: object, fragment: str) -> None:
    with pytest.raises(EdgeError) as caught:
        app_init.normalizeBackoffSeq(raw)
    assert caught.value.code is ErrorCode.CONFIG
    assert fragment in str(caught.value)


## @brief 装配层不再读取 config.ini 里已废弃的查表字典键
#  @return 无
def testDeprecatedIniLookupKeysAreNotReadAnymore() -> None:
    source = Path(app_init.__file__).read_text(encoding="utf-8")
    assert 'config.get("recognition", "roi_config"' not in source
    assert 'config.get("recognition", "class_item_map"' not in source
    assert 'config.get("recognition", "roi_bind_map"' not in source
    assert "cast(" not in source


## @brief 识别门面保留的三个查表入参固定为空字典
#  @return 无
def testEmptyLookupMapsAreEmptyDicts() -> None:
    assert app_init.EMPTY_ROI_CONFIG == {}
    assert app_init.EMPTY_CLASS_ITEM_MAP == {}
    assert app_init.EMPTY_ROI_BIND_MAP == {}


# --------------------------------------------------------------- 双口径降级

## @brief 严格口径下装载不到对照表时抛出 CONFIG
#  @param tmp_path pytest 临时目录
#  @return 无
def testStrictBindingLoadFailsFastOnMissingTable(tmp_path: Path) -> None:
    with pytest.raises(EdgeError) as caught:
        app_init.loadRoiBindingRows(
            RoiBindingLoader(FakeLogger()), str(tmp_path / "missing.csv"),
        )
    assert caught.value.code is ErrorCode.CONFIG
    assert "未装载 ROI 对照表" in str(caught.value)


## @brief 降级口径下装载不到对照表时返回空清单并记 error 日志
#  @param tmp_path pytest 临时目录
#  @return 无
def testLenientBindingLoadDegradesToEmptyRows(tmp_path: Path) -> None:
    logger = FakeLogger()
    rows = app_init.loadRoiBindingRowsLenient(
        RoiBindingLoader(logger), str(tmp_path / "missing.csv"), logger,
    )
    assert rows == []
    assert any("识别能力不可用" in record[1] for record in logger.errorRecords)


## @brief 识别能力不可用时识别请求走空清单出口，不触发采集
#  @return 无
## @brief 记录一次采集触发，并回报触发成功
#  @param requestId 请求编号
#  @param triggered 触发记录列表
#  @return 恒为 True
def recordTrigger(requestId: str, triggered: list[str]) -> bool:
    triggered.append(requestId)
    return True


## @brief 造出指定路数的摄像头状态
#  @param count 路数
#  @return 摄像头状态列表
def buildCameraStatus(count: int) -> list[dict[str, object]]:
    return [
        {"camera_id": f"CAM{index + 1}", "status": "ok"} for index in range(count)
    ]


## @brief 识别能力不可用时识别请求走空清单出口，不触发采集
#  @return 无
def testUnavailableCapabilityEmitsEmptyAckWithoutCapture() -> None:
    emitted: list[str] = []
    triggered: list[str] = []
    capability = app_init.RecognitionCapability()
    capability.markUnavailable()
    capability.bindEmptyAckEmitter(emitted.append)
    trigger = app_init.CaptureTrigger()
    trigger.bind(
        lambda requestId: recordTrigger(requestId, triggered),
    )
    app_init.handleRecognizeReq({"type": "recognize_req", "request_id": "req-1"},
                                trigger, capability)
    assert emitted == ["req-1"]
    assert triggered == []


## @brief 识别能力可用时识别请求触发采集并透传请求编号
#  @return 无
def testAvailableCapabilityTriggersCapture() -> None:
    triggered: list[str] = []
    trigger = app_init.CaptureTrigger()
    trigger.bind(
        lambda requestId: recordTrigger(requestId, triggered),
    )
    app_init.handleRecognizeReq({"type": "recognize_req", "request_id": "req-2"},
                                trigger, app_init.RecognitionCapability())
    assert triggered == ["req-2"]


# --------------------------------------------------------------- 协议帧字段

## @brief 周期帧四字段与上位机 parsePeriodic 读取的字段一致
#  @return 无
def testPeriodicFrameKeysMatchHostReader() -> None:
    frame = app_init.buildPeriodicFrame(
        lambda: buildCameraStatus(8), 0.0, "edge-0.1.0",
    )()
    assert set(frame) == {"type", "uptime_sec", "software_version", "camera_status"}
    assert frame["type"] == "periodic"
    assert isinstance(frame["uptime_sec"], int)
    cameraStatus = frame["camera_status"]
    assert isinstance(cameraStatus, list) and len(cameraStatus) == 8


## @brief 周期帧 camera_status 路数随 camera_indices 个数变化
#  @return 无
@pytest.mark.parametrize("count", [1, 2, 4, 8])
def testPeriodicCameraStatusCountFollowsIndices(count: int) -> None:
    indices = normalizeCameraIndices(list(range(count)))
    mode = app_init.resolveCaptureMode("auto", len(indices))
    devices: list[ICameraDevice] = [FakeCameraDevice(b"frame") for _ in indices]
    groups = buildCameraGroups(devices, mode)
    frame = app_init.buildPeriodicFrame(
        lambda: buildCameraStatus(len(indices)), 0.0, "edge-0.1.0",
    )()
    cameraStatus = frame["camera_status"]
    assert isinstance(cameraStatus, list) and len(cameraStatus) == len(indices)
    assert sum(len(group) for group in groups) == len(indices)
