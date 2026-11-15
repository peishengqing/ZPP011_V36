# -*- coding: utf-8 -*-
"""DashboardShell 完整集成 · 未读看板
覆盖全部看板逻辑，基于 DashboardShell 通用外壳。

定位：把「未读概览」弹窗里的 4 类未读（隔离区 / 变动提醒 / 替代料 / 偏差率预警）
聚合进一个可自由筛选的看板，方便裴哥一次性查看 / 下钻所有未读记录。

未读分类掩码单一真源 = dashboard_controller._unread_audit_masks()，
与未读概览弹窗、审核队列徽标、主表「未读」卡片完全对齐，杜绝口径分叉。
"""
import re
import pandas as pd
from PySide6.QtWidgets import (
    QLineEdit, QGroupBox, QLabel, QVBoxLayout, QHBoxLayout, QComboBox
)
from PySide6.QtCore import Qt

from gui_pyside6.components.dashboard_shell import DashboardShell
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import get_quarantined_ids
from core.read_status import load_read_status
from gui_pyside6.utils.semi_class import merge_semi_class_values, ensure_semi_class_column

# 4 类未读分类名称（顺序即下拉顺序，与未读概览弹窗一致）
_CAT_NAMES = ["隔离区", "变动提醒", "替代料", "偏差率预警"]


class UnreadDashboard(DashboardShell):
    """未读看板 · DashboardShell 完整实现"""

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("未读看板 · DashboardShell")
        self.main_window = main_window

        # 筛选状态
        self._keywords = ""
        self._cat_filter = "全部未读"
        self._read_filter = "未读"
        self._semi_class_filter = set()
        self._semi_class_col = None
        self._mtd_filter = "all"
        self._mtd_col = None
        self._workshop_filter = "all"
        self._workshop_col = None
        self._factory_filter = "all"
        self._factory_col = None
        self._quar_filter = "all"
        self._has_note_filter = "all"
        self._unit_filter = set()
        self._unit_col = None
        # 归属看板：独立筛选维度（全部 / 负损 / 正损 / 替代料 / 偏差率预警 / 隔离区 / 半成品）
        self._board_filter = "全部"
        self.original_df = None
        self.source_model = None
        self._kw_timer = None
        self._col_filter_ctrl = None
        self._header = None
        self._sort_ctrl = None
        self._initializing = True

        # 分类掩码（单一真源 = _unread_audit_masks），由 set_data 填充
        self._cat_masks = {}      # name -> bool Series（cat & read，供 KPI 计数，与未读概览弹窗一致）
        self._cat_all = None      # 4 类 OR（cat & read）
        # 纯分类标志（不含 read 约束），供筛选维度使用：
        # 选中某具体分类 + 已读=全部 时应显示该分类全部行（含已读），
        # 故筛选用纯标志，read 由独立「已读状态」筛选器正交叠加。
        self._cat_pure = {}       # name -> bool Series（纯分类标志）
        self._cat_all_pure = None # 4 类 OR（纯标志）

        # 设置标题和基础筛选
        self._setup_basic_ui()

        if df is not None:
            self.set_data(df)
        else:
            self._empty_model = DataFrameModel()
            self.set_model(self._empty_model)
            self.set_row_count(0)

    def _setup_basic_ui(self):
        """覆盖基类 UI 设置：构建未读看板特有筛选器。"""
        self.set_title("未读看板", "全部未读 · 隔离区 / 变动提醒 / 替代料 / 偏差率预警")

        self._build_unread_filters()

    def _build_unread_filters(self):
        """构建未读看板特有筛选器（抽屉三组：未读维度 / 组织与分类 / 状态）。"""
        current_layout = self.drawer_layout

        # 清空内容
        while current_layout.count():
            child = current_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

        # ── 第一组：未读维度 ──
        self.gp_unread = QGroupBox("未读维度")
        self.gp_unread.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 0px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        unread_layout = QVBoxLayout(self.gp_unread)
        unread_layout.setSpacing(8)

        # 未读分类
        cat_row = QHBoxLayout()
        cat_row.setSpacing(8)
        cat_row.addWidget(QLabel("未读分类:"))
        self.combo_cat = QComboBox()
        self.combo_cat.setFixedWidth(160)
        self.combo_cat.addItems(["全部未读"] + _CAT_NAMES)
        self.combo_cat.setCurrentText("全部未读")
        self.combo_cat.currentTextChanged.connect(self._on_cat_changed)
        cat_row.addWidget(self.combo_cat)
        cat_row.addStretch()
        unread_layout.addLayout(cat_row)

        # 已读
        read_row = QHBoxLayout()
        read_row.setSpacing(8)
        read_row.addWidget(QLabel("已读状态:"))
        self.combo_read = QComboBox()
        self.combo_read.setFixedWidth(160)
        self.combo_read.addItems(["全部", "已读", "未读"])
        self.combo_read.setCurrentText("未读")
        self.combo_read.currentTextChanged.connect(self._on_read_changed)
        read_row.addWidget(self.combo_read)
        read_row.addStretch()
        unread_layout.addLayout(read_row)

        # 关键字搜索
        kw_row = QHBoxLayout()
        kw_row.setSpacing(8)
        kw_row.addWidget(QLabel("关键字搜索(逗号分隔):"))
        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("输入名称/物料编码等关键词")
        self.edit_keywords.setMinimumWidth(200)
        self.edit_keywords.textChanged.connect(self._on_keywords_changed)
        kw_row.addWidget(self.edit_keywords)
        kw_row.addStretch()
        unread_layout.addLayout(kw_row)

        current_layout.addWidget(self.gp_unread)

        # ── 第二组：组织与分类 ──
        self.gp_org_class = QGroupBox("组织与分类")
        self.gp_org_class.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 12px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        org_class_layout = QHBoxLayout(self.gp_org_class)
        org_class_layout.setSpacing(12)

        org_class_layout.addWidget(QLabel("车间:"))
        self.combo_workshop = QComboBox()
        self.combo_workshop.setFixedWidth(120)
        self.combo_workshop.addItems(["全部"])
        self.combo_workshop.currentTextChanged.connect(self._on_workshop_changed)
        org_class_layout.addWidget(self.combo_workshop)

        org_class_layout.addWidget(QLabel("工厂:"))
        self.combo_factory = QComboBox()
        self.combo_factory.setFixedWidth(120)
        self.combo_factory.addItems(["全部"])
        self.combo_factory.currentTextChanged.connect(self._on_factory_changed)
        org_class_layout.addWidget(self.combo_factory)

        org_class_layout.addWidget(QLabel("半成品:"))
        self.grp_semi_class = QComboBox()
        self.grp_semi_class.setFixedWidth(120)
        self.grp_semi_class.addItems(["全部"])
        self.grp_semi_class.currentTextChanged.connect(self._on_semi_class_changed)
        org_class_layout.addWidget(self.grp_semi_class)

        org_class_layout.addWidget(QLabel("物料类型:"))
        self.combo_mtd = QComboBox()
        self.combo_mtd.setFixedWidth(120)
        self.combo_mtd.addItems(["全部"])
        self.combo_mtd.currentTextChanged.connect(self._on_mtd_changed)
        org_class_layout.addWidget(self.combo_mtd)

        # 归属看板：独立筛选维度（与「未读分类」正交并存）
        org_class_layout.addWidget(QLabel("归属看板:"))
        self.combo_board = QComboBox()
        self.combo_board.setFixedWidth(120)
        self.combo_board.addItems(["全部", "负损", "正损", "变动提醒", "替代料", "偏差率预警", "隔离区", "半成品"])
        self.combo_board.setCurrentText("全部")
        self.combo_board.currentTextChanged.connect(self._on_board_changed)
        org_class_layout.addWidget(self.combo_board)

        org_class_layout.addStretch()
        current_layout.addWidget(self.gp_org_class)

        # ── 第三组：状态 ──
        self.gp_status = QGroupBox("状态")
        self.gp_status.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 12px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        status_layout = QHBoxLayout(self.gp_status)
        status_layout.setSpacing(12)

        status_layout.addWidget(QLabel("单位:"))
        self.grp_unit = QComboBox()
        self.grp_unit.setFixedWidth(120)
        self.grp_unit.addItems(["全部"])
        self.grp_unit.currentTextChanged.connect(self._on_unit_changed)
        status_layout.addWidget(self.grp_unit)

        status_layout.addWidget(QLabel("隔离区:"))
        self.grp_quar = QComboBox()
        self.grp_quar.setFixedWidth(120)
        self.grp_quar.addItems(["全部", "是", "否"])
        self.grp_quar.currentTextChanged.connect(self._on_quar_changed)
        status_layout.addWidget(self.grp_quar)

        status_layout.addWidget(QLabel("备注:"))
        self.grp_note = QComboBox()
        self.grp_note.setFixedWidth(120)
        self.grp_note.addItems(["全部", "有", "无"])
        self.grp_note.currentTextChanged.connect(self._on_note_changed)
        status_layout.addWidget(self.grp_note)

        status_layout.addStretch()
        current_layout.addWidget(self.gp_status)

    # ── 筛选控件回调 ──
    def _on_cat_changed(self, text):
        self._cat_filter = text
        self._apply_filter()

    def _on_keywords_changed(self, text):
        self._keywords = text
        self._apply_filter()

    def _on_read_changed(self, text):
        self._read_filter = text
        self._apply_filter()

    def _on_workshop_changed(self, text):
        self._workshop_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _on_factory_changed(self, text):
        self._factory_filter = "all" if text == "全部" else text
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

    def _on_board_changed(self, text):
        self._board_filter = text
        self._apply_filter()

    def _on_quar_changed(self, text):
        self._quar_filter = text
        self._apply_filter()

    def _on_note_changed(self, text):
        self._has_note_filter = "all" if text == "全部" else "yes" if text == "有" else "no"
        self._apply_filter()

    def set_data(self, df):
        """设置数据并初始化。"""
        df = df.copy()

        # 确保数据完整性
        if "半成品重分类" not in df.columns:
            try:
                df, _ = ensure_semi_class_column(df)
            except Exception:
                df["半成品重分类"] = ""

        # 保证 data_id 存在
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

        # 隔离区列
        _qset = get_quarantined_ids()
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

        # 备注列移动到 data_id 前面
        if "备注" in df.columns and "data_id" in df.columns:
            cols = list(df.columns)
            cols.remove("备注")
            cols.insert(cols.index("data_id"), "备注")
            df = df[cols]

        # 隔离区列移到订单日期前
        if "隔离区" in df.columns and "订单日期" in df.columns:
            cols = list(df.columns)
            cols.remove("隔离区")
            idx = cols.index("订单日期")
            cols.insert(idx, "隔离区")
            df = df[cols]

        # 半成品重分类定位
        if "半成品重分类" in df.columns:
            _cols = list(df.columns)
            _cols.remove("半成品重分类")
            _anchor = next((c for c in ("组件物料类型描述", "组件物料类型", "物料类型") if c in _cols), None)
            _idx = _cols.index(_anchor) + 1 if _anchor else len(_cols)
            _cols.insert(_idx, "半成品重分类")
            df = df[_cols]

        self.original_df = df.copy()

        # ── 未读分类掩码 ──
        #   · self._cat_pure（纯分类标志）：供「未读分类」筛选维度使用。
        #     选中某具体分类 + 已读=全部 时应显示该分类【全部】行（含已读），
        #     故筛选用纯标志，read 由独立「已读状态」筛选器正交叠加。
        #   · self._cat_masks（cat & read）：供 KPI 计数，与未读概览弹窗/审核队列徽标同源。
        #     由纯标志 ∩ read 推出，与 dashboard_controller._unread_audit_masks 输出完全一致。
        self._cat_pure = self._compute_pure_cat_masks(df)
        self._cat_all_pure = (self._cat_pure["隔离区"] | self._cat_pure["变动提醒"]
                               | self._cat_pure["替代料"] | self._cat_pure["偏差率预警"])
        _read = (pd.to_numeric(df["_read"], errors="coerce").fillna(0).astype(int) == 0) \
            if "_read" in df.columns else pd.Series(True, index=df.index)
        self._cat_masks = {n: (self._cat_pure[n] & _read) for n in _CAT_NAMES}
        self._cat_all = self._cat_all_pure & _read

        # ── 归属看板（裴哥新增需求）：逐行标注命中哪些看板 ──
        df["归属看板"] = self._compute_board_tags(df)
        # 把「归属看板」列插到「隔离区」之后，靠前展示
        if "归属看板" in df.columns and "隔离区" in df.columns:
            _cols = list(df.columns)
            _cols.remove("归属看板")
            _idx = _cols.index("隔离区") + 1
            _cols.insert(_idx, "归属看板")
            df = df[_cols]
        self.original_df = df.copy()

        # 加载已读来源（沿用负损看板逻辑，便于「已读来源」列展示）
        if "data_id" in self.original_df.columns:
            try:
                data_ids = [str(x) for x in self.original_df["data_id"].tolist()]
                status_map = load_read_status(data_ids)
                if status_map:
                    source_map = {did: (vals[5] if len(vals) > 5 and vals[5] else '')
                                  for did, vals in status_map.items()}
                    self.original_df["_read_source"] = self.original_df["data_id"].astype(str).map(source_map).fillna('').astype(str)
                    if "_read" in self.original_df.columns:
                        self.original_df.loc[self.original_df["_read"] != 1, "_read_source"] = ''
                else:
                    self.original_df["_read_source"] = ''
            except Exception:
                self.original_df["_read_source"] = ''
        else:
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

        # 创建模型
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.set_model(self.source_model)
        # 归属看板列：可点击下钻对应看板 + 悬停提示
        if self.table_view is not None:
            self.table_view.setMouseTracking(True)
            self.table_view.cellClicked.connect(self._on_table_cell_clicked)
            self.table_view.entered.connect(self._on_cell_hovered)
        self.set_row_count(len(df))

        # 设置 KPI
        self._set_kpi()

        # 初始化筛选器
        self._initialize_filters()

        # 应用默认筛选
        self._apply_default_filter()

        self._initializing = False

    def _set_kpi(self):
        """KPI 卡：与未读概览弹窗 / 审核队列徽标同源。"""
        counts = self._cat_masks
        if counts:
            n_quar = int(counts["隔离区"].sum())
            n_change = int(counts["变动提醒"].sum())
            n_alt = int(counts["替代料"].sum())
            n_dev = int(counts["偏差率预警"].sum())
        else:
            n_quar = n_change = n_alt = n_dev = 0
        n_all = n_quar + n_change + n_alt + n_dev

        def _st(n):
            return "warn" if n > 0 else ""

        self.set_kpi_data([
            {"label": "全部未读", "value": f"{n_all} 条", "status": _st(n_all)},
            {"label": "隔离区", "value": f"{n_quar} 条", "status": _st(n_quar)},
            {"label": "变动提醒", "value": f"{n_change} 条", "status": _st(n_change)},
            {"label": "替代料", "value": f"{n_alt} 条", "status": _st(n_alt)},
            {"label": "偏差率预警", "value": f"{n_dev} 条", "status": _st(n_dev)},
        ])

    def _initialize_filters(self):
        """初始化所有筛选器。"""
        df = self.original_df

        # 半成品重分类
        self._semi_class_col = "半成品重分类" if "半成品重分类" in df.columns else None
        unique_vals = []
        if self._semi_class_col:
            unique_vals = sorted(v for v in df["半成品重分类"].dropna().astype(str).str.strip().unique() if v)
        self._build_semi_checkboxes(unique_vals)
        self.gp_unread.setVisible(True)

        # 已读筛选
        self._read_col = "_read" if "_read" in df.columns else None
        if self._read_col:
            self.combo_read.setCurrentText("未读")
        else:
            self.combo_read.setVisible(False)

        # 物料类型描述筛选
        self._mtd_col = "组件物料类型描述" if "组件物料类型描述" in df.columns else None
        if self._mtd_col:
            unique_vals = sorted(v for v in df[self._mtd_col].dropna().astype(str).str.strip().unique() if v)
            self._replace_combo_items(self.combo_mtd, unique_vals, "all")
        else:
            self.combo_mtd.setVisible(False)

        # 车间筛选
        self._workshop_col = "车间" if "车间" in df.columns else None
        if self._workshop_col:
            unique_vals = sorted(v for v in df["车间"].dropna().astype(str).str.strip().unique() if v)
            self._replace_combo_items(self.combo_workshop, unique_vals, "all")
        else:
            self.combo_workshop.setVisible(False)

        # 工厂筛选
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
            self.combo_factory.setVisible(False)

        # 单位筛选
        self._unit_col = "单位" if "单位" in df.columns else None
        if self._unit_col:
            unique_vals = df["单位"].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self._build_unit_checkboxes(unique_vals)
        else:
            self.grp_unit.setVisible(False)

    def _get_cascade_exclude_mtd(self):
        """获取排除物料类型（与负损看板一致）。"""
        return ["广宣", "礼品", "促销", "赠品", "样品", "营销"]

    def _build_semi_checkboxes(self, unique_vals):
        """构建半成品分类下拉列表。"""
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
        """构建单位下拉列表。"""
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

    def _replace_combo_items(self, combo, unique_vals, default_key):
        """通用下拉刷新。"""
        combo.blockSignals(True)
        kept = combo.currentText()
        combo.clear()
        combo.addItem("全部")
        combo.addItems(unique_vals)
        if kept and kept != "全部" and combo.findText(kept) >= 0:
            combo.setCurrentText(kept)
        else:
            combo.setCurrentText("全部")
        combo.blockSignals(False)

    def _apply_default_filter(self):
        """默认视图自适应：先试「全部未读 + 未读」，未读空但全量非空时回退「已读=全部」。

        与负损看板同纪律：避免「未读 0 行」时表格与下拉全部塌缩成空白，
        看着像程序坏了。必须在 _initializing=False 之后、首次 _apply_filter 之前调用。
        """
        self._cat_filter = "全部未读"
        self._read_filter = "未读"
        self.combo_cat.setCurrentText("全部未读")
        if self._read_col and hasattr(self, "combo_read"):
            self.combo_read.setCurrentText("未读")
        # 先按「未读」跑一次
        self._apply_filter()
        sm = getattr(self, "source_model", None)
        if sm is None or sm.rowCount() > 0:
            return                      # 有未读 → 保持默认，不动用户预期
        # 未读 0 行：确认全量确实非空才回退（两者皆空则保持未读，避免空表套空表）
        if self.original_df is not None and len(self.original_df) > 0:
            self._read_filter = "全部"
            if hasattr(self, "combo_read"):
                self.combo_read.setCurrentText("全部")
            else:
                self._apply_filter()

    def _apply_filter(self):
        """应用筛选逻辑。"""
        if self._initializing:
            return

        df = self.original_df.copy()

        mask = (
            self._name_mask(df)
            & self._cat_mask(df, self._cat_filter)
            & self._semi_class_mask(df)
            & self._quar_mask(df, self._quar_filter)
            & self._note_mask(df, self._has_note_filter)
            & self._read_mask(df, self._read_filter)
            & self._factory_mask(df, self._factory_filter)
            & self._mtd_mask(df)
            & self._workshop_mask(df, self._workshop_filter)
            & self._unit_mask(df)
            & self._board_mask(df)
        )

        df = df[mask]

        self.source_model.setDataFrame(df)
        self.set_row_count(len(df))
        self._refresh_cascade_combos()

    def _other_conditions_mask(self, df, exclude):
        """构造「除 exclude 维度外、所有其他筛选条件」的与掩码。"""
        mask = (self._name_mask(df)
                & self._cat_mask(df, self._cat_filter)
                & self._semi_class_mask(df)
                & self._quar_mask(df, self._quar_filter)
                & self._note_mask(df, self._has_note_filter)
                & self._read_mask(df, self._read_filter))
        mask &= self._factory_mask(df, self._factory_filter)
        if exclude != 'mtd':
            mask &= self._mtd_mask(df)
        if exclude != 'workshop':
            mask &= self._workshop_mask(df, self._workshop_filter)
        if exclude != 'unit':
            mask &= self._unit_mask(df)
        return mask

    def _refresh_cascade_combos(self, changed='all'):
        """重算物料类型 / 车间 / 单位三个下拉的选项（changed='mtd'/'workshop'/'unit'/'all'）。"""
        if getattr(self, '_initializing', False):
            return
        df = getattr(self, 'original_df', None)
        if df is None or df.empty or not hasattr(self, 'source_model'):
            return

        sub_mtd = df[self._other_conditions_mask(df, exclude='mtd')]
        mtd_vals = sorted(
            v for v in sub_mtd[self._mtd_col].dropna().astype(str).str.strip().unique() if v
        ) if (self._mtd_col and self._mtd_col in sub_mtd.columns) else []
        mtd_vals = [v for v in mtd_vals if v not in self._get_cascade_exclude_mtd()]
        self._replace_combo_items(self.combo_mtd, mtd_vals, self._mtd_filter)

        sub_ws = df[self._other_conditions_mask(df, exclude='workshop')]
        ws_vals = sorted(
            v for v in sub_ws[self._workshop_col].dropna().astype(str).str.strip().unique() if v
        ) if (self._workshop_col and self._workshop_col in sub_ws.columns) else []
        self._replace_combo_items(self.combo_workshop, ws_vals, self._workshop_filter)

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
                self.grp_unit.addItems(['全部'] + unit_vals)
                if keep_units:
                    idx = self.grp_unit.findText(next(iter(keep_units)))
                    if idx >= 0:
                        self.grp_unit.setCurrentIndex(idx)
                else:
                    self.grp_unit.setCurrentIndex(0)
            finally:
                self.grp_unit.blockSignals(False)
        self._unit_filter = keep_units if keep_units else set()

    def _name_cols(self, df):
        """全列关键字搜索：排除内部维护列。"""
        _internal = {"data_id", "隔离区", "_read", "_quarantined", "_read_source", "已读来源"}
        cols = [c for c in df.columns if c not in _internal]
        return cols

    def _cat_mask(self, df, mode):
        """未读分类掩码（用纯标志，read 由独立「已读状态」正交叠加）：

        全部未读 = 4 类纯标志 OR；具体分类 = 对应纯标志；列缺失则全 True。
        选中「替代料」+ 已读=全部 → 显示所有替代料行（含已读），不再被 _read 卡死。
        """
        if mode == "全部未读":
            if self._cat_all_pure is not None:
                return self._cat_all_pure.reindex(df.index).fillna(False).astype(bool)
            return pd.Series(True, index=df.index)
        m = self._cat_pure.get(mode)
        if m is None:
            return pd.Series(True, index=df.index)
        return m.reindex(df.index).fillna(False).astype(bool)

    def _compute_pure_cat_masks(self, df):
        """纯分类标志（不含 read 约束），与 _unread_audit_masks 的 4 个判定完全一致。

        直接复用 core.alert_monitor.filter_alt_alerts / core.threshold_config.dev_alert_mask，
        与控制器同源，避免两套口径；阈值取 main_window.alert_monitor.threshold（与替代料看板一致）。
        """
        idx = df.index

        def _flag(col):
            if col not in df.columns:
                return pd.Series(False, index=idx)
            return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int) == 1
        quar = _flag("_quarantined")
        change = _flag("_post_audit_changed")

        # 替代料：filter_alt_alerts 命中（与替代料看板 / 未读概览弹窗同一判据）
        alt = pd.Series(False, index=idx)
        if "是否替代料" in df.columns:
            threshold = 10
            am = getattr(self.main_window, "alert_monitor", None)
            if am is not None:
                try:
                    threshold = float(getattr(am, "threshold", 10))
                except (TypeError, ValueError):
                    threshold = 10
            try:
                from core.alert_monitor import filter_alt_alerts
                hits = filter_alt_alerts(df, threshold)
                if not hits.empty:
                    alt.loc[hits.index] = True
            except Exception:
                alt = df["是否替代料"].astype(str).str.strip() == "1"

        # 偏差率预警：core.threshold_config.dev_alert_mask（阈值/除零钳位/未投料排除同源）
        dev = pd.Series(False, index=idx)
        try:
            from core import threshold_config as _thr
            d = _thr.dev_alert_mask(df)
            if d is not None:
                dev = d
        except Exception:
            pass

        return {"隔离区": quar, "变动提醒": change, "替代料": alt, "偏差率预警": dev}

    def _compute_board_tags(self, df):
        """逐行标注「归属看板」：命中负损/正损/替代料/偏差率预警/隔离区/半成品 的标签，
        多标签用「、」连接；全不命中标「其他」。判定与各看板自身口径一致。
        """
        idx = df.index
        # 数量列（负损/正损共用）
        act_col = next((c for c in ["数量-实际", "实际", "实际数量", "数量 - 实际", "actual"]
                        if c in df.columns), None)
        qty_col = next((c for c in ["数量-定额", "定额", "定额数量", "数量 - 定额", "quota"]
                        if c in df.columns), None)
        if act_col and qty_col:
            a = pd.to_numeric(df[act_col], errors="coerce")
            q = pd.to_numeric(df[qty_col], errors="coerce")
            neg = a.notna() & q.notna() & (a >= 0) & (a < q)          # 含未投料
            pos = a.notna() & q.notna() & (q > 0) & (a > q)            # 超投
        else:
            neg = pd.Series(False, index=idx)
            pos = pd.Series(False, index=idx)
        # 半成品：物料编码 400/410 开头（与半成品看板一致）
        if "物料编码" in df.columns:
            semi = df["物料编码"].astype(str).str.strip().str.startswith(("400", "410"), na=False)
        else:
            semi = pd.Series(False, index=idx)
        # 复用纯分类标志
        pure = self._cat_pure
        cols = {
            "负损": neg,
            "正损": pos,
            "变动提醒": pure.get("变动提醒", pd.Series(False, index=idx)),
            "替代料": pure.get("替代料", pd.Series(False, index=idx)),
            "偏差率预警": pure.get("偏差率预警", pd.Series(False, index=idx)),
            "隔离区": pure.get("隔离区", pd.Series(False, index=idx)),
            "半成品": semi,
        }
        names = list(cols.keys())
        arrs = [cols[n].reindex(idx).fillna(False).to_numpy() for n in names]
        labels = []
        for i in range(len(idx)):
            hit = [names[j] for j in range(len(names)) if bool(arrs[j][i])]
            labels.append("、".join(hit) if hit else "其他")
        return pd.Series(labels, index=idx)


    def _semi_class_mask(self, df):
        """半成品重分类掩码：空集合=全True；否则精确匹配列值。多值 OR。"""
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

    def _board_mask(self, df):
        """归属看板独立筛选维度：全部=全True / 具体标签=逐行「归属看板」含该标签。

        与「未读分类」正交并存——两者可同时生效。匹配基于 _compute_board_tags 输出
        的多标签「、」串，用子串精确命中（如选「负损」会筛出含「负损」标签的行）。
        """
        if self._board_filter == "全部" or "归属看板" not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df["归属看板"].astype(str)
        return vals.str.contains(self._board_filter, regex=False)

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

    def _workshop_mask(self, df, mode):
        """车间掩码：all=全True / 车间名=车间列==该值。列缺失则全True。"""
        if mode == "all" or not self._workshop_col:
            return pd.Series(True, index=df.index)
        if self._workshop_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._workshop_col].astype(str).str.strip()
        return vals == mode

    def _factory_mask(self, df, mode):
        """工厂掩码：all=全True / 工厂名=工厂名称列==该值。列缺失则全True。"""
        if mode == "all" or not self._factory_col:
            return pd.Series(True, index=df.index)
        if self._factory_col not in df.columns:
            return pd.Series(True, index=df.index)
        vals = df[self._factory_col].astype(str).str.strip()
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

    def closeEvent(self, event):
        """关闭事件。"""
        self.action_triggered.emit("close")
        event.accept()

    # ── 归属看板列：点击下钻 + 悬停提示 ──
    _BOARD_DRILL = {
        "负损": "_show_neg_loss_dashboard",
        "正损": "_show_pos_loss_dashboard",
        "变动提醒": "_show_audit_changes_dialog",
        "替代料": "_show_alert_dashboard",
        "偏差率预警": "_show_deviation_warning_dialog",
        "隔离区": "_open_quarantine_dialog",
        "半成品": "_show_semi_dashboard",
    }

    def _on_table_cell_clicked(self, row, col):
        """点击「归属看板」列单元格 → 解析标签并下钻对应看板（非模态多开，不关闭本看板）。"""
        sm = self.source_model
        if sm is None or col < 0 or col >= len(sm._display_columns):
            return
        if sm._display_columns[col] != "归属看板":
            return
        idx = sm.index(row, col)
        text = sm.data(idx, Qt.DisplayRole)
        if not text or text == "其他":
            return
        mw = self.main_window
        if mw is None:
            return
        for tag in str(text).split("、"):
            fn = getattr(mw, self._BOARD_DRILL.get(tag.strip(), ""), None)
            if fn is not None:
                try:
                    fn()
                except Exception:
                    import traceback
                    traceback.print_exc()

    def _on_cell_hovered(self, index):
        """悬停「归属看板」列时提示可下钻。"""
        sm = self.source_model
        if sm is None or index.column() < 0 or index.column() >= len(sm._display_columns):
            self.set_status("")
            return
        if sm._display_columns[index.column()] == "归属看板":
            self.set_status("点击「归属看板」标签可下钻对应看板（负损/正损/变动提醒/替代料/偏差率预警/隔离区/半成品）")
        else:
            self.set_status("")


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    shell = UnreadDashboard(None, None)
    shell.setWindowTitle("未读看板 DashboardShell 测试")
    shell.resize(1400, 800)
    shell.show()

    import time
    time.sleep(3)

    print("DashboardShell 未读看板测试正常")
    app.quit()
