#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 EnhancedSortProxyModel 类末尾添加预警行高亮方法"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\models\enhanced_sort_proxy_model.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 lessThan 方法的结束位置（最后一个 return 语句）
# 实际上，我们需要在文件末尾（类结束前）插入新方法
# 在 Python 中，类的结束是通过缩进级别判断的

# 找到最后一个有内容的行的索引
last_line_idx = len(lines) - 1
while last_line_idx >= 0 and lines[last_line_idx].strip() == '':
    last_line_idx -= 1

print(f"Last non-empty line: {last_line_idx + 1}")

# 构建要插入的方法
new_methods = '''    def _is_alert_row(self, source_row: int) -> bool:
        """检查某行是否为预警行（偏差率 > 10%）"""
        source_model = self.sourceModel()
        if not source_model:
            return False
        # 查找偏差率列
        rate_col = None
        for col in range(source_model.columnCount()):
            col_name = source_model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
            if col_name in ('偏差率(%)', '偏差率'):
                rate_col = col
                break
        if rate_col is None:
            return False
        idx = source_model.index(source_row, rate_col)
        rate_str = source_model.data(idx, Qt.DisplayRole)
        try:
            rate = float(rate_str.replace('%', '').strip())
            return abs(rate) > 10
        except:
            return False

    def data(self, index, role=Qt.DisplayRole):
        """重写 data 方法，为预警行添加浅红色背景"""
        if not index.isValid():
            return None
        source_index = self.mapToSource(index)
        if not source_index.isValid():
            return None
        if role == Qt.BackgroundRole and self._is_alert_row(source_index.row()):
            return QColor(255, 200, 200)  # 浅红
        return self.sourceModel().data(source_index, role)
'''

# 在文件末尾插入新方法
# 需要先添加一个空行，然后添加新方法
lines.insert(last_line_idx + 1, '\n')
lines.insert(last_line_idx + 2, new_methods)

# 写入文件
with open(fp, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Done! Added _is_alert_row and data methods to EnhancedSortProxyModel")
print(f"Total lines: {len(lines)}")
