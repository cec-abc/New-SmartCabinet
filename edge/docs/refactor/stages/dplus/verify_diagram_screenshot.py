"""截图 + 布局自检脚本：起临时 http.server，用 playwright（msedge 通道）截图并跑页面内置自检。

用法：
    python verify_diagram_screenshot.py <html相对路径> <输出png>
        [视口宽] [视口高] [选择器|all] [裁剪x,y,w,h]

说明：
    * file:// 会被浏览器拦，必须走 http.server。
    * 页面里的「布局自检」面板会跑同层重叠检测与文字超宽检测，脚本一并打印结果。
    * 脚本自行起服务、截图、关服务，退出时清理。
    * 裁剪参数（可选）："x,y,w,h"，按 CSS 像素裁剪，用于逐块目检局部细节。
"""
## @file edge/docs/refactor/stages/dplus/verify_diagram_screenshot.py
## @brief 图表截图与布局自检：起临时 HTTP 服务，用浏览器截图并打印页面自检结果
## @author 袁燕
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # edge/
OUT_DIR = Path(__file__).resolve().parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_port(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    rel_html = sys.argv[1]
    out_png = Path(sys.argv[2])
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 3200
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 2400
    selector = sys.argv[5] if len(sys.argv) > 5 else "#root"
    clip = None
    if len(sys.argv) > 6 and sys.argv[6].strip():
        parts = sys.argv[6].split(",")
        if len(parts) != 4:
            print("[FAIL] 裁剪参数格式应为 x,y,w,h")
            return 2
        clip = {k: float(v) for k, v in zip(("x", "y", "width", "height"), parts)}

    html_path = (ROOT / rel_html).resolve()
    if not html_path.is_file():
        print(f"[FAIL] 找不到 HTML: {html_path}")
        return 2
    out_png = out_png if out_png.is_absolute() else (OUT_DIR / out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(port):
            print("[FAIL] http.server 未起来")
            return 3
        url = f"http://127.0.0.1:{port}/{html_path.relative_to(ROOT).as_posix()}"
        print(f"[INFO] 打开 {url}")
        shot = shoot(url, out_png, width, height, selector, clip)
        if shot is None:
            return 4
        print(f"[OK] 截图已生成: {out_png} ({shot[0]}x{shot[1]})")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def shoot(url: str, out_png: Path, width: int, height: int, selector: str = "#root",
          clip: dict | None = None):
    """用 playwright-core + msedge 通道截图。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[FAIL] 未安装 playwright（pip install playwright）")
        return None
    import playwright  # noqa: F401  仅用于确认来源

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=1)
        errors: list[str] = []
        page.on("pageerror",
                lambda e: errors.append(str(e) + " | " + (getattr(e, "stack", "") or "")))
        page.on("console",
                lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type == "error" else None)
        page.goto(url, wait_until="load")
        # 去掉滚动容器的限高，避免 SVG 被裁掉（否则只截到可见部分）
        page.add_style_tag(
            content=".scroller{max-height:none !important;overflow:visible !important;}")
        page.wait_for_timeout(700)
        ready = page.evaluate("() => window.__diagReady === true")
        if not ready:
            print("[WARN] 页面未置位 __diagReady，可能脚本报错")
        for e in errors:
            print(f"[PAGE-ERROR] {e}")
        check = page.query_selector("#check-body")
        if check is not None:
            print("[SELF-CHECK] " + check.inner_text().replace("\n", " | "))
        els = page.query_selector_all("svg")
        if not els:
            browser.close()
            print("[FAIL] 页面里没有 svg 元素")
            return None
        if selector and selector != "all":
            hit = page.query_selector(selector)
            els = [hit] if hit is not None else els
        results = []
        for idx, el in enumerate(els):
            target = out_png if len(els) == 1 else out_png.with_name(
                out_png.stem + f"_{idx+1}" + out_png.suffix)
            if clip:
                # 元素截图接口不支持裁剪，改用整页截图 + 文档坐标裁剪
                offset = el.evaluate(
                    "e => { const r = e.getBoundingClientRect();"
                    " return {x: r.x + window.scrollX, y: r.y + window.scrollY}; }")
                page.screenshot(path=str(target), full_page=True, clip={
                    "x": offset["x"] + clip["x"],
                    "y": offset["y"] + clip["y"],
                    "width": clip["width"],
                    "height": clip["height"],
                })
            else:
                el.screenshot(path=str(target))
            box = el.bounding_box()
            width = int(box["width"]) if box is not None else 0
            height = int(box["height"]) if box is not None else 0
            results.append((target, width, height))
        browser.close()
        for t, w, h in results:
            print(f"[OK] {t} ({w}x{h})")
        return (results[0][1], results[0][2])


if __name__ == "__main__":
    raise SystemExit(main())
