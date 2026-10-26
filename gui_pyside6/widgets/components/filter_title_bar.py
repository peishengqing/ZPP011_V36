"""
FilterTitleBar - Collapsible title bar for filter panel.

Provides a title with a collapse/expand button that emits a collapsed signal
when toggled.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt, QSize


class FilterTitleBar(QWidget):
    """
    Collapsible title bar widget for filter panels.

    This widget displays a title and a collapse/expand button.
    """

    collapsed = Signal(bool)  # Emitted with new collapsed state (True if collapsed)

    def __init__(self, title: str = "", parent: QWidget = None):
        """
        Initialize the FilterTitleBar.

        Args:
            title: The title text to display
            parent: Parent widget
        """
        super().__init__(parent)

        # Set object name for CSS targeting
        self.setObjectName("filterTitleBar")

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title label
        self.title_label = QLabel(title)
        self.title_label.setObjectName("filterTitleLabel")
        layout.addWidget(self.title_label)

        # Collapse button
        self.collapse_btn = QPushButton("▽")
        self.collapse_btn.setObjectName("filterCollapseBtn")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.collapse_btn)

        # Connect click
        self.collapse_btn.clicked.connect(self._toggle_collapsed)

        # Default: not collapsed
        self._collapsed = False

    def _toggle_collapsed(self):
        """Toggle collapsed state."""
        self._collapsed = not self._collapsed
        self.collapse_btn.setText("▽" if self._collapsed else "▷")
        self.collapsed.emit(self._collapsed)

    def is_collapsed(self) -> bool:
        """Check if panel is collapsed."""
        return self._collapsed

    def set_title(self, title: str):
        """
        Set the title text.

        Args:
            title: New title text
        """
        self.title_label.setText(title)

    def set_collapsed(self, collapsed: bool):
        """
        Set collapsed state.

        Args:
            collapsed: True for collapsed, False for expanded
        """
        if self._collapsed != collapsed:
            self._collapsed = collapsed
            self.collapse_btn.setText("▽" if collapsed else "▷")
            self.collapsed.emit(collapsed)
