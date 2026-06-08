#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final verification: Search for _set_audit_data and run syntax check"""

import py_compile
import sys

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

print("="*60)
print("Final Verification")
print("="*60)

# 1. Search for remaining _set_audit_data calls
print("\n1. Searching for remaining '_set_audit_data' calls...\n")

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

found = []
for i, line in enumerate(lines):
    if '_set_audit_data' in line:
        found.append((i + 1, line.rstrip()))

if found:
    print(f"  WARNING: Found {len(found)} remaining calls:\n")
    for line_num, content in found:
        print(f"  Line {line_num}: {content.strip()}")
else:
    print("  PASS: No remaining _set_audit_data calls found!")

# 2. Syntax check
print("\n" + "="*60)
print("2. Syntax check...\n")

try:
    py_compile.compile(fp, doraise=True)
    print("  PASS: Syntax check passed!")
    syntax_ok = True
except py_compile.PyCompileError as e:
    print(f"  FAIL: Syntax error: {e}")
    syntax_ok = False

# 3. Check if _init_table_model method exists
print("\n" + "="*60)
print("3. Checking if _init_table_model method exists...\n")

method_found = False
for i, line in enumerate(lines):
    if 'def _init_table_model(self):' in line:
        print(f"  PASS: Found _init_table_model method at line {i+1}")
        method_found = True
        break

if not method_found:
    print("  WARNING: _init_table_model method NOT FOUND!")

# 4. Check if _init_table_model() is called in __init__
print("\n" + "="*60)
print("4. Checking if _init_table_model() is called in __init__...\n")

in_init = False
call_found = False
for i, line in enumerate(lines):
    if 'def __init__(self' in line:
        in_init = True
        continue
    if in_init:
        if 'def ' in line and line.strip().startswith('def '):
            break
        if '_init_table_model()' in line:
            call_found = True
            print(f"  PASS: Found call at line {i+1}: {line.strip()}")
            break

if not call_found:
    print("  WARNING: _init_table_model() call NOT FOUND in __init__!")

# Summary
print("\n" + "="*60)
print("Summary")
print("="*60)

all_pass = (len(found) == 0) and syntax_ok and method_found and call_found

if all_pass:
    print("\nAll checks passed! Refactoring complete.")
else:
    print("\nSome checks failed. Please review.")
