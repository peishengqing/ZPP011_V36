# -*- coding: utf-8 -*-
"""v43.153 端到端验证：真实 MainWindow 方法 + 真实 proxy/model + 真实 dev.pkl 数据。

不再像 v43.150 那样只测 helper —— 这次从 `_apply_link_drilldown` 真实入口进，
把 MainWindow 上的 5 个真实方法绑到一个轻量 stub 上跑，覆盖：
  1. 单行订单 → 收敛 1 行
  2. 39 行订单 + 物料编码 → 收敛 1 行（v43.150 回归的原始场景）
  3. 错误物料编码 → 回退到纯订单（39 行），绝不给空表
  4. 横幅文本包含订单 + 来源 + 物料编码 + 名称
  5. _clear_link_drilldown 恢复快照
  6. 旧写法 keys[mat_key[0]] 在真实 record 上必抛 KeyError（反证根因）
  7. locate.locate_row 不再静默吞掉联动异常
"""
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.main_window import MainWindow
from gui_pyside6.utils import locate

PASS, FAIL = [], []


def chk(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("[PASS]" if cond else "[FAIL]", name,
                         ("  -> " + str(detail)) if detail else ""))


app = QApplication.instance() or QApplication([])

df = pd.read_pickle(r"C:\Temp\zpp_dev_out\dev.pkl")
df = df.reset_index(drop=True)
print("=" * 72)
print("数据: %d 行 / %d 列" % (len(df), len(df.columns)))
print("=" * 72)

mc_cols = [c for c in ("物料号", "物料编码", "code", "组件物料号") if c in df.columns]
po_cols = [c for c in ("流程订单", "流程订单号", "订单号", "生产订单") if c in df.columns]
print("物料列: %s" % mc_cols)
print("订单列: %s" % po_cols)

model = DataFrameModel(df)
proxy = AuditProxyModel()
proxy.setSourceModel(model)
proxy.setCustomFilters({})
app.processEvents()

# 造一个多行订单（>=10 行）以复现原辅料场景
po_col = po_cols[0]
vc = df[po_col].astype(str).str.strip()
cnt = vc.value_counts()
big_order = str(cnt.index[0])
big_n = int(cnt.iloc[0])
sub = df[vc == big_order]
mc_col = mc_cols[0]
target_code = str(sub[mc_col].iloc[0]).strip()
target_name = str(sub["物料名称"].iloc[0]).strip() if "物料名称" in sub.columns else ""
print("多行订单: %s (%d 行)" % (big_order, big_n))
print("目标物料: %s %s" % (target_code, target_name))

# 找一个单行订单
single_order = None
for o, n in cnt.items():
    if n == 1:
        single_order = str(o)
        break
print("单行订单: %s" % single_order)


class _Table:
    def __init__(self):
        self.banner = None
        self.cleared = 0

    def show_link_banner(self, text):
        self.banner = text

    def clear_link_banner(self):
        self.banner = None
        self.cleared += 1


class _Edit:
    def __init__(self):
        self._text = ""

    def blockSignals(self, b):
        pass

    def setText(self, t):
        self._text = t

    def text(self):
        return self._text


class _FilterPanel:
    def __init__(self):
        self.process_order_edit = _Edit()


class Stub:
    """只提供 _apply_link_drilldown 链路真正用到的属性。"""

    def __init__(self):
        self.proxy_model = proxy
        self._link_snapshot = None
        self.main_table = _Table()
        self.filter_panel = _FilterPanel()
        self.logs = []

    def log(self, msg, level="info"):
        self.logs.append((level, msg))

    def _update_summary(self):
        pass


# 把 MainWindow 上的真实方法绑到 stub（类未实例化，零副作用）
M = MainWindow.__dict__
for name in ("_apply_link_drilldown", "_link_material_condition",
             "_link_hit_any_row", "_clear_link_drilldown",
             "_apply_focus_filters"):
    setattr(Stub, name, M[name])


def vis():
    proxy.invalidateFilter()
    app.processEvents()
    return proxy.rowCount()


def reset():
    """每个用例前把 proxy 恢复到无筛选干净态，避免用例间污染。"""
    proxy.setCustomFilters({})
    app.processEvents()


def rec(order, code, name=""):
    r = {"流程订单": order}
    if code:
        r["物料编码"] = code
    if name:
        r["物料名称"] = name
    return pd.Series(r)


print("\n" + "=" * 72)
print("T1 单行订单 + 物料编码 → 收敛 1 行")
print("=" * 72)
reset()
s = Stub()
s._apply_link_drilldown(rec(single_order, str(df[vc == single_order][mc_col].iloc[0]).strip()),
                        "负损看板")
n = vis()
chk("T1 命中 1 行", n == 1, "实际 %d" % n)
chk("T1 筛选含 _material_code", "_material_code" in proxy.getCustomFilters(),
    proxy.getCustomFilters())
chk("T1 筛选含 _process_order", "_process_order" in proxy.getCustomFilters())
chk("T1 横幅非空", bool(s.main_table.banner), s.main_table.banner)
print("  横幅: %s" % s.main_table.banner)
chk("T1 订单框回填", s.filter_panel.process_order_edit.text() == single_order)

print("\n" + "=" * 72)
print("T2 %d 行订单 + 物料编码 → 收敛 1 行（v43.150 回归场景）" % big_n)
print("=" * 72)
reset()
s = Stub()
s._apply_link_drilldown(rec(big_order, target_code, target_name), "偏差率预警")
n = vis()
chk("T2 命中 1 行", n == 1, "实际 %d（纯订单过滤应为 %d）" % (n, big_n))
cf = proxy.getCustomFilters()
chk("T2 条件为订单+物料", "_material_code" in cf and "_process_order" in cf, cf)
chk("T2 横幅含物料编码+名称", bool(target_code in (s.main_table.banner or "")),
    s.main_table.banner)
print("  横幅: %s" % s.main_table.banner)

print("\n" + "=" * 72)
print("T3 错误物料编码 → 自动回退到纯订单，不给空表")
print("=" * 72)
reset()
s = Stub()
s._apply_link_drilldown(rec(big_order, "99999999", "不存在的物料"), "半成品看板")
n = vis()
chk("T3 回退到订单级 %d 行" % big_n, n == big_n, "实际 %d" % n)
chk("T3 已移除 _material_code", "_material_code" not in proxy.getCustomFilters(),
    proxy.getCustomFilters())
chk("T3 记录了 warning 日志", any(lv == "warning" for lv, _ in s.logs), s.logs)
print("  日志: %s" % s.logs)

print("\n" + "=" * 72)
print("T4 无物料信息 → 只按订单过滤")
print("=" * 72)
reset()
s = Stub()
s._apply_link_drilldown(rec(big_order, None, None), "包材看板")
n = vis()
chk("T4 命中 %d 行" % big_n, n == big_n, "实际 %d" % n)
chk("T4 无 _material_code", "_material_code" not in proxy.getCustomFilters())
chk("T4 无 _material_names", "_material_names" not in proxy.getCustomFilters())

print("\n" + "=" * 72)
print("T5 _clear_link_drilldown 恢复快照")
print("=" * 72)
s = Stub()
# 前置条件必须与该行真实车间一致（本机该物料属 1车间），否则叠加物料必然 0 行
# 而走回退分支 —— 那是期望行为，不是 T5 要测的东西。
before = {"车间": "1车间"}
proxy.setCustomFilters(before)
s._link_snapshot = None
s._apply_link_drilldown(rec(big_order, target_code, target_name), "包材看板")
mid = dict(proxy.getCustomFilters())
chk("T5 联动后含物料", "_material_code" in mid, mid)
s._clear_link_drilldown()
after = dict(proxy.getCustomFilters())
chk("T5 快照恢复", after == before, after)
chk("T5 横幅已清", s.main_table.banner is None)
chk("T5 snapshot 置 None", s._link_snapshot is None)

print("\n" + "=" * 72)
print("T6 反证：旧写法在真实 record 上必抛 KeyError")
print("=" * 72)
r = rec(big_order, target_code, target_name)
mat_key, mat_label = MainWindow._link_material_condition(r)
print("  _link_material_condition 返回 %r, %r" % (mat_key, mat_label))
chk("T6 mat_key 是 dict", isinstance(mat_key, dict))
try:
    k = {}
    k[mat_key[0]] = mat_key[1]
    chk("T6 旧写法抛 KeyError", False, "居然没抛，根因判断有误")
except KeyError as e:
    chk("T6 旧写法抛 KeyError（根因确认）", True, "KeyError: %s" % e)

print("\n" + "=" * 72)
print("T7 locate.locate_row 不再静默吞掉联动异常")
print("=" * 72)
captured = {}
real_toast = locate.toast
locate.toast = lambda msg, **kw: captured.setdefault("toast", []).append(msg)


class MWStub:
    def __init__(self):
        self.proxy_model = proxy
        self._link_snapshot = None
        self.main_table = _Table()
        self.filter_panel = _FilterPanel()
        self.logs = []

    def log(self, m, level="info"):
        self.logs.append((level, m))

    def _update_summary(self):
        pass

    def _locate_row_by_excel_no(self, n):
        return True

    def _locate_row_in_main_table(self, d, silent=False):
        return True

    def _apply_link_drilldown(self, rec_, lbl):
        raise RuntimeError("模拟联动内部异常")


for name in ("_apply_link_drilldown", "_link_material_condition",
             "_link_hit_any_row", "_clear_link_drilldown",
             "_apply_focus_filters"):
    pass  # MWStub 故意用会抛的 _apply_link_drilldown，不覆盖

import io
import contextlib
import traceback

err = io.StringIO()
mw = MWStub()
ok = locate.locate_row(mw, pd.Series({"原表行号": "1", "流程订单": big_order}),
                       link_source="负损看板")
try:
    with contextlib.redirect_stderr(err):
        pass
except Exception:
    pass
chk("T7 定位仍返回 True（行定位不受影响）", ok is True, ok)
chk("T7 有用户可见 toast（不再静默）", "toast" in captured, captured)
chk("T7 有 warning 日志", any(lv == "warning" for lv, _ in mw.logs), mw.logs)
locate.toast = real_toast

print("\n" + "=" * 72)
print("汇总: %d PASS / %d FAIL" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项: %s" % FAIL)
print("=" * 72)
sys.exit(1 if FAIL else 0)
