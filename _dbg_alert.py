# -*- coding: utf-8 -*-
"""复现 alert_dialog 半成品分类竖排 + 重复项。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from core.alert_monitor import filter_alt_alerts
from gui_pyside6.dialogs.alert_dialog import AlertDialog

dev = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
alerts = filter_alt_alerts(dev, 10)
print("替代料预警 =", alerts.shape)
cols = [c for c in [
    "工厂", "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
    "备注", "备注来源", "审核结果", "车间", "定额", "实际", "偏差数量",
    "偏差率(%)", "净偏差数量", "净偏差金额", "净偏差率(%)",
    "是否替代料", "_post_audit_changed", "_quarantined",
    "半成品重分类", "_read"] if c in alerts.columns]
sub = alerts[cols].copy()
print("半成品重分类唯一值 =", sorted(set(sub["半成品重分类"].fillna("").astype(str).str.strip())))

d = AlertDialog(sub, None)
d.resize(1200, 700)
d.show()
app.processEvents()

lay = d._semi_class_vlayout
print("\n=== 竖排布局里的控件（按 geometry 排序）===")
rows = []
for i in range(lay.count()):
    it = lay.itemAt(i)
    w = it.widget()
    if w is None:
        continue
    rows.append((w.y(), w.x(), w.text(), w.isChecked()))
for y, x, t, ck in sorted(rows):
    print("   y=%-4d x=%-3d %-22s checked=%s" % (y, x, t, ck))
print("layout 里的项数 =", len(rows))

print("\n=== grp_semi_class 的实际子控件（可能含未从布局移除的残留）===")
kids = d.grp_semi_class.findChildren(type(d._semi_class_vlayout.itemAt(0).widget()))
for w in kids:
    print("   %-22s visible=%-5s geometry=%s" % (w.text(), w.isVisible(),
          (w.x(), w.y(), w.width(), w.height())))
print("子控件总数 =", len(kids), " | 布局里 =", len(rows))

print("\n=== 再调一次 set_data，看是否翻倍 ===")
d.set_data(sub.copy())
app.processEvents()
rows2 = []
for i in range(lay.count()):
    w = lay.itemAt(i).widget()
    if w is not None:
        rows2.append((w.y(), w.x(), w.text()))
print("第二次后 layout 项数 =", len(rows2))
kids2 = d.grp_semi_class.findChildren(type(lay.itemAt(0).widget()))
print("第二次后子控件总数 =", len(kids2), "（残留 %d 个）" % (len(kids2) - len(rows2)))
for w in sorted(kids2, key=lambda x: (x.y(), x.x())):
    print("   %-22s visible=%s" % (w.text(), w.isVisible()))
