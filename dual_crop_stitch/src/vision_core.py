# @file vision_core.py
# @brief 视觉算法核心库：图像算法与数据结构的封闭黑盒。
#
# @details
# 本文件是系统的封闭黑盒，编译为单一动态库 vision_core.so（Linux 麒麟）/
# vision_core.pyd（Windows）后由 main.py 统一调度。编译后源码不可见，故所有
# 关键算法与坐标运算的注释必须在本文件中交代清楚。
# 运行环境依赖：cv2 / numpy / logging / dataclasses / typing，以及 ultralytics
# （其内部自动调度 onnxruntime 加载 .onnx 权重）。不 import 项目任何其他模块，
# 以保证动态库的高内聚与可独立部署。
#
# @note 失败一律通过返回的 success 字段或空列表暴露，由 main.py 决定是否拦截；
#       本库内部除 yolo_init 加载失败外不主动抛异常。
# @warning 编译到边缘设备前，请确认 numpy / opencv / ultralytics 版本与开发端一致，
#          否则 .so/.pyd 的符号表可能不兼容。

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# 模块级状态：YOLO 模型句柄与推理缓存参数（仅由 yolo_init 写入，yolo_detect 只读）。
# @note _confThreshold / _imgSize 的默认值（0.25 / 640）仅作向下兼容占位，
#       实际值始终由 yolo_init 调用方显式传入。
_model = None
_confThreshold = 0.25
_imgSize = 640


## @brief 切割结果数据结构。
## @details 封装左右双摄裁剪图与执行状态；success=False 时 leftImage/rightImage 为 None。
@dataclass
class CropResult:
    # @brief 左摄裁剪图，取自左原图右半；单位: 像素；尺寸 (cropHeight, cropWidth, 3) BGR
    leftImage: Optional[np.ndarray]
    # @brief 右摄裁剪图，取自右原图左半；单位: 像素；尺寸 (cropHeight, cropWidth, 3) BGR
    rightImage: Optional[np.ndarray]
    # @brief 是否成功；False 表示输入非法或尺寸越界
    success: bool
    # @brief 错误信息；成功时为空串 ""
    errorMessage: str


## @brief 拼接结果数据结构。
## @details 封装拼接画布与执行状态；success=False 时 panorama 为 None。
@dataclass
class SimpleStitchResult:
    # @brief 拼接画布；单位: 像素；尺寸 (canvasH, canvasW, 3) BGR
    panorama: Optional[np.ndarray]
    # @brief 是否成功；False 表示输入非法或尺寸不一致
    success: bool
    # @brief 错误信息；成功时为空串 ""
    errorMessage: str


## @brief 单个 YOLOv8 检测结果。
## @details 仅承载解析后的纯数据，不含任何算法逻辑，便于在接口间直接传递。
@dataclass
class Detection:
    # @brief 类别名称，如 "person"、"surfboard"（与 YOLO 训练的 names 一致）
    className: str
    # @brief 置信度；取值范围 0~1，由 YOLO 阈值过滤后输出
    confidence: float
    # @brief 目标框；格式 (x1, y1, x2, y2)；单位: 像素；整型，左上→右下
    box: Tuple[int, int, int, int]


## @brief 接口 4：空间归集结果。
## @details 按“单区域 / 跨界 / 游离”三态分类，直接供接口 5 业务校验消费。
@dataclass
class RoiCheckResult:
    # @brief 完全落在单一 ROI 内的物品字典；Key 为 roi_id，Value 为该区域内 Detection 列表
    single_roi_items: Dict[str, List[Detection]]
    # @brief 跨界/越界物品：碰触了多个 ROI，或碰触了 1 个但未完全被包含的物品
    multi_roi_items: List[Tuple[Detection, List[str]]]
    # @brief 完全游离在外的物品：与所有 ROI 均无物理交集
    unmatched: List[Detection]


## @brief 对左右原图做水平五五分切割 + 垂直居中裁剪。
##
## @details
## 切割遵循“五五分”原则：左摄保留其右半幅（原图右侧 cropWidth 宽），右摄保留其
## 左半幅（原图左侧 cropWidth 宽），两者等宽后便于后续沿 x 轴无缝拼接。
## 垂直方向采用居中裁剪：yStart = (原图高 - cropHeight) // 2，保证目标主体在画面中部。
## cropWidth / cropHeight 传 0 表示自动：cropWidth = 原图宽 // 2，cropHeight = 两图高的较小值。
## 所有失败（输入为空、尺寸越界）均在 success 字段返回，不抛异常。
##
## @param [in] leftImage   左摄像头原图；尺寸 (H, W, 3) BGR
## @param [in] rightImage  右摄像头原图；尺寸 (H, W, 3) BGR
## @param [in] cropWidth   裁剪宽；单位: 像素；0=自动(原图宽//2)
## @param [in] cropHeight  裁剪高；单位: 像素；0=自动(两图高的较小值)
## @return CropResult；两张输出图尺寸均为 (cropHeight, cropWidth, 3)
## @note 任意一图传入 None 即判定输入为空并返回 success=False。
def crop_images(leftImage: np.ndarray,
                rightImage: np.ndarray,
                cropWidth: int,
                cropHeight: int) -> CropResult:
    # 校验：任一输入图像为空
    if leftImage is None or rightImage is None:
        return CropResult(None, None, False, "输入图像为空")

    leftH, leftW = leftImage.shape[:2]
    rightH, rightW = rightImage.shape[:2]

    # 0 = 自动：宽取原图宽一半，高取两图较小值（保证两图都能切出该高）
    if cropWidth <= 0:
        cropWidth = leftW // 2
    if cropHeight <= 0:
        cropHeight = min(leftH, rightH)

    # 校验：裁剪宽超过任意一图图像宽
    if cropWidth > leftW or cropWidth > rightW:
        return CropResult(None, None, False, "裁剪宽超过图像宽")
    # 校验：裁剪高超过任意一图图像高
    if cropHeight > leftH or cropHeight > rightH:
        return CropResult(None, None, False, "裁剪高超过图像高")

    # 垂直居中：两张图各自按自己的 H 计算 yStart，保证主体居中
    leftYStart = (leftH - cropHeight) // 2
    rightYStart = (rightH - cropHeight) // 2

    # 左摄：保留右侧 cropWidth（原图切片 [W-cropW : W]）
    leftCrop = leftImage[leftYStart:leftYStart + cropHeight,
                         leftW - cropWidth:leftW]
    # 右摄：保留左侧 cropWidth（原图切片 [0 : cropW]）
    rightCrop = rightImage[rightYStart:rightYStart + cropHeight,
                           0:cropWidth]

    logger.info("切割完成：left=%s right=%s", leftCrop.shape, rightCrop.shape)
    return CropResult(leftCrop, rightCrop, True, "")


## @brief 把 imgA、imgB 沿 x 方向对齐拼到一张画布，y 方向顶部对齐。
##
## @details
## 仅做 x 轴偏移对齐：imgA 固定不动（offsetA=0），imgB 相对 imgA 平移
## offsetB = refX_A - refX_B，即令 imgA 局部 x=refX_A 与 imgB 局部 x=refX_B
## 这两条竖线在画布上重合，实现两图“拼接点”对齐。
## y 方向两图等高故顶部对齐；后写入的图像覆盖先写入的（后贴覆盖前贴）。
## stitchPoints 允许传入 float（如自动计算的非整数），内部统一 int(round())
## 转整型（画布尺寸与 numpy 切片下标必须为整型）。
##
## @param [in] imgA          图像 A；尺寸 (H, W, 3) BGR；固定不动（offsetA=0）
## @param [in] imgB          图像 B；尺寸 (H, W, 3) BGR；相对 A 平移
## @param [in] stitchPoints  [refX_A, refX_B]；允许 float（内部 int(round())）；
##                           A 局部 x=refX_A 与 B 局部 x=refX_B 的竖线在画布重合
## @return SimpleStitchResult；画布尺寸 (imgH, canvasW, 3)，canvasW 由两图偏移推导
## @note 若 imgB 跑到 imgA 左侧（offsetB<0），画布向左扩展，xMin 统一归零。
def stitch_images(imgA: np.ndarray,
                  imgB: np.ndarray,
                  stitchPoints: List[float]) -> SimpleStitchResult:
    # 校验：输入图像为空
    if imgA is None or imgB is None:
        return SimpleStitchResult(None, False, "输入图像为空")

    # 校验：两图尺寸（高、宽、通道）必须完全一致
    if imgA.shape != imgB.shape:
        return SimpleStitchResult(
            None, False,
            f"两图尺寸不一致: A={imgA.shape} B={imgB.shape}")

    # 校验：stitchPoints 长度必须为 2（恰好提供 refX_A 与 refX_B）
    if len(stitchPoints) != 2:
        return SimpleStitchResult(None, False, "stitchPoints 长度必须为 2")

    # 拼接点坐标取整：float -> int(round)，避免 numpy 切片越界
    refX_A = int(round(stitchPoints[0]))
    refX_B = int(round(stitchPoints[1]))

    imgH, imgW = imgA.shape[:2]

    # 只对齐 x：imgB 左边缘相对 imgA 左边缘的平移量
    offsetA = 0
    offsetB = refX_A - refX_B

    # 处理 imgB 跑到 imgA 左边的情况：取两偏移的最小值作为画布左边界起点
    xMin = min(offsetA, offsetB)
    canvasW = max(offsetA + imgW, offsetB + imgW) - xMin
    canvasH = imgH

    # 画布：黑色背景；后写入覆盖先写入（先贴 A、后贴 B）
    canvas = np.zeros((canvasH, canvasW, 3), dtype=np.uint8)
    canvas[:, offsetA - xMin:offsetA - xMin + imgW] = imgA
    canvas[:, offsetB - xMin:offsetB - xMin + imgW] = imgB

    logger.info("拼接完成：canvas=%s", canvas.shape)
    return SimpleStitchResult(canvas, True, "")


## @brief 初始化并加载 ONNX 模型（初始化配置步骤）。
##
## @details
## 负责加载模型（缓存到模块级变量 _model），并记录置信度阈值 _confThreshold
## 与推理尺寸 _imgSize 到模块级状态，供后续 yolo_detect 读取。
## ultralytics 在加载 .onnx 后缀时会自动调度 onnxruntime 作为推理后端，
## 无需手写 onnxruntime 解析逻辑；模型以 .onnx 格式提供，便于边缘部署提速。
## 若 _model 已加载则跳过重复加载（但同步更新阈值/尺寸，允许调用方热更新）。
##
## @param [in] modelPath      YOLOv8 ONNX 权重路径；.onnx 后缀
## @param [in] confThreshold  置信度阈值；取值范围 0~1
## @param [in] imgSize        YOLO 推理分辨率（长边）；单位: 像素
## @return bool；True 表示初始化成功
## @warning imgSize 必须与导出 ONNX 时指定的 imgsz 完全一致，否则推理报 Shape mismatch。
def yolo_init(modelPath: str, confThreshold: float, imgSize: int) -> bool:
    global _model, _confThreshold, _imgSize
    # 已加载则跳过重复加载，但同步更新阈值/尺寸（二者可由调用方后续调整）
    if _model is not None:
        logger.info("YOLO 模型已加载，跳过重复初始化")
        _confThreshold = confThreshold
        _imgSize = imgSize
        return True
    try:
        logger.info("YOLO 模型加载中：%s", modelPath)
        # .onnx 后缀时 ultralytics 自动调度 onnxruntime 后端推理；
        # 导出时已固定 imgsz，故 imgSize 必须与导出时一致，否则报 Shape mismatch
        from ultralytics import YOLO
        _model = YOLO(modelPath)
        _confThreshold = confThreshold
        _imgSize = imgSize
        return True
    except Exception as exc:
        logger.error("YOLO 模型加载失败：%s：%s", modelPath, exc)
        raise RuntimeError(
            f"YOLOv8 模型加载失败: {modelPath}: {exc}") from exc


## @brief 对单张 BGR 图执行 YOLO 推理（纯推理步骤）。
##
## @details
## 仅执行推理与解析，不做任何初始化、不接收路径/参数；内部直接读取 yolo_init
## 缓存的阈值 _confThreshold 与尺寸 _imgSize，保证“配置与推理”职责分离。
## 输入为空或模型未初始化（_model 为 None）时返回空列表 []，不抛异常，
## 由调用方决定如何处理“无结果”。
##
## @param [in] image BGR 图像阵列；尺寸 (H, W, 3)
## @return List[Detection]；模型未初始化或输入为空时返回空列表
## @note 原图直接喂入，不在此做归一化/resize 等预处理（由 ultralytics 内部处理）。
def yolo_detect(image: np.ndarray) -> List[Detection]:
    if _model is None:
        logger.warning("yolo_detect: 模型未初始化，请先调用 yolo_init")
        return []
    if image is None:
        logger.warning("yolo_detect: 输入图像为空，返回空列表")
        return []

    # 直接喂原 BGR 图，不做预处理；使用 yolo_init 缓存的阈值与尺寸
    results = _model.predict(image, conf=_confThreshold,
                             imgsz=_imgSize, verbose=False)
    boxes = results[0].boxes

    detections: List[Detection] = []
    if boxes is not None:
        for i in range(len(boxes)):
            # 解析单框：坐标取整(round)转整型像素，类别取 names 映射，置信度取 conf
            x1, y1, x2, y2 = (int(round(v)) for v in boxes.xyxy[i].tolist())
            className = str(_model.names[int(boxes.cls[i])])
            confidence = float(boxes.conf[i])
            detections.append(
                Detection(className, confidence, (x1, y1, x2, y2)))

    if detections:
        logger.info("识别完成：目标数=%d", len(detections))
    else:
        logger.info("识别完成：未检测到目标")
    return detections


## @brief 空间归集（100% 包含归属 + 重叠交集跨界判定）。
##
## @details
## 本函数只做纯数学的坐标归集，不涉及业务对错，判定分以下三条互斥且严密的规则：
## 1) 单区域归属：检测框被唯一 1 个 ROI 100% 绝对包含（四个顶点全部在 ROI 内部，
##    即 dx1>=rx1 且 dy1>=ry1 且 dx2<=rx2 且 dy2<=ry2），且仅与该 ROI 有交集；
## 2) 跨界报警：满足任一条件即报跨界——检测框与 2 个及以上 ROI 存在物理交集，
##    或检测框只与 1 个 ROI 有交集但未被其 100% 包含（探出边界，半截身子在外）；
## 3) 游离报警：检测框与所有 ROI 均无任何物理交集（完全在 ROI 外部）。
## 最终按【单区域 / 跨界 / 游离】三态归类，供接口 5 做工业防呆校验。
##
## @param [in] detections YOLO 输出的检测结果列表；元素为 Detection
## @param [in] roi_defs   手动定义的 ROI 字典；格式 {"roi_id": (x1, y1, x2, y2)}；
##                       坐标相对于拼接后的全景画布；单位: 像素
## @return RoiCheckResult；按单区域、跨界、游离三个维度分好类的数据结构
## @note single_roi_items 会预置 roi_defs 的全部 key（空列表也保留），便于查漏放。
def check_roi_containment(detections: List[Detection],
                          roi_defs: Dict[str, Tuple[int, int, int, int]]) -> RoiCheckResult:
    # 初始化：single_roi_items 先预置 roi_defs 的全部 key（空列表也保留，便于业务层查漏放）
    single_roi_items: Dict[str, List[Detection]] = {rid: [] for rid in roi_defs}
    multi_roi_items: List[Tuple[Detection, List[str]]] = []
    unmatched: List[Detection] = []

    for det in detections:
        dx1, dy1, dx2, dy2 = det.box

        contain_rois: List[str] = []  # 记录 100% 包含该框的 ROI（归属用）
        overlap_rois: List[str] = []  # 记录与该框有重叠(碰触)的 ROI（跨界用）

        for rid, (rx1, ry1, rx2, ry2) in roi_defs.items():
            # 【判定条件】100% 绝对包含：检测框的左/上边界必须越过 ROI 内侧、
            # 右/下边界不得越过 ROI 外侧，即 dx1>=rx1 且 dy1>=ry1 且 dx2<=rx2 且 dy2<=ry2
            if dx1 >= rx1 and dy1 >= ry1 and dx2 <= rx2 and dy2 <= ry2:
                contain_rois.append(rid)

            # 【判定条件】交集重叠：两框在 X 轴与 Y 轴上均存在重叠（未完全错开）。
            # 仅当“检测框右边<=ROI左边 或 左边>=ROI右边 或 下边<=上边 或 上边>=下边”
            # 四者之一成立时才完全分离；取反即表示两框有交集（碰触）。
            if not (dx2 <= rx1 or dx1 >= rx2 or dy2 <= ry1 or dy1 >= ry2):
                overlap_rois.append(rid)

        # 优先级 1：与所有 ROI 均无交集（完全在外部），归为游离
        if len(overlap_rois) == 0:
            unmatched.append(det)
        # 优先级 2：只有与唯一 1 个 ROI 有交集且被 100% 包含时，才算单区域归属
        elif len(overlap_rois) == 1 and len(contain_rois) == 1:
            single_roi_items[overlap_rois[0]].append(det)
        # 优先级 3：其余所有情况（碰触多个 ROI，或只碰 1 个但探出边界未完全包含），
        # 一律判定为跨界/越界报警
        else:
            multi_roi_items.append((det, overlap_rois))

    logger.info("空间归集完成：单区域=%d 跨界=%d 游离=%d",
                sum(len(v) for v in single_roi_items.values()),
                len(multi_roi_items), len(unmatched))
    return RoiCheckResult(single_roi_items, multi_roi_items, unmatched)


## @brief 相机视野自检。
##
## @details
## 在正式业务校验前，遍历自检映射表，检查指定的 ROI 内是否出现了预期的特定标识（Class）。
## 只检查 single_roi_items（100% 包含的池子），未在表中配置的 ROI 直接跳过。
## 若某个配置的 ROI 内未检测到期望的 Class，则判定相机视野异常、标志物丢失
## 或位置严重偏移，自检失败。
##
## @param [in] roi_check_result 接口 4 输出的 RoiCheckResult 空间归集结果
## @param [in] check_map        自检映射表；格式 {"roi_id": "期望的className"}
## @return bool；True 表示自检通过，False 表示自检失败
## @note 本函数纯读取，不涉及任何业务对错的判定。
def self_check(roi_check_result: RoiCheckResult,
               check_map: Dict[str, str]) -> bool:
    for roi_id, expected_class in check_map.items():
        # 获取该 ROI 内 100% 包含的物品列表
        items_in_roi = roi_check_result.single_roi_items.get(roi_id, [])
        present_classes = [d.className for d in items_in_roi]

        # 如果期望的类别不在该 ROI 的检测结果中，自检失败
        if expected_class not in present_classes:
            logger.error("[自检失败] 位置 %s 未检测到标识 '%s'，当前检测到: %s",
                         roi_id, expected_class, present_classes if present_classes else "空")
            return False

    logger.info("=== 相机视野自检通过 ===")
    return True


## @brief 业务校验（双表交叉校验）。
##
## @details
## 接收接口 4 的空间归集结果，结合两张映射表判定业务对错，并直接打印校验报告
## （不返回复杂结构体，结果即日志）。判定遵循三大优先级，依次从严到宽：
##   1) 跨界优先：物品压住多个 ROI，或仅碰 1 个 ROI 但未完全进入（multi_roi_items）
##      直接报“放错-跨越”；
##   2) 越界次之：完全游离在 ROI 外（unmatched）报“放错-游离”；
##   3) 查表匹配：对单区域内的物品，用 frozenset(类别组合) 查 CLASS_ITEM_MAP
##      得到实际物品名，再与 ROI_BIND_MAP 中该位置的预期物品名比对。
## 其中 frozenset 用于“物品构成”查表：类别组合本身无序（person+surfboard 与
## surfboard+person 等价），frozenset 可哈希且消除顺序影响，确保任意顺序都能命中映射。
##
## @param [in] roi_check_result 接口 4 输出的 RoiCheckResult 空间归集结果
## @param [in] class_item_map   物品构成映射表；Key=frozenset(类别组合)，Value=物品名称
## @param [in] roi_bind_map     ROI 绑定映射表；Key=ROI_ID，Value=该位置应放置的物品名称
## @return None；校验结果通过 logger 直接输出
## @note 本函数不修改任何入参，纯读取与打印。
def check_business_logic(roi_check_result: RoiCheckResult,
                         class_item_map: Dict[frozenset, str],
                         roi_bind_map: Dict[str, str]) -> None:
    logger.info("=== 工业防呆校验报告 ===")

    # 1. 最先查跨界：一个物品压住多个 ROI
    for det, crossed_rois in roi_check_result.multi_roi_items:
        logger.error("[放错] 物品 %s 跨越了多个ROI区域: %s", det.className, crossed_rois)

    # 2. 其次查越界：完全不在任何 ROI 内的游离物品
    for det in roi_check_result.unmatched:
        logger.error("[放错] 物品 %s 不在ROI区域内", det.className)

    # 3. 最后遍历查空位与匹配（单区域物品比对双表）
    for roi_id, expected_item in roi_bind_map.items():
        items_in_roi = roi_check_result.single_roi_items.get(roi_id, [])
        if not items_in_roi:
            logger.error("[漏放] 位置 %s 为空，预期放置: %s", roi_id, expected_item)
            continue
        # 用 frozenset 消除类别顺序影响：person+surfboard 与 surfboard+person 等价
        present_classes = frozenset([d.className for d in items_in_roi])
        actual_item = class_item_map.get(present_classes)
        if actual_item is None:
            logger.error("[放错] 位置 %s 检测到未知组合 %s", roi_id, set(present_classes))
        elif actual_item != expected_item:
            logger.error("[放错] 位置 %s 预期: %s，实际: %s",
                         roi_id, expected_item, actual_item)
        else:
            logger.info("[正确] 位置 %s 校验通过 (%s)", roi_id, expected_item)



