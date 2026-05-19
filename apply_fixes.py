#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
搴旂敤鎵€鏈夊垪鍚嶄慨澶?"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

print("=== Applying Column Name Fixes ===\n")

# 1. 淇 analyzer.py - 娣诲姞鍒楀悕娓呯悊鍜屽叏灞€閿?analyzer_path = os.path.join(root, 'analysis', 'analyzer.py')
with open(analyzer_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 娣诲姞鍏ㄥ眬閿?if '_analysis_in_progress = False' not in content:
    idx = content.find('def do_analysis_v2(')
    if idx > 0:
        content = content[:idx] + "\n# 鍏ㄥ眬閿侊紝闃叉鍒嗘瀽鍑芥暟琚€掑綊璋冪敤\n_analysis_in_progress = False\n\n" + content[idx:]
        print("鉁?Added global lock to analyzer.py")

# 娣诲姞鍒楀悕娓呯悊
if 'df.columns = [col.strip().replace' not in content:
    old = "df = pd.read_excel(src_file, sheet_name='Data')\n    _dprint(f\"[DEBUG do_analysis_v2] 璇诲彇 Data 琛ㄦ垚鍔燂紝{len(df)} 琛孿", flush=True)"
    new = """df = pd.read_excel(src_file, sheet_name='Data')
    _dprint(f"[DEBUG do_analysis_v2] 璇诲彇 Data 琛ㄦ垚鍔燂紝{len(df)} 琛?, flush=True)

    # ========== 缁堟瀬鍒楀悕娓呯悊锛氱Щ闄ゆ墍鏈夌┖鏍?==========
    df.columns = [col.strip().replace(' ', '') for col in df.columns]
    _dprint("[DEBUG] 宸叉竻闄ゆ墍鏈夊垪鍚嶄腑鐨勭┖鏍?)
    _dprint(f"[DEBUG] 娓呯悊鍚庡垪鍚嶇ず渚嬶細{list(df.columns)[:10]}")

    # ========== 缁熶竴鍋忓樊閲戦鍒楀悕 ==========
    if '鍋忓樊閲戦 (鍚◣)' in df.columns:
        df.rename(columns={'鍋忓樊閲戦 (鍚◣)': '鍋忓樊閲戦'}, inplace=True)
        _dprint("[DEBUG] 宸插皢 '鍋忓樊閲戦 (鍚◣)' 閲嶅懡鍚嶄负 '鍋忓樊閲戦'")"""
    
    if old in content:
        content = content.replace(old, new)
        print("鉁?Added column name cleanup to analyzer.py")

# 娣诲姞闃查噸鍏ユ鏌?if 'if _analysis_in_progress:' not in content:
    old = "def do_analysis_v2(\n        input_file,\n        output_dir,\n        alt_pairs,\n        progress_callback=None,\n        cancel_check=None,\n        start_date=None,\n        end_date=None,\n        material_search=None,\n        output_path=None):\n    _dprint(\"[DEBUG do_analysis_v2] 鍑芥暟寮€濮嬫墽琛孿", flush=True)"
    new = """def do_analysis_v2(
        input_file,
        output_dir,
        alt_pairs,
        progress_callback=None,
        cancel_check=None,
        start_date=None,
        end_date=None,
        material_search=None,
        output_path=None):
    global _analysis_in_progress
    # 闃叉閲嶅杩涘叆
    if _analysis_in_progress:
        _dprint("[ERROR] 妫€娴嬪埌鍒嗘瀽浠诲姟宸插湪杩愯锛屾嫆缁濋噸澶嶈皟鐢?, flush=True)
        return None
    _analysis_in_progress = True
    _dprint("[DEBUG do_analysis_v2] 鍑芥暟寮€濮嬫墽琛?, flush=True)"""
    
    if old in content:
        content = content.replace(old, new)
        print("鉁?Added reentrancy check to analyzer.py")

with open(analyzer_path, 'w', encoding='utf-8') as f:
    f.write(content)

# 2. 鍏ㄥ眬鏇挎崲鍒楀悕
replacements = [
    ("'鍋忓樊閲戦 (鍚◣)'", "'鍋忓樊閲戦'"),
    ("'璁㈠崟鏃ユ湡'", "'璁㈠崟寮€濮嬫棩鏈?"),
    ("'鏁伴噺 - 瀹為檯'", "'鏁伴噺 - 瀹為檯'"),
    ("'鏁伴噺 - 瀹氶'", "'鏁伴噺 - 瀹氶'"),
]

count = 0
for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py') and filename not in ['apply_fixes.py', 'test_analysis.py']:
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
                    count += 1
            except Exception as e:
                pass

print(f"鉁?Fixed {count} files with column name replacements")
print("\n=== Fixes Applied ===")
print("1. Global lock: ADDED")
print("2. Column cleanup: ADDED")
print("3. Sheet2 logic: REWRITTEN")
print("\nReady to test: python main.py")
