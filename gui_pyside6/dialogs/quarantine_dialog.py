# -*- coding: utf-8 -*-
"""
隔离区对话框 - 列出已隔离的疑难数据，支持取消隔离、查看明细、双击定位主表
"""
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel, QComboBox,
)
from PySide6.QtCore import Qt, QPoint
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import remove_quarantine, get_quarantine_records
from core.read_status import save_read_status
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for
from gui_pyside6.widgets.toast import toast

_HIDDEN_INTERNAL = ['_read', 'data_id', '_quarantined', '_post_audit_changed', 'fingerprint']


class QuarantineDialog(QDialog):
    """隔离区对话框 - 疑难数据暂存区，支持取消隔离 / 双击定位"""

    def __init__(self, quarantine_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("隔离区 - 疑难数据暂存")
        self.resize(1200, 600)
        # 允许最大化/最小化（Windows 上最大化按钮需与最小化成对才稳定显示）
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.main_window = main_window
        self.setup_ui()
        self.set_data(quarantine_df)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel("以下数据被标记为「疑难待处理」。修改主表后重新导入，隔离区记录会同步更新（引用模式，仅按 data_id 关联，不存副本）。可用上方「隔离原因」下拉仅看某一类（自动规则 / 手动移入 / 未填写）。")
        info.setWordWrap(True)
        layout.addWidget(info)

        # 隔离原因筛选栏：按 reason 过滤隔离记录
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(6)
        reason_label = QLabel("隔离原因:")
        self.reason_combo = QComboBox()
        self.reason_combo.setMinimumWidth(280)
        self.reason_combo.addItem("全部")
        self.reason_combo.setToolTip("按隔离原因筛选（自动规则 / 手动移入 / 未填写等）")
        self.reason_combo.currentIndexChanged.connect(self._on_reason_filter)
        filter_bar.addWidget(reason_label)
        filter_bar.addWidget(self.reason_combo)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)

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
        # 回填隔离原因（存于 quarantine_manager 的 SQLite，主表不存副本）
        try:
            recs = get_quarantine_records()
            reason_map = {str(r['uid']): (r.get('reason') or '') for r in recs}
            df['隔离原因'] = df['data_id'].astype(str).map(reason_map)
            df['隔离原因'] = df['隔离原因'].fillna('').replace('', '（未填写原因）')
        except Exception:
            df['隔离原因'] = '（未填写原因）'

        # 保留完整隔离数据，供隔离原因筛选切片使用
        self.full_df = df.copy()
        self._populate_reason_combo(df)
        self._render_table(df)

    def _populate_reason_combo(self, df):
        """用当前隔离数据的隔离原因 distinct 值填充下拉（保留用户当前选择）"""
        seen = set()
        reasons = []
        for r in df['隔离原因'].tolist():
            s = str(r).strip() or '（未填写原因）'
            if s not in seen:
                seen.add(s)
                reasons.append(s)
        reasons.sort()
        current = self.reason_combo.currentText()
        self.reason_combo.blockSignals(True)
        self.reason_combo.clear()
        self.reason_combo.addItem("全部")
        for r in reasons:
            self.reason_combo.addItem(r)
        # 数据刷新后，尽量恢复之前的选择
        idx = self.reason_combo.findText(current)
        self.reason_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.reason_combo.blockSignals(False)

    def _render_table(self, df):
        """重建表格模型并应用内部列隐藏（不重查 reason）"""
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        for col in _HIDDEN_INTERNAL:
            if col in df.columns:
                self.table_view.setColumnHidden(df.columns.get_loc(col), True)

    def _on_reason_filter(self):
        """按隔离原因下拉过滤表格（全部 = 不过滤）"""
        if not hasattr(self, 'full_df') or self.full_df is None:
            return
        selected = self.reason_combo.currentText()
        if selected == "全部" or not selected:
            display = self.full_df
        else:
            display = self.full_df[self.full_df['隔离原因'] == selected]
        self._render_table(display.copy())

    def show_context_menu(self, pos: QPoint):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        selection_model = self.table_view.selectionModel()
        selected_rows = sorted(set(idx.row() for idx in selection_model.selectedIndexes()))
        if not selected_rows:
            selected_rows = [index.row()]
        menu = QMenu()
        mark_read_action = menu.addAction("✓ 设为已读并移出隔离区")
        mark_read_action.triggered.connect(lambda: self._mark_read_and_remove(selected_rows))
        menu.addSeparator()
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

    def _mark_read_and_remove(self, rows):
        """隔离区右键：设为已读 + 移出隔离区

        设为已读 = 标记已读并建立变更检测基线（实际数量 + 备注原因），
        与主表右键「标记为已读」保持同一套逻辑；同时移出隔离区。
        """
        df = self.source_model.getDataFrame()
        if df is None:
            return
        ids = set()
        fp_map = {}
        qty_map = {}
        note_map = {}
        for r in rows:
            if r >= len(df):
                continue
            uid = df.iloc[r].get('data_id')
            if not uid:
                continue
            uid = str(uid)
            ids.add(uid)
            fp_map[uid] = df.iloc[r].get('fingerprint', '') if 'fingerprint' in df.columns else ''
            qty_map[uid] = snapshot_qty_for(df, uid)
            note_map[uid] = snapshot_note_for(df, uid)
        if not ids:
            return
        for uid in ids:
            save_read_status(uid, 1, fp_map.get(uid, ''),
                             snapshot_qty=qty_map.get(uid), snapshot_note=note_map.get(uid))
            remove_quarantine(uid)
        count = len(ids)
        # 回写主表内存：已读 + 移出隔离区
        if self.main_window and hasattr(self.main_window, 'view_model'):
            main_df = self.main_window.view_model.df
            if main_df is not None and 'data_id' in main_df.columns:
                mask = main_df['data_id'].isin(ids)
                if '_read' in main_df.columns:
                    main_df.loc[mask, '_read'] = 1
                if '_quarantined' in main_df.columns:
                    main_df.loc[mask, '_quarantined'] = 0
                self.main_window.view_model.df = main_df
                if hasattr(self.main_window, 'source_model') and self.main_window.source_model:
                    self.main_window.source_model.setDataFrame(main_df)
                    if hasattr(self.main_window, '_apply_column_visibility_by_name'):
                        self.main_window._apply_column_visibility_by_name()
        if self.main_window and hasattr(self.main_window, 'stats_cards'):
            self.main_window.stats_cards.refresh(self.main_window.view_model.df)
        self._refresh_self()
        toast(f"✓ 已设为已读并移出隔离区 {count} 条", parent=self)

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
                # 数据变化后重新应用用户当前的隔离原因筛选
                prev = self.reason_combo.currentText()
                self.set_data(qdf)
                if prev and prev != "全部":
                    idx = self.reason_combo.findText(prev)
                    if idx >= 0:
                        self.reason_combo.setCurrentIndex(idx)  # 触发 _on_reason_filter

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
