#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
淇鏁版嵁鍔犺浇闃舵鐨勫垪鍚嶉棶棰?"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 淇 gui/events.py
events_path = os.path.join(root, 'gui', 'events.py')
with open(events_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇绗?129 琛岋細鏀寔澶氱鍒楀悕
old_line129 = "date_col = headers.get('璁㈠崟寮€濮嬫棩鏈?) or headers.get('璁㈠崟寮€濮嬫棩鏈?)"
new_line129 = "date_col = headers.get('璁㈠崟寮€濮嬫棩鏈?) or headers.get('璁㈠崟寮€濮嬫棩鏈?) or headers.get('璁㈠崟鏃ユ湡') or headers.get('鏃ユ湡')"

if old_line129 in content:
    content = content.replace(old_line129, new_line129)
    print("FIXED: events.py line 129 - added fallback column names")

# 淇绗?209 琛?old_line209 = "if '璁㈠崟寮€濮嬫棩鏈? not in save_df.columns:"
new_line209 = "if not any(col in save_df.columns for col in ['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟鏃ユ湡', '鏃ユ湡']):"

if old_line209 in content:
    content = content.replace(old_line209, new_line209)
    print("FIXED: events.py line 209 - added flexible date column check")

with open(events_path, 'w', encoding='utf-8') as f:
    f.write(content)

# 淇 gui/app.py
app_path = os.path.join(root, 'gui', 'app.py')
with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇绗?511 琛岋細鏀寔澶氱鏃ユ湡鍒楀悕
old_line511 = "for c in ['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟寮€濮嬫棩鏈?, '鏃ユ湡', '宸ュ崟鏃ユ湡']:"
new_line511 = "for c in ['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟鏃ユ湡', '鏃ユ湡', '宸ュ崟鏃ユ湡']:"

if old_line511 in content:
    content = content.replace(old_line511, new_line511)
    print("FIXED: app.py line 511 - added '璁㈠崟鏃ユ湡' to date columns list")

# 淇绗?586 琛岋細鏀寔鍋忓樊閲戦鐨勪袱绉嶅垪鍚?old_line586 = "required_cols = ['璁㈠崟寮€濮嬫棩鏈?, '宸ュ巶', '杞﹂棿', '鐗╂枡缂栫爜', '鐗╂枡鍚嶇О', '鍋忓樊鐜?, '鍋忓樊閲戦 (鍚◣)', '澶囨敞']"
new_line586 = "required_cols = ['璁㈠崟寮€濮嬫棩鏈?, '宸ュ巶', '杞﹂棿', '鐗╂枡缂栫爜', '鐗╂枡鍚嶇О', '鍋忓樊鐜?, '鍋忓樊閲戦', '澶囨敞']"

if old_line586 in content:
    content = content.replace(old_line586, new_line586)
    print("FIXED: app.py line 586 - use '鍋忓樊閲戦' instead of '鍋忓樊閲戦 (鍚◣)'")

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n=== Fixes Applied ===")
print("1. events.py: Flexible date column detection")
print("2. app.py: Support multiple date column names")
print("\nReady to test: python main.py")
