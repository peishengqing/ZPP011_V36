# -*- coding: utf-8 -*-
"""
偏差率预警看板对话框 - 仅显示 |偏差率| >= 10% 的预警记录，
支持：列宽可拖拽调整、点击列头排序、Ctrl+C 复制、标记已读/未读、导出、双击定位主表。

数据源由主窗口预筛选（|偏差率(%)| >= 10）后传入，本对话框只负责展示与交互。
交互与「替代料看板」(alert_dialog.AlertDialog) 保持一致，仅列宽策略改为可拖拽。
"""

import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel, QFrame,
)
from PySide6.QtCore import Qt, QPoint, QTimer
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.read_status import save_read_status, save_read_status_batch
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for
from gui_pyside6.widgets.toast import toast


class DeviationWarningDialog(QDialog):
    """偏差率预警看板对话框 - |偏差率| >= 10% 的记录，支持标记已读/未读"""

    def __init__(self, warnings_df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏差率预警看板 - |偏差率| ≥ 10%")
        self.resize(1280, 640)
        # 允许最大化/最小化
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.main_window = main_window
        self.original_df = warnings_df.copy()
        self.filter_mode = "all"
        self.mat_filter = "all"   # 料别筛选：all / raw(原料) / pkg(包材)，与已读状态筛选独立叠加
        self._mat_col = None      # 料别列名（物料类型 / 物料大类），set_data 时探测
        self.setup_ui()
        self.set_data(warnings_df)

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

        # ---- 第二组：料别筛选（与上面的已读状态筛选独立，可叠加）----
        self.mat_sep = QFrame()
        self.mat_sep.setFrameShape(QFrame.VLine)
        self.mat_sep.setFrameShadow(QFrame.Sunken)
        filter_layout.addSpacing(8)
        filter_layout.addWidget(self.mat_sep)
        filter_layout.addSpacing(8)

        self.lbl_mat = QLabel("料别:")
        filter_layout.addWidget(self.lbl_mat)

        self.btn_mat_all = QPushButton("全部")
        self.btn_mat_all.setCheckable(True)
        self.btn_mat_all.setMinimumWidth(70)
        self.btn_mat_all.clicked.connect(lambda: self._set_mat_filter("all"))
        filter_layout.addWidget(self.btn_mat_all)

        self.btn_mat_raw = QPushButton("原料")
        self.btn_mat_raw.setCheckable(True)
        self.btn_mat_raw.setMinimumWidth(70)
        self.btn_mat_raw.clicked.connect(lambda: self._set_mat_filter("raw"))
        filter_layout.addWidget(self.btn_mat_raw)

        self.btn_mat_pkg = QPushButton("包材")
        self.btn_mat_pkg.setCheckable(True)
        self.btn_mat_pkg.setMinimumWidth(70)
        self.btn_mat_pkg.clicked.connect(lambda: self._set_mat_filter("pkg"))
        filter_layout.addWidget(self.btn_mat_pkg)

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
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(28)

        # 列宽可拖拽调整：Interactive 模式 + 初始按内容自适应 + 限制最大宽度防超宽
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(50)
        header.setMaximumSectionSize(420)
        header.setStretchLastSection(False)

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

    def _set_mat_filter(self, mode):
        """料别筛选（全部/原料/包材），与已读状态筛选独立叠加"""
        self.mat_filter = mode
        self.btn_mat_all.setChecked(mode == "all")
        self.btn_mat_raw.setChecked(mode == "raw")
        self.btn_mat_pkg.setChecked(mode == "pkg")
        self._apply_filter()

    def _read_mask(self, df, mode):
        """已读状态掩码：all=全True / unread=_read==0 / read=_read==1"""
        if "_read" in df.columns:
            r = pd.to_numeric(df["_read"], errors="coerce").fillna(0).astype(int)
        else:
            r = pd.Series(0, index=df.index)
        if mode == "unread":
            return r == 0
        if mode == "read":
            return r == 1
        return pd.Series(True, index=df.index)

    def _mat_mask(self, df, mode):
        """料别掩码：all=全True / raw=物料类型=='原料' / pkg=='包材'

        料别列取「物料类型」（analyzer 按物料编码前缀推断：20→包材、30→原料）。
        列缺失时一律返回全 True，等同于不做料别过滤（按钮此时已隐藏）。
        """
        if mode == "all" or not self._mat_col or self._mat_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._mat_col].astype(str).str.strip()
        return vals == ("原料" if mode == "raw" else "包材")

    def _apply_filter(self):
        """从 original_df 重新过滤并刷新模型（已读状态 × 料别 两组条件叠加）"""
        if not hasattr(self, "original_df") or self.original_df is None:
            return
        df = self.original_df.copy()
        if df.empty:
            if hasattr(self, "source_model"):
                self.source_model.setDataFrame(df)
            self._update_button_counts()
            return

        if "_read" not in df.columns:
            df["_read"] = 0

        filtered = df[self._read_mask(df, self.filter_mode)
                      & self._mat_mask(df, self.mat_filter)].copy()

        filtered = filtered.reset_index(drop=True)
        if hasattr(self, "source_model"):
            self.source_model.setDataFrame(filtered)
        self._update_button_counts()

    def _update_button_counts(self):
        """按钮上显示条数：每个按钮显示「点它之后会得到多少条」（另一组条件保持当前选择）"""
        try:
            df = self.original_df
            if df is None or df.empty:
                for b, t in [(self.btn_all, "全部"), (self.btn_unread, "未读"),
                             (self.btn_read, "已读"), (self.btn_mat_all, "全部"),
                             (self.btn_mat_raw, "原料"), (self.btn_mat_pkg, "包材")]:
                    b.setText(f"{t} (0)")
                return
            cur_read = self._read_mask(df, self.filter_mode)
            cur_mat = self._mat_mask(df, self.mat_filter)
            # 已读状态组：固定当前料别，看三种状态各多少条
            self.btn_all.setText(f"全部 ({int(cur_mat.sum())})")
            self.btn_unread.setText(
                f"未读 ({int((self._read_mask(df, 'unread') & cur_mat).sum())})")
            self.btn_read.setText(
                f"已读 ({int((self._read_mask(df, 'read') & cur_mat).sum())})")
            # 料别组：固定当前已读状态，看三种料别各多少条
            self.btn_mat_all.setText(f"全部 ({int(cur_read.sum())})")
            self.btn_mat_raw.setText(
                f"原料 ({int((cur_read & self._mat_mask(df, 'raw')).sum())})")
            self.btn_mat_pkg.setText(
                f"包材 ({int((cur_read & self._mat_mask(df, 'pkg')).sum())})")
        except Exception:
            pass

    def set_data(self, df):
        """设置表格数据 - 确保 _read / data_id / 状态 列存在，初始按内容自适应列宽"""
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
        # 派生「状态」列（已读/未读），供看板显示
        if "_read" in df.columns:
            df["状态"] = df["_read"].map({0: "未读", 1: "已读"})
            df = df[["状态"] + [c for c in df.columns if c != "状态"]]
        self.original_df = df.copy()

        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)

        # 初始按内容自适应，之后用户可拖拽调整（Interactive 模式）。
        # ⚠️ 必须在下一轮事件循环再 resizeColumnsToContents：set_data 在 __init__ 中调用
        # 同步执行该方法会逐行测宽，万行级数据直接卡死主线程、整窗变黑且「未响应」。
        # 延迟后弹窗先渲染、用户立即可见，再后台测宽不阻塞交互。
        QTimer.singleShot(0, lambda: self.table_view.resizeColumnsToContents())
        self.table_view.verticalHeader().setDefaultSectionSize(28)

        if '_read' in df.columns:
            col_idx = df.columns.get_loc('_read')
            self.table_view.setColumnHidden(col_idx, True)
        if 'data_id' in df.columns:
            col_idx = df.columns.get_loc('data_id')
            self.table_view.setColumnHidden(col_idx, True)

        # 探测料别列（物料类型：20开头→包材、30开头→原料）；列缺失则隐藏整组料别按钮
        self._mat_col = next(
            (c for c in ['物料类型', '物料大类'] if c in df.columns), None)
        has_mat = self._mat_col is not None
        for w in (self.mat_sep, self.lbl_mat, self.btn_mat_all,
                  self.btn_mat_raw, self.btn_mat_pkg):
            w.setVisible(has_mat)
        # 料别默认「全部」（直接置状态，避免与下面的 _set_filter 重复过滤一次）
        self.mat_filter = "all"
        self.btn_mat_all.setChecked(True)
        self.btn_mat_raw.setChecked(False)
        self.btn_mat_pkg.setChecked(False)

        # 默认打开时显示未读
        self._set_filter("unread")

    def _filter_desc(self):
        """当前筛选条件的中文描述，用于默认文件名与提示语"""
        state = {"all": "全部", "unread": "未读", "read": "已读"}.get(self.filter_mode, "全部")
        parts = [state]
        if self._mat_col:
            mat = {"all": "", "raw": "原料", "pkg": "包材"}.get(self.mat_filter, "")
            if mat:
                parts.append(mat)
        return "_".join(parts)

    def export_excel(self):
        """导出当前筛选+排序后、表格里实际显示的记录（非全量）。

        表格直接绑定 source_model 且 DataFrameModel.sort() 就地排序 _data，
        故 getDataFrame() 即为屏幕所见的那一份。
        """
        cur_df = self.source_model.getDataFrame() if hasattr(self, "source_model") else None
        if cur_df is None or cur_df.empty:
            toast("当前筛选结果为空，无可导出的记录", parent=self)
            return

        desc = self._filter_desc()
        default_name = f"偏差率预警_{desc}.xlsx" if desc else "偏差率预警.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, f"导出偏差率预警列表（当前筛选：{desc}，共 {len(cur_df)} 条）",
            default_name, "Excel files (*.xlsx)")
        if path:
            from gui_pyside6.save_guard import safe_save
            export_df = cur_df.drop(columns=['_read', 'data_id'], errors='ignore')
            saved = safe_save(self, path,
                              lambda p: export_df.to_excel(p, index=False),
                              what="预警列表")
            if saved:
                toast(f"已导出 {len(export_df)} 条记录（{desc}）到 {saved}", parent=self)

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
            save_read_status(data_id, 1, fingerprint, snapshot_qty=snapshot_qty_for(df, data_id), snapshot_note=snapshot_note_for(df, data_id))
            self._refresh_main_table_once()
            pass  # 不弹 toast，避免刷屏

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
