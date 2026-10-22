# -*- coding: utf-8 -*-
"""定位 T3/T4 失败根因：纯订单过滤到底能不能命中 39 行。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

import pandas as pd
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel

app = QApplication.instance() or QApplication([])

df = pd.read_pickle(r"C:\Temp\zpp_dev_out\dev.pkl").reset_index(drop=True)
model = DataFrameModel(df)
proxy = AuditProxyModel()
proxy.setSourceModel(model)
app.processEvents()

big = "300463299"
print("原始 rowCount:", proxy.rowCount())


def probe(filters, label):
    proxy.setCustomFilters(filters)
    app.processEvents()
    rc = proxy.rowCount()
    # 再手工逐行数一遍
    cnt = 0
    for r in range(model.rowCount()):
        if proxy.filterAcceptsRow(r, QModelIndex()):
            cnt += 1
    print("  %-46s rowCount=%-6d 逐行数=%-6d filters=%s" % (label, rc, cnt, filters))
    return rc, cnt


print("\n纯订单:")
probe({"_process_order": big}, "只有 _process_order")
probe({}, "空 filters")

print("\n叠加物料:")
probe({"_process_order": big, "_material_code": "10000583"}, "订单+正确物料")
probe({"_process_order": big, "_material_code": "99999999"}, "订单+错误物料")

print("\n再次回到纯订单（模拟 T3 回退）:")
probe({"_process_order": big}, "回退后再纯订单")

print("\n再叠加物料，再回退:")
probe({"_process_order": big, "_material_code": "10000583"}, "订单+物料")
probe({"_process_order": big}, "再回退")

print("\n检查 proxy 内部状态:")
print("  _custom_filters:", proxy.getCustomFilters())
print("  _filters:", getattr(proxy, "_filters", None))
print("  _value_filters:", getattr(proxy, "_value_filters", None))
print("  _alert_threshold:", getattr(proxy, "_alert_threshold", None))
