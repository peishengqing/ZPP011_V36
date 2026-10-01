# -*- coding: utf-8 -*-
"""列头点击链路回归测试。

背景（v43.119 根因）：QTableView.setModel 会把表头的 sectionsClickable 重置为默认
False，而本项目 PySide6 版本下 setSortingEnabled(True) 不会把它补回。表头若不自己
重新打开 clickable，列头点击就不发射 sectionClicked —— 表现即用户反馈的「点列头既
不能排序也不能筛选」。v43.110~v43.119 反复回归的正是这条链路，故在此固化保护。

无需真实显示：QT_QPA_PLATFORM=offscreen 即可运行。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHeaderView, QTableView

from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _Model(QAbstractTableModel):
    def rowCount(self, parent=QModelIndex()):
        return 5

    def columnCount(self, parent=QModelIndex()):
        return 4

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return f"r{index.row()}c{index.column()}"
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return f"col{section}"
        return None


class _PlainHeader(QHeaderView):
    """对照组：不覆写 setModel 的裸表头，即 v43.119 之前的表头行为。"""


def _click_section_1(header, view):
    """模拟真实鼠标：点击表头第 1 列（视觉列）中部。"""
    view.resize(500, 200)
    view.show()
    x = header.sectionViewportPosition(1) + header.sectionSize(1) // 2
    y = max(1, header.height() // 2)
    QTest.mouseClick(header.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(x, y))


def _build(view, header_cls, sorting_first):
    header = header_cls(Qt.Horizontal, view)
    view.setHorizontalHeader(header)
    seen = []
    header.sectionClicked.connect(seen.append)
    if sorting_first:
        view.setSortingEnabled(True)  # 对话框顺序：enable_click_sort 先于 setModel
    view.setModel(_Model())
    return header, seen


def test_shared_header_emits_section_clicked_after_setmodel(qapp):
    """核心回归：共享表头在 setModel 之后仍能发射 sectionClicked（对话框真实顺序）。"""
    view = QTableView()
    header, seen = _build(view, SortBadgeHeader, sorting_first=True)
    _click_section_1(header, view)
    assert seen == [1]


def test_shared_header_emits_section_clicked_without_sorting_enabled(qapp):
    """主表顺序：不调用 setSortingEnabled，setModel 后点击同样有效。"""
    view = QTableView()
    header, seen = _build(view, SortBadgeHeader, sorting_first=False)
    _click_section_1(header, view)
    assert seen == [1]


def test_plain_header_documents_root_cause(qapp):
    """根因对照组：裸表头 setModel 后点击不发射信号。

    本用例固化的是 PySide6 6.11.1 上的实测行为。若某次 Qt 升级后本用例失败，
    说明 setModel 不再重置 clickable，届时 SortBadgeHeader.setModel 的兜底可重新评估。
    """
    view = QTableView()
    header, seen = _build(view, _PlainHeader, sorting_first=False)
    _click_section_1(header, view)
    assert seen == []


def test_main_window_reuses_shared_header(qapp):
    """主表必须复用共享表头（本地副本没有 setModel 兜底，属 P1-1 回归点）。"""
    import gui_pyside6.main_window as mw

    assert mw.SortBadgeHeader is SortBadgeHeader
    assert "setModel" in mw.SortBadgeHeader.__dict__
