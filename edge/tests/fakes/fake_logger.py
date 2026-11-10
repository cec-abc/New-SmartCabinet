"""日志接口 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_logger import FrameData, ILogger


## @brief 只记录调用、不做落盘的日志 Fake
class FakeLogger(ILogger):
    ## @brief 构造 Fake
    def __init__(self) -> None:
        ## @brief 接收帧记录
        self.rxRecords: list[tuple[str, FrameData]] = []
        ## @brief 发送帧记录
        self.txRecords: list[tuple[str, FrameData]] = []
        ## @brief 信息日志记录
        self.infoRecords: list[tuple[str, str]] = []
        ## @brief 错误日志记录
        self.errorRecords: list[tuple[str, str, Exception | None]] = []

    ## @brief 记录接收帧
    #  @param module 模块名
    #  @param data 帧数据
    #  @return 无
    def rx(self, module: str, data: FrameData) -> None:
        self.rxRecords.append((module, data))

    ## @brief 记录发送帧
    #  @param module 模块名
    #  @param data 帧数据
    #  @return 无
    def tx(self, module: str, data: FrameData) -> None:
        self.txRecords.append((module, data))

    ## @brief 记录普通信息
    #  @param module 模块名
    #  @param msg 日志内容
    #  @return 无
    def info(self, module: str, msg: str) -> None:
        self.infoRecords.append((module, msg))

    ## @brief 记录错误与可选异常
    #  @param module 模块名
    #  @param msg 日志内容
    #  @param exception 可选异常对象
    #  @return 无
    def error(self, module: str, msg: str, exception: Exception | None = None) -> None:
        self.errorRecords.append((module, msg, exception))
