# -*- coding: utf-8 -*-
"""v43.147 验证：四处复选框重复项残影（setParent(None)）+ 固定分类清单 + 两行排版。

核心断言：
  A. 四个界面 set_data 连调 3 次后，布局项数 == grp 的 QCheckBox 子控件数（零残影）
  B. 复选框清单无重复，替代料看板 = 全部 + 6 分类 = 7 项
  C. 替代料看板两行布局：row0 全在食品侧、row1 全在饮料侧
  D. 半成品看板 v43.146 行为不回退（默认 1755 / 6 分类逐项数字）
  E. 筛选逻辑正确（勾某类 == 列值精确匹配）
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication, QCheckBox
from PySide6.QtGui import QFontMetrics
app = QApplication.instance() or QApplication([])

from core.alert_monitor import filter_alt_alerts
from gui_pyside6.utils.semi_class import (
    SEMI_CLASS_ALL, SEMI_CLASS_DEFAULT, merge_semi_class_values,
)
from gui_pyside6.dialogs.alert_dialog import AlertDialog
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog
from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog
from gui_pyside6.widgets.filter_panel import FilterPanel

OK, FAIL = [], []


def chk(name, cond, detail=""):
    (OK if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  -> " + str(detail)) if detail else ""))


def only(dlg, names):
    """只勾选 names 里的分类（'__all__' 不在其中），清掉其他。"""
    for k, cb in dlg._semi_class_checkboxes.items():
        cb.blockSignals(True)
        cb.setChecked(k in names)
        cb.blockSignals(False)
    dlg._on_semi_class_changed()


def no_residue(dlg, grp_name, lay_name, tag):
    """核心断言：连调 3 次 set_data 后零残影。"""
    lay = getattr(dlg, lay_name)
    grp = getattr(dlg, grp_name)
    n_lay = lay.count()
    kids = grp.findChildren(QCheckBox)
    texts = [c.text() for c in kids]
    dup = {t for t in texts if texts.count(t) > 1}
    print("  -- %s: 布局项=%d 子控件=%d 清单=%s" % (tag, n_lay, len(kids), texts))
    chk("%s 零残影（布局项==子控件数）" % tag, n_lay == len(kids),
        "布局=%d 子控件=%d" % (n_lay, len(kids)))
    chk("%s 无重复项" % tag, not dup, "重复=%s" % (sorted(dup) or "无"))
    return [c.text() for c in kids]


print("=" * 74)
print("准备真实数据")
print("=" * 74)
dev = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
# 这份 dev 未跑过替代料配对（「是否替代料」全为「否」），filter_alt_alerts 必然返空。
# 为验证替代料看板筛选逻辑，就地按 400/410 子集构造替代料标记（保留真实半成品重分类，
# 含空串 → 同时覆盖 v43.145 的工厂兜底分支），再走官方 filter_alt_alerts 入口。
_dev = dev.copy()
_pool = _dev[_dev["物料编码"].astype(str).str[:3].isin(["400", "410"])].copy()
_idx = _pool.index[::3]                      # 每 3 行标 1 行替代料
_dev.loc[_idx, "是否替代料"] = "是"
_dev.loc[_idx, "净偏差数量"] = 1.0            # 组内有差异 → 必进看板
alerts = filter_alt_alerts(_dev, 10)
sub = alerts[[c for c in alerts.columns]].copy()
print("替代料预警(构造后, 阈值10) =", sub.shape, "| dev =", dev.shape)
assert len(sub) > 0, "替代料数据仍为空，E 组无法验证"

# 半成品看板口径：400/410 前缀
semi = dev[dev["物料编码"].astype(str).str[:3].isin(["400", "410"])].copy()
print("400/410 子集 =", semi.shape)
uniq_semi = sorted(set(semi["半成品重分类"].fillna("").astype(str).str.strip()) - {""})
print("半成品看板 半成品重分类唯一值 =", uniq_semi)

print()
print("=" * 74)
print("A. 四处残影断言：set_data 连调 3 次")
print("=" * 74)
d = AlertDialog(sub, None)
d.resize(1200, 700)
d.show()
app.processEvents()
for _ in range(2):
    d.set_data(sub)
    app.processEvents()
alert_items = no_residue(d, "grp_semi_class", "_semi_class_vlayout", "替代料看板")

sd = SemiDashboardDialog(semi, None)
sd.resize(1280, 640)
sd.show()
app.processEvents()
for _ in range(2):
    sd.set_data(semi)
    app.processEvents()
semi_items = no_residue(sd, "grp_semi_class", "_semi_class_layout", "半成品看板")

dw = DeviationWarningDialog(semi, None)
dw.resize(1200, 700)
dw.show()
app.processEvents()
for _ in range(2):
    dw.set_data(semi)
    app.processEvents()
dev_items = no_residue(dw, "grp_semi_class", "_semi_class_grid", "偏差率预警看板")

fp = FilterPanel()
fp.resize(300, 900)
fp.show()
app.processEvents()
for _ in range(2):
    fp._rebuild_semi_class_checkboxes(uniq_semi)
    app.processEvents()
fp_items = [c for c in fp._semi_class_checkboxes.values()]

# 筛选栏的键必须是全名（短标签只用于显示），且短标签零截断
want_keys = ["__all__"] + list(SEMI_CLASS_ALL)
chk("筛选栏字典键为全名（显示用短标签）",
    list(fp._semi_class_checkboxes.keys()) == want_keys,
    list(fp._semi_class_checkboxes.keys()))
fmg = QFontMetrics(fp.font())
trunc = [c.text() for c in fp_items
         if c.width() < fmg.horizontalAdvance(c.text()) + 22]
chk("筛选栏短标签零截断", not trunc, trunc or "无")
chk("筛选栏 tooltip 保留全名",
    all("「%s」" % k in c.toolTip()
        for k, c in fp._semi_class_checkboxes.items() if k != "__all__"),
    {k: c.toolTip() for k, c in list(fp._semi_class_checkboxes.items())[:3]})
lay_fp = fp._semi_class_vlayout
nrows = len({lay_fp.getItemPosition(i)[0] for i in range(lay_fp.count())})
chk("筛选栏改多行（3 行而非 7 行竖排）", nrows == 3, "行数=%d" % nrows)
chk("筛选栏高度显著下降（<=80）", fp.grp_semi_class.height() <= 80,
    "h=%d（原 138）" % fp.grp_semi_class.height())

print()
print("=" * 74)
print("B. 复选框清单")
print("=" * 74)
want = ["全部"] + list(SEMI_CLASS_ALL)
chk("替代料看板 = 全部 + 6 分类（7 项）", alert_items == want, alert_items)
chk("半成品看板 = 全部 + 6 分类（7 项）", semi_items == want, semi_items)
chk("偏差率预警看板 = 全部 + 6 分类（7 项）", dev_items == want, dev_items)
chk("主表筛选面板 = 全部 + 6 分类（7 项）",
    [c.text() for c in fp_items] == ["全部", "食成品", "食综组", "配料中", "食辅原", "饮成品", "饮综仓"],
    [c.text() for c in fp_items])

print()
print("=" * 74)
print("C. 替代料看板两行排版（row0 食品 / row1 饮料）")
print("=" * 74)
lay = d._semi_class_vlayout
pos = {}
for i in range(lay.count()):
    it = lay.itemAt(i)
    if it.widget() is None:
        continue
    r, c, _, _ = lay.getItemPosition(i)
    pos[it.widget().text()] = (r, c)
for t in want:
    print("   %-22s (row=%d, col=%d)" % (t, pos[t][0], pos[t][1]))
chk("全部 在 row0", pos["全部"][0] == 0, pos["全部"])
chk("4 项食品分类 全在 row0",
    all(pos[v][0] == 0 for v in SEMI_CLASS_ALL[:4]),
    {v: pos[v][0] for v in SEMI_CLASS_ALL[:4]})
chk("2 项饮料分类 全在 row1",
    all(pos[v][0] == 1 for v in SEMI_CLASS_ALL[4:]),
    {v: pos[v][0] for v in SEMI_CLASS_ALL[4:]})
g = d.grp_semi_class
# 精确判据：两行共 7 项，控件必须全部落在 group 可视区内且未被压扁
over = []
for i in range(lay.count()):
    it = lay.itemAt(i)
    w = it.widget()
    if w is None:
        continue
    if w.y() < 0 or w.y() + w.height() > g.height() + 1:
        over.append((w.text(), w.y(), w.height(), g.height()))
    if w.height() < 14:  # 被压扁
        over.append((w.text(), "squashed h=%d" % w.height()))
chk("两行控件全部落在可视区（无裁切/压扁）", not over, over or "OK")
print("   分类组几何 = %dx%d" % (g.width(), g.height()))
print("   末行控件底边 = %d (组高 %d)" % (
    max((lay.itemAt(i).widget().y() + lay.itemAt(i).widget().height())
        for i in range(lay.count()) if lay.itemAt(i).widget() is not None),
    g.height()))
chk("分类组不截断（宽度够）", g.width() >= 300, "w=%d" % g.width())

print()
print("=" * 74)
print("D. 半成品看板 v43.146 行为不回退")
print("=" * 74)
# 注意：看板有独立于半成品分类的默认筛选——_quar_filter='no'（非隔离区）
# 与 _read_filter='未读'，本机隔离区有 7 行 → 基线是 3284 而非 3291，属预期。
# 这里把 GUI 口径对齐到「dialog 自己 original_df + 半成品掩码」，而非我外部切的 3291。
base = sd.original_df
print("  400/410 总数 = %d | dialog original_df = %d" % (len(semi), len(base)))
print("  默认额外筛选: _quar_filter=%r _read_filter=%r 隔离区=%d 行"
      % (sd._quar_filter, sd._read_filter,
         int((base["隔离区"].astype(str).str.strip() != "").sum())))

only(sd, set(SEMI_CLASS_DEFAULT))
app.processEvents()
n_def = sd.table_view.model().rowCount()
print("  默认勾选（食品成品+饮料成品）行数 =", n_def)

only(sd, set())
app.processEvents()
n_all = sd.table_view.model().rowCount()
print("  全部行数 =", n_all)
# 基线须扣除隔离区行：看板默认 _quar_filter='no'，隔离区 7 行不进表
_n_quar = int((base["隔离区"].astype(str).str.strip() != "").sum())
chk("全部 == 基线扣除隔离区（3291-7=3284）", n_all == len(base) - _n_quar,
    "%d vs %d" % (n_all, len(base) - _n_quar))
chk("默认勾选 = 1755（不回退）", n_def == 1755, n_def)

print()
print("  6 分类逐项（GUI 口径 == 列值精确匹配 & 基线）：")
for name in SEMI_CLASS_ALL:
    only(sd, {name})
    app.processEvents()
    n_gui = sd.table_view.model().rowCount()
    # 同口径：叠加看板其他默认筛选（非隔离区 + 未读）
    mask = ((base["半成品重分类"].fillna("").astype(str).str.strip() == name)
            & (base["隔离区"].astype(str).str.strip() == "")
            & (base.get("_read", pd.Series(0, index=base.index)).fillna(0) != 1))
    n_raw = int(mask.sum())
    chk("  %-22s GUI=%-5d 精确匹配=%-5d" % (name, n_gui, n_raw), n_gui == n_raw,
        "GUI=%d raw=%d" % (n_gui, n_raw))

print()
print("=" * 74)
print("E. 替代料看板筛选逻辑")
print("=" * 74)
uniq_alt = sorted(set(sub["半成品重分类"].fillna("").astype(str).str.strip()) - {""})
print("  替代料 半成品重分类唯一值 =", uniq_alt)
for name in SEMI_CLASS_ALL:
    if name not in uniq_alt:
        print("  [SKIP] %-22s 数据里无此分类" % name)
        continue
    only(d, {name})
    app.processEvents()
    n_gui = d.table_view.model().rowCount()
    mask = sub["半成品重分类"].fillna("").astype(str).str.strip() == name
    n_raw = int(mask.sum())
    chk("  %-22s GUI=%-5d 精确匹配=%-5d" % (name, n_gui, n_raw), n_gui == n_raw,
        "GUI=%d raw=%d" % (n_gui, n_raw))
only(d, set())
app.processEvents()
chk("替代料看板 全部 == 总行数", d.table_view.model().rowCount() == len(sub),
    "%d vs %d" % (d.table_view.model().rowCount(), len(sub)))

print()
print("=" * 74)
print("F. merge_semi_class_values 工具函数")
print("=" * 74)
r1 = merge_semi_class_values(["", None, "食品成品半成品", "脏数据类", "  ", "脏数据类"])
chk("固定清单在前 6 项", r1[:6] == list(SEMI_CLASS_ALL), r1[:6])
chk("脏数据追加且去重", r1 == list(SEMI_CLASS_ALL) + ["脏数据类"], r1)
chk("空/None/空白被丢弃", "" not in r1 and None not in r1 and "  " not in r1)
chk("无额外值时只返回 6 项", merge_semi_class_values([]) == list(SEMI_CLASS_ALL))
chk("None 入参安全", merge_semi_class_values(None) == list(SEMI_CLASS_ALL))

print()
print("=" * 74)
print("结果：%d PASS / %d FAIL" % (len(OK), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("   - " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
