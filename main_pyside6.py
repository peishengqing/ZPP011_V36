#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器 — PySide6 版本入口文件
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

# PyInstaller --noconsole: sys.stdout/stderr is None, redirect to devnull to avoid flush crash
if getattr(sys, 'frozen', False) and sys.stdout is None:
    class _NullWriter:
        def write(self, *a, **k): pass
        def flush(self): pass
        def close(self): pass
    sys.stdout = _NullWriter()
    sys.stderr = _NullWriter()

# 初始化日志系统
try:
    from core.logger import get_logger
    logger = get_logger("Startup")
    logger.info("程序启动 (PySide6版本)")
except Exception as e:
    print(f"日志初始化失败: {e}")

# 导入并运行主程序
try:
    from gui_pyside6.main_window import MainWindow
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setApplicationName("ZPP011生产偏差分析器")
    app.setOrganizationName("ZPP011")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
except Exception as e:
    import traceback
    error_msg = traceback.format_exc()
    print(f"启动失败: {error_msg}")
    
    # 如果是打包模式，显示错误对话框
    if getattr(sys, 'frozen', False):
        try:
            from PySide6.QtWidgets import QMessageBox
            from PySide6.QtCore import Qt
            app = QApplication(sys.argv)
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("启动错误")
            msg_box.setText(f"程序启动失败:\n\n{str(e)}")
            msg_box.setDetailedText(error_msg)
            msg_box.exec()
        except:
            pass
    
    input("按回车键退出...")
