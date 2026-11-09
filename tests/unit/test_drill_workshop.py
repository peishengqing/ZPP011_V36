# -*- coding: utf-8 -*-
"""v43.329 看板右键「下钻该车间」回归测试。

三个既有缺陷：
1. 看板是模态 exec()，下钻成功后不关窗 → 主表被挡住，用户以为没反应；
2. 联动筛选采用叠加语义，与面板当前「未读」条件叠加成 0 行 → 主表空白；
3. 全程无可见反馈，失败也静默返回。

验证：drop_keys 生效、_filter_main_table_to_workshop 放开未读后能筛出行、
drill_to_workshop 返回 bool 并在失败时可见提示、5 个看板均接了 accept()。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from unittest.mock import patch  # noqa: E402

pytest.importorskip("PySide6")

from gui_pyside6.main_window import MainWindow as MW  # noqa: E402
from gui_pyside6.utils import locate  # noqa: E402
from gui_pyside6.utils.locate import drill_to_workshop  # noqa: E402
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel  # noqa: E402


class _Banner:
    def __init__(self):
        self.text = None

    def show_link_banner(self, text):
        self.text = text


def _bare_mw(df):
    """不跑 __init__ 的 MainWindow 裸实例，只装配联动筛选所需最小对象。"""
    bare = MW.__new__(MW)
    bare.source_model = DataFrameModel(df)
    bare.proxy_model = AuditProxyModel()
    bare.proxy_model.setSourceModel(bare.source_model)
    bare.main_table = _Banner()
    bare._link_snapshot = None
    bare._update_summary = lambda: None
    bare.log = lambda m, level="info": None
    return bare


def _df():
    return pd.DataFrame({
        'data_id': ['a', 'b', 'c', 'd'],
        '_read': [1, 1, 0, 1],
        '工厂': ['云南达利-食品厂'] * 4,
        '车间': ['2车间', '2车间', '6车间', '6车间'],
    })


# ------------------------------------------------------- drop_keys 语义
def test_apply_focus_filters_drop_keys():
    """drop_keys 必须从合并条件里剔除指定键（不污染 _link_snapshot）。"""
    bare = _bare_mw(_df())
    bare.proxy_model.setCustomFilters({'_read_status': '未读'})
    MW._apply_focus_filters(bare, {'车间': '2车间'}, '联动', drop_keys=('_read_status',))
    got = bare.proxy_model.getCustomFilters()
    assert '_read_status' not in got, '未读条件未被剔除，会与车间叠加成 0 行'
    assert got['车间'] == '2车间'
    assert bare._link_snapshot == {'_read_status': '未读'}, '清除联动时应能恢复原快照'


def test_apply_focus_filters_without_drop_keys_keeps_original():
    """反证：不传 drop_keys 时行为与 v43.328 完全一致（其它调用方零回归）。"""
    bare = _bare_mw(_df())
    bare.proxy_model.setCustomFilters({'_read_status': '未读'})
    MW._apply_focus_filters(bare, {'车间': '2车间'}, '联动')
    got = bare.proxy_model.getCustomFilters()
    assert got['_read_status'] == '未读'
    assert got['车间'] == '2车间'


# ------------------------------------------------------- 端到端：不是 0 行
def test_drill_releases_unread_and_yields_rows():
    """主表挂着「未读」且 2车间全已读 → 下钻后仍应看到 2 行，而非空白。"""
    bare = _bare_mw(_df())
    bare.proxy_model.setCustomFilters({'_read_status': '未读'})
    assert bare.proxy_model.rowCount() == 1  # 下钻前只有 1 条未读
    with patch('gui_pyside6.widgets.toast.toast', return_value=None):
        ok = MW._filter_main_table_to_workshop(
            bare, '云南达利-食品厂', '2车间', '负损看板')
    assert ok is True
    cond = bare.proxy_model.getCustomFilters()
    assert '_read_status' not in cond
    assert bare.proxy_model.rowCount() == 2, '下钻应放开未读，看到 2车间的 2 行'
    assert '2车间' in bare.main_table.text


def test_drill_no_rows_when_both_keys_empty():
    """工厂/车间都空 → 返回 False，不写联动横幅。"""
    bare = _bare_mw(_df())
    assert MW._filter_main_table_to_workshop(bare, '', '') is False
    assert bare.main_table.text is None


# ------------------------------------------------------- locate 返回 bool
def test_drill_to_workshop_returns_true_on_success():
    rec = pd.Series({'车间': '2车间', '工厂名称': '云南达利-食品厂'})
    bare = _bare_mw(_df())
    with patch('gui_pyside6.widgets.toast.toast', return_value=None):
        assert drill_to_workshop(bare, rec, '负损看板') is True


def test_drill_to_workshop_returns_false_and_warns_on_missing_workshop():
    """无车间列 → False 且给可见提示，不再静默。"""
    bare = _bare_mw(_df())
    tips = []
    with patch.object(locate, 'toast', side_effect=lambda m, **k: tips.append(m)):
        assert drill_to_workshop(bare, pd.Series({'工厂': 'X'}), '负损看板') is False
    assert tips and '车间' in tips[0]


def test_drill_to_workshop_returns_false_when_mw_none():
    assert drill_to_workshop(None, pd.Series({'车间': '2车间'})) is False


# ------------------------------------------------------- 结构护栏
def test_all_five_dashboards_close_on_success():
    """5 个看板回调都必须含 self.accept()，否则模态窗口会挡住主表。"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = [
        'alert_dialog.py', 'deviation_warning_dialog.py',
        'neg_loss_dashboard_dialog.py', 'pos_loss_dashboard_dialog.py',
        'semi_dashboard_dialog.py',
    ]
    for name in files:
        p = os.path.join(root, 'gui_pyside6', 'dialogs', name)
        with open(p, encoding='utf-8') as f:
            src = f.read()
        assert 'self.accept() if drill_to_workshop(' in src, \
            '%s 下钻成功后未关闭看板' % name
