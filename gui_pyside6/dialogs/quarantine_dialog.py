# -*- coding: utf-8 -*-
"""
隔离区对话框 - 列出已隔离的疑难数据，支持取消隔离、查看明细、双击定位主表
v42.37 新增：Tab2「失效复核」——监控隔离区旧数据改动（如负损→补投相符），
可手动扫描并一键移出已失效记录。
"""
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView, QTabWidget,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel, QWidget,
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QPolygon, QColor, QBrush
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import (
    remove_quarantine, get_quarantine_records, scan_expired_quarantine,
)
from core.auto_quarantine import load_auto_quarantine_config
from core.read_status import save_read_status, save_read_status_batch
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for
from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.table_sort import enable_click_sort

_HIDDEN_INTERNAL = ['_read', 'data_id', '_quarantined', '_post_audit_changed', 'fingerprint']


class FilterHeader(QHeaderView):
    """带列头筛选三角的表头：点击指定列右侧的 ▼ 三角弹出该列筛选菜单，
    点击列头其余区域仍可排序。

    Qt6/PySide6 下自定义表头默认 `sectionClicked` 发射路径失效（点击列头不触发
    排序），故在本类内自行判定「同列按下并抬起」后手动补发 `sectionClicked`，
    交由 table_sort.HeaderSortController 处理排序；三角筛选与列宽拖动不受影响。
    """

    sectionFilterClicked = Signal(int)

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._filter_sections = set()
        self._tri_w = 16
        self._press_sec = -1

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

    def _is_triangle(self, x, sec):
        """点击位置是否落在 sec 列右侧 _tri_w 宽的筛选三角区域内。"""
        sp = self.sectionViewportPosition(sec)
        sz = self.sectionSize(sec)
        return x >= sp + sz - self._tri_w

    def mousePressEvent(self, event):
        x = event.position().x()
        xi = int(x)
        sec = self.logicalIndexAt(xi)
        if sec in self._filter_sections and self._is_triangle(x, sec):
            self.sectionFilterClicked.emit(sec)
            self._press_sec = -1
            return
        self._press_sec = sec
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        x = event.position().x()
        xi = int(x)
        sec = self.logicalIndexAt(xi)
        was_click = self._press_sec >= 0 and sec == self._press_sec
        self._press_sec = -1
        super().mouseReleaseEvent(event)
        if was_click:
            # 默认 sectionClicked 路径对自定义表头失效，手动补发（super 不会重复发射）
            self.sectionClicked.emit(sec)


class QuarantineDialog(QDialog):
    """隔离区对话框 - 疑难数据暂存区，支持取消隔离 / 双击定位 / 失效复核"""

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

        self.tabs = QTabWidget()
        # ── Tab1：隔离区列表 ──
        self.tab_list = QWidget()
        self._build_list_tab(self.tab_list)
        self.tabs.addTab(self.tab_list, "隔离区列表")
        # ── Tab2：失效复核 ──
        self.tab_expired = QWidget()
        self._build_expired_tab(self.tab_expired)
        self.tabs.addTab(self.tab_expired, "失效复核")
        layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ Tab1
    def _build_list_tab(self, tab):
        v = QVBoxLayout(tab)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.header = FilterHeader(Qt.Horizontal, self.table_view)
        self.table_view.setHorizontalHeader(self.header)
        # 点击列头排序（显式连接，规避 Qt6 下 setSortingEnabled 内部连接失效）。
        # 第0列 _read 为内部列，不参与排序；隔离原因列头的 ▼ 三角仍触发筛选菜单。
        self._sort_ctrl = enable_click_sort(
            self.table_view, lambda: getattr(self, "source_model", None), skip_cols=(0,))
        self.header.sectionFilterClicked.connect(self._show_reason_filter_menu)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.installEventFilter(self)
        v.addWidget(self.table_view)

        bl = QHBoxLayout()
        self.btn_restore = QPushButton("↩ 取消隔离（选中行）")
        self.btn_restore.clicked.connect(self.batch_restore)
        bl.addWidget(self.btn_restore)
        export_btn = QPushButton("📎 导出 Excel")
        export_btn.clicked.connect(self.export_excel)
        bl.addWidget(export_btn)
        bl.addStretch()
        v.addLayout(bl)

    # ------------------------------------------------------------------ Tab2
    def _build_expired_tab(self, tab):
        v = QVBoxLayout(tab)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        hint = QLabel("监控隔离区旧数据的改动：例如某行当初因「负损（实际<定额）」入区，"
                      "后来补投使实际≥定额（相符/盘盈）或实际归零，其入区原因即已失效。"
                      "点「扫描失效」实时比对主表，下方列出失效记录，可一键移出隔离区。")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.expired_view = QTableView()
        self.expired_view.setAlternatingRowColors(True)
        self.expired_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.expired_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.expired_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 点击列头排序（失效复核表；data_id 等列均可排，skip_cols 留空）
        self._sort_ctrl_expired = enable_click_sort(
            self.expired_view, lambda: getattr(self, "expired_model", None))
        self.expired_view.verticalHeader().setVisible(False)
        self.expired_view.verticalHeader().setDefaultSectionSize(28)
        v.addWidget(self.expired_view)

        bl = QHBoxLayout()
        scan_btn = QPushButton("🔄 扫描失效")
        scan_btn.clicked.connect(self._run_expired_scan)
        bl.addWidget(scan_btn)
        self.btn_mark_read_expired = QPushButton("✓ 设为已读并移出隔离区（选中行）")
        self.btn_mark_read_expired.clicked.connect(self._mark_expired_read_selected)
        bl.addWidget(self.btn_mark_read_expired)
        self.btn_remove_expired = QPushButton("↩ 移出隔离区（选中行）")
        self.btn_remove_expired.clicked.connect(self._remove_expired_selected)
        bl.addWidget(self.btn_remove_expired)
        bl.addStretch()
        self.expired_count_label = QLabel("失效记录：0 条")
        bl.addWidget(self.expired_count_label)
        v.addLayout(bl)

        # 初始渲染（复用主窗口已算好的缓存，若没有则实时算）
        self._render_expired(self._load_expired_from_main())

    # ------------------------------------------------------------------ 数据
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

        df = self._sync_read_from_main(df)

        df['状态'] = df.get('_read', pd.Series(0, index=df.index)).apply(
            lambda v: '已读' if (pd.notna(v) and int(v)) else '未读'
        )
        df = self._reorder_reason_before_order_date(df)

        self.full_df = df.copy()
        self._render_table(df)

    def _reorder_reason_before_order_date(self, df):
        """将「隔离原因」列移到「订单日期」列之前；找不到订单日期列则降级到状态列之后。"""
        if '隔离原因' not in df.columns:
            return df
        cols = list(df.columns)
        cols.remove('隔离原因')
        if '订单日期' in cols:
            idx = cols.index('订单日期')
            cols.insert(idx, '隔离原因')
        else:
            status_col = next((c for c in ('审核状态', '状态') if c in cols), None)
            if status_col is None:
                cols.append('隔离原因')
            else:
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
        self.header.clear_filter_sections()
        display_df = self.source_model.getDataFrame()
        if '隔离原因' in display_df.columns:
            self.header.add_filter_section(display_df.columns.get_loc('隔离原因'))
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        for col in _HIDDEN_INTERNAL:
            if col in df.columns:
                self.table_view.setColumnHidden(df.columns.get_loc(col), True)

        # 重渲染后恢复排序态：用户点过列头则保持；否则默认按 data_id 升序
        if hasattr(self, "_sort_ctrl"):
            if self._sort_ctrl.active:
                self._sort_ctrl.reapply()
            else:
                df0 = self.source_model.getDataFrame()
                col = df0.columns.get_loc('data_id') if 'data_id' in df0.columns else 1
                self._sort_ctrl.apply_default(col, Qt.AscendingOrder)

    # ------------------------------------------------------------------ Tab2 逻辑
    def _load_expired_from_main(self):
        """优先用主窗口分析后缓存的失效结果，否则实时算。"""
        if self.main_window and hasattr(self.main_window, '_expired_q_cache'):
            cache = self.main_window._expired_q_cache
            if cache:
                return list(cache.values())
        df = self.main_window.view_model.df if (self.main_window and hasattr(self.main_window, 'view_model')) else None
        if df is None or 'data_id' not in df.columns:
            return []
        return scan_expired_quarantine(df, load_auto_quarantine_config())

    def _run_expired_scan(self):
        """手动触发失效扫描（实时比对主表）。"""
        df = self.main_window.view_model.df if (self.main_window and hasattr(self.main_window, 'view_model')) else None
        if df is None or 'data_id' not in df.columns:
            toast("暂无数据，无法扫描", 'info', parent=self)
            return
        expired = scan_expired_quarantine(df, load_auto_quarantine_config())
        # 写回主窗口缓存，保持角标/后续一致
        if self.main_window and hasattr(self.main_window, '_expired_q_cache'):
            self.main_window._expired_q_cache = {r['uid']: r for r in expired}
            self.main_window._update_quarantine_badge(expired)
        self._render_expired(expired)
        toast(f"扫描完成：{len(expired)} 条失效记录", parent=self)

    def _render_expired(self, expired_list):
        """渲染失效复核表格。列：data_id / 隔离原因 / 失效说明 / 定额 / 实际 / 偏差数量。"""
        rows = []
        for r in expired_list:
            actual = r.get('actual')
            quota = r.get('quota')
            dev = (actual - quota) if (actual is not None and quota is not None) else ''
            rows.append({
                'data_id': r.get('uid', ''),
                '隔离原因': r.get('reason', ''),
                '失效说明': r.get('detail', ''),
                '定额': quota if quota is not None else '',
                '实际': actual if actual is not None else '',
                '偏差数量': dev,
            })
        edf = pd.DataFrame(rows, columns=['data_id', '隔离原因', '失效说明', '定额', '实际', '偏差数量'])
        if edf.empty:
            edf = pd.DataFrame(columns=['data_id', '隔离原因', '失效说明', '定额', '实际', '偏差数量'])
        self.expired_model = DataFrameModel()
        self.expired_model.setDataFrame(edf)
        self.expired_view.setModel(self.expired_model)
        self.expired_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.expired_count_label.setText("失效记录：%d 条" % len(edf))
        # 同步 Tab 标题角标
        idx = self.tabs.indexOf(self.tab_expired)
        self.tabs.setTabText(idx, "失效复核 (%d)" % len(edf) if edf.shape[0] else "失效复核")
        # 重渲染后恢复排序态：用户点过列头则保持；否则默认按偏差数量降序（偏差大的优先复核）
        if hasattr(self, "_sort_ctrl_expired"):
            if self._sort_ctrl_expired.active:
                self._sort_ctrl_expired.reapply()
            else:
                df0 = self.expired_model.getDataFrame()
                col = df0.columns.get_loc('偏差数量') if '偏差数量' in df0.columns else 1
                self._sort_ctrl_expired.apply_default(col, Qt.DescendingOrder)

    def _remove_expired_selected(self):
        """把失效复核中选中的记录移出隔离区。"""
        sel = self.expired_view.selectionModel()
        if not sel or not sel.hasSelection():
            toast("请先选中要移出的行", 'info', parent=self)
            return
        df = self.expired_model.getDataFrame()
        rows = sorted(set(idx.row() for idx in sel.selectedIndexes()))
        ids = set()
        for r in rows:
            if r < len(df):
                uid = df.iloc[r].get('data_id')
                if uid:
                    ids.add(str(uid))
        if not ids:
            return
        for uid in ids:
            remove_quarantine(uid)
        # 回写主表
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
        # 刷新本弹窗：Tab1 + Tab2
        self._refresh_self()
        toast(f"↩ 已移出隔离区 {len(ids)} 条", parent=self)

    def _mark_expired_read_selected(self):
        """把失效复核中选中的记录设为已读（建立变更检测基线）并移出隔离区。"""
        sel = self.expired_view.selectionModel()
        if not sel or not sel.hasSelection():
            toast("请先选中要处理的行", 'info', parent=self)
            return
        df = self.expired_model.getDataFrame()
        rows = sorted(set(idx.row() for idx in sel.selectedIndexes()))
        ids = set()
        for r in rows:
            if r < len(df):
                uid = df.iloc[r].get('data_id')
                if uid:
                    ids.add(str(uid))
        if not ids:
            return
        main_df = self.main_window.view_model.df if (
            self.main_window and hasattr(self.main_window, 'view_model')) else None
        for uid in ids:
            fp = ''
            qty = snapshot_qty_for(main_df, uid) if main_df is not None else None
            note = snapshot_note_for(main_df, uid) if main_df is not None else ''
            save_read_status(uid, 1, fp, snapshot_qty=qty, snapshot_note=note)
            remove_quarantine(uid)
        if main_df is not None and 'data_id' in main_df.columns:
            mask = main_df['data_id'].astype(str).isin(ids)
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
        toast(f"✓ 已设为已读并移出隔离区 {len(ids)} 条", parent=self)

    # ------------------------------------------------------------------ 原因筛选
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

        if main_df is not None and 'data_id' in main_df.columns and '_read' in main_df.columns:
            main_df.loc[main_df['data_id'].astype(str).isin(ids), '_read'] = int(is_read)
            self.main_window.view_model.df = main_df
            self._refresh_main_table()

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
        # 同步刷新失效复核页
        self._render_expired(self._load_expired_from_main())

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
            from gui_pyside6.save_guard import safe_save
            export_df = self.source_model.getDataFrame().drop(columns=_HIDDEN_INTERNAL, errors='ignore')
            saved = safe_save(self, path,
                              lambda p: export_df.to_excel(p, index=False),
                              what="隔离区列表")
            if saved:
                toast(f"已导出 {len(export_df)} 条记录到 {saved}", parent=self)

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
