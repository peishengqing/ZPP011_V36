# -*- coding: utf-8 -*-
"""负损(含未投料)看板对话框。

独立看板：显示「名称含指定关键词 且 负损(含未投料)」的记录，与主表/隔离区解耦。
- 不做任何自动整理；仅支持手动「加入隔离区 / 取消隔离」(与隔离区对话框一致的能力)。
- 关键词可编辑，默认 彩罐,托盘,手包袋；「包含未投料」勾选框默认开（实际=0 也视为负损，
  即 0<=实际<定额；取消勾选则退化为 0<实际<定额）。
- 数据由主窗口传入全量主表（已裁剪关键列），筛选在本对话框内完成，便于关键词/复选框即时重算。
"""

import re
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel, QLineEdit,
    QCheckBox, QDialogButtonBox, QComboBox, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import add_quarantine_batch, remove_quarantine, get_quarantined_ids
from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.table_sort import enable_click_sort


class NegLossDashboardDialog(QDialog):
    """负损(含未投料)看板：名称关键词 × 负损(含未投料) 的只读+手动隔离视图。"""

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("负损(含未投料)看板 - 彩罐/托盘/手包袋")
        self.resize(1280, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.main_window = main_window
        self._keywords = "彩罐,托盘,手包袋"
        self._include_zero = True
        self._semi_class_filter = "all"  # 半成品重分类筛选
        self._semi_class_col = None   # 半成品重分类列名（set_data 时探测）
        self.original_df = None
        self.source_model = None
        self._kw_timer = None
        self.setup_ui()
        self.set_data(df)

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ---- 顶部筛选栏 ----
        top = QHBoxLayout()
        top.addWidget(QLabel("名称关键词(逗号分隔):"))
        self.edit_keywords = QLineEdit(self._keywords)
        self.edit_keywords.setMinimumWidth(220)
        self.edit_keywords.setMaximumWidth(320)
        top.addWidget(self.edit_keywords)
        self.edit_keywords.textChanged.connect(self._on_keywords_changed)

        self.chk_include_zero = QCheckBox("包含未投料(实际=0 也视为负损)")
        self.chk_include_zero.setChecked(True)
        self.chk_include_zero.stateChanged.connect(self._on_include_zero_changed)
        top.addWidget(self.chk_include_zero)

        top.addSpacing(12)
        self.semi_sep = QFrame()
        self.semi_sep.setFrameShape(QFrame.VLine)
        self.semi_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.semi_sep)
        top.addSpacing(12)
        self.lbl_semi_class = QLabel("半成品分类:")
        top.addWidget(self.lbl_semi_class)
        self.combo_semi_class = QComboBox()
        self.combo_semi_class.setMinimumWidth(140)
        self.combo_semi_class.setMaximumWidth(200)
        self.combo_semi_class.setEditable(False)
        self.combo_semi_class.addItem("全部")
        self.combo_semi_class.currentTextChanged.connect(self._on_semi_class_changed)
        top.addWidget(self.combo_semi_class)

        top.addStretch()
        self.lbl_count = QLabel("共 0 条")
        self.lbl_count.setStyleSheet("color:#666;")
        top.addWidget(self.lbl_count)
        self.btn_refresh = QPushButton("重新筛选")
        self.btn_refresh.clicked.connect(self._apply_filter)
        top.addWidget(self.btn_refresh)
        layout.addLayout(top)

        # ---- 表格 ----
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._sort_ctrl = enable_click_sort(
            self.table_view, lambda: getattr(self, "source_model", None), skip_cols=())
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(50)
        header.setMaximumSectionSize(420)
        header.setStretchLastSection(False)
        self.table_view.installEventFilter(self)
        layout.addWidget(self.table_view)

        # ---- 底部按钮 ----
        btn_layout = QHBoxLayout()
        self.btn_add_quar = QPushButton("⚠️ 加入隔离区(选中行)")
        self.btn_add_quar.clicked.connect(self._add_selected_to_quarantine)
        btn_layout.addWidget(self.btn_add_quar)
        export_btn = QPushButton("📎 导出 Excel")
        export_btn.clicked.connect(self.export_excel)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ 筛选逻辑
    def _on_keywords_changed(self, text):
        self._keywords = text
        if self._kw_timer is None:
            self._kw_timer = QTimer(self)
            self._kw_timer.setSingleShot(True)
            self._kw_timer.setInterval(300)
            self._kw_timer.timeout.connect(self._apply_filter)
        self._kw_timer.start()

    def _on_include_zero_changed(self, state):
        self._include_zero = (state != 0)
        self._apply_filter()

    def _on_semi_class_changed(self, text):
        self._semi_class_filter = "all" if text == "全部" else text
        self._apply_filter()

    @staticmethod
    def _name_cols(df):
        """扩大搜索范围：物料名称/描述/组件物料描述 + 物料编码 + 车间 + 备注/备注原因。"""
        cols = [c for c in ["物料名称", "物料描述", "组件物料描述", "物料编码"] if c in df.columns]
        for c in ["车间", "备注", "备注原因"]:
            if c in df.columns:
                cols.append(c)
        return cols

    def _neg_loss_mask(self, df):
        """负损掩码：0<=实际<定额(含未投料) 或 0<实际<定额(不含未投料)。列缺失则全 False。"""
        act_col = next((c for c in ["数量-实际", "实际", "实际数量", "数量 - 实际", "actual"]
                        if c in df.columns), None)
        qty_col = next((c for c in ["数量-定额", "定额", "定额数量", "数量 - 定额", "quota"]
                        if c in df.columns), None)
        if not act_col or not qty_col:
            return pd.Series(False, index=df.index)
        a = pd.to_numeric(df[act_col], errors="coerce")
        q = pd.to_numeric(df[qty_col], errors="coerce")
        if self._include_zero:
            return a.notna() & (a >= 0) & q.notna() & (a < q)
        return a.notna() & (a > 0) & q.notna() & (a < q)

    def _semi_class_mask(self, df, mode):
        """半成品重分类掩码：all=全True / 分类名=列值==该分类"""
        if mode == "all" or not self._semi_class_col:
            return pd.Series(True, index=df.index)
        if self._semi_class_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._semi_class_col].astype(str).str.strip()
        return vals == mode

    def _name_mask(self, df):
        """名称关键词掩码：逗号/、/，分隔多值 OR；无关键词=全 True；无名称列=全 True。"""
        kws = [k.strip() for k in re.split("[,，、]", self._keywords) if k.strip()]
        if not kws:
            return pd.Series(True, index=df.index)
        cols = self._name_cols(df)
        if not cols:
            return pd.Series(True, index=df.index)
        m = pd.Series(False, index=df.index)
        for c in cols:
            s = df[c].astype(str).fillna("")
            for kw in kws:
                m = m | s.str.contains(kw, regex=False)
        return m

    # ------------------------------------------------------------------ 数据装载
    def set_data(self, df):
        df = df.copy()
        # 确保 data_id 存在（隔离区同步用）
        if "data_id" not in df.columns:
            if all(c in df.columns for c in ["订单日期", "流程订单", "物料编码"]):
                df["data_id"] = (df["订单日期"].astype(str) + "|" +
                                 df["流程订单"].astype(str) + "|" +
                                 df["物料编码"].astype(str))
            elif "工厂" in df.columns:
                df["data_id"] = (df["工厂"].astype(str) + "|" +
                                 df["订单日期"].astype(str) + "|" +
                                 df["流程订单"].astype(str) + "|" +
                                 df["物料编码"].astype(str))
        # 隔离区列：比对当前隔离集合（兼容4段uid与历史3段uid）
        try:
            _qset = get_quarantined_ids()
        except Exception:
            _qset = set()
        if "data_id" in df.columns:
            _did = df["data_id"].astype(str)
            _m = _did.isin(_qset)  # 直接匹配主表4段 data_id
            # 兼容历史3段 uid：隔离集合中取"后3段"(订单日期|流程订单|物料编码)与主表 data_id 后3段比对
            if _qset:
                _qset_tail3 = {u if len(u.split("|")) < 4 else "|".join(u.split("|")[-3:])
                               for u in _qset}
                _tail3 = _did.str.split("|").str[-3:].str.join("|")
                _m = _m | _tail3.isin(_qset_tail3)
            df["隔离区"] = _m.map({True: "是", False: ""})
        else:
            df["隔离区"] = ""
        # 备注列移到 data_id 前面，便于一眼看到疑难原因
        if "备注" in df.columns and "data_id" in df.columns:
            cols = list(df.columns)
            cols.remove("备注")
            cols.insert(cols.index("data_id"), "备注")
            df = df[cols]

        self.original_df = df.copy()
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)
        QTimer.singleShot(0, lambda: self.table_view.resizeColumnsToContents())
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        if "data_id" in df.columns:
            self.table_view.setColumnHidden(df.columns.get_loc("data_id"), True)
        # 初始化半成品重分类筛选器
        self._semi_class_filter = "all"
        self._semi_class_col = "半成品重分类" if "半成品重分类" in df.columns else None
        if self._semi_class_col:
            unique_vals = df["半成品重分类"].dropna().astype(str).str.strip().unique()
            unique_vals = [v for v in unique_vals if v]
            self.combo_semi_class.addItems(sorted(unique_vals))
        else:
            self.combo_semi_class.setVisible(False)
            self.semi_sep.setVisible(False)
            self.lbl_semi_class.setVisible(False)
        self._apply_filter()

    def _apply_filter(self):
        if self.original_df is None or not hasattr(self, "source_model"):
            return
        df = self.original_df
        if df.empty:
            self.source_model.setDataFrame(df)
            self._sort_ctrl.reapply()
            self.lbl_count.setText("共 0 条")
            return
        mask = self._name_mask(df) & self._neg_loss_mask(df) & self._semi_class_mask(df, self._semi_class_filter)
        filtered = df[mask].copy().reset_index(drop=True)
        self.source_model.setDataFrame(filtered)
        self._sort_ctrl.reapply()
        tag = "含未投料" if self._include_zero else "不含未投料"
        self.lbl_count.setText("共 %d 条（名称含「%s」· %s）" % (len(filtered), self._keywords, tag))

    # ------------------------------------------------------------------ 复制
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
        min_r, max_r, min_c, max_c = float('inf'), -1, float('inf'), -1
        for idx in indexes:
            r, c = idx.row(), idx.column()
            cells[(r, c)] = str(idx.data(Qt.DisplayRole) or "").replace("\n", " ").replace("\r", "")
            min_r, max_r = min(min_r, r), max(max_r, r)
            min_c, max_c = min(min_c, c), max(max_c, c)
        if max_r < 0:
            return
        lines = ["\t".join(cells.get((r, c), "") for c in range(min_c, max_c + 1))
                 for r in range(min_r, max_r + 1)]
        QApplication.clipboard().setText("\n".join(lines))

    # ------------------------------------------------------------------ 右键菜单
    def show_context_menu(self, pos):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        selection = self.table_view.selectionModel()
        selected_rows = sorted(set(idx.row() for idx in selection.selectedIndexes()))
        if index.row() not in selected_rows:
            self.table_view.clearSelection()
            self.table_view.selectRow(index.row())
            selected_rows = [index.row()]
        menu = QMenu()
        add_action = menu.addAction("⚠️ 加入隔离区(选中行)")
        add_action.triggered.connect(lambda: self._add_selected_to_quarantine())
        df = self.source_model.getDataFrame()
        if df is not None and selected_rows and "隔离区" in df.columns:
            try:
                all_q = all(str(df.iloc[r].get("隔离区", "")).strip() == "是"
                            for r in selected_rows if r < len(df))
            except Exception:
                all_q = False
            if all_q:
                cancel_action = menu.addAction("↩ 取消隔离(选中行)")
                cancel_action.triggered.connect(lambda: self._cancel_selected_quarantine())
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _selected_ids(self):
        df = self.source_model.getDataFrame() if hasattr(self, "source_model") else None
        if df is None:
            return set()
        selection = self.table_view.selectionModel()
        if not selection:
            return set()
        rows = sorted(set(idx.row() for idx in selection.selectedIndexes()))
        ids = set()
        for r in rows:
            if r >= len(df):
                continue
            did = df.iloc[r].get("data_id")
            if not did:
                rs = df.iloc[r]
                if "工厂" in df.columns:
                    did = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
                else:
                    did = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            if did:
                ids.add(str(did))
        return ids

    def _add_selected_to_quarantine(self):
        ids = self._selected_ids()
        if not ids:
            toast("请先选中要加入隔离区的行", parent=self)
            return
        reason = _ask_quarantine_reason(self, "加入隔离区")
        if reason is None:
            return
        basis = "手动:" + reason
        add_quarantine_batch([(uid, reason, basis) for uid in ids])
        self._sync_quarantine(ids, True)
        toast(f"⚠️ 已加入隔离区 {len(ids)} 条", parent=self)

    def _cancel_selected_quarantine(self):
        ids = self._selected_ids()
        if not ids:
            return
        for uid in ids:
            remove_quarantine(uid)
        self._sync_quarantine(ids, False)
        toast(f"↩ 已取消隔离 {len(ids)} 条", parent=self)

    def _sync_quarantine(self, ids, flag):
        """同步主表内存 _quarantined + source_model，并刷新本看板隔离区列（与隔离区对话框一致）。"""
        main_df = self.main_window.view_model.df if self.main_window else None
        if main_df is not None and "data_id" in main_df.columns and "_quarantined" in main_df.columns:
            main_df.loc[main_df["data_id"].isin(ids), "_quarantined"] = 1 if flag else 0
            self.main_window.view_model.df = main_df
            if self.main_window.source_model is not None:
                self.main_window.source_model.mark_quarantine(ids, flag)
                if hasattr(self.main_window, "_apply_column_visibility_by_name"):
                    self.main_window._apply_column_visibility_by_name()
            if hasattr(self.main_window, "stats_cards") and self.main_window.stats_cards is not None:
                self.main_window.stats_cards.refresh(main_df)
        if (hasattr(self, "original_df") and "data_id" in self.original_df.columns
                and "隔离区" in self.original_df.columns):
            self.original_df.loc[self.original_df["data_id"].isin(ids), "隔离区"] = "是" if flag else ""
        self._apply_filter()

    def on_double_click(self, index):
        if not index.isValid():
            return
        df = self.source_model.getDataFrame()
        if index.row() < len(df):
            try:
                self.main_window.locate_record(df.iloc[index.row()])
            except Exception:
                pass
            self.accept()

    # ------------------------------------------------------------------ 导出
    def export_excel(self):
        cur_df = self.source_model.getDataFrame() if hasattr(self, "source_model") else None
        if cur_df is None or cur_df.empty:
            toast("当前筛选结果为空，无可导出的记录", parent=self)
            return
        from gui_pyside6.save_guard import safe_save
        default_name = "负损含未投料看板.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, f"导出负损看板（共 {len(cur_df)} 条）", default_name, "Excel files (*.xlsx)")
        if path:
            export_df = cur_df.drop(columns=['data_id'], errors='ignore')
            saved = safe_save(self, path, lambda p: export_df.to_excel(p, index=False), what="负损看板")
            if saved:
                toast(f"已导出 {len(export_df)} 条记录到 {saved}", parent=self)


def _ask_quarantine_reason(parent, title: str) -> str | None:
    """弹出自定义「加入隔离区」对话框（显式确定/取消按钮，替代 QInputDialog.getText）。
    返回原因字符串，点取消/关闭返回 None。
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setFixedWidth(420)
    layout = QVBoxLayout(dlg)

    hint = QLabel("填写疑难原因（可选）：")
    layout.addWidget(hint)

    edit = QLineEdit()
    edit.setPlaceholderText("留空则默认填入「手动隔离」")
    layout.addWidget(edit)

    btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)
    layout.addWidget(btn_box)

    edit.setFocus()
    if dlg.exec() == QDialog.Accepted:
        return edit.text().strip() or "手动隔离"
    return None
