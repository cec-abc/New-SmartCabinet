"""线程生命周期接口定义。"""
from __future__ import annotations

from abc import ABC, abstractmethod


## @brief 线程生命周期契约，所有线程实现必须继承 BaseThread 后实现
class IThread(ABC):
    ## @brief 启动线程；重复调用必须幂等
    #  @return 无
    @abstractmethod
    def start(self) -> None:
        ...

    ## @brief 请求停止并等待线程退出
    #  @param timeout 等待线程退出的最长秒数
    #  @return 无
    @abstractmethod
    def stop(self, timeout: float = 3.0) -> None:
        ...

    ## @brief 查询线程是否处于运行态
    #  @return 运行中返回 True
    @abstractmethod
    def isRunning(self) -> bool:
        ...
