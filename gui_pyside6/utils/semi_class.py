# -*- coding: utf-8 -*-
"""半成品重分类的固定分类清单（全项目单一来源）。

v43.146/v43.147 起，半成品看板 / 替代料看板 / 偏差率预警看板 / 主表筛选面板
四处复选框组共用本清单，不再各自硬编码，也不再按数据 unique_vals 动态生成。

为什么必须固定枚举（不能靠数据动态生成）：
- 看板取的是主表 source_model 当前的 df，主表被左侧筛选面板收窄时
  unique_vals 会缺项，曾导致替代料/半成品看板的分类复选框只剩 2 项、
  其余 4 项凭空消失，用户无从勾选。
- 动态列表每次打开顺序可能不同，勾选体验不稳定。
真需要兼容脏数据时，用「固定清单 + 数据里额外出现的值追加」模式（见各看板
_build_semi_checkboxes），既稳定又不丢数据。

分类名与实际值的对应关系（analysis/analyzer.py ③ 号规则，2026-10-04 实测核对）：
Z004 全 3048 条均 400 开头 → 食品侧 4 类；Z005 全 243 条均 410 开头 → 饮料侧 2 类。
"""

# 食品侧（物料类型 Z004，编码 400 开头）
SEMI_CLASS_FOOD = (
    "食品成品半成品",
    "食品综合组半成品",
    "食品配料中心半成品",
    "食品辅原料",
)

# 饮料侧（物料类型 Z005，编码 410 开头）
SEMI_CLASS_DRINK = (
    "饮料成品半成品",
    "饮料综合组半成品仓",
)

# 默认勾选：只勾成品半成品，仓类 / 辅原料 / 配料中心需手动勾
SEMI_CLASS_DEFAULT = ("食品成品半成品", "饮料成品半成品")

# 400/410 前缀 → 半成品重分类名（无「半成品重分类」列时的兜底）
PREFIX_TO_SEMI_CLASS = (("400", "食品成品半成品"), ("410", "饮料成品半成品"))

# 全部固定分类（顺序：食品 → 饮料）
SEMI_CLASS_ALL = SEMI_CLASS_FOOD + SEMI_CLASS_DRINK

SEMI_CLASS_SET = frozenset(SEMI_CLASS_ALL)


def merge_semi_class_values(unique_vals):
    """返回「固定清单 + 数据里额外分类」的有序去重列表。

    unique_vals 里与固定清单重复的项会被跳过（保持固定清单的位置与顺序），
    空串/None 也会被剔除。各看板建复选框时用这个函数取最终清单。
    """
    out = []
    seen = set()
    for v in SEMI_CLASS_ALL:
        seen.add(v)
        out.append(v)
    for v in unique_vals or ():
        if v is None:
            continue
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out
