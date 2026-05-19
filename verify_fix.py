#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
楠岃瘉淇缁撴灉
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. 楠岃瘉鍏ㄥ眬閿?analyzer_path = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
content = open(analyzer_path, 'r', encoding='utf-8').read()

print("=== Verification Report ===\n")
print("1. Global Lock Check:")
if 'global _analysis_in_progress' in content:
    print("   鉁?PASS: Lock declaration found in do_analysis_v2")
else:
    print("   鉁?FAIL: Lock declaration not found")

if '_analysis_in_progress = False' in content:
    print("   鉁?PASS: Global variable initialized")
else:
    print("   鉁?FAIL: Global variable not found")

# 2. 楠岃瘉鍒楀悕淇
print("\n2. Column Name Check:")
files_to_check = [
    'analysis/analyzer.py',
    'analysis/sheets/sheet1_summary.py',
    'analysis/sheets/sheet3_no_note.py',
    'analysis/sheets/sheet5_full.py',
    'analysis/sheets/sheet7_amount.py',
]

for f in files_to_check:
    path = os.path.join(r'E:\zpp011_dev\妯″潡鍖栬剼鏈?, f)
    if os.path.exists(path):
        c = open(path, 'r', encoding='utf-8').read()
        # 妫€鏌ユ槸鍚﹁繕鏈夊甫绌烘牸鐨勫垪鍚?        bad_cols = ['鍋忓樊閲戦 (鍚◣)', '鏁伴噺 - 瀹為檯', '鏁伴噺 - 瀹氶', '閲戦 - 瀹為檯 (鍚◣)']
        found_bad = [col for col in bad_cols if col in c]
        if found_bad:
            print(f"   鉁?{f}: Still has {found_bad}")
        else:
            print(f"   鉁?{f}: Clean")
    else:
        print(f"   ? {f}: Not found")

# 3. 妫€鏌?sheet1_summary.py 鍏蜂綋淇
print("\n3. Sheet1 Specific Check:")
sheet1_path = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\sheets\sheet1_summary.py'
sheet1 = open(sheet1_path, 'r', encoding='utf-8').read()
if "'鍋忓樊閲戦'" in sheet1 and "'鍋忓樊閲戦 (鍚◣)'" not in sheet1:
    print("   鉁?PASS: Uses '鍋忓樊閲戦' (no parentheses)")
else:
    print("   Checking content...")
    if 'pos_amt' in sheet1:
        print("   Found pos_amt calculation")
    if 'neg_amt' in sheet1:
        print("   Found neg_amt calculation")

print("\n=== Ready for Testing ===")
print("Run: python main.py")

