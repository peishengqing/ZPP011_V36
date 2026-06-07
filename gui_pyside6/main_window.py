# -*- coding: utf-8 -*-
"""
ZPP011 主窗口 (PySide6 迁移版)
布局：左侧控制面板 + 右侧表格+日志
功能：分析、AI审核、表格筛选排序、合计行、单位汇总、右键菜单、批量操作、替代料管理、导入导出等
"""
import sys
import os
from datetime import datetime
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QProgressBar, QTextEdit, QMessageBox, QFileDialog,
    QTableView, QHeaderView, QMenu, QDialog, QDialogButtonBox, QSplitter,
    QScrollArea, QComboBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QAction, QFont, QShortcut, QKeySequence

from gui_pyside6.widgets.filter_panel import FilterPanel

# 导入自定义模块
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.models.workers import AnalysisWorker, AIAuditWorker
from gui_pyside6.dialogs.batch_operations_dialog import (
    BatchChangeStatusDialog, BatchRemarkDialog, BatchExportDialog
)
from gui_pyside6.dialogs.unit_summary_dialog import UnitSummaryDialog
from gui_pyside6.dialogs.rule_config_dialog import RuleConfigDialog
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
from gui_pyside6.dialogs.history_compare_dialog import HistoryCompareDialog
from gui_pyside6.dialogs.import_wizard_dialog import ImportWizard
from gui_pyside6.dialogs.benefit_report_dialog import BenefitReportDialog
from gui_pyside6.dialogs.health_check_dialog import HealthCheckDialog
from core.rule_engine import RuleEngine
from core.ai_client import AIClient
from core.alert_monitor import AlertMonitor
from domain.alt_material.alt_manager import load_alt_pairs, save_alt_pairs, DEFAULT_ALT_PAIRS
from core.config_manager import ConfigManager
from analysis.analyzer import do_analysis_v2

# 导入已读/未读状态管理模块
from core.fingerprint import calc_fingerprint
from core.read_status import load_read_status, record_deviation_change
from core.change_detector import detect_changes, build_snapshot


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZPP011 生产偏差分析器 (PySide6 迁移版)")
        self.resize(1200, 800)
        # 启动最大化，显示更多行
        self.showMaximized()

        # 状态变量
        self.audit_data = None
        self.source_model = None
        self.proxy_model = None
        self.current_input_file = None
        self.analysis_output_path = None
        self.alt_pairs = load_alt_pairs()
        self.config_manager = ConfigManager()
        self.rule_engine = RuleEngine()
        self.ai_client = AIClient()
        self.analysis_worker = None
        self.ai_worker = None
        self._analysis_params = {}  # 缓存分析参数，用于导出完整Excel

        # UI 搭建
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_connections()
        self._refresh_alt_view()
        # 实时预警监控（默认阈值10%，间隔60秒）
        self.alert_monitor = AlertMonitor(lambda: self.audit_data, threshold=10, interval=60)
        self.alert_monitor.alert_triggered.connect(self._on_alert)
        self.alert_monitor.start()
        
        # 全局快捷键
        QShortcut(QKeySequence("F5"), self).activated.connect(self._start_analysis)
        QShortcut(QKeySequence("F6"), self).activated.connect(self._export_current_table)
        QShortcut(QKeySequence("F7"), self).activated.connect(self._show_benefit_report)
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            lambda: self._batch_mark_selected_read(1)
        )
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._copy_previous_remark)

        # 多列联动排序状态
        self.sort_columns = []  # [(列索引, 升序标志), ...]
        
        self.statusBar().showMessage("就绪")

    # ------------------- UI 布局 -------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== 自定义标题栏（浅蓝色） ==========
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #42a5f5; border-bottom: 2px solid #1976d2;")  # 改为更浅的蓝色
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 0, 16, 0)  # 左边距改到4，让制作人更靠左

        # 1. 制作人信息（左边，往前移）
        maker_label = QLabel("制作人：裴盛清")
        maker_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 13px; font-weight: bold; padding: 2px 8px; background-color: rgba(255, 255, 255, 0.15); border-radius: 3px;")
        
        # 2. 图标
        icon_label = QLabel("🏭")
        icon_label.setStyleSheet("font-size: 20px;")
        
        # 3. 标题
        title_label = QLabel("云南达利ZPP011生产偏差分析器 v42.0")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")

        header_layout.addWidget(maker_label)  # 制作人放最左边
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addWidget(header)
        # 加一点间距，让表格不贴着标题栏
        spacer = QWidget()
        spacer.setFixedHeight(5)
        main_layout.addWidget(spacer)

        # ========== 主体区域 ==========
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(4, 4, 4, 4)

        # ========== 左侧面板 ==========
        left_panel = QWidget()
        left_panel.setFixedWidth(360)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(6)

        # 1. 文件选择
        file_group = QGroupBox("📁 文件选择")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(4)

        # 输入文件 — 横排
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("输入:"))
        self.input_file_edit = QLineEdit()
        self.input_file_edit.setReadOnly(True)
        row1.addWidget(self.input_file_edit, 1)
        browse_input_btn = QPushButton("浏览")
        browse_input_btn.clicked.connect(self._select_input_file)
        row1.addWidget(browse_input_btn)
        file_layout.addLayout(row1)

        # 输出目录 — 横排
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("输出:"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        row2.addWidget(self.output_dir_edit, 1)
        browse_output_btn = QPushButton("浏览")
        browse_output_btn.clicked.connect(self._select_output_dir)
        row2.addWidget(browse_output_btn)
        file_layout.addLayout(row2)

        left_layout.addWidget(file_group)

        # 2. 日期范围
        filter_group = QGroupBox("🔍 筛选选项（可选）")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(4)

        # 日期 — 横排一行
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("开始:"))
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("例：2026-04-01")
        date_row.addWidget(self.start_date_edit, 1)
        date_row.addWidget(QLabel("结束:"))
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("例：2026-04-30")
        date_row.addWidget(self.end_date_edit, 1)
        filter_layout.addLayout(date_row)

        # 物料搜索
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("物料:"))
        self.material_search_edit = QLineEdit()
        self.material_search_edit.setPlaceholderText("编码/名称")
        search_row.addWidget(self.material_search_edit, 1)
        filter_layout.addLayout(search_row)

        left_layout.addWidget(filter_group)

        # 4. 替代料配对（升级版）
        alt_group = QGroupBox("替代料配对")
        alt_layout = QVBoxLayout(alt_group)
        self.alt_count_label = QLabel("共 0 对")
        alt_layout.addWidget(self.alt_count_label)
        self.alt_table = QTableWidget()
        self.alt_table.setColumnCount(3)
        self.alt_table.setHorizontalHeaderLabels(["物料A", " ", "物料B"])
        self.alt_table.horizontalHeader().setStretchLastSection(True)
        self.alt_table.verticalHeader().setVisible(False)
        self.alt_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.alt_table.setDragEnabled(True)
        self.alt_table.setAcceptDrops(True)
        self.alt_table.setDragDropMode(QTableWidget.InternalMove)
        self.alt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.alt_table.model().rowsMoved.connect(self._on_alt_rows_moved)
        alt_layout.addWidget(self.alt_table)
        alt_btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_alt_pair)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self._delete_alt_pair)
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._reset_alt_pairs)
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._import_alt_pairs)
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_alt_pairs)
        zoom_btn = QPushButton("🔍 放大")
        zoom_btn.clicked.connect(self._zoom_alt_table)
        sort_btn = QPushButton("排序")
        sort_btn.clicked.connect(self._sort_alt_pairs)
        alt_btn_layout.addWidget(add_btn)
        alt_btn_layout.addWidget(del_btn)
        alt_btn_layout.addWidget(reset_btn)
        alt_btn_layout.addWidget(import_btn)
        alt_btn_layout.addWidget(export_btn)
        alt_btn_layout.addWidget(sort_btn)
        alt_btn_layout.addWidget(zoom_btn)
        alt_layout.addLayout(alt_btn_layout)
        left_layout.addWidget(alt_group)

        # 5. 数据预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("未选择文件")
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)
        left_layout.addWidget(preview_group)

        left_layout.addStretch()
        body_layout.addWidget(left_panel)

        self.filter_panel = FilterPanel()
        self.filter_panel.filter_changed.connect(self._on_filter_panel_changed)
        # 用 QSplitter 包裹，让侧边栏宽度可拖拽调整
        self.right_splitter = QSplitter(Qt.Horizontal)
        self.right_splitter.setSizes([260, 740])
        self.right_splitter.addWidget(self.filter_panel)

        # 右侧内容容器
        right_container = QWidget()
        right_container_layout = QVBoxLayout(right_container)
        right_container_layout.setContentsMargins(10, 10, 10, 10)  # 边距从4px改到10px，防止贴边

        # ========== 右侧面板 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(10)

        # 分析进度
        progress_group = QGroupBox("分析进度")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        right_layout.addWidget(progress_group)

        # 操作按钮
        action_group = QGroupBox("操作")
        action_layout = QHBoxLayout(action_group)
        self.start_btn = QPushButton("开始分析")
        self.cancel_btn = QPushButton("取消")
        self.open_dir_btn = QPushButton("打开目录")
        self.ppt_btn = QPushButton("生成PPT")
        self.excel_btn = QPushButton("生成表格")
        self.export_full_btn = QPushButton("导出完整Excel")
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.cancel_btn)
        action_layout.addWidget(self.open_dir_btn)
        action_layout.addWidget(self.ppt_btn)
        action_layout.addWidget(self.excel_btn)
        action_layout.addWidget(self.export_full_btn)
        right_layout.addWidget(action_group)

        # 偏差明细与审核
        audit_group = QGroupBox("偏差明细与审核")
        audit_layout = QVBoxLayout(audit_group)

        # 统计卡片
        stat_layout = QHBoxLayout()
        self.stat_total = QLabel("0")
        self.stat_high = QLabel("0")
        self.stat_need_note = QLabel("0")
        self.stat_ok = QLabel("0")
        stat_layout.addWidget(QLabel("总记录:"))
        stat_layout.addWidget(self.stat_total)
        stat_layout.addWidget(QLabel("偏差>10%:"))
        stat_layout.addWidget(self.stat_high)
        stat_layout.addWidget(QLabel("需补备注:"))
        stat_layout.addWidget(self.stat_need_note)
        stat_layout.addWidget(QLabel("已审核:"))
        stat_layout.addWidget(self.stat_ok)
        stat_layout.addStretch()
        audit_layout.addLayout(stat_layout)

        # 表格
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)  # 手动控制多列排序
        # 列宽策略：允许手动调整，最后一列不拉伸（水平滚动条自动出现）
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        self.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        # 行高28px，默认显示15行
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        audit_layout.addWidget(self.table_view)
        self.table_view.setFixedHeight(15 * 28 + 30)

        # 合计行
        summary_layout = QHBoxLayout()
        self.summary_quota = QLabel("定额: 0.00")
        self.summary_actual = QLabel("实际: 0.00")
        self.summary_amount = QLabel("偏差金额: 0.00")
        self.summary_qty = QLabel("偏差数量: 0.00")
        summary_layout.addWidget(self.summary_quota)
        summary_layout.addWidget(self.summary_actual)
        summary_layout.addWidget(self.summary_amount)
        summary_layout.addWidget(self.summary_qty)
        summary_layout.addStretch()
        unit_summary_btn = QPushButton("单位汇总")
        unit_summary_btn.clicked.connect(self._show_unit_summary)
        summary_layout.addWidget(unit_summary_btn)
        self.lock_btn = QPushButton("🔒 锁定列宽")
        self.lock_btn.setCheckable(True)
        self.lock_btn.clicked.connect(self._toggle_column_lock)
        summary_layout.addWidget(self.lock_btn)
        audit_layout.addLayout(summary_layout)

        right_container_layout.addWidget(audit_group)
        self.right_splitter.addWidget(right_container)

        right_layout.addWidget(self.right_splitter)

        # 运行日志
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(400)
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(log_group)

        # 用 QScrollArea 包裹右侧面板，实现整体垂直滚动
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right_panel)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body_layout.addWidget(right_scroll, 1)

        main_layout.addWidget(body_widget, 1)

    def _setup_menu_bar(self):
        menubar = self.menuBar()
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开 Excel", self)
        open_action.triggered.connect(self._select_input_file)
        file_menu.addAction(open_action)
        export_action = QAction("导出当前表格", self)
        export_action.triggered.connect(self._export_current_table)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 分析菜单
        analysis_menu = menubar.addMenu("分析")
        start_action = QAction("开始分析", self)
        start_action.triggered.connect(self._start_analysis)
        analysis_menu.addAction(start_action)

        # 审核菜单
        audit_menu = menubar.addMenu("审核")
        ai_action = QAction("AI 审核", self)
        ai_action.triggered.connect(self._run_ai_audit)
        audit_menu.addAction(ai_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        rule_action = QAction("规则配置", self)
        rule_action.triggered.connect(self._open_rule_config)
        tools_menu.addAction(rule_action)
        import_action = QAction("模板导入向导", self)
        import_action.triggered.connect(self._open_import_wizard)
        tools_menu.addAction(import_action)
        benefit_action = QAction("效益报告", self)
        benefit_action.triggered.connect(self._show_benefit_report)
        tools_menu.addAction(benefit_action)

        # 历史菜单
        history_menu = menubar.addMenu("历史")
        compare_action = QAction("历史对比", self)
        compare_action.triggered.connect(self._show_history_compare)
        history_menu.addAction(compare_action)
        dashboard_action = QAction("管理看板", self)
        dashboard_action.triggered.connect(self._open_dashboard)
        history_menu.addAction(dashboard_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        version_log_action = QAction("版本日志", self)
        version_log_action.triggered.connect(self._show_version_log)
        help_menu.addAction(version_log_action)
        help_menu.addSeparator()
        health_action = QAction("系统健康检查", self)
        health_action.triggered.connect(self._show_health_check)
        help_menu.addAction(health_action)
        help_menu.addSeparator()
        advanced_ppt_action = QAction("生成详细分析报告(专业版)", self)
        advanced_ppt_action.triggered.connect(self._generate_advanced_report)
        help_menu.addAction(advanced_ppt_action)

    def _setup_connections(self):
        self.start_btn.clicked.connect(self._start_analysis)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        self.open_dir_btn.clicked.connect(self._open_output_dir)
        self.ppt_btn.clicked.connect(self._generate_simple_ppt)
        self.excel_btn.clicked.connect(self._export_current_table)
        self.export_full_btn.clicked.connect(self._export_full_excel)
        # 连接双击信号（已读/未读切换）
        self.table_view.doubleClicked.connect(self._on_cell_double_clicked)

    # ------------------- 排序 -------------------
    def _on_sort_indicator_changed(self, logical_index, order):
        """多列联动排序（Ctrl+点击追加排序）"""
        modifiers = QApplication.keyboardModifiers()
        ctrl_pressed = (modifiers == Qt.ControlModifier)

        col = logical_index
        ascending = (order == Qt.AscendingOrder)

        if ctrl_pressed:
            found = False
            for i, (c, asc) in enumerate(self.sort_columns):
                if c == col:
                    self.sort_columns[i] = (col, not asc)
                    found = True
                    break
            if not found:
                self.sort_columns.append((col, ascending))
        else:
            self.sort_columns = [(col, ascending)]

        self._apply_multi_sort()

    def _apply_multi_sort(self):
        """将多列排序应用到 DataFrameModel"""
        if not self.sort_columns:
            return
        if not hasattr(self, 'source_model') or self.source_model is None:
            return
        df = self.source_model.getDataFrame()
        if df is None or df.empty:
            return
        sort_args = []
        for col, asc in self.sort_columns:
            if col == 0:   # 跳过状态列
                continue
            actual_col = col - 1  # 表格列索引偏移
            if actual_col < 0 or actual_col >= len(df.columns):
                continue
            col_name = df.columns[actual_col]
            sort_args.append((col_name, asc))
        if sort_args:
            df_sorted = df.sort_values(
                by=[c for c, _ in sort_args],
                ascending=[a for _, a in sort_args]
            )
            self.source_model.setDataFrame(df_sorted)
            # 更新排序指示器（显示所有排序列的箭头）
            for idx, (c_asc, asc) in enumerate(self.sort_columns):
                header = self.table_view.horizontalHeader()
                if idx == len(self.sort_columns) - 1:
                    header.setSortIndicator(c_asc, Qt.AscendingOrder if asc else Qt.DescendingOrder)

    # ------------------- 文件与目录 -------------------
    def _select_input_file(self):
        default_dir = r"E:\zpp011_dev\ZPP011导出文件原数据"
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 SAP Excel 文件", default_dir, "Excel files (*.xlsx *.xls)")
        if file_path:
            self.current_input_file = file_path
            self.input_file_edit.setText(file_path)
            # 预览文件基本信息
            try:
                xl = pd.ExcelFile(file_path)
                sheets = xl.sheet_names
                target = 'Data' if 'Data' in sheets else sheets[0]
                df = pd.read_excel(file_path, sheet_name=target)
                self.preview_label.setText(f"{os.path.basename(file_path)}\n总行数：{len(df)} 行\n列数：{len(df.columns)} 列")
            except Exception as e:
                self.preview_label.setText(f"读取失败：{e}")

    def _select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _open_output_dir(self):
        dir_path = self.output_dir_edit.text()
        if not dir_path:
            dir_path = os.path.expanduser("~/Documents/ZPP011分析报告")
        if os.path.exists(dir_path):
            os.startfile(dir_path)
        else:
            QMessageBox.warning(self, "提示", "输出目录不存在")

    # ------------------- 替代料配对 -------------------
    def _format_material_short(self, material):
        """返回 (显示文本, 工具提示)"""
        if isinstance(material, (list, tuple)):
            factory = material[0] if len(material) > 0 else ''
            code = material[1] if len(material) > 1 else ''
            name = material[2] if len(material) > 2 else ''
        else:
            factory = ''
            code = str(material)
            name = ''
        display = f"{code}|{name}" if code else name
        tooltip = f"工厂: {factory}\n编码: {code}\n名称: {name}" if factory else f"编码: {code}\n名称: {name}"
        return display, tooltip

    def _refresh_alt_view(self):
        self.alt_table.setRowCount(0)
        for idx, (a, b) in enumerate(self.alt_pairs):
            a_display, a_tip = self._format_material_short(a)
            b_display, b_tip = self._format_material_short(b)
            row = self.alt_table.rowCount()
            self.alt_table.insertRow(row)
            item_a = QTableWidgetItem(a_display)
            item_a.setToolTip(a_tip)
            item_a.setData(Qt.UserRole, idx)
            self.alt_table.setItem(row, 0, item_a)
            arrow = QTableWidgetItem(" ↔ ")
            arrow.setFlags(Qt.NoItemFlags)
            self.alt_table.setItem(row, 1, arrow)
            item_b = QTableWidgetItem(b_display)
            item_b.setToolTip(b_tip)
            item_b.setData(Qt.UserRole, idx)
            self.alt_table.setItem(row, 2, item_b)
        self.alt_count_label.setText(f"共 {len(self.alt_pairs)} 对")
        self.alt_table.resizeColumnsToContents()
        # 设置最小列宽，防止过窄
        self.alt_table.setColumnWidth(0, max(80, self.alt_table.columnWidth(0)))
        self.alt_table.setColumnWidth(2, max(80, self.alt_table.columnWidth(2)))

    def _on_alt_rows_moved(self, parent, start, end, destination, row):
        new_pairs = []
        for r in range(self.alt_table.rowCount()):
            item = self.alt_table.item(r, 0)
            if item:
                orig_idx = item.data(Qt.UserRole)
                if orig_idx is not None and orig_idx < len(self.alt_pairs):
                    new_pairs.append(self.alt_pairs[orig_idx])
        if new_pairs and len(new_pairs) == len(self.alt_pairs):
            self.alt_pairs = new_pairs
            save_alt_pairs(self.alt_pairs)
            self._refresh_alt_view()

    def _add_alt_pair(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("添加替代料配对")
        layout = QVBoxLayout(dialog)
        a_group = QGroupBox("物料A")
        a_form = QFormLayout(a_group)
        a_factory = QLineEdit()
        a_code = QLineEdit()
        a_name = QLineEdit()
        a_form.addRow("工厂:", a_factory)
        a_form.addRow("编码:", a_code)
        a_form.addRow("名称:", a_name)
        layout.addWidget(a_group)
        b_group = QGroupBox("物料B")
        b_form = QFormLayout(b_group)
        b_factory = QLineEdit()
        b_code = QLineEdit()
        b_name = QLineEdit()
        b_form.addRow("工厂:", b_factory)
        b_form.addRow("编码:", b_code)
        b_form.addRow("名称:", b_name)
        layout.addWidget(b_group)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            a = (a_factory.text(), a_code.text(), a_name.text())
            b = (b_factory.text(), b_code.text(), b_name.text())
            new_pair = (a, b)
            # 检查重复：以 (工厂, A编码, B编码) 为唯一键
            duplicate = False
            for existing in self.alt_pairs:
                if (existing[0][0] == a[0] and existing[0][1] == a[1]
                        and existing[1][1] == b[1]):
                    duplicate = True
                    break
            if duplicate:
                QMessageBox.warning(self, "提示",
                    "该替代料配对已存在，请勿重复添加")
                return
            self.alt_pairs.append(new_pair)
            save_alt_pairs(self.alt_pairs)
            self._refresh_alt_view()

    def _delete_alt_pair(self):
        current_row = self.alt_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先选中要删除的配对")
            return
        item = self.alt_table.item(current_row, 0)
        if item:
            idx = item.data(Qt.UserRole)
            if idx is not None and idx < len(self.alt_pairs):
                del self.alt_pairs[idx]
                save_alt_pairs(self.alt_pairs)
                self._refresh_alt_view()

    def _reset_alt_pairs(self):
        self.alt_pairs = list(DEFAULT_ALT_PAIRS)
        save_alt_pairs(self.alt_pairs)
        self._refresh_alt_view()

    def _import_alt_pairs(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入替代料配对", "", "JSON files (*.json);;Excel files (*.xlsx *.xls)")
        if not file_path:
            return
        try:
            if file_path.endswith('.json'):
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported = json.load(f)
                if isinstance(imported, list):
                    self.alt_pairs = imported
                    save_alt_pairs(self.alt_pairs)
                    self._refresh_alt_view()
                    QMessageBox.information(self, "成功", f"已导入 {len(imported)} 对")
                else:
                    QMessageBox.warning(self, "格式错误", "JSON 文件应为列表格式")
            else:
                wizard = ImportWizard(self, self.alt_pairs, None, on_alt_changed=self._refresh_alt_view, on_rules_changed=None)
                wizard.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {e}")

    def _export_alt_pairs(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出替代料配对", "alt_pairs.json", "JSON (*.json)")
        if file_path:
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.alt_pairs, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "成功", f"已导出到 {file_path}")

    def _zoom_alt_table(self):
        """放大显示替代料配对表格（支持右键删除）"""
        dialog = QDialog(self)
        dialog.setWindowTitle("替代料配对详情")
        dialog.resize(900, 600)
        layout = QVBoxLayout(dialog)
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["物料A", "", "物料B"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda pos: self._on_zoom_table_context_menu(pos, table, dialog))

        self._refresh_zoom_table(table)

        layout.addWidget(table)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    def _refresh_zoom_table(self, table):
        """刷新放大窗口的表格内容"""
        table.setRowCount(0)
        for idx, (a, b) in enumerate(self.alt_pairs):
            a_display, a_tip = self._format_material_short(a)
            b_display, b_tip = self._format_material_short(b)
            row = table.rowCount()
            table.insertRow(row)
            item_a = QTableWidgetItem(a_display)
            item_a.setToolTip(a_tip)
            item_a.setData(Qt.UserRole, idx)
            table.setItem(row, 0, item_a)
            arrow_item = QTableWidgetItem(" ↔ ")
            arrow_item.setFlags(Qt.NoItemFlags)
            table.setItem(row, 1, arrow_item)
            item_b = QTableWidgetItem(b_display)
            item_b.setToolTip(b_tip)
            item_b.setData(Qt.UserRole, idx)
            table.setItem(row, 2, item_b)
        table.resizeColumnsToContents()
        # 设置最小列宽，防止过窄
        table.setColumnWidth(0, max(80, table.columnWidth(0)))
        table.setColumnWidth(2, max(80, table.columnWidth(2)))

    def _on_zoom_table_context_menu(self, pos, table, dialog):
        """放大窗口表格的右键菜单"""
        item = table.itemAt(pos)
        if not item:
            return
        row = item.row()
        idx_item = table.item(row, 0)
        if not idx_item:
            return
        pair_idx = idx_item.data(Qt.UserRole)
        if pair_idx is None or pair_idx >= len(self.alt_pairs):
            return

        menu = QMenu()
        delete_action = menu.addAction("删除此配对")
        delete_action.triggered.connect(lambda: self._delete_alt_pair_from_zoom(pair_idx, table, dialog))
        menu.exec_(table.viewport().mapToGlobal(pos))

    def _delete_alt_pair_from_zoom(self, pair_idx, table, dialog):
        """从放大窗口删除替代料配对"""
        if pair_idx < 0 or pair_idx >= len(self.alt_pairs):
            return
        del self.alt_pairs[pair_idx]
        save_alt_pairs(self.alt_pairs)
        self._refresh_alt_view()          # 刷新主窗口替代料列表
        self._refresh_zoom_table(table)   # 刷新放大窗口表格
        QMessageBox.information(self, "删除成功", "已删除该替代料配对")

    def _sort_alt_pairs(self):
        """按物料A编码对替代料配对进行排序"""
        if not self.alt_pairs:
            return
        def get_code(pair):
            a = pair[0]
            if isinstance(a, (list, tuple)) and len(a) > 1:
                return str(a[1])
            else:
                return str(a)
        self.alt_pairs.sort(key=get_code)
        save_alt_pairs(self.alt_pairs)
        self._refresh_alt_view()
        QMessageBox.information(self, "排序完成", "已按物料A编码升序排列")

    def _toggle_column_lock(self):
        """切换列宽锁定/解锁状态"""
        locked = self.lock_btn.isChecked()
        header = self.table_view.horizontalHeader()
        if locked:
            header.setSectionResizeMode(QHeaderView.Fixed)
            self.lock_btn.setText("🔓 解锁列宽")
            self.statusBar().showMessage("列宽已锁定", 2000)
        else:
            header.setSectionResizeMode(QHeaderView.Interactive)
            self.lock_btn.setText("🔒 锁定列宽")
            self.statusBar().showMessage("列宽已解锁，可拖拽调整", 2000)

    # ------------------- 数据加载与表格 -------------------
    def _set_audit_data(self, df: pd.DataFrame):
        """加载数据到表格，并标准化「是否替代料」列，确保筛选器能正常匹配
        同时实现：指纹比对、状态恢复、变动检测
        """
        # 标准化"是否替代料"列为"是"/"否"字符串
        if "是否替代料" in df.columns:
            def _norm_alt(v):
                if pd.isna(v):
                    return "否"
                s = str(v).strip().lower()
                if s in ("是", "true", "1", "yes", "y"):
                    return "是"
                if "替代" in s or "alt" in s:
                    return "是"
                return "否"
            df["是否替代料"] = df["是否替代料"].apply(_norm_alt)
        else:
            # 如果数据中没有该列，根据替代料配对列表自动判断
            if hasattr(self, 'alt_pairs') and self.alt_pairs:
                alt_codes = set()
                for a, b in self.alt_pairs:
                    if isinstance(a, (list, tuple)) and len(a) > 1:
                        alt_codes.add(str(a[1]).strip())
                    if isinstance(b, (list, tuple)) and len(b) > 1:
                        alt_codes.add(str(b[1]).strip())
                # 查找物料编码列
                code_col = None
                for c in ['物料号', '物料编码', 'code', '组件物料号']:
                    if c in df.columns:
                        code_col = c
                        break
                if code_col:
                    df['是否替代料'] = df[code_col].astype(str).str.strip().isin(alt_codes)
                    df['是否替代料'] = df['是否替代料'].map({True: '是', False: '否'})
                else:
                    df['是否替代料'] = '否'
            else:
                df['是否替代料'] = '否'
        
        # ===== 新增：指纹比对 + 变动检测 =====
        
        # 1. 添加业务主键列
        try:
            df['data_id'] = df['订单日期'].astype(str) + '|' + df['流程订单'].astype(str) + '|' + df['物料编码'].astype(str)
        except Exception as e:
            self.log(f"创建data_id失败: {e}", "error")
            df['data_id'] = df.index.astype(str)
        
        # 2. 计算指纹
        try:
            df['fingerprint'] = df.apply(
                lambda r: calc_fingerprint(
                    r.get('偏差金额(含税)', r.get('偏差金额', 0)),
                    r.get('偏差率(%)', 0)
                ), axis=1
            )
        except Exception as e:
            self.log(f"计算指纹失败: {e}", "error")
            df['fingerprint'] = "0.00|0.0"
        
        # 3. 加载历史状态
        try:
            from core.read_status import load_read_status, record_deviation_change
            data_ids = df['data_id'].tolist()
            status_map = load_read_status(data_ids)
        except Exception as e:
            self.log(f"加载历史状态失败: {e}", "error")
            status_map = {}
        
        # 4. 构建旧快照（仅已审核记录）
        old_snapshot = {}
        if self.audit_data is not None and not self.audit_data.empty:
            try:
                for _, row in self.audit_data.iterrows():
                    if self._is_record_audited(row):
                        did = f"{row['订单日期']}|{row['流程订单']}|{row['物料编码']}"
                        old_snapshot[did] = (
                            row.get('偏差金额(含税)', row.get('偏差金额', 0)),
                            row.get('偏差率(%)', 0)
                        )
            except Exception as e:
                self.log(f"构建旧快照失败: {e}", "error")
        
        # 5. 构建新快照中的已审核记录
        new_audited = []
        try:
            for _, row in df.iterrows():
                if self._is_record_audited(row):
                    new_audited.append({
                        'data_id': row['data_id'],
                        'amount': row.get('偏差金额(含税)', row.get('偏差金额', 0)),
                        'rate': row.get('偏差率(%)', 0)
                    })
        except Exception as e:
            self.log(f"构建新快照失败: {e}", "error")
        
        # 6. 检测变动
        changes = []
        try:
            from core.change_detector import detect_changes
            changes = detect_changes(old_snapshot, new_audited)
        except Exception as e:
            self.log(f"检测变动失败: {e}", "error")
        
        # 7. 应用已读状态：指纹匹配则恢复历史，否则强制未读
        read_list = []
        try:
            for _, row in df.iterrows():
                did = row['data_id']
                fp = row['fingerprint']
                if did in status_map:
                    hist_read, hist_fp = status_map[did]
                    if hist_fp == fp:
                        read_list.append(hist_read)
                    else:
                        read_list.append(0)  # 指纹不匹配，强制未读
                else:
                    read_list.append(0)  # 新记录，默认未读
            df['_read'] = read_list
        except Exception as e:
            self.log(f"应用已读状态失败: {e}", "error")
            df['_read'] = 0  # 默认未读
        
        # 8. 记录变动并弹窗
        if changes:
            try:
                for ch in changes:
                    record_deviation_change(
                        ch['data_id'], ch['old_amount'], ch['new_amount'],
                        ch['old_rate'], ch['new_rate'], "重新分析数据变动"
                    )
                self._show_change_notification(changes)
            except Exception as e:
                self.log(f"记录变动失败: {e}", "error")
        
        # ===== 列重排序：把"偏差率"移到"偏差金额"后面 =====
        try:
            cols = list(df.columns)
            # 找到偏差金额列
            amt_col = None
            for col in ['偏差金额(含税)', '偏差金额']:
                if col in cols:
                    amt_col = col
                    break
            
            # 找到偏差率列
            rate_col = None
            for col in ['偏差率(%)', '偏差率']:
                if col in cols:
                    rate_col = col
                    break
            
            # 如果两个列都存在，把偏差率移到偏差金额后面
            if amt_col and rate_col:
                # 先移除偏差率列
                cols = [c for c in cols if c != rate_col]
                # 找到偏差金额的索引
                amt_idx = cols.index(amt_col)
                # 在偏差金额后面插入偏差率
                cols.insert(amt_idx + 1, rate_col)
                # 重新排列DataFrame列
                df = df[cols]
                self.log(f"已调整列顺序：{rate_col} 移到 {amt_col} 后面", "info")
        except Exception as e:
            self.log(f"列重排序失败: {e}", "error")
        
        # ===== 原有逻辑 =====
        
        self.audit_data = df
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)  # 确保 _read 列被移到第一列
        self.proxy_model = AuditProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)
        # 连接选中变化信号（setModel 会重建 selectionModel，需要重新连接）
        try:
            self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass
        self.table_view.resizeColumnsToContents()
        # 设置第一列（状态列）窄宽
        self.table_view.setColumnWidth(0, 35)
        self.source_model.dataChanged.connect(self._update_summary)
        self.proxy_model.layoutChanged.connect(self._update_summary)
        self._update_summary()
        self._update_stat_cards(df)
        # 更新侧边栏筛选面板的下拉选项
        self.filter_panel.update_options(df)
        # 初始化列宽锁定状态（默认解锁）
        self.lock_btn.setChecked(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        
        # 净偏差手动修正（临时方案）
        try:
            self.audit_data = self._recalc_net_offset(self.audit_data)
            self.log("已执行净偏差手动修正", "info")
        except Exception as e:
            self.log(f"净偏差手动修正失败: {e}", "error")


    def _recalc_net_offset(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        手动修正净偏差计算（临时方案）
        在 analyzer.py 的 apply_net_offset 之后，再次核对替代料配对的净偏差
        确保物料A和物料B的偏差金额正确抵消
        """
        try:
            if '物料编码' not in df.columns or '偏差金额(含税)' not in df.columns:
                return df
            
            alt_pairs = getattr(self, 'alt_pairs', [])
            if not alt_pairs:
                return df
            
            # 标准化配对列表
            pairs = []
            for p in alt_pairs:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    if isinstance(p[0], (list, tuple)):
                        code_a = str(p[0][1]) if len(p[0]) > 1 else str(p[0][0])
                        code_b = str(p[1][1]) if len(p[1]) > 1 else str(p[1][0])
                    else:
                        code_a = str(p[0])
                        code_b = str(p[1])
                    pairs.append((code_a, code_b))
            
            if not pairs:
                return df
            
            self.log(f"手动修正净偏差，共 {len(pairs)} 对替代料", "info")
            
            # 按 订单日期|流程订单 分组
            date_col = '订单日期' if '订单日期' in df.columns else '订单开始日期'
            if date_col not in df.columns:
                return df
                
            df['_match_key'] = df[date_col].astype(str) + '|' + df['流程订单'].astype(str)
            
            processed = set()
            for key, group in df.groupby('_match_key'):
                code_to_indices = {}
                for idx, row in group.iterrows():
                    code = str(row['物料编码'])
                    if code not in code_to_indices:
                        code_to_indices[code] = []
                    code_to_indices[code].append(idx)
                
                for code_a, code_b in pairs:
                    if code_a not in code_to_indices or code_b not in code_to_indices:
                        continue
                    
                    idx_list_a = code_to_indices[code_a]
                    idx_list_b = code_to_indices[code_b]
                    
                    min_len = min(len(idx_list_a), len(idx_list_b))
                    for i in range(min_len):
                        idx_a = idx_list_a[i]
                        idx_b = idx_list_b[i]
                        
                        if idx_a in processed or idx_b in processed:
                            continue
                        
                        # 获取偏差金额
                        amount_a = pd.to_numeric(df.at[idx_a, '偏差金额(含税)'], errors='coerce')
                        amount_b = pd.to_numeric(df.at[idx_b, '偏差金额(含税)'], errors='coerce')
                        
                        if pd.isna(amount_a) or pd.isna(amount_b):
                            continue
                        
                        # 计算净偏差
                        net = amount_a + amount_b
                        df.at[idx_a, '净偏差'] = net
                        df.at[idx_b, '净偏差'] = net
                        
                        processed.add(idx_a)
                        processed.add(idx_b)
            
            df.drop(columns=['_match_key'], inplace=True)
            self.log(f"净偏差修正完成，处理 {len(processed)} 行", "info")
            
        except Exception as e:
            self.log(f"净偏差修正失败: {e}", "error")
            
        return df

    def _update_stat_cards(self, df):
        total = len(df)
        if '偏差率(%)' in df.columns:
            high = (df['偏差率(%)'].abs() > 10).sum()
        else:
            high = 0
        if '备注原因' in df.columns:
            need_note = (df['备注原因'].isna() | (df['备注原因'] == '')).sum()
            ok = total - need_note
        else:
            need_note = 0
            ok = 0
        self.stat_total.setText(str(total))
        self.stat_high.setText(str(high))
        self.stat_need_note.setText(str(need_note))
        self.stat_ok.setText(str(ok))

    def _update_summary(self):
        if self.audit_data is None or self.audit_data.empty:
            self.summary_quota.setText("定额: 0.00")
            self.summary_actual.setText("实际: 0.00")
            self.summary_amount.setText("净偏差(抵消后): 0.00")
            self.summary_qty.setText("偏差数量: 0.00")
            return
        df = self.audit_data
        quota_col = next((c for c in ['定额', '数量-定额', 'quota'] if c in df.columns), None)
        actual_col = next((c for c in ['实际', '数量-实际', 'actual'] if c in df.columns), None)
        # 优先使用净偏差列（抵消后），兜底用偏差金额
        amount_col = next((c for c in ['净偏差', '偏差金额(含税)', '偏差金额', 'deviation_amount'] if c in df.columns), None)
        qty_col = next((c for c in ['偏差数量', '数量偏差', 'dev_qty'] if c in df.columns), None)
        quota_sum = df[quota_col].fillna(0).sum() if quota_col else 0
        actual_sum = df[actual_col].fillna(0).sum() if actual_col else 0
        amount_sum = df[amount_col].fillna(0).sum() if amount_col else 0
        if qty_col:
            qty_sum = df[qty_col].fillna(0).sum()
        elif actual_col and quota_col:
            qty_sum = (df[actual_col] - df[quota_col]).fillna(0).sum()
        else:
            qty_sum = 0
        self.summary_quota.setText(f"定额: {quota_sum:,.2f}")
        self.summary_actual.setText(f"实际: {actual_sum:,.2f}")
        # 根据使用的列决定标签
        if amount_col == '净偏差':
            self.summary_amount.setText(f"净偏差(抵消后): {amount_sum:,.2f}")
        else:
            self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")
        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")

    # ------------------------------------------------------------------ #
    # FilterPanel 侧边栏筛选处理器（使用 AuditProxyModel.setCustomFilters）
    # ------------------------------------------------------------------ #
    def _on_filter_panel_changed(self, filters: dict):
        """侧边栏筛选条件变化时的处理"""
        if self.proxy_model is None or self.audit_data is None:
            return
        self.proxy_model.setCustomFilters(filters)
        # 合计行会在 proxy_model.layoutChanged 信号中自动更新
        self._update_summary()

    def _show_unit_summary(self):
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.information(self, "提示", "无数据")
            return
        dialog = UnitSummaryDialog(self, self.audit_data)
        dialog.exec()

    # ------------------- 分析 -------------------
    def _start_analysis(self):
        if not self.current_input_file:
            QMessageBox.warning(self, "提示", "请先选择输入文件")
            return
        if self.analysis_worker and self.analysis_worker.isRunning():
            QMessageBox.information(self, "提示", "分析任务已在后台运行")
            return
        start_date = self.start_date_edit.text().strip()
        end_date = self.end_date_edit.text().strip()
        material_search = self.material_search_edit.text().strip()
        # 缓存分析参数，用于后续导出完整Excel
        self._analysis_params = {
            'input_file': self.current_input_file,
            'alt_pairs': list(self.alt_pairs),
            'start_date': start_date,
            'end_date': end_date,
            'material_search': material_search,
        }
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("分析中...")
        self.start_btn.setEnabled(False)
        self.analysis_worker = AnalysisWorker(
            self.current_input_file, self.alt_pairs, start_date, end_date, material_search
        )
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        self.analysis_worker.log.connect(self.log)
        self.analysis_worker.start()

    def _cancel_analysis(self):
        """取消分析和AI审核"""
        cancelled = False
        
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.cancel()
            self.log("正在取消分析...", "warn")
            cancelled = True
            # 等待线程结束（最多3秒）
            if not self.analysis_worker.wait(3000):
                self.analysis_worker.terminate()
                self.analysis_worker.wait()
            self.analysis_worker = None
            
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.cancel()
            self.log("正在取消AI审核...", "warn")
            cancelled = True
            # 等待线程结束（最多3秒）
            if not self.ai_worker.wait(3000):
                self.ai_worker.terminate()
                self.ai_worker.wait()
            self.ai_worker = None
            
        if cancelled:
            self.progress_bar.setVisible(False)
            self.progress_label.setText("已取消")
            self.start_btn.setEnabled(True)
            self.log("操作已取消", "info")

    def _on_analysis_progress(self, percent, step_name):
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{step_name} {percent}%")

    def _on_analysis_finished(self, df):
        """分析完成，直接加载 DataFrame（自动保存临时文件供PPT生成用）"""
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.progress_label.setText("完成")
        self.statusBar().showMessage("分析完成，正在加载结果...")
        try:
            # 不再反转偏差数量，analyzer 已按 实际-定额 计算
            if '偏差率(%)' in df.columns:
                df['偏差率(%)'] = pd.to_numeric(df['偏差率(%)'], errors='coerce')
            self._set_audit_data(df)
            # 保存临时Excel文件，供PPT生成使用（不弹窗提示用户）
            import tempfile
            temp_dir = os.path.join(tempfile.gettempdir(), "zpp011_analysis")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            df.to_excel(temp_path, sheet_name='完整偏差明细', index=False)
            self._analysis_output_path = temp_path
            self.statusBar().showMessage(f"分析完成，共加载 {len(df)} 条记录")
            QMessageBox.information(self, "完成", f"分析完成，共加载 {len(df)} 条记录")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载结果失败: {e}")
        finally:
            self.analysis_worker = None  # 清理worker引用

    def _on_analysis_error(self, error_msg):
        # 1. 打印到控制台
        print("=" * 60)
        print("分析错误:")
        print(error_msg)
        print("=" * 60)
        
        # 2. 弹窗显示
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.progress_label.setText("错误")
        QMessageBox.critical(self, "错误", error_msg)
        self.analysis_worker = None  # 清理worker引用

    def log(self, msg, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")

    # ------------------- AI 审核 -------------------
    def _run_ai_audit(self):
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        if self.ai_worker and self.ai_worker.isRunning():
            QMessageBox.information(self, "提示", "AI审核已在后台运行")
            return
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("AI审核中...")
        self.ai_worker = AIAuditWorker(self.audit_data, self.rule_engine, self.ai_client)
        self.ai_worker.progress.connect(self._on_ai_progress)
        self.ai_worker.finished.connect(self._on_ai_finished)
        self.ai_worker.error.connect(self._on_ai_error)
        self.ai_worker.log.connect(self.log)
        self.ai_worker.start()

    def _on_ai_progress(self, current, total):
        percent = int(current / total * 100)
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"AI审核: {current}/{total}")

    def _on_ai_finished(self, updated_df):
        """AI审核完成后的回调"""
        # 调试：检查 AI 建议列的数据情况
        if 'AI建议' in updated_df.columns:
            non_empty = updated_df['AI建议'].replace('', pd.NA).notna().sum()
            total = len(updated_df)
            self.log(f"AI审核完成：共 {total} 条记录，{non_empty} 条有AI建议", "info")
            if non_empty == 0:
                self.log("警告：AI建议列为空，可能是所有记录偏差率<1%被跳过", "warning")
                QMessageBox.warning(self, "AI审核结果", 
                    f"AI审核已完成，但所有记录的AI建议均为空。\n"
                    f"可能原因：\n"
                    f"1. 所有记录偏差率 < 1%，被自动跳过\n"
                    f"2. 所有记录已有备注且偏差率 < 10%\n"
                    f"3. AI客户端调用失败\n\n"
                    f"请检查数据或重试。")
        else:
            self.log("警告：AI建议列不存在", "warning")
        
        self._set_audit_data(updated_df)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("就绪")
        if 'AI建议' not in updated_df.columns or updated_df['AI建议'].replace('', pd.NA).notna().sum() > 0:
            QMessageBox.information(self, "完成", "AI审核已完成")
        self.ai_worker = None  # 清理worker引用

    def _on_ai_error(self, error_msg):
        # 1. 打印到控制台
        print("=" * 60)
        print("AI审核错误:")
        print(error_msg)
        print("=" * 60)
        
        # 2. 弹窗显示
        self.progress_bar.setVisible(False)
        self.progress_label.setText("错误")
        QMessageBox.critical(self, "错误", error_msg)
        self.ai_worker = None  # 清理worker引用

    # ------------------- 导出 -------------------
    def _export_current_table(self):
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出当前表格", "偏差明细.xlsx", "Excel files (*.xlsx)")
        if file_path:
            try:
                self.audit_data.to_excel(file_path, index=False)
                QMessageBox.information(self, "成功", f"已导出到 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _export_full_excel(self):
        """导出完整Excel，可选单Sheet或完整多Sheet（带预警颜色）"""
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据，请先进行分析")
            return
        default_name = f"ZPP011偏差分析最终版_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存完整Excel文件", default_name, "Excel files (*.xlsx)")
        if not save_path:
            return

        # 如果有缓存的分析参数，询问是否生成完整多Sheet
        if self._analysis_params and self.current_input_file:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "导出选项",
                "是否生成完整多Sheet分析报告（含汇总统计、预警颜色等）？\n\n"
                "点击「是」→ 生成完整多Sheet Excel（需重新分析，较慢）\n"
                "点击「否」→ 仅导出当前表格数据（快速）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._export_full_analysis_excel(save_path)
                return

        # 仅导出当前表格数据
        try:
            self.audit_data.to_excel(save_path, sheet_name='完整偏差明细', index=False)
            QMessageBox.information(self, "成功", f"已导出到 {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _export_full_analysis_excel(self, save_path):
        """使用缓存的分析参数重新生成完整多Sheet Excel（带预警颜色）"""
        try:
            from PySide6.QtWidgets import QProgressDialog
            progress_dlg = QProgressDialog("正在重新分析生成完整报告...", "取消", 0, 100, self)
            progress_dlg.setWindowTitle("导出中")
            progress_dlg.setWindowModality(Qt.WindowModal)  # WindowModal
            progress_dlg.show()
            QApplication.processEvents()

            result = do_analysis_v2(
                input_file=self._analysis_params['input_file'],
                output_dir=None,
                alt_pairs=self._analysis_params['alt_pairs'],
                progress_callback=lambda step_idx, step_name, percent: progress_dlg.setValue(percent),
                cancel_check=lambda *args: progress_dlg.wasCanceled(),
                start_date=self._analysis_params.get('start_date'),
                end_date=self._analysis_params.get('end_date'),
                material_search=self._analysis_params.get('material_search'),
                output_path=save_path,
                enable_net_offset=True,
                return_dataframe=False,  # 保存到文件
            )
            progress_dlg.close()
            QMessageBox.information(self, "成功", f"完整分析报告已导出到\n{save_path}\n\n"
                                               "包含Sheet:\n"
                                               "📋 分析说明 · 汇总统计(带预警颜色)\n"
                                               "完整偏差明细 · 替代料明细 · 无备注预警\n"
                                               "中间地带明细 · 异常预警 · 偏差金额分析\n"
                                               "偏差原因汇总 · 偏差原因分析 · 趋势分析")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出完整报告失败: {e}")

    # ------------------- 右键菜单 -------------------
    def _show_context_menu(self, pos: QPoint):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        
        # 获取所有选中的行（修复批量选择问题）
        selected_rows = set()
        for idx in self.table_view.selectionModel().selectedIndexes():
            source_index = self.proxy_model.mapToSource(idx)
            selected_rows.add(source_index.row())
        
        if not selected_rows:
            source_index = self.proxy_model.mapToSource(index)
            selected_rows.add(source_index.row())
        
        selected_rows = list(selected_rows)
        
        row = selected_rows[0]
        row_data = self.source_model.getDataFrame().iloc[row]
        menu = QMenu()
        copy_action = menu.addAction("复制物料编码")
        copy_action.triggered.connect(lambda: self._copy_material_code(row_data))
        menu.addSeparator()
        
        # 批量标记已读/未读
        menu.addSeparator()
        mark_read_action = menu.addAction("标记为已读")
        mark_read_action.triggered.connect(lambda: self._batch_mark_read(selected_rows, 1))
        mark_unread_action = menu.addAction("标记为未读")
        mark_unread_action.triggered.connect(lambda: self._batch_mark_read(selected_rows, 0))
        
        menu.addSeparator()
        batch_status = menu.addAction("批量改状态")
        batch_status.triggered.connect(lambda: self._batch_change_status(selected_rows))
        batch_remark = menu.addAction("批量填备注")
        batch_remark.triggered.connect(lambda: self._batch_remark(selected_rows))
        batch_export = menu.addAction("批量导出")
        batch_export.triggered.connect(lambda: self._batch_export(selected_rows))
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _copy_material_code(self, row_data):
        code = row_data.get('物料编码', '')
        if code:
            QApplication.clipboard().setText(str(code))
            self.statusBar().showMessage(f"已复制物料编码: {code}", 2000)

    def _batch_change_status(self, rows):
        dialog = BatchChangeStatusDialog(self, rows, self.audit_data, self._set_audit_data)
        dialog.exec()

    def _batch_remark(self, rows):
        dialog = BatchRemarkDialog(self, rows, self.audit_data, self._set_audit_data)
        dialog.exec()

    def _batch_export(self, rows):
        df_subset = self.audit_data.iloc[rows].copy()
        dialog = BatchExportDialog(self, df_subset)
        dialog.exec()

    # ------------------- 其他功能 -------------------
    def _open_rule_config(self):
        rules_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'system', 'rules.json')
        def on_rules_changed():
            self.rule_engine.load_rules()
            if self.audit_data is not None:
                self._set_audit_data(self.audit_data)  # 刷新表格颜色等
        dialog = RuleConfigDialog(self, rules_path, self.config_manager, on_rules_changed)
        dialog.exec()

    def _open_import_wizard(self):
        rules_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'system', 'rules.json')
        wizard = ImportWizard(self, self.alt_pairs, rules_path,
                              on_alt_changed=self._refresh_alt_view,
                              on_rules_changed=lambda: (self.rule_engine.load_rules(), self._set_audit_data(self.audit_data)))
        wizard.exec()

    def _generate_simple_ppt(self):
        """生成简明版 PPT（使用 ppt_generator.py）"""
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据，请先完成分析")
            return

        # 优先使用最近一次分析的 Excel 输出路径
        excel_path = getattr(self, '_analysis_output_path', None)
        if not excel_path or not os.path.exists(excel_path):
            excel_path, _ = QFileDialog.getOpenFileName(
                self, "请选择分析结果 Excel 文件", "", "Excel files (*.xlsx)"
            )
            if not excel_path:
                return

        from core.advanced_ppt_generator_v2 import generate_advanced_report_v2
        
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"ZPP011智能报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        )
        try:
            self.log(f"开始生成智能PPT：{excel_path}", "info")
            success = generate_advanced_report_v2(excel_path, output_path, log_cb=self.log)
            if success:
                self.log(f"PPT生成成功：{output_path}", "info")
                if QMessageBox.question(
                    self, "生成成功", f"报告已生成：\n{output_path}\n是否打开？"
                ) == QMessageBox.Yes:
                    os.startfile(output_path)
            else:
                QMessageBox.warning(self, "生成失败", "PPT生成返回失败，请查看日志")
        except Exception as e:
            self.log(f"PPT生成失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"生成失败: {e}")

    def _generate_advanced_report(self):
        """生成专业版详细分析报告（20+ 页，使用 advanced_ppt_generator_v2）"""
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据，请先完成分析")
            return

        excel_path = getattr(self, '_analysis_output_path', None)
        if not excel_path or not os.path.exists(excel_path):
            excel_path, _ = QFileDialog.getOpenFileName(
                self, "请选择分析结果 Excel 文件", "", "Excel files (*.xlsx)"
            )
            if not excel_path:
                return

        from core.advanced_ppt_generator_v2 import generate_advanced_report_v2
        
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"ZPP011专业报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        )
        try:
            self.log(f"开始生成专业版智能PPT：{excel_path}", "info")
            success = generate_advanced_report_v2(excel_path, output_path, log_cb=self.log)
            if success:
                self.log(f"专业版报告生成成功：{output_path}", "info")
                if QMessageBox.question(
                    self, "生成成功", f"报告已生成：\n{output_path}\n是否打开？"
                ) == QMessageBox.Yes:
                    os.startfile(output_path)
            else:
                QMessageBox.warning(self, "生成失败", "专业版报告生成返回失败，请查看日志")
        except Exception as e:
            self.log(f"专业版报告生成失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"生成失败: {e}")

    def _show_health_check(self):
        """显示系统健康检查面板"""
        dialog = HealthCheckDialog(self)
        dialog.exec()

    def _show_benefit_report(self):
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        dialog = BenefitReportDialog(self, self.audit_data)
        dialog.exec()

    def _show_history_compare(self):
        dialog = HistoryCompareDialog(self)
        dialog.exec()

    def _open_dashboard(self):
        dialog = DashboardDialog(self._get_current_audit_data(), None, self)
        dialog.drill_down_signal.connect(self._on_drill_down)
        dialog.exec()

    def _get_current_audit_data(self):
        return self.audit_data.copy() if self.audit_data is not None else pd.DataFrame()

    def _on_drill_down(self, filter_key, filter_value):
        if self.audit_data is None:
            return
        cols = self.source_model.getDataFrame().columns
        if filter_key in cols:
            idx = cols.get_loc(filter_key)
            self.proxy_model.setFilter(idx, filter_value)
            self.statusBar().showMessage(f"已下钻至物料类型：{filter_value}", 3000)

    def _show_about(self):
        QMessageBox.about(self, "关于", "ZPP011 生产偏差分析器\nPySide6 迁移版 v42.0\n\n功能：偏差分析、AI审核、规则配置、管理看板、批量操作等")

    def _is_record_audited(self, row):
        """判断是否已审核（根据审核状态或备注来源）"""
        try:
            if '审核状态' in row and row['审核状态'] == '已审核':
                return True
            if '备注来源' in row and row['备注来源'] not in ('', 'AI审核', None):
                return True
        except Exception:
            pass
        return False

    def _show_change_notification(self, changes):
        """显示变动提醒"""
        try:
            msg = f'发现 {len(changes)} 条已审核记录发生数值变动，已强制设为"未读"。'
            self.statusBar().showMessage(msg, 5000)
            # 非模态弹窗
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "变动提醒", msg)
        except Exception as e:
            self.log(f"显示变动提醒失败: {e}", "error")

    def _on_cell_double_clicked(self, index):
        """双击单元格事件"""
        try:
            if index.column() == 0:  # 第一列（状态列）
                source_index = self.proxy_model.mapToSource(index)
                row = source_index.row()
                df = self.source_model.getDataFrame()
                if row >= len(df):
                    return
                
                data_id = df.iloc[row]['data_id']
                current_read = df.iloc[row].get('_read', 0)
                new_read = 1 - current_read
                
                # 更新内存
                df.at[df.index[row], '_read'] = new_read
                self.source_model.setDataFrame(df)
                
                # 更新数据库
                from core.read_status import save_read_status
                fingerprint = df.iloc[row].get('fingerprint', '')
                save_read_status(data_id, new_read, fingerprint)
                
                self.statusBar().showMessage(f"已标记为{'已读' if new_read else '未读'}", 2000)
        except Exception as e:
            self.log(f"双击切换状态失败: {e}", "error")

    def _on_selection_changed(self, selected, deselected):
        """当选中的单元格变化时，计算选中单元格的数值合计（按列分组）"""
        if self.proxy_model is None or self.audit_data is None:
            self.statusBar().showMessage("")
            return

        indexes = self.table_view.selectionModel().selectedIndexes()
        if not indexes:
            self.statusBar().showMessage("")
            return

        df = self.source_model.getDataFrame()
        numeric_cols = ['定额', '实际', '偏差数量', '偏差金额', '净偏差数量', '净偏差金额']

        col_sums = {}
        for idx in indexes:
            source_idx = self.proxy_model.mapToSource(idx)
            row = source_idx.row()
            col = source_idx.column()
            if col == 0:  # 跳过状态列
                continue
            if col >= len(df.columns):
                continue
            col_name = df.columns[col]
            if col_name not in numeric_cols:
                continue
            val = df.iloc[row, col]
            if pd.notna(val) and isinstance(val, (int, float)):
                col_sums[col_name] = col_sums.get(col_name, 0) + val

        if col_sums:
            msg = "选中合计：" + " | ".join([f"{k}: {v:,.2f}" for k, v in col_sums.items()])
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().showMessage("选中合计：无有效数值", 2000)

    def _batch_mark_read(self, rows, is_read):
        """批量标记已读/未读（供右键菜单调用）"""
        try:
            df = self.source_model.getDataFrame()
            from core.read_status import save_read_status
            
            for row in rows:
                if row < len(df):
                    df.at[df.index[row], '_read'] = is_read
                    data_id = df.iloc[row]['data_id']
                    fingerprint = df.iloc[row].get('fingerprint', '')
                    save_read_status(data_id, is_read, fingerprint)
            
            self.source_model.setDataFrame(df)
            self.statusBar().showMessage(f"已批量标记为{'已读' if is_read else '未读'}", 2000)
        except Exception as e:
            self.log(f"批量标记失败: {e}", "error")

    def _batch_mark_selected_read(self, is_read=1):
        """批量标记选中行为已读/未读（从 selectionModel 获取选中行）"""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            self.statusBar().showMessage("请先选中要标记的行", 2000)
            return
        
        rows = set()
        for idx in selection:
            source_idx = self.proxy_model.mapToSource(idx)
            rows.add(source_idx.row())
        
        self._batch_mark_read(list(rows), is_read)

    def _copy_previous_remark(self):
        """复制当前选中行的上一行备注到当前行"""
        current = self.table_view.currentIndex()
        if not current.isValid():
            self.statusBar().showMessage("请先选中一行", 2000)
            return
        
        source_idx = self.proxy_model.mapToSource(current)
        row = source_idx.row()
        
        if row <= 0:
            self.statusBar().showMessage("第一行没有上一行可复制", 2000)
            return
        
        df = self.source_model.getDataFrame()
        
        # 获取上一行的备注
        prev_remark = ''
        for col in ['备注', '备注原因']:
            if col in df.columns:
                val = df.iloc[row-1][col]
                if pd.notna(val) and str(val).strip() != '':
                    prev_remark = str(val)
                    break
        
        if not prev_remark:
            self.statusBar().showMessage("上一行没有备注可复制", 2000)
            return
        
        # 更新当前行的备注列
        try:
            for col in ['备注', '备注原因']:
                if col in df.columns:
                    df.at[df.index[row], col] = prev_remark
            self.source_model.setDataFrame(df)
            self.statusBar().showMessage(f"已复制上一行备注：{prev_remark[:30]}", 3000)
        except Exception as e:
            self.log(f"复制上一行备注失败: {e}", "error")

    def _get_all_rows(self):
        """获取所有行索引"""
        if self.proxy_model is None:
            return []
        rows = []
        for i in range(self.proxy_model.rowCount()):
            source_index = self.proxy_model.mapToSource(self.proxy_model.index(i, 0))
            rows.append(source_index.row())
        return rows

    def _show_version_log(self):
        """显示版本日志对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("版本日志 - v42.0")
        dialog.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 标题
        title_label = QLabel("ZPP011 生产偏差分析器 - 版本日志")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 版本日志文本
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown("""
## v42.0 (2026-06-06)

### ✨ 新增功能
1. **预警等级颜色标识**
   - GUI表格：预警列红/黄/绿背景色
   - 导出Excel：汇总统计sheet预警列带颜色填充

2. **替代料配对区域优化**
   - 紧凑显示（2列布局）
   - 鼠标悬停显示完整配对信息
   - 添加"🔍 放大"按钮查看大图

3. **分析后不自动保存Excel**
   - 和tkinter版本一致，分析后只显示在表格中
   - 用户可手动点击"导出完整Excel"保存

### 🐛 修复问题
1. **偏差数量符号反转** - 删除多余的反转代码
2. **备注列为空** - 优先取"备注"列，没有再取"备注原因"
3. **侧边栏筛选无效** - 修复日期筛选语法错误
4. **表格行号不连续** - 重写headerData方法，行号始终按顺序显示
5. **净偏差计算不正确** - 修复net_offset.py重复代码和偏差金额获取逻辑

### 🎨 界面优化
1. **标题栏添加"制作人：裴盛清"** - 左边距调整到4px
2. **菜单栏完善** - 审核菜单包含"AI 审核"功能

---

## v41.3 (2026-06-03)

### ✨ 新增功能
- AI审核功能（Mock模式）
- 规则配置界面
- 管理看板

### 🐛 修复问题
- 修复多个bug

---

**制作人：裴盛清**
**更新日期：2026-06-06**
        """)
        layout.addWidget(text_edit)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def _on_alert(self, alerts_df):
        """收到预警时弹出通知"""
        count = len(alerts_df)
        reply = QMessageBox.question(
            self, "⚠️ 预警通知",
            f"发现 {count} 条新超阈值偏差，是否查看明细？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            from gui_pyside6.dialogs.alert_dialog import AlertDialog
            dialog = AlertDialog(alerts_df, self)
            dialog.exec()

    def closeEvent(self, event):
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.cancel()
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.cancel()
        if hasattr(self, 'alert_monitor') and self.alert_monitor.isRunning():
            self.alert_monitor.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
