# -*- coding: utf-8 -*-
"""导出列模板（模板自定义第一档）—— 只作用于「导出当前表格」。

裴哥 2026-11-14 · 模板自定义第一档

为什么只做当前表格：完整多 Sheet 报告由 analysis.do_analysis_v2 在 analysis 层
硬编码生成 10 个 Sheet，列固定，动它要深入 analysis 层、回归风险大一个量级；
而「导出当前表格」是 GUI 层一行 to_excel 直出，加列选择/顺序/合计行风险低、
几秒出结果。第一档聚焦这条路径（裴哥已确认）。

三件事：
  1. 列模板持久化：用户勾选哪些列、什么顺序，存 config/export_template.json；
  2. 内部字段过滤：data_id / fingerprint / _开头 / 原表行号 等技术列不该进导出；
  3. apply_template(df, include_total)：按模板重排列 + 可选「数值列求和」合计行。

合计行口径：对模板选中列里的**数值列**求和，文本列留空。数值列判定 =
  已知业务数值列名（NUMERIC_HINT）∪ dtype 为数值的列。偏差率(%)这类比率列
  求和无业务意义，排除（只对"量/金额"求和，不对"率"求和）。
"""
import json
import os
from typing import Dict, List

import pandas as pd

# 配置落盘位置（与 column_widths.json 同目录，跟项目其它模板配置一致）
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "export_template.json")

# 内部/技术字段：导出模板默认不列、用户勾选器里也不出现（它们是给程序用的，不是给人看的）
_INTERNAL_COLS = frozenset({
    "data_id", "fingerprint", "原表行号", "_post_audit_changed",
    "_quarantined", "_替代料组", "_read", "_is_alt",
})

# 比率列：求和无业务意义（百分比求和会得出错误结论），合计行跳过
_RATIO_COLS = frozenset({"偏差率(%)", "净偏差率(%)", "偏差率", "净偏差率"})

# 已知业务数值列名（用于 dtype 兜底之外再确认一遍；主表叫"偏差数量/净偏差数量"等）
_NUMERIC_HINT = frozenset({
    "产量", "定额", "实际", "偏差数量", "净偏差数量", "偏差金额",
    "净偏差金额", "材料偏差", "偏差金额(含税)", "数量-实际", "数量-定额",
})


def is_internal(col: str) -> bool:
    """是否内部/技术字段（不进导出勾选器）。"""
    c = str(col)
    return c in _INTERNAL_COLS or c.startswith("_")


def presentable_columns(df: pd.DataFrame) -> List[str]:
    """df 里适合导出的列（按原顺序，过滤内部字段）。给勾选器列候选用。"""
    return [c for c in df.columns if not is_internal(c)]


def is_numeric_col(df: pd.DataFrame, col: str) -> bool:
    """该列是否"可求和"的数值列（比率列除外）。"""
    if col in _RATIO_COLS:
        return False
    if col in _NUMERIC_HINT:
        return True
    try:
        return pd.api.types.is_numeric_dtype(df[col])
    except (KeyError, TypeError):
        return False


def load_template() -> Dict:
    """读导出模板配置。返回 {"order": [...], "include_total": bool}。

    无配置文件 / 字段缺失时返回空 order（= 用 df 原顺序）+ include_total=False。
    """
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            d = json.load(f)
        order = d.get("order") or []
        include_total = bool(d.get("include_total", False))
        return {"order": list(order), "include_total": include_total}
    except (OSError, ValueError):
        return {"order": [], "include_total": False}


def save_template(order: List[str], include_total: bool) -> None:
    """写导出模板配置（临时文件 + 原子替换，防写坏配置）。"""
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    data = {"order": list(order), "include_total": bool(include_total)}
    tmp = _CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _CONFIG_PATH)


def _build_total_row(df: pd.DataFrame, cols: List[str]) -> Dict:
    """构造合计行：数值列求和（保留 2 位小数消除浮点尾差），其它列留空。

    首列写「合计」标签，方便在 Excel 里一眼认出最后一行是汇总。
    """
    total = {c: "" for c in cols}
    if cols:
        total[cols[0]] = "合计"
    for c in cols:
        if is_numeric_col(df, c):
            try:
                s = pd.to_numeric(df[c], errors="coerce")
                val = round(float(s.sum()), 2)
                # 整数和就别带 .0 尾巴，看着干净
                total[c] = int(val) if val == int(val) else val
            except (ValueError, TypeError):
                total[c] = ""
    return total


def apply_template(df: pd.DataFrame, order: List[str], include_total: bool) -> pd.DataFrame:
    """按模板重排列 + 可选合计行，返回新 DataFrame（不改入参）。

    order 为空 → 用 presentable_columns(df) 原顺序（仍过滤内部字段）。
    order 里含 df 已不存在的列（如换了筛选/旧模板）→ 自动跳过，不报错。
    """
    present = presentable_columns(df)
    present_set = set(present)
    # 模板顺序优先，缺失列跳过；再补上模板没提到但 df 里有的可导出列（兜底不丢列）
    cols = [c for c in order if c in present_set]
    cols += [c for c in present if c not in cols]
    out = df[cols].copy()
    if include_total and cols:
        total = _build_total_row(df, cols)
        out = pd.concat([out, pd.DataFrame([total], columns=cols)], ignore_index=True)
    return out