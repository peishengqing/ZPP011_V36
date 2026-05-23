# -*- coding: utf-8 -*-
"""
过滤引擎核心（v39 重构）
冻结期版本：空骨架，不依赖 GUI
"""
import pandas as pd


class FilterEngine:
    def __init__(self, data: pd.DataFrame, column_mapping: dict = None):
        self.original_data = data
        self.column_mapping = column_mapping or {}

    def apply(self, filters: dict) -> pd.DataFrame:
        """接收筛选条件字典，返回过滤后的 DataFrame"""
        df = self.original_data.copy()
        # 冻结期先返回原始数据，后续实现过滤逻辑
        return df
