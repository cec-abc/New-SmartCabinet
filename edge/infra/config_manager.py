"""INI 配置管理：Fail-Fast 加载、类型推断与双检锁单例。"""
from __future__ import annotations

import configparser
import math
import re
from pathlib import Path
from threading import Lock
from typing import Any

from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_config import IConfig
from edge.interfaces.i_logger import ILogger

## @brief 布尔真值字面量；数字 1 / 0 交给整数分支，不当布尔
TRUE_LITERALS: frozenset[str] = frozenset({"true", "yes", "on"})
## @brief 布尔假值字面量
FALSE_LITERALS: frozenset[str] = frozenset({"false", "no", "off"})
## @brief 多值分隔符，命中即推断为 list
LIST_SEPARATOR: str = ","
## @brief 整数字面量模式，避免把 1 交给浮点分支
INT_PATTERN: re.Pattern[str] = re.compile(r"[+-]?\d+")
## @brief 日志模块名
MODULE_NAME: str = "IniConfigManager"


## @brief 把 INI 原始字符串推断为 bool / int / float / list / str
#  @param raw 原始值
#  @return 推断后的值；无匹配类型时返回原文
def inferValue(raw: str) -> Any:
    text = raw.strip()
    lowered = text.lower()
    if lowered in TRUE_LITERALS:
        return True
    if lowered in FALSE_LITERALS:
        return False
    if INT_PATTERN.fullmatch(text):
        return int(text)
    try:
        number = float(text)
    except ValueError:
        pass
    else:
        ## 非有限值（inf / nan）不认作 float，落回字符串语义
        if math.isfinite(number):
            return number
    if LIST_SEPARATOR in text:
        return [inferValue(item) for item in text.split(LIST_SEPARATOR)]
    return text


## @brief INI 配置读取门面；实现 IConfig，类内双检锁单例，普通构造亦可用于测试
class IniConfigManager(IConfig):
    ## @brief 全局唯一实例，由双检锁保护
    _sharedInstance: IniConfigManager | None = None
    ## @brief 实例构造锁
    _instanceLock: Lock = Lock()

    ## @brief 构造配置管理器；路径与日志器由上层注入
    #  @param configPath INI 文件路径
    #  @param logger 可选日志器，用于 default 分支的 info 记录
    #  @raises EdgeError 文件缺失或 INI 解析失败（CONFIG）
    def __init__(self, configPath: str, logger: ILogger | None = None) -> None:
        super().__init__()
        ## @brief 已推断类型的「节 → 键 → 值」
        self._data: dict[str, dict[str, Any]] = {}
        ## @brief 注入的日志器，可为空
        self._logger: ILogger | None = logger
        self.loadConfig(configPath)

    ## @brief 获取全局唯一实例；首次调用注入路径，双检锁避免并发重复加载
    #  @param configPath INI 文件路径
    #  @param logger 可选日志器
    #  @return 单例
    #  @raises EdgeError 首次加载失败时由构造抛出（CONFIG）
    @classmethod
    def instance(cls, configPath: str, logger: ILogger | None = None) -> IniConfigManager:
        shared = cls._sharedInstance
        if shared is None:
            with cls._instanceLock:
                shared = cls._sharedInstance
                if shared is None:
                    shared = cls(configPath, logger)
                    cls._sharedInstance = shared
        return shared

    ## @brief 读取并解析 INI；失败一律转 EdgeError(CONFIG) 阻断启动
    #  @param configPath INI 文件路径
    #  @return 无
    #  @raises EdgeError 文件缺失、不可读或解析失败（CONFIG）
    def loadConfig(self, configPath: str) -> None:
        path = Path(configPath)
        if not path.is_file():
            raise EdgeError(ErrorCode.CONFIG, f"配置文件缺失: {configPath}")
        parser = configparser.ConfigParser(interpolation=None)
        try:
            with path.open(encoding="utf-8") as stream:
                parser.read_file(stream)
        except (OSError, UnicodeError, configparser.Error) as error:
            ## 编码错误与解析错误都属于内置异常，出模块边界前一并转 EdgeError
            raise EdgeError(ErrorCode.CONFIG, f"配置解析失败: {error}") from error
        for section in parser.sections():
            self._data[section] = {
                key: inferValue(value) for key, value in parser.items(section)
            }

    ## @brief 读取配置项；缺失且无 default 抛异常，有 default 记 info 并返回
    #  @param section 配置节名
    #  @param key 配置键名
    #  @param default 缺失时返回的默认值；为 None 视为未提供
    #  @return 已推断类型的配置值或默认值
    #  @raises EdgeError 缺失且未提供 default（CONFIG）
    def get(self, section: str, key: str, default: Any = None) -> Any:
        sectionData = self._data.get(section)
        if sectionData is not None and key in sectionData:
            return sectionData[key]
        if default is None:
            raise EdgeError(ErrorCode.CONFIG, f"配置项缺失: [{section}] {key}")
        if self._logger is not None:
            self._logger.info(
                MODULE_NAME, f"配置项 [{section}] {key} 缺失，使用默认值 {default}"
            )
        return default
