# -*- coding: utf-8 -*-
"""评分卡「为什么分低」证据解释层（纯逻辑，无 PyQt，可 offscreen 单测）。

承接 v43.310 方案 A：不改 core.scorecard.compute_scorecard（守住红线区零改动），
另建一层把三个维度的笼统结论落到 Top-N 具体证据：

  备注覆盖率 → 哪些车间/物料的偏差行缺备注（按偏差行聚合，排除无偏差噪声）
  归因漂移率 → 哪些物料被反复改「备注原因」（读 deviation_history field='备注原因'）
  替代料长链 → 具体是哪些物料编码构成 >1 组的长链（读 alt_pairs.json）

设计原则：
  - 只读不改：纯查询 + 聚合，不写任何表、不改配置。
  - DB 路径走 core.read_status.DB_PATH（运行时取），便于单测 patch 隔离库。
  - 容错：任一维度数据缺失返回空列表，不抛异常（best-effort）。
"""
import os
import json
import sqlite3
from collections import defaultdict
from typing import Dict, List, Optional

from core import read_status as rs


def _has_remark(v) -> bool:
    """备注原因是否非空（兼容 NaN/None/空白）。"""
    if v is None:
        return False
    s = str(v).strip()
    return s not in ("", "nan", "None")


def _resolve_col(df, candidates: List[str]) -> Optional[str]:
    """按候选名顺序找第一个存在的列。"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ---------------------------------------------------------------------------
# 维度 1：备注缺失（按车间 / 物料聚合 Top-N）
# ---------------------------------------------------------------------------
def _missing_remark_top(main_df, top_n: int = 5) -> Dict:
    """在「有偏差」的行里找缺备注的，按车间 / 物料聚合 Top-N。

    只统计真正偏差行（|偏差率| 或 |偏差金额| 非零），避免把无偏差行也算进
    「缺备注」噪声里。返回 {total_missing, by_workshop, by_material}。
    """
    out = {"total_missing": 0, "by_workshop": [], "by_material": []}
    if main_df is None or len(main_df) == 0 or "备注原因" not in main_df.columns:
        return out

    df = main_df
    # 偏差行判定：优先偏差率列，其次偏差金额列
    dev_col = _resolve_col(df, ["偏差率", "偏差率%", "偏差率(%)", "偏差金额(含税)", "偏差金额"])
    if dev_col is not None:
        import pandas as pd
        dev_num = pd.to_numeric(df[dev_col], errors="coerce").fillna(0.0)
        is_dev = dev_num.abs() > 1e-9
    else:
        is_dev = None  # 无法判定偏差 → 退化为全量行

    remark = df["备注原因"]
    missing_mask = ~remark.apply(_has_remark)
    if is_dev is not None:
        missing_mask = missing_mask & is_dev

    sub = df[missing_mask]
    out["total_missing"] = int(len(sub))
    if out["total_missing"] == 0:
        return out

    # 按车间聚合
    ws_col = _resolve_col(df, ["车间", "生产管理员描述"])
    if ws_col is not None:
        vc = sub[ws_col].astype(str).str.strip().replace("", "未知").value_counts()
        out["by_workshop"] = [(str(k), int(v)) for k, v in vc.head(top_n).items()]

    # 按物料聚合（编码 + 描述）
    code_col = _resolve_col(df, ["物料编码", "组件物料号"])
    desc_col = _resolve_col(df, ["物料描述", "组件物料描述"])
    if code_col is not None:
        g = sub.groupby(sub[code_col].astype(str))
        rows = []
        for code, grp in g:
            desc = ""
            if desc_col is not None:
                d = grp[desc_col].dropna().astype(str)
                desc = d.iloc[0] if len(d) else ""
            rows.append((code, desc, int(len(grp))))
        rows.sort(key=lambda r: r[2], reverse=True)
        out["by_material"] = rows[:top_n]

    return out


# ---------------------------------------------------------------------------
# 维度 2：归因漂移（反复改「备注原因」的物料 Top-N）
# ---------------------------------------------------------------------------
def _drift_top(top_n: int = 5) -> List[Dict]:
    """从 deviation_history 找被反复改「备注原因」的物料，按改动次数降序 Top-N。

    物料编码 = data_id 末段。返回 [{material, changes}]。
    """
    out: List[Dict] = []
    try:
        conn = sqlite3.connect(rs.DB_PATH)
        try:
            rows = conn.execute(
                "select data_id, count(*) from deviation_history "
                "where data_id<>'X' and data_id is not null and field='备注原因' "
                "group by data_id order by count(*) desc"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return out

    per_mat = defaultdict(int)
    for data_id, cnt in rows:
        mat = str(data_id).split("|")[-1] if data_id else ""
        if mat:
            per_mat[mat] += int(cnt)
    ranked = sorted(per_mat.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [{"material": m, "changes": c} for m, c in ranked]


# ---------------------------------------------------------------------------
# 维度 3：替代料长链（具体物料编码）
# ---------------------------------------------------------------------------
def _alt_chain_detail(top_n: int = 10) -> Dict:
    """读 alt_pairs.json，列出构成 >1 组长链的具体物料编码及所在组数。

    返回 {chains_count, total_materials, details:[{code, groups}]}。
    """
    out = {"chains_count": 0, "total_materials": 0, "details": []}
    cfg = os.path.join(os.environ.get("APPDATA", ""), "ZPP011", "config", "alt_pairs.json")
    try:
        if not os.path.exists(cfg):
            return out
        with open(cfg, encoding="utf-8") as f:
            d = json.load(f)
        cnt = defaultdict(int)
        for grp in d:
            if not isinstance(grp, list):
                continue
            for s in grp:
                if not isinstance(s, (list, tuple)) or len(s) < 3:
                    continue
                cnt[str(s[1])] += 1
        out["total_materials"] = len(cnt)
        chains = {c: n for c, n in cnt.items() if n > 1}
        out["chains_count"] = len(chains)
        ranked = sorted(chains.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        out["details"] = [{"code": c, "groups": n} for c, n in ranked]
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# 对外主函数
# ---------------------------------------------------------------------------
def build_explanation(main_df) -> Dict:
    """组装评分卡三维度「为什么分低」的 Top-N 证据解释。

    返回 {missing_remark, drift_top, alt_chain}，各维度数据缺失时为空，不抛异常。
    """
    return {
        "missing_remark": _missing_remark_top(main_df),
        "drift_top": _drift_top(),
        "alt_chain": _alt_chain_detail(),
    }
