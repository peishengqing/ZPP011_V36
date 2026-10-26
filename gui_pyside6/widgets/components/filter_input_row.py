"""
FilterInputGroup - A row containing a label and an input widget.

Provides a highly reusable row with optional label and signal for value changes.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QComboBox, QSpinBox, QDateEdit
from PySide6.QtCore import Signal, Qt


class FilterInputGroup(QWidget):
    """
    Reusable filter input row.

    Contains a label on the left and an input widget on the right.
    Supports QLineEdit, QComboBox, QSpinBox, QDateEdit, and more.
    """

    value_changed = Signal(object)  # Emitted with new value, type depends on input

    def __init__(self, label: str = "", input_widget=None, parent: QWidget = None):
        """
        Initialize the FilterInputGroup.

        Args:
            label: Label text (empty for no label)
            input_widget: Pre-created input widget (requires `on_value_changed` method or signal)
            parent: Parent widget
        """
        super().__init__(parent)

        # Set object name for CSS targeting
        self.setObjectName("filterInputGroup")

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        if label:
            self.label = QLabel(label)
            self.label.setObjectName("filterInputLabel")
            self.label.setFixedWidth(80)  # Fixed width for alignment
            layout.addWidget(self.label)

        # Input widget
        self.input_widget = input_widget
        if input_widget:
            # Try to connect to value_changed signal
            self._connect_value_signal(input_widget)

            # Add width hint if possible
            input_widget.setObjectName("filterInputField")
            input_widget.setStyleSheet("QLineEdit, QComboBox, QSpinBox, QDateEdit { padding: 4px; background: var(--secondary-bg); border: 1px solid var(--border-color); }")
            layout.addWidget(input_widget)

        layout.addStretch()

    def _connect_value_signal(self, widget) -> None:
        """Connect to valueChanged or textChanged signal."""
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._on_value_changed)
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(self._on_value_changed)
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(self._on_value_changed)
        elif isinstance(widget, QDateEdit):
            widget.dateChanged.connect(self._on_value_changed)

    def _on_value_changed(self, value):
        """Emit value_changed signal."""
        self.value_changed.emit(value)

    def get_value(self):
        """Get the current value from the input widget."""
        if self.input_widget is None:
            return None
        if isinstance(self.input_widget, QLineEdit):
            return self.input_widget.text()
        elif isinstance(self.input_widget, QComboBox):
            return self.input_widget.currentText()
        elif isinstance(self.input_widget, QSpinBox):
            return self.input_widget.value()
        elif isinstance(self.input_widget, QDateEdit):
            return self.input_widget.date()
        return None

    def set_value(self, value):
        """Set the current value on the input widget."""
        if self.input_widget is None:
            return
        if isinstance(self.input_widget, QLineEdit):
            self.input_widget.setText(str(value))
        elif isinstance(self.input_widget, QComboBox):
            # Try to find the index
            index = self.input_widget.findText(str(value))
            if index >= 0:
                self.input_widget.setCurrentIndex(index)
        elif isinstance(self.input_widget, QSpinBox):
            self.input_widget.setValue(int(value))
        elif isinstance(self.input_widget, QDateEdit):
            from datetime import date
            if isinstance(value, date):
                self.input_widget.setDate(value)
