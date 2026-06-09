# -*- coding: utf-8 -*-
"""
ZPP011 PySide6 启动入口
裴哥 | 2026-06-04
"""
import sys
import os
import traceback

# 将项目根目录加入 sys.path，确保 gui_pyside6 可以正常导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ========== 全局异常捕获 ==========
def global_exception_hook(exc_type, exc_value, exc_tb):
    """捕获未处理的异常，同时输出到控制台和弹窗"""
    # 1. 打印详细堆栈到控制台
    traceback.print_exception(exc_type, exc_value, exc_tb)
    
    # 2. 弹出错误对话框
    try:
        from PySide6.QtWidgets import QMessageBox, QApplication
        # 获取当前活跃的 QApplication 实例
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None, 
                "严重错误", 
                f"程序发生未捕获的异常:\n\n{str(exc_value)}\n\n详细错误信息已输出到控制台。"
            )
    except Exception:
        pass  # 如果弹窗失败，至少控制台已经有输出了

# 设置全局异常钩子
sys.excepthook = global_exception_hook
# ========== 全局异常捕获结束 ==========

from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QFont
from PySide6.QtCore import QCoreApplication, QSettings, QLocale, Qt

from gui_pyside6.main_window import MainWindow


def main():
    # 高 DPI 支持（PySide6 >= 6.5 自动处理，无需手动设置）
    # 保留这两行是为了兼容旧版本，在新版本中无效果也不会报错
    # QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # Qt 6 已默认支持
    # QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # Qt 6 已默认支持

    app = QApplication(sys.argv)
    app.setApplicationName("ZPP011")
    app.setApplicationVersion("v42.0")
    app.setOrganizationName("云南达利食品有限公司")

    # 设置字体（中文友好）
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    # Fusion 样式 + 自定义 QSS 样式表
    if "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))

    # 加载现代化 QSS 样式表
    qss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_pyside6", "modern_style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        print("✅ 现代化样式已加载")
    else:
        print("⚠️ 样式文件不存在: " + qss_path)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

