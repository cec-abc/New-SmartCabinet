"""进程入口：第一件事拿进程锁，装配、注册信号、启动、等待退出、严格串行停机。"""
from __future__ import annotations

import signal
from collections.abc import Callable
from functools import partial
from threading import Event
from types import FrameType

from edge.app_init import AssemblyParts, buildSystem, defaultParts
from edge.interfaces.i_platform import IPlatformAdapter
from edge.platform.adapter import PlatformFactory
from edge.platform.file_lock import DEFAULT_LOCK_FILE_NAME, ProcessFileLock

## @brief 装配参数提供器（注入，便于测试替换）
PartsProvider = Callable[[], AssemblyParts]
## @brief 平台适配器提供器（注入，便于测试替换）
AdapterProvider = Callable[[], IPlatformAdapter]
## @brief 信号注册器（注入，便于测试替换）
SignalRegistrar = Callable[[Event], None]
## @brief 退出等待器（注入，便于测试替换）
ExitWaiter = Callable[[], None]


## @brief 停止信号处理：只置位退出事件，不做阻塞 IO
#  @param stopEvent 退出事件
#  @param signum 信号编号
#  @param frame 信号栈帧
#  @return 无
def requestStop(stopEvent: Event, signum: int, frame: FrameType | None) -> None:
    stopEvent.set()


## @brief 注册中断与终止信号
#  @param stopEvent 退出事件
#  @return 无
def registerSignals(stopEvent: Event) -> None:
    mapping = PlatformFactory.create().signalMap()

    ## @brief 转发信号到退出事件
    #  @param signum 信号编号
    #  @param frame 信号栈帧
    #  @return 无
    def handleSignal(signum: int, frame: FrameType | None) -> None:
        requestStop(stopEvent, signum, frame)

    signal.signal(mapping["interrupt"], handleSignal)
    signal.signal(mapping["terminate"], handleSignal)


## @brief 默认阻塞等待，收到停止信号后返回
#  @param stopEvent 退出事件
#  @return 无
def waitForStop(stopEvent: Event) -> None:
    stopEvent.wait()


## @brief 进程入口；不用 try/except 或 if not success 包裹业务流程
#  @param partsProvider 装配参数提供器
#  @param signalRegistrar 信号注册器
#  @param exitWaiter 退出等待器
#  @param adapterProvider 平台适配器提供器
#  @return 无
def main(partsProvider: PartsProvider | None = None,
         signalRegistrar: SignalRegistrar | None = None,
         exitWaiter: ExitWaiter | None = None,
         adapterProvider: AdapterProvider | None = None) -> None:
    adapter = adapterProvider() if adapterProvider is not None else PlatformFactory.create()
    processLock = ProcessFileLock(adapter, DEFAULT_LOCK_FILE_NAME)
    ## 第一件事拿进程单文件锁，失败由 acquireOrExit 内部退出
    processLock.acquireOrExit()
    parts = partsProvider() if partsProvider is not None else defaultParts()
    system = buildSystem(parts)
    stopEvent = Event()
    registrar = signalRegistrar if signalRegistrar is not None else registerSignals
    registrar(stopEvent)
    system.startSystem()
    waiter = exitWaiter if exitWaiter is not None else partial(waitForStop, stopEvent)
    waiter()
    system.stopSystem()
    processLock.release()


if __name__ == "__main__":
    main()
