"""
AppState - Central state management using PySide6's QObject.

Provides reactive state management for data, sorting, filtering,
and pagination with signal-based updates.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
from PySide6.QtCore import QObject, Signal
import pandas as pd


class SortOrder(Enum):
    """Sort order enum."""
    ASCENDING = 0
    DESCENDING = 1


class FilterRule:
    """Represents a single filter rule."""

    def __init__(self, column: str, condition: str, value: Any):
        self.column = column
        self.condition = condition  # e.g., '=', '>', '<', 'contains', etc.
        self.value = value

    def __eq__(self, other):
        if isinstance(other, FilterRule):
            return (self.column == other.column and
                    self.condition == other.condition and
                    self.value == other.value)
        return False

    def __repr__(self):
        return f"FilterRule(column='{self.column}', condition='{self.condition}', value={self.value})"


class AppState(QObject):
    """
    Central state management class using PySide6's QObject.

    Tracks current data, sorting, filtering, pagination, and export state.
    Emits signals when state changes to notify connected UI components.
    """

    # Main state change signals
    state_changed = Signal()  # Emitted when any state changes
    data_loaded = Signal()  # Emitted when data is loaded or updated
    filters_changed = Signal()  # Emitted when filter rules change
    sort_changed = Signal()  # Emitted when sort configuration changes

    # Other significant state transitions
    pagination_changed = Signal()  # Emitted when pagination settings change
    theme_changed = Signal()  # Emitted when theme settings change

    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize the AppState.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)

        # Internal state
        self._data: Optional[pd.DataFrame] = None
        self._sort_columns: List[Tuple[str, SortOrder]] = []
        self._filters: List[FilterRule] = []
        self._pagination = {
            "page_size": 20,
            "current_page": 1,
            "total_pages": 1,
            "total_rows": 0
        }
        self._export_state: Dict[str, Any] = {
            "export_format": None,
            "export_last_path": None,
            "export_success": False
        }
        self._theme = {
            "theme_mode": "light",
            "accent_color": "#0078D4"
        }

    # Data properties
    def set_data(self, df: Union[pd.DataFrame, Dict]) -> None:
        """
        Set the current data from a DataFrame or dictionary.

        Args:
            df: DataFrame or dict containing the data
        """
        try:
            if isinstance(df, dict):
                self._data = pd.DataFrame(df)
            else:
                self._data = df
        except Exception as e:
            raise ValueError(f"Failed to set data: {e}")

        # Reset pagination when new data is loaded
        self._pagination["total_rows"] = len(self._data)
        self._pagination["total_pages"] = max(1, (len(self._data) + self._pagination["page_size"] - 1) // self._pagination["page_size"])
        self._pagination["current_page"] = 1

        self.data_loaded.emit()
        self.state_changed.emit()

    def get_data(self) -> Optional[pd.DataFrame]:
        """
        Get the current data DataFrame.

        Returns:
            The current DataFrame, or None if no data is set
        """
        return self._data

    # Sort properties
    def set_sort_columns(self, columns: List[Tuple[str, SortOrder]]) -> None:
        """
        Set the sort columns and their orders.

        Args:
            columns: List of tuples (column_name, sort_order)
        """
        self._sort_columns = columns
        # Also emit sort_changed for listeners
        self.sort_changed.emit()
        self.state_changed.emit()

    def get_sort_columns(self) -> List[Tuple[str, SortOrder]]:
        """
        Get the current sort configuration.

        Returns:
            List of tuples (column_name, sort_order)
        """
        return self._sort_columns.copy()

    # Filter properties
    def set_filters(self, rules: List[FilterRule]) -> None:
        """
        Set the filter rules.

        Args:
            rules: List of FilterRule objects
        """
        self._filters = rules
        self.filters_changed.emit()
        self.state_changed.emit()

    def get_filters(self) -> List[FilterRule]:
        """
        Get the current filter rules.

        Returns:
            List of FilterRule objects
        """
        return self._filters.copy()

    # Pagination properties
    def set_pagination(self, page_size: int, current_page: int) -> None:
        """
        Set pagination settings.

        Args:
            page_size: Number of rows per page
            current_page: Current page number (1-indexed)
        """
        self._pagination["page_size"] = page_size
        self._pagination["current_page"] = current_page

        # Update total pages if total rows is known
        if self._pagination["total_rows"]:
            self._pagination["total_pages"] = max(1, (self._pagination["total_rows"] + page_size - 1) // self._pagination["page_size"])

        self.pagination_changed.emit()
        self.state_changed.emit()

    def get_pagination(self) -> Dict[str, int]:
        """
        Get the current pagination settings.

        Returns:
            Dictionary with pagination info
        """
        return self._pagination.copy()

    def update_total_rows(self, total_rows: int) -> None:
        """
        Update total rows count (useful for server-side pagination).

        Args:
            total_rows: Total number of rows available
        """
        self._pagination["total_rows"] = total_rows
        self._pagination["total_pages"] = max(1, (total_rows + self._pagination["page_size"] - 1) // self._pagination["page_size"])
        self.pagination_changed.emit()
        self.state_changed.emit()

    # Export properties
    def set_export_state(self, format: str = None, path: str = None, success: bool = True) -> None:
        """
        Set export state information.

        Args:
            format: Export format (e.g., 'csv', 'excel')
            path: Path where file was exported
            success: Whether the export was successful
        """
        self._export_state["export_format"] = format
        self._export_state["export_last_path"] = path
        self._export_state["export_success"] = success

    def get_export_state(self) -> Dict[str, Any]:
        """
        Get the export state information.

        Returns:
            Dictionary with export info
        """
        return self._export_state.copy()

    # Theme properties
    def set_theme(self, theme: Dict[str, Any]) -> None:
        """
        Set the application theme settings.

        Args:
            theme: Dictionary with theme configuration
        """
        self._theme = theme.copy()
        self.theme_changed.emit()
        self.state_changed.emit()

    def get_theme(self) -> Dict[str, Any]:
        """
        Get the current theme settings.

        Returns:
            Dictionary with theme configuration
        """
        return self._theme.copy()

    def clear(self) -> None:
        """
        Clear all state, resetting to defaults.

        Removes all data, filters, sorting, and pagination settings.
        """
        self._data = None
        self._sort_columns = []
        self._filters = []
        self._pagination = {
            "page_size": 20,
            "current_page": 1,
            "total_pages": 1,
            "total_rows": 0
        }
        self._export_state = {
            "export_format": None,
            "export_last_path": None,
            "export_success": False
        }
        self._theme = {
            "theme_mode": "light",
            "accent_color": "#0078D4"
        }
        # 清理预设存储
        if hasattr(self, '_preset_store'):
            self._preset_store = {}

        self.state_changed.emit()

    # 筛选执行扩展

    def apply_filters(self) -> Optional[pd.DataFrame]:
        """
        将当前 FilterRule 列表应用到 _data 上，返回筛选后的 DataFrame。

        规则：
        1. 按列顺序应用（避免列不存在错误）
        2. 每个条件独立处理
        3. 空值特殊处理

        Returns:
            筛选后的 DataFrame，如无数据则返回 None
        """
        if self._data is None:
            return None

        df = self._data.copy()
        rules = self._filters

        for rule in rules:
            if rule.column not in df.columns:
                continue

            col = rule.column
            cond = rule.condition
            val = rule.value

            # 处理空值
            if val is None or pd.isna(val):
                if cond == '=':
                    mask = df[col].isna()
                elif cond == '!=':
                    mask = df[col].notna()
                elif cond in ('>', '<', '>=', '<='):
                    continue
                else:
                    continue
            else:
                # 数值比较
                if cond == '=':
                    mask = df[col] == val
                elif cond == '!=':
                    mask = df[col] != val
                elif cond == '>':
                    mask = df[col] > val
                elif cond == '<':
                    mask = df[col] < val
                elif cond == '>=':
                    mask = df[col] >= val
                elif cond == '<=':
                    mask = df[col] <= val
                elif cond == 'contains':
                    mask = df[col].astype(str).str.contains(str(val), na=False)
                elif cond == 'not_contains':
                    mask = df[col].astype(str).str.contains(str(val), na=False)
                    mask = ~mask
                elif cond == 'start_with':
                    mask = df[col].astype(str).str.startswith(str(val))
                elif cond == 'end_with':
                    mask = df[col].astype(str).str.endswith(str(val))
                else:
                    continue

            df = df[mask]

        return df

    def get_filtered_data(self) -> Optional[pd.DataFrame]:
        """获取当前应用筛选后的数据（返回副本）"""
        if self._data is None:
            return None
        return self.apply_filters()

    def set_cascade_filters(self, parent_filters: List[FilterRule], dependent_rules: List[FilterRule]) -> None:
        """
        设置级联筛选规则。子筛选基于父筛选的条件动态计算选项。

        Args:
            parent_filters: 基础筛选条件
            dependent_rules: 依赖筛选的列规则（每个规则包含 target_column 和 valid_values）
        """
        # 先应用父筛选
        base_df = self.apply_filters()
        if base_df is None:
            self.set_filters(dependent_rules)
            return

        # 为每个 dependent rule 计算可用值
        for rule in dependent_rules:
            parent_col = getattr(rule, 'parent_column', None)

            if parent_col is None:
                continue

            # 计算该父筛选下的所有唯一值
            valid_vals = base_df[parent_col].unique().tolist()
            # 为新规则设置值
            if hasattr(rule, 'value'):
                rule.value = valid_vals[0] if valid_vals else None

        # 最后更新筛选状态
        self.set_filters(parent_filters + dependent_rules)

    def get_cascade_candidates(self, parent_filters: List[FilterRule], source_filters: List[FilterRule]) -> List[FilterRule]:
        """
        获取当前父筛选条件下的子筛选候选值列表。

        Args:
            parent_filters: 父级筛选的规则列表
            source_filters: 触发级联的源筛选规则（如工厂切换）

        Returns:
            符合条件的新子筛选规则列表（只包含目标列和可用值）
        """
        # 先应用父筛选
        base_df = self.apply_filters()
        if base_df is None:
            return []

        # 收集级联规则
        cascade_rules = []
        for rule in source_filters:
            if hasattr(rule, 'cache_to'):
                # 目标列和候选值（文本 'cache_to' 可能是拼写错误，保留）
                target_col = rule.cache_to
                if target_col in base_df.columns:
                    candidates = base_df[target_col].unique().tolist()
                    new_rule = FilterRule(column=rule.column, condition='=', value=candidates)
                    cascade_rules.append(new_rule)

        return cascade_rules
