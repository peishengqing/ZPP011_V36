#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet4_middle.py — Sheet4 中间地带明细（v36 抽取，未修改逻辑）
"""
import pandas as pd
import re


def build_sheet4(df, alt_df, alt_pairs, report_progress, progress_idx=4):
    """
    构建 Sheet4 中间地带明细 DataFrame
    参数:
        df: 主数据 DataFrame
        alt_df: 替代料明细 DataFrame
        alt_pairs: 替代料配对列表
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认4）
    返回:
        middle_df: 中间地带明细 DataFrame
    """
    report_progress(progress_idx, "Sheet4-中间地带明细", 0)

    col_p = '偏差率(%)'
    dyn_thresh = 10.0
    thresh = dyn_thresh

# 确保数值列为数值类型（防止字符串导致比较错误）
    for col in ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    middle = df[(df[col_p].notna()) & (df[col_p] >= -thresh)
                & (df[col_p] <= thresh)].copy()

    alt_orders = list(set(alt_df['订单号'])) if len(alt_df) > 0 else []
    alt_all_descs = [(a[-1] if isinstance(a, (list,tuple)) else a) for a, b in alt_pairs] + [(b[-1] if isinstance(b, (list,tuple)) else b) for a, b in alt_pairs]
    esc_descs = [re.escape(d) for d in alt_all_descs]
    middle = middle[~(middle['组件物料描述'].str.contains('|'.join(
        esc_descs), na=False, regex=True)) & ~(middle['流程订单'].isin(alt_orders))]

    middle_df = pd.DataFrame([{
        '订单日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
        '工厂': r['工厂名称'],
        '车间': r['车间'],
        '物料名称': r['组件物料描述'],
        '物料类型': r['物料分类'],
        '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
        '定额': r['数量-定额'],
        '实际': r['数量-实际'],
        '偏差数量': r['材料偏差'],
        '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
        '备注': str(r['备注原因']) if pd.notna(r['备注原因']) and r['备注原因'] != '' else '',
        '标准原因': r.get('标准原因', ''),
    } for _, r in middle.iterrows()])

    report_progress(progress_idx, "Sheet4-中间地带明细", 100)
    return middle_df
