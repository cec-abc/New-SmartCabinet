"""平台差异适配：Windows 实现、Linux 骨架与唯一平台工厂。"""
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

    ## @brief 文件锁骨架，上板后实现
    #  @param filePath 锁文件路径
    #  @return 锁文件句柄；当前骨架不返回
    #  @raises NotImplementedError 上板前统一抛出
    def lockFile(self, filePath: str) -> BinaryIO | None:
        # TODO: 上板后实现 fcntl.flock(fd, LOCK_EX | LOCK_NB)，并补 V4L2 摄像头后端
        raise NotImplementedError("Linux 文件锁待上板实现")


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
