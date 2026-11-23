"""USB 摄像头周期巡检线程：采集空闲时逐路错峰探测设备可用性。"""
## @file edge/modules/usb/usb_camera_probe_thread.py
## @brief 周期巡检线程：仅调度，探测动作由注入回调完成；采集在跑时跳过，避免重复取帧
## @author 袁燕
from __future__ import annotations

from collections.abc import Callable

from edge.base.base_thread import BaseThread
from edge.interfaces.i_logger import ILogger

## @brief 默认巡检周期秒数：8 路错峰下单路约 8 秒复检一次，兼顾状态响应与取帧开销
DEFAULT_PROBE_INTERVAL_SEC: float = 1.0


## @brief 摄像头周期巡检线程；采集空闲时每轮只探一路，错峰降低瞬时开销
class CameraProbeThread(BaseThread):
    ## @brief 构造巡检线程
    #  @param cameraCount 摄像头路数
    #  @param probeIfIdle 原子化的"空闲则探一路"回调；内部须与采集启停互斥
    #  @param logger 可选日志器
    #  @param probeIntervalSec 两轮巡检之间的等待秒数（构造注入）
    #  @return 无
    #  @note 不分别注入"判据+探测"两个回调：分开会在判据与探测之间留下竞态窗口，
    #        采集若在窗口内启动，巡检的 close 会释放 worker 刚打开的句柄
    def __init__(self, cameraCount: int, probeIfIdle: Callable[[], None],
                 logger: ILogger | None = None,
                 probeIntervalSec: float = DEFAULT_PROBE_INTERVAL_SEC) -> None:
        super().__init__(name="CameraProbe", logger=logger)
        ## @brief 摄像头路数
        self._cameraCount: int = cameraCount
        ## @brief 原子化的空闲探测回调
        self._probeIfIdle: Callable[[], None] = probeIfIdle
        ## @brief 两轮巡检之间的等待秒数
        self._probeIntervalSec: float = probeIntervalSec
        ## @brief 下一路待巡检的物理下标，逐路错峰
        self._nextIndex: int = 0

    ## @brief 巡检主循环：每轮只探一路，采集在跑时跳过，等待可被停止打断
    #  @return 无
    def runLoop(self) -> None:
        ## 首轮先等一个周期，让启动阶段的采集有机会拉起，避免巡检抢先读帧
        if not self.interruptibleWait(self._probeIntervalSec):
            return
        while self.isRunning():
            ## 错峰下标由 controller 回调内部维护（回调与采集启停同一把锁）
            self._probeIfIdle()
            if not self.interruptibleWait(self._probeIntervalSec):
                return
