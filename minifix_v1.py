# -*- coding: utf-8 -*-
"""鏈€灏忎慨澶嶅寘 v1 - 鍩轰簬v36.40.2鍥炴粴鍚庣殑绮剧‘淇"""
import os

fp1 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp1, 'r', encoding='utf-8') as f:
    c1 = f.read()

# 1a: 鍦?_dprint 涔嬪墠娣诲姞 _get_column
old_dprint = 'def _dprint(*args, **kwargs):\n    """Safe debug print - avoids GBK Errno 22 on Windows console"""'
new_dprint = 'def _get_column(df, candidates, default=None):\n    """浠?DataFrame 涓煡鎵剧涓€涓瓨鍦ㄧ殑鍒楀悕"""\n    for col in candidates:\n        if col in df.columns:\n            return col\n    return default\n\n\ndef _dprint(*args, **kwargs):\n    """Safe debug print - avoids GBK Errno 22 on Windows console"""'
if old_dprint in c1:
    c1 = c1.replace(old_dprint, new_dprint)
    print('1a OK')
else:
    print('1a SKIP')

# 1b: 鍑芥暟寮€澶存坊鍔?import
old_func = 'def do_analysis_v2(\n        input_file,\n        output_dir,\n        alt_pairs,\n        progress_callback=None,\n        cancel_check=None,\n        start_date=None,\n        end_date=None,\n        material_search=None,\n        output_path=None):\n    _dprint("[DEBUG do_analysis_v2]'
new_func = 'def do_analysis_v2(\n        input_file,\n        output_dir,\n        alt_pairs,\n        progress_callback=None,\n        cancel_check=None,\n        start_date=None,\n        end_date=None,\n        material_search=None,\n        output_path=None):\n    import os\n    import re\n    import glob as _glob\n    _dprint("[DEBUG do_analysis_v2]'
if old_func in c1:
    c1 = c1.replace(old_func, new_func)
    print('1b OK')
else:
    print('1b SKIP')

# 1c: 鍒犻櫎閲嶅 import os
old_dup = '    # DEBUG: Log input DataFrame info\n    import os\n    _debug_log'
new_dup = '    # DEBUG: Log input DataFrame info\n    _debug_log'
if old_dup in c1:
    c1 = c1.replace(old_dup, new_dup)
    print('1c OK')
else:
    print('1c SKIP')

# 1d: df璇诲彇鍚庢坊鍔燾ol_map
old_df = "    df = pd.read_excel(src_file, sheet_name='Data')\n    _dprint(f\"[DEBUG do_analysis_v2] \u8bfb\u53d6Data\u8868\u6210\u529f\uff0c{len(df)} \u884c\", flush=True)\n    \n    # DEBUG"
new_df = "    df = pd.read_excel(src_file, sheet_name='Data')\n    _dprint(f\"[DEBUG do_analysis_v2] \u8bfb\u53d6Data\u8868\u6210\u529f\uff0c{len(df)} \u884c\", flush=True)\n    col_map = {\n        'order_no': _get_column(df, ['\u6d41\u7a0b\u8ba2\u5355', '\u8ba2\u5355\u53f7', '\u8ba2\u5355\u7f16\u53f7', 'Order No', '\u751f\u4ea7\u8ba2\u5355']),\n        'material_code': _get_column(df, ['\u7269\u6599\u7f16\u7801', '\u7ec4\u4ef6\u7269\u6599\u53f7', '\u7269\u6599\u53f7', '\u7f16\u7801']),\n        'material_name': _get_column(df, ['\u7269\u6599\u540d\u79f0', '\u7ec4\u4ef6\u7269\u6599\u63cf\u8ff0', '\u63cf\u8ff0', '\u540d\u79f0']),\n        'factory': _get_column(df, ['\u5de5\u5382', '\u5de5\u5382\u540d\u79f0']),\n        'workshop': _get_column(df, ['\u8f66\u95f4', '\u751f\u4ea7\u7ba1\u7406\u5458\u63cf\u8ff0']),\n        'order_date': _get_column(df, ['\u8ba2\u5355\u5f00\u59cb\u65e5\u671f', '\u8ba2\u5355\u65e5\u671f', '\u65e5\u671f']),\n    }\n    _dprint(f\"[DEBUG] col_map: order_no={col_map['order_no']}\", flush=True)\n    \n    # DEBUG"
if old_df in c1:
    c1 = c1.replace(old_df, new_df)
    print('1d OK')
else:
    print('1d SKIP')

# 1e: 鏇挎崲 alt_order_mat
old_alt = "    alt_order_mat = set()\n    for _, r in alt_df.iterrows():\n        alt_order_mat.add((str(r['\u8ba2\u5355\u53f7']), str(r['\u7269\u6599A'])))\n        alt_order_mat.add((str(r['\u8ba2\u5355\u53f7']), str(r['\u7269\u6599B'])))"
new_alt = "    alt_order_col = _get_column(alt_df, ['\u6d41\u7a0b\u8ba2\u5355', '\u8ba2\u5355\u53f7', '\u8ba2\u5355\u7f16\u53f7', 'Order No', '\u751f\u4ea7\u8ba2\u5355'], '\u8ba2\u5355\u53f7')\n    alt_order_mat = set()\n    for _, r in alt_df.iterrows():\n        alt_order_mat.add((str(r[alt_order_col]), str(r.get('\u7269\u6599A', ''))))\n        alt_order_mat.add((str(r[alt_order_col]), str(r.get('\u7269\u6599B', ''))))"
if old_alt in c1:
    c1 = c1.replace(old_alt, new_alt)
    print('1e OK')
else:
    print('1e SKIP')

# 1f: 鏇夸唬鏂欐槑缁唖heet
old_s2 = "    rows2 = [[r['\u8ba2\u5355\u65e5\u671f'], r['\u8f66\u95f4'], r['\u8ba2\u5355\u53f7'], r['\u7269\u6599A'], r['\u5355\u4f4d'],"
new_s2 = "    rows2 = [[r['\u8ba2\u5355\u65e5\u671f'], r['\u8f66\u95f4'], r[alt_order_col], r['\u7269\u6599A'], r['\u5355\u4f4d'],"
if old_s2 in c1:
    c1 = c1.replace(old_s2, new_s2)
    print('1f OK')
else:
    print('1f SKIP')

with open(fp1, 'w', encoding='utf-8') as f:
    f.write(c1)

# sheet2_alt.py
fp2 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\sheets\sheet2_alt.py'
with open(fp2, 'r', encoding='utf-8') as f:
    c2 = f.read()
old_i2 = 'import pandas as pd'
new_i2 = "import pandas as pd\n\n\ndef _get_column(df, candidates, default=None):\n    for col in candidates:\n        if col in df.columns:\n            return col\n    return default"
if old_i2 in c2:
    c2 = c2.replace(old_i2, new_i2)
    print('2a OK')
old_a2 = "    alt_order_mat = set()\n    for _, r in alt_df.iterrows():\n        alt_order_mat.add((str(r['\u8ba2\u5355\u53f7']), str(r['\u7269\u6599A'])))\n        alt_order_mat.add((str(r['\u8ba2\u5355\u53f7']), str(r['\u7269\u6599B'])))"
new_a2 = "    order_col = _get_column(alt_df, ['\u6d41\u7a0b\u8ba2\u5355', '\u8ba2\u5355\u53f7', '\u8ba2\u5355\u7f16\u53f7', 'Order No', '\u751f\u4ea7\u8ba2\u5355'], '\u8ba2\u5355\u53f7')\n    alt_order_mat = set()\n    for _, r in alt_df.iterrows():\n        alt_order_mat.add((str(r[order_col]), str(r.get('\u7269\u6599A', ''))))\n        alt_order_mat.add((str(r[order_col]), str(r.get('\u7269\u6599B', ''))))"
if old_a2 in c2:
    c2 = c2.replace(old_a2, new_a2)
    print('2b OK')
with open(fp2, 'w', encoding='utf-8') as f:
    f.write(c2)

# sheet4_middle.py
fp3 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\sheets\sheet4_middle.py'
with open(fp3, 'r', encoding='utf-8') as f:
    c3 = f.read()
old_i3 = 'import pandas as pd\nimport re'
new_i3 = "import pandas as pd\nimport re\n\n\ndef _get_column(df, candidates, default=None):\n    for col in candidates:\n        if col in df.columns:\n            return col\n    return default"
if old_i3 in c3:
    c3 = c3.replace(old_i3, new_i3)
    print('3a OK')
old_a3 = "alt_orders = alt_df['\u8ba2\u5355\u53f7'].unique() if len(alt_df) > 0 else []"
new_a3 = "alt_orders = alt_df[_get_column(alt_df, ['\u6d41\u7a0b\u8ba2\u5355', '\u8ba2\u5355\u53f7', '\u8ba2\u5355\u7f16\u53f7', 'Order No', '\u751f\u4ea7\u8ba2\u5355'], '\u8ba2\u5355\u53f7')].unique() if len(alt_df) > 0 else []"
if old_a3 in c3:
    c3 = c3.replace(old_a3, new_a3)
    print('3b OK')
with open(fp3, 'w', encoding='utf-8') as f:
    f.write(c3)

# events.py - 鍒楀悕娓呯悊
fp4 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(fp4, 'r', encoding='utf-8') as f:
    c4 = f.read()
old_l = "        dev_df = pd.read_excel(latest_file, sheet_name='\u5b8c\u6574\u504f\u5dee\u660e\u7ec6')\n        if dev_df.empty:\n            raise ValueError('\u504f\u5dee\u660e\u7ec6\u5de5\u4f5c\u8868\u4e3a\u7a7a')"
new_l = "        dev_df = pd.read_excel(latest_file, sheet_name='\u5b8c\u6574\u504f\u5dee\u660e\u7ec6')\n        if dev_df.empty:\n            raise ValueError('\u504f\u5dee\u660e\u7ec6\u5de5\u4f5c\u8868\u4e3a\u7a7a')\n        dev_df.columns = [str(col).strip().replace(' ', '') for col in dev_df.columns]"
if old_l in c4:
    c4 = c4.replace(old_l, new_l)
    print('4 OK')
with open(fp4, 'w', encoding='utf-8') as f:
    f.write(c4)

print('Done!')
