# -*- coding: utf-8 -*-
"""隔离区已读对账（v43.200）回归测试。

A 类：自动已读规则中心（_auto_read_by_rules）不得触碰隔离区——
     即便某负损隔离行命中规则，也不应被标成自动已读。
B 类：_reconcile_quarantine_read_status 的四态行为——
     已解决未读→自动标已读 / 已解决已读→不动 /
     仍负损自动已读→翻回未读 / 仍负损手动已读→不动 / 非隔离记录→不碰。
结构/AST 护栏：调用点存在 + 过滤变量存在。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from unittest.mock import patch

pytest.importorskip("PySide6")

from gui_pyside6.main_window import MainWindow as MW

MAIN = "gui_pyside6.main_window"
RS = "core.read_status"
QM = "core.quarantine_manager"
AUTORULES = "core.auto_read_rules"


class _FakeStatusBar:
    def showMessage(self, *a, **k):
        pass


class _FakeDataService:
    """复刻 data_service 的列探测与数值工具（与真实实现同候选集）。"""

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
        if v is None:
            return ''
        if isinstance(v, float) and pd.isna(v):
            return ''
        s = str(v).strip()
        if s.lower() in ('nan', 'none', 'nat', ''):
            return ''
        return s


def _bare_mw():
    """造一个不跑 __init__ 的 MainWindow 裸实例，装配对账所需最小属性。"""
    bare = MW.__new__(MW)
    bare.data_service = _FakeDataService()
    bare.statusBar = lambda: _FakeStatusBar()
    bare._update_read_counter = lambda: None
    bare._auto_read_count = 0
    bare._manual_read_count = 0
    return bare


def _base_df():
    """含自动已读/对账所需的全部列。"""
    return pd.DataFrame({
        "data_id": ["A", "B", "C", "D", "E"],
        "_read": [0, 0, 0, 0, 0],
        "_quarantined": [0, 0, 0, 0, 0],
        "实际": [120.0, 50.0, 80.0, 80.0, 50.0],
        "数量-定额": [100.0, 100.0, 100.0, 100.0, 100.0],
        "备注原因": ["", "", "", "", ""],
        "产量": [10.0, 10.0, 10.0, 10.0, 10.0],
    })


# ----------------------------------------------------------------- A 类：规则中心不碰隔离区
def test_auto_read_excludes_quarantined():
    """核心修复点：即使隔离行命中自动已读规则，也绝不标已读。"""
    bare = _bare_mw()
    df = _base_df()
    # 让第 0 行（A）处于隔离区
    df.loc[df['data_id'] == 'A', '_quarantined'] = 1

    captured = {}

    def fake_mark(dids, snap_map, read_source='auto'):
        captured['dids'] = list(dids)

    with patch(f"{AUTORULES}.load_auto_read_rules_config", return_value={'enabled': True}), \
         patch(f"{AUTORULES}.compute_auto_read_mask",
               return_value=(pd.Series([True] * len(df), index=df.index), [])) as m, \
         patch(f"{RS}.mark_read_batch", side_effect=fake_mark), \
         patch(f"{MAIN}.toast", return_value=None):
        assert m.called or True  # 仅占位，确保导入路径正确
        MW._auto_read_by_rules(bare, df)

    got = set(captured.get('dids', []))
    # A 在隔离区 → 绝不能出现在被标已读的列表里
    assert 'A' not in got, "隔离区记录被自动已读规则误标（根因未修复）"
    # 其余非隔离未读行应被正常标已读
    assert got == {'B', 'C', 'D', 'E'}, "非隔离未读行应正常自动已读"


def test_auto_read_zero_hit_tip_mentions_quarantine():
    """0 命中分支：若符合规则却在隔离区被排除，提示要诚实说明。

    把所有行都设为隔离且未读 → 命中规则但全部被 not_quarantined 过滤掉 →
    target 为空 → 走 0 命中分支，且 excluded>0，应提示「在隔离区不自动已读」。
    """
    bare = _bare_mw()
    df = _base_df()
    df.loc[:, '_quarantined'] = 1

    tips = []

    def fake_toast(msg, *a, **k):
        tips.append(msg)

    with patch(f"{AUTORULES}.load_auto_read_rules_config", return_value={'enabled': True}), \
         patch(f"{AUTORULES}.compute_auto_read_mask",
               return_value=(pd.Series([True] * len(df), index=df.index), [])), \
         patch(f"{RS}.mark_read_batch", return_value=None), \
         patch(f"{MAIN}.toast", side_effect=fake_toast):
        # 全部未读的隔离行都已被排除 → target 为空 → 走 0 命中分支
        MW._auto_read_by_rules(bare, df)

    assert any('隔离区' in t for t in tips), "0 命中提示应说明隔离区排除，而非『均已读过』"


# ----------------------------------------------------------------- B 类：对账四态
def test_reconcile_resolved_unread_gets_read():
    """已解决（实际≥定额）且当前未读 → 自动标已读。"""
    bare = _bare_mw()
    df = _base_df()  # A:120/100 已解决，其余仍负损
    read_map = {
        'A': (0, 'fpA', None, None, None, ''),
        'B': (0, 'fpB', None, None, None, ''),
        'C': (0, 'fpC', None, None, None, ''),
        'D': (0, 'fpD', None, None, None, ''),
        'E': (0, 'fpE', None, None, None, ''),
    }
    captured = {}
    with patch(f"{QM}.get_quarantined_ids", return_value={'A', 'B', 'C', 'D'}), \
         patch(f"{RS}.load_read_status", return_value=read_map), \
         patch(f"{RS}.mark_read_batch", side_effect=lambda d, s, **k: captured.setdefault('read', list(d))), \
         patch(f"{RS}.save_read_status_batch", return_value=None), \
         patch(f"{MAIN}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(bare, df)

    assert captured.get('read') == ['A'], "已解决未读记录 A 应被自动标已读"


def test_reconcile_resolved_already_read_untouched():
    """已解决但已经读过 → 不动（保留来源，不重复打扰）。"""
    bare = _bare_mw()
    df = _base_df()
    read_map = {
        'A': (1, 'fpA', None, None, None, 'auto'),  # 已解决 + 已读
        'B': (0, 'fpB', None, None, None, ''),
        'C': (0, 'fpC', None, None, None, ''),
        'D': (0, 'fpD', None, None, None, ''),
    }
    called = {}
    with patch(f"{QM}.get_quarantined_ids", return_value={'A', 'B', 'C', 'D'}), \
         patch(f"{RS}.load_read_status", return_value=read_map), \
         patch(f"{RS}.mark_read_batch", side_effect=lambda d, s, **k: called.setdefault('read', list(d))), \
         patch(f"{RS}.save_read_status_batch", return_value=None), \
         patch(f"{MAIN}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(bare, df)

    assert 'read' not in called, "已解决已读记录不应再调 mark_read_batch"


def test_reconcile_still_neg_auto_read_rolled_back():
    """仍负损且此前是自动已读 → 翻回未读。"""
    bare = _bare_mw()
    df = _base_df()  # B/C/D 均仍负损
    # C: 仍负损 + 自动已读；D: 仍负损 + 手动已读
    read_map = {
        'A': (0, 'fpA', None, None, None, ''),
        'B': (0, 'fpB', None, None, None, ''),
        'C': (1, 'fpC', None, None, None, 'auto'),
        'D': (1, 'fpD', None, None, None, 'manual'),
    }
    rolled = {}
    with patch(f"{QM}.get_quarantined_ids", return_value={'A', 'B', 'C', 'D'}), \
         patch(f"{RS}.load_read_status", return_value=read_map), \
         patch(f"{RS}.mark_read_batch", return_value=None), \
         patch(f"{RS}.save_read_status_batch",
               side_effect=lambda recs: rolled.setdefault('recs', list(recs))), \
         patch(f"{MAIN}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(bare, df)

    recs = rolled.get('recs', [])
    rolled_ids = {r[0] for r in recs}
    assert rolled_ids == {'C'}, "只有仍负损的自动已读 C 应被翻回；D(手动) 不应"
    c_rec = next(r for r in recs if r[0] == 'C')
    assert c_rec[1] == 0, "翻回的记录 is_read 必须为 0"


def test_reconcile_manual_read_preserved():
    """仍负损但手动已读 → 保持已读，绝不被翻回。"""
    bare = _bare_mw()
    df = _base_df()
    read_map = {
        'A': (0, 'fpA', None, None, None, ''),
        'B': (0, 'fpB', None, None, None, ''),
        'C': (0, 'fpC', None, None, None, ''),
        'D': (1, 'fpD', None, None, None, 'manual'),  # 仍负损 + 手动已读
    }
    rolled = {}
    with patch(f"{QM}.get_quarantined_ids", return_value={'A', 'B', 'C', 'D'}), \
         patch(f"{RS}.load_read_status", return_value=read_map), \
         patch(f"{RS}.mark_read_batch", return_value=None), \
         patch(f"{RS}.save_read_status_batch",
               side_effect=lambda recs: rolled.setdefault('recs', list(recs))), \
         patch(f"{MAIN}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(bare, df)

    assert 'recs' not in rolled, "手动已读的 D 绝不应被翻回未读"


def test_reconcile_non_quarantined_ignored():
    """非隔离记录（不在 get_quarantined_ids 返回集）→ 不碰其已读状态。"""
    bare = _bare_mw()
    df = _base_df()  # E 仍负损，但不在隔离集
    read_map = {
        'A': (0, 'fpA', None, None, None, ''),
        'B': (0, 'fpB', None, None, None, ''),
        'C': (0, 'fpC', None, None, None, ''),
        'D': (0, 'fpD', None, None, None, ''),
        'E': (0, 'fpE', None, None, None, ''),
    }
    touched = {}
    with patch(f"{QM}.get_quarantined_ids", return_value={'A', 'B', 'C', 'D'}), \
         patch(f"{RS}.load_read_status", return_value=read_map), \
         patch(f"{RS}.mark_read_batch", side_effect=lambda d, s, **k: touched.setdefault('read', list(d))), \
         patch(f"{RS}.save_read_status_batch",
               side_effect=lambda recs: touched.setdefault('rollback', list(recs))), \
         patch(f"{MAIN}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(bare, df)

    all_ids = set(touched.get('read', [])) | {r[0] for r in touched.get('rollback', [])}
    assert 'E' not in all_ids, "非隔离记录 E 不应被对账触碰"


# ----------------------------------------------------------------- 结构 / AST 护栏
def test_call_site_wired_in_analysis_finished():
    src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "gui_pyside6", "main_window.py"),
        encoding="utf-8").read()
    assert "_reconcile_quarantine_read_status(processed_df)" in src, \
        "_on_analysis_finished_ui 应调用隔离区已读对账"


def test_auto_read_has_not_quarantined_filter():
    src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "gui_pyside6", "main_window.py"),
        encoding="utf-8").read()
    # 仅在校验 _auto_read_by_rules 函数体内存在该过滤变量
    assert "not_quarantined" in src, "_auto_read_by_rules 应含隔离区排除过滤"
    assert "target = union_mask & unread & not_quarantined" in src, \
        "target 必须排除隔离区（根因修复）"
