# -*- coding: utf-8 -*-
"""
PySide6 最小 Demo — 验证 QTableView + pandas DataFrame 可行性
阶段0交付物：验证 PySide6 基本功能是否正常
"""
import sys
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QVBoxLayout, QWidget,
    QLabel, QHeaderView
)
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class DataFrameModel(QAbstractTableModel):
    """将 pandas DataFrame 桥接到 QTableView 的 Model"""

    def __init__(self, data: pd.DataFrame):
        super().__init__()
        self._data = data

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            row = index.row()
            col = index.column()
            value = self._data.iloc[row, col]
            return str(value) if pd.notna(value) else ""
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._data.columns[section])
        return str(section + 1)


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZPP011 PySide6 Demo — 阶段0验证")
        self.resize(900, 600)

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)

        # 标题
        title = QLabel("✅ PySide6 QTableView 最小验证 Demo")
        title.setStyleSheet("font-size: 18px; padding: 10px;")

        # 表格
        self.table_view = QTableView()
        self.model = DataFrameModel(self._make_demo_data())
        self.table_view.setModel(self.model)

        # 表头自适应
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 启用排序
        self.table_view.setSortingEnabled(True)

        # 布局
        layout = QVBoxLayout(central)
        layout.addWidget(title)
        layout.addWidget(self.table_view)

    @staticmethod
    def _make_demo_data() -> pd.DataFrame:
        return pd.DataFrame({
            "订单日期": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "物料编码": ["M001", "M002", "M003"],
            "物料名称": ["白糖", "面粉", "食用油"],
            "偏差率(%)": [3.2, 8.5, 15.0],
            "审核结果": ["合格", "需关注", "需补备注"],
            "备注": ["", "", "用量异常"],
        })


def run_demo():
    app = QApplication(sys.argv)
    win = DemoWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_demo()
