# -*- coding: utf-8 -*-
"""复现：数据含多个半成品分类时，勾「全部」出 0 条。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

# 模拟真实分布：多种分类
cats = ["食品成品半成品"]*10 + ["饮料成品半成品"]*3 + ["食品综合组半成品"]*5 + ["食品配料中心半成品"]*2
N = len(cats)
df = pd.DataFrame({
 "工厂":["云南达利食品有限公司"]*N,"订单日期":["2026-10-03"]*N,
 "流程订单":["10034%04d"%i for i in range(N)],
 "组件物料号":["4000105%d"%(i%5) for i in range(N)],
 "组件物料号_str":["4000105%d"%(i%5) for i in range(N)],
 "物料编码":["4000105%d"%(i%5) for i in range(N)],
 "物料名称":["物料%02d"%i for i in range(N)],
 "组件物料类型描述":["食品半成品"]*N,"车间":["2车间"]*N,"单位":["包"]*N,
 "半成品重分类":cats,
 "数量-定额":[100]*N,"数量-实际":[0]*N,"偏差数量":[0]*N,
 "偏差率(%)":["-100.000%"]*N,"偏差金额":[0.0]*N,"备注原因":[""]*N,
 "_quarantined":["否"]*N,"_post_audit_changed":[""]*N,"_read":["N"]*N,
})
dlg = SemiDashboardDialog(df, None)
dlg.resize(1400,900); dlg.show(); app.processEvents()
print("original_df =", len(dlg.original_df))
print("复选框清单:")
for k,c in dlg._semi_class_checkboxes.items():
    print("   %-24s text=%-20s checked=%s" % (k, c.text(), c.isChecked()))
print("初始行数 =", dlg.source_model.rowCount(), "|", dlg.lbl_count.text())

print("\n--- 勾「全部」 ---")
dlg._semi_class_checkboxes["__all__"].setChecked(True)
app.processEvents()
print("行数 =", dlg.source_model.rowCount(), "|", dlg.lbl_count.text())
print("filter =", dlg._semi_class_filter)
print("各复选框:", {k: c.isChecked() for k,c in dlg._semi_class_checkboxes.items()})
m = dlg._semi_class_mask(dlg.original_df)
print("semi_mask sum =", int(m.sum()))
