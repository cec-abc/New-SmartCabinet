"""单人手动对焦 / 变焦测试：用方向键或字符键实时调摄像头对焦与变焦，看清画面。

复用生产 CameraDevice / CameraFactory，不另造设备逻辑，保证与生产行为一致。
支持一键探测：把焦点 / 变焦属性下到摄像头再回读，据此判断硬件到底支不支持。

用法：
    python edge/lab/manual_focus_test.py --device 0          # Windows 摄像头索引 0
    python edge/lab/manual_focus_test.py --device /dev/video0  # 麒麟固定路径

键位：
    对焦粗调： ← 或 [ 减小     → 或 ] 增大
    对焦微调： ↑ 增大          ↓ 减小      （每步约粗调的五分之一，便于落到清晰点）
    自动对焦： a 开启          m 关闭
    变焦：     , 减小          . 增大      （多数定焦 USB 摄像头硬件不支持）
    通用：     r 回读并显示当前对焦 / 变焦   q 退出
"""

from __future__ import annotations

import sys
from pathlib import Path

## 允许从任意目录直接运行本调试脚本：把工程根（edge 包的父目录）加入模块搜索路径，
## 否则在 edge/lab 下直接 python manual_focus_test.py 会因找不到 edge 包而 ModuleNotFoundError
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import argparse
import contextlib
import time

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # 无 Pillow 时中文无法渲染，自动回退英文提示
    Image = ImageDraw = ImageFont = None

from edge.modules.usb.usb_camera_device import (
    FOCUS_POSITION_MAX,
    FOCUS_POSITION_MIN,
    FRAME_SOURCE_CAMERA,
    ZOOM_POSITION_MAX,
    ZOOM_POSITION_MIN,
    CameraFactory,
)


## 方向键原始键值：Windows 图形库返回高字节扩展码，Linux 用小键值，两套都要认
_ARROW_KEY_LEFT = frozenset((2424832, 81))
_ARROW_KEY_RIGHT = frozenset((2555904, 83))
_ARROW_KEY_UP = frozenset((2490368, 82))
_ARROW_KEY_DOWN = frozenset((2621440, 84))


## @brief 把 waitKey 的原始返回值翻译成方向名；非方向键返回空串
#  @param rawKey waitKey 原始返回值，未做 0xFF 截断
#  @return left/right/up/down 之一，非方向键返回空串
def _arrowDirection(rawKey):
    if rawKey in _ARROW_KEY_LEFT:
        return "left"
    if rawKey in _ARROW_KEY_RIGHT:
        return "right"
    if rawKey in _ARROW_KEY_UP:
        return "up"
    if rawKey in _ARROW_KEY_DOWN:
        return "down"
    return ""


## @brief 探测摄像头硬件是否支持对焦 / 变焦：下发一个测试值再回读，两者接近视为支持
#  @param deviceAddr 设备地址：Windows 写索引、Linux 写 /dev/... 固定路径
#  @param isWindows 是否 Windows 平台
#  @return 能力字典：每项含 supported 标志与下发 / 回读原始值
def probeCapabilities(deviceAddr, isWindows):
    backend = cv2.CAP_DSHOW if isWindows else cv2.CAP_V4L2
    try:
        index = int(deviceAddr) if isWindows else deviceAddr
    except ValueError:
        index = deviceAddr
    capability = {"focus": {"supported": False}, "zoom": {"supported": False}}
    with contextlib.suppress(Exception):
        capture = cv2.VideoCapture(index, backend)
        try:
            if not capture.isOpened():
                return capability
            focusId = getattr(cv2, "CAP_PROP_FOCUS_ABSOLUTE", None)
            if focusId is None:
                focusId = getattr(cv2, "CAP_PROP_FOCUS", None)
            if focusId is not None:
                capability["focus"] = _probeOneControl(capture, int(focusId))
            zoomId = getattr(cv2, "CAP_PROP_ZOOM", None)
            if zoomId is not None:
                capability["zoom"] = _probeOneControl(capture, int(zoomId))
        finally:
            capture.release()
    return capability


## @brief 对单个控制属性做下发 + 回读探测
#  @param capture 已打开的 VideoCapture 句柄
#  @param propertyId 属性号
#  @return 探测结果字典
def _probeOneControl(capture, propertyId):
    ## 取一个与当前值不同的测试值，能看出回读是否真的跟着变
    current = capture.get(propertyId)
    testValue = 0.0 if abs(current - 0.0) > 1e-6 else 1.0
    capture.set(propertyId, testValue)
    readback = capture.get(propertyId)
    ## 部分驱动静默忽略不支持的控制，下发后回读不跟随；两者接近才认为支持
    supported = abs(readback - testValue) <= max(1e-3, abs(testValue) * 0.1)
    return {
        "supported": bool(supported),
        "testValue": float(testValue),
        "readback": float(readback),
    }


def _decodeFrame(frameBytes):
    ## readFrame 走生产链路返回 JPEG 字节，这里解回 numpy 数组用于本地预览
    if not frameBytes:
        return None
    array = np.frombuffer(frameBytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


## 常见中文字体候选：Windows 与麒麟 Linux 下各列几个，命中第一个存在的即可
_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


## @brief 查找可用中文字体：按候选列表取第一个存在的字体文件
#  @param size 字号像素
#  @return Pillow 字体实例；无 Pillow 或找不到字体时返回 None
def _loadChineseFont(size):
    if ImageFont is None:
        return None
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


## @brief 在帧上绘制文字：cv2.putText 内置字体不支持中文（画成问号），有字体时改用 Pillow
#  @param frame BGR 帧
#  @param text 要显示的文本
#  @param fallbackText 无中文字体时的 ASCII 回退文本
#  @param org 文字左上角坐标 (x, y)
#  @param colorBgr BGR 颜色
#  @param font Pillow 字体；None 时走 OpenCV 回退
#  @return 绘制后的帧
def _putText(frame, text, fallbackText, org, colorBgr, font):
    if font is None:
        cv2.putText(frame, fallbackText, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, colorBgr, 2)
        return frame
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(image).text(org, text, font=font, fill=(colorBgr[2], colorBgr[1], colorBgr[0]))
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def main():
    parser = argparse.ArgumentParser(description="手动对焦 / 变焦测试")
    parser.add_argument(
        "--device",
        default="2",
        help="摄像头地址：Windows 写索引，Linux 写 /dev/videoN",
    )
    args = parser.parse_args()

    isWindows = sys.platform.startswith("win")
    deviceAddr = args.device
    probe = probeCapabilities(deviceAddr, isWindows)
    print("==== 硬件能力探测 ====")
    for name, result in probe.items():
        flag = "支持" if result.get("supported") else "不支持 / 被驱动静默忽略"
        detail = ""
        if "testValue" in result:
            detail = f"（下发={result['testValue']}, 回读={result['readback']}）"
        print(f"  {name}: {flag}{detail}")
    print("=======================")

    ## 复用生产设备取真帧并下发对焦 / 变焦；frameReader 仅占位帧源用到，这里用 camera 源
    device = CameraFactory.createDevice(deviceAddr, lambda: None, frameSource=FRAME_SOURCE_CAMERA)
    try:
        device.open()
    except Exception as error:  # noqa: BLE001
        print(f"无法打开摄像头 {deviceAddr}：{error}")
        print("请确认设备号正确、摄像头已接入且未被其他程序占用后重试")
        return
    print("已打开摄像头，按方向键 / 字符键调对焦与变焦，按 q 退出")
    print("对焦粗调: ←/[ 减  →/] 增   对焦微调: ↑ 增  ↓ 减   a 自动  m 手动")
    print("变焦: , 减  . 增   r 回读   q 退出")

    focusStep = (FOCUS_POSITION_MAX - FOCUS_POSITION_MIN) / 20.0
    fineStep = focusStep / 5.0
    zoomStep = (ZOOM_POSITION_MAX - ZOOM_POSITION_MIN) / 20.0
    focusManual = True
    focusOk = bool(probe["focus"]["supported"])
    zoomOk = bool(probe["zoom"]["supported"])
    capText = (
        f"能力: 对焦={'支持' if focusOk else '不支持'}"
        f"  变焦={'支持' if zoomOk else '不支持'}"
    )
    capFallback = f"cap: focus={'yes' if focusOk else 'no'}  zoom={'yes' if zoomOk else 'no'}"
    font = _loadChineseFont(24)
    if font is None:
        print("未找到中文字体，画面提示将以英文显示")

    try:
        while True:
            frame = None
            with contextlib.suppress(Exception):
                frame = _decodeFrame(device.readFrame())
            if frame is None:
                time.sleep(0.03)
                continue
            focusText = (
                f"focus={device.getFocusPosition():.2f}"
                f"  zoom={device.getZoomPosition():.2f}"
                f"  auto={not focusManual}"
            )
            frame = _putText(frame, focusText, focusText, (10, 30), (0, 255, 0), font)
            frame = _putText(frame, capText, capFallback, (10, 60), (0, 255, 255), font)
            cv2.imshow("focus/zoom test", frame)
            rawKey = cv2.waitKey(30)
            key = rawKey & 0xFF
            if key in (ord("q"), 27):
                break
            currentFocus = device.getFocusPosition()
            currentZoom = device.getZoomPosition()
            direction = _arrowDirection(rawKey)
            ## 左右粗调、上下微调：统一走带边界钳制与失败兜底的焦点迁移
            focusDelta = 0.0
            if direction == "left" or key == ord("["):  # 左 / [ ：粗调减小
                focusDelta = -focusStep
            elif direction == "right" or key == ord("]"):  # 右 / ] ：粗调增大
                focusDelta = focusStep
            elif direction == "up":  # 上 ：微调增大
                focusDelta = fineStep
            elif direction == "down":  # 下 ：微调减小
                focusDelta = -fineStep
            if focusDelta != 0.0:
                focusManual = True
                target = min(max(currentFocus + focusDelta, FOCUS_POSITION_MIN), FOCUS_POSITION_MAX)
                try:
                    device.setFocusPosition(target)
                except Exception as error:  # noqa: BLE001
                    print(f"对焦迁移失败，可能已到硬件边界: {error}")
            elif key == ord("a"):  # a ：自动对焦
                focusManual = False
                with contextlib.suppress(Exception):
                    device.setAutoFocus(True)
            elif key == ord("m"):  # m ：回到手动对焦
                focusManual = True
                with contextlib.suppress(Exception):
                    device.setAutoFocus(False)
            elif key == ord(","):  # , ：减小变焦
                if not probe.get("zoom", {}).get("supported"):
                    print("本机摄像头不支持变焦(探测结论), 按键无效; 如确认支持请查占用/驱动")
                else:
                    with contextlib.suppress(Exception):
                        device.setZoomPosition(max(currentZoom - zoomStep, ZOOM_POSITION_MIN))
            elif key == ord("."):  # . ：增大变焦
                if not probe.get("zoom", {}).get("supported"):
                    print("本机摄像头不支持变焦(探测结论), 按键无效; 如确认支持请查占用/驱动")
                else:
                    with contextlib.suppress(Exception):
                        device.setZoomPosition(min(currentZoom + zoomStep, ZOOM_POSITION_MAX))
            elif key == ord("r"):  # r ：回读显示
                print(f"对焦位置={currentFocus:.2f}  变焦位置={currentZoom:.2f}")
    finally:
        device.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
