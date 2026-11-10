"""边缘计算项目统一异常定义：唯一异常类与业务异常码枚举。"""
from __future__ import annotations

from enum import IntEnum


## @brief 业务异常码；新增异常只加枚举值，不改异常类结构
class ErrorCode(IntEnum):
    ## @brief 配置、进程锁等静态错误
    CONFIG = 1
    ## @brief 链路断开
    LINK_DOWN = 2
    ## @brief 协议帧解析失败
    FRAME_PARSE = 3
    ## @brief 推理超时
    INFERENCE_TIMEOUT = 4
    ## @brief 图像采集失败
    CAPTURE = 5


## @brief 全项目唯一业务异常类型，日志侧可用 code.name 输出异常码
class EdgeError(Exception):
    ## @brief 构造业务异常
    #  @param code 业务异常码
    #  @param message 异常描述
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(f"[{code.name}] {message}")
        ## @brief 业务异常码
        self.code: ErrorCode = code
