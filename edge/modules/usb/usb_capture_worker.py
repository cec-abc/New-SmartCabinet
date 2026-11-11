"""USB 采集线程：双路取图落盘、滚动删旧与成功/失败回调。"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_camera import FrameImage, ICameraDevice
from edge.interfaces.i_logger import ILogger

## @brief 日志模块名
MODULE_NAME = "UsbCaptureWorker"


## @brief 采集线程；单轮双路取图落盘后静默退出，异常只影响本线程
class CaptureWorker(BaseThread):
    ## @brief 构造采集线程
    #  @param workerId 线程编号
    #  @param camera1 左路设备（注入）
    #  @param camera2 右路设备（注入）
    #  @param saveDir 专属存储目录（注入）
    #  @param logger 可选日志器
    #  @param onSuccess 成功回调，只做轻量上抛
    #  @param onError 失败回调，只做轻量上抛
    #  @param rollThreshold 占用比例阈值（构造注入，超阈值删旧）
    #  @param usageRatio 占用比例提供器（注入，便于确定性举证）
    #  @param clock 文件名时间戳提供器（注入）
    def __init__(self, workerId: int, camera1: ICameraDevice, camera2: ICameraDevice,
                 saveDir: str, logger: ILogger | None,
                 onSuccess: Callable[[int, str], None],
                 onError: Callable[[int, Exception], None],
                 rollThreshold: float, usageRatio: Callable[[], float],
                 clock: Callable[[], str]) -> None:
        super().__init__(name=f"UsbCaptureWorker-{workerId}", logger=logger)
        ## @brief 线程编号
        self._workerId: int = workerId
        ## @brief 左路设备
        self._camera1: ICameraDevice = camera1
        ## @brief 右路设备
        self._camera2: ICameraDevice = camera2
        ## @brief 专属存储目录
        self._saveDir: Path = Path(saveDir)
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
        ## @brief 本轮落盘文件，滚动删旧时跳过，避免误删刚采集的帧
        self._currentFiles: set[Path] = set()
        ## @brief 本轮已删除的旧文件数，供验收举证
        self.removedCount: int = 0

    ## @brief 单轮采集主流程；顶层异常转失败回调，不外抛、不波及其他线程
    #  @return 无
    def runLoop(self) -> None:
        try:
            self._camera1.open()
            self._camera2.open()
            stamp = self._clock()
            self.fetchAndSave(self._camera1, f"w{self._workerId}_left_{stamp}.jpg")
            self.fetchAndSave(self._camera2, f"w{self._workerId}_right_{stamp}.jpg")
            self.checkRollStorage()
            self.reportSuccess()
        except EdgeError as error:
            self.reportError(error)
        except Exception as error:
            ## 内置异常跨线程边界前统一转业务异常
            self.reportError(EdgeError(ErrorCode.CAPTURE, f"采集异常: {error}"))
        finally:
            self._camera1.close()
            self._camera2.close()

    ## @brief 取单路帧并写入指定文件
    #  @param camera 摄像头设备
    #  @param fileName 文件名
    #  @return 落盘路径字符串
    #  @raises EdgeError 无帧或写盘失败时抛出，code=CAPTURE
    def fetchAndSave(self, camera: ICameraDevice, fileName: str) -> str:
        frame: FrameImage | None = camera.readFrame()
        if frame is None:
            raise EdgeError(ErrorCode.CAPTURE, f"取图为空: {fileName}")
        target = self._saveDir / fileName
        target.write_bytes(frame)
        self._currentFiles.add(target)
        return str(target)

    ## @brief 占用超阈值时按最旧顺序删图；删后仍超阈值记 error 但不中断
    #  @return 无
    def checkRollStorage(self) -> None:
        if self._usageRatio() <= self._rollThreshold:
            return
        candidates = sorted(
            (path for path in self._saveDir.glob("*.jpg")
             if path not in self._currentFiles),
            key=lambda path: (path.stat().st_mtime, path.name),
        )
        for candidate in candidates:
            if self._usageRatio() <= self._rollThreshold:
                break
            try:
                candidate.unlink()
            except OSError:
                ## 单个旧文件删除失败不影响本轮采集
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

    ## @brief 失败回调：记录异常码后轻量上抛
    #  @param error 业务异常
    #  @return 无
    def reportError(self, error: EdgeError) -> None:
        self._logError(error)
        self._onError(self._workerId, error)

    ## @brief 统一的错误日志出口，异常码使用 code.name
    #  @param error 业务异常
    #  @return 无
    def _logError(self, error: EdgeError) -> None:
        if self._logger is not None:
            message = f"worker-{self._workerId} 采集失败 {error.code.name}"
            self._logger.error(MODULE_NAME, message, exception=error)
