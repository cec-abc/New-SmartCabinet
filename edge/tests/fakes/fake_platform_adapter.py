"""平台适配器接口 Fake 实现。"""
from __future__ import annotations

from typing import BinaryIO

from edge.interfaces.i_platform import IPlatformAdapter, SignalMapping


## @brief 不触碰系统资源、只记录调用的平台适配器 Fake
class FakePlatformAdapter(IPlatformAdapter):
    ## @brief 构造 Fake
    #  @param lockResult lockFile 的返回值，用于模拟锁被占用
    def __init__(self, lockResult: BinaryIO | None = None) -> None:
        ## @brief 预设的锁返回值
        self.lockResult = lockResult
        ## @brief lockFile 调用记录
        self.lockCalls: list[str] = []

    ## @brief 以斜杠拼接路径
    #  @param parts 路径片段
    #  @return 拼接结果
    def joinPath(self, *parts: str) -> str:
        return "/".join(parts)

    ## @brief 返回 Linux 风格换行符
    #  @return LF
    def newline(self) -> str:
        return "\n"

    ## @brief 返回固定信号映射
    #  @return 信号映射表
    def signalMap(self) -> SignalMapping:
        return {"interrupt": 2, "terminate": 15}

    ## @brief 返回固定时钟值
    #  @return 零值
    def monotonicClock(self) -> float:
        return 0.0

    ## @brief 记录调用并返回预设锁结果
    #  @param filePath 锁文件路径
    #  @return 预设的锁句柄或 None
    def lockFile(self, filePath: str) -> BinaryIO | None:
        self.lockCalls.append(filePath)
        return self.lockResult
