"""TCP 客户端套接字：边缘机主动连上位机，收发协议帧，超时与断链语义在此收敛。"""
from __future__ import annotations

import socket

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_socket import ISocket

## @file edge/modules/tcp/tcp_socket.py
## @brief TCP 客户端套接字：边缘机主动连上位机，收发协议帧，超时与断链语义在此收敛
## @author 袁燕

## @brief 单次接收的最大字节数
RECV_BUFFER_SIZE: int = 65536
## @brief 套接字选项的启用取值；三个选项都用同一个值，避免散落的数字
SOCKET_OPTION_ENABLED: int = 1
## @brief 套接字选项：地址复用；Windows 与 Linux 取值一致，无平台差异
SOCKET_OPTION_REUSE_ADDRESS: int = socket.SO_REUSEADDR
## @brief 套接字选项：保活探测；Windows 与 Linux 取值一致，无平台差异
SOCKET_OPTION_KEEP_ALIVE: int = socket.SO_KEEPALIVE
## @brief 套接字选项：关闭 Nagle 算法；Windows 与 Linux 取值一致，无平台差异
SOCKET_OPTION_NO_DELAY: int = socket.TCP_NODELAY
## @brief 套接字协议层：TCP
SOCKET_PROTOCOL_TCP: int = socket.IPPROTO_TCP


## @brief 真实 TCP 客户端套接字；实现 ISocket，供边缘机连上位机监听端口
#  @note 三个套接字选项在 Windows 与 Linux 上取值一致，无需平台分支；
#        平台差异的收敛点仍在 platform/adapter.py，本模块不出现平台判断。
class TcpSocket(ISocket):
    ## @brief 构造套接字；地址、端口与超时全部构造注入
    #  @param host 上位机地址
    #  @param port 上位机端口
    #  @param connectTimeoutSec 连接超时秒数
    #  @param recvTimeoutSec 接收超时秒数
    #  @return 无
    def __init__(self, host: str, port: int,
                 connectTimeoutSec: float, recvTimeoutSec: float) -> None:
        ## @brief 上位机地址
        self._host: str = host
        ## @brief 上位机端口
        self._port: int = port
        ## @brief 连接超时秒数
        self._connectTimeoutSec: float = connectTimeoutSec
        ## @brief 接收超时秒数
        self._recvTimeoutSec: float = recvTimeoutSec
        ## @brief 已建立的连接；None 表示当前未连接
        self._socket: socket.socket | None = None

    ## @brief 建立连接；先关掉旧连接再重连，保证每次连的都是新会话
    #  @return 无
    #  @raises EdgeError 建连失败时抛出，code=LINK_DOWN
    def connect(self) -> None:
        self.close()
        try:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as error:
            ## 内置异常跨模块边界前统一转业务异常
            raise EdgeError(ErrorCode.LINK_DOWN, f"创建套接字失败: {error}") from error
        try:
            connection.setsockopt(
                socket.SOL_SOCKET, SOCKET_OPTION_REUSE_ADDRESS, SOCKET_OPTION_ENABLED,
            )
            connection.setsockopt(
                socket.SOL_SOCKET, SOCKET_OPTION_KEEP_ALIVE, SOCKET_OPTION_ENABLED,
            )
            connection.setsockopt(
                SOCKET_PROTOCOL_TCP, SOCKET_OPTION_NO_DELAY, SOCKET_OPTION_ENABLED,
            )
            connection.settimeout(self._connectTimeoutSec)
            connection.connect((self._host, self._port))
        except OSError as error:
            connection.close()
            raise EdgeError(
                ErrorCode.LINK_DOWN,
                f"连接上位机 {self._host}:{self._port} 失败: {error}",
            ) from error
        ## 连上后按接收超时轮询，避免解码线程被永久阻塞
        connection.settimeout(self._recvTimeoutSec)
        self._socket = connection

    ## @brief 阻塞接收一段数据
    #  @return 接收到的原始字节
    #  @raises TimeoutError 接收超时；这是正常轮询节拍，不算断链，
    #          且只在 tcp 模块内部流转，由解码线程消化，不穿越模块边界
    #  @raises EdgeError 链路断开时抛出，code=LINK_DOWN
    def recv(self) -> bytes:
        current = self._socket
        if current is None:
            raise EdgeError(ErrorCode.LINK_DOWN, "套接字未连接")
        try:
            data = current.recv(RECV_BUFFER_SIZE)
        except socket.timeout as error:
            ## 接收超时是正常节拍，交给上层继续等，不当成断链
            raise TimeoutError(
                f"接收上位机数据超时 {self._recvTimeoutSec}s",
            ) from error
        except OSError as error:
            raise EdgeError(ErrorCode.LINK_DOWN, f"接收数据失败: {error}") from error
        if not data:
            ## 对端关闭连接属于真实断链，交给上层宣告断链并重连
            raise EdgeError(ErrorCode.LINK_DOWN, "上位机已关闭连接")
        return data

    ## @brief 发送数据；一次写完整帧，失败用返回值表达
    #  @param data 待发送字节
    #  @return 发送成功返回 True
    def send(self, data: bytes) -> bool:
        current = self._socket
        if current is None:
            return False
        try:
            current.sendall(data)
        except OSError:
            ## 发送失败只返回 False，链路断由上层状态机感知
            return False
        return True

    ## @brief 关闭连接；重复调用安全
    #  @return 无
    def close(self) -> None:
        current = self._socket
        self._socket = None
        if current is None:
            return
        try:
            current.close()
        except OSError:
            ## 关闭失败不阻断停机流程
            return
