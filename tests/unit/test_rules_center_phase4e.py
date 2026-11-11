# -*- coding: utf-8 -*-
"""Tab③「阈值与提醒」接进规则中心 + 保存当场生效（v43.356 第四期E）。

这一页改的不是「一条规则」，是**全工程的判据**。用例因此分三组，每组钉一种
「改了不生效」的事故：

1. **表单 → 落库**：五个控件对应五个键，默认值等于改造前的字面量；没点保存之前
   配置文件不产生（预览是草稿，草稿不许偷偷落盘）。
2. **预览 = 生产**：预览条数必须和 ``thr.dev_alert_mask`` 用同一份草稿算出来的
   一致；无偏差率列时显示「—」并说明原因，不许把「无从判断」写成「0 条」。
3. **保存 → 活对象**：``_apply_thresholds`` 把新值推到 AlertMonitor、代理模型、
   源模型，再走一遍 KPI/状态条/未读汇总的刷新链。这是
   ``AuditProxyModel.set_alert_threshold`` 历史上第一次真的有调用者。KPI 带那三格
   另有一组用例：改一次配置，偏差预警 / 真异常 / 通过率三格一起动。

外加入口收敛：「更多 ▸ 自动隔离规则」不再单开旧窗口，而是打开中心第 ① 页。

测试纪律：Tab①/② 的 ``save()`` 会写真配置，所以凡走到「保存全部」的用例一律把
另两页的 save 换成记账桩——本文件不落任何项目内配置文件。
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QLabel  # noqa: E402

from core import threshold_config as thr  # noqa: E402
from gui_pyside6.dialogs import auto_rules_center_dialog as center_mod  # noqa: E402
from gui_pyside6.dialogs.threshold_config_dialog import (  # noqa: E402
    ThresholdConfigWidget,
)

_ROWS = [
    # A|1 恰好到阈值（含等号）；A|2 差一点不算
    {"data_id": "A|1", "偏差率(%)": 10.0, "数量-实际": 5.0, "数量-定额": 10.0,
     "是否替代料": "否", "审核结果": "合格"},
    {"data_id": "A|2", "偏差率(%)": 9.99, "数量-实际": 5.0, "数量-定额": 10.0,
     "是否替代料": "否", "审核结果": "合格"},
    # A|3 SAP 除零钳位 +100.0（定额=0）：默认不计预警，但真异常口径仍算它
    {"data_id": "A|3", "偏差率(%)": 100.0, "数量-实际": 5.0, "数量-定额": 0.0,
     "是否替代料": "否", "审核结果": "不合格"},
    # A|4 未投料 -100.0：红线行，界面怎么说都不许被自动已读
    {"data_id": "A|4", "偏差率(%)": -100.0, "数量-实际": 0.0, "数量-定额": 10.0,
     "是否替代料": "否", "审核结果": "不合格"},
    {"data_id": "A|5", "偏差率(%)": -35.0, "数量-实际": 5.0, "数量-定额": 10.0,
     "是否替代料": "否", "审核结果": "合格"},
    # A|6 替代料：算预警、不算真异常
    {"data_id": "A|6", "偏差率(%)": 40.0, "数量-实际": 5.0, "数量-定额": 10.0,
     "是否替代料": "是", "审核结果": "合格"},
]


@pytest.fixture()
def df():
    return pd.DataFrame(_ROWS)


@pytest.fixture()
def tmp_cfg(monkeypatch, tmp_path):
    """配置指向 tmp：这一页的 save() 真会写盘，测试绝不许碰项目 config/。"""
    monkeypatch.setattr(thr, "CONFIG_PATH", str(tmp_path / "threshold_config.json"))
    monkeypatch.setattr(thr, "_cache", None)
    yield tmp_path / "threshold_config.json"
    monkeypatch.setattr(thr, "_cache", None)


@pytest.fixture()
def widget(qapp, tmp_cfg, df):
    """和中心一样的建法：建完立刻 wire_changed_signals()，改控件要实时刷预览。"""
    w = ThresholdConfigWidget(df=df).wire_changed_signals()
    yield w
    w.deleteLater()


def _raise(exc):
    def _f(*a, **k):
        raise exc
    return _f


# ---------------------------------------------------------------- 表单 → 落库
def test_five_controls_match_five_keys(widget):
    assert isinstance(widget.spin_alert, QDoubleSpinBox)
    assert (widget.spin_alert.value(), widget.spin_anomaly.value(),
            widget.spin_pass.value()) == (10.0, 30.0, 80.0)
    assert widget.chk_sap.isChecked() and widget.chk_unfed.isChecked()
    assert set(widget._draft()) == set(thr.DEFAULTS)


def test_draft_is_not_written_until_save(widget, tmp_cfg):
    widget.spin_alert.setValue(15.0)
    assert not tmp_cfg.exists()          # 预览是草稿，草稿不许偷偷落盘


def test_save_writes_the_draft_and_refreshes_cache(widget, tmp_cfg):
    widget.spin_alert.setValue(15.0)
    widget.chk_unfed.setChecked(False)
    assert widget.save() is True
    on_disk = thr.load_threshold_config()
    assert on_disk["alert_dev_rate_pct"] == 15.0
    assert on_disk["exclude_unfed"] is False
    # save_threshold_config 刷新进程内缓存，热路径不必重读文件
    assert thr.get_thresholds()["alert_dev_rate_pct"] == 15.0
    # 保存后草稿==生效值，红字提示应当自己消失
    assert "草稿" not in widget.pv_red.text()


def test_save_failure_reports_and_returns_false(qapp, tmp_cfg, df, monkeypatch):
    w = ThresholdConfigWidget(df=df)
    seen = []
    monkeypatch.setattr(thr, "save_threshold_config", _raise(OSError("磁盘满了")))
    monkeypatch.setattr(
        "gui_pyside6.dialogs.threshold_config_dialog.message_box.error",
        lambda *a, **k: seen.append(a))
    try:
        assert w.save() is False
        assert seen and seen[0][1] == "保存失败"
        assert not tmp_cfg.exists()
    finally:
        w.deleteLater()


# ---------------------------------------------------------------- 预览 = 生产
def test_preview_counts_match_production_masks(widget, df):
    draft = widget._draft()
    assert widget.pv_num.text() == str(int(thr.dev_alert_mask(df, draft).sum()))
    assert widget.pv_num.text() == "3"       # A|1 + A|5 + A|6
    assert "真异常 3 条" in widget.pv_post.text()   # A|3 + A|4 + A|5（口径不排钳位/未投料）
    assert "条预警" in widget.pv_post.text()


def test_lowering_the_alert_threshold_moves_the_preview_number(widget):
    before = int(widget.pv_num.text())
    widget.spin_alert.setValue(5.0)          # A|2 的 9.99 现在也命中
    assert int(widget.pv_num.text()) == before + 1
    assert "未保存的草稿" in widget.pv_red.text()
    # 父页从未 show 过，isVisible 恒 False；isHidden 才反映 setVisible(False) 的意图
    assert not widget.pv_red.isHidden()


def test_red_line_hides_again_when_draft_matches_saved(widget, tmp_cfg):
    widget.spin_alert.setValue(5.0)
    assert not widget.pv_red.isHidden()
    widget.save()                            # 落盘后草稿即生效值，提示该收回
    assert "草稿" not in widget.pv_red.text()
    assert widget.pv_red.isHidden()


def test_switching_off_unfed_says_rows_stay_quarantined(widget):
    widget.chk_unfed.setChecked(False)
    txt = widget.pv_red.text()
    assert "排除未投料已关" in txt
    # 红线：这一页只决定亮不亮橙色，任何措辞都不许暗示「已处理」
    assert "仍留在隔离区" in txt and "本页不改变谁被自动已读" in txt


def test_switching_off_sap_clamp_warns(widget):
    widget.chk_sap.setChecked(False)
    assert "定额=0 的 +100.0%" in widget.pv_red.text()


def test_no_rate_column_says_unknown_not_zero(qapp, tmp_cfg):
    w = ThresholdConfigWidget(df=pd.DataFrame([{"data_id": "A|1", "物料编码": "1"}]))
    try:
        assert w.pv_num.text() == "—"
        assert "无从判断" in w.pv_sample.text()
    finally:
        w.deleteLater()


def test_empty_master_says_no_data(qapp, tmp_cfg):
    w = ThresholdConfigWidget(df=pd.DataFrame())
    try:
        assert w.pv_num.text() == "—"
        assert "主表无数据" in w.pv_sample.text()
    finally:
        w.deleteLater()


def test_sample_ids_are_listed_for_spot_check(widget):
    widget.chk_unfed.setChecked(False)       # 让红线行 A|4 也进命中
    assert "样例：" in widget.pv_sample.text()
    assert "A|4" in widget.pv_sample.text()


def test_pass_rate_floor_is_reported_from_the_draft(widget):
    # 6 行里 4 行「通过」= 66.7%，默认下限 80% → 直接说低于下限
    assert "AI 通过率 67%，低于下限 80%" in widget.pv_sample.text()
    widget.spin_pass.setValue(50.0)
    assert "（下限 50%）" in widget.pv_sample.text()


# ---------------------------------------------------------------- 中心并页
def test_center_has_four_tabs_and_saves_three(qapp, tmp_cfg, df):
    dlg = center_mod.AutoRulesCenterDialog(df=df)
    done = []
    for name in ("tab_quarantine", "tab_read", "tab_threshold"):
        setattr(getattr(dlg, name), "save",
                (lambda n: lambda: (done.append(n), True)[1])(name))
    try:
        assert dlg.tabs.count() == 4
        assert dlg.tabs.tabText(2) == "③ 阈值与提醒"
        assert isinstance(dlg.tab_threshold, ThresholdConfigWidget)
        dlg._on_accept()
    finally:
        dlg.deleteLater()
    # 「保存全部」三页都要走到，阈值页不能是摆设
    assert done == ["tab_quarantine", "tab_read", "tab_threshold"]


def test_center_stays_open_when_threshold_save_fails(qapp, tmp_cfg, df, monkeypatch):
    monkeypatch.setattr(thr, "save_threshold_config", _raise(OSError("只读")))
    monkeypatch.setattr(
        "gui_pyside6.dialogs.threshold_config_dialog.message_box.error",
        lambda *a, **k: None)
    dlg = center_mod.AutoRulesCenterDialog(df=df)
    for name in ("tab_quarantine", "tab_read"):
        setattr(getattr(dlg, name), "save", lambda: True)
    try:
        dlg._on_accept()
        assert dlg.result() == 0             # 有一页没落盘就不许收窗
        assert not tmp_cfg.exists()
    finally:
        dlg.deleteLater()


def test_threshold_tab_gets_the_master_df(qapp, tmp_cfg, df, monkeypatch):
    """中心必须把主表递给阈值页，否则预览只会说「主表无数据」。"""
    seen = []
    real_cls = center_mod.ThresholdConfigWidget

    class _Spy(real_cls):
        def __init__(self, parent=None, df=None):
            seen.append(df)
            super().__init__(parent, df)

    monkeypatch.setattr(center_mod, "ThresholdConfigWidget", _Spy)
    dlg = center_mod.AutoRulesCenterDialog(df=df)
    try:
        assert seen and seen[0] is df
        assert dlg.tab_threshold.pv_num.text() == "3"
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------- 保存 → 活对象
class _FakeProxy:
    def __init__(self):
        self.threshold = None
        self.calls = 0

    def set_alert_threshold(self, v):
        self.threshold = v
        self.calls += 1


class _FakeSource:
    def __init__(self):
        self.refreshed = 0

    def refresh_threshold_colors(self):
        self.refreshed += 1


class _FakeMonitor:
    def __init__(self):
        self.threshold = None

    def update_config(self, threshold=None, only_alt=None):
        self.threshold = threshold


class _FakeMW:
    """只借 ``MainWindow._apply_thresholds`` 这一个方法，不起真窗口。"""

    def __init__(self):
        self.alert_monitor = _FakeMonitor()
        self.proxy_model = _FakeProxy()
        self.source_model = _FakeSource()
        self.view_refreshed = 0

    def _on_view_model_data_changed(self):
        self.view_refreshed += 1


def test_apply_thresholds_pushes_to_every_live_consumer(tmp_cfg, monkeypatch):
    from gui_pyside6.main_window import MainWindow

    monkeypatch.setattr(thr, "reload_thresholds",
                        lambda: dict(thr.DEFAULTS, alert_dev_rate_pct=25.0))
    mw = _FakeMW()
    MainWindow._apply_thresholds(mw)

    assert mw.alert_monitor.threshold == 25.0
    assert mw.proxy_model.threshold == 25.0      # 曾经的零调用者 setter
    assert mw.proxy_model.calls == 1
    assert mw.source_model.refreshed == 1        # 主表橙色重算
    assert mw.view_refreshed == 1                # KPI / 状态条 / 未读汇总同一条链


def test_apply_thresholds_survives_models_not_built_yet(tmp_cfg, monkeypatch):
    """启动早期 source_model/proxy_model 还是 None——保存动作不该因此炸掉。"""
    from gui_pyside6.main_window import MainWindow

    monkeypatch.setattr(thr, "reload_thresholds", lambda: dict(thr.DEFAULTS))
    mw = _FakeMW()
    mw.proxy_model = None
    mw.source_model = None
    MainWindow._apply_thresholds(mw)
    assert mw.alert_monitor.threshold == 10.0
    assert mw.view_refreshed == 1


# ---------------------------------------------------------------- 消费点同口径
def _kpi(card):
    """KPI 一格的实际文本：大字主体 + 小号单位（_split_value 拆开的两截）。"""
    return card._kpi_val.text() + "|" + card._kpi_unit.text()


def test_kpi_band_follows_the_saved_config(qapp, tmp_cfg, df):
    """KPI 带三格都读同一份配置：改一次数，三格一起动（改造前各写各的）。"""
    from gui_pyside6.widgets.stats_cards import StatsCardsWidget

    band = StatsCardsWidget()
    try:
        band.refresh(df)
        assert _kpi(band.card_deviation) == "3|"
        assert _kpi(band.card_anomaly) == "3|"
        assert _kpi(band.card_pass) == "67|% 低于80%"

        thr.save_threshold_config(dict(thr.DEFAULTS, alert_dev_rate_pct=5.0,
                                       anomaly_dev_rate_pct=50.0,
                                       ai_pass_rate_min_pct=60.0))
        band.refresh(df)
        assert _kpi(band.card_deviation) == "4|"   # A|2 的 9.99 进了预警
        assert _kpi(band.card_anomaly) == "2|"     # A|3/A|4 仍在，A|5 的 -35 出列
        assert _kpi(band.card_pass) == "67|%"       # 不再低于下限，单位只剩一个 %
    finally:
        band.deleteLater()


def test_kpi_pass_rate_no_longer_needs_the_english_column(qapp, tmp_cfg):
    """改造前只有中文「审核结果」列时 KPI 说 --，预览却说 67%：同一屏两种口径。"""
    from gui_pyside6.widgets.stats_cards import StatsCardsWidget

    band = StatsCardsWidget()
    try:
        band.refresh(pd.DataFrame([{"审核结果": "合格"}, {"审核结果": "不合格"}]))
        assert _kpi(band.card_pass) == "50|% 低于80%"
        band.refresh(pd.DataFrame([{"物料编码": "1"}]))
        assert _kpi(band.card_pass) == "--|"        # 真没有审核列才说「说不准」
    finally:
        band.deleteLater()


def test_proxy_model_boots_from_config_not_a_literal(qapp, tmp_cfg):
    from gui_pyside6.models.data_frame_model import AuditProxyModel

    thr.save_threshold_config(dict(thr.DEFAULTS, alert_dev_rate_pct=18.5))
    assert AuditProxyModel()._alert_threshold == 18.5


def test_displayed_percentages_quote_the_saved_number(qapp, tmp_cfg, df):
    """看板标题与 KPI 提示里那个百分号也是口径：曾是写死的「≥ 10%」「> 30%」。"""
    from gui_pyside6.dialogs.deviation_warning_dialog import _alert_label
    from gui_pyside6.widgets.stats_cards import StatsCardsWidget

    thr.save_threshold_config(dict(thr.DEFAULTS, alert_dev_rate_pct=15.0,
                                   anomaly_dev_rate_pct=45.0))
    assert _alert_label() == "|偏差率| ≥ 15%"
    band = StatsCardsWidget()
    try:
        band.refresh(df)
        assert "≥ 15%" in band.card_deviation.toolTip()
        assert "> 45%" in band.card_anomaly.toolTip()
    finally:
        band.deleteLater()


# ---------------------------------------------------------------- 入口收敛
class _StandIn:
    """入口方法只需要几个属性，用普通对象接住，避免构造真 MainWindow。"""


def test_more_menu_entry_opens_center_on_tab_one(qapp, monkeypatch):
    from gui_pyside6.main_window import MainWindow

    opened = []
    mw = _StandIn()
    mw._open_rule_center = lambda open_tab=0: opened.append(open_tab)
    monkeypatch.setattr(MainWindow, "_open_rule_center",
                        lambda self, open_tab=0: opened.append("real"))
    MainWindow._open_auto_quarantine_rule_dialog(mw)
    # 走的是实例上的桩（值 0），说明旧入口只是转发，没有自己开窗口
    assert opened == [0]


def test_rule_center_entry_applies_thresholds_after_accept(qapp, tmp_cfg, df, monkeypatch):
    from gui_pyside6 import main_window as mw_mod

    applied = []
    monkeypatch.setattr(mw_mod, "load_auto_quarantine_config", lambda: {})
    monkeypatch.setattr(mw_mod, "build_all_summary", lambda cfg: "空")
    monkeypatch.setattr(mw_mod, "toast", lambda *a, **k: None)

    class _DlgStub:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return 1                            # QDialog.Accepted

    monkeypatch.setattr(center_mod, "AutoRulesCenterDialog", _DlgStub)

    mw = _StandIn()
    mw._apply_thresholds = lambda: applied.append(1)
    mw._get_master_df = lambda: df
    tips = []
    mw.action_btn_auto_q = type("_Btn", (), {
        "setToolTip": lambda self, t: tips.append(t)})()
    mw_mod.MainWindow._open_rule_center(mw)
    assert applied == [1]
    assert tips and tips[0].startswith("按规则自动移入隔离区：")


# ---------------------------------------------------------------- 文案与红线
def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_entry_labels_name_all_three_rule_groups():
    """菜单/标题漏掉「阈值」，用户就找不到这一页——入口收敛要收得看得见。"""
    assert "规则中心（隔离/已读/阈值）" in _read("gui_pyside6/components/menu_bar.py")
    center_src = _read("gui_pyside6/dialogs/auto_rules_center_dialog.py")
    assert "阈值与提醒" in center_src
    # 旧入口不再实例化独立窗口类
    mw_src = _read("gui_pyside6/main_window.py")
    assert "AutoQuarantineRuleDialog(" not in mw_src


def test_red_line_wording_is_on_the_page(widget):
    joined = "　".join(l.text() for l in widget.findChildren(QLabel))
    assert "只决定亮不亮" in joined
    assert "不决定谁被自动已读" in joined


def test_both_exclusions_are_visible_checkboxes(widget):
    names = {b.text() for b in widget.findChildren(QCheckBox)}
    assert {"排除 SAP 除零假值", "排除未投料行"} <= names
