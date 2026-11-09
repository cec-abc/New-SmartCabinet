# @file main.py
# @brief 业务入口：串联「读取 → 切割 → 拼接 → 识别 → 归集 → 自检 → 校验」的纯流水线，
#        并常驻监听上位机 TCP 报文。
#
# @details
# 本文件是唯一调度者，不实现任何算法细节与通信细节；核心能力（切割/拼接/识别/
# 空间归集/业务校验/通信）均下沉到 vision_core 动态库。运行期若尚未编译，通过
# sys.path 回退加载 src/vision_core.py 源码；编译后根目录的 .so/.pyd 天然优先。
# 所有配置集中在 config.ini，由 config_loader.py 解析为 cfg 对象后 import 使用，
# 改配置无需改此处。流程中不做 if not success / try-except 等防御性判断，
# 底层失败由 success 字段或异常自然暴露，保证流水线极简。

from __future__ import annotations

import functools
import logging
import os
import sys
import time

import cv2
import numpy as np

# 开发期回退：编译前用 src/ 下的 .py 源码；编译后根目录 .so/.pyd 在 path 中天然优先
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_HERE, "src"))

import vision_core
from vision_core import Detection
from tcp_comm import TcpComm
from config_loader import cfg
from logger_setup import LogManager

logger = logging.getLogger(__name__)


# =========================================================================
# === 耗时打印总开关（不需要测耗时的时候，直接删掉这段代码即可） ===
# =========================================================================
## @brief 集中式耗时打印开关：动态包装动态库函数，零侵入业务代码。
def _enable_timing():
    def _wrap(func, name):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            result = func(*args, **kwargs)
            print(f"[耗时] {name}: {(time.perf_counter() - t0) * 1000:.2f} ms")
            return result
        return wrapper

    # 给底层接口穿上“计时外套”，之后原代码怎么调，它就怎么计时
    vision_core.crop_images = _wrap(vision_core.crop_images, "接口1 切割")
    vision_core.stitch_images = _wrap(vision_core.stitch_images, "接口2 拼接")
    vision_core.yolo_init = _wrap(vision_core.yolo_init, "接口3 加载模型")
    vision_core.yolo_detect = _wrap(vision_core.yolo_detect, "接口3 纯推理")
    vision_core.check_roi_containment = _wrap(vision_core.check_roi_containment, "接口4 空间归集")
    vision_core.self_check = _wrap(vision_core.self_check, "接口4.5 视野自检")
    vision_core.check_business_logic = _wrap(vision_core.check_business_logic, "接口5 业务校验")
# =========================================================================


## @brief 在图像上绘制 ROI 区域框及 ID 标签（蓝色）。
##
## @details 纯可视化辅助函数，不改动任何算法。遍历 roi_defs，以蓝色 (255,0,0)、
## 线宽 2 画矩形框，并在框左上角外侧偏移 6 像素处写 ROI ID 文本。
##
## @param [in] image    待绘制的画布；尺寸 (H, W, 3) BGR
## @param [in] roi_defs ROI 框字典；格式 {"roi_id": (x1, y1, x2, y2)}；坐标单位: 像素
## @return np.ndarray；绘制后的图像副本（不修改入参）
## @note 文字基线 y 坐标取 max(0, y1-6)，避免标签写到画布外导致截断。
def _draw_rois(image: np.ndarray, roi_defs: dict) -> np.ndarray:
    canvas = image.copy()
    for roi_id, (x1, y1, x2, y2) in roi_defs.items():
        # 画 ROI 框，颜色为蓝色 (255, 0, 0)，线宽 2
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (255, 0, 0), 2)
        # 在 ROI 框左上角写 ID（y 方向内缩 6 像素，避免与框线重叠）
        cv2.putText(canvas, roi_id, (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2, cv2.LINE_AA)
    return canvas


## @brief 单次视觉流水线：读取 → 切割 → 拼接 → 识别 → 归集 → 自检 → 校验 → 保存。
##
## @details
## 本函数是现有 main() 流水线体的原样搬迁，只做接口编排与 cfg 字段绑定，
## 不实现任何算法细节。接口调用顺序、绑定关系注释、行内逻辑解释、保存画框
## 逻辑全部保留；失败由底层 success/异常自然暴露。
##
## @return None
## @note 自检失败时直接 return，阻断后续接口 5 业务校验。
def run_pipeline() -> None:
    # 1. 读取（直接 imread，不判空）—— 失败在后续接口以 success/异常暴露
    left = cv2.imread(cfg.crop.left_path)
    right = cv2.imread(cfg.crop.right_path)

    # --- 接口 1：切割 (crop_images) ---
    crop = vision_core.crop_images(left, right, cfg.crop.width, cfg.crop.height)
    cfg.crop.out_left_img = crop.leftImage
    cfg.crop.out_right_img = crop.rightImage
    logger.info("切割完成：left=%s right=%s", crop.leftImage.shape, crop.rightImage.shape)

    # 将接口 1 的输出绑定给接口 2 的输入
    cfg.stitch.in_img_a = cfg.crop.out_right_img
    cfg.stitch.in_img_b = cfg.crop.out_left_img
    # None 自动计算拼接点：左原图宽 - 裁剪宽，即左右半幅接缝处
    stitchPoints = cfg.stitch.points if cfg.stitch.points is not None else \
        [left.shape[1] - cfg.crop.out_right_img.shape[1], 0]

    # --- 接口 2：拼接 (stitch_images) ---
    stitch = vision_core.stitch_images(cfg.stitch.in_img_a, cfg.stitch.in_img_b, stitchPoints)
    cfg.stitch.out_panorama = stitch.panorama
    logger.info("拼接完成：panorama=%s", stitch.panorama.shape)

    # 将接口 2 的输出绑定给接口 3 的输入
    cfg.yolo.in_img = cfg.stitch.out_panorama

    # --- 接口 3：识别 (yolo_init 初始化 + yolo_detect 纯推理) ---
    vision_core.yolo_init(cfg.yolo.model_path, cfg.yolo.conf_threshold, cfg.yolo.img_size)
    detections = vision_core.yolo_detect(cfg.yolo.in_img)
    cfg.yolo.out_detections = detections
    for det in detections:
        logger.info("%s conf=%.2f box=%s", det.className, det.confidence, det.box)
    logger.info("识别完成：共 %d 个目标", len(detections))

    # 将接口 3 的输出绑定给接口 4 的输入
    cfg.business.in_detections = cfg.yolo.out_detections

    # --- 接口 4：空间归集 (check_roi_containment) ---
    ROI_CHECK_RESULT = vision_core.check_roi_containment(
        cfg.business.in_detections, cfg.business.roi_boxes)
    cfg.business.in_roi_check_result = ROI_CHECK_RESULT

    # --- 接口 4.5：相机视野自检 ---
    # 自检失败说明相机视野遮挡/标志物丢失，必须阻断后续接口 5，直接 return
    is_valid = vision_core.self_check(cfg.business.in_roi_check_result, cfg.business.self_check_map)
    if not is_valid:
        logger.error("由于视野自检未通过，流水线终止，跳过接口5业务校验。")
        return

    # --- 接口 5：业务校验 (check_business_logic 双表交叉校验) ---
    vision_core.check_business_logic(
        cfg.business.in_roi_check_result,
        cfg.business.class_item_map,
        cfg.business.roi_bind_map)

    # 7. 保存结果（含检测画框）
    cv2.imwrite(os.path.join(cfg.output_dir, "crop_left.jpg"), cfg.crop.out_left_img)
    cv2.imwrite(os.path.join(cfg.output_dir, "crop_right.jpg"), cfg.crop.out_right_img)
    cv2.imwrite(os.path.join(cfg.output_dir, "stitch.jpg"), cfg.stitch.out_panorama)

    # 先画 ROI 区域（蓝色）
    canvas = _draw_rois(cfg.yolo.in_img, cfg.business.roi_boxes)

    # 再画 YOLO 检测框（绿色，线宽 2）
    for det in detections:
        x1, y1, x2, y2 = det.box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{det.className} {det.confidence:.2f}"
        cv2.putText(canvas, label, (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

    cv2.imwrite(os.path.join(cfg.output_dir, "detect.jpg"), canvas)
    logger.info("完成：crop_left.jpg / crop_right.jpg / stitch.jpg / detect.jpg（含ROI）")


## @brief 处理拍照识别全流程（注册给 TcpComm 的异步业务）。
## @details 由 TcpComm 异步任务网关在独立线程调用；内部直接复用现有 run_pipeline()
##          执行完整视觉流水线，返回业务 payload。msg 由上层透传，本业务暂未消费其内容。
## @param [in] msg 上位机发来的原始报文（包含 request_id 等）
## @return dict 业务返回的 payload（不需要带 type 和 request_id，底层自动补全）
def process_recognize(msg: dict) -> dict:
    run_pipeline()
    //todo
    return {"items": []}


## @brief 主入口：配置日志、启动通信、执行一次流水线、常驻监听。
##
## @details
## 只做四件事：logging 初始化、TcpComm 启停、调用 run_pipeline()、常驻等待。
## 报文语义（recognize / periodic 等）待定，当前 on_message 仅记录日志；
## 后续接入报文业务时，应在独立模块处理，禁止回填到本文件。
##
## @return None
def main() -> None:
    # 1. 确保输出目录存在（日志落盘依赖此目录；LogManager 不校验目录）
    os.makedirs(cfg.output_dir, exist_ok=True)

    # 2. 初始化日志系统：视觉主控与 TCP 通信日志隔离落盘
    #    注：config_loader 不解析布尔，true/false 为字符串，此处显式转为 bool
    LogManager(
        log_level=cfg.log_level,
        output_dir=cfg.output_dir,
        vision_file=cfg.project.log_vision_file,
        tcp_file=cfg.project.log_tcp_file,
        max_bytes=cfg.project.log_max_bytes,
        backup_count=cfg.project.log_backup_count,
        console_enable=(cfg.project.log_console_enable == "true"),
    ).setup()

    _enable_timing()  # <--- 开启耗时打印（不需要就直接删掉这行）

    ## @brief 收到上位机非去重类报文的回调（当前仅处理 version_query）。
    ## @details 由 TcpComm._dispatch_message 在非异步业务分支回调；A5 版本查询
    ##          立即回包 {"type":"version_ack","software_version": cfg.software_version}。
    ## @param [in] msg 解析后的报文 dict
    ## @return None
    def on_message(msg: dict) -> None:
        if msg.get("type") == "version_query":
            comm.send({"type": "version_ack",
                       "software_version": cfg.software_version})

    # --- 通信：边缘机=TCP Client，连接上位机（Server） ---
    comm = TcpComm(
        # --- A1 连接与重连 ---
        cfg.comm.host,
        cfg.comm.port,
        cfg.comm.reconnect_backoff,
        cfg.comm.connect_timeout,
        cfg.comm.recv_poll_timeout,
        cfg.comm.recv_buffer_size,

        # --- A2 心跳：周期帧间隔与内容 ---
        heartbeat_interval=cfg.heartbeat.interval,
        periodic_type=cfg.heartbeat.type,
        camera_ids=cfg.heartbeat.camera_ids,
        camera_status=cfg.heartbeat.camera_status,

        # --- 报文回调：非异步业务（如 version_query）走这里 ---
        on_message=on_message,

        # --- A3 分帧：字节流 → dict 的五关校验 ---
        known_types=cfg.comm.known_types,
        max_frame_bytes=cfg.comm.max_frame_bytes,
        drop_log_head_bytes=cfg.comm.drop_log_head_bytes,

        # --- A4 去重 + A6 离线缓存：防重发与断连补报 ---
        dedup_types=cfg.comm.dedup_types,
        dedup_cache_ttl=cfg.comm.dedup_cache_ttl,
        offline_cache_max=cfg.comm.offline_cache_max,

        # --- 业务挂载：收到 recognize 时在独立线程调 process_recognize ---
        async_handlers={"recognize": process_recognize})
    comm.start()
    comm.start_heartbeat()
    try:
        # 执行一次视觉流水线（现有行为）
        run_pipeline()
        # 常驻等待上位机报文；按 Ctrl+C 退出
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    finally:
        comm.stop_heartbeat()     # 先停心跳（断源）
        comm.stop()               # 再停连接（断管道）


if __name__ == "__main__":
    main()
