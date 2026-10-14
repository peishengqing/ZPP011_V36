# -*- coding: utf-8 -*-
"""筛选预设职责测试（ARC-003 第三刀，v43.195）。

补的正是这块此前的测试盲区：原实现里 _capture_last_used_filter /
_refresh_filter_preset_menu 用 `except Exception: pass` 静默吞异常，且 tests/
完全不覆盖——坏了不会报错、不会崩，只是功能不响应。本文件把行为钉住。

覆盖重点：两个纯函数（_filters_to_jsonable / _jsonable_to_filters）的逐分支
行为，断言按**原实现语义**写（不是理想语义），确保搬迁零行为漂移。
"""
import os
import sys
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.controllers.filter_preset_controller import FilterPresetController  # noqa: E402

SHELLS = [
    "_filter_preset_store", "_filters_to_jsonable", "_jsonable_to_filters",
    "_capture_last_used_filter", "_save_filter_preset", "_prompt_save_preset",
    "_apply_filter_preset", "_delete_filter_preset", "_refresh_filter_preset_menu",
]


def _load_main_window_cls():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from gui_pyside6.main_window import MainWindow
    return MainWindow


def _make_ctrl(store=None):
    """构造 controller + 装配好转发关系的假 MainWindow。

    真实 MainWindow 上，controller 内部的自调用（self.mw._filter_preset_store() 等）
    是经薄壳转发回 controller 的；mock 必须复现这层转发，否则 controller 拿到的是
    Mock 对象而非 dict/set，报 'argument of type Mock is not iterable'。
    """
    ctrl = FilterPresetController.__new__(FilterPresetController)
    cfg = mock.Mock()
    cfg.get.return_value = {} if store is None else store
    mw = mock.Mock()
    mw.config_manager = cfg
    mw._filter_preset_store.side_effect = lambda: dict(cfg.get("filter_history") or {})
    mw._filters_to_jsonable.side_effect = FilterPresetController._filters_to_jsonable
    mw._jsonable_to_filters.side_effect = FilterPresetController._jsonable_to_filters
    ctrl.mw = mw
    return ctrl, mw, cfg


# ---------- 1. 拆分结构护栏 ----------

def test_all_9_shells_exist_on_mainwindow():
    MW = _load_main_window_cls()
    missing = [m for m in SHELLS if not callable(getattr(MW, m, None))]
    assert not missing, f"MainWindow 缺失筛选预设薄壳: {missing}"


def test_all_9_methods_live_on_controller():
    missing = [m for m in SHELLS if not callable(getattr(FilterPresetController, m, None))]
    assert not missing, f"FilterPresetController 缺失方法: {missing}"


def test_controller_holds_mw_backref():
    ctrl = FilterPresetController(mock.Mock())
    assert hasattr(ctrl, "mw")


def test_jsonable_transformers_are_still_staticmethods():
    """关键回归：这两个是纯函数，必须保持 staticmethod 语义。

    搬迁时若误写成实例方法，MainWindow 薄壳会报
    `takes 1 positional argument but 2 were given`（已真实踩过）。
    """
    for name in ("_filters_to_jsonable", "_jsonable_to_filters"):
        raw = FilterPresetController.__dict__[name]
        assert isinstance(raw, staticmethod), f"{name} 必须保持 @staticmethod"
    MW = _load_main_window_cls()
    for name in ("_filters_to_jsonable", "_jsonable_to_filters"):
        assert isinstance(MW.__dict__[name], staticmethod), (
            f"MainWindow.{name} 薄壳也必须保持 @staticmethod"
        )


# ---------- 2. _filters_to_jsonable 逐分支（原实现语义） ----------

def test_to_jsonable_set_becomes_sorted_str_list():
    assert FilterPresetController._filters_to_jsonable({"厂": {"B", "A"}}) == {"厂": ["A", "B"]}


def test_to_jsonable_tuple_col_set_becomes_dict():
    src = {"_units": (3, {"y", "x"})}
    assert FilterPresetController._filters_to_jsonable(src) == {
        "_units": {"col": 3, "values": ["x", "y"]}
    }


def test_to_jsonable_tuple_without_set_passthrough():
    # tuple 但第二元素不是 set → 走 else 原样保留
    src = {"pair": (1, 2)}
    assert FilterPresetController._filters_to_jsonable(src) == {"pair": (1, 2)}


def test_to_jsonable_plain_values_passthrough():
    src = {"a": 1, "b": "x", "c": None, "d": False, "e": 2.5}
    assert FilterPresetController._filters_to_jsonable(src) == src


def test_to_jsonable_none_input():
    assert FilterPresetController._filters_to_jsonable(None) == {}
    assert FilterPresetController._filters_to_jsonable({}) == {}


def test_to_jsonable_semi_class_set_list_passthrough():
    """原实现：_semi_class_set 若已是 list，走 else 原样保留（非 set 分支）。"""
    src = {"_semi_class_set": ["饼干", "糕点"]}
    assert FilterPresetController._filters_to_jsonable(src) == src


# ---------- 3. _jsonable_to_filters 逐分支（原实现语义） ----------

def test_to_filters_semi_class_set_list_becomes_set():
    src = {"_semi_class_set": ["饼干", "糕点"]}
    assert FilterPresetController._jsonable_to_filters(src) == {
        "_semi_class_set": {"饼干", "糕点"}
    }


def test_to_filters_units_dict_becomes_tuple():
    src = {"_units": {"col": 3, "values": ["x", "y"]}}
    out = FilterPresetController._jsonable_to_filters(src)
    assert out["_units"] == (3, {"x", "y"})
    assert isinstance(out["_units"], tuple)


def test_to_filters_plain_values_passthrough():
    src = {"a": 1, "b": "x", "c": None}
    assert FilterPresetController._jsonable_to_filters(src) == src


def test_to_filters_semi_class_set_non_list_passthrough():
    src = {"_semi_class_set": {"已", "是集"}}  # 已是 set → 不进 isinstance(list) 分支
    assert FilterPresetController._jsonable_to_filters(src) == src


def test_to_filters_units_dict_missing_values_key():
    out = FilterPresetController._jsonable_to_filters({"_units": {"col": 9}})
    assert out["_units"] == (9, set())


# ---------- 4. 存取链路（mock 隔离 config_manager） ----------

def test_filter_preset_store_reads_config_and_copies():
    """store 必须返回 dict副本——防外部改动污染 config 缓存。"""
    src = {"___last___": {"a": 1}, "预设1": {"b": 2}}
    cfg = mock.Mock()
    cfg.get.return_value = src
    mw = mock.Mock()
    mw.config_manager = cfg
    out = FilterPresetController(mw)._filter_preset_store()
    assert out == src and out is not src, "必须是副本而非同一引用"
    cfg.get.assert_called_once_with("filter_history")


def test_filter_preset_store_handles_none():
    cfg = mock.Mock()
    cfg.get.return_value = None
    mw = mock.Mock()
    mw.config_manager = cfg
    assert FilterPresetController(mw)._filter_preset_store() == {}


def test_capture_last_used_filter_writes_and_refreshes():
    ctrl, mw, cfg = _make_ctrl({})
    mw.filter_panel.get_filters.return_value = {"厂": {"A"}}
    ctrl._capture_last_used_filter()
    cfg.set.assert_called_once()
    key, val = cfg.set.call_args[0]
    assert key == "filter_history"
    assert "___last___" in val
    mw._refresh_filter_preset_menu.assert_called_once()


def test_capture_last_used_filter_skips_when_empty():
    """筛选态为空时不应写入（否则会存一个空预设占位）。"""
    ctrl, mw, cfg = _make_ctrl({})
    mw.filter_panel.get_filters.return_value = {}
    ctrl._capture_last_used_filter()
    cfg.set.assert_not_called()


def test_capture_last_used_filter_swallows_exception():
    """既存行为：静默吞异常（fail-safe，不打断分析主流程）。本测试钉住它。"""
    ctrl, mw, cfg = _make_ctrl({})
    mw.filter_panel.get_filters.side_effect = RuntimeError("boom")
    ctrl._capture_last_used_filter()  # 不应抛出
    cfg.set.assert_not_called()


def test_refresh_menu_excludes_reserved_last_key():
    ctrl, mw, cfg = _make_ctrl({"___last___": {}, "A": {}, "B": {}})
    ctrl._refresh_filter_preset_menu()
    mw.filter_panel.set_preset_names.assert_called_once_with(["A", "B"], True)


def test_refresh_menu_swallows_exception():
    ctrl, mw, cfg = _make_ctrl({})
    mw.filter_panel.set_preset_names.side_effect = RuntimeError("boom")
    ctrl._refresh_filter_preset_menu()  # 不应抛出


def test_delete_preset_only_writes_when_present():
    ctrl, mw, cfg = _make_ctrl({"A": {"x": 1}, "___last___": {}})
    with mock.patch("gui_pyside6.controllers.filter_preset_controller.toast"):
        ctrl._delete_filter_preset("A")
    key, val = cfg.set.call_args[0]
    assert key == "filter_history"
    assert "A" not in val and "___last___" in val


def test_delete_preset_noop_when_absent():
    ctrl, mw, cfg = _make_ctrl({"A": {}})
    ctrl._delete_filter_preset("不存在")
    cfg.set.assert_not_called()


def test_apply_preset_missing_does_not_touch_panel():
    ctrl, mw, cfg = _make_ctrl({})
    with mock.patch("gui_pyside6.controllers.filter_preset_controller.toast"):
        ctrl._apply_filter_preset("___last___")
    mw.filter_panel.apply_filters.assert_not_called()


def test_save_preset_writes_name_and_refreshes():
    ctrl, mw, cfg = _make_ctrl({})
    mw.filter_panel.get_filters.return_value = {"厂": {"A"}}
    with mock.patch("gui_pyside6.controllers.filter_preset_controller.toast"):
        ctrl._save_filter_preset("我的预设")
    key, val = cfg.set.call_args[0]
    assert key == "filter_history" and "我的预设" in val
    mw._refresh_filter_preset_menu.assert_called_once()
