#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Search for remaining _set_audit_data calls"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Searching for remaining '_set_audit_data' calls:\n")

found = []
for i, line in enumerate(lines):
    if '_set_audit_data' in line:
        found.append((i + 1, line.rstrip()))

if found:
    print(f"Found {len(found)} remaining calls:\n")
    for line_num, content in found:
        print(f"Line {line_num}: {content.strip()}")
else:
    print("None found! All calls have been replaced.")

# Also check if _init_table_model method exists
print("\n" + "="*60)
print("Checking if _init_table_model method exists:")

for i, line in enumerate(lines):
    if 'def _init_table_model(self):' in line:
        print(f"  Found at line {i+1}")
        break
else:
    print("  NOT FOUND!")

# Check if _init_table_model() is called in __init__
print("\n" + "="*60)
print("Checking if _init_table_model() is called in __init__:")

in_init = False
found_call = False
for i, line in enumerate(lines):
    if 'def __init__(self' in line:
        in_init = True
        continue
    if in_init:
        if 'def ' in line and line.strip().startswith('def '):
            break
        if '_init_table_model()' in line:
            found_call = True
            print(f"  Found at line {i+1}: {line.strip()}")
            break

if not found_call:
    print("  NOT FOUND in __init__!")
