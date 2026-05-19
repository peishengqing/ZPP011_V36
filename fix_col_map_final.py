# -*- coding: utf-8 -*-
fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()
old = """    df = pd.read_excel(src_file, sheet_name='Data')
    _dprint(f"[DEBUG do_analysis_v2] 璇诲彇Data琛ㄦ垚鍔燂紝{len(df)} 琛?, flush=True)
    
    # DEBUG"""
new = """    df = pd.read_excel(src_file, sheet_name='Data')
    _dprint(f"[DEBUG do_analysis_v2] 璇诲彇Data琛ㄦ垚鍔燂紝{len(df)} 琛?, flush=True)
    col_map = {
        'order_no': _get_column(df, ['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', 'Order No', '鐢熶骇璁㈠崟']),
        'material_code': _get_column(df, ['鐗╂枡缂栫爜', '缁勪欢鐗╂枡鍙?, '鐗╂枡鍙?, '缂栫爜']),
        'material_name': _get_column(df, ['鐗╂枡鍚嶇О', '缁勪欢鐗╂枡鎻忚堪', '鎻忚堪', '鍚嶇О']),
        'factory': _get_column(df, ['宸ュ巶', '宸ュ巶鍚嶇О']),
        'workshop': _get_column(df, ['杞﹂棿', '鐢熶骇绠＄悊鍛樻弿杩?]),
        'order_date': _get_column(df, ['璁㈠崟寮€濮嬫棩鏈?, '鏃ユ湡']),
    }
    _dprint(f"[DEBUG] col_map: order_no={col_map['order_no']}", flush=True)
    # DEBUG"""
if old in content:
    content = content.replace(old, new)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK')
else:
    print('ERR')

