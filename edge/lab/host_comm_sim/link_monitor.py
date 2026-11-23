"""链路监控：扮演上位机收发真实 TCP 帧，只转发收到的内容，不生成任何数据。"""
from __future__ import annotations

import socket
from queue import Queue
from threading import Event, Lock, Thread

from edge.lab.host_comm_sim.protocol import decodeFrame, encodeFrame

## @file edge/lab/host_comm_sim/link_monitor.py
## @brief 真实 TCP 链路：监听/主动连接两种模式，按换行切帧，收发原文通过队列推给界面
## @author 袁燕
## @note 边缘机是 TCP 客户端，主动连上位机服务端（见 edge/modules/tcp/tcp_socket.py）。
##       本工具扮演上位机：默认监听地址与端口，等真实边缘机连入；周期帧与识别应答
##       全部来自对端，工具不生成、不修改、不折叠，只做原样收发与展示。

## @brief 单次接收最大字节数
RECV_BUFFER_SIZE: int = 65536
## @brief 套接字轮询超时秒数，用于响应停止指令
POLL_TIMEOUT_SEC: float = 0.2
## @brief 主动连接超时秒数
CONNECT_TIMEOUT_SEC: float = 5.0
## @brief 默认监听地址：全部网卡，便于边缘机从任意网卡连入
DEFAULT_HOST: str = "0.0.0.0"
## @brief 默认监听端口，与 config.ini 的 tcp.port 一致
DEFAULT_PORT: int = 9000
## @brief 事件类型：链路状态变化
EVENT_STATUS: str = "status"
## @brief 事件类型：收到一帧
EVENT_RECEIVED: str = "received"
## @brief 事件类型：发出一帧
EVENT_SENT: str = "sent"
## @brief 事件类型：异常
EVENT_ERROR: str = "error"
## @brief 状态：已监听等待连入
STATUS_LISTENING: str = "listening"
## @brief 状态：已连接
STATUS_CONNECTED: str = "connected"
## @brief 状态：已断开
STATUS_DISCONNECTED: str = "disconnected"


## @brief 链路事件：携带类型、状态、说明、原始字节与解析帧
class LinkEvent:
    ## @brief 构造事件
    #  @param kind 事件类型
    #  @param status 链路状态，非状态事件传空串
    #  @param text 说明文字
    #  @param raw 原始帧字节，非帧事件为 None
    #  @param frame 解析后的帧字典，解析失败为 None
    def __init__(self, kind: str, status: str, text: str,
                 raw: bytes | None = None,
                 frame: dict[str, object] | None = None) -> None:
        self.kind: str = kind
        self.status: str = status
        self.text: str = text
        self.raw: bytes | None = raw
        self.frame: dict[str, object] | None = frame


## @brief 链路监控器：管理监听/连接/收发，线程安全，事件经队列交给界面
class LinkMonitor:
    ## @brief 构造监控器
    #  @param eventQueue 事件队列，界面侧消费
    def __init__(self, eventQueue: Queue[LinkEvent]) -> None:
        ## @brief 事件队列
        self._queue: Queue[LinkEvent] = eventQueue
        ## @brief 停止事件
        self._stop: Event = Event()
        ## @brief 当前数据连接
        self._conn: socket.socket | None = None
        ## @brief 监听套接字
        self._server: socket.socket | None = None
        ## @brief 工作线程
        self._thread: Thread | None = None
        ## @brief 发送锁，避免界面线程与接收线程并发写
        self._sendLock: Lock = Lock()
        ## @brief 当前是否已连接
        self._connected: bool = False

    ## @brief 是否已连接
    #  @return 已连接返回 True
    def isConnected(self) -> bool:
        return self._connected

    ## @brief 启动监听，等边缘机主动连入（生产协议方向）
    #  @param host 监听地址
    #  @param port 监听端口
    #  @return 无
    #  @raises OSError 地址或端口不可用
    def startListen(self, host: str, port: int) -> None:
        self.stop()
        self._stop.clear()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        server.settimeout(POLL_TIMEOUT_SEC)
        self._server = server
        self._thread = Thread(target=self._listenLoop, args=(server,), daemon=True)
        self._thread.start()
        self._push(LinkEvent(EVENT_STATUS, STATUS_LISTENING,
                             f"已监听 {host}:{port}，等待边缘机连入"))

    ## @brief 主动连接对端（对端须已开服务端；生产边缘机默认不开）
    #  @param host 对端地址
    #  @param port 对端端口
    #  @return 无
    #  @raises OSError 连接失败
    def startConnect(self, host: str, port: int) -> None:
        self.stop()
        self._stop.clear()
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.settimeout(CONNECT_TIMEOUT_SEC)
        conn.connect((host, port))
        conn.settimeout(POLL_TIMEOUT_SEC)
        self._conn = conn
        self._connected = True
        self._thread = Thread(target=self._recvLoop, args=(conn,), daemon=True)
        self._thread.start()
        self._push(LinkEvent(EVENT_STATUS, STATUS_CONNECTED,
                             f"已连接边缘机 {host}:{port}"))

    ## @brief 发送一帧并把原文作为“下发”事件推给界面
    #  @param frame 待发送帧字典
    #  @return 发送成功返回 True
    def sendFrame(self, frame: dict[str, object]) -> bool:
        conn = self._conn
        if conn is None or not self._connected:
            self._push(LinkEvent(EVENT_ERROR, "", "未连接，无法下发帧"))
            return False
        raw = encodeFrame(frame)
        with self._sendLock:
            try:
                conn.sendall(raw)
            except OSError as error:
                self._push(LinkEvent(EVENT_ERROR, "", f"下发失败: {error}"))
                return False
        self._push(LinkEvent(EVENT_SENT, "", "上位机下发一帧", raw, frame))
        return True

    ## @brief 停止监控并释放套接字；重复调用安全
    #  @return 无
    def stop(self) -> None:
        self._stop.set()
        conn = self._conn
        server = self._server
        self._conn = None
        self._server = None
        wasConnected = self._connected
        self._connected = False
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        if server is not None:
            try:
                server.close()
            except OSError:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None
        if wasConnected:
            self._push(LinkEvent(EVENT_STATUS, STATUS_DISCONNECTED, "链路已断开"))

    ## @brief 监听循环：接受到第一个边缘机连接后转入收帧循环，断链后继续等待
    #  @param server 监听套接字
    #  @return 无
    def _listenLoop(self, server: socket.socket) -> None:
        while not self._stop.is_set():
            try:
                conn, address = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(POLL_TIMEOUT_SEC)
            self._conn = conn
            self._connected = True
            self._push(LinkEvent(EVENT_STATUS, STATUS_CONNECTED,
                                 f"边缘机已连入 {address[0]}:{address[1]}"))
            self._recvLoop(conn)
            self._connected = False
            self._conn = None
            try:
                conn.close()
            except OSError:
                pass
            if self._stop.is_set():
                break
            self._push(LinkEvent(EVENT_STATUS, STATUS_DISCONNECTED,
                                 "边缘机断开，继续等待重新连入"))

    ## @brief 收帧循环：按换行切帧，原文与解析结果一并推给界面
    #  @param conn 数据连接
    #  @return 无
    def _recvLoop(self, conn: socket.socket) -> None:
        buffer: bytes = b""
        while not self._stop.is_set():
            try:
                data = conn.recv(RECV_BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buffer += data
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                raw = line + b"\n"
                parsed: dict[str, object] | None = None
                note = ""
                try:
                    parsed = decodeFrame(raw)
                    frameType = parsed.get("type", "未知帧型")
                    note = f"收到 {frameType}"
                except (ValueError, UnicodeDecodeError) as error:
                    note = f"收到无法解析的帧: {error}"
                self._push(LinkEvent(EVENT_RECEIVED, "", note, raw, parsed))

    ## @brief 把事件放入队列
    #  @param event 事件
    #  @return 无
    def _push(self, event: LinkEvent) -> None:
        self._queue.put(event)
