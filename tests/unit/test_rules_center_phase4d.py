# -*- coding: utf-8 -*-
"""规则中心 Tab② 自动已读重做（v43.355 第四期D）—— 与 Tab① 同一套形态。

钉五件事：
1. **schema 不动**：编辑区只产出 ``name / enabled / ignore_exclude_unfed /
   ignore_exclude_units / conditions`` 五个键，历史键不丢；
2. **语义不动**：规则之间是并集（顺序不改变哪些行被读掉），这条既要钉住界面上的
   说法，也要钉住数字与 ``compute_auto_read_mask`` 一致；
3. **预览与生产同源**：列表命中数来自 ``compute_read_rule_hit_counts``，预览条来自
   ``describe_read_rule_hits``，试跑走 ``compute_auto_read_mask`` + ``read_scope_mask``
   —— 设计稿改进点 4 的「两套算法」不许复发；
4. **实际=0 红线**：命中里有几条未投料必须正面写出；主表没有 ``_read`` 列时不许断言
   「一条都没读掉」；表里没有「实际数量」列时不许说「不含未投料」；
5. **只读**：换条件、加条件、点试跑都不写配置、不改主表。
"""
import copy
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QFrame,
    QLabel,
    QWidget,
)

from core.auto_read_rules import (
    compute_auto_read_mask,
    compute_read_rule_hit_counts,
    describe_read_rule_hits,
    read_scope_mask,
)
from gui_pyside6.components import dialog_chrome
from gui_pyside6.dialogs import auto_read_rule_dialog as mod
from gui_pyside6.dialogs.auto_read_rule_dialog import AutoReadRuleDialog, AutoReadRuleWidget

_ROWS = [
    # R1「偏差数量=0」命中的三条：两条真投料、一条实际=0（未投料）
    {"data_id": "A|1", "物料编码": "400001", "物料名称": "彩箱1", "偏差数量": 0.0,
     "数量-实际": 10.0, "单位": "箱", "_read": 0, "_quarantined": 0},
    {"data_id": "A|2", "物料编码": "400002", "物料名称": "彩箱2", "偏差数量": 0.0,
     "数量-实际": 5.0, "单位": "箱", "_read": 0, "_quarantined": 0},
    {"data_id": "A|3", "物料编码": "400003", "物料名称": "彩箱3", "偏差数量": 0.0,
     "数量-实际": 0.0, "单位": "箱", "_read": 0, "_quarantined": 0},
    # R2「物料600开头」带未投料豁免：A|4 实际=0、A|5 已经读过
    {"data_id": "A|4", "物料编码": "600001", "物料名称": "托盘A", "偏差数量": -3.0,
     "数量-实际": 0.0, "单位": "个", "_read": 0, "_quarantined": 0},
    {"data_id": "A|5", "物料编码": "600002", "物料名称": "托盘B", "偏差数量": 2.0,
     "数量-实际": 8.0, "单位": "个", "_read": 1, "_quarantined": 0},
    # R1 命中，但在隔离区：自动已读不碰它
    {"data_id": "A|6", "物料编码": "400006", "物料名称": "彩箱6", "偏差数量": 0.0,
     "数量-实际": 5.0, "单位": "箱", "_read": 0, "_quarantined": 1},
    # 只有停用的 R3 会命中
    {"data_id": "A|7", "物料编码": "300007", "物料名称": "脱氧剂", "偏差数量": -1.0,
     "数量-实际": 7.0, "单位": "G", "_read": 0, "_quarantined": 0},
    {"data_id": "A|8", "物料编码": "300008", "物料名称": "标签纸", "偏差数量": 9.0,
     "数量-实际": 3.0, "单位": "G", "_read": 0, "_quarantined": 0},
]


def _c(t, **params):
    return {"type": t, "params": params}


def _rule(name, conds, enabled=True, unfed=False, units=False):
    return {"name": name, "enabled": enabled, "ignore_exclude_unfed": unfed,
            "ignore_exclude_units": units, "conditions": conds}


_CFG = {
    "enabled": True,
    "exclude_unfed": False,
    "exclude_units": False,
    "excluded_units": "",
    "rules": [
        _rule("R1 偏差数量=0", [_c("dev_qty_eq", value=0)]),
        _rule("R2 物料600开头", [_c("mat_code_prefix", value="600")],
              unfed=True, units=True),
        _rule("R3 偏差数量<0", [_c("dev_qty_lt", value=0)], enabled=False),
    ],
}


@pytest.fixture()
def widget(qapp, monkeypatch):
    """构造 Tab②，配置读写与弹窗都拦在内存里。"""
    monkeypatch.setattr(mod, "load_auto_read_rules_config", lambda: copy.deepcopy(_CFG))
    writes, dialogs = [], []
    monkeypatch.setattr(mod, "save_auto_read_rules_config",
                        lambda cfg: writes.append(copy.deepcopy(cfg)))
    for fn in ("info", "warn", "error"):
        monkeypatch.setattr(mod.message_box, fn,
                            lambda *a, **k: dialogs.append((a, k)))
    monkeypatch.setattr(mod.message_box, "confirm",
                        lambda *a, **k: dialogs.append((a, k)) or True)
    w = AutoReadRuleWidget(df=pd.DataFrame(_ROWS)).wire_changed_signals()
    w._writes = writes
    w._dialogs = dialogs
    return w


def _texts(widget):
    return " ".join(lb.text() for lb in widget.findChildren(QLabel))


# ---------------------------------------------------------------- 形态
def test_layout_is_list_panel_plus_editor(widget):
    panel = widget.findChild(QFrame, "ruleListPanel")
    assert panel is not None and panel.width() == 240
    assert [r.lbl_name.text() for r in widget._rows] == [
        "R1 偏差数量=0", "R2 物料600开头", "R3 偏差数量<0"]
    foot = widget.findChild(QLabel, "ruleFoot").text()
    # 自动已读是并集：脚注不许抄 Tab① 的「命中即停」，要照实说顺序无关
    assert "命中即停" not in foot
    assert "或" in foot and "上下顺序不改变哪些行被读掉" in foot


def test_three_cards_and_semantics_line(widget):
    titles = [c.findChild(QLabel, "cGroupTitle").text()
              for c in widget.findChildren(QFrame, "cGroup")]
    assert titles == ["条件", "全局排除（所有规则共用）", "本条规则的豁免"]
    sem = _texts(widget)
    assert "条件 全部满足" in sem and "规则 任一命中" in sem
    assert "任一规则命中即自动已读" in sem


def test_condition_row_labels_read_ru_then_qie(widget):
    """行首的字要把 AND 关系读出来：一条时是「若」，加了第二条才出现「且」。"""
    assert widget._rows_cond[0].lbl_and.text() == "若"
    widget.btn_add_cond.click()
    assert [w.lbl_and.text() for w in widget._rows_cond] == ["若", "且"]


def test_exclusion_switches_default_off_and_say_so(widget):
    """红线文案：两个排除开关默认关着，关着时未投料会被一起读掉 —— 不许含糊。"""
    assert not widget.chk_exclude_unfed.isChecked()
    assert "默认" in _texts(widget) and "实际=0（未投料）" in _texts(widget)


# ---------------------------------------------------------------- 预览与生产同源
def test_list_hit_counts_come_from_production_matcher(widget):
    stats = compute_read_rule_hit_counts(widget.df, widget._cfg_draft())
    assert [s["hits"] for s in stats] == [4, 2, 2]     # R3 停用：若启用会命中 2
    for i in (0, 1):
        assert widget._rows[i].lbl_num.text() == str(stats[i]["hits"])
        assert "占比" in widget._rows[i].lbl_post.text()
    assert widget._rows[2].lbl_pre.text() == "已停用 · 命中"
    assert widget._rows[2].lbl_num.text() == "—"


def test_preview_bar_numbers_equal_describe_read_rule_hits(widget):
    widget.chk_ignore_unfed.setChecked(True)
    got = describe_read_rule_hits(widget.df, widget._collect_preview(),
                                  widget._globals_draft())
    assert widget.pv_num.text() == str(got["hits"]) == "4"
    assert got["pending_hits"] == 3                     # A|6 在隔离区、不算真跑会读的
    assert got["unfed_hits"] == 1                       # A|3 实际=0
    assert "真跑实际读掉 3 条" in widget.pv_post.text()
    assert got["unfed_text"] in widget.pv_red.text()
    for s in got["samples"]:
        assert s in widget.pv_sample.text()


def test_global_exclusion_moves_the_preview_and_names_the_blocker(widget):
    widget.chk_exclude_unfed.setChecked(True)           # A|3 该被挡掉
    got = describe_read_rule_hits(widget.df, widget._collect_preview(),
                                  widget._globals_draft())
    assert got["hits"] == 3 and got["raw_hits"] == 4
    assert got["blocked_by"] == ["排除未投料（实际=0）"]
    assert widget.pv_num.text() == "3"
    assert "排除未投料" in widget.pv_red.text()
    # 豁免那条（R2）不受影响：切过去仍是 2 条，且照实报未投料
    widget.list_rules.setCurrentRow(1)
    assert widget.pv_num.text() == "2"
    assert "其中 1 条实际=0（未投料）—— 现在会被一起自动已读" in widget.pv_red.text()


def test_trial_run_uses_production_union_and_scope(widget):
    """试跑的数字必须等于生产 (union, read_scope_mask)，不许另算一套。"""
    widget.list_rules.setCurrentRow(1)                  # R2：带未投料豁免
    widget.btn_trial.click()
    probe = dict(_CFG)
    probe["rules"] = copy.deepcopy(_CFG["rules"])
    probe["rules"][1] = widget._collect_preview()
    union, _ = compute_auto_read_mask(widget.df, probe)
    scope = read_scope_mask(widget.df)
    assert int(union.sum()) == 6
    assert int((union & scope).sum()) == 4              # A|5 已读、A|6 在隔离区
    assert "试跑" in widget.pv_post.text()
    assert "合计符合 6" in widget.pv_post.text() and "实际读掉 4" in widget.pv_post.text()
    assert widget._writes == []
    assert "未落库" in widget._dialogs[0][0][1]


def test_trial_run_warns_when_unfed_rows_would_be_read(widget):
    """红线：真跑会连带读掉未投料行时，弹窗必须是提醒而不是「完成」。"""
    widget.btn_trial.click()
    (args, kwargs), = widget._dialogs
    assert args[1] == "试跑完成（未落库）"
    assert "未投料" in kwargs["detail"] and "排除未投料" in kwargs["detail"]
    assert widget._writes == []


# ---------------------------------------------------------------- 诚实的「说不准」
def test_empty_master_table_does_not_claim_zero_hits(widget):
    widget.set_df(pd.DataFrame())
    assert all(r.lbl_pre.text() == "主表无数据 · 不计命中" for r in widget._rows)
    assert widget.pv_num.text() == "—"
    assert "无数据" in widget.pv_sample.text()


def test_missing_read_column_is_not_reported_as_nothing_to_read(widget):
    df = pd.DataFrame(_ROWS).drop(columns=["_read", "_quarantined"])
    widget.set_df(df)
    assert widget.pv_num.text() == "4"                  # 命中照算
    assert "主表还没有「已读」列" in widget.pv_red.text()
    assert "真跑实际读掉" not in widget.pv_post.text()
    assert all(r.lbl_pre.text() != "主表无数据 · 不计命中" for r in widget._rows)


def test_missing_actual_qty_column_says_cannot_judge(widget):
    df = pd.DataFrame(_ROWS).drop(columns=["数量-实际"])
    widget.set_df(df)
    assert "无从判断" in widget.pv_red.text()


def test_master_switch_off_says_not_counted(widget):
    widget.chk_master.setChecked(False)
    assert all(r.lbl_pre.text() == "总开关已关 · 不计命中" for r in widget._rows)
    assert "总开关已关，真跑时一条都不会读" in widget.pv_red.text()
    assert "真跑实际读掉" not in widget.pv_post.text()


def test_disabled_rule_red_line_says_it_reads_nothing(widget):
    """停用那条不许留下「真跑会读掉 N 条」的错觉 —— 生产会整条跳过。"""
    widget.list_rules.setCurrentRow(2)                  # R3 enabled=False
    assert widget.pv_num.text() == "2"                  # 若启用会命中 2
    assert "本条已停用，真跑时它一条都不读" in widget.pv_red.text()
    assert "真跑实际读掉" not in widget.pv_post.text()


# ---------------------------------------------------------------- schema 与只读
def test_collect_preview_emits_exactly_five_keys(widget):
    assert set(widget._collect_preview()) == {
        "name", "enabled", "ignore_exclude_unfed", "ignore_exclude_units", "conditions"}


def test_commit_preserves_unknown_legacy_keys(widget):
    widget.cfg["rules"][0]["legacy_备注"] = "别删我"
    widget.edit_name.setText("改过的名字")
    widget._commit_editor()
    assert widget.cfg["rules"][0]["name"] == "改过的名字"
    assert widget.cfg["rules"][0]["legacy_备注"] == "别删我"


def test_condition_type_switch_rebuilds_matching_param_widget(widget):
    """类型与参数控件必须同步：这里回归的是旧版「combo 与 .value() 撞 QLineEdit 崩」。"""
    row = widget._rows_cond[0]
    row.combo_type.setCurrentIndex(row.combo_type.findData("mat_code_prefix"))
    assert isinstance(row._param, QLineEdit)
    assert row.get_condition() == {"type": "mat_code_prefix", "params": {"value": "600"}}
    row.combo_type.setCurrentIndex(row.combo_type.findData("dev_qty_range"))
    assert isinstance(row._param, tuple) and len(row._param) == 2
    row.combo_type.setCurrentIndex(row.combo_type.findData("dev_qty_gt"))
    assert isinstance(row._param, QDoubleSpinBox)
    row.combo_type.setCurrentIndex(row.combo_type.findData("dev_qty_eq"))
    assert isinstance(row._param, QDoubleSpinBox)


def test_number_param_sits_next_to_the_type_combo(widget, qapp):
    """参数一律左靠：布局把剩余空间摊到控件之间时，单个 spinbox 会被推到中间，
    看着像少了一个字段（Tab① 的字段行都是「标签 + 输入」，只有这里是裸输入）。"""
    widget.resize(960, 640)
    widget.show()
    for _ in range(4):
        qapp.processEvents()
    row = widget._rows_cond[0]
    row.combo_type.setCurrentIndex(row.combo_type.findData("dev_qty_gt"))
    for _ in range(2):
        qapp.processEvents()
    left = row._param.mapTo(row, row._param.pos()).x()
    assert left - row.combo_type.geometry().right() <= 8, "参数被摊到中间了"
    widget.hide()


def test_last_condition_row_cannot_be_deleted(widget):
    before = len(widget._rows_cond)
    widget._remove_condition_row(widget._rows_cond[0])
    assert len(widget._rows_cond) == before
    assert widget._dialogs and "至少保留一个条件" in widget._dialogs[0][0][2]


def test_save_writes_globals_and_only_the_edited_rule(widget):
    widget.edit_excluded_units.setText("G，个")
    widget.chk_exclude_units.setChecked(True)
    widget.chk_master.setChecked(False)
    widget.edit_name.setText("改名了")
    assert widget.save() is True
    (saved,) = widget._writes
    assert saved["enabled"] is False
    assert saved["exclude_units"] is True and saved["excluded_units"] == "G，个"
    assert saved["rules"][0]["name"] == "改名了"
    assert saved["rules"][1]["conditions"] == _CFG["rules"][1]["conditions"]


def test_preview_and_trial_never_mutate_inputs(widget):
    before_cfg = copy.deepcopy(widget.cfg)
    before_df = widget.df.copy(deep=True)
    widget.btn_add_cond.click()
    widget._rows_cond[-1].combo_type.setCurrentIndex(
        widget._rows_cond[-1].combo_type.findData("mat_name_contains"))
    widget._refresh_preview()
    widget._on_trial_run()
    assert widget.cfg == before_cfg
    assert widget.df.equals(before_df)
    assert widget._writes == []


# ---------------------------------------------------------------- 外壳 / 令牌
def test_qss_has_no_unsubstituted_tokens(widget):
    assert "$" not in widget.styleSheet()


def test_tab_fits_the_large_tier_width(widget):
    """整页最小宽度不许顶破 large 档位（960）。

    这轮真踩到的：把「（未读且不在隔离区）」「总开关已关…」这类长句全塞进不换行的
    预览主行，最小宽度顶到 1078，规则中心一打开就被撑宽；长句改放会换行的红线行。
    """
    widget.list_rules.setCurrentRow(0)
    widget._refresh_preview()
    assert widget.pv_post.minimumSizeHint().width() <= 320
    assert widget.minimumSizeHint().width() <= dialog_chrome.DIALOG_SIZES["large"][0]


def test_theme_flip_restyles_tab(widget, qapp):
    from utils.theme_manager import Thm
    light = widget.styleSheet()
    Thm.set_dark(True)
    try:
        assert widget.styleSheet() != light
    finally:
        Thm.set_dark(False)
    assert widget.styleSheet() == light


def test_standalone_shell_uses_large_tier(qapp):
    from PySide6.QtCore import Qt
    dlg = AutoReadRuleDialog(df=pd.DataFrame(_ROWS))
    assert (dlg.width(), dlg.height()) == dialog_chrome.DIALOG_SIZES["large"]
    assert dlg.windowTitle().startswith("自动已读规则")
    assert dlg.windowFlags() & Qt.WindowMaximizeButtonHint
    assert isinstance(dlg.widget, AutoReadRuleWidget)
    dlg.deleteLater()


def test_center_passes_master_df_to_read_tab(qapp, monkeypatch):
    """规则中心必须把主表递给 Tab②，否则命中预览永远是「无数据」。"""
    from gui_pyside6.dialogs import auto_rules_center_dialog as center

    seen = []

    class _StubTab(QWidget):
        saved = Signal(bool)

        def __init__(self, parent=None, df=None):
            super().__init__(parent)
            seen.append(df)

        def wire_changed_signals(self):
            return self

        def save(self):
            return True

    monkeypatch.setattr(center, "AutoQuarantineRuleWidget", _StubTab)
    monkeypatch.setattr(center, "AutoReadRuleWidget", _StubTab)
    monkeypatch.setattr(center, "RulePreviewWidget",
                        lambda df, parent=None: _StubTab(parent, df))
    dlg = center.AutoRulesCenterDialog(df=pd.DataFrame(_ROWS))
    assert len(seen) == 3                        # 两页规则 + 影子预览都要拿到主表
    assert all(df is not None and len(df) == len(_ROWS) for df in seen)
    assert dlg.tabs.count() == 3
    dlg.deleteLater()


def test_old_linear_form_is_gone(widget):
    """旧版的「当前规则预览」长标签不该还挂在页面上（信息已进卡片与 tooltip）。"""
    assert widget.findChild(QLabel, "ruleSummaryLabel") is None
    assert widget.findChild(QComboBox, "condType") is not None
    assert len(widget.findChildren(QCheckBox)) <= 8
