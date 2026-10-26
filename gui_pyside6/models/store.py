"""
AppState - Central state management using PySide6's QObject.

Provides reactive state management for data, sorting, filtering,
and pagination with signal-based updates.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
from PySide6.QtCore import QObject, Signal, Property
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

        self.state_changed.emit()
