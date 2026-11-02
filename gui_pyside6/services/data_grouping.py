# -*- coding: utf-8 -*-
"""
数据分组函数
负责：按指定列拆分 DataFrames，支持多组返回或单一组返回
"""

import pandas as pd


def process_analysis_results(df: pd.DataFrame, groupby_col: str = '工厂', return_all_groups: bool = True) -> dict:
    """
    处理分析结果，按指定列将 DataFrame 拆分为多个组。

    Args:
        df: 分析结果 DataFrame
        groupby_col: 用于分组的列名，默认 '工厂'
        return_all_groups: 如果 True，返回所有分组；否则只返回第一组（兼容旧逻辑）

    Returns:
        字典 {group_name: group_df}，或者当 return_all_groups=False 且唯一分组时返回单个 group_df
    """
    if df is None or df.empty or groupby_col not in df.columns:
        return {'全部': df} if df is not None and not df.empty else {}

    result = {}
    for group_name, group in df.groupby(groupby_col):
        result[str(group_name)] = group.copy()

    return result


def get_combined_factory_data(df: pd.DataFrame, groupby_col: str = '工厂'):
    """
    按照工厂（或指定列）合并数据，并返回分组后的字典 `data_by_factory`。
    同时返回一个 '全部' key，其值为所有组的拼接 DataFrame。

    Args:
        df: 原始 DataFrame
        groupby_col: 分组列名

    Returns:
        tuple: (data_by_factory: dict, all_data: DataFrame or None)
    """
    if df is None or df.empty or groupby_col not in df.columns:
        if df is None or df.empty:
            return {}, None
        return {'全部': df}, df

    groups = []
    factories = {}
    for name, grp in df.groupby(groupby_col):
        name = str(name)
        factories[name] = grp.copy()
        groups.append(grp)

    all_data = pd.concat(groups, ignore_index=True) if groups else None
    return factories, all_data
