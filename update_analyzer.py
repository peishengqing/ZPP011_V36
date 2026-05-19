#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
content = open(path, 'r', encoding='utf-8').read()

# 鏌ユ壘骞舵浛鎹㈠垪鍚嶆竻鐞嗛儴鍒?if '缁堟瀬鍒楀悕娓呯悊' not in content:
    old = '''df = pd.read_excel(src_file, sheet_name='Data')
    _dprint(f"[DEBUG do_analysis_v2] 璇诲彇 Data 琛ㄦ垚鍔燂紝{len(df)} 琛?, flush=True)

    # ========== 缁熶竴鍒楀悕锛氬幓闄ゆ墍鏈夌┖鏍?=========='''
    
    new = '''df = pd.read_excel(src_file, sheet_name='Data')
    _dprint(f"[DEBUG do_analysis_v2] 璇诲彇 Data 琛ㄦ垚鍔燂紝{len(df)} 琛?, flush=True)

    # ========== 缁堟瀬鍒楀悕娓呯悊锛氱Щ闄ゆ墍鏈夌┖鏍?==========
    df.columns = [col.strip().replace(' ', '') for col in df.columns]
    _dprint("[DEBUG] 宸叉竻闄ゆ墍鏈夊垪鍚嶄腑鐨勭┖鏍?)
    _dprint(f"[DEBUG] 娓呯悊鍚庡垪鍚嶇ず渚嬶細{list(df.columns)[:10]}")

    # ========== 缁熶竴鍋忓樊閲戦鍒楀悕 ==========
    if '鍋忓樊閲戦 (鍚◣)' in df.columns:
        df.rename(columns={'鍋忓樊閲戦 (鍚◣)': '鍋忓樊閲戦'}, inplace=True)
        _dprint("[DEBUG] 宸插皢 '鍋忓樊閲戦 (鍚◣)' 閲嶅懡鍚嶄负 '鍋忓樊閲戦'")'''
    
    if old in content:
        content = content.replace(old, new)
        open(path, 'w', encoding='utf-8').write(content)
        print('SUCCESS: Updated analyzer.py')
    else:
        print('NOT FOUND: Old code pattern')
        # 灏濊瘯鍙︿竴绉嶆柟寮?- 鐩存帴鍒犻櫎 col_rename 閮ㄥ垎
        if 'col_rename' in content:
            start = content.find('# ========== 缁熶竴鍒楀悕锛氬幓闄ゆ墍鏈夌┖鏍?==========')
            end = content.find('_dprint("[DEBUG] 宸查噸鍛藉悕甯︾┖鏍肩殑鍒楀悕"') + len('_dprint("[DEBUG] 宸查噸鍛藉悕甯︾┖鏍肩殑鍒楀悕", flush=True)')
            if start > 0 and end > start:
                replacement = '''# ========== 缁堟瀬鍒楀悕娓呯悊锛氱Щ闄ゆ墍鏈夌┖鏍?==========
    df.columns = [col.strip().replace(' ', '') for col in df.columns]
    _dprint("[DEBUG] 宸叉竻闄ゆ墍鏈夊垪鍚嶄腑鐨勭┖鏍?)
    _dprint(f"[DEBUG] 娓呯悊鍚庡垪鍚嶇ず渚嬶細{list(df.columns)[:10]}")

    # ========== 缁熶竴鍋忓樊閲戦鍒楀悕 ==========
    if '鍋忓樊閲戦 (鍚◣)' in df.columns:
        df.rename(columns={'鍋忓樊閲戦 (鍚◣)': '鍋忓樊閲戦'}, inplace=True)
        _dprint("[DEBUG] 宸插皢 '鍋忓樊閲戦 (鍚◣)' 閲嶅懡鍚嶄负 '鍋忓樊閲戦'")'''
                content = content[:start] + replacement + content[end+1:]
                open(path, 'w', encoding='utf-8').write(content)
                print('SUCCESS: Updated analyzer.py (alternative method)')
else:
    print('ALREADY UPDATED: analyzer.py has 缁堟瀬鍒楀悕娓呯悊')

# 楠岃瘉
content = open(path, 'r', encoding='utf-8').read()
if '缁堟瀬鍒楀悕娓呯悊' in content and '鍋忓樊閲戦' in content:
    print('VERIFIED: analyzer.py is correctly updated')
else:
    print('WARNING: Verification failed')

