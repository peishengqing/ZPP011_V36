# -*- coding: utf-8 -*-
"""影子预览接生产匹配器（v43.353 第四期B）。

第四期要把规则中心的「命中预览」从「控件里自己算的一套布尔」换成
「生产隔离用的那一套匹配」，否则预览报 428 条、真跑却是别的数 —— 设计稿
改进点 4 点名的就是这件事。重构的前提是**生产结果一个字都不许变**，
所以本文件先钉住重构前的金矿快照，再钉住新 API 与生产同源。

金矿快照怎么来的：4B 动手前，用当时的 `_match_single_rule`（一长串位置参数
那版）对下面这张表和这份 cfg 跑一遍，输出抄死在这里。快照刻意覆盖每条条件的
开/关/缺列分支，语义一旦漂移立刻红。
"""
import copy
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

import core.auto_quarantine as aq
from core.auto_quarantine import (
    DEFAULT_RULE,
    CONFIG_PATH,
    _COL_CANDIDATES,
    compute_auto_quarantine_ids,
    compute_rule_hit_counts,
    describe_rule_hits,
    match_rule_mask,
    _probe_columns,
)

ROWS = [
    {"data_id": "A|1", "是否替代料": "否", "组件物料描述": "彩罐-500ml箱",
     "组件物料类型描述": "包材", "数量-实际": 1150.0, "数量-定额": 1200.0,
     "偏差率(%)": -4.17, "物料编码": "40001234", "车间": "一车间", "备注": "",
     "组件单位": "个", "净偏差金额": -1200.0},
    {"data_id": "A|2", "是否替代料": "是", "组件物料描述": "手包袋",
     "组件物料类型描述": "包材", "数量-实际": 5.0, "数量-定额": 9.0,
     "偏差率(%)": -44.4, "物料编码": "40009999", "车间": "一车间", "备注": "替代",
     "组件单位": "个", "净偏差金额": -80.0},
    {"data_id": "A|3", "组件物料描述": "托盘0.4", "组件物料类型描述": "包材",
     "数量-实际": 9.0, "数量-定额": 9.5, "偏差率(%)": -5.26,
     "物料编码": "41000001", "车间": "二车间", "组件单位": "件", "净偏差金额": -5.0},
    {"data_id": "A|4", "组件物料描述": "塑料袋超投", "组件物料类型描述": "包材",
     "数量-实际": 30.0, "数量-定额": 20.0, "偏差率(%)": 50.0,
     "物料编码": "40000007", "车间": "二车间", "组件单位": "个", "净偏差金额": 60.0},
    # 实际=0（未投料）：负损条件按口径不命中，这条永远只能人工审计
    {"data_id": "A|5", "组件物料描述": "箱未投料", "组件物料类型描述": "包材",
     "数量-实际": 0.0, "数量-定额": 12.0, "偏差率(%)": -100.0,
     "物料编码": "40000008", "车间": "三车间", "组件单位": "个", "净偏差金额": -120.0},
    {"data_id": "A|6", "组件物料描述": "定制彩箱", "组件物料类型描述": "包材",
     "数量-实际": 10.0, "数量-定额": 30.0, "偏差率(%)": -66.67,
     "物料编码": "40000009", "车间": "三车间", "组件单位": "个", "净偏差金额": -200.0},
    {"data_id": "A|7", "组件物料描述": "脱氧剂片", "组件物料类型描述": "原辅料",
     "数量-实际": 5.0, "数量-定额": 10.0, "偏差率(%)": -50.0,
     "物料编码": "30001001", "车间": "四车间", "组件单位": "片",
     "产量单位": "件", "净偏差金额": -30.0},
    {"data_id": "A|8", "组件物料描述": "饮料半成品箱", "组件物料类型描述": "包材",
     "半成品重分类": "饮料半成品", "数量-实际": 3.0, "数量-定额": 9.0,
     "偏差率(%)": -66.67, "物料编码": "40000010", "车间": "一车间",
     "组件单位": "箱", "净偏差金额": -60.0},
    # 半成品重分类为 NaN → 回退物料分类（v43.211）
    {"data_id": "A|9", "组件物料描述": "彩罐NaN分类", "组件物料类型描述": "包材",
     "半成品重分类": None, "数量-实际": 8.0, "数量-定额": 20.0,
     "偏差率(%)": -60.0, "物料编码": "40000011", "车间": "一车间",
     "组件单位": "罐", "净偏差金额": -96.0},
    {"data_id": "A|10", "组件物料描述": "边界偏差量", "组件物料类型描述": "包材",
     "数量-实际": 1.0, "数量-定额": 2.0, "偏差率(%)": -50.0,
     "物料编码": "50000012", "车间": "二车间", "备注": "已核对",
     "组件单位": "个", "净偏差金额": -2.0},
]

GOLDEN_HITS = {
    "A|1": "自动规则[第1条:R1 包材负损默认]",
    "A|2": "自动规则[第4条:R4 偏差率范围]",
    "A|6": "自动规则[第1条:R1 包材负损默认]",
    "A|7": "自动规则[第2条:R2 原辅料+片单位]",
    "A|8": "自动规则[第3条:R3 编码前缀+车间+备注]",
}


def _rule(**kw):
    r = dict(DEFAULT_RULE)
    r.update(kw)
    return r


def _cfg():
    """钉死的规则集：每条对应一块条件分支，其中 R8 停用、R9/R10 撞缺列。"""
    return {"enabled": True, "rules": [
        _rule(name="R1 包材负损默认", name_keywords=["箱", "手包袋"],
              category_value="包材", exclude_alt=True, negative_loss_required=True),
        _rule(name="R2 原辅料+片单位", category_value="原辅料",
              name_keywords=["脱氧剂"], unit_required=True, unit_value="片",
              exclude_alt=True, negative_loss_required=True),
        _rule(name="R3 编码前缀+车间+备注", category_required=False,
              name_keywords=["箱"], mat_code_prefix="40,41", workshop_required=True,
              workshop_value="一车间", remark_mode="none",
              exclude_alt=False, negative_loss_required=False),
        _rule(name="R4 偏差率范围", category_required=False, name_keywords=["袋"],
              dev_rate_required=True, dev_rate_min=-60.0, dev_rate_max=0.0,
              exclude_alt=False, negative_loss_required=False),
        _rule(name="R5 名称排除", category_required=False,
              name_keywords=["彩箱", "定制"], name_exclude_keywords="定制",
              exclude_alt=False, negative_loss_required=False),
        _rule(name="R6 半成品重分类", category_value="饮料半成品，包材",
              name_keywords=["半成品"], exclude_alt=False,
              negative_loss_required=False),
        _rule(name="R7 偏差数量开区间", category_required=False, name_keywords=["边界"],
              dev_qty_required=True, dev_qty_min=0.0, dev_qty_max=1.0,
              exclude_alt=False, negative_loss_required=False),
        _rule(name="R8 停用规则不该命中", enabled=False, category_required=False,
              name_keywords=["彩罐"], exclude_alt=False, negative_loss_required=False),
        _rule(name="R9 缺列条件保守不匹配", category_required=False,
              name_keywords=["箱"], workshop_required=True, workshop_value="九车间",
              exclude_alt=False, negative_loss_required=False),
        _rule(name="R10 偏差率列缺失时保守", category_required=False,
              name_keywords=["脱氧剂"], dev_rate_required=True,
              exclude_alt=False, negative_loss_required=False),
    ]}


@pytest.fixture()
def df():
    return pd.DataFrame(ROWS)


@pytest.fixture()
def cfg():
    return _cfg()


# ------------------------------------------------------------------ 金矿：语义不许漂
def test_golden_snapshot_unchanged(df, cfg):
    assert compute_auto_quarantine_ids(df, cfg) == GOLDEN_HITS


def test_golden_snapshot_survives_repeated_calls(df, cfg):
    """同一份数据反复算，结果与顺序都稳定（规则顺序即优先级，不能被 set 迭代顺序影响）。"""
    first = compute_auto_quarantine_ids(df, cfg)
    for _ in range(3):
        assert compute_auto_quarantine_ids(df, cfg) == first


def test_empty_and_missing_id_still_return_empty(df, cfg):
    assert compute_auto_quarantine_ids(pd.DataFrame(), cfg) == {}
    assert compute_auto_quarantine_ids(pd.DataFrame([{"a": 1}]), cfg) == {}
    assert compute_auto_quarantine_ids(None, cfg) == {}


def test_master_switch_off_isolates_nothing(df, cfg):
    cfg["enabled"] = False
    assert compute_auto_quarantine_ids(df, cfg) == {}


# ------------------------------------------------------------------ 列探测唯一真源
def test_probe_columns_maps_sap_columns(df):
    cols = _probe_columns(df)
    assert cols["actual"] == "数量-实际"
    assert cols["quota"] == "数量-定额"
    assert cols["cat"] == "组件物料类型描述"
    assert cols["semi_class"] == "半成品重分类"
    assert cols["amount"] == "净偏差金额"
    # v43.202 口径：无裸「单位」列时必须落「组件单位」，绝不能落「产量单位」
    assert cols["unit"] == "组件单位"
    assert "产量单位" not in _COL_CANDIDATES["unit"]


def test_probe_columns_missing_is_none(df):
    cols = _probe_columns(df.drop(columns=["备注", "偏差率(%)"]))
    assert cols["remark"] is None
    assert cols["dev_rate"] is None


def test_probe_runs_once_per_batch(df, cfg, monkeypatch):
    """多规则循环共用一次探测结果（旧实现每条规则重探 12 列）。"""
    calls = []
    real = aq._probe_columns

    def counting(d):
        calls.append(1)
        return real(d)

    monkeypatch.setattr(aq, "_probe_columns", counting)
    compute_auto_quarantine_ids(df, cfg)
    assert len(calls) == 1


# ------------------------------------------------------------------ 预览与生产同源
def test_match_rule_mask_equals_production(df, cfg):
    """match_rule_mask 的并集 == 生产隔离结果（预览报多少，真跑就是多少）。"""
    union = set()
    for rule in cfg["rules"]:
        if not rule.get("enabled", True):
            continue
        ids = {str(x) for x in df.loc[match_rule_mask(df, rule), "data_id"]}
        union |= ids
    assert union == set(GOLDEN_HITS)


def test_hit_counts_net_equals_production(df, cfg):
    stats = compute_rule_hit_counts(df, cfg)
    production = compute_auto_quarantine_ids(df, cfg)
    assert sum(s["net_hits"] for s in stats) == len(production)
    # 每条记录的归属规则也必须一致（净命中分配方式同源）
    owner = {}
    for s in stats:
        for _ in range(s["net_hits"]):
            owner.setdefault(s["reason"], 0)
    for reason in production.values():
        assert reason in owner


def test_hit_counts_disabled_rule_shows_potential_but_zero_net(df, cfg):
    stats = {s["index"]: s for s in compute_rule_hit_counts(df, cfg)}
    disabled = stats[8]                      # R8 停用，但名称含「彩罐」的记录确实存在
    assert disabled["enabled"] is False
    assert disabled["hits"] > 0
    assert disabled["net_hits"] == 0


def test_hit_counts_priority_first_rule_wins(df, cfg):
    """靠前规则优先占行：靠后的规则 hits 里含这些行，但 net_hits 不含。

    A|8「饮料半成品箱」同时被 R3（编码前缀+车间）和 R6（半成品重分类）命中，
    列表靠前的 R3 拿走归属；A|1 又被更靠前的 R1 拿走 —— 于是 R3 是
    「命中 2 / 净 1」，R6 是「命中 1 / 净 0」。预览里这两列必须能分别显示。
    """
    stats = {s["index"]: s for s in compute_rule_hit_counts(df, cfg)}
    r3, r6 = stats[3], stats[6]
    assert r3["hits"] == 2 and r3["net_hits"] == 1
    assert r6["hits"] == 1 and r6["net_hits"] == 0
    assert GOLDEN_HITS["A|8"].startswith("自动规则[第3条")
    # 净命中之和永远等于生产结果条数：多规则重叠的行不会被重复计数
    assert sum(s["net_hits"] for s in stats.values()) == len(GOLDEN_HITS)
    assert sum(s["hits"] for s in stats.values()) >= len(GOLDEN_HITS)


def test_hit_counts_master_off(df, cfg):
    cfg["enabled"] = False
    stats = compute_rule_hit_counts(df, cfg)
    assert all(s["net_hits"] == 0 and s["enabled"] is False for s in stats)


def test_hit_counts_on_empty_table(cfg):
    stats = compute_rule_hit_counts(pd.DataFrame(), cfg)
    assert len(stats) == len(cfg["rules"])
    assert all(s["hits"] == 0 and s["net_hits"] == 0 for s in stats)


# ------------------------------------------------------------------ 预览结论条
def test_describe_rule_hits_fields(df, cfg):
    got = describe_rule_hits(df, cfg["rules"][0])     # R1：A|1 + A|6 两条包材负损
    assert got["hits"] == 2
    assert got["total"] == len(df)
    assert abs(got["ratio"] - 2 / 10) < 1e-9
    assert got["amount"] == pytest.approx(-1200 - 200)
    assert got["amount_text"] == "-¥1400"
    assert got["samples"][0].startswith("彩罐-500ml箱（定 1200 / 实 1150）")
    # 「实际=0」的 A|5 名称含「箱」，但负损口径要求真投过料，绝不进预览
    assert not any("未投料" in s for s in got["samples"])


def test_describe_rule_hits_amount_missing_is_dash(df, cfg):
    """没有金额列时必须回 None / 「—」，不能显示 ¥0 假装「金额为 0」。"""
    without = df.drop(columns=["净偏差金额"])
    got = describe_rule_hits(without, cfg["rules"][0])
    assert got["amount"] is None
    assert got["amount_text"] == "—"
    assert got["hits"] == 2                          # 匹配本身不受金额列缺失影响


def test_describe_rule_hits_respects_samples_limit(df, cfg):
    got = describe_rule_hits(df, cfg["rules"][0], samples=1)   # 该规则实命中 2 条
    assert got["hits"] == 2
    assert len(got["samples"]) == 1


def test_describe_rule_hits_empty_table(cfg):
    got = describe_rule_hits(pd.DataFrame(), cfg["rules"][0])
    assert got == {"hits": 0, "total": 0, "ratio": 0.0,
                   "amount": None, "amount_text": "—", "samples": []}


def test_describe_never_zero_actual_rows(df, cfg):
    """「实际=0」按口径永远进不了自动隔离（只能人工审计）—— 预览也必须如实报 0。"""
    rule = _rule(name="只看未投料", category_required=False, name_keywords=["未投料"],
                 negative_loss_required=False, exclude_alt=False)
    got = describe_rule_hits(df, rule)
    assert got["hits"] == 1                          # A|5 匹配到了（不参与负损判断）
    production = compute_auto_quarantine_ids(df, {"enabled": True, "rules": [
        _rule(name="未投料负损", category_required=False, name_keywords=["未投料"],
              exclude_alt=False, negative_loss_required=True)]})
    assert production == {}                          # 一旦要求负损就一条都不许命中


# ------------------------------------------------------------------ 只读红线
def test_preview_apis_are_read_only(df, cfg):
    """预览三件套：不改数据、不改规则对象、不碰配置文件。"""
    snapshot = df.copy(deep=True)
    cfg_before = copy.deepcopy(cfg)
    bytes_before = open(CONFIG_PATH, "rb").read() if os.path.exists(CONFIG_PATH) else None
    stats = compute_rule_hit_counts(df, cfg)
    describe_rule_hits(df, cfg["rules"][0])
    for rule in cfg["rules"]:
        match_rule_mask(df, rule)
    assert df.equals(snapshot)
    assert cfg == cfg_before
    assert len(stats) == len(cfg["rules"])
    if bytes_before is not None:
        assert open(CONFIG_PATH, "rb").read() == bytes_before
