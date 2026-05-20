#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet1_summary.py — Sheet1 汇总统计（v36 抽取，未修改逻辑）
"""
import pandas as pd


def build_sheet1(df, report_progress, progress_idx=1):
    """
    构建 Sheet1 汇总统计 DataFrame
    参数:
        df: 主数据 DataFrame
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认1）
    返回:
        summary_df: 汇总统计 DataFrame
    """
    report_progress(progress_idx, "Sheet1-汇总统计", 0)
    print("[DEBUG do_analysis_v2] 开始生成Sheet1")

    summary_rows = []
    idx = 1
    col_p = '偏差率(%)'

    for (factory, ws_name, mat_cat), grp in df.groupby(['工厂', '车间', '物料分类']):
        pos_dev = grp[grp['材料偏差'] > 0]
        neg_dev = grp[grp['材料偏差'] < 0]
        has_note = grp['备注原因'].notna() & (grp['备注原因'] != '')
        note_rate = has_note.sum() / len(grp) if len(grp) > 0 else 0
        warning = '🔴' if note_rate == 0 else ('🟡' if note_rate < 0.3 else '🟢')
        pos_amt = round(pos_dev['偏差金额(含税)'].sum(), 2) if len(pos_dev) > 0 else 0
        neg_amt = round(neg_dev['偏差金额(含税)'].sum(), 2) if len(neg_dev) > 0 else 0
        total_amt = round(grp['偏差金额(含税)'].sum(), 2)
        summary_rows.append({
            '序号': idx,
            '工厂': factory,
            '工厂名称': grp['工厂名称'].iloc[0],
            '车间': ws_name,
            '物料分类': mat_cat,
            '正偏差条数': len(pos_dev),
            '正偏差数量': round(pos_dev['材料偏差'].sum(), 2),
            '正偏差金额(含税)': pos_amt,
            '负偏差条数': len(neg_dev),
            '负偏差数量': round(neg_dev['材料偏差'].sum(), 2),
            '负偏差金额(含税)': neg_amt,
            '总条数': len(grp),
            '总数量': round(grp['材料偏差'].sum(), 2),
            '总偏差金额(含税)': total_amt,
            '备注覆盖率': f"{note_rate:.0%}",
            '预警': warning,
        })
        idx += 1

    summary_df = pd.DataFrame(summary_rows)
    print(f"[DEBUG do_analysis_v2] Sheet1完成，{len(summary_df)} 行")
    report_progress(progress_idx, "Sheet1-汇总统计", 100)
    return summary_df
