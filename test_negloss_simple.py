"""测试 NegLossContent 数据加载流程"""
import sys
import os
sys.path.insert(0, 'E:/zpp011_v2')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
# 移除 QVBoxLayout 未使用导入
import pandas as pd

from gui_pyside6.widgets.neg_loss_content import NegLossContent

app = QApplication.instance() or QApplication([])

class MockMainWindow:
    pass

mw = MockMainWindow()
content = NegLossContent(mw)

# 创建一些假数据
df = pd.DataFrame({
    '工厂': ['A'],
    '订单日期': ['2023-01-01'],
    '流程订单': ['1'],
    '物料编码': ['123'],
    '物料名称': ['Test'],
    '车间': ['Shop'],
    '单位': ['个'],
    '数量-定额': [1],
    '数量-实际': [0.5],
    '备注': [''],
    '半成品重分类': ['']
})

content.set_data(df)
print('SSet data OK')
