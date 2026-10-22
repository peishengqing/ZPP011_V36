# -*- coding: utf-8 -*-
"""定位：点「全部」出 0 条的真因。"""
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
 "半成品重分类":["食品成品半成品"]*N,
 "数量-定额":[100]*N,"数量-实际":[0]*N,"偏差数量":[0]*N,
 "偏差率(%)":["-100.000%"]*N,"偏差金额":[0.0]*N,"备注原因":[""]*N,
 "_quarantined":["否"]*N,"_post_audit_changed":[""]*N,"_read":["N"]*N,
})
dlg = SemiDashboardDialog(df, None)
dlg.resize(1400,900); dlg.show(); app.processEvents()
d2 = dlg.original_df
print("original_df 行数 =", len(d2))
print("semi_class_col =", dlg._semi_class_col)
print("半成品重分类唯一值 =", sorted(d2['半成品重分类'].unique()) if '半成品重分类' in d2.columns else 'N/A')
print("复选框 =", {k: (c.text(), c.isChecked()) for k,c in dlg._semi_class_checkboxes.items()})
print("当前 _semi_class_filter =", dlg._semi_class_filter)
print("当前行数 =", dlg.source_model.rowCount())

def probe(tag):
    d = dlg.original_df
    m = {
      "keywords": dlg._name_mask(d),
      "feed": dlg._feed_status_mask(d),
      "semi": dlg._semi_class_mask(d),
      "mtd": dlg._mtd_mask(d),
      "unit": dlg._unit_mask(d),
      "workshop": dlg._workshop_mask(d, dlg._workshop_filter),
      "quar": dlg._quar_mask(d, dlg._quar_filter),
      "note": dlg._note_mask(d, dlg._has_note_filter),
      "color": dlg._color_mask(d),
      "read": dlg._read_mask(d, dlg._read_filter),
    }
    print("\n[%s] filter=%s" % (tag, dlg._semi_class_filter))
    for k,v in m.items():
        print("   %-9s sum=%3d" % (k, int(v.sum())))
    comb = None
    for v in m.values():
        comb = v if comb is None else (comb & v)
    print("   AND后 = %d  实际行数 = %d" % (int(comb.sum()), dlg.source_model.rowCount()))

probe("初始(默认勾食品+饮料)")

# 勾「全部」
dlg._semi_class_checkboxes["__all__"].setChecked(True)
app.processEvents()
probe("勾全部后")
print("\n全部复选框状态:", {k: c.isChecked() for k,c in dlg._semi_class_checkboxes.items()})
print("_semi_class_filter =", dlg._semi_class_filter)
print("lbl_count =", dlg.lbl_count.text())

# 只勾食品
dlg._semi_class_checkboxes["__all__"].setChecked(False)
dlg._semi_class_checkboxes["食品成品半成品"].setChecked(True)
app.processEvents()
probe("只勾食品")
print("lbl_count =", dlg.lbl_count.text())
