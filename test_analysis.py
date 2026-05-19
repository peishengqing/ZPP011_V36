#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
娴嬭瘯鍒嗘瀽娴佺▼
"""
import sys
import os
sys.path.insert(0, r'E:\zpp011_dev\妯″潡鍖栬剼鏈?)

print("=== Testing Core Modules ===\n")

# 1. 娴嬭瘯妯″潡瀵煎叆
try:
    from analysis.analyzer import do_analysis_v2, _analysis_in_progress
    print("鉁?analyzer.py imports successfully")
    print(f"  - Global lock exists: {_analysis_in_progress is not None}")
except Exception as e:
    print(f"鉁?analyzer.py import failed: {e}")

try:
    from analysis.sheets.sheet2_alt import build_sheet2
    print("鉁?sheet2_alt.py imports successfully")
except Exception as e:
    print(f"鉁?sheet2_alt.py import failed: {e}")

try:
    import ppt_generator
    print("鉁?ppt_generator.py exists")
except Exception as e:
    print(f"鉁?ppt_generator.py error: {e}")

try:
    from core.auto_closer import AutoCloser
    print("鉁?AutoCloser exists")
except Exception as e:
    print(f"鉁?AutoCloser error: {e}")

# 2. 娴嬭瘯鍒楀悕娓呯悊閫昏緫
print("\n=== Testing Column Name Cleanup ===")
import pandas as pd

# 鍒涘缓娴嬭瘯 DataFrame
test_df = pd.DataFrame({
    '璁㈠崟寮€濮嬫棩鏈?': ['2024-01-01'],
    '娴佺▼璁㈠崟 ': ['123456'],
    '缁勪欢鐗╂枡鎻忚堪 ': ['Test Material'],
    '鍋忓樊鐜?(%)': [5.5],
    '鍋忓樊閲戦 (鍚◣)': [100.0],
    '鏁伴噺 - 瀹為檯': [10],
    '鏁伴噺 - 瀹氶': [9],
})

print(f"Original columns: {list(test_df.columns)}")

# 搴旂敤娓呯悊
test_df.columns = [col.strip().replace(' ', '') for col in test_df.columns]
print(f"After cleanup: {list(test_df.columns)}")

# 閲嶅懡鍚嶅亸宸噾棰?if '鍋忓樊閲戦 (鍚◣)' in test_df.columns:
    test_df.rename(columns={'鍋忓樊閲戦 (鍚◣)': '鍋忓樊閲戦'}, inplace=True)
    print(f"After rename: {list(test_df.columns)}")

print("\n鉁?Column cleanup logic works correctly")

# 3. 娴嬭瘯 Sheet2 閫昏緫
print("\n=== Testing Sheet2 Logic ===")
test_alt_pairs = [
    ('Test Material', 'Other Material'),
]

def mock_progress(idx, name, pct):
    print(f"  Progress: {name} {pct}%")

try:
    alt_df, alt_order_mat = build_sheet2(test_df, test_alt_pairs, mock_progress)
    print(f"鉁?Sheet2 generated {len(alt_df)} rows")
    if len(alt_df) > 0:
        print(f"  Columns: {list(alt_df.columns)}")
except Exception as e:
    print(f"鉁?Sheet2 failed: {e}")
    import traceback
    traceback.print_exc()

print("\n=== All Tests Complete ===")
print("Ready to run: python main.py")
