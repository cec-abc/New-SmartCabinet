"""周期帧观察工具：起桩上位机监听端口，逐帧打印边缘机发来的周期帧并统计到达节奏。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from time import monotonic

from edge.tests.integration.fake_host import FakeHost, HostFrame

## @file edge/tests/integration/watch_periodic.py
## @brief 周期帧观察工具：起桩上位机，逐帧打印周期帧并统计到达节奏
## @author 边缘计算项目

## @brief 默认监听端口，与 config.ini 的 tcp.port 保持一致
DEFAULT_PORT: int = 9000
## @brief 默认监听地址，只监听本机回环
DEFAULT_HOST: str = "127.0.0.1"
## @brief 单帧读取的最长等待秒
FRAME_READ_TIMEOUT_SEC: float = 0.5
## @brief 统计摘要的打印间隔秒
SUMMARY_INTERVAL_SEC: float = 10.0
## @brief 统计窗口秒，窗口内的帧数与平均间隔用于摘要
STAT_WINDOW_SEC: float = 10.0
## @brief 观察总时长秒，0 表示一直观察到手动退出
UNLIMITED_DURATION_SEC: int = 0
## @brief 周期帧类型
PERIODIC_FRAME_TYPE: str = "periodic"
## @brief 识别应答帧类型
ACK_FRAME_TYPE: str = "recognize_ack"
## @brief 联调用的请求标识
PROBE_REQUEST_ID: str = "req-watch-0001"
## @brief 接入等待秒数
CLIENT_WAIT_SEC: float = 15.0


## @brief 读命令行参数；缺省或空串时降级为调用方给的备用值
#  @param index 参数位置，从 1 开始
#  @param fallback 缺省值
#  @return 参数文本
def readArgument(index: int, fallback: str) -> str:
    if len(sys.argv) > index and sys.argv[index]:
        return sys.argv[index]
    return fallback


## @brief 把相机状态列表压成一行摘要
#  @param frame 收到的帧
#  @return 摘要文本
def describeCameraStatus(frame: HostFrame) -> str:
    status = frame.get("camera_status")
    if not isinstance(status, list):
        return "无 camera_status"
    parts: list[str] = []
    for entry in status:
        if isinstance(entry, dict):
            cameraId = str(entry.get("camera_id", "?"))
            state = str(entry.get("status", "?"))
            parts.append(f"{cameraId}={state}")
    return " ".join(parts)


## @brief 统计窗口内的周期帧数量与平均间隔
#  @param stamps 周期帧到达时刻列表
#  @param now 当前时刻
#  @return 窗口内帧数与平均间隔秒
def summarize(stamps: list[float], now: float) -> tuple[int, float]:
    window = [stamp for stamp in stamps if stamp >= now - STAT_WINDOW_SEC]
    if len(window) < 2:
        return len(window), 0.0
    gaps = [
        window[index] - window[index - 1] for index in range(1, len(window))
    ]
    return len(window), sum(gaps) / len(gaps)


## @brief 观察主流程：等边缘机连上，逐帧打印并滚动统计
#  @param host 桩上位机
#  @param port 实际监听端口
#  @param durationSec 观察总时长秒，0 表示一直观察
#  @param sendReq 是否在接入后发一帧识别请求
#  @return 无
def runWatch(host: FakeHost, port: int, durationSec: int, sendReq: bool) -> None:
    print(f"[观察] 桩上位机监听 {DEFAULT_HOST}:{port}", flush=True)
    print("[观察] 等待边缘机接入；请在另一个窗口运行 edge/run_edge.bat", flush=True)
    if not host.waitClient(CLIENT_WAIT_SEC):
        print(f"[观察] {CLIENT_WAIT_SEC:.0f} 秒内没有等到边缘机接入，退出", flush=True)
        return
    print("[观察] 边缘机已接入，开始接收周期帧", flush=True)
    if sendReq:
        host.sendRecognizeReq(PROBE_REQUEST_ID)
        print(f"[观察] 已发出识别请求 {PROBE_REQUEST_ID}", flush=True)

    startedAt = monotonic()
    lastSummaryAt = startedAt
    periodicStamps: list[float] = []
    lastPeriodicAt: float | None = None
    lastFrameAt: float | None = None
    while durationSec == UNLIMITED_DURATION_SEC or monotonic() - startedAt < durationSec:
        frame = host.readHostFrame(FRAME_READ_TIMEOUT_SEC)
        now = monotonic()
        if frame is None:
            if now - lastSummaryAt >= SUMMARY_INTERVAL_SEC:
                count, average = summarize(periodicStamps, now)
                print(
                    f"[观察] 最近 {STAT_WINDOW_SEC:.0f} 秒收到 {count} 帧周期帧, "
                    f"平均间隔 {average:.2f} 秒",
                    flush=True,
                )
                lastSummaryAt = now
            continue
        localTime = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        frameType = str(frame.get("type", ""))
        gapText = "-"
        if lastFrameAt is not None:
            gapText = f"{now - lastFrameAt:.2f}s"
        lastFrameAt = now
        if frameType == PERIODIC_FRAME_TYPE:
            periodicStamps.append(now)
            intervalText = "-"
            if lastPeriodicAt is not None:
                intervalText = f"{now - lastPeriodicAt:.2f}s"
            lastPeriodicAt = now
            print(
                f"[{localTime}] periodic  距上帧 {gapText}  距上周期帧 {intervalText}  "
                f"{describeCameraStatus(frame)}",
                flush=True,
            )
            print(f"          原始帧 {json.dumps(frame, ensure_ascii=False)}", flush=True)
            errors = host.validatePeriodic(frame)
            print(
                f"          上位机侧校验 {errors if errors else '通过，8 路 camera_status 齐全'}",
                flush=True,
            )
        elif frameType == ACK_FRAME_TYPE:
            print(
                f"[{localTime}] {frameType}  距上帧 {gapText}  "
                f"原始帧 {json.dumps(frame, ensure_ascii=False)}",
                flush=True,
            )
        else:
            print(
                f"[{localTime}] {frameType}  距上帧 {gapText}  "
                f"原始帧 {json.dumps(frame, ensure_ascii=False)}",
                flush=True,
            )
    count, average = summarize(periodicStamps, monotonic())
    total = len(periodicStamps)
    print(
        f"[观察] 合计收到 {total} 帧周期帧, 最近 {STAT_WINDOW_SEC:.0f} 秒 {count} 帧, "
        f"平均间隔 {average:.2f} 秒",
        flush=True,
    )


## @brief 工具入口；用法 python -m edge.tests.integration.watch_periodic [端口] [时长秒] [req]
#  @return 无
def main() -> None:
    port = int(readArgument(1, str(DEFAULT_PORT)))
    durationSec = int(readArgument(2, str(UNLIMITED_DURATION_SEC)))
    sendReq = readArgument(3, "") == "req"
    host = FakeHost(DEFAULT_HOST, port)
    actualPort = host.start()
    try:
        runWatch(host, actualPort, durationSec, sendReq)
    except KeyboardInterrupt:
        print("[观察] 收到 Ctrl+C，退出", flush=True)
    finally:
        host.stop()


if __name__ == "__main__":
    main()
