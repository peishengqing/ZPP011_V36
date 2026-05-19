#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缁堟瀬鍒楀悕淇锛氱粺涓€浣跨敤 '璁㈠崟寮€濮嬫棩鏈? 鏇夸唬 '璁㈠崟寮€濮嬫棩鏈?
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 鍒楀悕鏇挎崲瑙勫垯
replacements = [
    ("'璁㈠崟寮€濮嬫棩鏈?", "'璁㈠崟寮€濮嬫棩鏈?"),
    ('"璁㈠崟寮€濮嬫棩鏈?', '"璁㈠崟寮€濮嬫棩鏈?'),
    ("dev['璁㈠崟寮€濮嬫棩鏈?]", "dev['璁㈠崟寮€濮嬫棩鏈?]"),
    ("df['璁㈠崟寮€濮嬫棩鏈?]", "df['璁㈠崟寮€濮嬫棩鏈?]"),
    ("r['璁㈠崟寮€濮嬫棩鏈?]", "r['璁㈠崟寮€濮嬫棩鏈?]"),
    ("row['璁㈠崟寮€濮嬫棩鏈?]", "row['璁㈠崟寮€濮嬫棩鏈?]"),
]

count = 0
modified_files = []

for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py'):
            # 璺宠繃杈呭姪鑴氭湰
            skip_files = ['fix_all_amount.py', 'fix_column_names.py', 'fix_deviation_amount.py', 
                         'update_analyzer.py', 'check_deviation.py', 'check_sheets.py', 
                         'check_analyzer_amount.py', 'ultimate_fix.py', 'verify_fix.py']
            if filename in skip_files:
                continue
                
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
                    modified_files.append(filepath)
            except Exception as e:
                print(f"ERROR: {filepath} - {e}")

print(f"\n=== Summary ===")
print(f"Files modified: {count}")
for f in modified_files:
    print(f"  - {os.path.basename(f)}")

print(f"\nReady: Run python main.py")

