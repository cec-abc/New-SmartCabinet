"""套接字接口定义；setOption 不进接口，由 TcpSocket.__init__ 收敛。"""
from __future__ import annotations

from abc import ABC, abstractmethod


## @brief TCP 连接契约，只暴露收发与生命周期动作
class ISocket(ABC):
    ## @brief 建立连接
    #  @return 无
    @abstractmethod
    def connect(self) -> None:
        ...

    ## @brief 阻塞接收一段数据
    #  @return 接收到的原始字节
    @abstractmethod
    def recv(self) -> bytes:
        ...

    ## @brief 发送数据；失败用返回值表达，由链路状态机感知
    #  @param data 待发送字节
    #  @return 发送成功返回 True
    @abstractmethod
    def send(self, data: bytes) -> bool:
        ...

    ## @brief 关闭连接
    #  @return 无
    @abstractmethod
    def close(self) -> None:
        ...
