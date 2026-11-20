"""联调用的真实 TCP 客户端套接字：连桩上位机，让端到端用例走真实网络栈。"""
from __future__ import annotations

import socket

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_socket import ISocket

## @file edge/tests/integration/tcp_client_socket.py
## @brief 联调用的真实 TCP 客户端套接字：连桩上位机，让端到端用例走真实网络栈
## @author 边缘计算项目

## @brief 连接与接收的最长等待秒数
CONNECT_TIMEOUT_SEC: float = 5.0
## @brief 接收轮询超时秒数，与生产配置 recv_timeout_sec 同口径
## @note 接收超时只是"暂时没有数据"的节拍，不是断链；
##       这里必须与生产套接字 edge/modules/tcp/tcp_socket.py 保持一致，
##       否则联调里每静默一段时间就会误判一次断链，解码线程被停掉。
DEFAULT_RECV_TIMEOUT_SEC: float = 0.5


## @brief 真实 TCP 客户端套接字；实现 ISocket，供端到端联调使用
class TcpClientSocket(ISocket):
    ## @brief 构造客户端套接字
    #  @param host 上位机地址
    #  @param port 上位机端口
    #  @param recvTimeoutSec 接收轮询超时秒数
    def __init__(self, host: str, port: int,
                 recvTimeoutSec: float = DEFAULT_RECV_TIMEOUT_SEC) -> None:
        ## @brief 上位机地址
        self._host: str = host
        ## @brief 上位机端口
        self._port: int = port
        ## @brief 接收轮询超时秒数
        self._recvTimeoutSec: float = recvTimeoutSec
        ## @brief 已建立的连接
        self._socket: socket.socket | None = None

    ## @brief 建立连接
    #  @return 无
    #  @raises EdgeError 连接失败时抛出，code=LINK_DOWN
    def connect(self) -> None:
        try:
            self._socket = socket.create_connection(
                (self._host, self._port), timeout=CONNECT_TIMEOUT_SEC,
            )
        except OSError as error:
            ## 内置异常跨模块边界前统一转业务异常
            raise EdgeError(ErrorCode.LINK_DOWN, f"连接上位机失败: {error}") from error
        ## 连上后按接收超时轮询，避免解码线程被永久阻塞
        self._socket.settimeout(self._recvTimeoutSec)

    ## @brief 阻塞接收一段数据
    #  @return 接收到的字节
    #  @raises TimeoutError 接收超时；这是正常轮询节拍，不算断链
    #  @raises EdgeError 链路断开时抛出，code=LINK_DOWN
    def recv(self) -> bytes:
        current = self._socket
        if current is None:
            raise EdgeError(ErrorCode.LINK_DOWN, "套接字未连接")
        try:
            return current.recv(4096)
        except socket.timeout as error:
            ## 接收超时是正常节拍，交给上层继续等，不当成断链
            raise TimeoutError(
                f"接收上位机数据超时 {self._recvTimeoutSec}s",
            ) from error
        except OSError as error:
            raise EdgeError(ErrorCode.LINK_DOWN, f"接收数据失败: {error}") from error

    ## @brief 发送数据；失败用返回值表达
    #  @param data 待发送字节
    #  @return 发送成功返回 True
    def send(self, data: bytes) -> bool:
        current = self._socket
        if current is None:
            return False
        try:
            current.sendall(data)
        except OSError:
            return False
        return True

    ## @brief 关闭连接
    #  @return 无
    def close(self) -> None:
        current = self._socket
        self._socket = None
        if current is not None:
            current.close()
