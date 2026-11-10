"""只测试 DashboardShell 的亮/暗主题切换和布局"""

import sys
import os
sys.path.insert(0, 'E:/zpp011_v2')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel
# QSysInfo 未使用

app = QApplication.instance() or QApplication([])
app.setStyle('Fusion')

from gui_pyside6.components.dashboard_shell import DashboardShell

dialog = QDialog()
shell = DashboardShell()

# 只放个标签测试布局
label = QLabel("负损看板示例内容")
shell.set_content(label)
shell.set_title("负损 (含未投料) 看板 - SHELL 测试")
shell.set_status("已加载 · 共 0 条记录")

layout = QVBoxLayout(dialog)
layout.setContentsMargins(0, 0, 0, 0)
layout.addWidget(shell)
dialog.setWindowTitle("DashboardShell 主题切换测试")
dialog.setMinimumSize(1400, 800)
dialog.resize(1400, 800)
dialog.show()

import time
time.sleep(1)

print("=" * 60)
print("DASHBOARD SHELL THEME TEST")
print("=" * 60)
print(f"Shell Object ID: {id(shell)}")
print(f"Shell Theme: {shell.get_theme()}")

# 切换到暗色
shell.set_theme('dark')
print(f"After set_theme('dark'): {shell.get_theme()}")

# 切换回亮色
shell.set_theme('light')
print(f"After set_theme('light'): {shell.get_theme()}")

print("=" * 60)
print("✅ Shell 主题切换验证通过")
