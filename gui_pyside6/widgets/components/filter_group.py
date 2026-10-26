"""
FilterGroup - Reusable filter group with title and content area.

Provides a styled group box with a title and content area.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel
from PySide6.QtCore import Qt


class FilterGroup(QWidget):
    """
    Generic filter group widget.

    Contains a title bar, an optional content area, and handles borders and spacing.
    """

    def __init__(self, title: str = "", content_layout: QVBoxLayout = None, parent: QWidget = None):
        """
        Initialize the FilterGroup.

        Args:
            title: The group title
            content_layout: Optional pre-built layout to use as content
            parent: Parent widget
        """
        super().__init__(parent)

        # Set object name for CSS targeting
        self.setObjectName("filterGroup")

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # If using QGroupBox style, we might create one, but we'll use a custom widget
        # to match the original filter panel's appearance

        # Title label
        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName("filterGroupTitle")
            self.title_label.setStyleSheet(self._get_group_title_style())
            layout.addWidget(self.title_label)

        # Content layout
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)

        if content_layout:
            # Add all widgets from the provided layout
            while content_layout.count():
                child = content_layout.itemAt(0).widget()
                if child:
                    self._content_layout.addWidget(child)

        layout.addLayout(self._content_layout)

    def _get_group_title_style(self) -> str:
        """Return style sheet for group title."""
        return "QLabel { background: transparent; color: var(--text-primary); font-weight: bold; font-size: 13px; padding: 4px; }"

    def content_layout(self) -> QVBoxLayout:
        """Return the content layout."""
        return self._content_layout

    def add_widget(self, widget):
        """
        Add a widget to the content area.

        Args:
            widget: Widget to add
        """
        self._content_layout.addWidget(widget)

    def clear_content(self):
        """Clear all widgets from the content area."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_title(self, title: str):
        """
        Set the group title.

        Args:
            title: New title
        """
        if hasattr(self, 'title_label'):
            self.title_label.setText(title)
