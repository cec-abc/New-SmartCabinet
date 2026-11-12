"""事件缓存：DOWN 期间缓存必达事件，UP 时按开关补发或丢弃；seq 只填不用。"""
from __future__ import annotations

from collections.abc import Callable

from edge.interfaces.i_logger import ILogger

## @brief 缓存的协议帧
CachedEvent = dict[str, object]
## @brief 帧发送器；返回值由链路状态机感知，本模块不检查
FrameSender = Callable[[CachedEvent], bool]
## @brief 日志模块名
MODULE_NAME = "EventCache"


## @brief DOWN 期间的事件缓存；UP 时按 enabled 补发或丢弃，不做任何按 seq 判重
class EventCache:
    ## @brief 构造缓存
    #  @param enabled 补发开关，由上层读 event_cache.enabled 后注入
    #  @param logger 可选日志器
    def __init__(self, enabled: bool, logger: ILogger | None = None) -> None:
        ## @brief 补发开关
        self._enabled: bool = enabled
        ## @brief 可选日志器
        self._logger: ILogger | None = logger
        ## @brief 按入队顺序保存的缓存事件
        self._events: list[CachedEvent] = []
        ## @brief 下一个 seq，仅递增填充
        self._nextSeq: int = 1

    ## @brief 查询补发开关
    #  @return 开启返回 True
    def isEnabled(self) -> bool:
        return self._enabled

    ## @brief 缓存一条必达事件；seq 只递增填充，不参与去重 / 排序 / 幂等判断
    #  @param event 业务应答或通知帧
    #  @return 无
    def cacheEvent(self, event: CachedEvent) -> None:
        record = dict(event)
        ## 业务 payload 不得占用保留字段；seq 仅作占位填充，不用于任何判断
        record["seq"] = self._nextSeq
        self._nextSeq += 1
        self._events.append(record)

    ## @brief 待补发事件数
    #  @return 当前缓存条数
    def pendingCount(self) -> int:
        return len(self._events)

    ## @brief 返回缓存事件副本，供验收举证
    #  @return 缓存事件列表
    def pendingEvents(self) -> list[CachedEvent]:
        return [dict(event) for event in self._events]

    ## @brief UP 时按开关补发或丢弃并清空缓存；按入队顺序逐条发送，不按 seq 排序
    #  @param sender 帧发送器（注入）
    #  @return 实际补发的条数
    def flush(self, sender: FrameSender) -> int:
        pending = self._events
        self._events = []
        if not self._enabled:
            self.logInfo(f"丢弃断线期间 {len(pending)} 条缓存事件")
            return 0
        for event in pending:
            ## send 返回 False 时不检查，链路断由 onLinkDown 感知
            sender(event)
        self.logInfo(f"补发 {len(pending)} 条缓存事件")
        return len(pending)

    ## @brief 统一的 info 日志出口
    #  @param message 日志内容
    #  @return 无
    def logInfo(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(MODULE_NAME, message)
