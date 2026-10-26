"""
DateFilterGroup - Specialized filter group for date range selection.

Provides a pair of date editors with start and end date and a reset button.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDateEdit, QPushButton
from PySide6.QtCore import Signal, Qt
from gui_pyside6.widgets.components.filter_group import FilterGroup


class DateFilterGroup(FilterGroup):
    """
    Date filter group.

    Contains a title, start and end date editors, and apply/cancel buttons.
    """

    date_changed = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(title="日期范围", content_layout=QVBoxLayout(), parent=parent)

        # Set up the date row
        date_layout = QHBoxLayout()
        date_layout.setSpacing(8)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setObjectName("startDateEdit")
        date_layout.addWidget(self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setObjectName("endDateEdit")
        date_layout.addWidget(self.end_date_edit)

        self.content_layout().addLayout(date_layout)

        # Buttons
        button_row = QHBoxLayout()
        self.apply_btn = QPushButton("应用")
        self.apply_btn.setObjectName("applyFilterBtn")
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.clicked.connect(self._on_apply)
        button_row.addWidget(self.apply_btn)

        self.cancel_btn = QPushButton("重置")
        self.cancel_btn.setObjectName("resetDateFilterBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_row.addWidget(self.cancel_btn)

        self.content_layout().addLayout(button_row)

    def _on_apply(self):
        """Emit date_changed signal."""
        self.date_changed.emit()

    def _on_cancel(self):
        """Clear date filters."""
        self.start_date_edit.setDateTime(None)
        self.end_date_edit.setDateTime(None)
        self.date_changed.emit()
