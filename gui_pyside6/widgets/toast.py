# -*- coding: utf-8 -*-
"""Toast 消息提示控件"""

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PySide6.QtGui import QFont


def toast(message, level='info', parent=None, duration=3000):
    """显示一个 toast 消息提示"""
    Toast(message, level, parent, duration)


class Toast(QWidget):
    COLORS = {
        'success': ('#d4edda', '#155724'),
        'error': ('#f8d7da', '#721c24'),
        'info': ('#d1ecf1', '#0c5460'),
        'warning': ('#fff3cd', '#856404'),
    }

    def __init__(self, message, level='info', parent=None, duration=3000):
        super().__init__(parent)
        self.duration = duration
        bg, fg = self.COLORS.get(level, self.COLORS['info'])

        self.setObjectName("toastWidget")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        label = QLabel(message)
        label.setFont(QFont("Microsoft YaHei", 10))
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
