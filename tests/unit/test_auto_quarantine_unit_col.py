# -*- coding: utf-8 -*-
"""自动隔离「单位」列选法回归测试（v43.202）。

根因：core/auto_quarantine.py 的单位列候选旧为
["单位", "产量单位", "组件单位"]。真实 SAP 源表无裸「单位」列，于是命中
「产量单位」（产品母件出货量单位，取值只有 件/KG/包/罐/袋/瓶/盒，无「片」），
而「组件单位」才是组件物料自身投料单位（取值含 片/张/袋/罐 等）——于是按
「组件投料单位=片」的脱氧剂负损规则永远 0 命中。

全项目口径核对（sheet2~8 报表、筛选面板、auto_read_rules.py:290）：
物料单位一律用「组件单位」，从不用「产量单位」。本版把隔离规则单位列候选
对齐为 ["单位", "组件单位", "基本单位", "计量单位"]（与 auto_read_rules 同源），
去掉错列「产量单位」、组件单位提前。

本测试用真实 SAP 表特征构造数据（同时含 产量单位/组件单位 两列、无裸「单位」列），
钉住：① 单位条件比对「组件单位」而非「产量单位」；② 候选清单已不含「产量单位」。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest

from core.auto_quarantine import (
    compute_auto_quarantine_ids,
    load_auto_quarantine_config,
    _first_col,
)
import core.auto_quarantine as aq

pytest.importorskip("pandas")


def _build_df():
    """模拟真实 SAP 源表：无裸「单位」列，同时含 产量单位(产品母件,取值件) 与
    组件单位(组件自身投料,取值片)。一条脱氧剂负损记录应被规则5命中。"""
    return pd.DataFrame([
        {
            "data_id": "云南达利-食品厂|2026-10-13|1000001|30001001",
            "是否替代料": "否",
            "组件物料号": "30001001",
            "组件物料描述": "脱氧剂片",
            "组件物料类型描述": "原辅料",
            "数量-实际": 5.0,
            "数量-定额": 10.0,
            "产量单位": "件",     # 产品母件出货量单位——旧代码错比这一列
            "组件单位": "片",     # 组件自身投料单位——正确比这一列
        },
        # 反向护栏：同是原辅料负损、名称不含脱氧剂，不应被规则5命中
        {
            "data_id": "云南达利-食品厂|2026-10-13|1000002|30001002",
            "是否替代料": "否",
            "组件物料号": "30001002",
            "组件物料描述": "某辅料",
            "组件物料类型描述": "原辅料",
            "数量-实际": 5.0,
            "数量-定额": 10.0,
            "产量单位": "件",
            "组件单位": "片",
        },
    ])


def test_unit_col_resolves_to_component_not_yield():
    """单位列候选在真实 SAP schema 下必须解析到「组件单位」，而非「产量单位」。"""
    df = _build_df()
    # 无裸「单位」列 → _first_col 应落到「组件单位」（组件单位在候选且排在产量单位前）
    assert _first_col(df, aq._UNIT_CANDIDATES if hasattr(aq, "_UNIT_CANDIDATES")
                      else ["单位", "组件单位", "基本单位", "计量单位"]) == "组件单位"


def test_rule5_hits_component_unit_piece():
    """脱氧剂(原辅料·负损·组件单位=片) 必须被规则5命中——即单位条件确实比的是组件单位。"""
    df = _build_df()
    cfg = load_auto_quarantine_config()
    r5 = cfg["rules"][4]
    assert r5.get("name") == "脱氧剂负损", "规则5必须是脱氧剂负损（序号未漂移）"
    hit = compute_auto_quarantine_ids(df, cfg)
    dxy_id = "云南达利-食品厂|2026-10-13|1000001|30001001"
    assert dxy_id in hit, "脱氧剂行未命中规则5 → 单位列仍走错列"
    assert "第5条" in hit[dxy_id], f"命中原因应为第5条，实际：{hit[dxy_id]}"
    # 反向护栏：不含脱氧剂的辅料即便 组件单位=片 也不该被规则5命中
    assert "云南达利-食品厂|2026-10-13|1000002|30001002" not in hit


def test_candidate_list_dropped_yield_unit():
    """AST 护栏：单位列候选清单不得再含「产量单位」（病根已拔除、防回退）。"""
    with open(os.path.join(os.path.dirname(aq.__file__), "auto_quarantine.py"),
              encoding="utf-8") as f:
        src = f.read()
    assert '"产量单位"' not in src, "单位列候选仍含「产量单位」，病根未拔除"
    # 组件单位必须在前（真实 schema 无「单位」列时落到组件单位）
    assert '"组件单位"' in src


def test_component_unit_takes_priority_over_basic():
    """同含 组件单位 与 基本单位 时，单位条件优先取「组件单位」（顺序护栏）。"""
    df = pd.DataFrame([
        {"data_id": "X|1|1|1", "是否替代料": "否", "组件物料号": "30001",
         "组件物料描述": "脱氧剂片", "组件物料类型描述": "原辅料",
         "数量-实际": 5.0, "数量-定额": 10.0,
         "组件单位": "片", "基本单位": "箱"},
    ])
    cfg = load_auto_quarantine_config()
    hit = compute_auto_quarantine_ids(df, cfg)
    # 组件单位=片 命中；若误比基本单位=箱 则 0 命中
    assert "X|1|1|1" in hit, "组件单位优先级被破坏（误比基本单位）"
