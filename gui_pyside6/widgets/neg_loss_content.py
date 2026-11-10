"""NegLossContent - 负损看板内容组件（剥离自对话框）"""

import re
import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QComboBox, QFrame, QPushButton, QHeaderView, QAbstractItemView, QMenu, QFileDialog, QScrollArea, QGroupBox, QDialogButtonBox, QTableView, QInputDialog, QDialog, QShortcut
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence
from gui_pyside6.models.data_frame_model import DataFrameModel, classify_row_color_keys
from gui_pyside6.dialogs.col_filter_ui import make_col_filter_button, make_col_filter_hint_label, set_col_filter_button_on
from core.quarantine_manager import add_quarantine_batch, remove_quarantine, get_quarantined_ids
from core.read_status import save_read_status_batch
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for, build_data_id
from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.locate import locate_row, drill_to_workshop
from gui_pyside6.utils.table_sort import enable_click_sort
from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader
from gui_pyside6.utils.column_filter import ColumnFilterController
from gui_pyside6.utils.semi_class import merge_semi_class_values, ensure_semi_class_column
from gui_pyside6.widgets.filter_panel import _color_icon
from gui_pyside6.utils.icons import add_icon_action
from gui_pyside6.utils.table_autofit import get_adaptive


class NegLossContent(QWidget):
    """负损看板内容组件：标题 + 筛选 + 表格 + 操作按钮（不含对话框外壳）"""

    # 信号：当标题变化时触发
    title_changed = Signal(str)
    status_changed = Signal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setObjectName("NegLossContent")
        self.main_window = main_window
        self.shell = None  # 绑定到 shell 以更新状态条
        self._keywords = "彩罐 , 托盘 , 手包袋"
        self._include_zero = False
        self._semi_class_filter = set()
        self._semi_class_col = None
        self._read_filter = "未读"
        self._mtd_filter = "all"
        self._mtd_col = None
        self._workshop_filter = "all"
        self._workshop_col = None
        self._factory_filter = "all"
        self._factory_col = None
        self._quar_filter = "no"
        self._has_note_filter = "all"
        self._unit_filter = set()
        self.color_filters = set()
        self.original_df = None
        self.source_model = None
        self._kw_timer = None
        self._initializing = True
        # 新增属性初始化，避免 _apply_default_filter 访问未定义属性
        self._read_col = None
        self._unit_col = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 标题行
        title_row = QHBoxLayout()
        self._title_label = QLabel("负损(含未投料)看板")
        self._title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_row.addWidget(self._title_label)
        title_row.addStretch()
        layout.addLayout(title_row)

        # 顶部筛选栏（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(186)
        scroll.setMaximumHeight(194)
        top_widget = QWidget(scroll)
        _top_col = QVBoxLayout(top_widget)
        _top_col.setContentsMargins(4, 2, 4, 2)
        _top_col.setSpacing(4)

        # 第一行筛选
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(0)
        top.addWidget(QLabel("关键字搜索(逗号分隔):"))
        self.edit_keywords = QLineEdit(self._keywords)
        self.edit_keywords.setToolTip("全列关键字搜索：匹配任意文本列(名称/编码/车间/备注/原因等)，逗号或顿号分隔多值OR")
        self.edit_keywords.setMinimumWidth(160)
        self.edit_keywords.setMaximumWidth(240)
        self.edit_keywords.textChanged.connect(self._on_keywords_changed)
        self.edit_keywords.returnPressed.connect(self._apply_filter)
        top.addWidget(self.edit_keywords)

        self.chk_include_zero = QCheckBox("含未投料")
        self.chk_include_zero.setToolTip("包含未投料：实际=0 的行也视为负损（不影响未投料判定，仅影响负损口径）")
        self.chk_include_zero.setChecked(False)
        self.chk_include_zero.stateChanged.connect(self._on_include_zero_changed)
        top.addWidget(self.chk_include_zero)

        top.addSpacing(14)
        self.unit_sep = QFrame()
        self.unit_sep.setFrameShape(QFrame.VLine)
        self.unit_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.unit_sep)
        top.addSpacing(14)
        self.lbl_unit = QLabel("单位:")
        top.addWidget(self.lbl_unit)
        self.grp_unit = QComboBox()
        self.grp_unit.setMinimumWidth(130)
        self.grp_unit.setMaximumWidth(180)
        self.grp_unit.setEditable(False)
        self.grp_unit.addItem("全部")
        self.grp_unit.currentTextChanged.connect(self._on_unit_changed)
        top.addWidget(self.grp_unit)

        top.addSpacing(14)
        self.mtd_sep = QFrame()
        self.mtd_sep.setFrameShape(QFrame.VLine)
        self.mtd_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.mtd_sep)
        top.addSpacing(14)
        self.lbl_mtd = QLabel("物料类型:")
        top.addWidget(self.lbl_mtd)
        self.combo_mtd = QComboBox()
        self.combo_mtd.setMinimumWidth(130)
        self.combo_mtd.setMaximumWidth(180)
        self.combo_mtd.setEditable(False)
        self.combo_mtd.addItem("全部")
        self.combo_mtd.currentTextChanged.connect(self._on_mtd_changed)
        top.addWidget(self.combo_mtd)

        top.addSpacing(14)
        self.workshop_sep = QFrame()
        self.workshop_sep.setFrameShape(QFrame.VLine)
        self.workshop_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.workshop_sep)
        top.addSpacing(14)
        self.lbl_workshop = QLabel("车间:")
        top.addWidget(self.lbl_workshop)
        self.combo_workshop = QComboBox()
        self.combo_workshop.setMinimumWidth(130)
        self.combo_workshop.setMaximumWidth(180)
        self.combo_workshop.setEditable(False)
        self.combo_workshop.addItem("全部")
        self.combo_workshop.currentTextChanged.connect(self._on_workshop_changed)
        top.addWidget(self.combo_workshop)

        top.addSpacing(14)
        self.factory_sep = QFrame()
        self.factory_sep.setFrameShape(QFrame.VLine)
        self.factory_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.factory_sep)
        top.addSpacing(14)
        self.lbl_factory = QLabel("工厂:")
        top.addWidget(self.lbl_factory)
        self.combo_factory = QComboBox()
        self.combo_factory.setMinimumWidth(150)
        self.combo_factory.setMaximumWidth(200)
        self.combo_factory.setEditable(False)
        self.combo_factory.addItem("全部")
        self.combo_factory.currentTextChanged.connect(self._on_factory_changed)
        top.addWidget(self.combo_factory)

        self._mom_label = QLabel()
        top.addWidget(self._mom_label)

        top.addStretch()
        _top_col.addLayout(top)

        # 第二行
        top2 = QHBoxLayout()
        top2.setContentsMargins(0, 0, 0, 0)
        top2.setSpacing(0)
        top2.addSpacing(14)
        self.semi_sep = QFrame()
        self.semi_sep.setFrameShape(QFrame.VLine)
        self.semi_sep.setFrameShadow(QFrame.Sunken)
        top2.addWidget(self.semi_sep)
        top2.addSpacing(14)
        self.lbl_semi_class = QLabel("半成品分类:")
        top2.addWidget(self.lbl_semi_class)
        self.grp_semi_class = QComboBox()
        self.grp_semi_class.setMinimumWidth(170)
        self.grp_semi_class.setMaximumWidth(220)
        self.grp_semi_class.setEditable(False)
        self.grp_semi_class.addItem("全部")
        self.grp_semi_class.currentTextChanged.connect(self._on_semi_class_changed)
        top2.addWidget(self.grp_semi_class)

        top2.addSpacing(14)
        self.quar_sep = QFrame()
        self.quar_sep.setFrameShape(QFrame.VLine)
        self.quar_sep.setFrameShadow(QFrame.Sunken)
        top2.addWidget(self.quar_sep)
        top2.addSpacing(14)
        self.lbl_quar = QLabel("隔离区:")
        top2.addWidget(self.lbl_quar)
        self.btn_quar_all = QPushButton("全部")
        self.btn_quar_all.setCheckable(True)
        self.btn_quar_all.setMinimumWidth(80)
        self.btn_quar_all.clicked.connect(lambda: self._set_quar_filter("all"))
        top2.addWidget(self.btn_quar_all)
        self.btn_quar_yes = QPushButton("是")
        self.btn_quar_yes.setCheckable(True)
        self.btn_quar_yes.setMinimumWidth(80)
        self.btn_quar_yes.clicked.connect(lambda: self._set_quar_filter("yes"))
        top2.addWidget(self.btn_quar_yes)
        self.btn_quar_no = QPushButton("否")
        self.btn_quar_no.setCheckable(True)
        self.btn_quar_no.setMinimumWidth(80)
        self.btn_quar_no.clicked.connect(lambda: self._set_quar_filter("no"))
        top2.addWidget(self.btn_quar_no)

        top2.addSpacing(14)
        self.note_sep = QFrame()
        self.note_sep.setFrameShape(QFrame.VLine)
        self.note_sep.setFrameShadow(QFrame.Sunken)
        top2.addWidget(self.note_sep)
        top2.addSpacing(14)
        self.lbl_note = QLabel("备注:")
        top2.addWidget(self.lbl_note)
        self.btn_note_all = QPushButton("全部")
        self.btn_note_all.setCheckable(True)
        self.btn_note_all.setMinimumWidth(80)
        self.btn_note_all.clicked.connect(lambda: self._set_note_filter("all"))
        top2.addWidget(self.btn_note_all)
        self.btn_note_yes = QPushButton("有")
        self.btn_note_yes.setCheckable(True)
        self.btn_note_yes.setMinimumWidth(80)
        self.btn_note_yes.clicked.connect(lambda: self._set_note_filter("yes"))
        top2.addWidget(self.btn_note_yes)
        self.btn_note_no = QPushButton("无")
        self.btn_note_no.setCheckable(True)
        self.btn_note_no.setMinimumWidth(80)
        self.btn_note_no.clicked.connect(lambda: self._set_note_filter("no"))
        top2.addWidget(self.btn_note_no)

        top2.addStretch()
        _top_col.addLayout(top2)

        # 第三行
        top3 = QHBoxLayout()
        top3.setContentsMargins(0, 0, 0, 0)
        top3.setSpacing(0)
        _top_col.addLayout(top3)
        top3.addStretch()
        _top_col.addLayout(top3)

        # 第四行（颜色筛选）
        top_color = QHBoxLayout()
        top_color.setContentsMargins(0, 0, 0, 0)
        top_color.setSpacing(0)
        _top_col.addLayout(top_color)
        top_color.addSpacing(14)
        self.color_sep = QFrame()
        self.color_sep.setFrameShape(QFrame.VLine)
        self.color_sep.setFrameShadow(QFrame.Sunken)
        top_color.addWidget(self.color_sep)
        top_color.addSpacing(14)
        self.lbl_color = QLabel("颜色:")
        top_color.addWidget(self.lbl_color)
        self.color_group = QGroupBox()
        self.color_group.setFlat(True)
        self.color_group.setFixedHeight(36)
        self._color_layout = QHBoxLayout(self.color_group)
        self._color_layout.setContentsMargins(6, 4, 6, 4)
        self._color_layout.setSpacing(8)
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
            self._color_layout.addWidget(cb)
        top_color.addWidget(self.color_group)
        top_color.addStretch()

        top3.addSpacing(14)
        self.read_sep = QFrame()
        self.read_sep.setFrameShape(QFrame.VLine)
        self.read_sep.setFrameShadow(QFrame.Sunken)
        top3.addWidget(self.read_sep)
        top3.addSpacing(14)
        self.lbl_read = QLabel("已读:")
        top3.addWidget(self.lbl_read)
        self.combo_read = QComboBox()
        self.combo_read.setMinimumWidth(100)
        self.combo_read.setMaximumWidth(140)
        self.combo_read.setEditable(False)
        self.combo_read.addItems(["全部", "已读", "未读"])
        self.combo_read.currentTextChanged.connect(self._on_read_changed)
        top3.addWidget(self.combo_read)

        self.lbl_count = QLabel("共 0 条")
        self.lbl_count.setProperty("class", "mutedText")
        top3.addWidget(self.lbl_count)
        self.btn_refresh = QPushButton("重新筛选")
        self.btn_refresh.clicked.connect(self._apply_filter)
        top3.addWidget(self.btn_refresh)
        self.btn_col_filter = make_col_filter_button(self, self._on_toggle_col_filter)
        top3.addWidget(self.btn_col_filter)
        self._col_filter_hint_label = make_col_filter_hint_label()
        top3.addWidget(self._col_filter_hint_label)

        scroll.setWidget(top_widget)
        layout.addWidget(scroll)

        # 表格
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.header = SortBadgeHeader(Qt.Horizontal, self.table_view)
        self.table_view.setHorizontalHeader(self.header)
        self._sort_ctrl = enable_click_sort(
            self.table_view, lambda: getattr(self, "source_model", None), skip_cols=())
        self.col_filter_ctrl = ColumnFilterController(
            self.table_view, self.header, self._sort_ctrl,
            lambda: getattr(self, "source_model", None),
            self._apply_filter, skip_cols=())
        self.header.set_sort_columns_getter(lambda: [])
        self.header.set_filtered_columns_getter(lambda: self.col_filter_ctrl.filtered_col_set)
        try:
            self.header.sectionClicked.disconnect(self._sort_ctrl._on_click)
        except Exception:
            pass
        self.header.sectionClicked.connect(self.col_filter_ctrl.on_header_clicked)
        self.col_filter_ctrl.filtered_cols_changed.connect(self._update_col_filter_hint)
        self.col_filter_ctrl.attach_clear_menu(self._col_filter_hint_label)
        self._update_col_filter_hint()
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        self.header.setMinimumSectionSize(50)
        self.header.setMaximumSectionSize(420)
        self.header.setStretchLastSection(False)
        self.table_view.installEventFilter(self)
        # 优化滚动：启用双缓冲，减少闪烁
        self.table_view.setAttribute(Qt.WA_QuitOnClose, False)
        self.table_viewViewport = self.table_view.viewport()
        self.table_viewViewport.setAttribute(Qt.WA_OpaquePaintEvent, False)
        layout.addWidget(self.table_view)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.btn_add_quar = QPushButton("⚠️ 加入隔离区(选中行)")
        self.btn_add_quar.clicked.connect(self._add_selected_to_quarantine)
        btn_layout.addWidget(self.btn_add_quar)
        self.btn_export = QPushButton("📎 导出 Excel (Alt+V)")
        self.btn_export.clicked.connect(self.export_excel)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # 键盘快捷键
        self._sc_export = QShortcut(QKeySequence("Alt+V"), self)
        self._sc_export.activated.connect(self.export_excel)
        self._sc_refresh = QShortcut(QKeySequence("F5"), self)
        self._sc_refresh.activated.connect(self._apply_filter)
        self.btn_refresh.setText("重新筛选 (F5)")

    def _apply_default_filter(self):
        self._read_filter = "未读"
        if self._read_col and hasattr(self, "combo_read"):
            self.combo_read.setCurrentText("未读")
        self._apply_filter()
        sm = getattr(self, "source_model", None)
        if sm is None or sm.rowCount() > 0:
            return
        if self.original_df is not None and len(self.original_df) > 0:
            self._read_filter = "全部"
            if hasattr(self, "combo_read"):
                self.combo_read.setCurrentText("全部")
            else:
                self._apply_filter()

    def set_data(self, df):
        df = df.copy()
        if "半成品重分类" not in df.columns:
            try:
                df, _added = ensure_semi_class_column(df)
            except Exception:
                df["半成品重分类"] = ""

        self._initializing = True
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

        try:
            _qset = get_quarantined_ids()
        except Exception:
            _qset = set()
        if "data_id" in df.columns:
            _did = df["data_id"].astype(str)
            _m = _did.isin(_qset)
            if _qset:
                _qset_tail3 = {u if len(u.split("|")) < 4 else "|".join(u.split("|")[-3:])
                               for u in _qset}
                _tail3 = _did.str.split("|").str[-3:].str.join("|")
                _m = _m | _tail3.isin(_qset_tail3)
            df["隔离区"] = _m.map({True: "是", False: ""})
        else:
            df["隔离区"] = ""

        if "备注" in df.columns and "data_id" in df.columns:
            cols = list(df.columns)
            cols.remove("备注")
            cols.insert(cols.index("data_id"), "备注")
            df = df[cols]

        if "隔离区" in df.columns and "订单日期" in df.columns:
            cols = list(df.columns)
            cols.remove("隔离区")
            idx = cols.index("订单日期")
            cols.insert(idx, "隔离区")
            df = df[cols]

        if "半成品重分类" in df.columns:
            _cols = list(df.columns)
            _cols.remove("半成品重分类")
            _anchor = next((c for c in ("组件物料类型描述", "组件物料类型", "物料类型") if c in _cols), None)
            _idx = _cols.index(_anchor) + 1 if _anchor else len(_cols)
            _cols.insert(_idx, "半成品重分类")
            df = df[_cols]

        self.original_df = df.copy()

        if "data_id" in self.original_df.columns:
            try:
                from core.read_status import load_read_status
                data_ids = [str(x) for x in self.original_df["data_id"].tolist()]
                status_map = load_read_status(data_ids)
                if status_map:
                    source_map = {did: vals[5] if len(vals) > 5 and vals[5] else ''
                                  for did, vals in status_map.items()}
                    self.original_df["_read_source"] = self.original_df["data_id"].astype(str).map(source_map).fillna('').astype(str)
                    if "_read" in self.original_df.columns:
                        self.original_df.loc[self.original_df["_read"] != 1, "_read_source"] = ''
                else:
                    self.original_df["_read_source"] = ''
            except Exception:
                self.original_df["_read_source"] = ''

        def _fmt_source(v):
            if pd.isna(v) or v == '':
                return ''
            s = str(v).strip().lower()
            if s == 'auto':
                return '自动'
            elif s == 'manual':
                return '手动'
            return str(v)
        if "_read_source" in self.original_df.columns:
            self.original_df["已读来源"] = self.original_df["_read_source"].apply(_fmt_source)
        else:
            self.original_df["已读来源"] = ''

        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)
        try:
            _ctrl = get_adaptive(self.table_view)
            if _ctrl is not None:
                _ctrl.request_refit(0)
        except Exception:
            import traceback
            traceback.print_exc()
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        if "data_id" in df.columns:
            self.table_view.setColumnHidden(df.columns.get_loc("data_id"), True)

        self._semi_class_col = "半成品重分类" if "半成品重分类" in df.columns else None
        unique_vals = []
        if self._semi_class_col:
            unique_vals = sorted(
                v for v in df["半成品重分类"].dropna().astype(str).str.strip().unique() if v
            )
        self._build_semi_checkboxes(unique_vals)
        self.semi_sep.setVisible(True)
        self.lbl_semi_class.setVisible(True)
        self.grp_semi_class.setVisible(True)

        self._read_col = "_read" if "_read" in df.columns else None
        if self._read_col:
            self.combo_read.setCurrentText("未读")
        else:
            self.combo_read.setVisible(False)
            self.read_sep.setVisible(False)
            self.lbl_read.setVisible(False)

        self._mtd_col = "组件物料类型描述" if "组件物料类型描述" in df.columns else None
        if self._mtd_col:
            unique_vals = sorted(
                v for v in df[self._mtd_col].dropna().astype(str).str.strip().unique() if v
            )
            unique_vals = [v for v in unique_vals if v not in self._CASCADE_EXCLUDE_MTD]
            self._replace_combo_items(self.combo_mtd, unique_vals, "all",
                                      "_mtd_filter", "_on_mtd_changed")
        else:
            self.mtd_sep.setVisible(False)
            self.lbl_mtd.setVisible(False)
            self.combo_mtd.setVisible(False)

        self._workshop_col = "车间" if "车间" in df.columns else None
        if self._workshop_col:
            unique_vals = sorted(
                v for v in df["车间"].dropna().astype(str).str.strip().unique() if v
            )
            self._replace_combo_items(self.combo_workshop, unique_vals, "all",
                                      "_workshop_filter", "_on_workshop_changed")
        else:
            self.workshop_sep.setVisible(False)
            self.lbl_workshop.setVisible(False)
            self.combo_workshop.setVisible(False)
        self._workshop_filter = "all"
        self.combo_workshop.setCurrentText("全部")

        self._factory_col = ("工厂名称" if "工厂名称" in df.columns
                             else ("工厂" if "工厂" in df.columns else None))
        if self._factory_col:
            self.combo_factory.blockSignals(True)
            self.combo_factory.clear()
            self.combo_factory.addItem("全部")
            unique_vals = df[self._factory_col].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self.combo_factory.addItems(unique_vals)
            self.combo_factory.blockSignals(False)
        else:
            self.factory_sep.setVisible(False)
            self.lbl_factory.setVisible(False)
            self.combo_factory.setVisible(False)
        self._factory_filter = "all"
        self.combo_factory.setCurrentText("全部")

        self._unit_col = "单位" if "单位" in df.columns else None
        if self._unit_col:
            unique_vals = df["单位"].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self._build_unit_checkboxes(unique_vals)
        else:
            self.unit_sep.setVisible(False)
            self.lbl_unit.setVisible(False)
            self.grp_unit.setVisible(False)
        self._unit_filter = set()

        self._quar_filter = "no"
        self.btn_quar_no.setChecked(True)
        self._has_note_filter = "all"
        self.btn_note_all.setChecked(True)
        self._initializing = False
        # 应用默认筛选过滤
        self._apply_default_filter()

    def _refresh_cascade_combos(self, changed):
        if getattr(self, '_initializing', False):
            return
        df = getattr(self, 'original_df', None)
        if df is None or df.empty or not hasattr(self, 'source_model'):
            return

        sub_mtd = df[self._other_conditions_mask(df, exclude='mtd')]
        mtd_vals = sorted(
            v for v in sub_mtd[self._mtd_col].dropna().astype(str).str.strip().unique() if v
        ) if (self._mtd_col and self._mtd_col in sub_mtd.columns) else []
        mtd_vals = [v for v in mtd_vals if v not in self._CASCADE_EXCLUDE_MTD]
        self._replace_combo_items(self.combo_mtd, mtd_vals, self._mtd_filter,
                                  '_mtd_filter', '_on_mtd_changed')

        sub_ws = df[self._other_conditions_mask(df, exclude='workshop')]
        ws_vals = sorted(
            v for v in sub_ws[self._workshop_col].dropna().astype(str).str.strip().unique() if v
        ) if (self._workshop_col and self._workshop_col in sub_ws.columns) else []
        self._replace_combo_items(self.combo_workshop, ws_vals, self._workshop_filter,
                                  '_workshop_filter', '_on_workshop_changed')

        sub_unit = df[self._other_conditions_mask(df, exclude='unit')]
        unit_vals = sorted(
            v for v in sub_unit[self._unit_col].dropna().astype(str).str.strip().unique() if v
        ) if (self._unit_col and self._unit_col in sub_unit.columns) else []
        keep_units = {u for u in self._unit_filter if u in unit_vals}
        wanted_units = ['全部'] + unit_vals
        have_units = [self.grp_unit.itemText(i) for i in range(self.grp_unit.count())]
        if wanted_units != have_units:
            self.grp_unit.blockSignals(True)
            try:
                self.grp_unit.clear()
                self.grp_unit.addItems(wanted_units)
                self.grp_unit.setCurrentText(
                    '全部' if not keep_units else sorted(keep_units)[0])
            finally:
                self.grp_unit.blockSignals(False)
        self._unit_filter = keep_units

    def _replace_combo_items(self, combo, values, cur_value, attr_name, slot_name):
        wanted = ['全部'] + list(values)
        have = [combo.itemText(i) for i in range(combo.count())]
        if wanted == have:
            return False
        keep = cur_value if cur_value in values else 'all'
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems(wanted)
            combo.setCurrentText('全部' if keep == 'all' else keep)
        finally:
            combo.blockSignals(False)
        setattr(self, attr_name, keep)
        return True

    def _apply_filter(self):
        if getattr(self, "_initializing", False):
            return
        if self.original_df is None or not hasattr(self, "source_model"):
            return
        df = self.original_df
        if df.empty:
            self.source_model.setDataFrame(df)
            self._sort_ctrl.reapply()
            self.lbl_count.setText("共 0 条")
            # 更新状态条
            if self.shell is not None:
                self.shell.set_status("0 条记录")
            return

        self._refresh_cascade_combos('apply')
        mask = (self._name_mask(df) & self._neg_loss_mask(df)
                & self._semi_class_mask(df)
                & self._mtd_mask(df)
                & self._unit_mask(df)
                & self._workshop_mask(df, self._workshop_filter)
                & self._factory_mask(df, self._factory_filter)
                & self._quar_mask(df, self._quar_filter)
                & self._note_mask(df, self._has_note_filter)
                & self._color_mask(df)
                & self._read_mask(df, self._read_filter))
        filtered = df[mask].copy().reset_index(drop=True)
        if hasattr(self, "col_filter_ctrl"):
            filtered = self.col_filter_ctrl.mask_dataframe(filtered)
        self.source_model.setDataFrame(filtered)
        self._sort_ctrl.reapply()
        tag = "含未投料" if self._include_zero else "不含未投料"
        note_tag = {"all": "全部", "yes": "有备注", "no": "无备注"}[self._has_note_filter]
        count_text = "共 %d 条（名称含「%s」· %s · %s）" % (len(filtered), self._keywords, tag, note_tag)
        self.lbl_count.setText(count_text)
        # 更新状态条
        if self.shell is not None:
            self.shell.set_status(f"已筛选 {len(filtered)} 条记录")

    def _other_conditions_mask(self, df, exclude):
        mask = (self._name_mask(df) & self._neg_loss_mask(df)
                & self._semi_class_mask(df)
                & self._quar_mask(df, self._quar_filter)
                & self._note_mask(df, self._has_note_filter)
                & self._color_mask(df)
                & self._read_mask(df, self._read_filter))
        mask &= self._factory_mask(df, self._factory_filter)
        if exclude != 'mtd':
            mask &= self._mtd_mask(df)
        if exclude != 'workshop':
            mask &= self._workshop_mask(df, self._workshop_filter)
        if exclude != 'unit':
            mask &= self._unit_mask(df)
        return mask

    def _name_cols(self, df):
        _internal = {"data_id", "隔离区", "_read", "_quarantined"}
        cols = [c for c in df.columns if c not in _internal]
        return cols

    def _neg_loss_mask(self, df):
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

    def _semi_class_mask(self, df):
        if not self._semi_class_filter:
            return pd.Series(True, index=df.index)
        semi_col = "半成品重分类"
        blank = None
        if semi_col in df.columns:
            vals = df[semi_col].astype(str).str.strip()
            blank = vals == ""
        else:
            _mtd = (df['组件物料类型描述'].astype(str)
                    if '组件物料类型描述' in df.columns
                    else pd.Series('', index=df.index))
            _semi = ((df['物料分类'] == '半成品') if '物料分类' in df.columns
                     else pd.Series(False, index=df.index)) | _mtd.str.contains('半成品|成品', na=False)
            vals = _semi.map({True: '__SEMI__', False: ''}).reindex(df.index)
            blank = vals == ""
        if "物料编码" in df.columns:
            code = df["物料编码"].astype(str).str.strip()
        else:
            code = pd.Series("", index=df.index)
        mask = pd.Series(False, index=df.index)
        for m in self._semi_class_filter:
            hit = vals == m
            if m == "食品成品半成品":
                hit = hit | (blank & code.str.startswith("400", na=False))
            elif m == "饮料成品半成品":
                hit = hit | (blank & code.str.startswith("410", na=False))
            mask = mask | hit
        return mask

    def _mtd_mask(self, df):
        if self._mtd_filter == "all" or not self._mtd_col:
            return pd.Series(True, index=df.index)
        if self._mtd_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._mtd_col].astype(str).str.strip()
        return vals == self._mtd_filter

    def _unit_mask(self, df):
        if not self._unit_filter or not self._unit_col:
            return pd.Series(True, index=df.index)
        if self._unit_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._unit_col].astype(str).str.strip()
        return vals.isin(self._unit_filter)

    def _build_semi_checkboxes(self, unique_vals):
        self.grp_semi_class.blockSignals(True)
        kept = self.grp_semi_class.currentText()
        self.grp_semi_class.clear()
        self.grp_semi_class.addItem("全部")
        for v in merge_semi_class_values(unique_vals):
            self.grp_semi_class.addItem(v)
        if kept and kept != "全部" and self.grp_semi_class.findText(kept) >= 0:
            self.grp_semi_class.setCurrentText(kept)
        else:
            self.grp_semi_class.setCurrentText("全部")
        self.grp_semi_class.blockSignals(False)

    def _build_unit_checkboxes(self, unique_vals):
        self.grp_unit.blockSignals(True)
        kept = self.grp_unit.currentText()
        self.grp_unit.clear()
        self.grp_unit.addItem("全部")
        for v in unique_vals:
            self.grp_unit.addItem(v)
        if kept and kept != "全部" and self.grp_unit.findText(kept) >= 0:
            self.grp_unit.setCurrentText(kept)
        else:
            self.grp_unit.setCurrentText("全部")
        self.grp_unit.blockSignals(False)

    def _read_mask(self, df, mode):
        if mode == "all" or "_read" not in df.columns:
            return pd.Series(True, index=df.index)
        _r = pd.to_numeric(df["_read"], errors="coerce").fillna(0)
        if mode == "已读":
            return _r == 1
        if mode == "未读":
            return _r != 1
        return pd.Series(True, index=df.index)

    def _workshop_mask(self, df, mode):
        if mode == "all" or not self._workshop_col:
            return pd.Series(True, index=df.index)
        if self._workshop_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._workshop_col].astype(str).str.strip()
        return vals == mode

    def _factory_mask(self, df, mode):
        if mode == "all" or not self._factory_col:
            return pd.Series(True, index=df.index)
        if self._factory_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._factory_col].astype(str).str.strip()
        return vals == mode

    def _quar_mask(self, df, mode):
        if mode == "all" or "隔离区" not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df["隔离区"].astype(str).str.strip()
        if mode == "yes":
            return vals == "是"
        return vals != "是"

    def _note_mask(self, df, mode):
        if mode == "all" or "备注" not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df["备注"].astype(str).str.strip()
        if mode == "yes":
            return vals != ""
        return vals == ""

    def _color_mask(self, df):
        if not self.color_filters:
            return pd.Series(True, index=df.index)
        threshold = 10.0
        am = getattr(self.main_window, 'alert_monitor', None)
        if am is not None:
            try:
                threshold = float(getattr(am, 'threshold', 10))
            except (TypeError, ValueError):
                threshold = 10.0
        mask = df.apply(
            lambda r: bool(classify_row_color_keys(r, df, threshold) & self.color_filters),
            axis=1)
        return mask

    def _name_mask(self, df):
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

    def _set_quar_filter(self, mode):
        self._quar_filter = mode
        self.btn_quar_all.setChecked(mode == "all")
        self.btn_quar_yes.setChecked(mode == "yes")
        self.btn_quar_no.setChecked(mode == "no")
        self._apply_filter()

    def _set_note_filter(self, mode):
        self._has_note_filter = mode
        self.btn_note_all.setChecked(mode == "all")
        self.btn_note_yes.setChecked(mode == "yes")
        self.btn_note_no.setChecked(mode == "no")
        self._apply_filter()

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
        self._semi_class_filter = set() if text == "全部" else {text}
        self._apply_filter()

    def _on_mtd_changed(self, text):
        self._mtd_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _on_unit_changed(self, text):
        self._unit_filter = set() if text == "全部" else {text}
        self._apply_filter()

    def _on_workshop_changed(self, text):
        self._workshop_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _on_factory_changed(self, text):
        self._factory_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _on_color_toggled(self):
        self.color_filters = {k for k, cb in self.color_checks.items() if cb.isChecked()}
        self._apply_filter()

    def _on_read_changed(self, text):
        self._read_filter = text
        self._apply_filter()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeySequence
        if obj is self.table_view and event.type() == QEvent.KeyPress:
            if event.matches(QKeySequence.Copy):
                self._copy_selected_cells()
                return True
        return super().eventFilter(obj, event)

    def _copy_selected_cells(self):
        from gui_pyside6.utils.table_copy import copy_table_cells
        copy_table_cells(self.table_view)

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
        mark_read_action = add_icon_action(menu, "✅ 标记为已读（选中行）")
        mark_read_action.triggered.connect(
            lambda: self._mark_selected_rows_read(selected_rows))
        mark_unread_action = add_icon_action(menu, "⭕ 标记为未读（选中行）")
        mark_unread_action.triggered.connect(
            lambda: self._mark_selected_rows_unread(selected_rows))
        menu.addSeparator()
        add_action = add_icon_action(menu, "⚠️ 加入隔离区(选中行)")
        add_action.triggered.connect(lambda: self._add_selected_to_quarantine())
        df = self.source_model.getDataFrame()
        if df is not None and selected_rows and "隔离区" in df.columns:
            try:
                all_q = all(str(df.iloc[r].get("隔离区", "")).strip() == "是"
                            for r in selected_rows if r < len(df))
            except Exception:
                all_q = False
            if all_q:
                cancel_action = add_icon_action(menu, "↩ 取消隔离(选中行)")
                cancel_action.triggered.connect(lambda: self._cancel_selected_quarantine())
        menu.addSeparator()
        _df_drill = self.source_model.getDataFrame()
        if _df_drill is not None and selected_rows:
            try:
                _rec = _df_drill.iloc[selected_rows[0]]
                _drill = add_icon_action(menu, "🔍 下钻该车间（主表筛选）")
                _drill.triggered.connect(
                    lambda: self.close() if drill_to_workshop(self.main_window, _rec, "负损看板") else None)
            except Exception:
                pass
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _mark_selected_rows_read(self, rows):
        df = self.source_model.getDataFrame()
        if df is None:
            return
        target_ids = []
        for r in rows:
            if r >= len(df):
                continue
            data_id = df.iloc[r].get('data_id')
            if not data_id:
                rs = df.iloc[r]
                data_id = build_data_id(rs, df)
            if data_id and data_id not in target_ids:
                target_ids.append(data_id)
        if not target_ids:
            return
        count, records = self._sync_main_df_batch(target_ids, 1, df)
        if records:
            save_read_status_batch(records)
        self._refresh_main_table_once()
        if hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'].isin(target_ids)
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 1
                self.original_df.loc[orig_mask, '_read_source'] = 'manual'
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '✓ 已读'
                if '已读来源' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '已读来源'] = '手动'
        self._apply_filter()
        toast(f"✅ 已标记 {count} 条为已读", parent=self)

    def _mark_selected_rows_unread(self, rows):
        df = self.source_model.getDataFrame()
        if df is None:
            return
        target_ids = []
        for r in rows:
            if r >= len(df):
                continue
            data_id = df.iloc[r].get('data_id')
            if not data_id:
                rs = df.iloc[r]
                data_id = build_data_id(rs, df)
            if data_id and data_id not in target_ids:
                target_ids.append(data_id)
        if not target_ids:
            return
        count, records = self._sync_main_df_batch(target_ids, 0, df)
        if records:
            save_read_status_batch(records)
        self._refresh_main_table_once()
        if hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'].isin(target_ids)
            if orig_mask.any():
                self.original_df.loc[orig_mask, '_read'] = 0
                if '状态' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '状态'] = '未读'
                if '已读来源' in self.original_df.columns:
                    self.original_df.loc[orig_mask, '已读来源'] = ''
        self._apply_filter()
        toast(f"⭕ 已标记 {count} 条为未读", parent=self)

    def _sync_main_df_batch(self, target_ids, read_value, source_df):
        main_df = self.main_window.view_model.df
        if main_df is None or not target_ids:
            return 0, []

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
                    main_df['订单日期'].astype(str) + '|' +
                    main_df['流程订单'].astype(str) + '|' +
                    main_df['物料编码'].astype(str)
                )

        if '_read' not in main_df.columns:
            main_df['_read'] = 0

        mask = main_df['data_id'].isin(target_ids)
        if not mask.any():
            return 0, []

        current_vals = main_df.loc[mask, '_read']
        need_update = current_vals != read_value
        updated_ids = main_df.loc[mask, 'data_id'].tolist()

        main_df.loc[mask & need_update, '_read'] = read_value

        records = []
        count = int(need_update.sum())
        if count > 0:
            fingerprints = {}
            if 'fingerprint' in main_df.columns:
                for did in updated_ids:
                    row_mask = main_df['data_id'] == did
                    if row_mask.any():
                        idx = main_df[row_mask].index[0]
                        fingerprints[did] = main_df.at[idx, 'fingerprint']
                    else:
                        fingerprints[did] = ''
            else:
                fingerprints = {did: '' for did in updated_ids}

            for did in updated_ids:
                if did in fingerprints:
                    qty = snapshot_qty_for(source_df, did)
                    note = snapshot_note_for(source_df, did)
                    records.append((did, read_value, fingerprints[did], qty, note, None, 'manual'))

        self.main_window.view_model.df = main_df
        return count, records

    def _refresh_main_table_once(self):
        main_df = self.main_window.view_model.df
        if main_df is None:
            return
        if hasattr(self.main_window, 'source_model') and self.main_window.source_model:
            self.main_window.source_model.setDataFrame(main_df)
            if hasattr(self.main_window, '_apply_column_visibility_by_name'):
                self.main_window._apply_column_visibility_by_name()

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
            data_id = df.iloc[r].get("data_id")
            if not data_id:
                rs = df.iloc[r]
                data_id = build_data_id(rs, df)
            if data_id:
                ids.add(str(data_id))
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
        if (hasattr(self, "source_model") and self.source_model is not None
                and hasattr(self, "original_df") and self.original_df is not None
                and "data_id" in self.original_df.columns and "_quarantined" in self.original_df.columns):
            id_set = set(str(i) for i in ids)
            mask = self.original_df["data_id"].astype(str).isin(id_set)
            self.source_model._data.loc[mask, "_quarantined"] = 1 if flag else 0
            positions = {i for i, v in enumerate(mask) if v}
            if flag:
                self.source_model._quarantined_rows |= positions
            else:
                self.source_model._quarantined_rows -= positions
            last_col = max(self.source_model.columnCount() - 1, 0)
            for pos in positions:
                self.source_model.dataChanged.emit(self.source_model.index(pos, 0),
                                                   self.source_model.index(pos, last_col))
        self._apply_filter()

    def on_double_click(self, index):
        if not index.isValid():
            return
        df = self.source_model.getDataFrame()
        if index.row() < len(df):
            locate_row(self.main_window, df.iloc[index.row()], parent=self, link_source="负损看板")
            self.close()

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
            export_df = cur_df.drop(columns=['data_id', '原表行号'], errors='ignore')
            saved = safe_save(self, path, lambda p: export_df.to_excel(p, index=False), what="负损看板")
            if saved:
                toast(f"已导出 {len(export_df)} 条记录到 {saved}", parent=self)

    def _update_col_filter_hint(self):
        col_set = self.col_filter_ctrl.filtered_col_set
        sm = getattr(self, "source_model", None)
        display_cols = getattr(sm, "_display_columns", []) if sm is not None else []
        if not col_set:
            self._col_filter_hint_label.setText("列头筛选：0 列")
            return
        names = []
        for c in sorted(col_set):
            if 0 <= c < len(display_cols):
                names.append(str(display_cols[c]))
            else:
                names.append(f"列{c}")
        shown = names[:4]
        more = len(names) - len(shown)
        text = "列头筛选：%d 列（%s" % (len(names), "、".join(shown))
        if more > 0:
            text += " …+%d" % more
        text += "）"
        self._col_filter_hint_label.setText(text)

    def _on_toggle_col_filter(self):
        on = self.col_filter_ctrl.toggle_mode()
        self.btn_col_filter.setChecked(on)
        set_col_filter_button_on(self.btn_col_filter, on)

    # 级联排除
    _CASCADE_EXCLUDE_MTD = {'食品成品', '饮料成品'}


def _ask_quarantine_reason(parent, title: str) -> str | None:
    dlg = QInputDialog(parent)
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
