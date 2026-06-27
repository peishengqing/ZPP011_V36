# -*- coding: utf-8 -*-
"""
模态加载对话框（无边框，居中显示）
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QTimer


class LoadingDialog(QDialog):
    def __init__(self, message="正在处理，请稍候...", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(300, 100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.label = QLabel(message)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setObjectName("loadingLabel")
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # 无限进度条
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setObjectName("loadingProgress")
        layout.addWidget(self.progress)

        # 居中显示
        if parent:
            self.move(parent.geometry().center() - self.rect().center())

    def update_message(self, text):
        self.label.setText(text)
