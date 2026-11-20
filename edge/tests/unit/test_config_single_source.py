"""本轮单测：置信度门槛单一来源可配置、全景图滚动删旧。
对应 P0470c（阈值由配置提供、一处定义）、P0361/P0369（全景图滚动删除）。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import edge.modules.recognition.recognition_utils as ru
from edge.infra.roi_binding_loader import DEFAULT_CONFIDENCE
from edge.modules.recognition.recognition_worker import RecognitionWorker


def test_confidence_threshold_single_source() -> None:
    """置信度门槛的默认常量与装载器默认值同源，且 buildConfigItem 支持注入覆盖。"""
    assert ru.DEFAULT_CONFIDENCE_THRESHOLD == DEFAULT_CONFIDENCE == 0.85

    # 默认口径：0.80 低于 0.85 → 低置信度
    item_default = ru.buildConfigItem("A-01-01", "扳手", "扳手", 0.80)
    assert item_default["alert_type"] == ru.ALERT_LOW_CONFIDENCE

    # 注入更低的门槛 0.70 → 同样 0.80 判为正常
    item_injected = ru.buildConfigItem("A-01-01", "扳手", "扳手", 0.80,
                                       confidenceThreshold=0.70)
    assert item_injected["alert_type"] == ru.ALERT_NONE


def test_panorama_roll_deletes_oldest(tmp_path: Path) -> None:
    """磁盘超阈值时按最旧优先删除全景图，并跳过本轮受保护文件。"""
    worker = RecognitionWorker.__new__(RecognitionWorker)
    worker._saveDir = str(tmp_path)
    worker._rollThreshold = 0.3
    worker.removedPanoramaCount = 0
    usage = {"ratio": 0.9}

    def usageRatio() -> float:
        return usage["ratio"]

    worker._usageRatio = usageRatio  # type: ignore[method-assign]

    files = []
    for idx in range(3):
        p = tmp_path / f"w1_panorama_{idx}.png"
        p.write_bytes(b"x" * 10)
        os.utime(p, (time.time() - 100 + idx, time.time() - 100 + idx))
        files.append(p)
    protected = files[-1]  # 本轮文件最新，应保留

    worker.logFailure = lambda error: None  # type: ignore[method-assign]
    worker.rollPanoramaStorage(protected)

    assert worker.removedPanoramaCount == 2
    assert protected.exists()
    assert not files[0].exists()
    assert not files[1].exists()


def test_panorama_roll_noop_when_below_threshold(tmp_path: Path) -> None:
    """占用低于阈值时不删任何文件。"""
    worker = RecognitionWorker.__new__(RecognitionWorker)
    worker._saveDir = str(tmp_path)
    worker._rollThreshold = 0.3
    worker.removedPanoramaCount = 0
    worker._usageRatio = lambda: 0.1  # type: ignore[method-assign]
    p = tmp_path / "w1_panorama_0.png"
    p.write_bytes(b"x")
    worker.rollPanoramaStorage(p)
    assert worker.removedPanoramaCount == 0
    assert p.exists()
