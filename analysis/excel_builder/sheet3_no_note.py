#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet3_no_note.py — Sheet3 无备注预警（v36 抽取，未修改逻辑）
"""
import pandas as pd
from analysis.excel_builder.write_sheet_util import ensure_numeric_cols, NUMERIC_COLS
from config.settings import DEFAULT_THRESHOLD
from analysis.debug_util import dprint


def build_sheet3(df, report_progress, progress_idx=3, dyn_thresh=None):
    """
    构建 Sheet3 无备注预警 DataFrame
    参数:
        df: 主数据 DataFrame
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认3）
        dyn_thresh: 动态阈值（%），None 时回退到 DEFAULT_THRESHOLD
    返回:
        no_note_df: 无备注预警 DataFrame（按偏差金额绝对值降序）
    """
    report_progress(progress_idx, "Sheet3-无备注预警", 0)
    dprint("[DEBUG do_analysis_v2] 开始生成Sheet3")

    col_p = '偏差率(%)'
    dyn_thresh = DEFAULT_THRESHOLD if dyn_thresh is None else dyn_thresh

# 确保数值列为数值类型（防止字符串导致比较错误）
    ensure_numeric_cols(df, NUMERIC_COLS)
    has_dev = df[df['材料偏差'] != 0]
    no_note = has_dev[~(has_dev['备注原因'].notna()) &
                        (has_dev['备注原因'] != '')].copy()
    no_note = no_note[abs(no_note[col_p]) > dyn_thresh].copy()

    # 向量化构建（原 iterrows 列表推导，2026-07-27 性能优化）
    if no_note.empty:
        no_note_df = pd.DataFrame([])
    else:
        no_note_df = pd.DataFrame(index=no_note.index)
        no_note_df['订单日期'] = pd.to_datetime(no_note['订单开始日期'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        no_note_df['工厂'] = no_note['工厂名称']
        no_note_df['车间'] = no_note['车间']
        # v43.243 P1：严重度标签列。规则（按业务端最紧急优先）：
        #   🔴 完全未投料  = 定额>0 且 实际=0 且 |偏差率|>99
        #   🟠 严重偏差    = |偏差率|>=50
        #   🟡 超阈值      = |偏差率|>dyn_thresh（默认10）
        _quota = no_note['数量-定额'] if '数量-定额' in no_note.columns else 0
        _actual = no_note['数量-实际'] if '数量-实际' in no_note.columns else 0
        _rate_abs = no_note[col_p].abs()
        _is_under = (_quota > 0) & (_actual == 0) & (_rate_abs > 99)
        _is_severe = ~_is_under & (_rate_abs >= 50)
        _level = _is_under.map(lambda b: '🔴 完全未投料' if b else '')
        _level = _level.mask(_is_severe, '🟠 严重偏差')
        _level = _level.mask(~(_is_under | _is_severe), '🟡 超阈值')
        no_note_df['预警等级'] = _level.values
        no_note_df['物料名称'] = no_note['组件物料描述']
        no_note_df['物料类型'] = no_note['物料分类']
        no_note_df['单位'] = no_note['组件单位'].fillna('')
        no_note_df['定额'] = no_note['数量-定额']
        no_note_df['实际'] = no_note['数量-实际']
        no_note_df['偏差数量'] = no_note['材料偏差']
        # 性能（2026-10-01）：百分比格式化向量化（apply→round+astype），NaN→''
        no_note_df['偏差率'] = no_note[col_p].round(1).map(
            lambda x: f"{x:.1f}%" if pd.notna(x) else '')
        if '偏差金额(含税)' in no_note.columns:
            # 用 Python round 而非 .round(2)：np 舍入在 .xx5 边界会差 ±0.01
            no_note_df['偏差金额(含税)'] = no_note['偏差金额(含税)'].map(
                lambda v: round(v, 2) if pd.notna(v) and v != 0 else 0)
        else:
            no_note_df['偏差金额(含税)'] = 0
        no_note_df['标准原因'] = no_note['标准原因'] if '标准原因' in no_note.columns else ''
        no_note_df['备注'] = ''
        no_note_df = no_note_df.reset_index(drop=True)

    if no_note_df.empty:
        report_progress(progress_idx, "Sheet3-无备注预警", 100)
        return no_note_df

    # v43.243 P1：双键排序 —— 预警等级优先（🔴→🟠→🟡），同级内按 |金额| 降序
    _level_rank = {'🔴 完全未投料': 0, '🟠 严重偏差': 1, '🟡 超阈值': 2, '': 3}
    no_note_df['_level_w'] = no_note_df['预警等级'].map(_level_rank).fillna(3)
    no_note_df['_abs_amt'] = no_note_df['偏差金额(含税)'].apply(
        lambda x: abs(x) if isinstance(x, (int, float)) else 0)
    no_note_df = no_note_df.sort_values(
        ['_level_w', '_abs_amt'], ascending=[True, False]
    ).drop(['_level_w', '_abs_amt'], axis=1)

    report_progress(progress_idx, "Sheet3-无备注预警", 100)
    return no_note_df
