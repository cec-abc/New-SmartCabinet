"""识别模式常量：拼接全景推理与单路裁剪独立识别的模式名。"""
from __future__ import annotations

## @file edge/modules/recognition/recognition_modes.py
## @brief 识别模式常量单一来源：stitch=拼接全景推理；crop=每路裁剪独立识别
## @author 袁燕

## @brief 拼接模式：左右两路拼全景后整图推理一次（原口径）
RECOGNITION_MODE_STITCH: str = "stitch"
## @brief 裁剪模式：每路相机独立 worker，按归一化矩形裁剪后各推理一次
RECOGNITION_MODE_CROP: str = "crop"
## @brief 全部合法识别模式取值
RECOGNITION_MODES: tuple[str, ...] = (RECOGNITION_MODE_STITCH, RECOGNITION_MODE_CROP)
## @brief 识别模式缺省值，与原口径一致
DEFAULT_RECOGNITION_MODE: str = RECOGNITION_MODE_STITCH
## @brief 汇总去重策略：重复货位保留首条（原口径）
DEDUP_FIRST: str = "first"
## @brief 汇总去重策略：同货位保留置信度更高的一条
DEDUP_BEST_CONFIDENCE: str = "best_confidence"
## @brief 全部合法去重策略取值
DEDUP_STRATEGIES: tuple[str, ...] = (DEDUP_FIRST, DEDUP_BEST_CONFIDENCE)
## @brief 去重策略缺省值
DEFAULT_DEDUP_STRATEGY: str = DEDUP_FIRST
