"""
ResetButtonWidget - Standalone reset button.

Provides a button that emits a reset_clicked signal.
"""

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Signal, Qt


class ResetButtonWidget(QPushButton):
    """
    Reset button widget.

    A button that emits reset_clicked signal when pressed.
    """

    reset_clicked = Signal()

    def __init__(self, text: str = "重置", parent=None):
        """
        Initialize the ResetButtonWidget.

        Args:
            text: Button text
            parent: Parent widget
        """
        super().__init__(text, parent)

        # Set object name for CSS targeting
        self.setObjectName("resetButton")

        # Set cursor
        self.setCursor(Qt.PointingHandCursor)

        # Connect click
        self.clicked.connect(self._on_reset)

    def _on_reset(self):
        """Emit reset_clicked signal."""
        self.reset_clicked.emit()
