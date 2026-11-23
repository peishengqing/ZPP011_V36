# -*- coding: utf-8 -*-
"""变动提醒「净偏差数量(前/后)」口径回归（裴哥 2026-11-23 报障，v44.11）。

报障样例：杏仁片 2026-11-05 / 300525247 / 40000060，定额 196.632、
旧实际 120 → 新实际 210，主表净偏差 13.37（=210−196.632）。
旧逻辑把变更增量 90 又加到后值上 → 导出写 103.37，虚高 90。

钉死两条口径：
1. 后值 net_new 一律 = 主表当前净偏差，与实际数量是否变动无关（不得补增量）；
2. 前值 net_old：有基线快照用快照；无基线且实际变动时用「后值−变动量」反推。
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _mkdf(actual=210.0, net=13.37, did="2026-11-05|300525247|40000060"):
    """构造已审核且变动、未读的一行；基线快照由 monkeypatch load_read_status 提供。"""
    return pd.DataFrame({
        "data_id": [did],
        "_post_audit_changed": [1],
        "_read": [0],
        "实际数量": [actual],
        "净偏差数量": [net],
    })


def _svc_with_baseline(monkeypatch, *, snap_qty=None, snap_net=None):
    """打桩 load_read_status，避免写真库；返回 ReadStatusService。

    ReadStatusService.get_audit_changes 用 7 列结构解包 status_map：
    (_hist_read, _hist_fp, _hist_snap, _hist_note, _hist_yield, _hist_source, _hist_net)
    """
    from gui_pyside6.services import read_status_service as rss

    def fake_load(data_ids):
        out = {}
        for did in data_ids:
            out[did] = (1, "fp", snap_qty, "备注", None, "manual", snap_net)
        return out

    monkeypatch.setattr(rss, "load_read_status", fake_load)
    return rss.ReadStatusService()


def _only(changes):
    assert len(changes) == 1, changes
    return changes[0]


def test_qty_change_net_new_equals_master_without_baseline(monkeypatch):
    """核心回归：实际 120→210（基线 qty=120），主表净偏差 13.37 → 后值必须 13.37，不得 +90。"""
    svc = _svc_with_baseline(monkeypatch, snap_qty=120.0, snap_net=None)
    ch = _only(svc.get_audit_changes(_mkdf(actual=210.0, net=13.37)))
    assert ch["field"] == "实际数量"
    assert ch["net_new"] == 13.37                     # v44.11：主表真源，旧逻辑会是 103.37
    assert ch["net_old"] == -76.63                    # 13.37 − (210−120) 反推


def test_qty_change_net_new_equals_master_with_baseline(monkeypatch):
    """有基线快照：前值用快照 −76.63，后值仍取主表 13.37。"""
    svc = _svc_with_baseline(monkeypatch, snap_qty=120.0, snap_net=-76.63)
    ch = _only(svc.get_audit_changes(_mkdf(actual=210.0, net=13.37)))
    assert ch["net_old"] == -76.63
    assert ch["net_new"] == 13.37


def test_qty_unchanged_net_delta_not_added(monkeypatch):
    """实际数量没变（备注变动场景）：后值=主表净值，不得凭空加增量。"""
    df = _mkdf(actual=210.0, net=13.37)
    svc = _svc_with_baseline(monkeypatch, snap_qty=210.0, snap_net=13.37)
    ch = _only(svc.get_audit_changes(df))
    assert ch["net_new"] == 13.37
    assert ch["net_old"] == 13.37


def test_net_only_change_not_doubled(monkeypatch):
    """仅净偏差变动（替代料抵扣变化）：后值=主表净值 20.0，不加任何实际增量。"""
    # 基线备注给 None，避免 note_diff 抢在 net_diff 前面（本例只验证净偏差口径）
    svc = _svc_with_baseline(monkeypatch, snap_qty=210.0, snap_net=13.37)
    from gui_pyside6.services import read_status_service as rss

    def fake_load(data_ids):
        return {did: (1, "fp", 210.0, None, None, "manual", 13.37) for did in data_ids}

    monkeypatch.setattr(rss, "load_read_status", fake_load)
    ch = _only(svc.get_audit_changes(_mkdf(actual=210.0, net=20.0)))
    assert ch["field"] == "净偏差数量"
    assert ch["net_old"] == 13.37
    assert ch["net_new"] == 20.0


def test_no_baseline_at_all_net_new_still_master(monkeypatch):
    """完全无基线（老数据）：后值仍是主表净值，前值缺失不硬造。"""
    from gui_pyside6.services import read_status_service as rss
    monkeypatch.setattr(rss, "load_read_status", lambda ids: {})
    ch = _only(rss.ReadStatusService().get_audit_changes(_mkdf(actual=210.0, net=13.37)))
    assert ch["net_new"] == 13.37
    assert ch["net_old"] is None


def test_float_tail_rounded_two(monkeypatch):
    """反推前值保留两位，不留 -76.63000000000001 长尾。"""
    svc = _svc_with_baseline(monkeypatch, snap_qty=120.0, snap_net=None)
    ch = _only(svc.get_audit_changes(_mkdf(actual=210.3, net=13.668)))
    assert ch["net_old"] == round(13.668 - 90.3, 2)
    assert ch["net_new"] == 13.668
