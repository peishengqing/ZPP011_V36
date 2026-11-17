# -*- coding: utf-8 -*-
"""未投料看板（v43.385）· 口径与筛选回归测试。

口径铁律（与导出「完整偏差明细.未投料订单」post_process._add_unfed_flag 同源）：
- 某流程订单下**所有**组件行 |实际| ≤ 0.001 → 该单所有行算「未投料」；
- 实际为 NaN/非数值的行不算零投料（该单不算未投料）；
- 流程订单为空的行不参与判定；
- 部分投料的订单不算未投料。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest

pytest.importorskip("PySide6")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.dialogs.unfed_dashboard_dialog import (  # noqa: E402
    UnfedDashboardDialog, unfed_order_mask)


def _df():
    """7 行 5 单的构造数据：
    - 2001 食品厂·一车间：2 行全 0 → 整单未投料（2 行命中、1 单）
    - 2002 食品厂·二车间：0 + 80 部分投料 → 不算
    - 2003 饮料厂·灌装车间：1 行实际=0.0005（容差内）→ 整单未投料（1 行、1 单，带备注）
    - 2004 饮料厂·灌装车间：实际 NaN → 不算
    - 2005 流程订单为空：不参与判定
    """
    return pd.DataFrame([
        dict(订单日期="2026-10-13", 流程订单="2001", 工厂="云南达利-食品厂", 车间="一车间",
             产品物料描述="蛋卷300g", 物料编码="20000403", 物料名称="面粉", 单位="KG",
             定额=100.0, 实际=0.0, 净偏差数量=-100.0, 偏差金额=-500.0, 备注="",
             原表行号=1, data_id="云南达利-食品厂|2026-10-13|2001|20000403"),
        dict(订单日期="2026-10-13", 流程订单="2001", 工厂="云南达利-食品厂", 车间="一车间",
             产品物料描述="蛋卷300g", 物料编码="20000403", 物料名称="白砂糖", 单位="KG",
             定额=50.0, 实际=0.0, 净偏差数量=-50.0, 偏差金额=-250.0, 备注="",
             原表行号=2, data_id="云南达利-食品厂|2026-10-13|2001|20000499"),
        dict(订单日期="2026-10-14", 流程订单="2002", 工厂="云南达利-食品厂", 车间="二车间",
             产品物料描述="糖浆2.5kg", 物料编码="20000500", 物料名称="麦芽糖浆", 单位="KG",
             定额=80.0, 实际=0.0, 净偏差数量=-80.0, 偏差金额=-400.0, 备注="",
             原表行号=3, data_id="云南达利-食品厂|2026-10-14|2002|20000500"),
        dict(订单日期="2026-10-14", 流程订单="2002", 工厂="云南达利-食品厂", 车间="二车间",
             产品物料描述="糖浆2.5kg", 物料编码="20000500", 物料名称="果葡糖浆", 单位="KG",
             定额=40.0, 实际=80.0, 净偏差数量=40.0, 偏差金额=200.0, 备注="补投",
             原表行号=4, data_id="云南达利-食品厂|2026-10-14|2002|20000600"),
        dict(订单日期="2026-10-15", 流程订单="2003", 工厂="云南达利-饮料厂", 车间="灌装车间",
             产品物料描述="乐虎380ml", 物料编码="30000403", 物料名称="瓶坯", 单位="个",
             定额=1000.0, 实际=0.0005, 净偏差数量=-999.9995, 偏差金额=-1000.0, 备注="待核",
             原表行号=5, data_id="云南达利-饮料厂|2026-10-15|2003|30000403"),
        dict(订单日期="2026-10-15", 流程订单="2004", 工厂="云南达利-饮料厂", 车间="灌装车间",
             产品物料描述="茶饮500ml", 物料编码="30000500", 物料名称="茶粉", 单位="KG",
             定额=10.0, 实际=None, 净偏差数量=-10.0, 偏差金额=-50.0, 备注="",
             原表行号=6, data_id="云南达利-饮料厂|2026-10-15|2004|30000500"),
        dict(订单日期="2026-10-15", 流程订单="", 工厂="云南达利-饮料厂", 车间="灌装车间",
             产品物料描述="杂项", 物料编码="30000999", 物料名称="杂", 单位="个",
             定额=5.0, 实际=0.0, 净偏差数量=-5.0, 偏差金额=-10.0, 备注="",
             原表行号=7, data_id="云南达利-饮料厂|2026-10-15||30000999"),
    ])


# ---------------------------------------------------------------- 纯口径
def test_mask_basic():
    m = unfed_order_mask(_df())
    assert list(m) == [True, True, False, False, True, False, False]


def test_mask_tolerance_boundary():
    df = pd.DataFrame([
        dict(流程订单="A", 实际=0.0005),   # 容差内 → 零投料
        dict(流程订单="A", 实际=0.01),     # 超容差 → A 不算未投料
        dict(流程订单="B", 实际=-0.001),   # 负容差边界 → B 整单零投料
    ])
    assert list(unfed_order_mask(df)) == [False, False, True]


def test_mask_nan_and_empty_order():
    df = pd.DataFrame([
        dict(流程订单="C", 实际=float("nan")),   # NaN 不算零投料
        dict(流程订单=None, 实际=0.0),           # 空订单不参与
        dict(流程订单="", 实际=0.0),
    ])
    assert list(unfed_order_mask(df)) == [False, False, False]


def test_mask_degenerate_inputs():
    assert unfed_order_mask(pd.DataFrame()).empty
    assert not unfed_order_mask(None).any()
    df = pd.DataFrame([dict(流程订单="X", 定额=1.0)])   # 缺「实际」列
    assert not unfed_order_mask(df).any()


# ---------------------------------------------------------------- 看板
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make(qapp):
    return UnfedDashboardDialog(_df(), object())


def test_dialog_rows_and_stats(qapp):
    dlg = _make(qapp)
    shown = dlg.source_model.getDataFrame()
    assert len(shown) == 3                       # 2001×2 + 2003×1
    assert set(shown['流程订单']) == {"2001", "2003"}
    assert dlg.lbl_count.text() == "共 3 条 / 筛选命中 3 条"
    assert dlg.lbl_orders.text() == "订单：共 2 单 / 命中 2 单"
    ws = dlg.lbl_ws.text()
    assert "食品厂·一车间 1单" in ws and "饮料厂·灌装车间 1单" in ws


def test_dialog_keyword_filter(qapp):
    dlg = _make(qapp)
    dlg.edit_search.setText("乐虎")              # 只命中 2003
    dlg._apply_filters()
    shown = dlg.source_model.getDataFrame()
    assert len(shown) == 1
    assert "乐虎" in str(shown.iloc[0]['产品物料描述'])
    assert dlg.lbl_orders.text() == "订单：共 2 单 / 命中 1 单"


def test_dialog_remark_filter(qapp):
    dlg = _make(qapp)
    dlg.combo_remark.setCurrentText("有")        # 只有 2003 带备注「待核」
    assert len(dlg.source_model.getDataFrame()) == 1
    dlg.combo_remark.setCurrentText("无")
    assert len(dlg.source_model.getDataFrame()) == 2
    dlg.combo_remark.setCurrentText("全部")
    assert len(dlg.source_model.getDataFrame()) == 3


def test_dialog_net_range_filter(qapp):
    dlg = _make(qapp)
    dlg.edit_net_dev_min.setText("-600")         # 2001 两行(-100/-50)命中；2003(-1000)出界
    dlg.edit_net_dev_max.setText("0")
    dlg._apply_filters()
    shown = dlg.source_model.getDataFrame()
    assert len(shown) == 2
    assert set(shown['流程订单']) == {"2001"}
    assert dlg.lbl_count.text() == "共 3 条 / 筛选命中 2 条"


def test_dialog_internal_cols_hidden(qapp):
    dlg = _make(qapp)
    model_df = dlg.source_model.getDataFrame()
    for c in ("data_id", "原表行号", "_read", "_read_source"):
        assert c in model_df.columns
        assert dlg.table_view.isColumnHidden(int(model_df.columns.get_loc(c)))


def test_dialog_empty_data(qapp):
    dlg = UnfedDashboardDialog(pd.DataFrame([dict(流程订单="Z", 实际=5.0)]), object())
    assert len(dlg.source_model.getDataFrame()) == 0
    assert "没有" in dlg.lbl_count.text() or dlg.lbl_count.text().startswith("共 0 条")
    dlg2 = UnfedDashboardDialog(None, object())
    assert len(dlg2.source_model.getDataFrame()) == 0


# ---------------------------------------------------------------- 未读概览第 6 行
def test_unfed_stats_split_and_read():
    """未读概览第 6 行取数：订单粒度、区分食品/饮料厂、随已读清零。"""
    from gui_pyside6.controllers.dashboard_controller import unfed_stats
    # 无 _read 列 → 全按未读：2 单（食品 2001 + 饮料 2003），分厂各 1
    unread, total, detail = unfed_stats(_df())
    assert (unread, total) == (2, 2)
    assert "食品厂 1单" in detail and "饮料厂 1单" in detail
    # 2001 两行全标读、2003 保持未读 → 未读只剩饮料厂 1 单；总数不变
    df2 = _df()
    df2["_read"] = [1, 1, 0, 0, 0, 0, 0]
    unread2, total2, detail2 = unfed_stats(df2)
    assert (unread2, total2) == (1, 2)
    assert "食品厂" not in detail2 and "饮料厂 1单" in detail2
    # 全部标读 → 未读归 0（弹窗可按「全清零自动关闭」收起），明细清空
    df3 = _df()
    df3["_read"] = 1
    assert unfed_stats(df3) == (0, 2, "")


def test_unfed_stats_degenerate_inputs():
    from gui_pyside6.controllers.dashboard_controller import unfed_stats
    assert unfed_stats(None) == (0, 0, "")
    assert unfed_stats(pd.DataFrame()) == (0, 0, "")
    assert unfed_stats(pd.DataFrame([dict(流程订单="X", 实际=5.0)])) == (0, 0, "")
    # 缺流程订单列
    assert unfed_stats(pd.DataFrame([dict(实际=0.0)])) == (0, 0, "")


# ---------------------------------------------------------------- v43.387 产量两列 + 订单汇总页
def _df_with_yield():
    """在基础数据上补「产量/产量单位」两列（同单取值一致，模拟主表）。"""
    df = _df()
    df["产量"] = [1000.0, 1000.0, 2000.0, 2000.0, 500.0, 800.0, 300.0]
    df["产量单位"] = ["KG", "KG", "KG", "KG", "个", "KG", "个"]
    return df


def test_build_unfed_order_df_pure():
    """订单聚合纯函数：一单一行、数值列求和、维度列取首值、备注取首个非空。"""
    from gui_pyside6.dialogs.unfed_dashboard_dialog import build_unfed_order_df
    unfed_rows = [True, True, False, False, True, False, False]  # 2001×2 + 2003×1
    out = build_unfed_order_df(_df_with_yield().loc[unfed_rows])
    assert len(out) == 2
    r1 = out[out['流程订单'] == '2001'].iloc[0]
    assert int(r1['组件数']) == 2
    assert float(r1['定额合计']) == 150.0
    assert float(r1['实际合计']) == 0.0
    assert float(r1['净偏差数量合计']) == -150.0
    assert float(r1['偏差金额合计']) == -750.0
    assert str(r1['产量']) == '1000.0' and str(r1['产量单位']) == 'KG'
    assert str(r1['备注']) == ''
    r3 = out[out['流程订单'] == '2003'].iloc[0]
    assert int(r3['组件数']) == 1 and float(r3['定额合计']) == 1000.0
    assert str(r3['备注']) == '待核' and str(r3['产量单位']) == '个'
    # 空输入 → 带完整列结构的空表
    empty = build_unfed_order_df(pd.DataFrame())
    assert len(empty) == 0
    assert '定额合计' in empty.columns and '组件数' in empty.columns and '产量' in empty.columns


def test_dialog_production_columns(qapp):
    """组件明细页：产量/产量单位两列可见，插在「单位」与「定额」之间。"""
    dlg = UnfedDashboardDialog(_df_with_yield(), object())
    shown = dlg.source_model.getDataFrame()
    assert "产量" in shown.columns and "产量单位" in shown.columns
    for c in ("产量", "产量单位"):
        assert not dlg.table_view.isColumnHidden(int(shown.columns.get_loc(c)))
    assert (shown.columns.get_loc("单位") < shown.columns.get_loc("产量")
            < shown.columns.get_loc("产量单位") < shown.columns.get_loc("定额"))


def test_order_tab_aggregation_and_labels(qapp):
    """订单汇总页：一单一行、合计正确、底部计数换「单」口径、内部列隐藏。"""
    dlg = UnfedDashboardDialog(_df_with_yield(), object())
    dlg.tabs.setCurrentIndex(1)
    shown = dlg.order_source_model.getDataFrame()
    assert len(shown) == 2                       # 2001 + 2003
    assert dlg.lbl_count.text() == "共 2 单 / 筛选命中 2 单"
    r1 = shown[shown['流程订单'] == '2001'].iloc[0]
    assert int(r1['组件数']) == 2 and float(r1['偏差金额合计']) == -750.0
    for c in ("data_id", "原表行号", "_read", "_read_source"):
        assert dlg.order_table_view.isColumnHidden(int(shown.columns.get_loc(c)))


def test_order_tab_follows_component_filters(qapp):
    """订单汇总页随组件页筛选联动（关键字 / 净偏差区间）。"""
    dlg = UnfedDashboardDialog(_df_with_yield(), object())
    dlg.edit_search.setText("乐虎")              # 只剩 2003 一单
    dlg._apply_filters()
    dlg.tabs.setCurrentIndex(1)
    shown = dlg.order_source_model.getDataFrame()
    assert len(shown) == 1 and str(shown.iloc[0]['流程订单']) == '2003'
    assert dlg.lbl_count.text() == "共 2 单 / 筛选命中 1 单"
    # 清空关键字后改用净偏差区间 [-600,0]：2003（-1000 出界）被筛掉 → 订单页只剩 2001
    dlg.edit_search.clear()
    dlg._apply_filters()
    dlg.edit_net_dev_min.setText("-600")
    dlg.edit_net_dev_max.setText("0")
    dlg._apply_filters()
    shown2 = dlg.order_source_model.getDataFrame()
    assert len(shown2) == 1 and str(shown2.iloc[0]['流程订单']) == '2001'
    assert dlg.lbl_count.text() == "共 2 单 / 筛选命中 1 单"


def test_order_tab_without_yield_cols(qapp):
    """旧数据没有产量列 → 订单页照常聚合，产量列显示为空。"""
    dlg = _make(qapp)
    dlg.tabs.setCurrentIndex(1)
    shown = dlg.order_source_model.getDataFrame()
    assert len(shown) == 2
    assert "产量" in shown.columns
    assert all(str(v) in ('', 'nan') for v in shown['产量'])
    assert dlg.lbl_orders.text() == "订单：共 2 单 / 命中 2 单"
