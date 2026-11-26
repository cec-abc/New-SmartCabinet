"""桩上位机：监听临时端口、按行切分紧凑 JSON，并按上位机协议校验回包。"""
from __future__ import annotations

import json
import socket
from collections.abc import Callable
from threading import Event
from time import monotonic
from typing import cast

from edge.base.base_thread import BaseThread

## @file edge/tests/integration/fake_host.py
## @brief 纯 Python 桩上位机：监听临时端口、收发协议帧并按上位机口径校验
## @author 边缘计算项目

## @brief 上位机协议帧
HostFrame = dict[str, object]
## @brief 应答条目必须且只允许出现的字段集合
ACK_ITEM_FIELDS: frozenset[str] = frozenset({"position", "tool_id", "confidence", "alert_type"})
## @brief 协议允许的告警类型
ALERT_TYPES: frozenset[str] = frozenset(
    {"none", "misplaced", "unknown", "missing", "low_confidence"},
)
## @brief 协议允许的摄像头状态取值（两态，取图失败归并到离线）
CAMERA_STATUS_VALUES: frozenset[str] = frozenset(
    {"ok", "offline"},
)
## @brief 上位机 EdgeService.cpp:362-465 的分发分支认识的上行帧型
## @note 认不出的 type 落到 :463-465 的"未知 type 丢弃并计数"：
##       上位机既拿不到应答，丢弃计数又被污染。
HOST_RECOGNIZED_FRAME_TYPES: frozenset[str] = frozenset(
    {"periodic", "recognize_ack"},
)
## @brief 上位机单帧上限 1MB（CommTypes.h:20）；超限 EdgeLink.cpp:168-173 直接断链
HOST_FRAME_MAX_BYTES: int = 1024 * 1024
## @brief 期望覆盖的 8 路摄像头编号
CAMERA_IDS: tuple[str, ...] = ("CAM1", "CAM2", "CAM3", "CAM4", "CAM5", "CAM6", "CAM7", "CAM8")
## @brief 桩上位机默认监听端口，0 表示由系统分配临时端口
DEFAULT_PORT: int = 0


## @brief 桩上位机的接入线程：等边缘机连上后交给桩上位机处理
class FakeHostAcceptThread(BaseThread):
    ## @brief 构造接入线程
    #  @param server 监听套接字
    #  @param onClient 接入回调
    def __init__(self, server: socket.socket,
                 onClient: Callable[[socket.socket], None]) -> None:
        super().__init__(name="FakeHostAccept")
        ## @brief 监听套接字
        self._server: socket.socket = server
        ## @brief 接入回调
        self._onClient: Callable[[socket.socket], None] = onClient

    ## @brief 主循环：轮询接入，收到停止指令立即退出
    #  @return 无
    def runLoop(self) -> None:
        while self.isRunning():
            try:
                client, _address = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self._onClient(client)
            return


## @brief 纯 Python 桩上位机；只做协议收发与校验，不含任何界面逻辑
class FakeHost:
    ## @brief 构造桩上位机
    #  @param host 监听地址
    #  @param port 监听端口，0 表示由系统分配临时端口
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
        ## @brief 监听地址
        self._host: str = host
        ## @brief 监听端口
        self._port: int = port
        ## @brief 监听套接字
        self._server: socket.socket | None = None
        ## @brief 边缘机连接
        self._client: socket.socket | None = None
        ## @brief 边缘机已接入标记
        self._clientReady: Event = Event()
        ## @brief 接收缓冲
        self._buffer: bytes = b""
        ## @brief 已收到的帧
        self._received: list[HostFrame] = []
        ## @brief 按上位机口径被判丢弃的帧；上位机会丢弃并计数
        self._dropped: list[HostFrame] = []
        ## @brief 收到的原始帧字节，一帧一条，含行尾换行
        self._rawLines: list[bytes] = []
        ## @brief 接入线程
        self._acceptThread: FakeHostAcceptThread | None = None

    ## @brief 启动监听，返回实际监听端口
    #  @return 监听端口
    def start(self) -> int:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self._host, self._port))
        server.listen(1)
        server.settimeout(0.2)
        self._server = server
        self._port = int(server.getsockname()[1])
        self._acceptThread = FakeHostAcceptThread(server, self.acceptClient)
        self._acceptThread.start()
        return self._port

    ## @brief 边缘机接入回调：记录连接并唤醒等待方
    #  @param client 边缘机连接
    #  @return 无
    def acceptClient(self, client: socket.socket) -> None:
        self._client = client
        self._clientReady.set()

    ## @brief 等待边缘机接入
    #  @param timeoutSec 最长等待秒数
    #  @return 已接入返回 True
    def waitClient(self, timeoutSec: float) -> bool:
        return self._clientReady.wait(timeoutSec)

    ## @brief 发送识别请求帧；协议只有 type / request_id / timestamp 三个字段
    #  @param requestId 请求标识
    #  @return 无
    def sendRecognizeReq(self, requestId: str) -> None:
        self.sendFrame({
            "type": "recognize_req",
            "request_id": requestId,
            "timestamp": int(monotonic() * 1000),
        })

    ## @brief 发送一帧；紧凑 JSON 加换行
    #  @param frame 协议帧
    #  @return 无
    def sendFrame(self, frame: HostFrame) -> None:
        client = self._client
        if client is None:
            return
        client.sendall(json.dumps(frame, ensure_ascii=False).encode("utf-8") + b"\n")

    ## @brief 读取一帧；按换行切分紧凑 JSON
    #  @param timeoutSec 最长等待秒数
    #  @return 解析后的帧；超时或连接关闭返回 None
    def readHostFrame(self, timeoutSec: float) -> HostFrame | None:
        deadline = monotonic() + timeoutSec
        while True:
            line = self.readLine(deadline)
            if line is None:
                return None
            if not line.strip():
                continue
            self._rawLines.append(line + b"\n")
            frame = cast(HostFrame, json.loads(line.decode("utf-8")))
            self._received.append(frame)
            if not self.isHostRecognizedFrame(frame):
                ## 复刻上位机 EdgeService.cpp:463-465：认不出的 type 丢弃并计数
                self._dropped.append(frame)
            return frame

    ## @brief 判断帧型是否上位机认识
    #  @param frame 待判帧
    #  @return 认识返回 True
    def isHostRecognizedFrame(self, frame: HostFrame) -> bool:
        frameType = frame.get("type")
        return (
            isinstance(frameType, str)
            and frameType in HOST_RECOGNIZED_FRAME_TYPES
        )

    ## @brief 按上位机口径被判丢弃的帧
    #  @return 丢弃帧列表
    def droppedFrames(self) -> list[HostFrame]:
        return list(self._dropped)

    ## @brief 上位机口径的丢弃计数
    #  @return 丢弃条数
    def dropCount(self) -> int:
        return len(self._dropped)

    ## @brief 收到的原始帧字节，一帧一条，含行尾换行
    #  @return 原始字节列表
    def receivedRawLines(self) -> list[bytes]:
        return list(self._rawLines)

    ## @brief 等待指定类型的帧；期间收到的其它帧一并留存
    #  @param frameType 帧类型
    #  @param timeoutSec 最长等待秒数
    #  @return 匹配帧；超时返回 None
    def waitFrameOfType(self, frameType: str, timeoutSec: float) -> HostFrame | None:
        deadline = monotonic() + timeoutSec
        while True:
            frame = self.readHostFrame(max(0.0, deadline - monotonic()))
            if frame is None:
                return None
            if str(frame.get("type", "")) == frameType:
                return frame

    ## @brief 已收到的全部帧，供验收举证
    #  @return 帧列表
    def receivedFrames(self) -> list[HostFrame]:
        return list(self._received)

    ## @brief 关闭边缘机连接，模拟上位机断链
    #  @return 无
    def closeClient(self) -> None:
        client = self._client
        if client is None:
            return
        client.close()
        self._client = None

    ## @brief 停止监听，模拟上位机整体离线
    #  @return 无
    def shutdownServer(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()

    ## @brief 停止桩上位机并释放套接字
    #  @return 无
    def stop(self) -> None:
        if self._acceptThread is not None:
            self._acceptThread.stop(1.0)
        self.closeClient()
        if self._server is not None:
            self._server.close()
            self._server = None

    ## @brief 从接收缓冲取一整行
    #  @param deadline 截止时刻
    #  @return 行字节；超时或连接关闭返回 None
    def readLine(self, deadline: float) -> bytes | None:
        client = self._client
        if client is None:
            return None
        while b"\n" not in self._buffer:
            remaining = deadline - monotonic()
            if remaining <= 0:
                return None
            client.settimeout(remaining)
            try:
                chunk = client.recv(4096)
            except socket.timeout:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        if len(line) + 1 > HOST_FRAME_MAX_BYTES:
            ## 复刻 EdgeLink.cpp:168-173：单帧超上限直接断链，不是丢帧
            self.closeClient()
            return None
        return line

    ## @brief 校验识别应答帧是否符合上位机协议
    #  @param frame 应答帧
    #  @return 错误列表，空列表表示校验通过
    def validateAck(self, frame: HostFrame) -> list[str]:
        errors: list[str] = []
        if str(frame.get("type", "")) != "recognize_ack":
            errors.append(f"帧类型不是 recognize_ack: {frame.get('type')}")
        requestId = frame.get("request_id")
        if not isinstance(requestId, str) or not requestId:
            errors.append("request_id 缺失或不是非空字符串")
        items = frame.get("items")
        if not isinstance(items, list):
            errors.append("items 缺失或不是数组")
            return errors
        if not items:
            ## 空清单会被上位机判识别清单覆盖不全并弹窗告警
            errors.append("items 为空，上位机判清单覆盖不全")
        positions: set[str] = set()
        for item in items:
            errors.extend(self.validateAckItem(item, positions))
        return errors

    ## @brief 校验单条应答条目：恰好 4 字段、货位不重复、置信度与告警类型合法
    #  @param item 应答条目
    #  @param positions 已出现过的货位号
    #  @return 错误列表
    def validateAckItem(self, item: object, positions: set[str]) -> list[str]:
        errors: list[str] = []
        if not isinstance(item, dict):
            return ["items 元素不是对象"]
        fields = set(item.keys())
        if fields != ACK_ITEM_FIELDS:
            errors.append(f"items 字段不是恰好 4 个: {sorted(fields)}")
        position = item.get("position")
        if not isinstance(position, str) or not position:
            errors.append("position 不是非空字符串")
        elif position in positions:
            errors.append(f"position 重复: {position}")
        else:
            positions.add(position)
        toolId = item.get("tool_id")
        if not isinstance(toolId, str):
            errors.append("tool_id 不是字符串")
        confidence = item.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            errors.append("confidence 不是数值")
        elif not 0.0 <= float(confidence) <= 1.0:
            errors.append(f"confidence 越界: {confidence}")
        alertType = item.get("alert_type")
        if alertType not in ALERT_TYPES:
            errors.append(f"alert_type 非法: {alertType}")
        return errors

    ## @brief 校验周期帧是否符合上位机协议
    #  @param frame 周期帧
    #  @return 错误列表，空列表表示校验通过
    def validatePeriodic(self, frame: HostFrame) -> list[str]:
        errors: list[str] = []
        if str(frame.get("type", "")) != "periodic":
            errors.append(f"帧类型不是 periodic: {frame.get('type')}")
        uptime = frame.get("uptime_sec")
        if isinstance(uptime, bool) or not isinstance(uptime, int) or uptime < 0:
            errors.append(f"uptime_sec 非法: {uptime}")
        version = frame.get("software_version")
        if not isinstance(version, str) or not version:
            errors.append("software_version 缺失或不是非空字符串")
        status = frame.get("camera_status")
        if not isinstance(status, list):
            errors.append("camera_status 缺失或不是数组")
            return errors
        cameraIds: list[str] = []
        for entry in status:
            if not isinstance(entry, dict):
                errors.append("camera_status 元素不是对象")
                continue
            cameraId = entry.get("camera_id")
            if not isinstance(cameraId, str):
                errors.append("camera_id 不是字符串")
                continue
            cameraIds.append(cameraId)
            if entry.get("status") not in CAMERA_STATUS_VALUES:
                errors.append(f"摄像头状态非法: {cameraId} {entry.get('status')}")
        for expected in CAMERA_IDS:
            if expected not in cameraIds:
                errors.append(f"camera_status 缺少 {expected}")
        return errors
