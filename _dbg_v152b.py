# -*- coding: utf-8 -*-
"""v43.152 排查2：真实主表数据下四个 callback 的实际行为"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd

df = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
df["_read"] = 0
df["_quarantined"] = 0
df["_post_audit_changed"] = 0
df["是否替代料"] = "否"
df.loc[df.index[:2], "_quarantined"] = 1

from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
app = QApplication.instance() or QApplication([])

MSGS = []
QMessageBox.information = staticmethod(lambda *a, **k: MSGS.append(("info",) + tuple(a[1:3])))
QMessageBox.critical = staticmethod(lambda *a, **k: MSGS.append(("critical",) + tuple(a[1:3])))
QMessageBox.warning = staticmethod(lambda *a, **k: MSGS.append(("warn",) + tuple(a[1:3])))

print("真实列名：", [c for c in df.columns if "数量" in c or "定额" in c or "实际" in c])

print("\n" + "=" * 72)
print("复刻 _count_unread_items 的四个计数（复刻自 main_window 2905-2967）")
print("=" * 72)
read_mask = df["_read"].astype(int).eq(0)
n_q = int(((pd.to_numeric(df["_quarantined"], errors="coerce").fillna(0).astype(int) == 1) & read_mask).sum())
n_c = int(((pd.to_numeric(df["_post_audit_changed"], errors="coerce").fillna(0).astype(int) == 1) & read_mask).sum())
qty_col = next((c for c in ["数量-定额", "定额"] if c in df.columns), None)
act_col = next((c for c in ["数量-实际", "实际"] if c in df.columns), None)
print("  qty_col=%r act_col=%r" % (qty_col, act_col))
a = pd.to_numeric(df[act_col], errors="coerce").fillna(0) if act_col else pd.Series(0, index=df.index)
q = pd.to_numeric(df[qty_col], errors="coerce").fillna(0) if qty_col else pd.Series(0, index=df.index)
no_input = (a.abs() <= 0.001) & (q > 0.001)
rate_col = "偏差率(%)" if "偏差率(%)" in df.columns else None
if rate_col:
    rates = pd.to_numeric(df[rate_col], errors="coerce").fillna(0)
    n_d = int(((rates.abs() >= 10) & (~no_input) & read_mask).sum())
else:
    n_d = 0
print("  隔离区未读 n_q =", n_q)
print("  变动提醒未读 n_c =", n_c)
print("  偏差率预警未读 n_d =", n_d)

print("\n" + "=" * 72)
print("四个 callback 的 return 路径（重点：0 条时是否 return 静默）")
print("=" * 72)

# 隔离区
def cb_quarantine():
    qdf = df[df["_quarantined"] == 1].copy().reset_index(drop=True)
    if qdf.empty:
        QMessageBox.information(None, "隔离区", "隔离区当前为空")
        return "EMPTY→弹提示"
    return "OPEN→弹窗口(%d 行)" % len(qdf)

# 变动提醒
def cb_changes():
    changes = []
    if not changes:
        QMessageBox.information(None, "变动提醒", "暂无已审核记录变动。")
        return "EMPTY→弹提示"
    return "OPEN"

# 替代料
def cb_alt():
    if "是否替代料" in df.columns:
        # filter_alt_alerts 全是"否" → 空
        sub = df[df["是否替代料"].astype(str).str.strip() == "是"]
        if sub.empty:
            QMessageBox.information(None, "提示", "没有替代料预警记录")
            return "EMPTY→弹提示"
    return "OPEN"

# 偏差率预警
def cb_dev():
    warnings_df = df[(rates.abs() >= 10) & (~no_input)].copy()
    if warnings_df.empty:
        QMessageBox.information(None, "提示", "没有偏差率预警记录")
        return "EMPTY→弹提示"
    return "OPEN(%d 行)" % len(warnings_df)

for name, fn in (("隔离区", cb_quarantine), ("变动提醒", cb_changes),
                 ("替代料", cb_alt), ("偏差率预警", cb_dev)):
    MSGS.clear()
    r = fn()
    print("  %-8s → %s   消息框: %s" % (name, r, MSGS or "无"))

print("\n" + "=" * 72)
print("结论指向：_open_board 的 `except Exception: pass`")
print("=" * 72)
print("""
用户截图：隔离区 2 条、变动提醒 0 条、替代料 0 条、偏差率预警 9 条。
用户说「现在都不定位了」—— 注意用户措辞是「都」，即**四行全点了都没反应**。

两条可能：
A) 0 条的行本来就没窗口可弹（设计如此，会弹 QMessageBox 提示）
B) 有条的行也点不动 → 说明 callback 抛异常被 except Exception: pass 吞掉

无论 A 还是 B，**`except Exception: pass` 都是元凶**：它让任何真实崩溃
（列名不符、QMessageBox 被吞、对话框构造失败）都表现为「点了没反应」，
用户和开发者都看不到任何线索。这跟本会话已修的 v43.143/v43.147
「静默失效」是同一类问题。
""")
