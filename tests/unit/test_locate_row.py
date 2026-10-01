# -*- coding: utf-8 -*-
"""看板双击定位链路回归测试。

背景（P0）：4 个看板曾调用 ``main_window.locate_record(...)``，但该方法从未实现，
异常被 ``except (AttributeError, Exception): pass`` 吞掉 → 「双击定位主表」静默失效。
本测试锁定共享定位工具的优先级与失败提示，并守住「不得再出现 locate_record 调用」。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

import gui_pyside6.utils.locate as locate_mod
from gui_pyside6.utils.locate import locate_row


class _FakeMainWindow:
    """记录调用顺序的假主窗口。"""

    def __init__(self, excel_hit=False, data_id_hit=False, index_hit=False):
        self.calls = []
        self._excel_hit = excel_hit
        self._data_id_hit = data_id_hit
        self._index_hit = index_hit

    def _locate_row_by_excel_no(self, value):
        self.calls.append(("excel_no", value))
        return self._excel_hit

    def _locate_row_in_main_table(self, value, silent=False):
        self.calls.append(("data_id", value, silent))
        return self._data_id_hit

    def _locate_row_by_index(self, value):
        self.calls.append(("index", value))
        return self._index_hit


@pytest.fixture(autouse=True)
def _capture_toast(monkeypatch):
    messages = []
    monkeypatch.setattr(locate_mod, "toast", lambda msg, **kw: messages.append(msg))
    return messages


def test_prefers_excel_no(_capture_toast):
    mw = _FakeMainWindow(excel_hit=True)
    assert locate_row(mw, {"原表行号": 42, "data_id": "X"}) is True
    assert mw.calls == [("excel_no", "42")]


def test_falls_back_to_data_id_when_excel_no_absent(_capture_toast):
    mw = _FakeMainWindow(data_id_hit=True)
    assert locate_row(mw, {"data_id": "A|B|C"}) is True
    assert mw.calls == [("data_id", "A|B|C", True)]


def test_falls_back_to_data_id_when_excel_no_not_found(_capture_toast):
    mw = _FakeMainWindow(excel_hit=False, data_id_hit=True)
    assert locate_row(mw, {"原表行号": 7, "data_id": "D"}) is True
    assert [c[0] for c in mw.calls] == ["excel_no", "data_id"]


def test_last_resort_index_lookup(_capture_toast):
    mw = _FakeMainWindow(index_hit=True)
    assert locate_row(mw, {"原表行号": 9}) is True
    assert [c[0] for c in mw.calls] == ["excel_no", "index"]


def test_all_miss_returns_false_and_toasts(_capture_toast):
    mw = _FakeMainWindow()
    assert locate_row(mw, {"原表行号": 3, "data_id": "Z"}) is False
    assert _capture_toast, "定位失败必须给用户提示，不能静默"


@pytest.mark.parametrize("blank", [None, "", "nan", "None", float("nan")])
def test_blank_values_are_ignored(_capture_toast, blank):
    mw = _FakeMainWindow(data_id_hit=True)
    assert locate_row(mw, {"原表行号": blank, "data_id": "K"}) is True
    assert [c[0] for c in mw.calls] == ["data_id"]


def test_missing_methods_do_not_raise(_capture_toast):
    class _Bare:
        pass

    assert locate_row(_Bare(), {"原表行号": 1, "data_id": "Q"}) is False


DIALOGS = [
    "gui_pyside6/dialogs/alert_dialog.py",
    "gui_pyside6/dialogs/quarantine_dialog.py",
    "gui_pyside6/dialogs/deviation_warning_dialog.py",
    "gui_pyside6/dialogs/neg_loss_dashboard_dialog.py",
]


@pytest.mark.parametrize("rel", DIALOGS)
def test_dashboards_use_shared_locate_helper(rel):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = open(os.path.join(root, rel), encoding="utf-8").read()
    assert "locate_row(" in src, "%s 未接入共享定位工具" % rel
    assert "locate_record(" not in src, "%s 仍在调用不存在的 main_window.locate_record" % rel


# ---------------------------------------------------------------- 真实方法级
def test_locate_row_by_excel_no_matches_column_not_index(qapp):
    """核心修复点：按「原表行号」列值匹配，而不是拿 Excel 行号去撞 DataFrame 索引。

    主表索引是 RangeIndex，若按索引标签匹配，行号 3 会落到第 4 行（错位）；
    这里断言选中行确实是「原表行号 == 3」那一行。
    """
    import pandas as pd
    from PySide6.QtWidgets import QTableView

    from gui_pyside6.main_window import MainWindow
    from gui_pyside6.models.data_frame_model import DataFrameModel

    df = pd.DataFrame({
        "原表行号": [2, 3, 4, 5],
        "data_id": ["a", "b", "c", "d"],
        "物料编码": ["M1", "M2", "M3", "M4"],
    })
    model = DataFrameModel()
    model.setDataFrame(df)
    view = QTableView()
    view.setModel(model)

    class _Stub:
        pass

    stub = _Stub()
    stub.source_model = model
    stub.table_view = view
    stub.activateWindow = lambda: None
    stub.raise_ = lambda: None
    stub.log = lambda *a, **k: None
    # 关键：被测方法内部会调 self._select_source_row，桩对象必须绑定同一实现
    stub._select_source_row = lambda src_row: MainWindow._select_source_row(stub, src_row)

    assert MainWindow._locate_row_by_excel_no(stub, 4) is True
    selected = view.selectionModel().selectedRows()
    assert selected, "应选中主表对应行"
    assert selected[0].row() == 2, "原表行号=4 应落在第 3 行（位置 2），不是索引 4"

    # 不存在的行号：返回 False，不误选
    view.clearSelection()
    assert MainWindow._locate_row_by_excel_no(stub, 999) is False
    assert not view.selectionModel().selectedRows()


def test_locate_row_by_index_unchanged_semantics(qapp):
    """旧方法语义保持不变（按索引标签），避免影响 main_window 内部既有调用。"""
    import pandas as pd
    from PySide6.QtWidgets import QTableView

    from gui_pyside6.main_window import MainWindow
    from gui_pyside6.models.data_frame_model import DataFrameModel

    df = pd.DataFrame({"data_id": ["a", "b", "c"], "物料编码": ["M1", "M2", "M3"]})
    model = DataFrameModel()
    model.setDataFrame(df)
    view = QTableView()
    view.setModel(model)

    class _Stub:
        pass

    stub = _Stub()
    stub.source_model = model
    stub.table_view = view
    stub.activateWindow = lambda: None
    stub.raise_ = lambda: None
    stub.log = lambda *a, **k: None
    # 关键：被测方法内部会调 self._select_source_row，桩对象必须绑定同一实现
    stub._select_source_row = lambda src_row: MainWindow._select_source_row(stub, src_row)

    assert MainWindow._locate_row_by_index(stub, 2) is True
    assert view.selectionModel().selectedRows()[0].row() == 2
    assert MainWindow._locate_row_by_index(stub, 999) is False
