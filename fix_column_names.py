#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

# 璁剧疆 UTF-8 杈撳嚭
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 淇敼 analyzer.py锛氭浛鎹㈠垪鍚嶆竻鐞嗛€昏緫
analyzer_path = os.path.join(root, 'analysis', 'analyzer.py')
with open(analyzer_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''    # ========== 缁熶竴鍒楀悕锛氬幓闄ゆ墍鏈夌┖鏍?==========
    col_rename = {
        '鍋忓樊鐜?(%)': '鍋忓樊鐜?(%)',
        '璁㈠崟寮€濮嬫棩鏈?': '璁㈠崟寮€濮嬫棩鏈?,
        '娴佺▼璁㈠崟 ': '娴佺▼璁㈠崟',
        '缁勪欢鐗╂枡鎻忚堪 ': '缁勪欢鐗╂枡鎻忚堪',
        '缁勪欢鐗╂枡鍙?': '缁勪欢鐗╂枡鍙?,
        '宸ュ巶鍚嶇О ': '宸ュ巶鍚嶇О',
        '杞﹂棿 ': '杞﹂棿',
        '澶囨敞鍘熷洜 ': '澶囨敞鍘熷洜',
        '鏉愭枡鍋忓樊 ': '鏉愭枡鍋忓樊',
        '鏁伴噺-瀹氶': '鏁伴噺-瀹氶',
        '鏁伴噺-瀹為檯': '鏁伴噺-瀹為檯',
        '缁勪欢鍗曚綅 ': '缁勪欢鍗曚綅',
        '鐗╂枡鍒嗙被 ': '鐗╂枡鍒嗙被',
        '鏍囧噯鍘熷洜 ': '鏍囧噯鍘熷洜',
        '鐢熶骇绠＄悊鍛樻弿杩?': '鐢熶骇绠＄悊鍛樻弿杩?,
        '宸ュ巶 ': '宸ュ巶',
    }
    df.rename(columns=col_rename, inplace=True)
    _dprint("[DEBUG] 宸查噸鍛藉悕甯︾┖鏍肩殑鍒楀悕", flush=True)'''

new_code = '''    # ========== 缁堟瀬鍒楀悕娓呯悊锛氱Щ闄ゆ墍鏈夌┖鏍?==========
    df.columns = [col.strip().replace(' ', '') for col in df.columns]
    _dprint("[DEBUG] 宸叉竻闄ゆ墍鏈夊垪鍚嶄腑鐨勭┖鏍?)
    _dprint(f"[DEBUG] 娓呯悊鍚庡垪鍚嶇ず渚嬶細{list(df.columns)[:10]}")'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(analyzer_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Updated analyzer.py")
else:
    print("SKIP: analyzer.py already updated or different")

# 鍏ㄥ眬鏇挎崲鎵€鏈?Python 鏂囦欢涓殑甯︾┖鏍煎垪鍚?
replacements = [
    ('鏁伴噺-瀹為檯', '鏁伴噺-瀹為檯'),
    ('鏁伴噺-瀹氶', '鏁伴噺-瀹氶'),
    ('閲戦-瀹為檯 (鍚◣)', '閲戦-瀹為檯 (鍚◣)'),
    ('閲戦-瀹氶 (鍚◣)', '閲戦-瀹氶 (鍚◣)'),
    ('鐗╂枡 A', '鐗╂枡 A'),
    ('鐗╂枡 B', '鐗╂枡 B'),
    ('鍋忓樊 A', '鍋忓樊 A'),
    ('鍋忓樊 B', '鍋忓樊 B'),
    ('鍋忓樊鐜?A', '鍋忓樊鐜?A'),
    ('鍋忓樊鐜?B', '鍋忓樊鐜?B'),
    ('鍋忓樊閲戦', '鍋忓樊閲戦'),
]

count = 0
for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath:
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

