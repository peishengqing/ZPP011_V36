# -*- coding: utf-8 -*-
"""自定义标题栏组件 — 仿 Tkinter 旧版深蓝标题栏
左侧蓝色竖条 + 🏭 图标 + 主标题/副标题 + 主题切换
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class TitleBarWidget(QWidget):
    """品牌化深蓝标题栏（仿 Tkinter 旧版 header）"""

    theme_toggled = Signal()
    factory_selected = Signal(str)

    def __init__(self, version: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setObjectName("titleBar")
        self._setup_ui(version)

    def _setup_ui(self, version: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(0)

        # 左侧蓝色竖条（4px）
        accent_bar = QWidget()
        accent_bar.setFixedWidth(4)
        accent_bar.setObjectName("titleAccentBar")
        layout.addWidget(accent_bar)

        # Emoji 图标
        logo_label = QLabel("\U0001F3ED")  # factory emoji
        logo_label.setFont(QFont("Segoe UI Emoji", 20))
        logo_bar = QVBoxLayout()
        logo_bar.setContentsMargins(16, 0, 12, 0)
        logo_bar.addWidget(logo_label, alignment=Qt.AlignVCenter)
        layout.addLayout(logo_bar, 0)

        # 标题区域（主标题 + 副标题）
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.setContentsMargins(0, 0, 0, 0)

        main_title = QLabel(f"云南达利ZPP011生产偏差分析器 {version}")
        main_title.setObjectName("titleMain")
        title_box.addWidget(main_title)

        sub_title = QLabel(f"制作人：裴盛清 | {version}")
        sub_title.setObjectName("titleSub")
        title_box.addWidget(sub_title)

        layout.addLayout(title_box, 0)
        layout.addStretch()

        # 主题切换
        self.theme_btn = QPushButton("\u2601 暗色")
        self.theme_btn.setFixedSize(64, 28)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.clicked.connect(self.theme_toggled.emit)
        layout.addWidget(self.theme_btn, 0, Qt.AlignVCenter)

    def set_theme_light(self):
        """当前是亮色主题，按钮显示'暗色'"""
        self.theme_btn.setText("\u2601\uFE0F 暗色")

    def set_theme_dark(self):
        """当前是暗色主题，按钮显示'亮色'"""
        self.theme_btn.setText("\u2600\uFE0F 亮色")
