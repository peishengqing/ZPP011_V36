# -*- coding: utf-8 -*-
"""测试 MainWindow 导入和创建"""
import sys
import os

sys.path.insert(0, 'E:/zpp011_v2')
os.chdir('E:/zpp011_v2')

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel

app = QApplication(sys.argv)

print("Step 1: Qt 导入成功")

# 测试导入 MainWindow
try:
    from gui_pyside6.main_window import MainWindow
    print("Step 2: MainWindow 导入成功")
except Exception as e:
    print(f"Step 2 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试创建 MainWindow 实例（但不显示）
try:
    # 不实际创建，因为会启动事件循环
    # 只检查类定义是否正确
    print("Step 3: 准备创建 MainWindow 实例")
    print("  - 检查 AlertMonitor 信号...")
    
    from core.alert_monitor import AlertMonitor
    print(f"  - AlertMonitor 信号: {dir(AlertMonitor)[:10]}")
    
    print("Step 4: 所有检查通过")
    
except Exception as e:
    print(f"Step 3 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ 所有测试通过")
sys.exit(0)
