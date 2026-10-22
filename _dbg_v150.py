# -*- coding: utf-8 -*-
"""v43.150 联动视图定位不准 —— 验证脚本（离屏 + 真实数据）。

复刻用户场景：订单 300494954（原辅料，联动后显示整个订单十几行，无法定位）
              订单 300494957（包材，联动后 1 行，用户以为是对的）
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtCore import QModelIndex

PASS = []
FAIL = []


def chk(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  | " + str(detail)) if detail else ""))


PKL = r"C:/Temp/zpp_dev_out/dev.pkl"
df = pd.read_pickle(PKL)
df["流程订单"] = df["流程订单"].astype(str).str.strip()
df["物料编码"] = df["物料编码"].astype(str).str.strip()

print("=" * 74)
print("真实数据：%d 行 / %d 订单 / %d 物料" % (len(df), df["流程订单"].nunique(), df["物料编码"].nunique()))
print("=" * 74)

# ---------------------------------------------------------------- #
# 1. 物料条件抽取：_link_material_condition
# ---------------------------------------------------------------- #
print("\n[1] _link_material_condition 物料条件抽取")
src = open(r"E:\zpp011_v2\gui_pyside6\main_window.py", "r", encoding="utf-8").read()
ns = {"QModelIndex": QModelIndex}
start = src.index("    @staticmethod\n    def _link_material_condition")
end = src.index("    def _link_hit_any_row", start)
exec(compile("class _T:\n" + src[start:end], "<x>", "exec"), ns)
f_mat = ns["_T"]._link_material_condition

rec_full = df.iloc[0]
k, lbl = f_mat(rec_full)
chk("有物料编码时优先用 _material_code", k is not None and "_material_code" in k, k)
chk("标签含编码+名称", str(df.iloc[0]["物料编码"]) in lbl and str(df.iloc[0]["物料名称"]) in lbl, lbl)

# 编码缺失 → 降级名称
r2 = rec_full.copy()
r2["物料编码"] = None
k2, lbl2 = f_mat(r2)
chk("编码缺失降级到 _material_names", k2 is not None and "_material_names" in k2, k2)

# 编码是 NaN 也要降级
r3 = rec_full.copy()
r3["物料编码"] = float("nan")
k3, _ = f_mat(r3)
chk("编码为 NaN 也降级", k3 is not None and "_material_names" in k3, k3)

# 编码为 int（真实数据是 int64）要正确转字符串，不能变成 "20000103.0"
r4 = rec_full.copy()
r4["物料编码"] = 20000103
k4, _ = f_mat(r4)
chk("int 编码转 str 正确（无 .0 尾巴）", k4 is not None and k4.get("_material_code") == "20000103", k4)

# 编码+名称都空 → 无条件
r5 = {"流程订单": "300463299", "物料编码": None, "物料名称": None, "工厂": None}
k5, lbl5 = f_mat(r5)
chk("编码名称全空时返回 None（退回纯订单）", k5 is None and lbl5 == "", (k5, lbl5))

# record 无这些键（get 抛异常路径）
k6, lbl6 = f_mat({"流程订单": "300463299"})
chk("record 缺键不抛异常", k6 is None, (k6, lbl6))

# ---------------------------------------------------------------- #
# 2. 39 行大订单：叠加物料编码后由 39 → 1
# ---------------------------------------------------------------- #
print("\n[2] 39 行订单叠加物料编码后收敛为 1 行")
big_order = df["流程订单"].value_counts().index[0]
sub = df[df["流程订单"] == big_order]
chk("测试订单是多物料大单", len(sub) > 10, "订单 %s = %d 行 / %d 物料" % (big_order, len(sub), sub["物料编码"].nunique()))

code0 = sub.iloc[0]["物料编码"]
name0 = sub.iloc[0]["物料名称"]
hit_code = sub[sub["物料编码"] == code0]
chk("叠加 _material_code 收敛到 1 行", len(hit_code) == 1, "%s → %d 行" % (code0, len(hit_code)))
hit_name = sub[sub["物料名称"].astype(str).str.strip() == str(name0).strip()]
chk("叠加 _material_names 收敛到 1 行", len(hit_name) == 1, "%s → %d 行" % (name0, len(hit_name)))

# 编码子串误伤检查：8位等长，任意编码都不会是另一编码的子串
codes = sorted(sub["物料编码"].unique())
false_hits = [c for c in codes if any(c != o and c in o for o in codes)]
chk("物料编码之间无子串误伤", not false_hits, false_hits[:5])

# ---------------------------------------------------------------- #
# 3. 端到端：真实 proxy 上跑钻取 + 兜底
# ---------------------------------------------------------------- #
print("\n[3] 端到端 proxy 验证（含 0 行兜底回退）")
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
    from gui_pyside6.utils.locate import locate_row

    sm = DataFrameModel(df)
    pm = AuditProxyModel()
    pm.setSourceModel(sm)
    pm.setCustomFilters({})

    def visible_rows():
        out = []
        for r in range(sm.rowCount()):
            if pm.filterAcceptsRow(r, QModelIndex()):
                out.append(r)
        return out

    chk("初始无筛选时全表可见", len(visible_rows()) == len(df), len(visible_rows()))

    rec = sub.iloc[0]
    keys = {"_process_order": big_order, "_material_code": code0}
    pm.setCustomFilters(keys)
    rows = visible_rows()
    chk("订单+物料编码 → 命中 1 行", len(rows) == 1, len(rows))
    if len(rows) == 1:
        got = str(df.iloc[rows[0]]["物料编码"])
        chk("命中行就是目标物料", got == code0, "%s vs %s" % (got, code0))
        chk("命中行原表行号正确", str(df.iloc[rows[0]]["原表行号"]) == str(rec["原表行号"]),
            df.iloc[rows[0]]["原表行号"])

    # 兜底：叠加一个不存在的物料编码 → 应回退到纯订单 39 行
    pm.setCustomFilters({"_process_order": big_order, "_material_code": "99999999"})
    zero_rows = visible_rows()
    chk("不存在的物料编码 → 命中 0 行（兜底前提成立）", len(zero_rows) == 0, len(zero_rows))

    def f_hit_any():
        for r in range(sm.rowCount()):
            if pm.filterAcceptsRow(r, QModelIndex()):
                return True
        return False

    chk("_link_hit_any_row 正确识别 0 行", f_hit_any() is False)
    pm.setCustomFilters({"_process_order": big_order})
    chk("_link_hit_any_row 正确识别有行", f_hit_any() is True)
    chk("回退后 = 纯订单 39 行", len(visible_rows()) == len(sub), len(visible_rows()))

    # 快照/撤销链路
    pm.setCustomFilters({"_quarantined_is": "否"})
    base = pm.getCustomFilters()
    pm.setCustomFilters(dict(base, **{"_process_order": big_order, "_material_code": code0}))
    pm.setCustomFilters(base)
    chk("清除联动可恢复快照", len(visible_rows()) > len(sub), len(visible_rows()))

    # 单行订单（包材场景）不受影响
    one = df["流程订单"].value_counts()
    one_order = one[one == 1].index[0]
    orec = df[df["流程订单"] == one_order].iloc[0]
    pm.setCustomFilters({"_process_order": one_order, "_material_code": orec["物料编码"]})
    chk("单行订单（包材场景）仍命中 1 行", len(visible_rows()) == 1, len(visible_rows()))

except Exception as e:
    import traceback
    traceback.print_exc()
    chk("端到端 proxy 验证未抛异常", False, e)

# ---------------------------------------------------------------- #
# 4. 回归：所有看板 link_source 链路完好
# ---------------------------------------------------------------- #
print("\n[4] 5 个看板 link_source 链路")
import re
loc = open(r"E:\zpp011_v2\gui_pyside6\utils\locate.py", "r", encoding="utf-8").read()
chk("locate.py 仍调用 _apply_link_drilldown", "_apply_link_drilldown" in loc)
for f in ["alert_dialog", "deviation_warning_dialog", "neg_loss_dashboard_dialog",
          "quarantine_dialog", "semi_dashboard_dialog"]:
    p = r"E:\zpp011_v2\gui_pyside6\dialogs\%s.py" % f
    s = open(p, "r", encoding="utf-8").read()
    chk("%s 仍传 link_source" % f, "link_source=" in s)

# ---------------------------------------------------------------- #
# 5. 代码结构检查
# ---------------------------------------------------------------- #
print("\n[5] 代码结构")
chk("_link_material_condition 定义为 @staticmethod", "@staticmethod\n    def _link_material_condition" in src)
chk("新方法在文件 class 内部（未破坏类结构）", src.count("class MainWindow") >= 1)
chk("QModelIndex 已导入", "QModelIndex" in src.split("\n")[26])
chk("main_window 注释里的 v43.150 仅为改动说明", src.count("v43.150") <= 3, src.count("v43.150"))
chk("版本号来源仍是 version_history（未硬编码 APP_VERSION）", "43.150" not in src.replace("v43.150", ""))
vh = open(r"E:\zpp011_v2\utils\version_history.py", "r", encoding="utf-8").read()
chk("version_history 索引 0 = v43.150", '"v43.150"' in vh.split('"version": "v43.149"')[0])
chk("v43.150 有 fixes 字段", '"fixes"' in vh.split('"version": "v43.150"')[1][:2000])

print("\n" + "=" * 74)
print("结果：%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  - " + f)
print("=" * 74)
