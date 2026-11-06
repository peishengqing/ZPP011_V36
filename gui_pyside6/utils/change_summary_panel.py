# -*- coding: utf-8 -*-
"""D2 变更摘要面板：看板/快照内嵌可折叠面板，按需渲染三张静态图。不推送、不自动刷新、无动画。

仅此文件依赖 PySide6；核心逻辑在 core.change_summary（纯逻辑、可独立单测）。
"""
import os
import tempfile

from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QPushButton, QLabel,
                               QTextBrowser, QHBoxLayout, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

import core.change_summary as change_summary


def attach_change_summary(dialog) -> None:
    """在对话框顶部（快照条之后）插入可折叠的「变更摘要」面板。dialog 需具备 self.main_window。"""
    box = QGroupBox("📊 变更摘要（本期间 · 本地，不推送）")
    box.setCheckable(True)
    box.setChecked(False)
    inner = QVBoxLayout()

    btn = QPushButton("刷新摘要（按需渲染图表）")
    inner.addWidget(btn)

    info = QTextBrowser()
    info.setMaximumHeight(170)
    info.setOpenExternalLinks(False)
    inner.addWidget(info)

    charts = QHBoxLayout()
    labels = {}
    for key in ("staircase", "progress", "trend"):
        lab = QLabel("（展开并点「刷新」后显示）")
        lab.setAlignment(Qt.AlignCenter)
        lab.setFrameShape(QFrame.Box)
        lab.setMinimumSize(200, 130)
        labels[key] = lab
        charts.addWidget(lab)
    inner.addLayout(charts)

    box.setLayout(inner)
    btn.clicked.connect(lambda: _on_refresh(dialog, info, labels))

    layout = dialog.layout()
    if layout is not None:
        # 快照条在索引 0，变更摘要插到其后
        layout.insertWidget(1, box)


def _on_refresh(dialog, info, labels):
    mw = getattr(dialog, "main_window", None)
    if mw is None:
        info.setPlainText("无法获取主窗口数据，无法计算变更摘要。")
        return
    vm = getattr(mw, "view_model", None)
    df = vm.df if vm is not None else None
    if df is None or len(df) == 0:
        info.setPlainText("当前主表无数据，无法计算变更摘要。")
        return

    try:
        summary = change_summary.compute_change_summary(df)
    except Exception as e:  # noqa: BLE001 — 用户可见链路必须暴露错误
        info.setPlainText(f"计算变更摘要出错：\n{e}")
        return

    info.setMarkdown(_format_text(summary))

    out = os.path.join(tempfile.gettempdir(), "zpp_change_summary")
    try:
        paths = change_summary.render_charts(summary, out)
    except Exception as e:  # noqa: BLE001
        paths = {}
        info.append(f"\n[图表渲染失败] {e}")

    for key, lab in labels.items():
        p = paths.get(key)
        if p and os.path.exists(p):
            lab.setPixmap(QPixmap(p).scaled(200, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lab.setText("")
        else:
            lab.setPixmap(QPixmap())
            lab.setText("（暂无数据）")


def _fmt_delta(v):
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else ''}{v}"


def _format_text(s: dict) -> str:
    if not s["has_baseline"]:
        base_line = "（无对比基线：首次快照或历史为空，仅展示当前值与本期偏差修改）"
    else:
        base_line = f"（对比基线：{s['baseline_time']}）"

    lines = [
        f"## 变更摘要 {base_line}",
        f"- 当前未完结订单：**{s['current_unfinished_orders']} / {s['current_total_orders']}**；"
        f"未审核差额 数量 {s['current_unfinished_qty']} / 金额(含税) {s['current_unfinished_amount']}",
        f"- 本期偏差修改/归因漂移记录：**{s['change_records']}** 笔，涉及订单 **{len(s['change_orders'])}** 个",
    ]
    if s["has_baseline"]:
        lines.append(
            f"- 自基线起「从未完结→完结」订单：**{len(s['finished_orders'])}** 个；"
            f"新出现未完结：**{len(s['new_unfinished_orders'])}** 个；"
            f"仍处未完结：**{s['still_unfinished_count']}** 个")
    sc = s.get("score") or {}
    lines.append(
        f"- 评分卡：总评分 **{sc.get('score_total')}** ｜ 备注覆盖率 {sc.get('coverage_rate')} ｜ "
        f"归因漂移率 {sc.get('drift_rate')} ｜ 替代料长链 {sc.get('long_chain_cnt')}")
    sd = s.get("score_delta")
    if sd:
        lines.append(
            f"- 评分变化：总评 {_fmt_delta(sd.get('score_total'))} ｜ 覆盖率 {_fmt_delta(sd.get('coverage_rate'))} ｜ "
            f"漂移率 {_fmt_delta(sd.get('drift_rate'))} ｜ 长链 {_fmt_delta(sd.get('long_chain_cnt'))}")
    lines.append(f"- 结论：{s.get('conclusion', '')}")
    return "\n".join(lines)
