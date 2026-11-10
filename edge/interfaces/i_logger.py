"""日志接口定义：对外仅 rx / tx / info / error 四个方法。"""
from __future__ import annotations

from abc import ABC, abstractmethod


## @brief 日志契约，实现类必须异步消费、不得在调用线程做阻塞落盘
class ILogger(ABC):
    ## @brief 记录接收帧
    #  @param module 模块名
    #  @param data 帧数据（解析后的字典或原始字节）
    #  @return 无
    @abstractmethod
    def rx(self, module: str, data: dict[str, object] | bytes) -> None:
        ...

    ## @brief 记录发送帧
    #  @param module 模块名
    #  @param data 帧数据（解析后的字典或原始字节）
    #  @return 无
    @abstractmethod
    def tx(self, module: str, data: dict[str, object] | bytes) -> None:
        ...

    ## @brief 记录普通信息
    #  @param module 模块名
    #  @param msg 日志内容
    #  @return 无
    @abstractmethod
    def info(self, module: str, msg: str) -> None:
        ...

    ## @brief 记录错误；传入异常时由实现类自动附堆栈
    #  @param module 模块名
    #  @param msg 日志内容
    #  @param exception 可选异常对象
    #  @return 无
    @abstractmethod
    def error(self, module: str, msg: str, exception: Exception | None = None) -> None:
        ...
