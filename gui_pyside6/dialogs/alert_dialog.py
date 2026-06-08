# -*- coding: utf-8 -*-
"""
预警看板对话框 - 仅显示替代料预警，支持标记已读、导出、双击跳转
"""

import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QPoint
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.read_status import save_read_status
from gui_pyside6.widgets.toast import toast


class AlertDialog(QDialog):
    """预警看板对话框 - 替代料偏差预警，支持标记已读"""

    def __init__(self, alerts_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实时预警看板 - 替代料偏差预警")
        self.resize(1200, 600)
        self.main_window = main_window
        self.original_df = alerts_df.copy()  # 备份原始数据（含 _read, data_id）
        self.setup_ui()
        self.set_data(alerts_df)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 表格
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.on_double_click)
        layout.addWidget(self.table_view)

        # 底部按钮
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("📎 导出 Excel")
        export_btn.clicked.connect(self.export_excel)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def set_data(self, df):
        """设置表格数据"""
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)

        # 列宽自适应
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)

        # 隐藏 _read 和 data_id 列
        if '_read' in df.columns:
            col_idx = df.columns.get_loc('_read')
            self.table_view.setColumnHidden(col_idx, True)
        if 'data_id' in df.columns:
            col_idx = df.columns.get_loc('data_id')
            self.table_view.setColumnHidden(col_idx, True)

    def export_excel(self):
        """导出当前预警列表到 Excel"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出预警列表", "替代料预警.xlsx", "Excel files (*.xlsx)")
        if path:
            export_df = self.original_df.drop(columns=['_read', 'data_id'], errors='ignore')
            export_df.to_excel(path, index=False)
            toast(f"已导出 {len(export_df)} 条记录", parent=self)

    def show_context_menu(self, pos: QPoint):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        src_index = self.proxy_model.mapToSource(index)
        row = src_index.row()
        menu = QMenu()
        mark_read_action = menu.addAction("✅ 标记为已读")
        mark_read_action.triggered.connect(lambda: self.mark_row_read(row))
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def mark_row_read(self, row):
        """标记当前行为已读，同步主表格并刷新状态列"""
        df = self.source_model.getDataFrame()
        if row >= len(df):
            return

        # 获取唯一标识 data_id
        data_id = df.iloc[row].get('data_id')
        if not data_id:
            row_series = df.iloc[row]
            data_id = f"{row_series.get('订单日期', '')}|{row_series.get('流程订单', '')}|{row_series.get('物料编码', '')}"

        if not data_id:
            toast("无法定位记录，标记失败", 'error', parent=self)
            return

        # 更新主窗口的 ViewModel 中的 _read 状态
        main_df = self.main_window.view_model.df
        if main_df is not None and 'data_id' in main_df.columns:
            mask = main_df['data_id'] == data_id
            if mask.any():
                idx = main_df[mask].index[0]
                if main_df.at[idx, '_read'] == 1:
                    toast("该记录已是已读状态", parent=self)
                    return
                main_df.at[idx, '_read'] = 1
                fingerprint = main_df.at[idx, 'fingerprint'] if 'fingerprint' in main_df.columns else ''
                save_read_status(data_id, 1, fingerprint)
                # 刷新主表格模型
                self.main_window.source_model.setDataFrame(main_df)
                # 更新看板中当前行的 _read 值和状态列
                df.at[df.index[row], '_read'] = 1
                if '状态' in df.columns:
                    df.at[df.index[row], '状态'] = '✓ 已读'
                self.source_model.setDataFrame(df)
                toast("✅ 已标记为已读", parent=self)
            else:
                toast("未在主数据中找到对应记录", 'error', parent=self)
        else:
            toast("无法更新主表格状态", 'error', parent=self)

    def on_double_click(self, index):
        """双击跳转到主表格"""
        if not index.isValid():
            return
        src_index = self.proxy_model.mapToSource(index)
        row = src_index.row()
        df = self.source_model.getDataFrame()
        if row < len(df):
            record = df.iloc[row]
            self.main_window.locate_record(record)
            self.accept()
