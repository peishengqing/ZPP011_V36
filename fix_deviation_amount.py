#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 1. 淇敼 analyzer.py锛氭坊鍔犲亸宸噾棰濆垪鍚嶉噸鍛藉悕
analyzer_path = os.path.join(root, 'analysis', 'analyzer.py')
with open(analyzer_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 鍦ㄧ粓鏋佸垪鍚嶆竻鐞嗗悗娣诲姞鍋忓樊閲戦閲嶅懡鍚?
old_code = '''    # ========== 缁堟瀬鍒楀悕娓呯悊锛氱Щ闄ゆ墍鏈夌┖鏍?==========
    df.columns = [col.strip().replace(' ', '') for col in df.columns]
    _dprint("[DEBUG] 宸叉竻闄ゆ墍鏈夊垪鍚嶄腑鐨勭┖鏍?)
    _dprint(f"[DEBUG] 娓呯悊鍚庡垪鍚嶇ず渚嬶細{list(df.columns)[:10]}")'''

new_code = '''    # ========== 缁堟瀬鍒楀悕娓呯悊锛氱Щ闄ゆ墍鏈夌┖鏍?==========
    df.columns = [col.strip().replace(' ', '') for col in df.columns]
    _dprint("[DEBUG] 宸叉竻闄ゆ墍鏈夊垪鍚嶄腑鐨勭┖鏍?)
    _dprint(f"[DEBUG] 娓呯悊鍚庡垪鍚嶇ず渚嬶細{list(df.columns)[:10]}")

    # ========== 缁熶竴鍋忓樊閲戦鍒楀悕 ==========
    if '鍋忓樊閲戦' in df.columns:
        df.rename(columns={'鍋忓樊閲戦': '鍋忓樊閲戦'}, inplace=True)
        _dprint("[DEBUG] 宸插皢 '鍋忓樊閲戦' 閲嶅懡鍚嶄负 '鍋忓樊閲戦'")'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(analyzer_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Updated analyzer.py with 鍋忓樊閲戦 rename")
else:
    print("SKIP: analyzer.py code not found")

# 2. 鍏ㄥ眬鏇挎崲锛氬皢 '鍋忓樊閲戦' 鏇挎崲涓?'鍋忓樊閲戦'
replacements = [
    ('鍋忓樊閲戦', '鍋忓樊閲戦'),
]

count = 0
for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath or 'fix_column_names.py' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py'):
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

