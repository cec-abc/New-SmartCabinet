"""USB 采集门面：初始化校验、并发拉起采集线程与 Sink 回调转接。"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from threading import Lock

from edge.base.base_service import BaseService
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import ICameraDevice
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import ICaptureSink
from edge.modules.usb.usb_capture_worker import CaptureWorker

## @brief 日志模块名
MODULE_NAME = "UsbController"


## @brief USB 采集门面；采集指令唯一下发出口，只依赖 i_sinks.py 回调契约
class UsbController(BaseService):
    ## @brief 构造门面
    #  @param cameraPairs 每个 worker 的左右两路设备（注入）
    #  @param saveDirs 每个 worker 的专属存储目录（注入）
    #  @param sink 采集事件回调（注入）
    #  @param logger 可选日志器
    #  @param rollThreshold 占用比例阈值（构造注入）
    #  @param usageRatio 占用比例提供器（注入）
    #  @param clock 文件名时间戳提供器（注入）
    def __init__(self, cameraPairs: list[tuple[ICameraDevice, ICameraDevice]],
                 saveDirs: list[str], sink: ICaptureSink, logger: ILogger | None,
                 rollThreshold: float, usageRatio: Callable[[], float],
                 clock: Callable[[], str]) -> None:
        ## @brief 设备组
        self._cameraPairs: list[tuple[ICameraDevice, ICameraDevice]] = cameraPairs
        ## @brief 存储目录
        self._saveDirs: list[str] = saveDirs
        ## @brief 采集事件回调
        self._sink: ICaptureSink = sink
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief 占用比例阈值
        self._rollThreshold: float = rollThreshold
        ## @brief 占用比例提供器
        self._usageRatio: Callable[[], float] = usageRatio
        ## @brief 时间戳提供器
        self._clock: Callable[[], str] = clock
        ## @brief 是否已初始化
        self._inited: bool = False
        ## @brief 是否正在采集
        self._capturing: bool = False
        ## @brief 并发启停锁
        self._captureLock: Lock = Lock()
        ## @brief 当前采集线程实例（每次拉起新建）
        self._workers: list[CaptureWorker] = []

    ## @brief 初始化：校验目录存在且可写，Fail-Fast 不引入能力降级
    #  @return 无
    #  @raises EdgeError 配置不完整或目录不可写时抛出，code=CONFIG
    def init(self) -> None:
        if not self._cameraPairs or len(self._cameraPairs) != len(self._saveDirs):
            raise EdgeError(ErrorCode.CONFIG, "USB 采集配置不完整")
        for saveDir in self._saveDirs:
            path = Path(saveDir)
            if not path.is_dir() or not os.access(str(path), os.W_OK):
                raise EdgeError(ErrorCode.CONFIG, f"USB 采集目录不可写: {saveDir}")
        self._inited = True
        if self._logger is not None:
            message = f"USB 初始化完成, 配置 {len(self._saveDirs)} 个 Worker"
            self._logger.info(MODULE_NAME, message)

    ## @brief 生命周期启动；前置校验在 startCapture 内完成
    #  @return 无
    def start(self) -> None:
        self.startCapture()

    ## @brief 生命周期停止
    #  @return 无
    def stop(self) -> None:
        self.stopCapture()

    ## @brief 前置校验后并发拉起全部 worker 并立即返回，不等待子线程
    #  @return 无
    #  @raises EdgeError 未初始化或已在采集中时抛出，code=CONFIG
    def startCapture(self) -> None:
        with self._captureLock:
            if not self._inited or self._capturing:
                raise EdgeError(ErrorCode.CONFIG, "USB 未初始化或已在采集中")
            ## 每次拉起新建实例，绕开 BaseThread.start 的启动幂等
            workers = self._buildWorkers()
            self._workers = workers
            self._capturing = True
        for worker in workers:
            worker.start()
        if self._logger is not None:
            message = f"已拉起 {len(workers)} 个采集线程"
            self._logger.info(MODULE_NAME, message)

    ## @brief 中断全部采集线程并清空实例，允许下一轮重新拉起
    #  @return 无
    def stopCapture(self) -> None:
        with self._captureLock:
            workers = list(self._workers)
            self._workers = []
            self._capturing = False
        for worker in workers:
            worker.stop()

    ## @brief 自检预留空接口（裁决 D-01）；本轮不实现、不新增自检线程、不做能力降级
    #  @return 无
    def selfCheck(self) -> None:
        # TODO: 自检逻辑后续实现时另起独立自检线程，不占用采集线程与主线程
        return None

    ## @brief worker 成功回调：只做轻量转发，禁止在此执行阻塞 IO
    #  @param workerId 线程编号
    #  @param path 采集目录
    #  @return 无
    def onWorkerSuccess(self, workerId: int, path: str) -> None:
        self._sink.onCaptureSuccess(workerId, path)

    ## @brief worker 失败回调：只做轻量转发，不影响其他线程
    #  @param workerId 线程编号
    #  @param exception 业务异常
    #  @return 无
    def onWorkerError(self, workerId: int, exception: Exception) -> None:
        self._sink.onCaptureError(workerId, exception)

    ## @brief 供验收举证读取当前 worker 列表
    #  @return 当前采集线程列表
    def getWorkers(self) -> list[CaptureWorker]:
        return list(self._workers)

    ## @brief 供验收举证读取采集中状态
    #  @return 正在采集返回 True
    def isCapturing(self) -> bool:
        return self._capturing

    ## @brief 新建本轮全部采集线程实例
    #  @return 采集线程列表
    def _buildWorkers(self) -> list[CaptureWorker]:
        workers: list[CaptureWorker] = []
        for index, (camera1, camera2) in enumerate(self._cameraPairs):
            workerId = index + 1
            workers.append(CaptureWorker(
                workerId, camera1, camera2, self._saveDirs[index], self._logger,
                self.onWorkerSuccess, self.onWorkerError,
                self._rollThreshold, self._usageRatio, self._clock,
            ))
        return workers
