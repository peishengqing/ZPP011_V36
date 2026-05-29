# -*- coding: utf-8 -*-
"""AI 归因分析算法"""
import pandas as pd


def calculate_attribution(current_df, history_df=None):
    """
    返回文本报告，分析偏差变化的主要原因
    """
    if current_df is None or current_df.empty:
        return "当前无分析数据，无法归因。"

    # 确定偏差金额列
    amount_col = None
    for col in ['偏差金额', 'deviation_amount']:
        if col in current_df.columns:
            amount_col = col
            break

    if amount_col is None:
        return "数据中缺少偏差金额列，无法进行归因分析。"

    total_current = current_df[amount_col].sum()

    # 无历史数据时只展示当前分布
    if history_df is None or history_df.empty:
        report = "当前偏差总额: " + "{:,.2f}".format(total_current) + "元\n\n"

        if 'material_category' in current_df.columns:
            cat_stats = current_df.groupby('material_category')[amount_col].sum().sort_values(ascending=False)
            report += "偏差金额按物料大类分布：\n"
            for cat, amt in cat_stats.items():
                pct = (amt / total_current * 100) if total_current != 0 else 0
                report += "  " + str(cat) + ": " + "{:,.2f}".format(amt) + "元 (" + "{:.1f}".format(pct) + "%)\n"
        else:
            report += "数据中缺少物料大类列，无法按类别分析。"

        return report

    # 有历史数据：计算变化贡献率
    total_history = history_df[amount_col].sum()
    change = total_current - total_history

    report = "历史偏差总额: " + "{:,.2f}".format(total_history) + "元\n"
    report += "当前偏差总额: " + "{:,.2f}".format(total_current) + "元\n"

    if total_history != 0:
        pct = change / total_history * 100
        report += "变化: " + "{:+,.2f}".format(change) + "元 (" + "{:+.1f}".format(pct) + "%)\n\n"
    else:
        report += "变化: 历史总额为零，无法计算百分比\n\n"

    # 按物料大类分析贡献
    if 'material_category' in current_df.columns and 'material_category' in history_df.columns:
        current_by_cat = current_df.groupby('material_category')[amount_col].sum()
        history_by_cat = history_df.groupby('material_category')[amount_col].sum()
        all_cats = set(current_by_cat.index).union(set(history_by_cat.index))

        contributions = []
        for cat in all_cats:
            cur = current_by_cat.get(cat, 0)
            hist = history_by_cat.get(cat, 0)
            contr = cur - hist
            contributions.append((cat, contr, cur, hist))

        contributions.sort(key=lambda x: abs(x[1]), reverse=True)

        report += "偏差变化主要来源（按物料大类）：\n"
        for cat, contr, cur, hist in contributions[:5]:
            if contr > 0:
                report += ("  " + str(cat) + ": 增加 " + "{:+,.2f}".format(contr) + "元 (当前" + "{:.0f}".format(cur) + " vs 历史" + "{:.0f}".format(hist) + ")\n")
            elif contr < 0:
                report += ("  " + str(cat) + ": 减少 " + "{:+,.2f}".format(contr) + "元 (当前" + "{:.0f}".format(cur) + " vs 历史" + "{:.0f}".format(hist) + ")\n")

        if not contributions:
            report += "  无有效类别数据\n"
    else:
        report += "数据中缺少物料大类列，无法按类别分析贡献。\n"

    return report
