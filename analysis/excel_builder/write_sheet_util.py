#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
write_sheet_util.py — Excel 写入工具函数（v36 抽取，未修改逻辑）
"""
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
from config.settings import COLORS, FONTS


def get_default_styles():
    """返回默认样式对象（每次调用生成新实例，避免样式对象复用问题）"""
    c = COLORS
    header_fill = PatternFill(start_color=c['header'], end_color=c['header'], fill_type='solid')
    header_font = Font(bold=FONTS['header_bold'], size=FONTS['header_size'], color=c['white'])
    data_font = Font(size=FONTS['data_size'])
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    pos_fill = PatternFill(start_color=c['pos_fill'], end_color=c['pos_fill'], fill_type='solid')
    neg_fill = PatternFill(start_color=c['neg_fill'], end_color=c['neg_fill'], fill_type='solid')
    alt_fill = PatternFill(start_color=c['alt_fill'], end_color=c['alt_fill'], fill_type='solid')
    gx_fill = PatternFill(start_color=c['gx_fill'], end_color=c['gx_fill'], fill_type='solid')
    anomaly_fills = {
        '异常1': PatternFill(start_color=c['anomaly_1'], end_color=c['anomaly_1'], fill_type='solid'),
        '异常2': PatternFill(start_color=c['anomaly_2'], end_color=c['anomaly_2'], fill_type='solid'),
        '异常3': PatternFill(start_color=c['anomaly_3'], end_color=c['anomaly_3'], fill_type='solid'),
        '异常4': PatternFill(start_color=c['anomaly_4'], end_color=c['anomaly_4'], fill_type='solid'),
        '异常5': PatternFill(start_color=c['anomaly_5'], end_color=c['anomaly_5'], fill_type='solid'),
    }
    return {
        'header_fill': header_fill,
        'header_font': header_font,
        'data_font': data_font,
        'border': border,
        'center': center,
        'pos_fill': pos_fill,
        'neg_fill': neg_fill,
        'alt_fill': alt_fill,
        'gx_fill': gx_fill,
        'anomaly_fills': anomaly_fills,
    }


def write_sheet(ws, headers, data_rows, col_widths=None):
    """通用 Sheet 写入函数（用于 Sheet1/2/3/4/5/8）"""
    styles = get_default_styles()
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = styles['header_font']
        c.fill = styles['header_fill']
        c.alignment = styles['center']
        c.border = styles['border']
    for i, row in enumerate(data_rows, 2):
        for j, v in enumerate(row, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = styles['data_font']
            c.border = styles['border']
            c.alignment = styles['center']
    if col_widths:
        for j, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = 'A2'


def ensure_numeric_cols(df, cols):
    """将指定列转为数值型（转换失败填 0），原地修改并返回 df。
    用于消除各 sheet builder 中重复的 to_numeric 转换块。"""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df
