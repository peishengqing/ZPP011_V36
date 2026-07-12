import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import pandas as pd
from PySide6.QtWidgets import QApplication
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel

app = QApplication([])

# 模拟分析后的结果表：同时含 物料编码 与 物料号 两列
# 物料编码 列：5 行都是 20003246（用户看到的、要筛选的）
# 物料号 列：仅第 0 行是 20003246，其余是别的 9 位编码（旧逻辑只查这一列 → 只筛 1 行）
df = pd.DataFrame({
    '订单日期': ['2026-01-01'] * 5,
    '流程订单': ['PO1', 'PO2', 'PO3', 'PO4', 'PO5'],
    '物料编码': ['20003246', '20003246', '20003246', '20003246', '20003246'],
    '物料号':   ['20003246', '300012340', '300012341', '300012342', '300012343'],
    '组件物料号': ['20003246', '300012340', '300012341', '300012342', '300012343'],
    '偏差率(%)': [1.0, 2.0, 3.0, 4.0, 5.0],
})

src = DataFrameModel()
src.setDataFrame(df)
proxy = AuditProxyModel()
proxy.setSourceModel(src)

# 设置物料编码筛选
proxy.setCustomFilters({'_material_code': '20003246'})
proxy.invalidateFilter()
app.processEvents()

rows = proxy.rowCount()
print(f"筛选 '20003246' 命中行数 = {rows}  (期望 5)")
assert rows == 5, f"BUG: 只筛到 {rows} 行"

# 多值 OR + 跨列
proxy.setCustomFilters({'_material_code': '20003246,300012342'})
proxy.invalidateFilter()
app.processEvents()
rows2 = proxy.rowCount()
print(f"筛选 '20003246,300012342' 命中行数 = {rows2}  (期望 6: 5+1)")
assert rows2 == 6, f"多值OR异常: {rows2}"

# 不存在的编码
proxy.setCustomFilters({'_material_code': '99999999'})
proxy.invalidateFilter()
app.processEvents()
rows3 = proxy.rowCount()
print(f"筛选 '99999999' 命中行数 = {rows3}  (期望 0)")
assert rows3 == 0, f"不该命中: {rows3}"

print("ALL PASS")
