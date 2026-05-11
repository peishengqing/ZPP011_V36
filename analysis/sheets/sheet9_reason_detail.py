#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet9_reason_detail.py — Sheet9 偏差原因分析（v36 抽取，未修改逻辑）
"""
import pandas as pd
from utils.helpers import standardize_remark


def build_sheet9(df, report_progress, progress_idx=9):
    """
    构建 Sheet9 偏差原因分析 DataFrame
    参数:
        df: 主数据 DataFrame
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认9）
    返回:
        reason_analysis_df: 偏差原因分析 DataFrame
    """
    report_progress(progress_idx, "Sheet9-原因分析", 0)

    has_reason = df[(df['备注原因'].notna()) & (
        df['备注原因'] != '') & (df['材料偏差'] != 0)].copy()
    has_reason['_std_reason'] = has_reason['备注原因'].apply(standardize_remark)

    reason_analysis = []
    for (factory, ws_name, mat_cat, std_reason), grp in has_reason.groupby(
            ['工厂名称', '车间', '物料分类', '_std_reason']):
        total_dev = grp['材料偏差'].sum()
        ex_remarks = '；'.join(sorted(grp['备注原因'].unique())[:3])
        reason_analysis.append({
            '工厂': factory,
            '车间': ws_name,
            '物料分类': mat_cat,
            '备注原因': std_reason,
            '原始备注示例': ex_remarks,
            '涉及物料数': len(grp['组件物料描述'].unique()),
            '多耗': round(grp[grp['材料偏差'] > 0]['材料偏差'].sum(), 2),
            '少耗': round(abs(grp[grp['材料偏差'] < 0]['材料偏差'].sum()), 2),
            '净偏差': round(total_dev, 2),
            '涉及物料': '、'.join(grp['组件物料描述'].unique()),
        })

    reason_analysis_df = pd.DataFrame(reason_analysis)
    reason_analysis_df = reason_analysis_df.sort_values(
        ['工厂', '车间', '物料分类', '净偏差'], ascending=[True, True, True, False])

    report_progress(progress_idx, "Sheet9-原因分析", 100)
    return reason_analysis_df
