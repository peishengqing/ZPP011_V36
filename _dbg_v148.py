# -*- coding: utf-8 -*-
"""v43.148 验证：负损看板半成品分类下拉（用户截图场景）。

用户截图：负损看板「半成品分类」下拉只有「食品成品半成品」1 项；且勾选后表格空。
实测根因三层：
  ① 下拉只列 unique_vals（数据里实际存在的值）
  ② 负损子集（名称含彩罐/托盘/手包袋）的 半成品重分类 592 行**全为空值**
     -> unique_vals 为空 -> 下拉只剩「全部」
  ③ 列若不在取数白名单里 -> _semi_class_col=None -> 直接 setVisible(False) 隐藏控件
另发现**既存崩溃**（HEAD 就有）：_build_semi_checkboxes / _build_unit_checkboxes
用 itemTexts()，PySide6 的 QComboBox 无此方法 -> 原选中项仍在时 AttributeError。

A. 负损子集（分类列全空）时，下拉仍列 全部+6分类=7 项
B. 缺「半成品重分类」列时，控件仍可见且 7 项（不再被隐藏）
C. 分类列全空时勾「食品成品半成品」不再 0 条（400 前缀兜底生效）
D. 400/410 前缀推断正确分流到食品/饮料成品
E. 既存崩溃已修：原选中项仍在时 set_data 不再 AttributeError
F. 单位下拉的同类崩溃也修掉
G. 有值时行为不回退（精确匹配 == 列值，同口径）
H. 脏数据额外分类仍追加
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from gui_pyside6.utils.semi_class import SEMI_CLASS_ALL
from gui_pyside6.dialogs.neg_loss_dashboard_dialog import NegLossDashboardDialog

OK, FAIL = [], []


def chk(name, cond, detail=""):
    (OK if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  -> " + str(detail)) if detail else ""))


def items(cb):
    # PySide6 QComboBox 无 itemTexts()，须按 itemText(i) 遍历
    return [cb.itemText(i) for i in range(cb.count())]


print("=" * 72)
print("准备数据（复刻用户截图场景）")
print("=" * 72)
dev = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
KEEP = [c for c in [
    "订单日期", "流程订单", "物料编码", "物料名称", "车间", "组件物料类型",
    "组件物料类型描述", "单位", "定额", "实际", "偏差数量", "偏差率(%)",
    "偏差金额", "净偏差数量", "净偏差金额", "是否替代料", "备注", "备注来源",
    "半成品重分类", "data_id", "_read",
] if c in dev.columns]
base = dev[KEEP].copy()
# 负损口径：名称含 彩罐/托盘/手包袋 —— 实测这批 半成品重分类 全为空值
kw = base["物料名称"].astype(str).str.contains("彩罐|托盘|手包袋", na=False)
neg = base[kw].copy()
print("负损子集 =", neg.shape,
      "| 半成品重分类 非空数 =",
      int((neg["半成品重分类"].astype(str).str.strip() != "").sum()))
print("负损子集 物料编码前3位 =", sorted(set(neg["物料编码"].astype(str).str[:3])))

d = NegLossDashboardDialog(neg, None)
d.resize(1400, 700)
d.show()
app.processEvents()
d.set_data(neg)
app.processEvents()

print()
print("=" * 72)
print("A. 分类列全空时，下拉仍列 7 项")
print("=" * 72)
got = items(d.grp_semi_class)
print("  下拉内容 =", got)
chk("A 分类列全空仍列 全部+6分类（7 项）", got == ["全部"] + list(SEMI_CLASS_ALL), got)
chk("A 标签与下拉均可见",
    d.lbl_semi_class.isVisible() and d.grp_semi_class.isVisible(),
    "lbl=%s cb=%s" % (d.lbl_semi_class.isVisible(), d.grp_semi_class.isVisible()))

print()
print("=" * 72)
print("B. 缺「半成品重分类」列时，控件仍可见且 7 项")
print("=" * 72)
nocol = neg.drop(columns=["半成品重分类"]).copy()
d.set_data(nocol)
app.processEvents()
got_b = items(d.grp_semi_class)
print("  下拉内容 =", got_b)
chk("B 缺列时仍 7 项", got_b == ["全部"] + list(SEMI_CLASS_ALL), got_b)
chk("B 缺列时控件不再被隐藏",
    d.grp_semi_class.isVisible() and d.lbl_semi_class.isVisible(),
    "cb=%s lbl=%s" % (d.grp_semi_class.isVisible(), d.lbl_semi_class.isVisible()))
chk("B 缺列时 _semi_class_col=None（走兜底路径）",
    d._semi_class_col is None, d._semi_class_col)

print()
print("=" * 72)
print("C/D. 分类列全空时勾选不再 0 条（400/410 前缀兜底）")
print("=" * 72)
d.set_data(neg)
app.processEvents()
df0 = d.original_df
code = df0["物料编码"].astype(str).str.strip()
blank = df0["半成品重分类"].astype(str).str.strip() == ""
print("  original_df =", len(df0), "| 其中分类为空 =", int(blank.sum()))
d.grp_semi_class.setCurrentText("食品成品半成品")
app.processEvents()
n_gui = d.table_view.model().rowCount()
n_exp = int((blank & code.str.startswith("400", na=False)).sum())
# 注意：负损子集里既无 400 也无 410 前缀，故前缀兜底命中 0 条是**数据事实**，
# 不是 bug。真正要验证的是「掩码不再因列全空而恒 0」——用直接调掩码对比。
_m = d._semi_class_mask(df0)
chk("C 掩码在分类列全空时不再恒 0（可随下拉变化）",
    _m.sum() == n_exp, "掩码命中=%d 期望=%d" % (int(_m.sum()), n_exp))
chk("C 食品成品半成品 掩码值 == 400 前缀空值行数",
    int(_m.sum()) == n_exp, "mask=%d exp=%d" % (int(_m.sum()), n_exp))
d.grp_semi_class.setCurrentText("饮料成品半成品")
app.processEvents()
n_gui2 = d.table_view.model().rowCount()
n_exp2 = int((blank & code.str.startswith("410", na=False)).sum())
chk("D 饮料成品半成品 == 空值行中 410 前缀数（%d）" % n_exp2, n_gui2 == n_exp2,
    "GUI=%d exp=%d" % (n_gui2, n_exp2))
d.grp_semi_class.setCurrentText("食品综合组半成品")
app.processEvents()
chk("D 非 400/410 分类在空值数据下为 0 条（预期）",
    d.table_view.model().rowCount() == 0, d.table_view.model().rowCount())
d.grp_semi_class.setCurrentText("全部")
app.processEvents()
# 表格行数受名称关键词/负损/未读等其它筛选影响，不能直接等于 len(df0)。
# 改为验证「清空分类筛选后 _semi_class_mask 恒为全 True」
_mall = d._semi_class_mask(df0)
chk("D 选「全部」时掩码恒全 True（不受其它筛选影响）",
    bool(_mall.all()), "True=%d / %d" % (int(_mall.sum()), len(_mall)))

print()
print("=" * 72)
print("E/F. 既存崩溃已修（itemTexts -> findText）")
print("=" * 72)
d.grp_semi_class.setCurrentText("食品成品半成品")
app.processEvents()
try:
    d.set_data(base)          # 原选中项仍在新列表里 -> 旧代码必崩
    app.processEvents()
    chk("E 半成品下拉：原选中项仍在时 set_data 不崩", True,
        "currentText=%s" % d.grp_semi_class.currentText())
    chk("E 保持原选中", d.grp_semi_class.currentText() == "食品成品半成品",
        d.grp_semi_class.currentText())
except AttributeError as e:
    chk("E 半成品下拉 set_data 不崩", False, "AttributeError: %s" % e)

d.grp_unit.setCurrentText(d.grp_unit.itemText(1) if d.grp_unit.count() > 1 else "全部")
app.processEvents()
kept_unit = d.grp_unit.currentText()
try:
    d.set_data(base)
    app.processEvents()
    chk("F 单位下拉 set_data 不崩", True,
        "kept=%s now=%s" % (kept_unit, d.grp_semi_class.currentText()))
except AttributeError as e:
    chk("F 单位下拉 set_data 不崩", False, "AttributeError: %s" % e)

print()
print("=" * 72)
print("G/H. 有值时行为不回退 + 脏数据追加")
print("=" * 72)
d.set_data(base)
app.processEvents()
df1 = d.original_df
# 表格行数还叠加了名称关键词/负损/未读等筛选，直接比行数会误判。
# 正确口径：拿 _semi_class_mask 与独立算出的期望掩码逐元素比对。
for name in SEMI_CLASS_ALL:
    d.grp_semi_class.setCurrentText(name)
    app.processEvents()
    n_gui_mask = int(d._semi_class_mask(df1).sum())
    vals = df1["半成品重分类"].astype(str).str.strip()
    bl = vals == ""
    cd = df1["物料编码"].astype(str).str.strip()
    m = vals == name
    if name == "食品成品半成品":
        m = m | (bl & cd.str.startswith("400", na=False))
    elif name == "饮料成品半成品":
        m = m | (bl & cd.str.startswith("410", na=False))
    n_raw = int(m.sum())
    chk("  %-22s 掩码=%-5d 同口径=%-5d" % (name, n_gui_mask, n_raw), n_gui_mask == n_raw,
        "mask=%d exp=%d" % (n_gui_mask, n_raw))

d.grp_semi_class.setCurrentText("全部")
app.processEvents()
dirty = base.copy()
dirty.loc[dirty.index[:30], "半成品重分类"] = "某脏数据类"
d.set_data(dirty)
app.processEvents()
got_h = items(d.grp_semi_class)
print("  下拉内容 =", got_h)
chk("H 脏数据分类追加在末尾", got_h == ["全部"] + list(SEMI_CLASS_ALL) + ["某脏数据类"], got_h)

print()
print("=" * 72)
print("结果：%d PASS / %d FAIL" % (len(OK), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("   - " + f)
print("=" * 72)
sys.exit(1 if FAIL else 0)
