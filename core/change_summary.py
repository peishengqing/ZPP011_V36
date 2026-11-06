# -*- coding: utf-8 -*-
"""D2 本地变更摘要：纯逻辑，无 PyQt，可 offscreen 独立单测。

对比「当前实时状态」与「最近一次快照基线」，产出可汇报的变更摘要 +
三张静态图（未完结阶梯图 / 未完结进度条 / 评分卡趋势线）的数据。
GUI 侧面板在 gui_pyside6/utils/change_summary_panel.py。

「本期间」在本实现 = 「自最近一次快照以来」；无历史快照时优雅降级。
"""
import os
import json
import sqlite3
from typing import Dict, List, Optional

import pandas as pd

from core.snapshot import SNAPSHOT_ROOT, HISTORY_DB, compute_unfinished
from core.scorecard import compute_scorecard


# ------------------------- 快照基线发现 -------------------------

def list_snapshots() -> List[str]:
    """返回所有合法快照目录（含 meta.json），按目录名（时间戳）升序。"""
    if not os.path.isdir(SNAPSHOT_ROOT):
        return []
    dirs = []
    for d in os.listdir(SNAPSHOT_ROOT):
        p = os.path.join(SNAPSHOT_ROOT, d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "meta.json")):
            dirs.append(p)
    dirs.sort()
    return dirs


def latest_snapshot_dir(exclude: Optional[str] = None) -> Optional[str]:
    dirs = list_snapshots()
    if exclude:
        bn = os.path.basename(exclude)
        dirs = [d for d in dirs if os.path.basename(d) != bn]
    return dirs[-1] if dirs else None


def _load_json(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _ts_to_iso(ts: str) -> Optional[str]:
    """快照目录名 'YYYYMMDD-HHMMSS' -> iso 'YYYY-MM-DDTHH:MM:SS'（用于 deviation_history.change_time 比较）。"""
    try:
        d, t = ts.split("-")
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}"
    except Exception:
        return None


# ------------------------- 变更摘要计算 -------------------------

def _order_key(detail: dict) -> str:
    return "|".join([
        str(detail.get("factory", "")),
        str(detail.get("order_date", "")),
        str(detail.get("process_order", "")),
    ])


def _order_keys(unf: Optional[dict]) -> set:
    s = set()
    if unf:
        for d in unf.get("details", []):
            s.add(_order_key(d))
    return s


def _delta(a, b):
    if a is None or b is None:
        return None
    try:
        return round(float(b) - float(a), 4)
    except Exception:
        return None


def _order_key_of(data_id: str) -> str:
    segs = str(data_id).split("|")
    return "|".join(segs[:3]) if len(segs) >= 3 else str(data_id)


def _deviation_changes_since(since_iso: Optional[str]) -> List[dict]:
    from core.read_status import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            if since_iso:
                cur = conn.execute(
                    "SELECT * FROM deviation_history "
                    "WHERE data_id<>'X' AND data_id IS NOT NULL AND change_time >= ? "
                    "ORDER BY change_time DESC",
                    (since_iso,),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM deviation_history "
                    "WHERE data_id<>'X' AND data_id IS NOT NULL "
                    "ORDER BY change_time DESC LIMIT 500")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()
        return rows
    except Exception:
        return []


def compute_change_summary(main_df: pd.DataFrame,
                           baseline_dir: Optional[str] = None) -> Dict:
    """计算变更摘要。baseline_dir 不传则取最近一次快照作基线。

    返回结构（供面板与图表消费）：
      has_baseline / baseline_time
      current_unfinished_orders / current_total_orders / current_unfinished_qty / current_unfinished_amount
      finished_orders[] / new_unfinished_orders[] / still_unfinished_count
      change_records / change_orders[]
      score / score_delta / conclusion
    """
    current_unf = compute_unfinished(main_df)
    current_score = compute_scorecard(main_df)

    if baseline_dir is None:
        baseline_dir = latest_snapshot_dir()
    baseline_unf = None
    baseline_score = None
    baseline_ts = None
    if baseline_dir:
        baseline_unf = _load_json(os.path.join(baseline_dir, "unfinished.json"))
        baseline_score = _load_json(os.path.join(baseline_dir, "score.json"))
        baseline_ts = os.path.basename(baseline_dir)  # 用于 since 过滤

    cur_keys = _order_keys(current_unf)
    base_keys = _order_keys(baseline_unf)

    finished_orders = sorted(base_keys - cur_keys)
    new_unfinished = sorted(cur_keys - base_keys)
    still_unfinished = sorted(cur_keys & base_keys)

    since_iso = _ts_to_iso(baseline_ts) if baseline_ts else None
    changes = _deviation_changes_since(since_iso)
    change_orders = sorted({_order_key_of(c.get("data_id", "")) for c in changes})

    score_delta = None
    if baseline_score and current_score:
        score_delta = {
            "coverage_rate": _delta(baseline_score.get("coverage_rate"), current_score.get("coverage_rate")),
            "drift_rate": _delta(baseline_score.get("drift_rate"), current_score.get("drift_rate")),
            "long_chain_cnt": _delta(baseline_score.get("long_chain_cnt"), current_score.get("long_chain_cnt")),
            "score_total": _delta(baseline_score.get("score_total"), current_score.get("score_total")),
        }

    return {
        "has_baseline": baseline_dir is not None,
        "baseline_time": baseline_ts,
        "current_unfinished_orders": current_unf["unfinished_orders"],
        "current_total_orders": current_unf["total_orders"],
        "current_unfinished_qty": current_unf["unfinished_qty"],
        "current_unfinished_amount": current_unf["unfinished_amount"],
        "finished_orders": finished_orders,
        "new_unfinished_orders": new_unfinished,
        "still_unfinished_count": len(still_unfinished),
        "change_records": len(changes),
        "change_orders": change_orders,
        "score": current_score,
        "score_delta": score_delta,
        "conclusion": current_score.get("conclusion", ""),
    }


# ------------------------- 三张静态图（matplotlib Agg 离屏） -------------------------

def _history_rows() -> List[dict]:
    if not os.path.exists(HISTORY_DB):
        return []
    try:
        conn = sqlite3.connect(HISTORY_DB)
        try:
            cur = conn.execute(
                "SELECT ts, gen_moment, total_orders, unfinished_orders, "
                "coverage_rate, drift_rate, score_total FROM snapshot_history ORDER BY ts ASC")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()
        return rows
    except Exception:
        return []


def _ensure_cjk_font():
    """注册系统中文字体给 matplotlib（避免图表中文变方框）。返回字体名或 None。"""
    from matplotlib import font_manager
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\Source Han Serif SC Heavy (TrueType).ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                font_manager.fontManager.addfont(c)
                return font_manager.FontProperties(fname=c).get_name()
            except Exception:
                continue
    return None


def render_charts(summary: Dict, out_dir: str) -> Dict[str, str]:
    """渲染三张静态图到 out_dir，返回 {key: png_path}（无数据则缺省该 key）。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 中文字体（仅当存在时启用，缺失则退回默认，不影响出图）
    cjk = _ensure_cjk_font()
    if cjk:
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [cjk]
        plt.rcParams["axes.unicode_minus"] = False

    os.makedirs(out_dir, exist_ok=True)
    paths: Dict[str, str] = {}
    rows = _history_rows()

    # 1) 未完结订单数阶梯图
    if rows:
        xs = list(range(len(rows)))
        ys = [r["unfinished_orders"] or 0 for r in rows]
        fig, ax = plt.subplots(figsize=(6.0, 2.4))
        ax.step(xs, ys, where="post", color="#C62828", linewidth=1.6)
        ax.set_xticks(xs)
        ax.set_xticklabels([r["ts"] for r in rows], rotation=45, fontsize=6)
        ax.set_ylabel("未完结订单数", fontsize=8)
        ax.set_title("未完结订单数（阶梯 · 按快照时间）", fontsize=9)
        ax.text(0.99, 0.95,
                f"未完结 {summary['current_unfinished_orders']}/{summary['current_total_orders']}",
                transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#C62828")
        fig.tight_layout()
        p = os.path.join(out_dir, "staircase.png")
        fig.savefig(p, dpi=110)
        plt.close(fig)
        paths["staircase"] = p

        # 2) 未完结进度条拼图
        total = summary["current_total_orders"] or 0
        unf = summary["current_unfinished_orders"] or 0
        finished = max(total - unf, 0)
        today_changed = (len(rows) >= 2 and (rows[-1]["unfinished_orders"] != rows[-2]["unfinished_orders"]))
        fig2, ax2 = plt.subplots(figsize=(6.0, 1.4))
        ax2.barh([0], [finished], color="#2E7D32", label=f"已完结 {finished}")
        ax2.barh([0], [unfinished_bar := unf], left=[finished], color="#C62828", label=f"未完结 {unfinished_bar}")
        ax2.set_yticks([])
        ax2.set_xlim(0, max(total, 1))
        ax2.set_title(
            f"未完结进度条（{'今日有变更' if today_changed else '今日无变更'}）",
            fontsize=9,
            color="#EF6C00" if today_changed else "#555555")
        fig2.tight_layout()
        p2 = os.path.join(out_dir, "progress.png")
        fig2.savefig(p2, dpi=110)
        plt.close(fig2)
        paths["progress"] = p2

        # 3) 评分卡趋势线（近 30 天）
        fig3, ax3 = plt.subplots(figsize=(6.0, 2.4))
        plotted = False
        for key, color in (("coverage_rate", "#1565C0"), ("drift_rate", "#C62828"), ("score_total", "#2E7D32")):
            ys3 = [r[key] for r in rows if r.get(key) is not None]
            if ys3:
                ax3.plot(xs[:len(ys3)], ys3, marker=".", label=key, color=color, linewidth=1.2)
                plotted = True
        if plotted:
            ax3.set_xticks(xs)
            ax3.set_xticklabels([r["ts"] for r in rows], rotation=45, fontsize=6)
            ax3.legend(fontsize=6)
            ax3.set_title("评分卡趋势线（coverage/drift/score）", fontsize=9)
            fig3.tight_layout()
            p3 = os.path.join(out_dir, "trend.png")
            fig3.savefig(p3, dpi=110)
            plt.close(fig3)
            paths["trend"] = p3
        else:
            plt.close(fig3)

    return paths
