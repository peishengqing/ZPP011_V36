# -*- coding: utf-8 -*-
"""
预警明细对话框
显示超阈值偏差的详细信息
裴哥 | 2026-06-05
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView
from PySide6.QtCore import Qt


class AlertDialog(QDialog):
    """预警明细对话框"""

    def __init__(self, alerts_df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ 预警明细")
        self.resize(900, 500)

        # 过滤掉内部使用的列
        display_cols = [c for c in alerts_df.columns if not c.startswith('_')]
        df = alerts_df[display_cols].copy()

        layout = QVBoxLayout(self)

        # 表格
        self.table = QTableWidget(len(df), len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns.tolist())

        for i, row in df.iterrows():
            for j, col in enumerate(df.columns):
                item = QTableWidgetItem(str(row[col]))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 只读
                self.table.setItem(i, j, item)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
