# @file logger_setup.py
# @brief 日志独立封装：视觉主控与 TCP 通信日志隔离落盘。
#
# @details 封装 RotatingFileHandler，按模块名将日志分流到 vision.log 与 tcp.log；
#          所有参数均由构造者（main.py）从 config.ini 读取后传入，本文件不 import
#          任何项目内模块（config_loader / vision_core / tcp_comm 等），保持高内聚低耦合。
#          不做冗余保护：目录存在性交由 main 保证，log_level 非法直接抛异常暴露。

import logging
import logging.handlers
import os
import sys


## @brief 日志配置管理器
## @details 封装 RotatingFileHandler，实现视觉主控与 TCP 通信日志的隔离落盘。
class LogManager:
    ## @brief 构造日志管理器
    ## @param [in] log_level 根日志级别字符串，如 "INFO"
    ## @param [in] output_dir 日志输出目录（由 main 保证已存在）
    ## @param [in] vision_file 视觉与主调度日志文件名
    ## @param [in] tcp_file TCP 通信日志文件名
    ## @param [in] max_bytes 单文件最大字节数（来自 config.ini，零硬编码）
    ## @param [in] backup_count 循环备份文件数量（来自 config.ini，零硬编码）
    ## @param [in] console_enable 是否向控制台输出
    ## @return None
    def __init__(self, log_level: str, output_dir: str, vision_file: str,
                 tcp_file: str, max_bytes: int, backup_count: int,
                 console_enable: bool) -> None:
        self._level = log_level
        self._output_dir = output_dir
        self._vision_file = vision_file
        self._tcp_file = tcp_file
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        self._console_enable = console_enable
        # 统一格式器：构造一次，setup 中复用（变量复用红线）
        self._fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s")

    ## @brief 初始化日志系统
    ## @details 挂载根节点（视觉主控：__main__ / vision_core）与 tcp_comm 分支，
    ##          并阻断 tcp_comm 向上传播，实现两类日志隔离落盘。log_level 经
    ##          getattr(logging, self._level) 解析，填错即抛异常，不写兜底。
    ## @return None
    def setup(self) -> None:
        # 级别解析：填错直接 AttributeError 暴露，不做 try/except 兜底
        level = getattr(logging, self._level)

        # 统一格式器复用（self._fmt）
        vision_handler = logging.handlers.RotatingFileHandler(
            os.path.join(self._output_dir, self._vision_file),
            maxBytes=self._max_bytes, backupCount=self._backup_count)
        vision_handler.setFormatter(self._fmt)

        tcp_handler = logging.handlers.RotatingFileHandler(
            os.path.join(self._output_dir, self._tcp_file),
            maxBytes=self._max_bytes, backupCount=self._backup_count)
        tcp_handler.setFormatter(self._fmt)

        # 控制台 Handler（按需创建，默认不输出）
        console_handler = None
        if self._console_enable:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self._fmt)

        # 根节点绑定 vision_handler + 控制台（如有）：承接 __main__ / vision_core
        handlers = [vision_handler]
        if console_handler is not None:
            handlers.append(console_handler)
        logging.basicConfig(level=level, handlers=handlers)

        # TCP 分支绑定 tcp_handler + 控制台（如有），并阻断向上传播
        tcp_logger = logging.getLogger("tcp_comm")
        tcp_logger.setLevel(level)
        tcp_logger.addHandler(tcp_handler)
        if console_handler is not None:
            tcp_logger.addHandler(console_handler)
        tcp_logger.propagate = False
