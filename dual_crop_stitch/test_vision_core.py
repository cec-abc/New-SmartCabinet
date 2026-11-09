# @file test_vision_core.py
# @brief vision_core.py 的严密单元测试（分支覆盖率目标 100%）。
#
# @details
# 使用 pytest + unittest.mock，彻底 Mock 掉外部 IO 与 YOLO 模型，不读取本地图片、
# 不加载 .onnx、不发网络请求，测试完全离线且秒级完成。
# 覆盖：crop_images / stitch_images / check_roi_containment / check_business_logic /
# yolo_init / yolo_detect 的全部分支（含各 for 循环的“跳过/进入”与布尔短路分支）。
# 注释使用 # 风格，符合项目 Doxygen 规范（不使用三引号文档字符串）。

import os
import sys
import time
import types

import json

import numpy as np
import pytest
import unittest.mock as mock

# 将 src/ 加入导入路径，使 import vision_core 可行（无需编译 .so/.pyd）
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# 离线兜底：保证 patch("ultralytics.YOLO") 可定位模块，无需真实安装 ultralytics
if "ultralytics" not in sys.modules:
    _fake_ultra = types.ModuleType("ultralytics")
    _fake_ultra.YOLO = mock.MagicMock()
    sys.modules["ultralytics"] = _fake_ultra

# 必须在路径就绪后再导入被测模块
import vision_core
from tcp_comm import TcpComm
from vision_core import (
    Detection,
    CropResult,
    SimpleStitchResult,
    RoiCheckResult,
    crop_images,
    stitch_images,
    yolo_init,
    yolo_detect,
    check_roi_containment,
    check_business_logic,
    self_check,
)


# ---------------------------------------------------------------------------
# 公共辅助
# ---------------------------------------------------------------------------

def _img(h: int = 100, w: int = 100) -> np.ndarray:
    # 生成一张纯黑 BGR 测试图；尺寸 (h, w, 3)；单位: 像素
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_model_mock(num_boxes: int) -> mock.MagicMock:
    # 构造一个“假的 YOLO 模型实例”，其 predict 返回 num_boxes 个检测框
    model = mock.MagicMock()
    boxes = mock.MagicMock()
    boxes.xyxy = [np.array([10.0, 20.0, 30.0, 40.0]) for _ in range(num_boxes)]
    boxes.cls = [np.array([0]) for _ in range(num_boxes)]
    boxes.conf = [np.array([0.9]) for _ in range(num_boxes)]
    # len(boxes) 决定 yolo_detect 内 for 循环的执行次数（覆盖 0 次与 >=1 次两分支）
    boxes.__len__.return_value = num_boxes
    result0 = mock.MagicMock(boxes=boxes)
    model.predict.return_value = [result0]
    model.names = {0: "person"}
    return model


def _init_yolo(model_mock: mock.MagicMock) -> None:
    # 用 Mock 替换 ultralytics.YOLO，完成 yolo_init（写入模块级 _model）
    with mock.patch("ultralytics.YOLO", return_value=model_mock):
        vision_core.yolo_init("dummy.onnx", 0.5, 640)


# 接口单元级耗时累计表：键为接口名，值为累计耗时（秒）
_INTERFACE_TIMES: dict = {}


def _timed(name: str, fn, *args, **kwargs):
    # 计时并调用被测函数，把该接口的耗时累加到全局表，并即时打印单次耗时
    t0 = time.perf_counter()
    try:
        return fn(*args, **kwargs)
    finally:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        _INTERFACE_TIMES[name] = _INTERFACE_TIMES.get(name, 0.0) + dt_ms / 1000.0
        print(f"[耗时] {name}: {dt_ms:.4f} ms")


@pytest.fixture(autouse=True)
def _reset_yolo_state():
    # 每个用例前后清空模块级模型状态，保证用例相互独立
    vision_core._model = None
    vision_core._confThreshold = 0.25
    vision_core._imgSize = 640
    yield
    vision_core._model = None


# ---------------------------------------------------------------------------
# 切割 crop_images
# ---------------------------------------------------------------------------

def test_crop_none_input() -> None:
    # 任一输入为 None -> 判定输入为空，success=False
    r = crop_images(None, _img(), 0, 0)
    assert isinstance(r, CropResult)
    assert r.success is False
    assert r.errorMessage == "输入图像为空"
    assert r.leftImage is None and r.rightImage is None


def test_crop_auto_size() -> None:
    # cropWidth/cropHeight 传 0 -> 自动：宽=原图宽//2，高=两图较小值
    r = crop_images(_img(100, 100), _img(100, 100), 0, 0)
    assert r.success is True
    # 自动宽=50，高=100
    assert r.leftImage.shape == (100, 50, 3)
    assert r.rightImage.shape == (100, 50, 3)


def test_crop_specified_size() -> None:
    # 显式指定宽高 -> 不走自动分支
    r = crop_images(_img(100, 100), _img(100, 100), 50, 50)
    assert r.success is True
    assert r.leftImage.shape == (50, 50, 3)
    assert r.rightImage.shape == (50, 50, 3)


def test_crop_width_exceed() -> None:
    # 裁剪宽超过图像宽 -> 失败
    r = crop_images(_img(100, 100), _img(100, 100), 99999, 0)
    assert r.success is False
    assert r.errorMessage == "裁剪宽超过图像宽"


def test_crop_height_exceed() -> None:
    # 裁剪高超过图像高 -> 失败（覆盖 cropHeight > 校验分支的 True 方向）
    r = crop_images(_img(100, 100), _img(100, 100), 10, 99999)
    assert r.success is False
    assert r.errorMessage == "裁剪高超过图像高"


# ---------------------------------------------------------------------------
# 拼接 stitch_images
# ---------------------------------------------------------------------------

def test_stitch_none_input() -> None:
    # 任一输入为 None -> 失败
    r = stitch_images(None, _img(), [0, 0])
    assert isinstance(r, SimpleStitchResult)
    assert r.success is False
    assert r.errorMessage == "输入图像为空"
    assert r.panorama is None


def test_stitch_size_mismatch() -> None:
    # 两图尺寸不一致 -> 失败（f-string 分支）
    r = stitch_images(_img(100, 100), _img(200, 200), [0, 0])
    assert r.success is False
    assert "不一致" in r.errorMessage


def test_stitch_bad_points() -> None:
    # stitchPoints 长度不为 2 -> 失败
    r = stitch_images(_img(100, 100), _img(100, 100), [1])
    assert r.success is False
    assert r.errorMessage == "stitchPoints 长度必须为 2"


def test_stitch_normal() -> None:
    # 正常拼接：offsetB=refX_A-refX_B=50>0，xMin=0
    # offsetB=refX_A-refX_B=50；canvasW=max(0+100, 50+100)-0=150
    r = stitch_images(_img(100, 100), _img(100, 100), [100, 50])
    assert r.success is True
    assert r.panorama is not None
    assert r.panorama.shape == (100, 150, 3)


def test_stitch_negative_offset() -> None:
    # imgB 跑到 imgA 左侧：offsetB=-100，xMin 取负，画布向左扩展
    r = stitch_images(_img(100, 100), _img(100, 100), [0, 100])
    assert r.success is True
    # canvasW = max(0+100, -100+100) - (-100) = 100 + 100 = 200
    assert r.panorama.shape == (100, 200, 3)


# ---------------------------------------------------------------------------
# 空间归集 check_roi_containment
# ---------------------------------------------------------------------------

def test_check_classify_all_cases() -> None:
    # 四类语义场景一次性覆盖：游离 / 单区域 / 跨两框 / 碰单框越界
    roi_defs = {
        "roi_1": (0, 0, 100, 100),
        "roi_2": (110, 0, 210, 100),
        "roi_3": (0, 200, 100, 300),
    }
    dets = [
        Detection("free", 0.9, (500, 500, 600, 600)),     # 完全在外部 -> 游离
        Detection("single", 0.9, (10, 10, 90, 90)),        # 仅 roi_1 且完全包含 -> 单区域
        Detection("cross2", 0.9, (95, 10, 115, 90)),        # 横跨 roi_1 & roi_2 -> 跨界(多框)
        Detection("cross1", 0.9, (90, 10, 130, 90)),        # 只碰 roi_1 但探出右界 -> 跨界(越界)
    ]
    r = check_roi_containment(dets, roi_defs)
    assert isinstance(r, RoiCheckResult)
    assert len(r.unmatched) == 1 and r.unmatched[0].className == "free"
    assert r.single_roi_items["roi_1"][0].className == "single"
    # 跨界两类都进 multi_roi_items
    assert len(r.multi_roi_items) == 2


def test_check_branch_coverage() -> None:
    # 单一 ROI + 多组精心构造的框，覆盖 contain(and) 与 overlap(or) 的全部短路分支
    rx1, ry1, rx2, ry2 = 100, 100, 200, 200
    roi_defs = {"r": (rx1, ry1, rx2, ry2)}
    # 每个框针对某一子条件失败/成功，穷举 4 个 and 与 4 个 or 的短路方向
    boxes = [
        (rx1 + 1, ry1 + 1, rx2 - 1, ry2 - 1),   # 完全包含：and 全 True；or 全 False
        (rx1 - 5, ry1 + 1, rx2 - 1, ry2 - 1),   # and#1 短路
        (rx1 + 1, ry1 - 5, rx2 - 1, ry2 - 1),   # and#1 进, and#2 短路
        (rx1 + 1, ry1 + 1, rx2 + 5, ry2 - 1),   # and#1,#2 进, and#3 短路
        (rx1 + 1, ry1 + 1, rx2 - 1, ry2 + 5),   # and 全进, and#4 False
        (rx1 - 20, ry1, rx1 - 5, ry2),          # or A 短路（完全在左）
        (rx2 + 5, ry1, rx2 + 20, ry2),          # or B 短路（完全在右）
        (rx1, ry1 - 20, rx2, ry1 - 5),          # or C 短路（完全在上）
        (rx1, ry2 + 5, rx2, ry2 + 20),          # or D 短路（完全在下）
    ]
    dets = [Detection(f"b{i}", 0.9, b) for i, b in enumerate(boxes)]
    r = check_roi_containment(dets, roi_defs)
    assert isinstance(r, RoiCheckResult)


def test_check_empty_detections() -> None:
    # detections 为空 -> 外层 for 循环“跳过”分支
    r = check_roi_containment([], {"r": (0, 0, 10, 10)})
    assert r.unmatched == [] and r.multi_roi_items == []
    assert r.single_roi_items == {"r": []}


def test_check_empty_roi_defs() -> None:
    # roi_defs 为空 -> 内层 for 循环“跳过”分支，物品全部判游离
    det = Detection("x", 0.9, (5, 5, 6, 6))
    r = check_roi_containment([det], {})
    assert r.unmatched == [det]
    assert r.single_roi_items == {}


# ---------------------------------------------------------------------------
# 业务校验 check_business_logic（无返回值，断言 logger 调用参数）
# ---------------------------------------------------------------------------

def test_business_all_correct() -> None:
    # 完全正确场景：multi 与 unmatched 为空（两 for 跳过），单区域全部匹配
    bind = {"roi_1": "滑板人偶"}
    cimap = {frozenset(["person", "surfboard"]): "滑板人偶"}
    single = {"roi_1": [Detection("person", 0.9, (1, 1, 2, 2)),
                        Detection("surfboard", 0.9, (3, 3, 4, 4))]}
    r = RoiCheckResult(single, [], [])
    with mock.patch("vision_core.logger") as mlog:
        check_business_logic(r, cimap, bind)
    mlog.info.assert_any_call("=== 工业防呆校验报告 ===")
    mlog.info.assert_any_call("[正确] 位置 %s 校验通过 (%s)", "roi_1", "滑板人偶")
    # 跨界/游离/漏放 均不应触发
    assert mlog.error.call_count == 0


def test_business_full_branch() -> None:
    # 全覆盖场景：跨界 + 游离 + 漏放 + 未知组合 + 张冠李戴
    bind = {
        "roi_1": "滑板人偶",
        "roi_2": "单人偶",
        "roi_3": "单人偶",
        "roi_4": "滑板人偶",
    }
    cimap = {
        frozenset(["person", "surfboard"]): "滑板人偶",
        frozenset(["person"]): "单人偶",
    }
    cross = Detection("cross", 0.9, (1, 1, 2, 2))
    free = Detection("free", 0.9, (9, 9, 10, 10))
    single = {
        "roi_1": [],                                          # 漏放
        "roi_2": [Detection("person", 0.9, (1, 1, 2, 2))],    # 正确
        "roi_3": [Detection("surfboard", 0.9, (1, 1, 2, 2))], # 未知组合
        "roi_4": [Detection("person", 0.9, (1, 1, 2, 2))],    # 张冠李戴
    }
    r = RoiCheckResult(single, [(cross, ["roi_1", "roi_2"])], [free])
    with mock.patch("vision_core.logger") as mlog:
        check_business_logic(r, cimap, bind)
    mlog.error.assert_any_call(
        "[放错] 物品 %s 跨越了多个ROI区域: %s", cross.className, ["roi_1", "roi_2"])
    mlog.error.assert_any_call(
        "[放错] 物品 %s 不在ROI区域内", free.className)
    mlog.error.assert_any_call(
        "[漏放] 位置 %s 为空，预期放置: %s", "roi_1", "滑板人偶")
    mlog.error.assert_any_call(
        "[放错] 位置 %s 检测到未知组合 %s", "roi_3", set(frozenset(["surfboard"])))
    mlog.error.assert_any_call(
        "[放错] 位置 %s 预期: %s，实际: %s", "roi_4", "滑板人偶", "单人偶")
    mlog.info.assert_any_call(
        "[正确] 位置 %s 校验通过 (%s)", "roi_2", "单人偶")


def test_business_empty_bind_map() -> None:
    # roi_bind_map 为空 -> 第三层 for 循环“跳过”分支
    r = RoiCheckResult({}, [], [])
    with mock.patch("vision_core.logger") as mlog:
        check_business_logic(r, {}, {})
    mlog.info.assert_any_call("=== 工业防呆校验报告 ===")
    # 无跨界/游离/漏放可报，error 不应被调用
    assert mlog.error.call_count == 0


# ---------------------------------------------------------------------------
# 视野自检 self_check（接口 4.5）
# ---------------------------------------------------------------------------

def test_self_check_pass() -> None:
    # 仅校验 roi_2 的 person；roi_1 不在表中被跳过；含 person 则通过
    single = {"roi_1": [], "roi_2": [Detection("person", 0.9, (1, 1, 2, 2))]}
    r = RoiCheckResult(single, [], [])
    with mock.patch("vision_core.logger") as mlog:
        ok = self_check(r, {"roi_2": "person"})
    assert ok is True
    mlog.info.assert_any_call("=== 相机视野自检通过 ===")


def test_self_check_fail_missing() -> None:
    # roi_1 内检测到的是 surfboard，并非期望的 person -> 自检失败
    single = {"roi_1": [Detection("surfboard", 0.9, (1, 1, 2, 2))]}
    r = RoiCheckResult(single, [], [])
    with mock.patch("vision_core.logger") as mlog:
        ok = self_check(r, {"roi_1": "person"})
    assert ok is False
    mlog.error.assert_any_call(
        "[自检失败] 位置 %s 未检测到标识 '%s'，当前检测到: %s",
        "roi_1", "person", ["surfboard"])


def test_self_check_fail_empty() -> None:
    # roi_1 为空（未检测到任何物品）-> present_classes 为空走“空”分支，自检失败
    r = RoiCheckResult({"roi_1": []}, [], [])
    with mock.patch("vision_core.logger") as mlog:
        ok = self_check(r, {"roi_1": "person"})
    assert ok is False
    mlog.error.assert_any_call(
        "[自检失败] 位置 %s 未检测到标识 '%s'，当前检测到: %s",
        "roi_1", "person", "空")


def test_self_check_empty_config() -> None:
    # 自检映射表为空：循环 0 次直接通过，覆盖“未配置任何 ROI 跳过自检”分支
    r = RoiCheckResult({"roi_1": [Detection("person", 0.9, (1, 1, 2, 2))]}, [], [])
    with mock.patch("vision_core.logger") as mlog:
        ok = self_check(r, {})
    assert ok is True
    mlog.info.assert_any_call("=== 相机视野自检通过 ===")


# ---------------------------------------------------------------------------
# YOLO 初始化与推理
# ---------------------------------------------------------------------------

def test_yolo_init_success() -> None:
    # 首次初始化：走 try/正常分支，_model 被赋值为 Mock 模型实例
    model_mock = _make_model_mock(1)
    with mock.patch("ultralytics.YOLO", return_value=model_mock):
        rc = yolo_init("m.onnx", 0.5, 640)
    assert rc is True
    assert vision_core._model is model_mock


def test_yolo_init_already_loaded() -> None:
    # 已加载则跳过重复加载，但同步热更新阈值/尺寸
    model_mock = _make_model_mock(1)
    _init_yolo(model_mock)
    assert vision_core._model is not None
    rc = yolo_init("other.onnx", 0.9, 320)
    assert rc is True
    assert vision_core._confThreshold == 0.9
    assert vision_core._imgSize == 320


def test_yolo_init_failure() -> None:
    # 模型加载抛异常 -> 捕获后抛出 RuntimeError（覆盖 except 分支）
    with mock.patch("ultralytics.YOLO", side_effect=Exception("boom")):
        with pytest.raises(RuntimeError):
            yolo_init("bad.onnx", 0.5, 640)
    assert vision_core._model is None


def test_yolo_detect_no_model() -> None:
    # 模型未初始化 -> 返回空列表（覆盖 _model is None 分支）
    assert yolo_detect(_img()) == []


def test_yolo_detect_none_image() -> None:
    # 输入为空 -> 返回空列表
    _init_yolo(_make_model_mock(1))
    assert yolo_detect(None) == []


def test_yolo_detect_success() -> None:
    # 正常推理：解析出 1 个检测框
    _init_yolo(_make_model_mock(1))
    dets = yolo_detect(_img())
    assert len(dets) == 1
    assert dets[0].className == "person"
    assert dets[0].box == (10, 20, 30, 40)


def test_yolo_detect_no_boxes() -> None:
    # 预测结果 boxes 为 None -> 返回空列表（覆盖 if boxes is not None 的 False 分支）
    model = _make_model_mock(1)
    model.predict.return_value = [mock.MagicMock(boxes=None)]
    _init_yolo(model)
    assert yolo_detect(_img()) == []


def test_yolo_detect_empty_boxes() -> None:
    # 预测结果有 boxes 但长度为 0 -> for 循环“跳过”（覆盖 0 次迭代分支）
    model = _make_model_mock(0)
    _init_yolo(model)
    assert yolo_detect(_img()) == []


# ---------------------------------------------------------------------------
# 接口耗时基准（单元级：YOLO 用 Mock，仅反映函数调用开销，非真实推理耗时）
# ---------------------------------------------------------------------------

def test_interface_timing() -> None:
    # 逐个接口计时并打印（单元级：YOLO 用 Mock，仅反映函数调用开销，非真实推理耗时）
    print("\n========== 各接口单元级耗时（Mock 模型，仅函数调用开销）==========")
    img = _img()
    cr = _timed("接口1 切割 crop_images", crop_images, img, img, 0, 0)
    assert cr.success
    st = _timed("接口2 拼接 stitch_images", stitch_images, img, img, [100, 50])
    assert st.success

    model = _make_model_mock(1)
    with mock.patch("ultralytics.YOLO", return_value=model):
        _timed("接口3 初始化 yolo_init", yolo_init, "m.onnx", 0.5, 640)
    dets = _timed("接口3 推理 yolo_detect", yolo_detect, img)
    assert isinstance(dets, list)

    roi_defs = {"r": (100, 100, 200, 200)}
    det_list = [Detection("person", 0.9, (110, 110, 190, 190))]
    r = _timed("接口4 归集 check_roi_containment", check_roi_containment, det_list, roi_defs)
    assert isinstance(r, RoiCheckResult)
    assert _timed("接口4.5 自检 self_check", self_check, r, {"r": "person"}) is True
    with mock.patch("vision_core.logger"):
        _timed("接口5 校验 check_business_logic", check_business_logic, r,
               {frozenset(["person"]): "单人偶"}, {"r": "单人偶"})
    print("=============================================================")


# ---------------------------------------------------------------------------
# TcpComm 通信类测试（确定性、离线、分支覆盖率 100%）
# ---------------------------------------------------------------------------

def _scripted_sock(script, comm, terminate_on_call=None):
    # 构造“脚本化假 socket”：recv 按 script 顺序返回字节或抛异常；
    # 第 terminate_on_call 次 recv 前把 comm._running 置 False，使 _loop 干净退出。
    # @param [in] script 元素为 bytes（成功返回）或 Exception（recv 时抛出）
    # @param [in] comm 被测 TcpComm 实例（用于置 _running）
    # @param [in] terminate_on_call 第几次 recv 时置 running=False；None 表示不自动终止
    # @return MagicMock；recv 行为按 script 脚本化
    sock = mock.MagicMock()
    sock.settimeout = mock.MagicMock()
    state = {"n": 0}

    def _recv(n):
        state["n"] += 1
        if terminate_on_call is not None and state["n"] >= terminate_on_call:
            comm._running = False
        if not script:
            return b""
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    sock.recv.side_effect = _recv
    return sock


def _drive_loop(comm, sock_factory):
    # 同步驱动私有 _loop()：patch create_connection（每次连接新建 socket）与
    # time.sleep（no-op），直到脚本将 comm._running 置 False 后 _loop 自然退出。
    # @param [in] comm 被测 TcpComm 实例
    # @param [in] sock_factory 无参 callable，返回当次连接使用的假 socket
    # @return None
    comm._running = True
    with mock.patch("vision_core.socket.create_connection",
                    side_effect=lambda *a, **k: sock_factory()), \
         mock.patch("vision_core.time.sleep", lambda *a, **k: None):
        comm._loop()
    comm._running = False
    comm._conn = None


def test_tcpcomm_construct():
    # 构造后各字段初始化正确，接收队列为空
    cb = mock.MagicMock()
    c = TcpComm("127.0.0.1", 9000, 2.0, on_message=cb)
    assert c._host == "127.0.0.1" and c._port == 9000 and c._reconnect_interval == 2.0
    assert c._on_message is cb
    assert c._thread is None and c._running is False and c._conn is None
    assert c._recv_queue.empty()
    assert c._buffer == ""


def test_start_already_running():
    # 已 running 时 start() 直接返回，不创建线程
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    c._running = True
    c.start()
    assert c._thread is None


def test_start_spawn_thread():
    # 未 running 时 start() 创建并启动守护线程
    fake_thread = mock.MagicMock()
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    with mock.patch("vision_core.threading.Thread", return_value=fake_thread) as thr:
        c.start()
    assert c._running is True
    thr.assert_called_once()
    fake_thread.start.assert_called_once()


def test_stop_no_conn():
    # 无连接时 stop() 仅置 running=False，不调用 close
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    c.stop()
    assert c._running is False and c._conn is None


def test_stop_with_conn():
    # 有连接时 stop() 关闭 socket 并置 None
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    sock = mock.MagicMock()
    c._conn = sock
    c.stop()
    sock.close.assert_called_once()
    assert c._conn is None


def test_stop_with_conn_oserror():
    # close 抛 OSError 时 stop() 不应向上传播
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    sock = mock.MagicMock()
    sock.close.side_effect = OSError("boom")
    c._conn = sock
    c.stop()
    assert c._conn is None


def test_is_connected_false():
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    assert c.is_connected() is False


def test_is_connected_true():
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    c._conn = mock.MagicMock()
    assert c.is_connected() is True


def test_send_no_conn():
    # 未连接时 send 返回 False
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    assert c.send({"a": 1}) is False


def test_send_success():
    # 已连接：发送内容为单行 JSON + \n，返回 True
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    sock = mock.MagicMock()
    c._conn = sock
    assert c.send({"a": 1}) is True
    sent = sock.sendall.call_args[0][0]
    assert sent.endswith(b"\n")
    assert json.loads(sent.decode("utf-8").rstrip("\n")) == {"a": 1}


def test_send_oserror():
    # sendall 抛 OSError 时返回 False
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    sock = mock.MagicMock()
    sock.sendall.side_effect = OSError("boom")
    c._conn = sock
    assert c.send({"a": 1}) is False


def test_recv_nowait_empty():
    # 队列空：非阻塞 recv 返回 None
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    assert c.recv() is None


def test_recv_nowait_data():
    # 队列有数据：非阻塞 recv 取回 dict
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    c._recv_queue.put({"x": 1})
    assert c.recv() == {"x": 1}


def test_recv_timeout_empty():
    # 阻塞 recv 超时且无数据返回 None
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    assert c.recv(timeout=0.01) is None


def test_recv_timeout_data():
    # 阻塞 recv 在超时内取到数据
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    c._recv_queue.put({"y": 2})
    assert c.recv(timeout=0.01) == {"y": 2}


def test_loop_success():
    # 正常路径：连接 -> 收一行 JSON -> on_message 收到 -> 干净退出
    received = []
    c = TcpComm("h", 1, 1.0, on_message=received.append)
    sock = _scripted_sock([b'{"type":"recognize"}\n', b""], c, terminate_on_call=2)
    _drive_loop(c, lambda: sock)
    assert received == [{"type": "recognize"}]


def test_loop_connect_fail():
    # 连接失败：首次仍 running 走 sleep+continue；二次置 running=False 走 break
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    state = {"n": 0}

    def _factory():
        state["n"] += 1
        if state["n"] == 1:
            raise OSError("refused")
        c._running = False
        raise OSError("stop")

    _drive_loop(c, _factory)
    assert state["n"] == 2


def test_loop_recv_timeout():
    # 读超时（TimeoutError）-> continue 不视为断线；第三次干净退出
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    sock = _scripted_sock([TimeoutError("t"), TimeoutError("t"), b""], c, terminate_on_call=3)
    _drive_loop(c, lambda: sock)


def test_loop_recv_oserror_reconnect():
    # 收包抛 OSError -> 内层 break；running 仍 True -> finally 重连；二次连接后退出
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    sock1 = _scripted_sock([b'{"x":1}\n', OSError("reset")], c, terminate_on_call=None)
    sock2 = _scripted_sock([b""], c, terminate_on_call=1)
    state = {"n": 0}

    def _factory():
        state["n"] += 1
        return sock1 if state["n"] == 1 else sock2

    _drive_loop(c, _factory)
    assert state["n"] == 2
    assert sock1.close.called


def test_loop_partial_chunk():
    # 半包跨 recv：首包含完整行 + 半包，次包补齐 -> 两行均解析
    received = []
    c = TcpComm("h", 1, 1.0, on_message=received.append)
    sock = _scripted_sock([b'{"a":1}\n{"b":', b'2}\n', b""], c, terminate_on_call=3)
    _drive_loop(c, lambda: sock)
    assert received == [{"a": 1}, {"b": 2}]


def test_loop_blank_line():
    # 空行（strip 后为空）被跳过，不触发回调
    received = []
    c = TcpComm("h", 1, 1.0, on_message=received.append)
    sock = _scripted_sock([b'\n', b'{"ok":1}\n', b""], c, terminate_on_call=3)
    _drive_loop(c, lambda: sock)
    assert received == [{"ok": 1}]


def test_loop_bad_json():
    # 非法 JSON 行被跳过（JSONDecodeError -> continue）
    received = []
    c = TcpComm("h", 1, 1.0, on_message=received.append)
    sock = _scripted_sock([b'notjson\n', b'{"ok":1}\n', b""], c, terminate_on_call=3)
    _drive_loop(c, lambda: sock)
    assert received == [{"ok": 1}]


def test_loop_non_dict():
    # JSON 非 dict（如数组）不入队、不回调
    received = []
    c = TcpComm("h", 1, 1.0, on_message=received.append)
    sock = _scripted_sock([b'[1,2,3]\n', b'{"ok":1}\n', b""], c, terminate_on_call=3)
    _drive_loop(c, lambda: sock)
    assert received == [{"ok": 1}]


def test_loop_onmessage_none():
    # on_message 为 None 时不回调也不抛异常（仍入队）
    c = TcpComm("h", 1, 1.0, on_message=None)
    sock = _scripted_sock([b'{"ok":1}\n', b""], c, terminate_on_call=2)
    _drive_loop(c, lambda: sock)
    assert c._recv_queue.get_nowait() == {"ok": 1}


def test_loop_close_oserror():
    # finally 中 close 抛 OSError 被静默吞掉，不向上传播
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    sock = _scripted_sock([b'{"ok":1}\n', b""], c, terminate_on_call=2)
    sock.close.side_effect = OSError("boom")
    _drive_loop(c, lambda: sock)


def test_tcpcomm_integration():
    # 真实回环 socket 端到端：server 发一行 JSON，comm 经真实网络收到并回调
    import socket as _socket
    import threading as _threading

    received = []
    evt = _threading.Event()

    def _on(msg):
        received.append(msg)
        evt.set()

    c = TcpComm("127.0.0.1", 0, 0.2, on_message=_on)
    srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    c._port = srv.getsockname()[1]

    def _serve():
        conn, _ = srv.accept()
        with conn:
            conn.sendall(b'{"type":"periodic"}\n')

    _threading.Thread(target=_serve, daemon=True).start()
    c.start()
    try:
        assert evt.wait(timeout=5.0), "未在超时内收到上位机报文"
        assert received and received[0] == {"type": "periodic"}
    finally:
        c.stop()
        srv.close()


def test_loop_not_running():
    # running=False 时 _loop 直接退出，不进入任何网络逻辑（覆盖外层 while 不进入分支）
    c = TcpComm("h", 1, 1.0, on_message=mock.MagicMock())
    c._running = False
    c._loop()  # 应直接返回，不抛异常
    assert c._conn is None


def test_loop_terminate_via_running_flag():
    # 内层 while 因 running 变为 False 而正常退出（非 break 路径，覆盖 534->562 分支）
    received = []
    c = TcpComm("h", 1, 1.0, on_message=received.append)
    sock = _scripted_sock([b'{"a":1}\n', b'{"b":2}\n'], c, terminate_on_call=2)
    _drive_loop(c, lambda: sock)
    assert received == [{"a": 1}, {"b": 2}]
