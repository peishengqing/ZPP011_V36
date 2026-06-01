#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：为什么表格是空的"""
import sys, os, io, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

os.chdir(r'E:\zpp011_dev\模块化脚本')

print("=== 诊断开始 ===")

# 1. 检查 _refresh_audit_tree 中 insert 的值数量 vs 列数量
print("\n[1] 检查 Treeview 列定义...")
try:
    with open('gui/event_handlers/table_events.py', 'r', encoding='utf-8') as f:
        src = f.read()
    
    # 找 audit_tree['columns'] 或 configure(columns=...)
    import re
    col_matches = list(re.finditer(r'audit_tree.*?\[.columns.\]\s*=\s*[\[\(]', src))
    col_matches2 = list(re.finditer(r'audit_tree.*?configure\(\s*columns\s*=\s*[\[\(]', src))
    
    for m in col_matches + col_matches2:
        start = m.end()
        # extract list
        paren_count = 0
        vals = []
        for i, ch in enumerate(src[start:], start):
            if ch in '[(':
                paren_count += 1
            elif ch in '])':
                if paren_count == 0:
                    end = i
                    break
                paren_count -= 1
            vals.append(ch)
        print(f"  列定义: {''.join(vals[:200])}...")
    
    # 找 insert 调用，数 values 参数里有几个元素
    idx = src.find('def _refresh_audit_tree')
    chunk = src[idx:idx+15000]
    insert_idx = chunk.find('audit_tree.insert(')
    if insert_idx >= 0:
        # extract values=(...) 
        vi = chunk.find('values=', insert_idx)
        if vi >= 0:
            # count open/close parens
            paren = 0
            i = vi + 8  # skip 'values='
            if chunk[i] == '(':
                paren = 1
                i += 1
            vals_lines = []
            while i < len(chunk) and paren > 0:
                ch = chunk[i]
                if ch == '(': paren += 1
                elif ch == ')': paren -= 1
                vals_lines.append(chunk[i])
                i += 1
            val_str = ''.join(vals_lines)
            # count commas at top level
            paren = 0
            commas = 0
            for ch in val_str:
                if ch == '(': paren += 1
                elif ch == ')': paren -= 1
                elif ch == ',' and paren == 0:
                    commas += 1
            print(f"  insert values 元素数（逗号+1）: {commas + 1}")
            print(f"  values 片段: {val_str[:300]}")
    
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# 2. 检查 _load_data_worker 返回的 df 列是否包含 _refresh_audit_tree 需要的所有列
print("\n[2] 检查数据列完整性...")
try:
    import pandas as pd
    f = r'C:\Users\Administrator\Desktop\ZPP011偏差分析_20260501-0527.xlsx'
    dev_df = pd.read_excel(f, sheet_name='完整偏差明细')
    print(f"  数据: {len(dev_df)} 行")
    print(f"  列: {list(dev_df.columns)}")
    
    # 模拟 _load_data_worker 处理后的 audit_df 列
    audit_df = dev_df.copy()
    
    # 检查 _refresh_audit_tree 需要哪些列
    needed = ['订单日期', '流程订单', '工厂', '车间', '物料编码', '物料名称', '单位', '定额', '实际', '偏差率', '偏差金额', '备注', '备注来源', '是否替代料']
    missing = [c for c in needed if c not in audit_df.columns]
    print(f"  缺失列: {missing}")
    
    # 模拟 _on_load_done 里的 material_category 计算
    mat_cat_map = {"100":"原辅料","200":"包材","400":"食品辅料/食品半成品","410":"饮料辅料/饮料半成品","500":"食品成品","510":"饮料成品","600":"促销品"}
    if '物料编码' in audit_df.columns:
        audit_df['material_category'] = audit_df['物料编码'].apply(
            lambda x: mat_cat_map.get(str(x)[:3], '') if pd.notna(x) else ''
        )
        print(f"  material_category 示例: {audit_df['material_category'].value_counts().head()}")
    
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# 3. 检查 _on_filter_changed -> FilterEngine 是否返回空
print("\n[3] 检查 FilterEngine...")
try:
    from modules.audit.filters.filter_engine import FilterEngine
    import pandas as pd
    
    f = r'C:\Users\Administrator\Desktop\ZPP011偏差分析_20260501-0527.xlsx'
    dev_df = pd.read_excel(f, sheet_name='完整偏差明细')
    audit_df = dev_df.copy()
    audit_df['material_category'] = '原辅料'  # stub
    
    engine = FilterEngine()
    result = engine.apply({}, audit_df)
    print(f"  FilterEngine apply空筛选: 输入={len(audit_df)}, 输出={len(result)}")
    if len(result) == 0:
        print("  !!! FilterEngine 返回空 DataFrame !!!")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

print("\n=== 诊断完成 ===")
input("按回车退出...")
