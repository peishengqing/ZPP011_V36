#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 一键打包脚本
- 自动修复 main_window.py 中的错误引用
- 不删除 dist 目录（永久保留）
- 使用 PyInstaller 打包 PySide6 应用
"""

import os
import sys
import re
import subprocess

# ========== 配置 ==========
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_WINDOW = os.path.join(PROJECT_DIR, "gui_pyside6", "main_window.py")
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
REQUIRED_PACKAGES = ["PySide6", "pandas", "openpyxl", "xlsxwriter", "matplotlib", "python-pptx"]

# ========== 1. 修复 main_window.py 中的错误引用 ==========
def fix_main_window():
    if not os.path.exists(MAIN_WINDOW):
        print(f"❌ 未找到 {MAIN_WINDOW}")
        return False

    with open(MAIN_WINDOW, "r", encoding="utf-8") as f:
        content = f.read()

    # 替换错误的导入或调用
    # 情况1: from Domain.AltMaterial import build_alt_table
    if "from Domain.AltMaterial" in content:
        content = re.sub(r"from Domain\.AltMaterial import .*\n", "", content)
        print("✅ 已移除 from Domain.AltMaterial 导入")

    # 情况2: Domain.AltMaterial.build_alt_table() 调用
    if "Domain.AltMaterial.build_alt_table" in content:
        content = content.replace("Domain.AltMaterial.build_alt_table()", "self._refresh_alt_table()")
        print("✅ 已将 Domain.AltMaterial.build_alt_table() 替换为 self._refresh_alt_table()")

    # 情况3: 可能还有其他引用，直接搜索替换
    content = re.sub(r"Domain\.AltMaterial\.", "self.", content)

    with open(MAIN_WINDOW, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ main_window.py 修复完成")
    return True

# ========== 2. 检查并安装依赖 ==========
def install_packages():
    print("检查依赖包...")
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"⚠️ 缺少以下包: {missing}")
        print("正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
        print("✅ 依赖安装完成")
    else:
        print("✅ 所有依赖已安装")

# ========== 3. 打包（保留 dist 目录） ==========
def run_pyinstaller():
    # 确保 dist 目录存在（但不删除）
    if not os.path.exists(DIST_DIR):
        os.makedirs(DIST_DIR, exist_ok=True)

    # 构建 PyInstaller 命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=ZPP011偏差分析器_v42.0",
        "--windowed",
        "--onefile",
        "--distpath=dist",
        "--workpath=build",
        "--specpath=.",
        "--add-data=config;config",
        "--add-data=core;core",
        "--add-data=analysis;analysis",
        "--add-data=modules;modules",
        "--add-data=domain;domain",
        "--add-data=utils;utils",
        "--add-data=gui_pyside6;gui_pyside6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=matplotlib.backends.backend_qtagg",
        "--hidden-import=openpyxl",
        "--hidden-import=pandas",
        "--icon=ZPP011偏差分析器.ico",
        "gui_pyside6/main_window.py"
    ]

    print("开始打包...")
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ 打包成功！\n   输出文件: {os.path.join(DIST_DIR, 'ZPP011偏差分析器_v42.0.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"❌ 打包失败: {e}")
        sys.exit(1)

# ========== 主流程 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("ZPP011 一键打包工具")
    print("=" * 60)
    # 1. 修复代码
    if not fix_main_window():
        print("请确保项目路径正确，按任意键退出...")
        input()
        sys.exit(1)
    # 2. 安装依赖
    install_packages()
    # 3. 打包
    run_pyinstaller()
    print("\n🎉 打包完成！dist 目录保留，历史版本未删除。")
    input("按回车键退出...")