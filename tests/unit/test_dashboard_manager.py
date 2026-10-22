# -*- coding: utf-8 -*-
"""DashboardManager 单元测试 (重构 v43.214)"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

# 设置 offscreen Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui_pyside6.dashboard_manager import DashboardManager
from unittest.mock import Mock, MagicMock, patch


def test_dashboard_manager_init():
    """测试 DashboardManager 初始化."""
    mw = Mock()
    manager = DashboardManager(mw)
    assert manager.mw == mw
    assert hasattr(manager, '_open_dialogs')


def test_open_dialog_focus_existing():
    """测试打开已存在的对话框时聚焦."""
    mw = Mock()
    manager = DashboardManager(mw)

    dialog = MagicMock()
    dialog.closeEvent = False
    manager._open_dialogs["test"] = dialog

    manager._open_dialog(dialog, "test")

    dialog.raise_.assert_called_once()
    dialog.activateWindow.assert_called_once()


def test_open_dialog_new_dialog():
    """测试打开新对话框时正常执行."""
    mw = Mock()
    manager = DashboardManager(mw)

    dialog = MagicMock()
    dialog.closeEvent = None

    manager._open_dialog(dialog, "new_test")

    dialog.exec.assert_called_once()
    assert "new_test" in manager._open_dialogs
    assert manager._open_dialogs["new_test"] == dialog


def test_integration_methods_exist():
    """测试 DashboardManager 的集成方法都存在."""
    mw = Mock()
    manager = DashboardManager(mw)

    # 所有看板打开方法应该存在
    methods = [
        'show_alert_dashboard',
        'show_deviation_warning_dashboard',
        'show_neg_loss_dashboard',
        'show_pos_loss_dashboard',
        'show_data_stability_dashboard',
        'show_quarantine_review_dashboard',
        'show_alt_chain_dashboard',
        'show_material_profile',
        'show_semi_dashboard',
        'show_dashboard',
    ]

    for method in methods:
        assert hasattr(manager, method), f"缺少方法: {method}"
        assert callable(getattr(manager, method)), f"方法不是可调用: {method}"


def test_show_material_profile_none_params():
    """测试 _show_material_profile 无参调用."""
    mw = Mock()
    mw.table_view.selectionModel().selectedIndexes.return_value = []
    # 创建模拟 iloc 链的 MagicMock
    mock_iloc = MagicMock()
    mock_iloc.get.side_effect = lambda key, default: default
    mock_df = MagicMock()
    mock_df.iloc = mock_iloc
    mw.source_model.getDataFrame.return_value = mock_df

    manager = DashboardManager(mw)

    # 应该返回并显示提示信息，而不是 crash
    with patch('PySide6.QtWidgets.QMessageBox.information') as mock_info:
        result = manager.show_material_profile()
        assert result is None
        mock_info.assert_called_once()
