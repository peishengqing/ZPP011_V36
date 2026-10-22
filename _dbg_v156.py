# -*- coding: utf-8 -*-
"""v43.155 验证：主表缺「半成品重分类」列时，半成品看板能补齐且口径与完整数据一致。

复刻用户 2026-10-04 截图的真实数据源：主表经左侧筛选栏收窄后，
「半成品重分类」「是否替代料」两列都已丢失（截图列集实测复刻）。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtWidgets import QApplication

from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog
from gui_pyside6.utils.semi_class import (load_semi_classify_map,
                                          ensure_semi_class_column)

PASS, FAIL = [], []


def chk(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("[PASS]" if cond else "[FAIL]", name,
                         ("  -> " + str(detail)) if detail else ""))


app = QApplication.instance() or QApplication([])

full = pd.read_pickle(r"C:\Temp\zpp_dev_out\dev.pkl").reset_index(drop=True)

# ---- 主窗口取数路径（main_window._show_semi_dashboard 的 candidates 白名单）----
candidates = [
    "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
    "车间", "组件物料类型", "组件物料类型描述", "单位",
    "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
    "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
    "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
]
code_col = next((c for c in ("物料编码", "组件物料号") if c in full.columns), None)
sub_all = full[full[code_col].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
keep = [c for c in candidates if c in sub_all.columns]
sub = sub_all[keep].copy() if keep else sub_all.copy()

print("=" * 74)
print("场景A：数据里有该列（dev.pkl 路径）")
print("=" * 74)
print("  传入列 (%d): %s" % (len(sub.columns), list(sub.columns)))
chk("A 传入含半成品重分类", "半成品重分类" in sub.columns)

# ---- 场景 B：模拟用户截图——主表收窄后该列丢失 ----
narrowed = sub.drop(columns=[c for c in ("半成品重分类", "是否替代料")
                             if c in sub.columns])
print("\n" + "=" * 74)
print("场景B：数据缺该列（复刻用户截图）")
print("=" * 74)
print("  传入列 (%d): %s" % (len(narrowed.columns), list(narrowed.columns)))
chk("B 传入确实缺该列", "半成品重分类" not in narrowed.columns)

# ---- 分类表加载 ----
print("\n" + "=" * 74)
print("分类表 load_semi_classify_map()")
print("=" * 74)
m = load_semi_classify_map()
chk("分类表非空", bool(m), "条目=%d" % len(m))
if m:
    from collections import Counter
    print("  值分布: %s" % dict(Counter(m.values())))

# ---- 口径一致性：补出来的 vs 完整数据里原本的 ----
print("\n" + "=" * 74)
print("口径一致性：补列结果 vs 完整数据原值（逐行比对）")
print("=" * 74)
fixed, added = ensure_semi_class_column(narrowed.copy())
chk("B 补列成功", added)
chk("B 补后含该列", "半成品重分类" in fixed.columns)

if added and "半成品重分类" in sub.columns:
    a = sub["半成品重分类"].astype(str).str.strip().reset_index(drop=True)
    b = fixed["半成品重分类"].astype(str).str.strip().reset_index(drop=True)
    same = (a == b)
    n_bad = int((~same).sum())
    chk("B 补列口径与原值 100% 一致", n_bad == 0,
        "不一致 %d / %d 行" % (n_bad, len(a)))
    if n_bad:
        bad = pd.DataFrame({"原值": a[~same], "补出": b[~same]}).head(10)
        print("  不一致样本:\n%s" % bad.to_string())
    else:
        print("  分布对比:")
        print("    原值: %s" % a.value_counts().to_dict())
        print("    补出: %s" % b.value_counts().to_dict())

# ---- 关键：包材等非 400/410 的已填值不能被覆盖 ----
print("\n" + "=" * 74)
print("保护：分类表里已填的值不得被 400/410 覆盖")
print("=" * 74)
probe = pd.DataFrame({
    "物料编码": ["40001401", "40000001", "99999999", "41012345", ""],
})
pf, _ = ensure_semi_class_column(probe.copy())
for code, got in zip(probe["物料编码"], pf["半成品重分类"]):
    want = m.get(str(code).strip(), "")
    if want == "":
        s = str(code).strip()
        want = "食品成品半成品" if s.startswith("400") else (
            "饮料成品半成品" if s.startswith("410") else "")
    ok = (str(got).strip() == want)
    print("    %-10s → %-16s (期望 %-16s) %s" % (code, got, want, "OK" if ok else "❌"))
    chk("编码 %s 分类正确" % (code or "(空)"), ok, "实际 %r 期望 %r" % (got, want))

# ---- 真实看板：缺列数据打开，表格里必须有这一列 ----
print("\n" + "=" * 74)
print("真实看板：缺列数据打开后的可见列")
print("=" * 74)
dlg = SemiDashboardDialog(narrowed.copy(), None)
dlg.resize(1400, 700)
dlg.show()
app.processEvents()
dlg._apply_filter()
app.processEvents()

cols = list(dlg.source_model._display_columns)
chk("表格含半成品重分类", "半成品重分类" in cols, "共 %d 列" % len(cols))
if "半成品重分类" in cols:
    i = cols.index("半成品重分类")
    chk("该列未被隐藏", not dlg.table_view.isColumnHidden(i))
    chk("位置靠前（索引 < 20）", i < 20, "索引=%d" % i)
    print("  可见列顺序:")
    for j, c in enumerate(cols[:20]):
        print("    %2d %s%s" % (j, c, "  <== 半成品重分类" if j == i else ""))
    if "组件物料类型描述" in cols:
        print("  紧邻检查: 组件物料类型描述@%d, 半成品重分类@%d" % (
            cols.index("组件物料类型描述"), i))

# 表格里实际显示的值
dv = dlg.proxy_model if hasattr(dlg, "proxy_model") else None
try:
    mdl = dlg.source_model
    ci = cols.index("半成品重分类")
    vals = [str(mdl.data(mdl.index(r, ci), 0) or "") for r in range(min(8, mdl.rowCount()))]
    print("  前 8 行该列取值: %s" % vals)
    chk("该列有实际取值", any(v for v in vals), vals)
except Exception as e:
    print("  读值失败: %r" % e)

# 顶部复选框组仍正常（筛得出数据）——本看板无代理模型，直接过滤 DataFrame
dlg._apply_filter()
app.processEvents()
rc = dlg.source_model.rowCount()
cnt = dlg.lbl_count.text()
print("  筛选后行数: %s" % rc)
print("  计数标签: %s" % cnt)
chk("筛选仍能出数据", rc > 0, rc)
chk("计数标签与实际行数一致", ("共 %d 条" % rc) in cnt, cnt)

# 补列后各分类都能被复选框组命中（逐个分类反查）
mdl = dlg.source_model
ci = cols.index("半成品重分类")
from collections import Counter
cur = Counter(str(mdl.data(mdl.index(r, ci), 0) or "").strip()
              for r in range(mdl.rowCount()))
print("  当前筛选结果的分类分布: %s" % dict(cur))
for v in ("食品成品半成品", "饮料成品半成品"):
    chk("分类「%s」在结果中有行" % v, cur.get(v, 0) > 0, cur.get(v, 0))

print("\n" + "=" * 74)
print("汇总: %d PASS / %d FAIL" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项: %s" % FAIL)
print("=" * 74)

# ---- 截图取证：缺列数据打开后的表格 ----
try:
    tv = dlg.table_view
    pm = tv.viewport().grab()
    pm.save(r"E:/zpp011_v2/_shot_v155_reclass.png")
    print("\n已保存 _shot_v155_reclass.png (%dx%d)" % (pm.width(), pm.height()))
except Exception as e:
    print("截图失败: %r" % e)


sys.exit(1 if FAIL else 0)
