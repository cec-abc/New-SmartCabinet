"""阶段 c2 补强单测：异步队列、logMode 路由、滚动清理、停机清空与异常堆栈。"""
from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pytest

from edge.exceptions import EdgeError, ErrorCode
from edge.infra import log_manager
from edge.infra.log_manager import (
    LOG_MODE_MERGED,
    LOG_MODE_SPLIT,
    MODULE_NAME,
    TYPE_ALL,
    TYPE_ERROR,
    TYPE_INFO,
    TYPE_RX,
    TYPE_TX,
    LogManager,
    buildRecord,
    encodePayload,
)
from edge.interfaces import i_logger
from edge.interfaces.i_logger import ILogger
from edge.tests.fakes.fake_logger import FakeLogger

## @brief 测试用单文件上限（充足）
TEST_MAX_FILE_SIZE: int = 4096
## @brief 磁盘清理阈值
TEST_DISK_THRESHOLD: float = 0.3
## @brief 队列轮询秒数
TEST_POLL_SEC: float = 0.01
## @brief 第一天
DAY_ONE: datetime = datetime(2026, 11, 11, 10, 0, 0)
## @brief 第二天
DAY_TWO: datetime = datetime(2026, 11, 12, 10, 0, 0)


## @brief 固定磁盘剩余比例（充足），避免测试依赖真实磁盘
#  @return 剩余比例 1.0
def plentifulDisk() -> float:
    return 1.0


## @brief 可控时钟，供跨天滚动测试改写当前时间
class MutableClock:
    ## @brief 构造时钟
    #  @param start 初始时间
    def __init__(self, start: datetime) -> None:
        ## @brief 当前时间
        self.current: datetime = start

    ## @brief 读取当前时间
    #  @return 当前时间
    def now(self) -> datetime:
        return self.current


## @brief 构造注入完备的日志门面
#  @param logDir 日志目录
#  @param logMode 合并 / 分开模式
#  @param maxFileSize 单文件上限
#  @param clock 时间提供器
#  @param diskFreeRatio 磁盘剩余比例提供器
#  @return 日志门面
def makeManager(
    logDir: Path,
    logMode: int = LOG_MODE_MERGED,
    maxFileSize: int = TEST_MAX_FILE_SIZE,
    clock: Callable[[], datetime] | None = None,
    diskFreeRatio: Callable[[], float] | None = None,
) -> LogManager:
    return LogManager(
        str(logDir),
        maxFileSize,
        logMode,
        TEST_DISK_THRESHOLD,
        TEST_POLL_SEC,
        clock,
        diskFreeRatio if diskFreeRatio is not None else plentifulDisk,
    )


## @brief 列出某前缀的日志文件
#  @param logDir 日志目录
#  @param prefix 文件名前缀
#  @return 按文件名排序的路径列表
def logFiles(logDir: Path, prefix: str = TYPE_ALL) -> list[Path]:
    return sorted(logDir.glob(f"{prefix}_*.log"))


## @brief 读取并解析所有落盘 JSON 行
#  @param logDir 日志目录
#  @param prefix 文件名前缀
#  @return 记录字典列表
def readRecords(logDir: Path, prefix: str = TYPE_ALL) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in logFiles(logDir, prefix):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parsed: dict[str, object] = json.loads(line)
            records.append(parsed)
    return records


## @brief 并发调用单例入口，用屏障对齐起跑时刻
#  @param logDir 日志目录
#  @param barrier 并发屏障
#  @return 单例对象
def callInstance(logDir: str, barrier: Barrier) -> LogManager:
    barrier.wait(timeout=5.0)
    return LogManager.instance(
        logDir,
        TEST_MAX_FILE_SIZE,
        LOG_MODE_MERGED,
        TEST_DISK_THRESHOLD,
        TEST_POLL_SEC,
        None,
        plentifulDisk,
    )


# 对应验收项 c2-1：ILogger 仅四方法、error 带 exception=None、无 init(config) 与 FrameData
def testILoggerExposesOnlyFourMethods() -> None:
    abstractNames = set(getattr(ILogger, "__abstractmethods__"))
    fakeMethods = sorted(
        name
        for name, value in inspect.getmembers(FakeLogger, inspect.isfunction)
        if not name.startswith("_")
    )
    errorDefault = inspect.signature(ILogger.error).parameters["exception"].default
    rxAnnotation = str(inspect.signature(ILogger.rx).parameters["data"].annotation)
    assert abstractNames == {"rx", "tx", "info", "error"}
    assert fakeMethods == ["error", "info", "rx", "tx"]
    assert errorDefault is None
    assert rxAnnotation == "dict[str, object] | bytes"
    assert hasattr(ILogger, "init") is False
    assert hasattr(LogManager, "init") is False
    assert hasattr(i_logger, "FrameData") is False
    assert hasattr(log_manager, "FrameData") is False
    assert isinstance(FakeLogger(), ILogger) is True


# 对应验收项 c2-1：业务线程只组 JSON 入队不做磁盘 IO，唯一队列由后台线程异步消费
def testSingleQueueAndAsyncConsumption(tmp_path: Path) -> None:
    logDir = tmp_path / "logs"
    manager = makeManager(logDir)
    assert isinstance(manager, ILogger) is True
    assert manager._records is manager._executor._records
    manager.rx("Tcp", {"frame": 1})
    manager.tx("Tcp", b"\x01\x02")
    manager.info("Tcp", "hello")
    manager.error("Tcp", "bad")
    assert manager._records.qsize() == 4
    assert [path.read_text(encoding="utf-8") for path in logFiles(logDir)] == [""]
    manager.start()
    manager.stop()
    records = readRecords(logDir)
    assert manager._records.empty() is True
    assert [record["type"] for record in records] == [
        "RX", "TX", "INFO", "ERROR", "INFO",
    ]
    assert records[0]["payload"] == {"frame": 1}
    assert records[1]["payload"] == {"bytesHex": "0102"}
    assert records[4]["module"] == MODULE_NAME


# 对应验收项 c2-1：logMode 合并只一个 Writer，分开按 RX/TX/INFO/ERROR 四类路由
def testLogModeRoutingMergedAndSplit(tmp_path: Path) -> None:
    mergedDir = tmp_path / "merged"
    splitDir = tmp_path / "split"
    merged = makeManager(mergedDir)
    split = makeManager(splitDir, logMode=LOG_MODE_SPLIT)
    assert sorted(merged._executor._writers.keys()) == [TYPE_ALL]
    assert sorted(split._executor._writers.keys()) == ["ERROR", "INFO", "RX", "TX"]
    split.rx("Tcp", {"id": 1})
    split.tx("Tcp", {"id": 2})
    split.info("Tcp", "note")
    split.error("Tcp", "bad")
    merged.info("Tcp", "note")
    split.stop()
    merged.stop()
    assert [len(readRecords(splitDir, p)) for p in [TYPE_RX, TYPE_TX, TYPE_INFO, TYPE_ERROR]] == [
        1, 1, 2, 1,
    ]
    assert readRecords(splitDir, TYPE_RX)[0]["payload"] == {"id": 1}
    assert readRecords(mergedDir)[0]["type"] == TYPE_INFO
    assert len(readRecords(splitDir, TYPE_ERROR)) == 1


# 对应验收项 c2-1：rx/tx 的 dict 与 bytes 两类 data 都进 JSON，不新增帧类型
def testBuildRecordEncodesDictAndBytes() -> None:
    assert encodePayload(b"\x01\x02") == {"bytesHex": "0102"}
    assert encodePayload({"id": 7}) == {"id": 7}
    line = buildRecord(TYPE_RX, "Tcp", {"id": 7}, DAY_ONE, None)
    record: dict[str, object] = json.loads(line)
    assert record["type"] == "RX"
    assert record["module"] == "Tcp"
    assert record["timestamp"] == "2026-11-11T10:00:00"
    assert record["day"] == "20261111"
    assert record["payload"] == {"id": 7}
    assert "stack" not in record


# 对应验收项 c2-1：日志目录不可创建时内置 OSError 转 EdgeError(CONFIG)
def testDirectoryCreationFailsFast(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(EdgeError) as caught:
        LogManager(
            str(blocker),
            TEST_MAX_FILE_SIZE,
            LOG_MODE_MERGED,
            TEST_DISK_THRESHOLD,
            TEST_POLL_SEC,
        )
    assert caught.value.code == ErrorCode.CONFIG
    assert str(caught.value) == f"[CONFIG] 日志目录不可用: {blocker}"


# 对应验收项 c2-2：跨天触发文件滚动，新文件带新日期标签
def testRollOverAcrossDays(tmp_path: Path) -> None:
    logDir = tmp_path / "logs"
    clock = MutableClock(DAY_ONE)
    manager = makeManager(logDir, clock=clock.now)
    manager.info("Biz", "day-one")
    clock.current = DAY_TWO
    manager.info("Biz", "day-two")
    manager.stop()
    paths = logFiles(logDir)
    assert len(paths) == 2
    assert paths[0].name == "ALL_20261111_0001.log"
    assert paths[1].name == "ALL_20261112_0002.log"
    assert [record["day"] for record in readRecords(logDir)] == [
        "20261111", "20261112", "20261112",
    ]


# 对应验收项 c2-2：超过 maxFileSize 触发滚动，每条独占一个文件
def testRollOverOnSizeLimit(tmp_path: Path) -> None:
    logDir = tmp_path / "logs"
    manager = makeManager(logDir, maxFileSize=1)
    manager.info("Biz", "first")
    manager.info("Biz", "second")
    manager.stop()
    paths = logFiles(logDir)
    assert len(paths) == 4
    assert [path.read_text(encoding="utf-8").count("\n") for path in paths] == [0, 1, 1, 1]
    assert len(readRecords(logDir)) == 3


# 对应验收项 c2-2：磁盘剩余比例低于阈值时删最旧文件，比例回升即停止
def testDiskCleanupRemovesOldestFile(tmp_path: Path) -> None:
    logDir = tmp_path / "logs"
    logDir.mkdir()
    oldest = logDir / "ALL_20260101_0001.log"
    other = logDir / "ALL_20260102_0001.log"
    oldest.write_text("old\n", encoding="utf-8")
    other.write_text("other\n", encoding="utf-8")
    ratioCalls: dict[str, int] = {"count": 0}

    ## @brief 首次返回低比例触发清理，删除一个文件后回升
    #  @return 剩余比例
    def readRatio() -> float:
        ratioCalls["count"] += 1
        return 0.1 if ratioCalls["count"] == 1 else 0.9

    clock = MutableClock(DAY_ONE)
    manager = makeManager(logDir, clock=clock.now, diskFreeRatio=readRatio)
    clock.current = DAY_TWO
    manager.info("Biz", "trigger-roll")
    manager.stop()
    writer = manager._executor._writers[TYPE_ALL]
    assert oldest.exists() is False
    assert other.exists() is True
    assert writer._removedCount == 1
    assert ratioCalls["count"] == 2


# 对应验收项 c2-3：停机清空队列剩余并关闭所有 Writer 句柄，重复 stop 幂等
def testStopDrainsQueueAndClosesHandles(tmp_path: Path) -> None:
    logDir = tmp_path / "logs"
    manager = makeManager(logDir)
    manager.info("Biz", "a")
    manager.rx("Biz", {"id": 1})
    manager.tx("Biz", b"\xaa")
    assert manager._records.qsize() == 3
    manager.stop()
    assert manager._records.empty() is True
    assert all(
        writer._handle.closed is True for writer in manager._executor._writers.values()
    ) is True
    records = readRecords(logDir)
    assert len(records) == 4
    assert records[3]["module"] == MODULE_NAME
    assert str(records[3]["payload"]).startswith("停机统计") is True
    manager.stop()
    assert manager._records.empty() is True
    assert len(readRecords(logDir)) == 4


# 对应验收项 c2-3：线程已启动时 stop 唤醒阻塞 take，join 返回后完成落盘
def testStopWakesBlockedTake(tmp_path: Path) -> None:
    logDir = tmp_path / "logs"
    manager = makeManager(logDir)
    manager.start()
    manager.info("Biz", "async")
    manager.stop(timeout=1.0)
    assert manager._executor.isRunning() is False
    assert manager._records.empty() is True
    assert all(
        writer._handle.closed is True for writer in manager._executor._writers.values()
    ) is True
    assert len(readRecords(logDir)) == 2


# 对应验收项 c2-4：error(exception=e) 自动附 Traceback 与 code.name，无异常不带 stack
def testErrorAppendsStackTrace(tmp_path: Path) -> None:
    logDir = tmp_path / "logs"
    manager = makeManager(logDir)
    try:
        raise EdgeError(ErrorCode.CONFIG, "配置缺失")
    except EdgeError as caught:
        manager.error("Biz", "初始化失败", exception=caught)
    manager.error("Biz", "普通错误")
    manager.stop()
    errorRecords = [
        record for record in readRecords(logDir) if record["type"] == TYPE_ERROR
    ]
    assert len(errorRecords) == 2
    stack = str(errorRecords[0]["stack"])
    assert "Traceback (most recent call last)" in stack
    assert "CONFIG" in stack
    assert "配置缺失" in stack
    assert "testErrorAppendsStackTrace" in stack
    assert errorRecords[0]["payload"] == "初始化失败"
    assert errorRecords[1]["payload"] == "普通错误"
    assert "stack" not in errorRecords[1]


# 对应验收项 c2-1：类内 instance() 双检锁唯一，普通构造仍可用于测试
def testInstanceIsDoubleCheckedSingleton(tmp_path: Path) -> None:
    LogManager._sharedInstance = None
    logDir = str(tmp_path / "shared" / "logs")
    barrier = Barrier(8)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(callInstance, logDir, barrier) for _ in range(8)]
        results = [future.result(timeout=5.0) for future in futures]
    assert all(result is results[0] for result in results) is True
    assert LogManager._sharedInstance is results[0]
    plain = makeManager(tmp_path / "plain" / "logs")
    assert plain is not results[0]
    results[0].stop()
    plain.stop()
    LogManager._sharedInstance = None
