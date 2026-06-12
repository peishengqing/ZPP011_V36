#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find and display _recalculate_net_offset method"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到方法定义
start = None
for i, line in enumerate(lines):
    if line.strip() == 'def _recalculate_net_offset(self):':
        start = i
        print(f"Found _recalculate_net_offset at line {start+1}")
        break

if start is None:
    print("ERROR: _recalculate_net_offset method not found!")
    exit(1)

# 找到方法结束
end = None
base_indent = len(lines[start]) - len(lines[start].lstrip())
for i in range(start + 1, len(lines)):
    line_stripped = lines[i].strip()
    if line_stripped.startswith('def ') or line_stripped.startswith('class '):
        curr_indent = len(lines[i]) - len(lines[i].lstrip())
        if curr_indent <= base_indent:
            end = i
            break

if end is None:
    end = len(lines)

print(f"Method ends at line {end}")
print(f"\nMethod content:\n")

for i in range(start, min(end, start + 50)):  # 最多显示50行
    print(f"{i+1:4d}: {lines[i]}", end='')
