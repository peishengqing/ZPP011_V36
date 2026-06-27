#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet2_alt.py — Sheet2 替代料明细（v36 抽取，兼容三元组配对）
返回: (alt_df, alt_order_mat_set)
"""
import pandas as pd


def build_sheet2(df, alt_pairs, report_progress, progress_idx=2):
    """
    构建 Sheet2 替代料明细 DataFrame 及替代料订单-物料集合
    参数:
        df: 主数据 DataFrame
        alt_pairs: 替代料配对列表，每个元素为 (物料A, 物料B)
                  物料可以是字符串、二元组 (code, name) 或三元组 (factory, code, name)
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认2）
    返回:
        (alt_df, alt_order_mat_set):
            alt_df: 替代料明细 DataFrame
            alt_order_mat_set: set of (订单号, 物料描述) 用于标记替代料
    """
    report_progress(progress_idx, "Sheet2-替代料明细", 0)
    print("[DEBUG do_analysis_v2] 开始生成Sheet2")

    # ---------- 兼容性转换：将配对中的物料提取为描述字符串 ----------
    # 由于替代料明细表中匹配的是“物料描述”，我们需要将配对中的物料转换为描述字符串。
    # 原始逻辑中，alt_pairs 中的元素是物料描述字符串（如“核桃仁头二路”）。
    # 但现在存储的可能是三元组 (factory, code, name)，我们需要提取 name 作为描述。
    # 同时，为了兼容旧格式，如果已经是字符串则直接使用。
    converted_pairs = []
    for a, b in alt_pairs:
        def get_desc(item):
            if isinstance(item, (list, tuple)):
                # 如果是三元组 (factory, code, name)，取 name（最后一个元素）
                if len(item) == 3:
                    return str(item[2]) if item[2] else ''
                # 如果是二元组 (code, name)，取 name
                elif len(item) == 2:
                    return str(item[1]) if item[1] else ''
                else:
                    return str(item[0]) if item[0] else ''
            else:
                return str(item)
        desc_a = get_desc(a)
        desc_b = get_desc(b)
        if desc_a and desc_b:
            converted_pairs.append((desc_a, desc_b))
        else:
            print(f"[警告] 跳过无效替代料配对: {a} ↔ {b}")

    col_p = '偏差率(%)'
    alt_rows = []

    for order, grp in df.groupby('流程订单'):
        for mat_a_desc, mat_b_desc in converted_pairs:
            # 三级匹配：精确 → 包含 → 编码
            rows_a = grp[grp['组件物料描述'] == mat_a_desc]
            rows_b = grp[grp['组件物料描述'] == mat_b_desc]
            # 第二级：包含匹配
            if len(rows_a) == 0 and mat_a_desc:
                rows_a = grp[grp['组件物料描述'].str.contains(mat_a_desc, na=False, regex=False)]
            if len(rows_b) == 0 and mat_b_desc:
                rows_b = grp[grp['组件物料描述'].str.contains(mat_b_desc, na=False, regex=False)]
            # 第三级：用组件物料编码/物料号匹配（仅在该列存在时使用）
            code_col = next((c for c in grp.columns if c in ('组件物料编码', '组件物料号')), None)
            if len(rows_a) == 0 and mat_a_desc and code_col:
                rows_a = grp[grp[code_col].astype(str).str.contains(mat_a_desc, na=False, regex=False)]
            if len(rows_b) == 0 and mat_b_desc and code_col:
                rows_b = grp[grp[code_col].astype(str).str.contains(mat_b_desc, na=False, regex=False)]
            if len(rows_a) > 0 and len(rows_b) > 0:
                a, b = rows_a.iloc[0], rows_b.iloc[0]
                # 计算净偏差数量/金额（取A和B的合计；此时df中尚无净偏差列，直接用偏差数量/金额）
                qty_a = a.get('偏差数量', 0)
                qty_b = b.get('偏差数量', 0)
                amt_a = a.get('偏差金额', a.get('偏差金额(含税)', 0))
                amt_b = b.get('偏差金额', b.get('偏差金额(含税)', 0))
                alt_rows.append({
                    '订单日期': pd.Timestamp(a['订单开始日期']).strftime('%Y-%m-%d'),
                    '车间': a['车间'],
                    '订单号': order,
                    '物料A': a['组件物料描述'],
                    '单位': a['组件单位'] if pd.notna(a['组件单位']) else '',
                    '偏差A': a['材料偏差'],
                    '偏差率A': a[col_p],
                    '物料B': b['组件物料描述'],
                    '偏差B': b['材料偏差'],
                    '偏差率B': b[col_p],
                    '净偏差': round(float(a['材料偏差']) + float(b['材料偏差']), 2),
                    '净偏差数量': round(float(qty_a) + float(qty_b), 2),
                    '净偏差金额': round(float(amt_a) + float(amt_b), 2),
                    '备注': '替代料',
                    '标准原因': a.get('标准原因', ''),
                })

    alt_df = pd.DataFrame(alt_rows)
    print(f"[DEBUG do_analysis_v2] Sheet2完成，{len(alt_df)} 行")
    if len(alt_df) == 0 and len(converted_pairs) > 0:
        # 调试：打印前5个配对和df中的描述
        print(f"[DEBUG] 配对数: {len(converted_pairs)}, 前3个: {converted_pairs[:3]}")
        sample_descs = list(set(df['组件物料描述'].dropna()))[:5]
        print(f"[DEBUG] df物料描述样本: {sample_descs}")
    report_progress(progress_idx, "Sheet2-替代料明细", 100)

    # 构建替代料订单-物料集合（用于后续标记）
    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r['订单号']), str(r['物料A'])))
        alt_order_mat.add((str(r['订单号']), str(r['物料B'])))

    return alt_df, alt_order_mat