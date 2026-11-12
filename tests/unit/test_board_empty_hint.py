# -*- coding: utf-8 -*-
"""看板「筛出 0 行」时的中央提示 + 开箱只看未读（v43.364）。

裴哥 11-12：「各看板默认展示未读的数据，如果没有数据要给出提示」。两件事一起钉：

1. 空表不再是一片白。表体中央写清是哪一种空：真没数据 / 未读 0 条但已读还有 N 条 /
   被筛选条件筛没了。
2. 「未读空了就悄悄换成全部」这条退路取消（负损、正损、替代料三块原先都有）。
   待办看板替用户放宽口径是越界的：用户以为在看待办，其实看的是全量，而下拉/按钮
   还写着「未读」——显示与生效两套。放宽由人点「全部」完成。
"""
import os
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QTableView

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.utils.board_empty_hint import (  # noqa: E402
    NO_DATA_TEXT, empty_hint_text, set_empty_hint)


def _hint(view):
    """读表格中央那句提示；没显示就返回空串。

    用 isHidden() 而不是 isVisible()：测试里父窗体本身没 show()，isVisible() 恒为
    False，会把「标签已就绪」误判成「没提示」。
    """
    lbl = getattr(view.viewport(), "_board_empty_lbl", None)
    if lbl is None or lbl.isHidden():
        return ""
    return lbl.text()


def _df(n=3, read=0):
    """负损形态（实际 8 < 定额 10）：正损的行负损看板会直接筛掉。"""
    return pd.DataFrame({
        "订单日期": ["2026-11-0%d" % (i + 1) for i in range(n)],
        "工厂": ["食品厂"] * n,
        "流程订单": ["17000%d" % (i + 1) for i in range(n)],
        "物料编码": ["20000%d" % (i + 1) for i in range(n)],
        "物料描述": ["物料%d" % (i + 1) for i in range(n)],
        "数量-定额": [10.0] * n,
        "数量-实际": [8.0] * n,
        "偏差率": [20.0] * n,
        "单位": ["箱"] * n,
        "_read": [read] * n,
    })


class TestHintText:
    """文案真源：有行不显示，三种空各说各话。"""

    def test_rows_present_means_no_hint(self):
        assert empty_hint_text(5, _df(5), "未读") == ""

    def test_truly_no_data(self):
        assert empty_hint_text(0, pd.DataFrame(), "全部") == NO_DATA_TEXT

    def test_all_read_says_how_many_read(self):
        assert empty_hint_text(0, _df(4, read=1), "未读") == (
            "未读 0 条 · 已读 4 条\n"
            "看板默认只列未读；要看已读的记录请把「已读/未读」切到「全部」。")

    def test_unread_exists_but_other_filters_emptied(self):
        # 还有未读却筛空了 → 不能谎报「未读 0 条」，要说条件筛没了
        text = empty_hint_text(0, _df(4, read=0), "未读")
        assert "未读 0 条" not in text
        assert "原始 4 条" in text

    def test_already_read_mode_is_not_the_unread_message(self):
        text = empty_hint_text(0, _df(4, read=1), "已读")
        assert "未读 0 条" not in text and "原始 4 条" in text


class TestSetEmptyHint:
    def test_shows_then_hides(self, qapp):
        view = QTableView()
        set_empty_hint(view, "第一句")
        assert _hint(view) == "第一句"
        set_empty_hint(view, "换成第二句")
        assert _hint(view) == "换成第二句"
        set_empty_hint(view, "")
        assert _hint(view) == ""


@pytest.fixture()
def neg_board(qapp):
    from gui_pyside6.widgets.neg_loss_content import NegLossContent
    c = NegLossContent(object())
    yield c
    c.deleteLater()


class TestBoardDefaultsToUnread:
    def test_all_read_keeps_unread_and_hints(self, neg_board):
        """全量都已读：口径停在「未读」，表体中央把话讲明白。"""
        neg_board.set_data(_df(4, read=1))
        assert neg_board._read_filter == "未读"
        assert neg_board.source_model.rowCount() == 0
        assert _hint(neg_board.table_view).startswith("未读 0 条 · 已读 4 条")
        # 反证：这 4 行本身是负损，空表是「已读」筛出来的，不是数据不达标
        neg_board._read_filter = "全部"
        neg_board._apply_filter()
        assert neg_board.source_model.rowCount() == 4

    def test_unread_rows_show_without_hint(self, neg_board):
        neg_board.set_data(_df(4, read=0))
        assert neg_board.source_model.rowCount() == 4
        assert _hint(neg_board.table_view) == ""

    def test_no_source_says_no_data(self, neg_board):
        neg_board.set_data(pd.DataFrame(columns=["订单日期", "流程订单", "物料编码"]))
        assert _hint(neg_board.table_view) == NO_DATA_TEXT


class TestOtherBoardsDefaultUnread:
    """正损、半成品同样开箱「未读」，别只有负损一块改了。"""

    @pytest.mark.parametrize("module,cls", [
        ("gui_pyside6.widgets.pos_loss_content", "PosLossContent"),
        ("gui_pyside6.widgets.semi_content", "SemiContent"),
    ])
    def test_read_filter_starts_unread(self, qapp, module, cls):
        import importlib
        klass = getattr(importlib.import_module(module), cls)
        c = klass(object())
        try:
            assert c._read_filter == "未读"
        finally:
            c.deleteLater()


class TestAlertDialogKeepsUnread:
    def test_all_read_does_not_widen_to_all(self, qapp):
        from gui_pyside6.dialogs.alert_dialog import AlertDialog
        d = AlertDialog(_df(3, read=1), None)
        try:
            assert d.filter_mode == "unread"
            assert d.source_model.rowCount() == 0
            assert _hint(d.table_view).startswith("未读 0 条")
            # 三颗按钮的勾选态和生效条件一致
            assert d.btn_unread.isChecked()
            assert not d.btn_all.isChecked()
        finally:
            d.deleteLater()


class TestFlipBoardHint:
    """翻箱守恒没有已读/未读，但同样不能空着不说话。"""

    @pytest.fixture()
    def board(self, qapp):
        from tests.unit.test_flip_check_detail_page import _df as flip_df
        from gui_pyside6.dialogs.flip_check_dashboard_dialog import (
            FlipCheckDashboardDialog)
        d = FlipCheckDashboardDialog(flip_df(), None)
        yield d
        d.deleteLater()

    def test_filtered_to_zero_explains_the_controls(self, board):
        board.cmb_factory.setCurrentText("饮料厂")
        board.cmb_verdict.setCurrentText("疑似漏记")   # 饮料厂那一单是守恒 → 筛空
        assert board.table.rowCount() == 0
        text = _hint(board.table)
        assert "原始 2 条" in text                      # 结论页：一共 2 单
        assert "结论 / 工厂 / 车间" in text
        # 明细页同样为空，也不能留白；总数按自己那页的口径报（4 行组件）
        detail = _hint(board.table_detail)
        assert "原始 4 条" in detail and detail.endswith(text.split("\n")[1])

    def test_hint_clears_when_rows_return(self, board):
        """筛回有行 → 提示必须撤掉，不能留在表体上挡数据。"""
        board.cmb_verdict.setCurrentText("疑似漏记")
        assert board.table.rowCount() == 1 and _hint(board.table) == ""
        board.cmb_verdict.setCurrentText("全部")
        assert _hint(board.table) == ""
