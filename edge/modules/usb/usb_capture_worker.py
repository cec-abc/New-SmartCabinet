"""USB 采集线程：循环取帧、帧流回调、落盘滚动删旧与成功/失败回调。"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import monotonic

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import FrameImage, ICameraDevice
from edge.interfaces.i_frame_sink import IFrameSink
from edge.interfaces.i_logger import ILogger

## @file edge/modules/usb/usb_capture_worker.py
## @brief USB 采集线程：循环取帧、帧流回调、落盘滚动删旧与成功/失败回调
## @author 袁燕

## @brief 日志模块名
MODULE_NAME = "UsbCaptureWorker"
## @brief 默认采集间隔秒数，两轮取帧之间的等待时长
DEFAULT_CAPTURE_INTERVAL_SEC: float = 0.1
## @brief 默认重开间隔秒数，未就绪相机再次尝试打开的最短间隔
DEFAULT_REOPEN_INTERVAL_SEC: float = 2.0
## @brief 等待定焦屏障时的轮询间隔秒数，短间隔保证定焦完成后能立刻取帧
FOCUS_GATE_POLL_SEC: float = 0.01
## @brief 取图为空的日志间隔次数，累计到该倍数才记一条日志
EMPTY_FRAME_LOG_INTERVAL: int = 10
## @brief 连续取图为空达到该次数就判定该路异常并上报失败
EMPTY_FRAME_ERROR_THRESHOLD: int = 30
## @brief 单摄模式一组只有一路相机，帧元组长度为 1
SINGLE_CAMERA_FRAME_COUNT: int = 1
## @brief 单摄落盘文件名里的方位标记
SINGLE_FRAME_LABEL: str = "single"
## @brief 双摄左路落盘文件名里的方位标记
LEFT_FRAME_LABEL: str = "left"
## @brief 双摄右路落盘文件名里的方位标记
RIGHT_FRAME_LABEL: str = "right"
## @brief 落盘帧文件的后缀
FRAME_FILE_EXTENSION: str = ".jpg"
## @brief 滚动删旧时扫描的文件名模式
FRAME_GLOB_PATTERN: str = "*.jpg"

## @brief 相机就绪回调；参数为线程编号
DevicesReadyCallback = Callable[[int], None]


## @brief 采集线程；循环取帧直到收到停止指令，异常只影响本线程
class CaptureWorker(BaseThread):
    ## @brief 构造采集线程
    #  @param workerId 线程编号
    #  @param cameras 本线程挂载的相机组，单摄 1 路、双摄 2 路（左前右后）
    #  @param saveDir 专属存储目录（注入，留空表示只回调不落盘）
    #  @param logger 可选日志器
    #  @param onSuccess 成功回调，只做轻量上抛
    #  @param onError 失败回调，只做轻量上抛
    #  @param rollThreshold 占用比例阈值（构造注入，超阈值删旧）
    #  @param usageRatio 占用比例提供器（注入，便于确定性举证）
    #  @param clock 文件名时间戳提供器（注入）
    #  @param requestId 上位机请求标识，回调帧时原样带给下游
    #  @param frameSink 帧流回调（注入，为空表示只落盘）
    #  @param captureIntervalSec 两轮取帧之间的等待秒数（构造注入）
    #  @param onDevicesReady 相机就绪回调（注入，为空表示不回报就绪）
    #  @param focusStableMs 定焦后镜头稳定等待毫秒数
    #  @param focusGate 首帧定焦屏障（注入）；返回 True 表示本组各路定焦指令已下发完毕。
    #         worker 在稳定等待与首帧之前先等它，避免先就绪的线程在别人尚未定焦时抓到糊帧
    #  @param reopenIntervalSec 未就绪相机再次尝试打开的最短间隔秒数（构造注入）
    #  @param nowSec 单调时钟秒提供器（注入，便于确定性举证节流间隔）
    #  @return 无
    def __init__(self, workerId: int, cameras: tuple[ICameraDevice, ...],
                 saveDir: str, logger: ILogger | None,
                 onSuccess: Callable[[int, str], None],
                 onError: Callable[[int, Exception], None],
                 rollThreshold: float, usageRatio: Callable[[], float],
                 clock: Callable[[], str],
                 requestId: str = "", frameSink: IFrameSink | None = None,
                 captureIntervalSec: float = DEFAULT_CAPTURE_INTERVAL_SEC,
                 onDevicesReady: DevicesReadyCallback | None = None,
                 focusStableMs: int = 0,
                 focusGate: Callable[[], bool] | None = None,
                 reopenIntervalSec: float = DEFAULT_REOPEN_INTERVAL_SEC,
                 nowSec: Callable[[], float] | None = None) -> None:
        super().__init__(name=f"UsbCaptureWorker-{workerId}", logger=logger)
        ## @brief 线程编号
        self._workerId: int = workerId
        ## @brief 本线程挂载的相机组，单摄 1 路、双摄 2 路
        self._cameras: tuple[ICameraDevice, ...] = cameras
        ## @brief 专属存储目录
        self._saveDir: Path = Path(saveDir)
        ## @brief 是否落盘
        self._saveEnabled: bool = bool(saveDir)
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief 成功回调
        self._onSuccess: Callable[[int, str], None] = onSuccess
        ## @brief 失败回调
        self._onError: Callable[[int, Exception], None] = onError
        ## @brief 占用比例阈值
        self._rollThreshold: float = rollThreshold
        ## @brief 占用比例提供器
        self._usageRatio: Callable[[], float] = usageRatio
        ## @brief 时间戳提供器
        self._clock: Callable[[], str] = clock
        ## @brief 上位机请求标识
        self._requestId: str = requestId
        ## @brief 帧流回调
        self._frameSink: IFrameSink | None = frameSink
        ## @brief 两轮取帧之间的等待秒数
        self._captureIntervalSec: float = captureIntervalSec
        ## @brief 本轮落盘文件，滚动删旧时跳过，避免误删刚采集的帧；每轮开始清空
        self._currentFiles: set[Path] = set()
        ## @brief 本轮清理的旧文件数，供验收举证与现场排查按名读取，不参与业务判定
        self.removedCount: int = 0
        ## @brief 取图为空的累计次数，供验收举证
        self.emptyFrameCount: int = 0
        ## @brief 成功回调是否已上报，每轮采集只上报一次
        self._successReported: bool = False
        ## @brief 相机就绪回调
        self._onDevicesReady: DevicesReadyCallback | None = onDevicesReady
        ## @brief 定焦后镜头稳定等待毫秒数，0 表示不额外等待
        self._focusStableMs: int = focusStableMs
        ## @brief 首帧定焦屏障，为空表示不等待（无对焦能力的场景）
        self._focusGate: Callable[[], bool] | None = focusGate
        ## @brief 未就绪相机再次尝试打开的最短间隔秒数
        self._reopenIntervalSec: float = reopenIntervalSec
        ## @brief 单调时钟秒提供器，默认取系统单调时钟
        self._nowSec: Callable[[], float] = nowSec if nowSec is not None else monotonic
        ## @brief 各路上次尝试重开的时间戳，下标 = 相机在本组中的序号
        self._lastReopenAt: list[float] = [0.0] * len(cameras)

    ## @brief 线程主流程：开本组相机、等定焦完成、等镜头稳定、循环取帧、关本组相机
    #  @return 无
    def runLoop(self) -> None:
        try:
            self.openCameras()
            ## 先等本组各路定焦指令下发完毕：定焦由 controller 集中下发，
            #  屏障保证先就绪的线程不会在别人尚未定焦时抓首帧（SR_FOCUS_07）
            if not self.waitFocusApplied():
                return
            ## 定焦落地后再等镜头稳定取首帧；毫秒转秒交给可打断等待，停机立即返回
            if self._focusStableMs > 0 and not self.interruptibleWait(
                    self._focusStableMs / 1000.0):
                return
            self._captureStream()
        except EdgeError as error:
            self.reportError(error)
        except Exception as error:
            ## 内置异常跨线程边界前统一转业务异常
            self.reportError(EdgeError(ErrorCode.CAPTURE, f"采集异常: {error}"))
        finally:
            self._markCamerasCommFailed()
            self._closeCameras()

    ## @brief 线程退出时把本组相机标记为通信失败，避免线程已死状态还报 ok
    #  @return 无
    #  @note 用鸭子类型调用设备能力，Fake 设备未实现时跳过，不扩 L1 接口契约
    def _markCamerasCommFailed(self) -> None:
        for camera in self._cameras:
            marker = getattr(camera, "markCommFailed", None)
            if callable(marker):
                try:
                    marker()
                except Exception:
                    ## 单路标记失败不挡住其余路与后续句柄释放
                    pass

    ## @brief 逐路关掉本组相机；某一路关闭报错不挡住其它路，句柄一个都不留在手上
    #  @return 无
    #  @note 关闭动作放在主流程的 finally 里，循环退出、取帧异常、停机都一定会走到；
    #        这里再逐路包住异常，避免第一路驱动报错导致后面几路的句柄没释放
    def _closeCameras(self) -> None:
        firstError: Exception | None = None
        for camera in self._cameras:
            try:
                camera.close()
            except Exception as error:
                if firstError is None:
                    firstError = error
        if firstError is None:
            return
        ## 关闭异常只记日志，不再上抛失败事件，避免收尾问题被当成一轮采集失败
        self._logError(EdgeError(ErrorCode.CAPTURE, f"关闭相机异常: {firstError}"))

    ## @brief 打开本线程挂载的全部相机；单路失败只跳过该路，不阻断同组其余路
    #  @return 无
    def openCameras(self) -> None:
        try:
            for camera in self._cameras:
                try:
                    camera.open()
                except EdgeError:
                    ## 该路暂不可用，留到采集循环里按间隔重试；不能带死整组线程
                    pass
        finally:
            self.reportDevicesReady()

    ## @brief 对未就绪的路按间隔重试打开，让运行中接入的相机能自动恢复
    #  @return 无
    #  @note 用注入的单调时钟做节流，避免每轮取帧都触发驱动 open 造成日志刷屏
    def retryClosedCameras(self) -> None:
        now = self._nowSec()
        for index, camera in enumerate(self._cameras):
            if bool(camera.getStatus().get("opened", False)):
                continue
            if now - self._lastReopenAt[index] < self._reopenIntervalSec:
                continue
            self._lastReopenAt[index] = now
            try:
                camera.open()
            except EdgeError:
                ## 仍未接入或打开失败，标记该路不可用后等下个间隔再试，不影响其余路
                marker = getattr(camera, "markCommFailed", None)
                if callable(marker):
                    try:
                        marker()
                    except Exception:
                        ## 单路标记失败不影响其余路与本轮取帧
                        pass

    ## @brief 回报本线程的相机就绪；上层据此在全部线程就绪后统一下发对焦
    #  @return 无
    def reportDevicesReady(self) -> None:
        if self._onDevicesReady is None:
            return
        self._onDevicesReady(self._workerId)

    ## @brief 等本组定焦屏障放行；屏障为空或已放行立即返回 True，停机返回 False
    #  @return 屏障放行返回 True；停机中断返回 False
    #  @note 轮询用短时可打断等待，既让出 CPU 又能响应停机；定焦由 controller 集中下发，
    #        它对本组每一路下发完成（成功或失败）后置位，故这里不会永久阻塞
    def waitFocusApplied(self) -> bool:
        if self._focusGate is None:
            return True
        while not self._focusGate():
            if self.stopEvent.is_set():
                return False
            if not self.interruptibleWait(FOCUS_GATE_POLL_SEC):
                return False
        return True

    ## @brief 抓一轮帧；单摄返回长度 1，双摄返回长度 2（左前右后）
    #  @return 本轮帧元组；任一路为空返回 None
    def captureOnce(self) -> tuple[bytes, ...] | None:
        frames: list[FrameImage] = []
        for camera in self._cameras:
            ## 未就绪的路直接跳过，不依赖各设备 readFrame 是否自检 opened；
            ## 空帧计数统一由下方 len(frames) 判断按“轮”累加
            if not bool(camera.getStatus().get("opened", False)):
                continue
            try:
                frame = camera.readFrame()
            except EdgeError:
                ## 单路取帧失败只跳过该路，异常冒泡会杀死线程导致再也无人取帧；
                ## 空帧计数统一由下方 len(frames) 判断按“轮”累加，避免此处重复计数翻倍
                continue
            if frame is not None:
                frames.append(frame)
        if len(frames) != len(self._cameras):
            self._countEmptyFrame()
            return None
        ## 取到帧说明该路恢复，空帧计数归零
        self.emptyFrameCount = 0
        return tuple(frames)

    ## @brief 切换本线程服务的请求标识；上位机换一轮扫描时由采集门面下发
    #  @param requestId 上位机请求标识
    #  @return 无
    def setRequestId(self, requestId: str) -> None:
        self._requestId = requestId

    ## @brief 本轮帧落盘：单摄只写一张，双摄左右各写一张（文件名保持不变）
    #  @param frames 本轮帧元组，单摄 1 帧、双摄左前右后 2 帧
    #  @param stamp 文件名时间戳
    #  @return 无
    #  @raises EdgeError 写盘失败时抛出，code=CAPTURE
    def saveFrames(self, frames: tuple[bytes, ...], stamp: str) -> None:
        if len(frames) == SINGLE_CAMERA_FRAME_COUNT:
            self.saveFrame(frames[0], self._buildFrameName(SINGLE_FRAME_LABEL, stamp))
            return
        self.saveFrame(frames[0], self._buildFrameName(LEFT_FRAME_LABEL, stamp))
        self.saveFrame(frames[1], self._buildFrameName(RIGHT_FRAME_LABEL, stamp))

    ## @brief 拼落盘文件名，双摄沿用 wN_left_stamp.jpg / wN_right_stamp.jpg
    #  @param label 方位标记
    #  @param stamp 文件名时间戳
    #  @return 文件名
    def _buildFrameName(self, label: str, stamp: str) -> str:
        return f"w{self._workerId}_{label}_{stamp}{FRAME_FILE_EXTENSION}"

    ## @brief 单帧写入指定文件
    #  @param frame 图像字节
    #  @param fileName 文件名
    #  @return 落盘路径字符串
    #  @raises EdgeError 写盘失败时抛出，code=CAPTURE
    def saveFrame(self, frame: FrameImage, fileName: str) -> str:
        target = self._saveDir / fileName
        try:
            target.write_bytes(frame)
        except OSError as error:
            ## 内置异常跨模块边界前统一转业务异常
            raise EdgeError(ErrorCode.CAPTURE, f"写盘失败: {fileName}") from error
        self._currentFiles.add(target)
        return str(target)

    ## @brief 占用超阈值时按最旧顺序删图；删后仍超阈值记 error 但不中断
    #  @return 无
    #  @note 多个采集线程可能同时扫同一个目录，文件在排队期间被别的线程删掉是正常现象；
    #        取修改时间和删文件两处都按文件已消失处理，不把并发竞态报成一轮采集失败
    def checkRollStorage(self) -> None:
        if self._usageRatio() <= self._rollThreshold:
            return
        candidates: list[tuple[float, str, Path]] = []
        for path in self._saveDir.glob(FRAME_GLOB_PATTERN):
            if path in self._currentFiles:
                continue
            try:
                modified = path.stat().st_mtime
            except OSError:
                ## 别的线程刚把这个旧文件删走了，跳过即可
                continue
            candidates.append((modified, path.name, path))
        candidates.sort(key=lambda entry: (entry[0], entry[1]))
        for _modified, _name, candidate in candidates:
            if self._usageRatio() <= self._rollThreshold:
                break
            try:
                candidate.unlink()
            except OSError:
                ## 单个旧文件删除失败或已被别的线程删掉，都不影响本轮采集
                continue
            self.removedCount += 1
        if self._usageRatio() > self._rollThreshold:
            self._logError(EdgeError(ErrorCode.CAPTURE, "滚动删除后仍超阈值"))

    ## @brief 成功回调：只上报本次采集目录，不做阻塞 IO
    #  @return 无
    def reportSuccess(self) -> None:
        if self._logger is not None:
            message = f"worker-{self._workerId} 采集完成: {self._saveDir}"
            self._logger.info(MODULE_NAME, message)
        self._onSuccess(self._workerId, str(self._saveDir))

    ## @brief 失败回调：记录异常码后轻量上抛；停机过程中的收尾异常不再上报
    #  @param error 业务异常
    #  @return 无
    def reportError(self, error: EdgeError) -> None:
        if self.stopEvent.is_set():
            ## 停机过程中的收尾异常不再上抛，避免停机期刷失败事件
            return
        self._logError(error)
        self._onError(self._workerId, error)

    ## @brief 采集主循环：每轮取帧并分发，按间隔等待下一轮
    #  @return 无
    def _captureStream(self) -> None:
        while not self.stopEvent.is_set():
            self.retryClosedCameras()
            frames = self.captureOnce()
            if frames is not None:
                self._publishFrames(frames)
            if not self.interruptibleWait(self._captureIntervalSec):
                return

    ## @brief 一轮帧的分发：帧回调在前，落盘与滚动删旧在后，成功回调只报一次
    #  @param frames 本轮帧元组
    #  @return 无
    def _publishFrames(self, frames: tuple[bytes, ...]) -> None:
        if self._frameSink is not None:
            self._frameSink.onFrameCaptured(self._workerId, frames, self._requestId)
        if self._saveEnabled:
            ## 循环流式采集每轮换一批文件，保护集合只留本轮，避免集合无限增长
            self._currentFiles.clear()
            self.saveFrames(frames, self._clock())
            self.checkRollStorage()
        if self._successReported:
            return
        self._successReported = True
        self.reportSuccess()

    ## @brief 取图为空的计数与抽样日志，避免逐轮刷屏
    #  @return 无
    def _countEmptyFrame(self) -> None:
        self.emptyFrameCount += 1
        if self.emptyFrameCount % EMPTY_FRAME_LOG_INTERVAL == 0:
            if self._logger is not None:
                message = f"worker-{self._workerId} 取图为空 累计 {self.emptyFrameCount} 次"
                self._logger.error(MODULE_NAME, message)
        self.reportEmptyFrames()

    ## @brief 连续取图为空达到阈值就上报一次失败，让上层能降级出帧
    #  @return 无
    def reportEmptyFrames(self) -> None:
        if self.emptyFrameCount < EMPTY_FRAME_ERROR_THRESHOLD:
            return
        self.emptyFrameCount = 0
        error = EdgeError(
            ErrorCode.CAPTURE,
            f"连续 {EMPTY_FRAME_ERROR_THRESHOLD} 轮取图为空, 判定该路异常",
        )
        self.reportError(error)

    ## @brief 统一的错误日志出口，异常码使用 code.name
    #  @param error 业务异常
    #  @return 无
    def _logError(self, error: EdgeError) -> None:
        if self._logger is not None:
            message = f"worker-{self._workerId} 采集失败 {error.code.name}"
            self._logger.error(MODULE_NAME, message, exception=error)
