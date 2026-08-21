#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet5_full.py — Sheet5 完整偏差明细（v36 抽取，未修改逻辑）
"""
import pandas as pd
from analysis.excel_builder.write_sheet_util import ensure_numeric_cols
import numpy as np


def build_sheet5(df, report_progress, progress_idx=5, threshold=1.0):
    """
    构建 Sheet5 完整偏差明细 DataFrame
    参数:
        df: 主数据 DataFrame
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认5）
    返回:
        dev_df: 完整偏差明细 DataFrame
    """
    report_progress(progress_idx, "Sheet5-完整偏差明细", 0)

    col_p = '偏差率(%)'
# 确保数值列为数值类型（防止字符串导致比较错误）
    ensure_numeric_cols(df, ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"])
    has_real_dev = df[df[col_p].abs() >= threshold].copy()

    # 计算偏差金额（含税）
    if '单价' in has_real_dev.columns and has_real_dev['单价'].notna().any():
        has_real_dev['_偏差金额'] = has_real_dev['材料偏差'] * has_real_dev['单价'] * 1.13
    elif '金额-实际(含税)' in has_real_dev.columns and '数量-实际' in has_real_dev.columns:
        # 反算单价：金额-实际(含税) / 数量-实际
        unit_price = has_real_dev['金额-实际(含税)'] / has_real_dev['数量-实际'].replace(0, np.nan)
        unit_price = unit_price.fillna(0)
        has_real_dev['_偏差金额'] = has_real_dev['材料偏差'] * unit_price
    else:
        has_real_dev['_偏差金额'] = 0.0

    # 备注列：优先取原始备注，其次取备注原因（向量化，原 apply(axis=1)，2026-07-27 性能优化）
    has_real_dev = has_real_dev.copy()
    _remark = pd.Series('', index=has_real_dev.index)
    for _col in ['备注原因', '备注']:  # 倒序遍历，后者（备注）覆盖前者 → 优先级：备注 > 备注原因
        if _col in has_real_dev.columns:
            _v = has_real_dev[_col]
            _mask = _v.notna() & (_v.astype(str).str.strip() != '')
            _remark[_mask] = _v[_mask].astype(str)
    has_real_dev['_备注'] = _remark

    # 向量化构建（原 iterrows 列表推导，2026-07-27 性能优化）
    if has_real_dev.empty:
        # 防御：返回带完整列结构的空表，而非 pd.DataFrame([])。
        # 否则下游(df['流程订单']/主表展示/自动已读)在空结果时会 KeyError。
        dev_df = pd.DataFrame(columns=[
            '订单日期', '订单类型', '流程订单', '工厂', '车间', '物料类型',
            '原表行号', '产品物料号码', '产品物料描述', '产量', '产量单位', '物料编码', '物料名称',
            '单位', '定额', '实际', '偏差数量', '偏差率', '偏差率(%)',
            '偏差金额', '备注', '备注来源', '偏差区间',
            '组件物料类型', '组件物料类型描述',
        ])
    else:
        dev_df = pd.DataFrame(index=has_real_dev.index)
        dev_df['订单日期'] = pd.to_datetime(has_real_dev['订单开始日期'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        if '订单类型' in has_real_dev.columns:
            dev_df['订单类型'] = has_real_dev['订单类型'].fillna('')
        else:
            dev_df['订单类型'] = ''
        dev_df['流程订单'] = has_real_dev['流程订单']
        dev_df['工厂'] = has_real_dev['工厂名称']
        dev_df['车间'] = has_real_dev['车间']
        dev_df['物料类型'] = has_real_dev['物料分类']
        dev_df['原表行号'] = has_real_dev['_excel_row']
        dev_df['产品物料号码'] = has_real_dev['产品物料号码'] if '产品物料号码' in has_real_dev.columns else ''
        dev_df['产品物料描述'] = has_real_dev['产品物料描述'] if '产品物料描述' in has_real_dev.columns else ''
        dev_df['产量'] = pd.to_numeric(has_real_dev['产量'], errors='coerce') if '产量' in has_real_dev.columns else pd.Series([np.nan] * len(has_real_dev))
        dev_df['产量单位'] = has_real_dev['产量单位'].astype(str).fillna('') if '产量单位' in has_real_dev.columns else ''
        dev_df['物料编码'] = has_real_dev['组件物料号']
        dev_df['物料名称'] = has_real_dev['组件物料描述']
        dev_df['单位'] = has_real_dev['组件单位'].fillna('')
        dev_df['定额'] = has_real_dev['数量-定额']
        dev_df['实际'] = has_real_dev['数量-实际']
        dev_df['偏差数量'] = has_real_dev['材料偏差']
        dev_df['偏差率'] = has_real_dev[col_p].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else '')
        # 注意：必须用 Python round（银行家舍入的正确实现），np/pandas 的 .round(2)
        # 在 .xx5 边界值上会因浮点缩放误差产生 ±0.01 差异（实测 12527 行中 371 行不同）
        dev_df['偏差率(%)'] = has_real_dev[col_p].map(
            lambda x: round(float(x), 2) if pd.notna(x) else 0.0)
        dev_df['偏差金额'] = has_real_dev['_偏差金额'].map(
            lambda x: round(x, 2) if isinstance(x, (int, float)) else 0)
        dev_df['备注'] = has_real_dev['_备注']
        dev_df['备注来源'] = has_real_dev['_note_source'] if '_note_source' in has_real_dev.columns else '人工填写'
        dev_df['偏差区间'] = np.where(pd.to_numeric(has_real_dev[col_p], errors='coerce') > 0, '正偏差', '负偏差')
        dev_df['组件物料类型'] = has_real_dev['组件物料类型'].fillna('') if '组件物料类型' in has_real_dev.columns else ''
        dev_df['组件物料类型描述'] = has_real_dev['组件物料类型描述'].fillna('') if '组件物料类型描述' in has_real_dev.columns else ''
        dev_df = dev_df.reset_index(drop=True)

    report_progress(progress_idx, "Sheet5-完整偏差明细", 100)
    return dev_df
