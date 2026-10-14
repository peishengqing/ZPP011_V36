# -*- coding: utf-8 -*-
"""ARC-003 列控制器拆分回归：薄壳转发链路必须真实可达。

反证测试发现：现有 6 个碰 MainWindow 的测试**拦不住**薄壳被改成 return None
（注入后 14 tests 全过）。本文件专门覆盖「薄壳→controller」转发链路本身，
用 mock 打桩验证 MainWindow 薄壳确实把调用透传到 ColumnController。
"""
import os
import sys
import types
from unittest import mock

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

# 24 个搬迁方法的转发目标（ARC-003 拆分清单）
SHELLS = [
    "_toggle_column_lock", "_toggle_table_fullscreen", "_show_column_hide_dialog",
    "_is_column_effectively_hidden", "_ensure_column_visible_width",
    "_apply_column_visibility_by_name", "_set_column_widths", "_apply_default_width",
    "_get_user_config_dir", "_get_config_path", "_get_default_config_path",
    "_save_column_widths", "_load_column_widths", "_on_header_clicked",
    "_update_col_filter_hint", "_toggle_col_filter_mode", "_open_column_filter",
    "_open_empty_column_filter_popup", "_apply_multi_sort", "_update_sort_indicators",
    "_show_col_filter_clear_menu", "_clear_col_filter_by_name", "_clear_all_col_filters",
    "_drop_sort_columns",
]


def _load_main_window_cls():
    """离屏加载 MainWindow 类（不实例化，省 GUI 依赖）。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from gui_pyside6.main_window import MainWindow
    return MainWindow


def test_all_24_shells_exist_on_mainwindow():
    """MainWindow 侧 24 个薄壳方法必须都存在（外部信号绑定依赖它们）。"""
    MW = _load_main_window_cls()
    missing = [m for m in SHELLS if not callable(getattr(MW, m, None))]
    assert not missing, f"MainWindow 缺失薄壳方法: {missing}"


def test_all_24_methods_live_on_column_controller():
    """真实实现必须落在 ColumnController 上（不是还在 MainWindow 里重复定义）。"""
    from gui_pyside6.controllers.column_controller import ColumnController
    missing = [m for m in SHELLS if not callable(getattr(ColumnController, m, None))]
    assert not missing, f"ColumnController 缺失方法: {missing}"


def test_shells_forward_to_controller_not_stubbed():
    """核心防假通：薄壳必须真把调用送到 controller，而不是 return None/空实现。

    这是对反证测试发现的测试盲区的直接修补——注入 return None 时本测试必须失败。
    """
    MW = _load_main_window_cls()
    sentinel = object()
    for m in SHELLS:
        # 构造一个只有 column_controller 属性的假实例，避开 GUI 装配
        fake = types.SimpleNamespace(column_controller=mock.Mock())
        getattr(fake.column_controller, m).return_value = sentinel
        fn = MW.__dict__.get(m)
        assert fn is not None, f"{m} 未定义在 MainWindow 上"
        result = fn(fake, 1, key="v")
        assert result is sentinel, f"{m} 薄壳未透传返回值（疑似 return None 空实现）"
        getattr(fake.column_controller, m).assert_called_once_with(1, key="v")


def test_column_controller_holds_mw_backref():
    """controller 必须持有 MainWindow 反向引用（组合模式的连接点）。"""
    from gui_pyside6.controllers.column_controller import ColumnController
    ctrl = ColumnController(mock.Mock())
    assert hasattr(ctrl, "mw")


def test_ask_quarantine_reason_still_global_in_mainwindow():
    """防回归：_ask_quarantine_reason 是模块级函数，拆分时曾被误搬进 controller
    导致 main_window 内调用点 F821。断言它仍在 main_window 模块级可用。"""
    import gui_pyside6.main_window as mw_mod
    import gui_pyside6.controllers.column_controller as cc_mod
    assert hasattr(mw_mod, "_ask_quarantine_reason"), "main_window 缺 _ask_quarantine_reason"
    assert not hasattr(cc_mod, "_ask_quarantine_reason"), (
        "_ask_quarantine_reason 不应留在 column_controller（职责属隔离区）"
    )


def test_mainwindow_shrank_below_5000_lines():
    """结构护栏：ARC-003 拆分后 MainWindow 应降到 5000 行以下，防倒退回膨胀。"""
    MW = _load_main_window_cls()
    import inspect
    src_file = inspect.getfile(MW)
    with open(src_file, encoding="utf-8") as fh:
        lines = len(fh.readlines())
    assert lines < 5000, f"MainWindow 回升到 {lines} 行（阈值 5000），拆分成果可能已回退"