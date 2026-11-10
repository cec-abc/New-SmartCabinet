"""平台适配器接口定义：路径、换行符、信号、时钟与文件锁。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

## @brief 统一信号名到平台信号编号的映射
SignalMapping = dict[str, int]


## @brief 平台差异契约；全项目平台分支只允许出现在 PlatformFactory
class IPlatformAdapter(ABC):
    ## @brief 按平台规则拼接路径
    #  @param parts 路径片段
    #  @return 拼接后的路径
    @abstractmethod
    def joinPath(self, *parts: str) -> str:
        ...

    ## @brief 返回平台换行符
    #  @return 换行符
    @abstractmethod
    def newline(self) -> str:
        ...

    ## @brief 返回统一信号名到平台信号编号的映射
    #  @return 信号映射表
    @abstractmethod
    def signalMap(self) -> SignalMapping:
        ...

    ## @brief 返回高精度单调时钟
    #  @return 单调时钟秒值
    @abstractmethod
    def monotonicClock(self) -> float:
        ...

    ## @brief 非阻塞获取文件锁；句柄由调用方持有，关闭即释放
    #  @param filePath 锁文件路径
    #  @return 锁文件句柄；已被占用时返回 None
    @abstractmethod
    def lockFile(self, filePath: str) -> BinaryIO | None:
        ...
