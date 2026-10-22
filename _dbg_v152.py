# -*- coding: utf-8 -*-
"""v43.152 排查：未读概览弹窗「查看」按钮点了不定位"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd

df = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
df["_read"] = 0
df["_quarantined"] = 0
df["_post_audit_changed"] = 0
df["是否替代料"] = "否"
df.loc[df.index[:2], "_quarantined"] = 1
df.loc[df.index[2:5], "_post_audit_changed"] = 1

from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
app = QApplication.instance() or QApplication([])

# 屏蔽 QMessageBox，避免脚本阻塞
QMessageBox.information = staticmethod(lambda *a, **k: print("   [QMessageBox.information]", a[1:3]))
QMessageBox.critical = staticmethod(lambda *a, **k: print("   [QMessageBox.critical]", a[1:3]))

print("=" * 72)
print("列检查（callback 依赖的列是否都在）")
print("=" * 72)
for c in ["工厂", "订单日期", "流程订单", "物料编码", "物料名称", "偏差率(%)",
          "数量-定额", "数量-实际", "是否替代料", "_read", "_quarantined",
          "_post_audit_changed", "半成品重分类", "车间"]:
    print("  %-20s %s" % (c, "有" if c in df.columns else "❌ 缺"))

from gui_pyside6.widgets.unread_summary_popup import UnreadSummaryPopup

# 复刻 main_window._count_unread_items 的四个 callback
class FakeMW(QWidget):
    def _get_master_df(self):
        return df

    def _open_quarantine_dialog(self):
        print("   → _open_quarantine_dialog 被调用")
        from gui_pyside6.dialogs.quarantine_dialog import QuarantineDialog
        qdf = df[df["_quarantined"] == 1].copy().reset_index(drop=True)
        print("      隔离区行数:", len(qdf))
        return "quarantine-ok"

    def _show_audit_changes_dialog(self):
        print("   → _show_audit_changes_dialog 被调用")
        return "changes-ok"

    def _show_alert_dashboard(self):
        print("   → _show_alert_dashboard 被调用")
        return "alt-ok"

    def _show_deviation_warning_dialog(self):
        print("   → _show_deviation_warning_dialog 被调用")
        return "dev-ok"


mw = FakeMW()
items = [
    {"icon": "📦", "label": "隔离区", "count": 2, "callback": mw._open_quarantine_dialog},
    {"icon": "📝", "label": "变动提醒", "count": 3, "callback": mw._show_audit_changes_dialog},
    {"icon": "🔄", "label": "替代料", "count": 0, "callback": mw._show_alert_dashboard},
    {"icon": "⚠️", "label": "偏差率预警", "count": 9, "callback": mw._show_deviation_warning_dialog},
]

pop = UnreadSummaryPopup(items)
pop.show()
app.processEvents()

print("\n" + "=" * 72)
print("直接调 _open_board（绕过按钮，验证 callback 本身）")
print("=" * 72)
for it in items:
    print("[%s]" % it["label"])
    try:
        r = pop._open_board(it["callback"])
        print("   返回:", r)
    except Exception:
        traceback.print_exc()

print("\n" + "=" * 72)
print("关键：_open_board 里有 `except Exception: pass`，异常会被静默吞掉")
print("现在把 callback 换成会抛异常的，验证吞异常行为")
print("=" * 72)


def boom():
    raise RuntimeError("模拟真实异常")


pop._open_board(boom)
print("   ^ 抛了异常但没有任何提示 → 用户看到的就是「点了没反应」")

print("\n" + "=" * 72)
print("排查 _show_alert_dashboard 真实数据下的路径（替代料 0 条场景）")
print("=" * 72)
from analysis.post_process import filter_alt_alerts
try:
    alts = filter_alt_alerts(df, 10)
    print("  filter_alt_alerts 结果行数:", len(alts))
except Exception:
    traceback.print_exc()

print("\n" + "=" * 72)
print("排查 _show_deviation_warning_dialog 真实数据下的路径")
print("=" * 72)
rates = pd.to_numeric(df["偏差率(%)"], errors="coerce").fillna(0)
a = pd.to_numeric(df["数量-实际"], errors="coerce").fillna(0)
q = pd.to_numeric(df["数量-定额"], errors="coerce").fillna(0)
no_input = (a.abs() <= 0.001) & (q > 0.001)
mask = (rates.abs() >= 10) & (~no_input)
print("  偏差率预警命中:", int(mask.sum()))
print("  未读且命中:", int((mask & (df["_read"] == 0)).sum()))

print("\n" + "=" * 72)
print("各 popup 是否 parent=self 导致模态 dialog 被遮挡/无法激活？")
print("=" * 72)
print("  popup windowFlags 含 Qt.Tool + StaysOnTop → 关闭后 show() 回来")
print("  _open_board: self.hide() → callback() → 若未 closed 则 self.show()")
print("  ⚠ 关键：callback 是**模态 exec()**，popup 又是 Tool 窗口")
