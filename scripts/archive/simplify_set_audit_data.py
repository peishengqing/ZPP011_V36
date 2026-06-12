#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""替换 _set_audit_data 方法为简化版本（仅设置数据，不重复创建模型）"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 _set_audit_data 方法的开始和结束
start = None
end = None
base_indent = None

for i, line in enumerate(lines):
    if line.strip() == 'def _set_audit_data(self, df: pd.DataFrame):':
        start = i
        base_indent = len(line) - len(line.lstrip())
        print(f"Found _set_audit_data at line {start+1}")
        break

if start is None:
    print("ERROR: _set_audit_data method not found!")
    exit(1)

# 找到方法结束（下一个 def 或 class，或文件结束）
for i in range(start + 1, len(lines)):
    line_stripped = lines[i].strip()
    if line_stripped.startswith('def ') or line_stripped.startswith('class '):
        curr_indent = len(lines[i]) - len(lines[i].lstrip())
        if curr_indent <= base_indent:
            end = i
            break

if end is None:
    end = len(lines)

print(f"_set_audit_data ends at line {end}")
print(f"Method length: {end - start} lines")

# 构建新的方法
new_method = '''    def _set_audit_data(self, df: pd.DataFrame):
        """加载数据到表格，使用 DataService 预处理"""
        # 调用数据服务进行预处理
        processed_df = self.data_service.preprocess_audit_data(df, self.view_model.df)

        # 首次使用时创建模型（避免重复创建）
        if self.source_model is None:
            self.source_model = DataFrameModel()
            self.proxy_model = AuditProxyModel()
            self.proxy_model.setSourceModel(self.source_model)
            self.table_view.setModel(self.proxy_model)
            
            # 连接选中变化信号（仅首次）
            try:
                self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
            except Exception:
                pass
            
            # 连接数据变化信号（仅首次）
            self.source_model.dataChanged.connect(self._update_summary)
            self.proxy_model.layoutChanged.connect(self._update_summary)
            
            # 列宽初始化（仅首次）
            self.table_view.resizeColumnsToContents()
            self.table_view.setColumnWidth(0, 35)
            self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            self.lock_btn.setChecked(False)
        
        # 更新数据到模型
        self.source_model.setDataFrame(processed_df)
        
        # 通过 ViewModel 触发统一刷新（信号会调用 _on_view_model_data_changed）
        self.view_model.df = processed_df
        
        self.log("数据加载完成", "info")

'''

# 替换方法
lines[start:end] = [new_method]

# 写入文件
with open(fp, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Done! Replaced _set_audit_data method.")
print(f"New file length: {len(lines)} lines")
