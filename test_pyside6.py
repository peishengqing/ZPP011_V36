#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在无显示环境下验证 PySide6 应用能否正常初始化"""
import sys, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import QSettings, QLocale, Qt

from gui_pyside6.main_window import MainWindow

app = QApplication(sys.argv)
app.setApplicationName("ZPP011")
app.setApplicationVersion("v42.0")

font = QFont("Microsoft YaHei", 9)
app.setFont(font)

try:
    from PySide6.QtWidgets import QStyleFactory
    if "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))
    print("[OK] QStyleFactory")
except Exception as e:
    print(f"[WARN] QStyleFactory: {e}")

# 不实际显示窗口，只测试初始化
win = MainWindow()
print("[OK] MainWindow 初始化成功")

# 验证模型
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
import pandas as pd
df = pd.DataFrame({"colA": [1, 2], "colB": ["x", "y"]})
model = DataFrameModel(df)
proxy = AuditProxyModel()
proxy.setSourceModel(model)
print(f"[OK] DataFrameModel rowCount={model.rowCount()} columnCount={model.columnCount()}")
print(f"[OK] AuditProxyModel rowCount={proxy.rowCount()}")

# 验证 workers
from gui_pyside6.models.workers import AnalysisWorker, AIAuditWorker
print("[OK] workers 导入成功")

print("\n✅ 所有检查通过")
sys.exit(0)
