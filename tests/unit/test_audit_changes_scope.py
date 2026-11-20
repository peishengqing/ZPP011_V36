# -*- coding: utf-8 -*-
"""变动提醒数据源 v44.06 口径回归（裴哥 2026-11-20）。

场景：纸箱原本无负损，改产量后净偏差数量转负 → 按自动隔离规则应进隔离区，
不应同时挂在变动提醒里被误审核。这里把 get_audit_changes 的默认排除口径钉死：
已隔离（_quarantined==1）与替代料（substitute_mask 命中）的行不进变动提醒；
未读概览「变动提醒」掩码（dashboard_controller._unread_audit_masks）同口径。
"""
import os
import sys
import types

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _svc():
    from gui_pyside6.services.read_status_service import ReadStatusService
    return ReadStatusService()


def _df():
    """4 行都已审核且变动、未读：行 0 普通、行 1 已隔离、行 2 替代料、行 3 普通。"""
    return pd.DataFrame({
        "data_id": [f"2026-11-01|PO{i}|M{i}" for i in range(4)],
        "_post_audit_changed": [1, 1, 1, 1],
        "_read": [0, 0, 0, 0],
        "_quarantined": [0, 1, 0, 0],
        "是否替代料": ["否", "否", "是", "否"],
        "实际数量": [1.0, 2.0, 3.0, 4.0],
        "净偏差数量": [0.0, -1.0, 2.0, 3.0],
    })


def _controller(df):
    """真 DashboardController（不建窗口，沿用 test_audit_queue_badge 的假 mw 手法）。"""
    from gui_pyside6.controllers.dashboard_controller import DashboardController

    fake = types.SimpleNamespace()
    fake._get_master_df = lambda: df
    fake.alert_monitor = types.SimpleNamespace(threshold=10)
    for name in ("_open_quarantine_dialog", "_show_audit_changes_dialog",
                 "_show_alert_dashboard", "_show_deviation_warning_dialog",
                 "_show_flip_check_dashboard", "_show_unfed_dashboard"):
        setattr(fake, name, lambda: None)
    return DashboardController(fake)


def test_quarantined_and_alt_rows_excluded():
    changes = _svc().get_audit_changes(_df())
    ids = [c["data_id"] for c in changes]
    # 只剩两行普通行；已隔离（行 1）与替代料（行 2）被默认排除
    assert ids == ["2026-11-01|PO0|M0", "2026-11-01|PO3|M3"]


def test_read_rows_still_excluded():
    df = _df()
    df.loc[0, "_read"] = 1  # 行 0 已读 → 不提醒
    changes = _svc().get_audit_changes(df)
    assert [c["data_id"] for c in changes] == ["2026-11-01|PO3|M3"]


def test_missing_judge_columns_no_false_exclude():
    """旧快照 df 没有隔离/替代料判据列时不应误伤（退回基础口径）。"""
    df = _df().drop(columns=["_quarantined", "是否替代料"])
    changes = _svc().get_audit_changes(df)
    assert len(changes) == 4


def test_unread_overview_mask_matches_dialog_source():
    """未读概览「变动提醒」掩码与弹窗同口径：隔离区/替代料行不进掩码。"""
    df = _df()
    ctrl = _controller(df)
    masks = ctrl._unread_audit_masks(df)
    assert [i for i, v in enumerate(masks["变动提醒"]) if bool(v)] == [0, 3]
    # 隔离区掩码不受影响：行 1 仍算隔离区未读
    assert [i for i, v in enumerate(masks["隔离区"]) if bool(v)] == [1]
