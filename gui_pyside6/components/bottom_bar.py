# -*- coding: utf-8 -*-
"""底部栏组件：运行日志"""
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QTextEdit


class BottomBarComponent:
    """底部栏组件：运行日志"""

    def __init__(self, main_window):
        self.mw = main_window
        self._create_widgets()

    def _create_widgets(self):
        """创建运行日志控件"""
        self.log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(self.log_group)
        self.mw.log_text = QTextEdit()
        self.mw.log_text.setReadOnly(True)
        self.mw.log_text.setFixedHeight(400)
        log_layout.addWidget(self.mw.log_text)
