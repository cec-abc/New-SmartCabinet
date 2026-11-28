"""单层双摄识别闭环验证工具：只在 lab 内运行，不启动生产装配、控制与 TCP 链路。

用一对左右摄像头取帧、复用生产拼接器拼全景，按 ROI 对照表逐行做区域位置校验，
在无模型时按合法未命中产出 recognize_ack，验证"单层链路 + 协议形状"是否成立。

注意：生产代码不裁 ROI 小图、不逐 ROI 推理；它只对全景推理一次，再用检测框与
对照表矩形做"框完全落入区域"的位置判定。本工具中的裁片仅用于人工看图，
不代表生产链路。
"""
# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

## 允许从任意目录直接运行：把工程根加入模块搜索路径
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

## @file edge/lab/layer_dual_cam_verify.py
## @brief 单层双摄识别闭环验证：取帧、拼接、ROI 区域位置校验、组 recognize_ack、幂等比对
## @author 袁燕

import argparse
import json
from pathlib import Path
from typing import Any, TypedDict

import cv2
import numpy as np

from edge.exceptions import EdgeError, ErrorCode
from edge.infra.roi_binding_loader import RoiBindingLoader
from edge.interfaces.i_logger import ILogger
from edge.modules.recognition.recognition_stitcher import Cv2FrameStitcher
from edge.modules.recognition.recognition_utils import buildAck, buildRowItem
from edge.modules.usb.usb_camera_device import (
    FRAME_SOURCE_CAMERA,
    CameraFactory,
)

## @brief 默认 ROI 对照表路径（相对工程根）
DEFAULT_ROI_CSV: str = "edge/config/roi_binding.csv"
## @brief 默认输出目录（相对工程根）
DEFAULT_OUTPUT_DIR: str = "edge/lab/outputs/layer_verify"
## @brief 默认请求标识
DEFAULT_REQUEST_ID: str = "req-lab-001"
## @brief 占位帧边长，与样例 CSV 四象限坐标 640x480 对齐
FAKE_FRAME_WIDTH: int = 640
FAKE_FRAME_HEIGHT: int = 480
## @brief 退出码：全部通过
EXIT_OK: int = 0
## @brief 退出码：配置/ROI/摄像头/拼接/裁剪错误
EXIT_SETUP: int = 1
## @brief 退出码：协议形状或请求标识校验失败
EXIT_PROTOCOL: int = 2
## @brief 退出码：幂等比对失败
EXIT_IDEMPOTENT: int = 3
## @brief 退出码：lab 自身 IO 错误
EXIT_IO: int = 4


## @brief 单轮验证结果：字段类型固定，避免字典类型擦除
class VerifyResult(TypedDict):
    ## @brief 运行模式，camera 或 fake
    mode: str
    ## @brief 全景尺寸
    panoramaSize: dict[str, int]
    ## @brief 协议条目
    items: list[dict[str, object]]
    ## @brief 应答帧
    ack: dict[str, object]
    ## @brief ROI 区域有效性校验是否全部通过（生产用检测框完全落入区域做位置判定）
    cropOk: bool
    ## @brief 应答形状校验错误，空串表示通过
    shapeError: str
    ## @brief 全景 PNG 字节（拼接器编码为 png）
    panorama: bytes
    ## @brief 左帧字节
    leftBytes: bytes
    ## @brief 右帧字节
    rightBytes: bytes
    ## @brief 本层 ROI 行
    rows: list[Any]


## @brief 控制台日志器：只实现 ILogger 四方法，不写生产日志目录
class ConsoleLogger(ILogger):
    ## @brief 记录接收帧
    #  @param module 模块名
    #  @param data 帧数据
    #  @return 无
    def rx(self, module: str, data: dict[str, object] | bytes) -> None:
        print(f"[RX ][{module}] {self._brief(data)}")

    ## @brief 记录发送帧
    #  @param module 模块名
    #  @param data 帧数据
    #  @return 无
    def tx(self, module: str, data: dict[str, object] | bytes) -> None:
        print(f"[TX ][{module}] {self._brief(data)}")

    ## @brief 记录普通信息
    #  @param module 模块名
    #  @param msg 日志内容
    #  @return 无
    def info(self, module: str, msg: str) -> None:
        print(f"[INFO][{module}] {msg}")

    ## @brief 记录错误
    #  @param module 模块名
    #  @param msg 日志内容
    #  @param exception 可选异常对象
    #  @return 无
    def error(self, module: str, msg: str, exception: Exception | None = None) -> None:
        print(f"[ERR ][{module}] {msg}" + (f" ({exception})" if exception else ""))

    ## @brief 把帧数据压成简短文本，避免字节流刷屏
    #  @param data 帧数据
    #  @return 简短文本
    def _brief(self, data: dict[str, object] | bytes) -> str:
        if isinstance(data, bytes):
            return f"<{len(data)} bytes>"
        return str(data)


## @brief 解析命令行参数
#  @return 参数命名空间
def parseArgs() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="单层双摄识别闭环验证（lab 独立运行，不启动生产链路）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--left-camera", default="0",
                        help="左路摄像头索引（Windows）或设备路径（麒麟）")
    parser.add_argument("--right-camera", default="1",
                        help="右路摄像头索引或设备路径")
    parser.add_argument("--worker-id", type=int, default=1,
                        help="要验证的层号，对应 ROI CSV 的 worker_id")
    parser.add_argument("--roi-csv", default=DEFAULT_ROI_CSV, help="ROI 对照表路径")
    parser.add_argument("--model", default="", help="模型权重路径；留空=合法未命中模式")
    parser.add_argument("--save-images", action="store_true",
                        help="保存左/右原帧、全景与 ROI 裁片")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR,
                        help="结果 JSON 与图片输出目录")
    parser.add_argument("--request-id", default=DEFAULT_REQUEST_ID,
                        help="模拟请求标识，验证原样回带")
    parser.add_argument("--fake-camera", action="store_true",
                        help="不打开物理摄像头，用确定性占位帧")
    parser.add_argument("--fake-left-image", default="", help="用本地图片代替左路占位帧")
    parser.add_argument("--fake-right-image", default="", help="用本地图片代替右路占位帧")
    parser.add_argument("--repeat", type=int, default=2, help="同一请求标识连跑次数，用于幂等比对")
    parsed = parser.parse_args()
    ## 默认路径按工程根解析，保证从任意 cwd 运行都能找到配置与写出结果
    if parsed.roi_csv == DEFAULT_ROI_CSV:
        parsed.roi_csv = str(PROJECT_ROOT / DEFAULT_ROI_CSV)
    if parsed.output_dir == DEFAULT_OUTPUT_DIR:
        parsed.output_dir = str(PROJECT_ROOT / DEFAULT_OUTPUT_DIR)
    return parsed


## @brief 打印一项检查结果并登记
#  @param checkId 检查项编号
#  @param name 检查项名称
#  @param passed 是否通过
#  @param detail 说明
#  @param checks 汇总列表
#  @return 无
def recordCheck(checkId: str, name: str, passed: bool,
                detail: str, checks: list[dict[str, object]]) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"[{checkId}] {status}  {name}: {detail}")
    checks.append({"id": checkId, "name": name, "passed": passed, "detail": detail})


## @brief 从真实摄像头取一帧 JPEG 字节
#  @param address 摄像头索引或设备路径
#  @param logger 日志器
#  @return JPEG 帧字节
#  @raises EdgeError 打开或取帧失败
def grabRealFrame(address: str, logger: ILogger) -> bytes:
    device = CameraFactory.createDevice(
        address, None, logger, None, None, FRAME_SOURCE_CAMERA,
    )
    device.open()
    try:
        frame = device.readFrame()
        if frame is None:
            raise EdgeError(ErrorCode.CAPTURE, f"取帧为空: {address}")
        return frame
    finally:
        device.close()


## @brief 构造确定性的占位双帧：左帧右半幅与右帧左半幅拼出 640x480 全景
#  @param imagePath 可选本地图片路径，非空时改用它
#  @param isLeft 是否左路
#  @return JPEG 帧字节
#  @raises EdgeError 图片路径不可读
def makeFakeFrame(imagePath: str, isLeft: bool) -> bytes:
    if imagePath:
        data = cv2.imread(imagePath, cv2.IMREAD_COLOR)
        if data is None:
            raise EdgeError(ErrorCode.CAPTURE, f"占位图片无法读取: {imagePath}")
    else:
        data = np.zeros((FAKE_FRAME_HEIGHT, FAKE_FRAME_WIDTH, 3), dtype=np.uint8)
        mid = FAKE_FRAME_WIDTH // 2
        ## 左帧的有效半幅（右半）填浅灰，右帧的有效半幅（左半）填深灰，便于肉眼确认拼接方向
        if isLeft:
            data[:, mid:, :] = (200, 200, 200)
        else:
            data[:, :mid, :] = (90, 90, 90)
    ok, encoded = cv2.imencode(".jpg", data)
    if not ok:
        raise EdgeError(ErrorCode.CAPTURE, "占位帧编码失败")
    return bytes(encoded.tobytes())


## @brief 读取一对帧：真机或占位
#  @param args 命令行参数
#  @param logger 日志器
#  @return 左帧、右帧字节元组
#  @raises EdgeError 取帧失败
def readFramePair(args: argparse.Namespace, logger: ILogger) -> tuple[bytes, bytes]:
    if args.fake_camera:
        return (
            makeFakeFrame(args.fake_left_image, True),
            makeFakeFrame(args.fake_right_image, False),
        )
    return (
        grabRealFrame(args.left_camera, logger),
        grabRealFrame(args.right_camera, logger),
    )


## @brief 校验应答帧形状：顶层三键、条目四键、请求标识原样回带
#  @param ack 待校验应答帧
#  @param requestId 期望请求标识
#  @return 校验说明；空串表示通过
def validateAck(ack: dict[str, object], requestId: str) -> str:
    topKeys = set(ack.keys())
    if topKeys != {"type", "request_id", "items"}:
        return f"顶层键不符: {sorted(topKeys)}"
    if ack.get("type") != "recognize_ack":
        return f"帧类型不符: {ack.get('type')}"
    if ack.get("request_id") != requestId:
        return f"请求标识未原样回带: {ack.get('request_id')}"
    items = ack.get("items")
    if not isinstance(items, list):
        return "items 不是列表"
    positions: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            return "条目不是字典"
        if set(item.keys()) != {"position", "tool_id", "confidence", "alert_type"}:
            return f"条目键不符: {sorted(item.keys())}"
        position = str(item.get("position", ""))
        if position in positions:
            return f"货位重复: {position}"
        positions.add(position)
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            return f"置信度越界: {confidence}"
    return ""


## @brief 跑一轮单层验证
#  @param args 命令行参数
#  @param logger 日志器
#  @param checks 检查结果汇总
#  @return 结果字典
def runOnce(args: argparse.Namespace, logger: ILogger,
            checks: list[dict[str, object]], recordChecks: bool = True) -> VerifyResult:
    ## 首轮登记检查项，后续轮只校验不重复登记，保持报告口径唯一
    def emit(checkId: str, name: str, passed: bool,
             detail: str) -> None:
        if recordChecks:
            recordCheck(checkId, name, passed, detail, checks)

    loader = RoiBindingLoader(logger)
    allRows = loader.load(args.roi_csv)
    emit("C01", "ROI 对照表加载", True, f"{len(allRows)} 行")
    rows = [row for row in allRows if row.workerId == args.worker_id]
    if not rows:
        raise EdgeError(ErrorCode.CONFIG, f"worker_id={args.worker_id} 没有 ROI 行")
    positions = [row.position for row in rows]
    if len(set(positions)) != len(positions):
        raise EdgeError(ErrorCode.CONFIG, f"worker_id={args.worker_id} 货位重复")
    emit("C02", "单层 ROI 筛选", True,
         f"worker_id={args.worker_id}, {len(rows)} 行")

    leftBytes, rightBytes = readFramePair(args, logger)
    mode = "fake" if args.fake_camera else "camera"
    frameBytesOk = bool(leftBytes) and bool(rightBytes)
    emit("C03", "双摄取帧", frameBytesOk,
         f"mode={mode}, left={len(leftBytes)}B, right={len(rightBytes)}B")
    if not frameBytesOk:
        raise EdgeError(ErrorCode.CAPTURE, "取帧为空: 左路或右路返回 0 字节")

    stitcher = Cv2FrameStitcher(logger)
    panorama = stitcher.stitch((leftBytes, rightBytes))
    ## stitch 返回全景 PNG 字节，解码后拿尺寸供落盘与结果登记
    panoramaImage = cv2.imdecode(
        np.frombuffer(bytearray(panorama), dtype=np.uint8), cv2.IMREAD_COLOR,
    )
    if panoramaImage is None:
        raise EdgeError(ErrorCode.CAPTURE, "全景图解码失败")
    height, width = panoramaImage.shape[:2]
    emit("C04", "拼接全景", width > 0 and height > 0,
         f"{width}x{height}")

    items: list[dict[str, object]] = []
    cropOk = True
    for row in rows:
        try:
            stitcher.crop(panorama, row)
        except EdgeError as error:
            cropOk = False
            emit("C05", "ROI 区域有效性", False, f"{row.position}: {error}")
        ## 无模型时不伪造命中：生产口径是全景推理一次后做框-区域位置判定，
        ## 此处无模型只输出合法未命中条目，不生成检测框
        items.append(buildRowItem(row, False, 0.0))
    if cropOk:
        emit("C05", "ROI 区域有效性", True, f"{len(rows)}/{len(rows)}")
    emit("C06", "推理模式", True,
         "无模型，合法未命中" if not args.model else f"模型={args.model}")

    ack = buildAck(args.request_id, items)
    shapeError = validateAck(ack, args.request_id)
    emit("C07", "items 形状", not shapeError,
         shapeError or f"{len(items)} 项，每项 4 键")
    emit("C08", "recognize_ack 形状", not shapeError,
         shapeError or f"request_id={args.request_id}")

    return {
        "mode": mode,
        "panoramaSize": {"width": width, "height": height},
        "items": items,
        "ack": ack,
        "cropOk": cropOk,
        "shapeError": shapeError,
        "panorama": panorama,
        "leftBytes": leftBytes,
        "rightBytes": rightBytes,
        "rows": rows,
    }


## @brief 保存图片产物到输出目录
#  @param args 命令行参数
#  @param result runOnce 结果
#  @return 产物路径字典
def saveArtifacts(args: argparse.Namespace,
                  result: VerifyResult) -> dict[str, str]:
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    (output / "left.jpg").write_bytes(result["leftBytes"])
    (output / "right.jpg").write_bytes(result["rightBytes"])
    (output / "panorama.png").write_bytes(result["panorama"])
    artifacts["leftFrame"] = str(output / "left.jpg")
    artifacts["rightFrame"] = str(output / "right.jpg")
    artifacts["panorama"] = str(output / "panorama.png")
    stitcher = Cv2FrameStitcher()
    for row in result["rows"]:
        roiBytes = stitcher.crop(result["panorama"], row)
        name = f"roi_{row.position.replace('-', '_')}.png"
        (output / name).write_bytes(roiBytes)
        artifacts[row.roiId] = str(output / name)
    return artifacts


## @brief 主流程
#  @return 进程退出码
def main() -> int:
    args = parseArgs()
    logger = ConsoleLogger()
    checks: list[dict[str, object]] = []
    result: VerifyResult | None = None
    exitCode = EXIT_OK
    try:
        repeat = max(1, args.repeat)
        acks: list[dict[str, object]] = []
        for roundIndex in range(repeat):
            result = runOnce(args, logger, checks, recordChecks=(roundIndex == 0))
            acks.append(result["ack"])
        assert result is not None
        idempotent = all(ack == acks[0] for ack in acks)
        recordCheck("C09", "幂等比对", idempotent,
                    f"{repeat} 次 ack 一致" if idempotent else "ack 不一致", checks)
        if not idempotent:
            exitCode = EXIT_IDEMPOTENT

        if args.save_images:
            artifacts = saveArtifacts(args, result)
        else:
            artifacts = {}

        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        ## C10 在 payload 写入前登记，保证落盘的 checks 含完整 C01~C10
        recordCheck("C10", "结果输出", True, str(output / "result.json"), checks)
        payload = {
            "mode": "fake" if args.fake_camera else "camera",
            "leftCamera": args.left_camera,
            "rightCamera": args.right_camera,
            "workerId": args.worker_id,
            "requestId": args.request_id,
            "roiCsv": str(Path(args.roi_csv).resolve()),
            "modelPath": args.model,
            "checks": checks,
            "items": result["items"],
            "ack": result["ack"],
            "idempotent": idempotent,
            "artifacts": artifacts,
            "overallPassed": exitCode == EXIT_OK and all(check["passed"] for check in checks),
        }
        (output / "result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        passed = payload["overallPassed"]
        print(f"RESULT  {'PASS' if passed else 'FAIL'}  exit={exitCode}")
        return exitCode
    except EdgeError as error:
        print(f"[FATAL] 验证失败: {error}")
        return EXIT_SETUP
    except OSError as error:
        print(f"[FATAL] 输出 IO 失败: {error}")
        return EXIT_IO


if __name__ == "__main__":
    raise SystemExit(main())
