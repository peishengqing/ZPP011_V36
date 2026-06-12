#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""找到 _cancel_analysis 的准确行号"""
fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"
lines = open(fp, encoding='utf-8').readlines()

print("Searching for 'def _cancel_analysis'...")
for i, line in enumerate(lines):
    if '_cancel_analysis' in line and 'def ' in line:
        print(f"Found at line {i+1}: {line.rstrip()}")
        break
else:
    print("NOT FOUND in file!")
    
print("\nSearching for '_cancel_analysis' (any occurrence)...")
for i, line in enumerate(lines):
    if '_cancel_analysis' in line:
        print(f"  Line {i+1}: {line.rstrip()}")
        if i > 20:
            break
