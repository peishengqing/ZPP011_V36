# -*- coding: utf-8 -*-
"""
ZPP011 主窗口 (PySide6 迁移版)
布局：左侧控制面板 + 右侧表格+日志
功能：分析、AI审核、表格筛选排序、合计行、单位汇总、右键菜单、批量操作、替代料管理、导入导出等
"""
from gui_pyside6.widgets.toast import toast
import sys
import os
from datetime import datetime
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QProgressBar, QTextEdit, QMessageBox, QFileDialog,
    QTableView, QHeaderView, QMenu, QDialog, QDialogButtonBox, QSplitter,
    QScrollArea, QComboBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint,QTimer
from PySide6.QtGui import QAction, QFont, QShortcut, QKeySequence

from gui_pyside6.widgets.filter_panel import FilterPanel

# 导入自定义模块
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.controllers.analysis_controller import AnalysisController
from gui_pyside6.controllers.alt_controller import AltController
from gui_pyside6.controllers.audit_controller import AuditController
from gui_pyside6.controllers.export_controller import ExportController
from gui_pyside6.services.data_service import DataService
from gui_pyside6.dialogs.unit_summary_dialog import UnitSummaryDialog
from gui_pyside6.dialogs.rule_config_dialog import RuleConfigDialog
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
from gui_pyside6.dialogs.history_compare_dialog import HistoryCompareDialog
from gui_pyside6.dialogs.import_wizard_dialog import ImportWizard
from gui_pyside6.dialogs.benefit_report_dialog import BenefitReportDialog
from gui_pyside6.dialogs.health_check_dialog import HealthCheckDialog
from gui_pyside6.widgets.loading_dialog import LoadingDialog
from gui_pyside6.viewmodels.analysis_vm import AnalysisViewModel
from core.alert_monitor import AlertMonitor
from gui_pyside6.dialogs.alert_dialog import AlertDialog
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
        self._audit_df = None  # 临时占位，view_model 在 UI 搭建后初始化
        self.source_model = None
        self.proxy_model = None
        self.current_input_file = None
        self.analysis_output_path = None
        self.config_manager = ConfigManager()
        self._analysis_params = {}  # 缓存分析参数，用于导出完整Excel
        self.loading_dialog = None  # 加载对话框

        # UI 搭建（此时 view_model 还未创建，但 _setup_connections 等不依赖 view_model）
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_connections()
        self._refresh_alt_view()
        
        # 全局快捷键
        QShortcut(QKeySequence("F5"), self).activated.connect(self._start_analysis)
        QShortcut(QKeySequence("F6"), self).activated.connect(lambda: self.export_controller.export_current_table(self.view_model.df, self))
        QShortcut(QKeySequence("F7"), self).activated.connect(self._show_benefit_report)
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            lambda: self._batch_mark_selected_read(1)
        )
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._copy_previous_remark)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_table_fullscreen)

        # 多列联动排序状态
        self.sort_columns = []  # [(列索引, 升序标志), ...]
        
        self.statusBar().showMessage("就绪")

        # ViewModel (MVVM 状态管理)——必须在所有 _setup_xxx 之后，_start 之前创建
        self.view_model = AnalysisViewModel(self)
        self.view_model.df = pd.DataFrame()  # 初始化空数据
        self.view_model.data_changed.connect(self._on_view_model_data_changed)
        
        # 工厂数据缓存（与 controller 同步）
        self.factory_data = {}

        # 预警监控（不启动，等分析完成后由 _on_analysis_finished_ui 启动）
        from core.config_loader import config
        self.alert_monitor = AlertMonitor(
            data_source_func=lambda: self.view_model.df,
            threshold=config.get('alert.threshold_percent', 10.0),
            interval=config.get('alert.scan_interval_seconds', 60),
            only_alt=config.get('alert.only_alt_materials', True)
        )
        self.alert_monitor.alert_triggered.connect(self._on_new_alerts)

        # 初始化表格模型
        self._init_table_model()

    # ------------------- 数据处理服务回调 -------------------
    def _on_data_service_log(self, msg, level):
        """处理 DataService 的日志信号，包括变动提醒弹窗"""
        if level == "alert" and msg.startswith("变动提醒|"):
            count = msg.split("|")[1]
            QMessageBox.information(self, "变动提醒", f"发现 {count} 条已审核记录发生数值变动，已强制设为'未读'。")
        else:
            self.log(msg, level)

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
        title_label = QLabel("云南达利ZPP011生产偏差分析器 v42.5")
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
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(360)
        left_layout = QVBoxLayout(self.left_panel)
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

        # 工厂选择（分析完成后才启用）
        factory_group = QGroupBox("🏭 工厂选择")
        factory_layout = QVBoxLayout(factory_group)
        self.factory_combo = QComboBox()
        self.factory_combo.setEnabled(False)
        self.factory_combo.currentTextChanged.connect(self._on_factory_changed)
        factory_layout.addWidget(self.factory_combo)
        left_layout.addWidget(factory_group)

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
        body_layout.addWidget(self.left_panel)

        self.filter_panel = FilterPanel()
        self.filter_panel.filter_changed.connect(self._on_filter_panel_changed)
        # 用 QSplitter 包裹，让侧边栏宽度可拖拽调整
        self.right_splitter = QSplitter(Qt.Horizontal)
        self.right_splitter.setSizes([260, 740])
        self.right_splitter.addWidget(self.filter_panel)

        # 右侧内容容器
        right_container = QWidget()
        right_container_layout = QVBoxLayout(right_container)
        right_container_layout.setContentsMargins(6, 6, 6, 6)

        # ========== 右侧面板 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(4)

        # 分析进度
        self.progress_group = QGroupBox("分析进度")
        progress_layout = QVBoxLayout(self.progress_group)
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        right_layout.addWidget(self.progress_group)

        # 操作按钮
        self.action_group = QGroupBox("操作")
        action_layout = QHBoxLayout(self.action_group)
        self.start_btn = QPushButton("开始分析")
        self.cancel_btn = QPushButton("取消")
        self.open_dir_btn = QPushButton("打开目录")
        self.ppt_btn = QPushButton("生成PPT")
        self.excel_btn = QPushButton("生成表格")
        self.export_full_btn = QPushButton("导出完整Excel")
        self.refresh_net_btn = QPushButton("重算净偏差")
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.cancel_btn)
        action_layout.addWidget(self.open_dir_btn)
        action_layout.addWidget(self.ppt_btn)
        action_layout.addWidget(self.excel_btn)
        action_layout.addWidget(self.export_full_btn)
        action_layout.addWidget(self.refresh_net_btn)
        right_layout.addWidget(self.action_group)

        # 偏差明细与审核
        audit_group = QGroupBox("偏差明细与审核")
        audit_layout = QVBoxLayout(audit_group)
        audit_layout.setSpacing(4)
        audit_layout.setContentsMargins(6, 6, 6, 6)

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
        
        # ========== 多选区复制功能（仿 Excel） ==========
        # 启用多选（单元格级）
        self.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.table_view.setSelectionBehavior(QTableView.SelectItems)
        
        # 创建复制动作，覆盖 Ctrl+C
        copy_action = QAction("复制", self.table_view)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_selected_cells)
        self.table_view.addAction(copy_action)
        
        # ====================================================
        
        # 行高28px，默认显示15行
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        audit_layout.addWidget(self.table_view, 1)

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
        self.fullscreen_btn = QPushButton("⛶ 全屏")
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.clicked.connect(self._toggle_table_fullscreen)
        summary_layout.addWidget(self.fullscreen_btn)
        audit_layout.addLayout(summary_layout)

        right_container_layout.addWidget(audit_group)
        self.right_splitter.addWidget(right_container)

        right_layout.addWidget(self.right_splitter)

        # 运行日志
        self.log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(self.log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(400)
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(self.log_group)

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
        alert_rule_action = QAction("预警规则配置", self)
        alert_rule_action.triggered.connect(self._configure_alert_rules)
        tools_menu.addAction(alert_rule_action)

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
        help_menu.addSeparator()
        health_action = QAction("系统健康检查", self)
        health_action.triggered.connect(self._show_health_check)
        help_menu.addAction(health_action)
        help_menu.addSeparator()
        advanced_ppt_action = QAction("生成详细分析报告(专业版)", self)
        advanced_ppt_action.triggered.connect(self._generate_advanced_report)
        help_menu.addAction(advanced_ppt_action)

        # ---------- 创建 AnalysisController ----------
        self.analysis_controller = AnalysisController(self)
        self.analysis_controller.analysis_started.connect(self._on_analysis_ui_start)
        self.analysis_controller.progress_updated.connect(self._on_analysis_progress_ui)
        self.analysis_controller.log_message.connect(self.log)
        self.analysis_controller.analysis_finished.connect(self._on_analysis_finished_ui)
        self.analysis_controller.analysis_error.connect(self._on_analysis_error_ui)
        self.analysis_controller.analysis_cancelled.connect(self._on_analysis_cancelled_ui)
        # --------------------------------------------

        # ---------- 创建 AltController ----------
        self.alt_controller = AltController(self)
        self.alt_controller.data_changed.connect(self._refresh_alt_view)
        # --------------------------------------------

        # ---------- 创建 DataService ----------
        self.data_service = DataService(alt_controller=self.alt_controller)
        self.data_service.log_signal.connect(self.log)
        # 监听变动提醒信号（用于弹窗）
        self.data_service.log_signal.connect(self._on_data_service_log)
        # --------------------------------------------

        # ---------- 创建 AuditController ----------
        self.audit_controller = AuditController(self)
        self.audit_controller.log_message.connect(self.log)
        self.audit_controller.progress_started.connect(self._on_ai_ui_start)
        self.audit_controller.progress_updated.connect(self._on_ai_progress_ui)
        self.audit_controller.progress_finished.connect(self._on_ai_finished_ui)
        self.audit_controller.progress_error.connect(self._on_ai_error_ui)
        self.audit_controller.audit_data_changed.connect(self._on_audit_data_changed)
        # --------------------------------------------

        # ---------- 创建 ExportController ----------
        self.export_controller = ExportController(self)
        self.export_controller.log_message.connect(self.log)
        # --------------------------------------------

    # ------------------- 分析启动 -------------------
    def _start_analysis(self):
        """启动分析（委托给 AnalysisController）"""
        if not self.current_input_file:
            QMessageBox.warning(self, "提示", "请先选择输入文件")
            return
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            QMessageBox.information(self, "提示", "分析任务已在后台运行")
            return

        # 显示加载对话框
        self.loading_dialog = LoadingDialog("正在分析数据，请稍候...", self)
        self.loading_dialog.show()
        QApplication.processEvents()

        start_date = self.start_date_edit.text().strip()
        end_date = self.end_date_edit.text().strip()
        material_search = self.material_search_edit.text().strip()
        self.analysis_controller.start_analysis(
            self.current_input_file, self.alt_controller.get_pairs(),
            start_date, end_date, material_search
        )

    def _setup_connections(self):
        self.start_btn.clicked.connect(self._start_analysis)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        self.open_dir_btn.clicked.connect(self._open_output_dir)
        # 连接导出相关按钮到 ExportController
        self.ppt_btn.clicked.connect(lambda: self.export_controller.generate_simple_ppt(
            self.view_model.df, self.analysis_output_path, self.output_dir_edit.text().strip(), self, self.log
        ))
        self.excel_btn.clicked.connect(lambda: self.export_controller.export_current_table(self.view_model.df, self))
        self.export_full_btn.clicked.connect(lambda: self.export_controller.export_full_excel(
            self.view_model.df, self.current_input_file, self._analysis_params, self
        ))
        # 连接双击信号（已读/未读切换）
        self.refresh_net_btn.clicked.connect(self._recalculate_net_offset)
        self.table_view.doubleClicked.connect(self._on_cell_double_clicked)

    # ------------------- 分析 UI 回调（由 Controller 触发） -------------------
    def _on_analysis_ui_start(self):
        """分析开始时的界面准备"""
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.start_btn.setEnabled(False)
        self._countdown_seconds = 0
        self._current_step = "准备中"
        if not hasattr(self, '_countdown_timer'):
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

    def _on_analysis_progress_ui(self, percent, step_name):
        self.progress_bar.setValue(percent)
        self._current_step = step_name
        m, s = divmod(self._countdown_seconds, 60)
        self.progress_label.setText(f"{step_name} {percent}% | ⏱ {m:02d}:{s:02d}")

    def _on_analysis_finished_ui(self, df):
        # 关闭加载对话框
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        elapsed = self._format_elapsed()
        self.progress_label.setText(f"完成 ({elapsed})")
        from gui_pyside6.widgets.toast import toast
        toast(f"✅ 分析完成，共 {len(df)} 条记录 ({elapsed})", 'success', parent=self)
        self.statusBar().showMessage("分析完成，正在加载结果...")
        # 更新工厂下拉框
        factory_list = self.analysis_controller.get_factory_list()
        self.factory_combo.clear()
        if factory_list:
            self.factory_combo.addItems(factory_list)
            self.factory_combo.setEnabled(True)
            # 默认选中第一个
            if factory_list:
                self._on_factory_changed(factory_list[0])
        else:
            self.factory_combo.setEnabled(False)
        
        try:
            if '偏差率' in df.columns:
                df['偏差率'] = pd.to_numeric(df['偏差率'], errors='coerce')
            # Preprocess data
            processed_df = self.data_service.preprocess_audit_data(df, self.view_model.df)
            # Update table model
            self.source_model.setDataFrame(processed_df)
            # Trigger unified refresh via ViewModel
            self.view_model.df = processed_df
            # 更新分析参数缓存（供导出完整Excel使用）
            self._analysis_params = self.analysis_controller.get_analysis_params()
            # 保存临时Excel
            import tempfile
            temp_dir = os.path.join(tempfile.gettempdir(), "zpp011_analysis")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            df.to_excel(temp_path, sheet_name='完整偏差明细', index=False)
            self._analysis_output_path = temp_path
            self.statusBar().showMessage(f"分析完成，共加载 {len(df)} 条记录")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载结果失败: {e}")


        # 启动预警监控（如果未启动）
        if not self.alert_monitor.isRunning():
            self.alert_monitor.start()
    def _on_new_alerts(self, alerts_df):
        """收到新预警，弹窗询问是否查看（仅替代料，显示指定列）"""
        count = len(alerts_df)
        reply = QMessageBox.question(
            self, "⚠️ 预警通知",
            f"发现 {count} 条新超阈值偏差（替代料），是否查看明细？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            current_df = self.view_model.df
            if current_df is not None and not current_df.empty and '偏差率(%)' in current_df.columns:
                # 筛选：替代料且偏差率 >10%
                if '是否替代料' in current_df.columns:
                    all_alerts = current_df[
                        (current_df['偏差率(%)'].abs() > 10) &
                        (current_df['是否替代料'] == '是')
                    ].copy()
                else:
                    all_alerts = current_df[current_df['偏差率(%)'].abs() > 10].copy()

                if all_alerts.empty:
                    QMessageBox.information(self, "提示", "没有替代料预警记录")
                    return

                # 只保留看板需要的列
                required_cols = ['订单日期', '流程订单', '物料编码', '物料名称', '车间',
                                 '定额', '实际', '偏差数量', '_read', 'data_id']
                available_cols = [c for c in required_cols if c in all_alerts.columns]
                all_alerts = all_alerts[available_cols]

                # 将 _read 转换为状态文本
                if '_read' in all_alerts.columns:
                    all_alerts['状态'] = all_alerts['_read'].map({0: '○ 未读', 1: '✓ 已读'})
                    cols = ['状态'] + [c for c in all_alerts.columns if c != '状态']
                    all_alerts = all_alerts[cols]

                from gui_pyside6.dialogs.alert_dialog import AlertDialog
                dialog = AlertDialog(all_alerts, self)
                dialog.exec()

    def locate_record(self, record):
        """定位到主表格的某条记录"""
        if self.proxy_model is None or self.source_model is None:
            return
        target_date = record.get('订单日期')
        target_order = record.get('流程订单')
        target_material = record.get('物料编码')
        source_df = self.source_model.getDataFrame()
        for row in range(len(source_df)):
            r = source_df.iloc[row]
            if (str(r.get('订单日期')) == str(target_date) and
                str(r.get('流程订单')) == str(target_order) and
                str(r.get('物料编码')) == str(target_material)):
                proxy_index = self.proxy_model.mapFromSource(self.source_model.index(row, 0))
                if proxy_index.isValid():
                    self.table_view.scrollTo(proxy_index, QAbstractItemView.PositionAtCenter)
                    self.table_view.selectRow(proxy_index.row())
                break

    def _on_analysis_error_ui(self, error_msg):
        # 关闭加载对话框
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.progress_label.setText("错误")
        from gui_pyside6.widgets.toast import toast
        toast("❌ 分析失败，请查看日志", 'error', parent=self)
        QMessageBox.critical(self, "错误", error_msg)

    def _on_analysis_cancelled_ui(self):
        self.progress_bar.setVisible(False)
        self.progress_label.setText("已取消")
        self.start_btn.setEnabled(True)
        self.log("分析已取消", "info")

    # ------------------- AI 审核 UI 回调（由 AuditController 触发） -------------------
    def _on_ai_ui_start(self):
        """AI审核开始时的界面准备"""
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self._countdown_seconds = 0
        self._current_step = "AI审核"
        if not hasattr(self, '_countdown_timer'):
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

    def _on_ai_progress_ui(self, current, total):
        """AI审核进度更新"""
        percent = int(current / total * 100) if total else 0
        self.progress_bar.setValue(percent)
        m, s = divmod(self._countdown_seconds, 60)
        self.progress_label.setText(f"AI审核: {current}/{total} | ⏱ {m:02d}:{s:02d}")

    def _on_ai_finished_ui(self, updated_df):
        """AI审核完成后的界面更新"""
        # 关闭加载对话框
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        elapsed = self._format_elapsed()
        self.progress_label.setText(f"AI审核完成 ({elapsed})")
        from gui_pyside6.widgets.toast import toast
        toast(f"✅ AI审核完成 ({elapsed})", 'success', parent=self)

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

        # Preprocess data
        processed_df = self.data_service.preprocess_audit_data(updated_df, self.view_model.df)
        # Update table model
        self.source_model.setDataFrame(processed_df)
        # Trigger unified refresh via ViewModel
        self.view_model.df = processed_df
        self.progress_bar.setVisible(False)
        self.progress_label.setText("就绪")
        if 'AI建议' not in updated_df.columns or updated_df['AI建议'].replace('', pd.NA).notna().sum() > 0:
            QMessageBox.information(self, "完成", "AI审核已完成")

    def _on_ai_error_ui(self, error_msg):
        """AI审核错误时的界面更新"""
        # 关闭加载对话框
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        print("=" * 60)
        print("AI审核错误:")
        print(error_msg)
        print("=" * 60)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("错误")
        QMessageBox.critical(self, "错误", error_msg)

    def _on_audit_data_changed(self, updated_df):
        """当审核数据发生变更时（批量操作后），刷新界面"""
        # Preprocess data
        processed_df = self.data_service.preprocess_audit_data(updated_df, self.view_model.df)
        # Update table model
        self.source_model.setDataFrame(processed_df)
        # Trigger unified refresh via ViewModel
        self.view_model.df = processed_df

    # -----------------------------------------------------------------------

    # ------------------- 排序 -------------------
    def _on_sort_indicator_changed(self, logical_index, order):
        """多列联动排序（Ctrl+点击追加排序）"""
        print(f"[DEBUG] _on_sort_indicator_changed called: logical_index={logical_index}, order={order}")
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
        print(f"[DEBUG] _apply_multi_sort called, sort_columns={self.sort_columns}")
        if not self.sort_columns:
            print("[DEBUG] sort_columns empty, returning")
            return
        if not hasattr(self, 'source_model') or self.source_model is None:
            print("[DEBUG] source_model is None, returning")
            return
        df = self.source_model.getDataFrame()
        if df is None or df.empty:
            print("[DEBUG] df is None or empty, returning")
            return
        print(f"[DEBUG] df columns={list(df.columns)}")
        sort_args = []
        for col, asc in self.sort_columns:
            if col == 0:   # 跳过状态列
                continue
            if col < 0 or col >= len(df.columns):
                continue
            col_name = df.columns[col]
            sort_args.append((col_name, asc))
        print(f"[DEBUG] sort_args={sort_args}")
        if sort_args:
            cols = [c for c, _ in sort_args]
            asc = [a for _, a in sort_args]
            # 对 object 类型列转 str，避免 bytes/int 混合比较
            for c in cols:
                if df[c].dtype == object:
                    df[c] = df[c].apply(lambda x: x.decode('utf-8', errors='replace') if isinstance(x, bytes) else str(x) if not isinstance(x, str) else x)
            # 百分比列转数字排序，其余保持原样
            sort_keys = {}
            for c in cols:
                has_pct = df[c].astype(str).str.contains('%', na=False).any()
                print(f"[DEBUG] col={c!r}, dtype={df[c].dtype}, has_pct={has_pct}")
                if has_pct:  # 只要列里有 % 就按数值排序
                    numeric_vals = pd.to_numeric(df[c].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
                    sort_keys[c] = numeric_vals
                    print(f"[DEBUG] sort_keys[{c!r}] = {numeric_vals.tolist()[:5]}...")
            print(f"[DEBUG] sort_keys keys={list(sort_keys.keys())}")
            if sort_keys:
                df_sorted = df.sort_values(by=cols, ascending=asc, key=lambda col: sort_keys.get(col.name, col), na_position='last')
            else:
                df_sorted = df.sort_values(by=cols, ascending=asc, na_position='last')
            print(f"[DEBUG] df_sorted first 5 rows: {df_sorted[cols[0]].head().tolist()}")
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
        """刷新左侧替代料表格（从 controller 获取数据）"""
        pairs = self.alt_controller.get_pairs()
        self.alt_table.setRowCount(0)
        for idx, (a, b) in enumerate(pairs):
            a_display, a_tip = self.alt_controller.format_material_short(a)
            b_display, b_tip = self.alt_controller.format_material_short(b)
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
        self.alt_count_label.setText(f"共 {len(pairs)} 对")
        self.alt_table.resizeColumnsToContents()
        # 设置最小列宽，防止过窄
        self.alt_table.setColumnWidth(0, max(80, self.alt_table.columnWidth(0)))
        self.alt_table.setColumnWidth(2, max(80, self.alt_table.columnWidth(2)))

    def _on_alt_rows_moved(self, parent, start, end, destination, row):
        new_pairs = []
        pairs = self.alt_controller.get_pairs()
        for r in range(self.alt_table.rowCount()):
            item = self.alt_table.item(r, 0)
            if item:
                orig_idx = item.data(Qt.UserRole)
                if orig_idx is not None and orig_idx < len(pairs):
                    new_pairs.append(pairs[orig_idx])
        if new_pairs and len(new_pairs) == len(pairs):
            self.alt_controller.set_pairs_from_list(new_pairs)

    def _add_alt_pair(self):
        self.alt_controller.show_add_dialog(self)

    def _delete_alt_pair(self):
        current_row = self.alt_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先选中要删除的配对")
            return
        item = self.alt_table.item(current_row, 0)
        if item:
            idx = item.data(Qt.UserRole)
            if idx is not None:
                self.alt_controller.delete_pair(idx)

    def _reset_alt_pairs(self):
        self.alt_controller.reset_pairs()

    def _import_alt_pairs(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入替代料配对", "", "JSON files (*.json);;Excel files (*.xlsx *.xls)")
        if not file_path:
            return
        if file_path.endswith('.json'):
            if self.alt_controller.import_from_file(file_path, self):
                pass  # 成功，刷新由信号自动处理
        else:
            wizard = ImportWizard(self, self.alt_controller.get_pairs(), None,
                                  on_alt_changed=self._refresh_alt_view,
                                  on_rules_changed=None)
            wizard.exec()

    def _export_alt_pairs(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出替代料配对", "alt_pairs.json", "JSON (*.json)")
        if file_path:
            if self.alt_controller.export_to_file(file_path):
                QMessageBox.information(self, "成功", f"已导出到 {file_path}")
            else:
                QMessageBox.critical(self, "错误", "导出失败")

    def _zoom_alt_table(self):
        self.alt_controller.show_zoom_window(self)

    def _sort_alt_pairs(self):
        self.alt_controller.sort_pairs()
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

    def _toggle_table_fullscreen(self):
        """切换审核表格全屏模式（隐藏左侧面板、进度、操作和运行日志）"""
        full = self.fullscreen_btn.isChecked()
        if full:
            self.left_panel.setVisible(False)
            self.progress_group.setVisible(False)
            self.action_group.setVisible(False)
            self.log_group.setVisible(False)
            self.filter_panel.setVisible(False)
            self.fullscreen_btn.setText("⛶ 退出全屏")
            self.statusBar().showMessage("全屏模式 (F11 退出)", 3000)
        else:
            self.left_panel.setVisible(True)
            self.progress_group.setVisible(True)
            self.action_group.setVisible(True)
            self.log_group.setVisible(True)
            self.filter_panel.setVisible(True)
            self.fullscreen_btn.setText("⛶ 全屏")
            self.statusBar().showMessage("已退出全屏", 2000)

    # ------------------- 数据加载与表格 -------------------
    def _init_table_model(self):
        """Initialize table model (one-time setup)"""
        self.source_model = DataFrameModel()
        self.proxy_model = AuditProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)
        
        # Connect selection changed signal
        try:
            self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass
        
        # Connect data changed signals
        self.source_model.dataChanged.connect(self._update_summary)
        self.proxy_model.layoutChanged.connect(self._update_summary)
        
        # Column width initialization
        self.table_view.resizeColumnsToContents()
        self.table_view.setColumnWidth(0, 35)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.lock_btn.setChecked(False)
        self.log("Table model initialized", "info")


    def _on_view_model_data_changed(self):
        """ViewModel 数据变化时，刷新所有依赖的 UI 组件"""
        df = self.view_model.df
        if df is None or df.empty:
            # 清空界面
            self._update_summary()
            self._update_stat_cards(pd.DataFrame())
            self.filter_panel.update_options(pd.DataFrame())
            return
        
        # 刷新合计行
        self._update_summary()
        # 刷新统计卡片
        self._update_stat_cards(df)
        # 刷新筛选面板下拉选项
        self.filter_panel.update_options(df)

    def log(self, msg, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")

    # ------------------- AI 审核 -------------------
    def _run_ai_audit(self):
        """启动AI审核（委托给 AuditController）"""
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return

        # 显示加载对话框
        self.loading_dialog = LoadingDialog("AI 正在审核，请稍候...", self)
        self.loading_dialog.show()
        QApplication.processEvents()

        self.audit_controller.run_ai_audit(self.view_model.df)

    # ------------------- 导出 -------------------


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
        copy_action.triggered.connect(lambda: self.audit_controller.copy_material_code(row_data, self.statusBar().showMessage))
        menu.addSeparator()
        
        # 批量标记已读/未读
        menu.addSeparator()
        mark_read_action = menu.addAction("标记为已读")
        mark_read_action.triggered.connect(lambda: self.audit_controller.batch_mark_read(selected_rows, self.source_model, 1, self.statusBar().showMessage))
        mark_unread_action = menu.addAction("标记为未读")
        mark_unread_action.triggered.connect(lambda: self.audit_controller.batch_mark_read(selected_rows, self.source_model, 0, self.statusBar().showMessage))
        
        menu.addSeparator()
        batch_status = menu.addAction("批量改状态")
        batch_status.triggered.connect(lambda: self.audit_controller.batch_change_status(selected_rows, self))
        batch_remark = menu.addAction("批量填备注")
        batch_remark.triggered.connect(lambda: self.audit_controller.batch_remark(selected_rows, self))
        batch_export = menu.addAction("批量导出")
        batch_export.triggered.connect(lambda: self._batch_export_wrapper(selected_rows))
        
        # 添加"复制选中区域"选项（仿 Excel）
        menu.addSeparator()
        copy_region_action = menu.addAction("复制选中区域")
        copy_region_action.triggered.connect(self.copy_selected_cells)
        
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _batch_export_wrapper(self, rows):
        """批量导出包装方法（委托给 AuditController）"""
        df_subset = self.view_model.df.iloc[rows].copy()
        self.audit_controller.batch_export(rows, df_subset, self)

    # ------------------- 其他功能 -------------------
    def _open_rule_config(self):
        rules_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'system', 'rules.json')
        def on_rules_changed():
            self.audit_controller.rule_engine.load_rules()
            if self.view_model.df is not None:
                # 重新处理当前数据（规则已更新）
                if self.view_model.df is not None:
                    processed_df = self.data_service.preprocess_audit_data(self.view_model.df, self.view_model.df)
                    self.source_model.setDataFrame(processed_df)
                    self.view_model.df = processed_df
        dialog = RuleConfigDialog(self, rules_path, self.config_manager, on_rules_changed)
        dialog.exec()

    def _on_rules_changed_simple(self):
        """规则变化时的回调（简化版）"""
        self.audit_controller.rule_engine.load_rules()
        if self.view_model.df is not None:
            processed_df = self.data_service.preprocess_audit_data(self.view_model.df, self.view_model.df)
            self.source_model.setDataFrame(processed_df)
            self.view_model.df = processed_df

    def _open_import_wizard(self):
        rules_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'system', 'rules.json')
    def _show_health_check(self):
        """显示系统健康检查面板"""
        dialog = HealthCheckDialog(self)
        dialog.exec()

    def _show_benefit_report(self):
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        dialog = BenefitReportDialog(self, self.view_model.df)
        dialog.exec()

    def _configure_alert_rules(self):
        """打开预警规则配置对话框，保存后实时生效"""
        from gui_pyside6.dialogs.alert_rule_config_dialog import AlertRuleConfigDialog
        from core.config_loader import config
        import yaml
        from pathlib import Path

        current_threshold = config.get('alert.threshold_percent', 10.0)
        current_only_alt = config.get('alert.only_alt_materials', True)

        dialog = AlertRuleConfigDialog(self, current_threshold, current_only_alt)
        if dialog.exec() != QDialog.Accepted:
            return

        new_cfg = dialog.get_config()
        try:
            # 1. 更新内存配置
            full_config = config._config
            full_config.setdefault('alert', {})
            full_config['alert']['threshold_percent'] = new_cfg['threshold']
            full_config['alert']['only_alt_materials'] = new_cfg['only_alt']

            # 2. 写回配置文件
            cfg_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
            with open(cfg_path, 'w', encoding='utf-8') as f:
                yaml.dump(full_config, f, allow_unicode=True)

            # 3. 重新加载配置
            config.reload()

            # 4. 更新 AlertMonitor
            if hasattr(self, 'alert_monitor'):
                self.alert_monitor.update_config(
                    threshold=new_cfg['threshold'],
                    only_alt=new_cfg['only_alt']
                )

            # 5. 更新表格预警高亮（通知代理模型重新评估）
            if self.proxy_model is not None:
                if hasattr(self.proxy_model, 'set_alert_threshold'):
                    self.proxy_model.set_alert_threshold(new_cfg['threshold'])
                self.proxy_model.invalidateFilter()
                self.proxy_model.layoutChanged.emit()

            QMessageBox.information(self, "成功", "预警规则已更新，实时生效。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")

    def _show_history_compare(self):
        dialog = HistoryCompareDialog(self)
        dialog.exec()

    def _open_dashboard(self):
        dialog = DashboardDialog(self._get_current_audit_data(), None, self, main_window=self)
        dialog.drill_down_signal.connect(self._on_drill_down)
        dialog.exec()

    def _on_factory_changed(self, factory_name):
        """切换工厂，更新表格数据（跳过重复预处理）"""
        if not factory_name:
            return
        df = self.analysis_controller.factory_data.get(factory_name)
        if df is not None:
            # 直接设置源模型数据，不经过 DataService 预处理（分析时已完成）
            if self.source_model is None:
                from gui_pyside6.models.data_frame_model import DataFrameModel
                self.source_model = DataFrameModel()
                from gui_pyside6.models.audit_proxy_model import AuditProxyModel
                self.proxy_model = AuditProxyModel()
                self.proxy_model.setSourceModel(self.source_model)
                self.table_view.setModel(self.proxy_model)
            self.source_model.setDataFrame(df)
            self.view_model.df = df
            self._update_summary()
            self._update_stat_cards(df)
            self.filter_panel.update_options(df)
            self.statusBar().showMessage(f"已切换到工厂：{factory_name}", 2000)
        else:
            self.statusBar().showMessage(f"工厂 {factory_name} 数据为空", 2000)

    def _get_current_audit_data(self):
        return self.view_model.df.copy() if self.view_model.df is not None else pd.DataFrame()

    def _on_filter_panel_changed(self, filters: dict):
        """侧边栏筛选条件变化时的处理"""
        if self.proxy_model is None or self.view_model.df is None:
            return
        self.proxy_model.setCustomFilters(filters)
        # 合计行会在 proxy_model.layoutChanged 信号中自动更新
        self._update_summary()

    def _show_unit_summary(self):
        """显示单位汇总对话框"""
        df = self.view_model.df
        if df is None or df.empty:
            QMessageBox.information(self, "提示", "无数据")
            return
        from gui_pyside6.dialogs.unit_summary_dialog import UnitSummaryDialog
        dialog = UnitSummaryDialog(self, df)
        dialog.exec()

    def _export_current_table(self):
        """导出当前表格到 Excel"""
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出当前表格", "偏差明细.xlsx", "Excel files (*.xlsx)")
        if file_path:
            try:
                self.view_model.df.to_excel(file_path, index=False)
                QMessageBox.information(self, "成功", f"已导出到 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _show_about(self):
        """显示关于对话框（含版本日志）"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame)
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 - ZPP011 生产偏差分析器")
        dialog.setMinimumSize(680, 520)
        dialog.setStyleSheet("QDialog { background-color: #F5F5F5; }")
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        about_frame = QFrame()
        about_frame.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2B5EA7, stop:1 #1A3A6B);")
        about_layout = QVBoxLayout(about_frame)
        about_layout.setContentsMargins(28, 24, 28, 20)
        title_row = QHBoxLayout()
        icon_label = QLabel("🏭")
        icon_label.setStyleSheet("font-size: 28px; background: transparent;")
        title_row.addWidget(icon_label)
        title_label = QLabel("ZPP011 生产偏差分析器")
        title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        title_row.addWidget(title_label)
        title_row.addStretch()
        about_layout.addLayout(title_row)
        ver_label = QLabel("PySide6 迁移版 v42.3")
        ver_label.setStyleSheet("color: #A8C8E8; font-size: 13px; padding-left: 36px;")
        about_layout.addWidget(ver_label)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #5A8AC8;")
        line.setFixedHeight(1)
        about_layout.addWidget(line)
        desc_label = QLabel("功能：偏差分析 · AI审核 · 规则配置 · 管理看板 · 批量操作")
        desc_label.setStyleSheet("color: #D0D0D0; font-size: 12px; padding-left: 36px;")
        about_layout.addWidget(desc_label)
        author_label = QLabel("制作人：裴盛清")
        author_label.setStyleSheet("color: #D0D0D0; font-size: 12px; padding-left: 36px;")
        about_layout.addWidget(author_label)
        date_label = QLabel("更新日期：2026-06-08")
        date_label.setStyleSheet("color: #A0A0A0; font-size: 11px; padding-left: 36px;")
        about_layout.addWidget(date_label)
        main_layout.addWidget(about_frame)
        log_frame = QFrame()
        log_frame.setStyleSheet("background-color: white;")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(16, 10, 16, 10)
        log_title = QLabel("📋 版本更新日志")
        log_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2B5EA7;")
        log_layout.addWidget(log_title)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown("""
## v42.3 (2026-06-08)
### ✨ 新增功能
- 多工厂数据隔离与对比
- 实时预警看板 + 预警行高亮
- 专业版PPT报告 (20+页)
- 表格虚拟滚动性能优化
### 🐛 修复问题
- 修复多处MVVM集成缺失
- 修复信号连接错误
        """)
        text_edit.setStyleSheet("border: 1px solid #E0E0E0; border-radius: 6px; padding: 8px;")
        log_layout.addWidget(text_edit)
        main_layout.addWidget(log_frame)
        btn_frame = QFrame()
        btn_frame.setStyleSheet("background-color: #F0F0F0; border-top: 1px solid #E0E0E0;")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(88, 34)
        close_btn.setStyleSheet("background-color: #2B5EA7; color: white; border-radius: 6px;")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        main_layout.addWidget(btn_frame)
        dialog.exec()

    def _on_drill_down(self, filter_key, filter_value):
        if self.view_model.df is None:
            return
        cols = self.source_model.getDataFrame().columns
        if filter_key in cols:
            idx = cols.get_loc(filter_key)
            self.proxy_model.setFilter(idx, filter_value)
            self.statusBar().showMessage(f"已下钻至物料类型：{filter_value}", 3000)

    def _update_summary(self):
        """更新底部合计行（定额、实际、偏差金额、偏差数量）"""
        if self.view_model.df is None or self.view_model.df.empty:
            self.summary_quota.setText("定额: 0.00")
            self.summary_actual.setText("实际: 0.00")
            self.summary_amount.setText("偏差金额: 0.00")
            self.summary_qty.setText("偏差数量: 0.00")
            return
        df = self.view_model.df
        quota_col = next((c for c in ['定额', '数量-定额', 'quota'] if c in df.columns), None)
        actual_col = next((c for c in ['实际', '数量-实际', 'actual'] if c in df.columns), None)
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
        if amount_col == '净偏差':
            self.summary_amount.setText(f"净偏差(抵消后): {amount_sum:,.2f}")
        else:
            self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")
        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")

    def _recalculate_net_offset(self):
        """重算净偏差（基于当前数据重新应用替代料配对）"""
        df = self.view_model.df
        if df is None or df.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        from analysis.net_offset import apply_net_offset
        alt_pairs = self.alt_controller.get_pairs()
        if not alt_pairs:
            QMessageBox.information(self, "提示", "没有替代料配对，无需重算")
            return
        try:
            new_df = apply_net_offset(df, alt_pairs, group_key=['订单日期', '流程'])
            self.view_model.df = new_df
            # 不需要手动刷新，data_changed 信号会触发 _on_view_model_data_changed 统一刷新
            self.statusBar().showMessage("净偏差已重新计算", 2000)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重算净偏差失败: {e}")

    def _update_stat_cards(self, df):
        """更新统计卡片（总记录、偏差>10%、需补备注、已审核）"""
        total = len(df)
        high = (df['偏差率(%)'].abs() > 10).sum() if '偏差率(%)' in df.columns else 0
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

    # ------------------- 选中单元格合计 -------------------
    def _on_selection_changed(self, selected, deselected):
        """当选中的单元格变化时，计算选中数值列的合计"""
        if self.proxy_model is None or self.view_model.df is None:
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

    # ------------------- 取消分析 -------------------
    def _cancel_analysis(self):
        """取消分析和AI审核"""
        cancelled = False
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            self.analysis_controller.cancel()
            cancelled = True
        if self.audit_controller.ai_worker and self.audit_controller.ai_worker.isRunning():
            self.audit_controller.cancel_ai_audit()
            cancelled = True
        if cancelled:
            # 关闭加载对话框
            if self.loading_dialog:
                self.loading_dialog.accept()
                self.loading_dialog = None
            self.progress_bar.setVisible(False)
            self.progress_label.setText("已取消")
            self.start_btn.setEnabled(True)
            self.log("操作已取消", "info")

    def _batch_mark_selected_read(self, is_read=1):
        """批量标记选中行为已读/未读"""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            self.statusBar().showMessage("请先选中要标记的行", 2000)
            return
        rows = set()
        for idx in selection:
            source_idx = self.proxy_model.mapToSource(idx)
            rows.add(source_idx.row())
        self.audit_controller.batch_mark_read(list(rows), self.source_model, is_read, self.statusBar().showMessage)

    # ------------------- 复制上一行备注（快捷键） -------------------
    def _copy_previous_remark(self):
        """复制当前选中行的上一行备注到当前行"""
        current = self.table_view.currentIndex()
        if not current.isValid():
            self.statusBar().showMessage("请先选中一行", 2000)
            return
        source_idx = self.proxy_model.mapToSource(current)
        row = source_idx.row()
        self.audit_controller.copy_previous_remark(row, self.source_model, self.statusBar().showMessage)

    # ------------------- 预警通知 -------------------
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
        
    # ------------------- 合计行与统计卡片 -------------------
    def _update_summary(self):
        """更新底部合计行（定额、实际、偏差金额、偏差数量）"""
        if self.view_model.df is None or self.view_model.df.empty:
            self.summary_quota.setText("定额: 0.00")
            self.summary_actual.setText("实际: 0.00")
            self.summary_amount.setText("偏差金额: 0.00")
            self.summary_qty.setText("偏差数量: 0.00")
            return
        df = self.view_model.df
        quota_col = next((c for c in ['定额', '数量-定额', 'quota'] if c in df.columns), None)
        actual_col = next((c for c in ['实际', '数量-实际', 'actual'] if c in df.columns), None)
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
        if amount_col == '净偏差':
            self.summary_amount.setText(f"净偏差(抵消后): {amount_sum:,.2f}")
        else:
            self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")
        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")

    def _update_stat_cards(self, df):
        """更新统计卡片（总记录、偏差>10%、需补备注、已审核）"""
        total = len(df)
        high = (df['偏差率(%)'].abs() > 10).sum() if '偏差率(%)' in df.columns else 0
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

    # ------------------- 选中单元格合计 -------------------
    def _on_selection_changed(self, selected, deselected):
        """当选中的单元格变化时，计算选中数值列的合计"""
        if self.proxy_model is None or self.view_model.df is None:
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

    # ------------------- 取消分析 -------------------
    def _cancel_analysis(self):
        """取消分析和AI审核"""
        cancelled = False
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            self.analysis_controller.cancel()
            cancelled = True
        if self.audit_controller.ai_worker and self.audit_controller.ai_worker.isRunning():
            self.audit_controller.cancel_ai_audit()
            cancelled = True
        if cancelled:
            self.progress_bar.setVisible(False)
            self.progress_label.setText("已取消")
            self.start_btn.setEnabled(True)
            self.log("操作已取消", "info")

    # ------------------- 批量标记已读/未读（快捷键） -------------------
    def _batch_mark_selected_read(self, is_read=1):
        """批量标记选中行为已读/未读"""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            self.statusBar().showMessage("请先选中要标记的行", 2000)
            return
        rows = set()
        for idx in selection:
            source_idx = self.proxy_model.mapToSource(idx)
            rows.add(source_idx.row())
        self.audit_controller.batch_mark_read(list(rows), self.source_model, is_read, self.statusBar().showMessage)

    # ------------------- 复制上一行备注（快捷键） -------------------
    def _copy_previous_remark(self):
        """复制当前选中行的上一行备注到当前行"""
        current = self.table_view.currentIndex()
        if not current.isValid():
            self.statusBar().showMessage("请先选中一行", 2000)
            return
        source_idx = self.proxy_model.mapToSource(current)
        row = source_idx.row()
        self.audit_controller.copy_previous_remark(row, self.source_model, self.statusBar().showMessage)

    # ------------------- 预警通知 -------------------
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


    # ------------------- 合计行与统计卡片 -------------------
    def _update_summary(self):
        """更新底部合计行（定额、实际、偏差金额、偏差数量）"""
        if self.view_model.df is None or self.view_model.df.empty:
            self.summary_quota.setText("定额: 0.00")
            self.summary_actual.setText("实际: 0.00")
            self.summary_amount.setText("偏差金额: 0.00")
            self.summary_qty.setText("偏差数量: 0.00")
            return
        df = self.view_model.df
        quota_col = next((c for c in ['定额', '数量-定额', 'quota'] if c in df.columns), None)
        actual_col = next((c for c in ['实际', '数量-实际', 'actual'] if c in df.columns), None)
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
        if amount_col == '净偏差':
            self.summary_amount.setText(f"净偏差(抵消后): {amount_sum:,.2f}")
        else:
            self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")
        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")

    def _update_stat_cards(self, df):
        """更新统计卡片（总记录、偏差>10%、需补备注、已审核）"""
        total = len(df)
        high = (df['偏差率(%)'].abs() > 10).sum() if '偏差率(%)' in df.columns else 0
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

    # ------------------- 选中单元格合计 -------------------
    def _on_selection_changed(self, selected, deselected):
        """当选中的单元格变化时，计算选中数值列的合计"""
        if self.proxy_model is None or self.view_model.df is None:
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

    # ------------------- 取消分析 -------------------
    def _cancel_analysis(self):
        """取消分析和AI审核"""
        cancelled = False
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            self.analysis_controller.cancel()
            cancelled = True
        if self.audit_controller.ai_worker and self.audit_controller.ai_worker.isRunning():
            self.audit_controller.cancel_ai_audit()
            cancelled = True
        if cancelled:
            self.progress_bar.setVisible(False)
            self.progress_label.setText("已取消")
            self.start_btn.setEnabled(True)
            self.log("操作已取消", "info")

    # ------------------- 批量标记已读/未读（快捷键） -------------------
    def _batch_mark_selected_read(self, is_read=1):
        """批量标记选中行为已读/未读"""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            self.statusBar().showMessage("请先选中要标记的行", 2000)
            return
        rows = set()
        for idx in selection:
            source_idx = self.proxy_model.mapToSource(idx)
            rows.add(source_idx.row())
        self.audit_controller.batch_mark_read(list(rows), self.source_model, is_read, self.statusBar().showMessage)

    # ------------------- 复制上一行备注（快捷键） -------------------
    def _copy_previous_remark(self):
        """复制当前选中行的上一行备注到当前行"""
        current = self.table_view.currentIndex()
        if not current.isValid():
            self.statusBar().showMessage("请先选中一行", 2000)
            return
        source_idx = self.proxy_model.mapToSource(current)
        row = source_idx.row()
        self.audit_controller.copy_previous_remark(row, self.source_model, self.statusBar().showMessage)

    # ------------------- 预警通知 -------------------
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
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            self.analysis_controller.cancel()
        if self.audit_controller.ai_worker and self.audit_controller.ai_worker.isRunning():
            self.audit_controller.cancel_ai_audit()
        if hasattr(self, 'alert_monitor') and self.alert_monitor.isRunning():
            self.alert_monitor.stop()
        event.accept()


    # ------------------- 倒计时辅助方法 -------------------
    def _update_countdown(self):
        """每秒更新倒计时显示"""
        self._countdown_seconds += 1
        m, s = divmod(self._countdown_seconds, 60)
        self.progress_label.setText(f"{self._current_step} | ⏱ {m:02d}:{s:02d}")

    def _stop_countdown(self):
        """停止倒计时"""
        if hasattr(self, '_countdown_timer'):
            self._countdown_timer.stop()

    def _format_elapsed(self):
        """格式化耗时"""
        m, s = divmod(self._countdown_seconds, 60)
        return f"{m:02d}:{s:02d}"

    # ------------------- 多选区复制功能（仿 Excel） -------------------
    def copy_selected_cells(self):
        """复制选中区域为制表符分隔的文本（支持多行多列）"""
        indexes = self.table_view.selectedIndexes()
        if not indexes:
            return
        
        # 获取选中区域的行列范围
        rows = sorted(set(idx.row() for idx in indexes))
        cols = sorted(set(idx.column() for idx in indexes))
        
        # 获取模型（注意代理）
        proxy = self.table_view.model()
        source = proxy.sourceModel() if hasattr(proxy, 'mapToSource') else proxy
        
        # 构建二维数据
        data = []
        for row in rows:
            row_data = []
            for col in cols:
                # 代理索引 --> 源索引 --> 数据
                proxy_idx = proxy.index(row, col)
                if hasattr(proxy, 'mapToSource'):
                    src_idx = proxy.mapToSource(proxy_idx)
                    value = source.data(src_idx, Qt.DisplayRole)
                else:
                    value = proxy.data(proxy_idx, Qt.DisplayRole)
                
                # 转换为字符串，None 转为空
                text = str(value) if value is not None else ""
                # 如果内容包含制表符或换行，可以替换（可选）
                text = text.replace('\n', ' ').replace('\r', '')
                row_data.append(text)
            data.append(row_data)
        
        # 转为制表符分隔文本
        lines = ['\t'.join(row) for row in data]
        clipboard_text = '\n'.join(lines)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(clipboard_text)
        
        # 状态栏提示
        self.statusBar().showMessage(f"已复制 {len(rows)} 行 × {len(cols)} 列", 2000)
    
    def _generate_advanced_report(self):
        """生成详细分析报告(专业版) - 直接从内存DataFrame生成"""
        from core.advanced_ppt_generator_v3 import generate_advanced_report_v3
        from PySide6.QtWidgets import QMessageBox

        # 1. 检查是否有数据
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "无数据，请先完成分析")
            return

        # 2. 选择保存路径
        output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"ZPP011专业报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        )

        # 3. 开始生成
        self.log("正在从内存数据生成专业版 PPT 报告...", "info")
        try:
            success = generate_advanced_report_v3(
                output_path=output_path, log_cb=self.log, df=self.view_model.df
            )
            if success:
                self.log(f"专业版报告生成成功：{output_path}", "info")
                reply = QMessageBox.question(self, "生成成功",
                    f"报告已生成：\n{output_path}\n是否打开？",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    os.startfile(output_path)
            else:
                QMessageBox.warning(self, "生成失败", "报告生成失败，请查看日志")
        except Exception as e:
            self.log(f"专业版报告生成失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"生成失败: {e}")

    def _on_cell_double_clicked(self, index):
        """双击切换已读/未读状态"""
        try:
            if index.column() == 0 and self.proxy_model and self.source_model:
                source_index = self.proxy_model.mapToSource(index)
                row = source_index.row()
                df = self.source_model.getDataFrame()
                if row < len(df):
                    data_id = df.iloc[row]['data_id']
                    current_read = df.iloc[row].get('_read', 0)
                    new_read = 1 - current_read
                    df.at[df.index[row], '_read'] = new_read
                    self.source_model.setDataFrame(df)
                    from core.read_status import save_read_status
                    fingerprint = df.iloc[row].get('fingerprint', '')
                    save_read_status(data_id, new_read, fingerprint)
                    self.statusBar().showMessage(
                        f"已标记为{'已读' if new_read else '未读'}", 2000)
        except Exception as e:
            self.log(f"双击切换状态失败: {e}", "error")

    def _batch_mark_read(self, rows, is_read):
        """批量标记已读/未读的内部实现"""
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
            self.statusBar().showMessage(
                f"已批量标记为{'已读' if is_read else '未读'}", 2000)
        except Exception as e:
            self.log(f"批量标记失败: {e}", "error")

    def show_copy_menu(self, pos):
        """右键菜单显示复制选项"""
        menu = QMenu()
        copy_action = menu.addAction("复制选中区域")
        copy_action.triggered.connect(self.copy_selected_cells)
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))
    # -------------------------------------------------------------


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
