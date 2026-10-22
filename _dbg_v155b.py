# -*- coding: utf-8 -*-
"""量四个看板顶部 4 行的 sizeHint / minimumSize，找出到底哪行超宽。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtWidgets import (QApplication, QScrollArea, QHBoxLayout,
                               QVBoxLayout, QWidget)

app = QApplication.instance() or QApplication([])

df = pd.read_pickle(r"C:\Temp\zpp_dev_out\dev.pkl").reset_index(drop=True)
for c in ("半成品重分类", "隔离区", "备注"):
    if c not in df.columns:
        df[c] = ""


def probe(cls, title, w=1150):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    try:
        dlg = cls(df, None)
    except TypeError:
        dlg = cls(df)
    dlg.resize(w, 700)
    dlg.show()
    app.processEvents()
    for m in ("_apply_filter", "set_data", "_refresh"):
        if hasattr(dlg, m):
            try:
                getattr(dlg, m)()
            except Exception:
                pass
            app.processEvents()
            break
    dlg.show()
    app.processEvents()

    sc = dlg.findChild(QScrollArea)
    if sc is None:
        print("  无 QScrollArea")
        return dlg
    tw = sc.widget()
    lay = tw.layout()
    print("  scroll 可视宽=%d  widgetResizable=%s" % (sc.viewport().width(),
                                                    sc.widgetResizable()))
    print("  top_widget 实际=%dx%d  sizeHint=%dx%d  minimumSizeHint=%dx%d" % (
        tw.width(), tw.height(),
        tw.sizeHint().width(), tw.sizeHint().height(),
        tw.minimumSizeHint().width(), tw.minimumSizeHint().height()))
    print("  容器布局 minimumSize=%dx%d  sizeHint=%dx%d" % (
        lay.minimumSize().width(), lay.minimumSize().height(),
        lay.sizeHint().width(), lay.sizeHint().height()))
    avail = sc.viewport().width()
    for i in range(lay.count()):
        it = lay.itemAt(i)
        sub = it.layout() if it.layout() is not None else (it.widget() if it.widget() else None)
        if sub is None:
            continue
        if isinstance(sub, QHBoxLayout):
            nm = "row%d (QHBox)" % (i + 1)
        elif isinstance(sub, QVBoxLayout):
            nm = "row%d (QVBox)" % (i + 1)
        else:
            nm = "row%d %s" % (i + 1, type(sub).__name__)
        sh = sub.sizeHint().width()
        mn = sub.minimumSize().width()
        flag = ""
        if mn > avail:
            flag = "  <== 最小宽度超可用 %dpx，会被压缩→重叠" % (mn - avail)
        print("    %-18s sizeHint=%-6d minimum=%-6d%s" % (nm, sh, mn, flag))
    return dlg


from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog
from gui_pyside6.dialogs.neg_loss_dashboard_dialog import NegLossDashboardDialog
from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog

probe(SemiDashboardDialog, "半成品看板 SemiDashboardDialog")
try:
    probe(NegLossDashboardDialog, "负损看板 NegLossDashboardDialog")
except Exception as e:
    print("  负损看板跳过: %r" % e)
try:
    probe(DeviationWarningDialog, "偏差率预警 DeviationWarningDialog")
except Exception as e:
    print("  偏差率预警跳过: %r" % e)
