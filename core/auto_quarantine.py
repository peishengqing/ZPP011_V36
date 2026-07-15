# -*- coding: utf-8 -*-
"""
自动移入隔离区 — 业务规则

规则：同时满足以下 4 个条件的记录，自动标记为「疑难」并移入隔离区：
  1. 不是替代料   （是否替代料 != '是'）
  2. 属于包材     （物料分类 == '包材'）
  3. 物料名称带「箱」 （组件物料描述 / 物料名称 含「箱」字）
  4. 有实际数量  且 实际数量 < 定额数量 （实际 > 0 且 实际 < 定额）

说明：
  - 隔离区是引用模式（仅存 data_id），本模块只负责返回「应隔离的 data_id 集合」，
    真正的 add_quarantine / 列标记由 GUI 层完成，保持与手动移入一致。
  - 列名在不同 SAP 导出可能不同，故用候选名依次探测，缺失则对应条件判为不匹配。
"""

import pandas as pd


def _first_col(df: pd.DataFrame, candidates):
    """返回 df 中第一个存在的候选列名，都不存在则返回 None。"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def compute_auto_quarantine_ids(df: pd.DataFrame) -> set:
    """根据业务规则返回应移入隔离区的 data_id 集合（字符串）。无匹配返回空集。"""
    if df is None or df.empty or 'data_id' not in df.columns:
        return set()

    alt_col = _first_col(df, ['是否替代料', '替代料', 'is_alt'])
    cat_col = _first_col(df, ['物料分类', '物料大类', '物料类型', '组件物料类型描述'])
    name_col = _first_col(df, ['组件物料描述', '物料名称', '物料描述', 'material_name'])
    actual_col = _first_col(df, ['数量-实际', '实际', '实际数量', '数量 - 实际', 'actual'])
    quota_col = _first_col(df, ['数量-定额', '定额', '定额数量', '数量 - 定额', 'quota'])

    # 1. 不是替代料
    if alt_col:
        m_alt = df[alt_col].astype(str).str.strip() != '是'
    else:
        m_alt = pd.Series(True, index=df.index)

    # 2. 属于包材
    if cat_col:
        m_cat = df[cat_col].astype(str).str.strip() == '包材'
    else:
        m_cat = pd.Series(False, index=df.index)

    # 3. 物料名称带「箱」
    if name_col:
        m_name = df[name_col].astype(str).fillna('').str.contains('箱')
    else:
        m_name = pd.Series(False, index=df.index)

    # 4. 有实际数量（>0）且 实际 < 定额
    if actual_col and quota_col:
        actual = pd.to_numeric(df[actual_col], errors='coerce')
        quota = pd.to_numeric(df[quota_col], errors='coerce')
        m_qty = actual.notna() & (actual > 0) & quota.notna() & (actual < quota)
    else:
        m_qty = pd.Series(False, index=df.index)

    mask = m_alt & m_cat & m_name & m_qty
    return set(df.loc[mask, 'data_id'].astype(str).tolist())
