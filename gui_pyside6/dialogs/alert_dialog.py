# -*- coding: utf-8 -*-
"""
替代料看板对话框 - 仅显示替代料预警，支持标记已读、导出、双击跳转
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel, QCheckBox,
    QComboBox, QGroupBox,
)
from PySide6.QtCore import Qt, QPoint
import pandas as pd
from gui_pyside6.models.data_frame_model import DataFrameModel, classify_row_color_keys
from core.read_status import save_read_status, save_read_status_batch
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for
from gui_pyside6.widgets.toast import toast
from gui_pyside6.widgets.filter_panel import _color_icon
from gui_pyside6.utils.table_sort import enable_click_sort


class AlertDialog(QDialog):
    """替代料看板对话框 - 替代料偏差预警，支持标记已读"""

    def __init__(self, alerts_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实时替代料看板 - 替代料偏差预警")
        self.resize(1200, 600)
        self.main_window = main_window
        self.original_df = alerts_df.copy()
        self.filter_mode = "all"
        self.color_filters = set()
        self._semi_class_filter = set()  # 半成品重分类筛选：空集合=全部 / 集合内为选中分类（虚拟项模糊匹配）
        self._semi_class_col = None
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
        self.btn_all.setMinimumWidth(70)
        self.btn_all.clicked.connect(lambda: self._set_filter("all"))
        filter_layout.addWidget(self.btn_all)

        self.btn_unread = QPushButton("未读")
        self.btn_unread.setCheckable(True)
        self.btn_unread.setMinimumWidth(70)
        self.btn_unread.clicked.connect(lambda: self._set_filter("unread"))
        filter_layout.addWidget(self.btn_unread)

        self.btn_read = QPushButton("已读")
        self.btn_read.setCheckable(True)
        self.btn_read.setMinimumWidth(70)
        self.btn_read.clicked.connect(lambda: self._set_filter("read"))
        filter_layout.addWidget(self.btn_read)

        filter_layout.addStretch()

        # 批量操作
        self.btn_batch_read = QPushButton("批量标记已读")
        self.btn_batch_read.setMinimumWidth(100)
        self.btn_batch_read.clicked.connect(self.batch_mark_read)
        filter_layout.addWidget(self.btn_batch_read)

        self.btn_batch_unread = QPushButton("批量标记未读")
        self.btn_batch_unread.setMinimumWidth(100)
        self.btn_batch_unread.clicked.connect(self.batch_mark_unread)
        filter_layout.addWidget(self.btn_batch_unread)

        # 放大按钮
        self.btn_fullscreen = QPushButton("⛶ 放大")
        self.btn_fullscreen.setMinimumWidth(80)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        filter_layout.addWidget(self.btn_fullscreen)

        layout.addLayout(filter_layout)

        # ---- 颜色标记筛选栏（与主表颜色标记逻辑一致）----
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("颜色:"))
        self.color_checks = {}
        _color_items = [
            ("_changed_only", "审核后变更", (255, 205, 205)),
            ("_quarantined_only", "隔离区", (255, 248, 200)),
            ("_substitute_only", "替代料", (205, 230, 255)),
            ("_unused_only", "未投料", (200, 240, 210)),
            ("_alert_only", "偏差率预警", (255, 198, 142)),
            ("_plain_only", "无标记", (235, 235, 235)),
        ]
        for key, label, rgb in _color_items:
            cb = QCheckBox(label)
            cb.setIcon(_color_icon(rgb))
            cb.stateChanged.connect(self._on_color_toggled)
            self.color_checks[key] = cb
            color_row.addWidget(cb)
        self.color_clear_btn = QPushButton("清空颜色")
        self.color_clear_btn.setMaximumWidth(80)
        self.color_clear_btn.clicked.connect(self._clear_color_checks)
        color_row.addWidget(self.color_clear_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        # ---- 半成品重分类筛选（复选框组：全部 + 各值 + 虚拟两项）----
        semi_class_row = QHBoxLayout()
        semi_class_row.addWidget(QLabel("半成品分类:"))
        self.grp_semi_class = QGroupBox()
        self.grp_semi_class.setFlat(True)
        self.grp_semi_class.setFixedWidth(180)
        self._semi_class_vlayout = QVBoxLayout(self.grp_semi_class)
        self._semi_class_vlayout.setContentsMargins(4, 2, 4, 2)
        self._semi_class_vlayout.setSpacing(1)
        self._semi_class_checkboxes = {}  # 名称 -> QCheckBox（含特殊键 "__all__"）
        semi_class_row.addWidget(self.grp_semi_class)
        semi_class_row.addStretch()
        layout.addLayout(semi_class_row)

        # ---- 表格 ----
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 点击列头排序（显式连接，规避 Qt6 下 setSortingEnabled 内部连接失效）。
        # 第0列 _read 为内部列，不参与排序。
        self._sort_ctrl = enable_click_sort(
            self.table_view, lambda: getattr(self, "source_model", None), skip_cols=(0,))
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

    def _on_color_toggled(self):
        """颜色复选框变化：更新已勾选集合并刷新（与已读状态 AND）"""
        self.color_filters = {k for k, cb in self.color_checks.items() if cb.isChecked()}
        self._apply_filter()

    def _clear_color_checks(self):
        """清空所有颜色勾选"""
        for cb in self.color_checks.values():
            cb.setChecked(False)
        self.color_filters = set()
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

        # 颜色标记筛选（与已读状态 AND）：复用主表 classify_row_color_keys
        if self.color_filters:
            threshold = 10.0
            am = getattr(self.main_window, 'alert_monitor', None)
            if am is not None:
                try:
                    threshold = float(getattr(am, 'threshold', 10))
                except (TypeError, ValueError):
                    threshold = 10.0
            mask = filtered.apply(
                lambda r: bool(classify_row_color_keys(r, filtered, threshold) & self.color_filters),
                axis=1)
            filtered = filtered[mask]

        # 半成品重分类筛选（与已读状态 AND）
        filtered = filtered[self._semi_class_mask(filtered)]

        filtered = filtered.reset_index(drop=True)
        self.source_model.setDataFrame(filtered)
        self._sort_ctrl.reapply()  # 恢复排序态

    def _on_semi_class_changed(self):
        """半成品重分类复选框变化回调：收集勾选项（空=全部），全部与其他互斥。"""
        all_cb = self._semi_class_checkboxes.get("__all__")
        others = [cb for name, cb in self._semi_class_checkboxes.items() if name != "__all__"]
        sender = self.sender()
        if sender is all_cb:
            if all_cb.isChecked():
                for cb in others:
                    cb.setChecked(False)
                self._semi_class_filter = set()
        else:
            if any(cb.isChecked() for cb in others):
                if all_cb:
                    all_cb.setChecked(False)
                self._semi_class_filter = {
                    name for name, cb in self._semi_class_checkboxes.items()
                    if name != "__all__" and cb.isChecked()
                }
            else:
                if all_cb:
                    all_cb.setChecked(True)
                self._semi_class_filter = set()
        self._apply_filter()

    def _semi_class_mask(self, df):
        """半成品重分类掩码：空集合=全True；虚拟项「食品/饮料成品半成品」模糊匹配
        （列值含'成品'或'半成品' 且 工厂含'食品'/'饮料'）；其他=列值精确==分类名。多值 OR。"""
        if not self._semi_class_filter or not getattr(self, '_semi_class_col', None):
            return pd.Series(True, index=df.index)
        col = self._semi_class_col
        if col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[col].astype(str).str.strip()
        blank = df[col].fillna('').astype(str).str.strip() == ''
        fac = df['工厂'].astype(str) if '工厂' in df.columns else pd.Series('', index=df.index)
        mask = pd.Series(False, index=df.index)
        for m in self._semi_class_filter:
            if m == "食品成品半成品":
                mask = mask | ((vals.str.contains('成品|半成品', na=False) | blank) & fac.str.contains('食品', na=False))
            elif m == "饮料成品半成品":
                mask = mask | ((vals.str.contains('成品|半成品', na=False) | blank) & fac.str.contains('饮料', na=False))
            else:
                mask = mask | (vals == m)
        return mask

    def _build_semi_checkboxes(self, unique_vals):
        """构建半成品分类复选框组：全部 + 虚拟两项 + 实际各值。"""
        while self._semi_class_vlayout.count():
            it = self._semi_class_vlayout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._semi_class_checkboxes = {}
        cb_all = QCheckBox("全部")
        cb_all.setChecked(True)
        cb_all.stateChanged.connect(self._on_semi_class_changed)
        self._semi_class_vlayout.addWidget(cb_all)
        self._semi_class_checkboxes["__all__"] = cb_all
        for v in ("食品成品半成品", "饮料成品半成品"):
            cb = QCheckBox(v)
            cb.stateChanged.connect(self._on_semi_class_changed)
            self._semi_class_vlayout.addWidget(cb)
            self._semi_class_checkboxes[v] = cb
        for v in unique_vals:
            if v in ("食品成品半成品", "饮料成品半成品"):
                continue
            cb = QCheckBox(v)
            cb.stateChanged.connect(self._on_semi_class_changed)
            self._semi_class_vlayout.addWidget(cb)
            self._semi_class_checkboxes[v] = cb

    def set_data(self, df):
        """设置表格数据 - 确保 _read 和 data_id 列存在"""
        df = df.copy()
        if "_read" not in df.columns:
            df["_read"] = 0
        if "data_id" not in df.columns:
            if all(c in df.columns for c in ["订单日期", "流程订单", "物料编码"]):
                # 优先使用含工厂的 4 段格式，与主表 data_service.py 保持一致
                if '工厂' in df.columns:
                    df["data_id"] = (
                        df["工厂"].astype(str) + "|" +
                        df["订单日期"].astype(str) + "|" +
                        df["流程订单"].astype(str) + "|" +
                        df["物料编码"].astype(str)
                    )
                else:
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
        for _hc in ('_post_audit_changed', '_quarantined', '是否替代料'):
            if _hc in df.columns:
                self.table_view.setColumnHidden(df.columns.get_loc(_hc), True)

        # 默认打开时显示未读
        self._set_filter("unread")
        # 初始化半成品重分类筛选器（复选框组：全部 + 各值 + 虚拟两项）
        if "半成品重分类" in df.columns:
            self._semi_class_col = "半成品重分类"
            unique_vals = df["半成品重分类"].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self._build_semi_checkboxes(unique_vals)

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出预警列表", "替代料预警.xlsx", "Excel files (*.xlsx)")
        if path:
            from gui_pyside6.save_guard import safe_save
            export_df = self.original_df.drop(columns=['_read', 'data_id', '_post_audit_changed', '_quarantined', '是否替代料'], errors='ignore')
            saved = safe_save(self, path,
                              lambda p: export_df.to_excel(p, index=False),
                              what="预警列表")
            if saved:
                toast(f"已导出 {len(export_df)} 条记录到 {saved}", parent=self)

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
                note = snapshot_note_for(df, data_id)
                records.append((data_id, 1, fingerprint, qty, note))
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
                note = snapshot_note_for(df, data_id)
                records.append((data_id, 0, fingerprint, qty, note))
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
            save_read_status(data_id, 1, fingerprint, snapshot_qty=snapshot_qty_for(df, data_id), snapshot_note=snapshot_note_for(df, data_id))
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
            save_read_status(data_id, 0, fingerprint, snapshot_qty=snapshot_qty_for(df, data_id), snapshot_note=snapshot_note_for(df, data_id))
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
        count = 0

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
                note = snapshot_note_for(df, data_id)
                records.append((data_id, 1, fingerprint, qty, note))
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
        if count and hasattr(self, 'main_window') and self.main_window:
            self.main_window._on_manual_marked(count)

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
        count = 0

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
                note = snapshot_note_for(df, data_id)
                records.append((data_id, 0, fingerprint, qty, note))
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
