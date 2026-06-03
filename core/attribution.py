# -*- coding: utf-8 -*-
"""
AI 归因分析模块
对比当前分析数据与历史分析数据，定位偏差变化的主要贡献维度
"""
import pandas as pd
from core import history_db


def get_latest_history_analysis():
    """获取最近一次历史分析的数据（用于对比）"""
    try:
        records = history_db.get_analysis_list(limit=1)
        if records:
            latest_id = records[0]['id']  # 最近一次历史分析
            return history_db.get_analysis_data(latest_id)
    except Exception:
        pass
    return None


def generate_report_text(current_df, history_df):
    """
    生成 AI 归因分析报告文本
    """
    if current_df is None or current_df.empty:
        return "无当前分析数据，无法生成归因报告。"

    # 1. 计算偏差总额
    amount_col = None
    for col in ['偏差金额', '偏差金额(含税)', 'deviation_amount']:
        if col in current_df.columns:
            amount_col = col
            break
    if amount_col is None:
        return "数据中缺少偏差金额列，无法进行归因分析。"

    current_total = current_df[amount_col].fillna(0).sum()
    if history_df is not None and not history_df.empty:
        history_total = history_df[amount_col].fillna(0).sum()
        change = current_total - history_total
        change_pct = (change / abs(history_total) * 100) if history_total != 0 else float('inf')
    else:
        history_total = None
        change = None
        change_pct = None

    # 报告头部
    lines = []
    lines.append("📊 AI 归因分析报告")
    lines.append("=" * 40)
    if history_total is not None:
        lines.append("对比基准：最近一次历史分析")
        lines.append(f"历史偏差总额: {history_total:,.2f} 元")
        lines.append(f"当前偏差总额: {current_total:,.2f} 元")
        if change is not None:
            sign = "+" if change >= 0 else ""
            lines.append(f"变化: {sign}{change:,.2f} 元 ({sign}{change_pct:.1f}%)")
            lines.append("")
    else:
        lines.append("对比基准：无历史数据，仅展示当前分析")
        lines.append("")

    # 2. 按车间贡献度分解（如果有车间列）
    workshop_col = None
    for col in ['车间', '生产管理员描述', 'admin']:
        if col in current_df.columns:
            workshop_col = col
            break
    if workshop_col and history_total is not None and history_df is not None:
        # 计算各车间偏差金额（绝对值，用于贡献度）
        # 注意：贡献度定义为 (当前车间偏差 - 历史车间偏差) 占总变化的百分比
        hist_workshop = history_df.groupby(workshop_col)[amount_col].sum().fillna(0)
        curr_workshop = current_df.groupby(workshop_col)[amount_col].sum().fillna(0)
        all_workshops = set(hist_workshop.index) | set(curr_workshop.index)
        workshop_contrib = []
        for ws in all_workshops:
            hist_val = hist_workshop.get(ws, 0)
            curr_val = curr_workshop.get(ws, 0)
            diff = curr_val - hist_val
            if abs(diff) > 0.01 and abs(change) > 0.01:
                contrib = diff / change * 100
                workshop_contrib.append((ws, diff, contrib))
        # 按贡献度绝对值排序
        workshop_contrib.sort(key=lambda x: abs(x[2]), reverse=True)
        if workshop_contrib:
            lines.append("📌 主要偏差来源（按车间贡献度）：")
            for i, (ws, diff, contrib) in enumerate(workshop_contrib[:5], 1):
                sign = "+" if diff >= 0 else ""
                lines.append(f"  {i}. {ws}: {sign}{diff:,.2f} 元 (贡献率 {contrib:.1f}%)")
            lines.append("")

    # 3. 按物料大类贡献度分解（如果有物料大类列）
    cat_col = None
    for col in ['material_category', '物料大类']:
        if col in current_df.columns:
            cat_col = col
            break
    if cat_col and history_total is not None and history_df is not None:
        # 检查历史数据是否包含该列
        if cat_col not in history_df.columns:
            lines.append("📌 历史数据缺少物料大类列，无法按物料大类归因。")
            lines.append("")
        else:
            hist_cat = history_df.groupby(cat_col)[amount_col].sum().fillna(0)
            curr_cat = current_df.groupby(cat_col)[amount_col].sum().fillna(0)
            all_cats = set(hist_cat.index) | set(curr_cat.index)
            cat_contrib = []
            for cat in all_cats:
                hist_val = hist_cat.get(cat, 0)
                curr_val = curr_cat.get(cat, 0)
                diff = curr_val - hist_val
                if abs(diff) > 0.01 and abs(change) > 0.01:
                    contrib = diff / change * 100
                    cat_contrib.append((cat, diff, contrib))
            cat_contrib.sort(key=lambda x: abs(x[2]), reverse=True)
            if cat_contrib:
                lines.append("📌 主要偏差来源（按物料大类贡献度）：")
                for i, (cat, diff, contrib) in enumerate(cat_contrib[:5], 1):
                    sign = "+" if diff >= 0 else ""
                    lines.append(f"  {i}. {cat}: {sign}{diff:,.2f} 元 (贡献率 {contrib:.1f}%)")
                lines.append("")
            else:
                lines.append("📌 物料大类数据不足，无法归因。")
                lines.append("")

    # 4. 偏差方向分析（超耗/少耗）
    # 动态匹配偏差率列
    rate_col = None
    for col in current_df.columns:
        if '偏差率' in str(col):
            rate_col = col
            break
    if rate_col:
        # 先转换成数值，避免字符串比较报错
        _rates = pd.to_numeric(current_df[rate_col], errors='coerce').fillna(0)
        over = current_df[_rates > 0][amount_col].sum()
        under = current_df[_rates < 0][amount_col].sum()
        lines.append("💡 偏差方向分析：")
        lines.append(f"  超耗金额: {over:,.2f} 元")
        lines.append(f"  少耗金额: {under:,.2f} 元")
        lines.append("")

    # 5. 审核情况（可选）
    if '审核状态' in current_df.columns:
        reviewed = (current_df['审核状态'] == '已审核').sum()
        total = len(current_df)
        if total > 0:
            rate = reviewed / total * 100
            lines.append(f"📋 审核进度：{reviewed}/{total} 行已审核 ({rate:.1f}%)")
            lines.append("")

    # 6. 备注覆盖率（可选）
    if '备注原因' in current_df.columns:
        noted = current_df['备注原因'].notna().sum()
        total = len(current_df)
        if total > 0:
            noted_rate = noted / total * 100
            lines.append(f"📝 备注覆盖率：{noted}/{total} 行有备注 ({noted_rate:.1f}%)")
            lines.append("")

    lines.append("=" * 40)
    lines.append("报告生成时间：" + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))

    return "\n".join(lines)
