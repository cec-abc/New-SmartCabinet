"""探测摄像头绝对对焦属性的真实范围：set 后回读，回读不跟随即为硬件上限。"""
from __future__ import annotations
import cv2

cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)  # 1 改成您现在用的设备号
if not cap.isOpened():
    print("打不开摄像头")
    raise SystemExit(0)

prop = getattr(cv2, "CAP_PROP_FOCUS_ABSOLUTE", None)   #CAP_PROP_FOCUS_ABSOLUTE   CAP_PROP_ZOOM
if prop is None:
    prop = cv2.CAP_PROP_FOCUS
lastGood = None
for value in range(0, 1024, 5):
    ok = cap.set(prop, float(value))
    readback = cap.get(prop)
    followed = abs(readback - value) <= max(2.0, value * 0.1)
    if not ok or not followed:
        print(f"到 {value} 不再跟随: set={ok}, 回读={readback:.1f}")
        print(f"硬件真实上限约 = {lastGood}")
        break
    lastGood = value
else:
    print(f"0~1023 全程跟随，上限 > 1023，lastGood={lastGood}")
cap.release()
