# -*- coding: utf-8 -*-
"""规则中心 Tab① 重做（v43.354 第四期C）—— 设计稿 rules.html 的新形态落到了 Qt。

钉四件事，顺序即改造时最担心回归的四件事：
1. **schema 不动**：编辑区仍然只产出 ``DEFAULT_RULE`` 那 16 个键，历史键不丢；
2. **预览与生产同源**：界面上的数字必须等于 ``core/auto_quarantine`` 那套匹配器
   的返回值（第四期B 抽出来的 ``compute_rule_hit_counts`` / ``describe_rule_hits``），
   设计稿改进点 4 点名的「预览一套算法、真跑另一套」不许复发；
3. **只读红线**：换条件、点试跑，都不许碰配置文件、不许改主表；
4. **形态照抄**：240px 规则列表、三张条件卡、类别/单位走可搜索多选（20 个复选框
   不再平铺）、真实命中预览条。

另有一条是这次踩出来的坑：标签换行后控件高度会被宿主（QScrollArea + 字段行）压掉
一行，第三行标签和下一个字段叠在一起。第 12 个用例专门钉住它。
"""
import copy
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QToolButton

from core.auto_quarantine import DEFAULT_RULE, compute_rule_hit_counts, describe_rule_hits
from gui_pyside6.components import dialog_chrome
from gui_pyside6.dialogs import auto_quarantine_rule_dialog as mod
from gui_pyside6.dialogs.auto_quarantine_rule_dialog import (
    AutoQuarantineRuleDialog,
    AutoQuarantineRuleWidget,
)

_ROWS = ([{"data_id": "A|%d" % i, "组件物料描述": "彩罐-500ml箱%d" % i,
           "组件物料类型描述": "包材", "数量-实际": 10.0 + i, "数量-定额": 20.0,
           "偏差率(%)": -50.0 + i, "物料编码": "4000%04d" % i, "车间": "一车间",
           "备注": "", "组件单位": "个", "净偏差金额": -100.0, "是否替代料": "否"}
          for i in range(1, 8)]
         + [{"data_id": "A|8", "组件物料描述": "替代料箱", "组件物料类型描述": "包材",
             "数量-实际": 5.0, "数量-定额": 20.0, "偏差率(%)": -75.0,
             "物料编码": "40000008", "车间": "一车间", "备注": "替代",
             "组件单位": "个", "净偏差金额": -300.0, "是否替代料": "是"}]
         + [{"data_id": "A|%d" % i, "组件物料描述": "脱氧剂片%d" % (i - 8),
             "组件物料类型描述": "原辅料", "数量-实际": 5.0, "数量-定额": 10.0,
             "偏差率(%)": -50.0, "物料编码": "3000%04d" % i, "车间": "四车间",
             "备注": "", "组件单位": "片", "净偏差金额": -30.0, "是否替代料": "否"}
            for i in (9, 10)])


def _rule(**kw):
    r = dict(DEFAULT_RULE)
    r.update(kw)
    return r


_CFG = {"enabled": True, "rules": [
    _rule(name="R1 包材负损", category_required=True, category_value="包材",
          name_keywords=["箱"], negative_loss_required=True, exclude_alt=True),
    _rule(name="R2 原辅料片", category_required=True, category_value="原辅料",
          name_keywords=[], unit_required=True, unit_value="片",
          negative_loss_required=True),
    _rule(name="R3 停用那条", enabled=False, category_required=True,
          category_value="包材", name_keywords=[], negative_loss_required=True,
          exclude_alt=False),
]}


@pytest.fixture()
def widget(qapp, monkeypatch):
    """构造 Tab①，但把配置读写和弹窗都拦在内存里 —— 测试不该碰真实文件，也不该有人等着点确定。"""
    monkeypatch.setattr(mod, "load_auto_quarantine_config",
                        lambda: copy.deepcopy(_CFG))
    writes, dialogs = [], []
    monkeypatch.setattr(mod, "save_auto_quarantine_config",
                        lambda cfg: writes.append(copy.deepcopy(cfg)))
    monkeypatch.setattr(mod.message_box, "info",
                        lambda *a, **k: dialogs.append(a))
    monkeypatch.setattr(mod.message_box, "error",
                        lambda *a, **k: dialogs.append(a))
    monkeypatch.setattr(mod.message_box, "confirm",
                        lambda *a, **k: dialogs.append(a) or True)
    w = AutoQuarantineRuleWidget(df=pd.DataFrame(_ROWS)).wire_changed_signals()
    w._writes = writes
    w._dialogs = dialogs
    return w


def _texts(widget):
    return " ".join(lb.text() for lb in widget.findChildren(QLabel))


# ---------------------------------------------------------------- 形态
def test_layout_is_list_panel_plus_editor(widget):
    """左列 240px 规则列表 + 右列编辑区，列表底部固定写明匹配顺序。"""
    panel = widget.findChild(QFrame, "ruleListPanel")
    assert panel is not None and panel.width() == 240
    assert len(widget._rows) == len(_CFG["rules"])
    assert [r.lbl_name.text() for r in widget._rows] == ["R1 包材负损", "R2 原辅料片", "R3 停用那条"]
    foot = widget.findChild(QLabel, "ruleFoot")
    assert "从上到下" in foot.text() and "命中即停" in foot.text()
    # 设计稿的「↑↓ 排序」是编辑器上方两个工具按钮，列表页脚不许谎称可拖动
    assert "↑ ↓" in foot.text() and "拖动" not in foot.text()


def test_three_condition_cards_in_mockup_order(widget):
    titles = [c.findChild(QLabel, "cGroupTitle").text()
              for c in widget.findChildren(QFrame, "cGroup")]
    assert titles == ["物料维度", "数值维度", "组织与状态"]
    sem = _texts(widget)
    assert "组内 任一满足" in sem and "组间 全部满足" in sem
    assert "三组全部命中才算命中此规则" in sem


def test_twenty_units_are_not_tiled_as_checkboxes(widget):
    """设计稿原话「20 项不再平铺」：候选枚举只进 TagMultiSelect，不进复选框。"""
    assert len(widget.findChildren(QCheckBox)) <= 12
    assert widget.tag_unit.values()[:20] == mod._BUILTIN_UNITS
    assert widget.tag_cat.values()[:5] == mod._BUILTIN_CATEGORIES
    # 「半成品分类」不是新字段：那一行只有解释文案，没有第二个控件
    g3 = [c for c in widget.findChildren(QFrame, "cGroup")
          if c.findChild(QLabel, "cGroupTitle").text() == "组织与状态"][0]
    hint = [lb for lb in g3.findChildren(QLabel, "fieldHint") if "半成品重分类" in lb.text()]
    assert len(hint) == 1 and "不另设字段" in hint[0].text()
    assert "半成品分类" not in DEFAULT_RULE


def test_zero_input_row_never_implied_handled(widget):
    """人工审计红线：界面上必须写明「实际=0」永远不进自动隔离。"""
    assert "实际=0（未投料）" in _texts(widget)


# ---------------------------------------------------------------- 预览与生产同源
def test_list_hit_counts_come_from_production_matcher(widget):
    stats = compute_rule_hit_counts(widget.df, _CFG)
    assert [s["hits"] for s in stats] == [7, 2, 8]   # R3 停用：若启用会匹配 8 条
    for i in (0, 1):
        assert widget._rows[i].lbl_num.text() == str(stats[i]["hits"])
        assert "占比" in widget._rows[i].lbl_post.text()
    # 停用那条不显示数字，避免和「这条规则坏了」混淆
    assert widget._rows[2].lbl_pre.text() == "已停用 · 命中"
    assert widget._rows[2].lbl_num.text() == "—"
    assert widget._rows[0].property("sel") == "true"


def test_master_switch_off_says_not_counted(widget):
    """总开关关着时整列不许写「命中 0 条」—— 那等于骗人说规则失效了。"""
    widget.chk_master.setChecked(False)
    assert all(r.lbl_pre.text() == "总开关已关 · 不计命中" for r in widget._rows)
    assert all(r.lbl_num.text() == "" for r in widget._rows)


def test_preview_bar_numbers_equal_describe_rule_hits(widget):
    widget.chk_cat.setChecked(True)
    widget.tag_cat.setSelected(["原辅料"])
    widget.chk_dev_rate.setChecked(True)
    widget.spin_dev_rate_min.setValue(10.0)
    widget.spin_dev_rate_max.setValue(100.0)
    got = describe_rule_hits(widget.df, widget._collect_preview())
    assert widget.pv_num.text() == str(got["hits"])
    assert "%.1f%%" % (100.0 * got["ratio"]) in widget.pv_post.text()
    assert got["amount_text"] in widget.pv_post.text()
    for s in got["samples"]:
        assert s in widget.pv_sample.text()


def test_trial_run_reports_priority_split_without_writing(widget):
    """试跑走 compute_auto_quarantine_ids：能看到「归属本条」被靠前规则抢走多少。"""
    widget.chk_cat.setChecked(True)
    widget.tag_cat.setSelected(["包材"])
    widget.btn_trial.click()
    assert widget._writes == []
    text = widget.pv_post.text()
    assert "试跑" in text and "归属" in text and "净隔离" in text
    assert widget._dialogs and "未落库" in widget._dialogs[0][1]


def test_empty_master_table_does_not_claim_zero_hits(widget):
    widget.set_df(pd.DataFrame())
    assert all(r.lbl_pre.text() == "主表无数据 · 不计命中" for r in widget._rows)
    assert widget.pv_num.text() == "—"
    assert "无数据" in widget.pv_sample.text()


# ---------------------------------------------------------------- schema 与只读红线
def test_collect_preview_emits_exactly_the_16_keys(widget):
    assert set(widget._collect_preview()) == set(DEFAULT_RULE)


def test_commit_preserves_unknown_legacy_keys(widget):
    """历史键（旧版本/外部工具写的）不能因为重做就被 update 覆盖掉。"""
    widget.cfg["rules"][0]["legacy_备注"] = "别删我"
    widget.edit_name.setText("改过的名字")
    widget._commit_editor()
    assert widget.cfg["rules"][0]["name"] == "改过的名字"
    assert widget.cfg["rules"][0]["legacy_备注"] == "别删我"


def test_save_writes_master_switch_and_current_rule_only(widget):
    widget.chk_master.setChecked(False)
    widget.edit_keywords.setText("箱，手包袋")
    assert widget.save() is True
    assert len(widget._writes) == 1
    saved = widget._writes[0]
    assert saved["enabled"] is False
    assert saved["rules"][0]["name_keywords"] == ["箱", "手包袋"]
    # 没动的规则原样保留
    assert saved["rules"][2]["name"] == "R3 停用那条"


def test_preview_never_mutates_inputs(widget):
    before_cfg = copy.deepcopy(widget.cfg)
    before_df = widget.df.copy(deep=True)
    widget.chk_unit.setChecked(True)
    widget.tag_unit.setSelected(["个", "片"])
    widget._refresh_preview()
    widget._on_trial_run()
    assert widget.cfg == before_cfg
    assert widget.df.equals(before_df)
    assert widget._writes == []


# ---------------------------------------------------------------- 布局回归（这次真踩到的）
def test_wrapped_chips_do_not_lose_a_row(widget, qapp):
    """标签换到第三行时，控件高度不许被「字段行 + QScrollArea」抠掉一行。

    实截到的回归：内容高度停在旧值 640，而布局已经需要 655，缺的 27px 正是标签
    第三行 —— 于是第三行和下面的「可搜索多选，20 项不再平铺」提示叠在一起。
    """
    widget.resize(960, 640)
    widget.show()
    widget.tag_unit.setSelected(list(mod._BUILTIN_UNITS[:8]))
    for _ in range(4):
        qapp.processEvents()

    hint = [lb for lb in widget.findChildren(QLabel, "fieldHint")
            if "20 项不再平铺" in lb.text()][0]
    for tag in (widget.tag_cat, widget.tag_unit):
        chips = tag.findChildren(QToolButton)
        rows = sorted({c.geometry().top() for c in chips})
        tag_top = tag.mapTo(widget, tag.pos()).y()
        assert len(rows) >= 2, "样本没触发换行，这条用例就白写了"
        assert tag.height() >= max(c.geometry().bottom() for c in chips), (
            "标签占 %dpx，控件只有 %dpx" % (max(c.geometry().bottom() for c in chips),
                                            tag.height()))
        assert hint.mapTo(widget, hint.pos()).y() >= tag_top + tag.height(), (
            "提示行压在标签身上：说明宿主按旧高度排的版")


# ---------------------------------------------------------------- 外壳 / 令牌
def test_qss_has_no_unsubstituted_tokens(widget):
    assert "$" not in widget.styleSheet()


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
    dlg = AutoQuarantineRuleDialog(df=pd.DataFrame(_ROWS))
    assert (dlg.width(), dlg.height()) == dialog_chrome.DIALOG_SIZES["large"]
    assert dlg.windowTitle().startswith("自动隔离规则")
    assert dlg.windowFlags() & Qt.WindowMaximizeButtonHint
    assert isinstance(dlg.widget, AutoQuarantineRuleWidget)
    dlg.deleteLater()
