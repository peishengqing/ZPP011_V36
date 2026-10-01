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
