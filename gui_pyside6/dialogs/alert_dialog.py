# -*- coding: utf-8 -*-
"""
替代料看板对话框 - 仅显示替代料预警，支持标记已读、导出、双击跳转
"""

import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel,
)
from PySide6.QtCore import Qt, QPoint
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.read_status import save_read_status, save_read_status_batch
from gui_pyside6.services.data_service import snapshot_qty_for
from gui_pyside6.widgets.toast import toast


class AlertDialog(QDialog):
    """替代料看板对话框 - 替代料偏差预警，支持标记已读"""

    def __init__(self, alerts_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实时替代料看板 - 替代料偏差预警")
        self.resize(1200, 600)
        self.main_window = main_window
        self.original_df = alerts_df.copy()
        self.filter_mode = "all"
        self.setup_ui()
        self.set_data(alerts_df)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ---- 顶部筛选栏 ----
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))

        self.btn_all = QPushButton("全部")
        self.btn_all.setCheckable(True)
        self.btn_all.setChecked(True)
        self.btn_all.clicked.connect(lambda: self._set_filter("all"))
        filter_layout.addWidget(self.btn_all)

        self.btn_unread = QPushButton("未读")
        self.btn_unread.setCheckable(True)
        self.btn_unread.clicked.connect(lambda: self._set_filter("unread"))
        filter_layout.addWidget(self.btn_unread)

        self.btn_read = QPushButton("已读")
        self.btn_read.setCheckable(True)
        self.btn_read.clicked.connect(lambda: self._set_filter("read"))
        filter_layout.addWidget(self.btn_read)

        filter_layout.addStretch()

        # 批量操作
        self.btn_batch_read = QPushButton("批量标记已读")
        self.btn_batch_read.clicked.connect(self.batch_mark_read)
        filter_layout.addWidget(self.btn_batch_read)

        self.btn_batch_unread = QPushButton("批量标记未读")
        self.btn_batch_unread.clicked.connect(self.batch_mark_unread)
        filter_layout.addWidget(self.btn_batch_unread)

        # 放大按钮
        self.btn_fullscreen = QPushButton("⛶ 放大")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        filter_layout.addWidget(self.btn_fullscreen)

        layout.addLayout(filter_layout)

        # ---- 表格 ----
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(True)  # 允许点击列头排序
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        # 安装 Ctrl+C 复制事件过滤器
        self.table_view.installEventFilter(self)
        layout.addWidget(self.table_view)

        # ---- 底部按钮 ----
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("📎 导出 Excel")
        export_btn.clicked.connect(self.export_excel)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _set_filter(self, mode):
        self.filter_mode = mode
        self.btn_all.setChecked(mode == "all")
        self.btn_unread.setChecked(mode == "unread")
        self.btn_read.setChecked(mode == "read")
        self._apply_filter()

    def _apply_filter(self):
        """从 original_df 重新过滤并刷新模型"""
        if not hasattr(self, "original_df") or self.original_df is None:
            return
        df = self.original_df.copy()
        if df.empty:
            return

        if "_read" not in df.columns:
            df["_read"] = 0

        if self.filter_mode == "unread":
            filtered = df[df["_read"] == 0].copy()
        elif self.filter_mode == "read":
            filtered = df[df["_read"] == 1].copy()
        else:
            filtered = df.copy()

        filtered = filtered.reset_index(drop=True)
        self.source_model.setDataFrame(filtered)

    def set_data(self, df):
        """设置表格数据 - 确保 _read 和 data_id 列存在"""
        df = df.copy()
        if "_read" not in df.columns:
            df["_read"] = 0
        if "data_id" not in df.columns:
            if all(c in df.columns for c in ["订单日期", "流程订单", "物料编码"]):
                df["data_id"] = (
                    df["订单日期"].astype(str) + "|" +
                    df["流程订单"].astype(str) + "|" +
                    df["物料编码"].astype(str)
                )
        self.original_df = df.copy()

        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)

        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)

        if '_read' in df.columns:
            col_idx = df.columns.get_loc('_read')
            self.table_view.setColumnHidden(col_idx, True)
        if 'data_id' in df.columns:
            col_idx = df.columns.get_loc('data_id')
            self.table_view.setColumnHidden(col_idx, True)

    def export_excel(self):
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
        row = index.row()

        # 兼容 SelectItems 模式：从所有选中索引提取唯一行号
        selection_model = self.table_view.selectionModel()
        selected_indexes = selection_model.selectedIndexes()
        selected_rows = list(set(idx.row() for idx in selected_indexes))
        # 如果右键的行不在选中范围内，清空选择只选这一行
        if row not in selected_rows:
            self.table_view.clearSelection()
            self.table_view.selectRow(row)
            selected_rows = [row]

        menu = QMenu()
        mark_read_action = menu.addAction("✅ 标记为已读（选中行）")
        mark_read_action.triggered.connect(
            lambda: self._mark_selected_rows_read(selected_rows)
        )
        mark_unread_action = menu.addAction("⭕ 标记为未读（选中行）")
        mark_unread_action.triggered.connect(
            lambda: self._mark_selected_rows_unread(selected_rows)
        )
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _mark_selected_rows_read(self, rows):
        """标记所有选中行为已读（右键菜单）"""
        df = self.source_model.getDataFrame()
        if df is None:
            return
        records = []
        changed_ids = set()
        count = 0
        for r in rows:
            if r >= len(df):
                continue
            data_id = df.iloc[r].get('data_id')
            if not data_id:
                rs = df.iloc[r]
                if '工厂' in df.columns:
                    data_id = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
                else:
                    data_id = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            if not data_id:
                continue
            ok, already, fingerprint = self._sync_main_df(data_id, 1)
            if ok and not already:
                qty = snapshot_qty_for(df, data_id)
                records.append((data_id, 1, fingerprint, qty))
                changed_ids.add(data_id)
                count += 1
        if records:
            save_read_status_batch(records)
        self._refresh_main_table_once()
        if changed_ids and hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'].isin(changed_ids)
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 1
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '✓ 已读'
        self._apply_filter()
        toast(f"✅ 已标记 {count} 条为已读", parent=self)

    def _mark_selected_rows_unread(self, rows):
        """标记所有选中行为未读（右键菜单）"""
        df = self.source_model.getDataFrame()
        if df is None:
            return
        records = []
        changed_ids = set()
        count = 0
        for r in rows:
            if r >= len(df):
                continue
            data_id = df.iloc[r].get('data_id')
            if not data_id:
                rs = df.iloc[r]
                if '工厂' in df.columns:
                    data_id = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
                else:
                    data_id = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            if not data_id:
                continue
            ok, already, fingerprint = self._sync_main_df(data_id, 0)
            if ok and not already:
                qty = snapshot_qty_for(df, data_id)
                records.append((data_id, 0, fingerprint, qty))
                changed_ids.add(data_id)
                count += 1
        if records:
            save_read_status_batch(records)
        self._refresh_main_table_once()
        if changed_ids and hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'].isin(changed_ids)
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 0
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '○ 未读'
        self._apply_filter()
        toast(f"⭕ 已标记 {count} 条为未读", parent=self)

    def _sync_main_df(self, data_id, read_value):
        """同步主表内存中的已读状态（仅改内存，不做落盘和 UI 重建）

        在循环内调用，避免逐行重建主表模型（setDataFrame 会重建全量缓存，开销大）。
        落盘与 UI 重建由调用方在循环外统一做一次。
        返回 (success, already_status, fingerprint)
        """
        main_df = self.main_window.view_model.df
        if main_df is None:
            return False, False, ''

        # 确保主表有 data_id（不覆盖已有的 data_id，避免和 data_service 格式不一致）
        if 'data_id' not in main_df.columns:
            if '工厂' in main_df.columns:
                main_df['data_id'] = (
                    main_df['工厂'].astype(str) + '|' +
                    main_df['订单日期'].astype(str) + '|' +
                    main_df['流程订单'].astype(str) + '|' +
                    main_df['物料编码'].astype(str)
                )
            elif all(c in main_df.columns for c in ['订单日期', '流程订单', '物料编码']):
                main_df['data_id'] = (
                    main_df['订单日期'].astype(str) + "|" +
                    main_df['流程订单'].astype(str) + "|" +
                    main_df['物料编码'].astype(str)
                )
            else:
                return False, False, ''
            self.main_window.view_model.df = main_df

        if 'data_id' not in main_df.columns:
            return False, False, ''

        if '_read' not in main_df.columns:
            main_df['_read'] = 0
            self.main_window.view_model.df = main_df

        mask = main_df['data_id'] == data_id
        if not mask.any():
            return False, False, ''
        idx = main_df[mask].index[0]
        current_val = main_df.at[idx, '_read']
        if current_val == read_value:
            return True, True, ''  # 已经是目标状态
        main_df.at[idx, '_read'] = read_value
        fingerprint = main_df.at[idx, 'fingerprint'] if 'fingerprint' in main_df.columns else ''
        self.main_window.view_model.df = main_df
        return True, False, fingerprint

    def _refresh_main_table_once(self):
        """循环外统一重建主表（只调用一次，避免逐行重建，大幅提升连续标记性能）"""
        main_df = self.main_window.view_model.df
        if main_df is None:
            return
        if hasattr(self.main_window, 'source_model') and self.main_window.source_model:
            self.main_window.source_model.setDataFrame(main_df)
            # setDataFrame 会重排列（_read 移到第0列），按列名恢复显隐，避免列错位丢失
            if hasattr(self.main_window, '_apply_column_visibility_by_name'):
                self.main_window._apply_column_visibility_by_name()

    def mark_row_read(self, view_row):
        """标记当前行为已读"""
        df = self.source_model.getDataFrame()
        if df is None or view_row >= len(df):
            toast("无法定位记录，标记失败", 'error', parent=self)
            return

        data_id = df.iloc[view_row].get('data_id')
        if not data_id:
            rs = df.iloc[view_row]
            if '工厂' in df.columns:
                data_id = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            else:
                data_id = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
        if not data_id:
            toast("无法定位记录，标记失败", 'error', parent=self)
            return

        ok, already, fingerprint = self._sync_main_df(data_id, 1)
        if already:
            toast("该记录已是已读状态", parent=self)
        elif ok:
            # 单行标记：落盘一次 + 重建主表一次
            save_read_status(data_id, 1, fingerprint, snapshot_qty=snapshot_qty_for(df, data_id))
            self._refresh_main_table_once()
            pass  # 不弹 toast，避免刷屏

        # 更新 original_df
        if hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'] == data_id
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 1
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '✓ 已读'

        self._apply_filter()
        if not already:
            toast("✅ 已标记为已读", parent=self)

    def mark_row_unread(self, view_row):
        """标记当前行为未读"""
        df = self.source_model.getDataFrame()
        if df is None or view_row >= len(df):
            toast("无法定位记录，标记失败", 'error', parent=self)
            return

        data_id = df.iloc[view_row].get('data_id')
        if not data_id:
            rs = df.iloc[view_row]
            if '工厂' in df.columns:
                data_id = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            else:
                data_id = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
        if not data_id:
            toast("无法定位记录，标记失败", 'error', parent=self)
            return

        ok, already, fingerprint = self._sync_main_df(data_id, 0)
        if already:
            toast("该记录已是未读状态", parent=self)
        elif ok:
            save_read_status(data_id, 0, fingerprint, snapshot_qty=snapshot_qty_for(df, data_id))
            self._refresh_main_table_once()

        if hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'] == data_id
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 0
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '○ 未读'

        self._apply_filter()
        if not already:
            toast("⭕ 已标记为未读", parent=self)

    def batch_mark_read(self):
        """批量标记选中行为已读"""
        selection_model = self.table_view.selectionModel()
        if not selection_model:
            toast("选择模型不可用", 'error', parent=self)
            return
        if not selection_model.hasSelection():
            toast("请先选中要标记的行", 'info', parent=self)
            return

        # 兼容 SelectItems 模式：从所有选中索引提取唯一行号
        selected_indexes = selection_model.selectedIndexes()
        selected_rows = sorted(set(idx.row() for idx in selected_indexes))
        if not selected_rows:
            toast("请先选中要标记的行", 'info', parent=self)
            return

        df = self.source_model.getDataFrame()
        if df is None or df.empty:
            toast("没有可标记的记录", 'info', parent=self)
            return

        records = []          # [(data_id, is_read, fingerprint), ...] 待落盘
        changed_ids = set()   # 实际发生状态变化的 data_id（用于 original_df 向量化更新）

        for row in selected_rows:
            if row >= len(df):
                continue
            data_id = df.iloc[row].get('data_id')
            if not data_id:
                rs = df.iloc[row]
                if '工厂' in df.columns:
                    data_id = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
                else:
                    data_id = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            if not data_id:
                continue

            # 循环内：只改主表内存，不落盘、不重建
            ok, already, fingerprint = self._sync_main_df(data_id, 1)
            if ok and not already:
                qty = snapshot_qty_for(df, data_id)
                records.append((data_id, 1, fingerprint, qty))
                changed_ids.add(data_id)
                count += 1

        # 循环外统一：批量落盘一次 + 重建主表一次（关键性能优化）
        if records:
            save_read_status_batch(records)
        self._refresh_main_table_once()

        # original_df 向量化更新（一次到位，避免逐行）
        if changed_ids and hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'].isin(changed_ids)
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 1
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '✓ 已读'

        self._apply_filter()
        toast(f"✅ 已批量标记 {count} 条为已读", parent=self)

    def batch_mark_unread(self):
        """批量标记选中行为未读"""
        selection_model = self.table_view.selectionModel()
        if not selection_model:
            toast("选择模型不可用", 'error', parent=self)
            return
        if not selection_model.hasSelection():
            toast("请先选中要标记的行", 'info', parent=self)
            return

        # 兼容 SelectItems 模式：从所有选中索引提取唯一行号
        selected_indexes = selection_model.selectedIndexes()
        selected_rows = sorted(set(idx.row() for idx in selected_indexes))
        if not selected_rows:
            toast("请先选中要标记的行", 'info', parent=self)
            return

        df = self.source_model.getDataFrame()
        if df is None or df.empty:
            toast("没有可标记的记录", 'info', parent=self)
            return

        records = []
        changed_ids = set()

        for row in selected_rows:
            if row >= len(df):
                continue
            data_id = df.iloc[row].get('data_id')
            if not data_id:
                rs = df.iloc[row]
                if '工厂' in df.columns:
                    data_id = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
                else:
                    data_id = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            if not data_id:
                continue

            ok, already, fingerprint = self._sync_main_df(data_id, 0)
            if ok and not already:
                qty = snapshot_qty_for(df, data_id)
                records.append((data_id, 0, fingerprint, qty))
                changed_ids.add(data_id)
                count += 1

        if records:
            save_read_status_batch(records)
        self._refresh_main_table_once()

        if changed_ids and hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'].isin(changed_ids)
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 0
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '○ 未读'

        self._apply_filter()
        toast(f"⭕ 已批量标记 {count} 条为未读", parent=self)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.btn_fullscreen.setText("⛶ 放大")
        else:
            self.showFullScreen()
            self.btn_fullscreen.setText("⛶ 还原")

    def on_double_click(self, index):
        if not index.isValid():
            return
        row = index.row()
        df = self.source_model.getDataFrame()
        if row < len(df):
            record = df.iloc[row]
            try:
                self.main_window.locate_record(record)
            except (AttributeError, Exception):
                pass
            self.accept()

    # -----------------------------------------------------------
    # 复制选中单元格
    # -----------------------------------------------------------
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
            min_row = min(min_row, r)
            max_row = max(max_row, r)
            min_col = min(min_col, c)
            max_col = max(max_col, c)
        if max_row < 0:
            return
        lines = []
        for r in range(min_row, max_row + 1):
            row_vals = []
            for c in range(min_col, max_col + 1):
                row_vals.append(cells.get((r, c), ""))
            lines.append("\t".join(row_vals))
        QApplication.clipboard().setText("\n".join(lines))
