# -*- coding: utf-8 -*-
"""隔离区「豁免」闭环回归测试（v43.358）。

裴哥定稿：「我选择全修但是有一点，如果触发了审核后变动，豁免失效，并给出提示。」

覆盖四件事：
1. 豁免的真源语义 —— get_exempted_uids 刻意不看 restored_at（标记豁免会同时移出，
   按在区过滤就等于「只在点下的那一刻生效」，下次自动隔离又抓回来）。
2. 自动隔离不再抓回已豁免记录（这是「豁免看起来没生效」的根因）。
3. 已读对账不碰已豁免记录（人工收口的行不自动标已读、也不自动翻回）。
4. 「审核后变动」→ 豁免自动作废 + 提示；豁免台账页可取消豁免并放回隔离区。

红线两条见 test_revoke_does_not_self_quarantine（作废不越权写隔离区）与
test_revoke_runs_before_auto_quarantine（作废必须排在自动隔离之前）。
"""
import os
import sqlite3
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

pytest.importorskip("PySide6")

import core.quarantine_manager as qm
from gui_pyside6.main_window import MainWindow as MW
from gui_pyside6.controllers.quarantine_manager_controller import QuarantineManagerController

MAIN = "gui_pyside6.main_window"
CTRL = "gui_pyside6.controllers.quarantine_manager_controller"
QM = "core.quarantine_manager"
RS = "core.read_status"


# ------------------------------------------------------------------ 最小外壳
class _FakeStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, msg, *a, **k):
        self.messages.append(msg)


class _ViewModel:
    def __init__(self, df):
        self.df = df


class _FakeSourceModel:
    def __init__(self):
        self.frames = []

    def setDataFrame(self, df):
        self.frames.append(df)


class _FakeCards:
    def __init__(self):
        self.refreshed = 0

    def refresh(self, df=None):
        self.refreshed += 1


class _FakeDataService:
    """对账用到的列探测/数值工具（候选集与真实实现一致）。"""

    def __init__(self):
        self.read_status_service = self

    @staticmethod
    def _find_real_qty_col(df):
        for c in ('数量-实际', '实际', '实际数量', 'actual'):
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _find_remark_col(df):
        for c in ('备注原因', '备注', '审核备注', 'remark'):
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _find_yield_col(df):
        for c in ('产量', '产出', 'yield'):
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _safe_qty(v):
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return float(v)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _norm_note(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ''
        s = str(v).strip()
        return '' if s.lower() in ('nan', 'none', 'nat', '') else s


class _FakeColController:
    def _apply_column_visibility_by_name(self, *a, **k):
        pass


def _bare_mw(df):
    """不跑 __init__ 的 MainWindow，装配隔离区控制器需要的最小属性。"""
    bare = MW.__new__(MW)
    bare.view_model = _ViewModel(df)
    bare.source_model = _FakeSourceModel()
    bare.stats_cards = _FakeCards()
    bare.column_controller = _FakeColController()
    bare.data_service = _FakeDataService()
    bare.statusBar = lambda: _FakeStatusBar()
    bare.log = lambda *a, **k: None
    bare._update_read_counter = lambda: None
    bare.quarantine_manager_controller = QuarantineManagerController(bare)
    return bare


def _df(ids, actual=None, quota=None, changed=None):
    n = len(ids)
    return pd.DataFrame({
        'data_id': list(ids),
        '_read': [0] * n,
        '_quarantined': [1] * n,
        '实际': list(actual) if actual else [80.0] * n,
        '数量-定额': list(quota) if quota else [100.0] * n,
        '备注原因': [''] * n,
        '产量': [10.0] * n,
        '_post_audit_changed': list(changed) if changed else [0] * n,
    })


# ══════════════════════════════ 1. 数据层语义
@pytest.fixture
def tmp_db(monkeypatch):
    """qm._get_conn 读的是模块级 DB_PATH（from core.read_status import DB_PATH），
    所以必须 patch qm 命名空间里的这个名字，patch core.read_status 无效。"""
    path = os.path.join(tempfile.mkdtemp(), "audit_test.db")
    monkeypatch.setattr(qm, "DB_PATH", path)
    yield path


def _seed(uid, reason="负损:实际>0 且 实际<定额", basis="自动规则[第1条]",
          exempted=False, restored=False):
    """直写一行隔离记录；restored=True 表示已移出隔离区（软删除）。"""
    conn = qm._get_conn()
    conn.execute(
        "INSERT INTO quarantine_records (uid, reason, quarantined_at, restored_at, reason_basis, exempted)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (str(uid), reason, "2026-11-12T10:00:00",
         "2026-11-12T11:00:00" if restored else None, basis, 1 if exempted else 0))
    conn.commit()
    conn.close()


def test_exempted_uids_ignores_restored_at(tmp_db):
    """豁免语义与「此刻在不在区里」无关：移出隔离区的豁免行仍算已豁免。

    标记豁免那一步会同时移出（restored_at 有值）。若按 restored_at IS NULL 过滤，
    豁免就只在点下的那一刻生效，下次自动隔离又把它抓回来 —— 本次修复的根因。
    """
    _seed("U_IN", exempted=True)                       # 已豁免且仍在区（历史遗留）
    _seed("U_OUT", exempted=True, restored=True)       # 已豁免且已移出（正常态）
    _seed("U_NORMAL")                                  # 在区、未豁免
    assert qm.get_exempted_uids() == {"U_IN", "U_OUT"}
    assert qm.get_quarantined_ids() == {"U_IN", "U_NORMAL"}   # 前者仍按在区过滤


def test_get_exempted_records_carries_state(tmp_db):
    """台账明细要能区分「在隔离区」与「已移出（豁免生效中）」，并给出判定依据快照。"""
    _seed("U_OUT", reason="手动:财务要求隔离", basis="手动:财务", exempted=True, restored=True)
    _seed("U_IN", exempted=True)
    recs = {r['uid']: r for r in qm.get_exempted_records()}
    assert set(recs) == {"U_OUT", "U_IN"}
    assert recs["U_OUT"]['restored_at'] and recs["U_IN"]['restored_at'] is None
    assert recs["U_OUT"]['reason_basis'] == "手动:财务"


def test_clear_exempted_batch_only_touches_given(tmp_db):
    """批量作废只动传进来的 uid，返回值就是作废条数（调用方已筛过）。"""
    for u in ("U1", "U2", "U3"):
        _seed(u, exempted=True)
    assert qm.clear_exempted_batch(["U1", "U3"]) == 2
    assert qm.get_exempted_uids() == {"U2"}
    assert qm.clear_exempted_batch([]) == 0


# ══════════════════════════════ 2. 自动隔离不再抓回已豁免
def _auto_move(df, matched, exempted, manual=False):
    """跑一次 _auto_move_to_quarantine，返回 (写库的 uid, toast 文案)。"""
    bare = _bare_mw(df)
    written, toasts, boxes = [], [], []

    def fake_add(items):
        written.extend(str(it[0]) for it in items)

    with patch(f"{CTRL}.load_auto_quarantine_config", return_value={"enabled": True, "rules": []}), \
         patch(f"{CTRL}.compute_auto_quarantine_ids", return_value=dict(matched)), \
         patch(f"{CTRL}.build_all_summary", return_value="负损"), \
         patch(f"{CTRL}.get_exempted_uids", return_value=set(exempted)), \
         patch(f"{QM}.add_quarantine_batch", side_effect=fake_add), \
         patch(f"{CTRL}.QMessageBox.information",
               side_effect=lambda *a, **k: boxes.append(a[2] if len(a) > 2 else '')), \
         patch(f"{CTRL}.toast", side_effect=lambda msg, *a, **k: toasts.append(msg)):
        MW._auto_move_to_quarantine(bare, manual=manual)
    return written, toasts, boxes


def test_auto_move_skips_exempted():
    """已豁免且命中规则的记录不得被写回隔离区（其余照常移入）。"""
    df = _df(["U1", "U2", "U3"], changed=[0, 0, 0])
    df['_quarantined'] = 0                     # 全部当前不在区里
    matched = {u: f"自动规则[{u}]" for u in ("U1", "U2", "U3")}
    written, toasts, _ = _auto_move(df, matched, exempted=["U2"])
    assert sorted(written) == ["U1", "U3"], "U2 已豁免仍被自动抓回（v43.358 回归）"
    assert "已豁免" in toasts[-1], "toast 应诚实说明有多少条因豁免未抓回"
    assert int(df.loc[df['data_id'] == 'U2', '_quarantined'].iloc[0]) == 0


def test_auto_move_all_exempted_writes_nothing_and_says_why():
    """全部命中项都已豁免 → 一条都不写库，手动入口要给出可操作的说明。"""
    df = _df(["U1", "U2"])
    df['_quarantined'] = 0
    written, _, boxes = _auto_move(df, {"U1": "r1", "U2": "r2"},
                                   exempted=["U1", "U2"], manual=True)
    assert written == []
    assert boxes and "豁免" in boxes[0] and "豁免台账" in boxes[0]
    # 全被豁免挡掉时不该假装「均已在隔离区」
    assert "均已在隔离区" not in boxes[0]


def test_auto_move_without_exempted_behaves_as_before():
    """对照：没有任何豁免时行为与修复前完全一致（不误伤正常路径）。"""
    df = _df(["U1", "U2"])
    df['_quarantined'] = 0
    written, toasts, _ = _auto_move(df, {"U1": "r1", "U2": "r2"}, exempted=[])
    assert sorted(written) == ["U1", "U2"]
    assert "已豁免" not in toasts[-1]


# ══════════════════════════════ 3. 已读对账不碰已豁免
def _reconcile(df, read_map, quarantine_ids, exempted, captured):
    """跑一次已读对账。落库函数在 reconcile 内部是 `from core.read_status import ...`
    （调用时现取），补丁目标因此是 core.read_status（RS），不是控制器命名空间。"""
    with patch(f"{QM}.get_quarantined_ids", return_value=set(quarantine_ids)), \
         patch(f"{CTRL}.get_exempted_uids", return_value=set(exempted)), \
         patch(f"{RS}.load_read_status", return_value=read_map), \
         patch(f"{RS}.save_read_status_batch",
               side_effect=lambda recs: captured.setdefault('rollback', sorted(r[0] for r in recs))), \
         patch(f"{RS}.mark_read_batch",
               side_effect=lambda ids, src, **k: captured.setdefault('read', sorted(ids))), \
         patch(f"{CTRL}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(_bare_mw(df), df)
    return captured


def test_reconcile_exempted_never_auto_read():
    """已解决（实际≥定额，+5% 小幅超投）但已豁免 → 不自动标已读，交人工收口。"""
    df = _df(["U_EX", "U_NORM"], actual=[105.0, 105.0])
    read_map = {'U_EX': (0, 'fp', None, None, None, ''),
                'U_NORM': (0, 'fp', None, None, None, '')}
    out = _reconcile(df, read_map, ['U_EX', 'U_NORM'], ['U_EX'], {})
    assert out.get('read') == ['U_NORM'], "已豁免记录被对账自动标已读（v43.358 回归）"


def test_reconcile_exempted_never_rolled_back():
    """仍负损且此前自动已读、但已豁免 → 不翻回未读。"""
    df = _df(["U_EX", "U_NORM"], actual=[80.0, 80.0])
    read_map = {'U_EX': (1, 'fp', None, None, None, 'auto'),
                'U_NORM': (1, 'fp', None, None, None, 'auto')}
    out = _reconcile(df, read_map, ['U_EX', 'U_NORM'], ['U_EX'], {})
    assert out.get('rollback') == ['U_NORM'], "已豁免记录被对账翻回未读（v43.358 回归）"


def test_reconcile_all_exempted_returns_early():
    """隔离区里全是已豁免 → 直接返回：既不读已读状态，也不有任何写入。"""
    df = _df(["U_EX"])
    reads = []
    with patch(f"{QM}.get_quarantined_ids", return_value={'U_EX'}), \
         patch(f"{CTRL}.get_exempted_uids", return_value={'U_EX'}), \
         patch(f"{RS}.load_read_status", side_effect=lambda ids: reads.append(list(ids)) or {}), \
         patch(f"{RS}.mark_read_batch", return_value=None), \
         patch(f"{RS}.save_read_status_batch", return_value=None), \
         patch(f"{CTRL}.toast", return_value=None):
        MW._reconcile_quarantine_read_status(_bare_mw(df), df)
    assert reads == [], "全部豁免时不该再读一遍已读状态（应提前返回）"


# ══════════════════════════════ 4. 审核后变动 → 豁免作废 + 提示
def _revoke(df, exempted):
    """跑一次作废扫描：clear_exempted_batch 用记录器（不碰库），
    同时监视 add_quarantine_batch —— 作废只该解除标记，写回隔离区是自动隔离的活。"""
    bare = _bare_mw(df)
    moved_in = MagicMock()
    cleared = []
    toasts = []

    with patch(f"{CTRL}.get_exempted_uids", return_value=set(exempted)), \
         patch(f"{CTRL}.clear_exempted_batch",
               side_effect=lambda uids: cleared.extend(uids) or len(uids)), \
         patch(f"{CTRL}.toast",
               side_effect=lambda m, lvl='info', **k: toasts.append((m, lvl))), \
         patch(f"{CTRL}.add_quarantine_batch", moved_in), \
         patch(f"{QM}.add_quarantine_batch", moved_in):
        ids = MW._revoke_exemptions_on_post_audit_change(bare, df)
    return {'cleared': cleared, 'toasts': toasts, 'ret': ids, 'moved_in': moved_in}


def test_revoke_only_changed_and_exempted():
    """只有「已豁免 ∩ 审核后变动」才被作废，两者缺一不可。"""
    df = _df(["U_CH", "U_UNCH", "U_NOTEX"], changed=[1, 0, 1])
    out = _revoke(df, ["U_CH", "U_UNCH"])
    assert out['cleared'] == ['U_CH']
    assert out['ret'] == ['U_CH']


def test_revoke_notices_and_logs():
    """作废必须给出提示：toast 用 warning 级，文案说明「豁免已作废」并指向豁免台账。"""
    out = _revoke(_df(["U_CH"], changed=[1]), ["U_CH"])
    assert out['toasts'] and out['toasts'][0][1] == 'warning'
    assert '豁免已作废' in out['toasts'][0][0]
    assert '豁免台账' in out['toasts'][0][0]


def test_revoke_does_not_self_quarantine():
    """红线：作废不越权把行塞回隔离区，重新入区交给紧随其后的自动隔离按现行规则判。"""
    out = _revoke(_df(["U_CH"], changed=[1]), ["U_CH"])
    assert out['cleared'] == ['U_CH']
    assert not out['moved_in'].called, "作废函数越权写了隔离区"


def test_revoke_noop_without_any_exempted():
    """库里没有豁免记录 → 不作废、不提示（正常分析路径零打扰）。"""
    cleared = []
    toasts = []
    df = _df(["U_CH"], changed=[1])
    with patch(f"{CTRL}.get_exempted_uids", return_value=set()), \
         patch(f"{CTRL}.clear_exempted_batch",
               side_effect=lambda uids: cleared.extend(uids) or len(uids)), \
         patch(f"{CTRL}.toast", side_effect=lambda m, lvl='info', **k: toasts.append(m)):
        assert MW._revoke_exemptions_on_post_audit_change(_bare_mw(df), df) == []
    assert cleared == [] and toasts == []


def test_revoke_survives_missing_column():
    """没有 _post_audit_changed 列（还没建立已读基线）→ 静默跳过，不炸分析流程。"""
    cleared = []
    df = _df(["U_CH"]).drop(columns=['_post_audit_changed'])
    with patch(f"{CTRL}.get_exempted_uids", return_value={'U_CH'}), \
         patch(f"{CTRL}.clear_exempted_batch",
               side_effect=lambda uids: cleared.extend(uids) or len(uids)):
        assert MW._revoke_exemptions_on_post_audit_change(_bare_mw(df), df) == []
    assert cleared == []


def test_revoke_runs_before_auto_quarantine():
    """源码里作废调用排在 _auto_move_to_quarantine(manual=False) 之前。"""
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "gui_pyside6", "main_window.py"), encoding="utf-8").read()
    r = src.index("self._revoke_exemptions_on_post_audit_change()")
    a = src.index("self._auto_move_to_quarantine(manual=False)")
    assert r < a, "作废必须排在自动隔离之前，否则被作废的行这次仍进不了判定"


# ══════════════════════════════ 5. 豁免台账页
import gui_pyside6.dialogs.quarantine_dialog as qd
from gui_pyside6.dialogs.quarantine_dialog import QuarantineDialog


MAIN_DF = pd.DataFrame({
    "data_id": ["U1", "U2", "U3"],
    "物料编码": ["M001", "M002", "M003"],
    "物料名称": ["瓶身", "瓶盖", "标签"],
    "车间": ["灌装", "灌装", "包装"],
    "定额": [100.0, 100.0, 100.0],
    "实际": [80.0, 90.0, 70.0],
    "备注": ["", "", ""],
    "_read": [0, 0, 0],
    "_quarantined": [0, 0, 0],
})


class _FakeMain:
    def __init__(self, df):
        self.view_model = _ViewModel(df)
        self.source_model = None
        self.stats_cards = None
        self._expired_q_cache = {}

    def _update_quarantine_badge(self, expired):
        pass


@pytest.fixture
def exempt_env(monkeypatch):
    """豁免台账的落库替身 + 台账内容（不碰 SQLite，也不读项目配置）。"""
    calls = {"unexempt": [], "add_batch": [], "toast": []}
    recs = [
        {'uid': 'U1', 'reason': '手动:财务要求隔离', 'reason_basis': '手动:财务',
         'quarantined_at': '2026-11-12T10:00:00', 'restored_at': '2026-11-12T10:05:00'},
        {'uid': 'U3', 'reason': '自动规则:负损', 'reason_basis': '',
         'quarantined_at': '2026-11-11T09:00:00', 'restored_at': None},
    ]
    monkeypatch.setattr(qd, "get_exempted_records", lambda: list(recs))
    monkeypatch.setattr(qd, "get_quarantine_records", lambda: [])
    monkeypatch.setattr(qd, "scan_expired_quarantine", lambda df, cfg=None: [])
    monkeypatch.setattr(qd, "load_auto_quarantine_config", lambda: {"rules": []})
    monkeypatch.setattr(qd, "set_exempted",
                        lambda uid, flag: calls["unexempt"].append((str(uid), flag)))
    monkeypatch.setattr(qd, "add_quarantine_batch",
                        lambda items: calls["add_batch"].append(list(items)))
    monkeypatch.setattr(qd, "toast",
                        lambda msg, kind='info', parent=None, **kw: calls["toast"].append(msg))
    return calls


@pytest.fixture
def dlg(qapp, exempt_env):
    d = QuarantineDialog(MAIN_DF.copy(), _FakeMain(MAIN_DF.copy()))
    d.show()
    yield d
    d.close()


def _select_exempt_row(dlg, row):
    from PySide6.QtCore import QItemSelectionModel
    sel = dlg.exempt_view.selectionModel()
    sel.clearSelection()
    sel.select(dlg.exempt_model.index(row, 0),
               QItemSelectionModel.Select | QItemSelectionModel.Rows)


def test_third_tab_exists_and_counts(dlg):
    titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert any(t.startswith("豁免台账") for t in titles), titles
    assert dlg.tabs.count() == 3
    assert dlg.exempt_count_label.text() == "已豁免：2 条"


def test_ledger_rows_show_state_and_material(dlg):
    """台账要给出物料信息 + 「在区/已移出」，否则无法判断这条现在归谁管。"""
    edf = dlg.exempt_model.getDataFrame()
    assert list(edf['data_id']) == ['U1', 'U3']
    assert edf.loc[0, '当前状态'].startswith('已移出')
    assert edf.loc[1, '当前状态'] == '在隔离区'
    assert edf.loc[0, '物料名称'] == '瓶身'
    assert edf.loc[0, '车间'] == '灌装'


def test_cancel_exempt_puts_row_back(dlg, exempt_env):
    """取消豁免：作废标记 + 写回隔离区 + 主表 _quarantined=1（闭环，反悔可用）。"""
    _select_exempt_row(dlg, 0)
    dlg._cancel_exempt_selected()
    assert ('U1', False) in exempt_env["unexempt"]
    assert exempt_env["add_batch"] and {it[0] for it in exempt_env["add_batch"][0]} == {'U1'}
    # 当初的判定依据快照要带走，失效复核才能按同一条规则复算
    assert exempt_env["add_batch"][0][0][2] == "手动:财务"
    assert int(dlg.main_window.view_model.df.loc[
        dlg.main_window.view_model.df['data_id'] == 'U1', '_quarantined'].iloc[0]) == 1
    assert any('取消豁免' in t for t in exempt_env["toast"])


def test_cancel_exempt_falls_back_when_no_basis(dlg, exempt_env):
    """旧行没有依据快照（reason_basis 空列）→ 标记为「手动:取消豁免」，便于追溯来源。"""
    _select_exempt_row(dlg, 1)
    dlg._cancel_exempt_selected()
    assert exempt_env["add_batch"][0][0][2] == "手动:取消豁免"


def test_ledger_hint_announces_auto_revoke(dlg):
    """页面说明必须写清「审核后改动会自动作废」，否则裴哥以为豁免永久有效。"""
    texts = [w.text() for w in dlg.tab_exempt.findChildren(type(dlg.exempt_count_label))]
    joined = " ".join(t for t in texts if t)
    assert '改动' in joined and '作废' in joined


def test_ledger_hides_read_helper_cols(dlg):
    """台账表头只有业务列，不露 _read/_read_source。"""
    mdf = dlg.exempt_model.getDataFrame()
    for col in ('_read', '_read_source'):
        assert dlg.exempt_view.isColumnHidden(int(mdf.columns.get_loc(col)))
    assert not dlg.exempt_view.isColumnHidden(int(mdf.columns.get_loc('物料名称')))


def test_no_exempted_ledger_still_renders(dlg, monkeypatch):
    monkeypatch.setattr(qd, "get_exempted_records", lambda: [])
    dlg._render_exempt()
    assert dlg.exempt_count_label.text() == "已豁免：0 条"
    assert dlg.tabs.tabText(dlg.tabs.indexOf(dlg.tab_exempt)) == "豁免台账"


# ══════════════════════════════ 6. 库层护栏（真临时库）
def test_exempted_survives_reentry(tmp_db):
    """豁免标记要能扛住「移出→再写回」：add_quarantine* 的 ON CONFLICT 不重置 exempted。"""
    _seed("U1", exempted=True, restored=True)
    qm.add_quarantine("U1", "自动规则:负损", "自动规则[第1条]")
    assert qm.get_exempted_uids() == {"U1"}
    assert "U1" in qm.get_quarantined_ids()
    # 移出再取消豁免 → 标记干净归零
    qm.set_exempted("U1", False)
    assert qm.get_exempted_uids() == set()
    conn = sqlite3.connect(tmp_db)
    assert conn.execute("SELECT exempted FROM quarantine_records WHERE uid='U1'").fetchone()[0] == 0
    conn.close()
