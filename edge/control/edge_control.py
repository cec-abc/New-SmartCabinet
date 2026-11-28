"""控制层门面：按注入 asyncHandlers 分发、统一链路决策与一键停机严格串行。"""
from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from time import monotonic

from edge.base.base_service import BaseService
from edge.control.edge_dispatch_thread import EdgeDispatchThread
from edge.exceptions import EdgeError, ErrorCode
from edge.interfaces.i_frame_sink import IFrameSink
from edge.interfaces.i_logger import ILogger
from edge.interfaces.i_sinks import (
    AckFrame,
    DecodedSignal,
    ICaptureSink,
    IRecognitionSink,
    SignalSink,
)
from edge.modules.recognition.recognition_modes import (
    DEDUP_BEST_CONFIDENCE,
    DEDUP_FIRST,
)

## @file edge/control/edge_control.py
## @brief 控制层门面：信号分发、重复请求复用应答、链路决策与一键停机严格串行
## @author 袁燕

## @brief 协议帧类型；本控制层及装配层共用该别名
CachedEvent = dict[str, object]
## @brief 帧发送器；返回值由链路状态机感知
FrameSender = Callable[[CachedEvent], bool]
## @brief 注入的异步指令处理器
AsyncHandler = Callable[[DecodedSignal], None]
## @brief 失败应答帧构造器（注入）
FailureFrameBuilder = Callable[[int, Exception], CachedEvent]
## @brief 降级条目提供器：按采集线程编号给出该线程应上报的未识别条目
DegradedItemsProvider = Callable[[int], list[object]]
## @brief 信号类型键（协议保留键，不是业务字符串）
SIGNAL_TYPE_KEY: str = "type"
## @brief 内部帧用的请求标识键；协议帧统一用 request_id，取不到时才改用这个内部键
REQUEST_ID_KEY: str = "requestId"
## @brief 协议请求标识键（上位机原文 request_id）
WIRE_REQUEST_ID_KEY: str = "request_id"
## @brief 日志里保留的未知字段摘要最大字符数，防止网络超长字段撑爆日志队列
MAX_LOG_TEXT_CHARS: int = 64
## @brief 已完成请求的应答记录条数上限，超限丢弃最旧
MAX_COMPLETED_REQUESTS: int = 32
## @brief 在途聚合表条数上限，超限丢弃最旧的请求
MAX_AGGREGATION_ENTRIES: int = 32
## @brief 待发送应答队列条数上限，超限丢弃最旧，避免链路长期断开时无限增长
MAX_OUTBOX_FRAMES: int = 1024
## @brief 采集线程编号的起始值
FIRST_WORKER_ID: int = 1
## @brief 降级出帧时表示"整轮采集都没跑起来"的哨兵值，不是实际线程编号
NO_WORKER_ID: int = 0
## @brief 停止应答排空线程时等待其退出的最长秒数
THREAD_STOP_TIMEOUT_SEC: float = 3.0
## @brief 应答帧类型标识
ACK_FRAME_TYPE: str = "recognize_ack"
## @brief 协议帧的请求标识键名；与取号用的键同源，避免两处写死同一个字符串
WIRE_REQUEST_ID_FIELD: str = WIRE_REQUEST_ID_KEY
## @brief 协议帧的清单键名
WIRE_ITEMS_FIELD: str = "items"
## @brief 清单条目的工具编号键；用于全未知帧判定
ITEM_TOOL_ID_FIELD: str = "tool_id"
## @brief 清单条目的告警类型键；用于全未知帧判定
ITEM_ALERT_FIELD: str = "alert_type"
## @brief 清单条目的置信度键；出帧前逐键规范化时使用
ITEM_CONFIDENCE_FIELD: str = "confidence"
## @brief 条目字段非法时的空工具编号
EMPTY_TOOL_ID: str = ""
## @brief 条目字段非法时的空置信度
EMPTY_CONFIDENCE: float = 0.0
## @brief 条目字段非法时按未知告警处理
INVALID_ITEM_ALERT: str = "unknown"
## @brief 合法告警类型五值全集，与协议枚举一致
VALID_ALERT_TYPES: frozenset[str] = frozenset(
    {"none", "misplaced", "unknown", "missing", "low_confidence"},
)
## @brief 全未知告警值；与识别模块 ALERT_UNKNOWN 同值
ITEM_ALERT_UNKNOWN: str = "unknown"
## @brief 协议条目的货位号键名
WIRE_POSITION_FIELD: str = "position"
## @brief 边缘内部字段，顶层帧里不得出现
INTERNAL_WORKER_FIELD: str = "workerId"
## @brief 边缘内部字段，顶层帧里不得出现
INTERNAL_REQUEST_FIELD: str = REQUEST_ID_KEY
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
## @brief 聚合等待上限秒数：超过该时长仍未收齐就降级出帧
DEFAULT_AGGREGATION_TIMEOUT_SEC: float = 5.0


## @brief 装配前的空动作，避免未绑定时误触发
#  @return 无
def idleAction() -> None:
    return None


## @brief 装配前的空降级条目提供器；没有对照表信息时不产出任何条目
#  @param workerId 线程编号
#  @return 恒为空列表
def emptyDegradedItems(workerId: int) -> list[object]:
    return []


## @brief 装配前的空触发器
#  @param workerId 线程编号
#  @param requestId 请求标识
#  @return 恒为 False
def idleTrigger(workerId: int, requestId: str) -> bool:
    return False


## @brief 装配前的空流式触发器
#  @param workerId 线程编号
#  @param requestId 请求标识
#  @param frames 本轮流式帧
#  @return 恒为 False
def idleTriggerByFrames(workerId: int, requestId: str,
                        frames: tuple[bytes, ...]) -> bool:
    return False


## @brief 装配前的丢帧计数读取器；没接识别门面时恒为 0
#  @return 累计丢帧次数
def idleDroppedFrameCount() -> int:
    return 0


## @brief 装配前的链路探针；未接真实链路时一律按就绪处理
#  @return 恒为 True
def assumeLinkUp() -> bool:
    return True


## @brief 装配期填充的三个模块协作动作；EdgeControl 不直接 import modules/*
class ModuleWiring:
    ## @brief 构造空接线
    #  @return 无
    def __init__(self) -> None:
        ## @brief 初始化模块（不启业务线程）
        self.initializeModules: Callable[[], None] = idleAction
        ## @brief 启动链路（tcp 只拉重连线程）
        self.startLink: Callable[[], None] = idleAction
        ## @brief 启动采集
        self.startCapture: Callable[[], None] = idleAction
        ## @brief 按 workerId 触发识别
        self.triggerRecognition: Callable[[int, str], bool] = idleTrigger
        ## @brief 按 workerId 带流式帧触发识别
        self.triggerRecognitionByFrames: Callable[
            [int, str, tuple[bytes, ...]], bool
        ] = idleTriggerByFrames
        ## @brief 链路就绪探针；返回 False 表示上游已断链
        self.linkUpProbe: Callable[[], bool] = assumeLinkUp
        ## @brief 丢帧计数读取器；识别门面装配后注入，供验收取证
        self.droppedFrameCountProbe: Callable[[], int] = idleDroppedFrameCount
        ## @brief 停机动作表，键与 STOP_ORDER 一致
        self.stopActions: dict[str, Callable[[], None]] = {}


## @brief 跨模块协调者；实现四类 Sink，只做轻量分发与入队
class EdgeControl(BaseService, SignalSink, ICaptureSink, IRecognitionSink, IFrameSink):
    ## @brief 构造控制层
    #  @param logger 日志器（注入）
    #  @param asyncHandlers 注入的信号键到处理器映射
    #  @param wiring 装配期填充的模块协作动作
    #  @param frameSender 帧发送器（注入）
    #  @param failureFrameBuilder 失败应答构造器（注入）
    #  @param expectedWorkerCount 一次识别应答期望的采集线程数，收齐后才合并出帧
    #  @param maxAggregationEntries 在途聚合表条数上限
    #  @param degradedItemsProvider 降级条目提供器，按线程编号给出未识别条目
    #  @param aggregationTimeoutSec 聚合等待上限秒数，超时后降级出帧
    #  @return 无
    def __init__(self, logger: ILogger, asyncHandlers: dict[str, AsyncHandler],
                 wiring: ModuleWiring, frameSender: FrameSender,
                 failureFrameBuilder: FailureFrameBuilder,
                 expectedWorkerCount: int = 1,
                 maxAggregationEntries: int = MAX_AGGREGATION_ENTRIES,
                 degradedItemsProvider: DegradedItemsProvider = emptyDegradedItems,
                 aggregationTimeoutSec: float = DEFAULT_AGGREGATION_TIMEOUT_SEC,
                 dedupStrategy: str = DEDUP_FIRST) -> None:
        ## @brief 日志器
        self._logger: ILogger = logger
        ## @brief 注入的分发表
        self._asyncHandlers: dict[str, AsyncHandler] = asyncHandlers
        ## @brief 模块协作接线
        self._wiring: ModuleWiring = wiring
        ## @brief 帧发送器
        self._frameSender: FrameSender = frameSender
        ## @brief 失败应答构造器
        self._failureFrameBuilder: FailureFrameBuilder = failureFrameBuilder
        ## @brief 当前请求标识，routeSignal 内只提取一次
        self._requestId: str = ""
        ## @brief 链路就绪标记，由 Sink 宣告维护
        self._linkUp: bool = False
        ## @brief 停机总闸；置位后业务回调不再触发采集与识别，防止停机中重启已停模块
        self._stopping: bool = False
        ## @brief 待发送应答队列（回调内只入队）
        self._outbox: list[CachedEvent] = []
        ## @brief 停机步骤轨迹，供验收举证
        self._stopTrace: list[str] = []
        ## @brief 已完成请求的应答记录，供同一 request_id 重复请求时复用
        self._completedAcks: dict[str, CachedEvent] = {}
        ## @brief 在途请求计数，同一 request_id 只允许一次扫描
        self._pendingRequests: dict[str, int] = {}
        ## @brief 期望的采集线程数，收齐后才合并成一帧应答
        self._expectedWorkerCount: int = expectedWorkerCount
        ## @brief 在途聚合表，键是请求标识，值是各采集线程的清单
        self._aggregations: dict[str, dict[int, list[object]]] = {}
        ## @brief 在途请求的应答模板，合并出帧时沿用业务 payload 自带字段
        self._ackTemplates: dict[str, AckFrame] = {}
        ## @brief 在途聚合表条数上限
        self._maxAggregationEntries: int = maxAggregationEntries
        ## @brief 状态并发保护锁；只保护数据，不在锁内做 IO
        self._stateLock: Lock = Lock()
        ## @brief 应答排空线程，由装配层注入；为空表示不排空
        self._dispatchThread: EdgeDispatchThread | None = None
        ## @brief 降级条目提供器；某路采集线程失败时按它补齐未识别条目
        self._degradedItemsProvider: DegradedItemsProvider = degradedItemsProvider
        ## @brief 聚合等待上限秒数
        self._aggregationTimeoutSec: float = aggregationTimeoutSec
        ## @brief 在途请求的聚合截止时刻，键是请求标识
        self._scanDeadlines: dict[str, float] = {}
        ## @brief 各请求已确认失败的采集线程编号
        self._failedWorkers: dict[str, set[int]] = {}
        ## @brief 采集线程编号到当前请求标识的映射，失败回调据此归位请求
        self._workerRequests: dict[int, str] = {}
        ## @brief 坏帧丢弃累计数，仅统计 FRAME_PARSE；供验收举证
        self._frameErrorCount: int = 0
        ## @brief 全未知清单告警累计数，供运行期诊断识别退化
        self._allUnknownCount: int = 0
        ## @brief 汇总去重策略：first=重复货位保留首条；best_confidence=取高置信度
        self._dedupStrategy: str = dedupStrategy

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

    ## @brief 绑定应答排空线程；装配层在控制层构造完成后注入
    #  @param dispatchThread 应答排空线程（注入）
    #  @return 无
    def attachDispatchThread(self, dispatchThread: EdgeDispatchThread) -> None:
        self._dispatchThread = dispatchThread

    ## @brief 系统启动统一入口
    #  @return 无
    def startSystem(self) -> None:
        self.init()
        self.start()
        ## 应答排空线程随系统启动，保证应答真正出网
        if self._dispatchThread is not None:
            self._dispatchThread.start()
        self._logger.info(MODULE_NAME, "系统启动完成, 业务线程待链路 UP 后拉起")

    ## @brief 一键停机：先置总闸，再串行停 USB → RECOGNITION → TCP → LOG；单步异常不阻断后续
    #  @return 无
    #  @note 任一步失败仍继续其余步骤，运行态清理放在 finally，保证停机终态收敛
    def stopSystem(self) -> None:
        with self._stateLock:
            ## 总闸先置位，迟到的 Sink 回调据此不再触发业务
            self._stopping = True
            self._stopTrace = []
        firstError: Exception | None = None
        try:
            ## 排空线程最先停止，避免停机过程中继续把应答发到已停链路；
            ## 与其它停机步骤一样 best-effort，异常不阻断后续清理
            if self._dispatchThread is not None:
                try:
                    self._dispatchThread.stop(THREAD_STOP_TIMEOUT_SEC)
                except Exception as error:
                    firstError = error
                    self._logger.error(
                        MODULE_NAME, f"停机步骤 排空线程 异常: {error}", exception=error,
                    )
            for step in STOP_ORDER:
                try:
                    self._wiring.stopActions[step]()
                except Exception as error:
                    if firstError is None:
                        firstError = error
                    self._logger.error(
                        MODULE_NAME, f"停机步骤 {step} 异常: {error}", exception=error,
                    )
                with self._stateLock:
                    self._stopTrace.append(step)
        finally:
            self.clearRuntimeState()
            ## stop() 的统计信息使用 info
            self._logger.info(MODULE_NAME, f"停机统计 顺序={'-'.join(self.getStopTrace())}")
        if firstError is not None:
            raise firstError

    ## @brief 清空在途请求、聚合中间态与已完成应答，避免停机后残留占用内存
    #  @return 无
    def clearRuntimeState(self) -> None:
        with self._stateLock:
            self._pendingRequests.clear()
            self._completedAcks.clear()
            self._aggregations.clear()
            self._ackTemplates.clear()
            self._failedWorkers.clear()
            self._scanDeadlines.clear()
            self._workerRequests.clear()
            self._outbox.clear()

    ## @brief 按注入的 asyncHandlers 键分发；门面不感知具体业务字符串
    #  @param signal 已解码信号帧
    #  @return 命中处理器返回 True
    def routeSignal(self, signal: DecodedSignal) -> bool:
        signalType = str(signal.get(SIGNAL_TYPE_KEY, ""))
        handler = self._asyncHandlers.get(signalType)
        if handler is None:
            ## 未知 type 来自网络，截短记录，避免超长 type 撑爆日志队列
            preview = signalType[:MAX_LOG_TEXT_CHARS]
            self._logger.error(
                MODULE_NAME,
                f"未注册的信号键: {preview} 长度={len(signalType)}",
            )
            return False
        ## 请求标识只提取一次；处理器调用提平在锁外，避免深嵌套
        requestId = self.extractRequestId(signal)
        if not requestId:
            ## 无请求标识的帧无法配对应答，记日志后丢弃，不让上位机干等到重发超时
            self._logger.error(MODULE_NAME, "信号缺少请求标识，已丢弃")
            return True
        with self._stateLock:
            ## 停机中丢弃迟到信号，防止在途帧重启已停止的采集与识别；
            ## 与请求标识写入共用同一把锁，避免额外锁竞争改变请求到达时序
            if self._stopping:
                return True
            self._requestId = requestId
        ## 同一请求只处理一次：同一 request_id 只做一次扫描，重复请求直接复用上次应答
        if self.reuseCompletedAck(requestId):
            return True
        if not self.markRequestPending(requestId):
            self._logger.info(MODULE_NAME, f"请求 {requestId} 正在处理, 不重复触发扫描")
            return True
        try:
            handler(signal)
        except EdgeError as error:
            ## 业务处理失败不得上抛到解码线程，否则整条链路会失去接收能力
            self._logger.error(
                MODULE_NAME, f"请求 {requestId} 处理失败 {error.code.name}",
                exception=error,
            )
            self.enqueueDegradedFrame(requestId)
        except Exception as error:
            ## 无法识别的故障归入配置错误类别：跨出处理器边界前包装成 EdgeError(CONFIG)
            wrapped = EdgeError(
                ErrorCode.CONFIG, f"请求 {requestId} 处理出现未预期异常: {error}",
            )
            wrapped.__cause__ = error
            ## 处理器内的内置异常同样不得穿透到解码线程，统一按配置错误降级
            self._logger.error(
                MODULE_NAME,
                f"请求 {requestId} 处理出现未预期异常 {wrapped.code.name}: {error}",
                exception=wrapped,
            )
            self.enqueueDegradedFrame(requestId)
        return True

    ## @brief 取出信号中的请求标识；协议原文 request_id 优先，取不到时改用内部 requestId
    #  @param signal 已解码信号帧
    #  @return 请求标识；两键缺失或类型非字符串时返回空串
    #  @note 不做 str() 强转：数字等类型不是合法请求标识，强转会伪造出可配对的假 ID
    def extractRequestId(self, signal: DecodedSignal) -> str:
        wireId = signal.get(WIRE_REQUEST_ID_KEY, "")
        if isinstance(wireId, str) and wireId:
            return wireId
        internalId = signal.get(REQUEST_ID_KEY, "")
        if isinstance(internalId, str) and internalId:
            return internalId
        return ""

    ## @brief 重复请求命中处理：把上次应答重新入队，不重复触发采集与识别
    #  @param requestId 请求标识
    #  @return 命中并已重新入队返回 True
    def reuseCompletedAck(self, requestId: str) -> bool:
        if not requestId:
            return False
        with self._stateLock:
            cached = self._completedAcks.get(requestId)
        if cached is None:
            return False
        self.enqueueFrame(dict(cached))
        self._logger.info(MODULE_NAME, f"幂等复用请求 {requestId} 的上次应答")
        return True

    ## @brief 登记在途请求；同一 request_id 已在途则不重复触发扫描
    #  @param requestId 请求标识
    #  @return 首次登记返回 True；已在途返回 False
    def markRequestPending(self, requestId: str) -> bool:
        if not requestId:
            return True
        with self._stateLock:
            seen = self._pendingRequests.get(requestId, 0)
            self._pendingRequests[requestId] = seen + 1
            if seen == 0:
                ## 首次登记时给出聚合截止时刻，超时未收齐就降级出帧
                self._scanDeadlines[requestId] = (
                    monotonic() + self._aggregationTimeoutSec
                )
        return seen == 0

    ## @brief 清除在途登记；采集或识别失败后允许同一请求重试
    #  @param requestId 请求标识
    #  @return 无
    def clearPendingRequest(self, requestId: str) -> None:
        if not requestId:
            return
        with self._stateLock:
            self._pendingRequests.pop(requestId, None)

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

    ## @brief 坏帧回调：按帧解析错误计数并记说明日志
    #  @param exception 解析异常
    #  @return 无
    #  @note 只统计 FRAME_PARSE；坏帧的错误日志由解码层统一记，此处只记计数说明，
    #        避免同一坏帧产生两条 error
    def onFrameError(self, exception: Exception) -> None:
        if isinstance(exception, EdgeError) and exception.code == ErrorCode.FRAME_PARSE:
            with self._stateLock:
                self._frameErrorCount += 1
            self._logger.info(MODULE_NAME, "坏帧计数已累加")

    ## @brief 链路断开宣告：置链路标记为不可用，后续应答在分发时直接丢弃
    #  @param reason 断开原因
    #  @param source 宣告来源
    #  @return 无
    def onLinkDown(self, reason: str, source: str) -> None:
        with self._stateLock:
            self._linkUp = False
        self._logger.error(MODULE_NAME, f"链路断开 reason={reason} source={source}")

    ## @brief 链路恢复通知：置链路标记为可用
    #  @return 无
    def onLinkUp(self) -> None:
        with self._stateLock:
            self._linkUp = True
        self._logger.info(MODULE_NAME, "链路恢复")

    ## @brief 采集成功回调：只做轻量触发，禁止在此执行阻塞 IO
    #  @param workerId 线程编号
    #  @param path 采集目录
    #  @return 无
    def onCaptureSuccess(self, workerId: int, path: str) -> None:
        with self._stateLock:
            stopping = self._stopping
        if stopping:
            ## 停机中的采集回调不再触发识别，避免重启已停模块
            return
        self._wiring.triggerRecognition(workerId, self.getRequestId())
        self._logger.info(MODULE_NAME, f"采集完成 worker={workerId} dir={path}")

    ## @brief 采集失败回调：记日志、上报失败帧并把该路标记为降级
    #  @param workerId 线程编号
    #  @param exception 采集异常
    #  @return 无
    #  @note 失败帧是给现场排障看的本地记录，帧型上位机不认；
    #        它由出网守卫（modules/tcp/tcp_comm.py 的出网口）拦下，不会上线。
    #        上位机真正收到的是下面降级出来的那一帧合法应答。
    def onCaptureError(self, workerId: int, exception: Exception) -> None:
        self._logger.error(MODULE_NAME, f"采集失败 worker={workerId}", exception=exception)
        requestId = self.resolveWorkerRequestId(workerId)
        self.enqueueFrame(self._failureFrameBuilder(workerId, exception))
        if not self.enqueueDegradedFrame(requestId, workerId):
            ## 该请求还没收齐，降级出不了帧时允许上位机用同一请求标识重试
            self.clearPendingRequest(requestId)

    ## @brief 识别完成回调：先按请求标识聚合，收齐期望线程数后合并成一帧再入队
    #  @param workerId 线程编号
    #  @param ack 应答帧
    #  @param requestId 上位机请求标识
    #  @return 无
    def onRecognitionResult(self, workerId: int, ack: AckFrame,
                            requestId: str) -> None:
        for frame in self.collectAggregatedFrames(workerId, ack, requestId):
            self.enqueueFrame(frame)
        self._logger.info(MODULE_NAME, f"识别完成 worker={workerId} req={requestId}")

    ## @brief 帧流回调：一轮双路取帧完成，转调识别门面触发一次扫描
    #  @param workerId 线程编号
    #  @param frames 本轮帧元组，左路在前
    #  @param requestId 上位机请求标识
    #  @return 无
    def onFrameCaptured(self, workerId: int, frames: tuple[bytes, ...],
                        requestId: str) -> None:
        with self._stateLock:
            if self._stopping:
                ## 停机中的帧回调不再触发识别，避免重启已停模块
                return
            ## 记住该线程正在服务的请求，失败回调据此把降级条目归到正确的请求
            self._workerRequests[workerId] = requestId
        if self.isRequestAnswered(requestId):
            ## 该请求已经回过应答，后续帧不再重复触发扫描
            return
        self._wiring.triggerRecognitionByFrames(workerId, requestId, frames)

    ## @brief 聚合本线程的清单；收齐期望线程数后合并出一帧应答
    #  @param workerId 线程编号
    #  @param ack 应答帧
    #  @param requestId 上位机请求标识
    #  @return 应答帧副本列表，未收齐时为空
    def collectAggregatedFrames(self, workerId: int, ack: AckFrame,
                                requestId: str) -> list[CachedEvent]:
        with self._stateLock:
            if requestId in self._completedAcks:
                ## 已应答的请求不再重复出帧，重复请求由复用上次应答的路径处理
                return []
            table = self._aggregations.setdefault(requestId, {})
            table[workerId] = self.readAckItems(ack)
            self._ackTemplates[requestId] = dict(ack)
            self._workerRequests[workerId] = requestId
            self.trimAggregations()
        return self.completeRequestIfReady(requestId)

    ## @brief 收口判定：上报线程与失败线程合并覆盖到期望线程数就出帧
    #  @param requestId 上位机请求标识
    #  @return 应答帧副本列表，未收齐时为空
    #  @note 判定、清表与登记已完成应答都在同一把锁内完成，保证并发只出一次帧，
    #        也让重复请求复用取到完整应答而不是半成品。锁内调用的降级条目提供器
    #        由装配层注入，只允许按对照表做内存计算，不得回调控制层或做阻塞 IO。
    def completeRequestIfReady(self, requestId: str) -> list[CachedEvent]:
        with self._stateLock:
            if requestId in self._completedAcks:
                return []
            reported = set(self._aggregations.get(requestId, {}))
            failed = set(self._failedWorkers.get(requestId, set()))
            if len(reported | failed) < self._expectedWorkerCount:
                return []
            workerItems = dict(self._aggregations.get(requestId, {}))
            self._aggregations.pop(requestId, None)
            self._failedWorkers.pop(requestId, None)
            self._scanDeadlines.pop(requestId, None)
            template = self._ackTemplates.pop(requestId, None)
            ## 在途重复请求次数：同一请求回同样内容的应答应答次数，满足"只回同一结果"
            seen = self._pendingRequests.pop(requestId, 0)
            merged, duplicates = self.mergeWorkerItems(workerItems)
            ## 失败线程的货位按未识别补齐，保证清单覆盖全部已登记货位
            merged.extend(self.buildDegradedItems(sorted(failed - reported)))
            merged.sort(key=self.readItemPosition)
            frame = self.buildAggregatedFrame(
                template if template is not None else self.buildEmptyAck(requestId),
                requestId, merged,
            )
            if requestId:
                self._completedAcks[requestId] = dict(frame)
                ## 只保留最近若干条，超限丢弃最旧
                while len(self._completedAcks) > MAX_COMPLETED_REQUESTS:
                    del self._completedAcks[next(iter(self._completedAcks))]
        for duplicate in duplicates:
            self._logger.error(MODULE_NAME, f"货位 {duplicate} 重复上报, 保留第一条")
        ## 同一请求的重复上报次数决定应答帧数，各帧内容完全相同；
        ## 满足"同一请求只回同一结果"，也满足上位机按 request_id 配对
        count = seen if seen > 0 else 1
        return [dict(frame) for _index in range(count)]

    ## @brief 构造降级条目：按线程编号取该线程应上报的未识别条目
    #  @param workerIds 采集线程编号列表
    #  @return 协议条目列表
    #  @note 注入的提供器只在内存里按对照表拼条目，不做 IO、不回调控制层，
    #       因此放在状态锁内调用不会形成嵌套加锁。
    def buildDegradedItems(self, workerIds: list[int]) -> list[object]:
        items: list[object] = []
        for workerId in workerIds:
            items.extend(self._degradedItemsProvider(workerId))
        return items

    ## @brief 构造只有协议三键的空应答，作为降级出帧的模板
    #  @param requestId 上位机请求标识
    #  @return 空应答帧
    def buildEmptyAck(self, requestId: str) -> AckFrame:
        return {
            "type": ACK_FRAME_TYPE,
            WIRE_REQUEST_ID_FIELD: requestId,
            WIRE_ITEMS_FIELD: [],
        }

    ## @brief 识别能力不可用时立即回一帧空清单应答
    #  @param requestId 上位机请求标识
    #  @return 无
    #  @note 顶层恰好三个键：帧类型、请求标识与空清单，协议层合法；
    #        同时登记为该请求的应答，重复请求直接复用上次应答，不再重复触发扫描。
    def completeWithEmptyAck(self, requestId: str) -> None:
        if not requestId:
            return
        with self._stateLock:
            cached = self._completedAcks.get(requestId)
            if cached is None:
                cached = dict(self.buildEmptyAck(requestId))
                self._completedAcks[requestId] = cached
                self._pendingRequests.pop(requestId, None)
                self._scanDeadlines.pop(requestId, None)
                self._aggregations.pop(requestId, None)
                self._failedWorkers.pop(requestId, None)
                self._ackTemplates.pop(requestId, None)
            frame = dict(cached)
        ## 统一走 enqueueFrame，避免在这把锁内再嵌套加同一把锁
        self.enqueueFrame(frame)
        self._logger.info(
            MODULE_NAME, f"识别能力不可用, 已回空清单应答 req={requestId}",
        )

    ## @brief 把某路采集线程标记为失败并收口该请求；收不齐时不出帧
    #  @param requestId 上位机请求标识
    #  @param workerId 采集线程编号，NO_WORKER_ID 表示整轮都没跑起来
    #  @return 应答帧副本列表，收不齐时为空
    def enqueueDegradedFrame(self, requestId: str,
                             workerId: int = NO_WORKER_ID) -> list[CachedEvent]:
        if not requestId:
            return []
        with self._stateLock:
            if requestId in self._completedAcks:
                return []
            failed = self._failedWorkers.setdefault(requestId, set())
            if workerId != NO_WORKER_ID:
                failed.add(workerId)
            else:
                ## 整轮都没跑起来：所有采集线程都按降级处理
                for index in range(
                    FIRST_WORKER_ID, FIRST_WORKER_ID + self._expectedWorkerCount,
                ):
                    failed.add(index)
        frames = self.completeRequestIfReady(requestId)
        for frame in frames:
            self.enqueueFrame(frame)
        return frames

    ## @brief 解析采集线程当前服务的请求；优先用线程映射，回退到最近一次请求
    #  @param workerId 线程编号
    #  @return 请求标识；无法判定时为空串
    def resolveWorkerRequestId(self, workerId: int) -> str:
        with self._stateLock:
            mapped = self._workerRequests.get(workerId, "")
        return mapped or self.getRequestId()

    ## @brief 规范化单条清单条目：缺字段或类型非法时按空值处理并记日志
    #  @param rawItem 上游给出的条目
    #  @return 恰好四键的合法条目
    #  @note 不让脏条目原样上线被上位机整帧拒绝；单条非法不影响其它条目
    def normalizeAckItem(self, rawItem: object) -> dict[str, object]:
        source = rawItem if isinstance(rawItem, dict) else {}
        item: dict[str, object] = {}
        position = source.get(WIRE_POSITION_FIELD, "")
        item[WIRE_POSITION_FIELD] = position if isinstance(position, str) and position else ""
        toolId = source.get(ITEM_TOOL_ID_FIELD, EMPTY_TOOL_ID)
        item[ITEM_TOOL_ID_FIELD] = toolId if isinstance(toolId, str) else EMPTY_TOOL_ID
        confidence = source.get(ITEM_CONFIDENCE_FIELD, EMPTY_CONFIDENCE)
        item[ITEM_CONFIDENCE_FIELD] = (
            confidence if isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and 0.0 <= float(confidence) <= 1.0 else EMPTY_CONFIDENCE
        )
        alert = source.get(ITEM_ALERT_FIELD, INVALID_ITEM_ALERT)
        item[ITEM_ALERT_FIELD] = alert if alert in VALID_ALERT_TYPES else INVALID_ITEM_ALERT
        if set(source.keys()) != set(item.keys()) or any(
            source.get(key) != item[key] for key in item
        ):
            self._logger.error(
                MODULE_NAME, f"清单条目字段非法已按空值处理: {str(source)[:MAX_LOG_TEXT_CHARS]}",
            )
        return item

    ## @brief 取出应答帧里的清单条目
    #  @param ack 应答帧
    #  @return 清单条目列表
    def readAckItems(self, ack: AckFrame) -> list[object]:
        items = ack.get(WIRE_ITEMS_FIELD, [])
        return list(items) if isinstance(items, list) else []

    ## @brief 合并各采集线程的清单；按货位号排序，重复货位按配置策略保留
    #  @param workerItems 线程编号到清单条目的映射
    #  @return 合并后的清单与重复货位列表
    #  @note first=保留首条（原口径）；best_confidence=同货位取置信度高者，
    #        供 8 路独立裁剪模式下同货位被多路同时看到时择优
    def mergeWorkerItems(self, workerItems: dict[int, list[object]]) -> tuple[
        list[object], list[str],
    ]:
        merged: list[object] = []
        positionIndexes: dict[str, int] = {}
        duplicates: list[str] = []
        for workerId in sorted(workerItems):
            for rawItem in workerItems[workerId]:
                position = self.readItemPosition(rawItem)
                if position in positionIndexes:
                    duplicates.append(position)
                    self.resolveDuplicate(positionIndexes, position, rawItem, merged)
                    continue
                positionIndexes[position] = len(merged)
                merged.append(self.normalizeAckItem(rawItem))
        merged.sort(key=lambda entry: self.readItemPosition(entry))
        return merged, duplicates

    ## @brief 处理重复货位：按配置策略保留首条或替换为置信度更高的一条
    #  @param positionIndexes 货位号到 merged 下标的映射（原地更新）
    #  @param position 重复的货位号
    #  @param rawItem 新到的清单条目
    #  @param merged 已合并条目列表（原地更新）
    #  @return 无
    def resolveDuplicate(self, positionIndexes: dict[str, int], position: str,
                         rawItem: object, merged: list[object]) -> None:
        if self._dedupStrategy != DEDUP_BEST_CONFIDENCE:
            return
        index = positionIndexes[position]
        if self.readItemConfidence(rawItem) <= self.readItemConfidence(merged[index]):
            return
        merged[index] = self.normalizeAckItem(rawItem)

    ## @brief 读清单条目的置信度；缺字段或非数值按 0.0 处理，不冒充高置信
    #  @param rawItem 清单条目
    #  @return 置信度数值
    def readItemConfidence(self, rawItem: object) -> float:
        if not isinstance(rawItem, dict):
            return 0.0
        value = rawItem.get(ITEM_CONFIDENCE_FIELD)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0.0
        return float(value)

    ## @brief 读清单条目的货位号
    #  @param rawItem 清单条目
    #  @return 货位号
    def readItemPosition(self, rawItem: object) -> str:
        if not isinstance(rawItem, dict):
            return ""
        return str(rawItem.get(WIRE_POSITION_FIELD, ""))

    ## @brief 按协议组装聚合后的应答帧；顶层只保留帧类型、请求标识与清单
    #  @param ack 参与聚合的应答帧
    #  @param requestId 上位机请求标识
    #  @param items 合并后的清单条目
    #  @return 应答帧
    def buildAggregatedFrame(self, ack: AckFrame, requestId: str,
                             items: list[object]) -> CachedEvent:
        frame: CachedEvent = dict(ack)
        frame["type"] = ACK_FRAME_TYPE
        frame[WIRE_REQUEST_ID_FIELD] = requestId
        frame[WIRE_ITEMS_FIELD] = items
        ## 边缘内部字段不得上线
        frame.pop(INTERNAL_WORKER_FIELD, None)
        frame.pop(INTERNAL_REQUEST_FIELD, None)
        self.warnIfAllUnknown(items)
        return frame

    ## @brief 整帧清单全为未知时记 error 并累计告警，防止识别退化被当成正常
    #  @param items 合并后的清单条目
    #  @return 无
    #  @note 判定条件为"工具编号为空且告警为未知"，避免把真实空柜（告警为无告警）误报
    def warnIfAllUnknown(self, items: list[object]) -> None:
        if not items:
            return
        allUnknown = all(
            isinstance(item, dict)
            and item.get(ITEM_TOOL_ID_FIELD) == ""
            and item.get(ITEM_ALERT_FIELD) == ITEM_ALERT_UNKNOWN
            for item in items
        )
        if not allUnknown:
            return
        ## 调用方 buildAggregatedFrame 已在 _stateLock 内，此处不再加锁，避免重入死锁
        self._allUnknownCount += 1
        self._logger.error(
            MODULE_NAME, f"整帧清单全为未识别 条目数={len(items)}，请检查相机/标定/权重",
        )

    ## @brief 在途聚合表超限时丢弃最旧的请求
    #  @return 无
    #  @note 只由 collectAggregatedFrames 在持有 _stateLock 时调用；本方法不自行加锁，
    #       避免与调用方嵌套。改从别处调用前，务必先补齐这一层的并发保护。
    def trimAggregations(self) -> None:
        while len(self._aggregations) > self._maxAggregationEntries:
            oldest = next(iter(self._aggregations))
            del self._aggregations[oldest]
            self._ackTemplates.pop(oldest, None)
            self._scanDeadlines.pop(oldest, None)
            ## 在途状态一并清掉：失败集合与在途计数不残留，
            #  避免被挤掉的请求既收不到超时扫描又永不收口；
            #  已完成应答的幂等记录属另一语义，由 completeWithEmptyAck 单独管理
            self._failedWorkers.pop(oldest, None)
            self._pendingRequests.pop(oldest, None)

    ## @brief 判断该请求是否已经回过应答
    #  @param requestId 请求标识
    #  @return 已应答返回 True
    def isRequestAnswered(self, requestId: str) -> bool:
        if not requestId:
            return False
        with self._stateLock:
            return requestId in self._completedAcks

    ## @brief 识别失败回调：记日志、上报失败帧并把该路标记为降级
    #  @param workerId 线程编号
    #  @param exception 推理异常
    #  @return 无
    #  @note 与采集失败同一口径：失败帧只作本地记录，由出网守卫拦下不上线；
    #        上位机收到的是降级出来的那一帧合法应答。
    def onRecognitionError(self, workerId: int, exception: Exception) -> None:
        self._logger.error(MODULE_NAME, f"识别失败 worker={workerId}", exception=exception)
        requestId = self.resolveWorkerRequestId(workerId)
        self.enqueueFrame(self._failureFrameBuilder(workerId, exception))
        if not self.enqueueDegradedFrame(requestId, workerId):
            ## 该请求还没收齐，降级出不了帧时允许上位机用同一请求标识重试
            self.clearPendingRequest(requestId)

    ## @brief 应答入队（轻量）；队列超上限时丢弃最旧，防止断链期间无限增长
    #  @param frame 应答帧
    #  @return 无
    #  @note 锁内只动列表，日志在锁外记，锁内不做日志落盘。
    def enqueueFrame(self, frame: CachedEvent) -> None:
        dropped = 0
        with self._stateLock:
            self._outbox.append(frame)
            while len(self._outbox) > MAX_OUTBOX_FRAMES:
                self._outbox.pop(0)
                dropped += 1
        if dropped:
            self._logger.error(
                MODULE_NAME,
                f"待发应答超过上限 {MAX_OUTBOX_FRAMES} 条, 丢弃最旧 {dropped} 条",
            )

    ## @brief 同步链路状态：探针发现上游已断链时按断链处理，避免应答直发丢失
    #  @return 无
    def syncLinkState(self) -> None:
        if not self.isLinkUp():
            return
        if not self._wiring.linkUpProbe():
            self.onLinkDown("上游链路已断", "PROBE")

    ## @brief 由调用方在非回调上下文统一分发；UP 直发，DOWN 丢弃
    #  @return 本次分发条数
    def dispatchOutbox(self) -> int:
        self.syncLinkState()
        for frame in self.collectExpiredFrames():
            self.enqueueFrame(frame)
        with self._stateLock:
            pending = self._outbox
            self._outbox = []
        for frame in pending:
            if self.isLinkUp():
                ## send 返回 False 时不检查，链路断由 onLinkDown 感知
                self._frameSender(frame)
            else:
                self._logger.info(MODULE_NAME, "链路未建立，丢弃待发帧")
        return len(pending)

    ## @brief 扫描超过聚合等待上限的在途请求，降级补齐后出帧
    #  @return 应答帧列表，没有超期请求时为空
    def collectExpiredFrames(self) -> list[CachedEvent]:
        now = monotonic()
        with self._stateLock:
            expired = [
                requestId for requestId, deadline in self._scanDeadlines.items()
                if deadline <= now
            ]
        frames: list[CachedEvent] = []
        for requestId in expired:
            with self._stateLock:
                if requestId in self._completedAcks:
                    self._scanDeadlines.pop(requestId, None)
                    continue
                reported = set(self._aggregations.get(requestId, {}))
                failed = self._failedWorkers.setdefault(requestId, set())
                for workerId in range(
                    FIRST_WORKER_ID, FIRST_WORKER_ID + self._expectedWorkerCount,
                ):
                    if workerId not in reported:
                        failed.add(workerId)
            frames.extend(self.completeRequestIfReady(requestId))
        return frames

    ## @brief 供验收举证：注入的信号键
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 键列表
    def getHandlerKeys(self) -> list[str]:
        return sorted(self._asyncHandlers)

    ## @brief 供验收举证：停机轨迹
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 步骤列表
    def getStopTrace(self) -> list[str]:
        with self._stateLock:
            return list(self._stopTrace)

    ## @brief 供验收举证：待分发条数
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 队列长度
    def getOutboxCount(self) -> int:
        with self._stateLock:
            return len(self._outbox)

    ## @brief 供验收举证：链路就绪标记
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 就绪返回 True
    def isLinkUp(self) -> bool:
        with self._stateLock:
            return self._linkUp

    ## @brief 供验收举证：当前请求标识
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 请求标识
    def getRequestId(self) -> str:
        with self._stateLock:
            return self._requestId

    ## @brief 供验收举证：已完成请求的应答记录条数
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 记录条数
    def getCompletedAckCount(self) -> int:
        with self._stateLock:
            return len(self._completedAcks)

    ## @brief 供验收举证：在途请求条数
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 在途请求条数
    def getPendingRequestCount(self) -> int:
        with self._stateLock:
            return len(self._pendingRequests)

    ## @brief 供验收举证：在途聚合表条数
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 聚合表条数
    def getAggregationCount(self) -> int:
        with self._stateLock:
            return len(self._aggregations)

    ## @brief 供验收举证：识别忙时丢弃的帧轮数
    #  @note 只读观测口，被定向与集成用例按方法名调用，按引用关系保留
    #  @return 累计丢帧次数
    def getDroppedFrameCount(self) -> int:
        return self._wiring.droppedFrameCountProbe()

    ## @brief 返回仅统计 FRAME_PARSE 的累计坏帧数，用于运行期诊断
    #  @return 累计坏帧数
    def getFrameErrorCount(self) -> int:
        with self._stateLock:
            return self._frameErrorCount

    ## @brief 返回全未知清单告警累计数，用于运行期诊断识别退化
    #  @return 累计全未知告警数
    def getAllUnknownCount(self) -> int:
        with self._stateLock:
            return self._allUnknownCount
