"""控制层门面：按注入 asyncHandlers 分发、统一链路决策与一键停机严格串行。"""
from __future__ import annotations

from collections.abc import Callable

from edge.base.base_service import BaseService
from edge.control.event_cache import CachedEvent, EventCache, FrameSender
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import (
    AckFrame,
    DecodedSignal,
    ICaptureSink,
    IRecognitionSink,
    SignalSink,
)

## @brief 注入的异步指令处理器
AsyncHandler = Callable[[DecodedSignal], None]
## @brief 失败应答帧构造器（注入）
FailureFrameBuilder = Callable[[int, Exception], CachedEvent]
## @brief 信号类型键（协议保留键，不是业务字符串）
SIGNAL_TYPE_KEY: str = "type"
## @brief 请求标识键（协议保留键）
REQUEST_ID_KEY: str = "requestId"
## @brief 停机步骤：采集
STOP_USB: str = "USB"
## @brief 停机步骤：识别
STOP_RECOGNITION: str = "RECOGNITION"
## @brief 停机步骤：通信
STOP_TCP: str = "TCP"
## @brief 停机步骤：日志
STOP_LOG: str = "LOG"
## @brief 一键停机严格串行顺序
STOP_ORDER: tuple[str, str, str, str] = (STOP_USB, STOP_RECOGNITION, STOP_TCP, STOP_LOG)
## @brief 日志模块名
MODULE_NAME: str = "EdgeControl"


## @brief 装配前的空动作，避免未绑定时误触发
#  @return 无
def idleAction() -> None:
    return None


## @brief 装配前的空触发器
#  @param workerId 线程编号
#  @param requestId 请求标识
#  @return 恒为 False
def idleTrigger(workerId: int, requestId: str) -> bool:
    return False


## @brief 装配期填充的三个模块协作动作；EdgeControl 不直接 import modules/*
class ModuleWiring:
    ## @brief 构造空接线
    def __init__(self) -> None:
        ## @brief 初始化模块（不启业务线程）
        self.initializeModules: Callable[[], None] = idleAction
        ## @brief 启动链路（tcp 只拉重连线程）
        self.startLink: Callable[[], None] = idleAction
        ## @brief 启动采集
        self.startCapture: Callable[[], None] = idleAction
        ## @brief 按 workerId 触发识别
        self.triggerRecognition: Callable[[int, str], bool] = idleTrigger
        ## @brief 停机动作表，键与 STOP_ORDER 一致
        self.stopActions: dict[str, Callable[[], None]] = {}


## @brief 跨模块协调者；实现三个 Sink，只做轻量分发与入队
class EdgeControl(BaseService, SignalSink, ICaptureSink, IRecognitionSink):
    ## @brief 构造控制层
    #  @param logger 日志器（注入）
    #  @param asyncHandlers 注入的信号键到处理器映射
    #  @param wiring 装配期填充的模块协作动作
    #  @param cache 事件缓存（注入）
    #  @param frameSender 帧发送器（注入）
    #  @param failureFrameBuilder 失败应答构造器（注入）
    def __init__(self, logger: ILogger, asyncHandlers: dict[str, AsyncHandler],
                 wiring: ModuleWiring, cache: EventCache, frameSender: FrameSender,
                 failureFrameBuilder: FailureFrameBuilder) -> None:
        ## @brief 日志器
        self._logger: ILogger = logger
        ## @brief 注入的分发表
        self._asyncHandlers: dict[str, AsyncHandler] = asyncHandlers
        ## @brief 模块协作接线
        self._wiring: ModuleWiring = wiring
        ## @brief 事件缓存
        self._cache: EventCache = cache
        ## @brief 帧发送器
        self._frameSender: FrameSender = frameSender
        ## @brief 失败应答构造器
        self._failureFrameBuilder: FailureFrameBuilder = failureFrameBuilder
        ## @brief 当前请求标识，routeSignal 内只提取一次
        self._requestId: str = ""
        ## @brief 链路就绪标记，由 Sink 宣告维护
        self._linkUp: bool = False
        ## @brief 待发送应答队列（回调内只入队）
        self._outbox: list[CachedEvent] = []
        ## @brief 停机步骤轨迹，供验收举证
        self._stopTrace: list[str] = []

    ## @brief 生命周期初始化：只初始化模块，不启采集/识别线程（D-02）
    #  @return 无
    def init(self) -> None:
        self._wiring.initializeModules()

    ## @brief 生命周期启动：只拉起链路重连线程（D-02）
    #  @return 无
    def start(self) -> None:
        self._wiring.startLink()

    ## @brief 生命周期停止：转交严格串行停机
    #  @return 无
    def stop(self) -> None:
        self.stopSystem()

    ## @brief 系统启动统一入口
    #  @return 无
    def startSystem(self) -> None:
        self.init()
        self.start()
        self._logger.info(MODULE_NAME, "系统启动完成, 业务线程待链路 UP 后拉起")

    ## @brief 一键停机：严格串行 USB → RECOGNITION → TCP → LOG，不并行
    #  @return 无
    def stopSystem(self) -> None:
        self._stopTrace = []
        for step in STOP_ORDER:
            self._wiring.stopActions[step]()
            self._stopTrace.append(step)
        ## stop() 的统计信息使用 info
        self._logger.info(MODULE_NAME, f"停机统计 顺序={'-'.join(self._stopTrace)}")

    ## @brief 按注入的 asyncHandlers 键分发；门面不感知具体业务字符串
    #  @param signal 已解码信号帧
    #  @return 命中处理器返回 True
    def routeSignal(self, signal: DecodedSignal) -> bool:
        signalType = str(signal.get(SIGNAL_TYPE_KEY, ""))
        handler = self._asyncHandlers.get(signalType)
        if handler is None:
            self._logger.error(MODULE_NAME, f"未注册的信号键: {signalType}")
            return False
        ## reqId 只提取一次；handler 调用提平在锁外，避免深嵌套
        self._requestId = str(signal.get(REQUEST_ID_KEY, ""))
        handler(signal)
        return True

    ## @brief 自检预留空接口（D-01）；带模块前缀规避全局重名
    #  @return 无
    def selfCheckSystem(self) -> None:
        # TODO: 自检逻辑后续实现时另起独立线程，不占用业务线程与主线程
        return None

    ## @brief TCP 信号回调：轻量转发到分发表
    #  @param signal 已解码信号
    #  @return 无
    def onSignalDecoded(self, signal: DecodedSignal) -> None:
        self.routeSignal(signal)

    ## @brief 坏帧回调：只记日志
    #  @param exception 解析异常
    #  @return 无
    def onFrameError(self, exception: Exception) -> None:
        self._logger.error(MODULE_NAME, "帧解析失败", exception=exception)

    ## @brief 链路断开宣告：只切换缓存开关，停线程与重连由 c3 状态机去重处理
    #  @param reason 断开原因
    #  @param source 宣告来源
    #  @return 无
    def onLinkDown(self, reason: str, source: str) -> None:
        self._linkUp = False
        self._logger.error(MODULE_NAME, f"链路断开 reason={reason} source={source}")

    ## @brief 链路恢复通知：按 event_cache.enabled 补发或丢弃
    #  @return 无
    def onLinkUp(self) -> None:
        self._linkUp = True
        flushed = self._cache.flush(self._frameSender)
        self._logger.info(MODULE_NAME, f"链路恢复 补发 {flushed} 条")

    ## @brief 采集成功回调：只做轻量触发，禁止在此执行阻塞 IO
    #  @param workerId 线程编号
    #  @param path 采集目录
    #  @return 无
    def onCaptureSuccess(self, workerId: int, path: str) -> None:
        self._wiring.triggerRecognition(workerId, self._requestId)
        self._logger.info(MODULE_NAME, f"采集完成 worker={workerId} dir={path}")

    ## @brief 采集失败回调：只记日志并入队失败应答
    #  @param workerId 线程编号
    #  @param exception 采集异常
    #  @return 无
    def onCaptureError(self, workerId: int, exception: Exception) -> None:
        self._logger.error(MODULE_NAME, f"采集失败 worker={workerId}", exception=exception)
        self.enqueueFrame(self._failureFrameBuilder(workerId, exception))

    ## @brief 识别完成回调：只入队，不在此发送
    #  @param workerId 线程编号
    #  @param ack 应答帧
    #  @param requestId 上位机请求标识
    #  @return 无
    def onRecognitionResult(self, workerId: int, ack: AckFrame,
                            requestId: str) -> None:
        self.enqueueFrame(dict(ack))
        self._logger.info(MODULE_NAME, f"识别完成 worker={workerId} req={requestId}")

    ## @brief 识别失败回调：只记日志并入队失败应答
    #  @param workerId 线程编号
    #  @param exception 推理异常
    #  @return 无
    def onRecognitionError(self, workerId: int, exception: Exception) -> None:
        self._logger.error(MODULE_NAME, f"识别失败 worker={workerId}", exception=exception)
        self.enqueueFrame(self._failureFrameBuilder(workerId, exception))

    ## @brief 应答入队（轻量）
    #  @param frame 应答帧
    #  @return 无
    def enqueueFrame(self, frame: CachedEvent) -> None:
        self._outbox.append(frame)

    ## @brief 由调用方在非回调上下文统一分发；UP 直发，DOWN 入缓存
    #  @return 本次分发条数
    def dispatchOutbox(self) -> int:
        pending = self._outbox
        self._outbox = []
        for frame in pending:
            if self._linkUp:
                ## send 返回 False 时不检查，链路断由 onLinkDown 感知
                self._frameSender(frame)
            else:
                self._cache.cacheEvent(frame)
        return len(pending)

    ## @brief 供验收举证：注入的信号键
    #  @return 键列表
    def getHandlerKeys(self) -> list[str]:
        return sorted(self._asyncHandlers)

    ## @brief 供验收举证：停机轨迹
    #  @return 步骤列表
    def getStopTrace(self) -> list[str]:
        return list(self._stopTrace)

    ## @brief 供验收举证：待分发条数
    #  @return 队列长度
    def getOutboxCount(self) -> int:
        return len(self._outbox)

    ## @brief 供验收举证：链路就绪标记
    #  @return 就绪返回 True
    def isLinkUp(self) -> bool:
        return self._linkUp

    ## @brief 供验收举证：当前请求标识
    #  @return 请求标识
    def getRequestId(self) -> str:
        return self._requestId
