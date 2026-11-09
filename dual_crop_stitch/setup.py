# @file setup.py
# @brief 跨平台 Cython 编译脚本：将 src/vision_core.py 编译为单一动态库
#        （Windows 生成 .pyd / Linux·麒麟 生成 .so）。
#
# 利用 sys.platform 自动判断平台并选择编译器参数，不写死任何平台变量。
#
# 构建步骤：
#   [Windows] 安装 MSVC 构建工具（Visual Studio Build Tools）后执行：
#       python setup.py build_ext --inplace
#       生成 vision_core.cp3x-win_amd64.pyd，输出到项目根目录。
#   [Linux / 麒麟] 安装 gcc 与 python3-dev 后执行：
#       python3 setup.py build_ext --inplace
#       生成 vision_core.cpython-3x-x86_64-linux-gnu.so，输出到项目根目录。
#
# 关键点：setup() 不设置 package_dir，build_ext --inplace 将动态库直接输出到
# 项目根目录（setup.py 所在目录），无需人工 mv；开发期 main.py 通过 sys.path
# 回退加载 src/ 下的 vision_core.py 源码，生产期可安全删除 src/ 保护源码。

from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np
import sys

# 依据 sys.platform 动态选择编译器参数（不使用写死的平台变量）
if sys.platform.startswith("win"):
    extra_compile_args = ["/O2", "/utf-8"]
    print("[INFO] 当前平台: Windows -> 准备生成 .pyd (MSVC)")
else:
    extra_compile_args = ["-O3"]
    print("[INFO] 当前平台: Linux -> 准备生成 .so (GCC)")

# 仅编译 src/vision_core.py；Extension 的 sources 显式指向该文件，模块名不带包前缀；
# 不设置 package_dir，故动态库（.pyd / .so）输出到项目根目录。
extensions = [
    Extension("vision_core", ["src/vision_core.py"],
              include_dirs=[np.get_include()],
              extra_compile_args=extra_compile_args),
]

setup(
    name="dual_crop_stitch",
    ext_modules=cythonize(extensions, language_level=3),
)
