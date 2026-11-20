# -*- coding: utf-8 -*-
"""未读看板「标记已读」回归（v44.07，裴哥 2026-11-20：不单单只能看）。

钉死三件事：
1. MainWindow.mark_rows_read_by_ids：走 data_service.mark_changes_as_read 写库、
   主表 _read=1/_read_source=manual 同步、返回实际生效条数；
2. 未读看板「全部标记已读」：当前筛选未读行全标 + 确认框取消时不落库；
3. 未读看板「选中标记已读」：只标选中行；标完 KPI 掩码/筛选视图就地刷新。
data_service 一律打桩，不写真库（看板构造期的 DB 只读路径沿用既有看板测试）。
"""
import os
import sys
import types

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QMessageBox

import gui_pyside6.shells.unread_dashboard as ud_mod
from gui_pyside6.models.data_frame_model import DataFrameModel


def _master_df():
    n = 4
    return pd.DataFrame({
        "data_id": ["D%d" % i for i in range(n)],
        "_read": [0] * n,
        # 全部落「隔离区」纯分类：保证看板默认视图有行可见
        "_quarantined": [1] * n,
        "_post_audit_changed": [0] * n,
        "是否替代料": ["否"] * n,
        "物料编码": ["1000%02d" % i for i in range(n)],
        "物料名称": ["物料%d" % i for i in range(n)],
        "净偏差数量": [-1.0 * i for i in range(n)],
    })


class _StubDataService:
    """mark_changes_as_read 打桩：记录调用，返回 (条数, did 集合)。"""

    def __init__(self):
        self.calls = []

    def mark_changes_as_read(self, changes, df):
        dids = [str(c.get("data_id")) for c in changes]
        self.calls.append(dids)
        return len(dids), set(dids)


class _FakeMB:
    """QMessageBox 打桩：question 返回预设答案。"""
    Yes = QMessageBox.Yes
    No = QMessageBox.No
    answer = QMessageBox.Yes

    @staticmethod
    def question(*a, **k):
        return _FakeMB.answer

    @staticmethod
    def warning(*a, **k):
        return QMessageBox.StandardButton.Ok


def _fake_mw(df):
    from gui_pyside6.main_window import MainWindow

    fake = types.SimpleNamespace()
    fake.source_model = DataFrameModel()
    fake.source_model.setDataFrame(df)
    fake.view_model = types.SimpleNamespace(df=None)
    fake.data_service = _StubDataService()
    fake.manual_marked = []
    fake.popup_refreshed = []
    fake._on_manual_marked = lambda n: fake.manual_marked.append(n)
    fake._refresh_unread_popup = lambda: fake.popup_refreshed.append(1)
    # 绑定真方法（沿用 test_audit_queue_badge 手法，不建真窗口）
    fake.mark_rows_read_by_ids = (
        lambda dids: MainWindow.mark_rows_read_by_ids(fake, dids))
    return fake


def _make_board(df):
    from gui_pyside6.shells.unread_dashboard import UnreadDashboard
    mw = _fake_mw(df)
    board = UnreadDashboard(df.copy(), mw)
    if board.original_df is None:
        board.set_data(df.copy())
    return board, mw


# ---------- MainWindow.mark_rows_read_by_ids ----------

def test_mark_rows_read_by_ids_syncs_master_and_persists():
    mw = _fake_mw(_master_df())
    n = mw.mark_rows_read_by_ids(["D0", "D2"])
    assert n == 2
    assert mw.data_service.calls == [["D0", "D2"]]
    df = mw.source_model.getDataFrame()
    assert list(df["_read"]) == [1, 0, 1, 0]
    assert df.loc[df["data_id"] == "D0", "_read_source"].iloc[0] == "manual"
    assert mw.manual_marked == [2]
    assert len(mw.popup_refreshed) == 1


def test_mark_rows_read_by_ids_unknown_ids_returns_zero():
    mw = _fake_mw(_master_df())
    assert mw.mark_rows_read_by_ids(["X9"]) == 0  # 主表未命中任何行
    assert list(mw.source_model.getDataFrame()["_read"]) == [0, 0, 0, 0]


def test_mark_rows_read_by_ids_empty_noop():
    mw = _fake_mw(_master_df())
    assert mw.mark_rows_read_by_ids([]) == 0
    assert mw.data_service.calls == []


# ---------- 未读看板：全部标记已读 ----------

def test_board_mark_all_read_marks_and_refreshes(qapp):
    df = _master_df()
    board, mw = _make_board(df)
    _FakeMB.answer = QMessageBox.Yes
    real = ud_mod.QMessageBox
    ud_mod.QMessageBox = _FakeMB
    try:
        board._mark_all_read()
    finally:
        ud_mod.QMessageBox = real
    assert len(mw.data_service.calls) == 1
    assert sorted(mw.data_service.calls[0]) == ["D0", "D1", "D2", "D3"]
    assert list(mw.source_model.getDataFrame()["_read"]) == [1, 1, 1, 1]
    # 默认「未读」视图：全部标已读后表格清空，KPI 掩码同步清零
    assert board.source_model.rowCount() == 0
    assert int(board._cat_masks["隔离区"].sum()) == 0


def test_board_mark_all_cancelled_no_changes(qapp):
    df = _master_df()
    board, mw = _make_board(df)
    _FakeMB.answer = QMessageBox.No
    real = ud_mod.QMessageBox
    ud_mod.QMessageBox = _FakeMB
    try:
        board._mark_all_read()
    finally:
        ud_mod.QMessageBox = real
    assert mw.data_service.calls == []
    assert list(mw.source_model.getDataFrame()["_read"]) == [0, 0, 0, 0]


# ---------- 未读看板：选中标记已读 ----------

def test_board_mark_selected_read_only_selected_rows(qapp):
    df = _master_df()
    board, mw = _make_board(df)
    real = ud_mod.QMessageBox
    ud_mod.QMessageBox = _FakeMB
    try:
        sel = board.table_view.selectionModel()
        sel.select(board.source_model.index(1, 0), QItemSelectionModel.Select)
        board._mark_selected_read()
    finally:
        ud_mod.QMessageBox = real
    assert mw.data_service.calls == [["D1"]]
    assert list(mw.source_model.getDataFrame()["_read"]) == [0, 1, 0, 0]
    # 未读视图下被标行消失，其余 3 行仍在
    assert board.source_model.rowCount() == 3


def test_board_mark_selected_without_selection_noop(qapp):
    df = _master_df()
    board, mw = _make_board(df)
    board._mark_selected_read()
    assert mw.data_service.calls == []
