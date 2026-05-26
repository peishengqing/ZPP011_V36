#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查找需要修改的行号"""

import os

# 查找 ui_builder.py 中的 tree_container 行
ui_builder_path = r"E:\zpp011_dev\模块化脚本\gui\ui_builder.py"
with open(ui_builder_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if 'tree_container = tk.Frame(audit' in line:
            print(f"ui_builder.py 第 {i} 行: {line.rstrip()}")
            # 查看前后5行
            print(f"\n前5行:")
            for j in range(max(0, i-6), i-1):
                print(f"  {j+1}: {lines[j].rstrip()}")
            print(f"\n后5行:")
            for j in range(i, min(len(lines), i+5)):
                print(f"  {j+1}: {lines[j].rstrip()}")
            break

print("\n" + "="*60 + "\n")

# 查找 app.py 中的 _on_filter_panel_expand 方法
app_path = r"E:\zpp011_dev\模块化脚本\gui\app.py"
with open(app_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if '_on_filter_panel_expand' in line:
            print(f"app.py 第 {i} 行: {line.rstrip()}")
            # 查看方法体（假设方法不超过20行）
            print(f"\n方法内容:")
            for j in range(i-1, min(len(lines), i+20)):
                print(f"  {j+1}: {lines[j].rstrip()}")
            break
