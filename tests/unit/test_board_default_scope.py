# -*- coding: utf-8 -*-
"""v44.04：偏差率 / 正负损看板默认口径 = 非隔离区 + 非替代料。

裴哥 11-19：「偏差率看板、正负损看板默认非隔离区、非替代料的数据，现在不能筛选
这 2 列，只能按列头筛选」。

两件事分开钉：
1. 默认口径：打开看板就不该混进隔离区行和替代料行（隔离区已单独处置，替代料是
   已知等价料偏差，混在一起把真实异常冲淡）。
2. 可筛选：替代料此前在正/负损看板里根本没有控件，只能列头筛选；现在与隔离区
   同为三态按钮，默认「否」。
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


def _cell(board, row, header):
    """从模型当前数据帧取某列（模型内部字段是 _data）。"""
    return board.source_model._data[header].iloc[row]


def _neg_df():
    """负损形态（实际 < 定额）；4 行里只有第 3 行是「干净」的。"""
    return pd.DataFrame({
        "订单日期": ["2026-11-01"] * 4,
        "工厂": ["食品厂"] * 4,
        "流程订单": ["1700001"] * 4,
        "物料编码": ["2000001", "2000002", "2000003", "2000004"],
        "物料描述": ["普通料", "替代料A", "普通料B", "隔离料"],
        "数量-定额": [10.0] * 4,
        "数量-实际": [8.0] * 4,
        "偏差率": [20.0] * 4,
        "单位": ["箱"] * 4,
        "是否替代料": ["否", "是", "否", "否"],
        "_read": [0] * 4,
    })


def _pos_df():
    """正损形态（实际 > 定额）；同样只有第 3 行是干净的。"""
    df = _neg_df()
    df["数量-实际"] = [12.0] * 4
    df["偏差率"] = [-20.0] * 4
    return df


@pytest.fixture()
def neg_board(qapp, monkeypatch):
    from gui_pyside6.widgets import neg_loss_content
    from gui_pyside6.widgets import base_board_content as mod

    # 隔离区只留「隔离料」这一行，其余不依赖真实 config
    monkeypatch.setattr(mod, "get_quarantined_ids", lambda: {
        "食品厂|2026-11-01|1700001|2000004"})
    board = neg_loss_content.NegLossContent(object())
    yield board
    board.deleteLater()


@pytest.fixture()
def pos_board(qapp, monkeypatch):
    from gui_pyside6.widgets import pos_loss_content
    from gui_pyside6.widgets import base_board_content as mod

    monkeypatch.setattr(mod, "get_quarantined_ids", lambda: {
        "食品厂|2026-11-01|1700001|2000004"})
    board = pos_loss_content.PosLossContent(object())
    yield board
    board.deleteLater()


class TestDefaultScope:
    def test_neg_defaults_to_exclude_quarantine_and_substitute(self, neg_board):
        assert neg_board._quar_filter == "no"
        assert neg_board._alt_filter == "no"
        assert neg_board.btn_quar_no.isChecked()
        assert neg_board.btn_alt_no.isChecked()
        neg_board.set_data(_neg_df())
        # 4 行 - 替代料 1 行 - 隔离区 1 行
        assert neg_board.source_model.rowCount() == 2
        names = [_cell(neg_board, r, "物料描述")
                 for r in range(neg_board.source_model.rowCount())]
        assert "替代料A" not in names and "隔离料" not in names

    def test_pos_defaults_to_exclude_quarantine_and_substitute(self, pos_board):
        assert pos_board._alt_filter == "no"
        pos_board.set_data(_pos_df())
        assert pos_board.source_model.rowCount() == 2

    def test_switching_alt_to_all_brings_rows_back(self, neg_board):
        neg_board.set_data(_neg_df())
        assert neg_board.source_model.rowCount() == 2
        neg_board._set_alt_filter("all")
        # 只剩隔离区这一条噪声被排除
        assert neg_board.source_model.rowCount() == 3
        assert neg_board.btn_alt_all.isChecked()
        assert not neg_board.btn_alt_no.isChecked()
        neg_board._set_alt_filter("yes")
        assert neg_board.source_model.rowCount() == 1

    def test_alt_filter_is_hidden_when_no_alt_column(self, neg_board):
        df = _neg_df().drop(columns=["是否替代料"])
        neg_board.set_data(df)
        assert "alt" in neg_board._hidden_filters
        # 即便没有替代料列，默认口径也不能凭空少行：隔离区 1 行之外全在
        assert neg_board.source_model.rowCount() == 3

    def test_reset_returns_to_default_scope(self, neg_board):
        neg_board.set_data(_neg_df())
        neg_board._set_alt_filter("all")
        neg_board._reset_filters()
        assert neg_board._alt_filter == "no"
        assert neg_board._quar_filter == "no"


class TestDeviationDialogDefaults:
    """偏差率预警看板：两个筛选本来就存在，改的是默认值与 no 分支口径。"""

    def test_alt_mask_blank_values_are_not_substitute(self):
        from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog

        df = pd.DataFrame({"替代料": ["是", "否", ""]})
        mask = DeviationWarningDialog._alt_mask(object(), df, "no")
        assert list(mask) == [False, True, True]
        mask = DeviationWarningDialog._alt_mask(object(), df, "yes")
        assert list(mask) == [True, False, False]

    def test_source_defaults(self):
        import inspect

        from gui_pyside6.dialogs import deviation_warning_dialog as mod

        src = inspect.getsource(mod.DeviationWarningDialog.__init__)
        assert 'self._quar_filter = "no"' in src
        assert 'self._alt_filter = "no"' in src
