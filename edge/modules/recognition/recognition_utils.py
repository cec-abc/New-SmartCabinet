"""识别模块纯函数：图像拼接、ROI 标记、空间归集、查表校验与应答组帧。"""
from __future__ import annotations

from collections.abc import Callable

from edge.interfaces.i_camera import FrameImage
from edge.interfaces.i_recognition_engine import DetectionItem
from edge.interfaces.i_sinks import AckFrame

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
## @brief 查表未命中时的占位物品名
UNKNOWN_ITEM: str = "unknown"
## @brief 应答帧类型标识
ACK_TYPE: str = "recognize_ack"


## @brief 拼接左右两路图像字节；真实图像解码与拼接留 .so 下沉
#  @param left 左路图像字节
#  @param right 右路图像字节
#  @return 拼接后的不透明字节
def cropAndMerge(left: FrameImage, right: FrameImage) -> FrameImage:
    return left + MERGE_SEPARATOR + right


## @brief 按 ROI 配置生成确定性标记字节；真实画框留 .so 下沉
#  @param image 已拼接图像字节
#  @param roiConfig ROI 配置
#  @return 附加 ROI 标记后的字节
def drawRoi(image: FrameImage, roiConfig: RoiConfig) -> FrameImage:
    ordered = sorted(roiConfig)
    payload = ",".join(f"{key}={roiConfig[key]}" for key in ordered)
    return image + ROI_MARKER + payload.encode("utf-8")


## @brief 读取检测项的 ROI 编号，未标注时归入默认组
#  @param item 单条检测结果
#  @return ROI 编号
def roiIdOf(item: DetectionItem) -> str:
    return str(item.get("roiId", ""))


## @brief 按 ROI 编号对检测结果做空间归集
#  @param items 推理检测结果
#  @return ROI 到检测项的分组
def aggregateByRoi(items: list[DetectionItem]) -> RoiGroups:
    groups: RoiGroups = {}
    for item in items:
        groups.setdefault(roiIdOf(item), []).append(item)
    return groups


## @brief 查表校验：生成应答条目，未命中类别记 unknown 并回报说明
#  @param groups 空间归集结果
#  @param classItemMap 类别到物品名映射
#  @param roiBindMap ROI 到物品名绑定
#  @return 应答条目与未命中说明列表
def validateByTable(groups: RoiGroups, classItemMap: ClassItemMap,
                    roiBindMap: RoiBindMap) -> tuple[list[AckItem], list[str]]:
    ackItems: list[AckItem] = []
    misses: list[str] = []
    for roiId in sorted(groups):
        boundItem = roiBindMap.get(roiId, UNKNOWN_ITEM)
        for item in groups[roiId]:
            className = str(item.get("className", ""))
            mapped = classItemMap.get(className)
            if mapped is None:
                misses.append(f"{roiId}/{className}")
            ## 错放与否本轮不判定：类别映射与 ROI 绑定原样带入应答，待用户拍板
            ackItems.append({
                "roiId": roiId,
                "className": className,
                "item": mapped if mapped is not None else UNKNOWN_ITEM,
                "boundItem": boundItem,
            })
    return ackItems, misses


## @brief 组装识别应答帧；保留字段 type / requestId 不被业务 payload 占用
#  @param workerId 工作线程编号
#  @param requestId 上位机请求标识
#  @param items 查表校验后的应答条目
#  @return 应答帧
def buildAck(workerId: int, requestId: str, items: list[AckItem]) -> AckFrame:
    ack: AckFrame = {"type": ACK_TYPE, "requestId": requestId, "workerId": workerId}
    ## 业务 payload 不得占用保留字段
    ack.update({"items": items})
    return ack
