# -*- coding: utf-8 -*-
"""投料为负（实际<0）自动隔离规则回归测试（v43.207，BCD-D）。

条件：neg_actual_required=True 且 实际<0 → 命中自动隔离；实际>=0 / 空值 不命中。
钉死：
  ① 负实际命中、正实际/零实际/空值均不命中；
  ② _normalize_rule 必须保留 neg_actual_required（否则 config 里写的 true 会被吞掉，规则失效）；
  ③ 反证：neg_actual_required=False 且 negative_loss_required=True 时，实际<0 的行不命中
     （证明是 neg_actual_required 在起作用，而非别的字段）。
"""
import pandas as pd
import pytest

from core.auto_quarantine import compute_auto_quarantine_ids, _normalize_rule

pytest.importorskip("pandas")

NEG_RULE = {
    "name": "投料为负(实际<0)",
    "enabled": True,
    "exclude_alt": False,
    "category_required": False,
    "category_value": "",
    "name_keywords": [],
    "negative_loss_required": False,
    "neg_actual_required": True,
}


def _df():
    return pd.DataFrame([
        {"data_id": "A|1|1|1", "是否替代料": "否", "组件物料号": "20001",
         "组件物料描述": "面粉", "数量-实际": -5.0, "数量-定额": 10.0},
        {"data_id": "A|1|1|2", "是否替代料": "否", "组件物料号": "20002",
         "组件物料描述": "糖", "数量-实际": 5.0, "数量-定额": 10.0},
        {"data_id": "A|1|1|3", "是否替代料": "否", "组件物料号": "20003",
         "组件物料描述": "盐", "数量-实际": 0.0, "数量-定额": 10.0},
        {"data_id": "A|1|1|4", "是否替代料": "否", "组件物料号": "20004",
         "组件物料描述": "油", "数量-实际": "", "数量-定额": 10.0},
    ])


def test_neg_feed_hits_negative_only():
    """实际<0 的行必须被投料为负规则命中；正/零/空 均不命中。"""
    df = _df()
    cfg = {"enabled": True, "rules": [dict(NEG_RULE)]}
    hit = compute_auto_quarantine_ids(df, cfg)
    assert "A|1|1|1" in hit, "实际<0 的行必须被投料为负规则命中"
    assert "A|1|1|2" not in hit, "实际>0 不应命中"
    assert "A|1|1|3" not in hit, "实际=0 不应命中"
    assert "A|1|1|4" not in hit, "实际为空不应命中"


def test_neg_actual_field_preserved_by_normalize():
    """_normalize_rule 必须保留 neg_actual_required，否则 config 里写的 true 会被吞掉。"""
    r = _normalize_rule({"name": "x", "neg_actual_required": True})
    assert r["neg_actual_required"] is True, "_normalize_rule 把 neg_actual_required 丢了，规则会失效"


def test_neg_feed_reverse_when_flag_off_but_loss_on():
    """反证：neg_actual_required=False 且 negative_loss_required=True 时，实际<0 的行不应命中。"""
    df = _df()
    r = dict(NEG_RULE)
    r["neg_actual_required"] = False
    r["negative_loss_required"] = True
    cfg = {"enabled": True, "rules": [r]}
    hit = compute_auto_quarantine_ids(df, cfg)
    assert "A|1|1|1" not in hit, "neg_actual_required=False 时负实际不应命中（反证失败）"
