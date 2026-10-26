# -*- coding: utf-8 -*-
"""
未读汇总弹窗
非模态、右下角置顶、不阻塞主线程；分析/加载完成后显示 4 类未读条数，
每行可点击「查看」跳转对应看板。复用 AlertPopup 的安全写法（避免模态弹窗引发卡顿）。
裴哥 | 2026-08-01
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

import os

from gui_pyside6.utils.icons import get_icon, has_icon

# v43.152：打开看板失败时的运行日志（写失败静默吞掉，日志绝不反噬运行路径）
_RUNTIME_LOG = os.path.join("logs", "unread_summary.log")

# v43.264：旧调用方传 emoji 图标，这里做兼容映射（emoji → 线性图标名）。
# 新调用方直接传图标名（如 "box"）；两者都能渲染成 SVG 图标。
_LEGACY_ICONS = {
    "📦": "box", "📝": "edit", "🔄": "refresh", "⚠️": "alert",
    "📋": "clipboard", "🎉": "check", "🔒": "lock", "📊": "chart",
}


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
        # 宽度按内容算：原先写死 setFixedWidth(330)，标题「未读概览（本次分析）」
        # 在 12pt 加粗下刚好放不下，末尾括号被裁掉。
        # v43.264：360 也被裴哥判为「太窄」（行内挤、条数与按钮贴边）→
        # 舒适下限提到 420，并让行内留白与计数列宽度可预期。
        self.setMinimumWidth(420)
        self._setup_ui()
        self.adjustSize()
        self.setFixedWidth(max(self.width(), 420))
        self._move_to_bottom_right()
        # 注意：不再有「20 秒盲关」定时器——未清零就一直挂着。

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 标题行（图标 + 文字，整体居中）
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_icon = QLabel()
        title_icon.setFixedSize(18, 18)
        title_icon.setPixmap(get_icon("clipboard", 16).pixmap(16, 16))
        title_row.addStretch()
        title_row.addWidget(title_icon)
        title = QLabel("未读概览（本次分析）")
        title.setObjectName("unreadSummaryTitle")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # v42.29: 副标题——4 类全部清零时显示「全清零啦」+ 文字提示，
        # 数据再有未读会自动隐藏（与 mark_all_clear / clear_all_clear 配对）。
        self._all_clear_row = QHBoxLayout()
        self._all_clear_row.setSpacing(6)
        self._all_clear_icon = QLabel()
        self._all_clear_icon.setFixedSize(16, 16)
        self._all_clear_icon.setPixmap(get_icon("check", 14, "#1F7A4D").pixmap(14, 14))
        self._all_clear_row.addStretch()
        self._all_clear_row.addWidget(self._all_clear_icon)
        self._all_clear_label = QLabel("全清零啦")
        self._all_clear_label.setObjectName("unreadAllClear")
        self._all_clear_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        self._all_clear_label.setAlignment(Qt.AlignCenter)
        self._all_clear_row.addWidget(self._all_clear_label)
        self._all_clear_row.addStretch()
        self._all_clear_label.hide()
        self._all_clear_icon.hide()
        layout.addLayout(self._all_clear_row)

        for it in self._items:
            row = QFrame(self)
            row.setObjectName("unreadRow")
            rlayout = QHBoxLayout(row)
            rlayout.setContentsMargins(10, 7, 10, 7)
            rlayout.setSpacing(10)

            # 图标：传图标名直接渲染；传旧 emoji 做兼容映射
            raw_icon = str(it.get("icon", "") or "")
            icon_name = _LEGACY_ICONS.get(raw_icon, raw_icon)
            icon_label = QLabel()
            icon_label.setFixedSize(18, 18)
            if icon_name and has_icon(icon_name):
                icon_label.setPixmap(get_icon(icon_name, 16).pixmap(16, 16))
            else:
                icon_label.setText(raw_icon)
            name_label = QLabel(it["label"])
            name_label.setFont(QFont("Microsoft YaHei", 10))
            count_label = QLabel(f"{it['count']} 条未读")
            count_label.setObjectName("unreadCount")
            count_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            # 计数列定宽右对齐：4 行数字上下对齐，不再随名称长度飘
            count_label.setMinimumWidth(84)
            count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            view_btn = QPushButton("查看")
            view_btn.setFixedWidth(56)
            view_btn.setMinimumHeight(26)
            # v43.152：0 条未读的类别直接置灰不可点。原先点了只会弹一个
            # 「暂无记录」提示框，用户以为是程序坏了；从源头消除这种困惑。
            _n = it.get("count", 0)
            if _n <= 0:
                view_btn.setEnabled(False)
                view_btn.setToolTip("暂无未读记录，无需查看")
            else:
                view_btn.setToolTip("打开%s（%d 条未读）" % (it["label"], _n))
            # 用默认参数绑定，避免闭包复用同一 callback
            view_btn.clicked.connect(
                lambda _checked=False, cb=it["callback"], lb=it["label"]:
                    self._open_board(cb, lb)
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

    def mark_all_clear(self):
        """4 类未读全部清零时显示「全清零啦」副标题。"""
        try:
            self._all_clear_label.show()
            self._all_clear_icon.show()
        except RuntimeError:
            pass

    def clear_all_clear(self):
        """有任意未读时（清零状态结束）隐藏「全清零啦」副标题。"""
        try:
            self._all_clear_label.hide()
            self._all_clear_icon.hide()
        except RuntimeError:
            pass

    def _open_board(self, callback, label=""):
        """点击「查看」→ 打开对应看板（用户主动触发，此时分析已完成、主表就绪）。

        先隐藏本弹窗，避免遮挡模态看板；看板关闭后若本弹窗未被主窗口清零关闭，
        则恢复显示（满足「没清零就挂着」）。

        v43.152：原 `except Exception: pass` 会把真实异常彻底吞掉——用户点「查看」
        什么都不会发生，开发者也无从查起（与 v42.18/v43.143 的静默失效同类）。
        改为弹错误提示显示异常原文 + 写运行日志。
        """
        self.hide()
        try:
            if callable(callback):
                callback()
        except Exception as e:
            self._report_open_failed(label, e)
        if not self._closed:
            self.show()
            self._move_to_bottom_right()

    def _report_open_failed(self, label, err):
        """v43.152：callback 抛异常时的可见反馈（不再静默吞）。"""
        import traceback
        traceback.print_exc()
        try:
            with open(_RUNTIME_LOG, "a", encoding="utf-8") as fh:
                fh.write("[未读概览] 打开%s失败：%r\n" % (label or "看板", err))
                fh.write(traceback.format_exc())
        except Exception:
            pass
        try:
            QMessageBox.warning(None, "打开失败",
                                "无法打开%s，请重试或改用顶部菜单。\n\n错误：%s" % (label or "该看板", err))
        except Exception:
            pass

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
