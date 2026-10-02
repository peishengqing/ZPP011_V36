# -*- coding: utf-8 -*-
"""列头筛选漏斗图标回归测试：已被筛选列在列名左侧显示漏斗，点漏斗直接打开该列筛选。

无需真实显示：QT_QPA_PLATFORM=offscreen 即可运行。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView

from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader
from gui_pyside6.utils.column_filter import ColumnFilterController
from tests.unit.test_header_click import _Model, _build


def _click_funnel_zone(header, col):
    """先触发 paintEvent 计算 _funnel_rects，再点击该列列头左缘（漏斗命中区）。"""
    view = header.parent()
    view.resize(600, 200)
    view.show()
    QTest.qWait(1)
    x = header.sectionViewportPosition(col) + 5
    y = max(1, header.height() // 2)
    QTest.mouseClick(header.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(x, y))


def test_filtered_column_funnel_click_triggers_callback(qapp):
    """已筛选列：点中列头左缘漏斗区 → 回调触发。"""
    view = QTableView()
    header, _ = _build(view, SortBadgeHeader, sorting_first=True)
    seen = []
    header.set_filtered_columns_getter(lambda: {1})
    header.set_funnel_clicked(lambda c: seen.append(c))
    _click_funnel_zone(header, 1)
    assert 1 in seen


def test_unfiltered_column_center_click_keeps_section_clicked(qapp):
    """未筛选列：点列头中部 → 不触发漏斗回调，sectionClicked 路由不变。"""
    view = QTableView()
    header, clicked = _build(view, SortBadgeHeader, sorting_first=True)
    funnel_seen = []
    header.set_filtered_columns_getter(lambda: set())
    header.set_funnel_clicked(lambda c: funnel_seen.append(c))
    view.resize(600, 200)
    view.show()
    x = header.sectionViewportPosition(2) + header.sectionSize(2) // 2
    y = max(1, header.height() // 2)
    QTest.mouseClick(header.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(x, y))
    assert funnel_seen == []
    assert 2 in clicked


def test_column_filter_controller_wires_funnel_click(qapp):
    """ColumnFilterController：构造后点漏斗命中区 → open_filter 被调用（异步弹层）。"""
    view = QTableView()
    header, _ = _build(view, SortBadgeHeader, sorting_first=True)
    view.setModel(_Model())
    ctrl = ColumnFilterController(
        view, header, header,
        source_model_getter=lambda: None,
        apply_filter_cb=lambda: None,
        skip_cols=(0,))
    opened = []
    ctrl.open_filter = lambda col: opened.append(col)
    header.set_filtered_columns_getter(lambda: ctrl.filtered_col_set)
    ctrl._filtered_col_set.add(1)
    _click_funnel_zone(header, 1)
    QApplication.processEvents()
    assert 1 in opened
