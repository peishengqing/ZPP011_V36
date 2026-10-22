# -*- coding: utf-8 -*-
"""复现：勾「全部」时其它复选框仍勾选 -> 取消勾选的时序问题。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

cats = ["食品成品半成品"]*10 + ["食品综合组半成品"]*5
N=len(cats)
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

def show(tag):
    d = dlg.original_df
    print("[%s] 行数=%d filter=%s | %s" % (tag, dlg.source_model.rowCount(),
          sorted(dlg._semi_class_filter), dlg.lbl_count.text()))

show("初始")

# 场景A：先取消勾选（复选框被清空->0条），再勾「全部」
print("\n--- 场景A：先全不勾，再勾全部 ---")
for k,c in dlg._semi_class_checkboxes.items():
    if k != "__all__": c.setChecked(False)
app.processEvents()
show("全不勾")
dlg._semi_class_checkboxes["__all__"].setChecked(True)
app.processEvents()
show("再勾全部")

# 场景B：先勾全部，再取消其它
print("\n--- 场景B：先勾全部，再取消其它 ---")
dlg._semi_class_checkboxes["__all__"].setChecked(False)
for k,c in dlg._semi_class_checkboxes.items():
    if k != "__all__": c.setChecked(False)
app.processEvents()
dlg._semi_class_checkboxes["__all__"].setChecked(True)
app.processEvents()
show("勾全部")
for k,c in dlg._semi_class_checkboxes.items():
    if k != "__all__": c.setChecked(False)
app.processEvents()
show("勾全部后再取消其它")

# 场景C：直接点「全部」复选框（用户真实操作）
print("\n--- 场景C：从默认态点「全部」---")
dlg2 = SemiDashboardDialog(df, None)
dlg2.resize(1400,900); dlg2.show(); app.processEvents()
print("初始:", dlg2.source_model.rowCount())
dlg2._semi_class_checkboxes["__all__"].click()   # 真点击
app.processEvents()
print("点全部后:", dlg2.source_model.rowCount(), dlg2.lbl_count.text())
print("各框:", {k: c.isChecked() for k,c in dlg2._semi_class_checkboxes.items()})
