# -*- coding: utf-8 -*-
"""
隔离区对话框 - 列出已隔离的疑难数据，支持取消隔离、查看明细、双击定位主表
"""
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel,
)
from PySide6.QtCore import Qt, QPoint
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import remove_quarantine
from gui_pyside6.widgets.toast import toast

_HIDDEN_INTERNAL = ['_read', 'data_id', '_quarantined', '_post_audit_changed', 'fingerprint']


class QuarantineDialog(QDialog):
    """隔离区对话框 - 疑难数据暂存区，支持取消隔离 / 双击定位"""

    def __init__(self, quarantine_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("隔离区 - 疑难数据暂存")
        self.resize(1200, 600)
        self.main_window = main_window
        self.setup_ui()
        self.set_data(quarantine_df)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel("以下数据被标记为「疑难待处理」。修改主表后重新导入，隔离区记录会同步更新（引用模式，仅按 data_id 关联，不存副本）。")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.installEventFilter(self)
        layout.addWidget(self.table_view)

        btn_layout = QHBoxLayout()
        self.btn_restore = QPushButton("↩ 取消隔离（选中行）")
        self.btn_restore.clicked.connect(self.batch_restore)
        btn_layout.addWidget(self.btn_restore)

        export_btn = QPushButton("📎 导出 Excel")
        export_btn.clicked.connect(self.export_excel)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def set_data(self, df):
        df = df.copy()
        if "_read" not in df.columns:
            df["_read"] = 0
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        for col in _HIDDEN_INTERNAL:
            if col in df.columns:
                self.table_view.setColumnHidden(df.columns.get_loc(col), True)

    def show_context_menu(self, pos: QPoint):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        selection_model = self.table_view.selectionModel()
        selected_rows = sorted(set(idx.row() for idx in selection_model.selectedIndexes()))
        if not selected_rows:
            selected_rows = [index.row()]
        menu = QMenu()
        restore_action = menu.addAction("↩ 取消隔离（选中行）")
        restore_action.triggered.connect(lambda: self._restore_rows(selected_rows))
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _restore_rows(self, rows):
        df = self.source_model.getDataFrame()
        if df is None:
            return
        ids = set()
        for r in rows:
            if r >= len(df):
                continue
            uid = df.iloc[r].get('data_id')
            if uid:
                ids.add(str(uid))
        if not ids:
            return
        for uid in ids:
            remove_quarantine(uid)
        count = len(ids)
        # 回写主表内存 + 重建模型 + 刷新卡片
        if self.main_window and hasattr(self.main_window, 'view_model'):
            main_df = self.main_window.view_model.df
            if main_df is not None and 'data_id' in main_df.columns and '_quarantined' in main_df.columns:
                mask = main_df['data_id'].isin(ids)
                main_df.loc[mask, '_quarantined'] = 0
                self.main_window.view_model.df = main_df
                if hasattr(self.main_window, 'source_model') and self.main_window.source_model:
                    self.main_window.source_model.setDataFrame(main_df)
                    if hasattr(self.main_window, '_apply_column_visibility_by_name'):
                        self.main_window._apply_column_visibility_by_name()
        if self.main_window and hasattr(self.main_window, 'stats_cards'):
            self.main_window.stats_cards.refresh(self.main_window.view_model.df)
        self._refresh_self()
        toast(f"↩ 已取消隔离 {count} 条", parent=self)

    def batch_restore(self):
        selection_model = self.table_view.selectionModel()
        if not selection_model or not selection_model.hasSelection():
            toast("请先选中要取消隔离的行", 'info', parent=self)
            return
        rows = sorted(set(idx.row() for idx in selection_model.selectedIndexes()))
        self._restore_rows(rows)

    def _refresh_self(self):
        if self.main_window and hasattr(self.main_window, 'view_model'):
            df = self.main_window.view_model.df
            if df is not None and '_quarantined' in df.columns:
                qdf = df[df['_quarantined'] == 1].copy().reset_index(drop=True)
                self.set_data(qdf)

    def on_double_click(self, index):
        if not index.isValid():
            return
        df = self.source_model.getDataFrame()
        if index.row() >= len(df):
            return
        record = df.iloc[index.row()]
        try:
            self.main_window.locate_record(record)
        except (AttributeError, Exception):
            pass
        self.accept()

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出隔离区列表", "隔离区数据.xlsx", "Excel files (*.xlsx)")
        if path:
            export_df = self.source_model.getDataFrame().drop(columns=_HIDDEN_INTERNAL, errors='ignore')
            export_df.to_excel(path, index=False)
            toast(f"已导出 {len(export_df)} 条记录", parent=self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeySequence
        if obj is self.table_view and event.type() == QEvent.KeyPress:
            if event.matches(QKeySequence.Copy):
                self._copy_selected_cells()
                return True
        return super().eventFilter(obj, event)

    def _copy_selected_cells(self):
        from PySide6.QtWidgets import QApplication
        selection = self.table_view.selectionModel()
        if not selection or not selection.hasSelection():
            return
        indexes = selection.selectedIndexes()
        cells = {}
        min_row, max_row = float('inf'), -1
        min_col, max_col = float('inf'), -1
        for idx in indexes:
            r, c = idx.row(), idx.column()
            val = idx.data(Qt.DisplayRole) or ""
            cells[(r, c)] = str(val).replace("\n", " ").replace("\r", "")
            min_row = min(min_row, r); max_row = max(max_row, r)
            min_col = min(min_col, c); max_col = max(max_col, c)
        if max_row < 0:
            return
        lines = []
        for r in range(min_row, max_row + 1):
            lines.append("\t".join(cells.get((r, c), "") for c in range(min_col, max_col + 1)))
        QApplication.clipboard().setText("\n".join(lines))
