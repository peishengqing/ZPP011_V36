#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 _set_audit_data 方法后添加 _on_view_model_data_changed 方法"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 def _set_audit_data 的位置
start = None
for i, line in enumerate(lines):
    if line.strip() == 'def _set_audit_data(self, processed_df):':
        start = i
        break

if start is None:
    print("ERROR: _set_audit_data method not found!")
    exit(1)

print(f"Found _set_audit_data at line {start+1}")

# 找到方法结束的位置（下一个 def 或类结束）
end = None
for i in range(start + 1, len(lines)):
    if lines[i].strip().startswith('def ') or lines[i].strip().startswith('class '):
        end = i
        break

if end is None:
    end = len(lines)

print(f"_set_audit_data ends at line {end+1}")
print(f"Method body lines: {end - start}")

# 新方法代码
new_method = '''    def _on_view_model_data_changed(self):
        """ViewModel 数据变化时，刷新所有依赖的 UI 组件"""
        df = self.view_model.df
        if df is None or df.empty:
            # 清空界面
            self._update_summary()
            self._update_stat_cards(pd.DataFrame())
            self.filter_panel.update_options(pd.DataFrame())
            return
        
        # 刷新合计行
        self._update_summary()
        # 刷新统计卡片
        self._update_stat_cards(df)
        # 刷新筛选面板下拉选项
        self.filter_panel.update_options(df)

'''

# 插入到 _set_audit_data 方法结束后
lines = lines[:end] + [new_method] + lines[end:]

# 写入文件
with open(fp, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Added _on_view_model_data_changed after _set_audit_data")
print(f"New file lines: {len(lines)}")
