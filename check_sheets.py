#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\sheets'
files = ['sheet1_summary.py', 'sheet2_alt.py', 'sheet3_no_note.py', 'sheet4_middle.py', 'sheet5_full.py', 'sheet6_anomaly.py', 'sheet7_amount.py']

print("Searching for '鍋忓樊閲戦 (鍚◣)' in sheet files...\n")
for f in files:
    path = os.path.join(root, f)
    content = open(path, 'r', encoding='utf-8').read()
    if '鍋忓樊閲戦 (鍚◣)' in content:
        lines = [(i, l.strip()) for i, l in enumerate(content.split('\n'), 1) if '鍋忓樊閲戦 (鍚◣)' in l]
        print(f"FOUND in {f}:")
        for i, l in lines:
            print(f"  Line {i}: {l[:100]}")
    else:
        print(f"OK: {f}")

