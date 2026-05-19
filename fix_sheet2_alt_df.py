#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_sheet2_alt_df.py - 淇鏇夸唬鏂欐槑缁?sheet 涓虹┖鐨勯棶棰橈紙閫傞厤涓夊厓缁勬牸寮忥級"""
import re

filepath = 'analysis/analyzer.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 鈹€鈹€ 1. 鍦?cleaned_pairs 鏋勫缓鍚庢彃鍏ユ柊閫昏緫锛堝湪 "alt_df, alt_order_mat = build_sheet2" 涔嬪墠锛?鈹€鈹€
old = """    # 浣跨敤娓呯悊鍚庣殑閰嶅
    alt_df, alt_order_mat = build_sheet2(df, cleaned_pairs, report_progress)"""

new = """    # 浣跨敤娓呯悊鍚庣殑閰嶅
    # 鈹€鈹€ 鏂板锛氱洿鎺ユ牴鎹?alt_pairs 浠?df 绛涢€夋浛浠ｆ枡琛岋紙閫傞厤涓夊厓缁勬牸寮忥級 鈹€鈹€
    def _extract_item_key(item):
        \"\"\"浠庢浛浠ｆ枡閰嶅椤逛腑鎻愬彇缂栫爜鍜屽悕绉帮紝杩斿洖 (code, name)\"\"\"
        if isinstance(item, (list, tuple)):
            if len(item) >= 3:
                # 鏍囧噯涓夊厓缁?(宸ュ巶, 缂栫爜, 鍚嶇О)
                return (str(item[1]).strip(), str(item[2]).strip())
            elif len(item) == 2:
                return (str(item[0]).strip(), str(item[1]).strip())
            else:
                return (str(item[0]).strip(), '')
        else:
            s = str(item).strip()
            return (s, s)

    alt_names = set()   # 鍚嶇О闆嗗悎锛堜富鍖归厤锛?
    alt_codes = set()   # 缂栫爜闆嗗悎锛堥檷绾у尮閰嶏級
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

if old in content:
    content = content.replace(old, new, 1)
    print("OK: 鎻掑叆鏇夸唬鏂欐槑缁嗙瓫閫夐€昏緫")
else:
    print("SKIP: Pattern not found")

# 鈹€鈹€ 2. 淇 ws2 鍐欏叆鍒楀悕锛堥€傞厤 df 瀹為檯鍒楀悕锛?鈹€鈹€
old2 = """    headers2 = ['璁㈠崟寮€濮嬫棩鏈?, '杞﹂棿', '璁㈠崟鍙?, '鐗╂枡A', '鍗曚綅', '鍋忓樊A', '鍋忓樊鐜嘇',
                '鐗╂枡B', '鍋忓樊B', '鍋忓樊鐜嘊', '鍑€鍋忓樊', '澶囨敞']"""

new2 = """    # 鍔ㄦ€佹煡鎵惧垪鍚嶏紙鏇夸唬鏂欐槑缁?sheet锛?
    _s2_name_col = next((c for c in df.columns if any(k in str(c) for k in ['缁勪欢鐗╂枡鎻忚堪', '鐗╂枡鎻忚堪', '鐗╂枡鍚嶇О']), '鐗╂枡鍚嶇О')
    _s2_code_col = next((c for c in df.columns if any(k in str(c) for k in ['缁勪欢鐗╂枡鍙?, '鐗╂枡缂栫爜', '缂栫爜']), '鐗╂枡缂栫爜')
    _s2_order_col = next((c for c in df.columns if any(k in str(c) for k in ['璁㈠崟鍙?, '娴佺▼璁㈠崟']), '璁㈠崟鍙?)
    _s2_date_col = next((c for c in df.columns if '鏃ユ湡' in str(c)), '璁㈠崟寮€濮嬫棩鏈?)
    _s2_factory_col = next((c for c in df.columns if any(k in str(c) for k in ['杞﹂棿', '鐢熶骇绠＄悊鍛?]), '杞﹂棿')
    _s2_unit_col = next((c for c in df.columns if '鍗曚綅' in str(c)), '鍗曚綅')

    headers2 = ['璁㈠崟寮€濮嬫棩鏈?, '杞﹂棿', '璁㈠崟鍙?, '鐗╂枡A', '鍗曚綅', '鍋忓樊A', '鍋忓樊鐜嘇',
                '鐗╂枡B', '鍋忓樊B', '鍋忓樊鐜嘊', '鍑€鍋忓樊', '澶囨敞']"""

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("OK: 淇 headers2 鍒楀悕")
else:
    print("SKIP: headers2 pattern not found")

# 鍐欏叆
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")

