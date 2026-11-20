"""真实上位机联调检查：拉起真实上位机进程，以边缘机身份接入，用上位机自己的日志取证。

本脚本不改动上位机工程任何文件，只做两件事：
1. 启动上位机可执行文件（<exe 同级>/system.ini 已有 MySQL 连接串），并把 SC_LOG_DIR
   指到系统临时目录，使上位机日志不落进上位机工程目录；
2. 以 TCP 客户端身份连接上位机的 9000 端口，依次发周期帧与三种应答帧，
   再从上位机日志里提取它的真实反应作为证据。

区分说明（本脚本只能覆盖帧层与链路层）：
- 帧层"上位机认不认这个帧"的最终判据来自上位机自带的编译产物
  build/tests/Debug/test_edge.exe（真实 EdgeService::parseItems），本脚本不重复该判定；
- 本脚本证明的是"真实上位机进程收到了我们的帧、并按协议解析"，以及
  request_id 必须用 snake_case 的 request_id（上位机日志回带的编号可区分）。

用法（工作目录为仓库根）：
    python -m edge.tests.integration.live_link_check
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep

## @file edge/tests/integration/live_link_check.py
## @brief 真实上位机进程联调：接入 9000 端口并从上位机日志取证
## @author 边缘计算项目

## @brief 上位机可执行文件默认位置（只读引用，不修改）
DEFAULT_HOST_EXE: str = (
    r"D:\CFDZ\smartCabinet\trunk\SmartCabinetLite\build\Debug\QtSmartCabinet.exe"
)
## @brief 上位机 TCP 服务端口（CommTypes.h:16）
HOST_PORT: int = 9000
## @brief 等待上位机就绪的最长秒数；上位机启动要连库、起人脸相机、加载识别模型，实测约 16 秒
HOST_READY_WAIT_SEC: float = 150.0
## @brief 上位机就绪后额外等待秒数，给人脸模型加载留出时间
HOST_SETTLE_SEC: float = 3.0
## @brief 发出帧后等待上位机落日志的秒数
LOG_SETTLE_SEC: float = 2.0
## @brief 联调用的请求编号
LIVE_REQUEST_ID: str = "req-live-0001"
## @brief 联调用的驼峰键名对照编号（上位机不读这个键）
LIVE_CAMEL_REQUEST_ID: str = "req-live-0002"
## @brief 打印的上位机日志尾部行数
LOG_TAIL_LINES: int = 40
## @brief 上位机进入事件循环的日志标志（LoginPage 上屏即为 app.exec() 已开始）
HOST_READY_MARKER: str = "showEvent"


## @brief 等待上位机进入事件循环（以日志标志为准，不做探测连接）
#  @param logDir 上位机日志目录
#  @param process 上位机进程
#  @param timeoutSec 最长等待秒数
#  @return 就绪返回 True
def waitForHostReady(logDir: Path, process: subprocess.Popen[bytes],
                     timeoutSec: float) -> bool:
    deadline = monotonic() + timeoutSec
    while monotonic() < deadline:
        if process.poll() is not None:
            return False
        if HOST_READY_MARKER in readHostLog(logDir):
            sleep(HOST_SETTLE_SEC)
            return True
        sleep(0.5)
    return False


## @brief 构造 8 路全部正常的周期帧
#  @param uptimeSec 运行时长秒
#  @return 周期帧
def buildPeriodicFrame(uptimeSec: int) -> dict[str, object]:
    return {
        "type": "periodic",
        "uptime_sec": uptimeSec,
        "software_version": "edge-live-0.1.0",
        "camera_status": [
            {"camera_id": f"CAM{index}", "status": "ok"} for index in range(1, 9)
        ],
    }


## @brief 构造合法形状的识别应答帧
#  @param requestId 请求编号
#  @return 应答帧
def buildSnakeCaseAck(requestId: str) -> dict[str, object]:
    return {
        "type": "recognize_ack",
        "request_id": requestId,
        "items": [
            {
                "position": "A-01-05",
                "tool_id": "C01-T0007",
                "confidence": 0.93,
                "alert_type": "none",
            },
        ],
    }


## @brief 构造只带驼峰 requestId 的应答帧（上位机读不到编号的对照组）
#  @param requestId 请求编号
#  @return 应答帧
def buildCamelCaseAck(requestId: str) -> dict[str, object]:
    return {
        "type": "recognize_ack",
        "requestId": requestId,
        "items": [
            {
                "position": "A-01-05",
                "tool_id": "C01-T0007",
                "confidence": 0.93,
                "alert_type": "none",
            },
        ],
    }


## @brief 读取上位机日志目录里当天的日志全文
#  @param logDir 上位机日志目录
#  @return 日志全文；没有日志文件返回空串
def readHostLog(logDir: Path) -> str:
    name = f"app_{datetime.now().strftime('%Y%m%d')}.log"
    path = logDir / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


## @brief 从日志里筛出与联调证据相关的行
#  @param logText 日志全文
#  @return 证据行列表
def extractEvidence(logText: str) -> list[str]:
    markers = (
        "[EdgeLink] listening on port",
        "[EdgeLink] client connected",
        "[EdgeLink] 收到帧",
        "[EdgeService] 丢弃帧",
        "[EdgeService] 识别清单结构校验失败",
        "[EdgeService] 识别回应已配对",
        "[EdgeLink] bad frame",
    )
    return [line for line in logText.splitlines() if any(marker in line for marker in markers)]


## @brief 终止上位机进程并确保子进程一并退出
#  @param process 上位机进程
#  @return 无
def stopHostProcess(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


## @brief 跑一次真实上位机联调并输出取证结果
#  @param exePath 上位机可执行文件路径
#  @return 0 表示全部取证点都拿到；1 表示有取证点缺失
def main(exePath: str = DEFAULT_HOST_EXE) -> int:
    exe = Path(exePath)
    if not exe.exists():
        print(f"[联调] 上位机可执行文件不存在: {exe}")
        print("[联调] 真实上位机进程联调无法执行")
        return 1

    logDir = Path(tempfile.mkdtemp(prefix="edge_live_host_"))
    env = dict(os.environ)
    ## 上位机 Logger 读 SC_LOG_DIR，未设置时写 exe 同级 logs/；这里指到临时目录避免污染上位机工程
    env["SC_LOG_DIR"] = str(logDir)

    print(f"[联调] 上位机可执行文件: {exe}")
    print(f"[联调] 上位机日志目录(临时): {logDir}")

    process = subprocess.Popen(
        [str(exe)], cwd=str(exe.parent), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        if not waitForHostReady(logDir, process, HOST_READY_WAIT_SEC):
            print(f"[联调] 等待上位机就绪超时，进程返回码={process.poll()}")
            stdout, stderr = process.communicate(timeout=5)
            print(f"[联调] stdout={stdout.decode('utf-8', 'replace')[-800:]}")
            print(f"[联调] stderr={stderr.decode('utf-8', 'replace')[-800:]}")
            return 1
        print(f"[联调] 上位机已进入事件循环并监听 {HOST_PORT} 端口，边缘机接入")

        with socket.create_connection(("127.0.0.1", HOST_PORT), timeout=5) as sock:
            sock.settimeout(5)
            ## 1) 周期帧：上位机应按 periodic 解析并据此判在线
            periodic = buildPeriodicFrame(1)
            sock.sendall(json.dumps(periodic, ensure_ascii=False).encode("utf-8") + b"\n")
            print(f"[联调] 已发送周期帧: {json.dumps(periodic, ensure_ascii=False)[:120]}...")
            sleep(LOG_SETTLE_SEC)

            ## 2) snake_case request_id 的应答帧：上位机日志回带的编号应非空
            snakeAck = buildSnakeCaseAck(LIVE_REQUEST_ID)
            sock.sendall(json.dumps(snakeAck, ensure_ascii=False).encode("utf-8") + b"\n")
            print(f"[联调] 已发送 snake_case 应答帧 request_id={LIVE_REQUEST_ID}")
            sleep(LOG_SETTLE_SEC)

            ## 3) 只带驼峰 requestId 的应答帧：上位机读不到编号，日志回带应为空
            camelAck = buildCamelCaseAck(LIVE_CAMEL_REQUEST_ID)
            sock.sendall(json.dumps(camelAck, ensure_ascii=False).encode("utf-8") + b"\n")
            print(f"[联调] 已发送 camelCase 对照帧 requestId={LIVE_CAMEL_REQUEST_ID}")
            sleep(LOG_SETTLE_SEC)

            ## 4) 未知 type 的帧：上位机应按协议 3.6-② 丢弃并计数
            unknownFrame = {"type": "weird_type", "request_id": LIVE_REQUEST_ID}
            sock.sendall(json.dumps(unknownFrame, ensure_ascii=False).encode("utf-8") + b"\n")
            print("[联调] 已发送未知 type 对照帧 type=weird_type")
            sleep(LOG_SETTLE_SEC)

        logText = readHostLog(logDir)
        evidence = extractEvidence(logText)
        print("[联调] 上位机日志证据行:")
        for line in evidence:
            print(f"    {line}")
        print(f"[联调] 上位机日志全文行数={len(logText.splitlines())}")
        print("[联调] 上位机日志尾部:")
        for line in logText.splitlines()[-LOG_TAIL_LINES:]:
            print(f"    {line}")

        joined = "\n".join(evidence)
        checks: list[tuple[str, bool]] = [
            ("上位机在 9000 端口监听", "[EdgeLink] listening on port 9000" in joined),
            ("边缘机已连上上位机", "[EdgeLink] client connected" in joined),
            ("上位机收到并解析 periodic 周期帧", 'type= "periodic"' in joined),
            ("snake_case request_id 被上位机读到",
             f'"{LIVE_REQUEST_ID}"' in joined),
            ("驼峰 requestId 上位机读不到（回带编号为空）",
             '丢弃帧' in joined and f'"{LIVE_CAMEL_REQUEST_ID}"' not in joined),
            ("未知 type 被上位机按 3.6-② 丢弃", "未知type:" in joined),
        ]
        print("[联调] 取证结论:")
        failed = 0
        for name, passed in checks:
            print(f"    [{'通过' if passed else '未取到'}] {name}")
            if not passed:
                failed += 1
        print(f"[联调] 取证点 {len(checks) - failed}/{len(checks)} 命中")
        return 0 if failed == 0 else 1
    finally:
        stopHostProcess(process)
        print("[联调] 上位机进程已退出")


## @brief 脚本入口
#  @return 退出码
def run() -> int:
    exePath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST_EXE
    return main(exePath)


if __name__ == "__main__":
    sys.exit(run())
