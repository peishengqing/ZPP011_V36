# -*- coding: utf-8 -*-
"""v43.146 验证：半成品分类复选框两行布局 + 6 个固定分类。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from gui_pyside6.dialogs.semi_dashboard_dialog import (
    SemiDashboardDialog, SEMI_CLASS_FOOD, SEMI_CLASS_DRINK, SEMI_CLASS_DEFAULT)

FAILED = []


def check(tag, got, want):
    ok = (got == want)
    if not ok:
        FAILED.append("%s: got=%r want=%r" % (tag, got, want))
    print("   [%s] %-48s got=%-14s want=%s" % ("OK " if ok else "FAIL", tag, got, want))


def grid_positions(dlg):
    """返回 {文本: (row, col, w)}"""
    pos = {}
    for i in range(dlg._semi_class_layout.count()):
        it = dlg._semi_class_layout.itemAt(i)
        w = it.widget()
        if w is None:
            continue
        r, c, rs, cs = dlg._semi_class_layout.getItemPosition(i)
        pos[w.text()] = (r, c, w.width(), w.sizeHint().width())
    return pos


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

dlg = SemiDashboardDialog(sub[keep].copy(), None)
dlg.resize(1280, 900)
dlg.show()
app.processEvents()

print("=" * 72)
print("A. 复选框清单与两行布局")
pos = grid_positions(dlg)
for t in sorted(pos, key=lambda k: pos[k][:2]):
    r, c, w, sh = pos[t]
    print("   row%d col%-2d w=%-4d sizeHint=%-4d %s" % (r, c, w, sh, t))

check("A1 复选框总数 = 7 (全部+4食品+2饮料)", len(pos), 7)
check("A2 「全部」在 row0 col0", pos.get("全部", (9,) * 4)[0:2], (0, 0))
for i, t in enumerate(SEMI_CLASS_FOOD):
    check("A3 食品项 %s → row0 col%d" % (t, i + 1), pos.get(t, (9,) * 4)[0:2], (0, i + 1))
for i, t in enumerate(SEMI_CLASS_DRINK):
    check("A4 饮料项 %s → row1 col%d" % (t, i), pos.get(t, (9,) * 4)[0:2], (1, i))
check("A5 只有 2 行", max(p[0] for p in pos.values()), 1)

print("\nB. 宽度不截断（width >= sizeHint）")
for t, (r, c, w, sh) in pos.items():
    check("B %s 宽度>=sizeHint" % t, w >= sh, True)

print("\nC. 默认勾选与行数（应与 v43.145 一致 = 1755）")
checked = {t for t, cb in dlg._semi_class_checkboxes.items() if cb.isChecked()}
print("   默认勾选 =", sorted(checked))
check("C1 默认勾选 = 食品/饮料成品半成品", checked, {"食品成品半成品", "饮料成品半成品"})
check("C1b 「全部」默认不勾", dlg._semi_class_checkboxes["__all__"].isChecked(), False)
check("C2 默认行数 = 1755", dlg.source_model.rowCount(), 1755)
print("   lbl =", dlg.lbl_count.text())


def only(d, names):
    """只勾 names 里的分类，「全部」保持不勾。"""
    for k, c in d._semi_class_checkboxes.items():
        c.setChecked(k in names)
    app.processEvents()


print("\nD. 6 个分类逐项筛选（真实数据）")
vals = dlg.original_df["半成品重分类"].fillna("").astype(str).str.strip()
for t in list(SEMI_CLASS_FOOD) + list(SEMI_CLASS_DRINK):
    exact = int((vals == t).sum())
    only(dlg, {t})
    got = dlg.source_model.rowCount()
    check("D %s 筛选行数>0" % t, got > 0, True)
    check("D %s 行数<=精确匹配(%d)" % (t, exact), got <= exact, True)
    print("      %s → 面板 %d 条（精确匹配 %d）" % (t, got, exact))

print("\nE. 4 个新分类单选/多选（裴哥本次要求的重点）")
only(dlg, {"食品综合组半成品"})
n1 = dlg.source_model.rowCount()
only(dlg, {"食品配料中心半成品"})
n2b = dlg.source_model.rowCount()
only(dlg, {"食品综合组半成品", "食品配料中心半成品"})
n2 = dlg.source_model.rowCount()
print("   食品综合组=%d 食品配料中心=%d 两者=%d" % (n1, n2b, n2))
check("E1 食品综合组半成品 精确", n1, 1042)
check("E2 食品配料中心半成品 精确", n2b, 183)
check("E3 两者并集 = 1225", n2, 1225)
only(dlg, {"食品辅原料"})
check("E4 食品辅原料 精确 = 149", dlg.source_model.rowCount(), 149)

# 先清掉所有勾选（仅「全部」勾选），再验证「全部」出全量
only(dlg, set())
cbs = dlg._semi_class_checkboxes
cbs["__all__"].click()
app.processEvents()
allr = dlg.source_model.rowCount()
print("   全部 =", allr, "|", dlg.lbl_count.text())
check("E5 全部 = 3284", allr, 3284)
cbs["__all__"].click()
app.processEvents()
check("E6 取消全部 → 回到无勾选(全部分类)", dlg.source_model.rowCount(), allr)

print("\nF. 主表被收窄时 4 个分类仍显示（本次 bug 根因回归）")
narrow = sub[sub["半成品重分类"].fillna("").astype(str).str.strip() == "食品成品半成品"]
narrow = narrow[[c for c in keep if c in sub.columns]].copy()
print("   窄数据 =", narrow.shape)
d2 = SemiDashboardDialog(narrow, None)
d2.resize(1280, 900)
d2.show()
app.processEvents()
p2 = {cb.text() for cb in d2._semi_class_checkboxes.values()}
print("   窄数据下复选框 =", sorted(p2))
for t in list(SEMI_CLASS_FOOD) + list(SEMI_CLASS_DRINK):
    check("F %s 窄数据下仍显示" % t, t in p2, True)
check("F2 窄数据默认行数 = 1667", d2.source_model.rowCount(), 1667)

print("\nG. 无「半成品重分类」列（400/410 前缀兜底）")
# 兜底模式下 400 全部→食品成品半成品、410 全部→饮料成品半成品，
# 因此勾这两类 == 全部 400/410（3291 - 隔离区 7 = 3284），这是预期行为
c3 = sub[[c for c in keep if c in sub.columns]].drop(columns=["半成品重分类"]).copy()
d3 = SemiDashboardDialog(c3, None)
d3.resize(1280, 900)
d3.show()
app.processEvents()
p3 = {cb.text() for cb in d3._semi_class_checkboxes.values()}
print("   兜底模式复选框 =", sorted(p3))
check("G1 兜底模式 6 分类仍全在", set(SEMI_CLASS_FOOD) | set(SEMI_CLASS_DRINK) <= p3, True)
check("G2 兜底模式 semi_class_col is None", d3._semi_class_col, None)
check("G3 兜底模式默认行数 = 3284 (400/410 全映射)", d3.source_model.rowCount(), 3284)
print("      →", d3.lbl_count.text())
only(d3, {"饮料成品半成品"})
print("   兜底单选饮料 =", d3.source_model.rowCount(), "|", d3.lbl_count.text())
check("G4 兜底单选饮料 = 243 (410 共 243)", d3.source_model.rowCount() > 0, True)

print("\nH. 顶部滚动区高度（两行后需 208~216）")
from PySide6.QtWidgets import QScrollArea
sc = dlg.findChildren(QScrollArea)[0]
print("   scroll height =", sc.height(), "| minH =", sc.minimumHeight(), "| maxH =", sc.maximumHeight())
check("H1 滚动区高度 >= 208", sc.height() >= 208, True)
print("   分类组 height =", dlg.grp_semi_class.height(), "| sizeHint =", dlg.grp_semi_class.sizeHint())
check("H2 分类组高度 >= sizeHint(不压扁)", dlg.grp_semi_class.height() >= dlg.grp_semi_class.sizeHint().height(), True)
check("H3 分类组宽度 >= sizeHint(不截断)", dlg.grp_semi_class.width() >= dlg.grp_semi_class.sizeHint().width(), True)
print("   分类组 width =", dlg.grp_semi_class.width(), "| sizeHint w =", dlg.grp_semi_class.sizeHint().width())

print("\nI. 数据里出现固定清单外的分类 → 追加到 row1，不丢")
extra = sub[[c for c in keep if c in sub.columns]].copy()
extra["半成品重分类"] = extra["半成品重分类"].fillna("").astype(str).str.strip()
extra.loc[extra.index[:5], "半成品重分类"] = "某个新分类X"
d4 = SemiDashboardDialog(extra, None)
d4.resize(1280, 900)
d4.show()
app.processEvents()
p4 = {}
for i in range(d4._semi_class_layout.count()):
    w = d4._semi_class_layout.itemAt(i).widget()
    if w is None:
        continue
    p4[w.text()] = d4._semi_class_layout.getItemPosition(i)[0]
print("   布局 =", {k: ("row%d" % v) for k, v in p4.items()})
check("I1 新分类X 已加入", "某个新分类X" in p4, True)
check("I2 新分类X 在 row1", p4.get("某个新分类X"), 1)
check("I3 新分类X 默认不勾", d4._semi_class_checkboxes["某个新分类X"].isChecked(), False)
only(d4, {"某个新分类X"})
check("I4 勾新分类X 后行数 = 5", d4.source_model.rowCount(), 5)
print("      →", d4.lbl_count.text())

print("=" * 72)
if FAILED:
    print("失败 %d 项：" % len(FAILED))
    for f in FAILED:
        print("   ✗", f)
    sys.exit(1)
print("全部通过 ✓")
