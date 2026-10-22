# -*- coding: utf-8 -*-
"""截半成品看板顶部两行排版图，供人工核对。"""
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
        "半成品重分类"]
sub = sub[[c for c in keep if c in sub.columns]].copy()
d = SemiDashboardDialog(sub, None)
d.resize(1280, 640)
d.show()
app.processEvents()
d.grab().save(r"E:/zpp011_v2/_v146_top.png")
print("saved E:/zpp011_v2/_v146_top.png")
# 只截顶部区域
top = d.findChildren(type(d.edit_keywords).__mro__[0])
from PySide6.QtWidgets import QScrollArea
sc = d.findChildren(QScrollArea)[0]
sc.grab().save(r"E:/zpp011_v2/_v146_toponly.png")
print("saved E:/zpp011_v2/_v146_toponly.png")
