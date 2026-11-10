"""配置接口 Fake 实现。"""
from __future__ import annotations

from typing import Any

from edge.interfaces.i_config import IConfig


## @brief 内存配置 Fake，契约验证用
class FakeConfig(IConfig):
    ## @brief 构造 Fake
    #  @param values 预设配置值，键为「节名.键名」
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        ## @brief 预设配置值
        self.values: dict[str, Any] = values if values is not None else {}
        ## @brief get 调用记录
        self.calls: list[tuple[str, str, Any]] = []

    ## @brief 读取配置项并记录调用
    #  @param section 配置节名
    #  @param key 配置键名
    #  @param default 默认值
    #  @return 配置值
    def get(self, section: str, key: str, default: Any = None) -> Any:
        self.calls.append((section, key, default))
        return self.values.get(f"{section}.{key}", default)
