#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Search for all occurrences of 'self.audit_data' in main_window.py"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Searching for 'self.audit_data' in: {fp}\n")

occurrences = []
for i, line in enumerate(lines):
    if 'self.audit_data' in line:
        occurrences.append((i + 1, line.rstrip()))

print(f"Found {len(occurrences)} occurrences:\n")

for line_num, content in occurrences[:30]:  # Show first 30
    print(f"Line {line_num}: {content.strip()}")

if len(occurrences) > 30:
    print(f"\n... and {len(occurrences) - 30} more (total {len(occurrences)})")

# Also check for 'audit_data' without 'self.'
print("\n" + "="*60)
print("Checking for 'audit_data' without 'self.':")
count = 0
for i, line in enumerate(lines):
    if 'audit_data' in line and 'self.audit_data' not in line:
        print(f"Line {i+1}: {line.rstrip().strip()}")
        count += 1

if count == 0:
    print("None found.")
