#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
淇 events.py 涓殑璁㈠崟鏃ユ湡鍒楅棶棰?"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 鎵惧埌闇€瑕佹浛鎹㈢殑浠ｇ爜娈?old_code = """        # 璁㈠崟鍒楁煡鎵?        order_col = None
        for possible in ['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', '璁㈠崟鍙风爜', '璁㈠崟 No', 'Order No', '鐢熶骇璁㈠崟']:
            if possible in audit_df.columns:
                order_col = possible
                break
            if possible in dev_df.columns:
                order_col = possible
                break
        if order_col is None:
            audit_df['娴佺▼璁㈠崟'] = ''
        elif order_col != '娴佺▼璁㈠崟':
            audit_df['娴佺▼璁㈠崟'] = audit_df[order_col]

        # 鐢熸垚鍞竴 ID
        audit_df['_uid'] = (
            audit_df['璁㈠崟寮€濮嬫棩鏈?].astype(str).str[:10] + '_' +
            audit_df['娴佺▼璁㈠崟'].astype(str) + '_' +
            audit_df['缁勪欢鐗╂枡鍙?].astype(str)
        )"""

new_code = """        # 璁㈠崟鍒楁煡鎵?        order_col = None
        for possible in ['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', '璁㈠崟鍙风爜', '璁㈠崟 No', 'Order No', '鐢熶骇璁㈠崟']:
            if possible in audit_df.columns:
                order_col = possible
                break
            if possible in dev_df.columns:
                order_col = possible
                break
        if order_col is None:
            audit_df['娴佺▼璁㈠崟'] = ''
        elif order_col != '娴佺▼璁㈠崟':
            audit_df['娴佺▼璁㈠崟'] = audit_df[order_col]

        # 鏃ユ湡鍒楁煡鎵撅紙淇锛氭敮鎸佸绉嶅垪鍚嶏級
        date_col = None
        for possible in ['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟鏃ユ湡', '鏃ユ湡']:
            if possible in audit_df.columns:
                date_col = possible
                break
            if possible in dev_df.columns:
                date_col = possible
                break
        
        if date_col is None:
            # 濡傛灉鎵句笉鍒版棩鏈熷垪锛屽垱寤虹┖鍒?            audit_df['璁㈠崟寮€濮嬫棩鏈?] = ''
            audit_df['璁㈠崟鏃ユ湡'] = ''
        else:
            # 缁熶竴鍒涘缓涓や釜鍒楀悕锛屾柟渚垮悗缁娇鐢?            audit_df['璁㈠崟寮€濮嬫棩鏈?] = pd.to_datetime(audit_df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
            audit_df['璁㈠崟鏃ユ湡'] = audit_df['璁㈠崟寮€濮嬫棩鏈?]

        # 鐢熸垚鍞竴 ID
        audit_df['_uid'] = (
            audit_df['璁㈠崟寮€濮嬫棩鏈?].astype(str).str[:10] + '_' +
            audit_df['娴佺▼璁㈠崟'].astype(str) + '_' +
            audit_df['缁勪欢鐗╂枡鍙?].astype(str)
        )"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Fixed events.py date column handling")
else:
    print("NOT FOUND: Could not find the target code block")
    # 灏濊瘯鏇村鏉剧殑鍖归厤
    if "order_col = None" in content and "audit_df['_uid']" in content:
        print("PARTIAL: Found related code, but exact match failed")
