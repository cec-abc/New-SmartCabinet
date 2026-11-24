"""图形化链路监控：连接真实边缘计算机，原样显示它上报的周期帧与识别清单。"""
from __future__ import annotations

import tkinter as tk
from queue import Empty, Queue
from time import strftime
from tkinter import messagebox, ttk

from edge.lab.host_comm_sim.link_monitor import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    EVENT_ERROR,
    EVENT_RECEIVED,
    EVENT_SENT,
    EVENT_STATUS,
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    STATUS_LISTENING,
    LinkEvent,
    LinkMonitor,
)
from edge.lab.host_comm_sim.protocol import (
    FRAME_TYPE_PERIODIC,
    FRAME_TYPE_RECOGNIZE_ACK,
    HOST_FRAME_MAX_BYTES,
    buildRecognizeReq,
)

## @file edge/lab/host_comm_sim/simulator_gui.py
## @brief 界面：连接边缘计算机，只下发识别请求，周期帧与清单全部来自对端并原样全量显示
## @author 袁燕
## @note 工具不生成周期帧、不造识别数据、不折叠任何帧；收到什么就显示什么。

## @brief 窗口标题
WINDOW_TITLE: str = "边缘计算机通信监控（lab 工具）"
## @brief 窗口初始宽
WINDOW_WIDTH: int = 1280
## @brief 窗口初始高
WINDOW_HEIGHT: int = 860
## @brief 事件轮询间隔毫秒
TICK_MS: int = 100
## @brief 下发方向日志标记
DIR_TX: str = "下发 TX"
## @brief 上报方向日志标记
DIR_RX: str = "上报 RX"
## @brief 模式：等待边缘机连入（生产协议方向，工具作服务端）
MODE_LISTEN: str = "监听等待连入"
## @brief 模式：主动连接边缘机（对端须开服务端）
MODE_CONNECT: str = "主动连接边缘机"

## @brief 识别清单表格展示字段顺序
ACK_COLUMN_ORDER: tuple[str, ...] = ("position", "tool_id", "confidence", "alert_type")


## @brief 链路监控主界面
class SimulatorApp:
    ## @brief 构造界面
    #  @param root tkinter 根窗口
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._events: Queue[LinkEvent] = Queue()
        self._link = LinkMonitor(self._events)
        self._requestSeq = 0
        self._lastPeriodicFrame: dict[str, object] | None = None
        self._lastAckFrame: dict[str, object] | None = None
        self._buildWindow()
        self._buildConnectBar()
        self._buildRequestBar()
        self._buildRawFrameBar()
        self._buildWatchArea()
        self._buildLogArea()
        self._buildStatusBar()
        self._log(
            "工具就绪。填 IP 与端口后点“连接”；"
            "周期帧与识别清单全部来自边缘计算机，本工具不生成、不修改。",
        )
        self._root.after(TICK_MS, self._tick)

    ## @brief 配置根窗口
    #  @return 无
    def _buildWindow(self) -> None:
        self._root.title(WINDOW_TITLE)
        self._root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self._root.minsize(1080, 700)

    ## @brief 连接配置栏：IP、端口、模式、连接/断开
    #  @return 无
    def _buildConnectBar(self) -> None:
        bar = ttk.LabelFrame(self._root, text="连接边缘计算机", padding=(12, 10))
        bar.pack(fill=tk.X, padx=12, pady=(10, 4))
        ttk.Label(bar, text="IP 地址：").grid(row=0, column=0, sticky=tk.W)
        self._hostVar = tk.StringVar(value=DEFAULT_HOST)
        ttk.Entry(bar, textvariable=self._hostVar, width=18).grid(row=0, column=1)
        ttk.Label(bar, text="端口：").grid(row=0, column=2, padx=(12, 4))
        self._portVar = tk.StringVar(value=str(DEFAULT_PORT))
        ttk.Entry(bar, textvariable=self._portVar, width=8).grid(row=0, column=3)
        ttk.Label(bar, text="模式：").grid(row=0, column=4, padx=(16, 4))
        self._modeVar = tk.StringVar(value=MODE_LISTEN)
        ttk.Combobox(
            bar, textvariable=self._modeVar,
            values=[MODE_LISTEN, MODE_CONNECT], state="readonly", width=18,
        ).grid(row=0, column=5)
        self._connectBtn = ttk.Button(bar, text="连接", command=self._onConnect)
        self._connectBtn.grid(row=0, column=6, padx=(16, 4))
        self._disconnectBtn = ttk.Button(
            bar, text="断开", command=self._onDisconnect, state=tk.DISABLED,
        )
        self._disconnectBtn.grid(row=0, column=7)
        self._linkVar = tk.StringVar(value="链路：未连接")
        ## 状态标签本身持有颜色配置；StringVar 只管文本，改颜色须作用于 Label
        self._linkLabel = ttk.Label(bar, textvariable=self._linkVar, foreground="#c5221f")
        self._linkLabel.grid(row=1, column=0, columnspan=8, pady=(8, 0), sticky=tk.W)
        hint = (
            "默认“监听等待连入”符合生产协议：边缘机是 TCP 客户端，会主动连本机该地址与端口"
            "（与 config.ini 的 tcp.host / tcp.port 一致）。"
            "若边缘机侧开了服务端，选“主动连接边缘机”。"
        )
        ttk.Label(bar, text=hint, foreground="#555555", justify=tk.LEFT).grid(
            row=2, column=0, columnspan=8, pady=(4, 0), sticky=tk.W,
        )

    ## @brief 识别请求栏：只发请求，回什么由对端决定
    #  @return 无
    def _buildRequestBar(self) -> None:
        bar = ttk.LabelFrame(self._root, text="发送识别请求（清单由边缘机返回）", padding=(12, 10))
        bar.pack(fill=tk.X, padx=12, pady=(8, 4))
        ttk.Label(bar, text="request_id：").pack(side=tk.LEFT)
        self._requestVar = tk.StringVar(value="req-0001")
        ttk.Entry(bar, textvariable=self._requestVar, width=20).pack(side=tk.LEFT, padx=(4, 10))
        self._sendBtn = ttk.Button(bar, text="发送识别请求", command=self._onSendReq)
        self._sendBtn.pack(side=tk.LEFT)
        self._reqStatusVar = tk.StringVar(value="尚未连接边缘机")
        ttk.Label(bar, textvariable=self._reqStatusVar, foreground="#1a7f37").pack(
            side=tk.LEFT, padx=(16, 0),
        )

    ## @brief 帧编辑栏：输入任意帧文本原样下发，用于伪造异常帧验证边缘机校验
    #  @return 无
    def _buildRawFrameBar(self) -> None:
        bar = ttk.LabelFrame(
            self._root, text="帧编辑 / 原始帧下发（伪造异常帧测试用）", padding=(12, 8),
        )
        bar.pack(fill=tk.X, padx=12, pady=(4, 8))
        hint = (
            "输入完整帧文本后原样发出，不经过标准组帧（中间换行会压成空格，始终按一帧发送）。"
            "例：{\"type\":\"recognize_req\",\"request_id\":\"x\",\"extra\":\"bad\"}；"
            "也可发非法 JSON 或非对象帧测试对端校验。"
        )
        ttk.Label(bar, text=hint, foreground="#555555", justify=tk.LEFT, wraplength=980).pack(
            anchor=tk.W, pady=(0, 4),
        )
        self._rawFrameText = self._makeTextWithScroll(bar, height=3)
        btnBar = ttk.Frame(bar)
        btnBar.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btnBar, text="发送原始帧", command=self._onSendRaw).pack(side=tk.LEFT)
        self._rawStatusVar = tk.StringVar(value="")
        ttk.Label(btnBar, textvariable=self._rawStatusVar, foreground="#b06000").pack(
            side=tk.LEFT, padx=(12, 0),
        )

    ## @brief 监控展示区：周期帧（原样）+ 识别清单（原样）
    #  @return 无
    def _buildWatchArea(self) -> None:
        area = ttk.Frame(self._root, padding=(12, 4))
        area.pack(fill=tk.BOTH)

        periodic = ttk.LabelFrame(area, text="最近一帧周期帧（periodic，原样全量）", padding=10)
        periodic.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self._periodicVar = tk.StringVar(value="等待边缘机上报周期帧…")
        ttk.Label(periodic, textvariable=self._periodicVar, justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Label(periodic, text="原始帧（完整）：", foreground="#555555").pack(
            anchor=tk.W, pady=(8, 2),
        )
        self._periodicRaw = self._makeTextWithScroll(periodic, height=10)

        ack = ttk.LabelFrame(
            area, text="最近一次识别清单（recognize_ack.items，回什么显什么）", padding=10,
        )
        ack.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self._ackFrame = ttk.Frame(ack)
        self._ackFrame.pack(fill=tk.BOTH, expand=True)
        self._ackTree = ttk.Treeview(self._ackFrame, show="headings", height=8)
        self._ackTree.pack(fill=tk.BOTH, expand=True)
        ttk.Label(ack, text="原始应答（完整）：", foreground="#555555").pack(
            anchor=tk.W, pady=(8, 2),
        )
        self._ackRaw = self._makeTextWithScroll(ack, height=6)

    ## @brief 报文日志区：逐帧原文，完整不折叠
    #  @return 无
    def _buildLogArea(self) -> None:
        frame = ttk.LabelFrame(
            self._root, text="报文日志（原始帧全文，下发 TX / 上报 RX，不折叠）", padding=(12, 8),
        )
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 0))
        self._logText = tk.Text(frame, wrap=tk.NONE)
        self._logText.tag_config(DIR_TX, foreground="#0b5fa5")
        self._logText.tag_config(DIR_RX, foreground="#137333")
        self._logText.tag_config("系统", foreground="#666666")
        vScroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._logText.yview)
        hScroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self._logText.xview)
        self._logText.configure(yscrollcommand=vScroll.set, xscrollcommand=hScroll.set)
        self._logText.grid(row=0, column=0, sticky="nsew")
        vScroll.grid(row=0, column=1, sticky="ns")
        hScroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        btnBar = ttk.Frame(self._root, padding=(12, 4))
        btnBar.pack(fill=tk.X)
        ttk.Button(btnBar, text="清空日志", command=self._clearLog).pack(side=tk.RIGHT)

    ## @brief 创建带横竖滚动条的只读文本框，保证超长原文可横向查看
    #  @param parent 父容器
    #  @param height 文本框高度行数
    #  @return 文本框控件
    def _makeTextWithScroll(self, parent: ttk.Widget, height: int) -> tk.Text:
        box = ttk.Frame(parent)
        box.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(box, height=height, wrap=tk.NONE)
        vScroll = ttk.Scrollbar(box, orient=tk.VERTICAL, command=text.yview)
        hScroll = ttk.Scrollbar(box, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(yscrollcommand=vScroll.set, xscrollcommand=hScroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        vScroll.grid(row=0, column=1, sticky="ns")
        hScroll.grid(row=1, column=0, sticky="ew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        return text

    ## @brief 底部状态栏
    #  @return 无
    def _buildStatusBar(self) -> None:
        self._statusVar = tk.StringVar(value="就绪")
        ttk.Label(
            self._root, textvariable=self._statusVar, anchor=tk.W, padding=(12, 6),
        ).pack(fill=tk.X)

    ## @brief 连接：按模式监听等待连入或主动连接
    #  @return 无
    def _onConnect(self) -> None:
        host = self._hostVar.get().strip() or DEFAULT_HOST
        portText = self._portVar.get().strip()
        try:
            port = int(portText)
            if not 0 < port < 65536:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "端口须为 1~65535 的整数")
            return
        try:
            if self._modeVar.get() == MODE_CONNECT:
                self._link.startConnect(host, port)
            else:
                self._link.startListen(host, port)
        except OSError as error:
            messagebox.showerror("连接失败", str(error))
            self._log(f"连接失败: {error}")
            return
        self._connectBtn.configure(state=tk.DISABLED)
        self._disconnectBtn.configure(state=tk.NORMAL)
        self._statusVar.set(f"连接中：{host}:{port}（{self._modeVar.get()}）")

    ## @brief 断开链路
    #  @return 无
    def _onDisconnect(self) -> None:
        self._link.stop()
        self._connectBtn.configure(state=tk.NORMAL)
        self._disconnectBtn.configure(state=tk.DISABLED)
        self._statusVar.set("已断开")

    ## @brief 发送识别请求；请求编号自增，其余全由边缘机决定
    #  @return 无
    def _onSendReq(self) -> None:
        if not self._link.isConnected():
            messagebox.showwarning("提示", "尚未连接边缘机，无法下发识别请求")
            return
        requestId = self._requestVar.get().strip()
        if not requestId:
            messagebox.showwarning("提示", "请填写 request_id")
            return
        reqFrame = buildRecognizeReq(requestId)
        if self._link.sendFrame(reqFrame):
            self._reqStatusVar.set(f"已下发识别请求 {requestId}，等待边缘机回清单")
            self._statusVar.set(f"识别请求已下发：{requestId}")
            self._nextRequestId()

    ## @brief 发送编辑框里的原始帧文本；非法内容也原样发出，交由边缘机校验
    #  @return 无
    #  @note 不经 buildRecognizeReq 重写，绕过 JSON 结构化，便于伪造异常帧验证对端校验；
    #        超长帧会触发边缘机接收缓冲超限并断链，故在界面侧提醒
    def _onSendRaw(self) -> None:
        if not self._link.isConnected():
            messagebox.showwarning("提示", "尚未连接边缘机，无法下发原始帧")
            return
        text = self._rawFrameText.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请在帧编辑框输入要发送的内容")
            return
        ## 对端按换行切帧；把编辑框里的中间换行压成空格，保证多行 JSON 仍是一帧
        singleLine = " ".join(line.strip() for line in text.splitlines())
        raw = (singleLine + "\n").encode("utf-8")
        ## 1MB 缓冲上限，超过会被对端判链路异常；本地先提醒，不阻止发送以便测试
        if len(raw) > HOST_FRAME_MAX_BYTES:
            messagebox.showwarning(
                "注意",
                f"帧长度 {len(raw)} 超过 {HOST_FRAME_MAX_BYTES} 字节，"
                "边缘机会判接收缓冲超限并断链，需重新连接",
            )
        if self._link.sendRawFrame(raw):
            self._rawStatusVar.set(f"已原样下发 {len(raw)} 字节（非法帧将被对端丢弃）")
            self._log(f"[原始帧下发 {strftime('%H:%M:%S')}]\n{text}")
        else:
            self._rawStatusVar.set("下发失败，请检查链路")

    ## @brief 请求编号自增
    #  @return 无
    def _nextRequestId(self) -> None:
        self._requestSeq += 1
        self._requestVar.set(f"req-{self._requestSeq + 1:04d}")

    ## @brief 定时轮询事件队列，按事件更新界面
    #  @return 无
    def _tick(self) -> None:
        try:
            while True:
                try:
                    event = self._events.get_nowait()
                except Empty:
                    break
                try:
                    self._handleEvent(event)
                except Exception as error:
                    ## 单个事件处理失败只记日志，不能中断轮询，否则界面永远停在旧状态
                    self._log(f"事件处理失败（{type(error).__name__}）：{error}")
        finally:
            self._root.after(TICK_MS, self._tick)

    ## @brief 处理单个链路事件
    #  @param event 链路事件
    #  @return 无
    def _handleEvent(self, event: LinkEvent) -> None:
        if event.kind == EVENT_STATUS:
            self._handleStatus(event)
        elif event.kind == EVENT_RECEIVED:
            self._handleReceived(event)
        elif event.kind == EVENT_SENT:
            self._logFrame(DIR_TX, event)
        elif event.kind == EVENT_ERROR:
            self._log(event.text)
            self._statusVar.set(event.text)

    ## @brief 处理链路状态事件
    #  @param event 链路事件
    #  @return 无
    def _handleStatus(self, event: LinkEvent) -> None:
        if event.status == STATUS_CONNECTED:
            self._linkVar.set("链路：已连接")
            self._linkLabel.configure(foreground="#1a7f37")
        elif event.status == STATUS_DISCONNECTED:
            self._linkVar.set("链路：已断开")
            self._linkLabel.configure(foreground="#c5221f")
            self._reqStatusVar.set("链路已断开")
        elif event.status == STATUS_LISTENING:
            self._linkVar.set("链路：监听中，等待边缘机连入")
            self._linkLabel.configure(foreground="#b06000")
        self._log(event.text)
        self._statusVar.set(event.text)

    ## @brief 处理收到的一帧：原样写日志，按帧型更新对应展示区
    #  @param event 链路事件
    #  @return 无
    def _handleReceived(self, event: LinkEvent) -> None:
        self._logFrame(DIR_RX, event)
        frame = event.frame
        if frame is None:
            return
        frameType = str(frame.get("type", ""))
        if frameType == FRAME_TYPE_PERIODIC:
            self._lastPeriodicFrame = frame
            self._showPeriodic(frame, event.raw)
        elif frameType == FRAME_TYPE_RECOGNIZE_ACK:
            self._lastAckFrame = frame
            self._showAck(frame, event.raw)

    ## @brief 原样显示周期帧：字段值与原始帧都来自收到的数据
    #  @param frame 收到的周期帧
    #  @param raw 原始帧字节
    #  @return 无
    def _showPeriodic(self, frame: dict[str, object], raw: bytes | None) -> None:
        cameraStatus = frame.get("camera_status")
        cameras: list[str] = []
        if isinstance(cameraStatus, list):
            for entry in cameraStatus:
                if isinstance(entry, dict):
                    cameras.append(f"{entry.get('camera_id', '?')}={entry.get('status', '?')}")
        summary = (
            f"type={frame.get('type', '')}  uptime_sec={frame.get('uptime_sec', '')}  "
            f"software_version={frame.get('software_version', '')}\n"
            f"camera_status（{len(cameras)} 路，原样）：{'  '.join(cameras)}"
        )
        self._periodicVar.set(summary)
        self._setRawText(self._periodicRaw, raw, frame)
        self._statusVar.set("收到边缘机上报的周期帧（原样显示）")

    ## @brief 原样显示识别清单：表头取收到条目的字段，行数即收到条数
    #  @param frame 收到的识别应答
    #  @param raw 原始帧字节
    #  @return 无
    def _showAck(self, frame: dict[str, object], raw: bytes | None) -> None:
        for rowId in self._ackTree.get_children():
            self._ackTree.delete(rowId)
        items = frame.get("items")
        itemList = (
            [item for item in items if isinstance(item, dict)]
            if isinstance(items, list) else []
        )
        columns: list[str] = []
        for key in ACK_COLUMN_ORDER:
            if any(key in item for item in itemList):
                columns.append(key)
        for item in itemList:
            for key in item:
                if key not in columns:
                    columns.append(key)
        if not columns:
            columns = list(ACK_COLUMN_ORDER)
        self._ackTree.configure(columns=columns)
        for column in columns:
            self._ackTree.heading(column, text=column)
            self._ackTree.column(column, width=140, anchor=tk.CENTER)
        for item in itemList:
            self._ackTree.insert(
                "", tk.END, values=[str(item.get(column, "")) for column in columns],
            )
        self._setRawText(self._ackRaw, raw, frame)
        requestId = str(frame.get("request_id", ""))
        self._reqStatusVar.set(
            f"边缘机已回清单 {len(itemList)} 条（request_id={requestId}，原样显示）",
        )
        self._statusVar.set("收到边缘机回的识别清单（原样全量显示）")

    ## @brief 把原始帧完整写入文本框，不做任何截断或折叠
    #  @param widget 文本框
    #  @param raw 原始帧字节
    #  @param frame 解析后的帧
    #  @return 无
    def _setRawText(
        self, widget: tk.Text, raw: bytes | None, frame: dict[str, object],
    ) -> None:
        widget.delete("1.0", tk.END)
        if raw is not None:
            widget.insert(tk.END, raw.decode("utf-8", errors="replace").rstrip("\n"))
        else:
            widget.insert(tk.END, str(frame))

    ## @brief 把一帧完整原文写入报文日志，不折叠
    #  @param direction 方向标记
    #  @param event 链路事件
    #  @return 无
    def _logFrame(self, direction: str, event: LinkEvent) -> None:
        raw = event.raw
        payload = (
            raw.decode("utf-8", errors="replace").rstrip("\n")
            if raw is not None else ""
        )
        self._log(f"{direction} [{strftime('%H:%M:%S')}] {event.text}\n{payload}")

    ## @brief 写一行日志
    #  @param text 文本
    #  @return 无
    def _log(self, text: str) -> None:
        self._logText.insert(tk.END, text + "\n", "系统")
        self._logText.see(tk.END)

    ## @brief 清空报文日志
    #  @return 无
    def _clearLog(self) -> None:
        self._logText.delete("1.0", tk.END)
        self._statusVar.set("日志已清空")

    ## @brief 关闭窗口时断开链路
    #  @return 无
    def onClose(self) -> None:
        self._link.stop()
        self._root.destroy()

    ## @brief 启动界面
    #  @return 无
    def run(self) -> None:
        self._root.protocol("WM_DELETE_WINDOW", self.onClose)
        self._root.mainloop()


## @brief 程序入口
#  @return 无
def main() -> None:
    root = tk.Tk()
    app = SimulatorApp(root)
    app.run()


if __name__ == "__main__":
    main()
