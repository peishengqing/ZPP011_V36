# -*- coding: utf-8 -*-
"""整改回归：DashboardManager 的提示框父窗口必须是主窗口（v43.406）。

背景（审核报告 P0-2）：`DashboardManager` 是纯 Python 类（不是 QWidget），
但全部 21 处 `QMessageBox.*(self, ...)` 都把 self 当 parent 传进去。PySide6 的
parent 形参要求 QWidget，一旦触发提示/异常分支就可能抛 TypeError——而这些分支
恰好都写在 except 里，真实错误会被“提示框自身报错”覆盖。

本测试用 Mock 拦截 QMessageBox，直接断言 parent 是传入的主窗口对象。
"""
import os
import sys
from unittest import mock

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make_manager(qapp):
    from PySide6.QtWidgets import QWidget
    from gui_pyside6.dashboard_manager import DashboardManager

    mw = QWidget()
    mw._get_master_df = lambda: None          # 触发「暂无数据，请先分析」分支
    mw.view_model = mock.Mock()
    return DashboardManager(mw), mw


def test_information_uses_main_window_as_parent(qapp):
    mgr, mw = _make_manager(qapp)
    with mock.patch("gui_pyside6.dashboard_manager.QMessageBox.information") as info:
        mgr.show_neg_loss_dashboard()
    assert info.call_count == 1
    parent = info.call_args.args[0]
    assert parent is mw, f"提示框父窗口应为 MainWindow，实际为 {parent!r}"


def test_critical_in_except_branch_uses_main_window(qapp):
    """异常分支（P0-2 的高危路径）同样必须是主窗口，否则报错会被二次异常盖住。"""
    mgr, mw = _make_manager(qapp)
    mw._get_master_df = mock.Mock(side_effect=RuntimeError("boom"))
    with mock.patch("gui_pyside6.dashboard_manager.QMessageBox.critical") as crit:
        mgr.show_semi_dashboard()
    assert crit.call_count == 1
    assert crit.call_args.args[0] is mw
    assert "boom" in str(crit.call_args.args[2])
