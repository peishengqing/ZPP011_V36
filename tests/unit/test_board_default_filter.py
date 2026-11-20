# -*- coding: utf-8 -*-
"""未读/负损看板默认筛选回归（v44.08，裴哥 2026-11-20 截图：筛未读混出已读行）。

根因：set_data 在 _initializing=True 守卫期内调 _apply_default_filter，
而 _apply_filter 首行 `if self._initializing: return` → 首次筛选空操作，
表格停留全量数据（已读+未读混杂），下拉却仍显示「未读」。
修复：两个看板均改为先 `_initializing = False` 再 `_apply_default_filter()`。
"""
import os
import sys
import types

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gui_pyside6.shells.unread_dashboard as ud_mod
import gui_pyside6.shells.negloss_dashboard as ng_mod


def _row(订单="9000", 物料="2000", 日期="2026-11-01", read=0, quar=0):
    return dict(工厂="1000", 订单日期=日期, 流程订单=订单, 物料编码=物料,
                物料描述="物%s" % 物料, 净偏差数量=-1.0, 是否替代料="否", 备注="",
                **{"数量-实际": 1.0, "数量-定额": 10.0},
                _read=read, _quarantined=quar, _post_audit_changed=0)


def _df_mixed():
    """隔离区已读×2 + 隔离区未读×3 + 无分类已读×2 → 默认应只显 3 行未读。"""
    rows = [_row(订单="90%d" % i, 物料="20%d" % i, read=1, quar=1) for i in range(2)]
    rows += [_row(订单="91%d" % i, 物料="21%d" % i, 日期="2026-11-02", read=0, quar=1)
             for i in range(3)]
    rows += [_row(订单="92%d" % i, 物料="22%d" % i, 日期="2026-11-03", read=1)
             for i in range(2)]
    return pd.DataFrame(rows)


def _df_all_read():
    """截图同构：隔离区全部已读×4 + 无分类未读×3 + 无分类已读×5 → KPI 全 0。"""
    rows = [_row(订单="90%d" % i, 物料="20%d" % i, read=1, quar=1) for i in range(4)]
    rows += [_row(订单="91%d" % i, 物料="21%d" % i, 日期="2026-11-02", read=0)
             for i in range(3)]
    rows += [_row(订单="92%d" % i, 物料="22%d" % i, 日期="2026-11-03", read=1)
             for i in range(5)]
    return pd.DataFrame(rows)


def _stub_db():
    """打桩 DB 只读路径（名字已 import 进看板模块命名空间，须原地替换）。"""
    ud_mod.get_quarantined_ids = lambda: set()
    ud_mod.load_read_status = lambda dids: {}
    ng_mod.get_quarantined_ids = lambda: set()
    ng_mod.load_read_status = lambda dids: {}


def _make_unread(df, qapp):
    _stub_db()
    mw = types.SimpleNamespace(alert_monitor=None)
    from gui_pyside6.shells.unread_dashboard import UnreadDashboard
    return UnreadDashboard(df.copy(), mw)


def _make_negloss(df, qapp):
    _stub_db()
    mw = types.SimpleNamespace(alert_monitor=None)
    from gui_pyside6.shells.negloss_dashboard import NegLossDashboard
    return NegLossDashboard(df.copy(), mw)


def _model_df(board):
    m = board.source_model
    for attr in ("getDataFrame", "get_df", "dataframe"):
        fn = getattr(m, attr, None)
        if callable(fn):
            return fn()
    for attr in ("_df", "df", "_data"):
        v = getattr(m, attr, None)
        if v is not None:
            return v
    raise AssertionError("拿不到模型 DataFrame")


def _read_series(mdf):
    return pd.to_numeric(mdf["_read"], errors="coerce").fillna(0)


# ---------- 未读看板 ----------

def test_unread_default_shows_only_unread(qapp):
    board = _make_unread(_df_mixed(), qapp)
    assert board.combo_read.currentText() == "未读"
    mdf = _model_df(board)
    assert len(mdf) == 3                              # 只剩 3 行隔离区未读
    assert int((_read_series(mdf) == 1).sum()) == 0   # 表中不得混入已读行


def test_unread_default_fallback_when_no_unread(qapp):
    # 截图场景：KPI 全 0 → 回退「已读=全部」且下拉如实显示；
    # 表内只剩 4 行隔离区行，无分类的 ✓/○ 行不再混入。
    board = _make_unread(_df_all_read(), qapp)
    assert board.combo_read.currentText() == "全部"
    mdf = _model_df(board)
    assert len(mdf) == 4
    assert (mdf["_quarantined"] == 1).all()


# ---------- 负损看板（同款修复）----------

def test_negloss_default_shows_only_unread(qapp):
    board = _make_negloss(_df_mixed(), qapp)
    assert board.combo_read.currentText() == "未读"
    mdf = _model_df(board)
    assert int((_read_series(mdf) == 1).sum()) == 0
