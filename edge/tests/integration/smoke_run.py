"""手工冒烟脚本：起桩上位机 + 跑边缘机 main.py，确认周期帧与识别应答真实出网。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from time import monotonic

from edge import main
from edge.app_init import AssemblyParts, buildFrameSender, defaultParts
from edge.modules.tcp.tcp_comm import TcpComm
from edge.tests.integration.fake_host import FakeHost
from edge.tests.integration.tcp_client_socket import TcpClientSocket

## @file edge/tests/integration/smoke_run.py
## @brief 手工冒烟脚本：起桩上位机加边缘机 main.py，确认周期帧与识别应答真实出网
## @author 边缘计算项目

## @brief 边缘机工程根目录
EDGE_ROOT: Path = Path(__file__).resolve().parents[2]
## @brief 正式配置文件路径
CONFIG_PATH: Path = EDGE_ROOT / "config" / "config.ini"
## @brief 冒烟运行时长秒，留出周期帧与应答的时间
SMOKE_RUN_SEC: float = 8.0
## @brief 等待边缘机接入的最长秒数
CLIENT_WAIT_SEC: float = 5.0
## @brief 冒烟用的请求标识
SMOKE_REQUEST_ID: str = "req-smoke-0001"


## @brief 在临时工作目录里铺好采集、识别与日志目录
#  @param workDir 工作目录
#  @return 无
def prepareRuntimeDirs(workDir: Path) -> None:
    for name in ("capture/w1", "capture/w2", "capture/w3", "capture/w4",
                 "recog/w1", "recog/w2", "recog/w3", "recog/w4", "logs"):
        (workDir / name).mkdir(parents=True, exist_ok=True)


## @brief 构造冒烟用装配参数：读正式配置，并把套接字换成连桩上位机的真实连接
#  @param hostPort 桩上位机端口
#  @return 装配参数
def buildSmokeParts(hostPort: int) -> AssemblyParts:
    parts = defaultParts(str(CONFIG_PATH))
    clientSocket = TcpClientSocket("127.0.0.1", hostPort)
    parts.socket = clientSocket
    parts.frameSender = buildFrameSender(
        TcpComm(clientSocket, parts.maxFrameSize, parts.logger),
    )
    return parts


## @brief 执行一次冒烟：起桩上位机、跑边缘机 main.py、打印收到的帧与校验结论
#  @return 无
def runSmoke() -> None:
    host = FakeHost()
    port = host.start()
    workDir = Path(tempfile.mkdtemp(prefix="edge-smoke-"))
    prepareRuntimeDirs(workDir)
    os.chdir(workDir)
    print(f"[冒烟] 桩上位机监听 127.0.0.1:{port}")
    print(f"[冒烟] 边缘机工作目录 {workDir}")
    print(f"[冒烟] 正式配置 {CONFIG_PATH}")

    def partsProvider() -> AssemblyParts:
        return buildSmokeParts(port)

    def exitWaiter() -> None:
        connected = host.waitClient(CLIENT_WAIT_SEC)
        print(f"[冒烟] 边缘机接入 {connected}")
        host.sendRecognizeReq(SMOKE_REQUEST_ID)
        ## 持续读取桩上位机收到的帧，直到冒烟窗口结束
        deadline = monotonic() + SMOKE_RUN_SEC
        while monotonic() < deadline:
            host.readHostFrame(0.5)

    try:
        main.main(partsProvider=partsProvider, exitWaiter=exitWaiter)
    finally:
        host.stop()

    periodicCount = 0
    ackCount = 0
    ackErrors: list[str] = []
    for frame in host.receivedFrames():
        print(f"[桩上位机 收到] {json.dumps(frame, ensure_ascii=False)}")
        frameType = str(frame.get("type", ""))
        if frameType == "periodic":
            periodicCount += 1
            print(f"[桩上位机 校验] 周期帧错误 {host.validatePeriodic(frame)}")
        if frameType == "recognize_ack":
            ackCount += 1
            ackErrors = host.validateAck(frame)
            print(f"[桩上位机 校验] 应答帧错误 {ackErrors}")
    print(f"[冒烟] 周期帧 {periodicCount} 帧, 识别应答 {ackCount} 帧")
    print(f"[冒烟] 最后一帧应答校验结论 {ackErrors}")
    print(f"[冒烟] 边缘机日志目录 {workDir / 'logs'}")


if __name__ == "__main__":
    runSmoke()
