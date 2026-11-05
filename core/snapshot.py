# -*- coding: utf-8 -*-
"""D1 按需快照：本地只读留痕，系统不主动外发（不推送/不发邮件/不弹外部通知）。

未完结/完结定义（2026-11-06 裴哥拍板）：
  未完结(data_id) = (is_read == 0)
                    OR (∈ quarantine_records AND restored_at IS NULL AND exempted == 0)
  流程订单 = (工厂, 订单日期, 流程订单) 集合
  未完结订单数 = 满足「未完结」的流程订单个数
  未审核差额 = 这些未完结 data_id 的 偏差数量合计 + 偏差金额(含税)合计（豁免的排除）

本模块为纯逻辑（仅依赖 pandas / sqlite3 / 标准库），不 import PyQt，
便于 offscreen 独立单测。GUI 侧按钮/弹窗在 gui_pyside6/utils/snapshot_action.py。
"""
import os
import json
import sqlite3
import datetime
from typing import Dict, Optional

import pandas as pd

from core.read_status import load_read_status
from core.quarantine_manager import get_quarantine_records


def _appdata(*sub):
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    return os.path.join(base, *sub)


SNAPSHOT_ROOT = _appdata("ZPP011", "snapshots")
HISTORY_DB = _appdata("ZPP011", "history.sqlite")

_QTY_CANDIDATES = ["偏差数量", "净偏差数量", "数量"]
_AMT_CANDIDATES = ["偏差金额(含税)", "净偏差金额", "偏差金额"]
_GROUP_COLS = [("工厂", "订单日期", "流程订单")]


def _resolve_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _safe_float(v):
    try:
        if v is None:
            return 0.0
        f = float(v)
        if pd.isna(f):
            return 0.0
        return f
    except (ValueError, TypeError):
        return 0.0


def compute_unfinished(main_df: pd.DataFrame) -> Dict:
    """按拍板定义计算未完结统计与明细。main_df 为当前（已筛选）主表。

    返回 dict：
      unfinished_orders / total_orders / unfinished_qty / unfinished_amount
      details: 未完结 data_id 明细列表
    """
    empty = {
        "unfinished_orders": 0,
        "total_orders": 0,
        "unfinished_qty": 0.0,
        "unfinished_amount": 0.0,
        "details": [],
    }
    if main_df is None or len(main_df) == 0:
        return empty

    qty_col = _resolve_col(main_df, _QTY_CANDIDATES)
    amt_col = _resolve_col(main_df, _AMT_CANDIDATES)
    factory_col = _resolve_col(main_df, ["工厂"])
    date_col = _resolve_col(main_df, ["订单日期"])
    po_col = _resolve_col(main_df, ["流程订单"])
    mat_col = _resolve_col(main_df, ["物料编码"])
    id_col = _resolve_col(main_df, ["data_id"])

    if id_col is None:
        # 没有 data_id 无法关联 read_status / 隔离区，整体视为无未完结
        return empty

    # 收集去重 data_id 列表
    seen = set()
    data_ids = []
    for v in main_df[id_col]:
        s = str(v)
        if s and s != "nan" and s not in seen:
            seen.add(s)
            data_ids.append(s)

    # 批量查已读状态：{data_id: (is_read, fingerprint, ...)}
    read_map = load_read_status(data_ids) if data_ids else {}
    # 活跃隔离区：{uid: exempted_bool}（restored_at IS NULL）
    q_records = get_quarantine_records()
    q_map = {r["uid"]: bool(r.get("exempted")) for r in q_records}

    order_unfinished = {}  # order_key -> 是否含未完结
    details = []
    unfinished_qty = 0.0
    unfinished_amount = 0.0

    for _, row in main_df.iterrows():
        did = str(row[id_col])
        if not did or did == "nan":
            continue
        tup = read_map.get(did)
        is_read = tup[0] if tup else 0
        in_q = did in q_map
        exempted = q_map.get(did, False)
        unfinished = (is_read == 0) or (in_q and not exempted)

        if factory_col and date_col and po_col:
            gkey = (str(row[factory_col]), str(row[date_col]), str(row[po_col]))
        else:
            segs = did.split("|")
            gkey = tuple(segs[:3]) if len(segs) >= 3 else (did,)

        if unfinished:
            order_unfinished[gkey] = True
            q = _safe_float(row[qty_col]) if qty_col else 0.0
            a = _safe_float(row[amt_col]) if amt_col else 0.0
            unfinished_qty += q
            unfinished_amount += a
            details.append({
                "data_id": did,
                "factory": str(row[factory_col]) if factory_col else "",
                "order_date": str(row[date_col]) if date_col else "",
                "process_order": str(row[po_col]) if po_col else "",
                "material": str(row[mat_col]) if mat_col else "",
                "reason": "未读" if is_read == 0 else ("隔离区未豁免" if in_q else ""),
                "qty": round(q, 2),
                "amount": round(a, 2),
            })
        else:
            order_unfinished.setdefault(gkey, False)

    total_orders = len(order_unfinished)
    unfinished_orders = sum(1 for v in order_unfinished.values() if v)

    return {
        "unfinished_orders": unfinished_orders,
        "total_orders": total_orders,
        "unfinished_qty": round(unfinished_qty, 2),
        "unfinished_amount": round(unfinished_amount, 2),
        "details": details,
    }


def _period_label(main_df: pd.DataFrame) -> str:
    date_col = _resolve_col(main_df, ["订单日期"])
    if date_col is None or len(main_df) == 0:
        return "无日期"
    dates = pd.to_datetime(main_df[date_col], errors="coerce").dropna()
    if len(dates) == 0:
        return "无日期"
    return f"{dates.min().strftime('%Y-%m-%d')} ~ {dates.max().strftime('%Y-%m-%d')}"


def generate_snapshot(main_df: pd.DataFrame, caliber: str,
                      meta_context: Optional[dict] = None,
                      score_snapshot: Optional[dict] = None) -> str:
    """生成一次快照，返回快照目录路径。

    caliber: "期间累计" / "截至当前累计"
    meta_context: 筛选上下文（best-effort dict）
    score_snapshot: 评分卡快照（可选，D2 趋势线用；无则历史库相应列为 NULL）
    """
    now = datetime.datetime.now()
    ts = now.strftime("%Y%m%d-%H%M%S")
    snap_dir = os.path.join(SNAPSHOT_ROOT, ts)
    os.makedirs(snap_dir, exist_ok=True)

    gen_moment = now.strftime("%Y-%m-%d %H:%M")
    period = _period_label(main_df)
    unf = compute_unfinished(main_df)

    meta = {
        "generated_at": gen_moment,
        "timestamp": ts,
        "data_period": period,
        "caliber": caliber,
        "unfinished_orders": unf["unfinished_orders"],
        "total_orders": unf["total_orders"],
        "unfinished_qty": unf["unfinished_qty"],
        "unfinished_amount": unf["unfinished_amount"],
        "row_count": int(len(main_df)) if main_df is not None else 0,
        "filter_context": meta_context or {},
    }

    with open(os.path.join(snap_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if main_df is not None and len(main_df):
        main_df.to_csv(os.path.join(snap_dir, "data.csv"), index=False, encoding="utf-8-sig")

    with open(os.path.join(snap_dir, "unfinished.json"), "w", encoding="utf-8") as f:
        json.dump(unf, f, ensure_ascii=False, indent=2)

    if score_snapshot is not None:
        with open(os.path.join(snap_dir, "score.json"), "w", encoding="utf-8") as f:
            json.dump(score_snapshot, f, ensure_ascii=False, indent=2)

    _append_history(ts, gen_moment, period, caliber, unf, score_snapshot)

    # 只读留痕（Windows 上 chmod 仅作提示，防误改）
    try:
        os.chmod(snap_dir, 0o555)
    except Exception:
        pass

    return snap_dir


def _append_history(ts, gen_moment, period, caliber, unf, score_snapshot):
    os.makedirs(os.path.dirname(HISTORY_DB), exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS snapshot_history (
                ts TEXT PRIMARY KEY,
                gen_moment TEXT,
                period TEXT,
                caliber TEXT,
                coverage_rate REAL,
                drift_rate REAL,
                long_chain_cnt INTEGER,
                score_total REAL,
                unfinished_orders INTEGER,
                unfinished_qty REAL,
                unfinished_amount REAL
            )"""
        )
        s = score_snapshot or {}
        conn.execute(
            "INSERT OR REPLACE INTO snapshot_history "
            "(ts, gen_moment, period, caliber, coverage_rate, drift_rate, "
            "long_chain_cnt, score_total, unfinished_orders, unfinished_qty, unfinished_amount) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                ts, gen_moment, period, caliber,
                s.get("coverage_rate"), s.get("drift_rate"),
                s.get("long_chain_cnt"), s.get("score_total"),
                unf["unfinished_orders"], unf["unfinished_qty"], unf["unfinished_amount"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
