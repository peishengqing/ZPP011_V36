# -*- coding: utf-8 -*-
"""行首勾选道回归测试（v43.350 第五期G1）。

要守住的三件事：
1. 勾选道是**垂直表头**，不是模型里的真列 —— 模型列数/列号一个都不能动
   （全仓 20+ 处按列号取数、排序、列宽、复制都建立在「模型列号 == DataFrame 列号」上）；
2. 勾选状态 == 选中状态，不引入第二套 —— 点道就是在 selectionModel 里增删整行；
3. 左上角全选框由 MainTableView 手工摆到两块表头的交叉区
   （PySide6 6.6.3 的 setCornerWidget 只会放右下角）。

无需真实显示：QT_QPA_PLATFORM=offscreen 即可运行。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView

from gui_pyside6.themes.tokens import SIZE_PX
from gui_pyside6.widgets.main_table_view import MainTableView
from gui_pyside6.widgets.row_check_header import (
    _OFF, _ON, _PART, RowCheckHeader, SelectAllCheck,
)

ROWS, COLS = 6, 4


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _Model(QAbstractTableModel):
    def rowCount(self, parent=QModelIndex()):
        return ROWS

    def columnCount(self, parent=QModelIndex()):
        return COLS

    def data(self, index, role=Qt.DisplayRole):
        return f"r{index.row()}c{index.column()}" if role == Qt.DisplayRole else None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        return str(section + 1) if orientation == Qt.Vertical else f"col{section}"


def _build(view=None):
    view = view or QTableView()
    view.setModel(_Model())
    view.setSelectionBehavior(QTableView.SelectItems)
    lane = RowCheckHeader(view)
    view.setVerticalHeader(lane)
    # 表头要拿到真实节区几何才能按坐标点：先布局好再点
    view.resize(520, 260)
    view.show()
    QTest.qWait(1)
    return view, lane


def _click_lane(lane, row):
    y = lane.sectionViewportPosition(row) + lane.sectionSize(row) // 2
    QTest.mouseClick(lane.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(12, y))


def _selected_rows(view):
    return sorted({i.row() for i in view.selectionModel().selectedIndexes()})


def test_lane_is_header_not_column(qapp):
    """勾选道不占模型列：列数仍是 COLS，行号仍归垂直表头。"""
    view, lane = _build()
    assert view.model().columnCount() == COLS
    assert lane.count() == ROWS
    assert lane.width() == lane.sizeHint().width() == SIZE_PX["tableCheckLane"]
    assert view.verticalHeader() is lane


def test_click_lane_selects_that_row_only(qapp):
    """点第 3 行的道 → selectionModel 里只有这一行，且整行被选中。"""
    view, lane = _build()
    fired = []
    lane.checked_changed.connect(lambda: fired.append(1))
    _click_lane(lane, 2)
    assert _selected_rows(view) == [2]
    assert view.selectionModel().isRowSelected(2, QModelIndex())
    assert lane.is_row_checked(2) and not lane.is_row_checked(1)
    assert fired, "勾选态变化要发信号（外部按钮可用性靠它）"


def test_toggle_is_additive_and_reversible(qapp):
    """累加勾选：勾第二行不清第一行；再点一次只取消这一行。"""
    view, lane = _build()
    lane.toggle_row(0)
    lane.toggle_row(3)
    assert _selected_rows(view) == [0, 3]
    lane.toggle_row(0)
    assert _selected_rows(view) == [3]


def test_check_state_three_levels(qapp):
    view, lane = _build()
    assert lane.check_state() == _OFF
    lane.toggle_row(1)
    assert lane.check_state() == _PART
    lane.set_all(True)
    assert lane.check_state() == _ON and lane.total_rows() == ROWS
    lane.set_all(False)
    assert lane.check_state() == _OFF and not view.selectionModel().hasSelection()


def test_corner_click_reports_desired_state(qapp):
    """角标只报「该不该全选」：非全勾时 True，已全勾时 False。"""
    view = MainTableView()
    view.setModel(_Model())
    lane = RowCheckHeader(view)
    view.setVerticalHeader(lane)
    corner = SelectAllCheck(lane)
    view.set_corner_widget(corner)
    view.show()
    QTest.qWait(1)
    got = []
    corner.toggled.connect(got.append)
    lane.toggle_row(0)
    QTest.mouseClick(corner, Qt.LeftButton, Qt.NoModifier,
                     QPoint(corner.width() // 2, corner.height() // 2))
    assert got == [True]
    lane.set_all(True)
    QTest.mouseClick(corner, Qt.LeftButton, Qt.NoModifier,
                     QPoint(corner.width() // 2, corner.height() // 2))
    assert got == [True, False]
    view.hide()


def test_selection_inside_table_shows_check(qapp):
    """表格里选中首列单元格 → 道上也显示勾上（同一套状态，不是两套）。"""
    view, lane = _build()
    view.setCurrentIndex(view.model().index(4, 0))
    assert lane.is_row_checked(4)


def test_corner_widget_sits_on_header_intersection(qapp):
    """MainTableView 把角标摆在交叉区，且随窗口尺寸变化重摆。"""
    view = MainTableView()
    view.setModel(_Model())
    lane = RowCheckHeader(view)
    view.setVerticalHeader(lane)
    corner = SelectAllCheck(lane)
    view.set_corner_widget(corner)
    view.resize(600, 300)
    view.show()
    QTest.qWait(1)
    hh = view.horizontalHeader()
    assert (corner.x(), corner.y()) == (lane.x(), hh.y())
    assert (corner.width(), corner.height()) == (lane.width(), hh.height())
    view.resize(420, 260)
    QTest.qWait(1)
    assert (corner.x(), corner.y()) == (lane.x(), hh.y())
    view.hide()
