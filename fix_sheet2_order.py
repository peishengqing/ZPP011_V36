# -*- coding: utf-8 -*-
"""淇 sheet2_alt.py 鍔ㄦ€佸垪鍚嶆煡鎵捐鍗曞彿"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\sheets\sheet2_alt.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 璁㈠崟鍙峰垪鍊欓€?ORDER_COL_CANDIDATES = "['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', 'Order No', '鐢熶骇璁㈠崟']"

# 淇1: 娣诲姞鍔ㄦ€佸垪鍚嶆煡鎵惧嚱鏁?old_import = 'import pandas as pd'

new_import = '''import pandas as pd


def _get_order_col(df):
    """鍔ㄦ€佹煡鎵捐鍗曞彿鍒?""
    candidates = ['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', 'Order No', '鐢熶骇璁㈠崟']
    for col in candidates:
        if col in df.columns:
            return col
    # 濡傛灉閮芥壘涓嶅埌锛岃繑鍥?'璁㈠崟鍙? 浣滀负榛樿鍊硷紙鏃ф牸寮忓吋瀹癸級
    return '璁㈠崟鍙?
'''

if old_import in content:
    content = content.replace(old_import, new_import)
    print('OK: Added _get_order_col function')
else:
    print('SKIP: Import pattern not found')

# 淇2: alt_order_mat 鏋勫缓鏃朵娇鐢ㄥ姩鎬佸垪鍚?old_alt_mat = '''    # 鏋勫缓鏇夸唬鏂欒鍗?鐗╂枡闆嗗悎锛堢敤浜庡悗缁爣璁帮級
    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r['璁㈠崟鍙?]), str(r['鐗╂枡A'])))
        alt_order_mat.add((str(r['璁㈠崟鍙?]), str(r['鐗╂枡B'])))'''

new_alt_mat = '''    # 鏋勫缓鏇夸唬鏂欒鍗?鐗╂枡闆嗗悎锛堢敤浜庡悗缁爣璁帮級
    order_col = _get_order_col(alt_df)
    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r[order_col]), str(r.get('鐗╂枡A', ''))))
        alt_order_mat.add((str(r[order_col]), str(r.get('鐗╂枡B', ''))))'''

if old_alt_mat in content:
    content = content.replace(old_alt_mat, new_alt_mat)
    print('OK: Fixed alt_order_mat with dynamic column')
else:
    print('SKIP: alt_order_mat pattern not found')

# 淇3: 杩斿洖鍊兼枃妗ｆ洿鏂?old_doc = '            alt_order_mat_set: set of (璁㈠崟鍙? 鐗╂枡鎻忚堪) 鐢ㄤ簬鏍囪鏇夸唬鏂?
new_doc = '            alt_order_mat_set: set of (璁㈠崟鍙?娴佺▼璁㈠崟, 鐗╂枡鎻忚堪) 鐢ㄤ簬鏍囪鏇夸唬鏂?

if old_doc in content:
    content = content.replace(old_doc, new_doc)
    print('OK: Updated docstring')
else:
    print('SKIP: Docstring pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')

