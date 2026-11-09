# -*- coding: utf-8 -*-
"""v43.328：SortBadgeHeader.update() 无参重绘回归测试。

PySide6 6.6.3 下 QAbstractItemView.update(index) 槽遮蔽了 QWidget.update() 无参重载，
导致项目里所有 `header.update()` 抛 TypeError（点列头排序时必现）。
本测试钉死：无参调用不抛、确实转发到 QWidget.update、带 index 调用仍走父类。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QModelIndex, QRect  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402
from unittest.mock import patch  # noqa: E402

from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_update_no_args_does_not_raise(qapp):
    """回归核心：修复前 `header.update()` 直接抛 TypeError。"""
    h = SortBadgeHeader(Qt.Horizontal)
    h.update()  # 不抛即 PASS


def test_update_no_args_forwards_to_qwidget(qapp):
    """无参调用必须显式转到 QWidget.update(self)，而非落到 index 槽。"""
    h = SortBadgeHeader(Qt.Horizontal)
    with patch.object(QWidget, "update", autospec=True) as m:
        h.update()
    assert m.call_count == 1, "无参 update 应转发到 QWidget.update 一次"
    assert m.call_args[0][0] is h


def test_update_with_rect_forwards_to_qwidget(qapp):
    """QWidget 的 QRect 重载仍可用（不被 index 槽吞掉）。"""
    h = SortBadgeHeader(Qt.Horizontal)
    with patch.object(QWidget, "update", autospec=True) as m:
        h.update(QRect(0, 0, 10, 10))
    assert m.call_count == 1
    assert m.call_args[0][0] is h


def test_update_with_model_index_still_goes_to_parent(qapp):
    """带 QModelIndex 的调用仍走 QAbstractItemView 槽，避免破坏 Qt 内部刷新。"""
    h = SortBadgeHeader(Qt.Horizontal)
    with patch.object(QWidget, "update", autospec=True) as qw, \
         patch("PySide6.QtWidgets.QHeaderView.update", autospec=True) as hv:
        h.update(QModelIndex())
    assert hv.call_count == 1, "带 index 的 update 应交给父类槽"
    assert qw.call_count == 0


def test_all_project_call_sites_use_no_arg_form():
    """结构护栏：项目里表头重绘调用点必须保持无参形式（被本次修复覆盖）。

    若有人改成 `header.update(some_index)` 走父类槽，自绘角标/漏斗将不再重画。
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    targets = [
        "gui_pyside6/controllers/column_controller.py",
        "gui_pyside6/main_window.py",
        "gui_pyside6/view_manager.py",
        "gui_pyside6/analysis_orchestrator.py",
        "gui_pyside6/utils/column_filter.py",
    ]
    total = 0
    for rel in targets:
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                s = line.strip()
                if s.startswith('#'):
                    continue
                if ('header.update()' in s or '_sort_header.update()' in s
                        or 'self.header.update()' in s):
                    total += 1
    assert total >= 8, "表头无参重绘调用点数量异常，可能已被改写"
