# -*- coding: utf-8 -*-
"""AI 归因分析算法 - 偏差原因智能分析"""
import pandas as pd
from typing import Dict, Any, Optional
from core.history_db import get_analysis_list, get_analysis_data


def get_latest_history_analysis() -> Optional[pd.DataFrame]:
    """获取最近一次历史分析的明细数据（排除当前分析）"""
    records = get_analysis_list(limit=2)  # 最近两次
    if not records:
        return None
    # 如果有两条以上，取第二条（即上一次）；如果只有一条，则无历史
    if len(records) >= 2:
        latest_id = records[1]['id']  # 第一条是最新（当前），第二条是上一次
        return get_analysis_data(latest_id)
    return None


def calculate_contribution(current_df: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    计算偏差变化的贡献度（按物料大类 + 车间）
    返回: {
        'has_history': bool,
        'current_total': float,
        'history_total': float,
        'change': float,
        'change_pct': float,
        'contributions': [{'dimension': '包材', 'contribution': 12000, 'pct': 60, ...}, ...],
        'workshop_contributions': [{'dimension': '车间A', ...}, ...],
        'report_text': str
    }
    """
    # 确定偏差金额列名
    amount_col = None
    for col in ['偏差金额', '偏差金额(含税)', 'deviation_amount']:
        if col in current_df.columns:
            amount_col = col
            break
    if amount_col is None:
        return {'error': '当前数据缺少偏差金额列', 'report_text': '无法进行归因分析：数据中无偏差金额信息。'}

    # 当前总额
    current_total = current_df[amount_col].sum()
    result = {
        'has_history': False,
        'current_total': current_total,
        'history_total': 0.0,
        'change': 0.0,
        'change_pct': 0.0,
        'contributions': [],
        'workshop_contributions': [],
        'report_text': ''
    }

    if history_df is None or history_df.empty:
        # 无历史数据：仅展示当前分布
        report = f"📊 AI 归因分析报告\n\n"
        report += f"当前偏差总额: {current_total:,.2f} 元\n\n"
        # 按物料大类统计
        if 'material_category' in current_df.columns:
            cat_stats = current_df.groupby('material_category')[amount_col].apply(
                lambda x: x.abs().sum()).sort_values(ascending=False)
            report += "偏差金额按物料大类分布（绝对值）：\n"
            for cat, amt in cat_stats.head(5).items():
                pct = (amt / current_total * 100) if current_total != 0 else 0
                report += f"  • {cat}: {amt:,.2f} 元 ({pct:.1f}%)\n"
        else:
            report += "数据中缺少物料大类列，无法按类别分析。\n"
        # 按车间统计
        for wcol in ['车间', '生产管理员描述']:
            if wcol in current_df.columns:
                ws_stats = current_df.groupby(wcol)[amount_col].apply(
                    lambda x: x.abs().sum()).sort_values(ascending=False)
                report += f"\n偏差金额按{wcol}分布（绝对值）：\n"
                for ws, amt in ws_stats.head(5).items():
                    pct = (amt / current_total * 100) if current_total != 0 else 0
                    report += f"  • {ws}: {amt:,.2f} 元 ({pct:.1f}%)\n"
                break
        result['report_text'] = report
        return result

    # 有历史数据：计算变化贡献度
    history_total = history_df[amount_col].sum()
    change = current_total - history_total
    change_pct = (change / history_total * 100) if history_total != 0 else float('inf')

    result['has_history'] = True
    result['history_total'] = history_total
    result['change'] = change
    result['change_pct'] = change_pct

    # 按物料大类计算贡献度
    if 'material_category' in current_df.columns and 'material_category' in history_df.columns:
        current_by_cat = current_df.groupby('material_category')[amount_col].sum()
        history_by_cat = history_df.groupby('material_category')[amount_col].sum()
        all_cats = set(current_by_cat.index).union(history_by_cat.index)
        contributions = []
        for cat in all_cats:
            cur = current_by_cat.get(cat, 0)
            hist = history_by_cat.get(cat, 0)
            contr = cur - hist
            if contr != 0:
                contributions.append({
                    'dimension': cat,
                    'contribution': contr,
                    'current': cur,
                    'history': hist,
                    'pct': (contr / change * 100) if change != 0 else 0
                })
        contributions.sort(key=lambda x: abs(x['contribution']), reverse=True)
        result['contributions'] = contributions[:5]

    # 按车间计算贡献度
    for wcol in ['车间', '生产管理员描述']:
        if wcol in current_df.columns and wcol in history_df.columns:
            current_by_ws = current_df.groupby(wcol)[amount_col].sum()
            history_by_ws = history_df.groupby(wcol)[amount_col].sum()
            all_ws = set(current_by_ws.index).union(history_by_ws.index)
            ws_contribs = []
            for ws in all_ws:
                cur = current_by_ws.get(ws, 0)
                hist = history_by_ws.get(ws, 0)
                contr = cur - hist
                if contr != 0:
                    ws_contribs.append({
                        'dimension': ws,
                        'contribution': contr,
                        'current': cur,
                        'history': hist,
                        'pct': (contr / change * 100) if change != 0 else 0
                    })
            ws_contribs.sort(key=lambda x: abs(x['contribution']), reverse=True)
            result['workshop_contributions'] = ws_contribs[:5]
            break

    # 生成报告文本
    report = f"📊 AI 归因分析报告\n\n"
    report += f"对比基准：最近一次历史分析\n"
    report += f"历史偏差总额: {history_total:,.2f} 元\n"
    report += f"当前偏差总额: {current_total:,.2f} 元\n"
    if history_total != 0:
        report += f"变化: {change:+,.2f} 元 ({change_pct:+.1f}%)\n\n"
    else:
        report += f"变化: 历史总额为零，无法计算百分比\n\n"

    if result['contributions']:
        report += "📌 主要偏差来源（按物料大类贡献度）：\n"
        for i, c in enumerate(result['contributions'][:3], 1):
            if c['contribution'] > 0:
                report += f"  {i}. {c['dimension']}: 增加 {c['contribution']:+,.2f} 元 (贡献率 {c['pct']:.1f}%)\n"
            else:
                report += f"  {i}. {c['dimension']}: 减少 {c['contribution']:+,.2f} 元 (贡献率 {c['pct']:.1f}%)\n"
    else:
        report += "无有效的物料大类数据，无法归因。\n"

    if result['workshop_contributions']:
        report += "\n📌 主要偏差来源（按车间贡献度）：\n"
        for i, c in enumerate(result['workshop_contributions'][:3], 1):
            if c['contribution'] > 0:
                report += f"  {i}. {c['dimension']}: 增加 {c['contribution']:+,.2f} 元 (贡献率 {c['pct']:.1f}%)\n"
            else:
                report += f"  {i}. {c['dimension']}: 减少 {c['contribution']:+,.2f} 元 (贡献率 {c['pct']:.1f}%)\n"

    result['report_text'] = report
    return result


def generate_report_text(current_df: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> str:
    """生成可直接展示的文本报告"""
    res = calculate_contribution(current_df, history_df)
    return res.get('report_text', '归因分析失败')
