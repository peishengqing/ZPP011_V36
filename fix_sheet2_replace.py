#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_sheet2_replace.py - 褰诲簳绉婚櫎 build_sheet2 璋冪敤锛屾敼鐢ㄧ洿鎺ョ瓫閫?df 鐨勬柟寮?""
import re

filepath = 'analysis/analyzer.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 鈹€鈹€ 1. 绉婚櫎 build_sheet2 璋冪敤锛屾敼鐢ㄧ洿鎺ョ瓫閫夌殑 alt_df 鈹€鈹€
old = """    # 浣跨敤娓呯悊鍚庣殑閰嶅
    # 鈹€鈹€ 鏂板锛氱洿鎺ユ牴鎹?alt_pairs 浠?df 绛涢€夋浛浠ｆ枡琛岋紙閫傞厤涓夊厓缁勬牸寮忥級 鈹€鈹€
    def _extract_item_key(item):
        \"\"浠庢浛浠ｆ枡閰嶅椤逛腑鎻愬彇缂栫爜鍜屽悕绉帮紝杩斿洖 (code, name)\"\\"
        if isinstance(item, (list, tuple)):
            if len(item) >= 3:
                # 鏍囧噯涓夊厓缁?(宸ュ巶, 缂栫爜, 鍚嶇О)
                return (str(item[1])).strip(), str(item[2]).strip()
            elif len(item) == 2:
                return (str(item[0])).strip(), str(item[1]).strip()
            else:
                return (str(item[0])).strip(), ''
        else:
            s = str(item).strip()
            return (s, s)

    alt_names = set()   # 鍚嶇О闆嗗悎锛堜富鍖归厤锛?    alt_codes = set()   # 缂栫爜闆嗗悎锛堥檷绾у尮閰嶏級
    for a, b in cleaned_pairs:
        for item in (a, b):
            code, name = _extract_item_key(item)
            if name and name != 'None':
                alt_names.add(name)
            if code and code != 'None':
                alt_codes.add(code)

    # 鍔ㄦ€佹煡鎵?df 涓殑鍒楀悕
    _name_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['缁勪欢鎻忚堪', '鐗╂枡鎻忚堪', '鐗╂枡鍚嶇О', '鍚嶇О', 'name'])]
    _code_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['缁勪欢鐗╂枡鍙?, '缁勪欢缂栫爜', '鐗╂枡缂栫爜', '缂栫爜', 'code'])]

    alt_df = pd.DataFrame()
    if _name_cols or _code_cols:
        _name_col = _name_cols[0] if _name_cols else None
        _code_col = _code_cols[0] if _code_cols else None
        mask = pd.Series([False] * len(df))
        if _name_col:
            mask = mask | df[_name_col].astype(str).str.strip().isin(alt_names)
        if _code_col:
            mask = mask | df[_code_col].astype(str).str.strip().isin(alt_codes)
        alt_df = df[mask].copy()

    if alt_df.empty:
        print("[WARN] 鏇夸唬鏂欐槑缁嗕负绌猴紝璇锋鏌ユ浛浠ｆ枡閰嶇疆涓殑鐗╂枡鍚嶇О鎴栫紪鐮?)
    # 鈹€鈹€ 鏂板缁撴潫 鈹€鈹€

    alt_df, alt_order_mat = build_sheet2(df, cleaned_pairs, report_progress)"""

new = """    # 浣跨敤娓呯悊鍚庣殑閰嶅
    # 鈹€鈹€ 鏂板锛氱洿鎺ユ牴鎹?alt_pairs 浠?df 绛涢€夋浛浠ｆ枡琛岋紙閫傞厤涓夊厓缁勬牸寮忥級 鈹€鈹€
    def _extract_item_key(item):
        \"\"浠庢浛浠ｆ枡閰嶅椤逛腑鎻愬彇缂栫爜鍜屽悕绉帮紝杩斿洖 (code, name)\"\\"
        if isinstance(item, (list, tuple)):
            if len(item) >= 3:
                # 鏍囧噯涓夊厓缁?(宸ュ巶, 缂栫爜, 鍚嶇О)
                return str(item[1]).strip(), str(item[2]).strip()
            elif len(item) == 2:
                return str(item[0]).strip(), str(item[1]).strip()
            else:
                return str(item[0]).strip(), ''
        else:
            s = str(item).strip()
            return s, s

    alt_names = set()   # 鍚嶇О闆嗗悎锛堜富鍖归厤锛?    alt_codes = set()   # 缂栫爜闆嗗悎锛堥檷绾у尮閰嶏級
    for a, b in cleaned_pairs:
        for item in (a, b):
            code, name = _extract_item_key(item)
            if name and name != 'None':
                alt_names.add(name)
            if code and code != 'None':
                alt_codes.add(code)

    # 鍔ㄦ€佹煡鎵?df 涓殑鍒楀悕
    _name_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['缁勪欢鎻忚堪', '鐗╂枡鎻忚堪', '鐗╂枡鍚嶇О', '鍚嶇О', 'name'])]
    _code_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['缁勪欢鐗╂枡鍙?, '缁勪欢缂栫爜', '鐗╂枡缂栫爜', '缂栫爜', 'code'])]

    alt_df = pd.DataFrame()
    if _name_cols or _code_cols:
        _name_col = _name_cols[0] if _name_cols else None
        _code_col = _code_cols[0] if _code_cols else None
        mask = pd.Series([False] * len(df))
        if _name_col:
            mask = mask | df[_name_col].astype(str).str.strip().isin(alt_names)
        if _code_col:
            mask = mask | df[_code_col].astype(str).str.strip().isin(alt_codes)
        alt_df = df[mask].copy()

    if alt_df.empty:
        print("[WARN] 鏇夸唬鏂欐槑缁嗕负绌猴紝璇锋鏌ユ浛浠ｆ枡閰嶇疆涓殑鐗╂枡鍚嶇О鎴栫紪鐮?)
    # 鈹€鈹€ 鏂板缁撴潫 鈹€鈹€
    # 涓嶅啀璋冪敤 build_sheet2锛屼娇鐢ㄤ笂鏂圭洿鎺ョ瓫閫夌殑 alt_df
    # alt_df, alt_order_mat = build_sheet2(df, cleaned_pairs, report_progress)  # 宸茬Щ闄?""

if old in content:
    content = content.replace(old, new, 1)
    print("OK: 绉婚櫎 build_sheet2 璋冪敤锛屼娇鐢ㄧ洿鎺ョ瓫閫?)
else:
    print("SKIP: build_sheet2 璋冪敤鏈壘鍒帮紙鍙兘宸蹭慨澶嶏級")

# 鈹€鈹€ 2. 淇锛歛lt_order_mat 浠庢柊 alt_df 鏋勫缓锛堣€屼笉鏄粠 build_sheet2 鐨勮繑鍥炲€硷級鈹€鈹€
# 褰撳墠浠ｇ爜宸茬粡浠?alt_df.iterrows() 鏋勫缓 alt_order_mat锛屾棤闇€淇敼
# 鍙渶纭 alt_df 闈炵┖鏃?alt_order_mat 鑳芥纭瀯寤?
# 鍐欏叆
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")

