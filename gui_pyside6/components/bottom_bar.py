# -*- coding: utf-8 -*-
"""底部栏组件：运行日志"""
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QTextEdit


class BottomBarComponent:
    """底部栏组件：运行日志"""

    def __init__(self, main_window):
        self.mw = main_window
        self._create_widgets()

    def _create_widgets(self):
        self.log_group = QGroupBox("运行日志")
        self.log_group.setObjectName("logGroup")
        log_layout = QVBoxLayout(self.log_group)
        log_layout.setContentsMargins(0, 4, 0, 4)
        log_layout.setSpacing(0)

        self.mw.log_text = QTextEdit()
        self.mw.log_text.setReadOnly(True)
        self.mw.log_text.setObjectName("logTextEdit")
        self.mw.log_text.setMinimumHeight(100)
        self.mw.log_text.setMaximumHeight(260)

        log_layout.addWidget(self.mw.log_text)
