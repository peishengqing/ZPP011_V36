#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sheet9_reason_detail.py — Sheet9 偏差原因分析（v36 抽取，未修改逻辑）"""
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

    # 确保数值列为数值类型（防止字符串导致比较错误）
    for col in ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    has_reason = df[(df['备注原因'].notna()) & (
        df['备注原因'] != '') & (df['材料偏差'] != 0)].copy()
    has_reason['_std_reason'] = has_reason['备注原因'].apply(standardize_remark)

    # ⑤ 预计算各车间的偏差数量绝对值合计，作为"占车间偏差比%"的分母
    ws_dev_abs = has_reason.groupby(['工厂名称', '车间'])['材料偏差'].apply(
        lambda s: s.abs().sum()).to_dict()

    reason_analysis = []
    for (factory, ws_name, mat_cat, std_reason), grp in has_reason.groupby(
            ['工厂名称', '车间', '物料分类', '_std_reason']):
        total_dev = grp['材料偏差'].sum()
        # 用 set() 而非 .unique() 避免 numpy 内部排序时 int/str 比较崩溃
        _reasons = set()
        for x in grp['备注原因']:
            if pd.notna(x) and str(x).strip():
                _reasons.add(str(x))
        ex_remarks = '；'.join(sorted(_reasons)[:3])
        dev_abs = abs(total_dev)
        denom = ws_dev_abs.get((factory, ws_name), 0)
        ratio_pct = round(dev_abs / denom * 100, 2) if denom else 0.0
        orders = set()
        for x in grp['流程订单']:
            if pd.notna(x):
                try:
                    f = float(x)
                    orders.add(str(int(f)) if f == int(f) else str(f))
                except (ValueError, TypeError):
                    orders.add(str(x))
        reason_analysis.append({
            '工厂': factory,
            '车间': ws_name,
            '物料分类': mat_cat,
            '备注原因': std_reason,
            '原始备注示例': ex_remarks,
            '涉及物料数': len(set(str(x) for x in grp['组件物料描述'] if pd.notna(x))),
            '涉及订单数': len(orders),
            '多耗': round(grp[grp['材料偏差'] > 0]['材料偏差'].sum(), 2),
            '少耗': round(abs(grp[grp['材料偏差'] < 0]['材料偏差'].sum()), 2),
            '净偏差数量': round(total_dev, 2),
            '占车间偏差比%': ratio_pct,
            '涉及物料': '、'.join(sorted(set(str(x) for x in grp['组件物料描述'] if pd.notna(x)))),
        })

    reason_analysis_df = pd.DataFrame(reason_analysis)
    if not reason_analysis_df.empty:
        reason_analysis_df = reason_analysis_df.sort_values(
            ['工厂', '车间', '物料分类', '净偏差数量'], ascending=[True, True, True, False])

    report_progress(progress_idx, "Sheet9-原因分析", 100)
    return reason_analysis_df
