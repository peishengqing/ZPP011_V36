#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器（调试版本入口）
用于诊断 exe 启动问题
"""

import os
import sys
import traceback

def write_log(msg):
    """写入日志到桌面"""
    log_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'zpp011_debug.log')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{msg}\n")

def main():
    write_log("=" * 60)
    write_log("程序启动")
    write_log(f"Python: {sys.executable}")
    write_log(f"Frozen: {getattr(sys, 'frozen', False)}")
    write_log(f"MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
    write_log(f"CWD: {os.getcwd()}")
    write_log(f"sys.path: {sys.path}")
    write_log("-" * 60)
    
    try:
        # 添加当前目录到路径（关键修复）
        if getattr(sys, 'frozen', False):
            # 如果是打包后的 exe，添加 _MEIPASS 到路径
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
            write_log(f"Added to sys.path: {base_path}")
        
        # 尝试导入关键模块
        write_log("尝试导入 tkinter...")
        import tkinter as tk
        write_log("✓ tkinter 导入成功")
        
        write_log("尝试导入 pandas...")
        import pandas as pd
        write_log(f"✓ pandas 导入成功: {pd.__version__}")
        
        write_log("尝试导入 openpyxl...")
        import openpyxl
        write_log("✓ openpyxl 导入成功")
        
        write_log("尝试导入 PIL...")
        from PIL import Image, ImageTk
        write_log("✓ PIL 导入成功")
        
        write_log("尝试导入 widgets...")
        from widgets import C, STEPS
        write_log("✓ widgets 导入成功")
        
        write_log("尝试导入 storage...")
        from storage import storage
        write_log("✓ storage 导入成功")
        
        write_log("尝试导入 analysis...")
        from analysis.analyzer import do_analysis_v2
        write_log("✓ analysis 导入成功")
        
        write_log("尝试导入 gui.events...")
        from gui.events import run_app
        write_log("✓ gui.events 导入成功")
        
        write_log("-" * 60)
        write_log("所有模块导入成功，启动应用...")
        write_log("=" * 60)
        
        # 启动应用
        run_app()
        
    except Exception as e:
        error_msg = f"错误: {type(e).__name__}: {e}"
        write_log(error_msg)
        write_log(traceback.format_exc())
        
        # 显示错误对话框（如果 tkinter 可用）
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "启动错误",
                f"程序启动失败:\n\n{type(e).__name__}: {e}\n\n"
                f"详细信息已保存到桌面: zpp011_debug.log"
            )
        except:
            pass
        
        raise

if __name__ == "__main__":
    main()
