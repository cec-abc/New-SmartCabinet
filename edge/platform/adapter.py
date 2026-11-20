"""平台差异适配：Windows 实现、Linux 骨架与唯一平台工厂。"""
## @file edge/platform/adapter.py
## @brief 平台适配实现与工厂：Windows 锁文件、Linux 待补实现，工厂是唯一判断平台的位置
## @author 袁燕
from __future__ import annotations

import os
import signal
import sys
import time
from typing import BinaryIO

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_platform import IPlatformAdapter, SignalMapping


## @brief Windows 平台实现，文件锁使用 msvcrt.locking
class WindowsAdapter(IPlatformAdapter):
    ## @brief 按平台规则拼接路径
    #  @param parts 路径片段
    #  @return 拼接后的路径
    def joinPath(self, *parts: str) -> str:
        return os.path.join(*parts)

    ## @brief 返回 Windows 换行符
    #  @return CRLF
    def newline(self) -> str:
        return "\r\n"

    ## @brief 统一信号名到 Windows 信号编号的映射
    #  @return 信号映射表
    def signalMap(self) -> SignalMapping:
        ## Windows 无 SIGTERM 语义，用 SIGBREAK 承接「停止」事件
        terminateSignal = getattr(signal, "SIGBREAK", signal.SIGINT)
        return {"interrupt": int(signal.SIGINT), "terminate": int(terminateSignal)}

    ## @brief 返回高精度单调时钟
    #  @return 单调时钟秒值
    def monotonicClock(self) -> float:
        return time.monotonic()

    ## @brief 非阻塞锁定文件，句柄由调用方持有，关闭即释放锁
    #  @param filePath 锁文件路径
    #  @return 锁文件句柄；已被占用时返回 None
    def lockFile(self, filePath: str) -> BinaryIO | None:
        import msvcrt

        ## 以读写追加方式打开，保持句柄直到 release
        lockHandle = open(filePath, "a+b")
        try:
            ## 写入一字节，保证锁定区域真实存在
            lockHandle.write(b"\0")
            lockHandle.flush()
            lockHandle.seek(0)
            msvcrt.locking(lockHandle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            lockHandle.close()
            return None
        return lockHandle


## @brief Linux（麒麟 / RK3588）平台骨架，接口留好，上板后补齐实现
class LinuxAdapter(IPlatformAdapter):
    ## @brief 按平台规则拼接路径
    #  @param parts 路径片段
    #  @return 拼接后的路径
    def joinPath(self, *parts: str) -> str:
        return os.path.join(*parts)

    ## @brief 返回 Linux 换行符
    #  @return LF
    def newline(self) -> str:
        return "\n"

    ## @brief 统一信号名到 Linux 信号编号的映射
    #  @return 信号映射表
    def signalMap(self) -> SignalMapping:
        return {"interrupt": int(signal.SIGINT), "terminate": int(signal.SIGTERM)}

    ## @brief 返回高精度单调时钟
    #  @return 单调时钟秒值
    def monotonicClock(self) -> float:
        return time.monotonic()

    ## @brief 文件锁：麒麟 / Linux 用 fcntl.flock 实现非阻塞独占锁
    #  @param filePath 锁文件路径
    #  @return 锁文件句柄；已被占用时返回 None
    #  @raises EdgeError 平台不支持时由调用方转译
    def lockFile(self, filePath: str) -> BinaryIO | None:
        ## fcntl 是 Linux 标准库，函数体内导入避免 Windows 侧引入无关依赖
        import fcntl
        import os

        ## 以可读写方式创建锁文件，句柄随对象持有，close 即释放锁
        fd = os.open(filePath, os.O_CREAT | os.O_RDWR)
        try:
            ## 非阻塞排它锁：拿不到说明已有实例在跑
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return None
        ## fdopen 包装成文件对象；其 close() 会关闭 fd 并自动释放 flock 锁
        return os.fdopen(fd, "a+b")


## @brief 平台适配器工厂；全项目唯一判断 sys.platform 的位置
class PlatformFactory:
    ## @brief 按当前平台创建适配器
    #  @return 平台适配器实例
    #  @raises EdgeError 平台不受支持时抛出
    @staticmethod
    def create() -> IPlatformAdapter:
        ## Windows 分支返回完整实现
        if sys.platform == "win32":
            return WindowsAdapter()
        ## Linux 分支返回骨架实现，具体能力上板后补齐
        if sys.platform.startswith("linux"):
            return LinuxAdapter()
        raise EdgeError(ErrorCode.CONFIG, f"不支持的平台: {sys.platform}")
