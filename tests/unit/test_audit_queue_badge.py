# -*- coding: utf-8 -*-
"""左栏「审核队列」徽标口径回归（v43.365）。

裴哥的现场反馈：「我未审核的只有 100，他审核队列还有 1591」。
根因不是算错，是两处数本来就不是同一件事：

* 点开「审核队列」看到的四行 = 隔离区 / 变动提醒 / 替代料 / 偏差率预警 四类里
  **未读且值得核对**的行（同一行落在两类里只数一次）；
* 改造前徽标 = `(主表 _read==0).sum()` = **全表未读**。主表装的是每一行物料
  （分析阈值取 0.0，零偏差的也在表里），且从没被标过已读的行默认算未读。

本文件把「徽标 == 队列去重条数、且 != 全表未读」钉死，判据真源是
``MainWindow._unread_audit_masks``。手法沿用 test_dashboard_controller.py：
只导入 MainWindow 类、把未绑定方法挂到 SimpleNamespace 上，不建真窗口
（建窗口会有弹框把 pytest 卡死）。
"""
import os
import sys
import types

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _mw(df):
    """挂上三个真方法的假 MainWindow（不需要 QApplication）。"""
    from gui_pyside6.main_window import MainWindow

    class _Sigs:
        _unread_audit_masks = MainWindow._unread_audit_masks
        _unread_audit_count = MainWindow._unread_audit_count
        _count_unread_items = MainWindow._count_unread_items

    fake = _Sigs()
    fake._get_master_df = lambda: df
    fake.alert_monitor = types.SimpleNamespace(threshold=10)
    for name in ("_open_quarantine_dialog", "_show_audit_changes_dialog",
                 "_show_alert_dashboard", "_show_deviation_warning_dialog"):
        setattr(fake, name, lambda: None)
    return fake


def _df(read_all_zero=True):
    """10 行未读；隔离区{0,1} + 变动提醒{1,2} + 偏差预警{2,3}，行 1/2 故意重叠。

    四类去重后 = {0,1,2,3} 共 4 行；四个分类条数相加 = 6；全表未读 = 10。
    三个数各不一样，正好能区分「去重 / 相加 / 全表」三种口径。
    """
    n = 10
    df = pd.DataFrame({
        "data_id": [f"D{i}" for i in range(n)],
        "_read": [0] * n if read_all_zero else [0, 1, 0, 1, 0, 0, 0, 0, 0, 0],
        "_quarantined": [1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
        "_post_audit_changed": [0, 1, 1, 0, 0, 0, 0, 0, 0, 0],
        "偏差率(%)": [0.0, 0.0, 50.0, 50.0] + [1.0] * 6,
    })
    return df


# ---------- 1. 徽标 = 四类去重，不是全表未读 ----------

def test_badge_is_deduped_queue_not_whole_table_unread():
    mw = _mw(_df())
    assert mw._unread_audit_count() == 4
    # 改造前的两个错口径都必须是别的数，否则这条测试是假的
    whole_table_unread = int((mw._get_master_df()["_read"] == 0).sum())
    assert whole_table_unread == 10
    assert sum(int(m.sum()) for m in mw._unread_audit_masks(_df()).values()) == 6


def test_no_column_overcount_when_row_hits_two_boards():
    """同一行既在隔离区又在变动提醒（行 1）只数一次。"""
    mw = _mw(_df())
    masks = mw._unread_audit_masks(_df())
    assert bool(masks["隔离区"].iloc[1]) and bool(masks["变动提醒"].iloc[1])
    assert mw._unread_audit_count() == 4  # 2+2+0+2=6 相加会虚高到 6


# ---------- 2. 徽标与弹窗四行同源 ----------

def test_items_counts_match_masks():
    items = {it["label"]: it["count"] for it in _mw(_df())._count_unread_items()}
    assert items == {"隔离区": 2, "变动提醒": 2, "替代料": 0, "偏差率预警": 2}


def test_read_rows_leave_both_badge_and_popup():
    """把重叠的两行标成已读后，徽标与分类条数一起掉，不会徽标单独不动。"""
    df = _df(read_all_zero=False)  # 行 1、3 已读
    mw = _mw(df)
    items = {it["label"]: it["count"] for it in mw._count_unread_items()}
    # 隔离区{0,1}→{0}=1、变动提醒{1,2}→{2}=1、偏差{2,3}→{2}=1，去重{0,2}=2
    assert items == {"隔离区": 1, "变动提醒": 1, "替代料": 0, "偏差率预警": 1}
    assert mw._unread_audit_count() == 2


@pytest.mark.parametrize("df", [None, pd.DataFrame()])
def test_empty_master_returns_zero_and_none(df):
    mw = _mw(df)
    assert mw._unread_audit_count() == 0
    assert mw._count_unread_items() is None


# ---------- 3. 左栏确实改走这个数（防「改了真源没接线」） ----------

def test_left_panel_badge_reads_audit_count():
    src = os.path.join(ROOT, "gui_pyside6", "components", "left_panel.py")
    with open(src, encoding="utf-8") as f:
        text = f.read()
    assert "_unread_audit_count" in text, "左栏徽标必须走审核队列去重口径"
    seg = text[text.index("def refresh_counts"):text.index("def refresh_counts") + 2600]
    assert 'df["_read"] == 0' not in seg, (
        "refresh_counts 里不应再出现全表未读算式（那正是 1591 的来源）")
