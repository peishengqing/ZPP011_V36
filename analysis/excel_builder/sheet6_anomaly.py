#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet6_anomaly.py — Sheet6 异常预警（v36 抽取，未修改逻辑）
"""
import pandas as pd
from analysis.excel_builder.write_sheet_util import ensure_numeric_cols


def build_sheet6(df, alt_order_mat, report_progress, progress_idx=6, net_offset_map=None):
    """
    构建 Sheet6 异常预警 DataFrame
    参数:
        df: 主数据 DataFrame
        alt_order_mat: 替代料订单-物料集合 set of (订单号, 物料描述)
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认6）
        net_offset_map: 净偏差查找表 {(流程订单, 物料编码): (净偏差数量, 净偏差金额)}
    返回:
        anomaly_df: 异常预警 DataFrame
    """
    report_progress(progress_idx, "Sheet6-异常预警", 0)

    # ① 无定额标志缺省保护（独立测试时可能无该列）
    if '_no_quota' not in df.columns:
        df['_no_quota'] = False
    else:
        df['_no_quota'] = df['_no_quota'].fillna(False).astype(bool)

    col_p = '偏差率(%)'
    # 异常5 替代料残差阈值：0 = 只要偏差率≠0(存在净残差)就报，与「完整偏差明细」同口径
    # （原为 5.0，即 |偏差率|>5% 才报；2026-07-24 应业务要求放开为所有真实偏差）
    dyn_thresh = 0.0

# 确保数值列为数值类型（防止字符串导致比较错误）
    ensure_numeric_cols(df, ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"])
    anomaly1 = df[(df['数量-定额'] > 0) & (df['备注原因'] == '系统无定额')].copy()
    anomaly2 = df[(df['数量-定额'] > 0) & (df['数量-实际'] <= 0) &
                  (~(df['备注原因'].notna() & (df['备注原因'] != '')))].copy()
    anomaly3 = df[(df['数量-定额'] > 0) & (df['数量-实际'] == 0) &
                  (df['备注原因'].notna()) & (df['备注原因'] != '')].copy()
    # ① 排除无定额（数量-定额==0）的假性 ±100% 偏差，避免刷屏
    anomaly4 = df[(df['物料分类'] == '包材') & (df[col_p] < 0) & (~df['_no_quota'])].copy()
    anomaly5 = df[df['_is_alt'] & (df[col_p].notna()) & (abs(df[col_p]) > dyn_thresh) & (
        ~df['_no_quota'])].copy()

    def _get_product_no(r):
        return str(r.get('产品物料号码', '')) if pd.notna(r.get('产品物料号码', '')) else ''

    def _get_product_desc(r):
        return str(r.get('产品物料描述', '')) if pd.notna(r.get('产品物料描述', '')) else ''

    def _net_amt(r):
        v = r.get('偏差金额(含税)', r.get('偏差金额', 0))
        return round(v, 2) if pd.notna(v) else 0

    def _net_qty(r):
        """从 net_offset_map 获取净偏差数量，回退到材料偏差"""
        if net_offset_map:
            key = (str(r.get('流程订单', '')), str(r.get('组件物料号', '')))
            vals = net_offset_map.get(key)
            if vals and pd.notna(vals[0]):
                return round(float(vals[0]), 2)
        return r['材料偏差']

    def _net_amt_lookup(r):
        """从 net_offset_map 获取净偏差金额，回退到原始计算"""
        if net_offset_map:
            key = (str(r.get('流程订单', '')), str(r.get('组件物料号', '')))
            vals = net_offset_map.get(key)
            if vals and pd.notna(vals[1]):
                return round(float(vals[1]), 2)
        return _net_amt(r)

    def _net_rate(r):
        """计算净偏差率 = 净偏差数量 / 定额 * 100"""
        net_qty = _net_qty(r)
        quota = r.get('数量-定额', 0)
        try:
            quota = float(quota)
            if abs(quota) < 0.001:
                return 0.0
            return round(float(net_qty) / quota * 100, 2)
        except (ValueError, TypeError):
            return 0.0

    anomaly_rows = []

    for idx_r, r in anomaly1.iterrows():
        key = (str(r['流程订单']), str(r['组件物料描述']))
        is_alt = key in alt_order_mat
        anomaly_rows.append({
            '订单开始日期': pd.Timestamp(r['订单开始日期']).strftime('%Y-%m-%d'),
            '订单类型': r['订单类型'] if '订单类型' in r and pd.notna(r['订单类型']) else '',
            '流程订单': r['流程订单'],
            '异常类型': '异常1',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '产品物料号码': _get_product_no(r),
            '产品物料描述': _get_product_desc(r),
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '净偏差数量': _net_qty(r),
            '净偏差金额': _net_amt_lookup(r),
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '净偏差率': f"{_net_rate(r):.1f}%" if pd.notna(_net_rate(r)) else '',
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
            '订单类型': r['订单类型'] if '订单类型' in r and pd.notna(r['订单类型']) else '',
            '流程订单': r['流程订单'],
            '异常类型': '异常2',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '产品物料号码': _get_product_no(r),
            '产品物料描述': _get_product_desc(r),
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '净偏差数量': _net_qty(r),
            '净偏差金额': _net_amt_lookup(r),
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '净偏差率': f"{_net_rate(r):.1f}%" if pd.notna(_net_rate(r)) else '',
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
            '订单类型': r['订单类型'] if '订单类型' in r and pd.notna(r['订单类型']) else '',
            '流程订单': r['流程订单'],
            '异常类型': '异常3',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '产品物料号码': _get_product_no(r),
            '产品物料描述': _get_product_desc(r),
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '净偏差数量': _net_qty(r),
            '净偏差金额': _net_amt_lookup(r),
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '净偏差率': f"{_net_rate(r):.1f}%" if pd.notna(_net_rate(r)) else '',
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
            '订单类型': r['订单类型'] if '订单类型' in r and pd.notna(r['订单类型']) else '',
            '流程订单': r['流程订单'],
            '异常类型': '异常4',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '产品物料号码': _get_product_no(r),
            '产品物料描述': _get_product_desc(r),
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '净偏差数量': _net_qty(r),
            '净偏差金额': _net_amt_lookup(r),
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '净偏差率': f"{_net_rate(r):.1f}%" if pd.notna(_net_rate(r)) else '',
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
            '订单类型': r['订单类型'] if '订单类型' in r and pd.notna(r['订单类型']) else '',
            '流程订单': r['流程订单'],
            '异常类型': '异常5',
            '工厂': r['工厂名称'],
            '车间': r['车间'],
            '原表行号': r['_excel_row'],
            '物料编码': r['组件物料号'],
            '物料名称': r['组件物料描述'],
            '产品物料号码': _get_product_no(r),
            '产品物料描述': _get_product_desc(r),
            '单位': r['组件单位'] if pd.notna(r['组件单位']) else '',
            '定额': r['数量-定额'],
            '实际': r['数量-实际'],
            '偏差数量': r['材料偏差'],
            '净偏差数量': _net_qty(r),
            '净偏差金额': _net_amt_lookup(r),
            '偏差率': f"{r[col_p]:.1f}%" if pd.notna(r[col_p]) else '',
            '净偏差率': f"{_net_rate(r):.1f}%" if pd.notna(_net_rate(r)) else '',
            '备注': str(r['备注原因']) if pd.notna(r['备注原因']) and r['备注原因'] != '' else '',
            '标准原因': r.get('标准原因', ''),
            '异常说明': '替代料存在偏差残差，请确认是否为合理部分替代或配对有误',
            '处理建议': '替代料存在残差，请确认是否为合理部分替代或配对有误',
            'row_type': '异常5',
            '替代料': '是',
        })

    anomaly_df = pd.DataFrame(anomaly_rows)
    report_progress(progress_idx, "Sheet6-异常预警", 100)
    return anomaly_df
