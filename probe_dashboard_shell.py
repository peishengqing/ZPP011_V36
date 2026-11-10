"""探针脚本：测试 DashboardShell + NegLossContent 的基础功能"""

import sys
import os
sys.path.insert(0, 'E:/zpp011_v2')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout
from PySide6.QtCore import QSysInfo

app = QApplication.instance() or QApplication([])
app.setStyle('Fusion')

# 导入模块
from gui_pyside6.components.dashboard_shell import DashboardShell
from gui_pyside6.widgets.neg_loss_content import NegLossContent

# 创建对话框和组件
dialog = QDialog()
shell = DashboardShell()

# 创建内容组件并模拟设置数据
content = NegLossContent(app)
content.set_data(type('FakeDF', (), {'columns': [], 'empty': True, '__getitem__': lambda self, x: []})())

# 设置标题和状态
shell.set_title("负损(含未投料)看板 - 探针测试")
shell.set_content(content)
shell.set_status("探针模式 · 主题：亮色")

# 添加到对话框
layout = QVBoxLayout(dialog)
layout.setContentsMargins(0, 0, 0, 0)
layout.addWidget(shell)
dialog.setWindowTitle("DashboardShell 探针")
dialog.setMinimumSize(1400, 800)
dialog.show()
dialog.activateWindow()

# 延时检查
import time
time.sleep(1)

# 输出探针报告
print("=" * 60)
print("DASHBOARD SHELL PROBE REPORT")
print("=" * 60)
print(f"Qt Version: {QSysInfo.qtVersion()}")
print(f"Platform: {QSysInfo.productType()}")
print(f"Shell Object ID: {id(shell)}")
print(f"Shell Title: {shell.windowTitle()}")
print(f"Shell Theme QSS loaded: {len(shell.styleSheet()) > 0}")
print(f"Content Widget ID: {id(content)}")
print(f"Layout Structure: {'OK' if shell.layout() is not None else 'FAILED'}")

# 主题切换测试
shell.set_theme('dark')
print(f"Dark theme applied: {shell.get_theme() == 'dark'}")

shell.set_theme('light')
print(f"Light theme applied: {shell.get_theme() == 'light'}")

print("=" * 60)
print("✅ 探针完成")
