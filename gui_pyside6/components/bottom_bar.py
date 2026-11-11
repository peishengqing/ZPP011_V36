# -*- coding: utf-8 -*-
"""底部状态条 —— v43.349 第五期F：照抄设计稿 .status-bar（单行 30px）

改造前主窗口有**两条**状态条叠在一起：
  · 本组件（30px，记录/选中/偏差合计/未读）挂在中央布局最下方；
  · QMainWindow 原生 QStatusBar 挂着「分析时间 / 已读计数 / 列头筛选 / 版本号」四个常驻标签。
设计稿只有一根 30px 的 .status-bar，两条既多吃 30px 高度，又是两份字号两份底色。

本版并成一条：本组件直接**就是**主窗口的状态栏（main_window 里 setStatusBar），
  · 左半 = 高频指标：状态点 + 状态文字 + 已选 n / N 行 + 偏差合计 + 未读；
  · 右半 = 低频信息：原生 addPermanentWidget 的那四个标签（等价 .status-right{margin-left:auto}）；
  · 「选中合计 / 已复制…」这类瞬时提示仍走 QStatusBar.showMessage：显示期间整行指标
    让位给提示文本，超时自动回来（Qt 原生行为，无需自己管）。

数字一律用 FONT_NUM 等宽 + 主文本色（设计稿 .status-bar b），文字标签用 text-muted；
状态点用「7px 实心 + 3px 同色淡环」（.status-dot），三档：idle 灰 / ok 绿 / warn 琥珀。
偏差合计的正负色沿用现行口径：超投（正）红、节约（负）绿。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStatusBar, QWidget

import pandas as pd

from gui_pyside6.themes.tokens import SIZE_PX

# 状态点三档（对应 QSS 里 QFrame#statusDot[dotState=...]）
_IDLE = ("idle", "等待导入数据")
_OK = ("ok", "分析完成")
_WARN = ("warn", "分析完成 · 有待读")


class BottomBarComponent(QStatusBar):
    """主窗口唯一的底部状态条（同时是 QMainWindow 的 statusBar）。"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.setObjectName("bottomStatusBar")
        self.setFixedHeight(SIZE_PX["statusBar"])
        self.setSizeGripEnabled(False)      # 设计稿这根条没有拖拽角
        self.setContentsMargins(12, 0, 12, 0)

        row = QWidget()
        row.setObjectName("bottomStatusRow")
        # 裸 QWidget 要吃 QSS 必须开这个属性（本项目通用坑）
        row.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)                  # 设计稿 .status-bar{gap:14px}

        self.dot = QFrame()
        self.dot.setObjectName("statusDot")
        self.dot.setFixedSize(13, 13)       # 7px 实心 + 3px 淡环
        self.dot.setProperty("dotState", _IDLE[0])
        self.dot.setAttribute(Qt.WA_StyledBackground, True)
        lay.addWidget(self.dot)

        self.lbl_state = self._mk_label(lay, _IDLE[1])
        self.lbl_selected = self._mk_metric(lay, "已选", "0", "行")
        self.lbl_records = self._mk_metric(lay, "共", "--", "行")
        self.lbl_deviation = self._mk_metric(lay, "偏差合计", "--")
        self.lbl_unread = self._mk_metric(lay, "未读", "--")
        lay.addStretch(1)                   # 右端留给 addPermanentWidget 的低频标签

        # 指标整体放正常区并占满宽度；瞬时提示出现时由 QStatusBar 临时接管这一段
        self.addWidget(row, 1)

    # ── 构造小件 ──────────────────────────────────────────────────
    def _mk_label(self, layout, text, value=False):
        lbl = QLabel(text)
        lbl.setObjectName("bottomStatusValue" if value else "bottomStatusLabel")
        lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(lbl)
        return lbl

    def _mk_metric(self, layout, prefix, value, suffix=""):
        """一条指标 = 前缀(灰) + 数值(等宽加粗) + 可选单位(灰)，组内间距 4px。"""
        item = QWidget()
        item.setObjectName("bottomStatusItem")
        item.setAttribute(Qt.WA_StyledBackground, True)
        g = QHBoxLayout(item)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(4)
        self._mk_label(g, prefix)
        val = self._mk_label(g, value, value=True)
        g.addWidget(val)
        if suffix:
            self._mk_label(g, suffix)
        layout.addWidget(item)
        return val

    # ── 公开更新接口（签名与旧版一致，调用方无需改动）──────────────
    def set_records(self, n):
        self.lbl_records.setText(self._fmt_int(n))
        # 操作栏右端「共 N 条」与本条同源刷新，避免两处条数各说各话
        hint = getattr(self.mw, "action_hint_count", None)
        if hint is not None:
            hint.setText("—" if not isinstance(n, int) else f"{n:,}")
        self._sync_state()

    def set_selected(self, n):
        self.lbl_selected.setText(self._fmt_int(n))

    def set_deviation(self, text: str):
        self.lbl_deviation.setText(text)
        # 超投（正）红、节约（负）绿 —— 与表格偏差列、看板红绿语言同一口径
        try:
            val = float(text.replace("¥", "").replace("万", "").replace(",", "").lstrip("+"))
        except (TypeError, ValueError):
            val = 0.0
        self._set_property(self.lbl_deviation, "sign",
                           "neg" if val < 0 else ("pos" if val > 0 else "flat"))

    def set_unread(self, n):
        self.lbl_unread.setText(self._fmt_int(n))
        self._sync_state()

    # ── 状态点 ────────────────────────────────────────────────────
    def _sync_state(self):
        """由「共 N 行 / 未读 n」推出状态点：未加载=灰、有待读=琥珀、全部已读=绿。"""
        total = self._parse_int(self.lbl_records.text())
        if not total:
            self._set_state(_IDLE)
            return
        unread = self._parse_int(self.lbl_unread.text())
        self._set_state(_WARN if unread else _OK)

    def _set_state(self, state):
        key, text = state
        self.lbl_state.setText(text)
        self._set_property(self.dot, "dotState", key)

    @staticmethod
    def _set_property(widget, name, value):
        """动态属性变色必须 unpolish/polish 走一遍，否则 QSS 不重算。"""
        if widget.property(name) == value:
            return
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    @staticmethod
    def _fmt_int(n):
        return "—" if not isinstance(n, int) else f"{n:,}"

    @staticmethod
    def _parse_int(text):
        try:
            return int(str(text).replace(",", ""))
        except (TypeError, ValueError):
            return 0

    # ── 数据驱动刷新 ──────────────────────────────────────────────
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
