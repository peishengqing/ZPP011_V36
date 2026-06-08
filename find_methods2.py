#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印文件中所有方法定义"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Searching for method definitions containing '_set_audit_data'...")
for i, line in enumerate(lines):
    stripped = line.strip()
    if '_set_audit_data' in stripped:
        print(f"Line {i+1}: {stripped}")
        if i < 5:
            break

print("\nAll method definitions (def ...) in the file:")
count = 0
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('def '):
        print(f"Line {i+1}: {stripped}")
        count += 1
        if count > 30:  # 只打印前30个方法
            break
