# -*- coding: utf-8 -*-
"""自定义标题栏组件 — 暗色主题 + 工厂切换 + 主题切换
设计令牌: 背景 #1A1830, 文字 #EAE8E4, 边框 0.5px #444441
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class TitleBarWidget(QWidget):
    """品牌化暗色标题栏"""

    theme_toggled = Signal()
    factory_selected = Signal(str)

    def __init__(self, version: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self._setup_ui(version)

    def _setup_ui(self, version: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # --- Logo 图标 ---
        logo_label = QLabel("\U0001F3ED")  # factory emoji
        logo_label.setFont(QFont("Segoe UI Emoji", 16))
        layout.addWidget(logo_label)

        # --- 标题 ---
        self.title_label = QLabel(f"ZPP011 生产偏差分析器 v{version}")
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # --- 主题切换 ---
        self.theme_btn = QPushButton("\u2601 暗色")
        self.theme_btn.setFixedSize(56, 24)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.clicked.connect(self.theme_toggled.emit)
        layout.addWidget(self.theme_btn)

        # 注意：不显示自定义窗口控制按钮（最小化、最大化、关闭），使用系统默认

    def set_theme_light(self):
        """当前是亮色主题，按钮显示'暗色'"""
        self.theme_btn.setText("\u2601\uFE0F 暗色")

    def set_theme_dark(self):
        """当前是暗色主题，按钮显示'亮色'"""
        self.theme_btn.setText("\u2600\uFE0F 亮色")
