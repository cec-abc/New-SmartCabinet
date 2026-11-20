"""拼接与裁剪：左右各取一半并沿横轴拼成全景，按对照表矩形裁出区域图像。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from importlib.util import find_spec
from typing import Any

from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingRow
from edge.interfaces.i_logger import ILogger
from edge.modules.recognition.recognition_utils import MERGE_SEPARATOR

## @file edge/modules/recognition/recognition_stitcher.py
## @brief 拼接与裁剪：五五分加垂直居中裁切、沿横轴拼接、按对照表矩形裁出区域图像
## @author 袁燕

## @brief 拼接一路需要的帧数，左路在前右路在后；多出来的帧明确报错，不静默丢帧
REQUIRED_FRAME_COUNT: int = 2
## @brief 单摄模式一组的帧数；此时该帧本身就是全景，不做拼接
SINGLE_FRAME_COUNT: int = 1
## @brief 降级桩拼接时用的分隔符，与纯函数拼接分隔符共用同一个值
DEGRADED_SEPARATOR: bytes = MERGE_SEPARATOR
## @brief 降级桩裁出的空图像字节，表示本轮没有可用图像
DEGRADED_ROI_BYTES: bytes = b""
## @brief 裁剪结果编码成图像字节时用的后缀
ENCODED_IMAGE_EXTENSION: str = ".png"
## @brief 日志模块名
MODULE_NAME: str = "RecognitionStitcher"


## @brief 核对一组的帧数；单摄 1 帧、双摄 2 帧，少一帧多一帧都明确判错
#  @param frames 本轮帧元组
#  @return 无
#  @raises EdgeError 帧数不是 1 或 2 时抛出，code=CAPTURE
#  @note 多出来的帧不能悄悄丢掉，否则现场会以为某个相机还在正常出图
def _validateFrames(frames: tuple[bytes, ...]) -> None:
    if len(frames) in (SINGLE_FRAME_COUNT, REQUIRED_FRAME_COUNT):
        return
    raise EdgeError(
        ErrorCode.CAPTURE,
        f"一组帧数只能是 {SINGLE_FRAME_COUNT} 或 {REQUIRED_FRAME_COUNT}, "
        f"实收 {len(frames)} 帧",
    )


## @brief 拼接与裁剪契约；真实实现依赖图像处理库，缺失时按可选依赖处理
class FrameStitcher(ABC):
    ## @brief 把一组的帧拼成一张全景
    #  @param frames 本轮帧元组；单摄 1 帧直接返回该帧，双摄左路在前右路在后
    #  @return 全景的图像字节
    #  @note 单摄模式下全景就是这一帧的原图，区域矩形的参照系是该帧原图尺寸，
    #        不是左右拼接后的画布尺寸；换真相机后矩形坐标须按真相机原图尺寸重标
    @abstractmethod
    def stitch(self, frames: tuple[bytes, ...]) -> bytes:
        ...

    ## @brief 按对照表行登记的轴对齐矩形从全景里裁出该区域的图像
    #  @param image 拼接全景的图像字节
    #  @param roi 对照表行，用 rectX1/rectY1 记左上角、rectX2/rectY2 记右下角
    #  @return 该区域的图像字节
    #  @note 四个坐标确定的是与图像坐标轴平行的矩形，不是可旋转的四角点；
    #        矩形越界、或宽高不为正时由实现明确判错，本行按未识别降级
    @abstractmethod
    def crop(self, image: bytes, roi: RoiBindingRow) -> bytes:
        ...


## @brief 图像处理库真实实现；库是可选依赖，只能在函数体内导入
class Cv2FrameStitcher(FrameStitcher):
    ## @brief 构造拼接器
    #  @param logger 可选日志器
    #  @return 无
    def __init__(self, logger: ILogger | None = None) -> None:
        ## @brief 可选日志器
        self._logger: ILogger | None = logger

    ## @brief 单摄 1 帧原样返回；双摄按五五分加垂直居中裁切，再沿横轴拼成全景
    #  @param frames 本轮帧元组，左路在前
    #  @return 全景的图像字节
    #  @raises EdgeError 帧数不对、图像解码失败或库缺失时抛出，code=CAPTURE
    def stitch(self, frames: tuple[bytes, ...]) -> bytes:
        _validateFrames(frames)
        if len(frames) == SINGLE_FRAME_COUNT:
            ## 单摄：这一帧即全景，原样返回，不解码不拼接；矩形按该帧原图坐标系裁
            return frames[0]
        imageLibrary, arrayLibrary = self.loadImageLibraries()
        left = self.decodeImage(imageLibrary, arrayLibrary, frames[0])
        right = self.decodeImage(imageLibrary, arrayLibrary, frames[1])
        leftCrop, rightCrop = self.cropHalves(left, right)
        canvas = self.stitchOnXAxis(arrayLibrary, leftCrop, rightCrop)
        return self.encodeImage(imageLibrary, canvas)

    ## @brief 按对照表行的轴对齐矩形裁出该区域的图像
    #  @param image 拼接全景的图像字节
    #  @param roi 对照表行，给出矩形左上角与右下角坐标
    #  @return 该区域的图像字节
    #  @raises EdgeError 图像解码失败、矩形越界或畸形、库缺失时抛出，code=CAPTURE
    def crop(self, image: bytes, roi: RoiBindingRow) -> bytes:
        imageLibrary, arrayLibrary = self.loadImageLibraries()
        panorama = self.decodeImage(imageLibrary, arrayLibrary, image)
        height, width = panorama.shape[:2]
        self._validateRoiRect(roi, width, height)
        piece = panorama[roi.rectY1:roi.rectY2, roi.rectX1:roi.rectX2]
        return self.encodeImage(imageLibrary, piece)

    ## @brief 核对矩形是否落在全景内、宽高是否为正；畸形矩形不裁出空白图冒充结果
    #  @param roi 对照表行
    #  @param width 全景宽，单位像素
    #  @param height 全景高，单位像素
    #  @return 无
    #  @raises EdgeError 矩形越界、宽高不为正或起点落在画布外时抛出，code=CAPTURE
    def _validateRoiRect(self, roi: RoiBindingRow, width: int, height: int) -> None:
        if (roi.rectX1 < 0 or roi.rectY1 < 0
                or roi.rectX2 > width or roi.rectY2 > height
                or roi.rectX1 >= roi.rectX2 or roi.rectY1 >= roi.rectY2
                or roi.rectX1 >= width or roi.rectY1 >= height):
            raise EdgeError(
                ErrorCode.CAPTURE,
                f"ROI 矩形越界或畸形: {roi.roiId} "
                f"({roi.rectX1},{roi.rectY1})-({roi.rectX2},{roi.rectY2}), "
                f"全景 {width}x{height}",
            )

    ## @brief 载入图像处理库与数值计算库；两者都是可选依赖
    #  @return 图像处理库模块与数值计算库模块
    #  @raises EdgeError 库缺失时抛出，code=CAPTURE
    def loadImageLibraries(self) -> tuple[Any, Any]:
        try:
            import cv2  # type: ignore
        except ImportError as error:
            raise EdgeError(ErrorCode.CAPTURE, "未安装图像处理库") from error
        try:
            import numpy  # type: ignore
        except ImportError as error:
            raise EdgeError(ErrorCode.CAPTURE, "未安装数值计算库") from error
        return cv2, numpy

    ## @brief 解码图像字节
    #  @param imageLibrary 图像处理库模块
    #  @param arrayLibrary 数值计算库模块
    #  @param data 图像字节
    #  @return 图像阵列
    #  @raises EdgeError 数据为空或解码失败时抛出，code=CAPTURE
    def decodeImage(self, imageLibrary: Any, arrayLibrary: Any, data: bytes) -> Any:
        if not data:
            raise EdgeError(ErrorCode.CAPTURE, "图像字节为空, 无法解码")
        buffer = arrayLibrary.frombuffer(bytearray(data), dtype=arrayLibrary.uint8)
        decoded = imageLibrary.imdecode(buffer, imageLibrary.IMREAD_COLOR)
        if decoded is None:
            raise EdgeError(ErrorCode.CAPTURE, "图像解码失败")
        return decoded

    ## @brief 编码图像阵列
    #  @param imageLibrary 图像处理库模块
    #  @param canvas 图像阵列
    #  @return 图像字节
    #  @raises EdgeError 编码失败时抛出，code=CAPTURE
    def encodeImage(self, imageLibrary: Any, canvas: Any) -> bytes:
        ok, encoded = imageLibrary.imencode(ENCODED_IMAGE_EXTENSION, canvas)
        if not ok:
            raise EdgeError(ErrorCode.CAPTURE, "图像编码失败")
        return bytes(encoded.tobytes())

    ## @brief 五五分加垂直居中裁切：左摄取右半幅，右摄取左半幅
    #  @param left 左路原图
    #  @param right 右路原图
    #  @return 左裁片与右裁片
    #  @raises EdgeError 裁剪宽高超过图像尺寸时抛出，code=CAPTURE
    def cropHalves(self, left: Any, right: Any) -> tuple[Any, Any]:
        leftHeight, leftWidth = left.shape[:2]
        rightHeight, rightWidth = right.shape[:2]
        ## 裁剪宽取原图宽的一半，裁剪高取两图较小值，保证两图都能切出该高
        cropWidth = leftWidth // 2
        cropHeight = min(leftHeight, rightHeight)
        if cropWidth <= 0 or cropWidth > leftWidth or cropWidth > rightWidth:
            raise EdgeError(ErrorCode.CAPTURE, "裁剪宽超过图像宽")
        if cropHeight <= 0 or cropHeight > leftHeight or cropHeight > rightHeight:
            raise EdgeError(ErrorCode.CAPTURE, "裁剪高超过图像高")
        ## 垂直居中：两张图各自按自己的高算起点，保证主体居中
        leftYStart = (leftHeight - cropHeight) // 2
        rightYStart = (rightHeight - cropHeight) // 2
        leftCrop = left[leftYStart:leftYStart + cropHeight, leftWidth - cropWidth:leftWidth]
        rightCrop = right[rightYStart:rightYStart + cropHeight, 0:cropWidth]
        return leftCrop, rightCrop

    ## @brief 仅沿 x 轴偏移拼成全景，纵轴顶部对齐，不做缩放与融合
    #  @param arrayLibrary 数值计算库模块
    #  @param leftCrop 左裁片
    #  @param rightCrop 右裁片
    #  @return 全景画布
    #  @raises EdgeError 两片尺寸不一致时抛出，code=CAPTURE
    def stitchOnXAxis(self, arrayLibrary: Any, leftCrop: Any, rightCrop: Any) -> Any:
        if leftCrop.shape != rightCrop.shape:
            raise EdgeError(ErrorCode.CAPTURE, "两图尺寸不一致, 无法拼接")
        imageHeight, imageWidth = leftCrop.shape[:2]
        ## 左片贴画布左侧、右片接在左片右边：两张裁片等宽，画布宽就是两片宽之和
        referenceXLeft = imageWidth
        referenceXRight = 0
        offsetLeft = 0
        offsetRight = referenceXLeft - referenceXRight
        leftBoundary = min(offsetLeft, offsetRight)
        canvasWidth = max(offsetLeft + imageWidth, offsetRight + imageWidth) - leftBoundary
        canvas = arrayLibrary.zeros(
            (imageHeight, canvasWidth, 3), dtype=arrayLibrary.uint8,
        )
        canvas[:, offsetLeft - leftBoundary:offsetLeft - leftBoundary + imageWidth] = leftCrop
        canvas[:, offsetRight - leftBoundary:offsetRight - leftBoundary + imageWidth] = rightCrop
        return canvas


## @brief 降级桩：图像处理库缺失时使用；只保证链路走通，产出的是桩数据不是识别结果
class DegradedFrameStitcher(FrameStitcher):
    ## @brief 构造降级桩
    #  @param logger 可选日志器
    #  @return 无
    def __init__(self, logger: ILogger | None = None) -> None:
        ## @brief 可选日志器
        self._logger: ILogger | None = logger

    ## @brief 单摄 1 帧原样返回；双摄把帧按顺序拼成一段不透明字节，不做真实图像处理
    #  @param frames 本轮帧元组，左路在前
    #  @return 拼接后的不透明字节
    #  @raises EdgeError 帧数不是 1 或 2 时抛出，code=CAPTURE
    def stitch(self, frames: tuple[bytes, ...]) -> bytes:
        _validateFrames(frames)
        if len(frames) == SINGLE_FRAME_COUNT:
            ## 单摄：与真实拼接器一致，这一帧本身即全景，不加分隔符
            return frames[0]
        return DEGRADED_SEPARATOR.join(frames)

    ## @brief 裁剪降级为空图像；调用方据此直接判未命中，不拿空图去推理冒充命中
    #  @param image 拼接全景的图像字节
    #  @param roi 对照表行，给出矩形左上角与右下角坐标
    #  @return 空图像字节
    def crop(self, image: bytes, roi: RoiBindingRow) -> bytes:
        return DEGRADED_ROI_BYTES


## @brief 判断图像处理库是否可用；只查是否装了，不真正导入
#  @return 装了返回 True
def isImageLibraryAvailable() -> bool:
    return find_spec("cv2") is not None


## @brief 构造拼接器：装了图像处理库走真实实现，没装走降级桩并记一条说明
#  @param logger 日志器（注入）
#  @return 拼接器实例
def buildFrameStitcher(logger: ILogger) -> FrameStitcher:
    if isImageLibraryAvailable():
        return Cv2FrameStitcher(logger)
    logger.info(
        MODULE_NAME,
        "未安装图像处理库：拼接与裁剪走降级桩, 不产出真实图像；"
        "本轮清单只会是未命中, 不代表识别成功",
    )
    return DegradedFrameStitcher(logger)
