#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析报告生成器（基于企业级模板）
使用原版 AdvancedPPTGenerator 的样式和功能，数据源为 ZPP011 分析结果 Excel。
"""
import os
import sys
import datetime
from pathlib import Path
import pandas as pd

# 导入原版生成器（假设已保存为 core/ppt_enterprise_generator.py）
try:
    from core.ppt_enterprise_generator import AdvancedPPTGenerator
except ImportError:
    # 如果原版文件不存在，请先保存原版脚本
    raise ImportError("请先将原版脚本保存为 core/ppt_enterprise_generator.py")

# ========== 数据读取 ==========
def _load_zpp011_data(excel_path):
    """从 ZPP011 分析结果 Excel 中提取关键数据"""
    xl = pd.ExcelFile(excel_path)
    sheets = xl.sheet_names
    data = {}
    if '汇总统计' in sheets:
        data['summary'] = pd.read_excel(excel_path, sheet_name='汇总统计')
    if '完整偏差明细' in sheets:
        data['detail'] = pd.read_excel(excel_path, sheet_name='完整偏差明细')
    if '替代料明细' in sheets:
        data['alt'] = pd.read_excel(excel_path, sheet_name='替代料明细')
    if '偏差原因分析' in sheets:
        data['cause'] = pd.read_excel(excel_path, sheet_name='偏差原因分析')
    return data

# ========== 报告生成 ==========
def generate_zpp011_report(excel_path, output_path):
    """
    生成 ZPP011 偏差分析报告（使用企业级模板）
    excel_path: 分析结果 Excel 文件路径
    output_path: 输出 PPT 路径
    """
    data = _load_zpp011_data(excel_path)
    summary = data.get('summary')
    detail = data.get('detail')
    alt = data.get('alt')
    cause = data.get('cause')

    if summary is None or detail is None:
        raise ValueError("Excel 缺少必要的 Sheet（汇总统计或完整偏差明细）")

    # 1. 计算核心指标
    total_rows = int(summary['总条数'].sum())
    pos_cnt = int(summary['正偏差条数'].sum())
    neg_cnt = int(summary['负偏差条数'].sum())
    pos_amount = summary['正偏差金额(含税)'].sum()
    neg_amount = abs(summary['负偏差金额(含税)'].sum())
    net_amount = pos_amount - neg_amount
    # 备注覆盖率（加权）
    rate_col = summary['备注覆盖率']
    rates = rate_col.astype(str).str.replace('%', '').astype(float) / 100
    weights = summary['总条数']
    note_rate = (rates * weights).sum() / weights.sum() if weights.sum() > 0 else 0

    # 2. 创建生成器
    ppt = AdvancedPPTGenerator()
    ppt.REPORT_TITLE = "ZPP011 生产偏差分析报告"
    ppt.COMPANY_NAME = "云南达利生产基地"
    ppt.AUTHOR = "ZPP011 系统"

    # 3. 封面
    ppt.add_title_slide()

    # 4. 目录（将在最后添加）
    # 先收集章节
    sections = ["核心指标概览", "工厂与车间分析", "物料偏差排行", "替代料机制", "根因诊断", "改进行动"]
    for sec in sections:
        ppt.add_section(sec)

    # 5. 核心指标页（使用原版的 add_content_slide 或自定义KPI卡片）
    # 原版没有直接提供KPI卡片方法，但可以通过 add_content_slide 添加文本和图表
    # 这里简单使用 add_content_slide 添加指标列表
    ppt.add_content_slide(
        "核心指标概览",
        [
            f"总记录数：{total_rows:,} 条",
            f"正偏差（多耗）：{pos_cnt:,} 条，金额 {pos_amount:,.0f} 元",
            f"负偏差（少耗）：{neg_cnt:,} 条，金额 {neg_amount:,.0f} 元",
            f"净偏差：{net_amount:,.0f} 元",
            f"备注覆盖率：{note_rate:.1%}"
        ]
    )

    # 6. 工厂对比表格（如果有工厂列）
    factory_col = next((c for c in ['工厂', '工厂名称'] if c in summary.columns), None)
    if factory_col:
        factory_data = summary.groupby(factory_col).agg({
            '总条数': 'sum',
            '正偏差金额(含税)': 'sum',
            '负偏差金额(含税)': lambda x: abs(x.sum())
        }).reset_index()
        headers = ['工厂', '记录数', '正偏差(元)', '负偏差(元)']
        rows = []
        for _, r in factory_data.iterrows():
            rows.append([r[factory_col], r['总条数'], f"{r['正偏差金额(含税)']:,.0f}", f"{r['负偏差金额(含税)']:,.0f}"])
        ppt.add_table_slide("工厂维度对比", headers, rows)

    # 7. 车间偏差排行（Top10）
    workshop_col = next((c for c in ['车间', '生产管理员描述'] if c in detail.columns), None)
    if workshop_col:
        workshop_rank = detail.groupby(workshop_col)['偏差金额'].apply(lambda x: x.abs().sum()).nlargest(10).reset_index()
        workshop_rank.columns = ['车间', '偏差金额(元)']
        headers = ['车间', '偏差金额(元)']
        rows = [[r['车间'], f"{r['偏差金额(元)']:,.0f}"] for _, r in workshop_rank.iterrows()]
        ppt.add_table_slide("车间偏差金额排行(Top10)", headers, rows)

    # 8. 物料偏差排行（Top10）
    mat_col = next((c for c in ['物料编码', '组件物料号'] if c in detail.columns), None)
    if mat_col:
        mat_rank = detail.groupby(mat_col)['偏差金额'].apply(lambda x: x.abs().sum()).nlargest(10).reset_index()
        mat_rank.columns = ['物料编码', '偏差金额(元)']
        name_col = next((c for c in ['物料名称', '组件物料描述'] if c in detail.columns), None)
        if name_col:
            name_map = detail[[mat_col, name_col]].drop_duplicates()
            mat_rank = mat_rank.merge(name_map, on=mat_col, how='left')
            headers = ['物料编码', '物料名称', '偏差金额(元)']
            rows = [[r['物料编码'], r[name_col], f"{r['偏差金额(元)']:,.0f}"] for _, r in mat_rank.iterrows()]
        else:
            headers = ['物料编码', '偏差金额(元)']
            rows = [[r['物料编码'], f"{r['偏差金额(元)']:,.0f}"] for _, r in mat_rank.iterrows()]
        ppt.add_table_slide("物料偏差金额排行(Top10)", headers, rows)

    # 9. 替代料机制
    if not alt.empty:
        alt_sample = alt.head(3)
        headers = ['物料A', '偏差A(元)', '物料B', '偏差B(元)', '净偏差(元)']
        rows = []
        for _, r in alt_sample.iterrows():
            rows.append([
                r.get('物料A', '')[:20], f"{r.get('偏差金额A', 0):,.0f}",
                r.get('物料B', '')[:20], f"{r.get('偏差金额B', 0):,.0f}",
                f"{r.get('净偏差', 0):,.0f}"
            ])
        ppt.add_table_slide("替代料核对机制（示例）", headers, rows)

    # 10. 根因诊断
    if not cause.empty and '备注原因' in cause.columns:
        cause_counts = cause['备注原因'].value_counts().head(5).reset_index()
        cause_counts.columns = ['原因', '频次']
        headers = ['原因', '频次']
        rows = [[r['原因'], r['频次']] for _, r in cause_counts.iterrows()]
        ppt.add_table_slide("主要偏差原因 Top5", headers, rows)

    # 11. 改进行动（文本）
    ppt.add_content_slide(
        "分阶段改进行动",
        [
            "【立即行动（1周内）】",
            "• 强制补录无备注记录",
            "• 完善系统无定额物料",
            "• 核查领用记录异常",
            "",
            "【短期优化（1月内）】",
            "• 优化批次分摊逻辑",
            "• 加强设备维护",
            "• 规范工艺执行",
            "",
            "【中期建设（3月内）】",
            "• 替代料净偏差自动抵消",
            "• 上线实时预警看板",
            "• 实现系统领用与实际双重校验"
        ]
    )

    # 12. 目标量化
    ppt.add_content_slide(
        "预期效果与目标量化",
        [
            f"• 偏差金额降低30%（当前净偏差 {net_amount:,.0f} 元）",
            f"• 备注覆盖率从 {note_rate:.1%} 提升至 80% 以上",
            "• 异常响应时效从月度缩短至日度",
            "• 消除无备注高偏差记录，建立真实数据基础"
        ]
    )

    # 13. 目录页（放到最后，手动调整顺序）
    ppt.add_toc_slide()

    # 保存
    ppt.save(output_path)
    return output_path

if __name__ == "__main__":
    # 示例：直接运行测试
    import sys
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
        out_file = sys.argv[2] if len(sys.argv) > 2 else "ZPP011_Report.pptx"
        generate_zpp011_report(excel_file, out_file)
    else:
        print("用法: python ppt_zpp011_adapter.py <分析结果Excel路径> [输出PPT路径]")
