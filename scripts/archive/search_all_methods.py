#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索 _start_analysis 和 _run_ai_audit 方法定义"""
import re

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"
lines = open(fp, encoding='utf-8').readlines()

print("=" * 60)
print("搜索 def _start_analysis:")
found = False
for i, line in enumerate(lines):
    if re.search(r'^\s*def\s+_start_analysis\s*\(', line):
        print(f"  找到：行 {i+1}: {line.rstrip()}")
        found = True
        break
if not found:
    print("  未找到 def _start_analysis")

print("\n搜索 def _run_ai_audit:")
found = False
for i, line in enumerate(lines):
    if re.search(r'^\s*def\s+_run_ai_audit\s*\(', line):
        print(f"  找到：行 {i+1}: {line.rstrip()}")
        found = True
        break
if not found:
    print("  未找到 def _run_ai_audit")

print("\n搜索所有包含 'def _' 的行（前30个）:")
count = 0
for i, line in enumerate(lines):
    if re.search(r'^\s*def\s+_', line):
        print(f"  {i+1}: {line.rstrip()}")
        count += 1
        if count >= 30:
            break

print("=" * 60)
