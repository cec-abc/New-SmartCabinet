"""通用服务生命周期基类：init / start / stop 三件套供模块门面多态实现。"""
from __future__ import annotations

from abc import ABC


## @brief 三个 Controller 的生命周期基类；默认空实现，子类按需覆盖
class BaseService(ABC):
    ## @brief 初始化资源，基类默认无操作
    #  @return 无
    def init(self) -> None:
        return None

    ## @brief 启动服务，基类默认无操作
    #  @return 无
    def start(self) -> None:
        return None

    ## @brief 停止服务，基类默认无操作
    #  @return 无
    def stop(self) -> None:
        return None
