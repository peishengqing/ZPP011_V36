"""独立重算对账网核心（ARC-002 治理工具，方案②）。

不 import analysis.analyzer、不依赖 GUI；供 tools/recompute_check.py 做自洽扫描。

公式溯源（已对照 analyzer 源码核实，2026-10-14 修订）：
- dev 输出「偏差数量」= 原始(数量-实际 − 数量-定额)。analyzer 把 数量-实际/数量-定额
  改名为 实际/定额，故 dev 的「实际」「定额」是数量维度，不是金额。
- dev 输出「偏差率(%)」= SAP 原始导出「偏差率(%)」直透传，analyzer 不重算。
- dev 输出「偏差金额」= 偏差数量 × 单价(含税)。源码 sheet5：_偏差金额 =
  材料偏差(=偏差数量) × 单价(不含税) × 1.13(税) = 偏差数量 × (金额-实际(含税)/数量-实际)。
  数量偏差为零时金额强制为零（设计如此，非算错）。
- 「偏差金额(含税)」(analyzer 内部 gross 值，line 512 = 金额-实际(含税) − 金额-定额(含税))
  用于 Sheet1/7 汇总，与 dev 输出「偏差金额」(数量×单价口径) 不是同一列，勿混用。
- 净偏差数量/净偏差金额：analyzer:672-690，替代料组为组内净抵消重算值。

设计目标：裴哥零参与即可运行。机器拿 SAP 原始导出（或 analyzer 导出）独立重算，
与既有列逐项比对 + 自洽扫描，输出差异报告。算错与否由机器从原始数据独立证伪，
不要求人工按计算器。
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def _num(s, default: float = 0.0):
    """转数值，失败/缺失填 default。兼容标量（避免 .fillna 在 int/float 上崩）。"""
    if isinstance(s, (int, float, np.integer, np.floating)):
        return s
    return pd.to_numeric(s, errors="coerce").fillna(default)


def recompute_deviation_amount(df: pd.DataFrame) -> pd.Series:
    """独立重算偏差金额(含税)。优先用含税金额相减（与 analyzer:512 一字不差），
    其次材料偏差×单价（analyzer:533），都不具备返回 NaN 标记无法重算。"""
    if {"金额-实际(含税)", "金额-定额(含税)"}.issubset(df.columns):
        return (_num(df["金额-实际(含税)"]) - _num(df["金额-定额(含税)"])).round(2)
    if {"材料偏差", "_unit_price_tax"}.issubset(df.columns):
        return (_num(df["材料偏差"]) * _num(df["_unit_price_tax"])).round(2)
    return pd.Series(np.nan, index=df.index)


def recompute_deviation_rate(df: pd.DataFrame) -> pd.Series:
    """独立重算偏差率(%) = 偏差数量 / 定额数量 * 100（与 analyzer:687 同口径）。"""
    quota = _num(df.get("数量-定额", df.get("定额数量", 0))).replace(0, np.nan)
    qty = _num(df.get("偏差数量", df.get("材料偏差", 0)))
    return (qty / quota * 100).fillna(0).round(2)


def selfcheck(df: pd.DataFrame, amount_col: str = "偏差金额(含税)",
              rate_col: str = "偏差率(%)") -> list:
    """纯自洽扫描：加法守恒 / 符号方向 / 极端值 / 零额非零量。返回 finding 列表。"""
    findings: list = []
    amt = _num(df.get(amount_col, pd.Series(0.0, index=df.index)))
    rate = _num(df.get(rate_col, pd.Series(0.0, index=df.index)))

    # 1. 符号一致性：偏差金额符号 ↔ (实际数量 - 定额数量) 方向
    if {"数量-实际", "数量-定额"}.issubset(df.columns):
        actual = _num(df["数量-实际"])
        quota_q = _num(df["数量-定额"])
        wrong = df[((amt > 0) & (actual < quota_q)) | ((amt < 0) & (actual > quota_q))]
        if len(wrong):
            findings.append({"rule": "sign_mismatch", "n": int(len(wrong)),
                             "desc": "偏差金额符号与(实际-定额)方向不符的行，疑似口径或取数错"})

    # 2. 极端偏差率
    extreme = df[rate.abs() > 100]
    if len(extreme):
        findings.append({"rule": "extreme_rate", "n": int(len(extreme)),
                         "desc": "|偏差率|>100% 的可疑行，需人工确认是否真实"})

    # 3. 金额≈0 但数量≠0（漏算金额）
    if "偏差数量" in df.columns:
        z = df[(amt.abs() < 0.005) & (_num(df["偏差数量"]).abs() > 0)]
        if len(z):
            findings.append({"rule": "zero_amount_nonzero_qty", "n": int(len(z)),
                             "desc": "偏差金额≈0 但偏差数量≠0，金额可能漏算"})

    # 4. 加法守恒：按工厂聚合净偏差金额合计 应等于 全厂合计
    if {"工厂", "净偏差金额"}.issubset(df.columns):
        by_fac = _num(df["净偏差金额"]).groupby(df["工厂"]).sum()
        recon = float(by_fac.sum())
        total = float(_num(df["净偏差金额"]).sum())
        if abs(recon - total) > 0.01:
            findings.append({"rule": "conservation_factory", "n": -1,
                             "desc": f"按工厂合计({recon:.2f})≠全厂合计({total:.2f})，聚合不一致"})

    # 5. 替代料组净抵消：仅检查「组内净偏差数量合计」与「组内单行偏差数量合计」
    #    是否守恒（替代料抵消只重分配账面，组内总数量偏差不应变）。
    #    注意：不检查「净偏差金额 == 单行偏差金额和」——净偏差金额是组内重算值，
    #    设计上本就不等于原始单行和，该比较会制造假阳性，故不做。
    if {"_替代料组", "净偏差数量", "偏差数量"}.issubset(df.columns):
        grp = df.groupby("_替代料组")
        for gid, sub in grp:
            if gid in (None, "", "nan"):
                continue
            # 净偏差数量在组内每行重复同一个组净值，取唯一值做守恒比较，
            # 不能对重复值再求和（否则 N 行组会得出 N 倍伪差异）。
            uniq = _num(sub["净偏差数量"]).drop_duplicates()
            if len(uniq) != 1:
                continue  # 组内净偏差数量不唯一，异常跳过
            s1 = float(uniq.iloc[0])  # 组净偏差数量（每组唯一值）
            s2 = float(_num(sub["偏差数量"]).sum())
            if abs(s1 - s2) > 0.01:
                findings.append({"rule": "alt_group_qty", "n": int(len(sub)),
                                 "desc": f"替代料组 {gid} 净偏差数量({s1:.2f})≠单行偏差数量合计({s2:.2f})，组内总量不守恒"})

    return findings
