# -*- coding: utf-8 -*-
"""v43.327 隔离区「超额投料待人工复核」回归测试。

业务口径（裴哥 2026-11-09 确认）：
  凡在隔离区、且 (实际 - 定额) / 定额 × 100 严格 > 10%，属于超额投料：
    - 不算失效（scan_expired_quarantine 不列入、不会被一键移出）
    - 不能自动已读（_reconcile_quarantine_read_status 不标 auto）
    - 此前被自动已读的翻回未读（手动已读保留）
  10% 是「实际-定额的偏差率」，不是绝对量；定额<=0 一律排除（SAP 除零钳位假值）。
"""
import os

import pandas as pd
import pytest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from core.quarantine_manager import (  # noqa: E402
    is_overfeed_needs_review,
    scan_expired_quarantine,
)
from gui_pyside6.main_window import MainWindow as MW  # noqa: E402
from gui_pyside6.controllers.quarantine_manager_controller import (  # noqa: E402
    QuarantineManagerController,
)

QM = "core.quarantine_manager"
RS = "core.read_status"
CTRL = "gui_pyside6.controllers.quarantine_manager_controller"


class _FakeStatusBar:
    def showMessage(self, *a, **k):
        pass


class _FakeDataService:
    """复刻 data_service.read_status_service 的列探测与数值工具（与真实实现同候选集）。"""

    def __init__(self):
        self.read_status_service = self

    @staticmethod
    def _find_real_qty_col(df):
        for c in ('数量-实际', '实际', '实际数量', '数量 - 实际', 'actual',
                  '实际收货数量', '已收货数量', '收货数量', '实际领用数量', '实收数量'):
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _find_remark_col(df):
        for c in ('备注原因', '备注', '审核备注', '偏差备注', 'remark'):
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _find_yield_col(df):
        for c in ('产量', '产出', 'yield', '生产数量', '产出数量'):
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _safe_qty(v):
        try:
            if v is None:
                return None
            if isinstance(v, float) and pd.isna(v):
                return None
            return float(v)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _norm_note(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ''
        return str(v)


def _bare_mw():
    bare = MW.__new__(MW)
    bare.data_service = _FakeDataService()
    bare.statusBar = lambda: _FakeStatusBar()
    bare._update_read_counter = lambda: None
    bare._auto_read_count = 0
    bare._manual_read_count = 0
    bare.quarantine_manager_controller = QuarantineManagerController(bare)
    return bare


def _df(rows):
    """rows: [(data_id, 实际, 定额, _read)]"""
    return pd.DataFrame({
        'data_id': [r[0] for r in rows],
        '实际': [r[1] for r in rows],
        '数量-定额': [r[2] for r in rows],
        '_read': [r[3] for r in rows],
        '_read_source': ['' for _ in rows],
        '备注原因': ['' for _ in rows],
        '产量': [10.0 for _ in rows],
    })


# ---------------------------------------------------------------- 判据纯函数
@pytest.mark.parametrize("actual, quota, expect", [
    (6914, 6024, True),        # 裴哥样例：+14.77%
    (1100.01, 1000, True),     # 略高于 10%（严格大于）
    (1100, 1000, False),       # 恰好 10% → 不命中
    (1050, 1000, False),       # +5% 小幅超投 → 仍按旧逻辑
    (1000, 1000, False),       # 相符
    (800, 1000, False),        # 负损
    (0, 1000, False),          # 实际归零
    (6914, 0, False),          # 定额=0：SAP 除零钳位假值，必须排除
    (100, -5, False),          # 负定额
    (None, 1000, False),
    (6914, None, False),
    (float('nan'), 1000, False),
    (float('inf'), 1000, False),
    ('abc', 1000, False),
])
def test_is_overfeed_needs_review(actual, quota, expect):
    assert is_overfeed_needs_review(actual, quota) is expect


def test_is_overfeed_threshold_override():
    """反证：阈值调高到 20% 后，样例 +14.77% 不再命中（证明不是写死的特判）。"""
    assert is_overfeed_needs_review(6914, 6024) is True
    assert is_overfeed_needs_review(6914, 6024, threshold_pct=20.0) is False


def test_is_overfeed_exact_10pct_is_false():
    """边界：严格 >10%，恰好 10% 不命中（浮点用 1100.0/1000.0 精确表示）。"""
    assert is_overfeed_needs_review(1100.0, 1000.0) is False


# ---------------------------------------------------------------- 失效扫描
def _records(uid, reason, basis):
    return [{'uid': uid, 'reason': reason, 'reason_basis': basis,
             'exempted': 0, 'quarantined_at': '2026-11-09T00:00:00'}]


def _scan(df, recs):
    with patch(f"{QM}.get_quarantine_records", return_value=recs), \
         patch(f"{QM}.is_exempted", return_value=False), \
         patch("core.auto_quarantine.compute_auto_quarantine_ids", return_value={}), \
         patch("core.auto_quarantine.load_auto_quarantine_config",
               return_value={'rules': []}):
        return scan_expired_quarantine(df)


def test_scan_expired_excludes_overfeed():
    """超额投料 >10%：无论入区原因是负损/自动规则/手动，都不算失效。"""
    df = _df([
        ('U_NEG', 6914, 6024, 0),       # 当初因负损入区，后补投超 14.77%
        ('U_AUTO', 1200, 1000, 0),      # 自动规则入区，后超 +20%
        ('U_MAN', 6914, 6024, 0),       # 手动「多耗890」入区（裴哥样例）
    ])
    recs = (
        _records('U_NEG', '自动规则[第3条:食品半成品负损]', '负损:实际>0 且 实际<定额')
        + _records('U_AUTO', '自动规则[第1条:包材负损]',
                   '自动规则[第1条:包材负损]')
        + _records('U_MAN', '多耗890', '手动:多耗890')
    )
    assert _scan(df, recs) == [], "超额投料记录绝不能进失效复核列表"


def test_scan_expired_small_overfeed_still_expired():
    """反证：+5% 未超 10%，仍按旧逻辑判失效（证明短路只拦 >10%）。"""
    df = _df([('U_NEG', 1050, 1000, 0)])
    recs = _records('U_NEG', '自动规则[第3条:食品半成品负损]',
                    '负损:实际>0 且 实际<定额')
    out = _scan(df, recs)
    assert len(out) == 1 and out[0]['uid'] == 'U_NEG'
    assert out[0]['status'] == 'neg_loss_over'


def test_scan_expired_equal_quota_still_expired():
    """反证：补投刚好相符（偏差率 0）仍算失效并自动收口。"""
    df = _df([('U_NEG', 1000, 1000, 0)])
    recs = _records('U_NEG', '自动规则[第3条:食品半成品负损]',
                    '负损:实际>0 且 实际<定额')
    out = _scan(df, recs)
    assert len(out) == 1 and out[0]['status'] == 'neg_loss_resolved'


def test_scan_expired_quota_zero_not_treated_as_overfeed():
    """定额=0（SAP 恒给 +100% 钳位）不走超额短路，仍按原逻辑判定。"""
    df = _df([('U_ZERO', 500, 0, 0)])
    recs = _records('U_ZERO', '自动规则[第3条:食品半成品负损]',
                    '负损:实际>0 且 实际<定额')
    out = _scan(df, recs)
    assert len(out) == 1, "定额=0 不应被误判为超额待复核而漏掉失效判定"


# ---------------------------------------------------------------- 已读对账
def _reconcile(df, read_map, quarantine_ids, captured, exempted=None):
    with patch(f"{QM}.get_quarantined_ids", return_value=set(quarantine_ids)), \
         patch(f"{CTRL}.get_exempted_uids", return_value=set(exempted or ())), \
         patch(f"{RS}.load_read_status", return_value=read_map), \
         patch(f"{RS}.mark_read_batch",
               side_effect=lambda d, s, **k: captured.setdefault('read', list(d))), \
         patch(f"{RS}.save_read_status_batch",
               side_effect=lambda recs: captured.setdefault('rollback', list(recs))), \
         patch(f"{CTRL}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(_bare_mw(), df)


def test_reconcile_overfeed_not_auto_read():
    """超额投料且未读 → 绝不自动标已读（裴哥样例）。"""
    df = _df([('U_MAN', 6914, 6024, 0)])
    captured = {}
    _reconcile(df, {'U_MAN': (0, 'fp', None, None, None, '')}, ['U_MAN'], captured)
    assert captured.get('read', []) == [], "超额投料记录被自动已读（v43.327 回归）"


def test_reconcile_overfeed_auto_read_rolled_back():
    """超额投料且此前是 auto 已读 → 翻回未读，交回人工复核。"""
    df = _df([('U_MAN', 6914, 6024, 1)])
    df.loc[0, '_read_source'] = 'auto'
    captured = {}
    _reconcile(df, {'U_MAN': (1, 'fp', None, None, None, 'auto')}, ['U_MAN'], captured)
    recs = captured.get('rollback', [])
    assert {r[0] for r in recs} == {'U_MAN'}
    assert recs[0][1] == 0 and recs[0][6] == ''  # is_read=0 / read_source=''


def test_reconcile_overfeed_manual_read_preserved():
    """超额投料但手动已读 → 保留（尊重人工判断，不翻回）。"""
    df = _df([('U_MAN', 6914, 6024, 1)])
    captured = {}
    _reconcile(df, {'U_MAN': (1, 'fp', None, None, None, 'manual')}, ['U_MAN'], captured)
    assert 'rollback' not in captured


def test_reconcile_small_overfeed_still_auto_read():
    """反证：+5%（未超 10%）仍按旧逻辑自动已读。"""
    df = _df([('U_SMALL', 1050, 1000, 0)])
    captured = {}
    _reconcile(df, {'U_SMALL': (0, 'fp', None, None, None, '')}, ['U_SMALL'], captured)
    assert captured.get('read') == ['U_SMALL']


# ---------------------------------------------------------------- 实际=0（未投料/非耗用）
def test_scan_expired_actual_zero_not_expired():
    """反证：实际=0（未投料/非耗用）负损入区记录绝不判失效（不进失效列表，留隔离区待审计）。"""
    df = _df([('U_ZERO', 0, 5000, 0)])
    recs = _records('U_ZERO', '自动规则[第3条:食品半成品负损]',
                    '负损:实际>0 且 实际<定额')
    out = _scan(df, recs)
    assert out == [], "实际=0 的负损记录被误判为失效（应留在隔离区审计）"


def test_reconcile_actual_zero_not_auto_read():
    """反证：实际=0（未投料/非耗用）负损记录绝不自动已读，也不自动翻回。"""
    df = _df([('U_ZERO', 0, 5000, 0)])
    captured = {}
    _reconcile(df, {'U_ZERO': (0, 'fp', None, None, None, '')}, ['U_ZERO'], captured)
    assert captured.get('read', []) == [], "实际=0 记录被自动已读"
    assert 'rollback' not in captured, "实际=0 记录被自动翻回未读"
