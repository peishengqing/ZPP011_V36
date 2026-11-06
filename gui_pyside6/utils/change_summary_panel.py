# -*- coding: utf-8 -*-
"""D2 变更摘要面板：看板/快照内嵌可折叠面板，按需渲染三张静态图。不推送、不自动刷新、无动画。

仅此文件依赖 PySide6；核心逻辑在 core.change_summary（纯逻辑、可独立单测）。
"""
import os
import tempfile
import datetime

from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QPushButton, QLabel,
                               QTextBrowser, QHBoxLayout, QFrame, QFileDialog,
                               QMessageBox, QComboBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

import core.change_summary as change_summary
import core.report_pdf as report_pdf
import core.closing as closing


def attach_change_summary(dialog) -> None:
    """在对话框顶部（快照条之后）插入可折叠的「变更摘要」面板。dialog 需具备 self.main_window。"""
    box = QGroupBox("📊 变更摘要（本期间 · 本地，不推送）")
    box.setCheckable(True)
    box.setChecked(False)
    inner = QVBoxLayout()

    btn = QPushButton("刷新摘要（按需渲染图表）")
    inner.addWidget(btn)

    # 月报月份下拉（D4 关账粒度：按月）
    month_row = QHBoxLayout()
    month_row.addWidget(QLabel("月报月份:"))
    month_combo = QComboBox()
    month_row.addWidget(month_combo)
    month_row.addStretch(1)
    inner.addLayout(month_row)
    _populate_months(dialog, month_combo)

    btn_row = QHBoxLayout()
    btn_pdf = QPushButton("📄 导出 PDF（本地只读）")
    btn_pdf.setToolTip("导出为本地只读 PDF，系统不推送、不外发")
    btn_close = QPushButton("📅 关账")
    btn_close.setToolTip("未完结清零后生成本月定稿；关账后锁定，再导出走修订版")
    btn_row.addWidget(btn_pdf)
    btn_row.addWidget(btn_close)
    btn_row.addStretch(1)
    inner.addLayout(btn_row)

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
    btn_pdf.clicked.connect(lambda: _on_export(dialog, info, labels, month_combo))
    btn_close.clicked.connect(lambda: _on_close(dialog, info, month_combo))

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


def _populate_months(dialog, combo):
    """best-effort 用主表订单日期填充月份下拉；首项是「全部/不按月」。"""
    combo.clear()
    combo.addItem("（全部 / 不按月）", None)
    try:
        mw = getattr(dialog, "main_window", None)
        vm = getattr(mw, "view_model", None) if mw else None
        df = vm.df if vm is not None else None
        months = closing.months_in_df(df) if df is not None else []
        for m in months:
            combo.addItem(m, m)
        if months:
            combo.setCurrentIndex(combo.count() - 1)  # 默认最新月
    except Exception:
        pass


def _on_export(dialog, info, labels, month_combo):
    """D3/D4 一键 PDF：弹文件选择框，生成本地只读 PDF（拒绝覆盖已存在文件）。"""
    mw = getattr(dialog, "main_window", None)
    if mw is None:
        QMessageBox.warning(dialog, "提示", "无法获取主窗口数据，无法导出 PDF。")
        return
    vm = getattr(mw, "view_model", None)
    df = vm.df if vm is not None else None
    if df is None or len(df) == 0:
        QMessageBox.warning(dialog, "提示", "当前主表无数据，无法导出 PDF。")
        return

    # 口径与快照条保持一致（若存在）
    cal = "期间累计"
    snap = getattr(dialog, "_snap_caliber", None)
    if snap is not None and hasattr(snap, "currentText"):
        cal = snap.currentText()

    month = month_combo.currentData() if month_combo is not None else None

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    # 默认文件名带月份 + 关账标注（草稿/定稿/修订版），便于归档
    if month:
        proj = closing.next_label(month, force_final=False)
        default_name = f"ZPP011_{month}_{proj}_偏差变更摘要_{ts}.pdf"
    else:
        default_name = f"ZPP011_偏差变更摘要_{ts}.pdf"
    path, _ = QFileDialog.getSaveFileName(
        dialog, "导出 PDF（本地只读）", default_name, "PDF 文件 (*.pdf)")
    if not path:
        return  # 用户取消

    # 拒绝覆盖已存在文件：D 红线——系统不主动外发、不静默改写
    if os.path.exists(path):
        QMessageBox.warning(
            dialog, "未覆盖",
            f"该文件已存在，未予覆盖：\n{path}\n请换一个文件名或另选路径。")
        return

    try:
        saved = report_pdf.build_pdf(df, caliber=cal, internal=True,
                                     save_path=path, month=month, force_final=False)
    except Exception as e:  # noqa: BLE001 — 用户可见链路必须暴露错误
        QMessageBox.critical(dialog, "导出失败", f"生成 PDF 出错：\n{e}")
        return

    QMessageBox.information(
        dialog, "PDF 已生成",
        f"已生成本地只读 PDF：\n{saved}\n\n"
        f"口径：{cal}" + (f"\n报告月份：{month}" if month else "") +
        "\n系统未推送、未外发，请自行取用。",
    )


def _on_close(dialog, info, month_combo):
    """D4 关账：未完结清零才允许，生成本月定稿并锁定。"""
    mw = getattr(dialog, "main_window", None)
    if mw is None:
        QMessageBox.warning(dialog, "提示", "无法获取主窗口数据，无法关账。")
        return
    vm = getattr(mw, "view_model", None)
    df = vm.df if vm is not None else None
    if df is None or len(df) == 0:
        QMessageBox.warning(dialog, "提示", "当前主表无数据，无法关账。")
        return

    month = month_combo.currentData() if month_combo is not None else None
    if not month:
        QMessageBox.warning(dialog, "提示", "请先在「月报月份」下拉中选择一个月份再关账。")
        return

    ok, reason = closing.can_close(df, month)
    if not ok:
        QMessageBox.warning(dialog, "无法关账", reason)
        return

    st = closing.get_status(month)
    if st["status"] == "closed":
        QMessageBox.information(
            dialog, "已关账",
            f"{month} 已关账定稿（关账时间 {st['closed_at']} · 关账人 {st['closed_by'] or '—'}）。\n"
            f"如需改动请重新导出，将自动走「修订版」。")
        return

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    default_name = f"ZPP011_{month}_定稿_偏差变更摘要_{ts}.pdf"
    path, _ = QFileDialog.getSaveFileName(
        dialog, f"关账 · {month} 定稿", default_name, "PDF 文件 (*.pdf)")
    if not path:
        return  # 用户取消
    if os.path.exists(path):
        QMessageBox.warning(
            dialog, "未覆盖",
            f"该文件已存在，未予覆盖：\n{path}\n请换一个文件名或另选路径。")
        return

    try:
        saved = report_pdf.build_pdf(df, caliber="期间累计", internal=True,
                                     save_path=path, month=month,
                                     force_final=True, closed_by="裴盛清")
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(dialog, "关账失败", f"生成定稿出错：\n{e}")
        return

    QMessageBox.information(
        dialog, "已关账定稿",
        f"{month} 已关账定稿（关账人 裴盛清）：\n{saved}\n\n"
        f"此后数据锁定；如需改动请重新导出，将自动走「修订版 v1…」。",
    )


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
