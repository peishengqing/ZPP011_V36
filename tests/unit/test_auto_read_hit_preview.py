# -*- coding: utf-8 -*-
"""自动已读接命中预览（v43.355 第四期D）。

规则中心 Tab② 要显示「这条规则在真实主表上命中几条」，就必须复用生产那套匹配
（``core/auto_read_rules.compute_auto_read_mask`` 里的 ``_match_single_rule``），
不能像旧弹窗那样在控件里再拼一套布尔 —— 预览一套、真跑另一套是设计稿 rules.html
改进点 4 点名的问题，4B 已在自动隔离侧解决，本期在自动已读侧做同样的事。

重构的前提是**生产结果一个字都不许变**。GOLDEN 是 4D 动手前用当时的实现
（10 行 × 11 规则 × 5 组全局开关）跑出来的输出，原样抄死在这里：
· 表里刻意放了 实际=0（未投料）、偏差数量=0、偏差数量为 NaN（v43.105 缺失不等于 0）、
  开区间端点值、G/个 这类被「排除单位」盯上的单位、600 前缀编码、
  以及「条件引用了表里不存在的列」那条（保守不匹配）；
· 规则里覆盖 22 个条件类型每一个的 op 分支、多值逗号分隔、名称「不含」取反、
  空条件规则、停用规则、ignore_exclude_unfed / ignore_exclude_units 两个豁免；
· 全局开关跑 5 组：都不排 / 只排未投料 / 只排单位 / 两者都排 / 总开关关。
语义一旦漂移，这个测试立刻红。
"""
import copy
import json
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from core.auto_read_rules import (
    CONDITION_TYPES,
    _ACTUAL_QTY_CANDIDATES,
    _first_col,
    compute_auto_read_mask,
    compute_read_rule_hit_counts,
    describe_read_rule_hits,
    match_read_rule_mask,
)

GOLDEN = json.loads(r"""
{
 "cases": {
  "两者都排": {
   "per_rule": [
    {
     "ids": [
      "B|7"
     ],
     "name": "R1 600 直接已读"
    },
    {
     "ids": [],
     "name": "R2 偏差数量=0"
    },
    {
     "ids": [
      "B|4"
     ],
     "name": "R3 原辅料偏差率区间 且 名称含剂"
    },
    {
     "ids": [
      "B|3"
     ],
     "name": "R4 多值前缀 + 名称排除"
    },
    {
     "ids": [
      "B|4"
     ],
     "name": "R6 编码属于清单"
    },
    {
     "ids": [],
     "name": "R7 实际数量>=100"
    },
    {
     "ids": [],
     "name": "R8 缺列条件（保守不匹配）"
    },
    {
     "ids": [],
     "name": "R9 空条件"
    },
    {
     "ids": [
      "B|4",
      "B|5"
     ],
     "name": "R10 类型等于 + 工厂等于"
    },
    {
     "ids": [
      "B|4",
      "B|5"
     ],
     "name": "R11 名称不含 且 偏差量<=0"
    }
   ],
   "union": [
    "B|3",
    "B|4",
    "B|5",
    "B|7"
   ]
  },
  "全开（不排除）": {
   "per_rule": [
    {
     "ids": [
      "B|7"
     ],
     "name": "R1 600 直接已读"
    },
    {
     "ids": [
      "B|2"
     ],
     "name": "R2 偏差数量=0"
    },
    {
     "ids": [
      "B|4"
     ],
     "name": "R3 原辅料偏差率区间 且 名称含剂"
    },
    {
     "ids": [
      "B|1",
      "B|2",
      "B|3",
      "B|6",
      "B|8"
     ],
     "name": "R4 多值前缀 + 名称排除"
    },
    {
     "ids": [
      "B|4",
      "B|8"
     ],
     "name": "R6 编码属于清单"
    },
    {
     "ids": [
      "B|6"
     ],
     "name": "R7 实际数量>=100"
    },
    {
     "ids": [],
     "name": "R8 缺列条件（保守不匹配）"
    },
    {
     "ids": [],
     "name": "R9 空条件"
    },
    {
     "ids": [
      "B|4",
      "B|5"
     ],
     "name": "R10 类型等于 + 工厂等于"
    },
    {
     "ids": [
      "B|4",
      "B|5",
      "B|6"
     ],
     "name": "R11 名称不含 且 偏差量<=0"
    }
   ],
   "union": [
    "B|1",
    "B|2",
    "B|3",
    "B|4",
    "B|5",
    "B|6",
    "B|7",
    "B|8"
   ]
  },
  "总开关关": {
   "per_rule": [],
   "union": []
  },
  "排除单位 G,个": {
   "per_rule": [
    {
     "ids": [
      "B|7"
     ],
     "name": "R1 600 直接已读"
    },
    {
     "ids": [],
     "name": "R2 偏差数量=0"
    },
    {
     "ids": [
      "B|4"
     ],
     "name": "R3 原辅料偏差率区间 且 名称含剂"
    },
    {
     "ids": [
      "B|3"
     ],
     "name": "R4 多值前缀 + 名称排除"
    },
    {
     "ids": [
      "B|4"
     ],
     "name": "R6 编码属于清单"
    },
    {
     "ids": [],
     "name": "R7 实际数量>=100"
    },
    {
     "ids": [],
     "name": "R8 缺列条件（保守不匹配）"
    },
    {
     "ids": [],
     "name": "R9 空条件"
    },
    {
     "ids": [
      "B|4",
      "B|5"
     ],
     "name": "R10 类型等于 + 工厂等于"
    },
    {
     "ids": [
      "B|4",
      "B|5"
     ],
     "name": "R11 名称不含 且 偏差量<=0"
    }
   ],
   "union": [
    "B|3",
    "B|4",
    "B|5",
    "B|7"
   ]
  },
  "排除未投料": {
   "per_rule": [
    {
     "ids": [
      "B|7"
     ],
     "name": "R1 600 直接已读"
    },
    {
     "ids": [
      "B|2"
     ],
     "name": "R2 偏差数量=0"
    },
    {
     "ids": [
      "B|4"
     ],
     "name": "R3 原辅料偏差率区间 且 名称含剂"
    },
    {
     "ids": [
      "B|2",
      "B|3",
      "B|6",
      "B|8"
     ],
     "name": "R4 多值前缀 + 名称排除"
    },
    {
     "ids": [
      "B|4",
      "B|8"
     ],
     "name": "R6 编码属于清单"
    },
    {
     "ids": [
      "B|6"
     ],
     "name": "R7 实际数量>=100"
    },
    {
     "ids": [],
     "name": "R8 缺列条件（保守不匹配）"
    },
    {
     "ids": [],
     "name": "R9 空条件"
    },
    {
     "ids": [
      "B|4",
      "B|5"
     ],
     "name": "R10 类型等于 + 工厂等于"
    },
    {
     "ids": [
      "B|4",
      "B|5",
      "B|6"
     ],
     "name": "R11 名称不含 且 偏差量<=0"
    }
   ],
   "union": [
    "B|2",
    "B|3",
    "B|4",
    "B|5",
    "B|6",
    "B|7",
    "B|8"
   ]
  }
 },
 "edge": {
  "None": {
   "per_rule_count": 0,
   "union": []
  },
  "无 data_id": {
   "per_rule_count": 0,
   "union": []
  },
  "空表": {
   "per_rule_count": 0,
   "union": []
  },
  "缺偏差数量列": {
   "per_rule_count": 10,
   "union": [
    "B|1",
    "B|2",
    "B|3",
    "B|4",
    "B|5",
    "B|6",
    "B|7",
    "B|8"
   ]
  }
 },
 "per_type": {
  "actual_qty_eq": {
   "params": {
    "value": 9
   },
   "union": [
    "B|2",
    "B|3"
   ]
  },
  "actual_qty_gt": {
   "params": {
    "value": 9
   },
   "union": [
    "B|5",
    "B|6",
    "B|8"
   ]
  },
  "actual_qty_gte": {
   "params": {
    "value": 9
   },
   "union": [
    "B|2",
    "B|3",
    "B|5",
    "B|6",
    "B|8"
   ]
  },
  "actual_qty_lt": {
   "params": {
    "value": 9
   },
   "union": [
    "B|1",
    "B|4",
    "B|7"
   ]
  },
  "actual_qty_lte": {
   "params": {
    "value": 9
   },
   "union": [
    "B|1",
    "B|2",
    "B|3",
    "B|4",
    "B|7"
   ]
  },
  "dev_qty_eq": {
   "params": {
    "value": 0
   },
   "union": [
    "B|2"
   ]
  },
  "dev_qty_gt": {
   "params": {
    "value": 0
   },
   "union": [
    "B|8"
   ]
  },
  "dev_qty_gte": {
   "params": {
    "value": 0
   },
   "union": [
    "B|2",
    "B|8"
   ]
  },
  "dev_qty_lt": {
   "params": {
    "value": 0
   },
   "union": [
    "B|1",
    "B|4",
    "B|5",
    "B|6",
    "B|7"
   ]
  },
  "dev_qty_lte": {
   "params": {
    "value": 0
   },
   "union": [
    "B|1",
    "B|2",
    "B|4",
    "B|5",
    "B|6",
    "B|7"
   ]
  },
  "dev_qty_range": {
   "params": {
    "max": 10,
    "min": -30
   },
   "union": [
    "B|1",
    "B|2",
    "B|4",
    "B|5",
    "B|6"
   ]
  },
  "dev_rate_eq": {
   "params": {
    "value": -50
   },
   "union": [
    "B|4"
   ]
  },
  "dev_rate_gt": {
   "params": {
    "value": -50
   },
   "union": [
    "B|2",
    "B|3",
    "B|5",
    "B|6",
    "B|8"
   ]
  },
  "dev_rate_gte": {
   "params": {
    "value": -50
   },
   "union": [
    "B|2",
    "B|3",
    "B|4",
    "B|5",
    "B|6",
    "B|8"
   ]
  },
  "dev_rate_lt": {
   "params": {
    "value": -50
   },
   "union": [
    "B|1",
    "B|7"
   ]
  },
  "dev_rate_lte": {
   "params": {
    "value": -50
   },
   "union": [
    "B|1",
    "B|4",
    "B|7"
   ]
  },
  "dev_rate_range": {
   "params": {
    "max": -10,
    "min": -100
   },
   "union": [
    "B|4",
    "B|6"
   ]
  },
  "factory_eq": {
   "params": {
    "value": "一车间"
   },
   "union": []
  },
  "mat_code_in": {
   "params": {
    "value": "40000002,30001004"
   },
   "union": [
    "B|2",
    "B|4"
   ]
  },
  "mat_code_prefix": {
   "params": {
    "value": "40"
   },
   "union": [
    "B|1",
    "B|2",
    "B|6",
    "B|8"
   ]
  },
  "mat_name_contains": {
   "params": {
    "value": "箱,袋"
   },
   "union": [
    "B|1",
    "B|2",
    "B|7",
    "B|8"
   ]
  },
  "mat_name_not_contains": {
   "params": {
    "value": "箱"
   },
   "union": [
    "B|2",
    "B|3",
    "B|4",
    "B|5",
    "B|6",
    "B|8"
   ]
  },
  "mat_type_eq": {
   "params": {
    "value": "包材"
   },
   "union": [
    "B|1",
    "B|2",
    "B|3",
    "B|6",
    "B|7",
    "B|8"
   ]
  }
 }
}""")


def _cfg(**kw):
    c = {"enabled": True, "exclude_unfed": False, "exclude_units": False,
         "excluded_units": ""}
    c.update(kw)
    return c


def _rule(name, conds, enabled=True, **kw):
    r = {"name": name, "enabled": enabled, "conditions": conds}
    r.update(kw)
    return r


def _c(t, **params):
    return {"type": t, "params": params}


ROWS = [
    # 实际=0（未投料）：exclude_unfed 开关的靶子
    {"data_id": "B|1", "物料编码": "40000001", "组件物料描述": "彩罐-500ml箱",
     "组件物料类型描述": "包材", "物料分类": "包材", "工厂": "云南达利-饮料厂",
     "数量-实际": 0.0, "数量-定额": 12.0, "偏差数量": -12.0, "偏差率(%)": -100.0,
     "组件单位": "个", "车间": "一车间"},
    {"data_id": "B|2", "物料编码": "40000002", "组件物料描述": "手包袋",
     "组件物料类型描述": "包材", "物料分类": "包材", "工厂": "云南达利-饮料厂",
     "数量-实际": 9.0, "数量-定额": 9.0, "偏差数量": 0.0, "偏差率(%)": 0.0,
     "组件单位": "个", "车间": "一车间"},
    # 偏差数量 NaN：缺失不得当成 0（v43.105）
    {"data_id": "B|3", "物料编码": "41000003", "组件物料描述": "托盘",
     "组件物料类型描述": "包材", "物料分类": "包材", "工厂": "云南达利-饮料厂",
     "数量-实际": 9.0, "数量-定额": 9.5, "偏差数量": None, "偏差率(%)": -5.26,
     "组件单位": "件", "车间": "二车间"},
    {"data_id": "B|4", "物料编码": "30001004", "组件物料描述": "脱氧剂片",
     "组件物料类型描述": "原辅料", "物料分类": "原辅料", "工厂": "云南达利-食品厂",
     "数量-实际": 5.0, "数量-定额": 10.0, "偏差数量": -5.0, "偏差率(%)": -50.0,
     "组件单位": "片", "车间": "四车间"},
    # 偏差率恰为 -10：开区间不含端点
    {"data_id": "B|5", "物料编码": "30001005", "组件物料描述": "柠檬酸",
     "组件物料类型描述": "原辅料", "物料分类": "原辅料", "工厂": "云南达利-食品厂",
     "数量-实际": 18.0, "数量-定额": 20.0, "偏差数量": -2.0, "偏差率(%)": -10.0,
     "组件单位": "kg", "车间": "四车间"},
    # 单位 G：排除单位清单的靶子
    {"data_id": "B|6", "物料编码": "40000006", "组件物料描述": "标签贴纸",
     "组件物料类型描述": "包材", "物料分类": "包材", "工厂": "云南达利-饮料厂",
     "数量-实际": 100.0, "数量-定额": 120.0, "偏差数量": -20.0, "偏差率(%)": -16.67,
     "组件单位": "G", "车间": "三车间"},
    # 600 前缀：那条「永远直接已读」的最高优先级规则
    {"data_id": "B|7", "物料编码": "60000007", "组件物料描述": "600 彩箱",
     "组件物料类型描述": "包材", "物料分类": "包材", "工厂": "云南达利-饮料厂",
     "数量-实际": 0.0, "数量-定额": 30.0, "偏差数量": -30.0, "偏差率(%)": -100.0,
     "组件单位": "箱", "车间": "一车间"},
    {"data_id": "B|8", "物料编码": "40000008", "组件物料描述": "塑料袋大",
     "组件物料类型描述": "包材", "物料分类": "包材", "工厂": "云南达利-食品厂",
     "数量-实际": 30.0, "数量-定额": 20.0, "偏差数量": 10.0, "偏差率(%)": 50.0,
     "组件单位": "个", "车间": "二车间"},
]

RULES = [
    _rule(u"R1 600 直接已读", [_c("mat_code_prefix", value="600")],
          ignore_exclude_unfed=True, ignore_exclude_units=True),
    _rule(u"R2 偏差数量=0", [_c("dev_qty_eq", value=0)]),
    _rule(u"R3 原辅料偏差率区间 且 名称含剂",
          [_c("mat_type_eq", value="原辅料"),
           _c("dev_rate_range", **{"min": -100, "max": -10}),
           _c("mat_name_contains", value=u"剂")]),
    _rule(u"R4 多值前缀 + 名称排除",
          [_c("mat_code_prefix", value="40,41"),
           _c("mat_name_not_contains", value=u"彩箱,定制")]),
    _rule(u"R5 停用那条", [_c("actual_qty_eq", value=0)], enabled=False),
    _rule(u"R6 编码属于清单", [_c("mat_code_in", value="30001004,40000008")]),
    _rule(u"R7 实际数量>=100", [_c("actual_qty_gte", value=100)]),
    # 条件引用了表里不存在的列 → 整条保守不匹配
    _rule(u"R8 缺列条件（保守不匹配）",
          [_c("factory_eq", value=u"五车间"), _c("dev_qty_lt", value=0)]),
    _rule(u"R9 空条件", []),
    _rule(u"R10 类型等于 + 工厂等于",
          [_c("mat_type_eq", value=u"原辅料"),
           _c("factory_eq", value=u"云南达利-食品厂")]),
    _rule(u"R11 名称不含 且 偏差量<=0",
          [_c("mat_name_not_contains", value=u"箱,袋"), _c("dev_qty_lte", value=0)]),
]


def _df():
    return pd.DataFrame(ROWS)


# ---------------------------------------------------------------- 金矿快照
def test_golden_union_and_per_rule_are_unchanged():
    df = _df()
    for label, want in GOLDEN["cases"].items():
        globals_ = {
            u"全开（不排除）": _cfg(),
            u"排除未投料": _cfg(exclude_unfed=True),
            u"排除单位 G,个": _cfg(exclude_units=True, excluded_units="G,个"),
            u"两者都排": _cfg(exclude_unfed=True, exclude_units=True, excluded_units=u"G，个"),
            u"总开关关": _cfg(enabled=False, exclude_unfed=True, exclude_units=True,
                            excluded_units="G"),
        }[label]
        cfg = dict(globals_)
        cfg["rules"] = copy.deepcopy(RULES)
        union, per_rule = compute_auto_read_mask(df, cfg)
        got_union = sorted(str(u) for u in df.loc[union, "data_id"])
        got = [{"name": r.get("name"), "ids": sorted(str(u) for u in df.loc[m, "data_id"])}
               for r, m in per_rule]
        assert got_union == want["union"], "%s 的并集变了：%s != %s" % (label, got_union, want["union"])
        assert got == want["per_rule"], "%s 的逐条命中变了" % label


def test_golden_edge_cases_are_unchanged():
    df = _df()
    cfg = _cfg(rules=copy.deepcopy(RULES))
    for name, frame in ((u"空表", pd.DataFrame()), (u"无 data_id", df.drop(columns=["data_id"])),
                        (u"None", None)):
        union, per_rule = compute_auto_read_mask(frame, cfg)
        assert list(per_rule) == [] and len(union) == 0, name
    # 缺「偏差数量」列：只有引用它的规则整条失效，其余照旧（保守不匹配，不牵连别人）
    union, per_rule = compute_auto_read_mask(df.drop(columns=["偏差数量"]), cfg)
    assert sorted(str(u) for u in df.loc[union.reindex(df.index, fill_value=False), "data_id"]) \
        == GOLDEN["edge"][u"缺偏差数量列"]["union"]
    assert len(per_rule) == GOLDEN["edge"][u"缺偏差数量列"]["per_rule_count"]


def test_golden_every_condition_type_is_unchanged():
    df = _df()
    for t, want in GOLDEN["per_type"].items():
        cfg = _cfg(rules=[_rule(t, [_c(t, **want["params"])])])
        union, _ = compute_auto_read_mask(df, cfg)
        assert sorted(str(u) for u in df.loc[union, "data_id"]) == want["union"], t


# ---------------------------------------------------------------- 新 API 与生产同源
def test_match_read_rule_mask_ignores_enabled_and_global_switches():
    """停用规则也要能回答「若启用会命中多少」，全局排除开关也不掺进来。"""
    df = _df()
    rule = _rule(u"停用那条", [_c("actual_qty_eq", value=0)], enabled=False)
    assert sorted(str(u) for u in df.loc[match_read_rule_mask(df, rule), "data_id"]) == ["B|1", "B|7"]
    # 生产口径下总开关一关就全不匹配
    union, per_rule = compute_auto_read_mask(df, _cfg(enabled=False, rules=[rule]))
    assert union.any() is not True and per_rule == []


def test_global_exclusions_are_applied_unless_the_rule_waives_them():
    df = _df()
    rule = _rule(u"R2 偏差数量=0", [_c("dev_qty_eq", value=0)])
    plain = sorted(str(u) for u in df.loc[match_read_rule_mask(df, rule), "data_id"])
    assert plain == ["B|2"]
    cfg = _cfg(exclude_unfed=True, exclude_units=True, excluded_units=u"个",
               rules=[rule, _rule(u"R1 600", [_c("mat_code_prefix", value="600")],
                                  ignore_exclude_unfed=True, ignore_exclude_units=True)])
    union, per_rule = compute_auto_read_mask(df, cfg)
    # R2 命中行单位是「个」→ 被排除单位挡掉；R1 有豁免 → 实际=0 也照样已读
    assert sorted(str(u) for u in df.loc[union, "data_id"]) == ["B|7"]
    # per_rule 是**每条启用规则**的掩码，被全局排除挡空的那条也照样在里面（生产契约
    # 一直如此，调用方靠掩码本身是否为空判断），所以这里是两条而不是只留命中的 R1
    assert [r["name"] for r, _m in per_rule] == [u"R2 偏差数量=0", u"R1 600"]
    assert not per_rule[0][1].any()
    assert sorted(str(u) for u in df.loc[per_rule[1][1], "data_id"]) == ["B|7"]


def test_hit_counts_report_hits_and_already_covered():
    df = _df()
    cfg = _cfg(rules=copy.deepcopy(RULES))
    stats = compute_read_rule_hit_counts(df, cfg)
    assert [s["index"] for s in stats] == list(range(1, len(RULES) + 1))
    by_name = {s["name"]: s for s in stats}
    # R11 命中 3 条，但这 3 条更靠前的规则也覆盖到了 —— 自动已读是并集，被覆盖不
    # 影响结果，只是让用户看清「这条其实没在独自起作用」
    assert by_name[u"R11 名称不含 且 偏差量<=0"]["hits"] == 3
    assert by_name[u"R11 名称不含 且 偏差量<=0"]["net_hits"] == 0
    assert by_name[u"R5 停用那条"]["enabled"] is False
    # 停用规则也给 hits（含义是「若启用会命中多少」），net_hits 恒为 0
    assert by_name[u"R5 停用那条"]["hits"] == 2
    assert by_name[u"R5 停用那条"]["net_hits"] == 0
    assert by_name[u"R9 空条件"]["hits"] == 0


def test_hit_counts_zero_when_master_off():
    df = _df()
    stats = compute_read_rule_hit_counts(df, _cfg(enabled=False, rules=copy.deepcopy(RULES)))
    assert all(s["hits"] == 0 and s["net_hits"] == 0 for s in stats)


def test_describe_reports_the_unfed_count_not_hidden():
    """人工审计红线：命中里有多少是「实际=0（未投料）」必须说出来。"""
    df = _df()
    rule = _rule(u"R1 600", [_c("mat_code_prefix", value="600")],
                 ignore_exclude_unfed=True, ignore_exclude_units=True)
    got = describe_read_rule_hits(df, rule)
    assert got["hits"] == 1 and got["total"] == 8
    assert got["unfed_hits"] == 1          # B|7 实际=0，被这条豁免直接吞进已读
    assert got["samples"] and u"600" in got["samples"][0]
    assert got["ratio"] == pytest.approx(1 / 8.0)
    # 不豁免时，全局排除未投料会把它挡掉 → 预览必须跟着全局口径，并说清是谁挡的
    waived = describe_read_rule_hits(df, _rule(u"普通", [_c("mat_code_prefix", value="600")]),
                                     globals_=_cfg(exclude_unfed=True))
    assert waived["hits"] == 0 and waived["raw_hits"] == 1
    assert waived["blocked_by"] == [u"排除未投料（实际=0）"]
    assert describe_read_rule_hits(df, rule, globals_=_cfg(exclude_unfed=True))["hits"] == 1


def test_describe_blocked_by_names_the_global_switch():
    df = _df()
    rule = _rule(u"R2 偏差数量=0", [_c("dev_qty_eq", value=0)])
    got = describe_read_rule_hits(df, rule, globals_=_cfg(exclude_units=True, excluded_units=u"个"))
    assert got["hits"] == 0
    assert u"排除单位" in got["blocked_by"][0]


def test_preview_apis_are_read_only():
    df = _df()
    cfg = _cfg(rules=copy.deepcopy(RULES))
    cfg_before = copy.deepcopy(cfg)
    df_before = df.copy(deep=True)
    compute_read_rule_hit_counts(df, cfg)
    for r in cfg["rules"]:
        describe_read_rule_hits(df, r, globals_=cfg)
        match_read_rule_mask(df, r)
    compute_auto_read_mask(df, cfg)
    assert cfg == cfg_before
    assert df.equals(df_before)
    assert cfg["rules"] == cfg_before["rules"]


def test_actual_zero_rows_are_never_implied_handled():
    """「实际=0」在自动已读侧默认是被读掉的（除非勾了排除）—— 预览不许粉饰。"""
    df = _df()
    rule = _rule(u"全部", [_c("dev_qty_lte", value=0)])
    got = describe_read_rule_hits(df, rule)
    assert got["unfed_hits"] == 2 and got["hits"] == 6
    assert u"实际=0" in got["unfed_text"]


def test_column_candidates_stay_shared():
    """新 API 必须走生产同一份候选列，不许另抄一份。"""
    df = _df()
    assert _first_col(df, _ACTUAL_QTY_CANDIDATES) == u"数量-实际"
    rule = _rule(u"R1", [_c("mat_code_prefix", value="600")])
    ids = sorted(str(u) for u in df.loc[match_read_rule_mask(df, rule), "data_id"])
    assert ids == ["B|7"]
    assert set(CONDITION_TYPES) >= {"dev_qty_eq", "mat_type_eq", "factory_eq"}
