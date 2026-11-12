# -*- coding: utf-8 -*-
"""筛选预设 + 看板联动钻取回归（2026-09-30 新功能）。"""
import os
import shutil
import sys

import pytest
from pytest import MonkeyPatch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="module")
def main_window(qapp, tmp_path_factory):
    """离屏构造真实 MainWindow，副作用全部指向临时目录（同 test_toolbar_reorg）。"""
    import core.read_status as rs
    import gui_pyside6.main_window as mw
    from core.alert_monitor import AlertMonitor
    from core.config_manager import ConfigManager as _CM

    db_tmp = tmp_path_factory.mktemp("audit_db_preset")
    real_db = rs.DB_PATH
    if os.path.exists(real_db):
        shutil.copy2(real_db, str(db_tmp / "audit.db"))
    rs.DB_PATH = str(db_tmp / "audit.db")

    cfg_tmp = tmp_path_factory.mktemp("cfg_preset") / "cm.json"

    def _mk_cm(*a, **k):
        return _CM(config_path=cfg_tmp)

    mp = MonkeyPatch()
    mw.MainWindow._seed_monitor_baseline = lambda self: None
    mw.MainWindow._scan_monitor_dir = lambda self, *a, **k: None
    AlertMonitor.start = lambda self: None
    AlertMonitor.stop = lambda self, *a, **k: None
    mp.setattr(mw, "ConfigManager", _mk_cm)

    w = mw.MainWindow()
    w.show()
    yield w
    rs.DB_PATH = real_db
    mp.undo()


def test_apply_filters_roundtrip(qapp):
    """apply_filters 是 get_filters 的逆操作：重置后恢复，关键条件一致。"""
    from gui_pyside6.widgets.filter_panel import FilterPanel

    panel = FilterPanel()
    panel._col_map = {"工厂": "工厂", "车间": "车间", "物料类型": "物料类型", "流程订单": "流程订单"}
    # 置值
    panel.process_order_edit.setText("170001")
    panel.material_code_edit.setText("M-1")
    panel.remark_search_edit.setText("短缺")
    state = panel.get_filters()
    assert state.get("_process_order") == "170001"
    assert state.get("_material_code") == "M-1"

    panel.reset_filters()
    assert panel.process_order_edit.text().strip() == ""
    panel.apply_filters(state)

    s2 = panel.get_filters()
    for k in ("_process_order", "_material_code", "_remark_search", "_read_status"):
        assert s2.get(k) == state.get(k), "%s 未恢复: %r vs %r" % (k, s2.get(k), state.get(k))

    # 空状态 → 归位
    panel.apply_filters({})
    assert panel.process_order_edit.text().strip() == ""


def test_preset_save_apply_delete(main_window):
    """命名预设：保存 → 重置 → 应用 → 删除，全链路走 config_manager.filter_history。"""
    w = main_window
    # 模拟数据已载入的真实状态（_col_map 由 update_options 建立）
    w.filter_panel._col_map = {"流程订单": "流程订单"}
    w.filter_panel.process_order_edit.setText("9901")
    w._save_filter_preset("测试视角")
    store = w._filter_preset_store()
    assert store.get("测试视角", {}).get("_process_order") == "9901"

    w.filter_panel.reset_filters()
    assert w.filter_panel.process_order_edit.text().strip() == ""

    w._apply_filter_preset("测试视角")
    assert w.filter_panel.process_order_edit.text().strip() == "9901"

    w._delete_filter_preset("测试视角")
    assert "测试视角" not in w._filter_preset_store()
    # 菜单名单同步刷新
    assert "测试视角" not in w.filter_panel._preset_names


def test_capture_last_used(main_window):
    """发起分析前自动记「上次使用」，预设菜单可一键恢复。"""
    w = main_window
    w.filter_panel._col_map = {"流程订单": "流程订单"}
    w.filter_panel.process_order_edit.setText("7777")
    w._capture_last_used_filter()
    store = w._filter_preset_store()
    assert store.get("___last___", {}).get("_process_order") == "7777"
    # 菜单应显示「恢复上次使用」可用
    w._refresh_filter_preset_menu()
    assert w.filter_panel._preset_has_last is True


def test_link_drilldown_and_clear(main_window):
    """联动钻取：叠加订单精确+工厂上下文（保留原筛选），清除后完整恢复快照。"""
    import pandas as pd
    from gui_pyside6.models.data_frame_model import AuditProxyModel

    w = main_window
    proxy = AuditProxyModel()
    proxy.setCustomFilters({"_read_status": "未读"})
    w.proxy_model = proxy
    w._link_snapshot = None

    record = pd.Series({"流程订单": "170001", "工厂": "食品厂", "原表行号": 5})
    w._apply_link_drilldown(record, "偏差率预警")

    cf = proxy.getCustomFilters()
    assert cf.get("_process_order") == "170001"
    assert cf.get("工厂") == "食品厂"
    assert cf.get("_read_status") == "未读", "原筛选条件应保留"
    assert w.main_table.link_banner.isVisible()
    assert "170001" in w.main_table.link_banner_label.text()

    w._clear_link_drilldown()
    cf2 = proxy.getCustomFilters()
    assert "_process_order" not in cf2 and "工厂" not in cf2
    assert cf2.get("_read_status") == "未读"
    assert not w.main_table.link_banner.isVisible()
    assert w._link_snapshot is None

    # 无流程订单的记录：不钻取、不报错
    rec2 = pd.Series({"原表行号": 9})
    w._apply_link_drilldown(rec2, "隔离区")
    assert proxy.getCustomFilters().get("_process_order") is None


def test_locate_row_triggers_drilldown(main_window):
    """locate_row(link_source=…) 定位成功后自动联动钻取。"""
    import pandas as pd
    from gui_pyside6.models.data_frame_model import AuditProxyModel
    from gui_pyside6.utils.locate import locate_row

    w = main_window
    proxy = AuditProxyModel()
    w.proxy_model = proxy
    w._link_snapshot = None
    w._locate_row_by_excel_no = lambda no: True  # 模拟定位成功

    record = pd.Series({"流程订单": "170002", "工厂": "饮料厂", "原表行号": 3})
    ok = locate_row(w, record, link_source="隔离区")
    assert ok
    cf = proxy.getCustomFilters()
    assert cf.get("_process_order") == "170002"
    assert w.main_table.link_banner.isVisible()

    # 不带 link_source：保持旧行为（只定位不钻取）
    w._clear_link_drilldown()
    locate_row(w, record)
    assert proxy.getCustomFilters().get("_process_order") is None


def _main_df(n=8):
    import pandas as pd
    return pd.DataFrame({
        "data_id": ["d%d" % i for i in range(n)],
        "原表行号": list(range(1, n + 1)),
        "流程订单": ["1700%02d" % i for i in range(n)],
        "工厂": ["食品厂"] * n,
        "物料编码": ["3000%04d" % i for i in range(n)],
        "物料名称": ["物料%d" % i for i in range(n)],
    })


def _current_data_id(w):
    from PySide6.QtCore import QModelIndex  # noqa: F401  保持与主链路同样的映射方式
    idx = w.table_view.selectionModel().currentIndex()
    if not idx.isValid():
        return ""
    src = w.proxy_model.mapToSource(idx)
    df = w.source_model.getDataFrame()
    return "" if not src.isValid() else str(df.iloc[src.row()]["data_id"])


def _clean_board_state(w):
    """把主窗恢复到「只有一份 proxy、面板与条件一致」的干净态。

    本文件前面几条用例把 w.proxy_model 换成过裸 AuditProxyModel（没挂 source model），
    模块级 fixture 会把这个脏状态带到后面每条用例。
    """
    from PySide6.QtWidgets import QApplication
    w.proxy_model = w.table_view.model()
    w.filter_panel.reset_filters()
    w.proxy_model.setCustomFilters({})
    w._link_snapshot = None
    w._link_return = None
    w._link_return_board = None
    QApplication.processEvents()


def test_clear_link_drilldown_returns_to_original_row(main_window):
    """点横幅「清除」→ 回到钻取前那一行，流程订单框也回填原值（v43.362）。"""
    import pandas as pd
    from PySide6.QtWidgets import QApplication

    w = main_window
    df = _main_df()
    w.source_model.setDataFrame(df)
    w.view_model.df = df
    _clean_board_state(w)
    w.table_view.selectRow(5)
    assert _current_data_id(w) == "d5"

    w._apply_link_drilldown(
        pd.Series({"流程订单": "170003", "工厂": "食品厂", "物料编码": "30000003"}),
        "负损看板")
    assert w._link_return == ("d5", "")
    assert w.filter_panel.process_order_edit.text() == "170003"

    w._clear_link_drilldown()
    QApplication.processEvents()
    assert w.filter_panel.process_order_edit.text() == ""
    assert _current_data_id(w) == "d5", "清除联动后没有跳回原来那一行"
    assert w._link_snapshot is None and w._link_return is None


def test_clear_link_drilldown_skips_hidden_return_row(main_window, monkeypatch):
    """原行被恢复后的筛选挡住时不硬跳（选区不该落到不可见行上）。"""
    import pandas as pd
    from PySide6.QtWidgets import QApplication

    w = main_window
    df = _main_df()
    w.source_model.setDataFrame(df)
    w.view_model.df = df
    _clean_board_state(w)
    w.table_view.selectRow(5)

    w._apply_link_drilldown(pd.Series({"流程订单": "170003", "工厂": "食品厂"}), "正损看板")
    # 把「钻取前」口径改成只剩 d0：要回的 d5 恢复筛选后是隐藏行
    w._link_snapshot = {"物料名称": "物料0"}
    w._link_return = ("d5", "")
    calls = []
    monkeypatch.setattr(w, "_locate_row_in_main_table",
                        lambda did, silent=False: calls.append(did) or True)

    w._clear_link_drilldown()
    QApplication.processEvents()
    assert calls == [], "d5 已被筛掉，不该再往它身上跳"
    assert w.proxy_model.getCustomFilters().get("物料名称") == "物料0"


def test_clear_link_drilldown_brings_the_board_back(main_window):
    """看板为联动「让位」而隐藏；点横幅「清除」→ 看板弹回原位（v43.363）。

    这是 裴哥 要的那条路径：双击负损看板某行 → 主表筛出这一单 → 看完点「清除」
    → 负损看板自己回到屏幕上原来那块位置，选中行仍是刚才双击的那一行。
    """
    import pandas as pd
    from PySide6.QtWidgets import QApplication
    from gui_pyside6.widgets.neg_loss_content import NegLossContent

    w = main_window
    df = _main_df()
    w.source_model.setDataFrame(df)
    w.view_model.df = df
    _clean_board_state(w)
    w.table_view.selectRow(5)
    assert w._link_return_board is None

    # 真实 Content 作看板内容，承载窗由 _present_board 现造（key 用测试专用名，不撞车）
    key = "neg_loss|test_recall"
    content = NegLossContent(w)
    dlg = w.dashboard_controller._present_board(key, "负损看板（测试）", content,
                                                content=content)
    try:
        assert dlg.isVisible()

        w._apply_link_drilldown(
            pd.Series({"流程订单": "170003", "工厂": "食品厂"}), "负损看板")
        content.handoff_to_main.emit()       # 与 on_double_click 成功后同一发信号
        QApplication.processEvents()
        assert not dlg.isVisible(), "让位之后看板窗还挂着"
        assert w._link_return_board is dlg

        w._clear_link_drilldown()
        QApplication.processEvents()
        assert dlg.isVisible(), "清除联动后看板没有弹回原位"
        assert w._link_return_board is None
        assert _current_data_id(w) == "d5"
    finally:
        w.dashboard_controller._board_windows.pop(key, None)
        w._link_return_board = None
        dlg.deleteLater()
        content.deleteLater()
