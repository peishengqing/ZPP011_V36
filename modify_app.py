#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修改 app.py：实现 _on_filter_panel_expand 方法"""

import os

file_path = r"E:\zpp011_dev\模块化脚本\gui\app.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 _on_filter_panel_expand 方法的位置
# 当前是一个 stub：lines 335-337 (0-indexed) = lines 336-338 (1-indexed)
# def _on_filter_panel_expand(self, expanded):
#     """侧边栏展开/折叠时的回调（预览当前值，避免后续平移抖动）"""
#     pass

start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if '_on_filter_panel_expand' in line and 'def ' in line:
        start_idx = i
        # 找到方法的结束（下一个 def 或类方法）
        for j in range(i + 1, len(lines)):
            if lines[j].strip() and not lines[j].startswith('        ') and not lines[j].startswith('\t\t') and not lines[j].strip().startswith('#'):
                if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                    end_idx = j
                    break
            # 如果遇到空行后有缩进的行，继续
            if j == i + 3:  # stub 应该只有3行（def, docstring, pass）
                if 'pass' in lines[j] or (j + 1 < len(lines) and lines[j+1].strip() and not lines[j+1].startswith('        ')):
                    end_idx = j + 1
                    break
        if end_idx is None:
            end_idx = i + 3  # 默认 stub 有3行
        break

print(f"找到方法在第 {start_idx+1} 到 {end_idx} 行")

# 新实现
new_method = '''    def _on_filter_panel_expand(self, expanded):
        """侧边栏展开/折叠时的回调（消除平移抖动）"""
        try:
            # 动态获取侧边栏宽度（消除硬编码 250）
            sidebar_width = getattr(self.filter_panel, 'width', 250)
            new_width = self.root.winfo_width() - sidebar_width
            
            # 优化：仅在宽度变化超过 5px 时执行 update_idletasks
            current_width = self.table_frame.winfo_width()
            if abs(new_width - current_width) > 5:
                self.table_frame.configure(width=new_width)
                self.root.update_idletasks()
        except Exception as e:
            print(f"[_on_filter_panel_expand] 错误: {e}")

'''

# 替换
lines_new = lines[:start_idx] + [new_method] + lines[end_idx:]

# 写回文件
with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines_new)

print("✓ app.py 修改完成")
