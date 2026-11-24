"""识别应答取证脚本：真实 ROI 对照表加假引擎，走真实链路回一帧带清单的应答。"""
from __future__ import annotations

import json

from edge.app_init import (
    AssemblyParts,
    buildFrameSender,
    buildPlaceholderFrameBytes,
    buildSystem,
    defaultParts,
)
from edge.interfaces.i_camera import CameraStatus, FrameImage, ICameraDevice
from edge.interfaces.i_recognition_engine import DetectionItem, IRecognitionEngine
from edge.modules.tcp.tcp_comm import TcpComm
from edge.modules.tcp.tcp_socket import TcpSocket
from edge.tests.integration.fake_host import FakeHost

## @file edge/tests/integration/recognize_ack_probe.py
## @brief 识别应答取证脚本：真实对照表加假引擎，走真实链路回一帧带清单的应答
## @author 边缘计算项目

## @brief 假引擎给出的置信度，高于对照表登记的置信度下限
FAKE_CONFIDENCE: float = 0.93
## @brief 假引擎对任何区域都给出对照表登记的全部标志类别
FAKE_MARKER_IDS: tuple[str, ...] = ("mk_8821", "mk_8822", "mk_8823", "mk_8824")
## @brief 取证用的请求标识
PROBE_REQUEST_ID: str = "req-ack-probe-0001"
## @brief 等待边缘机接入的最长秒数
CLIENT_WAIT_SEC: float = 10.0
## @brief 等待应答的最长秒数
ACK_WAIT_SEC: float = 20.0
## @brief 连接超时秒数
CONNECT_TIMEOUT_SEC: float = 5.0
## @brief 接收超时秒数
RECV_TIMEOUT_SEC: float = 0.5


## @brief 假推理引擎：对任意区域都给出对照表登记的全部标志类别
class FakeMarkerEngine(IRecognitionEngine):
    ## @brief 构造；记录已加载的模型路径
    def __init__(self) -> None:
        ## @brief 已加载的模型路径，供取证查看
        self.loadedPaths: list[str] = []

    ## @brief 记录模型加载；本引擎不真正读权重
    #  @param path 模型文件路径
    #  @return 无
    def loadModel(self, path: str) -> None:
        self.loadedPaths.append(path)

    ## @brief 给出全部标志类别的命中结果
    #  @param image 图像字节
    #  @return 检测结果列表
    def infer(self, image: FrameImage) -> list[DetectionItem]:
        return [
            {"className": markerId, "confidence": FAKE_CONFIDENCE}
            for markerId in FAKE_MARKER_IDS
        ]


## @brief 占位相机设备：永远能打开，并吐出骨架占位图
class PlaceholderCameraDevice(ICameraDevice):
    ## @brief 构造设备
    #  @param deviceAddr 设备地址
    def __init__(self, deviceAddr: str) -> None:
        ## @brief 设备地址
        self._deviceAddr: str = deviceAddr
        ## @brief 是否已打开
        self._opened: bool = False

    ## @brief 打开设备
    #  @return 无
    def open(self) -> None:
        self._opened = True

    ## @brief 读取一帧；未打开时返回空
    #  @return 图像字节；未打开时为 None
    def readFrame(self) -> FrameImage | None:
        if not self._opened:
            return None
        return buildPlaceholderFrameBytes()

    ## @brief 关闭设备
    #  @return 无
    def close(self) -> None:
        self._opened = False

    ## @brief 返回状态快照
    #  @return 状态字典
    def getStatus(self) -> CameraStatus:
        return {
            "deviceAddr": self._deviceAddr,
            "backend": "PLACEHOLDER",
            "opened": self._opened,
            "everOpened": self._opened,
            "commOk": True,
            "everCaptured": self._opened,
            "focusPosition": 0.0,
        }


## @brief 构造取证用装配参数：真实对照表与真实拼接器，相机与引擎换成可控实现
#  @param hostPort 桩上位机端口
#  @return 装配参数
def buildProbeParts(hostPort: int) -> AssemblyParts:
    parts = defaultParts()
    engine = FakeMarkerEngine()
    parts.engine = engine
    ## 桩引擎返回无框检测项，按测试桩口径关闭生产缺框拒识
    parts.requireBox = False
    parts.cameraPairs = [
        (
            PlaceholderCameraDevice(f"left-{index + 1}"),
            PlaceholderCameraDevice(f"right-{index + 1}"),
        )
        for index in range(len(parts.cameraPairs))
    ]
    socket = TcpSocket("127.0.0.1", hostPort, CONNECT_TIMEOUT_SEC, RECV_TIMEOUT_SEC)
    parts.socket = socket
    parts.frameSender = buildFrameSender(
        TcpComm(socket, parts.maxFrameSize, parts.logger),
    )
    return parts


## @brief 执行一次取证：发识别请求，收到应答后打印原始 JSON 与校验结论
#  @return 无
def runProbe() -> None:
    host = FakeHost()
    port = host.start()
    print(f"[取证] 桩上位机监听 127.0.0.1:{port}", flush=True)
    parts = buildProbeParts(port)
    print(
        f"[取证] ROI 对照表装载 {len(parts.roiBindingRows or [])} 行, "
        f"识别能力可用={parts.recognitionCapability.isAvailable()}",
        flush=True,
    )
    system = buildSystem(parts)
    system.startSystem()
    try:
        if not host.waitClient(CLIENT_WAIT_SEC):
            print("[取证] 边缘机未接入", flush=True)
            return
        host.sendRecognizeReq(PROBE_REQUEST_ID)
        ack = host.waitFrameOfType("recognize_ack", ACK_WAIT_SEC)
        if ack is None:
            print("[取证] 等待应答超时", flush=True)
            return
        print(f"[取证] 应答原始 JSON {json.dumps(ack, ensure_ascii=False)}", flush=True)
        print(f"[取证] 顶层键 {sorted(ack.keys())}", flush=True)
        items = ack.get("items", [])
        print(f"[取证] 清单条目数 {len(items) if isinstance(items, list) else 0}", flush=True)
        errors = host.validateAck(ack)
        print(f"[取证] 上位机侧校验 {errors if errors else '通过'}", flush=True)
    finally:
        system.stopSystem()
        host.stop()


if __name__ == "__main__":
    runProbe()
