"""线程接口 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_thread import IThread


## @brief 不创建真实线程、只记录生命周期调用的 Fake
class FakeThread(IThread):
    ## @brief 构造 Fake
    def __init__(self) -> None:
        ## @brief start 调用次数
        self.startCount = 0
        ## @brief stop 收到的超时参数
        self.stopTimeouts: list[float] = []
        ## @brief 模拟的运行态
        self.running = False

    ## @brief 记录启动
    #  @return 无
    def start(self) -> None:
        self.startCount += 1
        self.running = True

    ## @brief 记录停止
    #  @param timeout 等待秒数
    #  @return 无
    def stop(self, timeout: float = 3.0) -> None:
        self.stopTimeouts.append(timeout)
        self.running = False

    ## @brief 返回模拟运行态
    #  @return 运行中返回 True
    def isRunning(self) -> bool:
        return self.running
