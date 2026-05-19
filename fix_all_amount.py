#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 鍏ㄥ眬鏇挎崲锛氬皢 '鍋忓樊閲戦' 鏇挎崲涓?'鍋忓樊閲戦'锛堝湪閲嶅懡鍚嶉€昏緫涔嬪浣跨敤鐨勬墍鏈夊湴鏂癸級
replacements = [
    ("'鍋忓樊閲戦'", "'鍋忓樊閲戦'"),
    ('"鍋忓樊閲戦"', '"鍋忓樊閲戦"'),
]

count = 0
for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py') and filename not in ['check_deviation.py', 'check_sheets.py', 'fix_column_names.py', 'fix_deviation_amount.py', 'update_analyzer.py']:
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    original = f.read()
                
                modified = original
                for old, new in replacements:
                    modified = modified.replace(old, new)
                
                if modified != original:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(modified)
                    print(f"FIXED: {filepath}")
                    count += 1
            except Exception as e:
                print(f"ERROR: {filepath} - {e}")

print(f"\nDONE: Fixed {count} files")

