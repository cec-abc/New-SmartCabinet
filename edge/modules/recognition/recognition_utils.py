"""识别模块纯函数：拼接标记、空间归集、查表校验与协议四键条目组帧。"""
from __future__ import annotations

from collections.abc import Callable

from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import (
    DEFAULT_CONFIDENCE,
    DETECTION_BOX_FIELD,
    DETECTION_CLASS_FIELD,
    DETECTION_CONFIDENCE_FIELD,
    DETECTION_ROI_FIELD,
    RoiBindingRow,
)
from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem
from edge.interfaces.i_sinks import AckFrame

## @file edge/modules/recognition/recognition_utils.py
## @brief 识别模块纯函数：拼接标记、空间归集、查表校验与协议四键条目组帧
## @author 袁燕

## @brief ROI 配置，键由上层按 config.ini 注入
RoiConfig = dict[str, object]
## @brief 空间归集结果：ROI 编号到检测项列表
RoiGroups = dict[str, list[DetectionItem]]
## @brief 类别名到物品名的查表
ClassItemMap = dict[str, str]
## @brief ROI 编号到物品名的绑定表
RoiBindMap = dict[str, str]
## @brief 应答帧中的单条物品
AckItem = dict[str, object]
## @brief 按目录与编号读取左右两图的注入回调
FrameLoader = Callable[[str, int], tuple[FrameImage, FrameImage]]
## @brief 推理超时执行器：执行推理函数并施加秒级上限
TimeoutRunner = Callable[[Callable[[], list[DetectionItem]], float], list[DetectionItem]]
## @brief 左右图拼接分隔符
MERGE_SEPARATOR: bytes = b"||"
## @brief ROI 标记前缀
ROI_MARKER: bytes = b"#ROI#"
## @brief 查表未命中时的占位物品名；四键条目不产出该字段，保留供查表链路说明口径
UNKNOWN_ITEM: str = "unknown"
## @brief 应答帧类型标识
ACK_TYPE: str = "recognize_ack"
## @brief 协议帧的请求标识键名，上位机只认这个蛇形写法
REQUEST_ID_FIELD: str = "request_id"
## @brief 协议帧的清单键名
ITEMS_FIELD: str = "items"
## @brief 协议条目的货位号键名
POSITION_FIELD: str = "position"
## @brief 协议条目的工具编号键名，空串表示该货位没有工具
TOOL_ID_FIELD: str = "tool_id"
## @brief 协议条目的置信度键名
CONFIDENCE_FIELD: str = "confidence"
## @brief 协议条目的告警类型键名
ALERT_TYPE_FIELD: str = "alert_type"
## @brief 告警类型：一切正常
ALERT_NONE: str = "none"
## @brief 告警类型：命中但置信度不足
ALERT_LOW_CONFIDENCE: str = "low_confidence"
## @brief 告警类型：没有识别到目标
ALERT_UNKNOWN: str = "unknown"
## @brief 告警类型：放错货位
ALERT_MISPLACED: str = "misplaced"
## @brief 告警类型：登记的工具缺失
ALERT_MISSING: str = "missing"
## @brief 上位机认可的告警类型五值，取自上位机告警枚举清单
ALERT_TYPE_VALUES: frozenset[str] = frozenset({
    ALERT_NONE, ALERT_LOW_CONFIDENCE, ALERT_UNKNOWN, ALERT_MISPLACED, ALERT_MISSING,
})
## @brief 置信度下限，与上位机判据一致
CONFIDENCE_MIN: float = 0.0
## @brief 置信度上限，与上位机判据一致
CONFIDENCE_MAX: float = 1.0
## @brief 置信度门槛，单一来源定义在 infra 装载器，与上位机 RECOG_MIN_CONFIDENCE 一致
DEFAULT_CONFIDENCE_THRESHOLD: float = DEFAULT_CONFIDENCE


## @brief 拼接左右两路图像字节；真实图像解码与拼接在拼接器里做
#  @param left 左路图像字节
#  @param right 右路图像字节
#  @return 拼接后的不透明字节
def cropAndMerge(left: FrameImage, right: FrameImage) -> FrameImage:
    return left + MERGE_SEPARATOR + right


## @brief 按 ROI 配置生成确定性标记字节；真实画框留给图像处理库
#  @param image 已拼接图像字节
#  @param roiConfig ROI 配置
#  @return 附加 ROI 标记后的字节
def drawRoi(image: FrameImage, roiConfig: RoiConfig) -> FrameImage:
    ordered = sorted(roiConfig)
    payload = ",".join(f"{key}={roiConfig[key]}" for key in ordered)
    return image + ROI_MARKER + payload.encode("utf-8")


## @brief 读取检测结果的区域编号；结果里没有区域编号时返回 None
#  @param detection 单条检测结果
#  @return 区域编号；缺该键或值为空时返回 None
#  @note 不静默吞错：缺区域编号说明推理引擎没有按区域出结果，
#        这种结果按区域归集必然塌缩成一个空组，必须由调用方显式处理，
#        所以这里返回 None 而不是空串
def roiIdOf(detection: DetectionItem) -> str | None:
    raw = detection.get(DETECTION_ROI_FIELD)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


## @brief 读取检测结果的类别名，未标注时返回空串
#  @param detection 单条检测结果
#  @return 类别名
def classNameOf(detection: DetectionItem) -> str:
    return str(detection.get(DETECTION_CLASS_FIELD, ""))


## @brief 读取检测结果的置信度；缺键或取值不是数值时按 0.0 处理
#  @param detection 单条检测结果
#  @return 置信度，取值 0 到 1
#  @note 约定：推理结果没有置信度、或置信度不是数值时按 0.0 判低置信，
#        不冒充高置信命中；布尔值也不当数值用
def confidenceOf(detection: DetectionItem) -> float:
    raw = detection.get(DETECTION_CONFIDENCE_FIELD)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0.0
    return float(raw)


## @brief 读取检测结果的检测框；缺该键（旧格式或测试桩）或形状不对时返回 None
#  @param detection 单条检测结果
#  @return (x1, y1, x2, y2) 像素坐标元组；无可解析框时返回 None
def boxOf(detection: DetectionItem) -> tuple[float, float, float, float] | None:
    raw = detection.get(DETECTION_BOX_FIELD)
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
    except (TypeError, ValueError):
        return None


## @brief 判断检测框是否完全落在 ROI 矩形内（四边都不越界）
#  @param box (x1, y1, x2, y2) 像素坐标；为 None 时直接判不在
#  @param row 对照表行，提供全景坐标系下的 ROI 矩形
#  @return 完全包含时为 True
def isBoxFullyInsideRoi(box: tuple[float, float, float, float] | None,
                        row: RoiBindingRow) -> bool:
    if box is None:
        return False
    x1, y1, x2, y2 = box
    return (x1 >= row.rectX1 and y1 >= row.rectY1
            and x2 <= row.rectX2 and y2 <= row.rectY2)


## @brief 只保留检测框完全落在 ROI 矩形内的检测项；供逐 ROI 几何判定使用
#  @param detections 全图推理得到的检测结果（带 box）
#  @param row 对照表行
#  @return 落在该 ROI 内的检测项列表
#  @note 生产检测项必带 box 字段，走严格几何判定；缺 box 是旧格式或测试桩，
#        兼容保留（视为在内）以免破坏既有行为，真实推理链路不会走到这条分支
def detectionsInRoi(detections: list[DetectionItem],
                    row: RoiBindingRow) -> list[DetectionItem]:
    kept: list[DetectionItem] = []
    for detection in detections:
        box = boxOf(detection)
        if box is None or isBoxFullyInsideRoi(box, row):
            kept.append(detection)
    return kept


## @brief 按区域编号对检测结果做空间归集
#  @param detections 推理检测结果
#  @return 区域到检测项的分组
#  @raises EdgeError 某条结果缺区域编号时抛出，code=CONFIG
#  @note 缺区域编号的结果无法归位，硬塞进空组会让整轮结果塌缩，
#        这种输入直接判配置错误，不产出误导性的分组
def aggregateByRoi(detections: list[DetectionItem]) -> RoiGroups:
    groups: RoiGroups = {}
    for detection in detections:
        roiId = roiIdOf(detection)
        if roiId is None:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"检测结果缺区域编号, 无法按区域归集: {detection}",
            )
        groups.setdefault(roiId, []).append(detection)
    return groups


## @brief 折算区域内实际放着的物品名；类别组合查不到时返回空串
#  @param detections 该区域内的检测结果
#  @param classItemMap 类别到物品名映射
#  @return 物品名与最高置信度
def resolveActualItem(detections: list[DetectionItem],
                      classItemMap: ClassItemMap) -> tuple[str, float]:
    if not detections:
        return "", 0.0
    confidence = max(confidenceOf(detection) for detection in detections)
    classNames = frozenset(classNameOf(detection) for detection in detections)
    if len(classNames) == 1:
        return classItemMap.get(next(iter(classNames)), ""), confidence
    ## 多个类别时按逗号连接的组合名查表，类别顺序不影响命中
    return classItemMap.get(",".join(sorted(classNames)), ""), confidence


## @brief 查表校验：按 ROI 配置逐区域产出协议条目，登记区域一行不漏；无检测结果时补一条未识别条目
#  @param groups 空间归集结果
#  @param classItemMap 类别到物品名映射
#  @param roiBindMap 区域到应放物品名绑定
#  @param roiConfig 区域到货位号配置
#  @param confidenceThreshold 置信度门槛，默认取模块常量，可被配置覆盖透传
#  @return 协议条目与未命中说明列表
def validateByTable(groups: RoiGroups, classItemMap: ClassItemMap,
                    roiBindMap: RoiBindMap, roiConfig: RoiConfig,
                    confidenceThreshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                    ) -> tuple[list[AckItem], list[str]]:
    items: list[AckItem] = []
    misses: list[str] = []
    seenPositions: set[str] = set()
    roiIds = sorted(set(roiConfig) | set(groups))
    for roiId in roiIds:
        position = str(roiConfig.get(roiId, ""))
        if not position:
            misses.append(f"{roiId}/无货位映射")
            continue
        if position in seenPositions:
            ## 同一货位重复上报会让上位机把整帧判为不可信，这里只保留第一条
            misses.append(f"{roiId}/货位重复")
            continue
        seenPositions.add(position)
        detections = groups.get(roiId, [])
        expected = roiBindMap.get(roiId, "")
        actual, confidence = resolveActualItem(detections, classItemMap)
        for detection in detections:
            if classNameOf(detection) not in classItemMap:
                misses.append(f"{roiId}/{classNameOf(detection)}")
        items.append(buildConfigItem(
            position, expected, actual, confidence, confidenceThreshold,
        ))
    return items, misses


## @brief 备用配置链路按 ROI 配置的货位号与应放物品产出一条协议条目
#  @param position 货位号
#  @param expected 该货位应放的物品名
#  @param actual 实际识别出的物品名，认不出时为空串
#  @param confidence 实际识别置信度
#  @param confidenceThreshold 置信度门槛，默认取模块常量，可被配置覆盖
#  @return 协议条目，恰好四个键
def buildConfigItem(position: str, expected: str, actual: str, confidence: float,
                    confidenceThreshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                    ) -> AckItem:
    if not actual:
        ## 认不出是哪件物品时按未识别处理，工具编号置空、置信度归零
        return buildAckItem(position, "", 0.0, ALERT_UNKNOWN)
    if expected and actual != expected:
        return buildAckItem(position, actual, confidence, ALERT_MISPLACED)
    if confidence < confidenceThreshold:
        return buildAckItem(position, actual, confidence, ALERT_LOW_CONFIDENCE)
    return buildAckItem(position, actual, confidence, ALERT_NONE)


## @brief 判断区域里有没有命中标志，并给出命中时的置信度
#  @param detections 该区域内的检测结果
#  @param markerId 对照表行里登记的标志类别名
#  @param classItemMap 类别组合到物品名映射，为空时按单个标志直映
#  @return 命中标记与命中置信度
def matchMarker(detections: list[DetectionItem], markerId: str,
                classItemMap: dict[frozenset[str], str]) -> tuple[bool, float]:
    if not detections:
        return False, 0.0
    detectedClasses = frozenset(classNameOf(detection) for detection in detections)
    if classItemMap:
        ## 类别组合表：检测到的类别集合【包含】组合键即命中，
        ## 区域里出现其他杂物类不影响判定（如榔头+红标签齐了就认 C）
        for comboClasses, itemName in classItemMap.items():
            if itemName == markerId and comboClasses.issubset(detectedClasses):
                matched = [
                    detection for detection in detections
                    if classNameOf(detection) in comboClasses
                ]
                return True, max(confidenceOf(d) for d in matched)
    ## 组合表折算不出物品名时，按单个标志直映
    matched = [
        detection for detection in detections
        if classNameOf(detection) == markerId
    ]
    if not matched:
        return False, 0.0
    return True, max(confidenceOf(detection) for detection in matched)


## @brief 按对照表行产出一条协议条目
#  @param row 对照表行
#  @param detected 区域里有没有命中标志
#  @param confidence 命中时的实际置信度
#  @return 协议条目，恰好四个键
def buildRowItem(row: RoiBindingRow, detected: bool, confidence: float) -> AckItem:
    if not detected:
        ## 没命中标志时工具编号置空、置信度归零，告警类型为未识别
        return buildAckItem(row.position, "", 0.0, ALERT_UNKNOWN)
    if confidence < row.confidence:
        return buildAckItem(row.position, row.toolId, confidence, ALERT_LOW_CONFIDENCE)
    return buildAckItem(row.position, row.toolId, confidence, ALERT_NONE)


## @brief 按协议拼出恰好四个键的识别条目
#  @param position 货位号
#  @param toolId 工具编号，空串表示该货位没有工具
#  @param confidence 置信度，取值 0 到 1
#  @param alertType 告警类型
#  @return 协议条目，恰好四个键
#  @note 上位机对越界置信度会把整帧判为不可信，所以出帧前把数值钳在 0 到 1，
#        并统一转成浮点数，避免整数写成另一种 JSON 数值类型
def buildAckItem(position: str, toolId: str, confidence: float,
                 alertType: str) -> AckItem:
    bounded = min(max(float(confidence), CONFIDENCE_MIN), CONFIDENCE_MAX)
    return {
        POSITION_FIELD: position,
        TOOL_ID_FIELD: toolId,
        CONFIDENCE_FIELD: bounded,
        ALERT_TYPE_FIELD: alertType,
    }


## @brief 组装识别应答帧；顶层只有帧类型、请求标识与清单三个键
#  @param requestId 上位机请求标识
#  @param items 协议条目列表
#  @return 应答帧
def buildAck(requestId: str, items: list[AckItem]) -> AckFrame:
    return {"type": ACK_TYPE, REQUEST_ID_FIELD: requestId, ITEMS_FIELD: items}
