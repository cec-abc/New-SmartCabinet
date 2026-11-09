# @file config_loader.py
# @brief 全局配置加载器：唯一 ini 解析处，生成嵌套 SimpleNamespace 并暴露全局 cfg。
#
# @details
# 本项目所有可调参数集中写入 config.ini，由本文件统一解析，main.py 与 vision_core.py
# 均不接触 configparser / json 解析逻辑（保证单一配置耦合点）。解析结果以嵌套
# SimpleNamespace 呈现，对外保持 cfg.crop.left_path 点号访问方式；[project] 段字段
# 提升到顶层（cfg.log_level / cfg.output_dir）。复杂结构（ROI 框、映射表、拼接点等）
# 以 JSON 字符串存于 ini，由 _cast 还原为对应 Python 类型。

from __future__ import annotations

import configparser
import json
import os
from types import SimpleNamespace
from typing import Any, Dict

_HERE = os.path.dirname(os.path.abspath(__file__))

# @brief ini 文件路径（与 config_loader.py 同目录）
_INI_PATH = os.path.join(_HERE, "config.ini")

# @brief 需要按 JSON 解析的字段名集合（ini 中以 JSON 字符串存值）
_JSON_FIELDS = frozenset({
    "points",
    "roi_boxes",
    "class_item_map",
    "roi_bind_map",
    "self_check_map",
    "valid_class_ids",
    "known_types",           # 新增：A3 帧编解码 type 白名单
    "dedup_types",           # 新增：A4 请求去重拦截类型白名单（JSON 数组 -> List[str]）
    "reconnect_backoff",     # 新增：A1 重连退避序列（JSON 数组 -> List[int]）
    "camera_ids",            # 新增：A2 周期帧 8 路摄像头 ID（JSON 数组 -> List[str]）
    "camera_status",         # 新增：A2 周期帧 8 路摄像头初始状态（JSON 数组 -> List[str]）
})

# @brief 需要转相对 _HERE 绝对路径的 (段名, 键名) 集合
_PATH_FIELDS = frozenset({
    ("project", "output_dir"),
    ("crop", "left_path"),
    ("crop", "right_path"),
    ("yolo", "model_path"),
})


## @brief 相对路径转相对 _HERE 的绝对路径。
## @details 若入参已是绝对路径则原样返回，避免重复拼接导致路径膨胀。
## @param [in] path 待转换的相对/绝对路径字符串
## @return str；相对于 _HERE 的绝对路径
def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(_HERE, path)


## @brief 把 ini 字符串按字段语义还原为 Python 类型。
##
## @details
## 规则如下：
##  - JSON 字段（key 在 _JSON_FIELDS）：空串时 points 返回 None、valid_class_ids /
##    known_types 返回 frozenset()、其余返回 {}；非空时按 JSON 解析，其中 roi_boxes
##    的值转 tuple，class_item_map 的键转 frozenset(k.split(","))，valid_class_ids /
##    known_types 转 frozenset。
##  - 标量字段：依次尝试 int -> float -> 原样 str。
##
## @param [in] key 字段名（用于判断是否为 JSON 字段）
## @param [in] val ini 读出的原始字符串
## @return Any；还原后的 Python 对象
def _cast(key: str, val: str) -> Any:
    if key in _JSON_FIELDS:
        stripped = val.strip()
        if stripped == "":
            if key == "points":
                return None
            if key == "valid_class_ids" or key == "known_types":
                return frozenset()
            return {}
        data = json.loads(stripped)
        if key == "roi_boxes":
            # 值从列表转元组，保持与旧 config.py 中 tuple 形态一致
            return {k: tuple(v) for k, v in data.items()}
        if key == "class_item_map":
            # 键为逗号分隔的类别组合，转 frozenset 以便后续快速查表
            return {frozenset(k.split(",")): v for k, v in data.items()}
        if key == "valid_class_ids" or key == "known_types":
            return frozenset(data)
        return data
    # 标量：int -> float -> str 依次尝试
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


## @brief 读 ini 生成嵌套 SimpleNamespace。
##
## @details 遍历各 section，把每个字段经 _cast 还原后挂到对应子 SimpleNamespace；
## [project] 段字段额外提升到返回对象顶层（cfg.log_level / cfg.output_dir）。
##
## @param [in] ini_path ini 文件路径
## @return SimpleNamespace；顶层含 [project] 提升字段 + 各段子命名空间
def _load_cfg(ini_path: str) -> SimpleNamespace:
    parser = configparser.ConfigParser()
    # 保留键名大小写，避免 section 名被强制小写
    parser.optionxform = str
    parser.read(ini_path, encoding="utf-8")

    root = SimpleNamespace()
    sections_ns: Dict[str, SimpleNamespace] = {}

    for section in parser.sections():
        ns = SimpleNamespace()
        for key, raw in parser.items(section):
            value = _cast(key, raw)
            if (section, key) in _PATH_FIELDS:
                value = _abs(value)
            setattr(ns, key, value)
        sections_ns[section] = ns

    # 将各段挂到顶层；[project] 段字段同时提升到顶层
    for section, ns in sections_ns.items():
        setattr(root, section, ns)
    if "project" in sections_ns:
        for key, value in vars(sections_ns["project"]).items():
            setattr(root, key, value)

    return root


# 模块加载时解析一次，对外暴露全局唯一配置实例
cfg = _load_cfg(_INI_PATH)
