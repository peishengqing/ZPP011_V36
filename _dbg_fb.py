# -*- coding: utf-8 -*-
"""单独查：兜底模式（无半成品重分类列）默认为何 3284 条。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

dev = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
sub = dev[dev["物料编码"].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
keep = ["订单日期", "流程订单", "物料编码", "物料名称", "车间", "组件物料类型",
        "组件物料类型描述", "单位", "定额", "实际", "偏差数量", "偏差率(%)",
        "偏差金额", "净偏差数量", "净偏差金额", "是否替代料", "备注", "备注来源",
        "半成品重分类", "data_id", "_read"]
c3 = sub[keep].drop(columns=["半成品重分类"]).copy()
d3 = SemiDashboardDialog(c3, None)
d3.resize(1280, 900)
d3.show()
app.processEvents()

print("semi_class_col =", d3._semi_class_col)
print("filter =", sorted(d3._semi_class_filter))
print("勾选 =", {cb.text(): cb.isChecked() for cb in d3._semi_class_checkboxes.values()})
vals = d3._semi_class_values(d3.original_df)
print("vals 唯一值 =", sorted(set(vals)))
print("vals 计数 =", vals.value_counts().to_dict())
mk = d3._semi_class_mask(d3.original_df)
print("mask sum =", int(mk.sum()), " 行数 =", d3.source_model.rowCount())
print("lbl =", d3.lbl_count.text())
print("_read_filter =", d3._read_filter, "| _quar_filter =", d3._quar_filter)
print("_color_mask sum =", int(d3._color_mask(d3.original_df).sum()))
print("_read_mask sum =", int(d3._read_mask(d3.original_df, d3._read_filter).sum()))
print("_quar_mask sum =", int(d3._quar_mask(d3.original_df, d3._quar_filter).sum()))
