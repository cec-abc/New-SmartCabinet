"""阶段 0 验收：异常码、平台工厂骨架、异常边界转换与双开拿锁失败。"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from edge.exceptions import EdgeError, ErrorCode
from edge.platform.adapter import LinuxAdapter, PlatformFactory, WindowsAdapter
from edge.platform.file_lock import ProcessFileLock


## @brief 为 skipif 装饰器补齐类型，避免 follow_imports=skip 下装饰器被推断为 Any
#  @param reason 跳过原因，原样传给 pytest.mark.skipif
#  @return 带类型的 skipif 装饰器
def windowsOnly(reason: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
    return cast(
        Callable[[Callable[[], None]], Callable[[], None]],
        pytest.mark.skipif(os.name != "nt", reason=reason),
    )


## @brief EdgeError 携带枚举码，字符串含 code.name 便于日志扫描
def testEdgeErrorCarriesCodeName() -> None:
    error = EdgeError(ErrorCode.FRAME_PARSE, "坏帧")
    assert error.code is ErrorCode.FRAME_PARSE
    assert error.code.name == "FRAME_PARSE"
    assert "[FRAME_PARSE]" in str(error)


## @brief Windows 上工厂返回完整实现的适配器
@windowsOnly("仅 Windows 验证")
def testFactoryReturnsWindowsAdapter() -> None:
    assert isinstance(PlatformFactory.create(), WindowsAdapter)


## @brief Linux 骨架的锁方法按方案抛内置 NotImplementedError
def testLinuxAdapterSkeletonRaises() -> None:
    with pytest.raises(NotImplementedError):
        LinuxAdapter().lockFile("unused.lock")


## @brief 骨架抛出的内置异常在跨模块边界前转换为 CONFIG 业务异常
def testLinuxSkeletonIsConvertedToEdgeError() -> None:
    with tempfile.TemporaryDirectory() as tempDir:
        lockPath = Path(tempDir) / "edge.lock"
        lock = ProcessFileLock(LinuxAdapter(), str(lockPath))
        with pytest.raises(EdgeError) as errorInfo:
            lock.acquire()
        assert errorInfo.value.code is ErrorCode.CONFIG


## @brief 主进程持锁时，第二进程拿锁失败并报告 CONFIG
@windowsOnly("仅 Windows 验证")
def testSecondProcessCannotAcquireLock() -> None:
    projectRoot = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as tempDir:
        lockPath = Path(tempDir) / "edge_runtime.lock"
        firstLock = ProcessFileLock(WindowsAdapter(), str(lockPath))
        firstLock.acquire()
        try:
            script = (
                "from edge.exceptions import EdgeError\n"
                "from edge.platform.adapter import WindowsAdapter\n"
                "from edge.platform.file_lock import ProcessFileLock\n"
                f"lock = ProcessFileLock(WindowsAdapter(), {str(lockPath)!r})\n"
                "try:\n"
                "    lock.acquire()\n"
                "except EdgeError as error:\n"
                "    print(error.code.name)\n"
                "else:\n"
                "    raise SystemExit(1)\n"
            )
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(projectRoot),
                capture_output=True,
                text=True,
                check=False,
            )
            assert completed.returncode == 0
            assert "CONFIG" in completed.stdout
        finally:
            firstLock.release()
