# -*- coding: utf-8 -*-
"""打包 PySide6 版本的 EXE（v42.0 预览版）"""
import sys
import os

# 确保当前目录是项目根目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyInstaller.__main__ import run as pyinstaller_run

if __name__ == "__main__":
    pyinstaller_run([
        "gui_pyside6/main_window.py",
        "--name=ZPP011偏差分析器_v42.0_preview",
        "--windowed",
        "--onefile",
        "--clean",
        f"--add-data={os.path.join('config')};config",
        f"--add-data={os.path.join('core')};core",
        f"--add-data={os.path.join('analysis')};analysis",
        f"--add-data={os.path.join('modules')};modules",
        f"--add-data={os.path.join('domain')};domain",
        f"--add-data={os.path.join('utils')};utils",
        f"--add-data={os.path.join('gui_pyside6', 'style.qss')};gui_pyside6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=matplotlib.backends.backend_qtagg",
        "--hidden-import=openpyxl",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=sklearn",
        "--icon=ZPP011偏差分析器.ico" if os.path.exists("ZPP011偏差分析器.ico") else "",
    ])
