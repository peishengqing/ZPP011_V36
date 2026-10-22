# -*- coding: utf-8 -*-
"""v43.153 定位：locate_row → _apply_link_drilldown 真实链路，剥掉静默 except 抓异常"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

df = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
df["_read"] = 0
df["_quarantined"] = 0
df["_post_audit_changed"] = 0
df["是否替代料"] = "否"
df["工厂"] = "云南达利食品有限公司"
df.loc[df.index[:2], "_quarantined"] = 1

from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel

sm = DataFrameModel(df)
pm = AuditProxyModel()
pm.setSourceModel(sm)
pm.setCustomFilters({})

# ---- 复刻 MainWindow._apply_link_drilldown 及其依赖（逐字取自源码）----
src = open(r"E:\zpp011_v2\gui_pyside6\main_window.py", "r", encoding="utf-8").read()
i = src.index("    def _apply_link_drilldown")
j = src.index("    def _clear_link_drilldown", i)
code = src[i:j]
print("抽取的源码行数:", len(code.split("\n")))

ns = {"QModelIndex": QModelIndex, "pd": pd}


class Fake:
    def __init__(self):
        self.proxy_model = pm
        self._link_snapshot = None
        self.filter_panel = type("FP", (), {
            "process_order_edit": type("E", (), {
                "blockSignals": lambda s, x: None,
                "setText": lambda s, x: None,
                "blockSignals": lambda s, x: None})()})()
        self.banners = []
        self.summary = 0
        self.fallback_log = []

    def log(self, m, lv="info"):
        self.fallback_log.append((m, lv))

    def _update_summary(self):
        self.summary += 1

    def _apply_focus_filters(self, filter_keys, label):
        if self._link_snapshot is None:
            self._link_snapshot = self.proxy_model.getCustomFilters()
        merged = dict(self.proxy_model.getCustomFilters())
        merged.update(filter_keys)
        self.proxy_model.setCustomFilters(merged)
        self._update_summary()
        self.banners.append(label)

    def show_link_banner(self, label):
        self.banners.append(label)


exec(compile("class _MW:\n" + code, "<drill>", "exec"), ns)
MWCls = ns["_MW"]
mw = MWCls()

# 看板行 record（pandas Series，就是实际传入的东西）
rec = df.iloc[0]

print("\n" + "=" * 72)
print("【关键】_link_hit_any_row 逐行遍历全部 %d 行" % len(df))
print("=" * 72)
import time
t = time.time()
try:
    r = mw._link_hit_any_row()
    print("  返回:", r, "耗时 %.2fs" % (time.time() - t))
except Exception:
    traceback.print_exc()

print("\n" + "=" * 72)
print("【关键】直接调 _apply_link_drilldown，异常不吞")
print("=" * 72)
mw2 = MWCls()
try:
    mw2._apply_link_drilldown(rec, "偏差率预警")
    print("  ✅ 无异常")
    print("  横幅:", mw2.banners)
    print("  代理条件:", pm.getCustomFilters())
except Exception:
    traceback.print_exc()

print("\n" + "=" * 72)
print("【关键】filterAcceptsRow 的真实签名（PySide6 强类型？）")
print("=" * 72)
import inspect
try:
    print("  签名:", inspect.signature(pm.filterAcceptsRow))
except Exception as e:
    print("  取签名失败:", e)
try:
    v = pm.filterAcceptsRow(0, QModelIndex())
    print("  filterAcceptsRow(0, QModelIndex()) =", v)
except Exception as e:
    print("  ❌ 调用失败:", type(e).__name__, e)

print("\n" + "=" * 72)
print("【关键】sm.rowCount() / 索引 0 是否有效")
print("=" * 72)
try:
    print("  sm.rowCount() =", sm.rowCount())
except Exception as e:
    print("  ❌", e)
try:
    print("  pm.rowCount() =", pm.rowCount())
except Exception as e:
    print("  ❌", e)

print("\n" + "=" * 72)
print("【关键】filterAcceptsRow 参数顺序：PySide6 要求 (source_row, parent)")
print("=" * 72)
try:
    print("  filterAcceptsRow(0) 单参:", pm.filterAcceptsRow(0))
except Exception as e:
    print("  单参失败:", type(e).__name__, str(e)[:200])
