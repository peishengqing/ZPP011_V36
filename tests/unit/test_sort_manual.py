# -*- coding: utf-8 -*-
"""手动排序链路冒烟测试（模拟点击表头、Ctrl+点击）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView

from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _Model(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows = [[f"r{i}c{j}" for j in range(4)] for i in range(5)]
    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)
    def columnCount(self, parent=QModelIndex()):
        return 4
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.rows[index.row()][index.column()]
        return None


def _click_section_1(header, view):
    view.resize(500, 200)
    view.show()
    x = header.sectionViewportPosition(1) + header.sectionSize(1) // 2
    y = max(1, header.height() // 2)
    QTest.mouseClick(header.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(x, y))


def test_header_emits_section_clicked(qapp):
    view = QTableView()
    header = SortBadgeHeader(Qt.Horizontal, view)
    view.setHorizontalHeader(header)
    view.setSortingEnabled(False)
    view.horizontalHeader().setSectionsClickable(True)
    view.setModel(_Model())
    seen = []
    header.sectionClicked.connect(seen.append)
    _click_section_1(header, view)
    assert seen == [1], f"sectionClicked not emitted: {seen}"
