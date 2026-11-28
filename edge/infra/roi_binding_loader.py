"""ROI 对照表装载：把 CSV 对照表读成强类型行对象，配置类问题一律当场判错、阻断启动。

本模块同时集中约定识别结果的字段名（类别名、置信度、区域编号），
识别模块只引用这里的常量，不在识别模块里散落内部字段名字面量。
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_logger import ILogger

## @file edge/infra/roi_binding_loader.py
## @brief ROI 对照表装载：CSV 读成强类型行，配置类问题一律当场判错、阻断启动
## @author 袁燕

## @brief 标志匹配置信度缺省下限，取值与上位机 RECOG_MIN_CONFIDENCE 一致
DEFAULT_CONFIDENCE: float = 0.85
## @brief 置信度合法下界
MIN_CONFIDENCE: float = 0.0
## @brief 置信度合法上界
MAX_CONFIDENCE: float = 1.0
## @brief 数据行的起始行号；表头占第 1 行，数据从第 2 行开始
FIRST_DATA_LINE: int = 2
## @brief 可打印字符的最小码点；码点小于它的都是控制字符
MIN_PRINTABLE_CODE: int = 32
## @brief 合法的工作线程编号下界
MIN_WORKER_ID: int = 1
## @brief 合法的工作线程编号上界；8 路单摄模式下每路一个编号（1~8）
MAX_WORKER_ID: int = 8
## @brief ROI 矩形坐标绝对上限；覆盖 8K 相机全景，拦住远超画布的离谱配置
MAX_ROI_COORDINATE: int = 8192
## @brief 十二列表头里必需的九列，缺任一列即判配置错误
## tool_id / required_type / confidence 三列可缺省，由 buildRow 给默认值
REQUIRED_COLUMNS: tuple[str, ...] = (
    "roi_id",
    "worker_id",
    "drawer_id",
    "position",
    "marker_id",
    "rect_x1",
    "rect_y1",
    "rect_x2",
    "rect_y2",
)
## @brief 类别组合表必需列
CLASS_ITEM_COLUMNS: tuple[str, ...] = ("class_names", "item_name")
## @brief 识别结果里的区域编号字段名
DETECTION_ROI_FIELD: str = "roiId"
## @brief 识别结果里的类别名字段名
DETECTION_CLASS_FIELD: str = "className"
## @brief 识别结果里的置信度字段名
DETECTION_CONFIDENCE_FIELD: str = "confidence"
## @brief 识别结果里的检测框字段名；值为 [x1, y1, x2, y2] 像素坐标，相对拼接全景
DETECTION_BOX_FIELD: str = "box"
## @brief 日志模块名
MODULE_NAME: str = "RoiBindingLoader"


## @brief 对照表一行：一个 ROI 同时锁定区域几何、货位、应放工具与内部标志
@dataclass(frozen=True)
class RoiBindingRow:
    ## @brief ROI 区域唯一标识
    roiId: str
    ## @brief 归属的采集线程编号
    workerId: int
    ## @brief 所属抽屉或柜组
    drawerId: str
    ## @brief 物理货位号，与上位机清单里的货位同格式
    position: str
    ## @brief 该货位应放的工具编号，空串表示该货位不登记工具
    toolId: str
    ## @brief 该货位应放的工具类型名，供人工核对
    requiredType: str
    ## @brief ROI 内训练出的特殊标志类别名
    markerId: str
    ## @brief 标志匹配置信度下限
    confidence: float
    ## @brief 拼接全景上的 ROI 左上角横坐标
    rectX1: int
    ## @brief 拼接全景上的 ROI 左上角纵坐标
    rectY1: int
    ## @brief 拼接全景上的 ROI 右下角横坐标
    rectX2: int
    ## @brief 拼接全景上的 ROI 右下角纵坐标
    rectY2: int


## @brief 对照表装载器：只读 CSV，任何配置问题当场抛业务异常
class RoiBindingLoader:
    ## @brief 构造装载器
    #  @param logger 日志器（注入）
    #  @param confidenceThreshold 置信度缺省下限，覆盖 CSV 缺列默认值；默认取模块常量
    #  @return 无
    def __init__(self, logger: ILogger,
                 confidenceThreshold: float = DEFAULT_CONFIDENCE) -> None:
        ## @brief 日志器
        self._logger: ILogger = logger
        ## @brief 置信度缺省下限；CSV 每行 confidence 可覆盖
        self._confidenceThreshold: float = confidenceThreshold

    ## @brief 装载 ROI 对照表；文件缺失、缺列、必填为空、矩形非法、编号越界、货位重复均判配置错误
    #  @param csvPath 对照表文件路径
    #  @return 对照表行列表，顺序与文件一致
    #  @raises EdgeError 对照表不可用时抛出，code=CONFIG
    def load(self, csvPath: str) -> list[RoiBindingRow]:
        records = self.readRecords(csvPath, REQUIRED_COLUMNS)
        if not records:
            raise EdgeError(ErrorCode.CONFIG, f"ROI 对照表没有数据行: {csvPath}")
        rows: list[RoiBindingRow] = []
        positions: set[str] = set()
        for index, record in enumerate(records):
            lineNo = index + FIRST_DATA_LINE
            row = self.buildRow(record, lineNo)
            if row.position in positions:
                raise EdgeError(
                    ErrorCode.CONFIG,
                    f"ROI 对照表货位重复: {row.position} (第 {lineNo} 行)",
                )
            positions.add(row.position)
            rows.append(row)
        self._logger.info(MODULE_NAME, f"ROI 对照表装载完成 {len(rows)} 行: {csvPath}")
        return rows

    ## @brief 装载类别组合表；类别名按逗号拆开转成集合，顺序无关
    #  @param csvPath 类别组合表文件路径
    #  @return 类别集合到物品名的映射
    #  @raises EdgeError 类别组合表不可用时抛出，code=CONFIG
    def loadClassItemMap(self, csvPath: str) -> dict[frozenset[str], str]:
        records = self.readRecords(csvPath, CLASS_ITEM_COLUMNS)
        mapping: dict[frozenset[str], str] = {}
        for index, record in enumerate(records):
            lineNo = index + FIRST_DATA_LINE
            classNames = frozenset(
                part.strip()
                for part in record.get("class_names", "").split(",")
                if part.strip()
            )
            itemName = record.get("item_name", "").strip()
            if not classNames or not itemName:
                raise EdgeError(
                    ErrorCode.CONFIG,
                    f"类别组合表必填列为空 (第 {lineNo} 行): {csvPath}",
                )
            mapping[classNames] = itemName
        self._logger.info(MODULE_NAME, f"类别组合表装载完成 {len(mapping)} 行: {csvPath}")
        return mapping

    ## @brief 读 CSV 并校验表头；返回的每条记录只含表头里的列
    #  @param csvPath 文件路径
    #  @param requiredColumns 必需列名
    #  @return 数据记录列表
    #  @raises EdgeError 文件缺失、缺列、编码异常、CSV 解析失败或字段含控制字符时抛出，code=CONFIG
    def readRecords(self, csvPath: str,
                    requiredColumns: tuple[str, ...]) -> list[dict[str, str]]:
        path = Path(csvPath)
        if not path.is_file():
            raise EdgeError(ErrorCode.CONFIG, f"对照表文件不存在: {csvPath}")
        records: list[dict[str, str]] = []
        try:
            ## utf-8-sig 会读掉文件开头的 BOM，避免首列名带上不可见前缀
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldNames = reader.fieldnames or []
                missing = [name for name in requiredColumns if name not in fieldNames]
                if missing:
                    raise EdgeError(
                        ErrorCode.CONFIG,
                        f"对照表缺少列 {', '.join(missing)}: {csvPath}",
                    )
                for raw in reader:
                    record: dict[str, str] = {}
                    for key, value in raw.items():
                        if key is None:
                            continue
                        text = "" if value is None else value.strip()
                        ## 控制字符会破坏单行日志与出网帧，读到就判配置错误
                        if any(ord(char) < MIN_PRINTABLE_CODE for char in text):
                            raise EdgeError(
                                ErrorCode.CONFIG,
                                f"对照表字段含控制字符: {key} ({csvPath})",
                            )
                        record[key] = text
                    records.append(record)
        except (csv.Error, UnicodeError, OSError) as error:
            ## 编码失败与 CSV 解析失败都是内置异常，出模块边界前统一转配置错误
            raise EdgeError(ErrorCode.CONFIG, f"对照表解析失败: {error}") from error
        return records

    ## @brief 把一条 CSV 记录读成对照表行；必填为空、编号越界、矩形非法均判配置错误
    #  @param record 单条 CSV 记录
    #  @param lineNo 行号，用于报错定位
    #  @return 对照表行
    #  @raises EdgeError 记录内容不合法时抛出，code=CONFIG
    def buildRow(self, record: dict[str, str], lineNo: int) -> RoiBindingRow:
        roiId = self.requireText(record, "roi_id", lineNo)
        workerId = self.parseWorkerId(record, lineNo)
        drawerId = self.requireText(record, "drawer_id", lineNo)
        position = self.requireText(record, "position", lineNo)
        toolId = record.get("tool_id", "")
        requiredType = record.get("required_type", "")
        markerId = self.requireText(record, "marker_id", lineNo)
        confidence = self.parseConfidence(record, lineNo)
        rectX1 = self.parseInt(record, "rect_x1", lineNo)
        rectY1 = self.parseInt(record, "rect_y1", lineNo)
        rectX2 = self.parseInt(record, "rect_x2", lineNo)
        rectY2 = self.parseInt(record, "rect_y2", lineNo)
        if (rectX2 <= rectX1 or rectY2 <= rectY1
                or min(rectX1, rectY1, rectX2, rectY2) < 0
                or max(rectX1, rectY1, rectX2, rectY2) > MAX_ROI_COORDINATE):
            ## 生产链路只做相对坐标比较、不调 crop 的越界校验；装载期就必须挡住
            ## 负值与远超画布的矩形，否则检测框会被恒判"完全落在 ROI 内"
            raise EdgeError(
                ErrorCode.CONFIG,
                f"ROI 矩形非法 (第 {lineNo} 行): "
                f"({rectX1},{rectY1})-({rectX2},{rectY2})",
            )
        return RoiBindingRow(
            roiId=roiId,
            workerId=workerId,
            drawerId=drawerId,
            position=position,
            toolId=toolId,
            requiredType=requiredType,
            markerId=markerId,
            confidence=confidence,
            rectX1=rectX1,
            rectY1=rectY1,
            rectX2=rectX2,
            rectY2=rectY2,
        )

    ## @brief 取必填列文本；空值判配置错误
    #  @param record 单条 CSV 记录
    #  @param column 列名
    #  @param lineNo 行号
    #  @return 列文本
    #  @raises EdgeError 该列为空时抛出，code=CONFIG
    def requireText(self, record: dict[str, str], column: str, lineNo: int) -> str:
        text = record.get(column, "")
        if not text:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"ROI 对照表必填列为空: {column} (第 {lineNo} 行)",
            )
        return text

    ## @brief 读工作线程编号；只接受 1 到 4
    #  @param record 单条 CSV 记录
    #  @param lineNo 行号
    #  @return 工作线程编号
    #  @raises EdgeError 编号非法时抛出，code=CONFIG
    def parseWorkerId(self, record: dict[str, str], lineNo: int) -> int:
        text = self.requireText(record, "worker_id", lineNo)
        try:
            workerId = int(text)
        except ValueError as error:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"ROI 对照表工作线程编号非法: {text} (第 {lineNo} 行)",
            ) from error
        if workerId < MIN_WORKER_ID or workerId > MAX_WORKER_ID:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"ROI 对照表工作线程编号越界: {workerId} (第 {lineNo} 行)",
            )
        return workerId

    ## @brief 读置信度下限；缺省取构造注入的门槛，非有限值或越界判配置错误
    #  @param record 单条 CSV 记录
    #  @param lineNo 行号
    #  @return 置信度下限
    #  @raises EdgeError 取值非法时抛出，code=CONFIG
    def parseConfidence(self, record: dict[str, str], lineNo: int) -> float:
        text = record.get("confidence", "")
        if not text:
            return self._confidenceThreshold
        try:
            confidence = float(text)
        except ValueError as error:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"ROI 对照表置信度非法: {text} (第 {lineNo} 行)",
            ) from error
        ## nan 与上下界比较都为假，须单独挡住，否则会把非法值带进识别判定
        outOfRange = (
            not math.isfinite(confidence)
            or confidence < MIN_CONFIDENCE
            or confidence > MAX_CONFIDENCE
        )
        if outOfRange:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"ROI 对照表置信度越界: {confidence} (第 {lineNo} 行)",
            )
        return confidence

    ## @brief 读整数列；空值或非数字判配置错误
    #  @param record 单条 CSV 记录
    #  @param column 列名
    #  @param lineNo 行号
    #  @return 整数值
    #  @raises EdgeError 取值非法时抛出，code=CONFIG
    def parseInt(self, record: dict[str, str], column: str, lineNo: int) -> int:
        text = self.requireText(record, column, lineNo)
        try:
            return int(text)
        except ValueError as error:
            raise EdgeError(
                ErrorCode.CONFIG,
                f"ROI 对照表坐标非法: {column}={text} (第 {lineNo} 行)",
            ) from error
