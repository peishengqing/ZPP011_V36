#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缁堟瀬淇鑴氭湰锛氳В鍐虫墍鏈夊垪鍚嶅拰閲嶅璋冪敤闂
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# ========== 1. 淇鍏ㄥ眬閿?==========
analyzer_path = os.path.join(root, 'analysis', 'analyzer.py')
content = open(analyzer_path, 'r', encoding='utf-8').read()

# 娣诲姞鍏ㄥ眬閿佸彉閲忥紙鍦ㄦ枃浠堕《閮ㄥ鍏ュ悗锛?
if '_analysis_in_progress = False' not in content:
    # 鍦?_dprint 鍑芥暟瀹氫箟鍓嶆坊鍔?
    old = '''def _dprint(*args, **kwargs):
    """Safe debug print - avoids GBK Errno 22 on Windows console"""
    try:
        print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        pass


def do_analysis_v2('''
    
    new = '''# 鍏ㄥ眬閿侊紝闃叉鍒嗘瀽鍑芥暟琚€掑綊璋冪敤
_analysis_in_progress = False


def _dprint(*args, **kwargs):
    """Safe debug print - avoids GBK Errno 22 on Windows console"""
    try:
        print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        pass


def do_analysis_v2('''
    
    if old in content:
        content = content.replace(old, new)
        open(analyzer_path, 'w', encoding='utf-8').write(content)
        print("OK: Added global lock variable")
    else:
        # 灏濊瘯鍦ㄥ嚱鏁板畾涔夊墠娣诲姞
        if 'def do_analysis_v2(' in content:
            idx = content.find('def do_analysis_v2(')
            content = content[:idx] + "\n# 鍏ㄥ眬閿侊紝闃叉鍒嗘瀽鍑芥暟琚€掑綊璋冪敤\n_analysis_in_progress = False\n\n" + content[idx:]
            open(analyzer_path, 'w', encoding='utf-8').write(content)
            print("OK: Added global lock at function start")
        else:
            print("SKIP: Could not find insertion point")

# ========== 2. 淇 do_analysis_v2 鍑芥暟娣诲姞閿佷繚鎶?==========
if 'if _analysis_in_progress:' not in content:
    old_func_start = '''def do_analysis_v2(
        input_file,
        output_dir,
        alt_pairs,
        progress_callback=None,
        cancel_check=None,
        start_date=None,
        end_date=None,
        material_search=None,
        output_path=None):
    _dprint("[DEBUG do_analysis_v2] 鍑芥暟寮€濮嬫墽琛?, flush=True)'''
    
    new_func_start = '''def do_analysis_v2(
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
    # 闃叉閲嶅杩涘叆锛堝鏋滃凡缁忔湁涓€涓垎鏋愬湪杩愯锛岀洿鎺ヨ繑鍥?None锛?
    if _analysis_in_progress:
        _dprint("[ERROR] 妫€娴嬪埌鍒嗘瀽浠诲姟宸插湪杩愯锛屾嫆缁濋噸澶嶈皟鐢?, flush=True)
        return None
    _analysis_in_progress = True
    _dprint("[DEBUG do_analysis_v2] 鍑芥暟寮€濮嬫墽琛?, flush=True)'''
    
    if old_func_start in content:
        content = content.replace(old_func_start, new_func_start)
        open(analyzer_path, 'w', encoding='utf-8').write(content)
        print("OK: Added lock protection at function start")
    else:
        print("SKIP: Function start pattern not found (may already be protected)")

# ========== 3. 淇鎵€鏈夊垪鍚嶏細缁熶竴浣跨敤鏃犵┖鏍肩増鏈?==========
# 鍏ㄥ眬鏇挎崲瑙勫垯
replacements = [
    ('鍋忓樊閲戦', '鍋忓樊閲戦'),
    ('鍋忓樊閲戦', '鍋忓樊閲戦'),
    ('閲戦 - 瀹為檯 (鍚◣)', '閲戦 - 瀹為檯 (鍚◣)'),  # 淇濇寔鍘熸牸寮?
    ('閲戦 - 瀹氶 (鍚◣)', '閲戦 - 瀹氶 (鍚◣)'),  # 淇濇寔鍘熸牸寮?
]

count = 0
for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py') and filename not in ['fix_all_amount.py', 'fix_column_names.py', 'fix_deviation_amount.py', 'update_analyzer.py', 'check_deviation.py', 'check_sheets.py', 'check_analyzer_amount.py']:
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

print(f"\n=== SUMMARY ===")
print(f"Global lock: ADDED")
print(f"Files fixed: {count}")
print(f"Columns unified: 鍋忓樊閲戦 -> 鍋忓樊閲戦")
print("\nREADY: Run python main.py to test")

