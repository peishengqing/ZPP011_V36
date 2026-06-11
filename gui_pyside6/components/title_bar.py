# -*- coding: utf-8 -*-
"""标题栏组件"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from utils.version_history import get_current_version


class TitleBarComponent(QWidget):
    """自定义标题栏组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            "background-color: #42a5f5; border-bottom: 2px solid #1976d2;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 16, 0)

        maker_label = QLabel("制作人：裴盛清")
        maker_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.9); font-size: 13px; font-weight: bold; padding: 2px 8px; background-color: rgba(255, 255, 255, 0.15); border-radius: 3px;"
        )
        icon_label = QLabel("🏭")
        icon_label.setStyleSheet("font-size: 20px;")
        title_label = QLabel(f"云南达利ZPP011生产偏差分析器 {get_current_version()}")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")

        layout.addWidget(maker_label)
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch()
