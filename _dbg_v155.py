# -*- coding: utf-8 -*-
"""量一量半成品看板顶部 row2 各控件的真实几何，定位重叠根因（offscreen 真实构造）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtWidgets import QApplication, QScrollArea

from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

app = QApplication.instance() or QApplication([])

df = pd.read_pickle(r"C:\Temp\zpp_dev_out\dev.pkl").reset_index(drop=True)
if "半成品重分类" not in df.columns:
    df["半成品重分类"] = ""
if "隔离区" not in df.columns:
    df["隔离区"] = ""

dlg = SemiDashboardDialog(df, None)
dlg.resize(1150, 700)
dlg.show()
app.processEvents()
dlg._apply_filter()
app.processEvents()

print("=" * 78)
print("窗口: %s" % (dlg.geometry().getRect(),))

scroll = dlg.findChild(QScrollArea)
print("scroll: geom=%s widgetResizable=%s minH=%d maxH=%d" % (
    scroll.geometry().getRect(), scroll.widgetResizable(),
    scroll.minimumHeight(), scroll.maximumHeight()))
top_widget = scroll.widget()
print("top_widget: geom=%s sizeHint=%dx%d minimumSizeHint=%dx%d" % (
    top_widget.geometry().getRect(),
    top_widget.sizeHint().width(), top_widget.sizeHint().height(),
    top_widget.minimumSizeHint().width(), top_widget.minimumSizeHint().height()))

g = dlg.grp_semi_class
print("\ngrp_semi_class: geom=%s sizeHint=%dx%d minW=%d maxW=%d" % (
    g.geometry().getRect(), g.sizeHint().width(), g.sizeHint().height(),
    g.minimumWidth(), g.maximumWidth()))

lay = g.layout()
print("grid: geom=%s sizeHint=%dx%d minimumSize=%dx%d" % (
    lay.geometry().getRect(), lay.sizeHint().width(), lay.sizeHint().height(),
    lay.minimumSize().width(), lay.minimumSize().height()))
print("grid items:")
for i in range(lay.count()):
    it = lay.itemAt(i)
    if it.widget() is None:
        continue
    rp, cp, rspan, cspan = lay.getItemPosition(i)
    print("    (r%d,c%d) %-24s %s  sizeHint.w=%d" % (
        rp, cp, it.widget().text(), it.geometry().getRect(),
        it.widget().sizeHint().width()))

items = [("lbl_semi_class", dlg.lbl_semi_class),
         ("grp_semi_class", g),
         ("quar_sep", dlg.quar_sep),
         ("lbl_quar", dlg.lbl_quar),
         ("btn_quar_all", dlg.btn_quar_all),
         ("btn_quar_yes", dlg.btn_quar_yes),
         ("btn_quar_no", dlg.btn_quar_no),
         ("note_sep", dlg.note_sep),
         ("lbl_note", dlg.lbl_note),
         ("btn_note_all", dlg.btn_note_all),
         ("btn_note_yes", dlg.btn_note_yes),
         ("btn_note_no", dlg.btn_note_no),
         ("lbl_unit", dlg.lbl_unit),
         ("grp_unit", dlg.grp_unit),
         ("lbl_mtd", dlg.lbl_mtd),
         ("combo_mtd", dlg.combo_mtd),
         ("lbl_workshop", dlg.lbl_workshop),
         ("combo_workshop", dlg.combo_workshop),
         ("lbl_read", dlg.lbl_read),
         ("combo_read", dlg.combo_read),
         ("lbl_count", dlg.lbl_count),
         ("btn_refresh", dlg.btn_refresh),
         ("btn_col_filter", dlg.btn_col_filter),
         ("lbl_color", dlg.lbl_color),
         ("color_group", dlg.color_group)]

print("\n按 y 分行检查（同一行内 x 应单调递增、互不重叠）:")


def rowkey(w):
    # 换算到 top_widget 坐标再取 y，避免不同 parent 坐标系混淆
    p = w.mapTo(top_widget, w.rect().topLeft())
    return p.y()


groups = {}
for nm, wdg in items:
    if wdg is None:
        continue
    groups.setdefault(rowkey(wdg), []).append((nm, wdg))

overlap = 0
for y in sorted(groups):
    row = groups[y]
    print("  --- 行 y=%d (%d 项) ---" % (y, len(row)))
    prev_right = -1
    for nm, wdg in row:
        p = wdg.mapTo(top_widget, wdg.rect().topLeft())
        flag = ""
        if p.x() < prev_right:
            flag = "  <== 重叠"
            overlap += 1
        print("    %-16s x=%-5d w=%-4d right=%-5d%s" % (nm, p.x(), wdg.width(), p.x() + wdg.width(), flag))
        prev_right = max(prev_right, p.x() + wdg.width())

print("\n子项溢出 group 检查:")
bad = 0
for i in range(lay.count()):
    it = lay.itemAt(i)
    if it.widget() is None:
        continue
    w = it.widget()
    wr = w.geometry()
    if wr.left() < 0 or wr.right() > g.width() or wr.width() < w.sizeHint().width():
        print("  溢出 %-24s geom=%s 需要w=%d groupw=%d" % (
            w.text(), wr.getRect(), w.sizeHint().width(), g.width()))
        bad += 1
if not bad:
    print("  无溢出")

print("\n结论: row2 重叠 %d 处, 子项溢出 %d 处" % (overlap, bad))


# ---- 截图取证 ----
try:
    sc = dlg.findChild(QScrollArea)
    pm = sc.grab()
    pm.save(r"E:/zpp011_v2/_shot_v154_top.png")
    print("已保存 _shot_v154_top.png (%dx%d)" % (pm.width(), pm.height()))
except Exception as e:
    print("截图失败: %r" % e)
