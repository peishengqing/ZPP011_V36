# -*- coding: utf-8 -*-
"""复现：_semi_class_col 为 None（无半成品重分类列）时的兜底路径。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

N=20
df = pd.DataFrame({
 "工厂":["云南达利食品有限公司"]*N,"订单日期":["2026-10-03"]*N,
 "流程订单":["10034%04d"%i for i in range(N)],
 "组件物料号":["4000105%d"%(i%5) for i in range(N)],
 "组件物料号_str":["4000105%d"%(i%5) for i in range(N)],
 "物料编码":["4000105%d"%(i%5) for i in range(N)],
 "物料名称":["物料%02d"%i for i in range(N)],
 "组件物料类型描述":["食品半成品"]*N,"车间":["2车间"]*N,"单位":["包"]*N,
 # 故意不给「半成品重分类」列 -> _semi_class_col is None
 "数量-定额":[100]*N,"数量-实际":[0]*N,"偏差数量":[0]*N,
 "偏差率(%)":["-100.000%"]*N,"偏差金额":[0.0]*N,"备注原因":[""]*N,
 "_quarantined":["否"]*N,"_post_audit_changed":[""]*N,"_read":["N"]*N,
})
dlg = SemiDashboardDialog(df, None)
dlg.resize(1400,900); dlg.show(); app.processEvents()
print("semi_class_col =", dlg._semi_class_col, "(None=走前缀兜底)")
print("复选框:", {k:(c.text(),c.isChecked()) for k,c in dlg._semi_class_checkboxes.items()})
print("初始行数 =", dlg.source_model.rowCount(), "|", dlg.lbl_count.text())
d = dlg.original_df
vals = dlg._semi_class_values(d)
print("vals 唯一值 =", sorted(set(vals))[:8])
print()
for tag in ["初始"]:
    print("[%s] filter=%s 行数=%d" % (tag, sorted(dlg._semi_class_filter), dlg.source_model.rowCount()))
dlg._semi_class_checkboxes["__all__"].click()
app.processEvents()
print("[点全部] filter=%s 行数=%d | %s" % (sorted(dlg._semi_class_filter), dlg.source_model.rowCount(), dlg.lbl_count.text()))
print("semi_mask sum =", int(dlg._semi_class_mask(d).sum()))
