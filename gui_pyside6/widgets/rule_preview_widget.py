# -*- coding: utf-8 -*-
"""规则中心 · 条件卡 + 只读命中预览（第四期 / 影子模式，v43.341）

规则语义：
  · 组内 OR   —— 同一条件组里任意一条命中即算该组命中
  · 组间 AND  —— 所有条件组都命中，该行才算最终命中

只读边界（硬约束）：只在传入的 pandas DataFrame 上算布尔掩码，
不写 rules.json、不改数据、不触发自动隔离 / 自动已读、不调用任何保存接口。
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox, QLineEdit,
    QPushButton, QLabel, QTableView, QScrollArea,
)

import pandas as pd

from gui_pyside6.models.data_frame_model import DataFrameModel

_OPS = ("包含", "等于", "不等于", "大于", "小于", "为空", "非空")
_PREVIEW_ROWS = 50


class _ConditionRow(QWidget):
    """一行条件：列 / 运算符 / 值 / 删除。"""

    def __init__(self, columns, group):
        super().__init__()
        self.col = QComboBox()
        self.col.addItems(columns)
        self.op = QComboBox()
        self.op.addItems(_OPS)
        self.val = QLineEdit()
        self.val.setPlaceholderText("值（大于/小于按数值比较）")
        remove_btn = QPushButton("×")
        remove_btn.setFixedWidth(26)
        remove_btn.setToolTip("删除本条件")
        remove_btn.clicked.connect(lambda: group.remove_row(self))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self.col, 2)
        lay.addWidget(self.op, 1)
        lay.addWidget(self.val, 2)
        lay.addWidget(remove_btn)

    def set_columns(self, columns):
        current = self.col.currentText()
        self.col.clear()
        self.col.addItems(columns)
        idx = self.col.findText(current)
        if idx >= 0:
            self.col.setCurrentIndex(idx)

    def evaluate(self, df):
        """返回该条件对 df 的布尔掩码；列不存在或值非法时保守返回全 False。"""
        col, op, val = self.col.currentText(), self.op.currentText(), self.val.text().strip()
        if col not in df.columns:
            return pd.Series(False, index=df.index)
        series = df[col]
        blank = series.isna() | series.astype(str).str.strip().eq("")
        if op == "为空":
            return blank
        if op == "非空":
            return ~blank
        if op in ("大于", "小于"):
            numeric = pd.to_numeric(series, errors="coerce")
            try:
                target = float(val)
            except (TypeError, ValueError):
                return pd.Series(False, index=df.index)
            return numeric > target if op == "大于" else numeric < target
        text = series.astype(str)
        if op == "包含":
            return text.str.contains(val, case=False, na=False, regex=False)
        if op == "等于":
            return text.str.strip().eq(val)
        return ~text.str.strip().eq(val)  # 不等于


class _ConditionGroup(QGroupBox):
    """一个条件组（组内 OR）。空组视为恒真，不参与过滤。"""

    def __init__(self, index, columns):
        super().__init__("条件组 %d（组内 OR）" % index)
        self._columns = columns
        self._rows = []
        outer = QVBoxLayout(self)
        outer.setSpacing(4)
        self.rows_layout = QVBoxLayout()
        outer.addLayout(self.rows_layout)
        add_btn = QPushButton("+ 添加条件")
        add_btn.clicked.connect(lambda: self.add_row())
        outer.addWidget(add_btn)
        self.add_row()

    def add_row(self):
        row = _ConditionRow(self._columns, self)
        self.rows_layout.addWidget(row)
        self._rows.append(row)

    def remove_row(self, row):
        if row in self._rows:
            self._rows.remove(row)
            row.setParent(None)
            row.deleteLater()

    def set_columns(self, columns):
        self._columns = columns
        for row in self._rows:
            row.set_columns(columns)

    def evaluate(self, df):
        if not self._rows:
            return pd.Series(True, index=df.index)
        result = pd.Series(False, index=df.index)
        for row in self._rows:
            result = result | row.evaluate(df)
        return result


class RulePreviewWidget(QWidget):
    """规则中心第三个 Tab：条件卡编排 + 真实命中预览（只读）。"""

    def __init__(self, df=None, parent=None):
        super().__init__(parent)
        self.df = df if df is not None else pd.DataFrame()
        self._groups = []
        self._model = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        note = QLabel(
            "影子模式 · 只读预览：组内条件 OR、多个条件组之间 AND。"
            "仅对当前主表内存数据计算命中，不写入规则文件、不修改数据、"
            "不触发自动隔离 / 自动已读。")
        note.setWordWrap(True)
        note.setObjectName("rulePreviewNote")
        root.addWidget(note)

        self.groups_host = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_host)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.groups_host)
        scroll.setMinimumHeight(170)
        root.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        self.btn_add_group = QPushButton("+ 条件组（组间 AND）")
        self.btn_add_group.clicked.connect(self.add_group)
        self.btn_eval = QPushButton("计算命中")
        self.btn_eval.setObjectName("rulePreviewEval")
        self.btn_eval.clicked.connect(self.evaluate)
        btn_row.addWidget(self.btn_add_group)
        btn_row.addWidget(self.btn_eval)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self.result = QLabel("尚未计算 · 添加条件后点「计算命中」")
        self.result.setObjectName("rulePreviewResult")
        root.addWidget(self.result)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        self.add_group()

    def _columns(self):
        return [str(c) for c in self.df.columns]

    def set_df(self, df):
        """切换数据源（主表刷新后可再调），同步刷新各条件行的列下拉。"""
        self.df = df if df is not None else pd.DataFrame()
        columns = self._columns()
        for group in self._groups:
            group.set_columns(columns)

    def add_group(self):
        group = _ConditionGroup(len(self._groups) + 1, self._columns())
        self._groups.append(group)
        self.groups_layout.addWidget(group)
        return group

    def evaluate(self):
        """按「组间 AND / 组内 OR」算掩码，并把命中前 50 行喂进只读预览表。"""
        df = self.df
        if df is None or df.empty:
            self.result.setText("当前主表无数据，无法预览")
            return None
        mask = pd.Series(True, index=df.index)
        for group in self._groups:
            mask = mask & group.evaluate(df)
        hit = df[mask]
        shown = min(_PREVIEW_ROWS, len(hit))
        self.result.setText("命中 %d / 共 %d 条 · 预览前 %d 行 · 只读" % (
            len(hit), len(df), shown))
        model = DataFrameModel()
        model.setDataFrame(hit.head(_PREVIEW_ROWS).reset_index(drop=True))
        self.table.setModel(model)
        self._model = model  # 保活，避免 Python 侧被 GC 后视图空表
        return mask
