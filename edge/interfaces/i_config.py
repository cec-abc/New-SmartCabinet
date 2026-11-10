"""配置读取接口定义。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


## @brief 配置读取契约；初版保留 Any 返回值，后续迭代按类型细分
class IConfig(ABC):
    ## @brief 读取指定配置项
    #  @param section 配置节名
    #  @param key 配置键名
    #  @param default 缺失时返回的默认值
    #  @return 配置值；调用方按声明类型使用
    @abstractmethod
    def get(self, section: str, key: str, default: Any = None) -> Any:
        ...
