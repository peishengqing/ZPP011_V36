#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet6_anomaly.py — Sheet6 异常预警（v36 抽取，未修改逻辑）
"""
import pandas as pd


def build_sheet6(df, alt_order_mat, report_progress, progress_idx=6):
    """
    构建 Sheet6 异常预警 DataFrame
    参数:
        df: 主数据 DataFrame
        alt_order_mat: 替代料订单-物料集合 set of (订单号, 物料描述)
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认6）
    返回:
        anomaly_df: 异常预警 DataFrame
    """
    report_progress(progress_idx, "Sheet6-异常预警", 0)

    col_p = '偏差率(%)'
    dyn_thresh = 10.0

    anomaly1 = df[(df['数量-定额'] > 0) & (df['备注原因'] == '系统无定额')].copy()
    anomaly2 = df[(df['数量-定额'] > 0) & (df['数量-实际'] <= 0) &
                  (~(df['备注原因'].notna() & (df['备注原因'] != '')))].copy()
    anomaly3 = df[(df['数量-定额'] > 0) & (df['数量-实际'] == 0) &
                  (df['备注原因'].notna()) & (df['备注原因'] != '')].copy()
    anomaly4 = df[(df['物料分类'] == '包材') & (df[col_p] < 0)].copy()
    anomaly5 = df[df['_is_alt'] & (df[col_p].notna()) & (
        abs(df[col_p]) > dyn_thresh)].copy()

    anomaly_rows = []

    for idx_r, r in anomaly1.iterrows():
        key = (str(r['流程订单']), str(r['组件物料描述']))
        is_alt = key in alt_order_mat
        anomaly_rows.append({
            '订单开始日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
            '流程订单': r['流程订单'],
            '异常类型': '异常1',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '备注': '系统无定额',
            '异常说明': '有定额但系统标记为"系统无定额"，请确认是否实际有定额',
            '标准原因': r.get('标准原因', ''),
            '处理建议': '确认是否有定额，如有请修正备注',
            'row_type': '异常1',
            '替代料': '是' if is_alt else '否',
        })

    for idx_r, r in anomaly2.iterrows():
        key = (str(r['流程订单']), str(r['组件物料描述']))
        is_alt = key in alt_order_mat
        anomaly_rows.append({
            '订单开始日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
            '流程订单': r['流程订单'],
            '异常类型': '异常2',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '备注': '',
            '异常说明': '有定额但实际未投料，且未填备注，请人工判断是否为替代料',
            '标准原因': r.get('标准原因', ''),
            '处理建议': '人工判断：替代料→填备注；未投料→填未投料',
            'row_type': '异常2',
            '替代料': '是' if is_alt else '否',
        })

    for idx_r, r in anomaly3.iterrows():
        key = (str(r['流程订单']), str(r['组件物料描述']))
        is_alt = key in alt_order_mat
        anomaly_rows.append({
            '订单开始日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
            '流程订单': r['流程订单'],
            '异常类型': '异常3',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '备注': str(r['备注原因']),
            '异常说明': '有定额但未投料，已填备注，请确认备注是否准确',
            '标准原因': r.get('标准原因', ''),
            '处理建议': '有定额但未投料，确认备注是否准确',
            'row_type': '异常3',
            '替代料': '是' if is_alt else '否',
        })

    for idx_r, r in anomaly4.iterrows():
        key = (str(r['流程订单']), str(r['组件物料描述']))
        is_alt = key in alt_order_mat
        anomaly_rows.append({
            '订单开始日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
            '流程订单': r['流程订单'],
            '异常类型': '异常4',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '备注': str(r['备注原因']) if pd.notna(r['备注原因']) and r['备注原因'] != '' else '',
            '标准原因': r.get('标准原因', ''),
            '异常说明': '包材实际用量少于定额（负偏差），请确认是否存在损耗或记录异常',
            '处理建议': '包材负偏差，请确认是否存在损耗或记录异常',
            'row_type': '异常4',
            '替代料': '是' if is_alt else '否',
        })

    for idx_r, r in anomaly5.iterrows():
        anomaly_rows.append({
            '订单开始日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
            '流程订单': r['流程订单'],
            '异常类型': '异常5',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '备注': str(r['备注原因']) if pd.notna(r['备注原因']) and r['备注原因'] != '' else '',
            '标准原因': r.get('标准原因', ''),
            '异常说明': '替代料偏差率超过动态阈值，残差过大，请确认是否为合理部分替代或配对有误',
            '处理建议': '替代料残差过大，请确认是否为合理部分替代或配对有误',
            'row_type': '异常5',
            '替代料': '是',
        })

    anomaly_df = pd.DataFrame(anomaly_rows)
    report_progress(progress_idx, "Sheet6-异常预警", 100)
    return anomaly_df
