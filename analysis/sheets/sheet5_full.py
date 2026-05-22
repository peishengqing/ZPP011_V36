#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet5_full.py — Sheet5 完整偏差明细（v36 抽取，未修改逻辑）
"""
import pandas as pd
import numpy as np


def build_sheet5(df, report_progress, progress_idx=5):
    """
    构建 Sheet5 完整偏差明细 DataFrame
    参数:
        df: 主数据 DataFrame
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认5）
    返回:
        dev_df: 完整偏差明细 DataFrame
    """
    report_progress(progress_idx, "Sheet5-完整偏差明细", 0)

    col_p = '偏差率(%)'
# 确保数值列为数值类型（防止字符串导致比较错误）
    for col in ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    has_real_dev = df[(df[col_p] < -1) | (df[col_p] > 1)].copy()

    # 计算偏差金额（含税）
    if '单价' in has_real_dev.columns and has_real_dev['单价'].notna().any():
        has_real_dev['_偏差金额'] = has_real_dev['材料偏差'] * has_real_dev['单价'] * 1.13
    elif '金额-实际(含税)' in has_real_dev.columns and '数量-实际' in has_real_dev.columns:
        # 反算单价：金额-实际(含税) / 数量-实际
        unit_price = has_real_dev['金额-实际(含税)'] / has_real_dev['数量-实际'].replace(0, np.nan)
        unit_price = unit_price.fillna(0)
        has_real_dev['_偏差金额'] = has_real_dev['材料偏差'] * unit_price
    else:
        has_real_dev['_偏差金额'] = 0.0

    dev_df = pd.DataFrame([{
        '订单日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
        '流程订单': r['流程订单'],
        '工厂': r['工厂名称'],
        '车间': r['车间'],
        '物料类型': r['物料分类'],
        '原表行号': r['_excel_row'],
        '物料编码': r['组件物料号'],
        '物料名称': r['组件物料描述'],
        '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
        '定额': r['数量-定额'],
        '实际': r['数量-实际'],
        '偏差数量': r['材料偏差'],
        '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
        '偏差金额': round(r['_偏差金额'], 2) if isinstance(r['_偏差金额'], (int, float)) else 0,
        '备注': str(r['备注原因']) if pd.notna(r['备注原因']) and r['备注原因'] != '' else '',
        '备注来源': r.get('_note_source', '人工填写'),
        '偏差区间': '正偏差' if r[col_p] > 0 else '负偏差',
    } for idx_r, (_, r) in enumerate(has_real_dev.iterrows())])

    report_progress(progress_idx, "Sheet5-完整偏差明细", 100)
    return dev_df
