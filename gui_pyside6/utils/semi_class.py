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


# ---------------------------------------------------------------------------
# v43.155：分类表加载 + 补列（本模块单一来源，供各看板在缺列时就地补齐）
# ---------------------------------------------------------------------------

def load_semi_classify_map():
    """读取「半成品重分类权威分类表」→ {物料编码(str): 分类名(str)}。

    查找顺序：打包资源 sys._MEIPASS/config/ → 工程内 config/。
    找不到或解析失败返回空 dict（调用方走 400/410 前缀兜底，不影响主流程）。
    与 analysis/analyzer.py 的 _load_semi_classify_map 同源同逻辑，
    抽到这里是为了让 GUI 侧不必 import analysis 包、也不必改 analyzer（红线区）。
    """
    import io
    import json
    import os
    import sys

    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "config", "semi_user_categories.json"))
    _here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(_here, "..", "..", "config", "semi_user_categories.json"))
    for p in candidates:
        if not os.path.exists(p):
            continue
        try:
            with io.open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if isinstance(data, dict):
            return {str(k).strip(): str(v).strip() for k, v in data.items() if k and v}
        # list 格式只存分类名、无「物料号→分类」映射，无法构建，返回空
        return {}
    return {}


def ensure_semi_class_column(df, code_col=None, out_col="半成品重分类"):
    """若 df 缺「半成品重分类」列，就地按 analyzer 同款规则补一列并返回 (df, 是否补了)。

    规则与 analysis/analyzer.py ② + ③ 完全一致（保持口径唯一）：
      1. 命中分类表 config/semi_user_categories.json 的物料编码 → 用表里原值
         （尤其 category_value='包材' 这类必须原样保留，绝不被 400/410 覆盖）；
      2. 表外且物料编码 400 开头 → 「食品成品半成品」；
      3. 表外且物料编码 410 开头 → 「饮料成品半成品」；
      4. 其余留空。

    只填补**空白值**的归属，绝不动已填值。
    df 已有该列时原样返回（不做任何改写）。
    code_col 为 None 时自动挑「物料编码/组件物料号/物料号」第一个存在的列。
    """
    import pandas as pd

    if out_col in df.columns:
        return df, False
    if code_col is None:
        code_col = next((c for c in ("物料编码", "组件物料号", "物料号", "产品物料号码")
                         if c in df.columns), None)
    if code_col is None:
        df[out_col] = pd.Series("", index=df.index, dtype=object)
        return df, True

    codes = df[code_col].fillna("").astype(str).str.strip()
    vals = pd.Series(codes.map(load_semi_classify_map()), index=df.index, dtype=object)
    vals = vals.fillna("")
    blank = vals == ""
    for prefix, cls in PREFIX_TO_SEMI_CLASS:
        hit = blank & codes.str.startswith(prefix, na=False)
        if hit.any():
            vals = vals.mask(hit, cls)
    df[out_col] = vals
    return df, True
