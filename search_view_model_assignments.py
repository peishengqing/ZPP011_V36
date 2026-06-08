#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Search for all assignments to self.view_model.df = """

import re

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Searching for 'self.view_model.df =' assignments:\n")

assignments = []
for i, line in enumerate(lines):
    # 匹配 self.view_model.df = （排除 == 比较）
    if re.search(r'self\.view_model\.df\s*=(?!=)', line):
        assignments.append((i + 1, line.rstrip()))

print(f"Found {len(assignments)} assignments:\n")

for line_num, content in assignments:
    print(f"Line {line_num}: {content.strip()}")

# Also check for direct modifications like self.view_model.df['column'] = value
print("\n" + "="*60)
print("Checking for direct DataFrame modifications (self.view_model.df[...] = ...):\n")

modifications = []
for i, line in enumerate(lines):
    if 'self.view_model.df[' in line and '=' in line:
        modifications.append((i + 1, line.rstrip()))

if modifications:
    for line_num, content in modifications:
        print(f"Line {line_num}: {content.strip()}")
else:
    print("None found.")

# Check for calls to _set_audit_data
print("\n" + "="*60)
print("Checking for calls to _set_audit_data:\n")

calls = []
for i, line in enumerate(lines):
    if '_set_audit_data(' in line:
        calls.append((i + 1, line.rstrip()))

print(f"Found {len(calls)} calls:\n")

for line_num, content in calls:
    print(f"Line {line_num}: {content.strip()}")
