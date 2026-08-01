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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class UnreadSummaryPopup(QWidget):
    """非模态未读汇总弹窗。

    items: list of dict，每个含
        icon     : str   图标
        label    : str   类别名（隔离区 / 变动提醒 / 替代料 / 偏差率预警）
        count    : int   未读数
        callback : callable  点击「查看」时打开对应看板的方法

    行为：
        - 常驻右下角，不自动消失；有「关闭」按钮手动关。
        - 主窗口在数据变化（隔离/标记已读等）时调用 update_counts 实时刷新条数；
          全部清零时由主窗口调用 close() 自动关闭（满足「信息清零自动关闭，没清零就挂着」）。
        - 点「查看」时先隐藏本弹窗，避免遮挡模态看板；看板关闭后再恢复显示
          （除非期间已全部清零被主窗口关闭）。
    """

    # 关闭信号：供主窗口清掉单例引用
    closed = Signal()

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = items or []
        self._count_labels = {}  # label -> count QLabel，供 update_counts 就地刷新

        # 非模态 + 无边框 + 置顶 + 工具窗口（不在任务栏显示），彻底不阻塞主线程
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        # 故意【不】设 WA_DeleteOnClose，避免点「查看」打开模态看板期间对象被销毁
        # 导致看板关闭后再操作本弹窗抛 "Internal C++ object already deleted"。
        # 改由 close() 仅隐藏/关闭，单例引用由主窗口在 closed 信号里清理。
        self._closed = False
        self.setFixedWidth(330)
        self._setup_ui()
        self._move_to_bottom_right()
        # 注意：不再有「20 秒盲关」定时器——未清零就一直挂着。

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

            # 记录引用，供 update_counts 就地刷新条数
            self._count_labels[it["label"]] = count_label

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def update_counts(self, items):
        """就地刷新各类未读条数（不重建窗口，避免闪烁/抢焦点）。"""
        for it in items:
            lbl = self._count_labels.get(it["label"])
            if lbl is not None:
                lbl.setText(f"{it['count']} 条未读")

    def _open_board(self, callback):
        """点击「查看」→ 打开对应看板（用户主动触发，此时分析已完成、主表就绪）。

        先隐藏本弹窗，避免遮挡模态看板；看板关闭后若本弹窗未被主窗口清零关闭，
        则恢复显示（满足「没清零就挂着」）。
        """
        self.hide()
        try:
            if callable(callback):
                callback()
        except Exception:
            pass
        if not self._closed:
            self.show()
            self._move_to_bottom_right()

    def _safe_close(self):
        """安全关闭：已关闭则跳过；C++ 对象万一已被销毁也不抛异常。"""
        if self._closed:
            return
        try:
            super().close()
        except RuntimeError:
            # 极少数情况下 C++ 对象已被销毁，忽略即可
            pass

    def closeEvent(self, event):
        if not self._closed:
            self._closed = True
            self.closed.emit()
        try:
            super().closeEvent(event)
        except Exception:
            pass

    def _move_to_bottom_right(self):
        """移动到屏幕右下角（与主窗无关，避免依赖 parent 几何）。

        必须先 adjustSize() 让窗口按布局算出真实高度，否则在 show() 之前
        self.height() 为 0，定位会偏下、把下方行与「关闭」按钮挤出屏幕。
        """
        self.adjustSize()
        screen = self.screen()
        if screen:
            sg = screen.availableGeometry()
            x = sg.x() + sg.width() - self.width() - 20
            y = sg.y() + sg.height() - self.height() - 60
            self.move(x, y)

    def showEvent(self, event):
        # 显示后再定位一次，保证高度已知、不超出屏幕
        self._move_to_bottom_right()
        super().showEvent(event)
