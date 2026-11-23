"""USB 采集门面：初始化校验、并发拉起采集线程、对焦控制与相机状态查询。"""
from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import Event, Lock

from edge.base.base_service import BaseService
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import ICameraDevice
from edge.interfaces.i_camera_focus import ICameraFocus
from edge.interfaces.i_frame_sink import IFrameSink
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import ICaptureSink
from edge.modules.usb.usb_camera_probe_thread import (
    DEFAULT_PROBE_INTERVAL_SEC,
    CameraProbeThread,
)
from edge.modules.usb.usb_capture_worker import (
    DEFAULT_CAPTURE_INTERVAL_SEC,
    DEFAULT_REOPEN_INTERVAL_SEC,
    CaptureWorker,
)

## @file edge/modules/usb/usb_controller.py
## @brief USB 采集门面：初始化校验、并发拉起采集线程、对焦控制与相机状态查询
## @author 袁燕

## @brief 日志模块名
MODULE_NAME = "UsbController"
## @brief 自动对焦模式：设备自行对焦
FOCUS_MODE_AUTO: str = "auto"
## @brief 手动定焦模式：设备锁定到指定焦点位置
FOCUS_MODE_FIXED: str = "fixed"
## @brief 默认相机路数，整柜 8 路
DEFAULT_CAMERA_COUNT: int = 8
## @brief 相机状态：正常
CAMERA_STATUS_OK: str = "ok"
## @brief 相机状态：不可用，设备缺失、从未成功打开或取图失败
CAMERA_STATUS_OFFLINE: str = "offline"


## @brief USB 采集门面；采集指令唯一下发出口，只依赖 i_sinks.py 回调契约
class UsbController(BaseService):
    ## @brief 构造门面
    #  @param cameraPairs 每个 worker 挂载的相机组，单摄 1 路、双摄 2 路（注入）
    #  @param saveDirs 每个 worker 的专属存储目录（注入）
    #  @param sink 采集事件回调（注入）
    #  @param logger 可选日志器
    #  @param rollThreshold 占用比例阈值（构造注入）
    #  @param usageRatio 占用比例提供器（注入）
    #  @param clock 文件名时间戳提供器（注入）
    #  @param focusMode 对焦模式，auto 或 fixed（构造注入）
    #  @param focusPosition 旧单值焦点位置，仅兼容用；新装配用 focusPositions
    #  @param focusPositions 逐路焦点位置，下标 = 物理路号 - 1（构造注入）
    #  @param zoomPositions 逐路变焦位置，下标 = 物理路号 - 1（构造注入）
    #  @param focusStableMs 定焦后镜头稳定等待毫秒数（构造注入）
    #  @param frameSink 帧流回调（注入，为空表示只落盘）
    #  @param cameraCount 相机路数（构造注入）
    #  @param captureIntervalSec 两轮取帧之间的等待秒数（构造注入）
    #  @param reopenIntervalSec 未就绪相机再次尝试打开的最短间隔秒数（构造注入）
    #  @param probeIntervalSec 摄像头巡检周期秒数（构造注入）
    #  @return 无
    def __init__(self, cameraPairs: Sequence[tuple[ICameraDevice, ...]],
                 saveDirs: list[str], sink: ICaptureSink, logger: ILogger | None,
                 rollThreshold: float, usageRatio: Callable[[], float],
                 clock: Callable[[], str],
                 focusMode: str = FOCUS_MODE_AUTO,
                 focusPosition: float = 0.0,
                 focusPositions: Sequence[float] = (),
                 zoomPositions: Sequence[float] = (),
                 focusStableMs: int = 0,
                 frameSink: IFrameSink | None = None,
                 cameraCount: int = DEFAULT_CAMERA_COUNT,
                 captureIntervalSec: float = DEFAULT_CAPTURE_INTERVAL_SEC,
                 reopenIntervalSec: float = DEFAULT_REOPEN_INTERVAL_SEC,
                 probeIntervalSec: float = DEFAULT_PROBE_INTERVAL_SEC) -> None:
        ## @brief 设备组，单摄 1 路、双摄 2 路，也支持多路（任意长度元组）
        self._cameraPairs: Sequence[tuple[ICameraDevice, ...]] = cameraPairs
        ## @brief 按物理编号顺序排列：先各组第 1 路，再各组第 2 路、第 3 路…，保持整柜编号口径；
        #        旧实现只取前 2 路会静默丢弃第 3 路及以后的相机，这里按列展开避免丢路
        columnCount = max((len(pair) for pair in cameraPairs), default=0)
        orderedDevices: list[ICameraDevice] = []
        for column in range(columnCount):
            for pair in cameraPairs:
                if column < len(pair):
                    orderedDevices.append(pair[column])
        self._cameraDevices: list[ICameraDevice] = orderedDevices
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
        ## @brief 对焦模式
        self._focusMode: str = focusMode
        ## @brief 逐路焦点位置，下标 = 物理路号 - 1；空则用旧单值广播
        self._focusPositions: list[float] = (
            list(focusPositions) if focusPositions else [focusPosition] * len(self._cameraDevices)
        )
        ## @brief 逐路变焦位置，下标 = 物理路号 - 1；空则全 0
        self._zoomPositions: list[float] = (
            list(zoomPositions) if zoomPositions else [0.0] * len(self._cameraDevices)
        )
        ## @brief 定焦后镜头稳定等待毫秒数
        self._focusStableMs: int = focusStableMs
        ## @brief 帧流回调
        self._frameSink: IFrameSink | None = frameSink
        ## @brief 相机路数
        self._cameraCount: int = cameraCount
        ## @brief 两轮取帧之间的等待秒数
        self._captureIntervalSec: float = captureIntervalSec
        ## @brief 未就绪相机再次尝试打开的最短间隔秒数
        self._reopenIntervalSec: float = reopenIntervalSec
        ## @brief 是否已初始化
        self._inited: bool = False
        ## @brief 是否正在采集
        self._capturing: bool = False
        ## @brief 巡检是否正在停机；置位后巡检跳过探测，避免停机窗口误启动
        self._probeStopping: bool = False
        ## @brief 并发启停锁
        self._captureLock: Lock = Lock()
        ## @brief 当前采集线程实例（每次拉起新建）
        self._workers: list[CaptureWorker] = []
        ## @brief 已回报就绪的采集线程编号，用于凑齐全部线程后统一下发对焦
        self._readyWorkerIds: set[int] = set()
        ## @brief 对焦下发状态与就绪集合的锁
        self._focusLock: Lock = Lock()
        ## @brief 本轮是否已下发过对焦，保证一轮采集只下发一次
        self._focusDispatched: bool = False
        ## @brief 开机探测失败的相机地址，供启动摘要如实告知哪几路没在位
        self._unreachableAddresses: list[str] = []
        ## @brief 逐路定焦完成事件，下标 = 物理路号 - 1；worker 取首帧前等本组两路都置位。
        #        定焦成功或失败都会置位（失败不阻塞采集），避免屏障永久等待
        self._focusDoneEvents: list[Event] = [Event() for _ in self._cameraDevices]
        ## @brief 两轮巡检之间的等待秒数
        self._probeIntervalSec: float = probeIntervalSec
        ## @brief 巡检下一路的下标，逐路错峰
        self._probeNextIndex: int = 0
        ## @brief 摄像头巡检线程；探测与采集启停共用同一把锁，避免并发操作设备
        self._probeThread: CameraProbeThread = CameraProbeThread(
            len(self._cameraDevices), self._probeIfIdle, logger, probeIntervalSec,
        )

    ## @brief 初始化：校验目录存在且可写、对焦模式合法，Fail-Fast 不引入能力降级
    #  @return 无
    #  @raises EdgeError 配置不完整、目录不可写或对焦模式非法时抛出，code=CONFIG
    def init(self) -> None:
        ## 单摄 1 组 1 目录、双摄 4 组 4 目录都合法；多配的目录忽略，不因此判残缺
        if not self._cameraPairs or len(self._saveDirs) < len(self._cameraPairs):
            raise EdgeError(ErrorCode.CONFIG, "USB 采集配置不完整")
        for saveDir in self._saveDirs[:len(self._cameraPairs)]:
            ## 空目录表示关闭落盘：只走内存帧回调，不要求目录存在
            if not saveDir:
                continue
            path = Path(saveDir)
            if not path.is_dir() or not os.access(str(path), os.W_OK):
                raise EdgeError(ErrorCode.CONFIG, f"USB 采集目录不可写: {saveDir}")
        if self._focusMode not in (FOCUS_MODE_AUTO, FOCUS_MODE_FIXED):
            raise EdgeError(ErrorCode.CONFIG, f"对焦模式非法: {self._focusMode}")
        self._inited = True
        self.probeCameraDevices()
        ## 启动后巡检常驻，采集在跑时由线程自行跳过，空闲时兜底探测设备可用性
        self._probeThread.start()
        if self._logger is not None:
            message = f"USB 初始化完成, 配置 {len(self._saveDirs)} 个 Worker"
            self._logger.info(MODULE_NAME, message)

    ## @brief 开机探测各路相机可达性；只探测不报错，探测结果由相机状态查询体现
    #  @return 无
    def probeCameraDevices(self) -> None:
        unreachable: list[str] = []
        for position, device in enumerate(self._cameraDevices):
            address = self._deviceAddress(position, device)
            try:
                device.open()
            except Exception as error:
                ## 探测失败不中断启动，该路在相机状态里按离线体现
                unreachable.append(address)
                if self._logger is not None:
                    message = f"相机打开失败 索引 {address}: {error}"
                    self._logger.error(MODULE_NAME, message, exception=error)
            finally:
                ## 打开动作只要碰过设备，无论成败都要关一次，别把采集句柄留在手上
                self._closeProbedDevice(device, address)
        with self._focusLock:
            self._unreachableAddresses = unreachable

    ## @brief 确保巡检线程处于可运行状态；停机后再次采集时重建实例（线程不可重启）
    #  @return 无
    #  @note 须在 _captureLock 内调用；新建实例后由调用方在锁外 start
    def _ensureProbeRunning(self) -> None:
        if not self._probeStopping:
            return
        self._probeStopping = False
        self._probeNextIndex = 0
        self._probeThread = CameraProbeThread(
            len(self._cameraDevices), self._probeIfIdle, self._logger,
            self._probeIntervalSec,
        )

    ## @brief 采集空闲时巡检一路；检查与探测在同一把锁内完成，避免与采集启停竞态
    #  @return 无
    #  @note 持 _captureLock 覆盖"检查 _capturing → 探测 → 关句柄"全过程：
    #        采集启停也持同一把锁，巡检飞行中采集无法启动，不会释放 worker 刚开的句柄
    def _probeIfIdle(self) -> None:
        with self._captureLock:
            if self._capturing or self._probeStopping or not self._cameraDevices:
                return
            index = self._probeNextIndex
            self._probeNextIndex = (index + 1) % len(self._cameraDevices)
            self._probeCamera(index)

    ## @brief 巡检单路：打开、取一帧确认在位、随后关闭；失败按通信异常处理
    #  @param index 物理路号减一
    #  @return 无
    def _probeCamera(self, index: int) -> None:
        if index < 0 or index >= len(self._cameraDevices):
            return
        device = self._cameraDevices[index]
        address = self._deviceAddress(index, device)
        try:
            device.open()
            ## readFrame 内部已按成功帧更新通信状态，这里不再重复标记，避免计数虚增
            device.readFrame()
        except Exception as error:
            marker = getattr(device, "markCommFailed", None)
            if callable(marker):
                marker()
            if self._logger is not None:
                self._logger.error(
                    MODULE_NAME, f"相机巡检失败 索引 {address}: {error}",
                )
        finally:
            self._closeProbedDevice(device, address)

    ## @brief 关掉探测用的设备；关闭失败只记日志，不把收尾问题当成探测失败
    #  @param device 摄像头设备
    #  @param address 设备地址，用于日志定位
    #  @return 无
    def _closeProbedDevice(self, device: ICameraDevice, address: str) -> None:
        try:
            device.close()
        except Exception as error:
            if self._logger is not None:
                self._logger.error(
                    MODULE_NAME,
                    f"相机探测后关闭失败 索引 {address}: {error}",
                    exception=error,
                )

    ## @brief 开机探测失败的相机地址；供启动摘要告知现场哪几路没在位
    #  @return 探测失败的相机地址列表
    def getUnreachableAddresses(self) -> list[str]:
        with self._focusLock:
            return list(self._unreachableAddresses)

    ## @brief 生命周期启动；前置校验在 startCapture 内完成
    #  @return 无
    def start(self) -> None:
        self.startCapture()

    ## @brief 生命周期停止
    #  @return 无
    def stop(self) -> None:
        self.stopCapture()

    ## @brief 前置校验后并发拉起全部 worker 并立即返回，不等待子线程
    #  @param requestId 上位机请求标识，透传给采集线程的帧回调
    #  @return 拉起成功返回 True
    #  @raises EdgeError 未初始化或已在采集中时抛出，code=CONFIG
    def startCapture(self, requestId: str = "") -> bool:
        with self._captureLock:
            if not self._inited or self._capturing:
                raise EdgeError(ErrorCode.CONFIG, "USB 未初始化或已在采集中")
            ## 每次拉起新建实例，绕开 BaseThread.start 同一实例只启动一次的限制
            workers = self._buildWorkers(requestId)
            self._workers = workers
            self._capturing = True
            self.resetFocusDispatch()
            self._ensureProbeRunning()
        self._probeThread.start()
        for worker in workers:
            worker.start()
        if self._logger is not None:
            message = f"已拉起 {len(workers)} 个采集线程"
            self._logger.info(MODULE_NAME, message)
        return True

    ## @brief 中断全部采集线程并清空实例，允许下一轮重新拉起
    #  @return 无
    def stopCapture(self) -> None:
        with self._captureLock:
            ## 先在锁内置停机标志与采集标志：巡检下次检查即跳过；
            #  不能在持锁时 join 巡检，否则巡检等锁会死锁
            self._probeStopping = True
            workers = list(self._workers)
            self._workers = []
            self._capturing = False
        self._probeThread.stop()
        for worker in workers:
            worker.stop()

    ## @brief 开始一次全柜扫描：未在采集时拉起采集线程，已在采集时给在跑线程换请求标识
    #  @param requestId 上位机请求标识
    #  @return 触发成功返回 True
    #  @raises EdgeError 未初始化时抛出，code=CONFIG
    def beginScan(self, requestId: str) -> bool:
        switched: bool = False
        workers: list[CaptureWorker] = []
        with self._captureLock:
            if not self._inited:
                raise EdgeError(ErrorCode.CONFIG, "USB 未初始化")
            if not self._capturing:
                workers = self._buildWorkers(requestId)
                self._workers = workers
                self._capturing = True
                self.resetFocusDispatch()
                self._ensureProbeRunning()
            else:
                ## 已在采集：给在跑的采集线程换请求标识，下一轮帧就归属新请求
                for worker in self._workers:
                    worker.setRequestId(requestId)
                switched = True
        if switched:
            if self._logger is not None:
                message = f"采集已在运行, 切换到请求 {requestId}"
                self._logger.info(MODULE_NAME, message)
            return True
        self._probeThread.start()
        for worker in workers:
            worker.start()
        if self._logger is not None:
            message = f"已拉起 {len(workers)} 个采集线程"
            self._logger.info(MODULE_NAME, message)
        return True

    ## @brief 按物理路号下标取逐路值，越界返回 0
    #  @param values 逐路值列表
    #  @param position 物理路号减一
    #  @return 该路取值
    @staticmethod
    def _valueAt(values: list[float], position: int) -> float:
        return values[position] if position < len(values) else 0.0

    ## @brief 给每路设备下发对焦与变焦指令；失败按路收集，最后只记一条汇总日志
    #  @return 无
    def applyFixedFocus(self) -> None:
        notOpened: list[str] = []
        failures: list[str] = []
        try:
            for position, device in enumerate(self._cameraDevices):
                try:
                    address = self._deviceAddress(position, device)
                    if not bool(device.getStatus().get("opened", False)):
                        ## 相机没打开就下对焦必然失败，如实记未生效，不去另开采集句柄
                        notOpened.append(address)
                        continue
                    ## position 即物理路号 - 1，逐路取本路值，不能按 worker 内下标取
                    focusValue = self._valueAt(self._focusPositions, position)
                    zoomValue = self._valueAt(self._zoomPositions, position)
                    failure = self._applyFocusToDevice(device, address, focusValue, zoomValue)
                    if failure is not None:
                        failures.append(failure)
                except Exception as error:
                    ## 单路出现未预期异常（如驱动 cv2.error）也只记一条失败说明，
                    #  不外抛、不打断其余路，避免屏障漏置位导致 worker 永久等待
                    failures.append(f"第{position + 1}路对焦异常: {error}")
        finally:
            ## 兜底：无条件置位全部路屏障。正常逐路已置位，这里保证任何中途异常
            #  都不会留下未放行的 worker（SR_FOCUS_07，消除条件性永久阻塞）
            for event in self._focusDoneEvents:
                event.set()
        self.reportFocusOutcome(notOpened, failures)

    ## @brief 运行期切换对焦模式并立即生效
    #  @param mode 对焦模式，auto 或 fixed
    #  @return 无
    #  @raises EdgeError 模式取值非法时抛出，code=CONFIG
    def setFocusMode(self, mode: str) -> None:
        if mode not in (FOCUS_MODE_AUTO, FOCUS_MODE_FIXED):
            raise EdgeError(ErrorCode.CONFIG, f"对焦模式非法: {mode}")
        self._focusMode = mode
        self.applyFixedFocus()

    ## @brief 采集线程的相机就绪回调；全部线程就绪后统一下发对焦并汇总一条日志
    #  @param workerId 线程编号
    #  @return 无
    def onWorkerDevicesReady(self, workerId: int) -> None:
        with self._focusLock:
            self._readyWorkerIds.add(workerId)
            if len(self._readyWorkerIds) < len(self._cameraPairs):
                return
            if self._focusDispatched:
                return
            self._focusDispatched = True
        ## 全部相机都开过一轮，这时才下发对焦，保证指令落在真正打开着的设备上
        self.applyFixedFocus()

    ## @brief 组一个"本组各路定焦是否都已完成"的屏障闭包，注入给采集线程
    #  @param workerId 线程编号，从 1 开始
    #  @return 屏障闭包；采集线程取首帧前调用，全部本路事件置位才返回 True
    #  @note worker W 持有 CAM{W} 与 CAM{W+4}，对应全局下标 W-1 与 W+3；
    #        按 cameraPairs 的成员逐个取事件，与 worker 实际挂载的相机严格一致
    def waitGroupFocusApplied(self, workerId: int) -> Callable[[], bool]:
        pair = self._cameraPairs[workerId - 1] if 0 < workerId <= len(self._cameraPairs) else ()
        positions = [self._cameraDevices.index(device) for device in pair
                     if device in self._cameraDevices]

        def gate() -> bool:
            return all(self._focusDoneEvents[p].is_set() for p in positions)
        return gate

    ## @brief 查询相机状态，供周期帧使用；只报实际装配的路数，不虚报不存在的路
    #  @return 相机状态列表，每项含 camera_id 与 status
    #  @note 路数取「配置声明路数」与「实际设备数」的较小值：单摄只报 CAM1，
    #        8 路整柜仍报 CAM1..CAM8；状态一律按设备真实快照判定，不为了放行而报 ok
    def getCameraStatus(self) -> list[dict[str, object]]:
        count = min(self._cameraCount, len(self._cameraDevices))
        statuses: list[dict[str, object]] = []
        for index in range(count):
            device: ICameraDevice | None = self._cameraDevices[index]
            item: dict[str, object] = {
                "camera_id": f"CAM{index + 1}",
                "status": self._resolveCameraStatus(device),
            }
            statuses.append(item)
        return statuses

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
    #  @param requestId 上位机请求标识，透传给采集线程
    #  @return 采集线程列表
    def _buildWorkers(self, requestId: str) -> list[CaptureWorker]:
        workers: list[CaptureWorker] = []
        for index, cameras in enumerate(self._cameraPairs):
            workerId = index + 1
            workers.append(CaptureWorker(
                workerId, tuple(cameras), self._saveDirs[index], self._logger,
                self.onWorkerSuccess, self.onWorkerError,
                self._rollThreshold, self._usageRatio, self._clock,
                requestId, self._frameSink, self._captureIntervalSec,
                self.onWorkerDevicesReady, focusStableMs=self._focusStableMs,
                focusGate=self.waitGroupFocusApplied(workerId),
                reopenIntervalSec=self._reopenIntervalSec,
            ))
        return workers

    ## @brief 取设备的对焦能力；设备未实现对焦契约时按配置错误上报
    #  @param device 摄像头设备
    #  @return 对焦能力对象
    #  @raises EdgeError 设备未实现对焦契约时抛出，code=CONFIG
    def _focusCapable(self, device: ICameraDevice) -> ICameraFocus:
        if not isinstance(device, ICameraFocus):
            raise EdgeError(ErrorCode.CONFIG, "摄像头设备不支持对焦")
        return device

    ## @brief 给单路已打开的设备下发对焦与变焦指令
    #  @param device 摄像头设备
    #  @param address 设备地址，用于日志定位
    #  @param focusValue 本路焦点位置
    #  @param zoomValue 本路变焦位置
    #  @return 失败原因文本；下发成功返回 None
    def _applyFocusToDevice(self, device: ICameraDevice, address: str,
                            focusValue: float, zoomValue: float) -> str | None:
        try:
            focus = self._focusCapable(device)
            if self._focusMode == FOCUS_MODE_FIXED:
                ## 先关自动对焦再设位置，否则设好的焦点会被自动对焦覆盖
                focus.setAutoFocus(False)
                focus.setFocusPosition(focusValue)
                focus.setZoomPosition(zoomValue)
            else:
                focus.setAutoFocus(True)
        except NotImplementedError as error:
            ## 骨架异常在模块内转成业务异常，不跨模块边界，也不打断采集
            businessError = EdgeError(ErrorCode.CAPTURE, f"对焦能力待上板实现: {error}")
            return f"相机索引 {address} {businessError}"
        except EdgeError as error:
            return f"相机索引 {address} {error}"
        return None

    ## @brief 记一条对焦汇总日志；成功与失败各只记一条，不逐路刷屏
    #  @param notOpened 未打开因而没下发对焦的相机地址列表
    #  @param failures 下发失败的说明列表
    #  @return 无
    def reportFocusOutcome(self, notOpened: list[str], failures: list[str]) -> None:
        if self._logger is None:
            return
        count = len(self._cameraDevices)
        if not notOpened and not failures:
            message = f"{count} 路相机对焦已下发，模式 {self._focusMode}"
            self._logger.info(MODULE_NAME, message)
            return
        reasons: list[str] = []
        if notOpened:
            reasons.append(f"相机索引 {'、'.join(notOpened)} 未打开")
        reasons.extend(failures)
        message = f"{count} 路相机对焦未生效：{'；'.join(reasons)}"
        ## 定焦失败不中断采集、不记为采集失败事件，按裁决只记 info 说明日志
        self._logger.info(MODULE_NAME, message)

    ## @brief 取设备的显示地址；设备自带地址就用地址，没有就用整柜顺序号占位
    #  @param position 设备在整柜里的顺序号
    #  @param device 摄像头设备
    #  @return 设备地址文本
    def _deviceAddress(self, position: int, device: ICameraDevice) -> str:
        address = str(device.getStatus().get("deviceAddr", ""))
        if address:
            return address
        return f"第{position + 1}路"

    ## @brief 清空本轮的就绪集合与对焦下发标记，供下一轮采集重新判定
    #  @return 无
    def resetFocusDispatch(self) -> None:
        with self._focusLock:
            self._readyWorkerIds = set()
            self._focusDispatched = False
            ## 本轮定焦屏障全部复位，等这一轮 applyFixedFocus 逐路重新置位
            for event in self._focusDoneEvents:
                event.clear()

    ## @brief 由设备状态快照推导相机状态；只有真正可用的设备才报正常
    #  @param device 摄像头设备，缺失时按离线处理
    #  @return 状态取值，只有正常、离线两种
    #  @note 取图失败、从未成功打开、设备缺失一律归离线；
    #        离线即不可用，上位机据此拒绝开柜，不会放行一个没有图像的相机
    def _resolveCameraStatus(self, device: ICameraDevice | None) -> str:
        if device is None:
            ## 没有对应设备就是离线，不许报正常
            return CAMERA_STATUS_OFFLINE
        status = device.getStatus()
        if not bool(status.get("commOk", True)):
            ## 取图失败过按不可用处理，归并到离线
            return CAMERA_STATUS_OFFLINE
        everOpened = bool(status.get("everOpened", status.get("opened", False)))
        if not everOpened:
            ## 从未成功打开过的设备一律离线，不许报正常
            return CAMERA_STATUS_OFFLINE
        return CAMERA_STATUS_OK
