# -*- coding: utf-8 -*-
"""阈值单一真源（v43.333 第四期E 第一步）—— 先把改造前那五处硬编码的输出抄死。

这一期要干的事本身很危险：把主表橙色高亮、颜色筛选、预警看板、KPI 偏差预警、
KPI 真异常、未读汇总里各写一遍的 ``>= 10`` 换成一个可配置的值。这类重构唯一的
护身符是**先钉住今天的输出**，再动代码。所以本文件的前几条用例是金矿快照：
参考实现就是改造前那五行字面量的逐字抄写，新函数必须在默认配置下和它完全一致。

钉住的东西：
1. 默认配置下 ``dev_alert_mask`` == 改造前五处共同的判据（含 +100.0% SAP 钳位
   排除、未投料排除、``>=`` 而非 ``>``、NaN 记 0）；
2. 真异常沿用改造前 stats_cards 的口径（只排替代料，**不**排 SAP 钳位与未投料）
   —— 这条看着别扭，但它是今天的数字，本期不改口径，只改「谁说了算」；
3. 数据里没有偏差率列时返回 None（无从判断），不许调用方把 0 说成「一条都没有」；
4. 带百分号的字符串偏差率：改造前主表算命中、KPI 算 0，这就是「同一屏两种红」，
   统一后两处都算命中；
5. 配置读写：坏文件回落默认并留日志，落库只有那 5 个键。
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from core import threshold_config as tc  # noqa: E402


# 10 行边界样本：阈值上下、SAP 钳位、未投料、NaN、字符串百分号、替代料
_ROWS = [
    {"偏差率(%)": 10.0, "数量-实际": 5.0, "数量-定额": 10.0, "是否替代料": "否"},
    {"偏差率(%)": 9.99, "数量-实际": 5.0, "数量-定额": 10.0, "是否替代料": "否"},
    {"偏差率(%)": -100.0, "数量-实际": 0.0, "数量-定额": 10.0, "是否替代料": "否"},
    {"偏差率(%)": 100.0, "数量-实际": 5.0, "数量-定额": 0.0, "是否替代料": "否"},
    {"偏差率(%)": -100.0, "数量-实际": 0.0, "数量-定额": 0.0, "是否替代料": "否"},
    {"偏差率(%)": np.nan, "数量-实际": 5.0, "数量-定额": 10.0, "是否替代料": "否"},
    {"偏差率(%)": "12.5%", "数量-实际": 5.0, "数量-定额": 10.0, "是否替代料": "否"},
    {"偏差率(%)": 30.1, "数量-实际": 5.0, "数量-定额": 10.0, "是否替代料": "是"},
    {"偏差率(%)": -35.0, "数量-实际": 5.0, "数量-定额": 10.0, "是否替代料": "否"},
    {"偏差率(%)": 100.0000001, "数量-实际": 5.0, "数量-定额": 0.0, "是否替代料": "否"},
]


@pytest.fixture()
def df():
    return pd.DataFrame(_ROWS)


@pytest.fixture()
def tmp_cfg(monkeypatch, tmp_path):
    """把配置文件指到 tmp，并把进程内缓存清空 —— 测试不许碰项目 config/。"""
    monkeypatch.setattr(tc, "CONFIG_PATH", str(tmp_path / "threshold_config.json"))
    monkeypatch.setattr(tc, "_cache", None)
    return tmp_path / "threshold_config.json"


# ---------------------------------------------------------------- 金矿快照
def ref_dev_alert_mask_pre_refactor(df):
    """改造前 data_frame_model / stats_cards / dashboard_controller / main_window
    四处的共同判据，逐字抄写（阈值 10、+100.0% 钳位排除、未投料排除）。"""
    rates = pd.to_numeric(
        df["偏差率(%)"].astype(str).str.replace("%", "").str.strip(),
        errors="coerce").fillna(0.0)
    a = pd.to_numeric(df["数量-实际"], errors="coerce").fillna(0)
    q = pd.to_numeric(df["数量-定额"], errors="coerce").fillna(0)
    no_input = (a.abs() <= 0.001) & (q > 0.001)
    return (rates.abs() >= 10) & ((rates - 100.0).abs() >= 1e-6) & (~no_input)


def ref_anomaly_mask_pre_refactor(df):
    """改造前 stats_cards._update_anomaly 的判据：只排替代料，不排钳位/未投料。"""
    rates = pd.to_numeric(df["偏差率(%)"], errors="coerce").fillna(0)
    is_alt = df["是否替代料"].astype(str).str.strip().isin(["是", "True", "true", "1"])
    return (~is_alt) & (rates.abs() > 30)


def test_default_config_reproduces_the_five_hardcoded_sites(df):
    got = tc.dev_alert_mask(df)
    assert list(got) == list(ref_dev_alert_mask_pre_refactor(df))
    assert tc.count_dev_alerts(df) == int(ref_dev_alert_mask_pre_refactor(df).sum()) == 5


def test_default_config_reproduces_anomaly_count(df):
    got = tc.anomaly_mask(df)
    assert list(got) == list(ref_anomaly_mask_pre_refactor(df))
    assert tc.count_anomalies(df) == 5


def test_alert_uses_ge_and_anomaly_uses_gt(df):
    """边界方向不许翻：预警是 ≥10（第 1 行算），真异常是 >30（30.1 才算）。"""
    assert bool(tc.dev_alert_mask(df).iloc[0])
    only_9_99 = pd.DataFrame([{"偏差率(%)": 9.99, "数量-实际": 5.0, "数量-定额": 10.0}])
    assert int(tc.dev_alert_mask(only_9_99).sum()) == 0
    only_30 = pd.DataFrame([{"偏差率(%)": 30.0, "数量-实际": 5.0, "数量-定额": 10.0}])
    assert int(tc.anomaly_mask(only_30).sum()) == 0


def test_sap_clamp_exclusion_is_plus_100_only(df):
    """改造前只排 +100.0%（定额=0 钳位），-100.0% 靠未投料那条排 —— 别顺手改成 abs()。"""
    m = tc.dev_alert_mask(df)
    assert not bool(m.iloc[3])          # +100.0 钳位
    assert not bool(m.iloc[9])          # +100.0000001 落在 1e-6 容差内，同样算钳位
    assert bool(m.iloc[4])              # -100.0 但定额=0（不是未投料）→ 仍计预警


def test_unfed_exclusion_follows_actual_zero_and_quota_positive(df):
    m = tc.dev_alert_mask(df)
    assert not bool(m.iloc[2])          # 实际=0 且 定额>0 → 未投料，不亮
    assert bool(m.iloc[4])              # 实际=0 但 定额=0 → 不是未投料


# ---------------------------------------------------------------- 口径统一
def test_percent_string_rates_no_longer_split_the_screen(df):
    """「12.5%」这种字符串偏差率：改造前主表算命中、KPI 与看板算 0（同一屏两种红）。

    统一后所有消费点都按 12.5 处理 —— 第 7 行必须计预警。
    """
    assert bool(tc.dev_alert_mask(df).iloc[6])
    assert float(tc.rate_series(df).iloc[6]) == 12.5


def test_missing_columns_say_we_cannot_tell(df):
    """没有偏差率列 → None（无从判断），不是全 False，更不是 0 条。"""
    no_rate = df.drop(columns=["偏差率(%)"])
    assert tc.dev_alert_mask(no_rate) is None
    assert tc.anomaly_mask(no_rate) is None
    assert tc.count_dev_alerts(no_rate) == 0      # 计数接口把「无从判断」折成 0
    empty = df.iloc[0:0]
    assert tc.dev_alert_mask(empty) is None
    assert tc.dev_alert_mask(None) is None


def test_unfed_switch_off_brings_unfed_rows_back(df):
    cfg = dict(tc.DEFAULTS, exclude_unfed=False)
    assert int(tc.dev_alert_mask(df, cfg).sum()) == 6      # 第 3 行回来
    cfg2 = dict(tc.DEFAULTS, exclude_sap_zero_div=False)
    assert int(tc.dev_alert_mask(df, cfg2).sum()) == 7     # 第 4、10 行回来


def test_threshold_change_moves_every_consumer_at_once(df):
    """阈值改成 5：第 2 行（9.99）也进预警 —— 一个值说了算，五处一起动。"""
    cfg = dict(tc.DEFAULTS, alert_dev_rate_pct=5.0)
    assert int(tc.dev_alert_mask(df, cfg).sum()) == 6
    cfg = dict(tc.DEFAULTS, alert_dev_rate_pct=30.0, anomaly_dev_rate_pct=100.0)
    assert int(tc.dev_alert_mask(df, cfg).sum()) == 3
    # 真异常沿用今天的口径，不看 SAP 钳位：100.0000001 在阈值 100 之上仍算一条
    assert int(tc.anomaly_mask(df, cfg).sum()) == 1


def test_anomaly_excludes_substitute_but_alert_does_not(df):
    """替代料只从「真异常」里排除（走替代料看板），预警口径里它照样亮 —— 与改造前一致。"""
    assert bool(tc.dev_alert_mask(df).iloc[7])
    assert not bool(tc.anomaly_mask(df).iloc[7])


def test_substitute_group_column_also_counts(df):
    """没有「是否替代料」时回退到 _替代料组 非空，照抄改造前 stats_cards 的探测顺序。"""
    alt = pd.DataFrame([{"偏差率(%)": 40.0, "_替代料组": "G1"},
                        {"偏差率(%)": 40.0, "_替代料组": ""}])
    assert list(tc.anomaly_mask(alt).astype(bool)) == [False, True]


# ---------------------------------------------------------------- AI 通过率
def test_pass_rate_floor_and_unknown():
    ok = pd.DataFrame({"审核结果": ["合格", "合格", "不合格", ""]})
    assert tc.ai_pass_rate(ok) == pytest.approx(200.0 / 3.0)
    assert tc.ai_pass_rate(pd.DataFrame({"x": [1]})) is None
    assert tc.ai_pass_rate(pd.DataFrame({"审核结果": ["", None]})) is None


# ---------------------------------------------------------------- 落库
def test_save_writes_exactly_the_five_keys(tmp_cfg):
    saved = tc.save_threshold_config(dict(tc.DEFAULTS, alert_dev_rate_pct=12.5))
    on_disk = json.loads(tmp_cfg.read_text(encoding="utf-8"))
    assert set(on_disk) == set(tc.DEFAULTS)
    assert on_disk["alert_dev_rate_pct"] == 12.5
    assert saved["alert_dev_rate_pct"] == 12.5
    assert tc.get_thresholds()["alert_dev_rate_pct"] == 12.5   # 缓存同步刷新


def test_load_merges_partial_and_coerces_types(tmp_cfg):
    tmp_cfg.write_text(json.dumps({"alert_dev_rate_pct": "8", "unknown_key": 1,
                                   "exclude_unfed": 0}), encoding="utf-8")
    cfg = tc.load_threshold_config()
    assert set(cfg) == set(tc.DEFAULTS)          # 未知键不落地，缺键回落默认
    assert cfg["alert_dev_rate_pct"] == 8.0 and isinstance(cfg["alert_dev_rate_pct"], float)
    assert cfg["exclude_unfed"] is False


def test_broken_file_falls_back_but_logs(tmp_cfg, caplog):
    tmp_cfg.write_text("{ this is not json", encoding="utf-8")
    assert tc.load_threshold_config() == tc.DEFAULTS
    assert "阈值配置读取失败" in caplog.text


def test_missing_file_is_not_an_error(tmp_cfg):
    assert tc.load_threshold_config() == tc.DEFAULTS


def test_describe_mentions_the_live_numbers():
    text = tc.describe_thresholds(dict(tc.DEFAULTS, alert_dev_rate_pct=15.0))
    assert "15.00%" in text and "30.00%" in text and "未投料" in text
