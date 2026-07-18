# -*- coding: utf-8 -*-
"""
隔离区对话框 - 列出已隔离的疑难数据，支持取消隔离、查看明细、双击定位主表
"""
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel,
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QPolygon, QColor, QBrush
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import remove_quarantine, get_quarantine_records
from core.read_status import save_read_status, save_read_status_batch
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for
from gui_pyside6.widgets.toast import toast

_HIDDEN_INTERNAL = ['_read', 'data_id', '_quarantined', '_post_audit_changed', 'fingerprint']


class FilterHeader(QHeaderView):
    """带列头筛选三角的表头：点击指定列右侧的 ▼ 三角弹出该列筛选菜单，
    点击列头其余区域仍按原逻辑排序（不破坏排序交互）。"""

    sectionFilterClicked = Signal(int)

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._filter_sections = set()
        self._tri_w = 16

    def add_filter_section(self, logical):
        self._filter_sections.add(logical)

    def clear_filter_sections(self):
        self._filter_sections.clear()

    def paintSection(self, painter, rect, logicalIndex):
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex in self._filter_sections:
            painter.save()
            mid_x = rect.right() - self._tri_w / 2
            mid_y = rect.center().y()
            painter.setBrush(QBrush(QColor(90, 90, 90)))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygon([
                QPoint(int(mid_x - 3), int(mid_y - 2)),
                QPoint(int(mid_x + 3), int(mid_y - 2)),
                QPoint(int(mid_x), int(mid_y + 3)),
            ]))
            painter.restore()

    def mousePressEvent(self, event):
        x = event.position().x()
        xi = int(x)
        for sec in self._filter_sections:
            if self.logicalIndexAt(xi) == sec:
                sp = self.sectionViewportPosition(sec)
                sz = self.sectionSize(sec)
                if x >= sp + sz - self._tri_w:
                    self.sectionFilterClicked.emit(sec)
                    return
        super().mousePressEvent(event)


class QuarantineDialog(QDialog):
    """隔离区对话框 - 疑难数据暂存区，支持取消隔离 / 双击定位"""

    def __init__(self, quarantine_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("隔离区 - 疑难数据暂存")
        self.resize(1200, 600)
        # 允许最大化/最小化（Windows 上最大化按钮需与最小化成对才稳定显示）
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.main_window = main_window
        self._current_reason_filter = "全部"
        self.setup_ui()
        self.set_data(quarantine_df)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel("以下数据被标记为「疑难待处理」。修改主表后重新导入，隔离区记录会同步更新（引用模式，仅按 data_id 关联，不存副本）。点击「隔离原因」列头右侧的 ▼ 三角可按原因筛选（自动规则 / 手动移入 / 未填写）；点击列头其余区域仍可排序。")
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
        # 自定义表头：隔离原因列带筛选三角
        self.header = FilterHeader(Qt.Horizontal, self.table_view)
        self.table_view.setHorizontalHeader(self.header)
        self.header.sectionFilterClicked.connect(self._show_reason_filter_menu)
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

        # 与主表同步最新 _read：避免主表已读状态变化后隔离区仍显示旧状态
        df = self._sync_read_from_main(df)

        # 派生「状态」列（已读/未读），供隔离区显示，并作为隔离原因的目标锚点
        df['状态'] = df.get('_read', pd.Series(0, index=df.index)).apply(
            lambda v: '已读' if (pd.notna(v) and int(v)) else '未读'
        )

        # 列序调整：把「隔离原因」移到「状态」列之后（用户要求：隔离原因跟在已读状态后）
        df = self._reorder_reason_after_status(df)

        # 保留完整隔离数据，供隔离原因筛选切片使用
        self.full_df = df.copy()
        self._render_table(df)

    def _reorder_reason_after_status(self, df):
        """将「隔离原因」列移到「审核状态/状态」列之后；找不到状态列则保持末尾。"""
        if '隔离原因' not in df.columns:
            return df
        status_col = next((c for c in ('审核状态', '状态') if c in df.columns), None)
        if status_col is None:
            return df
        cols = list(df.columns)
        cols.remove('隔离原因')
        idx = cols.index(status_col)
        cols.insert(idx + 1, '隔离原因')
        return df[cols]

    def _sync_read_from_main(self, df):
        """用主表 view_model.df 的最新 _read 覆盖隔离区 df 的 _read。"""
        if self.main_window and hasattr(self.main_window, 'view_model'):
            main_df = self.main_window.view_model.df
            if main_df is not None and 'data_id' in main_df.columns and '_read' in main_df.columns:
                read_map = main_df.set_index('data_id')['_read'].to_dict()
                current = df.get('_read', pd.Series(0, index=df.index))
                df['_read'] = df['data_id'].astype(str).map(read_map).fillna(current).astype(int)
        return df

    def _render_table(self, df):
        """重建表格模型并应用内部列隐藏（不重查 reason），并重注册隔离原因列筛选三角"""
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)
        # 重注册隔离原因列的筛选三角（setModel 会重置表头状态）
        # 注意：DataFrameModel 内部会重排列顺序（如把 _read 前置），
        # 必须用模型实际显示的列顺序取列号，否则筛选三角会错位到别的列。
        self.header.clear_filter_sections()
        display_df = self.source_model.getDataFrame()
        if '隔离原因' in display_df.columns:
            self.header.add_filter_section(display_df.columns.get_loc('隔离原因'))
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        for col in _HIDDEN_INTERNAL:
            if col in df.columns:
                self.table_view.setColumnHidden(df.columns.get_loc(col), True)

    def _show_reason_filter_menu(self, col):
        """点击隔离原因列头 ▼ 三角：弹出该列 distinct 值菜单"""
        if not hasattr(self, 'full_df') or self.full_df is None:
            return
        if '隔离原因' not in self.full_df.columns:
            return
        values = self.full_df['隔离原因'].dropna().astype(str).tolist()
        seen = set()
        uniq = []
        for v in values:
            if v not in seen:
                seen.add(v)
                uniq.append(v)
        menu = QMenu(self)
        act_all = menu.addAction("全部（清除筛选）")
        menu.addSeparator()
        actions = {}
        for v in uniq:
            actions[menu.addAction(v)] = v
        header = self.table_view.horizontalHeader()
        pos = header.sectionViewportPosition(col)
        sz = header.sectionSize(col)
        global_pos = header.mapToGlobal(QPoint(int(pos + sz - 16), 0))
        chosen = menu.exec_(global_pos)
        if chosen is None:
            return
        if chosen == act_all:
            self._apply_reason_filter("全部")
        else:
            self._apply_reason_filter(actions[chosen])

    def _apply_reason_filter(self, value):
        """按隔离原因筛选表格（全部 = 不过滤），并记住当前选择以便刷新后恢复"""
        if not hasattr(self, 'full_df') or self.full_df is None:
            return
        self._current_reason_filter = value
        if value == "全部" or not value:
            display = self.full_df
        else:
            display = self.full_df[self.full_df['隔离原因'] == value]
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
        # 动态判断当前选中行是否有未读/已读，分别提供对应操作
        df = self.source_model.getDataFrame()
        any_unread = False
        any_read = False
        if df is not None:
            for r in selected_rows:
                if r < len(df):
                    val = df.iloc[r].get('_read', 0)
                    try:
                        is_read = int(val) if pd.notna(val) else 0
                    except Exception:
                        is_read = 0
                    if is_read:
                        any_read = True
                    else:
                        any_unread = True
        if any_unread:
            mark_read_action = menu.addAction("✓ 标记为已读")
            mark_read_action.triggered.connect(lambda: self._mark_rows_read_state(selected_rows, 1))
        if any_read:
            mark_unread_action = menu.addAction("🔘 标记为未读")
            mark_unread_action.triggered.connect(lambda: self._mark_rows_read_state(selected_rows, 0))
        if any_unread or any_read:
            menu.addSeparator()
        mark_read_and_remove_action = menu.addAction("✓ 设为已读并移出隔离区")
        mark_read_and_remove_action.triggered.connect(lambda: self._mark_read_and_remove(selected_rows))
        menu.addSeparator()
        restore_action = menu.addAction("↩ 取消隔离（选中行）")
        restore_action.triggered.connect(lambda: self._restore_rows(selected_rows))
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _mark_rows_read_state(self, rows, is_read):
        """批量切换隔离区选中行的已读/未读状态，并同步回主表和 SQLite。"""
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

        main_df = self.main_window.view_model.df if (self.main_window and hasattr(self.main_window, 'view_model')) else None
        records = []
        for uid in ids:
            fp = ''
            if 'fingerprint' in df.columns:
                sel = df.loc[df['data_id'].astype(str) == uid, 'fingerprint']
                if len(sel) > 0:
                    fp = sel.iloc[0]
            qty = snapshot_qty_for(main_df, uid) if main_df is not None else None
            note = snapshot_note_for(main_df, uid) if main_df is not None else ''
            records.append((uid, int(is_read), str(fp), qty, note))

        save_read_status_batch(records)

        # 回写主表内存
        if main_df is not None and 'data_id' in main_df.columns and '_read' in main_df.columns:
            main_df.loc[main_df['data_id'].astype(str).isin(ids), '_read'] = int(is_read)
            self.main_window.view_model.df = main_df
            self._refresh_main_table()

        # 刷新隔离区弹窗自身
        self._refresh_self()
        toast(f"已标记为{'已读' if is_read else '未读'} {len(ids)} 条", parent=self)

    def _refresh_main_table(self):
        """刷新主表显示和统计卡片。"""
        if self.main_window and hasattr(self.main_window, 'source_model') and self.main_window.source_model:
            self.main_window.source_model.setDataFrame(self.main_window.view_model.df)
            if hasattr(self.main_window, '_apply_column_visibility_by_name'):
                self.main_window._apply_column_visibility_by_name()
        if self.main_window and hasattr(self.main_window, 'stats_cards') and self.main_window.stats_cards:
            self.main_window.stats_cards.refresh(self.main_window.view_model.df)

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
                prev = self._current_reason_filter
                self.set_data(qdf)
                if prev and prev != "全部":
                    self._apply_reason_filter(prev)  # 重新应用筛选，保持选择

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
