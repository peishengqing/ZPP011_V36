#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
鏈€缁堥獙璇侊細妫€鏌ユ墍鏈夊叧閿枃浠剁殑鍒楀悕鏄惁姝ｇ‘
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

print("=== Final Verification Report ===\n")

# 妫€鏌ュ叧閿枃浠?files_to_check = {
    'analysis/analyzer.py': [
        ('璁㈠崟寮€濮嬫棩鏈?, True),
        ('鍋忓樊閲戦', True),
        ('鏁伴噺 - 瀹為檯', False),  # 搴旇涓嶅瓨鍦?        ('鏁伴噺 - 瀹氶', False),  # 搴旇涓嶅瓨鍦?    ],
    'analysis/sheets/sheet1_summary.py': [
        ('鍋忓樊閲戦', True),
        ('鍋忓樊閲戦 (鍚◣)', False),  # 搴旇宸叉浛鎹?    ],
    'analysis/sheets/sheet2_alt.py': [
        ('鐗╂枡 A', True),
        ('鐗╂枡 B', True),
        ('鍋忓樊 A', True),
        ('鍋忓樊 B', True),
        ('鍋忓樊鐜?A', True),
        ('鍋忓樊鐜?B', True),
    ],
    'analysis/sheets/sheet3_no_note.py': [
        ('鍋忓樊閲戦', True),
        ('璁㈠崟寮€濮嬫棩鏈?, True),
    ],
    'analysis/sheets/sheet4_middle.py': [
        ('鍋忓樊鐜?(%)', False),  # 搴旇鏃犳嫭鍙?        ('鍋忓樊鐜?(%)', False),
        ('鍋忓樊鐜?(%)', False),
    ],
    'analysis/sheets/sheet5_full.py': [
        ('鍋忓樊閲戦', True),
        ('璁㈠崟寮€濮嬫棩鏈?, True),
    ],
    'analysis/sheets/sheet6_anomaly.py': [
        ('鏁伴噺 - 瀹氶', False),  # 搴旇鏃犵┖鏍?        ('鏁伴噺 - 瀹為檯', False),  # 搴旇鏃犵┖鏍?        ('鏁伴噺 - 瀹氶', False),
        ('鏁伴噺 - 瀹為檯', False),
    ],
    'analysis/sheets/sheet10_trend.py': [
        ('璁㈠崟寮€濮嬫棩鏈?, True),
    ],
}

all_good = True
for rel_path, checks in files_to_check.items():
    full_path = os.path.join(root, rel_path)
    if not os.path.exists(full_path):
        print(f"鈿?MISSING: {rel_path}")
        all_good = False
        continue
    
    content = open(full_path, 'r', encoding='utf-8').read()
    print(f"鉁?{rel_path}:")
    
    for check_str, should_exist in checks:
        exists = check_str in content
        status = "OK" if (exists == should_exist) else "ERROR"
        expected = "should exist" if should_exist else "should NOT exist"
        actual = "exists" if exists else "not found"
        print(f"    [{status}] '{check_str}' - {expected} ({actual})")
        if status == "ERROR":
            all_good = False

print(f"\n=== Conclusion ===")
if all_good:
    print("鉁?ALL CHECKS PASSED - Ready to run analysis")
else:
    print("鈿?Some issues detected - review the errors above")

print(f"\n=== Next Step ===")
print("Run: python main.py")
print("If KeyError occurs, the exact error message will guide further fixes")

