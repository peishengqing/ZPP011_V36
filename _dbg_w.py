# -*- coding: utf-8 -*-
"""量各行 sizeHint 宽度，确认 1280 窗口下不溢出。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication, QScrollArea, QHBoxLayout
app = QApplication.instance() or QApplication([])
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

dev = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
sub = dev[dev["物料编码"].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
keep = ["订单日期", "流程订单", "物料编码", "物料名称", "车间", "组件物料类型",
        "组件物料类型描述", "单位", "定额", "实际", "偏差数量", "偏差率(%)",
        "偏差金额", "净偏差数量", "净偏差金额", "是否替代料", "备注", "备注来源",
        "半成品重分类"]
sub = sub[[c for c in keep if c in sub.columns]].copy()
d = SemiDashboardDialog(sub, None)
d.resize(1280, 640)
d.show()
app.processEvents()

sc = d.findChildren(QScrollArea)[0]
tw = sc.widget()
print("窗口 w =", d.width())
print("scroll viewport w =", sc.viewport().width())
print("top_widget w =", tw.width(), " sizeHint w =", tw.sizeHint().width())
print("分类组 w =", d.grp_semi_class.width(), "sizeHint w =", d.grp_semi_class.sizeHint().width())
print("横向滚动条 visible =", sc.horizontalScrollBar().isVisible())

from PySide6.QtWidgets import QVBoxLayout
lay = tw.layout()
for i in range(lay.count()):
    it = lay.itemAt(i)
    if it.layout() is not None:
        print("  row%d sizeHint w = %d" % (i, it.sizeHint().width()))
    elif it.widget() is not None:
        print("  row%d widget %s w=%d" % (i, it.widget().__class__.__name__, it.sizeHint().width()))

# 检查两行各自内容宽度
g = d.grp_semi_class.layout()
r0 = sum(g.itemAtPosition(0, c).sizeHint().width() for c in range(g.columnCount())
         if g.itemAtPosition(0, c) is not None)
r1 = sum(g.itemAtPosition(1, c).sizeHint().width() for c in range(g.columnCount())
         if g.itemAtPosition(1, c) is not None)
print("分类组 row0 内容宽 =", r0, " row1 内容宽 =", r1)
print("分类列数 =", g.columnCount(), " 行数 =", g.rowCount())
print("溢出? top_widget %d vs scroll viewport %d" % (tw.width(), sc.viewport().width()))

print("\n=== 1280x640 下逐项宽度（真实窗口尺寸）===")
bad = []
for i in range(d._semi_class_layout.count()):
    w = d._semi_class_layout.itemAt(i).widget()
    if w is None:
        continue
    r, c, _, _ = d._semi_class_layout.getItemPosition(i)
    ok = w.width() >= w.sizeHint().width()
    if not ok:
        bad.append(w.text())
    print("   row%d col%d %-12s w=%-4d sizeHint=%-4d %s"
          % (r, c, w.text(), w.width(), w.sizeHint().width(), "OK" if ok else "*** 截断 ***"))
print("截断项 =", bad if bad else "无")
print("分类组实际 w =", d.grp_semi_class.width())
