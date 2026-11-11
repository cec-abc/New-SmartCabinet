"""日志门面：唯一阻塞队列、异步消费、logMode 路由、滚动清理与停机清空。"""
from __future__ import annotations

import json
import shutil
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Lock
from typing import IO

from edge.base.base_thread import BaseThread
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_logger import ILogger

## @brief 日志类型常量
TYPE_RX: str = "RX"
TYPE_TX: str = "TX"
TYPE_INFO: str = "INFO"
TYPE_ERROR: str = "ERROR"
TYPE_ALL: str = "ALL"
## @brief logMode：合并写入单一文件
LOG_MODE_MERGED: int = 1
## @brief logMode：按类型分开写入
LOG_MODE_SPLIT: int = 0
## @brief 文件名日期标签格式
DAY_FORMAT: str = "%Y%m%d"
## @brief 落盘换行符
LINE_BREAK: str = "\n"
## @brief 队列无界容量
UNBOUNDED_QUEUE_SIZE: int = 0
## @brief 日志模块名
MODULE_NAME: str = "LogManager"


## @brief 把字节负载转为可序列化结构，其余负载原样返回
#  @param data 业务负载
#  @return 可进入 JSON 的对象
def encodePayload(data: object) -> object:
    if isinstance(data, bytes):
        return {"bytesHex": data.hex()}
    return data


## @brief 业务线程内组装单行 JSON 记录，不做任何磁盘 IO
#  @param logType 日志类型
#  @param module 模块名
#  @param payload 日志负载
#  @param stamp 注入时钟给出的时间戳
#  @param stack 可选异常堆栈
#  @return 单行 JSON 字符串
def buildRecord(
    logType: str,
    module: str,
    payload: object,
    stamp: datetime,
    stack: str | None = None,
) -> str:
    record: dict[str, object] = {
        "type": logType,
        "module": module,
        "timestamp": stamp.isoformat(),
        "day": stamp.strftime(DAY_FORMAT),
        "payload": encodePayload(payload),
    }
    if stack is not None:
        record["stack"] = stack
    ## 兜底把非基本类型转字符串，保证业务线程入队不抛异常
    return json.dumps(record, ensure_ascii=False, default=str)


## @brief 生成异常堆栈文本；业务异常附带 code.name 便于扫描
#  @param error 异常对象
#  @return 含 Traceback 的堆栈文本
def formatStackTrace(error: Exception) -> str:
    text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    if isinstance(error, EdgeError):
        return f"{error.code.name}: {text}"
    return text


## @brief 默认磁盘剩余比例，供未注入时使用
#  @param logDir 日志目录
#  @return 剩余空间比例
def defaultDiskFreeRatio(logDir: Path) -> float:
    usage = shutil.disk_usage(logDir)
    return usage.free / usage.total


## @brief 单个日志文件写入器：滚动、磁盘清理与句柄生命周期
class LogFileWriter:
    ## @brief 构造并立即打开首个日志文件
    #  @param logDir 日志目录
    #  @param prefix 文件名前缀，即日志类型
    #  @param maxFileSize 单文件字节上限，构造注入
    #  @param diskFreeThreshold 磁盘剩余比例阈值，构造注入
    #  @param day 初始日期标签
    #  @param diskFreeRatio 磁盘剩余比例提供器
    #  @raises EdgeError 日志文件不可打开（CONFIG）
    def __init__(
        self,
        logDir: Path,
        prefix: str,
        maxFileSize: int,
        diskFreeThreshold: float,
        day: str,
        diskFreeRatio: Callable[[], float],
    ) -> None:
        ## @brief 日志目录
        self._logDir: Path = logDir
        ## @brief 文件名前缀
        self._prefix: str = prefix
        ## @brief 单文件字节上限
        self._maxFileSize: int = maxFileSize
        ## @brief 磁盘清理阈值
        self._diskFreeThreshold: float = diskFreeThreshold
        ## @brief 磁盘剩余比例提供器
        self._diskFreeRatio: Callable[[], float] = diskFreeRatio
        ## @brief 当前文件流水号
        self._sequence: int = 1
        ## @brief 当前文件日期标签
        self._currentDay: str = day
        ## @brief 当前文件已写字节数
        self._currentSize: int = 0
        ## @brief 当前文件路径
        self._currentPath: Path = self.buildPath(day)
        ## @brief 当前文件句柄
        self._handle: IO[str] = self.openHandle(self._currentPath)
        ## @brief 落盘失败跳过行数
        self._writeFailureCount: int = 0
        ## @brief 磁盘清理删除文件数
        self._removedCount: int = 0

    ## @brief 按前缀、日期与流水号生成文件路径
    #  @param day 日期标签
    #  @return 日志文件路径
    def buildPath(self, day: str) -> Path:
        return self._logDir / f"{self._prefix}_{day}_{self._sequence:04d}.log"

    ## @brief 打开（或新建）指定路径的文件句柄
    #  @param path 目标路径
    #  @return 文本写入句柄
    #  @raises EdgeError 打开失败（CONFIG）
    def openHandle(self, path: Path) -> IO[str]:
        try:
            return path.open("a", encoding="utf-8")
        except OSError as error:
            raise EdgeError(ErrorCode.CONFIG, f"日志文件不可用: {path}") from error

    ## @brief 写入一行；必要时先滚动，落盘失败跳过本行保持后台线程存活
    #  @param line 单行 JSON 记录
    #  @param day 记录日期标签
    #  @return 无
    def writeLine(self, line: str, day: str) -> None:
        size = len(line.encode("utf-8")) + len(LINE_BREAK.encode("utf-8"))
        self.rollIfNeeded(size, day)
        try:
            self._handle.write(line + LINE_BREAK)
            self._handle.flush()
            self._currentSize += size
        except OSError:
            ## 日志落盘属必要容错：单行失败不阻断后台线程
            self._writeFailureCount += 1

    ## @brief 跨天或超上限时切换文件并触发磁盘清理
    #  @param incomingSize 待写字节数
    #  @param day 记录日期标签
    #  @return 无
    def rollIfNeeded(self, incomingSize: int, day: str) -> None:
        oversized = self._currentSize + incomingSize > self._maxFileSize
        if day == self._currentDay and not oversized:
            return
        self.closeHandle()
        self._sequence += 1
        self._currentDay = day
        self._currentSize = 0
        self._currentPath = self.buildPath(day)
        self._handle = self.openHandle(self._currentPath)
        self.purgeOldFiles()

    ## @brief 磁盘剩余比例低于阈值时删除最旧的历史文件
    #  @return 无
    def purgeOldFiles(self) -> None:
        if self._diskFreeRatio() >= self._diskFreeThreshold:
            return
        for candidate in sorted(self._logDir.glob(f"{self._prefix}_*.log")):
            if candidate == self._currentPath:
                continue
            try:
                candidate.unlink()
            except OSError:
                ## 历史文件删除失败不影响当前写入
                continue
            self._removedCount += 1
            if self._diskFreeRatio() >= self._diskFreeThreshold:
                break

    ## @brief 关闭当前句柄；重复调用幂等
    #  @return 无
    def closeHandle(self) -> None:
        if not self._handle.closed:
            self._handle.close()


## @brief 后台消费线程：从唯一队列取记录、按 logMode 路由、停机清空并关句柄
class LogExecutor(BaseThread):
    ## @brief 构造消费线程与 Writer 集合
    #  @param records 唯一阻塞队列（由 LogManager 创建并共享）
    #  @param logDir 日志目录
    #  @param maxFileSize 单文件字节上限
    #  @param logMode 合并 / 分开模式
    #  @param diskFreeThreshold 磁盘清理阈值
    #  @param queuePollSec 队列 take 超时秒数，构造注入
    #  @param clock 时间提供器
    #  @param diskFreeRatio 磁盘剩余比例提供器
    def __init__(
        self,
        records: Queue[str],
        logDir: Path,
        maxFileSize: int,
        logMode: int,
        diskFreeThreshold: float,
        queuePollSec: float,
        clock: Callable[[], datetime],
        diskFreeRatio: Callable[[], float],
    ) -> None:
        super().__init__(name="LogExecutor")
        ## @brief 唯一阻塞队列
        self._records: Queue[str] = records
        ## @brief 日志模式
        self._logMode: int = logMode
        ## @brief take 超时秒数
        self._queuePollSec: float = queuePollSec
        prefixes = (
            [TYPE_ALL] if logMode == LOG_MODE_MERGED
            else [TYPE_RX, TYPE_TX, TYPE_INFO, TYPE_ERROR]
        )
        day = clock().strftime(DAY_FORMAT)
        ## @brief 类型到 Writer 的映射
        self._writers: dict[str, LogFileWriter] = {
            prefix: LogFileWriter(
                logDir, prefix, maxFileSize, diskFreeThreshold, day, diskFreeRatio
            )
            for prefix in prefixes
        }

    ## @brief 主循环：阻塞 take 消费；收到停止指令后清空队列并关闭句柄
    #  @return 无
    def runLoop(self) -> None:
        try:
            while True:
                try:
                    record = self._records.get(timeout=self._queuePollSec)
                except Empty:
                    if self.stopEvent.is_set():
                        break
                    continue
                self.consumeRecord(record)
        finally:
            self.flushRecords()
            self.closeWriters()

    ## @brief 把单条 JSON 记录按模式路由到对应 Writer
    #  @param record 单行 JSON 记录
    #  @return 无
    def consumeRecord(self, record: str) -> None:
        payload: dict[str, object] = json.loads(record)
        key = TYPE_ALL if self._logMode == LOG_MODE_MERGED else str(payload["type"])
        writer = self._writers.get(key)
        if writer is None:
            ## 仅四类日志会入队，未知类型直接跳过
            return
        writer.writeLine(record, str(payload["day"]))

    ## @brief 停机时把队列剩余记录全部写完
    #  @return 无
    def flushRecords(self) -> None:
        while True:
            try:
                record = self._records.get_nowait()
            except Empty:
                return
            self.consumeRecord(record)

    ## @brief 依次关闭所有 Writer 句柄
    #  @return 无
    def closeWriters(self) -> None:
        for writer in self._writers.values():
            writer.closeHandle()


## @brief 日志门面：实现 ILogger 四方法，唯一队列、类内双检锁单例
class LogManager(ILogger):
    ## @brief 全局唯一实例
    _sharedInstance: LogManager | None = None
    ## @brief 实例构造锁
    _instanceLock: Lock = Lock()

    ## @brief 构造日志门面；所有阈值与周期由上层构造注入
    #  @param logDir 日志目录
    #  @param maxFileSize 单文件字节上限
    #  @param logMode 合并（1）/ 分开（0）
    #  @param diskFreeThreshold 磁盘清理阈值
    #  @param queuePollSec 队列 take 超时秒数
    #  @param clock 时间提供器，便于测试跨天
    #  @param diskFreeRatio 磁盘剩余比例提供器
    #  @param maxQueueSize 队列容量，0 表示无界
    #  @raises EdgeError 日志目录不可创建（CONFIG）
    def __init__(
        self,
        logDir: str,
        maxFileSize: int,
        logMode: int,
        diskFreeThreshold: float,
        queuePollSec: float,
        clock: Callable[[], datetime] | None = None,
        diskFreeRatio: Callable[[], float] | None = None,
        maxQueueSize: int = UNBOUNDED_QUEUE_SIZE,
    ) -> None:
        super().__init__()
        ## @brief 日志目录
        self._logDir: Path = Path(logDir)
        try:
            self._logDir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise EdgeError(ErrorCode.CONFIG, f"日志目录不可用: {self._logDir}") from error
        ## @brief 时间提供器
        self._clock: Callable[[], datetime] = (
            clock if clock is not None else lambda: datetime.now()
        )
        ## @brief 磁盘剩余比例提供器
        ratioProvider: Callable[[], float] = (
            diskFreeRatio if diskFreeRatio is not None
            else lambda: defaultDiskFreeRatio(self._logDir)
        )
        ## @brief 唯一阻塞队列
        self._records: Queue[str] = Queue(maxsize=maxQueueSize)
        ## @brief 后台消费线程
        self._executor: LogExecutor = LogExecutor(
            self._records,
            self._logDir,
            maxFileSize,
            logMode,
            diskFreeThreshold,
            queuePollSec,
            self._clock,
            ratioProvider,
        )
        ## @brief 停机锁
        self._stopLock: Lock = Lock()
        ## @brief 是否已停机，保证重复 stop 幂等
        self._stopped: bool = False

    ## @brief 获取全局唯一实例；首次调用注入参数，双检锁避免并发重复构造
    #  @param logDir 日志目录
    #  @param maxFileSize 单文件字节上限
    #  @param logMode 合并（1）/ 分开（0）
    #  @param diskFreeThreshold 磁盘清理阈值
    #  @param queuePollSec 队列 take 超时秒数
    #  @param clock 时间提供器
    #  @param diskFreeRatio 磁盘剩余比例提供器
    #  @param maxQueueSize 队列容量
    #  @return 单例
    @classmethod
    def instance(
        cls,
        logDir: str,
        maxFileSize: int,
        logMode: int,
        diskFreeThreshold: float,
        queuePollSec: float,
        clock: Callable[[], datetime] | None = None,
        diskFreeRatio: Callable[[], float] | None = None,
        maxQueueSize: int = UNBOUNDED_QUEUE_SIZE,
    ) -> LogManager:
        shared = cls._sharedInstance
        if shared is None:
            with cls._instanceLock:
                shared = cls._sharedInstance
                if shared is None:
                    shared = cls(
                        logDir,
                        maxFileSize,
                        logMode,
                        diskFreeThreshold,
                        queuePollSec,
                        clock,
                        diskFreeRatio,
                        maxQueueSize,
                    )
                    cls._sharedInstance = shared
        return shared

    ## @brief 记录接收帧，仅入队不落盘
    #  @param module 模块名
    #  @param data 解析后的字典或原始字节
    #  @return 无
    def rx(self, module: str, data: dict[str, object] | bytes) -> None:
        self.publishRecord(TYPE_RX, module, data)

    ## @brief 记录发送帧，仅入队不落盘
    #  @param module 模块名
    #  @param data 解析后的字典或原始字节
    #  @return 无
    def tx(self, module: str, data: dict[str, object] | bytes) -> None:
        self.publishRecord(TYPE_TX, module, data)

    ## @brief 记录普通信息，仅入队不落盘
    #  @param module 模块名
    #  @param msg 日志内容
    #  @return 无
    def info(self, module: str, msg: str) -> None:
        self.publishRecord(TYPE_INFO, module, msg)

    ## @brief 记录错误；传入异常时自动附堆栈
    #  @param module 模块名
    #  @param msg 日志内容
    #  @param exception 可选异常对象
    #  @return 无
    def error(self, module: str, msg: str, exception: Exception | None = None) -> None:
        stack = None if exception is None else formatStackTrace(exception)
        self.publishRecord(TYPE_ERROR, module, msg, stack)

    ## @brief 组装 JSON 并放入唯一队列；无界队列入队不阻塞业务线程
    #  @param logType 日志类型
    #  @param module 模块名
    #  @param payload 日志负载
    #  @param stack 可选异常堆栈
    #  @return 无
    def publishRecord(
        self, logType: str, module: str, payload: object, stack: str | None = None
    ) -> None:
        self._records.put(buildRecord(logType, module, payload, self._clock(), stack))

    ## @brief 启动后台消费线程；BaseThread 保证重复 start 幂等
    #  @return 无
    def start(self) -> None:
        self._executor.start()

    ## @brief 停机：记统计、唤醒 take、清空队列并关闭句柄；重复调用幂等
    #  @param timeout 等待消费线程退出的最长秒数
    #  @return 无
    def stop(self, timeout: float = 3.0) -> None:
        with self._stopLock:
            if self._stopped:
                return
            self._stopped = True
        ## 停机统计用 info 入队，同时唤醒阻塞中的 take
        self.info(MODULE_NAME, f"停机统计 待处理 {self._records.qsize()} 条")
        if self._executor.isRunning():
            self._executor.stop(timeout)
        else:
            self._executor.flushRecords()
            self._executor.closeWriters()
