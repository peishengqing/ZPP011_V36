#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试偏差率排序（通过ProxyModel）"""

import sys
sys.path.insert(0, r'E:\zpp011_dev\模块化脚本')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import pandas as pd
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel

# 需要QApplication
app = QApplication(sys.argv)

# 创建测试数据
df = pd.DataFrame({
    '订单日期': ['2026-01-01'] * 8,
    '偏差率(%)': ['-10.2%', '-100.0%', '18.7%', '-27.4%', '100.0%', '100.0%', '100.0%', '100.0%'],
    '偏差金额': [100, 200, 300, 400, 500, 600, 700, 800],
})

print("原始数据偏差率:", df['偏差率(%)'].tolist())

# 创建模型
model = DataFrameModel()
model.setDataFrame(df)

proxy = AuditProxyModel()
proxy.setSourceModel(model)

# 找到偏差率列的索引
rate_col_idx = -1
for i, col in enumerate(model._data.columns):
    if '偏差率' in col:
        rate_col_idx = i
        break

print(f"偏差率列索引: {rate_col_idx}")

# 测试升序排序
print("\n=== 升序排序 ===")
proxy.sort(rate_col_idx, Qt.AscendingOrder)
for i in range(proxy.rowCount()):
    idx = proxy.index(i, rate_col_idx)
    val = proxy.data(idx, Qt.DisplayRole)
    print(f"  行{i}: {val}")

# 测试降序排序
print("\n=== 降序排序 ===")
proxy.sort(rate_col_idx, Qt.DescendingOrder)
for i in range(proxy.rowCount()):
    idx = proxy.index(i, rate_col_idx)
    val = proxy.data(idx, Qt.DisplayRole)
    print(f"  行{i}: {val}")
