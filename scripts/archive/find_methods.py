#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索 _start_analysis 方法定义"""
import re

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"
lines = open(fp, encoding='utf-8').readlines()

print("搜索 def _start_analysis:")
for i, line in enumerate(lines):
    if re.search(r'^\s*def\s+_start_analysis\s*\(', line):
        print(f"  找到：行 {i+1}: {line.rstrip()}")
        break
else:
    print("  未找到")

print("\n搜索 _cancel_analysis 方法定义:")
for i, line in enumerate(lines):
    if re.search(r'^\s*def\s+_cancel_analysis\s*\(', line):
        print(f"  找到：行 {i+1}: {line.rstrip()}")
        break
else:
    print("  未找到")
