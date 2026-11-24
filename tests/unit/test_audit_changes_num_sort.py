# -*- coding: utf-8 -*-
"""变动提醒数值列排序回归（裴哥 2026-11-24 截图，v44.14）。

截图现象：净偏差数量(后) 升序结果
13.37 → -134.84 → -138.92 → -18.19 → -20.48 → -213.4 → 23.64 …
这是字符串字典序（str(float) 写入 QTableWidgetItem 的默认行为），
正确数值序应是 -213.4 → -138.92 → -134.84 → … → 13.37 → 23.64 → 256.0。

钉死 _NumericSortItem 三条：
1. 数值列按 float 大小排（正负/小数/千分位）；
2. 非数值（备注变动时旧值/新值是文字）回退字符串排，不崩；
3. 显示文本原样保留，不冒浮点长尾。
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtWidgets import QApplication, QTableWidget
from PySide6.QtCore import Qt

from gui_pyside6.main_window import _NumericSortItem


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _sorted_text(values, order=Qt.AscendingOrder):
    t = QTableWidget()
    t.setColumnCount(1)
    t.setRowCount(len(values))
    for i, v in enumerate(values):
        t.setItem(i, 0, _NumericSortItem(v))
    t.setSortingEnabled(True)
    t.sortItems(0, order)
    return [t.item(r, 0).text() for r in range(t.rowCount())]


def test_numeric_column_sorts_by_value(qapp):
    """裴哥截图那一列：必须按数值升序，不再是字典序。"""
    vals = ["13.37", "-134.84", "-138.92", "-18.19", "-20.48", "-213.4",
            "23.64", "-25.47", "256.0", "-26.05", "-26.78", "-27.95"]
    got = _sorted_text(vals)
    assert got == [str(v) for v in sorted(float(x) for x in vals)]
    assert got[0] == "-213.4"
    assert got[-1] == "256.0"


def test_numeric_column_descending(qapp):
    """降序同样按数值（表头二次点击）。"""
    vals = ["13.37", "-134.84", "-18.19", "23.64", "256.0"]
    got = _sorted_text(vals, Qt.DescendingOrder)
    assert got == [str(v) for v in sorted((float(x) for x in vals), reverse=True)]


def test_text_values_fallback(qapp):
    """备注变动场景：旧值/新值是文字，回退字符串排序且不崩。"""
    got = _sorted_text(["无备注", "吨包上料", "AI建议", "0"])
    assert got == sorted(["无备注", "吨包上料", "AI建议", "0"])


def test_mixed_values_no_crash(qapp):
    """数值与文字混在同一列（异常数据）也不能崩。"""
    vals = ["13.37", "文字", "-5", "", "2.0"]
    got = _sorted_text(vals)
    assert len(got) == len(vals)
    assert set(got) == set(vals)


def test_display_text_preserved(qapp):
    """显示文本原样：'13.37' 不能变成 '13.370000' 或 13.37 数值。"""
    got = _sorted_text(["13.37", "-134.84", "256.0"])
    assert all(isinstance(x, str) for x in got)
    assert "13.37" in got and "256.0" in got
