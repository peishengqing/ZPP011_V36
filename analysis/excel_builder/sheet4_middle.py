#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet4_middle.py — Sheet4 中间地带明细（v36 抽取，未修改逻辑）
"""
import pandas as pd
import re
from analysis.excel_builder.write_sheet_util import ensure_numeric_cols
from config.settings import DEFAULT_THRESHOLD


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
    dyn_thresh = DEFAULT_THRESHOLD
    thresh = dyn_thresh

# 确保数值列为数值类型（防止字符串导致比较错误）
    ensure_numeric_cols(df, ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"])
    middle = df[(df[col_p].notna()) & (df[col_p] >= -thresh)
                & (df[col_p] <= thresh)].copy()

    alt_orders = list(set(alt_df['订单号'])) if len(alt_df) > 0 else []
    alt_all_descs = [(a[-1] if isinstance(a, (list,tuple)) else a) for a, b in alt_pairs] + [(b[-1] if isinstance(b, (list,tuple)) else b) for a, b in alt_pairs]
    esc_descs = [re.escape(d) for d in alt_all_descs]
    middle = middle[~(middle['组件物料描述'].str.contains('|'.join(
        esc_descs), na=False, regex=True)) & ~(middle['流程订单'].isin(alt_orders))]

    # 向量化构建（原 iterrows 列表推导，2026-07-27 性能优化）
    if middle.empty:
        middle_df = pd.DataFrame([])
    else:
        middle_df = pd.DataFrame(index=middle.index)
        middle_df['订单日期'] = pd.to_datetime(middle['订单开始日期'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        middle_df['工厂'] = middle['工厂名称']
        middle_df['车间'] = middle['车间']
        middle_df['物料名称'] = middle['组件物料描述']
        middle_df['物料类型'] = middle['物料分类']
        middle_df['单位'] = middle['组件单位'].fillna('')
        middle_df['定额'] = middle['数量-定额']
        middle_df['实际'] = middle['数量-实际']
        middle_df['偏差数量'] = middle['材料偏差']
        middle_df['偏差率'] = middle[col_p].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else '')
        middle_df['备注'] = middle['备注原因'].where(
            middle['备注原因'].notna() & (middle['备注原因'] != ''), '').astype(str)
        middle_df['标准原因'] = middle['标准原因'] if '标准原因' in middle.columns else ''
        middle_df = middle_df.reset_index(drop=True)

    report_progress(progress_idx, "Sheet4-中间地带明细", 100)
    return middle_df
