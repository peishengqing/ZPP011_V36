# -*- coding: utf-8 -*-
"""翻箱守恒看板「组件明细」页（v43.364）。

裴哥 11-12：「翻箱守恒这里按明细列出来，现在在同一行不好核对」——原先一单一行，
整单组件用「；」拼在两个单元格里，核对时只能靠鼠标悬停一行行看。现在多一页
一行一组件，且判别照用导出侧同一个 _food_kg_of，明细加起来必须能回对结论页的
「投入食物合计KG」，这条用反证钉住（两页各算一套是这个模块的历史事故源）。
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.dialogs.flip_check_dashboard_dialog import (  # noqa: E402
    _DETAIL_HEADERS, _HEADERS, FlipCheckDashboardDialog)


def _df():
    """两单翻箱：170001 产出>投入（疑似漏记，3 组件），170002 守恒（1 组件）。"""
    return pd.DataFrame([
        # 170001：产出 = 10 件 × (0.5kg×24) = 120KG
        {"订单类型": "ZPFX", "流程订单": "170001", "订单日期": "2026-11-01",
         "工厂名称": "食品厂", "车间": "软罐车间", "产品物料号码": "51000001",
         "产品物料描述": "可乐500gx24罐", "产量": 10,
         "组件物料类型": "Z007", "组件物料类型描述": "成品",
         "物料编码": "20000403", "物料名称": "蛋卷300gx60包", "单位": "PC",
         "实际": 2, "备注": ""},
        {"订单类型": "ZPFX", "流程订单": "170001", "订单日期": "2026-11-01",
         "工厂名称": "食品厂", "车间": "软罐车间", "产品物料号码": "51000001",
         "产品物料描述": "可乐500gx24罐", "产量": 10,
         "组件物料类型": "Z002", "组件物料类型描述": "原材料",
         "物料编码": "20003014", "物料名称": "自动包玉米粒", "单位": "KG",
         "实际": 10, "备注": "散货"},
        {"订单类型": "ZPFX", "流程订单": "170001", "订单日期": "2026-11-01",
         "工厂名称": "食品厂", "车间": "软罐车间", "产品物料号码": "51000001",
         "产品物料描述": "可乐500gx24罐", "产量": 10,
         "组件物料类型": "Z002", "组件物料类型描述": "包装材料",
         "物料编码": "200004995", "物料名称": "周转纸箱", "单位": "PC",
         "实际": 5, "备注": ""},
        # 170002：产出 = 4 件 × 2.5KG = 10KG，投入 = 4 × 2.5 = 10KG → 守恒
        {"订单类型": "ZPFX", "流程订单": "170002", "订单日期": "2026-11-02",
         "工厂名称": "饮料厂", "车间": "PET车间", "产品物料号码": "51000002",
         "产品物料描述": "糖浆2.5kg", "产量": 4,
         "组件物料类型": "Z007", "组件物料类型描述": "成品",
         "物料编码": "20000500", "物料名称": "糖浆2.5kg", "单位": "PC",
         "实际": 4, "备注": ""},
    ])


@pytest.fixture
def board(qapp):
    dlg = FlipCheckDashboardDialog(_df(), None)
    yield dlg
    dlg.deleteLater()


def _col(table, j):
    return [table.item(i, j).text() for i in range(table.rowCount())]


def test_detail_has_one_row_per_component(board):
    """明细页一行一组件：4 个组件就是 4 行，不再拼进一单的一格。"""
    assert board.table.rowCount() == 2, "结论页仍是一单一行"
    assert board.table_detail.rowCount() == 4
    assert _col(board.table_detail, _DETAIL_HEADERS.index('组件物料编码')) == \
        ["20000403", "20003014", "200004995", "20000500"]
    assert _col(board.table_detail, _DETAIL_HEADERS.index('组件物料名称')) == \
        ["蛋卷300gx60包", "自动包玉米粒", "周转纸箱", "糖浆2.5kg"]
    # 结论页那两列照旧（导出格式没动）
    assert "；".join(["20000403", "20003014", "200004995"]) in \
        board.table.item(0, _HEADERS.index('组件物料编码')).text()


def test_detail_kg_sums_back_to_the_order_total(board):
    """同口径反证：明细「计入KG」按单求和 == 结论页「投入食物合计KG」。"""
    j_flag = _DETAIL_HEADERS.index('是否计入食物投入')
    j_kg = _DETAIL_HEADERS.index('计入KG(参考)')
    j_ord = _DETAIL_HEADERS.index('流程订单')
    from gui_pyside6.dialogs.flip_check_dashboard_dialog import _HEADERS
    j_in_food = _HEADERS.index('投入食物合计KG')

    sums = {}
    for i in range(board.table_detail.rowCount()):
        if board.table_detail.item(i, j_flag).text() == '是':
            oid = board.table_detail.item(i, j_ord).text()
            sums[oid] = sums.get(oid, 0.0) + float(board.table_detail.item(i, j_kg).text())

    by_ord = {board.table.item(i, 1).text(): float(
        board.table.item(i, j_in_food).text()) for i in range(board.table.rowCount())}
    assert sums["170001"] == pytest.approx(by_ord["170001"])   # 36 + 10 = 46
    assert sums["170002"] == pytest.approx(by_ord["170002"])   # 10
    assert by_ord["170001"] == pytest.approx(46.0)


def test_packaging_row_is_marked_not_counted(board):
    """包材行不丢，但要标成「否」——留在明细里正是人工核对要看的那几行。"""
    j_flag = _DETAIL_HEADERS.index('是否计入食物投入')
    j_code = _DETAIL_HEADERS.index('组件物料编码')
    flags = {board.table_detail.item(i, j_code).text():
             board.table_detail.item(i, j_flag).text()
             for i in range(board.table_detail.rowCount())}
    assert flags["200004995"] == "否"          # 周转纸箱
    assert flags["20003014"] == "是"           # 自动包玉米粒（散货食物）


def test_filters_apply_to_both_pages(board):
    """筛选是看板级口径：切页只换视角，不换数据范围。"""
    board.cmb_verdict.setCurrentText("疑似漏记")
    assert board.table.rowCount() == 1
    assert board.table_detail.rowCount() == 3
    assert set(_col(board.table_detail, _DETAIL_HEADERS.index('流程订单'))) == {"170001"}

    board.cmb_factory.setCurrentText("饮料厂")
    assert board.table.rowCount() == 0
    assert board.table_detail.rowCount() == 0, "结论+工厂两个条件要同时生效"


def test_count_label_follows_active_page(board):
    board.tabs.setCurrentIndex(0)
    assert "单" in board.lbl_count.text() and "组件" not in board.lbl_count.text()
    board.tabs.setCurrentIndex(1)
    assert "组件" in board.lbl_count.text()


def test_export_records_cover_their_headers(board):
    """导出行的键必须与表头一一对应，否则 DataFrame 出来整列空白。"""
    assert set(board._order_record(board._filtered[0])) == set(_HEADERS)
    assert set(board._detail_record(board._filtered_detail[0])) == set(_DETAIL_HEADERS)


def test_empty_source_says_so(qapp, monkeypatch):
    """没有翻箱单要明确告诉用户，不要静默给两块空表。"""
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: shown.append(a[2])))
    dlg = FlipCheckDashboardDialog(_df().iloc[0:0], None)
    assert shown and "暂无数据" in shown[0]
    assert dlg.table.rowCount() == 0 and dlg.table_detail.rowCount() == 0
    dlg.deleteLater()
