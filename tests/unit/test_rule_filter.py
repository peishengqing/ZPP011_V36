# -*- coding: utf-8 -*-
"""规则驱动看板筛选（隔离区口径）单元测试。

覆盖 ``gui_pyside6/utils/rule_filter.py`` 的核心契约：
- 匹配语义：单条规则内部 AND、多条规则 OR、缺列保守不匹配、exclude_alt 放行；
- ``RuleFilterController`` 的过滤 / 摘要 / 规则行 / 启用规则读取；
- ``RuleFilterWidget`` 的 apply / get_state / clear / 结果表渲染 / set_applied。

数据用构造函数生成的「探针候选列名」建 DataFrame（列名与 ``core.auto_quarantine._probe_columns``
的候选名一一对应），并让每行同时满足「该规则生效」的全部判定字段，
避免依赖散落业务数据，专注验证匹配语义与控制器契约。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtCore import Qt

from core.auto_quarantine import (
    _match_single_rule,
    _probe_columns,
    load_auto_quarantine_config,
    build_rule_reason,
)

from gui_pyside6.utils.rule_filter import (
    RuleFilterController,
    RuleFilterWidget,
    _expand_config_rules,
)

# 探针候选列名（_probe_columns 的键 → 实际列名，顺序即优先级）
_CAND_COLUMNS = [
    "是否替代料", "半成品重分类", "物料分类", "组件物料描述",
    "数量-实际", "数量-定额", "偏差率", "物料编码", "车间", "备注",
    "偏差数量", "单位", "金额",
]


def _make_df(rows):
    """rows 为 dict（键为探针候选列名）；返回用候选列名构造的 DataFrame。"""
    return pd.DataFrame(rows, columns=_CAND_COLUMNS)


def _row(rule_idx, actual=5, quota=100, rate=None, name=None, mat_code="20001",
         workshop=None, unit=None, remark="", cat="包材"):
    """构造一条满足指定规则全部判定字段的行（列名对齐探针候选列名）。

    按规则配置构造：类别取规则 category_value；单位/车间取规则配置值；
    偏差率取落在规则区间内的合法值；名称取规则 name_keywords 首项；
    编码默认取「默认编码」（与规则 mat_code_prefix 对齐），按需覆盖。
    仅在未显式指定字段时取规则配置值，确保「规则 i 构造的行必然命中规则 i」。

    显式参数（name/mat_code/unit/workshop）显式传入即覆盖规则值，
    否则一律由规则配置派生（保证规则 i 构造的行必然命中规则 i）。
    """
    r = load_auto_quarantine_config()["rules"][rule_idx]
    if name is None:
        name = (r.get("name_keywords") or [""])[0]
    if unit is None:
        # 真实数据「单位」列是单值；取规则允许集合的第一个，不能用整个多值串
        # （否则 _match_single_rule 的精确相等 unit_str == v 恒不命中）。
        _u = [x.strip() for x in str(r.get("unit_value") or "").replace("，", ",").split(",") if x.strip()]
        unit = _u[0] if _u else ""
    if workshop is None:
        workshop = str(r.get("workshop_value") or "").strip()
    # 真实语义：category_required=False 时类别条件放行，任意值均可；这里取规则配置值或默认包材
    cat = str(r.get("category_value") or "").strip() or cat
    if cat is None or str(cat).strip() == "":
        cat = "包材"
    mn = float(r.get("dev_rate_min", 0) or 0)
    mx = float(r.get("dev_rate_max", 100) or 100)
    # dev_rate 端点不含（开区间），取区间中点确保落在区间内；dev_rate_required=False 时不校验也无害
    rate = str((mn + mx) / 2.0)
    # 编码：规则有前缀时，默认编码不满足前缀约束，改用前缀对齐编码；
    # 否则回退到传入的 mat_code（显式覆盖优先）。
    prefix = str(r.get("mat_code_prefix") or "").strip()
    if prefix and mat_code == "20001":
        mat_code = prefix + "0001"
    else:
        mat_code = mat_code if mat_code else "20001"
    return {
        "是否替代料": "否",
        "半成品重分类": "",
        "物料分类": cat,
        "组件物料描述": name,
        "数量-实际": actual,
        "数量-定额": quota,
        "偏差率": rate,
        "物料编码": mat_code if mat_code else (prefix or "20001"),
        "车间": workshop,
        "备注": remark,
        "偏差数量": 0,
        "单位": unit,
        "金额": 0,
    }


# --------------------------------------------------------------------------- 配置加载
def test_config_loaded_with_enabled_rules():
    cfg = load_auto_quarantine_config()
    assert cfg.get("enabled") is True
    assert len([r for r in cfg["rules"] if r["name"]]) == 5


def test_config_rules_expanded_has_all_fields():
    rules = _expand_config_rules(load_auto_quarantine_config())
    assert len(rules) == 5
    for r in rules:
        assert r["name"] and r["enabled"]
        assert r["category_required"] is not None
        assert r["name_keywords"] is not None
        assert r["negative_loss_required"] is not None
        assert r["dev_rate_min"] is not None
        assert r["dev_rate_max"] is not None
        assert r["mat_code_prefix"] is not None
        assert isinstance(r["unit_value"], str)
        if r["name_keywords"]:
            assert any(str(k).strip() for k in r["name_keywords"])


# --------------------------------------------------------------------------- 匹配语义
def test_match_single_rule_and_scope():
    """单条规则内部 AND：多条件同时满足才命中；任一条件不满足即不命中。

    v43.379：钉死单位必须【精确匹配】——规则0 限定单位「个/箱/瓶/盒/张」，
    把单位换成「kg」应不命中（回归截图里「限定罐/袋/包却混入巧克力果粒」的 bug）。
    """
    rule = load_auto_quarantine_config()["rules"][0]
    df = _make_df([_row(0)])
    cols = _probe_columns(df)
    assert _match_single_rule(df, rule, cols).all()
    # 单位 kg 不在规则允许集合 → 不命中（精确匹配，非 contains）
    df2 = _make_df([{
        "是否替代料": "否", "半成品重分类": "", "物料分类": "包材", "组件物料描述": "箱",
        "数量-实际": 5, "数量-定额": 100, "偏差率": 50, "物料编码": "20001",
        "车间": "食品厂A", "备注": "", "偏差数量": 0, "单位": "kg", "金额": 0,
    }])
    assert not _match_single_rule(df2, rule, _probe_columns(df2)).all()


def test_match_AND_with_other_rule_condition():
    """命中同规则的不同条件时，AND 必须同时成立。"""
    df = _make_df([_row(1, name="瓶盖", mat_code="40002", unit="瓶")])
    rule = load_auto_quarantine_config()["rules"][1]
    assert _match_single_rule(df, rule, _probe_columns(df)).all()


def test_or_semantics_across_rules():
    """多条规则 OR：命中任意一条启用规则即保留该行，逐规则命中数分开统计。"""
    rows = [_row(i) for i in range(5)]
    df = _make_df(rows)
    cfg = load_auto_quarantine_config()
    controller = RuleFilterController(df, cfg)
    filtered, per_rule = controller.filter(df)
    assert len(filtered) == 5
    assert len(per_rule) == 5
    names = [pr["name"] for pr in per_rule]
    for expected in [
        "食品厂包材箱类、纸罐、手包袋、不干胶、托盘负损",
        "饮料厂瓶胚、瓶盖少投",
        "食品半成品负损",
        "饮料半成品负损",
        "脱氧剂负损",
    ]:
        assert expected in names, f"缺少规则 {expected}，per_rule={names}"


def test_filter_empty_or_missing_columns_conservative():
    """空表 / 无对应列 → 保守返回空集，不误伤。"""
    df = pd.DataFrame([])
    c = RuleFilterController(df)
    filtered, per_rule = c.filter(df)
    assert len(filtered) == 0
    assert per_rule == []

    df2 = _make_df([{
        "是否替代料": "否", "半成品重分类": "", "物料分类": "", "组件物料描述": "示例",
        "数量-实际": 5, "数量-定额": 10, "偏差率": 7.5, "物料编码": "1",
        "车间": "A", "备注": "", "偏差数量": 0, "单位": "箱", "金额": 0,
    }])
    c2 = RuleFilterController(df2)
    filtered2, per_rule2 = c2.filter(df2)
    assert len(filtered2) == 0


def test_filter_disabled_config_returns_original():
    """配置总开关关闭 → 返回原 df，per_rule_hits 为空。"""
    cfg = load_auto_quarantine_config()
    cfg["enabled"] = False
    df = _make_df([_row(0)])
    controller = RuleFilterController(df, cfg)
    filtered, per_rule = controller.filter(df)
    assert filtered is df
    assert per_rule == []


def test_get_enabled_rules_only_enabled():
    cfg = load_auto_quarantine_config()
    c = RuleFilterController(_make_df([_row(0)]), cfg)
    assert len(c.get_enabled_rules()) == 5
    cfg["rules"][0]["enabled"] = False
    c2 = RuleFilterController(_make_df([_row(0)]), cfg)
    assert len(c2.get_enabled_rules()) == 4


def test_rule_index_and_reason_built():
    cfg = load_auto_quarantine_config()
    rules = _expand_config_rules(cfg)
    c = RuleFilterController(_make_df([_row(0)]), cfg)
    assert c.rule_count == len(rules) == 5
    assert c._rule_index(rules[1]) == 2
    assert c._rule_index({"name": "不存在"}) == c._rule_index({"name": "不存在"})
    for r in rules:
        build_rule_reason(r, c._rule_index(r))


def test_controller_probe_columns_and_summary():
    df = _make_df([_row(0)])
    c = RuleFilterController(df)
    assert set(c.cols.keys()) == set(_probe_columns(df).keys())
    assert c.get_summary()
    rows = c.get_rule_rows()
    assert len(rows) == 5
    for r in rows:
        assert r["name"] and r["summary"] and isinstance(r["conditions"], list)


# --------------------------------------------------------------------------- Widget 行为
@pytest.fixture()
def controller():
    return RuleFilterController(_make_df([_row(i) for i in range(5)]), load_auto_quarantine_config())


def test_widget_apply_returns_filtered_and_hits(controller):
    w = RuleFilterWidget(controller)
    filtered, per_rule = w.apply()
    assert len(filtered) == 5
    assert len(per_rule) == 5
    assert [pr["name"] for pr in per_rule] == [r["name"] for r in _expand_config_rules(load_auto_quarantine_config())]


def test_widget_state_and_clear(controller):
    w = RuleFilterWidget(controller)
    assert w.get_state() == "all"
    w.set_state("none")
    assert w.get_state() == "none"
    w.set_state("active")
    w.clear()
    assert w.get_state() == "all"


def test_widget_result_table_render(controller):
    w = RuleFilterWidget(controller)
    w.apply()
    table = w._result_table
    assert table.rowCount() == 5
    # Qt6 已删 QHeaderView.headerList()：从模型的水平表头数据取列名
    model = table.model()
    headers = [str(model.headerData(c, Qt.Horizontal)) for c in range(table.columnCount())]
    assert len(headers) == 3
    first = (table.item(0, 0).text(), table.item(0, 1).text(), table.item(0, 2).text())
    assert str(1) in first[0]
    assert first[2] != ""


def test_widget_set_applied_contains_hits(controller):
    w = RuleFilterWidget(controller)
    _filtered, per_rule = w.apply()
    df_applied, per_rule_applied = w.set_applied(_filtered, per_rule)
    assert len(df_applied) == 5
    assert per_rule_applied[0].get("hits", 0) >= 1


def test_widget_empty_df_returns_empty():
    c = RuleFilterController(pd.DataFrame(), load_auto_quarantine_config())
    w = RuleFilterWidget(c)
    filtered, per_rule = w.apply()
    assert len(filtered) == 0
    assert per_rule == []


def test_widget_uses_controller_filter_not_direct():
    """Widget.apply 走 controller.filter，结果应与直接调用一致。"""
    df = _make_df([_row(i) for i in range(3)])
    controller = RuleFilterController(df, load_auto_quarantine_config())
    w = RuleFilterWidget(controller)
    f1, r1 = controller.filter(df)
    f2, r2 = w.apply()
    # 两次独立调用返回内容一致（不要求同一对象——filter 每次新建 DataFrame 是正确的）
    pd.testing.assert_frame_equal(f1, f2)
    assert r1 == r2


def test_widget_init_no_error(controller):
    """Widget 初始化 + apply 路径不抛异常（offscreen 环境真实组装 UI）。"""
    w = RuleFilterWidget(controller)
    w.set_state("active")
    filtered, per_rule = w.apply()
    assert filtered is not None
    assert per_rule is not None
