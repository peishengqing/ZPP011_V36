#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""添加 _update_filter_options 方法到 analysis_events.py"""
import re

def add_method():
    filepath = 'gui/event_handlers/analysis_events.py'
    
    # 读取文件
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    
    content = ''.join(lines)
    
    # 检查是否已有 _update_filter_options 方法
    if 'def _update_filter_options(' in content:
        print("[INFO] _update_filter_options 方法已存在，跳过添加")
        return True
    
    # 新方法代码
    new_method = r"""

    def _update_filter_options(self):
        \"\"\"基于全量数据 (self.full_audit_data) 更新筛选下拉框的选项。
        确保方法只在数据加载时被调用一次。
        \"\"\"
        if not hasattr(self, 'full_audit_data') or self.full_audit_data is None:
            print("[DEBUG] full_audit_data 不存在，跳过下拉框初始化")
            return
        
        # 选择性地打印数据列，方便调试
        print(f"[DEBUG] 全量数据列名: {list(self.full_audit_data.columns)}")
        
        # 在全量数据中查找物料相关列
        if 'material_category' in self.full_audit_data.columns:
            category_col = 'material_category'
        elif '物料类型' in self.full_audit_data.columns:
            category_col = '物料类型'
        else:
            print("[DEBUG] 未找到物料大类列，跳过下拉框初始化")
            return
        
        # 从全量数据中提取唯一值并排序
        unique_vals = sorted(self.full_audit_data[category_col].dropna().unique())
        options = ["全部"] + [str(val) for val in unique_vals if val]
        
        # 更新下拉框
        if hasattr(self, 'mat_category_cb') and self.mat_category_cb:
            self.mat_category_cb['values'] = options
            # 如果当前选中的值已不在新选项列表中，则重置为"全部"
            if self.mat_category_cb.get() not in options:
                self.mat_category_cb.set("全部")
            print(f"[DEBUG] 物料大类下拉框已初始化，选项数: {len(options)}")
            print(f"[DEBUG] 选项内容: {options}")
        
        # 触发一次筛选刷新
        if hasattr(self, '_on_filter_changed'):
            self._on_filter_changed('material_category')
"""
    
    # 找最后一个方法的位置
    # 找所有 "    def " 开头的行
    last_def_line = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('def '):
            last_def_line = i
    
    if last_def_line == -1:
        print("[ERROR] 未找到任何方法定义")
        return False
    
    # 找这个方法体结束的位置（下一个 def 或 class 或文件末尾）
    insert_line = len(lines)
    for i in range(last_def_line + 1, len(lines)):
        line = lines[i]
        if line.strip().startswith('def ') or line.strip().startswith('class '):
            insert_line = i
            break
    
    # 插入新方法
    new_lines = new_method.split('\n')
    for i, line in enumerate(new_lines):
        lines.insert(insert_line + i, line + '\n')
    
    # 写回文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"[SUCCESS] _update_filter_options 方法已添加到 analysis_events.py 第 {insert_line} 行")
    return True

if __name__ == '__main__':
    add_method()
