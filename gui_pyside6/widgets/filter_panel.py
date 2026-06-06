# -*- coding: utf-8 -*-
"""
可折叠侧边栏筛选面板（含日期范围）
支持：工厂、车间、物料类型、替代料、偏差率范围、审核状态、备注为空、日期范围
支持展开/收起，节省界面空间
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QPushButton, QLabel, QDateEdit, QLineEdit
)
from PySide6.QtCore import Signal, Qt, QDate
from datetime import datetime
import pandas as pd


class FilterPanel(QWidget):
    filter_changed = Signal(dict)  # 筛选条件变化信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._data_min_date = None
        self._data_max_date = None
        self.setMaximumWidth(280)
        self.setMinimumWidth(32)
        self.setStyleSheet("background-color: #f8f9fa; border-right: 1px solid #dee2e6;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏（折叠按钮）
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(8, 8, 8, 8)
        self.collapse_btn = QPushButton("◀")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        title_label = QLabel("筛选条件")
        title_label.setStyleSheet("font-weight: bold;")
        title_bar.addWidget(self.collapse_btn)
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        main_layout.addLayout(title_bar)

        # 内容区域（可折叠）
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(12)

        # 基础信息
        basic_group = QGroupBox("基础信息")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(8)
        self.factory_combo = QComboBox()
        self.factory_combo.addItem("全部")
        self.workshop_combo = QComboBox()
        self.workshop_combo.addItem("全部")
        self.process_order_edit = QLineEdit()
        self.process_order_edit.setPlaceholderText("输入流程订单号搜索")
        basic_layout.addRow("工厂:", self.factory_combo)
        basic_layout.addRow("车间:", self.workshop_combo)
        basic_layout.addRow("流程订单:", self.process_order_edit)
        content_layout.addWidget(basic_group)

        # 物料属性
        material_group = QGroupBox("物料属性")
        material_layout = QFormLayout(material_group)
        material_layout.setSpacing(8)
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部")
        self.alt_combo = QComboBox()
        self.alt_combo.addItems(["全部", "是", "否"])
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItem("全部")
        self.material_code_edit = QLineEdit()
        self.material_code_edit.setPlaceholderText("输入编码，逗号分隔多选")
        material_layout.addRow("物料类型:", self.category_combo)
        material_layout.addRow("替代料:", self.alt_combo)
        material_layout.addRow("订单类型:", self.order_type_combo)
        material_layout.addRow("物料编码:", self.material_code_edit)
        content_layout.addWidget(material_group)

        # 偏差与审核
        dev_group = QGroupBox("偏差与审核")
        dev_layout = QFormLayout(dev_group)
        dev_layout.setSpacing(8)
        self.dev_rate_combo = QComboBox()
        self.dev_rate_combo.addItems(["全部", "绝对值>=10%", ">10%", ">20%", ">30%", "<-10%", "<-20%", "<-30%"])
        self.audit_status_combo = QComboBox()
        self.audit_status_combo.addItems(["全部", "未审核", "已审核", "需补备注", "已备注"])
        self.remark_empty_combo = QComboBox()
        self.remark_empty_combo.addItems(["全部", "是", "否"])
        self.read_status_combo = QComboBox()
        self.read_status_combo.addItems(["全部", "已读", "未读"])
        dev_layout.addRow("偏差率范围:", self.dev_rate_combo)
        dev_layout.addRow("审核状态:", self.audit_status_combo)
        dev_layout.addRow("备注为空:", self.remark_empty_combo)
        dev_layout.addRow("已读/未读:", self.read_status_combo)
        content_layout.addWidget(dev_group)

        # 日期范围
        date_group = QGroupBox("日期范围")
        date_layout = QFormLayout(date_group)
        date_layout.setSpacing(8)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setSpecialValueText("未选择")
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setSpecialValueText("未选择")
        self.end_date_edit.setDate(QDate.currentDate())
        date_layout.addRow("开始日期:", self.start_date_edit)
        date_layout.addRow("结束日期:", self.end_date_edit)
        self.date_filter_btn = QPushButton("筛选")
        self.date_filter_btn.clicked.connect(self._emit_date_filter)
        date_layout.addRow("", self.date_filter_btn)
        content_layout.addWidget(date_group)

        # 重置按钮
        reset_btn = QPushButton("重置筛选")
        reset_btn.clicked.connect(self.reset_filters)
        content_layout.addWidget(reset_btn, alignment=Qt.AlignCenter)

        content_layout.addStretch()
        main_layout.addWidget(self.content_widget)

        # 连接实时筛选信号（非日期）
        self.factory_combo.currentIndexChanged.connect(self._emit_filter)
        self.workshop_combo.currentIndexChanged.connect(self._emit_filter)
        self.process_order_edit.textChanged.connect(self._emit_filter)
        self.category_combo.currentIndexChanged.connect(self._emit_filter)
        self.alt_combo.currentIndexChanged.connect(self._emit_filter)
        self.dev_rate_combo.currentIndexChanged.connect(self._emit_filter)
        self.audit_status_combo.currentIndexChanged.connect(self._emit_filter)
        self.remark_empty_combo.currentIndexChanged.connect(self._emit_filter)
        self.order_type_combo.currentIndexChanged.connect(self._emit_filter)
        self.read_status_combo.currentIndexChanged.connect(self._emit_filter)
        self.material_code_edit.textChanged.connect(self._emit_filter)

        self._data = None
        self._col_map = {}
        self._date_filters = {}

    # ------------------------------------------------------------------ #
    # 折叠/展开
    # ------------------------------------------------------------------ #
    def _toggle_collapse(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.setMaximumWidth(280)
            self.content_widget.setVisible(True)
            self.collapse_btn.setText("◀")
        else:
            self.setMaximumWidth(32)
            self.content_widget.setVisible(False)
            self.collapse_btn.setText("▶")

    # ------------------------------------------------------------------ #
    # 公共属性（兼容旧代码）
    # ------------------------------------------------------------------ #
    @property
    def factory_cb(self):
        return self.factory_combo

    @property
    def workshop_cb(self):
        return self.workshop_combo

    @property
    def alt_cb(self):
        return self.alt_combo

    @property
    def dev_rate_cb(self):
        return self.dev_rate_combo

    @property
    def status_cb(self):
        return self.audit_status_combo

    @property
    def color_cb(self):
        return None

    @property
    def material_entry(self):
        return None

    @property
    def amount_min_entry(self):
        return None

    @property
    def amount_max_entry(self):
        return None

    # ------------------------------------------------------------------ #
    # 数据源更新
    # ------------------------------------------------------------------ #
    def set_data(self, df: pd.DataFrame):
        self._data = df
        self._col_map['工厂'] = self._find_column(['工厂', '工厂名称', 'plant'])
        self._col_map['车间'] = self._find_column(['车间', '生产管理员描述', 'workshop'])
        self._col_map['物料类型'] = self._find_column(['物料类型', '物料大类', 'material_category'])
        self._col_map['替代料'] = self._find_column(['是否替代料', '替代料', 'is_alt'])
        self._col_map['审核状态'] = self._find_column(['审核状态', 'audit_status'])
        self._col_map['备注原因'] = self._find_column(['备注原因', '备注'])
        self._col_map['偏差率(%)'] = self._find_column(['偏差率(%)', '偏差率'])
        self._col_map['日期'] = self._find_column(['订单日期', '订单开始日期', '日期'])
        self._col_map['订单类型'] = self._find_column(['订单类型', 'order_type'])
        self._col_map['物料编码'] = self._find_column(['物料号', '物料编码', 'code', '组件物料号'])
        self._col_map['流程订单'] = self._find_column(['流程订单', 'process_order'])

        # 记录数据中的最小/最大日期，用于重置
        self._data_min_date = None
        self._data_max_date = None
        date_col = self._col_map.get('日期')
        if date_col and df is not None and not df.empty:
            try:
                sr = pd.to_datetime(df[date_col], errors='coerce').dropna()
                if not sr.empty:
                    self._data_min_date = sr.min().date()
                    self._data_max_date = sr.max().date()
            except Exception:
                pass

        self._update_combo(self.factory_combo, self._col_map.get('工厂'))
        self._update_combo(self.workshop_combo, self._col_map.get('车间'))
        self._update_combo(self.category_combo, self._col_map.get('物料类型'))
        self._update_combo(self.order_type_combo, self._col_map.get('订单类型'))

        # 重置日期为数据范围
        self._reset_date_range()

    def update_options(self, df: pd.DataFrame):
        self.set_data(df)

    def _find_column(self, candidates):
        if self._data is None:
            return None
        for col in candidates:
            if col in self._data.columns:
                return col
        return None

    def _update_combo(self, combo, col_name):
        if col_name and self._data is not None:
            values = self._data[col_name].dropna().unique()
            values = sorted([str(v) for v in values if str(v) != ''])
            combo.clear()
            combo.addItem("全部")
            combo.addItems(values)
        else:
            combo.clear()
            combo.addItem("全部")

    def _reset_date_range(self):
        """将日期控件重置为数据的最小/最大日期"""
        if self._data_min_date:
            self.start_date_edit.setDate(QDate(
                self._data_min_date.year,
                self._data_min_date.month,
                self._data_min_date.day,
            ))
        else:
            self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))

        if self._data_max_date:
            self.end_date_edit.setDate(QDate(
                self._data_max_date.year,
                self._data_max_date.month,
                self._data_max_date.day,
            ))
        else:
            self.end_date_edit.setDate(QDate.currentDate())

        self._date_filters = {}

    # ------------------------------------------------------------------ #
    # 筛选条件获取
    # ------------------------------------------------------------------ #
    def get_filters(self):
        filters = {}
        factory_col = self._col_map.get('工厂')
        if factory_col and self.factory_combo.currentText() != "全部":
            filters[factory_col] = self.factory_combo.currentText()
        workshop_col = self._col_map.get('车间')
        if workshop_col and self.workshop_combo.currentText() != "全部":
            filters[workshop_col] = self.workshop_combo.currentText()
        process_order_col = self._col_map.get('流程订单')
        process_order_text = self.process_order_edit.text().strip()
        if process_order_col and process_order_text:
            filters['_process_order'] = process_order_text
        cat_col = self._col_map.get('物料类型')
        if cat_col and self.category_combo.currentText() != "全部":
            filters[cat_col] = self.category_combo.currentText()
        alt_col = self._col_map.get('替代料')
        if self.alt_combo.currentText() != "全部":
            filters['是否替代料'] = self.alt_combo.currentText()
        order_type_col = self._col_map.get('订单类型')
        if order_type_col and self.order_type_combo.currentText() != "全部":
            filters[order_type_col] = self.order_type_combo.currentText()
        material_code_text = self.material_code_edit.text().strip()
        if material_code_text:
            filters['_material_code'] = material_code_text
        if self.dev_rate_combo.currentText() != "全部":
            rate_range = self.dev_rate_combo.currentText()
            if rate_range == "绝对值>=10%":
                filters['_dev_rate_abs_ge_10'] = True
            else:
                filters['_dev_rate_range'] = rate_range
        status_col = self._col_map.get('审核状态')
        if status_col and self.audit_status_combo.currentText() != "全部":
            filters[status_col] = self.audit_status_combo.currentText()
        remark_col = self._col_map.get('备注原因')
        if remark_col and self.remark_empty_combo.currentText() != "全部":
            filters['_remark_empty'] = (self.remark_empty_combo.currentText() == '是')
        if self.read_status_combo.currentText() != "全部":
            filters['_read_status'] = self.read_status_combo.currentText()
        if self._date_filters:
            filters.update(self._date_filters)
        return filters

    # ------------------------------------------------------------------ #
    # 内部槽
    # ------------------------------------------------------------------ #
    def _emit_filter(self):
        filters = self.get_filters()
        self.filter_changed.emit(filters)

    def _emit_date_filter(self):
        """日期筛选：用户点击"筛选"按钮时触发"""
        self._date_filters = {}
        start = self.start_date_edit.date()
        end = self.end_date_edit.date()

        # 判断用户是否选择了有效日期（与最小值不同表示用户修改过）
        min_date = self.start_date_edit.minimumDate()
        if start != min_date:
            self._date_filters['_date_start'] = start.toString("yyyy-MM-dd")
        if end != min_date:
            self._date_filters['_date_end'] = end.toString("yyyy-MM-dd")

        self._emit_filter()

    def reset_filters(self):
        self.factory_combo.setCurrentIndex(0)
        self.workshop_combo.setCurrentIndex(0)
        self.process_order_edit.clear()
        self.category_combo.setCurrentIndex(0)
        self.alt_combo.setCurrentIndex(0)
        self.dev_rate_combo.setCurrentIndex(0)
        self.audit_status_combo.setCurrentIndex(0)
        self.remark_empty_combo.setCurrentIndex(0)
        self.order_type_combo.setCurrentIndex(0)
        self.read_status_combo.setCurrentIndex(0)
        self.material_code_edit.clear()
        # 重置日期为数据最小/最大日期
        self._reset_date_range()
        self._emit_filter()
