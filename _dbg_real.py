# -*- coding: utf-8 -*-
"""用真实 xlsx 走完整管线复现「点全部出 0 条 / 无半成品重分类列」。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from analysis.analyzer import do_analysis_v2
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

SRC = r"H:/ZPP011导出文件原数据/ZPP011_20260901-20260930.xlsx"
OUT = r"C:/Temp/zpp_dev_out"
os.makedirs(OUT, exist_ok=True)
print("读取", SRC)
raw = pd.read_excel(SRC, sheet_name=0)
print("原始表 =", raw.shape)
dev = do_analysis_v2(SRC, OUT, {}, start_date="2026-09-01", end_date="2026-09-30",
                     material_search="", return_dataframe=True, input_df=raw)
print("dev_df =", dev.shape)
print("含半成品重分类列 =", "半成品重分类" in dev.columns)
code_col = next((c for c in ("物料编码", "组件物料号") if c in dev.columns), None)
sub = dev[dev[code_col].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
print("400/410 子集 =", sub.shape)
print("半成品重分类 唯一值:")
vc = sub["半成品重分类"].fillna("").astype(str).str.strip().value_counts()
for k, v in vc.items():
    print("   %-24s %5d" % (k or "(空)", v))

candidates = [
    "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
    "车间", "组件物料类型", "组件物料类型描述", "单位",
    "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
    "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
    "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
]
keep = [c for c in candidates if c in sub.columns]
print("看板白名单命中 =", keep)

dlg = SemiDashboardDialog(sub[keep].copy(), None)
dlg.resize(1400, 900)
dlg.show()
app.processEvents()
d = dlg.original_df
print("\nsemi_class_col =", dlg._semi_class_col)
print("复选框:")
for k, c in dlg._semi_class_checkboxes.items():
    print("   %-24s checked=%s" % (c.text(), c.isChecked()))
print("初始行数 =", dlg.source_model.rowCount(), "|", dlg.lbl_count.text())

print("\n--- 真点「全部」 ---")
dlg._semi_class_checkboxes["__all__"].click()
app.processEvents()
print("行数 =", dlg.source_model.rowCount(), "|", dlg.lbl_count.text())
print("filter =", sorted(dlg._semi_class_filter))
print("semi_mask sum =", int(dlg._semi_class_mask(dlg.original_df).sum()))
print("values 唯一值 =", sorted(set(dlg._semi_class_values(dlg.original_df)))[:10])

m = {
    "keywords": dlg._name_mask(dlg.original_df), "feed": dlg._feed_status_mask(dlg.original_df),
    "semi": dlg._semi_class_mask(dlg.original_df), "mtd": dlg._mtd_mask(dlg.original_df),
    "unit": dlg._unit_mask(dlg.original_df), "workshop": dlg._workshop_mask(dlg.original_df, dlg._workshop_filter),
    "quar": dlg._quar_mask(dlg.original_df, dlg._quar_filter), "note": dlg._note_mask(dlg.original_df, dlg._has_note_filter),
    "color": dlg._color_mask(dlg.original_df), "read": dlg._read_mask(dlg.original_df, dlg._read_filter),
}
print("\n各掩码:")
comb = None
for k, v in m.items():
    print("   %-9s sum=%5d" % (k, int(v.sum())))
    comb = v if comb is None else (comb & v)
print("   AND =", int(comb.sum()), " 实际行数 =", dlg.source_model.rowCount())
