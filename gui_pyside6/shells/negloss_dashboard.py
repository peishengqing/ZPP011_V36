# -*- coding: utf-8 -*-
"""DashboardShell 完整集成 · 负损看板
覆盖全部看板逻辑，基于 DashboardShell 通用外壳
"""
import re
import pandas as pd
from PySide6.QtWidgets import QLineEdit

from gui_pyside6.components.dashboard_shell import DashboardShell
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import get_quarantined_ids
from core.read_status import load_read_status
from gui_pyside6.utils.semi_class import merge_semi_class_values, ensure_semi_class_column


class NegLossDashboard(DashboardShell):
    """负损看板 · DashboardShell 完整实现"""

    # 材料排除清单（用于级联筛选）
    _CASCADE_EXCLUDE_MTD = {'食品成品', '饮料成品'}  # 负损看板永远筛不出成品的类型（v43.81 既有口径）

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("负损(含未投料)看板 · DashboardShell")
        self.main_window = main_window

        # 筛选状态
        self._keywords = ""
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
        self._unit_col = None
        self.color_filters = set()
        self.original_df = None
        self.source_model = None
        self._kw_timer = None
        self._col_filter_ctrl = None
        self._header = None
        self._sort_ctrl = None
        self._initializing = True

        # 设置标题和基础筛选
        self._setup_basic_ui()

        if df is not None:
            self.set_data(df)
        else:
            # 空数据初始化
            self._empty_model = DataFrameModel()
            self.set_model(self._empty_model)
            self.set_row_count(0)

    def _setup_basic_ui(self):
        """覆盖基类 UI 设置"""
        # 1. 在标题条中替换工厂选择为完整筛选
        # 2. 在筛选抽屉中填充所有筛选控件
        # 3. 在操作条中添加负损特定按钮

        self.set_title("负损看板", "含未投料")

        # 在标题条中，我们保留 Concerted 的 factory_select
        # 但负损看板使用独立的筛选区域

        # 在筛选抽屉中添加负损特定控件
        self._build_negloss_filters()

    def _build_negloss_filters(self):
        """构建负损看板特有的筛选器"""
        # 清空并重新构建抽屉内容
        # 先保存现有抽屉布局
        current_layout = self.drawer_layout

        # 清空内容
        while current_layout.count():
            child = current_layout.takeAt(0)
            child.widget().deleteLater()

        # 第一组：物料和操作条件（关键字 + 含未投料）
        self.gp_material_info = QGroupBox("物料条件")
        self.gp_material_info.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 0px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        gp_material_layout = QVBoxLayout(self.gp_material_info)
        gp_material_layout.setSpacing(8)

        # 关键字搜索
        kw_row = QHBoxLayout()
        kw_row.setSpacing(8)
        kw_row.addWidget(QLabel("关键字搜索(逗号分隔):"))
        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("输入名称关键词")
        self.edit_keywords.setMinimumWidth(200)
        self.edit_keywords.textChanged.connect(self._on_keywords_changed)
        kw_row.addWidget(self.edit_keywords)

        # 含未投料复选框
        self.chk_include_zero = QCheckBox("含未投料")
        self.chk_include_zero.setToolTip("包含未投料：实际=0 的行也视为负损")
        self.chk_include_zero.setChecked(True)
        self.chk_include_zero.stateChanged.connect(self._on_include_zero_changed)
        kw_row.addWidget(self.chk_include_zero)

        kw_row.addStretch()
        gp_material_layout.addLayout(kw_row)

        current_layout.addWidget(self.gp_material_info)

        # 第二组：组织与分类筛选
        self.gp_org_class = QGroupBox("组织与分类")
        self.gp_org_class.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 12px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        org_class_layout = QHBoxLayout(self.gp_org_class)
        org_class_layout.setSpacing(12)

        # 车间
        org_class_layout.addWidget(QLabel("车间:"))
        self.combo_workshop = QComboBox()
        self.combo_workshop.setFixedWidth(120)
        self.combo_workshop.addItems(["全部"])
        self.combo_workshop.currentTextChanged.connect(self._on_workshop_changed)
        org_class_layout.addWidget(self.combo_workshop)

        # 工厂
        org_class_layout.addWidget(QLabel("工厂:"))
        self.combo_factory = QComboBox()
        self.combo_factory.setFixedWidth(120)
        self.combo_factory.addItems(["全部"])
        self.combo_factory.currentTextChanged.connect(self._on_factory_changed)
        org_class_layout.addWidget(self.combo_factory)

        # 半成品分类
        org_class_layout.addWidget(QLabel("半成品:"))
        self.grp_semi_class = QComboBox()
        self.grp_semi_class.setFixedWidth(120)
        self.grp_semi_class.addItems(["全部"])
        self.grp_semi_class.currentTextChanged.connect(self._on_semi_class_changed)
        org_class_layout.addWidget(self.grp_semi_class)

        # 物料类型
        org_class_layout.addWidget(QLabel("物料类型:"))
        self.combo_mtd = QComboBox()
        self.combo_mtd.setFixedWidth(120)
        self.combo_mtd.addItems(["全部"])
        self.combo_mtd.currentTextChanged.connect(self._on_mtd_changed)
        org_class_layout.addWidget(self.combo_mtd)

        org_class_layout.addStretch()
        current_layout.addWidget(self.gp_org_class)

        # 第三组：单位和状态筛选
        self.gp_unit_status = QGroupBox("单位与状态")
        self.gp_unit_status.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 12px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        unit_status_layout = QHBoxLayout(self.gp_unit_status)
        unit_status_layout.setSpacing(12)

        # 单位
        unit_status_layout.addWidget(QLabel("单位:"))
        self.grp_unit = QComboBox()
        self.grp_unit.setFixedWidth(120)
        self.grp_unit.addItems(["全部"])
        self.grp_unit.currentTextChanged.connect(self._on_unit_changed)
        unit_status_layout.addWidget(self.grp_unit)

        # 已读
        unit_status_layout.addWidget(QLabel("已读:"))
        self.combo_read = QComboBox()
        self.combo_read.setFixedWidth(120)
        self.combo_read.addItems(["全部", "已读", "未读"])
        self.combo_read.currentTextChanged.connect(self._on_read_changed)
        unit_status_layout.addWidget(self.combo_read)

        # 隔离区
        unit_status_layout.addWidget(QLabel("隔离区:"))
        self.grp_quar = QComboBox()
        self.grp_quar.setFixedWidth(120)
        self.grp_quar.addItems(["全部", "是", "否"])
        self.grp_quar.currentTextChanged.connect(self._on_quar_changed)
        unit_status_layout.addWidget(self.grp_quar)

        # 备注
        unit_status_layout.addWidget(QLabel("备注:"))
        self.grp_note = QComboBox()
        self.grp_note.setFixedWidth(120)
        self.grp_note.addItems(["全部", "有", "无"])
        self.grp_note.currentTextChanged.connect(self._on_note_changed)
        unit_status_layout.addWidget(self.grp_note)

        unit_status_layout.addStretch()
        current_layout.addWidget(self.gp_unit_status)

    def _on_keywords_changed(self, text):
        self._keywords = text
        self._apply_filter()

    def _on_include_zero_changed(self, state):
        self._include_zero = (state != 0)
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

    def _on_read_changed(self, text):
        self._read_filter = text
        self._apply_filter()

    def _on_quar_changed(self, text):
        self._quar_filter = text
        self._apply_filter()

    def _on_note_changed(self, text):
        self._has_note_filter = "all" if text == "全部" else "yes" if text == "有" else "no"
        self._apply_filter()

    def set_data(self, df):
        """设置数据并初始化"""
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

        # 加载已读来源
        if "data_id" in self.original_df.columns:
            try:
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

        # 生成已读来源显示列
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
        self.set_row_count(len(df))

        # 设置 KPI
        self.set_kpi_data([
            {"label": "负损", "value": f"{len(df)}条"},
            {"label": "金额", "value": "-¥0.0"},
            {"label": "涉及车间", "value": "3个"},
            {"label": "隔离", "value": "0条"},
        ])

        # 初始化筛选器
        self._initialize_filters()

        # 应用默认筛选
        self._apply_default_filter()

        self._initializing = False

    def _initialize_filters(self):
        """初始化所有筛选器"""
        df = self.original_df

        # 半成品重分类
        self._semi_class_col = "半成品重分类" if "半成品重分类" in df.columns else None
        unique_vals = []
        if self._semi_class_col:
            unique_vals = sorted(v for v in df["半成品重分类"].dropna().astype(str).str.strip().unique() if v)
        self._build_semi_checkboxes(unique_vals)
        self.gp_material_info.setVisible(True)

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
            unique_vals = [v for v in unique_vals if v not in self._get_cascade_exclude_mtd()]
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
        """获取排除物料类型"""
        return ["广宣", "礼品", "促销", "赠品", "样品", "营销"]

    def _build_semi_checkboxes(self, unique_vals):
        """构建半成品分类下拉列表"""
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
        """构建单位下拉列表"""
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
        """通用下拉刷新"""
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
        """默认视图自适应：先试「未读」，未读空但全量非空时回退「全部」(v43.177)。

        在负损看板上后果比替代料看板更严重：`_read_filter` 不只参与
        `_apply_filter` 的 mask 链，还被用于级联的一维。于是「未读 0 行」会同时：
            ① 表格空（0 行）
            ② 物料类型 / 车间 / 单位下拉全部塌缩成只剩「全部」

        必须在 `_initializing = False` 之后、首次 `_apply_filter` 之前调用：
        否则 source_model 尚未装载，算出的 0 是「还没数据」而非「筛不到」，
        会把每一次都误判成需回退。
        """
        self._read_filter = "未读"
        if self._read_col and hasattr(self, "combo_read"):
            self.combo_read.setCurrentText("未读")
        # 先按「未读」跑一次
        self._apply_filter()
        sm = getattr(self, "source_model", None)
        if sm is None or sm.rowCount() > 0:
            return                      # 有未读 → 保持默认「未读」，不动用户预期
        # 未读 0 行：确认全量确实非空才回退（两者皆空则保持未读，避免空表套空表）
        if self.original_df is not None and len(self.original_df) > 0:
            self._read_filter = "全部"
            if hasattr(self, "combo_read"):
                self.combo_read.setCurrentText("全部")
            else:
                self._apply_filter()

    def _apply_filter(self):
        """应用筛选逻辑"""
        if self._initializing:
            return

        df = self.original_df.copy()

        # 应用所有筛选条件（始终包含所有 mask）
        mask = (self._name_mask(df) & self._neg_loss_mask(df)
                & self._semi_class_mask(df)
                & self._quar_mask(df, self._quar_filter)
                & self._note_mask(df, self._has_note_filter)
                & self._color_mask(df)
                & self._read_mask(df, self._read_filter)
                & self._factory_mask(df, self._factory_filter)
                & self._mtd_mask(df)
                & self._workshop_mask(df, self._workshop_filter)
                & self._unit_mask(df))

        df = df[mask]

        self.source_model.setDataFrame(df)
        self.set_row_count(len(df))
        self._refresh_cascade_combos()

    def _other_conditions_mask(self, df, exclude):
        """构造「除 exclude 维度外、所有其他筛选条件」的与掩码。"""
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

    def _refresh_cascade_combos(self, changed='all'):
        """重算物料类型 / 车间两个下拉的选项（changed='mtd' 或 'workshop' 或 'all'）。"""
        if getattr(self, '_initializing', False):
            return
        df = getattr(self, 'original_df', None)
        if df is None or df.empty or not hasattr(self, 'source_model'):
            return

        # --- 物料类型：按「除自己外」的条件重算 ---
        sub_mtd = df[self._other_conditions_mask(df, exclude='mtd')]
        mtd_vals = sorted(
            v for v in sub_mtd[self._mtd_col].dropna().astype(str).str.strip().unique() if v
        ) if (self._mtd_col and self._mtd_col in sub_mtd.columns) else []
        mtd_vals = [v for v in mtd_vals if v not in self._CASCADE_EXCLUDE_MTD]
        self._replace_combo_items(self.combo_mtd, mtd_vals, self._mtd_filter,
                                  '_mtd_filter', '_on_mtd_changed')

        # --- 车间：按「除自己外」的条件重算 ---
        sub_ws = df[self._other_conditions_mask(df, exclude='workshop')]
        ws_vals = sorted(
            v for v in sub_ws[self._workshop_col].dropna().astype(str).str.strip().unique() if v
        ) if (self._workshop_col and self._workshop_col in sub_ws.columns) else []
        self._replace_combo_items(self.combo_workshop, ws_vals, self._workshop_filter,
                                  '_workshop_filter', '_on_workshop_changed')

        # --- 单位：同样纳入级联（v43.175；原 unit 被无视叠加进主 mask）---
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
        """全列关键字搜索：排除内部维护列(data_id/隔离区/_read 等)后，所有文本/对象列均参与匹配。"""
        _internal = {"data_id", "隔离区", "_read", "_quarantined"}
        cols = [c for c in df.columns if c not in _internal]
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

    def _color_mask(self, df):
        """颜色筛选掩码：空集合=全True；否则按 classify_row_color_keys 判断命中颜色集合。"""
        if not self.color_filters:
            return pd.Series(True, index=df.index)
        from gui_pyside6.dialogs.col_filter_ui import classify_row_color_keys
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

    def closeEvent(self, event):
        """关闭事件"""
        self.action_triggered.emit("close")
        event.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 创建负损看板
    shell = NegLossDashboard(None, None)
    shell.setWindowTitle("负损看板 DashboardShell 测试")
    shell.resize(1400, 800)
    shell.show()

    # 延时退出
    import time
    time.sleep(3)

    print("DashboardShell 负损看板测试正常")
    app.quit()
