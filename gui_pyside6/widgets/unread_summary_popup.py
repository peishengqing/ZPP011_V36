# -*- coding: utf-8 -*-
"""
未读汇总弹窗
非模态、右下角置顶、不阻塞主线程；分析/加载完成后显示 4 类未读条数，
每行可点击「查看」跳转对应看板。复用 AlertPopup 的安全写法（避免模态弹窗引发卡顿）。
裴哥 | 2026-08-01
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class UnreadSummaryPopup(QWidget):
    """非模态未读汇总弹窗。

    items: list of dict，每个含
        icon     : str   图标
        label    : str   类别名（隔离区 / 变动提醒 / 替代料 / 偏差率预警）
        count    : int   未读数
        callback : callable  点击「查看」时打开对应看板的方法
    """

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = items or []

        # 非模态 + 无边框 + 置顶 + 工具窗口（不在任务栏显示），彻底不阻塞主线程
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        # 注意：故意【不】设 WA_DeleteOnClose。
        # 若开启，点「查看」打开模态看板期间，20 秒自动关闭定时器触发 close()
        # 会直接销毁 C++ 对象；看板关闭后 _open_board 末尾再调 close() 即抛
        # "Internal C++ object already deleted"。改为 close() 仅隐藏，由持有方
        # （main_window 单例）负责 deleteLater 释放，杜绝生命周期竞态。
        self._closed = False
        self.setFixedWidth(330)
        self._setup_ui()
        self._move_to_bottom_right()
        self._start_auto_close()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("📋 未读概览（本次分析）")
        title.setObjectName("unreadSummaryTitle")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        for it in self._items:
            row = QFrame(self)
            row.setObjectName("unreadRow")
            rlayout = QHBoxLayout(row)
            rlayout.setContentsMargins(8, 5, 8, 5)
            rlayout.setSpacing(6)

            icon_label = QLabel(it.get("icon", ""))
            name_label = QLabel(it["label"])
            name_label.setFont(QFont("Microsoft YaHei", 10))
            count_label = QLabel(f"{it['count']} 条未读")
            count_label.setObjectName("unreadCount")
            count_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))

            view_btn = QPushButton("查看")
            view_btn.setFixedWidth(48)
            # 用默认参数绑定，避免闭包复用同一 callback
            view_btn.clicked.connect(
                lambda _checked=False, cb=it["callback"]: self._open_board(cb)
            )

            rlayout.addWidget(icon_label)
            rlayout.addWidget(name_label)
            rlayout.addStretch()
            rlayout.addWidget(count_label)
            rlayout.addWidget(view_btn)
            layout.addWidget(row)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _open_board(self, callback):
        """点击「查看」→ 打开对应看板（用户主动触发，此时分析已完成、主表就绪）。"""
        try:
            # 先停定时器：避免看板模态期间定时器触发 close() 销毁本对象
            self._auto_close_timer.stop()
        except Exception:
            pass
        try:
            if callable(callback):
                callback()
        except Exception:
            pass
        self._safe_close()

    def _safe_close(self):
        """安全关闭：已关闭则跳过；C++ 对象万一已被销毁也不抛异常。"""
        if self._closed:
            return
        self._closed = True
        try:
            super().close()
        except RuntimeError:
            # 极少数情况下 C++ 对象已被销毁，忽略即可
            pass

    def closeEvent(self, event):
        try:
            self._auto_close_timer.stop()
        except Exception:
            pass
        self._closed = True
        super().closeEvent(event)

    def _move_to_bottom_right(self):
        """移动到屏幕右下角（与主窗无关，避免依赖 parent 几何）"""
        screen = self.screen()
        if screen:
            sg = screen.availableGeometry()
            x = sg.x() + sg.width() - self.width() - 20
            y = sg.y() + sg.height() - self.height() - 60
            self.move(x, y)

    def _start_auto_close(self):
        """20 秒后自动关闭（用受控 QTimer，可被 stop 取消）"""
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._safe_close)
        self._auto_close_timer.start(20000)
