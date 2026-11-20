"""上位机协议校验器：逐条复刻上位机 EdgeService 的帧校验规则，作为上位机侧裁判。

复刻依据（只读引用上位机工程 d:/CFDZ/smartCabinet/trunk/SmartCabinetLite）：

| 上位机位置 | 复刻内容 | 本模块函数 |
| --- | --- | --- |
| src/comm/EdgeService.cpp:401-408 | items 缺失或不是数组 -> 整帧拒绝 | check_items |
| src/comm/EdgeService.cpp:62-65 | items 元素不是对象 | check_items |
| src/comm/EdgeService.cpp:68-72 | position 缺失、为空或不是字符串 | check_items |
| src/comm/EdgeService.cpp:73-77 | tool_id 缺失或不是字符串（空串合法） | check_items |
| src/comm/EdgeService.cpp:78-87 | confidence 缺失/非数值、超出 0~1 | check_items |
| src/comm/EdgeService.cpp:88-94 | alert_type 缺席兼容 none；带上必须是枚举内字符串 | check_items |
| src/comm/EdgeService.cpp:95-100 | 同一货位重复上报 | check_items |
| src/comm/EdgeService.cpp:389-396 | recognize_ack 的 request_id 配对（snake_case） | check_ack |
| src/comm/EdgeService.cpp:118-132 | parsePeriodic 周期帧解析 | check_periodic |
| src/comm/EdgeService.cpp:239-247 | allCamerasOk 开柜闸门 | check_periodic |
| src/comm/EdgeService.cpp:362-465 | 帧型分发；认不出的 type 丢弃并计数 | check_frame_type |
| src/comm/EdgeLink.cpp:164-173 | 按行切帧；单帧超上限直接断链 | check_frame_size |
| src/comm/CommTypes.h:37-42 | items 每项四字段定义 | check_items |
| src/common/ProtocolAlertTypes.h:19-22 | alert_type 五值枚举 | ALERT_TYPE_VALUES |
| src/services/ToolService.cpp:115-218 | 出库取出正确判据、清单覆盖口径 | check_coverage 等 |

重要口径差异（如实记录，不粉饰）：

1. 上位机 parseItems **忽略协议外多余字段**（EdgeService.cpp:52-53 注释：收到协议外多余字段
   含历史 present 忽略，不判为结构错）。但本项目协议 spec-digest §1.5 明令禁止这些字段上线，
   因此本模块把它们单列为 extraKeys：上位机不拒，协议不容。
2. 上位机 parsePeriodic **不拒绝任何周期帧**（缺失字段退化为默认值）。因此 check_periodic 的
   errors 是"协议形状"违规而非"上位机拒收"，notes 里额外给出开柜闸门结论。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

## @file edge/tests/integration/host_protocol_checker.py
## @brief 上位机协议校验器：逐条复刻上位机 EdgeService 校验规则，输出可读中文原因
## @author 边缘计算项目

## @brief 协议帧通用类型
ProtocolFrame = dict[str, object]
## @brief items 单项类型
ProtocolItem = dict[str, object]
## @brief items 每项恰好允许出现的四个字段（CommTypes.h:37-42）
ACK_ITEM_FIELDS: frozenset[str] = frozenset({"position", "tool_id", "confidence", "alert_type"})
## @brief 协议允许的告警类型五值（ProtocolAlertTypes.h:19-22）
ALERT_TYPE_VALUES: frozenset[str] = frozenset(
    {"none", "misplaced", "unknown", "missing", "low_confidence"},
)
## @brief 协议允许的摄像头状态两值（取图失败归并到离线）
CAMERA_STATUS_VALUES: frozenset[str] = frozenset(
    {"ok", "offline"},
)
## @brief 协议明令禁止上线的历史字段（spec-digest §1.5）
FORBIDDEN_ITEM_KEYS: frozenset[str] = frozenset({"present", "alert_level", "class_id", "tool_name"})
## @brief 边缘内部字段：不得出现在线上帧里（spec-digest §8.3.3）
INTERNAL_ITEM_KEYS: frozenset[str] = frozenset(
    {"roiId", "className", "item", "boundItem", "workerId", "requestId"},
)
## @brief 入库"正确放入"的置信度门槛（Constants.h:63）
RECOG_MIN_CONFIDENCE: float = 0.85
## @brief 上位机单帧上限 1MB（CommTypes.h:20）
MAX_FRAME_BYTES: int = 1024 * 1024
## @brief 上位机 EdgeService.cpp:362-465 的分发分支认识的上行帧型
## @note 认不出的 type 落到 EdgeService.cpp:463-465 的"未知 type 丢弃并计数"：
##       上位机既拿不到应答，丢弃计数又被污染。
HOST_RECOGNIZED_FRAME_TYPES: frozenset[str] = frozenset(
    {"periodic", "recognize_ack", "close_ack"},
)


## @brief 校验结论：区分"上位机拒收"与"协议不容但上位机忽略"
@dataclass(frozen=True)
class HostCheckResult:
    ## @brief 上位机会拒绝的原因；空元组表示上位机结构校验放行
    errors: tuple[str, ...] = ()
    ## @brief 协议禁止或协议外、但上位机忽略的多余键
    extraKeys: tuple[str, ...] = ()
    ## @brief 不影响判定的补充说明（闸门结论、业务口径提示）
    notes: tuple[str, ...] = ()

    ## @brief 上位机结构校验是否放行
    #  @return 无错误返回 True
    @property
    def hostAccepts(self) -> bool:
        return not self.errors

    ## @brief 是否连协议形状也干净（无错误且无多余键）
    #  @return 全部干净返回 True
    @property
    def protocolClean(self) -> bool:
        return not self.errors and not self.extraKeys

    ## @brief 拼成一句可读中文结论
    #  @return 结论文本
    def describe(self) -> str:
        parts: list[str] = list(self.errors)
        parts.extend(f"[协议多余字段] {text}" for text in self.extraKeys)
        parts.extend(f"[提示] {text}" for text in self.notes)
        return "；".join(parts) if parts else "通过"


## @brief 判断是否为 JSON 数值；bool 在 Python 里是 int 子类，必须单独排除
#  @param value 待判值
#  @return 是数值返回 True
def isJsonNumber(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


## @brief 逐条复刻 parseItems 与 onFrameReceived 的 items 校验
#  @param items 待校验的 items 值（正常是数组）
#  @return 校验结论
def check_items(items: object) -> HostCheckResult:
    if not isinstance(items, list):
        return HostCheckResult(errors=("items 字段缺失或不是数组",))
    errors: list[str] = []
    extraKeys: list[str] = []
    seenPositions: set[str] = set()
    for index, rawItem in enumerate(items):
        line = index + 1
        if not isinstance(rawItem, dict):
            errors.append(f"第{line}项不是对象")
            continue
        item = cast(ProtocolItem, rawItem)
        keys = set(item.keys())
        for key in sorted(keys - ACK_ITEM_FIELDS):
            if key in FORBIDDEN_ITEM_KEYS:
                extraKeys.append(f"第{line}项携带协议禁止字段 {key}")
            elif key in INTERNAL_ITEM_KEYS:
                extraKeys.append(f"第{line}项携带边缘内部字段 {key}")
            else:
                extraKeys.append(f"第{line}项携带协议外字段 {key}")
        position = item.get("position")
        if not isinstance(position, str) or not position:
            errors.append(f"第{line}项 position 缺失、为空或不是字符串")
        toolId = item.get("tool_id")
        if not isinstance(toolId, str):
            errors.append(f"第{line}项 tool_id 缺失或不是字符串")
        confidence = item.get("confidence")
        if not isJsonNumber(confidence):
            errors.append(f"第{line}项 confidence 缺失或不是数值")
        elif not 0.0 <= float(cast(float, confidence)) <= 1.0:
            errors.append(f"第{line}项 confidence={confidence} 超出 0~1")
        if "alert_type" in item:
            alertType = item.get("alert_type")
            if not isinstance(alertType, str) or alertType not in ALERT_TYPE_VALUES:
                errors.append(f"第{line}项 alert_type 不是字符串或不在协议枚举内")
        if isinstance(position, str) and position:
            if position in seenPositions:
                errors.append(f"第{line}项货位 {position} 重复上报")
            else:
                seenPositions.add(position)
    return HostCheckResult(errors=tuple(errors), extraKeys=tuple(extraKeys))


## @brief 复刻 onFrameReceived 的 recognize_ack 配对与清单校验
#  @param frame 待校验的应答帧
#  @param expectRequestId 期望原样回带的请求编号
#  @return 校验结论
def check_ack(frame: object, expectRequestId: str) -> HostCheckResult:
    if not isinstance(frame, dict):
        return HostCheckResult(errors=("帧不是 JSON 对象",))
    ackFrame = cast(ProtocolFrame, frame)
    errors: list[str] = []
    notes: list[str] = []
    if ackFrame.get("type") != "recognize_ack":
        errors.append(f"帧类型不是 recognize_ack: {ackFrame.get('type')}")
    requestId = ackFrame.get("request_id")
    if not isinstance(requestId, str) or not requestId:
        errors.append(
            "request_id 缺失或不是非空字符串"
            "（协议字段名是 snake_case 的 request_id，上位机不读 requestId）",
        )
    elif requestId != expectRequestId:
        errors.append(f"request_id 与期望不符: 收到 {requestId}，期望 {expectRequestId}")
    itemResult = check_items(ackFrame.get("items"))
    errors.extend(itemResult.errors)
    notes.extend(itemResult.notes)
    return HostCheckResult(errors=tuple(errors), extraKeys=itemResult.extraKeys, notes=tuple(notes))


## @brief 复刻 parsePeriodic 的周期帧解析，并给出上位机开柜闸门结论
#  @param frame 待校验的周期帧
#  @return 校验结论；errors 为协议形状违规，notes 含闸门结论
def check_periodic(frame: object) -> HostCheckResult:
    if not isinstance(frame, dict):
        return HostCheckResult(errors=("帧不是 JSON 对象",))
    periodicFrame = cast(ProtocolFrame, frame)
    errors: list[str] = []
    notes: list[str] = []
    if periodicFrame.get("type") != "periodic":
        errors.append(f"帧类型不是 periodic: {periodicFrame.get('type')}")
    uptime = periodicFrame.get("uptime_sec")
    if not isJsonNumber(uptime):
        errors.append(f"uptime_sec 不是数值: {uptime}")
    version = periodicFrame.get("software_version")
    if not isinstance(version, str) or not version:
        errors.append(f"software_version 缺失或不是非空字符串: {version}")
    cameraStatus = periodicFrame.get("camera_status")
    abnormal: list[str] = []
    if not isinstance(cameraStatus, list):
        errors.append("camera_status 缺失或不是数组")
    else:
        for index, rawEntry in enumerate(cameraStatus):
            line = index + 1
            if not isinstance(rawEntry, dict):
                errors.append(f"camera_status 第{line}项不是对象")
                continue
            entry = cast(ProtocolItem, rawEntry)
            cameraId = entry.get("camera_id")
            if not isinstance(cameraId, str) or not cameraId:
                errors.append(f"camera_status 第{line}项 camera_id 缺失或不是非空字符串")
                continue
            status = entry.get("status")
            if status not in CAMERA_STATUS_VALUES:
                errors.append(f"camera_status 第{line}项 {cameraId} 状态非法: {status}")
                continue
            if status != "ok":
                abnormal.append(f"{cameraId}({status})")
    if abnormal:
        notes.append(f"开柜闸门将被上位机拒绝，异常摄像头: {' '.join(abnormal)}")
    elif isinstance(cameraStatus, list):
        notes.append("开柜闸门放行：已上报摄像头全部为 ok")
    return HostCheckResult(errors=tuple(errors), notes=tuple(notes))


## @brief 复刻帧型分发：判断上位机会不会把这个帧当"未知 type"丢弃
#  @param frame 待校验的帧
#  @return 校验结论
def check_frame_type(frame: object) -> HostCheckResult:
    if not isinstance(frame, dict):
        return HostCheckResult(errors=("帧不是 JSON 对象",))
    frameType = cast(ProtocolFrame, frame).get("type")
    if not isinstance(frameType, str) or not frameType:
        return HostCheckResult(errors=("帧缺少 type 字段或不是非空字符串",))
    if frameType not in HOST_RECOGNIZED_FRAME_TYPES:
        return HostCheckResult(
            errors=(
                f"上位机不认识的帧型: {frameType}"
                "（EdgeService.cpp:463-465 丢弃并计数，既拿不到应答又污染丢弃计数）",
            ),
        )
    return HostCheckResult()


## @brief 复刻链路层分帧：判断这一帧会不会把上位机踢下线
#  @param frameBytes 完整出网字节，含行尾换行；与上位机 readLine() 的 size 同口径
#  @return 校验结论
def check_frame_size(frameBytes: int) -> HostCheckResult:
    if frameBytes > MAX_FRAME_BYTES:
        return HostCheckResult(
            errors=(
                f"单帧 {frameBytes} 字节超过上位机上限 {MAX_FRAME_BYTES}，"
                "EdgeLink.cpp:168-173 会直接断链",
            ),
        )
    return HostCheckResult()


## @brief 复刻业务层覆盖口径：识别清单必须覆盖全部已登记货位
#  @param items 待校验的 items 值
#  @param registeredPositions 本机组全部已登记货位
#  @return 校验结论
def check_coverage(items: object, registeredPositions: list[str]) -> HostCheckResult:
    if not isinstance(items, list):
        return HostCheckResult(errors=("items 字段缺失或不是数组",))
    if not items:
        return HostCheckResult(
            errors=("识别清单为空，上位机判清单覆盖不全（全部货位记为未检测到）",),
        )
    reported: set[str] = set()
    for rawItem in items:
        if isinstance(rawItem, dict):
            position = cast(ProtocolItem, rawItem).get("position")
            if isinstance(position, str):
                reported.add(position)
    missing = [position for position in registeredPositions if position not in reported]
    if missing:
        return HostCheckResult(
            errors=(f"识别清单未覆盖已登记货位 {len(missing)} 个: {', '.join(missing)}",),
        )
    return HostCheckResult()


## @brief 复刻出库"取出正确"判据（ToolService.cpp:181-197）
#  @param items 已通过结构校验的 items 值
#  @param position 出库目标货位
#  @return 人读结论
def judgeOutbound(items: object, position: str) -> str:
    if not isinstance(items, list):
        return "识别清单不是数组，无法判定"
    for rawItem in items:
        if not isinstance(rawItem, dict):
            continue
        item = cast(ProtocolItem, rawItem)
        if item.get("position") != position:
            continue
        toolId = item.get("tool_id")
        if not isinstance(toolId, str):
            return "tool_id 不是字符串，无法判定"
        if toolId == "":
            return "取出正确"
        return f"货位上仍有{toolId}"
    return "识别清单未回报该货位，仅提示，不判取出正确"


## @brief 复刻入库"正确放入"判据（ToolService.cpp:159-180）
#  @param items 已通过结构校验的 items 值
#  @param position 入库目标货位
#  @param expectToolCode 该货位应放的工具编号
#  @return 人读结论
def judgeInbound(items: object, position: str, expectToolCode: str) -> str:
    if not isinstance(items, list):
        return "识别清单不是数组，无法判定"
    for rawItem in items:
        if not isinstance(rawItem, dict):
            continue
        item = cast(ProtocolItem, rawItem)
        if item.get("position") != position:
            continue
        toolId = item.get("tool_id")
        if not isinstance(toolId, str):
            return "tool_id 不是字符串，无法判定"
        if toolId == "":
            return "货位无工具或物品无法识别"
        if toolId != expectToolCode:
            return f"货位上为{toolId}"
        confidence = item.get("confidence")
        if isJsonNumber(confidence):
            value = float(cast(float, confidence))
            if value < RECOG_MIN_CONFIDENCE:
                return f"置信度{value * 100:.0f}%，未达{RECOG_MIN_CONFIDENCE * 100:.0f}%门槛"
        return "放入正确"
    return "货位为空，未检测到工具放入"
