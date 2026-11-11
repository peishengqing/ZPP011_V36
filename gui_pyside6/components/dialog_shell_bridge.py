# -*- coding: utf-8 -*-
"""重型弹窗接入 DashboardShell 的桥接器（v43.341）

不剥壳、不重写：AlertDialog / DeviationWarningDialog 的窗口级逻辑
（closeEvent 断连、open_maximized 的 Win32 硬兜底、mark_row_read、
batch_mark_read / batch_mark_unread、筛选/导出/双击定位）全部保留。

接入方式只有两步：
  1. ``setup_ui()`` 开头把 ``QVBoxLayout(self)`` 改成 ``QVBoxLayout(host)``，
     后面几百行 ``layout.addWidget(...)`` 一行不动；
  2. ``__init__`` 末尾（且必须在 apply_board_visual 之后，才能合并其 QSS）
     调用本模块 ``install_dialog_shell(dialog, host, title, status)``。

这样 dialog 自身仍是 QDialog，shell 只是它的根内容 widget，
title_changed / status_changed / 亮暗主题同步由 shell 提供。
"""
from PySide6.QtWidgets import QVBoxLayout

from gui_pyside6.components.dashboard_shell import DashboardShell
from utils.theme_manager import Thm


def install_dialog_shell(dialog, host, title, status=None):
    """把 host 里的原内容包进 DashboardShell，作为 dialog 的根内容。

    返回 shell，并挂到 ``dialog.dashboard_shell`` 供后续状态更新。
    """
    # v43.345：Shell 不再依赖 parent，直接创建即可，主题由全局主题管理器 Thm 驱动。
    # DashboardShell 构造函数会读取当前 Thm.is_dark 并加载对应的 QSS。
    shell = DashboardShell()
    shell.set_title(title)
    shell.set_content(host)
    shell.set_status(status or "")

    # apply_board_visual 在 install 之前就把「亮色」BOARD_QSS 挂在 dialog 级
    # （含 QDialog#zppBoardDialog QTableView{background:#ffffff}）。它会向下级联到
    # 所有子控件，且选择器比 shell 的裸 QTableView 更具体，暗色下会把表格刷成
    # 白底 + 浅色字，实测出现白色横条、文字几乎不可读。
    #   · 亮色：把 dialog 级规则追加到 shell 后面，保住原有表格视觉；
    #   · 暗色：清空 dialog 级 QSS，也不合并 —— 交给 app 级 dark_theme.qss
    #     与 shell 级 dark_dashboard.qss 接管。
    # 只动 dialog 的样式挂载，不碰 board_visual.py（五个看板共用，影响面大）。
    try:
        prev = dialog.styleSheet() or ""
        is_dark = Thm.is_dark
        if not is_dark:
            if prev:
                shell.setStyleSheet(shell.styleSheet() + "\n" + prev)
        elif prev:
            dialog.setStyleSheet("")
    except Exception:
        pass

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    outer.addWidget(shell)

    dialog.dashboard_shell = shell
    dialog.shell_host = host
    return shell


def update_shell_status(dialog, text):
    """供弹窗在筛选/标记已读后刷新统一状态条（不存在 shell 时安全空操作）。"""
    shell = getattr(dialog, 'dashboard_shell', None)
    if shell is not None:
        shell.set_status(text)
