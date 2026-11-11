"""TCP 底层通信封装：组帧、切帧与收发。"""
from __future__ import annotations

import json

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_socket import ISocket


## @brief TCP 通信封装；负责单帧字节上限、\n 切帧与 JSON 解析
class TcpComm:
    ## @brief 构造通信封装
    #  @param socket 套接字实现（注入）
    #  @param maxFrameSize 单帧字节上限，构造注入，禁止读取配置
    #  @param logger 可选日志器
    def __init__(self, socket: ISocket, maxFrameSize: int, logger: ILogger | None = None) -> None:
        ## @brief 注入的套接字
        self._socket: ISocket = socket
        ## @brief 单帧字节上限，由上层构造注入
        self._maxFrameSize: int = maxFrameSize
        ## @brief 注入的日志器
        self._logger: ILogger | None = logger

    ## @brief 发送原始字节，失败由返回值表达
    #  @param data 待发送字节
    #  @return 发送成功返回 True
    def send(self, data: bytes) -> bool:
        return self._socket.send(data)

    ## @brief 阻塞接收一段数据
    #  @return 接收到的原始字节
    def recv(self) -> bytes:
        return self._socket.recv()

    ## @brief 关闭底层套接字
    #  @return 无
    def close(self) -> None:
        self._socket.close()

    ## @brief 把帧字典组为出网字节；出网 JSON 键由调用方按协议原文组装，末尾追加 \n
    #  @param frame 已用协议键名组装的帧字典
    #  @return 可发送的字节
    def encodeFrame(self, frame: dict[str, object]) -> bytes:
        return json.dumps(frame, ensure_ascii=False).encode("utf-8") + b"\n"

    ## @brief 按 \n 切分缓冲；返回完整帧与剩余未完整数据
    #  @param buffer 当前接收缓冲
    #  @return 完整帧列表与剩余缓冲
    def splitFrames(self, buffer: bytes) -> tuple[list[bytes], bytes]:
        if b"\n" not in buffer:
            return [], buffer
        *parts, rest = buffer.split(b"\n")
        frames = [part for part in parts if part]
        return frames, rest

    ## @brief 解析单帧；超长或非法 JSON 抛 FRAME_PARSE
    #  @param raw 单帧原始字节
    #  @return 解析后的信号字典
    #  @raises EdgeError 帧超长或 JSON 解析失败时抛出，code=FRAME_PARSE
    def decodeAndParse(self, raw: bytes) -> dict[str, object]:
        if len(raw) > self._maxFrameSize:
            raise EdgeError(ErrorCode.FRAME_PARSE, f"单帧超长 {len(raw)} > {self._maxFrameSize}")
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise EdgeError(ErrorCode.FRAME_PARSE, f"帧解析失败: {exc}")
