# -*- coding: utf-8 -*-
"""
按单位汇总弹窗
"""
import pandas as pd
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QMessageBox


class UnitSummaryDialog(QDialog):
    def __init__(self, parent, df):
        super().__init__(parent)
        self.setWindowTitle("按单位汇总")
        self.resize(600, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._load_data(df)

    def _load_data(self, df):
        if df.empty:
            self.text_edit.setText("无数据")
            return
        # 查找单位列
        unit_col = None
        for c in df.columns:
            if '单位' in str(c) or 'unit' in str(c).lower():
                unit_col = c
                break
        if not unit_col:
            QMessageBox.warning(self, "提示", "数据中未找到单位列")
            self.text_edit.setText("无法按单位汇总：未找到单位列")
            return

        quota_col = next((c for c in ['定额', '数量-定额', 'quota'] if c in df.columns), None)
        actual_col = next((c for c in ['实际', '数量-实际', 'actual'] if c in df.columns), None)
        amount_col = next((c for c in ['偏差金额', '偏差金额(含税)', 'deviation_amount'] if c in df.columns), None)
        qty_col = next((c for c in ['偏差数量', '数量偏差', 'dev_qty'] if c in df.columns), None)

        groups = df.groupby(unit_col)
        lines = []
        for unit, group in groups:
            quota_sum = pd.to_numeric(group[quota_col], errors='coerce').fillna(0).sum() if quota_col else 0
            actual_sum = pd.to_numeric(group[actual_col], errors='coerce').fillna(0).sum() if actual_col else 0
            amount_sum = pd.to_numeric(group[amount_col], errors='coerce').fillna(0).sum() if amount_col else 0
            if qty_col:
                qty_sum = pd.to_numeric(group[qty_col], errors='coerce').fillna(0).sum()
            elif actual_col and quota_col:
                qty_sum = (pd.to_numeric(group[actual_col], errors='coerce').fillna(0) -
                           pd.to_numeric(group[quota_col], errors='coerce').fillna(0)).sum()
            else:
                qty_sum = 0
            lines.append(
                f"单位 {unit}：定额 {quota_sum:,.2f}，实际 {actual_sum:,.2f}，"
                f"偏差金额 {amount_sum:,.2f}，偏差数量 {qty_sum:,.2f}"
            )
        if not lines:
            lines = ["无有效分组数据"]
        self.text_edit.setText("\n".join(lines))
