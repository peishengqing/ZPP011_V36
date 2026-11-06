# -*- coding: utf-8 -*-
"""D1 快照的 GUI 侧入口：在对话框顶部插入「生成当前快照」工具条。

仅此文件依赖 PySide6；核心逻辑在 core.snapshot（纯逻辑、可独立单测）。
"""
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QLabel, QComboBox, QMessageBox

import core.snapshot as snapshot


def attach_snapshot_bar(dialog) -> None:
    """在对话框顶部插入快照工具条。dialog 需具备 self.main_window 属性。"""
    bar = QHBoxLayout()
    bar.addWidget(QLabel("口径:"))
    caliber = QComboBox()
    caliber.addItems(["期间累计", "截至当前累计"])
    caliber.setCurrentText("期间累计")
    bar.addWidget(caliber)
    btn = QPushButton("📸 生成当前快照")
    btn.clicked.connect(lambda: _on_click(dialog, caliber))
    bar.addWidget(btn)
    bar.addStretch(1)

    layout = dialog.layout()
    if layout is not None:
        layout.insertLayout(0, bar)
    dialog._snap_caliber = caliber


def _on_click(dialog, caliber) -> None:
    mw = getattr(dialog, "main_window", None)
    if mw is None:
        QMessageBox.warning(dialog, "提示", "无法获取主窗口数据，无法生成快照。")
        return
    vm = getattr(mw, "view_model", None)
    df = vm.df if vm is not None else None
    if df is None or len(df) == 0:
        QMessageBox.warning(dialog, "提示", "当前主表无数据，无法生成快照。")
        return

    cal = caliber.currentText()
    ctx = _collect_filter_context(mw)
    try:
        score = _collect_score(mw)
        path = snapshot.generate_snapshot(df, cal, meta_context=ctx, score_snapshot=score)
    except Exception as e:  # noqa: BLE001 — 用户可见链路必须暴露错误，不能静默
        QMessageBox.critical(dialog, "快照失败", f"生成快照出错：\n{e}")
        return

    QMessageBox.information(
        dialog, "快照已生成",
        f"已生成本地只读快照：\n{path}\n\n"
        f"口径：{cal}\n系统未推送、未外发，请自行取用。",
    )


def _collect_filter_context(mw):
    """best-effort 收集当前筛选上下文。拿不到就返回空 dict，不报错。"""
    ctx = {}
    try:
        fp = getattr(mw, "filter_panel", None)
        if fp is not None and hasattr(fp, "get_active_filters"):
            ctx["filters"] = fp.get_active_filters()
    except Exception:
        pass
    return ctx


def _collect_score(mw):
    """best-effort 收集评分卡快照（D2 趋势线用）。无可用来源返回 None。

    v43.303 起改用纯逻辑 core.scorecard.compute_scorecard（原 current_score 方法不存在，
    导致历史库评分字段恒为 NULL）。
    """
    try:
        vm = getattr(mw, "view_model", None)
        df = vm.df if vm is not None else None
        if df is not None and len(df):
            from core.scorecard import compute_scorecard
            return compute_scorecard(df)
    except Exception:
        pass
    return None
