#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修改 ui_builder.py：添加 table_frame 并使其成为 tree_container 的父容器"""

import os

file_path = r"E:\zpp011_dev\模块化脚本\gui\ui_builder.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# 找到 "tree_container = tk.Frame(audit," 所在的行
target_line_idx = None
for i, line in enumerate(lines):
    if 'tree_container = tk.Frame(audit,' in line or 'tree_container = tk.Frame(audit ' in line:
        target_line_idx = i
        break

if target_line_idx is None:
    print("错误：找不到 tree_container 的定义")
    exit(1)

print(f"找到目标行在第 {target_line_idx + 1} 行:")
print(f"  {lines[target_line_idx]}")

# 在目标行之前插入 table_frame 的创建代码
# 需要保持相同的缩进级别（8个空格）
insert_code = [
    '        self.table_frame = tk.Frame(audit, bg=C[\'surface\'])',
    '        self.table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))',
    ''
]

# 插入
lines_with_table_frame = lines[:target_line_idx] + insert_code + lines[target_line_idx:]

# 现在修改原目标行（注意：因为插入了3行，所以索引增加了3）
new_target_idx = target_line_idx + 3

if 'tree_container = tk.Frame(audit,' in lines_with_table_frame[new_target_idx]:
    old_line = lines_with_table_frame[new_target_idx]
    lines_with_table_frame[new_target_idx] = old_line.replace('tk.Frame(audit,', 'tk.Frame(self.table_frame,')
    print(f"\n已修改第 {new_target_idx + 1} 行:")
    print(f"  原行: {old_line}")
    print(f"  新行: {lines_with_table_frame[new_target_idx]}")
else:
    print(f"\n警告：预期在第 {new_target_idx + 1} 行找到 tree_container 定义，但实际是:")
    print(f"  {lines_with_table_frame[new_target_idx]}")
    exit(1)

# 重新组合成字符串，保持 Unix 换行符
new_content = '\n'.join(lines_with_table_frame)

# 写回文件（使用 UTF-8 编码，Unix 换行符）
with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content)

print("\n✓ ui_builder.py 修改完成")
