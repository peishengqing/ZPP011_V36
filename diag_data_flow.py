#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：表格空白的完整数据流"""
import sys, io, os, traceback, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.chdir(r'E:\zpp011_dev\模块化脚本')

print("=== 步骤1: 文件查找 ===")
import pandas as pd, glob as _glob

out_dir = os.path.expanduser('~/Desktop')
patterns = [
    os.path.join(out_dir, 'ZPP011偏差分析最终版_*.xlsx'),
    os.path.join(out_dir, 'ZPP011偏差分析结果包_*.xlsx'),
    os.path.join(out_dir, 'ZPP011偏差分析_*.xlsx'),
    os.path.join(out_dir, 'ZPP011*.xlsx'),
]
latest_file = None
for pattern in patterns:
    files = _glob.glob(pattern)
    if files:
        latest_file = max(files, key=os.path.getmtime)
        print(f"  OK: {os.path.basename(latest_file)}")
        break
if not latest_file:
    print("  ERROR: 未找到文件!")
    sys.exit(1)

print("\n=== 步骤2: 读取Excel ===")
dev_df = pd.read_excel(latest_file, sheet_name='完整偏差明细')
print(f"  dev_df: {len(dev_df)} 行")
print(f"  列: {list(dev_df.columns)}")

print("\n=== 步骤3: 模拟 _load_data_worker 构建 audit_df ===")
audit_df = dev_df.copy()

# 偏差率解析
def parse_rate(v):
    if isinstance(v, str):
        return float(v.replace('%','').replace('＞','>').replace('>','')) / 100
    return abs(float(v)) if pd.notna(v) else 0
audit_df['偏差率数值'] = dev_df['偏差率'].apply(parse_rate)

# 单价
audit_df['_unit_price'] = 0.0
if '金额-实际(含税)' in dev_df.columns and '数量-实际' in dev_df.columns:
    audit_df['金额-实际(含税)'] = dev_df['金额-实际(含税)']
    audit_df['数量-实际'] = dev_df['数量-实际']
    mask = (audit_df['数量-实际'] != 0) & audit_df['数量-实际'].notna()
    audit_df.loc[mask, '_unit_price'] = audit_df.loc[mask, '金额-实际(含税)'] / audit_df.loc[mask, '数量-实际']

# 订单类型
audit_df['订单类型'] = dev_df['订单类型'] if '订单类型' in dev_df.columns else ''

# 原表行号
audit_df['excel_row'] = range(2, len(audit_df) + 2)
audit_df['原表行号'] = audit_df['excel_row']
if '_excel_row' in dev_df.columns:
    audit_df['excel_row'] = dev_df['_excel_row'].apply(lambda x: int(x) if pd.notna(x) else 0)
    audit_df['原表行号'] = dev_df['_excel_row']

# 列映射
mapping = [
    ('组件物料号', '物料编码', ''),
    ('组件物料描述', '物料名称', ''),
    ('工厂名称', '工厂', ''),
    ('生产管理员描述', '车间', ''),
    ('数量-定额', '定额', 0),
    ('数量-实际', '实际', 0),
    ('备注原因', '备注', ''),
]
for dst, src, default in mapping:
    if src in audit_df.columns:
        audit_df[dst] = audit_df[src]
    else:
        audit_df[dst] = default

audit_df['偏差率(%)'] = audit_df['偏差率数值'] * 100

print(f"  audit_df: {len(audit_df)} 行")
print(f"  列: {list(audit_df.columns)[:15]}")

print("\n=== 步骤4: 模拟 _on_load_done 处理 ===")
# material_category
mat_cat_map = {
    "100": "原辅料", "200": "包材",
    "400": "食品辅料/食品半成品", "410": "饮料辅料/饮料半成品",
    "500": "食品成品", "510": "饮料成品", "600": "促销品",
}
if '物料编码' in audit_df.columns:
    audit_df['material_category'] = audit_df['物料编码'].apply(
        lambda x: mat_cat_map.get(str(x)[:3], '') if pd.notna(x) else ''
    )
    vc = audit_df['material_category'].value_counts()
    print(f"  material_category 分布:")
    for k, v in vc.items():
        print(f"    {k}: {v}")

# 数值列转换
for col in ['偏差率(%)', '偏差数量', '定额', '实际', '偏差金额']:
    if col in audit_df.columns:
        audit_df[col] = pd.to_numeric(audit_df[col], errors='coerce')

print(f"  数值列转换完成")

print("\n=== 步骤5: 检查 _refresh_audit_tree 所需列 ===")
# 从 table_events.py 的 insert 语句推断所需列
required = [
    'excel_row', '工厂', '车间', '订单日期', '流程订单', '物料编码',
    '物料名称', '单位', '定额', '实际', '偏差率', '偏差数量', '偏差金额',
    '备注原因', '备注来源', '物料分类', '偏差区间', 'audit_result', 'AI建议',
    'material_category', '备注原因长度', '_priority_label', '偏差金额_排序',
]
missing = [c for c in required if c not in audit_df.columns]
print(f"  缺失列 ({len(missing)}): {missing}")

print("\n=== 步骤6: 模拟 _refresh_audit_tree 的 insert ===")
# 尝试构建一行 insert 的值，看是否有 KeyError
try:
    row = audit_df.iloc[0]
    vals = []
    for col in required:
        v = row.get(col, '')
        vals.append(str(v)[:50] if pd.notna(v) else '')
    print(f"  首行 values 构建成功，共 {len(vals)} 个元素")
    print(f"  示例: excel_row={vals[0]}, 工厂={vals[1]}, 车间={vals[2]}")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

print("\n=== 结论 ===")
print(f"如果所有步骤都 OK，问题一定在 GUI 层的调用链:")
print(f"  1. _load_data_worker 是否被正确调用?")
print(f"  2. _on_load_done 是否被正确回调?")
print(f"  3. _refresh_audit_tree 是否被调用?")
print(f"  4. Treeview insert 是否因异常被吞?")
print(f"建议: 在 _on_load_done 第一行加 print/self.log 确认被调用")
print(f"建议: 在 _refresh_audit_tree 的 for 循环加 try/except 打印每行错误")

input("\n按回车退出...")
