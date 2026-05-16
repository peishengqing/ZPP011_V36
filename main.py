#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器 — 打包入口文件
"""
import sys
import os

# 确保当前目录在 Python 路径中
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后
    base_dir = sys._MEIPASS
else:
    # 开发模式
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 导入并运行主程序
try:
    from gui.events import run_app
    run_app()
except Exception as e:
    import traceback
    traceback.print_exc()
    input("按回车键退出...")
