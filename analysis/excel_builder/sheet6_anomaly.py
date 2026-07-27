#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet6_anomaly.py — Sheet6 异常预警（v36 抽取，未修改逻辑）
"""
import pandas as pd
from analysis.excel_builder.write_sheet_util import ensure_numeric_cols


import numpy as np


def _net_qty_series(sub_df, net_offset_map):
    """向量化净偏差数量：优先查 net_offset_map，否则回退材料偏差（与旧 _net_qty 口径一致）"""
    fb = sub_df['材料偏差']
    if not net_offset_map:
        return fb.copy()
    keys = pd.Series(list(zip(sub_df['流程订单'].astype(str),
                              sub_df['组件物料号'].astype(str))), index=sub_df.index)
    qmap = {k: round(float(v[0]), 2)
            for k, v in net_offset_map.items()
            if v is not None and pd.notna(v[0])}
    q = keys.map(qmap)
    return q.fillna(fb)


def _net_amt_series(sub_df, net_offset_map):
    """向量化净偏差金额：优先查 net_offset_map，否则回退偏差金额(含税)/偏差金额（NaN→0，与旧 _net_amt 口径一致）"""
    # 用 Python round 而非 .round(2)：np 舍入在 .xx5 边界会差 ±0.01
    if '偏差金额(含税)' in sub_df.columns:
        fb = sub_df['偏差金额(含税)'].map(lambda v: round(v, 2) if pd.notna(v) else 0)
    elif '偏差金额' in sub_df.columns:
        fb = sub_df['偏差金额'].map(lambda v: round(v, 2) if pd.notna(v) else 0)
    else:
        fb = pd.Series(0, index=sub_df.index)
    if not net_offset_map:
        return fb
    keys = pd.Series(list(zip(sub_df['流程订单'].astype(str),
                              sub_df['组件物料号'].astype(str))), index=sub_df.index)
    amap = {k: round(float(v[1]), 2)
            for k, v in net_offset_map.items()
            if v is not None and pd.notna(v[1])}
    a = keys.map(amap)
    return a.fillna(fb)


def _build_anomaly_slice(sub_df, atype, alt_order_mat, net_offset_map, col_p,
                         remark, anomaly_desc, advice):
    """向量化构建单个异常类型的 DataFrame（替代原 iterrows 循环）"""
    if sub_df is None or sub_df.empty:
        return pd.DataFrame()
    res = pd.DataFrame()
    res['订单开始日期'] = pd.to_datetime(sub_df['订单开始日期'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
    res['订单类型'] = sub_df['订单类型'].fillna('').astype(str)
    res['流程订单'] = sub_df['流程订单']
    res['异常类型'] = atype
    res['工厂'] = sub_df['工厂名称']
    res['车间'] = sub_df['车间']
    res['原表行号'] = sub_df['_excel_row']
    res['物料编码'] = sub_df['组件物料号']
    res['物料名称'] = sub_df['组件物料描述']
    res['产品物料号码'] = sub_df['产品物料号码'].fillna('').astype(str)
    res['产品物料描述'] = sub_df['产品物料描述'].fillna('').astype(str)
    res['单位'] = sub_df['组件单位'].fillna('')
    res['定额'] = sub_df['数量-定额']
    res['实际'] = sub_df['数量-实际']
    res['偏差数量'] = sub_df['材料偏差']
    res['净偏差数量'] = _net_qty_series(sub_df, net_offset_map)
    res['净偏差金额'] = _net_amt_series(sub_df, net_offset_map)
    res['偏差率'] = sub_df[col_p].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else '')
    _nq = pd.to_numeric(res['净偏差数量'], errors='coerce')
    _quota = pd.to_numeric(sub_df['数量-定额'], errors='coerce')
    _quota = _quota.where(_quota.abs() >= 0.001)  # 与旧 _net_rate 一致：|定额|<0.001 → 净偏差率 0
    # 用 Python round 而非 .round(2)：np 舍入在 .xx5 边界会差 ±0.01
    res['净偏差率'] = (_nq / _quota * 100).map(
        lambda x: f"{round(float(x), 2):.1f}%" if pd.notna(x) else '0.0%')
    if isinstance(remark, str):
        res['备注'] = remark
    else:
        res['备注'] = remark.fillna('').astype(str)
    res['异常说明'] = anomaly_desc
    res['标准原因'] = sub_df['标准原因'].fillna('') if '标准原因' in sub_df.columns else ''
    res['处理建议'] = advice
    res['row_type'] = atype
    if atype == '异常5':
        res['替代料'] = '是'
    else:
        keys = pd.Series(list(zip(sub_df['流程订单'].astype(str),
                                  sub_df['组件物料描述'].astype(str))), index=sub_df.index)
        res['替代料'] = keys.isin(alt_order_mat).map({True: '是', False: '否'})
    return res


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

    # 向量化构建（原 5 个 iterrows 循环，2026-07-27 性能优化）
    anomaly_df = pd.concat([
        _build_anomaly_slice(anomaly1, '异常1', alt_order_mat, net_offset_map, col_p,
                             '系统无定额',
                             '有定额但系统标记为"系统无定额"，请确认是否实际有定额',
                             '确认是否有定额，如有请修正备注'),
        _build_anomaly_slice(anomaly2, '异常2', alt_order_mat, net_offset_map, col_p,
                             '',
                             '有定额但实际未投料，且未填备注，请人工判断是否为替代料',
                             '人工判断：替代料→填备注；未投料→填未投料'),
        _build_anomaly_slice(anomaly3, '异常3', alt_order_mat, net_offset_map, col_p,
                             anomaly3['备注原因'].fillna('').astype(str),
                             '有定额但未投料，已填备注，请确认备注是否准确',
                             '有定额但未投料，确认备注是否准确'),
        _build_anomaly_slice(anomaly4, '异常4', alt_order_mat, net_offset_map, col_p,
                             anomaly4['备注原因'].where(
                                 anomaly4['备注原因'].notna() & (anomaly4['备注原因'] != ''), '').astype(str),
                             '包材实际用量少于定额（负偏差），请确认是否存在损耗或记录异常',
                             '包材负偏差，请确认是否存在损耗或记录异常'),
        _build_anomaly_slice(anomaly5, '异常5', alt_order_mat, net_offset_map, col_p,
                             anomaly5['备注原因'].where(
                                 anomaly5['备注原因'].notna() & (anomaly5['备注原因'] != ''), '').astype(str),
                             '替代料存在偏差残差，请确认是否为合理部分替代或配对有误',
                             '替代料存在残差，请确认是否为合理部分替代或配对有误'),
    ], ignore_index=True)
    report_progress(progress_idx, "Sheet6-异常预警", 100)
    return anomaly_df
