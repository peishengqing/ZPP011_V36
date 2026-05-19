#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缁堟瀬鍒楀悕淇锛氱粺涓€鎵€鏈夊甫绌烘牸鍒楀悕涓烘棤绌烘牸鐗堟湰
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 瀹屾暣鏇挎崲瑙勫垯锛堣鐩栦箣鍓嶆墍鏈変慨澶嶏級
replacements = [
    # Sheet2 鏇夸唬鏂欑浉鍏?
    ("'鐗╂枡 A'", "'鐗╂枡 A'"),
    ("'鐗╂枡 B'", "'鐗╂枡 B'"),
    ("'鍋忓樊 A'", "'鍋忓樊 A'"),
    ("'鍋忓樊 B'", "'鍋忓樊 B'"),
    ("'鍋忓樊鐜?A'", "'鍋忓樊鐜?A'"),
    ("'鍋忓樊鐜?B'", "'鍋忓樊鐜?B'"),
    
    # 閲戦鐩稿叧
    ("'閲戦 - 瀹為檯 (鍚◣)'", "'閲戦 - 瀹為檯 (鍚◣)'"),
    ("'閲戦 - 瀹氶 (鍚◣)'", "'閲戦 - 瀹氶 (鍚◣)'"),
    ("'鍋忓樊閲戦'", "'鍋忓樊閲戦'"),
    
    # 鍏朵粬鍙兘鐨勯棶棰?
    ("'璁㈠崟寮€濮嬫棩鏈?", "'璁㈠崟寮€濮嬫棩鏈?"),
    ("'璁㈠崟寮€濮嬫棩鏈?", "'璁㈠崟寮€濮嬫棩鏈?"),
]

count = 0
modified_files = []

for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py'):
            # 璺宠繃杈呭姪鑴氭湰鍜屾湰鏂囨。
            skip_files = ['fix_all_amount.py', 'fix_column_names.py', 'fix_deviation_amount.py', 
                         'update_analyzer.py', 'check_deviation.py', 'check_sheets.py', 
                         'check_analyzer_amount.py', 'ultimate_fix.py', 'verify_fix.py',
                         'fix_order_date.py', 'fix_all_columns.py', 'fix_col_map_final.py',
                         'fix_order_col.py', 'fix_sheet2_alt_df.py']
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

# 鐗瑰埆澶勭悊 sheet2_alt.py 涓殑 DataFrame 鍒楀悕瀹氫箟
print("\n=== Special Fix for sheet2_alt.py ===")
sheet2_path = os.path.join(root, 'analysis', 'sheets', 'sheet2_alt.py')
if os.path.exists(sheet2_path):
    with open(sheet2_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 淇缁撴灉 DataFrame 鐨勫垪鍚嶅畾涔夛紙纭繚浣跨敤鏃犵┖鏍肩増鏈級
    if "'鐗╂枡 A'" in content or "'鐗╂枡 B'" in content:
        # 妫€鏌ユ槸鍚﹀凡缁忎娇鐢ㄦ纭殑鍒楀悕
        if "alt_rows.append({" in content:
            # 鏌ョ湅 append 閮ㄥ垎
            import re
            append_match = re.search(r"alt_rows\.append\(\{([^}]+)\}", content, re.DOTALL)
            if append_match:
                append_content = append_match.group(1)
                if "'鐗╂枡 A'" in append_content or "'鐗╂枡 B'" in append_content:
                    print("Note: sheet2_alt.py alt_rows uses '鐗╂枡 A' and '鐗╂枡 B' columns")
    
    open(sheet2_path, 'w', encoding='utf-8').write(content)
    print("Verified: sheet2_alt.py structure")

print(f"\n=== Summary ===")
print(f"Files modified: {count}")
print(f"Replacement rules applied: {len(replacements)}")

print(f"\n=== Next Steps ===")
print("1. Run: python main.py")
print("2. If any KeyError remains, provide the exact error message")
print("3. The script has unified all column names to no-space version")

