# -*- coding: utf-8 -*-
"""v44.17 列顺序持久化（方案B：列设置对话框）回归。

覆盖四段核心链路（不构造完整看板，用最小 QTableView + DataFrameModel）：
- ColumnOrderDialog：上移/下移/置底 + 恢复默认 + 取结果；
- BoardLayoutManager.apply_column_order：应用视觉顺序 + 落盘 + 幂等；
- open_board_column_order：读顺序→弹框→应用+保存 的编排（mock 对话框）。
set_data 末尾的「恢复已保存顺序」已由 tools/gui_smoke_offscreen.py 的
⑦⑧（三看板构建 + 灌数据）间接触达，不在此重复。
"""
import os
import sys
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QTableView, QDialog

from gui_pyside6.models.data_frame_model import DataFrameModel
from gui_pyside6.utils.board_layouts import BoardLayoutManager
import gui_pyside6.utils.board_layouts as bl
from gui_pyside6.dialogs.column_order_dialog import ColumnOrderDialog
import gui_pyside6.dialogs.column_order_dialog as cod


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _table(df):
    tv = QTableView()
    m = DataFrameModel()
    m.setDataFrame(df)
    tv.setModel(m)
    return tv


def test_dialog_reorder_move_default(app):
    cur = ["A", "B", "C", "D"]
    dlg = ColumnOrderDialog(None, title="t", current_order=cur, default_order=cur)
    assert dlg.result_order() == cur
    dlg._list.setCurrentRow(3)      # D
    dlg._move(-1)                   # 上移 → 到 C 位
    assert dlg.result_order() == ["A", "B", "D", "C"]
    dlg._list.setCurrentRow(0)      # A
    dlg._move(100)                  # 置底
    assert dlg.result_order() == ["B", "D", "C", "A"]
    dlg._restore_default()
    assert dlg.result_order() == cur


def test_dialog_restore_default_appends_new(app):
    # 默认序列里没有的列（B/NEW）按当前顺序殿后，不丢列
    cur = ["A", "B", "C", "NEW"]
    dlg = ColumnOrderDialog(None, title="t", current_order=cur, default_order=["A", "C"])
    dlg._restore_default()
    assert dlg.result_order() == ["A", "C", "B", "NEW"]


def test_apply_column_order_table_and_disk(app, tmp_path, monkeypatch):
    monkeypatch.setattr(bl, "BOARD_CONFIG_PATH", str(tmp_path / "bl.json"))
    tv = _table(pd.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]}))
    # DataFrameModel 会自补「状态/已读来源」列；apply 的幂等比较针对**完整**视觉顺序
    full = BoardLayoutManager.current_column_order(tv)
    tail = [nm for nm in full if nm not in ("a", "b", "c", "d")]
    new_full = ["d", "b", "a", "c"] + tail
    assert BoardLayoutManager.apply_column_order(tv, "bd", new_full) is True
    assert BoardLayoutManager.current_column_order(tv) == new_full
    assert BoardLayoutManager.load_board_order("bd") == new_full
    # 顺序未变时 apply 幂等（不重复写盘）→ False
    assert BoardLayoutManager.apply_column_order(tv, "bd", new_full) is False


def test_open_board_column_order_orchestrates(app, tmp_path, monkeypatch):
    monkeypatch.setattr(bl, "BOARD_CONFIG_PATH", str(tmp_path / "bl.json"))
    tv = _table(pd.DataFrame({"a": [1], "b": [2], "c": [3]}))
    fake = mock.Mock()
    fake.exec.return_value = QDialog.Accepted
    fake.result_order.return_value = ["c", "a", "b"]
    monkeypatch.setattr(cod, "ColumnOrderDialog", lambda *a, **k: fake)

    assert bl.open_board_column_order(None, tv, "x", "标题") is True
    # 对话框给出的是核心 3 列顺序；DataFrameModel 自补列殿后
    assert BoardLayoutManager.current_column_order(tv)[:3] == ["c", "a", "b"]
    assert BoardLayoutManager.load_board_order("x") == ["c", "a", "b"]

    # 取消 → 表格与落盘都不变
    fake.exec.return_value = QDialog.Rejected
    assert bl.open_board_column_order(None, tv, "x", "标题") is False
    assert BoardLayoutManager.current_column_order(tv)[:3] == ["c", "a", "b"]

