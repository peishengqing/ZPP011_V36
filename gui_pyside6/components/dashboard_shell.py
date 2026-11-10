"""DashboardShell - 看板统一容器组件"""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QFont, QPalette

# v43.335：QSS 用模块相对定位，不再写死 E:/zpp011_v2（换机器/换盘即读不到，静默退化成兜底样式）
_THEME_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "themes")


class DashboardShell(QWidget):
    """
    统一看板容器：标题 + 操作条 + 内容区 + 状态条
    目的：隔离样式与尺寸，支持亮暗主题切换
    """

    title_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardShell")
        self._current_theme = "light"
        self._parent_window = parent
        self._init_layout()
        self._load_theme_qss(self._current_theme)
        # 检查父窗口并启动主题监听
        if parent is not None:
            self._init_theme_sync()

    def _init_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏 48px
        self._title_bar = QFrame()
        self._title_bar.setFixedHeight(48)
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(16, 8, 16, 8)
        self._title_label = QLabel()
        self._title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_layout.addWidget(self._title_label, 1)
        self._action_bar = QFrame()
        self._action_bar.setFixedHeight(36)
        layout.addWidget(self._title_bar)
        layout.addWidget(self._action_bar)

        # 内容区
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        layout.addWidget(self._content, 1)

        # 状态条 30px
        self._status_bar = QFrame()
        self._status_bar.setFixedHeight(30)
        self._status_label = QLabel()
        self._status_label.setFont(QFont("Segoe UI", 9))
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.addWidget(self._status_label, 1)
        layout.addWidget(self._status_bar)

    def _load_theme_qss(self, theme):
        """加载亮/暗主题 QSS"""
        self._current_theme = theme
        qss_content = ""
        qss_name = "light_dashboard.qss" if theme == "light" else "dark_dashboard.qss"
        try:
            with open(os.path.join(_THEME_DIR, qss_name), "r", encoding="utf-8") as f:
                qss_content = f.read()
        except Exception:
            qss_content = (self._default_light_qss() if theme == "light"
                            else self._default_dark_qss())
        self.setStyleSheet(qss_content)

    def _default_light_qss(self):
        return """
            #DashboardShell { background: #F5F6FA; }
            #title_bar { background: #FFFFFF; border-bottom: 1px solid #E2E8F0; }
            #action_bar { background: #FFFFFF; padding: 8px; border-bottom: 1px solid #E2E8F0; }
            #content { background: #FFFFFF; }
            #status_bar { background: #F8F9FA; border-top: 1px solid #E2E8F0; }
            QPushButton {
                background-color: #1E40AF;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1E3A8A; }
            QPushButton:pressed { background-color: #152466; }
            QLabel { color: #1F2937; }
        """

    def _default_dark_qss(self):
        return """
            #DashboardShell { background: #1E1E24; }
            #title_bar { background: #25262B; border-bottom: 1px solid #2C2E33; }
            #action_bar { background: #25262B; padding: 8px; border-bottom: 1px solid #2C2E33; }
            #content { background: #25262B; }
            #status_bar { background: #2C2E33; border-top: 1px solid #35334A; }
            QPushButton {
                background-color: #5C7CFA;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #4C6EF5; }
            QPushButton:pressed { background-color: #3B5BDB; }
            QLabel { color: #E9ECEF; }
        """

    def set_title(self, text):
        self._title_label.setText(text)
        self.title_changed.emit(text)

    def set_action_widget(self, widget):
        layout = QHBoxLayout(self._action_bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(widget)

    def set_content(self, widget):
        self._content_layout.addWidget(widget)

    def set_status(self, text):
        self._status_label.setText(text)

    def set_theme(self, theme):
        """theme: 'light' or 'dark'"""
        self._load_theme_qss(theme)

    def get_theme(self):
        return self._current_theme

    def _init_theme_sync(self):
        """同步父窗口主题"""
        # 立即同步一次
        self._sync_theme_with_window()
        # 使用定时器持续监听主题变化（每隔500ms检查一次）
        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(500)
        self._theme_timer.timeout.connect(self._sync_theme_with_window)
        self._theme_timer.start()

    def _sync_theme_with_window(self):
        """根据父窗口的palette自动切换主题"""
        if self._parent_window is None:
            return
        try:
            palette = self._parent_window.palette()
            window_color = palette.color(QPalette.Window)
            # 计算亮度的简单方法：(R*0.299 + G*0.587 + B*0.114)
            brightness = int(window_color.red() * 0.299 + window_color.green() * 0.587 + window_color.blue() * 0.114)
            new_theme = "dark" if brightness < 128 else "light"
            if new_theme != self._current_theme:
                self.set_theme(new_theme)
        except Exception:
            pass
