"""套接字接口 Fake 实现。"""
from __future__ import annotations

from edge.interfaces.i_socket import ISocket


## @brief 不建立真实连接、只记录收发数据的 Fake
class FakeSocket(ISocket):
    ## @brief 构造 Fake
    #  @param recvData recv 固定返回的数据
    def __init__(self, recvData: bytes = b"") -> None:
        ## @brief recv 固定返回值
        self.recvData = recvData
        ## @brief 已发送帧记录
        self.sentFrames: list[bytes] = []
        ## @brief 是否已连接
        self.connected = False
        ## @brief 是否已关闭
        self.closed = False

    ## @brief 记录连接动作
    #  @return 无
    def connect(self) -> None:
        self.connected = True

    ## @brief 返回预设数据
    #  @return 预设字节
    def recv(self) -> bytes:
        return self.recvData

    ## @brief 记录发送并返回成功
    #  @param data 待发送字节
    #  @return 固定返回 True
    def send(self, data: bytes) -> bool:
        self.sentFrames.append(data)
        return True

    ## @brief 记录关闭动作
    #  @return 无
    def close(self) -> None:
        self.closed = True
