"""应答排空线程：周期调用排空动作，把待发应答真正送出。"""
from __future__ import annotations

from collections.abc import Callable

from edge.base.base_thread import BaseThread
from edge.interfaces.i_logger import ILogger

## @file edge/control/edge_dispatch_thread.py
## @brief 应答排空线程：周期调用排空动作，把待发应答真正送出
## @author 袁燕

## @brief 日志模块名
MODULE_NAME: str = "EdgeDispatch"


## @brief 应答排空线程；只服务控制层，生命周期随控制层启停
class EdgeDispatchThread(BaseThread):
    ## @brief 构造排空线程
    #  @param dispatchAction 排空动作，注入后由本线程周期调用
    #  @param logger 日志器（注入）
    #  @param pollIntervalSec 排空周期秒（构造注入）
    #  @return 无
    def __init__(self, dispatchAction: Callable[[], None], logger: ILogger,
                 pollIntervalSec: float) -> None:
        super().__init__(name="EdgeDispatch", logger=logger)
        ## @brief 排空动作
        self._dispatchAction: Callable[[], None] = dispatchAction
        ## @brief 排空周期秒
        self._pollIntervalSec: float = pollIntervalSec

    ## @brief 主循环：先排空一次再周期等待，停止指令到达立即退出
    #  @return 无
    def runLoop(self) -> None:
        while self.isRunning():
            self._dispatchAction()
            if not self.interruptibleWait(self._pollIntervalSec):
                return
