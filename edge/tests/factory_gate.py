"""出厂配置口径判定：现场调试/标定改值时，出厂默认断言让位并注明原因。

config.ini 不入版本库、现场可调（相机路数、焦点、权重、后端），一批守护测试
把工作区 config.ini 当出厂基准读。本地处于调试态时这些断言跳过并注明原因，
出厂形态恢复后自动恢复执行；断言原文一律不改动。
"""
from __future__ import annotations

import configparser
from pathlib import Path

## @brief 出厂相机路数字面量：CAM1~CAM8
FACTORY_CAMERA_INDICES: str = "1,2,3,4,5,6,7,8"
## @brief 本地处于现场调试态时跳过出厂断言的理由文案
SKIP_REASON: str = (
    "本地 config.ini 为现场调试/标定配置（非出厂 8 路口径），"
    "出厂默认断言跳过；出厂形态恢复后自动执行"
)


## @brief 判定本地 config.ini 是否保持出厂 8 路口径
#  @param iniPath 现场配置文件路径
#  @return 出厂口径为真；文件缺失或路数被调试改动为假
def factoryConfigActive(iniPath: Path) -> bool:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(iniPath, encoding="utf-8")
    if not parser.has_section("usb"):
        return False
    return parser.get("usb", "camera_indices", fallback="") == FACTORY_CAMERA_INDICES


## @brief 出厂样例 ROI 对照表的标志占位类别名
SAMPLE_MARKER_ID: str = "mk_8821"
## @brief 本地 ROI 对照表已是现场标定值时跳过样例断言的理由文案
ROI_SAMPLE_SKIP_REASON: str = (
    "本地 roi_binding.csv 已按现场实测重标（非出厂四行占位样例），"
    "样例形态断言跳过；出厂样例恢复后自动执行"
)


## @brief 判定 ROI 对照表是否仍是出厂四行占位样例
#  @param csvPath ROI 对照表路径
#  @return 表头加四行且含占位标志名时为真；现场已重标为假
def sampleRoiBindingActive(csvPath: Path) -> bool:
    try:
        lines = csvPath.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return len(lines) == 5 and SAMPLE_MARKER_ID in lines[1]
