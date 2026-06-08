# -*- coding: utf-8 -*-
"""
分析数据视图模型（MVVM）
负责持有当前分析结果 DataFrame，并提供数据变更信号
"""

import pandas as pd
from PySide6.QtCore import QObject, Signal


class AnalysisViewModel(QObject):
    """单一数据源，所有界面组件通过它访问和修改数据"""

    # 当任何数据发生变化时发射（如新分析完成、批量编辑、排序/过滤后的数据）
    data_changed = Signal()

    # 可选：更细粒度的信号，用于特定场景
    row_updated = Signal(int)  # 某行数据更新
    filter_applied = Signal(dict)  # 筛选条件变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()  # 原始/当前显示的 DataFrame（含 _read 等）
        self._filtered_df = pd.DataFrame()  # 可选：暂存过滤后数据，目前由 ProxyModel 处理，可以不维护
        self._alt_pairs = []  # 替代料配对（可选，方便联动）

    @property
    def df(self) -> pd.DataFrame:
        """获取当前数据（只读）"""
        return self._df

    @df.setter
    def df(self, new_df: pd.DataFrame):
        """设置新数据，触发刷新信号"""
        if new_df is None:
            new_df = pd.DataFrame()
        self._df = new_df
        self.data_changed.emit()

    def update_row(self, row_index: int, column_name: str, value):
        """单行单列更新（如备注编辑）"""
        if row_index < 0 or row_index >= len(self._df):
            return
        self._df.at[row_index, column_name] = value
        self.row_updated.emit(row_index)
        self.data_changed.emit()  # 亦可只发射 row_updated，但为简化，全刷新

    def batch_update(self, updates: list):
        """
        批量更新：updates = [(row, col_name, value), ...]
        """
        for row, col, val in updates:
            if 0 <= row < len(self._df) and col in self._df.columns:
                self._df.at[row, col] = val
        self.data_changed.emit()

    def get_row(self, row_index: int) -> pd.Series:
        return self._df.iloc[row_index] if row_index < len(self._df) else None
