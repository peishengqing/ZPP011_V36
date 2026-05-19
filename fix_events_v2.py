#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
淇 events.py 涓殑璁㈠崟鏃ユ湡鍒楅棶棰?"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
lines = open(path, 'r', encoding='utf-8').readlines()

# 鎵惧埌闇€瑕佷慨鏀圭殑浣嶇疆锛堢 2122-2128 琛岄檮杩戯級
new_lines = []
skip_until_uid = False
uid_inserted = False

for i, line in enumerate(lines, 1):
    # 璺宠繃鍘熸潵鐨?"鐢熸垚鍞竴 ID" 閮ㄥ垎
    if i >= 2122 and i <= 2127 and '璁㈠崟寮€濮嬫棩鏈? in line:
        if "'璁㈠崟寮€濮嬫棩鏈?.astype" in line:
            skip_until_uid = True
            continue
        if skip_until_uid:
            continue
    
    new_lines.append(line)

# 鍦ㄥ悎閫備綅缃彃鍏ヤ慨澶嶄唬鐮?# 鎵惧埌 "audit_df['_uid'] =" 涔嬪墠鐨勪綅缃?insert_idx = None
for i, line in enumerate(new_lines):
    if "audit_df['_uid'] =" in line:
        insert_idx = i
        break

if insert_idx is not None:
    # 鎻掑叆鏃ユ湡鍒楁煡鎵句唬鐮?    date_fix_code = """        # 鏃ユ湡鍒楁煡鎵撅紙淇锛氭敮鎸佸绉嶅垪鍚嶏級
        date_col = None
        for possible in ['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟鏃ユ湡', '鏃ユ湡']:
            if possible in audit_df.columns:
                date_col = possible
                break
            if possible in dev_df.columns:
                date_col = possible
                break
        
        if date_col is None:
            # 濡傛灉鎵句笉鍒版棩鏈熷垪锛屽垱寤虹┖鍒?            audit_df['璁㈠崟寮€濮嬫棩鏈?] = ''
            audit_df['璁㈠崟鏃ユ湡'] = ''
        else:
            # 缁熶竴鍒涘缓涓や釜鍒楀悕锛屾柟渚垮悗缁娇鐢?            audit_df['璁㈠崟寮€濮嬫棩鏈?] = pd.to_datetime(audit_df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
            audit_df['璁㈠崟鏃ユ湡'] = audit_df['璁㈠崟寮€濮嬫棩鏈?]

"""
    new_lines.insert(insert_idx, date_fix_code)
    print(f"SUCCESS: Inserted date column fix at line {insert_idx}")
else:
    print("ERROR: Could not find insertion point")

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("File updated successfully")
