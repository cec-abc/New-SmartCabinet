# @file run_tests.py
# @brief 一键自动化测试脚本：自动安装测试依赖并执行 pytest 分支覆盖率测试。
#
# @details
# 本脚本为跨平台（Windows / Linux / macOS）纯标准库实现，不依赖任何第三方包。
# 运行流程：
#   1. 自动安装 requirements-test.txt 中的依赖（已安装则 pip 自动跳过，避免重复下载）；
#   2. 将 src/ 加入 PYTHONPATH，调用 pytest 对 vision_core 做分支覆盖率测试（--cov-branch）；
#   3. 在终端清晰打印测试结果与覆盖率报告，并给出成功/失败提示。
# 任何一步失败都会被捕获，并以非零退出码结束，便于 CI 集成或“交差”判定。
#
# @note vision_core 位于 src/ 子目录，脚本自动将其加入 PYTHONPATH 以保证导入。
# @warning 需要 Python 3.8+；若处于离线环境且依赖未缓存，pip 安装可能失败（已做容错提示）。

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_HERE, "src")


def _install_deps() -> bool:
    # 安装测试依赖；已存在则 pip 会快速跳过，不重复下载
    req = os.path.join(_HERE, "requirements-test.txt")
    if not os.path.isfile(req):
        print(f"[警告] 未找到依赖清单 {req}，跳过安装")
        return True
    print("==> 正在安装测试依赖（若已安装会自动跳过）...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", req],
            cwd=_HERE)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[错误] 依赖安装失败：{exc}")
        return False


def _run_tests() -> int:
    # 执行 pytest 并开启分支覆盖率；返回 pytest 退出码（0=全过且达标）
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _SRC_DIR + os.pathsep + existing
    cmd = [
        sys.executable, "-m", "pytest",
        "--cov=vision_core", "--cov-branch", "--cov-report=term-missing",
        "test_vision_core.py", "-v", "-s",
    ]
    print("==> 执行测试：", " ".join(cmd))
    try:
        return subprocess.call(cmd, cwd=_HERE, env=env)
    except FileNotFoundError:
        print("[错误] 未找到 pytest，请确认依赖已正确安装")
        return 1


def main() -> None:
    print("########## 一键自动化测试开始 ##########")
    if not _install_deps():
        print("[失败] 测试未执行：依赖安装失败")
        sys.exit(2)
    rc = _run_tests()
    print("########## 测试结束 ##########")
    if rc == 0:
        print("[成功] 全部测试通过，分支覆盖率达标（见上方绿油油报告）")
    else:
        print(f"[失败] 测试未通过或覆盖率未达标，pytest 退出码={rc}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
