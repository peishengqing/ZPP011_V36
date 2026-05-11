#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet2_alt.py — Sheet2 替代料明细（v36 抽取，未修改逻辑）
返回: (alt_df, alt_order_mat_set)
"""
import pandas as pd


def build_sheet2(df, alt_pairs, report_progress, progress_idx=2):
    """
    构建 Sheet2 替代料明细 DataFrame 及替代料订单-物料集合
    参数:
        df: 主数据 DataFrame
        alt_pairs: 替代料配对列表 [(物料A描述, 物料B描述), ...]
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认2）
    返回:
        (alt_df, alt_order_mat_set):
            alt_df: 替代料明细 DataFrame
            alt_order_mat_set: set of (订单号, 物料描述) 用于标记替代料
    """
    report_progress(progress_idx, "Sheet2-替代料明细", 0)
    print("[DEBUG do_analysis_v2] 开始生成Sheet2", flush=True)

    col_p = '偏差率(%)'
    alt_rows = []

    for order, grp in df.groupby('流程订单'):
        for mat_a_desc, mat_b_desc in alt_pairs:
            rows_a = grp[grp['组件物料描述'] == mat_a_desc]
            rows_b = grp[grp['组件物料描述'] == mat_b_desc]
            if len(rows_a) > 0 and len(rows_b) > 0:
                a, b = rows_a.iloc[0], rows_b.iloc[0]
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
                    '备注': '替代料',
                    '标准原因': a.get('标准原因', ''),
                })

    alt_df = pd.DataFrame(alt_rows)
    print(f"[DEBUG do_analysis_v2] Sheet2完成，{len(alt_df)} 行", flush=True)
    report_progress(progress_idx, "Sheet2-替代料明细", 100)

    # 构建替代料订单-物料集合（用于后续标记）
    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r['订单号']), str(r['物料A'])))
        alt_order_mat.add((str(r['订单号']), str(r['物料B'])))

    return alt_df, alt_order_mat
