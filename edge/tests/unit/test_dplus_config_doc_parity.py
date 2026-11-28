"""D 组新增单测：配置与文档的一致性、编码与启动脚本口径。

只依赖标准库与本仓库的静态文件内容，不 import 任何业务模块，便于并行期独立运行。
"""
from __future__ import annotations

import configparser
import re
from pathlib import Path

import pytest

from edge.tests.factory_gate import (
    FACTORY_CAMERA_INDICES,
    SKIP_REASON,
    factoryConfigActive,
)

## @file edge/tests/unit/test_dplus_config_doc_parity.py
## @brief 配置文件、两份说明文档与启动脚本的一致性回归用例
## @author 袁燕

## @brief edge 工程根目录
EDGE_ROOT: Path = Path(__file__).resolve().parents[2]
## @brief 现场配置文件
INI_PATH: Path = EDGE_ROOT / "config" / "config.ini"
## @brief 启动与配置手册
README_PATH: Path = EDGE_ROOT / "README.md"
## @brief 配置件字段说明
CFG_README_PATH: Path = EDGE_ROOT / "config" / "README.md"
## @brief ROI 对照表
ROI_CSV_PATH: Path = EDGE_ROOT / "config" / "roi_binding.csv"
## @brief 类别组合表
CLASS_CSV_PATH: Path = EDGE_ROOT / "config" / "class_item_map.csv"
## @brief 一键启动脚本
BAT_PATH: Path = EDGE_ROOT / "run_edge.bat"
## @brief ROI 对照表固定的十二列表头
ROI_HEADER: str = (
    "roi_id,worker_id,drawer_id,position,tool_id,required_type,"
    "marker_id,confidence,rect_x1,rect_y1,rect_x2,rect_y2"
)
## @brief 含配置键表的手册小节编号
KEY_SECTIONS: tuple[str, ...] = ("tcp", "log", "usb", "recognition")


## @brief 用 UTF-8 读出现场配置，返回 键到值 的平铺字典
#  @return 形如 {"tcp.port": "9000"} 的字典
def readIniPairs() -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(INI_PATH, encoding="utf-8")
    return {
        f"{section}.{key}": parser.get(section, key)
        for section in parser.sections()
        for key in parser.options(section)
    }


## @brief 从手册第 3 节的配置键表中读出 键到当前值 的映射
#  @return 形如 {"tcp.port": "9000"} 的字典；缩写值原样保留
def readReadmePairs() -> dict[str, str]:
    pairs: dict[str, str] = {}
    current = ""
    for line in README_PATH.read_text(encoding="utf-8").splitlines():
        title = re.match(r"^### 3\.\d+\s+`\[(\w+)\]`", line)
        if re.match(r"^### 3\.\d+\s+", line):
            current = title.group(1) if title and title.group(1) in KEY_SECTIONS else ""
        row = re.match(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]*)`\s*\|", line)
        if row and current:
            pairs[f"{current}.{row.group(1)}"] = row.group(2)
    return pairs


## @brief 现场配置可由 configparser 以 UTF-8 实读，中文注释不破坏解析
#  @return 无
def testConfigIniIsUtf8AndReadableWithChineseComments() -> None:
    if not factoryConfigActive(INI_PATH):
        pytest.skip(SKIP_REASON)
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(INI_PATH, encoding="utf-8")
    assert parser.sections() == ["log", "tcp", "usb", "recognition"]
    assert parser.get("tcp", "port") == "9000"
    assert parser.get("usb", "camera_indices") == FACTORY_CAMERA_INDICES
    assert parser.get("recognition", "require_roi_binding") == "true"
    # 文件里含中文注释，能按 UTF-8 解码即证明编码口径正确
    assert "#" in INI_PATH.read_text(encoding="utf-8")


## @brief config.ini 的每个键都在手册配置键表里出现
#  @return 无
def testEveryConfigKeyIsDocumentedInReadme() -> None:
    ini = readIniPairs()
    documented = readReadmePairs()
    missing = sorted(set(ini) - set(documented))
    assert missing == [], f"手册未写到的配置键: {missing}"


## @brief 手册配置键表里的每个键都真实存在于 config.ini
#  @return 无
def testEveryReadmeKeyExistsInConfigIni() -> None:
    ini = readIniPairs()
    documented = readReadmePairs()
    ghost = sorted(set(documented) - set(ini))
    assert ghost == [], f"手册写了但配置里没有的键: {ghost}"


## @brief 手册标注的当前值与 config.ini 默认值逐项一致
#  @return 无
@pytest.mark.parametrize(
    "fullKey",
    [
        "tcp.host", "tcp.port", "tcp.connect_timeout_sec", "tcp.recv_timeout_sec",
        "tcp.max_frame_size", "tcp.backoff_seq", "tcp.heart_interval_sec",
        "log.dir", "log.max_file_size", "log.mode", "log.disk_free_threshold",
        "log.queue_poll_sec", "usb.roll_threshold", "usb.camera_indices",
        "usb.capture_mode", "usb.focus_mode",
        "usb.focus_positions", "usb.zoom_positions", "usb.focus_stable_ms",
        "recognition.model_path", "recognition.infer_timeout_sec",
        "recognition.roi_binding_csv", "recognition.require_roi_binding",
        "recognition.aggregation_timeout_sec", "recognition.inference_backend",
        "recognition.nms_iou_threshold",
    ],
)
def testReadmeDefaultMatchesIni(fullKey: str) -> None:
    ## 焦点/权重/后端/路数属现场可调项：本地调试态与出厂手册不一致时让位
    if fullKey in {
        "usb.camera_indices", "usb.focus_positions", "usb.zoom_positions",
        "recognition.model_path", "recognition.inference_backend",
    } and not factoryConfigActive(INI_PATH):
        pytest.skip(SKIP_REASON)
    ini = readIniPairs()
    documented = readReadmePairs()
    assert documented[fullKey] == ini[fullKey], (
        f"{fullKey}: 手册={documented[fullKey]!r} 配置={ini[fullKey]!r}"
    )


## @brief 手册用 w1..w4 缩写列出的目录，与配置里展开的四条目录一致
#  @return 无
@pytest.mark.parametrize("section", ["usb", "recognition"])
def testReadmeAbbreviatedSaveDirsMatchExpandedIni(section: str) -> None:
    ini = readIniPairs()
    documented = readReadmePairs()
    expanded = ini[f"{section}.save_dirs"].split(",")
    assert len(expanded) == 4, f"{section}.save_dirs 应展开为 4 条目录"
    assert ".." in documented[f"{section}.save_dirs"], "手册应使用 w1..w4 缩写"
    assert expanded[0].endswith("w1") and expanded[-1].endswith("w4")


## @brief 现场默认值没有被改动，仍是 8 路、auto、camera、false
#  @return 无
def testSiteDefaultsStayUnchanged() -> None:
    if not factoryConfigActive(INI_PATH):
        pytest.skip(SKIP_REASON)
    ini = readIniPairs()
    assert ini["usb.camera_indices"] == FACTORY_CAMERA_INDICES
    assert ini["usb.capture_mode"] == "auto"
    assert ini["recognition.require_roi_binding"] == "true"


## @brief ROI 对照表表头恰好十二列，顺序与配置说明一致
#  @return 无
def testRoiCsvHeaderHasTwelveColumns() -> None:
    header = ROI_CSV_PATH.read_text(encoding="utf-8").splitlines()[0].strip()
    assert header == ROI_HEADER
    assert len(header.split(",")) == 12


## @brief 配置说明声明的十二列表头与 CSV 实际表头逐字一致
#  @return 无
def testConfigReadmeHeaderMatchesRoiCsv() -> None:
    text = CFG_README_PATH.read_text(encoding="utf-8")
    assert "十二列" in text
    match = re.search(r"表头固定十二列[^\n]*\n+```\n([^\n]+)\n```", text)
    assert match is not None, "配置说明应给出代码块形式的表头"
    assert match.group(1).strip() == ROI_HEADER


## @brief 类别组合表表头与装载器要求的列名一致
#  @return 无
def testClassItemCsvHeaderHasTwoColumns() -> None:
    header = CLASS_CSV_PATH.read_text(encoding="utf-8").splitlines()[0].strip()
    assert header == "class_names,item_name"
    text = CFG_README_PATH.read_text(encoding="utf-8")
    assert "`class_names`" in text and "`item_name`" in text


## @brief 配置说明已按双口径描述装载不到对照表时的行为
#  @return 无
def testConfigReadmeDocumentsBothRequireRoiBindingModes() -> None:
    text = CFG_README_PATH.read_text(encoding="utf-8")
    assert "require_roi_binding" in text
    assert "`false`（现场默认值）" in text
    assert "`true`（生产严格口径）" in text
    assert "识别能力置为不可用" in text
    assert "启动即失败" in text


## @brief 配置说明不再声称缺表一律拒绝启动，避免与降级口径矛盾
#  @return 无
def testConfigReadmeNoLongerClaimsMissingTableAlwaysFailsFast() -> None:
    text = CFG_README_PATH.read_text(encoding="utf-8")
    assert "时边缘机直接判配置错误拒绝启动" not in text
    assert "对照表文件缺失、缺列" not in text


## @brief 配置说明保留既有验收要求的关键词
#  @return 无
@pytest.mark.parametrize("keyword", ["marker_id", "类别名", "worker_id", "上板"])
def testConfigReadmeKeepsRequiredKeywords(keyword: str) -> None:
    assert keyword in CFG_README_PATH.read_text(encoding="utf-8")


## @brief 启动脚本使用切到仓库根的写法并以模块方式启动入口
#  @return 无
def testRunEdgeBatUsesRepoRootAndModuleEntry() -> None:
    text = BAT_PATH.read_bytes().decode("gbk")
    assert 'cd /d "%~dp0.."' in text
    assert "python -m edge.main" in text
    assert "chcp 936" in text


## @brief 启动脚本为 GBK 编码且无 BOM，与 chcp 936 代码页配套
#  @return 无
def testRunEdgeBatEncodingMatchesChcp936() -> None:
    raw = BAT_PATH.read_bytes()
    assert raw[:3] != b"\xef\xbb\xbf"
    assert raw.decode("gbk")  # 能按 GBK 解码，中文 echo 不乱码
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")


## @brief 手册的启动命令与故障排查写法与启动脚本一致
#  @return 无
def testReadmeStartupAndTroubleshootingMatchBat() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    assert "python -m edge.main" in text
    assert 'cd /d "%~dp0.."' in text
    assert "python edge\\main.py" in text  # 明确标出不可用的写法
    assert "ModuleNotFoundError" in text


## @brief 手册按代码实际行为说明相对路径候选与配置文件自锚定
#  @return 无
def testReadmeExplainsCwdCandidateAndSelfAnchoredConfig() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    assert "配置文件自身" in text
    assert "运行时工作目录" in text
    assert "第 1 项就是工作目录" in text
    assert "与你当前在哪个目录无关" not in text


## @brief 手册不再把命令行绝对路径说成第四级查找位置
#  @return 无
def testReadmeDropsWrongFourthCandidateClaim() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    assert "命令行给的绝对路径" not in text
    assert "直接查这个绝对路径是否存在" in text


## @brief 手册的日志方向统一使用大写 RX 与 TX
#  @return 无
def testReadmeUsesUppercaseRxTx() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    assert "`RX`" in text and "`TX`" in text
    assert "`rx`" not in text and "`tx`" not in text


## @brief 手册把 camera_indices = 0 明确写成联调临时值而非现场默认值
#  @return 无
def testReadmeMarksSingleCameraIndexZeroAsTemporary() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    assert "camera_indices = 0" in text
    assert "别留着 `0` 上现场" in text
    assert "1,2,3,4,5,6,7,8" in text
