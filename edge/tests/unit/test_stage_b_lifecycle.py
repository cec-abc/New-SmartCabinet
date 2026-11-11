"""阶段 b 补强单测：可打断等待、join 超时、重复 stop 幂等、BaseService 多态与异常边界。"""
from __future__ import annotations

import time
from threading import Event

from edge.base.base_service import BaseService
from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError, ErrorCode
from edge.tests.fakes.fake_logger import FakeLogger


## @brief 测试替身：每轮做一次可打断等待，记录完成的轮数
class WaitLoopThread(BaseThread):
    ## @brief 构造替身
    #  @param name 线程名
    #  @param waitSec 单轮等待秒数
    #  @param entered 进入等待前通知主测试的事件
    #  @param rounds 已完成轮数记录
    def __init__(self, name: str, waitSec: float, entered: Event, rounds: list[int]) -> None:
        super().__init__(name=name)
        ## @brief 单轮等待秒数
        self.waitSec: float = waitSec
        ## @brief 进入等待前通知主测试
        self.entered: Event = entered
        ## @brief 已完成轮数
        self.rounds: list[int] = rounds

    ## @brief 收到停止指令立即退出循环
    #  @return 无
    def runLoop(self) -> None:
        while True:
            self.entered.set()
            if not self.interruptibleWait(self.waitSec):
                return
            self.rounds.append(len(self.rounds) + 1)


## @brief 测试替身：模拟无法被停止事件唤醒的阻塞，验证 join 超时
class BlockingLoopThread(BaseThread):
    ## @brief 构造替身
    #  @param name 线程名
    #  @param entered 进入阻塞前通知主测试的事件
    #  @param release 外部释放事件
    def __init__(self, name: str, entered: Event, release: Event) -> None:
        super().__init__(name=name)
        ## @brief 进入阻塞前通知主测试
        self.entered: Event = entered
        ## @brief 外部释放事件
        self.release: Event = release

    ## @brief 阻塞在外部事件上，直到测试释放
    #  @return 无
    def runLoop(self) -> None:
        self.entered.set()
        self.release.wait(5.0)


## @brief 测试替身：不启动线程，只用于直接调用 interruptibleWait
class IdleThread(BaseThread):
    ## @brief 构造替身
    #  @param name 线程名
    def __init__(self, name: str) -> None:
        super().__init__(name=name)

    ## @brief 空主循环
    #  @return 无
    def runLoop(self) -> None:
        return None


## @brief 测试替身：runLoop 抛内置异常，验证跨线程边界前转 EdgeError
class FailingThread(BaseThread):
    ## @brief 构造替身
    #  @param name 线程名
    #  @param logger 日志 Fake
    def __init__(self, name: str, logger: FakeLogger) -> None:
        super().__init__(name=name, logger=logger)

    ## @brief 故意抛出内置异常
    #  @return 无
    #  @raises ValueError 固定抛出，用于验证边界转换
    def runLoop(self) -> None:
        raise ValueError("runLoop 故障")


## @brief 测试替身：记录 BaseService 三件套的调用顺序
class RecordingService(BaseService):
    ## @brief 构造替身
    def __init__(self) -> None:
        ## @brief 调用顺序记录
        self.calls: list[str] = []

    ## @brief 记录 init
    #  @return 无
    def init(self) -> None:
        self.calls.append("init")

    ## @brief 记录 start
    #  @return 无
    def start(self) -> None:
        self.calls.append("start")

    ## @brief 记录 stop
    #  @return 无
    def stop(self) -> None:
        self.calls.append("stop")


# 对应验收项 b-1：stop() 瞬间打断 interruptibleWait
def testStopInterruptsInterruptibleWaitImmediately() -> None:
    entered = Event()
    rounds: list[int] = []
    worker = WaitLoopThread("b-1", 30.0, entered, rounds)
    worker.start()
    assert entered.wait(1.0) is True
    startedAt = time.monotonic()
    worker.stop(timeout=1.0)
    elapsed = time.monotonic() - startedAt
    assert elapsed < 0.8
    assert rounds == []
    assert worker.is_alive() is False
    assert worker.isRunning() is False
    assert worker.interruptibleWait(0.01) is False


# 对应验收项 b-1：未收到停止指令时 interruptibleWait 返回 True
def testInterruptibleWaitReturnsTrueWithoutStopSignal() -> None:
    worker = IdleThread("b-1-idle")
    assert worker.interruptibleWait(0.01) is True
    worker.stop(timeout=0.0)
    assert worker.interruptibleWait(0.01) is False


# 对应验收项 b-1：runLoop 内置异常在线程边界前转 EdgeError 并记日志
def testRunLoopExceptionBecomesEdgeErrorInLogger() -> None:
    logger = FakeLogger()
    worker = FailingThread("b-1-error", logger)
    worker.start()
    worker.join(timeout=1.0)
    assert worker.is_alive() is False
    assert len(logger.errorRecords) == 1
    module, message, exception = logger.errorRecords[0]
    assert module == "BaseThread"
    assert message == "b-1-error runLoop 异常 CONFIG"
    assert isinstance(exception, EdgeError) is True
    assert isinstance(exception, ValueError) is False
    if isinstance(exception, EdgeError):
        assert exception.code == ErrorCode.CONFIG


# 对应验收项 b-2：join 超时强制返回，线程仍存活不挂死
def testStopReturnsAfterJoinTimeout() -> None:
    entered = Event()
    release = Event()
    worker = BlockingLoopThread("b-2", entered, release)
    worker.start()
    assert entered.wait(1.0) is True
    startedAt = time.monotonic()
    worker.stop(timeout=0.2)
    elapsed = time.monotonic() - startedAt
    assert elapsed < 1.0
    assert worker.is_alive() is True
    release.set()
    worker.join(timeout=1.0)
    assert worker.is_alive() is False


# 对应验收项 b-3：重复 stop 幂等，重复 start 不抛异常
def testRepeatedStopIsIdempotent() -> None:
    entered = Event()
    rounds: list[int] = []
    worker = WaitLoopThread("b-3", 30.0, entered, rounds)
    worker.start()
    assert entered.wait(1.0) is True
    worker.stop(timeout=1.0)
    worker.stop(timeout=1.0)
    worker.stop(timeout=0.0)
    worker.start()
    assert worker.is_alive() is False
    assert worker.isRunning() is False
    assert worker.stopEvent.is_set() is True
    assert rounds == []


# 对应验收项 b-3：BaseService 三件套可多态且基类默认为空实现
def testBaseServiceLifecycleIsPolymorphic() -> None:
    service = RecordingService()
    service.init()
    service.start()
    service.stop()
    assert service.calls == ["init", "start", "stop"]
    assert isinstance(service, BaseService) is True
    plainService = BaseService()
    plainService.init()
    plainService.start()
    plainService.stop()
    assert plainService.__dict__ == {}
