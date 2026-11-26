"""D 组新增集成用例：真实进程锁双开与配置路径自锚定。

既有进程锁用例走 Fake 适配器或 WindowsAdapter 单进程，这里补上真实模块入口
`python -m edge.main` 作为第二实例时的行为，以及两种工作目录下配置路径的一致性。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from edge import app_init
from edge.exceptions import EdgeError, ErrorCode
from edge.runtime_platform.adapter import WindowsAdapter
from edge.runtime_platform.file_lock import ProcessFileLock

## @file edge/tests/integration/test_dplus_real_process_lock.py
## @brief 真实进程锁双开与配置路径自锚定的集成用例
## @author 袁燕

## @brief 仓库根目录
REPO_ROOT: Path = Path(__file__).resolve().parents[3]
## @brief 工程目录
EDGE_ROOT: Path = REPO_ROOT / "edge"
## @brief 等待第二实例退出的超时秒数
SECOND_EXIT_TIMEOUT_SEC: float = 20.0
## @brief 判定"立即退出"的上限秒数
IMMEDIATE_EXIT_SEC: float = 5.0
## @brief 第一实例持锁的等待秒数
FIRST_HOLD_SEC: float = 15.0
## @brief 子进程环境：临时目录放在 pytest 的临时盘，避免占用系统盘
CHILD_ENV_KEYS: tuple[str, ...] = ("TMP", "TEMP", "TMPDIR")


## @brief 造出子进程环境，补上仓库根作为模块搜索路径
#  @param tmpPath 本用例的临时目录
#  @return 环境变量字典
def buildChildEnv(tmpPath: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    ## 子进程按 UTF-8 输出中文提示，父进程同编码读取，避免 Windows 默认代码页把提示打乱
    env["PYTHONIOENCODING"] = "utf-8"
    for key in CHILD_ENV_KEYS:
        env[key] = str(tmpPath)
    return env


## @brief 第一实例只做持锁，不装配业务模块，避免并行期读到未完成的实现
#  @param lockPath 锁文件路径
#  @return 子进程脚本源码
def buildFirstHolderCode(lockPath: Path) -> str:
    return (
        "import time\n"
        "from edge.runtime_platform.adapter import WindowsAdapter\n"
        "from edge.runtime_platform.file_lock import ProcessFileLock\n"
        f"lock = ProcessFileLock(WindowsAdapter(), {str(lockPath)!r})\n"
        "lock.acquire()\n"
        "print('LOCKED', flush=True)\n"
        f"time.sleep({FIRST_HOLD_SEC})\n"
        "lock.release()\n"
    )


## @brief 第二实例用真实模块入口，锁被占时应立即带 CONFIG 退出
#  @param tmp_path pytest 临时目录
#  @return 无
def testSecondRealMainInstanceExitsImmediately(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows 文件锁语义验证，仅 win32 适用")
    lockPath = tmp_path / "edge_runtime.lock"
    env = buildChildEnv(tmp_path)
    first = subprocess.Popen(
        [sys.executable, "-c", buildFirstHolderCode(lockPath)],
        cwd=str(tmp_path), env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
    )
    try:
        assert first.stdout is not None
        assert first.stdout.readline().strip() == "LOCKED"
        deadline = time.monotonic() + IMMEDIATE_EXIT_SEC
        while not lockPath.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert lockPath.exists(), "第一实例应已创建锁文件"
        started = time.monotonic()
        second = subprocess.run(
            [sys.executable, "-m", "edge.main"],
            cwd=str(tmp_path), env=env, capture_output=True,
            text=True, timeout=SECOND_EXIT_TIMEOUT_SEC,
            encoding="utf-8", errors="replace",
        )
        elapsed = time.monotonic() - started
        message = second.stdout + second.stderr
        assert second.returncode != 0, "第二实例不应正常返回"
        assert elapsed < IMMEDIATE_EXIT_SEC, f"第二实例耗时 {elapsed:.2f}s，未立即退出"
        assert "已有实例运行" in message
        assert "CONFIG" in message
    finally:
        first.terminate()
        try:
            first.wait(timeout=5)
        except subprocess.TimeoutExpired:
            first.kill()


## @brief 配置文件自身路径按工程目录自锚定，两种工作目录下解析结果一致
#  @param tmp_path pytest 临时目录
#  @return 无
def testDefaultConfigPathIsCwdIndependent(tmp_path: Path) -> None:
    code = (
        "from edge import app_init as a\n"
        "print(a.DEFAULT_CONFIG_PATH)\n"
        "print(a.resolveConfigFilePath(a.DEFAULT_CONFIG_PATH))\n"
    )
    env = buildChildEnv(tmp_path)
    outputs: list[list[str]] = []
    for cwd in (REPO_ROOT, EDGE_ROOT):
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=str(cwd), env=env,
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout.strip().splitlines())
    assert outputs[0] == outputs[1], (
        f"两种工作目录解析结果不同: {outputs[0]} vs {outputs[1]}"
    )
    assert outputs[0][0] == str(EDGE_ROOT / "config" / "config.ini")


## @brief 相对路径候选把运行时工作目录排在第一位
#  @param tmp_path pytest 临时目录
#  @return 无
def testConfigPathCandidatesStartWithCwd(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    code = (
        "from edge import app_init as a\n"
        "print('|'.join(str(p) for p in a.configPathCandidates('./logs')))\n"
    )
    env = buildChildEnv(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=str(work), env=env,
        capture_output=True, text=True, timeout=20,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stderr
    candidates = result.stdout.strip().split("|")
    assert len(candidates) == 3
    assert Path(candidates[0]) == work / "logs"
    assert Path(candidates[1]) == EDGE_ROOT / "logs"
    assert Path(candidates[2]) == REPO_ROOT / "logs"


## @brief 运行目录不存在时由 ensureRuntimeDirs 逐级建好
#  @param tmp_path pytest 临时目录
#  @return 无
def testEnsureRuntimeDirsCreatesMissingPaths(tmp_path: Path) -> None:
    logDir = tmp_path / "fresh" / "logs"
    captureDirs = [str(tmp_path / "fresh" / "capture" / f"w{i}") for i in range(1, 5)]
    recogDirs = [str(tmp_path / "fresh" / "recog" / f"w{i}") for i in range(1, 5)]
    app_init.ensureRuntimeDirs(str(logDir), captureDirs, recogDirs)
    assert logDir.is_dir()
    assert all(Path(item).is_dir() for item in captureDirs)
    assert all(Path(item).is_dir() for item in recogDirs)


## @brief 目录创建失败时转成 CONFIG 配置错误，不泄漏系统异常
#  @param tmp_path pytest 临时目录
#  @return 无
def testEnsureRuntimeDirsConvertsOsErrorToConfig(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(EdgeError) as caught:
        app_init.ensureRuntimeDirs(str(blocker / "child"), [], [])
    assert caught.value.code is ErrorCode.CONFIG
    assert "运行目录创建失败" in str(caught.value)


## @brief release 重复调用结果一致，且不抛异常
#  @param tmp_path pytest 临时目录
#  @return 无
def testProcessLockReleaseIsIdempotent(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows 文件锁语义验证，仅 win32 适用")
    lock = ProcessFileLock(WindowsAdapter(), str(tmp_path / "edge_runtime.lock"))
    lock.acquire()
    try:
        assert lock.lockHandle is not None
        lock.release()
        assert lock.lockHandle is None
        lock.release()
        assert lock.lockHandle is None
    finally:
        lock.release()
