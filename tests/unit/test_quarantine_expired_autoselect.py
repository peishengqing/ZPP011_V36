# -*- coding: utf-8 -*-
"""隔离区「失效复核」扫描后自动选中回归测试（v43.357）。

裴哥需求原话：「在失效复核那里，点击扫描失效，可以自动选中列出的行，然后我就可以点击
设为已读并移出隔离区（选中行），不需要我手动选中。」

本期只自动**选中**，不自动**改状态**：扫描一条记录都不会被标为已读或移出隔离区，
必须用户点右侧按钮 —— 与「状态变更要手动」的既定口径一致，红线钉在下面第 5 条。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest

pytest.importorskip("PySide6")

import gui_pyside6.dialogs.quarantine_dialog as qd
from gui_pyside6.dialogs.quarantine_dialog import QuarantineDialog


def _expired(uid, reason="负损（实际<定额）", detail="补投后已相符", actual=120.0, quota=100.0):
    return {"uid": uid, "reason": reason, "basis": "手动:负损", "detail": detail,
            "actual": actual, "quota": quota, "status": "neg_loss_resolved"}


class _ViewModel:
    def __init__(self, df):
        self.df = df


class _FakeMainWindow:
    """只提供 QuarantineDialog 实际用到的属性：主表、失效缓存、角标刷新。"""

    def __init__(self, df):
        self.view_model = _ViewModel(df)
        self._expired_q_cache = {}
        self.badge_calls = []
        self.source_model = None  # 有属性但为 None → 弹窗跳过主表重建

    def _update_quarantine_badge(self, expired):
        self.badge_calls.append(len(expired))


MAIN_DF = pd.DataFrame({
    "data_id": ["U1", "U2", "U3"],
    "物料编码": ["M001", "M002", "M003"],
    "物料名称": ["瓶身", "瓶盖", "标签"],
    "车间": ["灌装", "灌装", "包装"],
    "定额": [100.0, 100.0, 100.0],
    "实际": [80.0, 90.0, 120.0],
    "备注": ["", "", ""],
    "_read": [0, 0, 0],
    "_quarantined": [1, 1, 1],
})


@pytest.fixture
def patched(monkeypatch):
    """把弹窗命名空间里的落库/扫描函数换成记录器：测试不碰 SQLite，也不读项目配置。"""
    calls = {"scan": [], "read_batch": [], "remove_batch": [], "toast": []}

    def _scan(df, cfg=None):
        recs = calls["scan_result"]
        calls["scan"].append(len(recs))
        return list(recs)

    monkeypatch.setattr(qd, "scan_expired_quarantine", _scan)
    monkeypatch.setattr(qd, "load_auto_quarantine_config", lambda: {"rules": []})
    monkeypatch.setattr(qd, "get_quarantine_records", lambda: [])
    monkeypatch.setattr(qd, "get_exempted_records", lambda: [])
    monkeypatch.setattr(qd, "save_read_status_batch",
                        lambda records: calls["read_batch"].append(list(records)))
    monkeypatch.setattr(qd, "remove_quarantine_batch",
                        lambda ids: calls["remove_batch"].append(sorted(ids)))
    monkeypatch.setattr(qd, "toast", lambda msg, kind="success", parent=None, **kw:
                        calls["toast"].append(msg))
    import core.read_status as rs
    monkeypatch.setattr(rs, "load_read_status", lambda ids: {})
    calls["scan_result"] = []
    return calls


@pytest.fixture
def dialog(qapp, patched):
    dlg = QuarantineDialog(MAIN_DF.copy(), _FakeMainWindow(MAIN_DF.copy()))
    dlg.show()
    yield dlg
    dlg.close()


def _selected_uids(dlg):
    sel = dlg.expired_view.selectionModel()
    if sel is None or not sel.hasSelection():
        return []
    df = dlg.expired_model.getDataFrame()
    rows = sorted({i.row() for i in sel.selectedIndexes()})
    return [str(df.iloc[r].get("data_id")) for r in rows if r < len(df)]


def test_scan_selects_every_listed_row(dialog, patched):
    """点「扫描失效」→ 列出的 3 行全部处于选中态（用户不用再框选）。"""
    patched["scan_result"] = [_expired("U1"), _expired("U2"), _expired("U3")]
    dialog.btn_scan_expired.click()
    assert _selected_uids(dialog) == ["U1", "U2", "U3"]
    assert dialog.expired_view.selectionModel().hasSelection()


def test_scan_toast_and_label_say_rows_are_selected(dialog, patched):
    """提示要说清「已全选」，否则用户不知道自己已经被选中了，容易误点右侧按钮。"""
    patched["scan_result"] = [_expired("U1"), _expired("U2")]
    dialog.btn_scan_expired.click()
    assert any("已自动全选" in m for m in patched["toast"])
    assert "已自动全选" in dialog.expired_count_label.text()


def test_scan_then_mark_read_needs_no_manual_select(dialog, patched):
    """扫描后直接点「设为已读并移出隔离区（选中行）」就要生效，且带走全部 3 条。"""
    patched["scan_result"] = [_expired("U1"), _expired("U2"), _expired("U3")]
    dialog.btn_scan_expired.click()
    dialog.btn_mark_read_expired.click()
    assert patched["remove_batch"] == [["U1", "U2", "U3"]]
    assert len(patched["read_batch"]) == 1
    assert {r[0] for r in patched["read_batch"][0]} == {"U1", "U2", "U3"}
    assert all(r[1] == 1 for r in patched["read_batch"][0])


def test_scan_then_remove_only_selected_dialog_path(dialog, patched):
    """另一个按钮「移出隔离区（选中行）」同样能直接用；它不该写已读。"""
    patched["scan_result"] = [_expired("U1"), _expired("U2")]
    dialog.btn_scan_expired.click()
    dialog.btn_remove_expired.click()
    assert patched["remove_batch"] == [["U1", "U2"]]
    assert patched["read_batch"] == []


def test_scan_itself_never_changes_state(dialog, patched):
    """红线：扫描只改选中态。落库函数一次都不许被调用。"""
    patched["scan_result"] = [_expired("U1"), _expired("U2"), _expired("U3")]
    dialog.btn_scan_expired.click()
    assert patched["read_batch"] == [], "扫描失效自动改了已读状态"
    assert patched["remove_batch"] == [], "扫描失效自动移出了隔离区"
    main_df = dialog.main_window.view_model.df
    assert list(main_df["_read"]) == [0, 0, 0]
    assert list(main_df["_quarantined"]) == [1, 1, 1]


def test_empty_scan_selects_nothing(dialog, patched):
    """扫出 0 条：不选中，提示也别说「已全选」。"""
    patched["scan_result"] = []
    dialog.btn_scan_expired.click()
    assert not dialog.expired_view.selectionModel().hasSelection()
    assert patched["toast"] == ["扫描完成：没有失效记录"]
    assert "已自动全选" not in dialog.expired_count_label.text()


def test_opening_dialog_does_not_preselect(dialog, patched):
    """只渲染不点扫描（打开时的初始渲染）保持原样：不预选，避免「打开即待批量操作」。"""
    patched["scan_result"] = [_expired("U1")]
    dlg2 = QuarantineDialog(MAIN_DF.copy(), _FakeMainWindow(MAIN_DF.copy()))
    assert not dlg2.expired_view.selectionModel().hasSelection()
    dlg2.close()


def test_manual_reselect_is_respected(dialog, patched):
    """自动全选后用户手动只留 1 行：按钮按用户的选择走，不会被重新全选。"""
    from PySide6.QtCore import QItemSelectionModel
    patched["scan_result"] = [_expired("U1"), _expired("U2"), _expired("U3")]
    dialog.btn_scan_expired.click()
    sm = dialog.expired_view.selectionModel()
    sm.clearSelection()
    sm.select(dialog.expired_model.index(0, 0), QItemSelectionModel.Select)
    keep = _selected_uids(dialog)
    assert len(keep) == 1
    dialog.btn_mark_read_expired.click()
    assert patched["remove_batch"] == [keep]


def test_hint_text_documents_auto_select():
    """说明文案要写明「自动全部选中」和「不会替你改状态」。"""
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "gui_pyside6", "dialogs", "quarantine_dialog.py")
    text = open(src, encoding="utf-8").read()
    assert "自动全部选中" in text
    assert "不会替你改状态" in text


def test_expired_table_hides_read_helper_cols(dialog, patched):
    """失效复核表与豁免台账共用 _hide_read_cols，两页列观感一致。"""
    patched["scan_result"] = [_expired("U1")]
    dialog.btn_scan_expired.click()
    mdf = dialog.expired_model.getDataFrame()
    for col in ('_read', '_read_source'):
        assert dialog.expired_view.isColumnHidden(int(mdf.columns.get_loc(col)))
    assert not dialog.expired_view.isColumnHidden(int(mdf.columns.get_loc('物料名称')))
