# -*- coding: utf-8 -*-
"""
可折叠侧边栏筛选面板（含日期范围）
支持：工厂、车间、物料类型、替代料、偏差率范围、审核状态、备注为空、日期范围
支持展开/收起，节省界面空间
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QPushButton, QLabel, QDateEdit, QLineEdit, QScrollArea,
    QDoubleSpinBox, QListWidget, QListWidgetItem, QDialog, QCalendarWidget,
    QSizePolicy, QMenu
)
from PySide6.QtCore import Signal, Qt, QDate, QEvent
from PySide6.QtGui import QColor, QPixmap, QIcon
from datetime import datetime
import pandas as pd
import json
import os

from gui_pyside6.dialogs.material_presets_dialog import MaterialPresetsDialog


def _color_icon(rgb):
    """生成纯色小图标，用于筛选下拉里直观显示颜色标记"""
    pix = QPixmap(14, 14)
    pix.fill(QColor(*rgb))
    return QIcon(pix)


class FilterPanel(QWidget):
    filter_changed = Signal(dict)  # 筛选条件变化信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._data_min_date = None
        self._data_max_date = None
        self.setMaximumWidth(540)
        self.setMinimumWidth(540)
        self.setObjectName("filterPanel")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏（折叠按钮）
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(8, 8, 8, 8)
        self.collapse_btn = QPushButton("◀")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        title_label = QLabel("筛选条件")
        title_label.setObjectName("filterTitleLabel")
        title_bar.addWidget(self.collapse_btn)
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        main_layout.addLayout(title_bar)

        # 内容区域（可折叠）
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(12)

        # 分析参数（阈值调整属于分析阶段，修改后需重新分析生效）
        param_group = QGroupBox("分析参数")
        param_layout = QFormLayout(param_group)
        param_layout.setSpacing(8)
        param_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        param_layout.setLabelAlignment(Qt.AlignRight)
        self.dev_threshold_spin = QDoubleSpinBox()
        self.dev_threshold_spin.setRange(0.0, 50.0)
        self.dev_threshold_spin.setSingleStep(0.5)
        self.dev_threshold_spin.setValue(1.0)
        self.dev_threshold_spin.setSuffix("%")
        self.dev_threshold_spin.setToolTip("仅纳入偏差率绝对值 ≥ 此阈值的工单进入主表；调为 0% 可显示全部明细。修改后重新分析生效。")
        param_layout.addRow("偏差率纳入阈值:", self.dev_threshold_spin)
        # 分析日期范围（重新分析生效）：控制 do_analysis_v2 的 start_date/end_date
        # 分析日期：QDateEdit + 📅选日期按钮 + ✕清除按钮，规避 specialValueText 下键盘输入不可靠
        self.analysis_start_date_edit, sd_container = self._make_date_field(
            "分析起始日期（重新分析生效）。留空=从最早数据开始。修改后点「分析」生效。")
        self.analysis_end_date_edit, ed_container = self._make_date_field(
            "分析截止日期（重新分析生效）。留空=到最新数据为止。修改后点「分析」生效。")
        param_layout.addRow("分析起始日:", sd_container)
        param_layout.addRow("分析截止日:", ed_container)
        note_label = QLabel("提示：阈值与日期修改后需重新点「分析」生效")
        note_label.setStyleSheet("color: #888888; font-size: 10px;")
        param_layout.addRow("", note_label)
        content_layout.addWidget(param_group)

        # 基础信息
        basic_group = QGroupBox("基础信息")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(8)
        basic_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        basic_layout.setLabelAlignment(Qt.AlignRight)
        self.factory_combo = QComboBox()
        self.factory_combo.addItem("全部")
        self.workshop_combo = QComboBox()
        self.workshop_combo.addItem("全部")
        self.process_order_edit = QLineEdit()
        self.process_order_edit.setPlaceholderText("输入流程订单号搜索")
        self.process_order_edit.setMaximumWidth(240)
        basic_layout.addRow("工厂:", self.factory_combo)
        basic_layout.addRow("车间:", self.workshop_combo)
        basic_layout.addRow("流程订单:", self.process_order_edit)
        content_layout.addWidget(basic_group)

        # 物料属性
        material_group = QGroupBox("物料属性")
        material_layout = QFormLayout(material_group)
        material_layout.setSpacing(8)
        material_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        material_layout.setLabelAlignment(Qt.AlignRight)
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部")
        self.alt_combo = QComboBox()
        self.alt_combo.addItems(["全部", "是", "否"])
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItem("全部")
        self.material_code_edit = QLineEdit()
        self.material_code_edit.setPlaceholderText("输入编码，逗号分隔多选")
        self.material_code_edit.setMaximumWidth(240)
        # 物料名称：使用可编辑下拉框，内容完全由用户通过 config/material_name_presets.json 自定义
        self.material_name_edit = QComboBox()
        self.material_name_edit.setEditable(True)
        self.material_name_edit.addItem("全部")
        self.material_name_edit.setCurrentText("")
        self.material_name_edit.lineEdit().setPlaceholderText("输入名称(逗号分隔多选)")
        self.material_name_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.material_name_edit.setMinimumWidth(180)
        self.material_name_edit.setMaximumWidth(240)
        self.material_name_edit.setInsertPolicy(QComboBox.NoInsert)
        # 下拉项由用户自定义维护（不自动灌入数据名称，也不自动收录手输值），见 _load_material_presets
        self._material_presets = self._load_material_presets()
        # 编辑预设按钮：直接打开 JSON 文件让用户自己维护下拉项
        self.edit_presets_btn = QPushButton("编辑")
        self.edit_presets_btn.setToolTip("打开 config/material_name_presets.json 自定义下拉项")
        self.edit_presets_btn.setMaximumWidth(50)
        self.edit_presets_btn.clicked.connect(self._open_material_presets_editor)
        material_name_row = QHBoxLayout()
        material_name_row.addWidget(self.material_name_edit, 1)
        material_name_row.addWidget(self.edit_presets_btn)
        material_layout.addRow("物料类型:", self.category_combo)
        material_layout.addRow("替代料:", self.alt_combo)
        material_layout.addRow("订单类型:", self.order_type_combo)
        material_layout.addRow("物料编码:", self.material_code_edit)
        material_layout.addRow("物料名称:", material_name_row)
        content_layout.addWidget(material_group)

        # 偏差与审核
        dev_group = QGroupBox("偏差与审核")
        dev_layout = QFormLayout(dev_group)
        dev_layout.setSpacing(8)
        dev_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        dev_layout.setLabelAlignment(Qt.AlignRight)
        self.dev_rate_combo = QComboBox()
        self.dev_rate_combo.addItems(["全部", "绝对值>=10%", ">10%", ">20%", ">30%", "<-10%", "<-20%", "<-30%"])
        self.audit_status_combo = QComboBox()
        self.audit_status_combo.addItems(["全部", "合格", "需关注", "需改进", "需补备注"])
        self.remark_empty_combo = QComboBox()
        self.remark_empty_combo.addItems(["全部", "是", "否"])
        self.read_status_combo = QComboBox()
        self.read_status_combo.addItems(["全部", "已读", "未读"])
        # 默认只看「未读」，与替代料看板一致，减少已读记录干扰；
        # 此时信号尚未连接（连接在后面），不会触发筛选，加载数据后由 _emit_filter 应用。
        self.read_status_combo.setCurrentIndex(2)
        self.remark_source_combo = QComboBox()
        self.remark_source_combo.addItems(["全部", "AI审核", "人工填写"])
        self.zero_qty_combo = QComboBox()
        self.zero_qty_combo.addItems(["全部", "定额为0", "实际为0", "定额/实际为0", "定额/实际非0"])
        self.remark_search_edit = QLineEdit()
        self.remark_search_edit.setPlaceholderText("输入备注关键词，逗号分隔多选")
        self.remark_search_edit.setMaximumWidth(240)
        self.remark_not_edit = QLineEdit()
        self.remark_not_edit.setPlaceholderText("排除包含这些关键词的备注，逗号分隔")
        self.remark_not_edit.setMaximumWidth(240)
        dev_layout.addRow("偏差率范围:", self.dev_rate_combo)
        self.dev_qty_combo = QComboBox()
        self.dev_qty_combo.addItems(["全部", "大于0", "等于0", "小于0"])
        dev_layout.addRow("偏差数量:", self.dev_qty_combo)
        # 替代料/非耗用筛查：纯数值检测（实际=0 且 定额>0），与已有"是否替代料"列无关
        self.substitute_combo = QComboBox()
        self.substitute_combo.addItems(["全部", "疑似替代料（实际0·定额>0）"])
        self.substitute_combo.setToolTip("实际耗用为 0、但定额大于 0 的行——多为替代料/未耗用，偏差率恒为 -100%。这是 ZPP011 重点排查对象。")
        dev_layout.addRow("替代料筛查:", self.substitute_combo)
        dev_layout.addRow("审核结果:", self.audit_status_combo)
        dev_layout.addRow("备注来源:", self.remark_source_combo)
        dev_layout.addRow("备注搜索:", self.remark_search_edit)
        dev_layout.addRow("备注不为:", self.remark_not_edit)
        dev_layout.addRow("备注为空:", self.remark_empty_combo)
        dev_layout.addRow("零值筛选:", self.zero_qty_combo)
        dev_layout.addRow("已读/未读:", self.read_status_combo)
        # 颜色标记筛选（与表格行背景色对应）
        self.color_combo = QComboBox()
        self.color_combo.addItem("全部")
        self.color_combo.addItem("审核后变更（浅红）")
        self.color_combo.addItem("隔离区（浅黄）")
        self.color_combo.addItem("无标记（空白）")
        self.color_combo.addItem("替代料/非耗用（浅蓝）")
        self.color_combo.setItemIcon(1, _color_icon((255, 205, 205)))
        self.color_combo.setItemIcon(2, _color_icon((255, 248, 200)))
        self.color_combo.setItemIcon(3, _color_icon((235, 235, 235)))
        self.color_combo.setItemIcon(4, _color_icon((205, 230, 255)))
        dev_layout.addRow("颜色标记:", self.color_combo)
        content_layout.addWidget(dev_group)

        # 日期范围
        date_group = QGroupBox("日期范围")
        date_layout = QFormLayout(date_group)
        date_layout.setSpacing(8)
        date_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        date_layout.setLabelAlignment(Qt.AlignRight)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setSpecialValueText("未选择")
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.start_date_edit.setEnabled(True)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setSpecialValueText("未选择")
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setEnabled(True)
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

        # 用 QScrollArea 包裹内容区，窗口矮时可滚动
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidget(self.content_widget)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QScrollArea.NoFrame)
        main_layout.addWidget(self._scroll_area)

        # 连接实时筛选信号（非日期）
        self.factory_combo.currentIndexChanged.connect(self._emit_filter)
        self.workshop_combo.currentIndexChanged.connect(self._emit_filter)
        self.process_order_edit.textChanged.connect(self._emit_filter)
        self.process_order_edit.editingFinished.connect(self._emit_filter)
        self.process_order_edit.returnPressed.connect(self._emit_filter)
        self.category_combo.currentIndexChanged.connect(self._emit_filter)
        self.alt_combo.currentIndexChanged.connect(self._emit_filter)
        self.dev_rate_combo.currentIndexChanged.connect(self._emit_filter)
        self.dev_qty_combo.currentIndexChanged.connect(self._emit_filter)
        self.substitute_combo.currentIndexChanged.connect(self._emit_filter)
        self.audit_status_combo.currentIndexChanged.connect(self._emit_filter)
        self.remark_empty_combo.currentIndexChanged.connect(self._emit_filter)
        self.order_type_combo.currentIndexChanged.connect(self._emit_filter)
        self.read_status_combo.currentIndexChanged.connect(self._emit_filter)
        self.color_combo.currentIndexChanged.connect(self._emit_filter)
        self.material_code_edit.textChanged.connect(self._emit_filter)
        self.material_code_edit.editingFinished.connect(self._emit_filter)
        self.material_code_edit.returnPressed.connect(self._emit_filter)
        self.remark_source_combo.currentIndexChanged.connect(self._emit_filter)
        self.material_name_edit.currentTextChanged.connect(self._emit_filter)
        self.material_name_edit.lineEdit().editingFinished.connect(self._emit_filter)
        self.material_name_edit.lineEdit().returnPressed.connect(self._emit_filter)
        self.zero_qty_combo.currentIndexChanged.connect(self._emit_filter)
        self.remark_search_edit.textChanged.connect(self._emit_filter)
        self.remark_search_edit.editingFinished.connect(self._emit_filter)
        self.remark_search_edit.returnPressed.connect(self._emit_filter)
        self.remark_not_edit.textChanged.connect(self._emit_filter)
        self.remark_not_edit.editingFinished.connect(self._emit_filter)
        self.remark_not_edit.returnPressed.connect(self._emit_filter)

        self._data = None
        self._col_map = {}
        self._date_filters = {}
        # 记录用户已选的日期（即便数据刷新也不清空），保证日期筛选可用
        self._user_start_date = None
        self._user_end_date = None

        # 滚轮保护：在筛选面板内滚动滚轮时，不要误改筛选条件
        for _w in (self.dev_threshold_spin, self.factory_combo, self.workshop_combo,
                   self.category_combo, self.alt_combo, self.order_type_combo,
                   self.dev_rate_combo, self.dev_qty_combo, self.audit_status_combo, self.remark_empty_combo,
                   self.read_status_combo, self.remark_source_combo, self.zero_qty_combo,
                   self.color_combo, self.substitute_combo, self.start_date_edit, self.end_date_edit,
                   self.analysis_start_date_edit, self.analysis_end_date_edit,
                   self.material_name_edit):
            _w.installEventFilter(self)

        # 输入框右键菜单改为中文（Qt 默认是英文 Undo/Redo/Cut/Copy/Paste/Delete/Select All）
        self._setup_chinese_context_menus()

    # ------------------------------------------------------------------ #
    # 中文右键菜单（替换 QLineEdit / QComboBox lineEdit 的英文默认菜单）
    # ------------------------------------------------------------------ #
    def _setup_chinese_context_menus(self):
        def attach(line_edit):
            if line_edit is None:
                return
            line_edit.setContextMenuPolicy(Qt.CustomContextMenu)
            line_edit.customContextMenuRequested.connect(
                lambda pos, le=line_edit: self._show_chinese_edit_menu(pos, le)
            )

        for child in self.findChildren(QLineEdit):
            attach(child)
        for combo in self.findChildren(QComboBox):
            if combo.isEditable() and combo.lineEdit() is not None:
                attach(combo.lineEdit())

    def _show_chinese_edit_menu(self, pos, line_edit):
        menu = QMenu(self)
        undo = menu.addAction("撤销")
        redo = menu.addAction("重做")
        menu.addSeparator()
        cut = menu.addAction("剪切")
        copy = menu.addAction("复制")
        paste = menu.addAction("粘贴")
        delete = menu.addAction("删除")
        menu.addSeparator()
        select_all = menu.addAction("全选")

        undo.triggered.connect(line_edit.undo)
        redo.triggered.connect(line_edit.redo)
        cut.triggered.connect(line_edit.cut)
        copy.triggered.connect(line_edit.copy)
        paste.triggered.connect(line_edit.paste)
        delete.triggered.connect(line_edit.del_)
        select_all.triggered.connect(line_edit.selectAll)

        # 禁用不可用的动作（与原生行为一致）
        undo.setEnabled(line_edit.isUndoAvailable())
        redo.setEnabled(line_edit.isRedoAvailable())
        cut.setEnabled(line_edit.hasSelectedText())
        copy.setEnabled(line_edit.hasSelectedText())
        delete.setEnabled(line_edit.hasSelectedText())

        menu.exec_(line_edit.mapToGlobal(pos))

    # ------------------------------------------------------------------ #
    # 事件过滤（滚轮保护）
    # ------------------------------------------------------------------ #
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if isinstance(obj, (QComboBox, QDoubleSpinBox, QDateEdit)):
                return True
        elif event.type() == QEvent.FocusIn:
            if isinstance(obj, QDateEdit):
                obj.selectAll()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------ #
    # 折叠/展开
    # ------------------------------------------------------------------ #
    def _make_date_field(self, tooltip):
        # 构建带「选择日期 / 清除」按钮的日期输入控件，绕开 specialValueText 下键盘输入不可靠的问题
        w = QDateEdit()
        w.setCalendarPopup(False)  # 关闭 QDateEdit 自带的下拉箭头，避免与自定义按钮重复
        w.setButtonSymbols(QDateEdit.NoButtons)  # 同时隐藏上下箭头，只作为纯文本显示框
        w.setDisplayFormat("yyyy-MM-dd")
        w.setSpecialValueText("未选择")
        w.setMinimumDate(QDate(2000, 1, 1))
        w.setMaximumDate(QDate(2099, 12, 31))
        w.setDate(w.minimumDate())
        w.setReadOnly(False)
        w.setInputMethodHints(Qt.ImhPreferLatin)  # 编辑时优先拉丁输入，避免中文 IME 吞数字
        w.setToolTip(tooltip)
        cal_btn = QPushButton("选择")
        cal_btn.setFixedWidth(38)
        cal_btn.setToolTip("选择日期")
        cal_btn.clicked.connect(lambda: self._popup_calendar(w))
        clear_btn = QPushButton("清除")
        clear_btn.setFixedWidth(38)
        clear_btn.setToolTip("清除（不限制日期）")
        clear_btn.clicked.connect(lambda: w.setDate(w.minimumDate()))
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)
        h.addWidget(w, 1)
        h.addWidget(cal_btn)
        h.addWidget(clear_btn)
        container = QWidget()
        container.setLayout(h)
        return w, container

    def _popup_calendar(self, target_edit):
        # 自定义日历弹窗：点击 📅 时弹出，避免某些 PySide6 版本 QDateEdit.showPopup 不可用的问题
        dlg = QDialog(self)
        dlg.setWindowTitle("选择日期")
        dlg.setModal(True)
        v = QVBoxLayout(dlg)
        cal = QCalendarWidget()
        cur = target_edit.date()
        cal.setSelectedDate(cur if cur > target_edit.minimumDate() else QDate.currentDate())
        cal.setMinimumDate(target_edit.minimumDate())
        cal.setMaximumDate(target_edit.maximumDate())
        v.addWidget(cal)
        btn = QPushButton("确定")
        v.addWidget(btn)
        btn.clicked.connect(lambda: (target_edit.setDate(cal.selectedDate()), dlg.accept()))
        dlg.exec()

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
        self._col_map['审核结果'] = self._find_column(['审核结果', 'audit_result'])
        self._col_map['备注来源'] = self._find_column(['备注来源', '备注来源'])
        self._col_map['备注原因'] = self._find_column(['备注原因', '备注'])
        self._col_map['偏差率(%)'] = self._find_column(['偏差率(%)', '偏差率'])
        self._col_map['日期'] = self._find_column(['订单日期', '订单开始日期', '日期'])
        self._col_map['订单类型'] = self._find_column(['订单类型', 'order_type'])
        self._col_map['物料编码'] = self._find_column(['物料号', '物料编码', 'code', '组件物料号'])
        self._col_map['流程订单'] = self._find_column(['流程订单', 'process_order'])
        self._col_map['物料名称'] = self._find_column(['物料名称', '物料描述', 'material_name', '组件物料描述'])

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

        # 更新动态下拉前屏蔽信号，避免触发中间态筛选条件把表格刷空
        for _c in (self.factory_combo, self.workshop_combo, self.category_combo, self.order_type_combo,
                   self.material_name_edit):
            _c.blockSignals(True)
        self._update_combo(self.factory_combo, self._col_map.get('工厂'))
        self._update_combo(self.workshop_combo, self._col_map.get('车间'))
        self._update_combo(self.category_combo, self._col_map.get('物料类型'))
        self._update_combo(self.order_type_combo, self._col_map.get('订单类型'))
        self._update_material_name_combo()
        for _c in (self.factory_combo, self.workshop_combo, self.category_combo, self.order_type_combo,
                   self.material_name_edit):
            _c.blockSignals(False)

        # 重置日期为数据范围
        self._reset_date_range()

        # 数据/选项更新后统一发射一次最终筛选条件，确保 proxy 只拿到最终状态
        self._emit_filter()

        # 关键修复：数据刷新（标记已读/改备注/切工厂等会触发 set_data）时，
        # 不能清空用户已设置的日期区间，否则日期筛选会被悄悄丢弃、"用不了"。
        # 仅当用户此前选过日期且本次数据非空时，恢复其选择并保持生效。
        if self._user_start_date is not None and df is not None and not df.empty:
            self.start_date_edit.setDate(self._user_start_date)
            self.end_date_edit.setDate(
                self._user_end_date if self._user_end_date is not None else self._user_start_date)
            self._date_filters = self._compute_date_filters()

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

    def _preset_path(self):
        """用户自定义物料名称下拉项配置文件路径（项目 config 目录）"""
        return os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "material_name_presets.json"))

    def _load_material_presets(self):
        """读取用户自定义的物料名称下拉项；文件不存在或损坏则返回空列表。"""
        try:
            with open(self._preset_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except Exception:
            pass
        return []

    def _save_material_presets(self):
        """将用户自定义物料名称下拉项写回配置文件。"""
        try:
            p = self._preset_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self._material_presets, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _remember_material_preset(self):
        """用户在框里手输并确认一个值时，自动收进下拉项（永久保留，方便下次直接选）。"""
        text = self.material_name_edit.currentText().strip()
        # 只收藏单个值：含逗号分隔的不收（那是一次性多选），已存在的跳过
        if not text or (',' in text) or ('，' in text) or (text in self._material_presets):
            return
        self._material_presets.append(text)
        self._save_material_presets()
        # 刷新下拉项，保留当前输入文本（屏蔽信号避免额外触发筛选）
        self.material_name_edit.blockSignals(True)
        self._update_material_name_combo()
        self.material_name_edit.blockSignals(False)

    def _update_material_name_combo(self):
        """物料名称下拉项来自用户自定义预设，不自动灌入数据中的名称（避免下拉过长难找）。"""
        current_text = self.material_name_edit.currentText()
        self.material_name_edit.clear()
        self.material_name_edit.addItem("全部")
        for name in self._material_presets:
            self.material_name_edit.addItem(name)
        self.material_name_edit.setCurrentText(current_text)

    def _open_material_presets_editor(self):
        """弹窗管理物料名称下拉预设，无需手写 JSON。"""
        dialog = MaterialPresetsDialog(
            self,
            presets=self._material_presets,
            preset_path=self._preset_path(),
        )
        if dialog.exec() == QDialog.Accepted:
            self._material_presets = dialog.get_presets()
            self._update_material_name_combo()

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

        # 确保日期控件始终可用（防止被外部或样式意外禁用）
        self.start_date_edit.setEnabled(True)
        self.end_date_edit.setEnabled(True)

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
        # 物料名称模糊搜索（逗号分隔多选，OR匹配）
        material_name_text = self.material_name_edit.currentText().strip()
        if material_name_text:
            filters['_material_names'] = material_name_text
        if self.dev_rate_combo.currentText() != "全部":
            rate_range = self.dev_rate_combo.currentText()
            if rate_range == "绝对值>=10%":
                filters['_dev_rate_abs_ge_10'] = True
            else:
                filters['_dev_rate_range'] = rate_range
        status_col = self._col_map.get('审核结果')
        if status_col and self.audit_status_combo.currentText() != "全部":
            filters[status_col] = self.audit_status_combo.currentText()
        remark_source_col = self._col_map.get('备注来源')
        if remark_source_col and self.remark_source_combo.currentText() != "全部":
            filters[remark_source_col] = self.remark_source_combo.currentText()
        remark_col = self._col_map.get('备注原因')
        if remark_col and self.remark_empty_combo.currentText() != "全部":
            filters['_remark_empty'] = (self.remark_empty_combo.currentText() == '是')
        if self.read_status_combo.currentText() != "全部":
            filters['_read_status'] = self.read_status_combo.currentText()
        if self.zero_qty_combo.currentText() != "全部":
            filters['_zero_qty'] = self.zero_qty_combo.currentText()
        # 偏差数量筛选：大于0 / 等于0 / 小于0
        dev_qty_sel = self.dev_qty_combo.currentText()
        if dev_qty_sel == "大于0":
            filters['_dev_qty_sign'] = 'gt0'
        elif dev_qty_sel == "等于0":
            filters['_dev_qty_sign'] = 'eq0'
        elif dev_qty_sel == "小于0":
            filters['_dev_qty_sign'] = 'lt0'
        # 替代料筛查（纯数值：实际=0 且 定额>0）
        if self.substitute_combo.currentText() != "全部":
            filters['_substitute_only'] = True
        # 颜色标记筛选：与表格行背景色对应
        color_sel = self.color_combo.currentText()
        if color_sel == "审核后变更（浅红）":
            filters['_changed_only'] = True
        elif color_sel == "隔离区（浅黄）":
            filters['_quarantined_only'] = True
        elif color_sel == "无标记（空白）":
            filters['_plain_only'] = True
        elif color_sel == "替代料/非耗用（浅蓝）":
            filters['_substitute_only'] = True
        # 备注关键词搜索（逗号分隔多选，OR匹配）
        remark_search_text = self.remark_search_edit.text().strip()
        if remark_search_text:
            filters['_remark_search'] = remark_search_text
        # 备注不为（排除包含这些关键词的备注，逗号分隔多选，OR匹配）
        remark_not_text = self.remark_not_edit.text().strip()
        if remark_not_text:
            filters['_remark_not'] = remark_not_text
        if self._date_filters:
            filters.update(self._date_filters)
        return filters

    # ------------------------------------------------------------------ #
    # 内部槽
    # ------------------------------------------------------------------ #
    def _emit_filter(self):
        filters = self.get_filters()
        self.filter_changed.emit(filters)

    def _compute_date_filters(self):
        """根据当前日期控件值计算日期筛选条件字典（可能为空）。
        同时记录用户选择，供 set_data 数据刷新后保留日期区间。"""
        start = self.start_date_edit.date()
        end = self.end_date_edit.date()
        self._user_start_date = start
        self._user_end_date = end
        date_filters = {}
        # 仅当用户调整了日期（与数据范围不同）才加入筛选，避免无意义全量过滤
        if self._data_min_date is not None:
            if (start.year(), start.month(), start.day()) != (
                    self._data_min_date.year, self._data_min_date.month, self._data_min_date.day):
                date_filters['_date_start'] = start.toString("yyyy-MM-dd")
        if self._data_max_date is not None:
            if (end.year(), end.month(), end.day()) != (
                    self._data_max_date.year, self._data_max_date.month, self._data_max_date.day):
                date_filters['_date_end'] = end.toString("yyyy-MM-dd")
        return date_filters

    def _emit_date_filter(self):
        """日期筛选：用户点击"筛选"按钮时触发"""
        self._date_filters = self._compute_date_filters()
        self._emit_filter()

    def set_color_filter(self, mode: str):
        """程序控制颜色标记筛选（与统计卡片联动）。mode: 'all'/'changed'/'quarantine'/'plain'"""
        mapping = {
            'all': 0,
            'changed': 1,
            'quarantine': 2,
            'plain': 3,
            'substitute': 4,
        }
        idx = mapping.get(mode, 0)
        if self.color_combo.currentIndex() != idx:
            self.color_combo.setCurrentIndex(idx)
        else:
            # 索引相同也要发一次，确保 proxy 与 UI 一致
            self._emit_filter()

    def set_read_status_filter(self, status: str):
        """程序控制已读/未读筛选（与统计卡片联动）。status: '全部'/'已读'/'未读'"""
        mapping = {"全部": 0, "已读": 1, "未读": 2}
        idx = mapping.get(status, 0)
        if self.read_status_combo.currentIndex() != idx:
            self.read_status_combo.setCurrentIndex(idx)
        else:
            self._emit_filter()

    def reset_filters(self):
        self.factory_combo.setCurrentIndex(0)
        self.workshop_combo.setCurrentIndex(0)
        self.process_order_edit.clear()
        self.category_combo.setCurrentIndex(0)
        self.alt_combo.setCurrentIndex(0)
        self.dev_rate_combo.setCurrentIndex(0)
        self.dev_qty_combo.setCurrentIndex(0)
        self.substitute_combo.setCurrentIndex(0)
        self.audit_status_combo.setCurrentIndex(0)
        self.remark_empty_combo.setCurrentIndex(0)
        self.order_type_combo.setCurrentIndex(0)
        self.read_status_combo.setCurrentIndex(0)
        self.remark_source_combo.setCurrentIndex(0)
        self.zero_qty_combo.setCurrentIndex(0)
        self.color_combo.setCurrentIndex(0)
        self.material_code_edit.clear()
        self.material_name_edit.setCurrentIndex(0)
        self.remark_search_edit.clear()
        self.remark_not_edit.clear()
        # 重置日期为数据最小/最大日期
        self._user_start_date = None
        self._user_end_date = None
        self._reset_date_range()
        self._emit_filter()
