"""TCP 底层通信封装：组帧、切帧与收发；出网字节在这里设闸。"""
from __future__ import annotations

import json

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_socket import ISocket

## @file edge/modules/tcp/tcp_comm.py
## @brief TCP 底层通信封装：组帧、切帧、收发与出网守卫
## @author 袁燕

## @brief 上位机能识别的上行帧型全集
## @note 本软件主动发出的只有 periodic 与 recognize_ack 两种；
##       close_ack 是下位机的关柜帧，列入全集仅为对齐上位机可识别帧型，本软件不产生。
##       上位机 EdgeService.cpp:362-465 的分发只认这些 type；
##       认不出的 type 落到 :463-465 的"未知 type 丢弃并计数"，
##       上位机既拿不到应答，丢弃计数又被污染。
##       出网字节只从这里出去，所以在出网口设闸最稳妥。
HOST_RECOGNIZED_FRAME_TYPES: frozenset[str] = frozenset(
    {"periodic", "recognize_ack", "close_ack"},
)
## @brief 链路就绪状态取值；心跳线程与门面共用，避免各处写死同一个字符串
LINK_UP: str = "UP"
## @brief 链路断开状态取值
LINK_DOWN: str = "DOWN"
## @brief 应答帧里的清单键名；上位机 CommTypes.h:44-47 的 items
ACK_ITEMS_FIELD: str = "items"
## @brief 紧凑 JSON 的分隔符；与上位机 QJsonDocument::Compact 同形
COMPACT_SEPARATORS: tuple[str, str] = (",", ":")
## @brief 出网单帧安全阈值占配置上限的比例
## @note 上位机 CommTypes.h:20 的 frameMaxBytes 是 1MB，EdgeLink.cpp:168-173
##       帧体超限直接 abort 断链（不是丢帧）；取一半当阈值，留一倍余量。
SAFE_FRAME_LIMIT_RATIO: float = 0.5
## @brief 上位机接收单帧硬上限字节数；取值与 CommTypes.h:20 的 frameMaxBytes 一致
HOST_FRAME_MAX_BYTES: int = 1024 * 1024
## @brief 出网安全阈值的绝对上限：上位机硬上限的一半，注入值再大也不越界
HOST_SAFE_FRAME_LIMIT_BYTES: int = HOST_FRAME_MAX_BYTES // 2
## @brief 安全阈值的最小可用值，避免注入过小上限时算出 0
MIN_SAFE_FRAME_LIMIT_BYTES: int = 1
## @brief 接收缓冲累计字节上限；取值与上位机单帧硬上限一致，防止无换行数据撑爆内存
## @note 解码线程每轮把 recv 结果累加进缓冲，一直没换行就一直攒；
##       给一个与上位机同量级的上限，超过就宣告断链，不再无限增长。
MAX_RECV_BUFFER_BYTES: int = HOST_FRAME_MAX_BYTES
## @brief 紧凑 JSON 里相邻清单条目之间的逗号占 1 字节
ITEM_SEPARATOR_BYTES: int = 1
## @brief 请求标识最大字符数；超长 ID 会在日志与队列里被放大，按坏帧拒绝
MAX_REQUEST_ID_CHARS: int = 128
## @brief 日志模块名
MODULE_NAME: str = "TcpComm"
## @brief 接收方向日志的模块名
RX_MODULE_NAME: str = "TcpRx"
## @brief 发送方向日志的模块名
TX_MODULE_NAME: str = "TcpTx"
## @brief 外部交互日志整帧落盘的帧体字节上限，超过只记折叠摘要
## @note 100 货位应答约 8KB，周期帧每 3 秒一条，逐帧全量会很快把日志撑大
IO_LOG_FULL_FRAME_BYTES: int = 4096
## @brief 折叠摘要里保留的清单前几条
IO_LOG_ITEM_PREVIEW_COUNT: int = 3
## @brief 折叠摘要的提示文案
## @note 日志里只留清单前几条摘要，没有另一份完整帧，文案按实情写。
IO_LOG_FOLDED_NOTE: str = "清单已折叠，日志仅保留前若干条摘要"


## @brief 统计按换行切帧时会被静默忽略的空行数量
#  @param buffer 当前接收缓冲
#  @return 空行数量
def countEmptyLines(buffer: bytes) -> int:
    if b"\n" not in buffer:
        return 0
    *parts, _rest = buffer.split(b"\n")
    return sum(1 for part in parts if not part)


## @brief 把帧字典整理成日志负载；小帧保留完整字段，大帧只留摘要
#  @param frame 解析后的帧字典
#  @param frameBytes 帧体字节数，便于排查帧大小，同时作为是否折叠的判据
#  @param threshold 整帧落盘的字节上限，默认取模块常量，也可由调用方注入
#  @return 可直接交给 rx / tx 的字典负载
def buildIoLogPayload(
    frame: dict[str, object],
    frameBytes: int,
    threshold: int = IO_LOG_FULL_FRAME_BYTES,
) -> dict[str, object]:
    if frameBytes <= threshold:
        full: dict[str, object] = dict(frame)
        full["frameBytes"] = frameBytes
        return full
    items = frame.get(ACK_ITEMS_FIELD)
    itemList: list[object] = list(items) if isinstance(items, list) else []
    return {
        "type": frame.get("type"),
        "request_id": frame.get("request_id"),
        "itemsCount": len(itemList),
        "itemsPreview": itemList[:IO_LOG_ITEM_PREVIEW_COUNT],
        "frameBytes": frameBytes,
        "folded": True,
        "note": IO_LOG_FOLDED_NOTE,
    }


## @brief TCP 通信封装；负责单帧字节上限、\n 切帧与 JSON 解析
class TcpComm:
    ## @brief 构造通信封装
    #  @param socket 套接字实现（注入）
    #  @param maxFrameSize 单帧字节上限，构造注入，禁止读取配置
    #  @param logger 可选日志器
    #  @return 无
    def __init__(self, socket: ISocket, maxFrameSize: int, logger: ILogger | None = None) -> None:
        ## @brief 注入的套接字
        self._socket: ISocket = socket
        ## @brief 单帧字节上限，由上层构造注入
        self._maxFrameSize: int = maxFrameSize
        ## @brief 注入的日志器
        self._logger: ILogger | None = logger
        ## @brief 出网单帧安全阈值：配置上限的一半，且不超过上位机硬上限的一半
        self._safeFrameLimit: int = min(
            max(MIN_SAFE_FRAME_LIMIT_BYTES, int(maxFrameSize * SAFE_FRAME_LIMIT_RATIO)),
            HOST_SAFE_FRAME_LIMIT_BYTES,
        )

    ## @brief 发送原始字节，失败由返回值表达
    #  @param data 待发送字节
    #  @return 发送成功返回 True
    #  @note 空载荷表示帧被出网闸拦下：交给套接字发空字节等于没有字节上线，
    #       套接字仍按自己的成败语义回话，链路状态机不会因此误判断链。
    def send(self, data: bytes) -> bool:
        return self._socket.send(data)

    ## @brief 阻塞接收一段数据
    #  @return 接收到的原始字节
    #  @note 底层按接收超时轮询；超时抛 TimeoutError，只在 tcp 模块内部当节拍信号，
    #       不转成业务异常、也不穿越模块边界；真实断链仍以 EdgeError(LINK_DOWN) 表达。
    def recv(self) -> bytes:
        return self._socket.recv()

    ## @brief 关闭底层套接字
    #  @return 无
    def close(self) -> None:
        self._socket.close()

    ## @brief 把帧字典组为出网字节并记一条发送方向日志；帧型不认识或帧体超限时不出网
    #  @param frame 已用协议键名组装的帧字典
    #  @return 可发送的字节；被闸拦下时返回空字节，表示这一帧不上网
    def encodeFrame(self, frame: dict[str, object]) -> bytes:
        if not self.isAcceptedFrameType(frame):
            ## 帧型上位机不认，送上去只会被丢弃并计数，不如不上网
            self.logRejectedFrame(frame)
            return b""
        payload = self.serializeFrame(frame)
        loggedFrame = frame
        if len(payload) > self._safeFrameLimit:
            ## 帧体超安全阈值时裁剪清单，保证不触发上位机断链
            payload = self.shrinkFrameToLimit(frame)
            ## 日志记真正上线的那一帧，避免摘要条数与实际出网帧对不上
            loggedFrame = self.parseWireFrame(payload)
        ## 出网字节只在这里成型，发送方向日志跟着这一帧只记一次
        self.logTxFrame(loggedFrame, len(payload))
        return payload + b"\n"

    ## @brief 把出网帧体还原成帧字典，供发送方向日志核对真正上线的内容
    #  @param payload 出网帧体字节，不含末尾换行
    #  @return 帧字典；解析不出对象时返回空字典
    def parseWireFrame(self, payload: bytes) -> dict[str, object]:
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        result: dict[str, object] = {}
        for key, value in parsed.items():
            if isinstance(key, str):
                result[key] = value
        return result

    ## @brief 判断帧型是否上位机认识
    #  @param frame 待判帧
    #  @return 认识返回 True
    def isAcceptedFrameType(self, frame: dict[str, object]) -> bool:
        frameType = frame.get("type")
        return (
            isinstance(frameType, str)
            and frameType in HOST_RECOGNIZED_FRAME_TYPES
        )

    ## @brief 把帧字典序列化成紧凑 JSON 字节，不含换行
    #  @param frame 待序列化帧
    #  @return UTF-8 字节
    def serializeFrame(self, frame: dict[str, object]) -> bytes:
        text = json.dumps(
            frame, ensure_ascii=False, separators=COMPACT_SEPARATORS,
        )
        try:
            return text.encode("utf-8")
        except UnicodeEncodeError:
            ## 业务载荷里混进了编不进 UTF-8 的字符时退回全转义，保证帧还能发出去
            return json.dumps(
                frame, ensure_ascii=True, separators=COMPACT_SEPARATORS,
            ).encode("utf-8")

    ## @brief 帧体超安全阈值时裁剪清单条目，裁完仍在阈值内
    #  @param frame 待裁剪帧
    #  @return 裁剪后的紧凑 JSON 字节
    #  @note 协议不支持分片：一个请求编号只对一帧应答，多发的那几帧
    #       会被上位机当重复回应丢弃并计数（EdgeService.cpp:391-396）。
    #       因此这里只截断清单，宁可让上位机判清单覆盖不全，也不能超限把链路踢掉。
    def shrinkFrameToLimit(self, frame: dict[str, object]) -> bytes:
        items = frame.get(ACK_ITEMS_FIELD)
        if not isinstance(items, list) or not items:
            ## 没有可裁剪的清单，只能原样发
            return self.serializeFrame(frame)
        trimmed: dict[str, object] = dict(frame)
        trimmed[ACK_ITEMS_FIELD] = []
        used = len(self.serializeFrame(trimmed))
        emptyBytes = len(self.serializeFrame({ACK_ITEMS_FIELD: []}))
        kept: list[object] = []
        for item in items:
            itemBytes = (
                len(self.serializeFrame({ACK_ITEMS_FIELD: [item]})) - emptyBytes
            )
            ## 两条及以上条目之间每多一条多一个逗号
            extra = itemBytes + (ITEM_SEPARATOR_BYTES if kept else 0)
            if used + extra > self._safeFrameLimit:
                break
            kept.append(item)
            used += extra
        trimmed[ACK_ITEMS_FIELD] = kept
        self.logTrimmedFrame(len(items), len(kept))
        return self.serializeFrame(trimmed)

    ## @brief 记一条帧型被拦下的日志
    #  @param frame 被拦下的帧
    #  @return 无
    def logRejectedFrame(self, frame: dict[str, object]) -> None:
        if self._logger is not None:
            self._logger.error(
                MODULE_NAME,
                f"上行帧型 {frame.get('type')!r} 不被上位机识别, 已拦截不上网",
            )

    ## @brief 记一条清单被裁剪的日志
    #  @param total 原清单条数
    #  @param kept 裁剪后保留条数
    #  @return 无
    def logTrimmedFrame(self, total: int, kept: int) -> None:
        if self._logger is not None:
            self._logger.error(
                MODULE_NAME,
                f"单帧超安全阈值 {self._safeFrameLimit} 字节, "
                f"清单裁剪为 {kept}/{total} 条后上线",
            )

    ## @brief 记录一帧出网数据；负载用解析后的帧字典，大帧自动折叠
    #  @param frame 已按协议键名组装、且与实际出网字节一致的帧字典
    #  @param frameBytes 实际出网帧体字节数
    #  @return 无
    def logTxFrame(self, frame: dict[str, object], frameBytes: int) -> None:
        if self._logger is not None:
            self._logger.tx(TX_MODULE_NAME, buildIoLogPayload(frame, frameBytes))

    ## @brief 按 \n 切分缓冲；返回完整帧与剩余未完整数据
    #  @param buffer 当前接收缓冲
    #  @return 完整帧列表与剩余缓冲
    #  @note 空行会被静默忽略；缓冲累计上限由解码线程按 MAX_RECV_BUFFER_BYTES 把关。
    def splitFrames(self, buffer: bytes) -> tuple[list[bytes], bytes]:
        if b"\n" not in buffer:
            return [], buffer
        *parts, rest = buffer.split(b"\n")
        frames = [part for part in parts if part]
        return frames, rest

    ## @brief 解析单帧；超长或非法 JSON 抛 FRAME_PARSE
    #  @param raw 单帧原始字节
    #  @return 解析后的信号字典
    #  @raises EdgeError 帧超长或 JSON 解析失败时抛出，code=FRAME_PARSE
    def decodeAndParse(self, raw: bytes) -> dict[str, object]:
        if len(raw) > self._maxFrameSize:
            raise EdgeError(ErrorCode.FRAME_PARSE, f"单帧超长 {len(raw)} > {self._maxFrameSize}")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise EdgeError(ErrorCode.FRAME_PARSE, f"帧解析失败: {exc}") from exc
        except RecursionError as exc:
            ## 深度嵌套 JSON 会抛 RecursionError（属 RuntimeError，不在上一分支）；
            ## 不转 FRAME_PARSE 会穿透到线程顶层杀死解码线程且不会触发重连
            raise EdgeError(ErrorCode.FRAME_PARSE, "帧嵌套过深") from exc
        # 帧根必须是对象，否则下游 buildIoLogPayload / signal.get 按 dict 取键会抛
        # TypeError 或取到错值；在此统一拦截，避免脏数据穿透到业务逻辑层
        if not isinstance(parsed, dict):
            raise EdgeError(ErrorCode.FRAME_PARSE, "帧根必须是对象而非数组或标量")
        requestId = parsed.get("request_id")
        if requestId is not None:
            if not isinstance(requestId, str):
                raise EdgeError(ErrorCode.FRAME_PARSE, "请求标识必须是字符串")
            if len(requestId) > MAX_REQUEST_ID_CHARS:
                raise EdgeError(
                    ErrorCode.FRAME_PARSE,
                    f"请求标识过长 {len(requestId)} > {MAX_REQUEST_ID_CHARS}",
                )
        return parsed
