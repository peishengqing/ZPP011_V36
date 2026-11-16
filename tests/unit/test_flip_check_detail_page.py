# -*- coding: utf-8 -*-
"""翻箱守恒看板（食品/饮料分厂 · 四页）· 组件明细与同源口径。

历史演进：
- v43.364「组件明细」页：一行一组件，判别照用导出侧同一个 _food_kg_of，明细加起来
  必须能回对结论页的「投入食物合计KG」（两页各算一套是本模块的历史事故源）。
- v43.370 分厂四页：食品走净含量 KG 守恒、饮料走总容器数守恒，路由统一走
  split_by_factory（与导出四张 sheet 同源）。饮料订单一律不得套食品 KG 逻辑
  （parse_net_kg('380ml…')=None 会静默落「待人工确认」，正是本次要修的事故）。
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.dialogs.flip_check_dashboard_dialog import (  # noqa: E402
    _ALL_HEADERS, _DETAIL_HEADERS, _DRINK_DETAIL_HEADERS, _DRINK_HEADERS,
    _HEADERS, FlipCheckDashboardDialog)


def _df():
    """翻箱五单三厂：
    - 170001 食品厂 疑似漏记（3 组件：成品件 + 散货食物 + 包材），车间=一车间
    - 170002 食品厂 守恒（1 组件），车间=一车间
    - 180001 饮料厂 守恒（容器数 150 = 150），车间=饮料车间
    - 180002 饮料厂 疑似漏记（产出 150 / 投入 75），车间=饮料车间
    - 190001 未知厂「其他厂」（不进任何守恒表，单独留痕）
    """
    base = {"订单类型": "ZPFX", "订单日期": "2026-11-01", "备注": ""}
    food_ws, drink_ws = "一车间", "饮料车间"
    return pd.DataFrame([
        # ---- 170001 食品·疑似漏记：产出 10×12KG=120，投入 36+10=46 -> 差 +74
        dict(base, 流程订单="170001", 工厂名称="食品厂", 车间=food_ws,
             产品物料号码="51000001", 产品物料描述="可乐500gx24罐", 产量=10,
             组件物料类型="Z007", 组件物料类型描述="成品", 物料编码="20000403",
             物料名称="蛋卷300gx60包", 单位="PC", 实际=2),
        dict(base, 流程订单="170001", 工厂名称="食品厂", 车间=food_ws,
             产品物料号码="51000001", 产品物料描述="可乐500gx24罐", 产量=10,
             组件物料类型="Z002", 组件物料类型描述="原材料", 物料编码="20003014",
             物料名称="自动包玉米粒", 单位="KG", 实际=10, 备注="散货"),
        dict(base, 流程订单="170001", 工厂名称="食品厂", 车间=food_ws,
             产品物料号码="51000001", 产品物料描述="可乐500gx24罐", 产量=10,
             组件物料类型="Z002", 组件物料类型描述="包装材料", 物料编码="200004995",
             物料名称="周转纸箱", 单位="PC", 实际=5),
        # ---- 170002 食品·守恒：产出 4×2.5KG=10，投入 4×2.5=10 -> 差 0
        dict(base, 流程订单="170002", 工厂名称="食品厂", 车间=food_ws,
             产品物料号码="51000002", 产品物料描述="糖浆2.5kg", 产量=4,
             组件物料类型="Z007", 组件物料类型描述="成品", 物料编码="20000500",
             物料名称="糖浆2.5kg", 单位="PC", 实际=4),
        # ---- 180001 饮料·守恒：产出 10×15瓶=150，投入 10×15=150 -> 差 0
        dict(base, 流程订单="180001", 工厂名称="饮料厂", 车间=drink_ws,
             产品物料号码="52000001", 产品物料描述="乐虎380mlx3瓶x5组", 产量=10,
             组件物料类型="Z008", 组件物料类型描述="成品", 物料编码="30000403",
             物料名称="乐虎380mlx3瓶x5组", 单位="PC", 实际=10),
        # ---- 180002 饮料·疑似漏记：产出 150，投入 5×15=75 -> 差 +75
        dict(base, 流程订单="180002", 工厂名称="饮料厂", 车间=drink_ws,
             产品物料号码="52000001", 产品物料描述="乐虎380mlx3瓶x5组", 产量=10,
             组件物料类型="Z008", 组件物料类型描述="成品", 物料编码="30000403",
             物料名称="乐虎380mlx3瓶x5组", 单位="PC", 实际=5),
        # ---- 190001 未知厂：既非食品也非饮料，不猜、单独留痕
        dict(base, 流程订单="190001", 工厂名称="其他厂", 车间=food_ws,
             产品物料号码="59000001", 产品物料描述="某品", 产量=1,
             组件物料类型="Z007", 组件物料类型描述="成品", 物料编码="40000001",
             物料名称="某品2kg", 单位="PC", 实际=1),
    ])


@pytest.fixture
def board(qapp):
    dlg = FlipCheckDashboardDialog(_df(), None)
    yield dlg
    dlg.deleteLater()


def _col(table, j):
    return [table.item(i, j).text() for i in range(table.rowCount())]


# ---------------------------------------------------------------- 分厂路由
def test_orders_route_to_their_factory(board):
    """食品 2 单落食品结论页、饮料 2 单落饮料结论页、未知厂不进任何守恒表。"""
    assert board.food_table.rowCount() == 2
    assert board.drink_table.rowCount() == 2
    assert set(_col(board.food_table, _HEADERS.index('流程订单'))) == \
        {"170001", "170002"}
    assert set(_col(board.drink_table, _DRINK_HEADERS.index('流程订单'))) == \
        {"180001", "180002"}
    assert board._unknown_orders == [("190001", "其他厂")]


def test_code_plus_name_factory_spelling_routes_correctly(qapp):
    """工厂值「1101食品/1102饮料」这类码+名连写也得落对厂，不能全甩进未知厂。

    主表 dev_df 的工厂列常是这种拼写，split_by_factory 精确集合套不上会把
    整单进未知厂 → 食品/饮料结论页 0 单（裴哥 2026-11-16 实报：有 6 行 ZPFX
    却「食品 0 单」）。子串兜底同源 main_window 预览统计，任意拼写都能分厂。
    """
    base = {"订单类型": "ZPFX", "订单日期": "2026-11-01", "备注": ""}
    df = pd.DataFrame([
        dict(base, 流程订单="200001", 工厂名称="1101食品", 车间="一车间",
             产品物料号码="51000010", 产品物料描述="糖浆2.5kg", 产量=4,
             组件物料类型="Z007", 组件物料类型描述="成品", 物料编码="20000600",
             物料名称="糖浆2.5kg", 单位="PC", 实际=4),
        dict(base, 流程订单="200002", 工厂名称="1102饮料", 车间="饮料车间",
             产品物料号码="52000010", 产品物料描述="乐虎380mlx3瓶x5组", 产量=10,
             组件物料类型="Z008", 组件物料类型描述="成品", 物料编码="30000500",
             物料名称="乐虎380mlx3瓶x5组", 单位="PC", 实际=10),
    ])
    d = FlipCheckDashboardDialog(df, None)
    assert d.food_table.rowCount() == 1, "1101食品 必须落食品结论页"
    assert d.drink_table.rowCount() == 1, "1102饮料 必须落饮料结论页"
    assert d._unknown_orders == [], "码+名连写不该进未知厂"
    d.deleteLater()


def test_food_uses_kg_verdicts(board):
    """食品侧结论来自 _check_order（KG 守恒）：漏记 170001、守恒 170002。"""
    jv = _HEADERS.index('结论')
    assert _col(board.food_table, jv) == ["疑似漏记", "守恒/正常"]


def test_drink_uses_container_verdicts(board):
    """饮料侧结论来自 check_drink_order（容器数守恒），绝不套食品 KG 逻辑：
    180001 守恒、180002 漏记。若饮料被误套 parse_net_kg，两单都会落「待人工确认」。"""
    jv = _DRINK_HEADERS.index('结论')
    assert _col(board.drink_table, jv) == ["守恒/正常", "疑似漏记"]


def test_drink_order_metrics_are_containers_not_kg(board):
    """饮料结论页报的是「容器数」：180001 产出 150 / 投入 150 / 差 0。"""
    j_ord = _DRINK_HEADERS.index('流程订单')
    j_out = _DRINK_HEADERS.index('产出总容器数')
    j_in = _DRINK_HEADERS.index('投入总容器数')
    j_diff = _DRINK_HEADERS.index('差额容器数')
    assert board.drink_table.item(0, j_ord).text() == "180001"
    assert float(board.drink_table.item(0, j_out).text()) == 150.0
    assert float(board.drink_table.item(0, j_in).text()) == 150.0
    assert float(board.drink_table.item(0, j_diff).text()) == 0.0


# ---------------------------------------------------------------- 明细页
def test_detail_has_one_row_per_component(board):
    """食品明细 4 行（170001 三件 + 170002 一件），饮料明细 2 行。"""
    assert board.food_table_detail.rowCount() == 4
    assert board.drink_table_detail.rowCount() == 2
    assert _col(board.food_table_detail, _DETAIL_HEADERS.index('组件物料编码')) == \
        ["20000403", "20003014", "200004995", "20000500"]
    assert set(_col(board.drink_table_detail,
                    _DRINK_DETAIL_HEADERS.index('组件物料编码'))) == {"30000403"}


def test_food_kg_sums_back_to_order_total(board):
    """食品同口径反证：明细「计入KG」按单求和 == 结论页「投入食物合计KG」。"""
    j_flag = _DETAIL_HEADERS.index('是否计入食物投入')
    j_kg = _DETAIL_HEADERS.index('计入KG(参考)')
    j_ord = _DETAIL_HEADERS.index('流程订单')
    j_in = _HEADERS.index('投入食物合计KG')
    sums = {}
    for i in range(board.food_table_detail.rowCount()):
        if board.food_table_detail.item(i, j_flag).text() == '是':
            oid = board.food_table_detail.item(i, j_ord).text()
            sums[oid] = sums.get(oid, 0.0) + float(
                board.food_table_detail.item(i, j_kg).text())
    by_ord = {board.food_table.item(i, _HEADERS.index('流程订单')).text():
              float(board.food_table.item(i, j_in).text())
              for i in range(board.food_table.rowCount())}
    assert sums["170001"] == pytest.approx(46.0)   # 36 + 10
    assert sums["170002"] == pytest.approx(10.0)
    assert by_ord["170001"] == pytest.approx(sums["170001"])
    assert by_ord["170002"] == pytest.approx(sums["170002"])


def test_drink_containers_sum_back_to_order_total(board):
    """饮料同口径反证：明细「计入容器数」按单求和 == 结论页「投入总容器数」。"""
    j_flag = _DRINK_DETAIL_HEADERS.index('是否计入容器数')
    j_c = _DRINK_DETAIL_HEADERS.index('计入容器数(参考)')
    j_ord = _DRINK_DETAIL_HEADERS.index('流程订单')
    j_in = _DRINK_HEADERS.index('投入总容器数')
    sums = {}
    for i in range(board.drink_table_detail.rowCount()):
        if board.drink_table_detail.item(i, j_flag).text() == '是':
            oid = board.drink_table_detail.item(i, j_ord).text()
            sums[oid] = sums.get(oid, 0.0) + float(
                board.drink_table_detail.item(i, j_c).text())
    by_ord = {board.drink_table.item(i, _DRINK_HEADERS.index('流程订单')).text():
              float(board.drink_table.item(i, j_in).text())
              for i in range(board.drink_table.rowCount())}
    assert sums["180001"] == pytest.approx(by_ord["180001"])   # 150
    assert sums["180002"] == pytest.approx(by_ord["180002"])   # 75


def test_drink_detail_carries_yield(board):
    """饮料·组件明细也带「产量(件)」列（与食品明细对齐），值随所属订单。

    180001/180002 产量都 10，饮料明细 2 行「产量(件)」列都得是 10。
    """
    j_y = _DRINK_DETAIL_HEADERS.index('产量(件)')
    vals = [board.drink_table_detail.item(i, j_y).text()
            for i in range(board.drink_table_detail.rowCount())]
    assert vals == ["10", "10"]


def test_all_table_combines_food_and_drink(board):
    """总表页把食+饮订单合并一屏：食品 2 单 + 饮料 2 单，口径列各归各套。"""
    assert board.tabs.count() == 5
    assert board.all_table.rowCount() == 4
    j_cal = _ALL_HEADERS.index('口径')
    j_ord = _ALL_HEADERS.index('流程订单')
    by_ord = {board.all_table.item(i, j_ord).text():
              board.all_table.item(i, j_cal).text()
              for i in range(board.all_table.rowCount())}
    assert by_ord == {"170001": "KG守恒", "170002": "KG守恒",
                     "180001": "容器数守恒", "180002": "容器数守恒"}


def test_all_table_filter_applies(board):
    """总表同样受「结论/车间」筛选：疑似漏记 → 食品 1 单 + 饮料 1 单。"""
    board.tabs.setCurrentIndex(0)
    board.cmb_verdict.setCurrentText("疑似漏记")
    j_ord = _ALL_HEADERS.index('流程订单')
    got = {board.all_table.item(i, j_ord).text()
           for i in range(board.all_table.rowCount())}
    assert got == {"170001", "180002"}


def test_packaging_row_is_marked_not_counted(board):
    """食品包材行不丢，标「否」；散货食物标「是」——留在明细里正是人工核对要看的那几行。"""
    j_flag = _DETAIL_HEADERS.index('是否计入食物投入')
    j_code = _DETAIL_HEADERS.index('组件物料编码')
    flags = {board.food_table_detail.item(i, j_code).text():
             board.food_table_detail.item(i, j_flag).text()
             for i in range(board.food_table_detail.rowCount())}
    assert flags["200004995"] == "否"          # 周转纸箱（包材）
    assert flags["20003014"] == "是"          # 自动包玉米粒（散货食物）


def test_drink_zero_and_non_z008_left_with_reason(board):
    """饮料被排除的行不静默丢：实际=0 的成品 / Z005 半成品都在「排除原因」留痕。"""
    extra = pd.DataFrame([
        dict(订单类型="ZPFX", 流程订单="180003", 订单日期="2026-11-01",
             工厂名称="饮料厂", 车间="饮料车间", 产品物料号码="52000003",
             产品物料描述="乐虎380mlx3瓶x5组", 产量=10, 组件物料类型="Z008",
             组件物料类型描述="成品", 物料编码="30000403",
             物料名称="乐虎380mlx3瓶x5组", 单位="PC", 实际=0, 备注=""),
        dict(订单类型="ZPFX", 流程订单="180003", 订单日期="2026-11-01",
             工厂名称="饮料厂", 车间="饮料车间", 产品物料号码="52000003",
             产品物料描述="乐虎380mlx3瓶x5组", 产量=10, 组件物料类型="Z005",
             组件物料类型描述="半成品", 物料编码="30000900",
             物料名称="半成品糖浆", 单位="PC", 实际=0, 备注="翻箱订单，未使用"),
    ])
    d = FlipCheckDashboardDialog(pd.concat([_df(), extra]), None)
    j_flag = _DRINK_DETAIL_HEADERS.index('是否计入容器数')
    j_reason = _DRINK_DETAIL_HEADERS.index('排除原因')
    j_ord = _DRINK_DETAIL_HEADERS.index('流程订单')
    rows = [tuple(d.drink_table_detail.item(i, j).text()
                  for j in (j_ord, j_flag, j_reason))
            for i in range(d.drink_table_detail.rowCount())
            if d.drink_table_detail.item(i, j_ord).text() == "180003"]
    assert len(rows) == 2, "180003 两个组件都得在明细里留痕"
    assert all(flag == "否" for _o, flag, _r in rows)
    reasons = " ".join(r for _o, _f, r in rows)
    assert "实际耗用=0" in reasons
    assert ("半成品" in reasons) or ("Z005" in reasons)
    d.deleteLater()


# ---------------------------------------------------------------- 筛选
def test_verdict_filter_applies_to_each_factory(board):
    """「结论」筛选对食品/饮料各自生效：疑似漏记 → 食品 1 单 + 饮料 1 单。"""
    board.tabs.setCurrentIndex(0)
    board.cmb_verdict.setCurrentText("疑似漏记")
    assert board.food_table.rowCount() == 1
    assert board.drink_table.rowCount() == 1
    assert _col(board.food_table, _HEADERS.index('流程订单')) == ["170001"]
    assert _col(board.drink_table, _DRINK_HEADERS.index('流程订单')) == ["180002"]


def test_workshop_filter_applies_to_both_pages(board):
    """「车间」筛选同时作用于同厂结论页与明细页：饮料车间只属饮料厂。"""
    board.tabs.setCurrentIndex(0)
    board.cmb_workshop.setCurrentText("饮料车间")
    assert board.food_table.rowCount() == 0        # 食品全在一车间，被筛空
    assert board.drink_table.rowCount() == 2
    assert board.drink_table_detail.rowCount() == 2
    board.cmb_workshop.setCurrentIndex(0)          # 回「全部」
    assert board.food_table.rowCount() == 2


def test_count_label_follows_active_page(board):
    """计数跟着当前页说人话：总表报「食+饮共 N 单」，结论页报「几单」，明细页报「几行组件」。"""
    board.tabs.setCurrentIndex(0)
    assert "食+饮" in board.lbl_count.text()
    board.tabs.setCurrentIndex(1)
    assert "食品" in board.lbl_count.text() and "单" in board.lbl_count.text()
    board.tabs.setCurrentIndex(2)
    assert "组件" in board.lbl_count.text()
    board.tabs.setCurrentIndex(3)
    assert "饮料" in board.lbl_count.text() and "单" in board.lbl_count.text()
    board.tabs.setCurrentIndex(4)
    assert "组件" in board.lbl_count.text()


# ---------------------------------------------------------------- 导出
def test_export_records_cover_their_headers(board):
    """五页导出行的键必须与各自表头一一对应，否则 DataFrame 出来整列空白。"""
    for idx in range(5):
        rec, cols = board._record_for_tab(idx)
        _table, shown, _total = board._active_tables(idx)
        assert shown, "每一页都得有数据才能验键"
        assert set(rec(shown[0])) == set(cols)


def test_empty_source_says_so(qapp, monkeypatch):
    """没有翻箱单要明确告诉用户，四张表都空。"""
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: shown.append(a[2])))
    d = FlipCheckDashboardDialog(_df().iloc[0:0], None)
    assert shown and "暂无数据" in shown[0]
    assert d.food_table.rowCount() == 0 and d.food_table_detail.rowCount() == 0
    assert d.drink_table.rowCount() == 0 and d.drink_table_detail.rowCount() == 0
    d.deleteLater()
