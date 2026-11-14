# -*- coding: utf-8 -*-
"""AI审核结果明细。

AI审核跑完后的落地视图：把「审核结果」按行列出，可按类型 / 已读未读过滤，
双击（或选中后点「定位到主表」）跳到主表对应行。替代掉原先挤在一行里的完成弹窗。
"""
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QTableView,
    QPushButton, QHeaderView, QAbstractItemView,
)

from gui_pyside6.models.data_frame_model import DataFrameModel
from gui_pyside6.utils.locate import locate_row
from gui_pyside6.utils.row_number_gutter import enable_row_numbers

# 明细里要展示的业务列（存在的才显示，缺失自动跳过）
_SHOW_COLS = ["已读/未读", "审核结果", "物料编码", "物料名称", "车间", "偏差率(%)",
              "归因", "建议动作", "候选建议", "备注来源"]
# 定位用、保留在数据里但不展示的列（locate_row 靠 原表行号 / data_id 匹配）
_KEEP_HIDDEN = ["data_id", "原表行号"]
# 常见类别的展示优先级（其余按数据里出现的顺序追加在后）
_CAT_ORDER = ["合格", "需关注", "需改进", "需补备注", "不确定(数据未完结)", "未判定"]


class AiAuditResultDialog(QDialog):
    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._full_df = df.reset_index(drop=True).copy()
        self._cat = "全部"
        self._state = "全部"
        self._ensure_read_label()
        self.setWindowTitle("AI审核结果")
        self.resize(1120, 660)
        # 看板形态：允许标题栏最大化/最小化（构造期、show 前改 flags，避免重建窗口）
        self.setWindowFlags(self.windowFlags()
                            | Qt.WindowMaximizeButtonHint
                            | Qt.WindowMinimizeButtonHint)
        self._build_ui()

    def _ensure_read_label(self):
        """派生「已读/未读」展示列：主表 _read（0/1）没有就默认未读。

        _read 可能是 int、float 或字符串（'0'/'1'），一律先强转数值再判，
        否则 map({1:,0:}) 在字符串上全落空 → 整列被误标成未读，状态筛选失灵。
        """
        if "已读/未读" in self._full_df.columns:
            return
        if "_read" in self._full_df.columns:
            r = pd.to_numeric(self._full_df["_read"], errors="coerce")
            self._full_df["已读/未读"] = np.where(r >= 1, "已读", "未读")
        else:
            self._full_df["已读/未读"] = "未读"

    def _build_ui(self):
        root = QVBoxLayout(self)

        # 顶部：类型 + 已读/未读 过滤 + 当前条数
        top = QHBoxLayout()
        top.addWidget(QLabel("类型:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["全部"] + self._categories())
        self.cat_combo.currentTextChanged.connect(self._on_cat_changed)
        top.addWidget(self.cat_combo)
        top.addWidget(QLabel("  状态:"))
        self.state_combo = QComboBox()
        self.state_combo.addItems(["全部", "未读", "已读"])
        self.state_combo.currentTextChanged.connect(self._on_state_changed)
        top.addWidget(self.state_combo)
        self.cur_lbl = QLabel("")
        top.addWidget(self.cur_lbl)
        top.addStretch()
        top.addWidget(QLabel("双击一行 → 定位到主表对应行"))
        root.addLayout(top)

        # 全量分布：一眼看到各类型各多少条
        self.summary_lbl = QLabel(self._summary_text())
        root.addWidget(self.summary_lbl)

        # 明细表格
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.doubleClicked.connect(self._locate_selected)
        self.source_model = DataFrameModel()
        self.table_view.setModel(self.source_model)
        enable_row_numbers(self.table_view)
        root.addWidget(self.table_view, 1)

        # 底部：定位 + 最大化/还原 + 关闭
        foot = QHBoxLayout()
        btn_locate = QPushButton("定位到主表（选中行）")
        btn_locate.clicked.connect(self._locate_selected)
        foot.addWidget(btn_locate)
        foot.addStretch()
        self._btn_max = QPushButton("最大化")
        self._btn_max.setFixedWidth(72)
        self._btn_max.clicked.connect(self._toggle_maximize)
        foot.addWidget(self._btn_max)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        foot.addWidget(btn_close)
        root.addLayout(foot)

        self._apply()

    def _categories(self):
        if "审核结果" not in self._full_df.columns:
            return []
        vals = [v for v in self._full_df["审核结果"].astype(str).str.strip().unique() if v]
        ordered = [c for c in _CAT_ORDER if c in vals]
        ordered += [v for v in vals if v not in ordered]
        return ordered

    def _summary_text(self):
        total = len(self._full_df)
        if "审核结果" not in self._full_df.columns:
            return f"共 {total} 条"
        vc = (self._full_df["审核结果"].astype(str).str.strip()
              .replace("", "未判定").value_counts())
        dist = " · ".join(f"{k} {v} 条" for k, v in vc.items())
        return f"共 {total} 条：{dist}"

    def _on_cat_changed(self, text):
        self._cat = text
        self._apply()

    def _on_state_changed(self, text):
        self._state = text
        self._apply()

    def _apply(self):
        df = self._full_df
        if self._cat != "全部" and "审核结果" in df.columns:
            df = df[df["审核结果"].astype(str).str.strip() == self._cat]
        if self._state != "全部" and "已读/未读" in df.columns:
            df = df[df["已读/未读"] == self._state]
        df = df.reset_index(drop=True)

        show_cols = [c for c in _SHOW_COLS if c in df.columns]
        keep = [c for c in _KEEP_HIDDEN if c in df.columns]
        slim_cols = [c for c in show_cols + keep if c in df.columns]
        self.source_model.setDataFrame(df[slim_cols])

        # 按模型实际列序隐藏 状态/已读来源 与定位列
        hidden = {"_read", "_read_source"} | set(keep)
        cols = getattr(self.source_model, "_display_columns", None) or slim_cols
        n_cols = self.source_model.columnCount()
        for i, name in enumerate(cols):
            if i < n_cols:
                self.table_view.setColumnHidden(i, name in hidden)

        hh = self.table_view.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setStretchLastSection(True)

        parts = [p for p in (self._cat, self._state) if p != "全部"]
        label = " / ".join(parts) if parts else "全部"
        self.cur_lbl.setText(f"{label}：{len(df)} 条")

    def _locate_selected(self, _index=None):
        """定位到主表对应行：双击传 QModelIndex，按钮走当前选中行。"""
        df = self.source_model.getDataFrame()
        if df is None or len(df) == 0:
            return
        if _index is not None and hasattr(_index, "row"):
            row = _index.row()
        else:
            sel = self.table_view.selectionModel()
            rows = [ix.row() for ix in (sel.selectedIndexes() if sel else [])]
            row = rows[0] if rows else self.table_view.currentIndex().row()
        if row is None or row < 0 or row >= len(df):
            return
        locate_row(self.main_window, df.iloc[row], parent=self, link_source="AI审核")

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        # 标题栏最大化/还原也同步按钮文字，别出现按钮和窗口状态不一致
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "_btn_max"):
            self._btn_max.setText("还原" if self.isMaximized() else "最大化")
