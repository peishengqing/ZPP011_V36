# -*- coding: utf-8 -*-
"""淇 analyzer.py 鎵€鏈夌‖缂栫爜鍒楀悕涓哄姩鎬佹煡鎵?""
import os
import re

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 鍒楀悕鏄犲皠閰嶇疆
COLUMN_MAP = {
    'order_no': ("['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', 'Order No', '鐢熶骇璁㈠崟']", '璁㈠崟鍙?),
    'material_code': ("['鐗╂枡缂栫爜', '缁勪欢鐗╂枡鍙?, '鐗╂枡鍙?, '缂栫爜', '缁勪欢鐗╂枡鍙风爜']", '鐗╂枡缂栫爜'),
    'material_name': ("['鐗╂枡鍚嶇О', '缁勪欢鐗╂枡鎻忚堪', '鎻忚堪', '鍚嶇О', '缁勪欢鎻忚堪']", '鐗╂枡鍚嶇О'),
    'factory': ("['宸ュ巶', '宸ュ巶鍚嶇О']", '宸ュ巶'),
    'workshop': ("['杞﹂棿', '鐢熶骇绠＄悊鍛樻弿杩?]", '杞﹂棿'),
    'order_date': ("['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟寮€濮嬫棩鏈?, '鏃ユ湡']", '璁㈠崟寮€濮嬫棩鏈?),
}

# 1. 纭繚 _get_column 鍑芥暟瀛樺湪
if 'def _get_column(' not in content:
    print('ERROR: _get_column not found')
    exit(1)

# 2. 鍦?do_analysis_v2 寮€澶存坊鍔犲垪鍚嶆槧灏?
old_start = '''    def report_progress(step_idx, step_name, percent):
        if progress_callback:
            progress_callback(step_idx, step_name, percent)

    from analysis.sheets.write_sheet_util import get_default_styles'''

new_start = '''    def report_progress(step_idx, step_name, percent):
        if progress_callback:
            progress_callback(step_idx, step_name, percent)

    # ========== 鍔ㄦ€佸垪鍚嶆槧灏?==========
    col_map = {
        'order_no': _get_column(df, ['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', 'Order No', '鐢熶骇璁㈠崟']),
        'material_code': _get_column(df, ['鐗╂枡缂栫爜', '缁勪欢鐗╂枡鍙?, '鐗╂枡鍙?, '缂栫爜', '缁勪欢鐗╂枡鍙风爜']),
        'material_name': _get_column(df, ['鐗╂枡鍚嶇О', '缁勪欢鐗╂枡鎻忚堪', '鎻忚堪', '鍚嶇О', '缁勪欢鎻忚堪']),
        'factory': _get_column(df, ['宸ュ巶', '宸ュ巶鍚嶇О']),
        'workshop': _get_column(df, ['杞﹂棿', '鐢熶骇绠＄悊鍛樻弿杩?]),
        'order_date': _get_column(df, ['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟寮€濮嬫棩鏈?, '鏃ユ湡']),
    }
    # 妫€鏌ュ繀瑕佸垪
    for key, col in col_map.items():
        if col is None:
            raise ValueError(f"Excel缂哄皯蹇呰鍒楋細{key}锛屽彲鐢ㄥ垪锛歿list(df.columns)}")

    from analysis.sheets.write_sheet_util import get_default_styles'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print('OK: Added column mapping')
else:
    print('SKIP: Column mapping pattern not found')

# 3. 鏇挎崲 df['璁㈠崟鍙?] 涓?df[col_map['order_no']]
# 鍏堝鐞嗙畝鍗曠殑鐩存帴鏇挎崲
replacements = [
    (r"df\['璁㈠崟鍙?\]", "df[col_map['order_no']]"),
    (r"r\['璁㈠崟鍙?\]", "r[col_map['order_no']]"),
    (r"row\['璁㈠崟鍙?\]", "row[col_map['order_no']]"),
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)
    
print('OK: Replaced order_no references')

# 4. 淇濆瓨
with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')

