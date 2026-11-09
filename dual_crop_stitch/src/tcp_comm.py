# @file tcp_comm.py
# @brief TCP 通信模块：纯 Python 字节流搬运器（边缘机=Client，上位机=Server）。
#
# @details
# 本模块与算法库、配置解析器彻底解耦：不 import 任何业务/算法/配置实现模块，
# 所有连接与帧编解码参数均由调度者在构造 TcpComm / FrameDecoder 时显式传入。
# 职责分两层：
#   - FrameDecoder：字节流 -> 合法 dict 的帧编解码（粘包/半包/超长/非法 JSON/
#     未知 type 五类边界），纯黑盒，无网络、无业务、无锁。
#   - TcpComm：socket 搬运、后台线程、重连、心跳、去重、离线缓存。
# 收包运行在独立守护线程 TcpCommRecv，心跳运行在 TcpCommHeartbeat，
# 与主线程视觉流水线互不阻塞；断线后按退避序列自动重连。
#
# @note 本模块属于通信层，内部的 try/except（OSError / json.JSONDecodeError /
#       UnicodeDecodeError / queue.Empty）为必要容错，属正常工程实践，不违反
#       “业务流水线不写防御判断”。
#
# @par 阅读顺序（本文件按运行流程排序，自上而下读即可）
#   单元一 FrameStats      统计快照（纯数据）
#   单元二 FrameDecoder    字节流 -> 合法 dict（收包底层）
#   单元三 TcpComm         通信主体，方法顺序 = 一条报文的生命周期：
#     ① __init__              构造：只存参数建锁，不连网、不起线程
#     ② start                 启动收包线程
#     ③ start_heartbeat       启动心跳线程
#     ④ _loop                 收包线程主干：退避→建连→收包→断线→回顶部
#     ⑤ _wait_before_retry    ┐ _loop 步骤A 调用
#     ⑥ send_periodic_once    ├ _loop 步骤C 调用（建连首发）
#     ⑦ _flush_offline_cache  ┘ _loop 步骤C 调用（重连补发）
#     ⑧ _dispatch_message     _loop 步骤E 调用：每条合法帧都过这里
#     ⑨ send                  ┐ _dispatch_message / 心跳 / 补发 都调它
#     ⑩ send_reliable         ┘ _dispatch_message 回 ack 用
#     ⑪ _heartbeat_loop       心跳线程主体（调 ⑥）
#     ⑫ is_connected / update_camera_status / recv / get_stats   查询辅助
#     ⑬ stop_heartbeat / stop 收尾（先停心跳，再停连接）
#
# @par 线程全景
#   主线程(main.py)         TcpCommRecv 线程           TcpCommHeartbeat 线程
#   ─────────────          ────────────────           ────────────────────
#   TcpComm(...)           _loop():                   _heartbeat_loop():
#   start() ─────────────→  退避等待                   每 interval 秒:
#   start_heartbeat() ──────────────────────────────→  if 连着:
#   run_pipeline()          建连 socket                 send_periodic_once()
#   while sleep(1)          send_periodic_once()           │
#                           _flush_offline_cache()         │
#                           conn.recv() 循环 ←─────────────┼── 抢 _send_lock
#                             │                            │
#                             ↓ chunk                      │
#                           decoder.feed() 切帧           │
#                             ↓ [msg, ...]                 │
#                           _dispatch_message(msg)         │
#                             ├ async(recognize) → 起业务线程跑
#                             │    process_recognize → send_reliable()
#                             └ 普通(version_query) → on_message()
#                                  → comm.send() ←────────────────────────┘

from __future__ import annotations

import json
import logging
import queue
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║ 单元一：FrameStats —— 统计快照（纯数据，无逻辑）                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

## @brief 帧编解码运行期统计快照。
## @details 累计收字节、合法帧数、各类丢弃计数；仅供日志留痕与外部查询，
##          不参与业务判定。
@dataclass
class FrameStats:
    # @brief 累计收到的原始字节数；单位: 字节（含被丢弃与超长部分）
    recv_bytes: int
    # @brief 累计成功解析并入队的合法帧数
    frames_ok: int
    # @brief 累计超长丢弃数（含无 \n 超限与单行超限两种情况）
    drop_oversize: int
    # @brief 累计 UTF-8 非法或 JSON 解析失败数
    drop_invalid_json: int
    # @brief 累计 JSON 解析成功但非 dict 数
    drop_non_dict: int
    # @brief 累计 type 不在白名单或缺失数
    drop_unknown_type: int


# ╔══════════════════════════════════════════════════════════════════════╗
# ║ 单元二：FrameDecoder —— 字节流 -> 合法 dict                            ║
# ║                                                                      ║
# ║ 【流程位置】TcpCommRecv 线程的 _loop 收到 chunk 后调 feed()，          ║
# ║   feed 返回 [msg1, msg2, ...]，_loop 再逐条 _dispatch_message。       ║
# ║                                                                      ║
# ║ 【内部顺序】__init__ -> feed -> _feed_data -> _process_line（主链路） ║
# ║            -> reset -> get_stats -> _log_drop（辅助）                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

## @brief 帧编解码器：TCP 字节流 -> 合法 JSON dict 列表。
##
## @details 以 \n 为行分隔符（协议 v1.0），处理粘包、半包、超长帧、非法 JSON、
##          未知 type 五类边界；内部维护半包缓存、超长丢弃态与统计计数。
##          纯字节->dict 黑盒，不感知业务语义、不访问网络、不依赖外部模块。
##
## @note 线程语义：被 TcpComm 收包线程（TcpCommRecv）串行调用 feed()，单一调用方
##       保证内部状态（_buffer / _discarding / 计数）无需加锁即线程安全。
class FrameDecoder:

    ## @brief 构造帧编解码器。
    ## @details 只存参数 + 初始化两个运行状态 + 六个统计计数，不做任何 I/O。
    ## @param [in] max_frame_bytes    单帧 payload 上限；单位: 字节；不含末尾 \n
    ## @param [in] known_types        业务 type 白名单；不在此列一律丢弃
    ## @param [in] drop_log_head_bytes 丢弃日志截取原始片段的前 N 字节
    ## @return None
    def __init__(self, max_frame_bytes: int,
                 known_types: frozenset[str],
                 drop_log_head_bytes: int) -> None:
        # 构造入参缓存（仅读取，不修改）
        self._max_frame_bytes = max_frame_bytes
        self._known_types = known_types
        self._drop_log_head_bytes = drop_log_head_bytes

        # ═══ 运行状态（只有两个，均被 TcpCommRecv 单线程串行访问）═══
        # 半包缓存：上次 feed 未凑齐 \n 的尾巴，留到下次拼。用 bytearray 是为了
        # 原地 del 前缀（O(n)），字节级缓存保证 UTF-8 多字节字符被半包边界
        # 劈开时不会解码失败。
        self._buffer: bytearray = bytearray()

        # 超长丢弃态：True 时只找下一个 \n，找到即恢复正常。作用：一个畸形大包
        # （无 \n 且超限）不能把后续正常帧全吞了，必须一路丢弃到下一个 \n，
        # 从那里重新开始分帧。
        self._discarding: bool = False

        # ═══ 六项统计计数，与 FrameStats 字段一一对应 ═══
        self._stat_recv_bytes: int = 0
        self._stat_frames_ok: int = 0
        self._stat_drop_oversize: int = 0
        self._stat_drop_invalid_json: int = 0
        self._stat_drop_non_dict: int = 0
        self._stat_drop_unknown_type: int = 0

    ## @brief 喂入一段 TCP 原始字节，返回本批解析出的全部合法帧。
    ## @details 内部累积半包缓存，按 \n 切行，逐行五关校验（空行/UTF-8/
    ##          JSON/dict/type 白名单）；超长帧丢弃并进入丢弃态，遇下一个
    ##          \n 恢复。任何异常输入均不抛出，只计数并日志。
    ##          调用方无需处理异常，只需消费返回的合法帧列表。
    ## @param [in] chunk 本次 recv 得到的原始字节
    ## @return List[Dict[str, Any]]；本批解析出的合法帧（可能为空列表）
    ## @note 线程语义：只能被单一线程调用（当前是 TcpCommRecv）。
    def feed(self, chunk: bytes) -> List[Dict[str, Any]]:
        # 累计原始收字节（含被丢弃与超长部分）
        self._stat_recv_bytes += len(chunk)
        return self._feed_data(chunk)

    ## @brief 核心状态机：分发丢弃态/正常态处理，循环切行并五关校验。
    ## @details 私有方法，由 feed() 调用。丢弃态优先 -> 追加 buffer -> 循环切行
    ##          -> 超长判定 -> 分发到 _process_line。任何行解析失败都不抛出。
    ## @param [in] chunk 本次 recv 的原始字节
    ## @return List[Dict[str, Any]]；本批解析出的合法帧（可能为空列表）
    ## @note 超长数据与其后紧跟的正常帧之间若无 \n 分隔，二者在协议语义上属同一
    ##       行，会被整体丢弃——这是 \n 分帧的必然结果。
    def _feed_data(self, chunk: bytes) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        # ═══ 分支一：当前处于"超长丢弃态" ═══
        # 只找一个 \n：找不到整段丢；找到则从 \n 之后重新进正常态。
        # 递归调用：\n 之后可能还有完整帧，直接复用本函数处理。
        if self._discarding:
            nl = chunk.find(b"\n")
            if nl == -1:
                return out
            self._discarding = False
            self._buffer = bytearray()
            return self._feed_data(chunk[nl + 1:])

        # ═══ 分支二：正常态，追加缓存后循环切行 ═══
        self._buffer.extend(chunk)
        while True:
            nl = self._buffer.find(b"\n")
            if nl == -1:
                # 没 \n：正常半包等下次补齐；超长则进丢弃态并清空缓存
                if len(self._buffer) > self._max_frame_bytes:
                    self._stat_drop_oversize += 1
                    self._log_drop("oversize_no_nl", self._buffer)
                    self._buffer = bytearray()
                    self._discarding = True
                break

            # 切出一行（不含 \n）；显式转 bytes 保持 _process_line 形参标注一致
            line = bytes(self._buffer[:nl])
            del self._buffer[:nl + 1]

            # 整行超长：直接丢弃并继续，仍计超长（满足"行超限"分支）。
            # 此处不出丢弃态：\n 已找到，下一行边界是干净的。
            if len(line) > self._max_frame_bytes:
                self._stat_drop_oversize += 1
                self._log_drop("oversize_line", line)
                continue

            msg = self._process_line(line)
            if msg is not None:
                out.append(msg)
        return out

    ## @brief 单行五关校验：空行 / UTF-8 / JSON / dict / type 白名单。
    ## @details 私有方法，由 _feed_data 对每行调用。通过返回 dict，任一关失败
    ##          返回 None 并累加对应丢弃计数（调用方据此跳过该行）。
    ## @param [in] line 不含 \n 的单行原始字节
    ## @return Optional[Dict[str, Any]]；合法帧返回 dict，否则返回 None
    def _process_line(self, line: bytes) -> Optional[Dict[str, Any]]:
        # 第一关：空行（\n\n）静默跳过，不计数，避免刷屏
        if line.strip() == b"":
            return None

        # 第二关：UTF-8 严格解码（非法字节计 invalid_json，与 JSON 失败同源）
        try:
            text = line.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            self._stat_drop_invalid_json += 1
            self._log_drop("invalid_utf8", line)
            return None

        # 第三关：JSON 解析（失败计 invalid_json）
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            self._stat_drop_invalid_json += 1
            self._log_drop("invalid_json", line)
            return None

        # 第四关：仅接受 dict（协议规定顶层为对象）
        if not isinstance(data, dict):
            self._stat_drop_non_dict += 1
            self._log_drop("non_dict", line)
            return None

        # 第五关：type 白名单（缺失等同未知，一律丢弃）
        ftype = data.get("type")
        if ftype not in self._known_types:
            self._stat_drop_unknown_type += 1
            self._log_drop("unknown_type", line)
            return None

        # 全部通过：累加合法帧计数并返回
        self._stat_frames_ok += 1
        return data

    ## @brief 复位内部状态（半包缓存 + 超长丢弃态），统计计数保留。
    ## @details 断线重连时调用：旧连接残包在新连接上无意义，必须清空，否则会把
    ##          两次连接的字节拼成一条畸形帧。
    ## @return None
    def reset(self) -> None:
        self._buffer = bytearray()
        self._discarding = False

    ## @brief 获取当前统计快照。
    ## @return FrameStats；快照副本（新建实例，内部计数不受外部修改影响）
    def get_stats(self) -> FrameStats:
        return FrameStats(
            recv_bytes=self._stat_recv_bytes,
            frames_ok=self._stat_frames_ok,
            drop_oversize=self._stat_drop_oversize,
            drop_invalid_json=self._stat_drop_invalid_json,
            drop_non_dict=self._stat_drop_non_dict,
            drop_unknown_type=self._stat_drop_unknown_type,
        )

    ## @brief 统一丢弃日志：reason 枚举 + size + 前 N 字节片段。
    ## @details 私有方法，由五关校验在丢弃时调用；截取 raw 前 _drop_log_head_bytes
    ##          字节防刷屏。
    ## @param [in] reason 丢弃原因枚举（oversize_no_nl / oversize_line /
    ##                    invalid_utf8 / invalid_json / non_dict / unknown_type）
    ## @param [in] raw    被丢弃的原始字节片段
    ## @return None
    def _log_drop(self, reason: str, raw: Union[bytes, bytearray]) -> None:
        # 先切片（仅取前 N 字节，O(N)）再转 bytes，避免超大帧整段复制
        head = bytes(raw[:self._drop_log_head_bytes])
        logger.error("[丢帧] reason=%s size=%d head=%r",
                     reason, len(raw), head)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║ 单元三：TcpComm —— 通信主体                                           ║
# ║                                                                      ║
# ║ 【状态分四组，互不交叉】                                              ║
# ║   A1 连接：_conn / _running / _thread / _backoff_idx / _stop_event    ║
# ║   A2 心跳：_heartbeat_thread / _heartbeat_stop_event / _camera_status ║
# ║   A4 去重：_in_flight / _completed_cache / _dedup_lock                ║
# ║   A6 离线：_offline_cache / _offline_lock                             ║
# ║   另加：_send_lock（保护 sendall）、_recv_queue（备用队列）            ║
# ╚══════════════════════════════════════════════════════════════════════╝

## @brief TCP 通信封装类：边缘机作为客户端，连接上位机（Server），按行收发 JSON。
##
## @details 本类只做字节流搬运（socket / 重连 / 线程），不识别报文语义；收包得到
##          的原始字节统一交给内置 FrameDecoder 做帧编解码（切行/校验/白名单），
##          合法帧入队并通过 on_message / async_handlers 上抛。传输约定：一行一个
##          JSON、以 \n 结尾、UTF-8 编码。
##
## @note 线程语义：start() 拉起 TcpCommRecv 守护线程后立即返回，连接/收包/重连
##       全部在该后台线程内闭环，主线程不被阻塞；start_heartbeat() 另拉起独立的
##       TcpCommHeartbeat 守护线程按间隔发送 periodic 周期帧，两条线程互不交叉
##       持有状态。
class TcpComm:

    # ────────────────────────────────────────────────────────────────
    # ① 构造：只存参数、建锁、建 decoder，不连网、不起线程
    # ────────────────────────────────────────────────────────────────

    ## @brief 构造 TCP 客户端通信器（边缘机=Client，上位机=Server）。
    ## @details 入参按功能分四组注入：A1 连接与重连、A2 心跳、A4 去重、
    ##          A6 离线缓存，另加 on_message / async_handlers 两个业务回调。
    ##          本构造不校验任何参数（含 camera_ids 与 camera_status 长度），
    ##          由调用方保证一致性；长度不一致时 send_periodic_once 内 zip
    ##          自然截断到较短者。构造本身不做任何网络 I/O。
    ## @param [in] host 上位机 IP 地址
    ## @param [in] port 上位机监听端口
    ## @param [in] reconnect_backoff 断线重连退避序列（秒）；走完停在末档循环
    ## @param [in] connect_timeout 建连超时（秒）
    ## @param [in] recv_poll_timeout 收包轮询超时（秒）；超时仅表示暂无数据
    ## @param [in] recv_buffer_size 单次 recv 缓冲区大小（字节）
    ## @param [in] heartbeat_interval 周期帧发送间隔（秒）
    ## @param [in] periodic_type 周期帧 type 字段值（来自 [heartbeat].type）
    ## @param [in] camera_ids 8 路摄像头 ID 列表（只读）
    ## @param [in] camera_status 8 路摄像头初始状态列表（拷贝一份，可被 update 覆盖）
    ## @param [in] on_message 收到非异步业务的完整报文时的回调（dict -> None）
    ## @param [in] known_types 业务 type 白名单（透传给 FrameDecoder）
    ## @param [in] max_frame_bytes 单帧 payload 上限（透传给 FrameDecoder）
    ## @param [in] drop_log_head_bytes 丢弃日志截取前 N 字节（透传给 FrameDecoder）
    ## @param [in] dedup_types 需要去重拦截的报文类型白名单
    ## @param [in] dedup_cache_ttl 已完成请求缓存保留时长（秒）
    ## @param [in] offline_cache_max 断连期间可靠消息本地缓存上限（条）
    ## @param [in] async_handlers 耗时业务注册表；type -> (msg -> payload)
    ## @return None
    def __init__(self, host: str, port: int, reconnect_backoff: List[int],
                 connect_timeout: float, recv_poll_timeout: float,
                 recv_buffer_size: int, heartbeat_interval: float,
                 periodic_type: str, camera_ids: List[str],
                 camera_status: List[str],
                 on_message: Callable[[Dict[str, Any]], None],
                 known_types: frozenset[str],
                 max_frame_bytes: int,
                 drop_log_head_bytes: int,
                 dedup_types: List[str],
                 dedup_cache_ttl: float,
                 offline_cache_max: int,
                 async_handlers: Dict[str, Callable[[dict], dict]]) -> None:

        # ═══ A1 连接与重连 ═══
        self._host = host
        self._port = port
        self._reconnect_backoff = reconnect_backoff   # 退避序列，如 [1,2,5,10]
        self._connect_timeout = connect_timeout
        self._recv_poll_timeout = recv_poll_timeout
        self._recv_buffer_size = recv_buffer_size
        self._periodic_type = periodic_type
        self._on_message = on_message                 # ← main 注册的普通报文回调

        # ═══ A2 心跳 ═══
        self._heartbeat_interval: float = heartbeat_interval
        self._camera_ids: List[str] = camera_ids              # 只读引用
        self._camera_status: List[str] = list(camera_status)  # 拷贝，可被 update 覆盖
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop_event = threading.Event()
        # 保护 _camera_status 跨线程读写（主线程 update / 心跳线程 send 快照）
        self._heartbeat_lock = threading.Lock()

        # ═══ A4 去重 ═══
        self._dedup_types: List[str] = list(dedup_types)
        self._dedup_cache_ttl: float = dedup_cache_ttl
        self._async_handlers = async_handlers     # ← main 注册的异步业务表
        self._in_flight: Set[str] = set()          # 正在处理的 request_id
        # 已完成请求缓存：request_id -> (响应包副本, 过期时间戳)，应对上位机超时重发
        self._completed_cache: Dict[str, Tuple[dict, float]] = {}
        # 保护 _in_flight 与 _completed_cache 跨线程读写（收包线程 / 业务线程）
        self._dedup_lock = threading.Lock()

        # ═══ A6 离线缓存 ═══
        self._offline_max: int = offline_cache_max
        # 断连期间的可靠消息缓存队列，元素为 (报文副本, 入队时间戳)
        self._offline_cache: List[Tuple[dict, float]] = []
        # 保护 _offline_cache 跨线程读写（业务线程写 / 重连线程读）
        self._offline_lock = threading.Lock()

        # ═══ 线程与连接句柄 ═══
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._conn: Optional[socket.socket] = None
        self._conn_lock = threading.Lock()     # 保护 _conn 读写
        self._send_lock = threading.Lock()     # 保护 sendall（多线程可能同时发）

        # 接收队列：_loop 往里 put；目前 main 没调 recv()，是备用通道
        self._recv_queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()

        # ═══ 退避状态机 ═══
        # -1 = 首次立即尝试；>=0 = 下次等待的档位下标（末档封顶）
        self._backoff_idx: int = -1
        # stop() 置位，可立即打断阻塞在退避等待中的 _loop，避免滞留最多末档秒数
        self._stop_event = threading.Event()
        # uptime 计时基准：实例创建时刻，跨重连不重置
        self._start_monotonic = time.monotonic()

        # ═══ 帧编解码器（字节流搬运与分帧严格隔离）═══
        self._decoder = FrameDecoder(
            max_frame_bytes, known_types, drop_log_head_bytes)

    # ────────────────────────────────────────────────────────────────
    # ② 启动：拉起两条后台线程，立即返回
    # ────────────────────────────────────────────────────────────────

    ## @brief 启动后台连接与收包线程（断线自动重连）。
    ## @details 仅启动一次；若已启动则直接返回。线程内部循环：连不上或断线则按
    ##          退避序列等待后重试，连接成功则持续收包并按 \n 切行上抛。
    ##          线程名固定为 "TcpCommRecv"，便于日志与调试追踪。
    ## @return None
    ## @note 本方法返回后，收包逻辑已在独立守护线程内运行，主线程可立即继续。
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="TcpCommRecv")
        self._thread.start()
        logger.info("TcpComm 收包线程 TcpCommRecv 已启动")

    ## @brief 启动周期帧心跳守护线程（幂等）。
    ## @details 若已启动则直接返回；否则清空停止信号并拉起 TcpCommHeartbeat 守护
    ##          线程，线程内部按 _heartbeat_interval 周期调用 send_periodic_once。
    ## @return None
    ## @note 本方法返回后，心跳发送已在独立守护线程内运行，主线程可立即继续。
    def start_heartbeat(self) -> None:
        if self._heartbeat_thread is not None:
            return
        self._heartbeat_stop_event.clear()
        hb_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="TcpCommHeartbeat")
        hb_thread.start()
        self._heartbeat_thread = hb_thread
        logger.info("心跳线程 TcpCommHeartbeat 已启动，间隔 %.1fs",
                    self._heartbeat_interval)

    # ────────────────────────────────────────────────────────────────
    # ③ 心脏：收包线程主循环（start() 拉起的线程跑的就是它）
    #    下面 ④⑤⑥⑦ 都是它在不同步骤调用的方法，按调用顺序排列
    # ────────────────────────────────────────────────────────────────

    ## @brief 后台主循环：连接 -> periodic 首发 -> 收包 -> 断线重连（退避序列）。
    ## @details 私有方法，由 start() 拉起的守护线程 TcpCommRecv 执行。循环内先按
    ##          退避档位等待，再建连，成功后首发 periodic 并持续收包，断开后回到
    ##          循环顶部按退避序列重试。退避状态机：_backoff_idx==-1 首次立即
    ##          尝试；建连失败 min(+1, len-1) 推进档位；建连成功复位为 0；序列
    ##          走完后恒停在末档循环。
    ## @return None
    ## @note 线程语义：本方法整体运行于 TcpCommRecv 后台线程，所有网络 I/O 不
    ##       阻塞主线程。
    def _loop(self) -> None:
        while self._running:

            # ═══ 步骤A：退避等待（首次不等，断线后按 1s→2s→5s… 等）═══
            if self._wait_before_retry():
                break   # 收到 stop 信号，退出整个循环

            # ═══ 步骤B：建连 ═══
            try:
                conn = socket.create_connection(
                    (self._host, self._port), timeout=self._connect_timeout)
            except OSError as exc:
                # 建连失败（error 级）：推进退避档位后回到循环顶部等待
                self._backoff_idx = min(self._backoff_idx + 1,
                                        len(self._reconnect_backoff) - 1)
                logger.error("建连失败：%s，%ds 后重连",
                             exc, self._reconnect_backoff[self._backoff_idx])
                continue

            # ═══ 步骤C：连接成功后的三件事 ═══
            self._backoff_idx = 0                    # 复位退避档位（下次断线从 1s 重启）
            with self._conn_lock:
                self._conn = conn                    # 保存引用，send() 会读
            self._decoder.reset()                    # 清空旧连接残包
            logger.info("已连接上位机 %s:%d", self._host, self._port)
            self.send_periodic_once()                # 首发 periodic（告诉上位机我上线）
            logger.info("重连首帧 periodic 已发送")
            self._flush_offline_cache()              # 补发断连期间攒的消息

            # ═══ 步骤D：收包循环 ═══
            try:
                conn.settimeout(self._recv_poll_timeout)
                while self._running:
                    try:
                        chunk = conn.recv(self._recv_buffer_size)
                    except (TimeoutError, getattr(socket, "timeout", TimeoutError)):
                        continue    # 读超时仅表示暂无数据，不视为断线
                    except OSError:
                        logger.warning("收包连接中断，准备重连")
                        break
                    if not chunk:
                        logger.warning("上位机主动断开，准备重连")
                        break

                    # ═══ 步骤E：字节 -> 合法帧 -> 逐条分发 ═══
                    for msg in self._decoder.feed(chunk):
                        self._recv_queue.put(msg)        # 入队（备用）
                        self._dispatch_message(msg)      # 核心分发
            finally:
                # ═══ 步骤F：断线收尾，旧连接必须关 ═══
                with self._conn_lock:
                    try:
                        self._conn.close()
                    except (OSError, AttributeError):
                        pass
                    self._conn = None

            if not self._running:
                break
            logger.warning("断开，准备重连")
            # 回到 while 顶部，重新走步骤A 等退避

    ## @brief 退避等待：按退避档位阻塞，直到被 stop 打断或等待超时。
    ## @details 私有方法，由 _loop 每次循环顶部调用。_backoff_idx==-1 表示首次
    ##          启动，立即返回 False（不等待）；>=0 时取
    ##          wait_sec = reconnect_backoff[min(idx, len-1)]（末档封顶），先打
    ##          warning 日志再 Event.wait(wait_sec)。
    ## @return bool；True 表示被 stop 置位打断（调用方据此退出循环），
    ##         False 表示等待正常完成（或首次启动不等待），调用方继续建连。
    def _wait_before_retry(self) -> bool:
        # 首次启动：不等待，直接尝试建连
        if self._backoff_idx == -1:
            return False
        # 取退避序列本地引用，避免重复长表达式
        backoff = self._reconnect_backoff
        idx = min(self._backoff_idx, len(backoff) - 1)        # 末档封顶
        wait_sec = backoff[idx]
        logger.warning("第 %d 次重连，等待 %ds", self._backoff_idx + 1, wait_sec)
        # Event.wait 可被 stop() 立即打断，不用傻等满末档
        return self._stop_event.wait(wait_sec)

    ## @brief 发送一帧 periodic 周期帧（A2 核心接口）。
    ## @details 由 _loop 建连成功首帧与 _heartbeat_loop 每周期各调用一次。
    ##          uptime_sec 以实例创建时刻为基准（time.monotonic() -
    ##          _start_monotonic），跨重连不重置；camera_status 由 _camera_ids
    ##          与当前 _camera_status 经 zip 配对，长度不一致时自然截断（不校验）。
    ## @return None
    ## @note 不检查 send() 返回值：发送失败即连接已断，_loop 的 recv 侧会立即
    ##       触发断线流程。内部日志为 debug 级，默认 INFO 下不刷屏。
    def send_periodic_once(self) -> None:
        # uptime_sec 仅计算一次，payload 与日志复用
        uptime_sec = int(time.monotonic() - self._start_monotonic)
        # 持锁仅做快照拷贝，避免锁内停留过久（主线程可能 update）
        with self._heartbeat_lock:
            status_snapshot = list(self._camera_status)
        # zip 自然配对：长度不一致时截断到较短者，无校验
        camera_status_payload = [
            {"camera_id": cid, "status": st}
            for cid, st in zip(self._camera_ids, status_snapshot)
        ]
        payload = {
            "type": self._periodic_type,
            "uptime_sec": uptime_sec,
            "camera_status": camera_status_payload,
        }
        self.send(payload)
        logger.debug("periodic 帧已发送，uptime_sec=%d", uptime_sec)

    ## @brief 重连成功后补发断连期间的缓存消息（A6）。
    ## @details 拷贝缓存后清空，逐条走 send() 补发；send() 内部会按 request_id
    ##          重新登记 _completed_cache 闭环状态。空缓存则直接返回。
    ## @return None
    def _flush_offline_cache(self) -> None:
        with self._offline_lock:
            cache_copy = list(self._offline_cache)
            self._offline_cache.clear()

        if not cache_copy:
            return
        logger.info("准备补发 %d 条断连期间缓存的消息", len(cache_copy))
        for msg, _ in cache_copy:
            self.send(msg)

    # ────────────────────────────────────────────────────────────────
    # ④ 分发枢纽：每条合法帧都过这里，决定走异步业务还是普通回调
    # ────────────────────────────────────────────────────────────────

    ## @brief 分发收到的报文（核心网关拦截逻辑）。
    ## @details 若为注册的异步业务（_async_handlers 命中），执行去重判定与线程
    ##          调度；若为普通业务（如 version_query），回调 on_message。
    ##          两条分支速记：
    ##            recognize（异步）：去重 -> 起线程跑 handler -> send_reliable 回 ack
    ##            version_query（普通）：直接 on_message -> comm.send(version_ack)
    ## @param [in] msg 解析后的报文 dict，必须包含 type 字段
    ## @return None
    ## @note 【死锁规避】_dedup_lock 内只判断，锁外调 send()/send_reliable()，
    ##       避免 _dedup_lock 自死锁。
    ## @note 【线程】在 TcpCommRecv 线程内执行；异步业务另起独立线程跑 handler，
    ##       收包线程不被阻塞。
    def _dispatch_message(self, msg: dict) -> None:
        msg_type = msg.get("type")

        # ═══ 分支一：注册过的异步业务（如 recognize）═══
        if msg_type in self._async_handlers:
            req_id = msg.get("request_id")
            if not req_id:
                logger.error("[丢弃] 异步任务缺少 request_id")
                return

            hit_resp = None
            with self._dedup_lock:
                # 1) 查已完成缓存（顺手清过期）
                if req_id in self._completed_cache:
                    resp, expire = self._completed_cache[req_id]
                    if time.monotonic() < expire:
                        hit_resp = resp      # 命中：这条之前回过包
                    else:
                        del self._completed_cache[req_id]
                # 2) 没命中缓存，查是否正在处理
                if hit_resp is None:
                    if req_id in self._in_flight:
                        return               # 正在跑，丢弃重发
                    self._in_flight.add(req_id)   # 登记在途

            # 【死锁规避】send 会拿 _dedup_lock，必须锁外调
            if hit_resp is not None:
                self.send(hit_resp)          # 重发上次响应
                return

            # 起独立线程执行业务：收包线程不阻塞
            ## @brief 异步执行业务并自动组装 _ack 回包（_dispatch_message 内部闭包）。
            ## @details 业务正常则以 result_payload 补全 ack；异常则兜底为
            ##          success=false 的 ack，保证 _in_flight 始终被 send_reliable()
            ##          闭环释放。payload 不得占用保留字段(type/request_id)。
            ## @return None
            def _run_task() -> None:
                try:
                    # ↓ 调 main.py 的 process_recognize -> run_pipeline
                    result_payload = self._async_handlers[msg_type](msg)
                    # 业务 payload 不得占用保留字段(type/request_id)，底层自动补全
                    ack = {"type": f"{msg_type}_ack", "request_id": req_id}
                    ack.update(result_payload)
                except Exception as exc:
                    logger.exception("[业务异常] %s", msg_type)
                    ack = {"type": f"{msg_type}_ack", "request_id": req_id,
                           "success": False, "error": str(exc)}
                # 【A4+A6 融合点】：回包走可靠通道，断网时缓存、重连后补发
                self.send_reliable(ack)

            threading.Thread(target=_run_task, daemon=True).start()
            return

        # ═══ 分支二：普通业务（version_query 等），原样回调 ═══
        if self._on_message is not None:
            # ↓ 调 main.py 的 on_message（虽定义在 main，但运行在 Recv 线程）
            self._on_message(msg)

    # ────────────────────────────────────────────────────────────────
    # ⑤ 发送线：所有往外发的报文都最终汇聚到 send
    # ────────────────────────────────────────────────────────────────

    ## @brief 发送一条 dict（序列化为单行 JSON + \n）。
    ## @details 在 _send_lock 保护下调用 sendall；任意异常均视为发送失败返回 False。
    ##          发送成功后按 request_id 更新去重状态（在途移除 + 写入已完成缓存，
    ##          供上位机超时重发命中）。
    ## @param [in] obj 待发送的 Python dict
    ## @return bool；发送成功返回 True，失败（未连接或异常）返回 False
    ## @note 【线程】谁调就在谁线程跑（on_message 在 Recv 线程、_run_task 在业务
    ##       线程、心跳在 Heartbeat 线程）；多线程并发靠 _send_lock 串行化。
    ## @note 【死锁规避】锁全释放后才更新去重状态，避免 _dedup_lock 自死锁。
    def send(self, obj: Dict[str, Any]) -> bool:
        # ① 序列化：\n 是分帧符，与接收端 FrameDecoder 对齐
        payload = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self._send_lock:
            with self._conn_lock:
                conn = self._conn
                if conn is None:
                    return False
                try:
                    conn.sendall(payload)
                except OSError:
                    return False
        # ② 锁全释放后才更新去重状态（响应落库供上位机超时重发）
        req_id = obj.get("request_id")
        if req_id is not None:
            with self._dedup_lock:
                self._in_flight.discard(req_id)
                self._completed_cache[req_id] = (
                    dict(obj), time.monotonic() + self._dedup_cache_ttl)
        return True

    ## @brief 可靠发送报文（A6 断连缓存机制）。
    ## @details 若当前已连接，则直接调用 send()；若断网，则连同时间戳存入离线
    ##          缓存队列，队列达到上限时丢弃最旧消息。
    ## @param [in] obj 待发送的 Python dict（必须包含 type 字段）
    ## @return bool；True 表示已发送或已成功入队
    ## @note 心跳等非关键帧不应调用本方法（心跳丢弃即可，无需补发）。
    def send_reliable(self, obj: dict) -> bool:
        if self.is_connected():
            return self.send(obj)

        with self._offline_lock:
            self._offline_cache.append((dict(obj), time.time()))
            # 超上限丢弃最旧，防爆内存
            if len(self._offline_cache) > self._offline_max:
                self._offline_cache.pop(0)
        return True

    # ────────────────────────────────────────────────────────────────
    # ⑥ 心跳线程主体（与收包线程完全独立）
    # ────────────────────────────────────────────────────────────────

    ## @brief 心跳守护线程主循环（私有）。
    ## @details 由 start_heartbeat 拉起的 TcpCommHeartbeat 线程执行。循环内先
    ##          Event.wait(_heartbeat_interval)：被 set（stop）返回 True 即退出；
    ##          超时返回 False 则判断连接状态，已连则发送一帧 periodic。
    ## @return None
    ## @note 断线期 is_connected() 为 False 跳过发送，避免空转与假日志。无
    ##       try/except：send 内部已 catch OSError，is_connected 内部已加锁，
    ##       无异常外溢。
    ## @note 【线程】本方法整体运行于 TcpCommHeartbeat 后台线程。
    def _heartbeat_loop(self) -> None:
        while True:
            # 等 interval 秒；被 stop_heartbeat 置位则返回 True，退出
            if self._heartbeat_stop_event.wait(self._heartbeat_interval):
                break
            # 连着才发，断了跳过（避免空转 + 假日志）
            if self.is_connected():
                self.send_periodic_once()

    # ────────────────────────────────────────────────────────────────
    # ⑦ 查询与辅助
    # ────────────────────────────────────────────────────────────────

    ## @brief 当前是否已建立连接。
    ## @return bool；True 表示连接可用
    ## @note 线程安全：读取 _conn 受 _conn_lock 保护。
    def is_connected(self) -> bool:
        with self._conn_lock:
            return self._conn is not None

    ## @brief 更新 8 路摄像头自检状态（供未来相机自检模块对接）。
    ## @details 主线程调用，持 _heartbeat_lock 替换 _camera_status 快照；不校验
    ##          长度，由 send_periodic_once 内 zip 自然截断到与 camera_ids 一致。
    ## @param [in] status_list 新的摄像头状态列表（List[str]）
    ## @return None
    def update_camera_status(self, status_list: List[str]) -> None:
        with self._heartbeat_lock:
            self._camera_status = list(status_list)

    ## @brief 接收一条 dict（默认非阻塞）。
    ## @details 从接收队列取数据；timeout<=0 时非阻塞（队列空即返回 None），否则
    ##          阻塞至多 timeout 秒。
    ## @param [in] timeout 阻塞等待时长（秒）；0 或负数表示非阻塞
    ## @return Optional[Dict[str, Any]]；取到报文返回 dict，超时或无数据返回 None
    ## @note 备用通道：main.py 目前依赖 on_message / async_handlers 回调，未调用
    ##       本方法。若将来启用，需注意 _recv_queue 无界，应及时消费防增长。
    def recv(self, timeout: Optional[float] = 0.0) -> Optional[Dict[str, Any]]:
        try:
            if timeout and timeout > 0:
                return self._recv_queue.get(timeout=timeout)
            return self._recv_queue.get_nowait()
        except queue.Empty:
            return None

    ## @brief 对外暴露帧编解码统计快照（A3 统计输出接口）。
    ## @details 直接转发内置 FrameDecoder 的统计；供 main.py / 运维脚本随时查询。
    ## @return FrameStats；当前帧统计快照副本
    def get_stats(self) -> FrameStats:
        return self._decoder.get_stats()

    # ────────────────────────────────────────────────────────────────
    # ⑧ 收尾：先停心跳（断源），再停连接（断管道）
    # ────────────────────────────────────────────────────────────────

    ## @brief 停止周期帧心跳守护线程（幂等）。
    ## @details 若未启动则直接返回；否则置位停止信号立即打断 Event.wait，并将
    ##          线程句柄置 None（不 join，与现有 stop() 风格一致）。线程将在本轮
    ##          wait 超时或被打断后自然退出。
    ## @return None
    ## @note 必须在 stop() 之前调用：先断心跳源，否则停连接后心跳线程仍会打
    ##       send 失败日志。
    def stop_heartbeat(self) -> None:
        if self._heartbeat_thread is None:
            return
        self._heartbeat_stop_event.set()   # 立即打断 Event.wait
        self._heartbeat_thread = None
        logger.info("心跳线程已停止")

    ## @brief 停止收包线程并关闭连接。
    ## @details 置 _running=False 使后台循环退出，置 _stop_event 立即唤醒可能阻塞
    ##          在退避等待中的 _loop，随后在锁内关闭 socket（若有），并输出收包
    ##          统计总账与去重/离线缓存状态留痕。
    ## @return None
    ## @note 调用后 TcpCommRecv 线程将在本轮循环结束时自然退出。与
    ##       stop_heartbeat() 均为幂等，重复调用安全。
    def stop(self) -> None:
        self._running = False
        self._stop_event.set()   # 立即唤醒可能阻塞在退避等待里的 _loop
        with self._conn_lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except OSError:
                    pass
                self._conn = None
        # 统计总账：留痕运行期收包与各类丢弃，便于现场排查
        stats = self._decoder.get_stats()
        logger.info(
            "TCP 停止，统计：recv_bytes=%d frames_ok=%d "
            "drop(oversize=%d invalid_json=%d non_dict=%d unknown_type=%d)",
            stats.recv_bytes, stats.frames_ok,
            stats.drop_oversize, stats.drop_invalid_json,
            stats.drop_non_dict, stats.drop_unknown_type)
        # 去重与离线缓存状态留痕：确认在途任务已闭环、缓存规模符合预期
        logger.info("去重状态：in_flight=%d completed_cache=%d；离线缓存：%d",
                    len(self._in_flight), len(self._completed_cache),
                    len(self._offline_cache))
