# -*- coding: utf-8 -*-
"""v43.145 验证：半成品看板分类掩码修复。真实数据 + 合成数据双测。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

FAILED = []


def check(tag, got, want):
    ok = (got == want)
    if not ok:
        FAILED.append("%s: got=%s want=%s" % (tag, got, want))
    print("   [%s] %-46s got=%-6s want=%s" % ("OK " if ok else "FAIL", tag, got, want))


# ============================================================ 场景 A：真实数据
print("=" * 70)
print("场景 A：真实数据 ZPP011_20260901-20260930.xlsx")
dev = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
code_col = "物料编码"
sub = dev[dev[code_col].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
candidates = [
    "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
    "车间", "组件物料类型", "组件物料类型描述", "单位",
    "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
    "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
    "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
]
keep = [c for c in candidates if c in sub.columns]
print("白名单命中(无工厂列) =", "工厂" in keep, "| 列数 =", len(keep))

dlg = SemiDashboardDialog(sub[keep].copy(), None)
dlg.resize(1400, 900)
dlg.show()
app.processEvents()
# 注意：set_data 末尾已按「默认勾选」跑过一次 _apply_filter，
# 所以这里的初始行数就是默认勾选（食品+饮料成品半成品）后的行数。
default_rows = dlg.source_model.rowCount()
print("   默认勾选后行数 =", default_rows)
check("A0 默认勾选即 1667+88=1755", default_rows, 1755)

# 1. 默认勾选：应 >0（这是原来报 0 的场景）
check("A1 默认勾选(食品+饮料成品半成品)", dlg.source_model.rowCount() > 0, True)
print("      lbl =", dlg.lbl_count.text())

# 2. 单独勾食品成品半成品：应等于纯精确匹配数（1674 中未读未隔离的部分）
cbs = dlg._semi_class_checkboxes
cbs["__all__"].setChecked(False)
cbs["饮料成品半成品"].setChecked(False)
cbs["食品成品半成品"].setChecked(True)
app.processEvents()
d = dlg.original_df
exact_food = int((d["半成品重分类"].astype(str).str.strip() == "食品成品半成品").sum())
print("   精确匹配 食品成品半成品 =", exact_food, "→ 面板显示", dlg.source_model.rowCount())
check("A2 单选食品成品半成品 行数>0", dlg.source_model.rowCount() > 0, True)
check("A3 单选行数 <= 精确匹配数", dlg.source_model.rowCount() <= exact_food, True)

# 3. 勾饮料成品半成品：两行都有
cbs["饮料成品半成品"].setChecked(True)
app.processEvents()
two = dlg.source_model.rowCount()
print("   食品+饮料 =", two, "|", dlg.lbl_count.text())
check("A4 两类同时勾 仍>0", two > 0, True)

# 4. 点「全部」：应全部 400/410 子集（除隔离区 7 条）
cbs["__all__"].setChecked(True)
app.processEvents()
allrows = dlg.source_model.rowCount()
print("   全部 =", allrows, "|", dlg.lbl_count.text())
check("A5 全部 > 两类", allrows > two, True)
check("A6 全部 == 400/410 子集 3291 - 隔离区 7", allrows, 3284)
check("A6b 默认勾选 < 全部", default_rows < allrows, True)

# 5. 取消「全部」→ 回到无勾选 = 全部（空集=全True）
cbs["__all__"].setChecked(False)
cbs["食品成品半成品"].setChecked(False)
cbs["饮料成品半成品"].setChecked(False)
app.processEvents()
check("A7 全不勾 == 全部", dlg.source_model.rowCount(), allrows)

# 6. 多选：食品成品半成品 + 食品综合组半成品
cbs["食品成品半成品"].setChecked(True)
cbs["食品综合组半成品"].setChecked(True)
app.processEvents()
combo = dlg.source_model.rowCount()
print("   食品成品+食品综合组 =", combo, "|", dlg.lbl_count.text())
check("A8 多选 > 单类", combo > 1667, True)
check("A8b 多选 < 全部", combo < allrows, True)

# 7. 复选框里工厂列不存在时不应崩、且不靠工厂过滤
check("A9 df 无工厂列", "工厂" in dlg.original_df.columns, False)

# ============================================================ 场景 B：带工厂列（含空值兜底）
print("=" * 70)
print("场景 B：df 含「工厂」列 → 空值行的工厂名兜底应生效")
b = sub[keep].copy()
b["工厂"] = "云南达利食品有限公司"
b["半成品重分类"] = b["半成品重分类"].fillna("").astype(str).str.strip()
# 人工造几条空分类行：饮料厂 / 食品厂
n = len(b)
extra = b.iloc[:6].copy()
extra["工厂"] = ["云南达利食品有限公司"] * 3 + ["云南达利饮料有限公司"] * 3
extra["半成品重分类"] = [""] * 6
b2 = pd.concat([b, extra], ignore_index=True)
d2 = SemiDashboardDialog(b2, None)
d2.resize(1400, 900)
d2.show()
app.processEvents()
base2 = d2.source_model.rowCount()
print("   含兜底基线 =", base2)
check("B1 默认勾选 >0", base2 > 0, True)
c2 = d2._semi_class_checkboxes
c2["__all__"].setChecked(True)
app.processEvents()
print("   全部 =", d2.source_model.rowCount())
check("B2 全部 >= 基线", d2.source_model.rowCount() >= base2, True)

# 直接验掩码：食品成品半成品应含 3 条空值食品行
d2._semi_class_checkboxes["__all__"].setChecked(False)
for k, c in d2._semi_class_checkboxes.items():
    if k != "食品成品半成品":
        c.setChecked(False)
app.processEvents()
vals = d2._semi_class_values(d2.original_df)
mk = d2._semi_class_mask(d2.original_df)
blank = vals == ""
print("   空分类行数 =", int(blank.sum()),
      "| 其中食品厂 =", int((blank & (d2.original_df['工厂'].str.contains('食品'))).sum()))
check("B3 食品掩码命中空值食品行",
      int((mk & blank & (d2.original_df['工厂'].str.contains('食品'))).sum()),
      int((blank & (d2.original_df['工厂'].str.contains('食品'))).sum()))
check("B4 食品掩码不含空值饮料行",
      int((mk & blank & (d2.original_df['工厂'].str.contains('饮料'))).sum()), 0)

# ============================================================ 场景 C：无半成品重分类列（400/410 前缀兜底）
print("=" * 70)
print("场景 C：无「半成品重分类」列 → 前缀兜底")
c = b[keep].copy()
c = c.drop(columns=["半成品重分类"])
d3 = SemiDashboardDialog(c, None)
d3.resize(1400, 900)
d3.show()
app.processEvents()
print("   semi_class_col =", d3._semi_class_col)
print("   复选框 =", {cc.text(): cc.isChecked() for cc in d3._semi_class_checkboxes.values()})
check("C1 前缀兜底默认 >0", d3.source_model.rowCount() > 0, True)
d3._semi_class_checkboxes["__all__"].click()
app.processEvents()
print("   全部 =", d3.source_model.rowCount(), "|", d3.lbl_count.text())
check("C2 前缀兜底 全部 >0", d3.source_model.rowCount() > 0, True)

# ============================================================ 汇总
print("=" * 70)
if FAILED:
    print("失败 %d 项：" % len(FAILED))
    for f in FAILED:
        print("   ✗", f)
    sys.exit(1)
print("全部通过 ✓")
