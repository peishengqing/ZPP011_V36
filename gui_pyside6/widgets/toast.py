# -*- coding: utf-8 -*-
"""Toast 消息提示控件"""

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PySide6.QtGui import QFont


def toast(message, level='info', parent=None, duration=3000):
    """显示一个 toast 消息提示"""
    Toast(message, level, parent, duration)


class Toast(QWidget):
    """轻提示。配色完全由 light/dark_theme.qss 的 #toastWidget 规则负责，
    这里不再维护第二套颜色表（改造前的 COLORS 从未被使用，且只有浅色值）。"""

    def __init__(self, message, level='info', parent=None, duration=3000):
        super().__init__(parent)
        self.duration = duration
        self.level = level

        self.setObjectName("toastWidget")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        label = QLabel(message)
        layout.addWidget(label)
        self.adjustSize()

        # 定位到父窗口顶部居中
        if parent:
            pw = parent.width()
            x = (pw - self.width()) // 2
            y = 60
            self.setGeometry(x, y, self.width(), self.height())
            self.setParent(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.show()

        # 自动关闭
        QTimer.singleShot(duration, self.close)
