# -*- coding: utf-8 -*-
"""
服务工具函数 - 数据操作和辅助功能
"""

import pandas as pd
import numpy as np


def find_real_qty_col(df: pd.DataFrame) -> str:
    """查找实际数量列名"""
    candidates = ['数量-实际', '实际', '实际数量', '数量 - 实际', 'actual',
                  '实际收货数量', '已收货数量', '收货数量', '实际领用数量', '实收数量']
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        s = str(c)
        if '实际' in s and '数量' in s:
            return c
    return None


def find_remark_col(df: pd.DataFrame) -> str:
    """查找备注列名"""
    candidates = ['备注原因', '备注', '审核备注', '偏差备注', 'remark']
    for c in candidates:
        if c in df.columns:
            return c
    return None


def find_yield_col(df: pd.DataFrame) -> str:
    """查找产量列名"""
    candidates = ['产量', '产出', 'yield', '生产数量', '产出数量']
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        if '产量' in str(c):
            return c
    return None


def norm_note(v):
    """规范化备注文本"""
    if v is None:
        return ''
    if isinstance(v, float) and pd.isna(v):
        return ''
    s = str(v).strip()
    if s.lower() in ('nan', 'none', 'nat', ''):
        return ''
    return s


def safe_qty(v):
    """安全转换数量为数值"""
    try:
        if v is None:
            return None
        if isinstance(v, float) and pd.isna(v):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def classify_row_color_keys(df: pd.DataFrame):
    """根据 DataFrame 的列自动分类行颜色规则"""
    color_keys = []
    for col in df.columns:
        col_lower = str(col).lower()
        if '审核' in col_lower or '状态' in col_lower or '标记' in col_lower or '颜色' in col_lower:
            color_keys.append(col)
    return color_keys
