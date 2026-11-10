"""进程单文件锁：防止双开与端口占用，平台差异由注入的适配器提供。"""
from __future__ import annotations

import sys
from typing import BinaryIO

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_platform import IPlatformAdapter

## @brief 默认锁文件名；main.py 拿锁早于读取配置，故使用固定常量
DEFAULT_LOCK_FILE_NAME = "edge_runtime.lock"


## @brief 进程单文件锁，锁句柄随对象生命周期持有
class ProcessFileLock:
    ## @brief 构造进程锁
    #  @param adapter 平台适配器，提供文件锁实现
    #  @param lockFilePath 锁文件路径
    def __init__(self, adapter: IPlatformAdapter, lockFilePath: str) -> None:
        ## @brief 平台适配器
        self.adapter = adapter
        ## @brief 锁文件路径
        self.lockFilePath = lockFilePath
        ## @brief 锁文件句柄；None 表示当前未持锁
        self.lockHandle: BinaryIO | None = None

    ## @brief 获取锁；失败抛业务异常
    #  @return 无
    #  @raises EdgeError 锁被占用或平台骨架未实现时抛出
    def acquire(self) -> None:
        try:
            lockHandle = self.adapter.lockFile(self.lockFilePath)
        except NotImplementedError as error:
            ## Linux 骨架抛出的内置异常不跨模块边界，统一转成业务异常
            raise EdgeError(ErrorCode.CONFIG, "平台文件锁尚未实现") from error
        if lockHandle is None:
            raise EdgeError(ErrorCode.CONFIG, "已有实例运行，进程锁获取失败")
        self.lockHandle = lockHandle

    ## @brief 获取锁；失败立即退出进程，供 main.py 第一件事调用
    #  @return 无
    def acquireOrExit(self) -> None:
        try:
            self.acquire()
        except EdgeError as error:
            sys.exit(f"[{error.code.name}] {error}")

    ## @brief 释放锁；重复调用安全
    #  @return 无
    def release(self) -> None:
        if self.lockHandle is not None:
            self.lockHandle.close()
            self.lockHandle = None
