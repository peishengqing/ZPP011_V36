# -*- coding: utf-8 -*-
"""底部状态条组件（v43.337 复活，设计稿第6项）

旧版 BottomBarComponent 承载「运行日志面板」，后因日志功能确认不再需要而沦为
空壳（只占位、不创建任何 widget，MainWindow.log() 为空操作）。

本版复活为**常驻状态条**，显示三类关键信息（与审阅/核对工作流高度相关）：
  · 记录总数         —— 当前主表数据条数
  · 选中行数         —— 随表格 selectionChanged 实时刷新
  · 偏差合计         —— 净偏差金额列求和（万元/元自适应）
  · 未读             —— 主表 _read==0 的条数

与 QMainWindow 原生 statusBar（仅显示临时提示，如「已复制…/选中合计」）并存、
互不干扰：原生 statusBar 仍负责瞬态消息，本组件负责常驻指标。
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

import pandas as pd


class BottomBarComponent(QWidget):
    """常驻底部状态条（v43.337）。self 本身即 QWidget，可直接 addWidget 到布局。"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.setObjectName("bottomStatusBar")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(18)

        self.lbl_records = self._mk(layout, "记录：--")
        self.lbl_selected = self._mk(layout, "选中：0")
        self.lbl_deviation = self._mk(layout, "偏差合计：--")
        self.lbl_unread = self._mk(layout, "未读：--")

        layout.addStretch(1)
        # 右侧预留一个版本/模式标签位（接入点，待后续填充）
        self.lbl_mode = self._mk(layout, "")
        self.lbl_mode.setVisible(False)

    @staticmethod
    def _mk(layout: QHBoxLayout, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("bottomStatusLabel")
        lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(lbl)
        return lbl

    # ── 公开更新接口 ──

    def set_records(self, n):
        self.lbl_records.setText(f"记录：{n}")

    def set_selected(self, n):
        self.lbl_selected.setText(f"选中：{n}")

    def set_deviation(self, text: str):
        self.lbl_deviation.setText(f"偏差合计：{text}")

    def set_unread(self, n):
        self.lbl_unread.setText(f"未读：{n}")

    def set_mode(self, text: str):
        if text:
            self.lbl_mode.setText(text)
            self.lbl_mode.setVisible(True)
        else:
            self.lbl_mode.setVisible(False)

    def refresh_from_df(self, df):
        """根据当前主表 DataFrame 刷新记录总数 / 偏差合计 / 未读。"""
        if df is None or getattr(df, "empty", True):
            self.set_records("--")
            self.set_deviation("--")
            self.set_unread("--")
            return

        self.set_records(len(df))

        # 偏差合计：净偏差金额列求和（万元 / 元自适应）
        amt_col = next(
            (c for c in ("净偏差金额", "偏差金额(含税)", "偏差金额") if c in df.columns),
            None,
        )
        if amt_col:
            total = pd.to_numeric(df[amt_col], errors="coerce").fillna(0).sum()
            if abs(total) >= 10000:
                self.set_deviation(f"¥{total / 10000:.1f}万")
            else:
                self.set_deviation(f"¥{total:.0f}")
        else:
            self.set_deviation("--")

        # 未读：主表 _read 列为 0 的条数
        if "_read" in df.columns:
            self.set_unread(int((df["_read"] == 0).sum()))
        else:
            self.set_unread("--")
