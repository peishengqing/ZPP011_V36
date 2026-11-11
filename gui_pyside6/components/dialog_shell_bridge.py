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

    # apply_board_visual 在 install 之前就把 dialog 级 QSS 挂在 dialog 上
    # （含 QDialog#zppBoardDialog QTableView 等更具体的选择器）。它会向下级联到
    # 所有子控件，若与 shell 的裸 QTableView 规则不一致，实测会出现「深色筛选区 +
    # 白色表格」撕裂。
    # v43.344 的临时办法是按主题分支：亮色合并、暗色直接清空 dialog 级 QSS，
    # 交给 app 级 dark_theme.qss 兜着 —— 那是在绕过「BOARD_QSS 只有浅色值」这个
    # 真实病因。现在 dialog 级 QSS 由 tokens.build_board_qss(theme) 生成，
    # 暗色有自己的取值（设计稿第一期第 2 条），绕行可以拆掉：
    # **两种主题都合并**，视觉来源唯一。
    try:
        prev = dialog.styleSheet() or ""
        if prev:
            shell.setStyleSheet(shell.styleSheet() + "\n" + prev)
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
