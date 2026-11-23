"""通信协议：帧构造、序列化、解析与校验，口径对齐 edge 生产代码。"""
from __future__ import annotations

import json
from time import monotonic

## @file edge/lab/host_comm_sim/protocol.py
## @brief 上位机与边缘机通信协议的单一事实源：帧型、字段、序列化与校验
## @author 袁燕
## @note 字段口径来自 edge/app_init.py、edge/modules/tcp/tcp_comm.py、
##       edge/modules/usb/usb_controller.py、edge/tests/integration/fake_host.py。
##       本文件是 lab 演示用的独立副本，不 import 生产模块，改生产协议时须同步此处。

## @brief 上行周期帧帧型
FRAME_TYPE_PERIODIC: str = "periodic"
## @brief 下行识别请求帧型
FRAME_TYPE_RECOGNIZE_REQ: str = "recognize_req"
## @brief 上行识别应答帧型
FRAME_TYPE_RECOGNIZE_ACK: str = "recognize_ack"
## @brief 下位机关柜应答帧型（本模拟器不产生，仅用于展示上位机可识别集合）
FRAME_TYPE_CLOSE_ACK: str = "close_ack"

## @brief 上位机可识别的上行帧型全集（其它帧型会被上位机丢弃并计数）
RECOGNIZED_UPLINK_TYPES: frozenset[str] = frozenset(
    {FRAME_TYPE_PERIODIC, FRAME_TYPE_RECOGNIZE_ACK, FRAME_TYPE_CLOSE_ACK},
)

## @brief 8 路摄像头编号，顺序即物理编号
CAMERA_IDS: tuple[str, ...] = tuple(f"CAM{index}" for index in range(1, 9))
## @brief 摄像头正常状态取值
CAMERA_STATUS_OK: str = "ok"
## @brief 摄像头离线状态取值
CAMERA_STATUS_OFFLINE: str = "offline"
## @brief 摄像头状态允许取值集合
CAMERA_STATUS_VALUES: frozenset[str] = frozenset({CAMERA_STATUS_OK, CAMERA_STATUS_OFFLINE})

## @brief 识别清单条目允许的告警类型
ALERT_TYPES: frozenset[str] = frozenset(
    {"none", "misplaced", "unknown", "missing", "low_confidence"},
)
## @brief 识别清单条目必须且只允许的字段集合
ACK_ITEM_FIELDS: frozenset[str] = frozenset(
    {"position", "tool_id", "confidence", "alert_type"},
)

## @brief 边缘机上报的软件版本号（对齐 app_init.py 的 SOFTWARE_VERSION）
SOFTWARE_VERSION: str = "edge-0.1.0"
## @brief 周期帧发送间隔秒数（对齐 config.ini 的 heart_interval_sec）
HEART_INTERVAL_SEC: float = 3.0
## @brief 紧凑 JSON 分隔符，与上位机 QJsonDocument::Compact 同形
COMPACT_SEPARATORS: tuple[str, str] = (",", ":")
## @brief 上位机接收单帧硬上限字节数
HOST_FRAME_MAX_BYTES: int = 1024 * 1024


## @brief 把帧字典序列化为出网字节：紧凑 JSON + 换行，UTF-8
#  @param frame 待发送帧字典
#  @return 出网字节（含末尾换行）；UTF-8 编码失败时退回全转义
def encodeFrame(frame: dict[str, object]) -> bytes:
    try:
        text = json.dumps(frame, ensure_ascii=False, separators=COMPACT_SEPARATORS)
        return text.encode("utf-8") + b"\n"
    except UnicodeEncodeError:
        text = json.dumps(frame, ensure_ascii=True, separators=COMPACT_SEPARATORS)
        return text.encode("utf-8") + b"\n"


## @brief 把一帧出网字节解析回帧字典；超长或非对象帧抛 ValueError
#  @param raw 单帧原始字节，可含末尾换行
#  @return 解析后的帧字典
#  @raises ValueError 帧超上限、JSON 非法或帧根不是对象
def decodeFrame(raw: bytes) -> dict[str, object]:
    if len(raw) > HOST_FRAME_MAX_BYTES:
        raise ValueError(f"单帧超长 {len(raw)} > {HOST_FRAME_MAX_BYTES}")
    parsed = json.loads(raw.decode("utf-8").rstrip("\n"))
    if not isinstance(parsed, dict):
        raise ValueError("帧根必须是对象")
    return {str(key): value for key, value in parsed.items()}


## @brief 构造下行识别请求帧
#  @param requestId 请求编号
#  @param timestampMs 毫秒时间戳，缺省取当前单调时钟
#  @return 请求帧字典，恰含 type/request_id/timestamp 三键
def buildRecognizeReq(
    requestId: str,
    timestampMs: int | None = None,
) -> dict[str, object]:
    return {
        "type": FRAME_TYPE_RECOGNIZE_REQ,
        "request_id": requestId,
        "timestamp": int(monotonic() * 1000) if timestampMs is None else timestampMs,
    }


## @brief 按上位机口径校验识别应答帧
#  @param frame 待校验帧
#  @return 错误列表，空列表表示合法
def validateAck(frame: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if frame.get("type") != FRAME_TYPE_RECOGNIZE_ACK:
        errors.append(f"帧类型不是 recognize_ack: {frame.get('type')}")
    requestId = frame.get("request_id")
    if not isinstance(requestId, str) or not requestId:
        errors.append("request_id 缺失或不是非空字符串")
    items = frame.get("items")
    if not isinstance(items, list):
        errors.append("items 缺失或不是数组")
        return errors
    if not items:
        errors.append("items 为空，上位机判清单覆盖不全")
    positions: set[str] = set()
    for item in items:
        errors.extend(_validateAckItem(item, positions))
    return errors


## @brief 校验单条识别清单条目
#  @param item 待校验条目
#  @param positions 已出现货位集合，用于查重
#  @return 错误列表
def _validateAckItem(item: object, positions: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return ["items 元素不是对象"]
    if set(item.keys()) != ACK_ITEM_FIELDS:
        errors.append(f"items 字段不是恰好 4 个: {sorted(item.keys())}")
    position = item.get("position")
    if not isinstance(position, str) or not position:
        errors.append("position 不是非空字符串")
    elif position in positions:
        errors.append(f"position 重复: {position}")
    else:
        positions.add(position)
    confidence = item.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        errors.append("confidence 不是数值")
    elif not 0.0 <= float(confidence) <= 1.0:
        errors.append(f"confidence 越界: {confidence}")
    toolId = item.get("tool_id")
    if not isinstance(toolId, str):
        errors.append("tool_id 不是字符串")
    if item.get("alert_type") not in ALERT_TYPES:
        errors.append(f"alert_type 非法: {item.get('alert_type')}")
    return errors


## @brief 按上位机口径校验周期帧
#  @param frame 待校验帧
#  @return 错误列表，空列表表示合法
def validatePeriodic(frame: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if frame.get("type") != FRAME_TYPE_PERIODIC:
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
    seen: list[str] = []
    for entry in status:
        if not isinstance(entry, dict):
            errors.append("camera_status 元素不是对象")
            continue
        cameraId = entry.get("camera_id")
        if not isinstance(cameraId, str):
            errors.append("camera_id 不是字符串")
            continue
        seen.append(cameraId)
        if entry.get("status") not in CAMERA_STATUS_VALUES:
            errors.append(f"摄像头状态非法: {cameraId} {entry.get('status')}")
    for expected in CAMERA_IDS:
        if expected not in seen:
            errors.append(f"camera_status 缺少 {expected}")
    return errors
