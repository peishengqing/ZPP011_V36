#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""替换 gui_pyside6/dialogs/alert_dialog.py 为新版本（支持双击定位）"""

new_content = '''# -*- coding: utf-8 -*-
"""
预警看板对话框
显示所有超阈值偏差记录，双击可定位到主表格
裴哥 | 2026-06-08
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableView, QHeaderView, QPushButton, QAbstractItemView
from PySide6.QtCore import Qt, QSortFilterProxyModel
from gui_pyside6.models.data_frame_model import DataFrameModel


class AlertDialog(QDialog):
    """预警看板对话框"""

    def __init__(self, alerts_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实时预警看板")
        self.resize(900, 500)
        self.main_window = main_window

        layout = QVBoxLayout(self)

        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table_view)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._set_data(alerts_df)

    def _set_data(self, df):
        """设置表格数据"""
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _on_double_click(self, index):
        """双击某行，定位到主表格对应记录"""
        if not index.isValid():
            return
        src_index = self.proxy_model.mapToSource(index)
        row = src_index.row()
        df = self.source_model.getDataFrame()
        if row < len(df):
            record = df.iloc[row]
            self.main_window.locate_record(record)
            self.accept()
'''

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\dialogs\alert_dialog.py"
with open(fp, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Done! Replaced alert_dialog.py with new version")
print(f"File: {fp}")
