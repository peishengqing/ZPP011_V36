# -*- coding: utf-8 -*-
"""DashboardController 看板对话框接线回归测试（v43.201 修复）。

根因（v43.196 重构遗留）：看板方法从 MainWindow 原样搬进 DashboardController 后，
打开对话框时仍把 ``self``（=DashboardController 自身）当 ``main_window``/parent 传进去，
但所有看板 dialog 内部都写死 ``self.main_window.view_model.df``，而 controller 没有
``view_model`` 属性 → AttributeError 崩溃。

修复：dialog 一律接收 ``self.mw``（真正的 MainWindow）。

行为层：驱动各 ``_show_*`` 方法，断言 dialog 收到的 ``main_window``/parent 是真实 MainWindow（fake_mw），
而不是 controller 自身。
结构层：源码断言 10 处 dialog 实例化全部用 ``self.mw``，且无任何 ``, self)`` 把 controller 当 main_window。
"""
import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

pytest.importorskip("PySide6")

from gui_pyside6.controllers.dashboard_controller import DashboardController

DC = "gui_pyside6.controllers.dashboard_controller"


def _rich_df():
    """覆盖各看板取数分支所需列的宽表；偏差率=50 触发 alert/deviation 非空集，
    物料编码 400 前缀触发 semi 子集非空。"""
    return pd.DataFrame({
        "data_id": ["d1"],
        "_read": [0],
        "工厂": ["F1"], "工厂名称": ["FN"],
        "车间": ["C1"], "组件物料类型": ["T"], "组件物料类型描述": ["TD"], "单位": ["U"],
        "数量-定额": [10.0], "定额": [10.0], "数量-实际": [10.0], "实际": [10.0],
        "偏差数量": [0.0], "偏差率(%)": [50.0], "偏差金额": [0.0],
        "净偏差数量": [0.0], "净偏差金额": [0.0], "净偏差率(%)": [0.0],
        "是否替代料": [""], "备注": [""], "备注原因": [""], "备注来源": [""],
        "半成品重分类": [""], "物料编码": ["400M1"], "物料名称": ["N1"], "物料描述": ["D1"],
        "订单日期": ["2026-01-01"], "流程订单": ["P1"], "原表行号": [0],
    })


def _fake_mw():
    mw = types.SimpleNamespace()
    mw.view_model = types.SimpleNamespace(df=_rich_df())
    mw.alert_monitor = types.SimpleNamespace(threshold=10)
    mw.table_view = MagicMock()
    mw.table_view.selectionModel.return_value.selectedIndexes.return_value = []
    mw.proxy_model = types.SimpleNamespace(mapToSource=lambda ix: types.SimpleNamespace(row=0))
    mw.source_model = types.SimpleNamespace(getDataFrame=lambda: _rich_df())
    mw._apply_board_focus = lambda *a, **k: None
    mw._locate_row_in_main_table = lambda *a, **k: None
    mw._get_master_df = lambda: _rich_df()
    return mw


def _recorder(name, captured):
    def _make(*a, **k):
        captured.append((name, a, k))
        m = MagicMock()
        m.exec.return_value = 0
        return m
    return _make


def test_show_dashboard_passes_main_window_not_controller():
    """精确复现崩溃路径：_show_dashboard 必须把真实 MainWindow 传给 DashboardDialog。"""
    mw = _fake_mw()
    captured = []
    with patch(f"{DC}.DashboardDialog", side_effect=_recorder("DashboardDialog", captured)), \
         patch(f"{DC}.QMessageBox") as mbox:
        mbox.warning.return_value = None
        DashboardController(mw)._show_dashboard()
    assert captured, "DashboardDialog 应被实例化"
    name, a, k = captured[0]
    assert k.get("main_window") is mw, "main_window 必须是真实 MainWindow，而非 controller"
    assert k.get("parent") is mw, "parent 必须是真实 MainWindow，而非 controller"


def test_show_neg_loss_passes_main_window():
    mw = _fake_mw()
    captured = []
    with patch(f"{DC}.NegLossDashboardDialog", side_effect=_recorder("NegLossDashboardDialog", captured)), \
         patch(f"{DC}.QMessageBox"):
        DashboardController(mw)._show_neg_loss_dashboard()
    assert captured, "NegLossDashboardDialog 应被实例化"
    name, a, k = captured[0]
    # 第二位置参即 main_window
    assert a[1] is mw, "NegLossDashboardDialog 的 main_window 必须是真实 MainWindow"


def test_show_semi_passes_main_window():
    mw = _fake_mw()
    captured = []
    with patch(f"{DC}.SemiDashboardDialog", side_effect=_recorder("SemiDashboardDialog", captured)), \
         patch(f"{DC}.QMessageBox"):
        DashboardController(mw)._show_semi_dashboard()
    assert captured, "SemiDashboardDialog 应被实例化"
    name, a, k = captured[0]
    assert a[1] is mw, "SemiDashboardDialog 的 main_window 必须是真实 MainWindow"


def test_controller_never_passed_as_dialog_main_window():
    """结构层：源码所有看板 dialog 实例化都必须用 self.mw，无任何 ``, self)`` 把 controller 当 main_window。"""
    src = open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "gui_pyside6", "controllers", "dashboard_controller.py"), encoding="utf-8").read()
    dialogs = [
        "AlertDialog", "DeviationWarningDialog", "NegLossDashboardDialog",
        "PosLossDashboardDialog", "DataStabilityDialog", "QuarantineReviewDialog",
        "AltChainDialog", "MaterialProfileDialog", "SemiDashboardDialog", "DashboardDialog",
    ]
    for d in dialogs:
        # 必须存在「Dialog(xxx, self.mw)」形式
        assert f"{d}(" in src, "%s 实例化缺失" % d
        # 不得出现「Dialog(..., self)」把 controller 当 main_window（QDialog(self) 是合法自承载弹窗，单独豁免）
        bad = "%s(sub, self)" % d in src or "%s(warnings_df, self)" % d in src \
            or "%s(alerts_df, self)" % d in src or "%s(audit_df, None, parent=self, main_window=self)" % d in src \
            or "%s(code, self)" % d in src or "%s(self)" % d in src or "%s(self, code_name_map" % d in src
        assert not bad, "%s 仍把 controller 当 main_window 传入（应为 self.mw）" % d
    # 全部应改为 self.mw（DataStabilityDialog/MaterialProfileDialog 用 `self.mw,` 带逗号，
    # DashboardDialog 主窗口参数算 1 处，故精确为 8 处 `self.mw)`）
    assert src.count("self.mw)") >= 8, "应有至少 8 处 dialog 调用使用 self.mw"
