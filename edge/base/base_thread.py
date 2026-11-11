"""通用线程基类：统一启动幂等、可打断等待与停机生命周期。"""
from __future__ import annotations

from abc import abstractmethod
from threading import Event, Lock, Thread

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_thread import IThread


## @brief 所有业务线程的基类；置停止事件唤醒等待，join 超时强制返回
class BaseThread(Thread, IThread):
    ## @brief 构造线程
    #  @param name 线程名
    #  @param logger 可选日志器，用于线程顶层异常与停机统计
    def __init__(self, name: str, logger: ILogger | None = None) -> None:
        super().__init__(name=name, daemon=True)
        ## @brief 停止事件，置位后 interruptibleWait 立即返回 False
        self.stopEvent: Event = Event()
        ## @brief 是否已启动过，保证 start() 幂等
        self._hasStarted: bool = False
        ## @brief 启动锁，避免并发重复拉起线程
        self._startLock: Lock = Lock()
        ## @brief 停止锁与请求标记，保证重复 stop 幂等
        self._stopLock: Lock = Lock()
        ## @brief 是否已发出停止请求
        self._stopRequested: bool = False
        ## @brief 注入的日志器，为空时不记录异常与统计
        self._logger: ILogger | None = logger

    ## @brief 启动线程；重复调用直接返回，不抛 RuntimeError
    #  @return 无
    def start(self) -> None:
        with self._startLock:
            if self._hasStarted:
                return
            self._hasStarted = True
        super().start()

    ## @brief 置停止事件、唤醒可打断等待、join 后超时强制返回；重复调用幂等
    #  @param timeout 等待线程退出的最长秒数
    #  @return 无
    def stop(self, timeout: float = 3.0) -> None:
        with self._stopLock:
            if self._stopRequested:
                return
            self._stopRequested = True
            self.stopEvent.set()
        ## 未启动或已退出的线程不再 join，join 本身超时即返回、不杀线程
        if self._hasStarted and self.is_alive():
            self.join(timeout)
        self._logStopStats(timeout)

    ## @brief 查询运行态：已启动、仍存活且未收到停止指令
    #  @return 运行中返回 True
    def isRunning(self) -> bool:
        return self._hasStarted and self.is_alive() and not self.stopEvent.is_set()

    ## @brief 周期等待；False 表示收到停止指令，禁止在业务线程里裸 sleep
    #  @param sec 等待秒数，由调用方构造注入
    #  @return 未收到停止指令返回 True
    def interruptibleWait(self, sec: float) -> bool:
        return not self.stopEvent.wait(sec)

    ## @brief 线程入口；顶层异常统一转 EdgeError 后记录，不穿越线程边界
    #  @return 无
    def run(self) -> None:
        try:
            self.runLoop()
        except EdgeError as error:
            self._reportError(error)
        except Exception as error:
            ## 内置异常在跨线程边界前统一转 EdgeError；业务码细分留 c3 / d
            self._reportError(EdgeError(ErrorCode.CONFIG, f"{self.name} 运行异常: {error}"))

    ## @brief 线程主循环，由子类实现
    #  @return 无
    @abstractmethod
    def runLoop(self) -> None:
        ...

    ## @brief 记录线程内异常，日志异常码使用 code.name
    #  @param error 业务异常
    #  @return 无
    def _reportError(self, error: EdgeError) -> None:
        if self._logger is None:
            return
        message = f"{self.name} runLoop 异常 {error.code.name}"
        self._logger.error("BaseThread", message, exception=error)

    ## @brief 用 info 记录本次停机统计
    #  @param timeout 本次 stop 使用的超时秒数
    #  @return 无
    def _logStopStats(self, timeout: float) -> None:
        if self._logger is None:
            return
        stats = f"{self.name} stop(timeout={timeout}) 存活={self.is_alive()}"
        self._logger.info("BaseThread", stats)
