#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet3_no_note.py — Sheet3 无备注预警（v36 抽取，未修改逻辑）
"""
import pandas as pd


def build_sheet3(df, report_progress, progress_idx=3):
    """
    构建 Sheet3 无备注预警 DataFrame
    参数:
        df: 主数据 DataFrame
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认3）
    返回:
        no_note_df: 无备注预警 DataFrame（按偏差金额绝对值降序）
    """
    report_progress(progress_idx, "Sheet3-无备注预警", 0)
    print("[DEBUG do_analysis_v2] 开始生成Sheet3")

    col_p = '偏差率(%)'
    dyn_thresh = 10.0

# 确保数值列为数值类型（防止字符串导致比较错误）
    for col in ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    has_dev = df[df['材料偏差'] != 0]
    no_note = has_dev[~(has_dev['备注原因'].notna()) &
                        (has_dev['备注原因'] != '')].copy()
    no_note = no_note[abs(no_note[col_p]) > dyn_thresh].copy()

    no_note_df = pd.DataFrame([{
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
        '偏差金额(含税)': round(r['偏差金额(含税)'], 2) if pd.notna(r.get('偏差金额(含税)')) and r['偏差金额(含税)'] != 0 else 0,
        '标准原因': r.get('标准原因', ''),
        '备注': '',
    } for _, r in no_note.iterrows()])

    no_note_df['_abs_amt'] = no_note_df['偏差金额(含税)'].apply(
        lambda x: abs(x) if isinstance(x, (int, float)) else 0)
    no_note_df = no_note_df.sort_values(
        '_abs_amt', ascending=False).drop('_abs_amt', axis=1)

    report_progress(progress_idx, "Sheet3-无备注预警", 100)
    return no_note_df
