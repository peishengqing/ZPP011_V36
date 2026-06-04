# -*- coding: utf-8 -*-
"""
PySide6 DataFrame Model & Proxy Model
支持排序、筛选、数据更新、行高亮等
"""

from PySide6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt, Signal, QModelIndex
from PySide6.QtGui import QColor
import pandas as pd
from typing import Optional, Dict, Any, List


class DataFrameModel(QAbstractTableModel):
    """将 pandas DataFrame 适配为 QAbstractTableModel"""

    def __init__(self, data: pd.DataFrame = None):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()
        self._original_data = self._data.copy()
        self._row_colors = {}

    # ── 数据写入 ───────────────────────────────────
    def set_data(self, df: pd.DataFrame):
        """整体替换数据源（分析加载结果时调用）"""
        self.beginResetModel()
        self._data = df.copy()
        self._original_data = self._data.copy()
        self.endResetModel()

    def set_data_cell(self, row: int, col_name: str, value):
        """单格回写（AI 审核 / 用户编辑后调用）"""
        if col_name in self._data.columns and 0 <= row < len(self._data):
            self._data.at[row, col_name] = value
            col_idx = list(self._data.columns).index(col_name)
            top_left = self.index(row, col_idx)
            bottom_right = self.index(row, col_idx)
            self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.BackgroundRole])

    def get_data(self) -> pd.DataFrame:
        return self._data

    def getDataFrame(self) -> pd.DataFrame:
        """兼容方法，返回内部 DataFrame（供 main_window.py 调用）"""
        return self._data

    # ── 基类接口 ──────────────────────────────────────
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if 0 <= row < len(self._data) and 0 <= col < len(self._data.columns):
            value = self._data.iloc[row, col]
            if role == Qt.DisplayRole or role == Qt.EditRole:
                col_name = self._data.columns[col]
                if col_name in ['偏差率(%)', '偏差率', 'dev_rate']:
                    try:
                        num = float(str(value).replace('%', ''))
                        return f"{num:.2f}%"
                    except (ValueError, TypeError):
                        return str(value) if pd.notna(value) else ""
                return str(value) if pd.notna(value) else ""
            elif role == Qt.TextAlignmentRole:
                col_name = self._data.columns[col]
                if col_name in ['偏差率(%)', '偏差率', 'dev_rate', '偏差数量', '偏差金额']:
                    return Qt.AlignRight | Qt.AlignVCenter
                if pd.api.types.is_numeric_dtype(self._data.dtypes.iloc[col]):
                    return Qt.AlignRight | Qt.AlignVCenter
                return Qt.AlignLeft | Qt.AlignVCenter
            elif role == Qt.BackgroundRole:
                return self._row_colors.get(row)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])
            else:
                return str(self._data.index[section] + 1)
        return None

    def flags(self, index):
        """设置单元格是否可编辑"""
        if not index.isValid():
            return Qt.NoItemFlags
        col_name = self._data.columns[index.column()]
        if col_name in ('备注', '备注原因', 'remark'):
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def setData(self, index, value, role=Qt.EditRole):
        """编辑数据"""
        if role == Qt.EditRole:
            row = index.row()
            col = index.column()
            try:
                dtype = self._data.dtypes.iloc[col]
                if pd.api.types.is_integer_dtype(dtype):
                    value = int(value)
                elif pd.api.types.is_float_dtype(dtype):
                    value = float(value)
                self._data.iloc[row, col] = value
                self.dataChanged.emit(index, index, [Qt.DisplayRole])
                return True
            except Exception:
                return False
        return False

    def sort(self, column: int, order=Qt.AscendingOrder):
        """排序"""
        self.beginResetModel()
        col_name = self._data.columns[column]
        ascending = (order == Qt.AscendingOrder)
        self._data = self._data.sort_values(by=col_name, ascending=ascending)
        self.endResetModel()

    # ── 行颜色标记 ──────────────────────────────────────
    def set_row_color(self, row: int, color: QColor):
        """设置行背景色"""
        self._row_colors[row] = color
        top_left = self.index(row, 0)
        bottom_right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.BackgroundRole])

    def clear_row_colors(self):
        """清除所有行颜色"""
        self._row_colors.clear()
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.BackgroundRole])


class AuditProxyModel(QSortFilterProxyModel):
    """排序/过滤代理模型"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters = {}
        self._filter_func = None

    def set_audit_result(self, target: str):
        if target == '全部':
            self._filters.pop('审核结果', None)
        else:
            self._filters['审核结果'] = target
        self.invalidateFilter()

    def setFilter(self, column: int, text: str):
        if text:
            self._filters[column] = text.lower()
        else:
            self._filters.pop(column, None)
        self.invalidateFilter()

    def clearFilters(self):
        self._filters.clear()
        self._filter_func = None
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if self._filter_func:
            source_model = self.sourceModel()
            if not self._filter_func(source_model.get_data().iloc[source_row]):
                return False
        if self._filters:
            source_model = self.sourceModel()
            for key, filter_text in self._filters.items():
                if isinstance(key, int):
                    if key >= source_model.columnCount():
                        continue
                    idx = source_model.index(source_row, key)
                    value = source_model.data(idx, Qt.DisplayRole)
                    if filter_text not in str(value).lower():
                        return False
                elif isinstance(key, str):
                    if key not in source_model.get_data().columns:
                        continue
                    col = list(source_model.get_data().columns).index(key)
                    idx = source_model.index(source_row, col)
                    value = source_model.data(idx, Qt.DisplayRole)
                    if filter_text not in str(value).lower():
                        return False
        return True

    def setCustomFilter(self, filter_func):
        self._filter_func = filter_func
        self.invalidateFilter()

    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.DisplayRole)
        right_data = self.sourceModel().data(right, Qt.DisplayRole)
        try:
            return float(left_data) < float(right_data)
        except (ValueError, TypeError):
            return str(left_data) < str(right_data)
