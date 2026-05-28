#!/usr/bin/env python3
# -*- coding: utf-8 -*'
"""添加 _update_filter_options 方法到 analysis_events.py"""

import re

def add_method():
    filepath = 'gui/event_handlers/analysis_events.py'
    
    # 读取文件
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # 新方法代码
    new_method = '''

    def _update_filter_options(self):
        """基于全量数据 (self.full_audit_data) 更新筛选下拉框的选项。
        确保方法只在数据加载时被调用一次。
        """
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
'''
    
    # 在文件末尾添加新方法（在最后一个方法之后）
    # 找最后一个 '    def ' 的位置
    last_def_match = None
    for m in re.finditer(r'^    def \w+', content, re.MULTILINE):
        last_def_match = m
    
    if last_def_match:
        # 找这个方法体结束的位置（下一个 def 或文件末尾）
        last_def_pos = last_def_match.start()
        
        # 找下一个 def 或 class 的位置
        next_def_pos = content.find('\n    def ', last_def_pos + 10)
        next_class_pos = content.find('\nclass ', last_def_pos + 10)
        
        # 取较小的有效位置
        positions = [p for p in [next_def_pos, next_class_pos] if p != -1]
        if positions:
            insert_pos = min(positions)
        else:
            # 没找到，插入到文件末尾
            insert_pos = len(content)
        
        # 插入新方法
        content = content[:insert_pos] + new_method + '\n' + content[insert_pos:]
        
        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ _update_filter_options 方法已添加到 analysis_events.py")
        print(f"   插入位置: {insert_pos}")
    else:
        print("❌ 未找到任何方法定义，无法添加")

if __name__ == '__main__':
    add_method()
