# -*- coding: utf-8 -*-
"""D3 一键 PDF：把当前看板/变更摘要导出为本地只读 PDF（matplotlib PdfPages，无新依赖）。

PDF 结构（A4 多页）：
  ① 封面：期间 / 截止时间 / 口径 / 未完结数 + 数据质量评分卡
  ② 看板摘要 + Top 异常（按偏差金额(含税) 取前 15，万行表只出 TopN 不整表）
  ③ 趋势与未完结可视化（复用 D2 的阶梯图 / 进度条 / 趋势线 PNG）
  ④ 变更摘要附录
每页页脚标注「只读快照，数据截至 XX · 系统未推送未外发」。

内部版 / 外发版通过 internal 参数切换敏感列（外发隐藏物料编码）。
"""
import os
import shutil
import datetime
from typing import Dict, List, Optional

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from core.snapshot import compute_unfinished, _period_label, _safe_float
from core.scorecard import compute_scorecard
from core.change_summary import compute_change_summary, render_charts, _ensure_cjk_font
import core.closing as closing


_A4 = (8.27, 11.69)
_REPORT_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "ZPP011", "reports")


def _setup_font():
    cjk = _ensure_cjk_font()
    if cjk:
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [cjk]
        plt.rcParams["axes.unicode_minus"] = False


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def _footer(fig, generated_at: str, extra: str = ""):
    note = f"只读快照，数据截至 {generated_at} · 系统未推送未外发"
    if extra:
        note += f" · {extra}"
    fig.text(0.5, 0.02, note, ha="center", fontsize=7, color="#888888")


def _top_anomalies(df: pd.DataFrame, n: int = 15, internal: bool = True) -> Optional[Dict]:
    amt_col = None
    for c in ["偏差金额(含税)", "净偏差金额", "偏差金额"]:
        if c in df.columns:
            amt_col = c
            break
    if amt_col is None or len(df) == 0:
        return None
    d = df.copy()
    d["_abs"] = d[amt_col].apply(lambda v: abs(_safe_float(v)))
    d = d.sort_values("_abs", ascending=False).head(n)
    headers = ["工厂", "流程订单", "偏差数量", amt_col, "备注原因"]
    cells: List[List[str]] = []
    for _, r in d.iterrows():
        row = [
            str(r.get("工厂", "")),
            str(r.get("流程订单", "")),
            _fmt(_safe_float(r.get("偏差数量"))),
            _fmt(_safe_float(r.get(amt_col))),
            str(r.get("备注原因", ""))[:24],
        ]
        if internal:
            row.insert(2, str(r.get("物料编码", "")))
        cells.append(row)
    if internal:
        headers.insert(2, "物料编码")
    return {"headers": headers, "cells": cells}


def _summary_lines(summary: Dict) -> List[str]:
    lines = []
    if not summary["has_baseline"]:
        lines.append("（无对比基线：首次快照或历史为空，仅展示当前值与本期偏差修改）")
    else:
        lines.append(f"对比基线：{summary['baseline_time']}")
    lines.append(
        f"当前未完结订单：{summary['current_unfinished_orders']} / {summary['current_total_orders']}；"
        f"未审核差额 数量 {_fmt(summary['current_unfinished_qty'])} / 金额(含税) {_fmt(summary['current_unfinished_amount'])}")
    lines.append(
        f"本期偏差修改/归因漂移记录：{summary['change_records']} 笔，涉及订单 {len(summary['change_orders'])} 个")
    if summary["has_baseline"]:
        lines.append(
            f"自基线起「从未完结→完结」：{len(summary['finished_orders'])} 个；"
            f"新出现未完结：{len(summary['new_unfinished_orders'])} 个；"
            f"仍处未完结：{summary['still_unfinished_count']} 个")
    sc = summary.get("score") or {}
    lines.append(
        f"评分卡：总评分 {_fmt(sc.get('score_total'))} ｜ 备注覆盖率 {_fmt(sc.get('coverage_rate'))} ｜ "
        f"归因漂移率 {_fmt(sc.get('drift_rate'))} ｜ 替代料长链 {_fmt(sc.get('long_chain_cnt'))}")
    sd = summary.get("score_delta")
    if sd:
        def _d(v):
            return "—" if v is None else f"{'+' if v >= 0 else ''}{v}"
        lines.append(
            f"评分变化：总评 {_d(sd.get('score_total'))} ｜ 覆盖率 {_d(sd.get('coverage_rate'))} ｜ "
            f"漂移率 {_d(sd.get('drift_rate'))} ｜ 长链 {_d(sd.get('long_chain_cnt'))}")
    lines.append(f"结论：{summary.get('conclusion', '')}")
    return lines


def build_pdf(main_df: pd.DataFrame, caliber: str = "期间累计",
              internal: bool = True, save_path: Optional[str] = None,
              month: Optional[str] = None, force_final: bool = False,
              closed_by: Optional[str] = None) -> str:
    """生成 D3/D4 报告 PDF，返回文件路径。

    month 不传 → 整表导出（D3 行为，不涉关账）。
    month 传入（'YYYY-MM'）→ 按月 filter 主表，并按关账状态标注：
      draft  → 封面标「草稿 vN」+（数据未关账可能变动）
      final  → 封面标「定稿」（关账动作触发，force_final=True）
      revised→ 封面标「修订版 vN」（定稿后再次导出）
    每次导出后把对应状态/计数写回 audit.db 的 closing_status 表。
    """
    _setup_font()
    now = datetime.datetime.now()
    gen = now.strftime("%Y-%m-%d %H:%M")
    ts = now.strftime("%Y%m%d-%H%M%S")

    # 按月划分：决定使用的数据范围 + 关账标注
    mode = None
    label = None
    if month:
        st = closing.get_status(month)
        if force_final and st["status"] != "closed":
            mode, label = "final", "定稿"
        elif st["status"] == "closed":
            # 已关账后再导出 → 修订版
            mode, label = "revised", f"修订版 v{st['revised_count'] + 1}"
        else:
            mode, label = "draft", f"草稿 v{st['draft_count'] + 1}"
        df_use = closing._filter_month(main_df, month)
    else:
        df_use = main_df

    if not save_path:
        os.makedirs(_REPORT_DIR, exist_ok=True)
        if month and label:
            base = f"ZPP011_{month}_{label}_偏差变更摘要_{ts}.pdf"
        else:
            base = f"ZPP011_偏差变更摘要_{ts}.pdf"
        save_path = os.path.join(_REPORT_DIR, base)

    unf = compute_unfinished(df_use)
    score = compute_scorecard(df_use)
    summary = compute_change_summary(df_use)

    chart_dir = os.path.join(_REPORT_DIR, f"_charts_{ts}")
    charts = render_charts(summary, chart_dir)

    # 封面附加的关账标注 / 提示
    if label:
        status_note = f"报告状态：{label}"
        if mode == "draft":
            status_note += "（数据未关账，可能变动）"
        elif mode == "final":
            stt = closing.get_status(month)
            if stt["closed_at"]:
                status_note += f"（关账时间 {stt['closed_at']} · 关账人 {stt['closed_by'] or '—'}）"
    else:
        status_note = ""

    with PdfPages(save_path) as pdf:
        # ① 封面 + 评分卡
        fig = plt.figure(figsize=_A4)
        fig.text(0.5, 0.92, "ZPP011 生产偏差分析 · 变更摘要报告",
                 ha="center", fontsize=18, weight="bold")
        cover = [
            f"生成时刻：{gen}",
            f"口径：{caliber}",
        ]
        if month:
            cover.append(f"报告月份：{month}（按月）")
        if status_note:
            cover.append(status_note)
        cover += [
            f"数据期间：{_period_label(df_use)}",
            f"当前未完结订单：{unf['unfinished_orders']} / {unf['total_orders']}",
            f"未审核差额：数量 {_fmt(unf['unfinished_qty'])} / 金额(含税) {_fmt(unf['unfinished_amount'])}",
            "",
            "【数据质量评分卡】",
            f"  总评分：{_fmt(score.get('score_total'))} / 100",
            f"  备注覆盖率：{_fmt(score.get('coverage_rate'))}",
            f"  归因漂移率：{_fmt(score.get('drift_rate'))}",
            f"  替代料长链数：{_fmt(score.get('long_chain_cnt'))}",
            f"  结论：{score.get('conclusion', '')}",
        ]
        fig.text(0.08, 0.80, "\n".join(cover), ha="left", va="top", fontsize=11)
        _footer(fig, gen, extra=label or "")
        pdf.savefig(fig)
        plt.close(fig)

        # ② 看板摘要 + Top 异常
        fig = plt.figure(figsize=_A4)
        title = "看板摘要 · Top 异常（按偏差金额(含税) 取前 15）"
        if month:
            title = f"看板摘要 · {month} · Top 异常（按偏差金额(含税) 取前 15）"
        fig.text(0.5, 0.95, title, ha="center", fontsize=14, weight="bold")
        top = _top_anomalies(df_use, n=15, internal=internal)
        ax = fig.add_axes([0.05, 0.06, 0.90, 0.84])
        ax.axis("off")
        if top is not None and top["cells"]:
            tbl = ax.table(cellText=top["cells"], colLabels=top["headers"],
                           loc="upper center", cellLoc="left")
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(7)
            tbl.scale(1, 1.3)
        else:
            ax.text(0.5, 0.5, "（无数据）", ha="center", va="center")
        _footer(fig, gen, extra=label or "")
        pdf.savefig(fig)
        plt.close(fig)

        # ③ 趋势与未完结可视化
        fig = plt.figure(figsize=_A4)
        fig.text(0.5, 0.95, "趋势与未完结可视化", ha="center", fontsize=14, weight="bold")
        for key, y in (("staircase", 0.56), ("progress", 0.31), ("trend", 0.06)):
            p = charts.get(key)
            if p and os.path.exists(p):
                img = plt.imread(p)
                ax = fig.add_axes([0.1, y, 0.8, 0.22])
                ax.axis("off")
                ax.imshow(img)
        _footer(fig, gen, extra=label or "")
        pdf.savefig(fig)
        plt.close(fig)

        # ④ 变更摘要附录
        fig = plt.figure(figsize=_A4)
        fig.text(0.5, 0.95, "变更摘要附录", ha="center", fontsize=14, weight="bold")
        lines = _summary_lines(summary)
        y = 0.88
        for ln in lines:
            fig.text(0.08, y, ln, ha="left", va="top", fontsize=10)
            y -= 0.032
        _footer(fig, gen, extra=label or "")
        pdf.savefig(fig)
        plt.close(fig)

    # 关账状态落库（仅按月导出时）
    if month and save_path:
        if mode == "final":
            closing.close_month(month, closed_by or "裴盛清", save_path)
        elif mode == "revised":
            closing.record_revised_export(month, save_path)
        else:
            closing.record_draft_export(month, save_path)

    # 清理临时图表目录，避免 %APPDATA%/ZPP011/reports 堆积 _charts_* 残留
    shutil.rmtree(chart_dir, ignore_errors=True)

    return save_path
