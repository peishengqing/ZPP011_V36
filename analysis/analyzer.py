#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析核心逻辑（v36 抽取）
⚠️ 本文件从 main.py 原样抽取，未修改任何分析逻辑
"""

import pandas as pd
import numpy as np
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.utils import get_column_letter
from datetime import datetime
import os
import re
import glob as _glob
import sys as _sys
import threading
import time
import json
import tempfile
import subprocess
import queue
import traceback
import shutil
import sqlite3
import zipfile
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk

# 模块化组件
from storage import storage
from domain.alt_material import alt_manager

# Sheet 构建函数（第五步抽取）
from analysis.excel_builder.sheet1_summary import build_sheet1
from analysis.excel_builder.sheet2_alt import build_sheet2
from analysis.excel_builder.sheet3_no_note import build_sheet3
from analysis.excel_builder.sheet4_middle import build_sheet4
from analysis.excel_builder.sheet5_full import build_sheet5
from analysis.excel_builder.sheet6_anomaly import build_sheet6
from analysis.excel_builder.sheet7_amount import build_sheet7
from analysis.excel_builder.sheet8_reason_summary import build_sheet8
from analysis.excel_builder.sheet9_reason_detail import build_sheet9
from analysis.excel_builder.sheet10_trend import build_sheet10
from analysis.excel_builder.write_sheet_util import write_sheet


# 通用工具函数
from utils.helpers import standardize_remark


def _dprint(*args, **kwargs):
    """Safe debug print - avoids GBK Errno 22 on Windows console"""
    import sys
    if getattr(sys.stdout, 'closed', False) or sys.stdout is None:
        return
    kwargs.pop('flush', None)
    try:
        print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        pass


def do_analysis_v2(
        input_file,
        output_dir,
        alt_pairs,
        progress_callback=None,
        cancel_check=None,
        start_date=None,
        end_date=None,
        material_search=None,
        output_path=None):
    _dprint("[DEBUG do_analysis_v2] 函数开始执行")

    # ========== 数值列追踪初始化 ==========
    _trace_log = os.path.join(os.environ.get('TEMP', '.'), 'zpp011_trace.log')
    _snapshot = {}
    _dprint(f"[TRACE] 追踪日志将写入: {_trace_log}")

    def check_cancel():
        if cancel_check and cancel_check():
            raise KeyboardInterrupt("用户取消")

    def report_progress(step_idx, step_name, percent):
        if progress_callback:
            progress_callback(step_idx, step_name, percent)
            time.sleep(0.01)

    from analysis.excel_builder.write_sheet_util import get_default_styles
    _styles = get_default_styles()
    pos_fill = _styles['pos_fill']
    neg_fill = _styles['neg_fill']
    alt_fill = _styles['alt_fill']
    gx_fill = _styles['gx_fill']
    header_font = _styles['header_font']
    header_fill = _styles['header_fill']
    center = _styles['center']
    border = _styles['border']
    data_font = _styles['data_font']
    anomaly_fills = _styles['anomaly_fills']

    report_progress(0, "预处理", 30)
    check_cancel()

    src_file = input_file
    try:
        df = pd.read_excel(src_file, sheet_name='Data')
        _dprint(f"[DEBUG do_analysis_v2] 读取Data表成功，{len(df)} 行")
        # 强制刷新输出
        import sys
        sys.stdout.flush()
    except Exception as e:
        _dprint(f"❌ 读取Excel失败: {e}")
        raise
    

    # ========== 追踪点1: 读取数据后（原始状态） ==========
    _snapshot['after_read'] = {
        '数量-实际': df['数量-实际'].describe().to_dict() if '数量-实际' in df.columns else 'NOT_FOUND',
        '数量-定额': df['数量-定额'].describe().to_dict() if '数量-定额' in df.columns else 'NOT_FOUND',
        '行数': len(df)
    }
    _dprint(f"[TRACE-1] 读取后: 数量-实际 sum={df['数量-实际'].sum() if '数量-实际' in df.columns else 'N/A'}")

    # ========== 诊断：找出哪个数值列被字符串污染 ==========
    # 使用文件日志（避免输出被吞掉）
    _diag_log = os.path.join(os.environ.get('TEMP', '.'), 'zpp011_diagnostic.log')
    with open(_diag_log, 'w', encoding='utf-8') as _f:
        _f.write(f"=== 诊断开始 {pd.Timestamp.now()} ===\n")
        _f.write(f"文件: {src_file}\n")
        _f.write(f"行数: {len(df)}\n")
        _f.write(f"列名: {list(df.columns)}\n\n")
    
    _dprint(f"[诊断] 正在检查数值列，日志写入: {_diag_log}")
    print("[诊断] 检查数值列中的字符串...")
    numeric_cols_check = [
        '数量-定额', '数量-实际', '材料偏差', '偏差率(%)',
        '金额-定额(含税)', '金额-实际(含税)', '实际成本', '产量', '组件数量'
    ]
    for col in numeric_cols_check:
        if col in df.columns:
            try:
                # 找出非数值的行（包括字符串）
                mask = ~df[col].apply(lambda x: isinstance(x, (int, float)) or pd.isna(x))
                if mask.any():
                    bad_vals = df.loc[mask, col].unique()[:5]
                    print(f"⚠️ 列 [{col}] 包含非数值：{bad_vals}")
                    # 同时打印对应的物料名称和订单号，便于定位
                    sample_rows = df.loc[mask].head(3)
                    if all(c in df.columns for c in ['流程订单', '组件物料描述', col]):
                        print(f" 示例行：{sample_rows[['流程订单', '组件物料描述', col]].to_dict(orient='records')}")
            except Exception as e:
                print(f"⚠️ 检查列 [{col}] 时出错: {e}")
    print("[诊断] 数值列检查完成")
    
    # 同时写入诊断日志文件
    with open(_diag_log, 'a', encoding='utf-8') as _f:
        _f.write(f"\n=== 数值列检查完成 ===\n")
        _f.write(f"df.shape: {df.shape}\n")
        _f.write(f"数值列检查: 完成\n\n")
        _f.write(f"'组件单位' in df.columns: {'组件单位' in df.columns}\n")

    # 保留原始 Excel 行号：用 openpyxl 读取真实行号（避免 pandas read_excel 跳过空行导致偏移）
    try:
        from openpyxl import load_workbook
        _wb = load_workbook(src_file, read_only=True, data_only=True)
        _ws = _wb['Data']
        _real_rows = []
        _rn = 0
        for _row in _ws:
            _rn += 1
            if _rn == 1:
                continue  # 跳过表头
            _real_rows.append(_rn)
        _wb.close()
        if len(_real_rows) == len(df):
            df.insert(0, '_excel_row', _real_rows)
        else:
            # 行数不匹配时回退到计算方式
            df.insert(0, '_excel_row', range(2, len(df) + 2))
    except Exception:
        df.insert(0, '_excel_row', range(2, len(df) + 2))

    # ========== 强制转换数值列，防止字符串混入 ==========
    numeric_cols = [
        '数量-定额', '数量-实际', '材料偏差', '偏差率(%)',
        '金额-定额(含税)', '金额-实际(含税)', '实际成本', '产量', '组件数量'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    col_p = '偏差率(%)'

    # ── 固定阈值（公司规定）─────────────────────
    dyn_thresh = 10.0
    thresh_desc = "固定阈值（公司规定）：±10%"
    df['_dyn_thresh'] = dyn_thresh

    # 确保日期列是datetime类型
    df['订单开始日期'] = pd.to_datetime(df['订单开始日期'], errors='coerce')

    # 新增：日期范围过滤
    if start_date:
        try:
            sd = pd.to_datetime(start_date)
            df = df[df['订单开始日期'] >= sd]
            report_progress(0, "日期过滤", 100)
            if progress_callback:
                progress_callback(-1, f"已按开始日期 {start_date} 过滤", 0)
        except BaseException:
            pass

    if end_date:
        try:
            ed = pd.to_datetime(end_date)
            df = df[df['订单开始日期'] <= ed]
            report_progress(0, "日期过滤", 100)
            if progress_callback:
                progress_callback(-1, f"已按结束日期 {end_date} 过滤", 0)
        except BaseException:
            pass

    # 新增：物料搜索过滤（编码或名称）
    if material_search:
        search_lower = material_search.lower()
        # 智能列名匹配
        code_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['组件物料号', '组件编码', '物料编码', 'code', '编码', 'mat', 'material'])]
        name_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['组件描述', '物料描述', '名称', 'name', '描述', 'desc', 'description'])]

        if not code_cols and not name_cols:
            report_progress(0, "物料过滤", 100)
            if progress_callback:
                progress_callback(-1, f"⚠ 未找到编码/名称列，跳过搜索", 0)
        else:
            # 构建mask
            mask = None
            if code_cols:
                mask = df[code_cols[0]].astype(str).str.lower().str.contains(search_lower, na=False)
            if name_cols:
                name_mask = df[name_cols[0]].astype(str).str.lower().str.contains(search_lower, na=False)
                mask = name_mask if mask is None else (mask | name_mask)

            df = df[mask]
            report_progress(0, "物料过滤", 100)
            if progress_callback:
                used_cols = []
                if code_cols: used_cols.append(f"编码列={code_cols[0]}")
                if name_cols: used_cols.append(f"名称列={name_cols[0]}")
                progress_callback(
                    -1, f"已按物料搜索 '{material_search}' 过滤，剩余 {len(df)} 行（{', '.join(used_cols)}）", 0)

    # 优先使用用户输入的日期范围，否则使用数据中的日期范围
    if start_date and end_date:
        # 用户指定了日期范围
        date_min = pd.to_datetime(start_date)
        date_max = pd.to_datetime(end_date)
    elif start_date:
        date_min = pd.to_datetime(start_date)
        date_max = df['订单开始日期'].max()
    elif end_date:
        date_min = df['订单开始日期'].min()
        date_max = pd.to_datetime(end_date)
    else:
        # 没有用户输入，使用数据中的日期范围
        date_min = df['订单开始日期'].min()
        date_max = df['订单开始日期'].max()

    date_range = f"{pd.Timestamp(date_min).strftime('%Y%m%d')}-{pd.Timestamp(date_max).strftime('%m%d')}"
    _dprint(f"[DEBUG do_analysis_v2] 日期范围：{date_range}")
    
    report_progress(0, "预处理", 100)

    def classify_material(row):
        mtype = row['组件物料类型']
        mtype_desc = row['组件物料类型描述']
        if mtype in ('Z002', 'Z009'):
            return '包材'
        elif mtype == 'Z004':
            return '原材料'
        elif mtype_desc and '半成品' in str(mtype_desc):
            return '半成品'
        return '原材料'

    df['物料分类'] = df.apply(classify_material, axis=1)
    df['组件物料号_str'] = df['组件物料号'].astype(str)

    gx_mask = df['组件物料号_str'].str.startswith('6')
    no_note_mask = ~(df['备注原因'].notna() & (df['备注原因'] != ''))
    dev_rate = df[col_p].fillna(0)
    raw_mat_mask = df['物料分类'].isin(['原材料', '包材'])
    small_dev_mask = dev_rate.between(-3, 3)
    no_auto_mask = raw_mat_mask & small_dev_mask

    gx_auto_fill = gx_mask & no_note_mask & ~no_auto_mask
    df.loc[gx_auto_fill, '备注原因'] = '系统无定额'

    tape_mask = df['组件物料描述'].str.contains('透明胶带', na=False)
    tape_auto_fill = tape_mask & no_note_mask & ~no_auto_mask
    df.loc[tape_auto_fill, '备注原因'] = '系统无定额'

    # ========== 数值列保护（自动填充后） ==========
    _numeric_cols = ['数量-定额', '数量-实际', '材料偏差', '偏差率(%)',
                    '金额-定额(含税)', '金额-实际(含税)', '实际成本', '产量', '组件数量']
    for _col in _numeric_cols:
        if _col in df.columns:
            _before = df[_col].dtype
            df[_col] = pd.to_numeric(df[_col], errors='coerce').fillna(0)
            _after = df[_col].dtype
            if _before != _after:
                print(f"[数值保护] 列 [{_col}] 已转换: {_before} → {_after}")
    
    df['_note_source'] = '人工填写'

    # DeepSeek版：标注标准原因列
    df['标准原因'] = df['备注原因'].apply(standardize_remark) if '备注原因' in df.columns else '未填写'

    df.loc[df['备注原因'].isna() | (df['备注原因'] == ''), '_note_source'] = '无'
    df.loc[gx_auto_fill, '_note_source'] = '系统无定额(广宣)'
    df.loc[tape_auto_fill, '_note_source'] = '自动填充'

    df['车间'] = df['生产管理员描述'].apply(lambda x: str(x).strip())

    # ========== 数值列保护（偏差计算前） ==========
    for _col in ['金额-实际(含税)', '金额-定额(含税)']:
        if _col in df.columns:
            _before = df[_col].dtype
            df[_col] = pd.to_numeric(df[_col], errors='coerce').fillna(0)
            _after = df[_col].dtype
            if _before != _after:
                print(f"[数值保护-计算前] 列 [{_col}] 已转换: {_before} → {_after}")
    
    # ========== 偏差金额计算（优先使用含税金额直接相减） ==========
    if '金额-实际(含税)' in df.columns and '金额-定额(含税)' in df.columns:
        # 方法1：直接相减（推荐，最准确）
        df['偏差金额(含税)'] = (df['金额-实际(含税)'] - df['金额-定额(含税)']).round(2)
        print(f"[偏差金额计算] 使用含税金额直接相减，非零偏差行数: {(df['偏差金额(含税)'] != 0).sum()}")
    else:
        # 方法2：降级使用材料偏差 × 单价（兼容旧格式）
        for col in ['金额-实际(含税)', '金额-定额(含税)']:
            if col not in df.columns:
                print(f"⚠️ 当前文件缺少[{col}]列，相关计算将按0处理")
                df[col] = 0.0
        df['_unit_price_tax'] = 0.0
        valid_mask_actual = (df['数量-实际'] > 0) & (df['金额-实际(含税)'] > 0)
        valid_mask_quota = (df['数量-定额'] > 0) & (df['金额-定额(含税)'] > 0)
        df.loc[valid_mask_actual, '_unit_price_tax'] = (
            df.loc[valid_mask_actual, '金额-实际(含税)'] /
            df.loc[valid_mask_actual, '数量-实际']
        )
        missing_mask = (~valid_mask_actual) & valid_mask_quota
        df.loc[missing_mask, '_unit_price_tax'] = (
            df.loc[missing_mask, '金额-定额(含税)'] /
            df.loc[missing_mask, '数量-定额']
        )
        df['偏差金额(含税)'] = (df['材料偏差'] * df['_unit_price_tax']).round(2)
        print(f"[偏差金额计算] 使用单价计算，成功计算 {(df['_unit_price_tax'] > 0).sum()}/{len(df)} 行的单价")

    check_cancel()
    # Sheet1（第五步抽取 → analysis/sheets/sheet1_summary.py）
    summary_df = build_sheet1(df, report_progress)
    check_cancel()

    # Sheet2（第五步抽取 → analysis/sheets/sheet2_alt.py）
    # 彻底清理 alt_pairs，只保留纯物料编码字符串
    cleaned_pairs = []
    for pair in alt_pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        a, b = pair
        # 提取编码和描述：兼容三元组、二元组、纯字符串
        def get_code_and_desc(item):
            if isinstance(item, (list, tuple)):
                if len(item) >= 3:
                    code, desc = item[1], item[2]
                elif len(item) == 2:
                    code, desc = item[0], item[1]
                else:
                    code, desc = item[0], ''
            else:
                code, desc = '', str(item)
            if code is None or code == 'None': code = ''
            if desc is None or desc == 'None': desc = ''
            return str(code).strip(), str(desc).strip()

        a_code, a_desc = get_code_and_desc(a)
        b_code, b_desc = get_code_and_desc(b)
        a_match = a_desc if a_desc else a_code
        b_match = b_desc if b_desc else b_code
        if a_match and b_match:
            cleaned_pairs.append((a_match, b_match))
    # 使用清理后的配对

    # ========== 追踪点2: 预处理后（build_sheet2 前） ==========
    _snapshot['after_preprocess'] = {
        '数量-实际': df['数量-实际'].describe().to_dict() if '数量-实际' in df.columns else 'NOT_FOUND',
        '行数': len(df)
    }
    _dprint(f"[TRACE-2] 预处理后: 数量-实际 sum={df['数量-实际'].sum() if '数量-实际' in df.columns else 'N/A'}")

    alt_df, alt_order_mat = build_sheet2(df, cleaned_pairs, report_progress)
    check_cancel()

    # 构建所有替代料物料描述集合（用于强制标记）
    alt_materials_set = set()
    for pair in cleaned_pairs:
        a_desc, b_desc = pair  # cleaned_pairs 已经是 (描述, 描述) 的列表
        alt_materials_set.add(a_desc)
        alt_materials_set.add(b_desc)

    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r['订单号']), str(r['物料A'])))
        alt_order_mat.add((str(r['订单号']), str(r['物料B'])))

    # 原有的订单级替代料标记（基于 alt_order_mat）
    for idx_r, r in df.iterrows():
        key = (str(r['流程订单']), str(r['组件物料描述']))
        if key in alt_order_mat:
            df.at[idx_r, '_note_source'] = '替代料'

    # 新增：强制标记所有在 alt_materials_set 中的物料行为替代料
    mask_alt_material = df['组件物料描述'].isin(alt_materials_set)
    df.loc[mask_alt_material, '_note_source'] = '替代料'

    # 更新标准原因
    df.loc[df['_note_source'] == '替代料', '标准原因'] = '替代料'

    # 重新计算 _is_alt 标志（满足任意条件即标记）
    _order_alt = df.apply(lambda r: (str(r['流程订单']), str(r['组件物料描述'])) in alt_order_mat, axis=1)
    _mat_alt = df['组件物料描述'].isin(alt_materials_set)
    df['_is_alt'] = _order_alt | _mat_alt

    check_cancel()

    # Sheet3（第五步抽取 → analysis/sheets/sheet3_no_note.py）
    no_note_df = build_sheet3(df, report_progress)
    check_cancel()

    # Sheet4（第五步抽取 → analysis/sheets/sheet4_middle.py）
    middle_df = build_sheet4(df, alt_df, alt_pairs, report_progress)
    check_cancel()

    # Sheet5（第五步抽取 → analysis/sheets/sheet5_full.py）
    dev_df = build_sheet5(df, report_progress)

    # ========== 追踪点3: build_sheet5 后 ==========
    _snapshot['after_sheet5'] = {
        '数量-实际': df['数量-实际'].describe().to_dict() if '数量-实际' in df.columns else 'NOT_FOUND',
        '行数': len(df)
    }
    _dprint(f"[TRACE-3] build_sheet5后: 数量-实际 sum={df['数量-实际'].sum() if '数量-实际' in df.columns else 'N/A'}")

    check_cancel()

    # Sheet6（第五步抽取 → analysis/sheets/sheet6_anomaly.py）
    anomaly_df = build_sheet6(df, alt_order_mat, report_progress)
    check_cancel()

    # Sheet7（第五步抽取 → analysis/sheets/sheet7_amount.py）
    wb = Workbook()   # 原 Sheet7 代码块中创建（必需，供后续 Sheet 使用）
    build_sheet7(wb, df, report_progress)
    check_cancel()

    # Sheet8（第五步抽取 → analysis/sheets/sheet8_reason_summary.py）
    reason_summary_df = build_sheet8(df, report_progress)
    check_cancel()

    # Sheet9（第五步抽取 → analysis/sheets/sheet9_reason_detail.py）
    reason_analysis_df = build_sheet9(df, report_progress)
    check_cancel()

    # Sheet10（第五步抽取 → analysis/sheets/sheet10_trend.py）
    build_sheet10(wb, dev_df, date_min, report_progress)

    ws1 = wb.active
    ws1.title = '汇总统计'
    headers1 = ['序号', '工厂', '工厂名称', '车间', '物料分类',
                '正偏差条数', '正偏差数量', '正偏差金额(含税)',
                '负偏差条数', '负偏差数量', '负偏差金额(含税)',
                '总条数', '总数量', '总偏差金额(含税)', '备注覆盖率', '预警']
    rows1 = [[r['序号'], r['工厂'], r['工厂名称'], r['车间'], r['物料分类'],
              r['正偏差条数'], r['正偏差数量'], r['正偏差金额(含税)'],
              r['负偏差条数'], r['负偏差数量'], r['负偏差金额(含税)'],
              r['总条数'], r['总数量'], r['总偏差金额(含税)'],
              r['备注覆盖率'], r['预警']] for r in summary_df.to_dict('records')]
    write_sheet(ws1, headers1, rows1,
                [8, 10, 10, 10, 10, 12, 14, 16, 12, 14, 16, 10, 14, 16, 12, 8])

    ws2 = wb.create_sheet('替代料明细')
    headers2 = ['订单日期', '车间', '订单号', '物料A', '单位', '偏差A', '偏差率A',
                '物料B', '偏差B', '偏差率B', '净偏差', '备注']
    rows2 = [[r['订单日期'], r['车间'], r['订单号'], r['物料A'], r['单位'],
              r['偏差A'], r.get('偏差率A', ''), r['物料B'], r['偏差B'],
              r.get('偏差率B', ''), r.get('净偏差', ''), r['备注']]
             for r in alt_df.to_dict('records')]
    write_sheet(ws2, headers2, rows2,
                [14, 10, 14, 30, 8, 12, 12, 30, 12, 12, 12, 20])

    ws3 = wb.create_sheet('无备注预警')
    headers3 = ['订单日期', '工厂', '车间', '物料名称', '物料类型', '单位',
                '定额', '实际', '偏差数量', '偏差率', '偏差金额(含税)', '备注']
    rows3 = [[r['订单日期'], r['工厂'], r['车间'], r['物料名称'], r['物料类型'],
              r['单位'], r['定额'], r['实际'], r['偏差数量'], r['偏差率'],
              r['偏差金额(含税)'] if isinstance(r.get('偏差金额(含税)'), (int, float)) and r['偏差金额(含税)'] != 0 else '-',
              r['备注']] for r in no_note_df.to_dict('records')]
    write_sheet(ws3, headers3, rows3,
                [14, 10, 10, 28, 10, 8, 12, 12, 12, 10, 16, 20])

    ws4 = wb.create_sheet('中间地带明细')
    headers4 = ['订单日期', '工厂', '车间', '物料名称', '物料类型', '单位',
                '定额', '实际', '偏差数量', '偏差率', '备注']
    rows4 = [[r['订单日期'], r['工厂'], r['车间'], r['物料名称'], r['物料类型'],
              r['单位'], r['定额'], r['实际'], r['偏差数量'], r['偏差率'],
              r['备注']] for r in middle_df.to_dict('records')]
    write_sheet(ws4, headers4, rows4,
                [14, 10, 10, 28, 10, 8, 12, 12, 12, 10, 20])

    ws5 = wb.create_sheet('完整偏差明细')
    headers5 = ['订单日期', '流程订单', '工厂', '车间', '物料类型', '原表行号',
                '物料编码', '物料名称', '单位', '定额', '实际',
                '偏差数量', '偏差率', '偏差金额', '是否替代料', '备注', '备注来源', '偏差区间']
    rows5 = [[r['订单日期'], r.get('流程订单', ''), r['工厂'], r['车间'], r['物料类型'], r['原表行号'],
              r['物料编码'], r['物料名称'], r['单位'], r['定额'], r['实际'],
              r['偏差数量'], r['偏差率'], r['偏差金额'],
              '是' if r.get('_is_alt', False) else '否',
              r['备注'], r['备注来源'], r['偏差区间']] for r in dev_df.to_dict('records')]
    write_sheet(ws5, headers5, rows5,
                [14, 16, 10, 10, 10, 10, 16, 28, 8, 12, 12, 12, 10, 14, 20, 16, 10])

    for i, r in enumerate(dev_df.to_dict('records'), 2):
        dev_qty = r['偏差数量']
        if isinstance(dev_qty, (int, float)) and dev_qty != 0:
            fill = pos_fill if dev_qty > 0 else neg_fill
            for j in range(1, len(headers5) + 1):
                ws5.cell(row=i, column=j).fill = fill
        src = r['备注来源']
        if src == '替代料':
            ws5.cell(row=i, column=15).fill = alt_fill
        elif src in ('系统无定额(广宣)', '自动填充'):
            ws5.cell(row=i, column=15).fill = gx_fill

    ws6 = wb.create_sheet('异常预警')
    headers6 = ['订单开始日期', '订单号', '异常类型', '工厂', '车间',
                '原表行号', '物料编码', '物料名称', '单位', '定额', '实际',
                '偏差数量', '偏差率', '备注', '处理建议', '替代料']
    for j, h in enumerate(headers6, 1):
        c = ws6.cell(row=1, column=j, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.border = border
    ws6.cell(row=2, column=1, value='颜色说明：').font = Font(size=10, bold=True)
    legend = [
        ('异常1', '浅红', 'FFCDD2'),
        ('异常2', '浅橙', 'FFE0B2'),
        ('异常3', '浅紫', 'E1BEE7'),
        ('异常4', '浅蓝', 'B3E5FC'),
        ('异常5', '浅黄', 'FEFFD6'),
    ]
    for k, (key, label, color) in enumerate(legend, 2):
        c = ws6.cell(row=2, column=k, value=f" {label}")
        c.fill = PatternFill(start_color=color, end_color=color, fill_type='solid')
        c.font = Font(size=10, bold=True, color='FF000000')
        c.alignment = center
        ws6.column_dimensions[get_column_letter(k)].width = 10
    r_row = 3
    for r in anomaly_df.to_dict('records'):
        fill = anomaly_fills.get(r['row_type'], anomaly_fills['异常1'])
        row_vals = [
            r['订单开始日期'], r['流程订单'], r['异常类型'], r['工厂'], r['车间'],
            r['原表行号'], r['物料编码'], r['物料名称'], r['单位'],
            r['定额'], r['实际'], r['偏差数量'], r['偏差率'],
            r.get('备注', ''), r.get('处理建议', ''), r.get('替代料', '否')]
        for j, v in enumerate(row_vals, 1):
            c = ws6.cell(row=r_row, column=j, value=v)
            c.font = data_font
            c.border = border
            c.alignment = center
            c.fill = fill
        r_row += 1
    for j, w in enumerate([14, 18, 10, 10, 10, 10, 16, 28, 8, 12, 12, 12, 10, 16, 30, 10], 1):
        ws6.column_dimensions[get_column_letter(j)].width = w
    check_cancel()

    ws7 = wb.create_sheet('偏差原因汇总')
    ws7.merge_cells('A1:H1')
    tc = ws7.cell(row=1, column=1,
                  value=(f'ZPP011 偏差原因汇总（'
                         f'{pd.Timestamp(date_min).strftime("%Y-%m-%d")} ~ '
                         f'{pd.Timestamp(date_max).strftime("%Y-%m-%d")}）'))
    tc.font = Font(bold=True, size=12)
    tc.alignment = Alignment(horizontal='center')
    headers7 = ['工厂', '车间', '多耗', '少耗', '净偏差', '原因数',
                '原料主要原因（Top5）', '包材主要原因（Top5）']
    for j, h in enumerate(headers7, 1):
        c = ws7.cell(row=2, column=j, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.border = border
    # 对原因文本内部添加序号
    def _add_ordinal(text):
        if pd.isna(text) or not text:
            return ''
        lines = str(text).split('\n')
        circles = ['①','②','③','④','⑤','⑥','⑦','⑧','⑨','⑩']
        numbered = []
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            prefix = circles[i] if i < 10 else f'{i+1}.'
            numbered.append(f'{prefix} {line.strip()}')
        return '\n'.join(numbered)

    for i, r in enumerate(reason_summary_df.to_dict('records'), 3):
        for j, v in enumerate([r['工厂'], r['车间'], r['多耗'], r['少耗'],
                               r['净偏差'], r['原因数']], 1):
            c = ws7.cell(row=i, column=j, value=v)
            c.border = border
            c.font = Font(size=11)
            c.alignment = Alignment(vertical='top', horizontal='center')
        for col, key in [(7, '原料主要原因（Top5）'), (8, '包材主要原因（Top5）')]:
            c = ws7.cell(row=i, column=col, value=_add_ordinal(r[key]))
            c.border = border
            c.font = Font(size=11)
            c.alignment = Alignment(wrap_text=True, vertical='top', horizontal='left')
        raw_t = str(r['原料主要原因（Top5）']) if pd.notna(r['原料主要原因（Top5）']) else ''
        pkg_t = str(r['包材主要原因（Top5）']) if pd.notna(r['包材主要原因（Top5）']) else ''
        lines = sum(max(1, (len(p.strip()) + 19) // 20) for p in raw_t.split('\n') if p.strip())
        lines += sum(max(1, (len(p.strip()) + 19) // 20) for p in pkg_t.split('\n') if p.strip())
        ws7.row_dimensions[i].height = max(lines * 16, 67)
    for col, w in zip(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
                      [14, 10, 14, 14, 14, 10, 55, 55]):
        ws7.column_dimensions[col].width = w

    ws8 = wb.create_sheet('偏差原因分析')
    headers8 = ['工厂', '车间', '物料分类', '备注原因', '原始备注示例',
                '涉及物料数', '多耗', '少耗', '净偏差', '涉及物料']
    rows8 = [[r['工厂'], r['车间'], r['物料分类'], r['备注原因'],
              r['原始备注示例'], r['涉及物料数'], r['多耗'], r['少耗'],
              r['净偏差'], r['涉及物料']] for r in reason_analysis_df.to_dict('records')]
    write_sheet(ws8, headers8, rows8,
                [14, 10, 10, 20, 25, 10, 14, 14, 14, 80])

    # 如果用户指定了输出路径，直接使用；否则自动生成
    if output_path:
        final_output_path = output_path
    else:
        pattern = os.path.join(output_dir, f'ZPP011偏差分析最终版_{date_range}_v*.xlsx')
        existing = _glob.glob(pattern)
        versions = [int(re.search(r'_v(\d+)\.xlsx$', os.path.basename(f)).group(1))
                    for f in existing if re.search(r'_v(\d+)\.xlsx$', os.path.basename(f))]
        next_ver = max(versions) + 1 if versions else 1
        final_output_path = os.path.join(
            output_dir,
            f'ZPP011偏差分析最终版_{date_range}_v{next_ver:02d}.xlsx')

    report_progress(11, "生成Excel", 50)

    # ── 分析说明 sheet ────────────────────────────
    ws_info = wb.create_sheet('📋 分析说明', index=0)
    info_rows = [
        ['ZPP011 偏差分析器 · 分析说明', ''],
        ['', ''],
        ['分析日期范围', f"{pd.Timestamp(date_min).strftime('%Y-%m-%d')} ～ {pd.Timestamp(date_max).strftime('%Y-%m-%d')}"],
        ['动态阈值方法', thresh_desc],
        ['动态阈值数值', f"±{dyn_thresh:.1f}%"],
        ['', ''],
        ['各Sheet说明', ''],
        ['汇总统计', '按车间×物料分类统计偏差条数、数量、金额、备注覆盖率'],
        ['替代料明细', '识别到的替代料配对及净偏差'],
        ['无备注预警', f'偏差率超过 ±{dyn_thresh:.1f}% 但未填备注的记录（按偏差金额降序）'],
        ['中间地带明细', f'偏差率在 ±{dyn_thresh:.1f}% 区间内（不纳入汇总统计）'],
        ['完整偏差明细', '所有偏差率超 ±1% 的记录（剔除替代料）'],
        ['异常预警', '5类异常：系统无定额、实际为0/负数、BOM问题、包材负偏差、替代料超阈值'],
        ['偏差金额分析', '按物料汇总正/负偏差金额（含税）'],
        ['偏差原因汇总', '按车间汇总原因 Top5（备注已自动标准化）'],
        ['偏差原因分析', '按标准原因类别汇总分析'],
        ['趋势分析', '按自然日均分三段（早期/中期/近期），计算各段平均偏差率并判断趋势'],
    ]
    for i, row in enumerate(info_rows, 1):
        for j, v in enumerate(row, 1):
            c = ws_info.cell(row=i, column=j, value=v)
            if i == 1:
                c.font = Font(bold=True, size=14, color='1B5E20')
                c.alignment = Alignment(horizontal='left', vertical='center')
            elif i == 7:
                c.font = Font(bold=True, size=11)
            elif i > 7:
                c.font = Font(size=11)
                if j == 1:
                    c.font = Font(bold=True, size=11)
        ws_info.row_dimensions[i].height = 22
        ws_info.column_dimensions['A'].width = 28
        ws_info.column_dimensions['B'].width = 62

    _dprint(f"[DEBUG do_analysis_v2] 准备保存到：{final_output_path}")
    try:
        wb.save(final_output_path)
    except PermissionError as e:
        raise PermissionError(
            f"无法保存文件，可能被其他程序占用！\n\n"
            f"文件路径：{final_output_path}\n\n"
            f"可能的原因：\n"
            f"  1. 文件已用 Excel 打开，请先关闭 Excel 中的这个文件\n"
            f"  2. 文件被其他程序占用（如 WPS、预览窗口等）\n"
            f"  3. 没有写入权限\n\n"
            f"解决方法：\n"
            f"  • 关闭 Excel 中打开的这个文件，然后重试\n"
            f"  • 或者换一个输出文件名（在弹出的另存为对话框中修改文件名）"
        ) from e
    report_progress(11, "生成Excel", 100)
    # 返回实际保存的路径
    _dprint(f"[DEBUG do_analysis_v2] 保存完成，返回：{final_output_path}")
    # ========== 保存追踪日志 ==========
    try:
        with open(_trace_log, 'a', encoding='utf-8') as f:
            f.write(f"\n=== Trace Log {datetime.now()} ===\n")
            f.write(f"Input file: {src_file}\n")
            f.write(json.dumps(_snapshot, indent=2, ensure_ascii=False, default=str))
            f.write('\n')
        _dprint(f"[TRACE] 日志已保存到: {_trace_log}")
    except Exception as e:
        _dprint(f"[TRACE] 保存日志失败: {e}")

    return final_output_path
def _build_deviation_summary(dev_df, orig_df):
    """
    构建偏差金额汇总表（Sheet: 偏差金额分析）
    dev_df: 完整偏差明细 DataFrame
    orig_df: 原始数据 DataFrame（用于获取单价等额外信息，可选）
    """
    # 按物料编码汇总偏差金额
    if '偏差金额' not in dev_df.columns:
        # 如果没有偏差金额列，尝试计算
        if '数量-实际' in dev_df.columns and '数量-定额' in dev_df.columns:
            # 计算单价（从原始数据获取，这里简单处理）
            dev_df['偏差金额'] = (dev_df['数量-实际'] - dev_df['数量-定额']) * dev_df.get('单价', 0)
        else:
            dev_df['偏差金额'] = 0.0
    
    # 按物料编码、物料名称、物料类型分组
    group_cols = []
    for col in ['物料编码', '物料名称', '物料类型']:
        if col in dev_df.columns:
            group_cols.append(col)
    if not group_cols:
        group_cols = ['物料编码']
    
    summary = dev_df.groupby(group_cols).agg(
        正偏差金额=('偏差金额', lambda x: x[x > 0].sum()),
        负偏差金额=('偏差金额', lambda x: x[x < 0].sum()),
        总偏差金额=('偏差金额', 'sum'),
        涉及条数=('偏差金额', 'count')
    ).reset_index()
    
    # 格式化金额（保留两位小数）
    for col in ['正偏差金额', '负偏差金额', '总偏差金额']:
        summary[col] = summary[col].round(2)
    
    # 添加单位（如果有）
    if '单位' in dev_df.columns:
        unit_map = dev_df.groupby('物料编码')['单位'].first().to_dict()
        summary['单位'] = summary['物料编码'].map(unit_map)
    
    # 按总偏差金额绝对值排序（降序）
    summary = summary.sort_values('总偏差金额', key=abs, ascending=False)
    
    return summary