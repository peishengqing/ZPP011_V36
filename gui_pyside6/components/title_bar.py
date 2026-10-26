# -*- coding: utf-8 -*-
"""自定义标题栏组件 — v43.264 去 Tkinter 化重构

旧版仿 Tkinter 深蓝标题栏（4px 竖条 + 🏭 emoji + 主副标题 + ☁ 暗色按钮）。
新版：SVG 工厂标收进主色圆角方块（品牌承托），主题按钮改「图标+文字」，
层级、信号与 API（theme_toggled / set_theme_light / set_theme_dark）保持不变。
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal

from gui_pyside6.utils.icons import get_icon


class TitleBarWidget(QWidget):
    """现代化品牌标题栏（v43.264：SVG 图标 + 主色品牌块）"""

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

        # 左侧主色竖条（4px，保留品牌锚点）
        accent_bar = QWidget()
        accent_bar.setFixedWidth(4)
        accent_bar.setObjectName("titleAccentBar")
        layout.addWidget(accent_bar)

        # 品牌块：主色圆角方块 + 白色工厂标（替代原 🏭 emoji）
        brand = QLabel()
        brand.setFixedSize(30, 30)
        brand.setAlignment(Qt.AlignCenter)
        brand.setObjectName("titleBrand")
        brand.setPixmap(get_icon("factory", 18, "#FFFFFF").pixmap(18, 18))
        logo_bar = QVBoxLayout()
        logo_bar.setContentsMargins(14, 0, 10, 0)
        logo_bar.addWidget(brand, alignment=Qt.AlignVCenter)
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

        # 主题切换（图标 + 文字，语义不变）
        self.theme_btn = QPushButton("暗色")
        self.theme_btn.setFixedSize(76, 28)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.clicked.connect(self.theme_toggled.emit)
        layout.addWidget(self.theme_btn, 0, Qt.AlignVCenter)

    def set_theme_light(self):
        """当前是亮色主题，按钮显示'暗色'（月亮图标）"""
        self.theme_btn.setIcon(get_icon("moon", 14))
        self.theme_btn.setText("暗色")

    def set_theme_dark(self):
        """当前是暗色主题，按钮显示'亮色'（太阳图标）"""
        self.theme_btn.setIcon(get_icon("sun", 14))
        self.theme_btn.setText("亮色")
