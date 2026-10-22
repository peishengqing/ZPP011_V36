# -*- coding: utf-8 -*-
"""v43.152 排查3：真实点击「查看」按钮的完整时序（离屏）"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox

app = QApplication.instance() or QApplication([])
MSGS = []
QMessageBox.information = staticmethod(lambda *a, **k: MSGS.append(a[1:3]))
QMessageBox.critical = staticmethod(lambda *a, **k: MSGS.append(a[1:3]))

df = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
df["_read"] = 0
df["_quarantined"] = 0
df["_post_audit_changed"] = 0
df["是否替代料"] = "否"
df.loc[df.index[:2], "_quarantined"] = 1

from gui_pyside6.widgets.unread_summary_popup import UnreadSummaryPopup

CALLS = []


class MW(QWidget):
    def _open_quarantine_dialog(self):
        CALLS.append("隔离区")
        print("      → 隔离区窗口打开")

    def _show_audit_changes_dialog(self):
        CALLS.append("变动提醒")
        print("      → 变动提醒窗口打开")

    def _show_alert_dashboard(self):
        CALLS.append("替代料")
        print("      → 替代料窗口打开")

    def _show_deviation_warning_dialog(self):
        CALLS.append("偏差率预警")
        print("      → 偏差率预警窗口打开")


mw = MW()
items = [
    {"icon": "📦", "label": "隔离区", "count": 2, "callback": mw._open_quarantine_dialog},
    {"icon": "📝", "label": "变动提醒", "count": 0, "callback": mw._show_audit_changes_dialog},
    {"icon": "🔄", "label": "替代料", "count": 0, "callback": mw._show_alert_dashboard},
    {"icon": "⚠️", "label": "偏差率预警", "count": 9, "callback": mw._show_deviation_warning_dialog},
]

pop = UnreadSummaryPopup(items)
pop.show()
app.processEvents()

print("=" * 72)
print("popup 可见:", pop.isVisible(), " 几何:", pop.geometry())
print("=" * 72)

# 收集所有「查看」按钮
btns = pop.findChildren(type(pop.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)[0]))
from PySide6.QtWidgets import QPushButton
btns = [b for b in pop.findChildren(QPushButton) if b.text() == "查看"]
print("找到 %d 个「查看」按钮" % len(btns))

print("\n" + "=" * 72)
print("逐个 QTest 真实点击")
print("=" * 72)
labels = [it["label"] for it in items]
for i, b in enumerate(btns):
    CALLS.clear()
    MSGS.clear()
    print("[%s]" % labels[i])
    QTest.mouseClick(b, Qt.LeftButton, pos=QPoint(5, 5))
    app.processEvents()
    print("   callback 调用:", CALLS or "❌ 没调到")
    print("   消息框:", MSGS or "无")
    print("   popup 可见:", pop.isVisible(), " _closed:", pop._closed)

print("\n" + "=" * 72)
print("结论")
print("=" * 72)
print("若上面 callback 全部调到了 → 按钮链路正常，问题在 callback 内部")
print("（被 _open_board 的 `except Exception: pass` 吞掉真实异常）")
