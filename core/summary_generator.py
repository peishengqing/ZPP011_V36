# -*- coding: utf-8 -*-
"""智能小结生成器 - 基于统计的自然语言报告"""

import pandas as pd
from typing import Optional, Tuple


def generate_summary(current_df: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> str:
    """
    生成智能小结报告
    
    Args:
        current_df: 当前分析数据
        history_df: 历史分析数据（用于对比）
    
    Returns:
        str: 格式化的报告文本
    """
    if current_df is None or current_df.empty:
        return "当前无分析数据，无法生成小结。"
    
    # 确定列名
    amount_col = _find_column(current_df, ['偏差金额', '偏差金额(含税)', 'deviation_amount'])
    workshop_col = _find_column(current_df, ['车间', '生产管理员描述', 'workshop'])
    material_col = _find_column(current_df, ['物料大类', '物料编码', 'material_category'])
    
    if amount_col is None:
        return "数据中无偏差金额列，无法生成小结。"
    
    # 计算当前总额
    current_total = current_df[amount_col].abs().sum()
    
    # 历史对比
    if history_df is None or history_df.empty:
        history_total = None
        change_pct = None
    else:
        if amount_col in history_df.columns:
            history_total = history_df[amount_col].abs().sum()
            if history_total != 0:
                change_pct = (current_total - history_total) / history_total * 100
            else:
                change_pct = 0
        else:
            history_total = None
            change_pct = None
    
    # 趋势判断（阈值 ±5%）
    if change_pct is not None:
        if change_pct > 5:
            trend = "上升"
            trend_desc = f"较上期增长 {change_pct:.1f}%"
        elif change_pct < -5:
            trend = "下降"
            trend_desc = f"较上期下降 {abs(change_pct):.1f}%"
        else:
            trend = "平稳"
            trend_desc = f"较上期基本持平 ({change_pct:+.1f}%)"
    else:
        trend = "未知"
        trend_desc = "（无历史数据无法对比）"
    
    # Top 2 车间
    if workshop_col and workshop_col in current_df.columns:
        workshop_stats = current_df.groupby(workshop_col)[amount_col].apply(
            lambda x: x.abs().sum()).sort_values(ascending=False)
        top_workshops = workshop_stats.head(2)
        workshop_lines = []
        for i, (ws, amt) in enumerate(top_workshops.items(), 1):
            pct = amt / current_total * 100 if current_total > 0 else 0
            workshop_lines.append(f"  {i}. {ws}：偏差金额 {amt:,.0f} 元，占比 {pct:.1f}%")
    else:
        workshop_lines = ["  （车间信息不可用）"]
    
    # Top 2 物料大类
    if material_col and material_col in current_df.columns:
        material_stats = current_df.groupby(material_col)[amount_col].apply(
            lambda x: x.abs().sum()).sort_values(ascending=False)
        top_materials = material_stats.head(2)
        material_lines = []
        for i, (mat, amt) in enumerate(top_materials.items(), 1):
            pct = amt / current_total * 100 if current_total > 0 else 0
            material_lines.append(f"  {i}. {mat}：偏差金额 {amt:,.0f} 元，占比 {pct:.1f}%")
    else:
        material_lines = ["  （物料大类信息不可用）"]
    
    # 组装报告
    lines = []
    lines.append("=" * 50)
    lines.append("📊 ZPP011 生产偏差分析 - 智能小结")
    lines.append("=" * 50)
    lines.append("")
    
    # 总体偏差
    lines.append("【总体偏差概况】")
    lines.append(f"  本期偏差总额：{current_total:,.0f} 元")
    if history_total is not None:
        lines.append(f"  上期偏差总额：{history_total:,.0f} 元")
        lines.append(f"  变化趋势：{trend} - {trend_desc}")
    else:
        lines.append(f"  变化趋势：{trend_desc}")
    lines.append("")
    
    # 主要贡献车间
    lines.append("【主要贡献车间 Top 2】")
    lines.extend(workshop_lines)
    lines.append("")
    
    # 主要贡献物料
    lines.append("【主要贡献物料大类 Top 2】")
    lines.extend(material_lines)
    lines.append("")
    
    # 免责声明
    lines.append("-" * 50)
    lines.append("⚠️ 免责声明：本报告基于历史数据统计，仅供参考，不构成决策依据。")
    lines.append("=" * 50)
    
    return "\n".join(lines)


def _find_column(df: pd.DataFrame, candidates: list) -> Optional[str]:
    """查找存在的列名"""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def generate_summary_html(current_df: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> str:
    """生成 HTML 格式的报告（用于窗口展示）"""
    text = generate_summary(current_df, history_df)
    # 简单转换：换行转为 <br>
    html = text.replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: '微软雅黑', sans-serif; padding: 20px; }}
        .title {{ font-size: 18px; font-weight: bold; text-align: center; margin-bottom: 20px; }}
        .section {{ margin: 15px 0; }}
        .section-title {{ font-weight: bold; color: #333; }}
        .disclaimer {{ color: #666; font-size: 12px; margin-top: 20px; border-top: 1px solid #ccc; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="content">
        {html.replace("【", "<div class='section'><div class='section-title'>").replace("】", "</div>")}
    </div>
</body>
</html>
"""
