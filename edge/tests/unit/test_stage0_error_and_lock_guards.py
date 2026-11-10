"""阶段 0 补强单测：ErrorCode 五码格式、EdgeError 抛捕、平台工厂分支与进程锁边界。"""
from __future__ import annotations

import inspect
import io
import sys
from unittest.mock import patch

import pytest

from edge.exceptions import EdgeError, ErrorCode
from edge.platform.adapter import LinuxAdapter, PlatformFactory, WindowsAdapter
from edge.platform.file_lock import ProcessFileLock
from edge.tests.fakes.fake_platform_adapter import FakePlatformAdapter


## @brief 校验五码枚举的成员名、整数值与 IntEnum 语义
# 对应验收项 0-2：ErrorCode 恰五码且 code.name 可枚举
def testErrorCodeEnumeratesFiveCodes() -> None:
    assert [code.name for code in ErrorCode] == [
        "CONFIG",
        "LINK_DOWN",
        "FRAME_PARSE",
        "INFERENCE_TIMEOUT",
        "CAPTURE",
    ]
    assert [int(code) for code in ErrorCode] == [1, 2, 3, 4, 5]
    assert ErrorCode.CONFIG.value == 1
    assert isinstance(ErrorCode.CAPTURE, int)


## @brief 捕获抛出的 EdgeError 并校验精确的 [CODE] 日志格式
# 对应验收项 0-2：EdgeError 抛出 / 捕获与 code.name 日志格式正确
def testEdgeErrorRaiseAndCatchCarriesExactCodeName() -> None:
    with pytest.raises(EdgeError) as caught:
        raise EdgeError(ErrorCode.LINK_DOWN, "链路中断")
    error = caught.value
    assert error.code is ErrorCode.LINK_DOWN
    assert error.code.name == "LINK_DOWN"
    assert str(error) == "[LINK_DOWN] 链路中断"
    assert error.args == ("[LINK_DOWN] 链路中断",)


## @brief 逐一构造五码异常，校验 [CODE] 前缀对全部枚举码一致
# 对应验收项 0-2：[CODE] 字符串格式对五码统一
def testEdgeErrorFormatsEveryCodeNamePrefix() -> None:
    rendered: list[str] = []
    for code in ErrorCode:
        error = EdgeError(code, "msg")
        assert error.code is code
        rendered.append(str(error))
    assert rendered == [
        "[CONFIG] msg",
        "[LINK_DOWN] msg",
        "[FRAME_PARSE] msg",
        "[INFERENCE_TIMEOUT] msg",
        "[CAPTURE] msg",
    ]


## @brief 不受运行 OS 影响，win32 分支返回 WindowsAdapter 具体类型
# 对应验收项 0-3：PlatformFactory Windows 返回 WindowsAdapter
def testFactoryReturnsWindowsAdapterForWin32() -> None:
    with patch.object(sys, "platform", "win32"):
        adapter = PlatformFactory.create()
    assert type(adapter) is WindowsAdapter
    assert adapter.newline() == "\r\n"


## @brief linux 分支返回 LinuxAdapter 骨架实现
# 对应验收项 0-3：PlatformFactory Linux 分支
def testFactoryReturnsLinuxAdapterForLinux() -> None:
    with patch.object(sys, "platform", "linux"):
        adapter = PlatformFactory.create()
    assert type(adapter) is LinuxAdapter
    assert adapter.newline() == "\n"


## @brief 不受支持平台由工厂抛 EdgeError(CONFIG)
# 对应验收项 0-3：sys.platform 收敛于唯一工厂，其余平台 Fail-Fast
def testFactoryRejectsUnsupportedPlatformWithConfig() -> None:
    with pytest.raises(EdgeError) as caught:
        with patch.object(sys, "platform", "freebsd"):
            PlatformFactory.create()
    error = caught.value
    assert error.code is ErrorCode.CONFIG
    assert str(error) == "[CONFIG] 不支持的平台: freebsd"


## @brief Linux 锁骨架抛内置异常且源码保留上板 TODO 与 fcntl.flock 提示
# 对应验收项 0-3：Linux 分支 NotImplementedError + TODO 骨架
def testLinuxLockSkeletonMarksTodoAndRaisesExactMessage() -> None:
    source = inspect.getsource(LinuxAdapter.lockFile)
    assert source.count("TODO") == 1
    assert source.count("fcntl.flock") == 1
    with pytest.raises(NotImplementedError) as caught:
        LinuxAdapter().lockFile("unused.lock")
    assert str(caught.value) == "Linux 文件锁待上板实现"


## @brief Fake 模拟锁被占用返回 None，acquire 抛 CONFIG 且不重试
# 对应验收项 0-4：双开取锁失败
def testAcquireOccupiedLockRaisesConfigViaFake() -> None:
    adapter = FakePlatformAdapter(lockResult=None)
    lock = ProcessFileLock(adapter, "edge_runtime.lock")
    with pytest.raises(EdgeError) as caught:
        lock.acquire()
    error = caught.value
    assert error.code is ErrorCode.CONFIG
    assert str(error) == "[CONFIG] 已有实例运行，进程锁获取失败"
    assert adapter.lockCalls == ["edge_runtime.lock"]
    assert lock.lockHandle is None


## @brief 骨架内置异常转 EdgeError(CONFIG) 且保留 __cause__ 因果链
# 对应验收项 0-4：内置异常不跨模块边界
def testAcquireConvertsSkeletonErrorPreservingCause() -> None:
    lock = ProcessFileLock(LinuxAdapter(), "edge_runtime.lock")
    with pytest.raises(EdgeError) as caught:
        lock.acquire()
    error = caught.value
    assert error.code is ErrorCode.CONFIG
    assert str(error) == "[CONFIG] 平台文件锁尚未实现"
    assert type(error.__cause__) is NotImplementedError
    assert str(error.__cause__) == "Linux 文件锁待上板实现"


## @brief 取锁失败时 acquireOrExit 立即 sys.exit 且携带 CONFIG 码
# 对应验收项 0-4：双开取锁失败并立即退出
def testAcquireOrExitExitsImmediatelyWithConfigMessage() -> None:
    adapter = FakePlatformAdapter(lockResult=None)
    lock = ProcessFileLock(adapter, "edge_runtime.lock")
    with pytest.raises(SystemExit) as caught:
        lock.acquireOrExit()
    expectedMessage = f"[CONFIG] {EdgeError(ErrorCode.CONFIG, '已有实例运行，进程锁获取失败')}"
    assert type(caught.value.code) is str
    assert caught.value.code == expectedMessage
    assert adapter.lockCalls == ["edge_runtime.lock"]
    assert lock.lockHandle is None


## @brief 取锁成功时 acquireOrExit 不退出且继续持有句柄
# 对应验收项 0-4：成功分支不误触发进程退出
def testAcquireOrExitKeepsLockWhenAcquired() -> None:
    handle = io.BytesIO()
    lock = ProcessFileLock(FakePlatformAdapter(lockResult=handle), "edge_runtime.lock")
    lock.acquireOrExit()
    assert lock.lockHandle is handle
    assert handle.closed is False


## @brief release 关闭句柄并把状态置 None，重复调用安全
# 对应验收项 0-4：release 幂等
def testReleaseIsIdempotentAndClosesHandle() -> None:
    handle = io.BytesIO()
    adapter = FakePlatformAdapter(lockResult=handle)
    lock = ProcessFileLock(adapter, "edge_runtime.lock")
    lock.acquire()
    assert lock.lockHandle is handle
    assert handle.closed is False
    lock.release()
    assert handle.closed is True
    assert lock.lockHandle is None
    lock.release()
    assert lock.lockHandle is None
    assert adapter.lockCalls == ["edge_runtime.lock"]
