# -*- coding: utf-8 -*-
"""
ZPP011 主窗口 (PySide6 迁移版)
布局：标题栏 + 操作栏 + 侧栏 + 数据表格 + 日志面板
暗色主题 v43.0 | 裴哥 2026-06-23
"""

import sys
import os
from datetime import datetime
import pandas as pd
import numpy as np
import subprocess

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QHeaderView, QDialog, QDialogButtonBox, QSplitter,
    QComboBox, QAbstractItemView, QMessageBox, QTableWidgetItem,
    QMenu, QSizePolicy, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem, QScrollArea, QGridLayout, QCheckBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QTimer
from PySide6.QtGui import QFont, QShortcut, QKeySequence, QAction

# 导入组件
from gui_pyside6.components.menu_bar import MenuBarComponent
from gui_pyside6.components.title_bar import TitleBarWidget
from gui_pyside6.components.left_panel import LeftPanelComponent
from gui_pyside6.components.main_table import MainTableComponent
from gui_pyside6.components.bottom_bar import BottomBarComponent

# 导入自定义模块
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.widgets.toast import toast
from gui_pyside6.widgets.loading_dialog import LoadingDialog
from gui_pyside6.widgets.filter_panel import FilterPanel
from gui_pyside6.widgets.stats_cards import StatsCardsWidget
from gui_pyside6.dialogs.unit_summary_dialog import UnitSummaryDialog
from gui_pyside6.dialogs.alert_dialog import AlertDialog
from gui_pyside6.dialogs.rule_config_dialog import RuleConfigDialog
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
from gui_pyside6.dialogs.history_compare_dialog import HistoryCompareDialog
from gui_pyside6.dialogs.import_wizard_dialog import ImportWizard
from gui_pyside6.dialogs.benefit_report_dialog import BenefitReportDialog
from gui_pyside6.dialogs.health_check_dialog import HealthCheckDialog
from gui_pyside6.viewmodels.analysis_vm import AnalysisViewModel
from core.alert_monitor import AlertMonitor, filter_alt_alerts
from domain.alt_material.alt_manager import (
    load_alt_pairs,
    save_alt_pairs,
    DEFAULT_ALT_PAIRS,
)
from core.config_manager import ConfigManager

from core.fingerprint import calc_fingerprint
from core.read_status import load_read_status, record_deviation_change
from gui_pyside6.services.data_service import DataService
from utils.version_history import get_current_version, VERSION_HISTORY, APP_NAME, AUTHOR

from gui_pyside6.controllers.analysis_controller import AnalysisController
from gui_pyside6.controllers.audit_controller import AuditController
from gui_pyside6.controllers.export_controller import ExportController
from gui_pyside6.controllers.alt_controller import AltController


class MainWindow(QMainWindow):
    """ZPP011 主窗口 — 暗色主题"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ZPP011 生产偏差分析器 {get_current_version()} (PySide6)")
        self.resize(1200, 800)

        # 状态变量
        self._audit_df = None
        self.source_model = None
        self.proxy_model = None
        self.current_input_file = None
        self.analysis_output_path = None
        self.config_manager = ConfigManager()
        self._analysis_params = {}
        self._full_analysis_cache_path = None
        self._cache_worker = None
        self.loading_dialog = None
        self.sort_columns = []
        self._countdown_seconds = 0
        self._countdown_timer = None
        # 按"列名"记录需要隐藏的列（避免 setDataFrame 重排列后索引错位导致列丢失）
        self._hidden_column_names = {'_post_audit_changed'}  # 内部变更标记列默认隐藏

        # 控制器
        self.analysis_controller = AnalysisController(self)
        self.audit_controller = AuditController(self)
        self.export_controller = ExportController(self)
        self.alt_controller = AltController(self)
        self.data_service = DataService(self.alt_controller)
        self.data_service.log_signal.connect(self._on_data_service_log)

        # 数据分析视图模型（单一数据源）
        self.view_model = AnalysisViewModel(self)
        self.view_model.data_changed.connect(self._on_view_model_data_changed)

        # 监控 & 缓存
        # AlertMonitor 需要 data_source_func 参数
        # 必须在 view_model 创建之后创建
        self.alert_monitor = AlertMonitor(
            data_source_func=lambda: self.view_model.df if self.view_model else None,
            threshold=10,
            interval=60,
            only_alt=True
        )
        self.alert_monitor.alert_triggered.connect(self._on_new_alerts)
        self.alert_monitor.start()

        # 创建组件
        self.menu_bar = MenuBarComponent(self)
        self.title_bar = TitleBarWidget(get_current_version(), self)
        self.left_panel_component = LeftPanelComponent(self)
        self.main_table = MainTableComponent(self)
        self.stats_cards = StatsCardsWidget(self)  # 统计卡片（审核概览 + 变更感知）
        self.bottom_bar = BottomBarComponent(self)
        self.filter_panel = FilterPanel(self)

        # UI 引用（必须在 _setup_connections 之前赋值）
        self.left_panel = self.left_panel_component.left_panel
        self.filter_panel = self.filter_panel  # Already created above
        # input_file_edit / output_dir_edit / preview_label 由 LeftPanelComponent 创建
        # 标题栏是子控件，不是顶层窗口，不需要 setWindowFlags
        self.progress_bar = self.main_table.progress_bar
        self.progress_label = self.main_table.progress_label
        # 无统计卡片相关变量
        # self.stat_total = ... 已删除
        # self.stat_high = ... 已删除
        # self.stat_need_note = ... 已删除
        # self.stat_ok = ... 已删除
        self.table_view = self.main_table.table_view
        self.summary_quota = self.main_table.summary_quota
        self.summary_actual = self.main_table.summary_actual
        self.summary_amount = self.main_table.summary_amount
        self.summary_qty = self.main_table.summary_qty
        self.start_btn = self.main_table.start_btn
        self.cancel_btn = self.main_table.cancel_btn
        self.lock_btn = self.main_table.lock_btn
        self.fullscreen_btn = self.main_table.fullscreen_btn
        self.unit_summary_btn = self.main_table.unit_summary_btn
        self._is_fullscreen = False
        # log_text 已由 BottomBarComponent 在初始化时设置到主窗口
        self.log_group = self.bottom_bar.log_group

        # 初始化表格模型
        self._init_table_model()

        # 连接按钮信号
        self._setup_connections()
        self._setup_shortcuts()

        # 组装布局（必须在 show 之前）
        self._assemble_layout()

        # 加载亮色主题（在所有组件创建和布局组装之后，show 之前）
        self._is_dark_theme = False
        qss_path = os.path.join(os.path.dirname(__file__), "light_theme.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
        self.title_bar.set_theme_light()

        # 所有组件初始化完成后才显示窗口
        self._refresh_alt_view()
        self.show()

        self.title_bar.theme_toggled.connect(self._toggle_theme)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self).activated.connect(self._start_analysis)
        QShortcut(QKeySequence("F6"), self).activated.connect(
            lambda: self.export_controller.export_current_table(
                self.view_model.df, self
            )
        )
        QShortcut(QKeySequence("F7"), self).activated.connect(self._show_benefit_report)
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            lambda: self._batch_mark_selected_read(1)
        )
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(
            self._copy_previous_remark
        )
        QShortcut(QKeySequence("F11"), self).activated.connect(
            self._toggle_table_fullscreen
        )

    def _load_dark_theme(self):
        """加载暗色主题 QSS（app 级别）"""
        qss_path = os.path.join(os.path.dirname(__file__), "dark_theme.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())

    def _assemble_layout(self):
        """组装新布局：标题栏 + 操作栏 + 统计卡片 + 侧栏 + 表格 + 日志"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 自定义标题栏
        main_layout.addWidget(self.title_bar)

        # 2. 操作栏（按钮）
        action_bar = QWidget()
        action_bar.setObjectName("actionBar")
        action_bar.setFixedHeight(38)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(8, 4, 8, 4)
        action_layout.setSpacing(6)

        self.action_btn_filter = QPushButton("☰ 隐藏筛选")
        self.action_btn_filter.setCheckable(True)
        self.action_btn_filter.setChecked(True)
        self.action_btn_filter.setCursor(Qt.PointingHandCursor)
        self.action_btn_filter.setObjectName("actionBtnFilter")
        self.action_btn_filter.setProperty("class", "actionBtn")
        self.action_btn_filter.clicked.connect(self._toggle_filter_panel)

        self.action_btn_analyze = QPushButton("📊 分析")
        self.action_btn_analyze.setCursor(Qt.PointingHandCursor)
        self.action_btn_analyze.setObjectName("actionBtnAnalyze")
        self.action_btn_analyze.clicked.connect(self._start_analysis)

        self.action_btn_ai = QPushButton("🤖 AI审核")
        self.action_btn_ai.setCursor(Qt.PointingHandCursor)
        self.action_btn_ai.setObjectName("actionBtnAi")
        self.action_btn_ai.clicked.connect(lambda: self.audit_controller.run_ai_audit(self.view_model.df))

        spacer2 = QWidget()
        spacer2.setFixedWidth(4)

        self.action_btn_excel = QPushButton("📤 Excel")
        self.action_btn_excel.setCursor(Qt.PointingHandCursor)
        self.action_btn_excel.setObjectName("actionBtnExcel")
        self.action_btn_excel.setProperty("class", "actionBtn")
        self.action_btn_excel.clicked.connect(
            lambda: self.export_controller.export_current_table(self.view_model.df, self)
        )

        self.action_btn_export_full = QPushButton("📋 完整报告")
        self.action_btn_export_full.setCursor(Qt.PointingHandCursor)
        self.action_btn_export_full.setObjectName("actionBtnExportFull")
        self.action_btn_export_full.setProperty("class", "actionBtn")
        self.action_btn_export_full.clicked.connect(self._on_export_full_excel)

        self.action_btn_ppt = QPushButton("📈 PPT")
        self.action_btn_ppt.setCursor(Qt.PointingHandCursor)
        self.action_btn_ppt.setObjectName("actionBtnPpt")
        self.action_btn_ppt.setProperty("class", "actionBtn")
        self.action_btn_ppt.clicked.connect(self._show_benefit_report)

        shortcut_hint = QLabel("F5:分析 | F6:导出 | F7:效益 | F11:全屏")
        shortcut_hint.setObjectName("shortcutHint")

        action_layout.addWidget(self.action_btn_filter)
        action_layout.addWidget(self.action_btn_analyze)
        action_layout.addWidget(self.action_btn_ai)
        action_layout.addWidget(spacer2)
        action_layout.addWidget(self.action_btn_excel)
        action_layout.addWidget(self.action_btn_export_full)
        action_layout.addWidget(self.action_btn_ppt)
        action_layout.addStretch()
        action_layout.addWidget(shortcut_hint)

        main_layout.addWidget(action_bar)
        main_layout.addWidget(self.stats_cards)

        # 3. 主体区域（侧栏 + 数据表格+日志）
        self.body_splitter = QSplitter(Qt.Horizontal)

        # 左侧面板
        self.body_splitter.addWidget(self.left_panel)
        
        # 右侧筛选面板（FilterPanel）
        self.body_splitter.addWidget(self.filter_panel)
        self.filter_panel.setVisible(False)  # 默认隐藏

        # 右侧：审核表格 + 日志面板
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(0)

        # 垂直分割器：表格 + 日志
        self._v_splitter = QSplitter(Qt.Vertical)
        self._v_splitter.setChildrenCollapsible(True)
        self._v_splitter.addWidget(self.main_table.audit_widget)
        self._v_splitter.addWidget(self.log_group)
        self._v_splitter.setSizes([500, 140])
        self._v_splitter.setStretchFactor(0, 7)
        self._v_splitter.setStretchFactor(1, 3)
        # 记录日志面板是否被用户手动展开
        self._log_user_expanded = False
        self._log_saved_sizes = [500, 140]
        # 复用单个定时器
        self._log_auto_timer = QTimer(self)
        self._log_auto_timer.setSingleShot(True)
        self._log_auto_timer.timeout.connect(self._auto_collapse_log)

        # 组合：分割器(stretch) + 合计栏(固定在底部，不被挤出)
        right_layout.addWidget(self._v_splitter, 1)
        right_layout.addWidget(self.main_table.summary_container, 0)

        self.body_splitter.addWidget(right_container)
        self.body_splitter.setSizes([260, 280, 940])

        main_layout.addWidget(self.body_splitter, 1)

        # 底部状态栏
        status_bar = QWidget()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(28)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.setSpacing(6)
        accent = QWidget()
        accent.setFixedWidth(3)
        accent.setObjectName("statusAccentBar")
        status_layout.addWidget(accent)
        self.status_label = QLabel("就绪 — 选择输入文件后点击「开始分析」")
        self.status_label.setObjectName("statusLabel")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addWidget(status_bar)

    def _setup_connections(self):
        self.main_table.start_btn.clicked.connect(self._start_analysis)
        self.main_table.cancel_btn.clicked.connect(self._cancel_analysis)
        self.main_table.open_dir_btn.clicked.connect(self._open_output_dir)
        self.main_table.ppt_btn.clicked.connect(
            lambda: self.export_controller.generate_simple_ppt(
                self.view_model.df,
                self.analysis_output_path,
                self.output_dir_edit.text().strip(),
                self,
                self.log,
            )
        )
        self.main_table.excel_btn.clicked.connect(
            lambda: self.export_controller.export_current_table(
                self.view_model.df, self
            )
        )
        self.main_table.export_full_btn.clicked.connect(self._on_export_full_excel)
        self.main_table.refresh_net_btn.clicked.connect(self._recalculate_net_offset)
        self.main_table.table_view.doubleClicked.connect(self._on_cell_double_clicked)
        self._install_table_copy_handler()

        self.analysis_controller.analysis_started.connect(self._on_analysis_ui_start)
        self.analysis_controller.progress_updated.connect(self._on_analysis_progress_ui)
        self.analysis_controller.log_message.connect(self.log)
        self.export_controller.log_message.connect(self.log)
        self.audit_controller.log_message.connect(self.log)
        self.analysis_controller.analysis_finished.connect(self._on_analysis_finished_ui)
        self.stats_cards.card_clicked.connect(self._on_stats_card_clicked)
        self.analysis_controller.analysis_error.connect(self._on_analysis_error_ui)
        self.audit_controller.progress_started.connect(self._on_ai_ui_start)
        self.audit_controller.progress_updated.connect(self._on_ai_progress_ui)
        self.audit_controller.progress_finished.connect(self._on_ai_finished_ui)
        self.audit_controller.progress_error.connect(self._on_ai_error_ui)
        self.alt_controller.data_changed.connect(self._on_alt_pairs_changed)

        # 筛选面板信号
        self.filter_panel.filter_changed.connect(self._on_filter_panel_changed)

    def _on_title_factory_selected(self, factory_name):
        self._on_factory_changed(factory_name)

    def _toggle_theme(self):
        """切换亮色/暗色主题"""
        # 用成员变量跟踪当前主题
        if not hasattr(self, '_is_dark_theme'):
            self._is_dark_theme = True  # 默认是暗色主题

        if self._is_dark_theme:
            # 切换到亮色主题
            qss_path = os.path.join(os.path.dirname(__file__), "light_theme.qss")
            if os.path.exists(qss_path):
                with open(qss_path, "r", encoding="utf-8") as f:
                    QApplication.instance().setStyleSheet(f.read())
            else:
                QApplication.instance().setStyleSheet("")
            self._is_dark_theme = False
            self.title_bar.set_theme_light()
            toast("☀️ 已切换至亮色主题", "info", parent=self)
        else:
            # 切换到暗色主题
            self._load_dark_theme()
            self._is_dark_theme = True
            self.title_bar.set_theme_dark()
            toast("🌙 已切换至暗色主题", "info", parent=self)

    # -----------------------------------------------------------
    # 业务方法
    # -----------------------------------------------------------
    def _on_data_service_log(self, msg, level):
        if level == "alert" and msg.startswith("变动提醒|"):
            count = msg.split("|")[1]
            QMessageBox.information(self, "变动提醒", f"发现 {count} 条已审核记录发生变动，已强制设为'未读'。")
        else:
            self.log(msg, level)

    def _start_analysis(self):
        if not self.current_input_file:
            QMessageBox.warning(self, "提示", "请先选择输入文件")
            return
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            QMessageBox.information(self, "提示", "分析任务已在后台运行")
            return

        self.loading_dialog = LoadingDialog("正在分析数据，请稍候...", self)
        self.loading_dialog.show()
        QApplication.processEvents()

        dev_threshold = getattr(self.filter_panel, 'dev_threshold_spin', None)
        dev_threshold_val = dev_threshold.value() if dev_threshold is not None else 1.0

        self.analysis_controller.start_analysis(
            self.current_input_file,
            self.alt_controller.get_pairs(),
            "",
            "",
            "",
            dev_threshold_val,
        )

    def _on_analysis_ui_start(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.start_btn.setEnabled(False)
        self._countdown_seconds = 0
        self._current_step = "准备中"
        if self._countdown_timer is None:
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

    def _on_analysis_progress_ui(self, percent, step_name):
        self.progress_bar.setValue(percent)
        self._current_step = step_name
        m, s = divmod(self._countdown_seconds, 60)
        self.progress_label.setText(f"{step_name} {percent}% | ⏱ {m:02d}:{s:02d}")

    def _on_analysis_finished_ui(self, df):
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        elapsed = self._format_elapsed()
        self.progress_label.setText(f"完成 ({elapsed})")
        toast(f"✅ 分析完成，共 {len(df)} 条记录 ({elapsed})", "success", parent=self)
        self.statusBar().showMessage("分析完成，正在加载结果...")

        factory_list = self.analysis_controller.get_factory_list()
        if factory_list:
            # 默认显示全部工厂，不按工厂拆分
            self._on_factory_changed('全部')

        try:
            processed_df = self.view_model.df
            if processed_df is None or processed_df.empty:
                processed_df = self.data_service.preprocess_audit_data(df)
                self.source_model.setDataFrame(processed_df)
                self.view_model.df = processed_df
            self._analysis_params = self.analysis_controller.get_analysis_params()

            import tempfile
            temp_dir = os.path.join(tempfile.gettempdir(), "zpp011_analysis")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            df.to_excel(temp_path, sheet_name="完整偏差明细", index=False)
            self._analysis_output_path = temp_path

            cache_dir = os.path.join(tempfile.gettempdir(), "zpp011_analysis")
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"full_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            self._full_analysis_cache_path = cache_path

            from PySide6.QtCore import QThread
            class _FullCacheWorker(QThread):
                def __init__(self, input_file, alt_pairs, start_date, end_date, material_search, output_path):
                    super().__init__()
                    self.input_file = input_file
                    self.alt_pairs = alt_pairs
                    self.start_date = start_date
                    self.end_date = end_date
                    self.material_search = material_search
                    self.output_path = output_path
                def run(self):
                    from analysis.analyzer import do_analysis_v2
                    from core.config_manager import ConfigManager
                    _cfg = ConfigManager()
                    do_analysis_v2(
                        input_file=self.input_file, output_dir=None,
                        alt_pairs=self.alt_pairs, start_date=self.start_date,
                        end_date=self.end_date, material_search=self.material_search,
                        output_path=self.output_path,
                        enable_net_offset=_cfg.get_net_offset_enabled(),
                        return_dataframe=False,
                    )

            params = self.analysis_controller.get_analysis_params()
            self._cache_worker = _FullCacheWorker(
                params['input_file'], params['alt_pairs'],
                params.get('start_date', ''), params.get('end_date', ''),
                params.get('material_search', ''), cache_path
            )
            _cw = self._cache_worker
            def _on_cache_done():
                _cw.wait()
                if self._cache_worker is _cw:
                    self._cache_worker = None
            self._cache_worker.finished.connect(_on_cache_done)
            self._cache_worker.start()

            self._set_column_widths()
            self.statusBar().showMessage(f"分析完成，共加载 {len(processed_df)} 行 × {len(processed_df.columns)} 列")
            # 更新左侧"数据预览"卡片（文字统计，使用与表格一致的预处理后 df）
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.setText(self._format_preview_stats(processed_df))
            if hasattr(self, 'left_panel') and hasattr(self.left_panel, 'preview_group'):
                self.left_panel.preview_group.expand()
            self.main_table.summary_container.setVisible(True)
            self._update_summary()
            self.main_table.summary_container.raise_()
            self.main_table.summary_container.repaint()
            QApplication.processEvents()
            # 分析完成后5秒自动折叠日志面板
            self._log_auto_timer.start(5000)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载结果失败: {e}")

        if not self.alert_monitor.isRunning():
            self.alert_monitor.start()

    def _on_analysis_error_ui(self, error_msg):
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        self.progress_label.setText("错误")
        QMessageBox.critical(self, "错误", error_msg)

    def _on_ai_ui_start(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self._countdown_seconds = 0
        self._current_step = "AI审核"
        if not hasattr(self, "_countdown_timer"):
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

    def _on_ai_progress_ui(self, current, total):
        percent = int(current / total * 100) if total else 0
        self.progress_bar.setValue(percent)
        m, s = divmod(self._countdown_seconds, 60)
        self.progress_label.setText(f"AI审核: {current}/{total} | ⏱ {m:02d}:{s:02d}")

    def _on_ai_finished_ui(self, updated_df):
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        elapsed = self._format_elapsed()
        self.progress_label.setText(f"AI审核完成 ({elapsed})")
        toast(f"✅ AI审核完成 ({elapsed})", "success", parent=self)

        if "AI建议" in updated_df.columns:
            non_empty = updated_df["AI建议"].replace("", pd.NA).notna().sum()
            total = len(updated_df)
            self.log(f"AI审核完成：共 {total} 条记录，{non_empty} 条有AI建议", "info")
            if non_empty == 0:
                self.log("警告：AI建议列为空", "warning")
        else:
            self.log("警告：AI建议列不存在", "warning")

        processed_df = self.data_service.preprocess_audit_data(updated_df, self.view_model.df)
        self.source_model.setDataFrame(processed_df)
        self._apply_column_visibility_by_name()
        self.view_model.df = processed_df
        self.progress_bar.setVisible(False)
        self.progress_label.setText("就绪")
        if "AI建议" not in updated_df.columns or updated_df["AI建议"].replace("", pd.NA).notna().sum() > 0:
            QMessageBox.information(self, "完成", "AI审核已完成")

    def _on_ai_error_ui(self, error_msg):
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self.progress_bar.setVisible(False)
        self.progress_label.setText("错误")
        QMessageBox.critical(self, "错误", error_msg)

    def _on_new_alerts(self, alerts_df):
        count = len(alerts_df)
        reply = QMessageBox.question(
            self, "⚠️ 预警通知",
            f"发现 {count} 条新替代料预警（含差异/超阈值），是否查看明细？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            try:
                # 直接用 AlertMonitor 传过来的 alerts_df，已经过滤过替代料了
                all_alerts = alerts_df.copy()
                if all_alerts is None or all_alerts.empty:
                    QMessageBox.information(self, "提示", "没有替代料预警记录")
                    return
                # 只保留关键列，避免显示乱七八糟
                required_cols = [c for c in [
                    "订单日期", "流程订单", "物料编码", "物料描述", "物料名称",
                    "车间", "定额", "实际", "偏差数量", "偏差率(%)",
                    "净偏差数量", "净偏差金额", "净偏差率(%)", "备注", "备注原因", "备注来源",
                    "_read"
                ] if c in all_alerts.columns]
                all_alerts = all_alerts[required_cols]
                if "_read" in all_alerts.columns:
                    all_alerts["状态"] = all_alerts["_read"].map({0: "未读", 1: "已读"})
                    all_alerts = all_alerts[["状态"] + [c for c in all_alerts.columns if c != "状态"]]
                dialog = AlertDialog(all_alerts, self)
                dialog.exec()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"显示预警失败: {e}")

    def _show_alert_dashboard(self):
        """手动打开替代料看板"""
        try:
            df = self.view_model.df
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            if "偏差率(%)" not in df.columns:
                QMessageBox.information(self, "提示", "当前数据无偏差率列")
                return
            # 筛选替代料：有差异 或 偏差率超阈值 都进看板
            threshold = getattr(self.alert_monitor, 'threshold', 10)
            if "是否替代料" in df.columns:
                alerts_df = filter_alt_alerts(df, threshold)
            else:
                alerts_df = df[df["偏差率(%)"].abs() > threshold]
            if alerts_df.empty:
                QMessageBox.information(self, "提示", "没有替代料预警记录")
                return
            # 只保留关键列
            required_cols = [c for c in [
                "订单日期", "流程订单", "物料编码", "物料描述", "物料名称",
                "车间", "定额", "实际", "偏差数量", "偏差率(%)",
                "净偏差数量", "净偏差金额", "净偏差率(%)", "备注", "备注原因", "备注来源",
                "_read"
            ] if c in alerts_df.columns]
            alerts_df = alerts_df[required_cols]
            if "_read" in alerts_df.columns:
                alerts_df["状态"] = alerts_df["_read"].map({0: "未读", 1: "已读"})
                alerts_df = alerts_df[["状态"] + [c for c in alerts_df.columns if c != "状态"]]
            dialog = AlertDialog(alerts_df, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开替代料看板失败: {e}")

    def _update_all_summary(self):
        """恢复整体合计"""
        self._update_summary()

    def _on_selection_changed(self, selected, deselected):
        """选中变化时，显示选中合计"""
        if self.proxy_model is None or self.view_model.df is None:
            self.statusBar().showMessage("")
            return
        
        # 如果没有选中行，恢复整体合计
        if not selected:
            self._update_all_summary()
            return
        
        indexes = self.table_view.selectionModel().selectedIndexes()
        if not indexes:
            self.statusBar().showMessage("")
            return
        df = self.source_model.getDataFrame()
        # 收集选中行中的唯一行号
        selected_rows = set()
        for idx in indexes:
            source_idx = self.proxy_model.mapToSource(idx)
            selected_rows.add(source_idx.row())
        
        # 按列累加选中行的值
        col_sums = {}
        # 从 df 中找出所有可能的数值列
        numeric_candidates = ["配额", "定额", "数量-定额", "实际", "数量-实际", "偏差金额", "偏差金额(含税)", "偏差数量", "数量偏差", "净偏差数量", "净偏差金额"]
        
        for row in selected_rows:
            for col_idx, col_name in enumerate(df.columns):
                if col_idx == 0:  # 跳过行号列
                    continue
                if col_name not in numeric_candidates:
                    continue
                val = df.iloc[row, col_idx]
                if pd.notna(val) and isinstance(val, (int, float, np.integer, np.floating)):
                    col_sums[col_name] = col_sums.get(col_name, 0) + val
        
        if col_sums:
            # 更新选中合计显示
            self._update_selection_summary(col_sums)
        else:
            self.statusBar().showMessage("选中合计：无有效数值", 2000)
            self._clear_selection_summary()

    def _cancel_analysis(self):
        cancelled = False
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            self.analysis_controller.cancel()
            cancelled = True
        if self.audit_controller.ai_worker and self.audit_controller.ai_worker.isRunning():
            self.audit_controller.cancel_ai_audit()
            cancelled = True
        if cancelled:
            if self.loading_dialog:
                self.loading_dialog.accept()
                self.loading_dialog = None
            self.progress_bar.setVisible(False)
            self.progress_label.setText("已取消")
            self.start_btn.setEnabled(True)
            self.log("操作已取消", "info")

    def _batch_mark_selected_read(self, is_read=1):
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            self.statusBar().showMessage("请先选中要标记的行", 2000)
            return
        rows = set()
        for idx in selection:
            source_idx = self.proxy_model.mapToSource(idx)
            rows.add(source_idx.row())
        self.audit_controller.batch_mark_read(list(rows), self.source_model, is_read, self.statusBar().showMessage)

    def _copy_previous_remark(self):
        current = self.table_view.currentIndex()
        if not current.isValid():
            self.statusBar().showMessage("请先选中一行", 2000)
            return
        source_idx = self.proxy_model.mapToSource(current)
        row = source_idx.row()
        self.audit_controller.copy_previous_remark(row, self.source_model, self.statusBar().showMessage)

    # -----------------------------------------------------------
    # 文件与目录
    # -----------------------------------------------------------
    def _select_input_file(self):
        default_dir = r"E:\ZPP011导出文件原数据"
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 SAP Excel 文件", default_dir, "Excel files (*.xlsx *.xls)")
        if file_path:
            self.current_input_file = file_path
            self.input_file_edit.setText(file_path)
            # 显示短文件名，完整路径放到 tooltip
            short_name = os.path.basename(file_path)
            self.input_file_edit.setToolTip(file_path)
            try:
                xl = pd.ExcelFile(file_path)
                sheets = xl.sheet_names
                target = "Data" if "Data" in sheets else sheets[0]
                df = pd.read_excel(file_path, sheet_name=target)
                basename = os.path.basename(file_path)
                if hasattr(self, 'preview_label') and self.preview_label:
                    self.preview_label.setText(self._format_preview_stats(df))
            except Exception as e:
                if hasattr(self, 'preview_label') and self.preview_label:
                    self.preview_label.setText(f"读取失败：{e}")

    def _select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_edit.setText(dir_path)
            # 只显示最后一级目录名，避免路径过长
            self.output_dir_edit.setToolTip(dir_path)

    def _format_preview_stats(self, df):
        """根据 DataFrame 生成数据预览统计文字（列数只算可见列）"""
        factory_col = None
        for cand in ['工厂名称', '工厂', 'plant']:
            if cand in df.columns:
                factory_col = cand
                break
        # 列数 = 总列数 - 隐藏列数（按列名匹配）
        total_cols = len(df.columns)
        hidden_count = sum(1 for c in df.columns if c in self._hidden_column_names)
        visible_cols = total_cols - hidden_count
        # 再剔除当前被拖成 0 宽（挤没）的列，使预览与实际可见列一致
        model = self.table_view.model() if hasattr(self, 'table_view') else None
        if model is not None:
            try:
                for col in range(model.columnCount()):
                    if self.table_view.columnWidth(col) <= 1:
                        visible_cols -= 1
            except Exception:
                pass

        lines = [f"总行数：{len(df)} 行"]
        if factory_col:
            food = int((df[factory_col].astype(str).str.contains('食品')).sum())
            drink = int((df[factory_col].astype(str).str.contains('饮料')).sum())
            other = len(df) - food - drink
            lines.append(f"食品厂：{food} 行")
            lines.append(f"饮料厂：{drink} 行")
            if other > 0:
                lines.append(f"其他：{other} 行")
        lines.append(f"列数：{visible_cols} 列")
        return "\n".join(lines)

    def _open_output_dir(self):
        dir_path = self.output_dir_edit.text()
        if not dir_path:
            dir_path = os.path.expanduser("~/Documents/ZPP011分析报告")
        if os.path.exists(dir_path):
            os.startfile(dir_path)
        else:
            QMessageBox.warning(self, "提示", "输出目录不存在")

    # -----------------------------------------------------------
    # 替代料配对
    # -----------------------------------------------------------
    def _refresh_alt_view(self):
        if self.alt_table is None:
            return
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
        if self.alt_count_label is not None:
            self.alt_count_label.setText(f"共 {len(pairs)} 对")

    def _on_alt_pairs_changed(self):
        self._refresh_alt_view()
        self._recalculate_net_offset(silent=True)

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
        if file_path.endswith(".json"):
            self.alt_controller.import_from_file(file_path, self)
        else:
            wizard = ImportWizard(self, self.alt_controller.get_pairs(), None, on_alt_changed=self._refresh_alt_view, on_rules_changed=None)
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
        locked = self.lock_btn.isChecked()
        header = self.table_view.horizontalHeader()
        if locked:
            header.setSectionResizeMode(QHeaderView.Fixed)
            self.lock_btn.setText("🔓")
            self.statusBar().showMessage("列宽已锁定", 2000)
        else:
            header.setSectionResizeMode(QHeaderView.Interactive)
            self.lock_btn.setText("🔒")
            self.statusBar().showMessage("列宽已解锁，可拖拽调整", 2000)

    def _toggle_table_fullscreen(self):
        """切换全屏模式"""
        full = not getattr(self, '_is_fullscreen', False)
        self._is_fullscreen = full
        if full:
            self.left_panel.setVisible(False)
            # 全屏时隐藏日志面板
            self.log_group.setVisible(False)
            # 全屏时保留底部合计栏，隐藏系统状态栏
            if hasattr(self, 'filter_panel') and self.filter_panel:
                self.filter_panel.setVisible(False)
            self.statusBar().hide()
            QApplication.processEvents()
            self.statusBar().showMessage("全屏模式 (F11 退出)", 3000)
        else:
            self.left_panel.setVisible(True)
            self.log_group.setVisible(True)
            if hasattr(self, 'filter_panel') and self.filter_panel:
                self.filter_panel.setVisible(True)
            self.statusBar().show()
            QApplication.processEvents()
            self.statusBar().showMessage("已退出全屏", 2000)

    def _show_column_hide_dialog(self):
        """显示隐藏列对话框（按列名记录显隐，避免列重排后错位丢失）"""
        model = self.table_view.model()
        if not model:
            return
        col_count = model.columnCount()
        if col_count == 0:
            return

        # 收集 (列索引, 列名) —— 列名用于稳定记录显隐状态
        cols_info = []
        for col in range(col_count):
            hdr = model.headerData(col, Qt.Horizontal)
            name = str(hdr).replace('\n', '') if hdr else f"列{col}"
            if name == '_post_audit_changed':  # 内部变更标记列，不在显隐对话框列出
                continue
            cols_info.append((col, name))

        dialog = QDialog(self)
        dialog.setWindowTitle("隐藏/显示列")
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog)

        hint = QLabel("勾选要显示的列，取消勾选则隐藏；标「（已隐藏）」的列当前未显示：")
        layout.addWidget(hint)

        # 快捷按钮：一键恢复全部 / 全部隐藏
        btn_row = QHBoxLayout()
        btn_show_all = QPushButton("恢复全部显示")
        btn_hide_all = QPushButton("全部隐藏")
        btn_row.addWidget(btn_show_all)
        btn_row.addWidget(btn_hide_all)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 复选框列表（滚动区域）；隐藏的列追加「（已隐藏）」标记便于辨认
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)

        checkboxes = []
        for idx, (col, name) in enumerate(cols_info):
            # 真实可见性：既认 setColumnHidden，也认“宽度被拖成 0”的挤没列
            is_hidden = self._is_column_effectively_hidden(col)
            label = f"{idx + 1}. {name}（已隐藏）" if is_hidden else f"{idx + 1}. {name}"
            cb = QCheckBox(label)
            cb.setChecked(not is_hidden)
            checkboxes.append((col, name, cb))
            scroll_layout.addWidget(cb)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # 确定按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        # 快捷按钮：恢复全部显示 / 全部隐藏（按列名清空/填满隐藏集合）
        btn_show_all.clicked.connect(lambda: [cb.setChecked(True) for _, _, cb in checkboxes])
        btn_hide_all.clicked.connect(lambda: [cb.setChecked(False) for _, _, cb in checkboxes])

        if dialog.exec() == QDialog.Accepted:
            # 记录被取消勾选（即要隐藏）的列名
            self._hidden_column_names = {
                name for _, name, cb in checkboxes if not cb.isChecked()
            }
            self._apply_column_visibility_by_name()
            # 被勾选（要显示）的列若被拖成 0 宽，恢复默认宽度（像 Excel 取消隐藏）
            for col, name, cb in checkboxes:
                if cb.isChecked():
                    self._ensure_column_visible_width(col, name)
            self._save_column_widths()  # 持久化显隐状态：手动显示/隐藏都记住
            self.statusBar().showMessage("列显示已更新", 2000)

    def _is_column_effectively_hidden(self, col):
        """列是否实际不可见：被 setColumnHidden 或宽度被拖成 0 都算"""
        if self.table_view.isColumnHidden(col):
            return True
        try:
            return self.table_view.columnWidth(col) <= 1
        except Exception:
            return False

    def _ensure_column_visible_width(self, col, name):
        """若列宽被拖成 0（挤没），恢复一个合理的默认宽度"""
        if self.table_view.columnWidth(col) <= 1:
            self._apply_default_width(col, name)
            if self.table_view.columnWidth(col) <= 1:
                self.table_view.setColumnWidth(col, 120)

    def _apply_column_visibility_by_name(self):
        """按列名设置列的显隐状态（不受列重排 / 模型重置影响）"""
        self._hidden_column_names.add('_post_audit_changed')  # 内部变更标记列始终隐藏
        model = self.table_view.model()
        if not model:
            return
        for col in range(model.columnCount()):
            hdr = model.headerData(col, Qt.Horizontal)
            name = str(hdr).replace('\n', '') if hdr else ''
            self.table_view.setColumnHidden(col, name in self._hidden_column_names)

    def _on_left_panel_visibility_changed(self, visible: bool):
        """左侧面板显隐时的回调"""
        pass

    # -----------------------------------------------------------
    # 数据加载
    # -----------------------------------------------------------
    def _init_table_model(self):
        self.source_model = DataFrameModel()
        self.proxy_model = AuditProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)
        try:
            self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass
        self.source_model.dataChanged.connect(self._update_summary)
        # self.source_model.dataChanged.connect(self._refresh_stats_cards)  # stats_cards 已删除
        self.proxy_model.layoutChanged.connect(self._update_summary)
        # self.proxy_model.layoutChanged.connect(self._refresh_stats_cards)  # stats_cards 已删除
        self.table_view.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        self._set_column_widths()
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # 表头2行显示：自动换行
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table_view.setWordWrap(True)
        self.lock_btn.setChecked(False)
        self.log("Table model initialized", "info")

    def _on_view_model_data_changed(self):
        df = self.view_model.df
        if df is None or df.empty:
            self._update_summary()
            self.filter_panel.update_options(pd.DataFrame())
            return
        self._update_summary()
        self.stats_cards.refresh(df)
        self.filter_panel.update_options(df)

    def _on_stats_card_clicked(self, card_type: str):
        """统计卡片点击：切换对应筛选（审核后变更卡可过滤变更行）"""
        proxy = self.proxy_model
        if proxy is None or self.view_model.df is None:
            return
        current = dict(getattr(proxy, '_custom_filters', {}))
        if card_type == 'changed':
            if current.get('_changed_only'):
                current.pop('_changed_only', None)
                msg = "已显示全部记录"
            else:
                current['_changed_only'] = True
                msg = "已过滤：仅显示审核后变更的记录"
            proxy.setCustomFilters(current)
            self.statusBar().showMessage(msg, 3000)

    def log(self, msg, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")
        # 定时器尚未初始化时只记录日志，不触发折叠
        if not hasattr(self, '_log_auto_timer') or not self._log_auto_timer:
            return
        # 有新日志时自动展开日志面板，5秒后自动折叠
        self._log_auto_timer.stop()
        # 如果日志面板已折叠，展开它
        sizes = self._v_splitter.sizes()
        if len(sizes) >= 2 and sizes[1] < 30:
            self._v_splitter.setSizes(self._log_saved_sizes if self._log_saved_sizes else [500, 140])
            QApplication.processEvents()
        # 重启5秒倒计时
        self._log_auto_timer.start(5000)

    def _auto_collapse_log(self):
        """自动折叠日志面板（通过设置分割器大小，而非setVisible）"""
        sizes = self._v_splitter.sizes()
        if len(sizes) >= 2 and sizes[1] > 30:
            self._log_saved_sizes = sizes
        total = sum(sizes) if sizes else 640
        self._v_splitter.setSizes([total, 0])
        QApplication.processEvents()

    # -----------------------------------------------------------
    # 数据相关
    # -----------------------------------------------------------
    def _set_column_widths(self):
        header = self.table_view.horizontalHeader()
        model = self.table_view.model()
        if not model:
            return

        # 优先从配置文件恢复用户保存的列宽与隐藏状态
        saved_widths, saved_hidden = self._load_column_widths()
        # 恢复隐藏集合（按列名），再按名应用显隐
        self._hidden_column_names = set(saved_hidden) if saved_hidden else set()
        self._apply_column_visibility_by_name()

        if saved_widths:
            for col in range(model.columnCount()):
                col_name = model.headerData(col, Qt.Horizontal)
                if col_name:
                    col_name = str(col_name).replace('\n', '')
                    if col_name in saved_widths:
                        self.table_view.setColumnWidth(col, saved_widths[col_name])
                        continue
                # 没有保存过的列用默认逻辑
                self._apply_default_width(col, col_name)
            return

        # 无配置文件时用默认逻辑
        self.table_view.resizeColumnsToContents()
        self.table_view.setColumnWidth(0, 35)
        for col in range(1, model.columnCount()):
            col_name = model.headerData(col, Qt.Horizontal) if hasattr(model, 'headerData') else ''
            self._apply_default_width(col, col_name)

    def _apply_default_width(self, col, col_name):
        """对单列应用默认宽度逻辑"""
        if isinstance(col_name, str):
            if '名称' in col_name or '描述' in col_name or col_name == '物料':
                if self.table_view.columnWidth(col) < 200:
                    self.table_view.setColumnWidth(col, 200)
            elif '编码' in col_name or '号' in col_name or '订单' in col_name:
                if self.table_view.columnWidth(col) < 120:
                    self.table_view.setColumnWidth(col, 120)
            elif '备注' in col_name or '原因' in col_name:
                if self.table_view.columnWidth(col) < 150:
                    self.table_view.setColumnWidth(col, 150)

    def _get_config_path(self):
        """获取列宽配置文件路径"""
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'column_widths.json')

    def _save_column_widths(self):
        """保存当前列宽与隐藏状态到配置文件（隐藏按列名记录，可手动在对话框中恢复显示）"""
        model = self.table_view.model()
        if not model:
            return
        config = {}
        for col in range(model.columnCount()):
            col_name = model.headerData(col, Qt.Horizontal)
            if col_name:
                col_name = str(col_name).replace('\n', '')
                config[col_name] = {
                    'width': self.table_view.columnWidth(col),
                    'hidden': col_name in self._hidden_column_names,
                }
        try:
            import json
            with open(self._get_config_path(), 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存列宽失败: {e}", "warning")

    def _load_column_widths(self):
        """从配置文件加载列宽与隐藏状态。返回 (widths_dict, hidden_set)。"""
        try:
            import json
            path = self._get_config_path()
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                widths = {}
                hidden = set()
                for k, v in raw.items():
                    if isinstance(v, dict):
                        widths[k] = v.get('width', 100)
                        if v.get('hidden'):
                            hidden.add(k)
                    else:
                        # 兼容旧格式（纯宽度数值）
                        widths[k] = v
                return widths, hidden
        except Exception as e:
            self.log(f"加载列宽失败: {e}", "warning")
        return None, set()

    def _on_filter_panel_changed(self, filters: dict):
        if self.proxy_model is None or self.view_model.df is None:
            return
        self.proxy_model.setCustomFilters(filters)
        self._update_summary()

    def _on_sort_indicator_changed(self, logical_index, order):
        modifiers = QApplication.keyboardModifiers()
        ctrl_pressed = modifiers == Qt.ControlModifier
        col = logical_index
        ascending = order == Qt.AscendingOrder
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
        if not self.sort_columns:
            return
        if not hasattr(self, "source_model") or self.source_model is None:
            return
        df = self.source_model.getDataFrame()
        if df is None or df.empty:
            return
        sort_args = []
        for col, asc in self.sort_columns:
            if col == 0 or col < 0 or col >= len(df.columns):
                continue
            sort_args.append((df.columns[col], asc))
        if sort_args:
            cols = [c for c, _ in sort_args]
            asc = [a for _, a in sort_args]
            sort_keys = {}
            for c in cols:
                has_pct = df[c].astype(str).str.contains("%", na=False).any()
                if has_pct:
                    numeric_vals = pd.to_numeric(df[c].astype(str).str.replace("%", "").str.strip(), errors="coerce").fillna(0)
                    sort_keys[c] = numeric_vals
            if sort_keys:
                df_sorted = df.sort_values(by=cols, ascending=asc, key=lambda col: sort_keys.get(col.name, col), na_position="last")
            else:
                df_sorted = df.sort_values(by=cols, ascending=asc, na_position="last")
            self.source_model.setDataFrame(df_sorted)
            self._apply_column_visibility_by_name()

    # -----------------------------------------------------------
    # 工厂切换
    # -----------------------------------------------------------
    def _on_factory_changed(self, factory_name):
        if not factory_name:
            return
        if factory_name == '全部':
            # 显示全部工厂数据
            all_data = self.analysis_controller.factory_data.get('全部')
            if all_data is None:
                # 合并所有工厂数据
                all_parts = []
                for f, g in self.analysis_controller.factory_data.items():
                    all_parts.append(g)
                if all_parts:
                    import pandas as pd
                    all_data = pd.concat(all_parts, ignore_index=True)
                    self.analysis_controller.factory_data['全部'] = all_data
            df = all_data
        else:
            df = self.analysis_controller.factory_data.get(factory_name)
        if df is not None:
            processed_df = self.data_service.preprocess_audit_data(df)
            if self.source_model is None:
                self.source_model = DataFrameModel()
                self.proxy_model = AuditProxyModel()
                self.proxy_model.setSourceModel(self.source_model)
                self.table_view.setModel(self.proxy_model)
            self.source_model.setDataFrame(processed_df)
            self._apply_column_visibility_by_name()
            self.view_model.df = processed_df
            self._update_summary()
            self.filter_panel.update_options(processed_df)
            self.statusBar().showMessage(f"已切换到工厂：{factory_name}", 2000)
        else:
            self.statusBar().showMessage(f"工厂 {factory_name} 数据为空", 2000)

    # -----------------------------------------------------------
    # 统计与合计
    # -----------------------------------------------------------
    # _refresh_stats_cards 已删除（stats_cards 不再使用）

    def _on_stats_card_clicked(self, card_type: str):
        if card_type == "anomaly":
            try:
                df = self.source_model.getDataFrame() if self.source_model else None
                if df is not None and not df.empty:
                    rate_col = next((c for c in ['偏差率(%)', '偏差率', 'dev_rate'] if c in df.columns), None)
                    if rate_col:
                        rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
                        mask = rates.abs() > 30
                        count = int(mask.sum())
                        self.statusBar().showMessage(f"🔴 真异常 {count} 条（已排除替代料）", 5000)
            except Exception:
                pass

    def _update_summary(self):
        if self.view_model.df is None or self.view_model.df.empty:
            self.summary_quota.setText("配额: 0.00")
            self.summary_actual.setText("实际: 0.00")
            self.summary_amount.setText("偏差率: 0.00%")
            self.summary_qty.setText("偏差量: 0.00")
            return
        df = self.view_model.df
        # 配额列
        quota_col = next((c for c in ["配额", "定额", "数量-定额", "quota"] if c in df.columns), None)
        actual_col = next((c for c in ["实际", "数量-实际", "actual"] if c in df.columns), None)
        rate_col = next((c for c in ["偏差率(%)", "偏差率"] if c in df.columns), None)
        qty_col = next((c for c in ["偏差数量", "数量偏差", "dev_qty"] if c in df.columns), None)
        net_rate_col = next((c for c in ["净偏差率(%)", "净偏差率"] if c in df.columns), None)

        quota_sum = df[quota_col].fillna(0).sum() if quota_col else 0
        actual_sum = df[actual_col].fillna(0).sum() if actual_col else 0

        # 偏差率平均值
        if rate_col:
            rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
            avg_rate = rates.mean()
            rate_str = f"{avg_rate:.2f}%"
        else:
            if actual_col and quota_col:
                avg_rate = ((df[actual_col].fillna(0) - df[quota_col].fillna(0)) / df[quota_col].fillna(0).replace(0, float('nan'))).mean()
                rate_str = f"{avg_rate:.2f}%"
            else:
                rate_str = "0.00%"
                avg_rate = 0

        # 净偏差率平均值
        if net_rate_col:
            net_rates = pd.to_numeric(df[net_rate_col], errors='coerce').fillna(0)
            net_rate_str = f"{net_rates.mean():.2f}%"
        else:
            net_rate_str = ""

        # 偏差量汇总
        if qty_col:
            qty_sum = df[qty_col].fillna(0).sum()
        elif actual_col and quota_col:
            qty_sum = (df[actual_col].fillna(0) - df[quota_col].fillna(0)).sum()
        else:
            qty_sum = 0

        self.summary_quota.setText(f"配额: {quota_sum:,.2f}")
        self.summary_actual.setText(f"实际: {actual_sum:,.2f}")
        if net_rate_str:
            self.summary_amount.setText(f"偏差率: {rate_str} | 净偏差率: {net_rate_str}")
        else:
            self.summary_amount.setText(f"偏差率: {rate_str}")
        self.summary_qty.setText(f"偏差量: {qty_sum:,.2f}")

    def _update_selection_summary(self, col_sums: dict):
        """更新选中行合计到底部栏"""
        # 收集显示的列名和值
        display_map = {}
        for k, v in col_sums.items():
            # 映射到标准名称
            if k in ("配额", "定额", "数量-定额"):
                display_map["配额"] = v
            elif k in ("实际", "数量-实际"):
                display_map["实际"] = v
            elif k in ("偏差金额", "偏差金额(含税)"):
                display_map["偏差金额"] = v
            elif k in ("偏差数量", "数量偏差"):
                display_map["偏差数量"] = v
            else:
                display_map[k] = v
        
        # 如果有关键数值列，更新底部栏
        if "配额" in display_map or "实际" in display_map or "偏差金额" in display_map or "偏差数量" in display_map:
            quota = display_map.get("配额", 0)
            actual = display_map.get("实际", 0)
            amount = display_map.get("偏差金额", 0)
            qty = display_map.get("偏差数量", 0)
            
            # 更新底部栏
            self.summary_quota.setText(f"配额: {quota:,.2f}")
            self.summary_actual.setText(f"实际: {actual:,.2f}")
            self.summary_amount.setText(f"偏差金额: {amount:,.2f}")
            self.summary_qty.setText(f"偏差量: {qty:,.2f}")
            
            # 状态栏显示详细合计
            parts = []
            for k, v in display_map.items():
                if "%" in k:
                    parts.append(f"{k}: {v:.2f}")
                else:
                    parts.append(f"{k}: {v:,.2f}")
            self.statusBar().showMessage("选中合计：" + " | ".join(parts))

    def _clear_selection_summary(self):
        """清空选中合计，恢复默认"""
        self.summary_quota.setText("配额: 0.00")
        self.summary_actual.setText("实际: 0.00")
        self.summary_amount.setText("偏差金额: 0.00")
        self.summary_qty.setText("偏差量: 0.00")


    # _update_stat_cards 已删除（统计卡片不再使用）

    def _on_export_full_excel(self):
        """点击「导出完整Excel」— 完整逻辑内联，不依赖 export_controller"""
        import shutil
        from datetime import datetime
        from PySide6.QtWidgets import QFileDialog, QProgressDialog, QApplication

        audit_data = self.view_model.df
        if audit_data is None or audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据，请先进行分析")
            return

        # 1. 选择保存路径
        default_name = f"ZPP011偏差分析最终版_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存完整Excel文件", default_name, "Excel files (*.xlsx)"
        )
        if not save_path:
            return

        analysis_params = self._analysis_params
        current_input_file = self.current_input_file
        cache_path = self._full_analysis_cache_path

        # 检查参数是否有效
        has_valid_params = (
            analysis_params
            and isinstance(analysis_params, dict)
            and analysis_params.get('input_file')
            and current_input_file
        )

        # 2. 如果有有效参数，询问是否生成完整多Sheet
        if has_valid_params:
            reply = QMessageBox.question(
                self, "导出选项",
                "是否生成完整多Sheet分析报告（含汇总统计、预警颜色等）？\n\n"
                "点击「是」→ 生成完整多Sheet Excel（缓存命中则秒传，否则重新分析）\n"
                "点击「否」→ 仅导出当前表格数据（快速）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self._export_full_analysis_inline(
                    save_path, analysis_params, cache_path
                )
                return

        # 3. 仅导出当前表格数据
        try:
            audit_data.to_excel(save_path, sheet_name='完整偏差明细', index=False)
            if QMessageBox.question(
                self, "导出成功", f"文件已导出到：\n{save_path}\n是否打开？"
            ) == QMessageBox.Yes:
                os.startfile(save_path)
            self.log(f"已导出完整Excel到 {save_path}", "info")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
            self.log(f"导出失败: {e}", "error")

    def _export_full_analysis_inline(self, save_path, analysis_params, cache_path):
        """生成完整多Sheet Excel（优先使用缓存）"""
        import shutil
        from PySide6.QtWidgets import QApplication, QProgressDialog

        # 缓存命中：直接复制
        if cache_path and os.path.exists(cache_path):
            try:
                shutil.copy2(cache_path, save_path)
                if QMessageBox.question(
                    self, "导出成功",
                    f"完整分析报告已导出到\n{save_path}\n\n"
                    "（使用缓存，秒传完成）\n\n"
                    "包含Sheet:\n"
                    "📋 分析说明 · 汇总统计(带预警颜色)\n"
                    "完整偏差明细 · 替代料明细 · 无备注预警\n"
                    "中间地带明细 · 异常预警 · 偏差金额分析\n"
                    "偏差原因汇总 · 偏差原因分析 · 趋势分析\n\n"
                    "是否立即打开？"
                ) == QMessageBox.Yes:
                    os.startfile(save_path)
                self.log(f"已导出完整分析报告到 {save_path} (缓存)", "info")
                return
            except PermissionError:
                QMessageBox.critical(
                    self, "文件被占用",
                    f"目标文件被占用，无法写入：\n{save_path}\n\n"
                    "请先关闭正在打开该文件的 Excel，然后重试。"
                )
                self.log(f"导出失败：文件被占用 {save_path}", "error")
                return
            except Exception as e:
                QMessageBox.warning(
                    self, "缓存复制失败",
                    f"缓存复制失败：{e}\n\n将重新分析生成报告。"
                )
                self.log(f"缓存复制失败，回退重新分析: {e}", "warning")

        # 导出前检查目标文件是否可写
        try:
            test_f = open(save_path, 'a')
            test_f.close()
        except (PermissionError, OSError):
            QMessageBox.critical(
                self, "文件被占用",
                f"目标文件被占用，无法写入：\n{save_path}\n\n"
                "请先关闭正在打开该文件的 Excel，然后重试。"
            )
            self.log(f"导出失败：文件被占用 {save_path}", "error")
            return

        # 重新分析生成
        try:
            progress_dlg = QProgressDialog("正在重新分析生成完整报告...", "取消", 0, 100, self)
            progress_dlg.setWindowTitle("导出中")
            progress_dlg.setWindowModality(Qt.WindowModal)
            progress_dlg.setMinimumDuration(0)
            progress_dlg.show()
            QApplication.processEvents()

            from analysis.analyzer import do_analysis_v2
            do_analysis_v2(
                input_file=analysis_params['input_file'],
                output_dir=None,
                alt_pairs=analysis_params['alt_pairs'],
                progress_callback=lambda step_idx, step_name, percent: (
                    progress_dlg.setValue(percent),
                    progress_dlg.setLabelText(f"{step_name} ({percent}%)"),
                    QApplication.processEvents(),
                )[0],
                cancel_check=lambda *args: (QApplication.processEvents(), progress_dlg.wasCanceled())[1],
                start_date=analysis_params.get('start_date'),
                end_date=analysis_params.get('end_date'),
                material_search=analysis_params.get('material_search'),
                output_path=save_path,
                enable_net_offset=True,
                return_dataframe=False,
            )
            progress_dlg.setValue(100)
            progress_dlg.close()

            # 回存缓存
            if cache_path and not os.path.exists(cache_path):
                try:
                    shutil.copy2(save_path, cache_path)
                except Exception:
                    pass

            if QMessageBox.question(
                self, "导出成功",
                f"完整分析报告已导出到\n{save_path}\n\n"
                "包含Sheet:\n"
                "📋 分析说明 · 汇总统计(带预警颜色)\n"
                "完整偏差明细 · 替代料明细 · 无备注预警\n"
                "中间地带明细 · 异常预警 · 偏差金额分析\n"
                "偏差原因汇总 · 偏差原因分析 · 趋势分析\n\n"
                "是否立即打开？"
            ) == QMessageBox.Yes:
                os.startfile(save_path)
            self.log(f"已导出完整分析报告到 {save_path}", "info")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"导出完整报告失败: {e}")
            self.log(f"导出完整报告失败: {e}", "error")

    # -----------------------------------------------------------
    # 净偏差
    # -----------------------------------------------------------
    def _recalculate_net_offset(self, silent=False):
        df = self.view_model.df
        if df is None or df.empty:
            if not silent:
                QMessageBox.warning(self, "提示", "无数据")
            return
        from analysis.net_offset import apply_net_offset
        alt_pairs = self.alt_controller.get_pairs()
        if not alt_pairs:
            if not silent:
                QMessageBox.information(self, "提示", "没有替代料配对，已删除所有配对")
            df = df.copy()
            df["净偏差数量"] = df.get("偏差数量", 0)
            df["是否替代料"] = "否"
            self.view_model.df = df
            if self.source_model is not None:
                self.source_model.setDataFrame(df)
                self._apply_column_visibility_by_name()
                self.proxy_model.invalidate()
            self._on_view_model_data_changed()
            if not silent:
                self.statusBar().showMessage("净偏差已重置为原始值", 2000)
            return
        try:
            new_df = apply_net_offset(df, alt_pairs, group_key=["订单日期", "流程订单"])
            self.view_model.df = new_df
            if self.source_model is not None:
                self.source_model.setDataFrame(new_df)
                self._apply_column_visibility_by_name()
                self.proxy_model.invalidate()
            self._on_view_model_data_changed()
            if not silent:
                self.statusBar().showMessage("净偏差已重新计算", 2000)
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "错误", f"重算净偏差失败: {e}")
            else:
                self.log(f"重算净偏差失败: {e}", "error")

    # -----------------------------------------------------------
    # 右键菜单
    # -----------------------------------------------------------
    def _show_context_menu(self, pos: QPoint):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
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
        copy_action.triggered.connect(
            lambda: self.audit_controller.copy_material_code(row_data, self.statusBar().showMessage)
        )
        menu.addSeparator()
        mark_read_action = menu.addAction("标记为已读")
        mark_read_action.triggered.connect(
            lambda: self.audit_controller.batch_mark_read(selected_rows, self.source_model, 1, self.statusBar().showMessage)
        )
        mark_unread_action = menu.addAction("标记为未读")
        mark_unread_action.triggered.connect(
            lambda: self.audit_controller.batch_mark_read(selected_rows, self.source_model, 0, self.statusBar().showMessage)
        )
        menu.addSeparator()
        batch_status = menu.addAction("批量改状态")
        batch_status.triggered.connect(lambda: self.audit_controller.batch_change_status(selected_rows, self))
        batch_remark = menu.addAction("批量填备注")
        batch_remark.triggered.connect(lambda: self.audit_controller.batch_remark(selected_rows, self))
        batch_export = menu.addAction("批量导出")
        batch_export.triggered.connect(lambda: self._batch_export_wrapper(selected_rows))
        menu.addSeparator()
        copy_region_action = menu.addAction("复制选中区域")
        copy_region_action.triggered.connect(self.copy_selected_cells)
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _batch_export_wrapper(self, rows):
        df_subset = self.view_model.df.iloc[rows].copy()
        self.audit_controller.batch_export(rows, df_subset, self)

    # -----------------------------------------------------------
    # 表格复制
    # -----------------------------------------------------------
    def _install_table_copy_handler(self):
        self.table_view.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        if obj is self.table_view and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.matches(QKeySequence.Copy):
                self._copy_selected_cells()
                return True
        return super().eventFilter(obj, event)

    def copy_selected_cells(self):
        indexes = self.table_view.selectedIndexes()
        if not indexes:
            return
        rows = sorted(set(idx.row() for idx in indexes))
        cols = sorted(set(idx.column() for idx in indexes))
        proxy = self.table_view.model()
        source = proxy.sourceModel() if hasattr(proxy, "mapToSource") else proxy
        data = []
        for row in rows:
            row_data = []
            for col in cols:
                proxy_idx = proxy.index(row, col)
                if hasattr(proxy, "mapToSource"):
                    src_idx = proxy.mapToSource(proxy_idx)
                    value = source.data(src_idx, Qt.DisplayRole)
                else:
                    value = proxy.data(proxy_idx, Qt.DisplayRole)
                text = str(value) if value is not None else ""
                text = text.replace("\n", " ").replace("\r", "")
                row_data.append(text)
            data.append(row_data)
        lines = ["\t".join(row) for row in data]
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage(f"已复制 {len(rows)} 行 × {len(cols)} 列", 2000)

    def _copy_selected_cells(self):
        tv = self.table_view
        model = tv.model()
        selection = tv.selectionModel()
        indexes = selection.selectedIndexes()
        if not indexes:
            return
        cells = {}
        min_row, max_row = float('inf'), -1
        min_col, max_col = float('inf'), -1
        for idx in indexes:
            r, c = idx.row(), idx.column()
            cells[(r, c)] = idx.data(Qt.DisplayRole) or ""
            min_row = min(min_row, r)
            max_row = max(max_row, r)
            min_col = min(min_col, c)
            max_col = max(max_col, c)
        lines = []
        for r in range(min_row, max_row + 1):
            row_vals = []
            for c in range(min_col, max_col + 1):
                row_vals.append(str(cells.get((r, c), "")))
            lines.append("\t".join(row_vals))
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage(f"已复制 {max_row - min_row + 1} 行 × {max_col - min_col + 1} 列", 2000)

    # -----------------------------------------------------------
    # 双击明细
    # -----------------------------------------------------------
    def _on_cell_double_clicked(self, index):
        try:
            if self.proxy_model and self.source_model:
                source_index = self.proxy_model.mapToSource(index)
                row = source_index.row()
                df = self.source_model.getDataFrame()
                if row < len(df):
                    row_data = df.iloc[row]
                    self._show_row_detail(row_data)
                else:
                    self.log(f"双击弹窗: row={row} 超出范围 len={len(df)}", "warn")
            else:
                self.log(f"双击弹窗失败: proxy_model={self.proxy_model}, source_model={self.source_model}", "error")
        except Exception as e:
            import traceback
            self.log(f"双击弹窗失败: {e}\n{traceback.format_exc()}", "error")

    def _show_row_detail(self, row_data):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox
        from PySide6.QtCore import Qt
        def _val(*keys):
            for k in keys:
                if k in row_data.index:
                    v = row_data[k]
                    if not (v is None or (pd.isna(v) if not isinstance(v, str) else False)):
                        return v
                for col in row_data.index:
                    if col.strip() == k:
                        v = row_data[col]
                        if not (v is None or (pd.isna(v) if not isinstance(v, str) else False)):
                            return v
            return ""
        dialog = QDialog(self)
        mat_code = _val("物料编码", "物料号")
        mat_name = _val("物料描述", "物料名称", "物料")
        dialog.setWindowTitle(f"明细 - {mat_code} {mat_name}")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        def _mk_label(text=""):
            lbl = QLabel(str(text))
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return lbl
        gb1 = QGroupBox("基本信息")
        fl1 = QFormLayout(gb1)
        for label, keys in [("工厂", ["工厂", "工厂名称"]), ("车间", ["车间"]), ("订单日期", ["订单日期"]), ("流程订单", ["流程订单"]), ("物料编码", ["物料编码", "物料号"]), ("物料描述", ["物料描述", "物料名称"]), ("物料大类", ["物料大类", "物料类型"])]:
            fl1.addRow(f"{label}：", _mk_label(_val(*keys)))
        layout.addWidget(gb1)
        gb2 = QGroupBox("偏差数据")
        fl2 = QFormLayout(gb2)
        for label, keys in [("定额用量", ["定额"]), ("实际用量", ["实际"]), ("偏差数量", ["偏差数量"]), ("偏差率", ["偏差率", "偏差率(%)"]), ("偏差金额", ["偏差金额"]), ("总偏差金额(含税)", ["总偏差金额(含税)", "偏差金额"]), ("审核结果", ["审核结果", "audit_result"])]:
            val = _val(*keys)
            display = str(val)
            if "偏差率" in label and val:
                try: display = f"{float(val):.2f}%"
                except: pass
            fl2.addRow(f"{label}：", _mk_label(display))
        layout.addWidget(gb2)
        gb3 = QGroupBox("备注与建议")
        fl3 = QFormLayout(gb3)
        remark_label = _mk_label(_val("备注原因", "备注"))
        remark_label.setWordWrap(True)
        fl3.addRow("备注：", remark_label)
        ai_label = _mk_label(_val("AI建议"))
        ai_label.setWordWrap(True)
        fl3.addRow("AI建议：", ai_label)
        layout.addWidget(gb3)
        btn = QDialogButtonBox(QDialogButtonBox.Ok)
        btn.accepted.connect(dialog.accept)
        layout.addWidget(btn)
        dialog.exec()

    # -----------------------------------------------------------
    # 工具函数
    # -----------------------------------------------------------
    def _update_countdown(self):
        self._countdown_seconds += 1
        m, s = divmod(self._countdown_seconds, 60)
        self.progress_label.setText(f"{self._current_step} | ⏱ {m:02d}:{s:02d}")

    def _stop_countdown(self):
        if hasattr(self, "_countdown_timer") and self._countdown_timer is not None:
            try:
                self._countdown_timer.stop()
            except Exception:
                pass

    def _format_elapsed(self):
        m, s = divmod(self._countdown_seconds, 60)
        return f"{m:02d}:{s:02d}"

    def _show_benefit_report(self):
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        dialog = BenefitReportDialog(self, self.view_model.df)
        dialog.exec()

    def _open_rule_config(self):
        rules_path = os.path.join(os.path.dirname(__file__), "..", "config", "system", "rules.json")
        def on_rules_changed():
            self.audit_controller.rule_engine.load_rules()
            if self.view_model.df is not None:
                processed_df = self.data_service.preprocess_audit_data(self.view_model.df, self.view_model.df)
                self.source_model.setDataFrame(processed_df)
                self._apply_column_visibility_by_name()
                self.view_model.df = processed_df
        dialog = RuleConfigDialog(self, rules_path, self.config_manager, on_rules_changed)
        dialog.exec()

    def _show_health_check(self):
        dialog = HealthCheckDialog(self)
        dialog.exec()

    def _show_unit_summary(self):
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "无数据")
            return
        dialog = UnitSummaryDialog(self, self.view_model.df)
        dialog.exec()

    def _show_about(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame, QTextBrowser
        dialog = QDialog(self)
        dialog.setWindowTitle(f"关于 - ZPP011 v{get_current_version()}")
        dialog.setMinimumSize(680, 560)
        dialog.setObjectName("aboutDialog")
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部信息区
        info_frame = QFrame()
        info_frame.setObjectName("aboutInfoFrame")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(28, 24, 28, 16)
        title_row = QHBoxLayout()
        icon_label = QLabel("\U0001F3ED")
        title_label = QLabel(f"{APP_NAME} v{get_current_version()}")
        title_label.setObjectName("aboutTitle")
        title_row.addWidget(icon_label)
        title_row.addWidget(title_label)
        info_layout.addLayout(title_row)
        desc_label = QLabel("功能：偏差分析 · AI审核 · 规则配置 · 批量操作")
        desc_label.setObjectName("aboutDesc")
        info_layout.addWidget(desc_label)
        author_label = QLabel(f"制作人：{AUTHOR} | 云南达利食品")
        author_label.setObjectName("aboutAuthor")
        info_layout.addWidget(author_label)
        main_layout.addWidget(info_frame)

        # 版本日志区
        log_label = QLabel("📜 版本日志")
        log_label.setObjectName("aboutSectionLabel")
        log_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 8px 28px 4px;")
        main_layout.addWidget(log_label)

        log_browser = QTextBrowser()
        log_browser.setObjectName("versionLogBrowser")
        log_browser.setOpenExternalLinks(False)
        log_browser.setStyleSheet("border: none; background-color: #fafbfc; padding: 8px;")
        html = self._build_version_log_html()
        log_browser.setHtml(html)
        main_layout.addWidget(log_browser, 1)

        # 底部按钮
        btn_frame = QFrame()
        btn_frame.setObjectName("aboutBtnFrame")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(88, 34)
        close_btn.setObjectName("aboutCloseBtn")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        main_layout.addWidget(btn_frame)
        dialog.exec()

    def _build_version_log_html(self):
        """生成版本日志 HTML"""
        html_parts = ["<style>"
                      "body { font-family: 'Microsoft YaHei', sans-serif; font-size: 12px; color: #1f2328; }"
                      ".ver { font-weight: bold; color: #0969da; font-size: 13px; margin-top: 12px; }"
                      ".date { color: #656d76; font-size: 11px; margin-left: 8px; }"
                      ".section { color: #1f2328; font-weight: 600; margin-top: 6px; }"
                      "ul { margin: 2px 0 6px 0; padding-left: 20px; }"
                      "li { margin: 2px 0; }"
                      "</style>"]
        for i, v in enumerate(VERSION_HISTORY):
            ver = v.get("version", "")
            date = v.get("date", "")
            html_parts.append(f'<div class="ver">{ver}<span class="date">{date}</span></div>')
            for section_key, section_title in [("features", "✦ 新功能"), ("fixes", "🔧 修复"), ("optimizations", "⚡ 优化"), ("notes", "📌 说明")]:
                items = v.get(section_key, [])
                if items:
                    html_parts.append(f'<div class="section">{section_title}</div><ul>')
                    for item in items:
                        html_parts.append(f'<li>{item}</li>')
                    html_parts.append('</ul>')
        return "".join(html_parts)

    def _show_import_wizard(self):
        dialog = ImportWizard(self)
        dialog.exec()

    def _show_history_compare(self):
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return
        dialog = HistoryCompareDialog(self)
        dialog.exec()

    def _show_dashboard(self):
        audit_df = self.view_model.df
        if audit_df is None or audit_df.empty:
            QMessageBox.warning(self, "提示", "无数据，请先进行分析")
            return
        # material_df 暂无独立来源，传 None（DashboardDialog 内部仅预留）
        dialog = DashboardDialog(audit_df, None, parent=self, main_window=self)
        dialog.exec()

    def _show_source_backup(self):
        """打开历史源码备份目录"""
        from PySide6.QtWidgets import QMessageBox
        
        backup_dir = os.path.expanduser("~/.zpp011_audit/source_backups")
        if not os.path.exists(backup_dir):
            QMessageBox.information(self, "提示", f"源码备份目录不存在:\n{backup_dir}\n\n请先运行一次打包脚本以生成备份")
            return
        
        # 尝试打开文件夹
        if sys.platform == "win32":
            os.startfile(backup_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", backup_dir])
        else:
            subprocess.Popen(["xdg-open", backup_dir])
        
        QMessageBox.information(self, "已打开", f"已打开源码备份目录:\n{backup_dir}")

    def _toggle_filter_panel(self):
        """切换右侧筛选面板（FilterPanel）的显示/隐藏"""
        if self.filter_panel.isVisible():
            self.filter_panel.setVisible(False)
            prev_sizes = self.body_splitter.sizes()
            # 将 FilterPanel 的宽度加到右侧表格区域
            self.body_splitter.setSizes([prev_sizes[0], 0, prev_sizes[2] + prev_sizes[1]])
            self.action_btn_filter.setText("🔍 显示筛选")
            self.action_btn_filter.setChecked(False)
        else:
            self.filter_panel.setVisible(True)
            self.filter_panel.setFixedWidth(280)
            prev_sizes = self.body_splitter.sizes()
            # left_panel | filter_panel | table_area
            self.body_splitter.setSizes([prev_sizes[0], 280, prev_sizes[2]])
            self.action_btn_filter.setText("🔍 隐藏筛选")
            self.action_btn_filter.setChecked(True)

    def _toggle_alt_panel(self):
        if hasattr(self, "_alt_panel_shown") and self._alt_panel_shown:
            self.left_panel.setVisible(False)
            self._alt_panel_shown = False
        else:
            self.left_panel.setVisible(True)
            self._alt_panel_shown = True

    def closeEvent(self, event):
        # 保存列宽配置
        self._save_column_widths()
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            self.analysis_controller.cancel()
        if self.audit_controller.ai_worker and self.audit_controller.ai_worker.isRunning():
            self.audit_controller.cancel_ai_audit()
        if hasattr(self, "alert_monitor") and self.alert_monitor.isRunning():
            self.alert_monitor.stop()
        if self._cache_worker:
            if self._cache_worker.isRunning():
                self._cache_worker.quit()
                self._cache_worker.wait(3000)
            else:
                self._cache_worker.wait(3000)
            self._cache_worker = None
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    sys.exit(app.exec())
