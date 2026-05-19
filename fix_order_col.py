# -*- coding: utf-8 -*-
"""淇 analyzer.py 鍔ㄦ€佸垪鍚嶆煡鎵捐鍗曞彿"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 鍦ㄦ枃浠堕《閮ㄦ坊鍔犺緟鍔╁嚱鏁?
# 鎵惧埌绗竴涓嚱鏁板畾涔夌殑浣嶇疆
import_pattern = '''import pandas as pd
import re'''

new_import = '''import pandas as pd
import re


def _get_column(df, candidates, default=None):
    """浠?DataFrame 涓煡鎵剧涓€涓瓨鍦ㄧ殑鍒楀悕
    
    Args:
        df: pandas DataFrame
        candidates: 鍒楀悕鍊欓€夊垪琛紝鎸変紭鍏堢骇鎺掑簭
        default: 鏈壘鍒版椂鐨勯粯璁ゅ€?
    
    Returns:
        鎵惧埌鐨勫垪鍚嶆垨榛樿鍊?
    """
    for col in candidates:
        if col in df.columns:
            return col
    return default


def _require_column(df, candidates, sheet_name=""):
    """浠?DataFrame 涓煡鎵惧垪鍚嶏紝鏈壘鍒板垯鎶涘嚭鏄庣‘閿欒
    
    Args:
        df: pandas DataFrame
        candidates: 鍒楀悕鍊欓€夊垪琛?
        sheet_name: 褰撳墠澶勭悊鐨剆heet鍚嶇О锛堢敤浜庨敊璇彁绀猴級
    
    Returns:
        鎵惧埌鐨勫垪鍚?
    
    Raises:
        KeyError: 鏈壘鍒颁换浣曞€欓€夊垪鍚?
    """
    for col in candidates:
        if col in df.columns:
            return col
    raise KeyError(
        f"Excel涓己灏戝繀瑕佸垪锛丼heet[{sheet_name}]闇€瑕佷互涓嬪垪涔嬩竴锛歿candidates}銆?
        f"褰撳墠鍙敤鍒楋細{list(df.columns)}"
    )


ORDER_COL_CANDIDATES = ['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', 'Order No', '鐢熶骇璁㈠崟']'''

if import_pattern in content:
    content = content.replace(import_pattern, new_import)
    print('OK: Added _get_column and ORDER_COL_CANDIDATES')
else:
    print('SKIP: Import pattern not found, trying alternative...')
    # 灏濊瘯鍏朵粬鏂瑰紡娣诲姞

# 淇2: alt_order_mat 鏋勫缓鏃朵娇鐢ㄥ姩鎬佸垪鍚?
old_alt_mat = '''    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r['璁㈠崟鍙?]), str(r['鐗╂枡A'])))
        alt_order_mat.add((str(r['璁㈠崟鍙?]), str(r['鐗╂枡B'])))'''

new_alt_mat = '''    # 鍔ㄦ€佹煡鎵捐鍗曞彿鍒?
    alt_order_col = _get_column(alt_df, ORDER_COL_CANDIDATES, '璁㈠崟鍙?)
    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r[alt_order_col]), str(r.get('鐗╂枡A', ''))))
        alt_order_mat.add((str(r[alt_order_col]), str(r.get('鐗╂枡B', ''))))'''

if old_alt_mat in content:
    content = content.replace(old_alt_mat, new_alt_mat)
    print('OK: Fixed alt_order_mat with dynamic column')
else:
    print('SKIP: alt_order_mat pattern not found')

# 淇3: 鏇夸唬鏂欐槑缁?sheet 鐨勫姩鎬佸垪鍚?
old_alt_sheet = '''    ws2 = wb.create_sheet('鏇夸唬鏂欐槑缁?)
    headers2 = ['璁㈠崟寮€濮嬫棩鏈?, '杞﹂棿', '璁㈠崟鍙?, '鐗╂枡A', '鍗曚綅', '鍋忓樊A', '鍋忓樊鐜嘇',
                '鐗╂枡B', '鍋忓樊B', '鍋忓樊鐜嘊', '鍑€鍋忓樊', '澶囨敞']
    rows2 = [[r['璁㈠崟寮€濮嬫棩鏈?], r['杞﹂棿'], r['璁㈠崟鍙?], r['鐗╂枡A'], r['鍗曚綅'],
              r['鍋忓樊A'], r.get('鍋忓樊鐜嘇', ''), r['鐗╂枡B'], r['鍋忓樊B'],
              r.get('鍋忓樊鐜嘊', ''), r.get('鍑€鍋忓樊', ''), r['澶囨敞']]
             for r in alt_df.to_dict('records')]'''

new_alt_sheet = '''    ws2 = wb.create_sheet('鏇夸唬鏂欐槑缁?)
    headers2 = ['璁㈠崟寮€濮嬫棩鏈?, '杞﹂棿', '璁㈠崟鍙?, '鐗╂枡A', '鍗曚綅', '鍋忓樊A', '鍋忓樊鐜嘇',
                '鐗╂枡B', '鍋忓樊B', '鍋忓樊鐜嘊', '鍑€鍋忓樊', '澶囨敞']
    rows2 = [[r['璁㈠崟寮€濮嬫棩鏈?], r['杞﹂棿'], r[alt_order_col], r['鐗╂枡A'], r['鍗曚綅'],
              r['鍋忓樊A'], r.get('鍋忓樊鐜嘇', ''), r['鐗╂枡B'], r['鍋忓樊B'],
              r.get('鍋忓樊鐜嘊', ''), r.get('鍑€鍋忓樊', ''), r['澶囨敞']]
             for r in alt_df.to_dict('records')]'''

if old_alt_sheet in content:
    content = content.replace(old_alt_sheet, new_alt_sheet)
    print('OK: Fixed alt sheet with dynamic column')
else:
    print('SKIP: alt sheet pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')

