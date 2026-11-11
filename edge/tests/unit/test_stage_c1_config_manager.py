"""阶段 c1 补强单测：Fail-Fast、类型推断、default 两分支与双检锁单例。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from edge.exceptions import EdgeError, ErrorCode
from edge.infra.config_manager import IniConfigManager, inferValue
from edge.interfaces.i_config import IConfig
from edge.tests.fakes.fake_logger import FakeLogger

## @brief 覆盖五种推断类型的 INI 样本
INI_CONTENT: str = (
    "[comm]\n"
    "port = 9000\n"
    "negative = -12\n"
    "timeout = 3.5\n"
    "enabled = true\n"
    "disabled = off\n"
    "hosts = 10.0.0.1, 10.0.0.2\n"
    "label = edge_node\n"
)


## @brief 在临时目录写入 INI 配置
#  @param directory pytest 临时目录
#  @param content INI 文本内容
#  @return 配置文件路径字符串
def writeIni(directory: Path, content: str) -> str:
    configPath = directory / "config.ini"
    configPath.write_text(content, encoding="utf-8")
    return str(configPath)


## @brief 并发调用单例入口，用屏障对齐起跑时刻
#  @param configPath 配置文件路径
#  @param barrier 并发屏障
#  @return 单例对象
def callInstance(configPath: str, barrier: Barrier) -> IniConfigManager:
    barrier.wait(timeout=5.0)
    return IniConfigManager.instance(configPath)


# 对应验收项 c1-1：文件缺失 Fail-Fast 抛 EdgeError(CONFIG)，异常码可打印
def testMissingConfigFileFailsFast(tmp_path: Path) -> None:
    missingPath = str(tmp_path / "absent.ini")
    with pytest.raises(EdgeError) as caught:
        IniConfigManager(missingPath)
    error = caught.value
    assert isinstance(error, EdgeError) is True
    assert error.code == ErrorCode.CONFIG
    assert error.code.name == "CONFIG"
    assert str(error) == f"[CONFIG] 配置文件缺失: {missingPath}"


# 对应验收项 c1-1：INI 解析失败同样 Fail-Fast，内置异常转 EdgeError(CONFIG)
def testMalformedIniFailsFast(tmp_path: Path) -> None:
    configPath = writeIni(tmp_path, "port = 9000\n")
    with pytest.raises(EdgeError) as caught:
        IniConfigManager(configPath)
    error = caught.value
    assert error.code == ErrorCode.CONFIG
    assert "[CONFIG]" in str(error)
    assert "配置解析失败" in str(error)


# 对应验收项 c1-1：非法 UTF-8 编码文件的内置异常同样转 EdgeError(CONFIG)
def testInvalidEncodingFailsFast(tmp_path: Path) -> None:
    configPath = tmp_path / "config.ini"
    configPath.write_bytes(b"[comm]\nlabel = \xff\n")
    with pytest.raises(EdgeError) as caught:
        IniConfigManager(str(configPath))
    error = caught.value
    assert error.code == ErrorCode.CONFIG
    assert "[CONFIG]" in str(error)
    assert "配置解析失败" in str(error)


# 对应验收项 c1-2：int / float / bool / list / str 五类值经 get 返回推断后类型
def testValuesAreInferredToNativeTypes(tmp_path: Path) -> None:
    manager = IniConfigManager(writeIni(tmp_path, INI_CONTENT))
    assert manager.get("comm", "port") == 9000
    assert isinstance(manager.get("comm", "port"), int) is True
    assert manager.get("comm", "negative") == -12
    assert manager.get("comm", "timeout") == 3.5
    assert isinstance(manager.get("comm", "timeout"), float) is True
    assert manager.get("comm", "enabled") is True
    assert manager.get("comm", "disabled") is False
    assert manager.get("comm", "hosts") == ["10.0.0.1", "10.0.0.2"]
    assert manager.get("comm", "label") == "edge_node"
    assert isinstance(manager.get("comm", "label"), str) is True


# 对应验收项 c1-2：推断函数边界，数字不被布尔吞并、非有限值保留字符串
def testInferValueBoundaryCases() -> None:
    assert inferValue("1") == 1
    assert isinstance(inferValue("1"), bool) is False
    assert inferValue("0") == 0
    assert inferValue("TRUE") is True
    assert inferValue("OFF") is False
    assert inferValue("1e3") == 1000.0
    assert inferValue("inf") == "inf"
    assert inferValue("nan") == "nan"
    assert inferValue(" 7 , 8 ") == [7, 8]
    assert inferValue("hello") == "hello"


# 对应验收项 c1-3：命中 key 返回推断值，default 不生效且不记 info
def testGetIgnoresDefaultWhenKeyExists(tmp_path: Path) -> None:
    logger = FakeLogger()
    manager = IniConfigManager(writeIni(tmp_path, INI_CONTENT), logger)
    assert manager.get("comm", "port", default=1234) == 9000
    assert logger.infoRecords == []


# 对应验收项 c1-3：缺 key 且无 default 抛 EdgeError(CONFIG) 并带节键信息
def testGetWithoutDefaultFailsFast(tmp_path: Path) -> None:
    manager = IniConfigManager(writeIni(tmp_path, INI_CONTENT))
    with pytest.raises(EdgeError) as caught:
        manager.get("comm", "absent")
    assert caught.value.code == ErrorCode.CONFIG
    assert str(caught.value) == "[CONFIG] 配置项缺失: [comm] absent"


# 对应验收项 c1-3：缺 key 有 default 返回默认值并逐条记 info，含 falsy 默认值
def testGetWithDefaultReturnsValueAndLogsInfo(tmp_path: Path) -> None:
    logger = FakeLogger()
    manager = IniConfigManager(writeIni(tmp_path, INI_CONTENT), logger)
    assert manager.get("comm", "absent", default=8080) == 8080
    assert manager.get("other", "absent", default="fallback") == "fallback"
    assert manager.get("comm", "absent", default=0) == 0
    assert logger.infoRecords == [
        ("IniConfigManager", "配置项 [comm] absent 缺失，使用默认值 8080"),
        ("IniConfigManager", "配置项 [other] absent 缺失，使用默认值 fallback"),
        ("IniConfigManager", "配置项 [comm] absent 缺失，使用默认值 0"),
    ]


# 对应验收项 c1-4：普通构造可用于测试，实例之间数据独立且实现 IConfig
def testPlainConstructorsAreIndependent(tmp_path: Path) -> None:
    first = IniConfigManager(writeIni(tmp_path, INI_CONTENT))
    otherPath = tmp_path / "other.ini"
    otherPath.write_text("[comm]\nport = 7000\n", encoding="utf-8")
    second = IniConfigManager(str(otherPath))
    assert isinstance(first, IConfig) is True
    assert first.get("comm", "port") == 9000
    assert second.get("comm", "port") == 7000
    assert first is not second


# 对应验收项 c1-1、c1-4：instance() 首次加载失败不留下半成品单例
def testInstanceFailFastLeavesNoSingleton(tmp_path: Path) -> None:
    IniConfigManager._sharedInstance = None
    with pytest.raises(EdgeError) as caught:
        IniConfigManager.instance(str(tmp_path / "absent.ini"))
    assert caught.value.code == ErrorCode.CONFIG
    assert IniConfigManager._sharedInstance is None


# 对应验收项 c1-4：instance() 双检锁并发 8 路只创建一个实例
def testInstanceIsDoubleCheckedSingleton(tmp_path: Path) -> None:
    IniConfigManager._sharedInstance = None
    configPath = writeIni(tmp_path, INI_CONTENT)
    barrier = Barrier(8)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(callInstance, configPath, barrier) for _ in range(8)]
        results = [future.result(timeout=5.0) for future in futures]
    assert all(result is results[0] for result in results) is True
    assert results[0] is IniConfigManager.instance(configPath)
    assert results[0].get("comm", "port") == 9000
    assert IniConfigManager._sharedInstance is results[0]
    IniConfigManager._sharedInstance = None


# 对应验收项 c1-4：普通构造不污染单例，instance() 重复调用返回同一对象
def testInstanceDoesNotDependOnPlainConstructor(tmp_path: Path) -> None:
    IniConfigManager._sharedInstance = None
    configPath = writeIni(tmp_path, INI_CONTENT)
    plain = IniConfigManager(configPath)
    assert IniConfigManager._sharedInstance is None
    shared = IniConfigManager.instance(configPath)
    assert shared is not plain
    assert shared is IniConfigManager.instance(configPath)
    assert shared.get("comm", "port") == 9000
    IniConfigManager._sharedInstance = None
