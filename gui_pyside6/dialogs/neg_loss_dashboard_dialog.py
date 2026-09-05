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
# 虚拟半成品分类名（与 analyzer.py 归并规则一致，用于筛选框和掩码判断）
_SEMI_VIRT_FOOD = "食品半成品"
_SEMI_VIRT_DRINK = "饮料半成品"



from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QAbstractItemView, QMenu, QFileDialog, QLabel, QLineEdit,
    QCheckBox, QDialogButtonBox, QComboBox, QFrame, QGroupBox, QScrollArea,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer
from gui_pyside6.models.data_frame_model import DataFrameModel, classify_row_color_keys
from core.quarantine_manager import add_quarantine_batch, remove_quarantine, get_quarantined_ids
from core.read_status import save_read_status_batch
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for
from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.table_sort import enable_click_sort
from gui_pyside6.widgets.filter_panel import _color_icon


class NegLossDashboardDialog(QDialog):
    """负损(含未投料)看板：名称关键词 × 负损(含未投料) 的只读+手动隔离视图。"""

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("负损(含未投料)看板 - 彩罐/托盘/手包袋")
        self.resize(1280, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.main_window = main_window
        self._keywords = ""
        self._include_zero = True  # 默认包含未投料（实际=0），与对话框标题"负损(含未投料)"一致
        self._semi_class_filter = set()  # 半成品重分类筛选：空集合=全部 / 集合内为选中分类（虚拟项模糊匹配）
        self._semi_class_col = None   # 半成品重分类列名（set_data 时探测）
        self._read_filter = "all"     # 已读/未读筛选（全部/已读/未读）
        self._mtd_filter = "all"      # 组件物料类型描述筛选（全部/具体类型）
        self._mtd_col = None          # 组件物料类型描述列名（set_data 时探测）
        self._workshop_filter = "all"  # 车间筛选（全部/车间名）
        self._workshop_col = None     # 车间列名（set_data 时探测）
        self._quar_filter = "all"     # 隔离区筛选（全部/是/否）
        self._has_note_filter = "all" # 是否有备注筛选（全部/是/否）
        self.color_filters = set()    # 颜色筛选
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

        # ---- 顶部筛选栏（包在水平滚动区域内，避免控件被挤压重叠）----
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(52)
        scroll.setMaximumHeight(56)
        top_widget = QWidget(scroll)
        top = QHBoxLayout(top_widget)
        top.setContentsMargins(4, 2, 4, 2)
        top.setSpacing(0)
        top.addWidget(QLabel("关键字搜索(逗号分隔):"))
        self.edit_keywords = QLineEdit(self._keywords)
        self.edit_keywords.setToolTip("全列关键字搜索：匹配任意文本列(名称/编码/车间/备注/原因等)，逗号或顿号分隔多值OR")
        self.edit_keywords.setMinimumWidth(160)
        self.edit_keywords.setMaximumWidth(240)
        top.addWidget(self.edit_keywords)
        self.edit_keywords.textChanged.connect(self._on_keywords_changed)

        self.chk_include_zero = QCheckBox("包含未投料(实际=0 也视为负损)")
        self.chk_include_zero.setChecked(True)
        self.chk_include_zero.stateChanged.connect(self._on_include_zero_changed)
        top.addWidget(self.chk_include_zero)

        top.addSpacing(14)
        self.semi_sep = QFrame()
        self.semi_sep.setFrameShape(QFrame.VLine)
        self.semi_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.semi_sep)
        top.addSpacing(14)
        self.lbl_semi_class = QLabel("半成品分类:")
        top.addWidget(self.lbl_semi_class)
        self.grp_semi_class = QComboBox()
        self.grp_semi_class.setMinimumWidth(170)
        self.grp_semi_class.setMaximumWidth(220)
        self.grp_semi_class.setEditable(False)
        self.grp_semi_class.addItem("全部")
        self.grp_semi_class.currentTextChanged.connect(self._on_semi_class_changed)
        top.addWidget(self.grp_semi_class)

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

        # ---- 车间筛选 ----
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

        # ---- 颜色筛选 ----
        top.addSpacing(14)
        self.color_sep = QFrame()
        self.color_sep.setFrameShape(QFrame.VLine)
        self.color_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.color_sep)
        top.addSpacing(14)
        self.lbl_color = QLabel("颜色:")
        top.addWidget(self.lbl_color)
        self.color_group = QGroupBox()
        self.color_group.setFlat(True)
        self.color_group.setMinimumWidth(300)
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
        top.addWidget(self.color_group)

        top.addSpacing(14)
        self.read_sep = QFrame()
        self.read_sep.setFrameShape(QFrame.VLine)
        self.read_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.read_sep)
        top.addSpacing(14)
        self.lbl_read = QLabel("已读:")
        top.addWidget(self.lbl_read)
        self.combo_read = QComboBox()
        self.combo_read.setMinimumWidth(100)
        self.combo_read.setMaximumWidth(140)
        self.combo_read.setEditable(False)
        self.combo_read.addItems(["全部", "已读", "未读"])
        self.combo_read.currentTextChanged.connect(self._on_read_changed)
        top.addWidget(self.combo_read)

        # ---- 隔离区筛选 ----
        top.addSpacing(14)
        self.quar_sep = QFrame()
        self.quar_sep.setFrameShape(QFrame.VLine)
        self.quar_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.quar_sep)
        top.addSpacing(14)
        self.lbl_quar = QLabel("隔离区:")
        top.addWidget(self.lbl_quar)
        self.btn_quar_all = QPushButton("全部")
        self.btn_quar_all.setCheckable(True)
        self.btn_quar_all.setMinimumWidth(80)
        self.btn_quar_all.clicked.connect(lambda: self._set_quar_filter("all"))
        top.addWidget(self.btn_quar_all)
        self.btn_quar_yes = QPushButton("是")
        self.btn_quar_yes.setCheckable(True)
        self.btn_quar_yes.setMinimumWidth(80)
        self.btn_quar_yes.clicked.connect(lambda: self._set_quar_filter("yes"))
        top.addWidget(self.btn_quar_yes)
        self.btn_quar_no = QPushButton("否")
        self.btn_quar_no.setCheckable(True)
        self.btn_quar_no.setMinimumWidth(80)
        self.btn_quar_no.clicked.connect(lambda: self._set_quar_filter("no"))
        top.addWidget(self.btn_quar_no)

        # ---- 是否有备注筛选 ----
        top.addSpacing(14)
        self.note_sep = QFrame()
        self.note_sep.setFrameShape(QFrame.VLine)
        self.note_sep.setFrameShadow(QFrame.Sunken)
        top.addWidget(self.note_sep)
        top.addSpacing(14)
        self.lbl_note = QLabel("备注:")
        top.addWidget(self.lbl_note)
        self.btn_note_all = QPushButton("全部")
        self.btn_note_all.setCheckable(True)
        self.btn_note_all.setMinimumWidth(80)
        self.btn_note_all.clicked.connect(lambda: self._set_note_filter("all"))
        top.addWidget(self.btn_note_all)
        self.btn_note_yes = QPushButton("有")
        self.btn_note_yes.setCheckable(True)
        self.btn_note_yes.setMinimumWidth(80)
        self.btn_note_yes.clicked.connect(lambda: self._set_note_filter("yes"))
        top.addWidget(self.btn_note_yes)
        self.btn_note_no = QPushButton("无")
        self.btn_note_no.setCheckable(True)
        self.btn_note_no.setMinimumWidth(80)
        self.btn_note_no.clicked.connect(lambda: self._set_note_filter("no"))
        top.addWidget(self.btn_note_no)

        top.addStretch()
        self.lbl_count = QLabel("共 0 条")
        self.lbl_count.setStyleSheet("color:#666;")
        top.addWidget(self.lbl_count)
        self.btn_refresh = QPushButton("重新筛选")
        self.btn_refresh.clicked.connect(self._apply_filter)
        top.addWidget(self.btn_refresh)
        scroll.setWidget(top_widget)
        layout.addWidget(scroll)

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
        """半成品分类下拉变化：文本='全部'则清空筛选，否则设为该值。"""
        self._semi_class_filter = set() if text == "全部" else {text}
        self._apply_filter()

    def _on_mtd_changed(self, text):
        self._mtd_filter = text
        self._apply_filter()

    def _on_unit_changed(self, text):
        """单位下拉变化：文本='全部'则清空筛选，否则设为该值。"""
        self._unit_filter = set() if text == "全部" else {text}
        self._apply_filter()

    def _on_workshop_changed(self, text):
        self._workshop_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _set_quar_filter(self, mode):
        """隔离区筛选（全部/是/否）"""
        self._quar_filter = mode
        self.btn_quar_all.setChecked(mode == "all")
        self.btn_quar_yes.setChecked(mode == "yes")
        self.btn_quar_no.setChecked(mode == "no")
        self._apply_filter()

    def _set_note_filter(self, mode):
        """是否有备注筛选（全部/是/否）"""
        self._has_note_filter = mode
        self.btn_note_all.setChecked(mode == "all")
        self.btn_note_yes.setChecked(mode == "yes")
        self.btn_note_no.setChecked(mode == "no")
        self._apply_filter()

    def _on_color_toggled(self):
        """颜色复选框变化：更新已勾选集合并刷新"""
        self.color_filters = {k for k, cb in self.color_checks.items() if cb.isChecked()}
        self._apply_filter()

    @staticmethod
    def _name_cols(df):
        """全列关键字搜索：排除内部维护列(data_id/隔离区/_read 等)后，所有文本/对象列均参与匹配。"""
        _internal = {"data_id", "隔离区", "_read", "_quarantined"}
        cols = [c for c in df.columns if c not in _internal]
        # 仅保留可转字符串搜索的列（跳过纯数值对象列也 OK，str() 同样能匹配，故全部纳入）
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

    def _semi_class_mask(self, df):
        """半成品重分类掩码：空集合=全True；虚拟项「食品/饮料成品半成品」精确匹配+空白
        （列值==分类名 或 列值为空 且 工厂含'食品'/'饮料'）；其他=列值精确==分类名。多值 OR。
        无半成品重分类列时,用物料分类/组件物料类型描述/工厂兜底推断(对齐analyzer.py归并规则)。"""
        if not self._semi_class_filter:
            return pd.Series(True, index=df.index)
        semi_col = "半成品重分类"
        if semi_col in df.columns:
            vals = df[semi_col].astype(str).str.strip()
            blank = df[semi_col].fillna('').astype(str).str.strip() == ''
        else:
            # 兜底:半成品类判断(与analyzer.py ③号规则一致)
            _mtd = df['组件物料类型描述'].astype(str) if '组件物料类型描述' in df.columns else pd.Series('', index=df.index)
            _semi = (df['物料分类'] == '半成品') | _mtd.str.contains('半成品|成品', na=False)
            vals = _semi.map({True: '__SEMI__', False: ''}).reindex(df.index)
            blank = ~_semi
        fac = df['工厂'].astype(str) if '工厂' in df.columns else pd.Series('', index=df.index)
        mask = pd.Series(False, index=df.index)
        for m in self._semi_class_filter:
            if m == _SEMI_VIRT_FOOD:
                mask = mask | (((vals == m) | blank) & fac.str.contains('食品', na=False))
            elif m == _SEMI_VIRT_DRINK:
                mask = mask | (((vals == m) | blank) & fac.str.contains('饮料', na=False))
            else:
                mask = mask | (vals == m)
        return mask

    def _mtd_mask(self, df):
        """组件物料类型描述掩码：all=全True / 具体值=列值==该值。"""
        if self._mtd_filter == "all" or not self._mtd_col:
            return pd.Series(True, index=df.index)
        if self._mtd_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._mtd_col].astype(str).str.strip()
        return vals == self._mtd_filter

    def _unit_mask(self, df):
        """单位掩码：空集合=全True / 非空=列值OR命中被勾选单位集合。列缺失则全True。"""
        if not self._unit_filter or not self._unit_col:
            return pd.Series(True, index=df.index)
        if self._unit_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._unit_col].astype(str).str.strip()
        return vals.isin(self._unit_filter)

    def _build_semi_checkboxes(self, unique_vals):
        """构建半成品分类下拉列表：全部 + 虚拟两项 + 实际各值。"""
        self.grp_semi_class.blockSignals(True)
        kept = self.grp_semi_class.currentText()
        self.grp_semi_class.clear()
        self.grp_semi_class.addItem("全部")
        for v in (_SEMI_VIRT_FOOD, _SEMI_VIRT_DRINK):
            self.grp_semi_class.addItem(v)
        for v in unique_vals:
            if v in (_SEMI_VIRT_FOOD, _SEMI_VIRT_DRINK):
                continue
            self.grp_semi_class.addItem(v)
        if kept and kept != "全部" and kept in self.grp_semi_class.itemTexts():
            self.grp_semi_class.setCurrentText(kept)
        self.grp_semi_class.blockSignals(False)

    def _build_unit_checkboxes(self, unique_vals):
        """构建单位下拉列表：全部 + 各值。"""
        self.grp_unit.blockSignals(True)
        kept = self.grp_unit.currentText()
        self.grp_unit.clear()
        self.grp_unit.addItem("全部")
        for v in unique_vals:
            self.grp_unit.addItem(v)
        if kept and kept != "全部" and kept in self.grp_unit.itemTexts():
            self.grp_unit.setCurrentText(kept)
        self.grp_unit.blockSignals(False)

    def _read_mask(self, df, mode):
        """已读/未读掩码：all=全True / 已读=_read==1 / 未读=_read!=1(含0或NaN)。"""
        if mode == "all" or "_read" not in df.columns:
            return pd.Series(True, index=df.index)
        _r = pd.to_numeric(df["_read"], errors="coerce").fillna(0)
        if mode == "已读":
            return _r == 1
        if mode == "未读":
            return _r != 1
        return pd.Series(True, index=df.index)

    def _on_read_changed(self, text):
        self._read_filter = text
        self._apply_filter()

    def _workshop_mask(self, df, mode):
        """车间掩码：all=全True / 车间名=车间列==该值。列缺失则全True。"""
        if mode == "all" or not self._workshop_col:
            return pd.Series(True, index=df.index)
        if self._workshop_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._workshop_col].astype(str).str.strip()
        return vals == mode

    def _quar_mask(self, df, mode):
        """隔离区掩码：all=全True / yes=隔离区列=='是' / no=隔离区列!='是'。列缺失则全True。"""
        if mode == "all" or "隔离区" not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df["隔离区"].astype(str).str.strip()
        if mode == "yes":
            return vals == "是"
        return vals != "是"

    def _note_mask(self, df, mode):
        """是否有备注掩码：all=全True / yes=备注非空 / no=备注为空。列缺失则全True。"""
        if mode == "all" or "备注" not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df["备注"].astype(str).str.strip()
        if mode == "yes":
            return vals != ""
        return vals == ""

    def _color_mask(self, df):
        """颜色筛选掩码：空集合=全True；否则按 classify_row_color_keys 判断命中颜色集合。"""
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
        """全列关键字掩码：逗号/、/，分隔多值 OR；无关键词=全 True；无候选列=全 True。"""
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

        # 将隔离区列移到订单日期前（让用户一眼可见）
        if "隔离区" in df.columns and "订单日期" in df.columns:
            cols = list(df.columns)
            cols.remove("隔离区")
            idx = cols.index("订单日期")
            cols.insert(idx, "隔离区")
            df = df[cols]

        self.original_df = df.copy()
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)
        QTimer.singleShot(0, lambda: self.table_view.resizeColumnsToContents())
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        if "data_id" in df.columns:
            self.table_view.setColumnHidden(df.columns.get_loc("data_id"), True)
        # 初始化半成品重分类筛选器（复选框组：全部 + 各值 + 虚拟两项）
        # 无半成品重分类列时仍可用虚拟项——通过其他列推断（物料分类/组件物料类型描述/工厂）
        self._semi_class_col = "半成品重分类" if "半成品重分类" in df.columns else None
        if self._semi_class_col:
            unique_vals = df["半成品重分类"].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self._build_semi_checkboxes(unique_vals)
        else:
            # 无半成品重分类列:隐藏UI控件,保留虚拟筛选能力(由虚拟项推断逻辑兜底)
            self.semi_sep.setVisible(False)
            self.lbl_semi_class.setVisible(False)
            self.grp_semi_class.setVisible(False)
        # 初始化 已读/未读 筛选器
        self._read_filter = "all"
        self._read_col = "_read" if "_read" in df.columns else None
        if self._read_col:
            self.combo_read.setCurrentText("全部")
        else:
            self.combo_read.setVisible(False)
            self.read_sep.setVisible(False)
            self.lbl_read.setVisible(False)
        # 初始化组件物料类型描述筛选器
        self._mtd_col = "组件物料类型描述" if "组件物料类型描述" in df.columns else None
        if self._mtd_col:
            unique_vals = df[self._mtd_col].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self.combo_mtd.addItems(unique_vals)
            self.combo_mtd.setCurrentText("全部")
        else:
            self.mtd_sep.setVisible(False)
            self.lbl_mtd.setVisible(False)
            self.combo_mtd.setVisible(False)
        # 初始化车间筛选器
        self._workshop_col = "车间" if "车间" in df.columns else None
        if self._workshop_col:
            unique_vals = df["车间"].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self.combo_workshop.addItems(unique_vals)
        else:
            self.workshop_sep.setVisible(False)
            self.lbl_workshop.setVisible(False)
            self.combo_workshop.setVisible(False)
        self._workshop_filter = "all"
        self.combo_workshop.setCurrentText("全部")
        # 初始化单位筛选器
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
        # 初始化隔离区筛选器（始终可见，因为隔离区列由本对话框计算）
        self._quar_filter = "all"
        self.btn_quar_all.setChecked(True)
        # 初始化备注筛选器
        self._has_note_filter = "all"
        self.btn_note_all.setChecked(True)
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
        mask = (self._name_mask(df) & self._neg_loss_mask(df)
                & self._semi_class_mask(df)
                & self._mtd_mask(df)
                & self._unit_mask(df)
                & self._workshop_mask(df, self._workshop_filter)
                & self._quar_mask(df, self._quar_filter)
                & self._note_mask(df, self._has_note_filter)
                & self._color_mask(df)
                & self._read_mask(df, self._read_filter))
        filtered = df[mask].copy().reset_index(drop=True)
        self.source_model.setDataFrame(filtered)
        self._sort_ctrl.reapply()
        tag = "含未投料" if self._include_zero else "不含未投料"
        note_tag = {"all": "全部", "yes": "有备注", "no": "无备注"}[self._has_note_filter]
        self.lbl_count.setText("共 %d 条（名称含「%s」· %s · %s）" % (len(filtered), self._keywords, tag, note_tag))
        # 动态刷新车间下拉：只列出当前可见数据中实际存在的车间
        if self._workshop_col and not filtered.empty:
            current = self.combo_workshop.currentText()
            new_vals = sorted(filtered[self._workshop_col].dropna().astype(str).str.strip().unique())
            self.combo_workshop.blockSignals(True)
            self.combo_workshop.clear()
            self.combo_workshop.addItem("全部")
            self.combo_workshop.addItems(new_vals)
            # 保留之前选中的项（若仍存在），否则回退"全部"
            if current and current != "全部" and current in new_vals:
                self.combo_workshop.setCurrentText(current)
            else:
                self.combo_workshop.setCurrentText("全部")
                self._workshop_filter = "all"
            self.combo_workshop.blockSignals(False)
        # 动态刷新单位下拉：只列出当前可见数据中实际存在的单位
        if self._unit_col and not filtered.empty:
            current = self.grp_unit.currentText()
            new_vals = sorted(filtered[self._unit_col].dropna().astype(str).str.strip().unique())
            self.grp_unit.blockSignals(True)
            self.grp_unit.clear()
            self.grp_unit.addItem("全部")
            self.grp_unit.addItems(new_vals)
            # 保留之前选中的项（若仍存在），否则回退"全部"
            if current and current != "全部" and current in new_vals:
                self.grp_unit.setCurrentText(current)
                self._unit_filter = {current}
            else:
                self.grp_unit.setCurrentText("全部")
                self._unit_filter = set()
            self.grp_unit.blockSignals(False)

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
        # 标记已读/未读
        mark_read_action = menu.addAction("✅ 标记为已读（选中行）")
        mark_read_action.triggered.connect(
            lambda: self._mark_selected_rows_read(selected_rows))
        mark_unread_action = menu.addAction("⭕ 标记为未读（选中行）")
        mark_unread_action.triggered.connect(
            lambda: self._mark_selected_rows_unread(selected_rows))
        menu.addSeparator()
        # 隔离区操作
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

    def _mark_selected_rows_read(self, rows):
        """标记所有选中行为已读（右键菜单）"""
        df = self.source_model.getDataFrame()
        if df is None:
            return
        # 收集要更新的 data_id 列表
        target_ids = []
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
            if data_id and data_id not in target_ids:
                target_ids.append(data_id)
        if not target_ids:
            return
        # 批量同步主表（循环外，向量化操作）
        count, records = self._sync_main_df_batch(target_ids, 1, df)
        if records:
            save_read_status_batch(records)
        self._refresh_main_table_once()
        if hasattr(self, 'original_df') and 'data_id' in self.original_df.columns:
            orig_mask = self.original_df['data_id'].isin(target_ids)
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
        # 收集要更新的 data_id 列表
        target_ids = []
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
            if data_id and data_id not in target_ids:
                target_ids.append(data_id)
        if not target_ids:
            return
        # 批量同步主表（循环外，向量化操作）
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

    def _sync_main_df_batch(self, target_ids, read_value, source_df):
        """批量同步主表内存中的已读状态（向量化操作，性能优化）

        相比 _sync_main_df 的逐行操作，此方法在循环外一次性完成所有更新。
        返回 (count, records) 其中 count 是实际更新的条数，records 是用于落盘的记录列表。
        """
        main_df = self.main_window.view_model.df
        if main_df is None or not target_ids:
            return 0, []

        # 确保主表有 data_id 列
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

        # 确保 _read 列存在
        if '_read' not in main_df.columns:
            main_df['_read'] = 0

        # 向量化批量更新
        mask = main_df['data_id'].isin(target_ids)
        if not mask.any():
            return 0, []

        # 记录更新前的状态（用于判断是否需要落盘）
        current_vals = main_df.loc[mask, '_read']
        need_update = current_vals != read_value
        updated_ids = main_df.loc[mask, 'data_id'].tolist()

        # 批量赋值（向量化操作，比 at[] 快得多）
        main_df.loc[mask & need_update, '_read'] = read_value

        # 构建落盘记录
        records = []
        count = int(need_update.sum())
        if count > 0:
            # 获取 fingerprint
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

            # 从 source_df 获取 qty 和 note（使用更新后的数据）
            for did in updated_ids:
                if did in fingerprints:
                    qty = snapshot_qty_for(source_df, did)
                    note = snapshot_note_for(source_df, did)
                    records.append((did, read_value, fingerprints[did], qty, note))

        # 只赋值一次 view_model.df
        self.main_window.view_model.df = main_df
        return count, records

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
        # 同时更新本看板自己的 original_df（关键：否则 _color_mask 会读到旧值，导致加入隔离区后数据消失）
        if (hasattr(self, "original_df") and "data_id" in self.original_df.columns
                and "隔离区" in self.original_df.columns):
            self.original_df.loc[self.original_df["data_id"].isin(ids), "隔离区"] = "是" if flag else ""
        # 同时更新本看板 source_model 的 _quarantined 列，确保颜色筛选不丢失数据
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
