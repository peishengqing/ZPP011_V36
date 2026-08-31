# -*- coding: utf-8 -*-
"""
偏差率预警看板对话框 - 仅显示 |偏差率| >= 10% 的预警记录，
支持：列宽可拖拽调整、点击列头排序、Ctrl+C 复制、标记已读/未读、导出、双击定位主表。

数据源由主窗口预筛选（|偏差率(%)| >= 10）后传入，本对话框只负责展示与交互。
交互与「替代料看板」(alert_dialog.AlertDialog) 保持一致，仅列宽策略改为可拖拽。
"""

import re
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel, QFrame,
    QComboBox, QLineEdit, QDialogButtonBox, QGroupBox, QCheckBox, QGridLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QPoint, QTimer
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.read_status import save_read_status, save_read_status_batch
from core.quarantine_manager import add_quarantine_batch, remove_quarantine
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for
from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.table_sort import enable_click_sort


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
        self._workshop_filter = "all"  # 车间筛选：all / 车间名
        self._workshop_col = None   # 车间列名，set_data 时探测
        self._factory_filter = "all"  # 工厂筛选：all / 工厂名
        self._factory_col = None    # 工厂列名，set_data 时探测
        self._quar_filter = "all"   # 隔离区筛选：all / yes(是)
        self._alt_filter = "all"    # 替代料筛选：all / yes(是) / no(否)
        self._keyword = ""          # 关键字搜索（跨列，与分类筛选叠加）
        self._remark_filter = "all"   # 是否备注筛选：all / has(有) / none(无)
        self._remark_col_name = None  # 备注列名（set_data 时探测）
        self._semi_class_filter = set()  # 半成品重分类筛选：空集合=全部 / 集合内为选中分类（虚拟项模糊匹配）
        self._semi_class_col = None   # 半成品重分类列名（set_data 时探测）
        self._mtd_filter = "all"      # 组件物料类型描述筛选（全部/具体类型）
        self._mtd_col = None          # 组件物料类型描述列名（set_data 时探测）
        self.setup_ui()
        self.set_data(warnings_df)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ---- 顶部筛选栏（垂直布局，每行一个筛选组）----
        self._main_filter_vlayout = QVBoxLayout()
        self._main_filter_vlayout.setSpacing(4)
        self._main_filter_vlayout.setContentsMargins(0, 0, 0, 0)

        # ==== 第1行：已读状态 + 关键字搜索 ====
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("筛选:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("关键字搜索(全列,逗号分隔多值OR)")
        self.search_edit.setToolTip("全列关键字搜索：匹配任意文本列(名称/编码/车间/备注/原因等)，逗号或顿号分隔多值OR")
        self.search_edit.setMinimumWidth(200)
        self.search_edit.setMaximumWidth(260)
        row1.addWidget(self.search_edit)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_search_changed)
        self.search_edit.textChanged.connect(lambda _t: self._search_timer.start())

        self.btn_all = QPushButton("全部")
        self.btn_all.setCheckable(True)
        self.btn_all.setMinimumWidth(70)
        self.btn_all.clicked.connect(lambda: self._set_filter("all"))
        row1.addWidget(self.btn_all)

        self.btn_unread = QPushButton("未读")
        self.btn_unread.setCheckable(True)
        self.btn_unread.setMinimumWidth(70)
        self.btn_unread.clicked.connect(lambda: self._set_filter("unread"))
        row1.addWidget(self.btn_unread)

        self.btn_read = QPushButton("已读")
        self.btn_read.setCheckable(True)
        self.btn_read.setMinimumWidth(70)
        self.btn_read.clicked.connect(lambda: self._set_filter("read"))
        row1.addWidget(self.btn_read)

        # 工厂筛选（始终可见，放在第1行末尾）
        row1.addSpacing(16)
        row1.addWidget(QLabel("工厂:"))
        self.combo_factory = QComboBox()
        self.combo_factory.setMinimumWidth(100)
        self.combo_factory.setMaximumWidth(160)
        self.combo_factory.setEditable(False)
        self.combo_factory.addItem("全部")
        self.combo_factory.currentTextChanged.connect(self._on_factory_changed)
        row1.addWidget(self.combo_factory)

        # 隔离区筛选（始终可见，放第1行工厂筛选之后，与已读/工厂并列）
        row1.addSpacing(16)
        self.quar_sep = QFrame()
        self.quar_sep.setFrameShape(QFrame.VLine)
        self.quar_sep.setFrameShadow(QFrame.Sunken)
        row1.addWidget(self.quar_sep)
        row1.addSpacing(8)
        self.lbl_quar = QLabel("隔离区:")
        row1.addWidget(self.lbl_quar)
        self.btn_quar_all = QPushButton("全部")
        self.btn_quar_all.setCheckable(True)
        self.btn_quar_all.setMinimumWidth(70)
        self.btn_quar_all.clicked.connect(lambda: self._set_quar_filter("all"))
        row1.addWidget(self.btn_quar_all)
        self.btn_quar_yes = QPushButton("是")
        self.btn_quar_yes.setCheckable(True)
        self.btn_quar_yes.setMinimumWidth(70)
        self.btn_quar_yes.clicked.connect(lambda: self._set_quar_filter("yes"))
        row1.addWidget(self.btn_quar_yes)
        self.btn_quar_no = QPushButton("否")
        self.btn_quar_no.setCheckable(True)
        self.btn_quar_no.setMinimumWidth(70)
        self.btn_quar_no.clicked.connect(lambda: self._set_quar_filter("no"))
        row1.addWidget(self.btn_quar_no)

        # 车间筛选（始终可见，放第1行隔离区之后，与工厂/隔离区并列）
        row1.addSpacing(16)
        self.workshop_sep = QFrame()
        self.workshop_sep.setFrameShape(QFrame.VLine)
        self.workshop_sep.setFrameShadow(QFrame.Sunken)
        row1.addWidget(self.workshop_sep)
        row1.addSpacing(8)
        self.lbl_workshop = QLabel("车间:")
        row1.addWidget(self.lbl_workshop)
        self.combo_workshop = QComboBox()
        self.combo_workshop.setMinimumWidth(100)
        self.combo_workshop.setMaximumWidth(160)
        self.combo_workshop.setEditable(False)
        self.combo_workshop.addItem("全部")
        self.combo_workshop.currentTextChanged.connect(self._on_workshop_changed)
        row1.addWidget(self.combo_workshop)

        row1.addStretch()
        self._main_filter_vlayout.addLayout(row1)

        # ==== 第2行：料别 + 半成品分类（全屏时显示；车间已提至第1行始终可见）====
        self._row2_widget = QWidget()
        self._row2 = QHBoxLayout(self._row2_widget)
        # 料别筛选
        self.mat_sep = QFrame()
        self.mat_sep.setFrameShape(QFrame.VLine)
        self.mat_sep.setFrameShadow(QFrame.Sunken)
        self._row2.addWidget(self.mat_sep)
        self._row2.addSpacing(8)

        self.lbl_mat = QLabel("料别:")
        self._row2.addWidget(self.lbl_mat)

        self.btn_mat_all = QPushButton("全部")
        self.btn_mat_all.setCheckable(True)
        self.btn_mat_all.setMinimumWidth(70)
        self.btn_mat_all.clicked.connect(lambda: self._set_mat_filter("all"))
        self._row2.addWidget(self.btn_mat_all)

        self.btn_mat_raw = QPushButton("原料")
        self.btn_mat_raw.setCheckable(True)
        self.btn_mat_raw.setMinimumWidth(70)
        self.btn_mat_raw.clicked.connect(lambda: self._set_mat_filter("raw"))
        self._row2.addWidget(self.btn_mat_raw)

        self.btn_mat_pkg = QPushButton("包材")
        self.btn_mat_pkg.setCheckable(True)
        self.btn_mat_pkg.setMinimumWidth(70)
        self.btn_mat_pkg.clicked.connect(lambda: self._set_mat_filter("pkg"))
        self._row2.addWidget(self.btn_mat_pkg)

        self.btn_mat_semi = QPushButton("半成品")
        self.btn_mat_semi.setCheckable(True)
        self.btn_mat_semi.setMinimumWidth(70)
        self.btn_mat_semi.clicked.connect(lambda: self._set_mat_filter("semi"))
        self._row2.addWidget(self.btn_mat_semi)

        # 半成品分类
        self.semi_class_sep = QFrame()
        self.semi_class_sep.setFrameShape(QFrame.VLine)
        self.semi_class_sep.setFrameShadow(QFrame.Sunken)
        self._row2.addWidget(self.semi_class_sep)
        self._row2.addSpacing(8)

        self.lbl_semi_class = QLabel("半成品分类:")
        self._row2.addWidget(self.lbl_semi_class)

        self.grp_semi_class = QGroupBox()
        self.grp_semi_class.setFlat(True)
        self.grp_semi_class.setMinimumWidth(220)
        self._semi_class_grid = QGridLayout(self.grp_semi_class)
        self._semi_class_grid.setContentsMargins(6, 4, 6, 4)
        self._semi_class_grid.setSpacing(3)
        self._semi_class_checkboxes = {}
        self._row2.addWidget(self.grp_semi_class)

        self._row2.addStretch()
        self._main_filter_vlayout.addWidget(self._row2_widget)
        self._row2_widget.setVisible(False)  # 默认隐藏，全屏时显示

        # ==== 第3行：物料类型 + 替代料 + 是否备注（全屏时显示；隔离区已提至第1行始终可见）====
        self._row3_widget = QWidget()
        self._row3 = QHBoxLayout(self._row3_widget)
        # 物料类型
        self.mtd_sep = QFrame()
        self.mtd_sep.setFrameShape(QFrame.VLine)
        self.mtd_sep.setFrameShadow(QFrame.Sunken)
        self._row3.addWidget(self.mtd_sep)
        self._row3.addSpacing(8)

        self.lbl_mtd = QLabel("物料类型:")
        self._row3.addWidget(self.lbl_mtd)

        self.combo_mtd = QComboBox()
        self.combo_mtd.setMinimumWidth(100)
        self.combo_mtd.setMaximumWidth(140)
        self.combo_mtd.setEditable(False)
        self.combo_mtd.addItem("全部")
        self.combo_mtd.currentTextChanged.connect(self._on_mtd_changed)
        self._row3.addWidget(self.combo_mtd)

        # 替代料
        self.alt_sep = QFrame()
        self.alt_sep.setFrameShape(QFrame.VLine)
        self.alt_sep.setFrameShadow(QFrame.Sunken)
        self._row3.addWidget(self.alt_sep)
        self._row3.addSpacing(8)

        self.lbl_alt = QLabel("替代料:")
        self._row3.addWidget(self.lbl_alt)

        self.btn_alt_all = QPushButton("全部")
        self.btn_alt_all.setCheckable(True)
        self.btn_alt_all.setMinimumWidth(70)
        self.btn_alt_all.clicked.connect(lambda: self._set_alt_filter("all"))
        self._row3.addWidget(self.btn_alt_all)

        self.btn_alt_yes = QPushButton("是")
        self.btn_alt_yes.setCheckable(True)
        self.btn_alt_yes.setMinimumWidth(70)
        self.btn_alt_yes.clicked.connect(lambda: self._set_alt_filter("yes"))
        self._row3.addWidget(self.btn_alt_yes)

        self.btn_alt_no = QPushButton("否")
        self.btn_alt_no.setCheckable(True)
        self.btn_alt_no.setMinimumWidth(70)
        self.btn_alt_no.clicked.connect(lambda: self._set_alt_filter("no"))
        self._row3.addWidget(self.btn_alt_no)

        # 是否备注
        self.remark_sep = QFrame()
        self.remark_sep.setFrameShape(QFrame.VLine)
        self.remark_sep.setFrameShadow(QFrame.Sunken)
        self._row3.addWidget(self.remark_sep)
        self._row3.addSpacing(8)

        self.lbl_remark = QLabel("是否备注:")
        self._row3.addWidget(self.lbl_remark)

        self.btn_remark_all = QPushButton("全部")
        self.btn_remark_all.setCheckable(True)
        self.btn_remark_all.setMinimumWidth(70)
        self.btn_remark_all.clicked.connect(lambda: self._set_remark_filter("all"))
        self._row3.addWidget(self.btn_remark_all)

        self.btn_remark_has = QPushButton("有")
        self.btn_remark_has.setCheckable(True)
        self.btn_remark_has.setMinimumWidth(70)
        self.btn_remark_has.clicked.connect(lambda: self._set_remark_filter("has"))
        self._row3.addWidget(self.btn_remark_has)

        self.btn_remark_none = QPushButton("无")
        self.btn_remark_none.setCheckable(True)
        self.btn_remark_none.setMinimumWidth(70)
        self.btn_remark_none.clicked.connect(lambda: self._set_remark_filter("none"))
        self._row3.addWidget(self.btn_remark_none)

        self._row3.addStretch()
        self._main_filter_vlayout.addWidget(self._row3_widget)
        self._row3_widget.setVisible(False)  # 默认隐藏，全屏时显示

        # ==== 第4行：批量操作 + 放大按钮（全屏时显示）====
        self._row4_widget = QWidget()
        self._row4 = QHBoxLayout(self._row4_widget)
        self.btn_batch_read = QPushButton("批量标记已读")
        self.btn_batch_read.setMinimumWidth(100)
        self.btn_batch_read.clicked.connect(self.batch_mark_read)
        self._row4.addWidget(self.btn_batch_read)

        self.btn_batch_unread = QPushButton("批量标记未读")
        self.btn_batch_unread.setMinimumWidth(100)
        self.btn_batch_unread.clicked.connect(self.batch_mark_unread)
        self._row4.addWidget(self.btn_batch_unread)

        self.btn_fullscreen = QPushButton("⛶ 放大")
        self.btn_fullscreen.setMinimumWidth(80)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self._row4.addWidget(self.btn_fullscreen)

        self._main_filter_vlayout.addWidget(self._row4_widget)
        self._row4_widget.setVisible(False)  # 默认隐藏，全屏时显示

        layout.addLayout(self._main_filter_vlayout)

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

    def _on_search_changed(self):
        """关键字搜索框防抖回调：更新关键字并重新筛选"""
        self._keyword = self.search_edit.text().strip()
        self._apply_filter()

    def _keyword_mask(self, df):
        """跨列全列关键字掩码：逗号/、/，分隔多值 OR；任一（非内部）列包含即命中；空关键字=全True。"""
        if not self._keyword:
            return pd.Series(True, index=df.index)
        kws = [k.strip().lower() for k in re.split("[,，、]", self._keyword) if k.strip()]
        if not kws:
            return pd.Series(True, index=df.index)
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            if col in ('_read', '_post_audit_changed', '状态', 'data_id'):
                continue
            s = df[col].astype(str).str.lower()
            for kw in kws:
                mask = mask | s.str.contains(kw, na=False, regex=False)
        return mask

    def _set_filter(self, mode):
        self.filter_mode = mode
        self.btn_all.setChecked(mode == "all")
        self.btn_unread.setChecked(mode == "unread")
        self.btn_read.setChecked(mode == "read")
        self._apply_filter()

    def _set_mat_filter(self, mode):
        """料别筛选（全部/原料/包材/半成品），与已读状态筛选独立叠加"""
        self.mat_filter = mode
        self.btn_mat_all.setChecked(mode == "all")
        self.btn_mat_raw.setChecked(mode == "raw")
        self.btn_mat_pkg.setChecked(mode == "pkg")
        self.btn_mat_semi.setChecked(mode == "semi")
        self._apply_filter()

    def _set_quar_filter(self, mode):
        """隔离区筛选（全部/是/否），与已读状态、料别、车间独立叠加"""
        self._quar_filter = mode
        self.btn_quar_all.setChecked(mode == "all")
        self.btn_quar_yes.setChecked(mode == "yes")
        self.btn_quar_no.setChecked(mode == "no")
        self._apply_filter()

    def _set_alt_filter(self, mode):
        """替代料筛选（全部/是/否），与已读状态、料别、车间独立叠加"""
        self._alt_filter = mode
        self.btn_alt_all.setChecked(mode == "all")
        self.btn_alt_yes.setChecked(mode == "yes")
        self.btn_alt_no.setChecked(mode == "no")
        self._apply_filter()

    def _set_remark_filter(self, mode):
        """是否备注筛选（全部/有/无），与已读状态、料别、车间、隔离区、替代料独立叠加"""
        self._remark_filter = mode
        self.btn_remark_all.setChecked(mode == "all")
        self.btn_remark_has.setChecked(mode == "has")
        self.btn_remark_none.setChecked(mode == "none")
        self._apply_filter()

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

    def _on_mtd_changed(self, text):
        """组件物料类型描述下拉框变化时触发筛选"""
        self._mtd_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _mtd_mask(self, df):
        """组件物料类型描述掩码：all=全True / 具体值=列值==该值。"""
        if self._mtd_filter == "all" or not self._mtd_col:
            return pd.Series(True, index=df.index)
        if self._mtd_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._mtd_col].astype(str).str.strip()
        return vals == self._mtd_filter

    def _semi_class_mask(self, df):
        """半成品重分类掩码：空集合=全True；虚拟项「食品/饮料成品半成品」精确匹配+空白
        （列值==分类名 或 列值为空 且 工厂含'食品'/'饮料'）；其他=列值精确==分类名。多值 OR。"""
        if not self._semi_class_filter or not self._semi_class_col or self._semi_class_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._semi_class_col].astype(str).str.strip()
        blank = df[self._semi_class_col].fillna('').astype(str).str.strip() == ''
        fac = df['工厂'].astype(str) if '工厂' in df.columns else pd.Series('', index=df.index)
        mask = pd.Series(False, index=df.index)
        for m in self._semi_class_filter:
            if m == "食品成品半成品":
                mask = mask | ((vals == m) | blank) & fac.str.contains('食品', na=False)
            elif m == "饮料成品半成品":
                mask = mask | ((vals == m) | blank) & fac.str.contains('饮料', na=False)
            else:
                mask = mask | (vals == m)
        return mask

    def _build_semi_checkboxes(self, unique_vals):
        """构建半成品分类复选框组：全部 + 虚拟两项 + 实际各值（QGridLayout 多列排列）。"""
        # 清空旧控件
        while self._semi_class_grid.count():
            it = self._semi_class_grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._semi_class_checkboxes = {}

        all_cb = QCheckBox("全部")
        all_cb.setChecked(True)
        all_cb.stateChanged.connect(self._on_semi_class_changed)
        self._semi_class_grid.addWidget(all_cb, 0, 0)
        self._semi_class_checkboxes["__all__"] = all_cb

        # 虚拟归并项
        virtual_items = [("食品成品半成品", 0, 1), ("饮料成品半成品", 0, 2)]
        for v, r, c in virtual_items:
            cb = QCheckBox(v)
            cb.stateChanged.connect(self._on_semi_class_changed)
            self._semi_class_grid.addWidget(cb, r, c)
            self._semi_class_checkboxes[v] = cb

        # 数据中实际出现的分类值，从第1行开始多列排列
        row = 1
        col = 0
        for v in unique_vals:
            if v in ("食品成品半成品", "饮料成品半成品"):
                continue
            cb = QCheckBox(v)
            cb.stateChanged.connect(self._on_semi_class_changed)
            self._semi_class_grid.addWidget(cb, row, col)
            self._semi_class_checkboxes[v] = cb
            col += 1
            if col >= 3:  # 每行3列
                col = 0
                row += 1

    def _quar_mask(self, df, mode):
        """隔离区掩码：all=全True / yes=隔离区列=='是' / no=隔离区列!='是'"""
        if mode == "all" or "隔离区" not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df["隔离区"].astype(str).str.strip()
        if mode == "yes":
            return vals == "是"
        return vals != "是"

    def _alt_mask(self, df, mode):
        """替代料掩码：all=全True / yes=替代料列=='是' / no=替代料列=='否'"""
        if mode == "all" or "替代料" not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df["替代料"].astype(str).str.strip()
        if mode == "yes":
            return vals == "是"
        return vals == "否"

    def _remark_mask(self, df, mode):
        """是否备注掩码：all=全True / has=备注列非空 / none=备注列为空

        备注列名在 set_data 时探测存入 self._remark_col_name；列缺失一律全 True。
        """
        if mode == "all" or not self._remark_col_name or self._remark_col_name not in df.columns:
            return pd.Series(True, index=df.index)
        col = df[self._remark_col_name]
        vals = col.apply(lambda x: "" if pd.isna(x) else str(x).strip())
        if mode == "has":
            return vals != ""
        return vals == ""

    def _on_workshop_changed(self, text):
        """车间下拉框变化时触发筛选"""
        self._workshop_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _on_factory_changed(self, text):
        """工厂下拉框变化时触发筛选"""
        self._factory_filter = "all" if text == "全部" else text
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
        """料别掩码：all=全True / raw=物料类型=='原料' / pkg=='包材' / semi=='半成品'

        料别列取「物料类型」（analyzer 按物料编码前缀推断：20→包材、30→原料、40/41→半成品）。
        列缺失时一律返回全 True，等同于不做料别过滤（按钮此时已隐藏）。
        """
        if mode == "all" or not self._mat_col or self._mat_col not in df.columns:
            return pd.Series(True, index=df.index)
        col = df[self._mat_col].astype(str).str.strip()
        if mode == "raw":
            return col.isin(["原材料", "原料"])
        if mode == "pkg":
            return col.isin(["包材", "原料"])  # 保留既有写法（包材按钮同时含原料）
        if mode == "semi":
            # 半成品：料别列值含「半成品」；若数据带「物料分类」列且其值为半成品，也命中
            semi = col.str.contains("半成品", na=False)
            if "物料分类" in df.columns:
                semi = semi | (df["物料分类"].astype(str).str.strip() == "半成品")
            return semi
        return pd.Series(True, index=df.index)

    def _workshop_mask(self, df, mode):
        """车间掩码：all=全True / 车间名=车间列==该值

        列缺失时一律返回全 True，等同于不做车间过滤（下拉框此时已隐藏）。
        """
        if mode == "all" or not self._workshop_col or self._workshop_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._workshop_col].astype(str).str.strip()
        return vals == mode

    def _factory_mask(self, df, mode):
        """工厂掩码：all=全True / 工厂名=工厂列==该值

        列缺失时一律返回全 True，等同于不做工厂过滤（下拉框此时已隐藏）。
        """
        if mode == "all" or not self._factory_col or self._factory_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._factory_col].astype(str).str.strip()
        return vals == mode

    def _apply_filter(self):
        """从 original_df 重新过滤并刷新模型（已读状态 × 料别 × 车间 三组条件叠加）"""
        if not hasattr(self, "original_df") or self.original_df is None:
            return
        df = self.original_df.copy()
        if df.empty:
            if hasattr(self, "source_model"):
                self.source_model.setDataFrame(df)
                self._sort_ctrl.reapply()  # 恢复排序态
            self._update_button_counts()
            return

        if "_read" not in df.columns:
            df["_read"] = 0

        filtered = df[self._read_mask(df, self.filter_mode)
                      & self._mat_mask(df, self.mat_filter)
                      & self._workshop_mask(df, self._workshop_filter)
                      & self._factory_mask(df, self._factory_filter)
                      & self._quar_mask(df, self._quar_filter)
                      & self._alt_mask(df, self._alt_filter)
                      & self._remark_mask(df, self._remark_filter)
                      & self._semi_class_mask(df)
                      & self._mtd_mask(df)
                      & self._keyword_mask(df)].copy()

        filtered = filtered.reset_index(drop=True)
        if hasattr(self, "source_model"):
            self.source_model.setDataFrame(filtered)
            self._sort_ctrl.reapply()  # 恢复排序态
        self._update_button_counts()

    def _update_button_counts(self):
        """按钮上显示条数：每个按钮显示「点它之后会得到多少条」（另一组条件保持当前选择）"""
        try:
            df = self.original_df
            if df is None or df.empty:
                for b, t in [(self.btn_all, "全部"), (self.btn_unread, "未读"),
                             (self.btn_read, "已读"), (self.btn_mat_all, "全部"),
                             (self.btn_mat_raw, "原料"), (self.btn_mat_pkg, "包材"),
                             (self.btn_mat_semi, "半成品"),
                             (self.btn_remark_all, "全部"), (self.btn_remark_has, "有"),
                             (self.btn_remark_none, "无")]:
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
            self.btn_mat_semi.setText(
                f"半成品 ({int((cur_read & self._mat_mask(df, 'semi')).sum())})")
            # 隔离区组：固定当前已读状态，看 是/否 各多少条
            cur_quar_yes = (df["隔离区"].astype(str).str.strip() == "是") if "隔离区" in df.columns else pd.Series(False, index=df.index)
            cur_quar_no = ~cur_quar_yes
            self.btn_quar_all.setText(f"全部 ({int(cur_read.sum())})")
            self.btn_quar_yes.setText(
                f"是 ({int((cur_read & cur_quar_yes).sum())})")
            self.btn_quar_no.setText(
                f"否 ({int((cur_read & cur_quar_no).sum())})")
            # 替代料组：固定当前已读状态，看 是/否 各多少条
            cur_alt_yes = (df["替代料"].astype(str).str.strip() == "是") if "替代料" in df.columns else pd.Series(False, index=df.index)
            cur_alt_no = (df["替代料"].astype(str).str.strip() == "否") if "替代料" in df.columns else pd.Series(False, index=df.index)
            self.btn_alt_all.setText(f"全部 ({int(cur_read.sum())})")
            self.btn_alt_yes.setText(
                f"是 ({int((cur_read & cur_alt_yes).sum())})")
            self.btn_alt_no.setText(
                f"否 ({int((cur_read & cur_alt_no).sum())})")
            # 是否备注组：固定当前已读状态，看 有/无 各多少条
            rc = self._remark_col_name
            if rc and rc in df.columns:
                cur_remark_has = df[rc].apply(lambda x: "" if pd.isna(x) else str(x).strip()) != ""
            else:
                cur_remark_has = pd.Series(False, index=df.index)
            cur_remark_none = ~cur_remark_has
            self.btn_remark_all.setText(f"全部 ({int(cur_read.sum())})")
            self.btn_remark_has.setText(
                f"有 ({int((cur_read & cur_remark_has).sum())})")
            self.btn_remark_none.setText(
                f"无 ({int((cur_read & cur_remark_none).sum())})")
            # 车间下拉框：不更新，但显示当前选中车间的记录数（用于验证）
            if self._workshop_filter != "all" and self._workshop_col and self._workshop_col in df.columns:
                workshop_count = (df[self._workshop_col].astype(str).str.strip() == self._workshop_filter).sum()
                self.combo_workshop.setToolTip(f"当前车间: {self._workshop_filter}，共 {int(workshop_count)} 条")
        except Exception:
            pass

    def set_data(self, df):
        """设置表格数据 - 确保 _read / data_id / 状态 列存在，初始按内容自适应列宽"""
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
        # 派生「状态」列（已读/未读），供看板显示
        if "_read" in df.columns:
            df["状态"] = df["_read"].map({0: "未读", 1: "已读"})
            df = df[["状态"] + [c for c in df.columns if c != "状态"]]

        # ===== 跨看板提示：隔离区 / 替代料（偏差率预警看板需求）=====
        # 隔离区：优先用主表已水合的 _quarantined 列（data_service 已从隔离库比对好，最可靠），
        # 避免本看板自构 data_id 因「订单日期」类型/格式与隔离库 uid 对不齐而漏判（表现为筛选"是"永远0条）。
        # 兜底：主表未传 _quarantined 时，再用本看板 data_id 比对隔离库。
        try:
            from core.quarantine_manager import get_quarantined_ids
            _qset = get_quarantined_ids()
        except Exception:
            _qset = set()
        if "_quarantined" in df.columns:
            df["隔离区"] = df["_quarantined"].astype(int).map({1: "是", 0: ""})
            df = df.drop(columns=["_quarantined"])
        elif "data_id" in df.columns:
            df["隔离区"] = df["data_id"].astype(str).isin(_qset).map({True: "是", False: ""})
        else:
            df["隔离区"] = ""
        # 替代料：直接复用主表现成的「是否替代料」列（值 是/否），改名展示即可，不做重复推断
        if "是否替代料" in df.columns:
            df = df.rename(columns={"是否替代料": "替代料"})
        else:
            df["替代料"] = ""
        # 把两列插到「状态」之后，确保一眼可见
        _cols = list(df.columns)
        for _extra in ("替代料", "隔离区"):
            if _extra in _cols:
                _cols.remove(_extra)
                _cols.insert(1, _extra)
        df = df[_cols]

        self.original_df = df.copy()

        # 备注列移到 data_id 前面（如果存在）
        if "备注" in df.columns and "data_id" in df.columns:
            cols = list(df.columns)
            cols.remove("备注")
            idx = cols.index("data_id")
            cols.insert(idx, "备注")
            df = df[cols]

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
                  self.btn_mat_raw, self.btn_mat_pkg, self.btn_mat_semi):
            w.setVisible(has_mat)
        # 料别默认「全部」（直接置状态，避免与下面的 _set_filter 重复过滤一次）
        self.mat_filter = "all"
        self.btn_mat_all.setChecked(True)
        self.btn_mat_raw.setChecked(False)
        self.btn_mat_pkg.setChecked(False)
        self.btn_mat_semi.setChecked(False)

        # 探测车间列，填充下拉框
        self._workshop_col = None
        if "车间" in df.columns:
            self._workshop_col = "车间"
            unique_workshops = df["车间"].dropna().astype(str).str.strip().unique()
            unique_workshops = [w for w in unique_workshops if w]
            self.combo_workshop.addItems(sorted(unique_workshops))
        has_workshop = self._workshop_col is not None
        self.workshop_sep.setVisible(has_workshop)
        self.lbl_workshop.setVisible(has_workshop)
        self.combo_workshop.setVisible(has_workshop)
        # 车间默认「全部」
        self._workshop_filter = "all"
        self.combo_workshop.setCurrentText("全部")

        # 探测工厂列，填充下拉框（始终可见）
        self._factory_col = None
        if "工厂" in df.columns:
            self._factory_col = "工厂"
            unique_factories = df["工厂"].dropna().astype(str).str.strip().unique()
            unique_factories = [f for f in unique_factories if f]
            self.combo_factory.addItems(sorted(unique_factories))
        # 工厂默认「全部」
        self._factory_filter = "all"
        self.combo_factory.setCurrentText("全部")

        # 探测是否备注列（精确「备注」优先，否则首个含「备注」的列），控制「是否备注」筛选组显隐
        self._remark_col_name = "备注" if "备注" in df.columns else None
        if self._remark_col_name is None:
            self._remark_col_name = next((c for c in df.columns if "备注" in str(c)), None)
        has_remark = self._remark_col_name is not None
        self.remark_sep.setVisible(has_remark)
        self.lbl_remark.setVisible(has_remark)
        self.btn_remark_all.setVisible(has_remark)
        self.btn_remark_has.setVisible(has_remark)
        self.btn_remark_none.setVisible(has_remark)
        # 是否备注默认「全部」
        self._remark_filter = "all"
        self.btn_remark_all.setChecked(True)
        self.btn_remark_has.setChecked(False)
        self.btn_remark_none.setChecked(False)

        # 探测半成品重分类列，构建复选框组（全部 + 各值 + 虚拟两项）
        self._semi_class_col = "半成品重分类" if "半成品重分类" in df.columns else None
        has_semi_class = self._semi_class_col is not None
        self.semi_class_sep.setVisible(has_semi_class)
        self.lbl_semi_class.setVisible(has_semi_class)
        self.grp_semi_class.setVisible(has_semi_class)
        self._semi_class_filter = set()
        if has_semi_class:
            unique_vals = df[self._semi_class_col].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self._build_semi_checkboxes(unique_vals)

        # 探测组件物料类型描述列，填充下拉框
        self._mtd_col = "组件物料类型描述" if "组件物料类型描述" in df.columns else None
        has_mtd = self._mtd_col is not None
        self.mtd_sep.setVisible(has_mtd)
        self.lbl_mtd.setVisible(has_mtd)
        self.combo_mtd.setVisible(has_mtd)
        self._mtd_filter = "all"
        self.combo_mtd.setCurrentText("全部")
        if has_mtd:
            unique_vals = df[self._mtd_col].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self.combo_mtd.addItems(unique_vals)

        # 默认打开时显示未读
        self._set_filter("unread")

    def _filter_desc(self):
        """当前筛选条件的中文描述，用于默认文件名与提示语"""
        state = {"all": "全部", "unread": "未读", "read": "已读"}.get(self.filter_mode, "全部")
        parts = [state]
        if self._mat_col:
            mat = {"all": "", "raw": "原料", "pkg": "包材", "semi": "半成品"}.get(self.mat_filter, "")
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

        # 移入/取消隔离区：判断选中第一条是否已隔离（看板「隔离区」列=="是"）
        cur_df = self.source_model.getDataFrame() if hasattr(self, "source_model") else None
        first_is_q = False
        if cur_df is not None and selected_rows and "隔离区" in cur_df.columns:
            try:
                first_is_q = str(cur_df.iloc[selected_rows[0]].get("隔离区", "")).strip() == "是"
            except Exception:
                first_is_q = False
        if first_is_q:
            q_action = menu.addAction("↩ 取消隔离（选中行）")
            q_action.triggered.connect(lambda: self._set_quarantine(selected_rows, False))
        else:
            q_action = menu.addAction("⚠️ 移入隔离区（选中行）")
            q_action.triggered.connect(lambda: self._set_quarantine(selected_rows, True))
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

    def _set_quarantine(self, rows, flag: bool):
        """右键菜单：将选中行移入/移出隔离区，与主表方法一致。

        - 移入：弹 QInputDialog 填疑难原因（可选）→ add_quarantine_batch([(uid, reason, basis)])
        - 移出：remove_quarantine(uid) 逐条
        - 同步主表内存 _quarantined 列 + 本看板 original_df 的「隔离区」列，并刷新
        """
        df = self.source_model.getDataFrame() if hasattr(self, "source_model") else None
        if df is None:
            return
        ids = set()
        for r in rows:
            if r >= len(df):
                continue
            data_id = df.iloc[r].get("data_id")
            if not data_id:
                rs = df.iloc[r]
                if "工厂" in df.columns:
                    data_id = f"{rs.get('工厂','')}|{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
                else:
                    data_id = f"{rs.get('订单日期','')}|{rs.get('流程订单','')}|{rs.get('物料编码','')}"
            if data_id:
                ids.add(str(data_id))
        if not ids:
            return
        if flag:
            reason = _ask_quarantine_reason(self, "移入隔离区")
            if reason is None:
                return
            basis = "手动:" + reason
            add_quarantine_batch([(uid, reason, basis) for uid in ids])
        else:
            for uid in ids:
                remove_quarantine(uid)

        # 同步主表内存 _quarantined 列，并就地更新主表 source_model（与主表右键加隔离一致），
        # 使主表显示 / 隔离区对话框 / 统计卡实时反映，无需重新分析；
        # 用 mark_quarantine 就地改行（发单行 dataChanged），不整表 reset，故主表滚动/排序/选中/筛选保留。
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

        # 更新本看板 original_df 的「隔离区」列（是 / 空），保证筛选与显示即时正确
        if hasattr(self, "original_df") and "data_id" in self.original_df.columns and "隔离区" in self.original_df.columns:
            self.original_df.loc[self.original_df["data_id"].isin(ids), "隔离区"] = "是" if flag else ""

        self._apply_filter()
        self._update_button_counts()
        toast(f"{'⚠️ 已移入隔离区' if flag else '↩ 已取消隔离'} {len(ids)} 条", parent=self)

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
            self._row2_widget.setVisible(False)
            self._row3_widget.setVisible(False)
            self._row4_widget.setVisible(False)
        else:
            self.showFullScreen()
            self.btn_fullscreen.setText("⛶ 还原")
            self._row2_widget.setVisible(True)
            self._row3_widget.setVisible(True)
            self._row4_widget.setVisible(True)
            # 全屏后重新调整列宽
            QTimer.singleShot(100, lambda: self.table_view.resizeColumnsToContents())

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


def _ask_quarantine_reason(parent, title: str) -> str | None:
    """弹出自定义「移入隔离区」对话框（显式确定/取消按钮，替代 QInputDialog.getText）。
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
