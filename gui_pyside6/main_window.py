# -*- coding: utf-8 -*-
"""
ZPP011 主窗口 (PySide6 迁移版)
布局：标题栏 + 操作栏 + 侧栏 + 数据表格 + 日志面板
暗色主题 v43.0 | 裴哥 2026-06-23
"""

import sys
import logging
import os
import time
import json
from datetime import datetime
import pandas as pd
import numpy as np
import subprocess
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QHeaderView, QDialog, QDialogButtonBox, QSplitter,
    QComboBox, QAbstractItemView, QMessageBox, QTableWidgetItem, QTableWidget,
    QMenu, QSizePolicy, QGroupBox, QFormLayout, QProgressDialog,
    QListWidget, QListWidgetItem, QScrollArea, QGridLayout, QCheckBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QTimer, QItemSelection, QItemSelectionModel
from PySide6.QtGui import QFont, QFontMetrics, QShortcut, QKeySequence, QAction

# 导入组件
from gui_pyside6.components.menu_bar import MenuBarComponent
from gui_pyside6.components.title_bar import TitleBarWidget
from gui_pyside6.components.left_panel import LeftPanelComponent
from gui_pyside6.components.main_table import MainTableComponent
from gui_pyside6.components.bottom_bar import BottomBarComponent

# 导入自定义模块
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.widgets.toast import toast
from gui_pyside6.widgets.filter_panel import FilterPanel
from gui_pyside6.widgets.stats_cards import StatsCardsWidget
from gui_pyside6.widgets.unread_summary_popup import UnreadSummaryPopup
from gui_pyside6.dialogs.unit_summary_dialog import UnitSummaryDialog
from gui_pyside6.dialogs.alert_dialog import AlertDialog
from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog
from gui_pyside6.dialogs.neg_loss_dashboard_dialog import NegLossDashboardDialog
from gui_pyside6.dialogs.quarantine_dialog import QuarantineDialog
from core.quarantine_manager import add_quarantine, add_quarantine_batch, remove_quarantine, scan_expired_quarantine, get_quarantined_ids
from core.auto_quarantine import (
    build_all_summary,
    compute_auto_quarantine_ids,
    load_auto_quarantine_config,
)
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
from gui_pyside6.dialogs.history_compare_dialog import HistoryCompareDialog
from gui_pyside6.dialogs.import_wizard_dialog import ImportWizard
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


class _FullReportWorker(QThread):
    """后台生成完整多Sheet报告，进度/完成/失败均通过信号回主线程。"""
    progress = Signal(int, str)      # (百分比, 步骤名)
    finished_ok = Signal(str)        # (输出路径)
    failed = Signal(str)             # (错误信息)

    def __init__(self, input_file, alt_pairs, start_date, end_date,
                 material_search, output_path, parent=None, dyn_thresh=None):
        super().__init__(parent)
        self.input_file = input_file
        self.alt_pairs = alt_pairs
        self.start_date = start_date
        self.end_date = end_date
        self.material_search = material_search
        self.output_path = output_path
        self.dyn_thresh = dyn_thresh
        self._cancel = False

    def request_cancel(self):
        self._cancel = True

    def run(self):
        from analysis.analyzer import do_analysis_v2
        from core.config_manager import ConfigManager
        try:
            _cfg = ConfigManager()
            do_analysis_v2(
                input_file=self.input_file, output_dir=None,
                alt_pairs=self.alt_pairs,
                progress_callback=lambda step_idx, step_name, percent: (
                    self.progress.emit(percent, step_name),
                    self._cancel,
                )[1] if self._cancel_check() else self.progress.emit(percent, step_name),
                cancel_check=self._cancel_check,
                start_date=self.start_date, end_date=self.end_date,
                material_search=self.material_search,
                output_path=self.output_path,
                enable_net_offset=_cfg.get_net_offset_enabled(),
                return_dataframe=False,
                dyn_thresh=self.dyn_thresh,
            )
            if self._cancel:
                self.failed.emit("已取消")
                return
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self.failed.emit(str(e))

    def _cancel_check(self, *args):
        return self._cancel


class _PptViewShim:
    """适配 MainWindow.view_model.df 给 AuditPresenter.generate_ppt 使用。

    generate_ppt 依赖 view.get_audit_data() / get_output_path() / log()，
    而 MainWindow 用的是 view_model.df，这里做一层桥接。
    """

    def __init__(self, df, log_emit):
        self._df = df
        self._log_emit = log_emit  # callable(msg, level)，由 worker 转成跨线程信号

    def get_audit_data(self):
        return self._df

    def get_output_path(self):
        # generate_ppt 调用方已显式传入 output_path，这里返回 None 即可
        return None

    def log(self, msg, level='info'):
        try:
            self._log_emit(msg, level)
        except Exception:
            pass


class _PptReportWorker(QThread):
    """后台调用 build_ppt_net.build_net_report 生成净偏差口径 PPT（不锁界面）。"""
    progress = Signal(int, str)      # (百分比, 步骤名)
    finished_ok = Signal(str)        # (输出路径)
    failed = Signal(str)             # (错误信息)
    _log = Signal(str, str)          # (msg, level) -> 主线程日志

    def __init__(self, df, output_path, src_name=None, parent=None):
        super().__init__(parent)
        self.df = df
        self.output_path = output_path
        self.src_name = src_name

    def run(self):
        try:
            import os as _os
            import sys as _sys
            _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from build_ppt_net import build_net_report
            build_net_report(self.df, self.output_path, src_name=self.src_name)
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self.failed.emit(str(e))


class _FileReadWorker(QThread):
    """后台读取 SAP Excel，避免大文件阻塞主线程（文件选择卡顿修复）"""
    loaded = Signal(object, str)   # (df, file_path)
    failed = Signal(str)           # (错误信息)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            xl = pd.ExcelFile(self.file_path)
            sheets = xl.sheet_names
            target = "Data" if "Data" in sheets else sheets[0]
            df = pd.read_excel(self.file_path, sheet_name=target)
            self.loaded.emit(df, self.file_path)
        except Exception as e:
            self.failed.emit(str(e))


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
        self._full_report_worker = None
        self._file_worker = None
        # v42.26: 这两个后台 worker 此前从未初始化。_ai_preprocess_worker 在
        # _on_ai_preprocess_error() 中被读取，未初始化时会直接 AttributeError；
        # _ppt_worker 在 closeEvent 里需要收尾，同样需要一个稳定的初始值。
        self._ppt_worker = None
        self._ai_preprocess_worker = None
        # 全局"重型操作进行中"标志：分析 / 缓存生成 / 完整报告导出共用，
        # 用于防止多个 do_analysis_v2 并发抢占 GIL 导致 UI 假死（"未响应"）。
        self._heavy_busy = False
        self.sort_columns = []
        self._countdown_seconds = 0
        self._countdown_timer = None
        self._analysis_start_ts = 0.0
        # 半成品分类列表（从 config/semi_user_categories.json 加载，运行时可追加）
        self._semi_categories = self._load_semi_categories()
        # 按"列名"记录需要隐藏的列（避免 setDataFrame 重排列后索引错位导致列丢失）
        self._hidden_column_names = {
            '_post_audit_changed', 'data_id', 'fingerprint', '_quarantined',
        }  # 内部技术列默认隐藏（用户无需看到）

        # 控制器
        self.analysis_controller = AnalysisController(self)
        self.audit_controller = AuditController(self)
        self.audit_controller.manual_marked.connect(self._on_manual_marked)
        # 状态栏常驻「分析时间」：最近一次分析的触发方式(自动/手动) + 完成时刻
        # （windowed exe 无控制台，自动读取/自动分析后用户无从知晓何时发生，故常驻显示）
        self._analysis_time_label = QLabel("🕒 分析：—")
        self._analysis_time_label.setObjectName("analysisTimeLabel")
        self._analysis_time_label.setToolTip(
            "最近一次分析的触发方式与时刻：手动=点「分析」按钮/F5；自动=文件夹监控自动读取后自动分析"
        )
        # 醒目样式：加粗琥珀色字 + 左边框分隔，与蓝字「已读」标签区分
        self._analysis_time_label.setStyleSheet(
            "QLabel#analysisTimeLabel{padding:2px 10px;font-weight:bold;color:#8a5a00;"
            "border-left:1px solid #b8c4d0;}"
        )
        self.statusBar().addPermanentWidget(self._analysis_time_label)

        # 状态栏常驻「已读计数」：自动 N / 手动 M（每批数据清零，见 _on_file_loaded）
        self._auto_read_count = 0
        self._manual_read_count = 0
        self._read_counter_label = QLabel("📖 已读：自动 0 / 手动 0")
        self._read_counter_label.setObjectName("readCounterLabel")
        self._read_counter_label.setToolTip("本次数据中自动已读 / 手动标记已读的累计条数")
        # 醒目样式：加粗蓝字 + 左边框分隔，避免用户注意不到
        self._read_counter_label.setStyleSheet(
            "QLabel#readCounterLabel{padding:2px 10px;font-weight:bold;color:#15598c;"
            "border-left:1px solid #b8c4d0;}"
        )
        self.statusBar().addPermanentWidget(self._read_counter_label)
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
        # 关闭自动弹窗（变动提醒表格 / 新替代料预警弹窗），避免阻塞主线程导致「未响应」。
        # 手动按钮（变动提醒 / 替代料看板 / 偏差率预警）仍可用。
        self._auto_pop_alerts = False
        # 未读汇总弹窗：分析/加载完成后自动弹（非模态、延迟渲染，安全不卡顿）
        self._pending_unread_summary = False
        self._unread_popup = None

        # 创建组件
        self.menu_bar = MenuBarComponent(self)
        self.title_bar = TitleBarWidget(get_current_version(), self)
        self.left_panel_component = LeftPanelComponent(self)
        self.main_table = MainTableComponent(self)
        self.stats_cards = StatsCardsWidget(self)  # 统计卡片（审核概览 + 变更感知）
        self.bottom_bar = BottomBarComponent(self)
        self.filter_panel = FilterPanel(self)

        # 文件夹监控自动加载（SAP 导出半自动：监控目录有新 Excel 则自动加载）
        self._monitor_dir = r"E:\ZPP011导出文件原数据"
        self._monitor_enabled = True   # 默认开启
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(2000)  # 每 2 秒扫描一次
        self._monitor_timer.timeout.connect(self._scan_monitor_dir)
        self._monitor_last_size = {}   # path -> 上次文件大小（用于判定文件写完）
        self._monitor_loaded = set()   # (path, mtime, size) 已自动加载的文件指纹
        self._monitor_pending = set()  # (path, mtime, size) 已排队等待加载（避免重复排队）
        self._monitor_current_key = None  # 当前正在自动加载的文件指纹
        self._monitor_auto_loading = False  # 是否正在由监控触发自动加载
        self._expired_q_cache = {}  # 隔离区失效复核缓存：uid -> 明细
        self._expired_q_notified = set()  # 本会话已弹窗告知过的失效 uid（避免重复打扰）
        self._monitor_delay_ms = 5000  # 检测到新文件后延迟加载的毫秒数（等用户关闭自动打开的预览）
        self._monitor_busy_retry = 6   # 文件仍被占用时的重试次数
        self._monitor_busy_interval = 3000  # 被占用时每次重试间隔(ms)
        # 默认开启：以当前目录最新文件为基线（不立即分析），只监控「新导出」的文件
        self._seed_monitor_baseline()
        self._monitor_timer.start()

        # UI 引用（必须在 _setup_connections 之前赋值）
        self.left_panel = self.left_panel_component.left_panel
        self._refresh_semi_list_ui()  # 初始化半成品列表显示
        self.filter_panel = self.filter_panel  # Already created above
        # input_file_edit / output_dir_edit / preview_label 由 LeftPanelComponent 创建
        # 标题栏是子控件，不是顶层窗口，不需要 setWindowFlags
        self.progress_bar = self.main_table.progress_bar
        self.progress_label = self.main_table.progress_label
        self.timer_lbl = self.main_table.timer_lbl
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
        # self.start_btn 别名在工具栏创建后赋值（见下方 action_bar 构建末尾）
        # self.cancel_btn = self.main_table.cancel_btn  # 底部操作按钮已删除
        self.lock_btn = self.main_table.lock_btn
        self.fullscreen_btn = self.main_table.fullscreen_btn
        self.unit_summary_btn = self.main_table.unit_summary_btn
        self._is_fullscreen = False

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
        self.showMaximized()

        self.title_bar.theme_toggled.connect(self._toggle_theme)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self).activated.connect(self._start_analysis)
        QShortcut(QKeySequence("F6"), self).activated.connect(
            lambda: self.export_controller.export_current_table(
                self.view_model.df, self
            )
        )
        QShortcut(QKeySequence("F7"), self).activated.connect(self._generate_ppt_report)
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            lambda: self._batch_mark_selected_read(1)
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

        self.action_btn_left_panel = QPushButton("☰ 隐藏左侧栏")
        self.action_btn_left_panel.setCheckable(True)
        self.action_btn_left_panel.setChecked(True)
        self.action_btn_left_panel.setCursor(Qt.PointingHandCursor)
        self.action_btn_left_panel.setObjectName("actionBtnLeftPanel")
        self.action_btn_left_panel.setProperty("class", "actionBtn")
        self.action_btn_left_panel.clicked.connect(self._toggle_left_panel)

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
            lambda: self.export_controller.export_current_table(self._get_displayed_dataframe(), self)
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
        self.action_btn_ppt.clicked.connect(self._generate_ppt_report)

        shortcut_hint = QLabel("F5:分析 | F6:导出 | F7:效益 | F11:全屏")
        shortcut_hint.setObjectName("shortcutHint")

        action_layout.addWidget(self.action_btn_left_panel)
        action_layout.addWidget(self.action_btn_filter)
        action_layout.addWidget(self.action_btn_analyze)
        action_layout.addWidget(self.action_btn_ai)
        action_layout.addWidget(spacer2)
        action_layout.addWidget(self.action_btn_excel)
        action_layout.addWidget(self.action_btn_export_full)
        action_layout.addWidget(self.action_btn_ppt)

        self.action_btn_dashboard = QPushButton("📊 管理看板")
        self.action_btn_dashboard.setCursor(Qt.PointingHandCursor)
        self.action_btn_dashboard.setObjectName("actionBtnDashboard")
        self.action_btn_dashboard.setProperty("class", "actionBtn")
        self.action_btn_dashboard.clicked.connect(self._show_dashboard)
        action_layout.addWidget(self.action_btn_dashboard)

        self.action_btn_quarantine = QPushButton("⚠️ 隔离区")
        self.action_btn_quarantine.setCursor(Qt.PointingHandCursor)
        self.action_btn_quarantine.setObjectName("actionBtnQuarantine")
        self.action_btn_quarantine.setProperty("class", "actionBtn")
        self.action_btn_quarantine.clicked.connect(self._open_quarantine_dialog)
        action_layout.addWidget(self.action_btn_quarantine)

        self.action_btn_audit_changes = QPushButton("📝 变动提醒")
        self.action_btn_audit_changes.setCursor(Qt.PointingHandCursor)
        self.action_btn_audit_changes.setObjectName("actionBtnAuditChanges")
        self.action_btn_audit_changes.setProperty("class", "actionBtn")
        self.action_btn_audit_changes.clicked.connect(self._show_audit_changes_dialog)
        action_layout.addWidget(self.action_btn_audit_changes)

        self.action_btn_alt_board = QPushButton("🔔 替代料看板")
        self.action_btn_alt_board.setCursor(Qt.PointingHandCursor)
        self.action_btn_alt_board.setObjectName("actionBtnAltBoard")
        self.action_btn_alt_board.setProperty("class", "actionBtn")
        self.action_btn_alt_board.clicked.connect(self._show_alert_dashboard)
        action_layout.addWidget(self.action_btn_alt_board)

        self.action_btn_deviation = QPushButton("📊 偏差率预警")
        self.action_btn_deviation.setCursor(Qt.PointingHandCursor)
        self.action_btn_deviation.setObjectName("actionBtnDeviation")
        self.action_btn_deviation.setProperty("class", "actionBtn")
        self.action_btn_deviation.clicked.connect(self._show_deviation_warning_dialog)
        action_layout.addWidget(self.action_btn_deviation)

        self.action_btn_neg_loss = QPushButton("🟠 负损看板")
        self.action_btn_neg_loss.setCursor(Qt.PointingHandCursor)
        self.action_btn_neg_loss.setObjectName("actionBtnNegLoss")
        self.action_btn_neg_loss.setProperty("class", "actionBtn")
        self.action_btn_neg_loss.clicked.connect(self._show_neg_loss_dashboard)
        action_layout.addWidget(self.action_btn_neg_loss)

        self.action_btn_auto_q = QPushButton("🧹 自动整理隔离区")
        self.action_btn_auto_q.setCursor(Qt.PointingHandCursor)
        self.action_btn_auto_q.setObjectName("actionBtnAutoQ")
        self.action_btn_auto_q.setProperty("class", "actionBtn")
        self.action_btn_auto_q.setToolTip(
            "按规则自动移入隔离区：" + build_all_summary(load_auto_quarantine_config()))
        self.action_btn_auto_q.clicked.connect(lambda: self._auto_move_to_quarantine(manual=True))
        action_layout.addWidget(self.action_btn_auto_q)

        self.action_btn_auto_q_rule = QPushButton("⚙ 规则")
        self.action_btn_auto_q_rule.setCursor(Qt.PointingHandCursor)
        self.action_btn_auto_q_rule.setObjectName("actionBtnAutoQRule")
        self.action_btn_auto_q_rule.setProperty("class", "actionBtn")
        self.action_btn_auto_q_rule.setToolTip("规则中心（自动隔离 / 自动已读）")
        self.action_btn_auto_q_rule.clicked.connect(self._open_rule_center)
        action_layout.addWidget(self.action_btn_auto_q_rule)

        action_layout.addStretch()

        # 面板显隐切换按钮（当面板被“隐藏”后，可在此恢复显示）
        self.action_btn_toggle_stats = QPushButton("📊 概览")
        self.action_btn_toggle_stats.setCursor(Qt.PointingHandCursor)
        self.action_btn_toggle_stats.setObjectName("actionBtnToggleStats")
        self.action_btn_toggle_stats.setProperty("class", "actionBtn")
        self.action_btn_toggle_stats.setToolTip("显示/隐藏「本次分析概览」面板")
        self.action_btn_toggle_stats.clicked.connect(self._toggle_stats_from_toolbar)
        action_layout.addWidget(self.action_btn_toggle_stats)

        self.action_btn_toggle_progress = QPushButton("⚡ 进度")
        self.action_btn_toggle_progress.setCursor(Qt.PointingHandCursor)
        self.action_btn_toggle_progress.setObjectName("actionBtnToggleProgress")
        self.action_btn_toggle_progress.setProperty("class", "actionBtn")
        self.action_btn_toggle_progress.setToolTip("显示/隐藏「分析进度」面板")
        self.action_btn_toggle_progress.clicked.connect(self._toggle_progress_from_toolbar)
        action_layout.addWidget(self.action_btn_toggle_progress)

        # v42.29: 工具栏「📋 未读概览」按钮——分析后已弹的弹窗可被数据/面板挡住，
        # 用户随时可点击重开。复用 _show_unread_summary 的单例机制 + force 选项，
        # 全已读时也会弹出并显示 0 条 + "全清零啦"。
        self.action_btn_unread_summary = QPushButton("📋 未读概览")
        self.action_btn_unread_summary.setCursor(Qt.PointingHandCursor)
        self.action_btn_unread_summary.setObjectName("actionBtnUnreadSummary")
        self.action_btn_unread_summary.setProperty("class", "actionBtn")
        self.action_btn_unread_summary.setToolTip("打开「未读概览」弹窗（隔离区/变动提醒/替代料/偏差率预警）")
        self.action_btn_unread_summary.clicked.connect(lambda: self.show_unread_summary(force=True))
        action_layout.addWidget(self.action_btn_unread_summary)

        action_layout.addWidget(shortcut_hint)

        # 底部按钮行已删除，start_btn 别名指向顶部工具栏分析按钮（供分析起止启用/禁用）
        self.start_btn = self.action_btn_analyze

        main_layout.addWidget(action_bar)

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
        right_layout.setSpacing(6)

        # 上半部分：本次分析概览 + 分析进度（用户可拖动，默认占较小空间）
        self.top_panel = QWidget()
        self.top_panel.setObjectName("topPanel")
        top_layout = QVBoxLayout(self.top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        top_layout.addWidget(self.stats_cards)                # 📊 本次分析概览
        top_layout.addWidget(self.main_table.progress_group)  # ⚡ 分析进度
        self.top_panel.setMaximumHeight(240)                       # 限制最大高度，不抢表格空间

        # 垂直分割器：仅表格（运行日志已移除，空间全部给表格）
        self._v_splitter = QSplitter(Qt.Vertical)
        self._v_splitter.setChildrenCollapsible(True)
        self._v_splitter.addWidget(self.main_table.audit_widget)
        self._v_splitter.setStretchFactor(0, 1)

        # 右侧整体垂直分割器：上面概览/进度，下面表格
        # 用户可拖动中间分隔线，把上面压扁以显示更多表格行
        self._right_v_splitter = QSplitter(Qt.Vertical)
        self._right_v_splitter.setChildrenCollapsible(True)
        self._right_v_splitter.addWidget(self.top_panel)
        self._right_v_splitter.addWidget(self._v_splitter)
        self._right_v_splitter.setSizes([150, 650])
        self._right_v_splitter.setStretchFactor(0, 0)
        self._right_v_splitter.setStretchFactor(1, 1)

        right_layout.addWidget(self._right_v_splitter, 1)
        right_layout.addWidget(self.main_table.summary_container, 0)

        self.body_splitter.addWidget(right_container)
        self.body_splitter.setSizes([260, 440, 860])

        main_layout.addWidget(self.body_splitter, 1)

    def _setup_connections(self):
        self.main_table.table_view.doubleClicked.connect(self._on_cell_double_clicked)
        self._install_table_copy_handler()

        self.analysis_controller.analysis_started.connect(self._on_analysis_ui_start)
        self.analysis_controller.progress_updated.connect(self._on_analysis_progress_ui)
        self.analysis_controller.log_message.connect(self.log)
        self.export_controller.log_message.connect(self.log)
        self.audit_controller.log_message.connect(self.log)
        self.analysis_controller.analysis_finished.connect(self._on_analysis_finished_ui)
        self.stats_cards.card_clicked.connect(self._on_stats_card_clicked)
        self.stats_cards.visibility_changed.connect(self._on_stats_visibility_changed)
        self.main_table.progress_visibility_changed.connect(self._on_progress_visibility_changed)
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
            # 变动明细已记录在 data_service.last_audit_changes，工具栏「变动提醒」按钮可随时手动查看。
            # 自动弹窗已关闭（self._auto_pop_alerts=False），避免阻塞主线程 / 误触冻结。
            if getattr(self, "_auto_pop_alerts", False):
                # 关键修复：原实现在数据预处理（preprocess_audit_data）执行栈内
                # 同步弹出模态对话框——此时主表 setDataFrame 尚未执行、模型处于
                # 不一致状态，且弹窗阻塞会触发 Qt 层崩溃（无 Python 堆栈直接退出）。
                # 改为推迟到下一轮事件循环（当前分析→预处理→setDataFrame 全部结束后）
                # 再弹窗，此时主表已刷新、调用栈已展开，彻底规避死锁/崩溃。
                QTimer.singleShot(0, self._show_audit_changes_dialog)
            else:
                self.log(msg, level)
        else:
            self.log(msg, level)

    def _show_audit_changes_dialog(self):
        # 防重入：延迟触发期间若弹窗已开，跳过（避免堆叠多个模态框导致崩溃）
        if getattr(self, '_audit_changes_dialog_open', False):
            return
        # 顶部工具栏：显示已审核记录变更明细（alert 与手动点击均复用）。
        # 单一数据源：从主表 df 的 _post_audit_changed==1（且未读）行重算，
        # 与未读概览弹窗/标记统计共用同一真相，不再依赖易失的 last_audit_changes 列表。
        _adf = self.source_model.getDataFrame() if self.source_model else getattr(self.view_model, 'df', None)
        changes = self.data_service.get_audit_changes(_adf) if (_adf is not None and not getattr(_adf, 'empty', True)) else []
        if not changes:
            QMessageBox.information(self, "变动提醒", "暂无已审核记录变动。")
            return
        count = len(changes)
        MAX_DISPLAY = 3000
        display_len = min(count, MAX_DISPLAY)
        # 自定义对话框：表格展示变更明细 + 筛选/搜索/排序/复制/双击定位 + 手动导出
        self._audit_changes_dialog_open = True
        dlg = QDialog(self)
        dlg.setWindowTitle(f"变动提醒（{count} 条）")
        dlg.resize(1100, 600)
        # 允许最大化/最小化（Windows 上最大化按钮需与最小化成对才稳定显示）
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowMinMaxButtonsHint)
        layout = QVBoxLayout(dlg)

        # 工具栏：字段筛选 + 关键字搜索
        tool_bar = QHBoxLayout()
        tool_bar.addWidget(QLabel("字段:"))
        field_combo = QComboBox()
        field_combo.addItems(["全部字段", "实际数量", "备注原因"])
        tool_bar.addWidget(field_combo)
        tool_bar.addSpacing(12)
        tool_bar.addWidget(QLabel("搜索:"))
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("日期 / 车间 / 流程订单 / 物料编码 / 物料名称")
        tool_bar.addWidget(search_edit, 1)
        layout.addLayout(tool_bar)

        extra = f"（仅显示前 {display_len} 条，共 {count} 条；导出按钮可导出全部）" if count > display_len else ""
        tip = QLabel(f"发现 {count} 条已审核记录的实际数量/备注原因发生变动，已强制设为'未读'。\n（表格可排序/筛选/搜索，右键复制单元格或整行，双击定位到主表对应行）{extra}")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        table = QTableWidget(dlg)
        cols = ["日期", "车间", "流程订单", "物料编码", "物料名称", "变更字段", "旧值", "新值"]
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 支持 Ctrl/Shift 多选，点击行即高亮选中
        table.verticalHeader().setVisible(False)
        layout.addWidget(table)

        # 待处理变动列表（标记已读后从此移除并刷新表格）；行内 UserRole 存 remaining 索引，排序/部分标记后仍可正确映射
        remaining = list(changes)

        def _populate(show_list, with_progress=False):
            table.setSortingEnabled(False)
            table.setRowCount(len(show_list))
            prog = None
            if with_progress and len(show_list) > 0:
                prog = QProgressDialog("正在加载变更明细...", None, 0, len(show_list), self)
                prog.setWindowTitle("加载变动提醒")
                prog.setWindowModality(Qt.WindowModal)
                prog.setMinimumDuration(300)
                prog.setValue(0)
            for i, c in enumerate(show_list):
                did = str(c.get('data_id', ''))
                parts = did.split('|')
                date = parts[0] if len(parts) > 0 else ''
                order = parts[1] if len(parts) > 1 else ''
                mat = parts[2] if len(parts) > 2 else ''
                wk = c.get('workshop', '') or ''
                old_v = c.get('old_value', '')
                new_v = c.get('new_value', '')
                it0 = QTableWidgetItem(date)
                it0.setData(Qt.UserRole, i)  # 存 remaining 索引
                table.setItem(i, 0, it0)
                table.setItem(i, 1, QTableWidgetItem(str(wk)))
                table.setItem(i, 2, QTableWidgetItem(order))
                table.setItem(i, 3, QTableWidgetItem(mat))
                table.setItem(i, 4, QTableWidgetItem(str(c.get('material_name', '') or '')))
                table.setItem(i, 5, QTableWidgetItem(str(c.get('field', ''))))
                table.setItem(i, 6, QTableWidgetItem('' if old_v is None else str(old_v)))
                table.setItem(i, 7, QTableWidgetItem('' if new_v is None else str(new_v)))
                if prog and (i + 1) % 200 == 0:
                    prog.setValue(i + 1)
                    QApplication.processEvents()
            if prog:
                prog.setValue(len(show_list))
            # 列宽：手动设定固定/拉伸，避免 ResizeToContents 在大量行时逐行测量导致卡顿
            header = table.horizontalHeader()
            fixed_widths = {0: 100, 1: 90, 2: 100, 3: 110, 4: 200, 5: 90}
            for col, w in fixed_widths.items():
                header.setSectionResizeMode(col, QHeaderView.Fixed)
                table.setColumnWidth(col, w)
            name_col = 4
            name_max_w = 200
            header.setSectionResizeMode(6, QHeaderView.Stretch)  # 旧值
            header.setSectionResizeMode(7, QHeaderView.Stretch)  # 新值
            # 仅在小数据量时做逐行字号缩放（大数据量跳过，避免逐行 QFontMetrics 卡顿）
            n = len(show_list)
            if n <= 2000:
                base_font = table.font()
                fm = QFontMetrics(base_font)
                pad = 12
                avail = name_max_w - pad
                max_text_w = 0
                for r in range(n):
                    it = table.item(r, name_col)
                    if it:
                        max_text_w = max(max_text_w, fm.horizontalAdvance(it.text()))
                if max_text_w > avail:
                    ps = base_font.pointSizeF() or 9.0
                    new_size = max(7.0, ps * avail / max_text_w)
                    shrink_font = QFont(base_font)
                    shrink_font.setPointSizeF(new_size)
                    for r in range(n):
                        it = table.item(r, name_col)
                        if it:
                            it.setFont(shrink_font)
            table.setSortingEnabled(True)

        _populate(remaining[:MAX_DISPLAY], with_progress=True)

        # 右键：复制单元格 / 复制整行
        _ctx_index = [None]  # 记录右键所在的单元格，避免整行选中导致取错列

        def _copy_cell():
            idx = _ctx_index[0]
            if idx is None or not idx.isValid():
                idxs = table.selectedIndexes()
                idx = idxs[0] if idxs else None
            if idx is not None and idx.isValid():
                QApplication.clipboard().setText(str(idx.data() or ''))
                toast("已复制单元格", parent=dlg)

        def _copy_row():
            r = table.currentRow()
            if r < 0:
                return
            vals = []
            for cc in range(table.columnCount()):
                it = table.item(r, cc)
                vals.append(it.text() if it else '')
            QApplication.clipboard().setText('\t'.join(vals))
            toast("已复制整行", parent=dlg)

        def _on_context(pos):
            _ctx_index[0] = table.indexAt(pos)
            menu = QMenu()
            a_cell = menu.addAction("复制单元格")
            a_row = menu.addAction("复制整行")
            menu.addSeparator()
            a_mark_read = menu.addAction("标记为已读（选中行）")
            act = menu.exec_(table.viewport().mapToGlobal(pos))
            if act == a_cell:
                _copy_cell()
            elif act == a_row:
                _copy_row()
            elif act == a_mark_read:
                _mark_selected_read()

        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(_on_context)

        # 过滤（字段筛选 + 关键字搜索）
        def _apply_filter():
            kw = search_edit.text().strip().lower()
            fsel = field_combo.currentText()
            for r in range(table.rowCount()):
                show = True
                if fsel != "全部字段" and table.item(r, 5).text() != fsel:
                    show = False
                if show and kw:
                    hay = ' '.join(table.item(r, cc).text().lower() for cc in (0, 1, 2, 3, 4))
                    if kw not in hay:
                        show = False
                table.setRowHidden(r, not show)

        search_edit.textChanged.connect(_apply_filter)
        field_combo.currentTextChanged.connect(_apply_filter)

        # 双击定位到主表对应行（按当前行单元格重建 data_id，排序后仍正确）
        def _on_double(idx):
            r = idx.row()
            if r < 0:
                return
            d = table.item(r, 0).text()
            o = table.item(r, 2).text()
            m = table.item(r, 3).text()
            did = '|'.join([d, o, m])
            if self._locate_row_in_main_table(did):
                dlg.accept()

        table.doubleClicked.connect(_on_double)

        btn_box = QDialogButtonBox(dlg)
        export_btn = QPushButton("导出Excel并打开")
        mark_sel_btn = QPushButton("选中标记为已读")
        mark_read_btn = QPushButton("全部标记为已读（不再提醒）")
        ok_btn = QPushButton("确定")
        btn_box.addButton(export_btn, QDialogButtonBox.ActionRole)
        btn_box.addButton(mark_sel_btn, QDialogButtonBox.ActionRole)
        btn_box.addButton(mark_read_btn, QDialogButtonBox.ActionRole)
        btn_box.addButton(ok_btn, QDialogButtonBox.AcceptRole)
        layout.addWidget(btn_box)

        def _export():
            try:
                tmp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "zpp011_audit_changes")
                os.makedirs(tmp_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(tmp_dir, f"audit_changes_{ts}.xlsx")
                rows = []
                for c in changes:
                    did = str(c.get('data_id', ''))
                    parts = did.split('|')
                    rows.append({
                        '日期': parts[0] if len(parts) > 0 else '',
                        '车间': c.get('workshop', '') or '',
                        '流程订单': parts[1] if len(parts) > 1 else '',
                        '物料编码': parts[2] if len(parts) > 2 else '',
                        '物料名称': c.get('material_name', '') or '',
                        '变更字段': c.get('field', ''),
                        '旧值': '' if c.get('old_value') is None else c.get('old_value'),
                        '新值': '' if c.get('new_value') is None else c.get('new_value'),
                    })
                pd.DataFrame(rows).to_excel(path, index=False)
                if os.name == "nt" and os.path.exists(path):
                    os.startfile(path)
                else:
                    opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                    subprocess.Popen([opener, path])
                toast(f"已导出并打开：{path}", parent=dlg)
            except Exception as e:
                QMessageBox.warning(dlg, "导出失败", f"导出失败：{e}")

        def _get_df_for_mark():
            """构造用于标记已读的主表快照 df（优先 source_model，其次 view_model.df，最后最小 data_id df）。"""
            df = None
            if self.source_model:
                df = self.source_model.getDataFrame()
            if df is None or (hasattr(df, 'empty') and df.empty):
                df = getattr(self.view_model, 'df', None)
                if df is not None and not (hasattr(df, 'empty') and df.empty):
                    self.log("source_model 为空，使用 view_model.df 作为已读快照", "warning")
            if df is None or (hasattr(df, 'empty') and df.empty):
                data_ids = list(dict.fromkeys([str(c.get('data_id', '')) for c in remaining if c.get('data_id')]))
                if not data_ids:
                    return None
                df = pd.DataFrame({'data_id': data_ids})
                self.log("主表数据为空，以最小 data_id 列标记变动已读（不保存当前值快照）", "warning")
            return df

        def _sync_main_read_status(dids):
            """把一组 data_id 对应的主表行 _read 设为 1 并触发界面刷新。"""
            if not dids or not self.source_model:
                return
            df = self.source_model.getDataFrame()
            if df is None or (hasattr(df, 'empty') and df.empty):
                return
            if 'data_id' not in df.columns or '_read' not in df.columns:
                return
            mask = df['data_id'].astype(str).isin(dids)
            if mask.any():
                df.loc[mask, '_read'] = 1
                df.loc[mask, '_read_source'] = 'manual'
                self.source_model.setDataFrame(df)

        def _mark_selected_read():
            """把当前选中的行（点击高亮即选中，Ctrl/Shift 可多选）标记为已读，并从列表移除。"""
            sel = table.selectedIndexes()
            if not sel:
                QMessageBox.information(dlg, "提示", "请先选中要标记的行（点击行即高亮选中，Ctrl/Shift 可多选）。")
                return
            rows = sorted({idx.row() for idx in sel})
            idxs = []
            for r in rows:
                ud = table.item(r, 0).data(Qt.UserRole)
                if isinstance(ud, int) and 0 <= ud < len(remaining):
                    idxs.append(ud)
            if not idxs:
                return
            idxs = sorted(set(idxs))
            sub_changes = [remaining[i] for i in idxs]
            df = _get_df_for_mark()
            if df is None:
                QMessageBox.warning(dlg, "提示", "主表数据为空且无有效 data_id，无法标记已读。")
                return
            n, marked_dids = self.data_service.mark_changes_as_read(sub_changes, df)
            if n > 0:
                _sync_main_read_status(marked_dids)
                self._on_manual_marked(n)  # 变动提醒弹窗手动标已读 → 累加到状态栏计数
                # 从 remaining 移除已标记行（按 data_id+变更字段 去重，避免误删未选中的同名行）
                marked_keys = {(str(c.get('data_id', '')), str(c.get('field', ''))) for c in sub_changes}
                new_remaining = [c for c in remaining if (str(c.get('data_id', '')), str(c.get('field', ''))) not in marked_keys]
                remaining[:] = new_remaining
                dlg.setWindowTitle(f"变动提醒（{len(remaining)} 条）")
                _populate(remaining[:MAX_DISPLAY])
                _apply_filter()
                toast(f"已把 {n} 条标记为已读（剩余 {len(remaining)} 条）", parent=dlg)
                if not remaining:
                    toast("已全部标记为已读", parent=dlg)
                    dlg.accept()
            else:
                QMessageBox.warning(dlg, "标记失败", "未能标记所选行为已读，请检查数据。")

        def _mark_all_read():
            try:
                df = _get_df_for_mark()
                if df is None:
                    QMessageBox.warning(dlg, "提示", "主表数据为空且无有效 data_id，无法标记已读。")
                    return
                marked_dids = {str(c.get('data_id', '')) for c in remaining if c.get('data_id')}
                n, _ = self.data_service.mark_changes_as_read(remaining, df)
                if n > 0:
                    _sync_main_read_status(marked_dids)
                    self._on_manual_marked(n)  # 「全部标记为已读」→ 累加到状态栏计数
                    toast(f"已把 {n} 条记录标记为已读，下次不再提醒", parent=dlg)
                remaining[:] = []
                dlg.setWindowTitle("变动提醒（0 条）")
                _populate([])
                dlg.accept()
            except Exception as e:
                QMessageBox.warning(dlg, "标记失败", f"标记已读失败：{e}")

        export_btn.clicked.connect(_export)
        mark_sel_btn.clicked.connect(_mark_selected_read)
        mark_read_btn.clicked.connect(_mark_all_read)
        ok_btn.clicked.connect(dlg.accept)
        dlg.exec()
        self._audit_changes_dialog_open = False

    def _locate_row_in_main_table(self, data_id):
        """变动提醒弹窗双击某行时，定位并选中主表对应行（经 proxy_model 映射）"""
        try:
            if self.source_model is None:
                return False
            df = self.source_model.getDataFrame()
            if df is None or 'data_id' not in df.columns:
                return False
            matches = df.index[df['data_id'].astype(str) == str(data_id)].tolist()
            if not matches:
                toast("主表中未找到该记录", parent=self)
                return False
            src_row = matches[0]
            src_idx = self.source_model.index(src_row, 0)
            proxy = self.table_view.model()
            proxy_idx = proxy.mapFromSource(src_idx) if hasattr(proxy, 'mapFromSource') else src_idx
            self.table_view.selectRow(proxy_idx.row())
            self.table_view.scrollTo(proxy_idx)
            self.table_view.setFocus()
            self.activateWindow()
            self.raise_()
            return True
        except Exception as e:
            self.log(f"定位主表失败: {e}", "error")
            return False

    def _start_analysis(self):
        if not self.current_input_file:
            QMessageBox.warning(self, "提示", "请先选择输入文件")
            return
        if self._heavy_busy:
            QMessageBox.information(self, "提示", "分析/报告生成进行中，请稍候")
            return
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            QMessageBox.information(self, "提示", "分析任务已在后台运行")
            return
        # 统一路径格式（正/反斜杠），避免与监控指纹对不上导致重复触发
        self.current_input_file = os.path.normpath(self.current_input_file)

        dev_threshold = getattr(self.filter_panel, 'dev_threshold_spin', None)
        dev_threshold_val = dev_threshold.value() if dev_threshold is not None else 0.0

        # 动态阈值（公司规定）：默认 10.0%，可被 filter_panel.dyn_thresh_spin 改
        dyn_threshold = getattr(self.filter_panel, 'dyn_thresh_spin', None)
        dyn_thresh_val = dyn_threshold.value() if dyn_threshold is not None else 10.0

        # 读取"分析参数"组里的分析日期范围（留空=全部）。修复：此前写死为空导致日期控制失效。
        def _qdate_or_empty(edit):
            try:
                if edit.date() == edit.minimumDate():
                    return ""
            except Exception:
                return ""
            return edit.date().toString("yyyy-MM-dd")

        fp = self.filter_panel
        if hasattr(fp, 'analysis_start_date_edit'):
            start_date = _qdate_or_empty(fp.analysis_start_date_edit)
            end_date = _qdate_or_empty(fp.analysis_end_date_edit)
        else:
            start_date, end_date = "", ""

        self.analysis_controller.start_analysis(
            self.current_input_file,
            self.alt_controller.get_pairs(),
            start_date,
            end_date,
            "",
            dev_threshold_val,
            self.data_service,
            self.analysis_controller.get_last_processed_df(),
            getattr(self, '_cached_input_df', None),  # 复用选文件时缓存的 DataFrame，跳过重复文件 IO
            dyn_thresh=dyn_thresh_val,
        )

    def _on_analysis_ui_start(self):
        self._heavy_busy = True
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.start_btn.setEnabled(False)
        self._countdown_seconds = 0
        self._analysis_start_ts = time.perf_counter()
        self._current_step = "准备中"
        self.main_table.reset_step_icons()
        self.main_table.set_progress_visible(True)  # 分析开始自动展开进度面板
        self.timer_lbl.setText("⏱ 00:00")
        # 状态栏「分析时间」先显示进行中 + 触发方式（自动=监控触发 / 手动=点按钮）
        try:
            _mode = "自动" if getattr(self, "_monitor_auto_loading", False) else "手动"
            self._analysis_time_label.setText(f"🕒 分析中…（{_mode}）")
        except RuntimeError:
            pass

        if self._countdown_timer is None:
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

    def _on_analysis_progress_ui(self, percent, step_name):
        self.progress_bar.setValue(percent)
        self._current_step = step_name
        self.main_table.update_step_icons(percent, step_name)
        elapsed = int(time.perf_counter() - getattr(self, "_analysis_start_ts", 0))
        m, s = divmod(elapsed, 60)
        self.timer_lbl.setText(f"⏱ {m:02d}:{s:02d}")
        self.progress_label.setText(f"{step_name}  {percent}%")

    def _on_analysis_finished_ui(self, df):
        import tempfile  # 下方生成完整报告缓存目录时使用
        # 抢在 _monitor_auto_loading 被重置前判定触发方式（自动=监控触发 / 手动=点按钮）
        _analysis_mode = "自动" if getattr(self, "_monitor_auto_loading", False) else "手动"
        self._monitor_auto_loading = False
        self._monitor_current_key = None
        self._stop_countdown()
        # 状态栏「分析时间」：标触发方式 + 完成时刻（Finish 时刻）
        self._update_analysis_time_label(_analysis_mode)
        self.progress_bar.setValue(100)
        self.main_table.complete_step_icons()
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        elapsed = self._format_elapsed()
        self.progress_label.setText(f"✅ 完成 ({elapsed})")
        toast(f"✅ 分析完成，共 {len(df)} 条记录 ({elapsed})", "success", parent=self)
        self.statusBar().showMessage("分析完成，正在加载结果...")
        QApplication.processEvents()

        # 修复「分析完成主表空白」：上一轮残留的筛选条件（proxy._filters/_custom_filters）
        # 会把新分析的整表过滤成 0 行（右下角显示 0/0）。每次分析完成时统一清空：
        # 1) proxy 两个筛选字典；2) 侧边栏面板 UI 同步复位（blockSignals 防止重复触发）。
        try:
            if self.proxy_model is not None:
                self.proxy_model.clearFilters()
            if hasattr(self, 'filter_panel') and self.filter_panel is not None:
                self.filter_panel.blockSignals(True)
                try:
                    self.filter_panel.reset_filters()
                finally:
                    self.filter_panel.blockSignals(False)
        except Exception as _e:
            print(f"[WARN] 分析完成后清筛选失败(不影响主流程): {_e}", flush=True)
        self._on_factory_changed('全部')
        QApplication.processEvents()

        try:
            processed_df = self.view_model.df
            if processed_df is None or processed_df.empty:
                # 首次分析：后台未预处理过（带 _read 列）则复用，否则主线程预处理
                if '_read' in df.columns:
                    processed_df = df
                else:
                    processed_df = self.data_service.preprocess_audit_data(df)
            else:
                # 重新分析：用本次新分析的 df 刷新主表，避免显示陈旧数据
                processed_df = df if '_read' in df.columns else self.data_service.preprocess_audit_data(df)
            # 新增：分析完成后按「自动已读规则中心」配置自动标已读，并逐规则报告命中数
            self._auto_read_by_rules(processed_df)
            self.source_model.setDataFrame(processed_df)
            QApplication.processEvents()
            self._schedule_unread_summary()
            self.view_model.df = processed_df
            self._analysis_params = self.analysis_controller.get_analysis_params()

            # 注意：完整报告缓存由后台线程(_FullCacheWorker)生成，主线程绝不等待，
            # 否则分析完成后标题栏会显示「未响应」。导出完整报告时优先复制该缓存。

            cache_dir = os.path.join(tempfile.gettempdir(), "zpp011_analysis")
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"full_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            self._full_analysis_cache_path = cache_path

            # 后台生成完整报告缓存：独立线程，主线程不等待（避免"未响应"）。
            # 用全局 _heavy_busy 标志防止与其他重型操作（再次分析/导出）并发抢占 GIL。
            params = self.analysis_controller.get_analysis_params()
            if self._cache_worker is not None and self._cache_worker.isRunning():
                # 已有缓存在生成，复用其路径即可，不叠加第二个 do_analysis_v2
                pass
            else:
                from PySide6.QtCore import QThread
                class _FullCacheWorker(QThread):
                    def __init__(self, input_file, alt_pairs, start_date, end_date, material_search, output_path, dyn_thresh=None):
                        super().__init__()
                        self.input_file = os.path.normpath(input_file)
                        self.alt_pairs = alt_pairs
                        self.start_date = start_date
                        self.end_date = end_date
                        self.material_search = material_search
                        self.output_path = output_path
                        self.dyn_thresh = dyn_thresh

                    def run(self):
                        import analysis.analyzer as _az
                        from analysis.analyzer import export_full_report_from_intermediates
                        from core.config_manager import ConfigManager
                        _cfg = ConfigManager()
                        try:
                            _li = _az.LATEST_INTERMEDIATES
                            if _li is not None:
                                # 复用 worker 已算好的 Sheet1~5 中间结果，只生成 Sheet6~10 + 保存，避免重算
                                export_full_report_from_intermediates(
                                    _li, output_path=self.output_path,
                                    progress_callback=None, cancel_check=None)
                            else:
                                # 兜底：中间结果缺失时退回完整分析（理论上不会发生，worker 必先生效）
                                _az.do_analysis_v2(
                                    input_file=self.input_file, output_dir=None,
                                    alt_pairs=self.alt_pairs, start_date=self.start_date,
                                    end_date=self.end_date, material_search=self.material_search,
                                    output_path=self.output_path,
                                    enable_net_offset=_cfg.get_net_offset_enabled(),
                                    return_dataframe=False,
                                    dyn_thresh=getattr(self, 'dyn_thresh', None),
                                )
                        except Exception:
                            import traceback as _tb
                            _tb.print_exc()

                self._cache_worker = _FullCacheWorker(
                    params['input_file'], params['alt_pairs'],
                    params.get('start_date', ''), params.get('end_date', ''),
                    params.get('material_search', ''), cache_path,
                    dyn_thresh=params.get('dyn_thresh'),
                )
                _cw = self._cache_worker
                self._heavy_busy = True  # 缓存生成期间仍视为"重型操作进行中"
                def _on_cache_done():
                    # 仅在 finished 信号槽里清引用与标志，绝不调用 wait() 阻塞主线程
                    self._heavy_busy = False
                    if self._cache_worker is _cw:
                        self._cache_worker = None
                self._cache_worker.finished.connect(_on_cache_done)
                self._cache_worker.start()

            self._set_column_widths()
            QApplication.processEvents()
            self.statusBar().showMessage(f"分析完成，共加载 {len(processed_df)} 行 × {len(processed_df.columns)} 列")
            # 更新左侧"数据预览"卡片（文字统计，使用与表格一致的预处理后 df）
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.setText(self._format_preview_stats(processed_df))
            if hasattr(self, 'left_panel') and hasattr(self.left_panel, 'preview_group'):
                self.left_panel.preview_group.expand()
            self.main_table.summary_container.setVisible(True)
            self._update_summary()
            QApplication.processEvents()
            self.main_table.summary_container.raise_()
            self.main_table.summary_container.repaint()
            QApplication.processEvents()
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self._heavy_busy = False
            QMessageBox.critical(self, "错误", f"加载结果失败: {e}")

        if not self.alert_monitor.isRunning():
            self.alert_monitor.start()

        # 分析完成后自动把「疑难包材箱」记录移入隔离区（静默：仅当有新增时 toast）
        self._auto_move_to_quarantine(manual=False)

        # 分析完成后静默扫描「隔离区失效」：仅当有新增失效记录时弹窗/亮角标
        self._scan_expired_quarantine_after_analysis()

    # ------------------------------------------------------------------ #
    # 顶部面板（概览 / 进度）显隐控制
    # ------------------------------------------------------------------ #
    def _toggle_stats_from_toolbar(self):
        """工具栏「📊 概览」按钮：切换本次分析概览面板显隐"""
        if self.stats_cards._user_hidden:
            self.stats_cards.show_panel()
        else:
            self.stats_cards._toggle_cards(False)

    def _toggle_progress_from_toolbar(self):
        """工具栏「⚡ 进度」按钮：切换分析进度面板显隐"""
        self.main_table.set_progress_visible(self.main_table._progress_hidden)

    def _on_stats_visibility_changed(self, visible: bool):
        """概览面板显隐变化时同步工具栏按钮文字和顶部容器可见性"""
        self.action_btn_toggle_stats.setText("📊 概览" if visible else "📊 显示概览")
        self.action_btn_toggle_stats.setToolTip("隐藏本次分析概览" if visible else "显示本次分析概览")
        self._update_top_panel_visibility()

    def _on_progress_visibility_changed(self, visible: bool):
        """进度面板显隐变化时同步工具栏按钮文字和顶部容器可见性"""
        self.action_btn_toggle_progress.setText("⚡ 进度" if visible else "⚡ 显示进度")
        self.action_btn_toggle_progress.setToolTip("隐藏分析进度" if visible else "显示分析进度")
        self._update_top_panel_visibility()

    def _update_top_panel_visibility(self):
        """两个面板都隐藏时，把顶部容器也隐藏，释放空间给表格。
        注意：必须用各自的「用户期望可见」状态变量判断，不能用 isVisible()——
        因为 isVisible() 受父级 top_panel 可见性影响：一旦 top_panel 被隐藏，
        子 widget 的 isVisible() 也会返回 False，会导致「显示」时 top_panel 永远
        无法重新出现（死循环）。"""
        stats_visible = not self.stats_cards._user_hidden
        progress_visible = not self.main_table._progress_hidden
        self.top_panel.setVisible(stats_visible or progress_visible)

    def _auto_read_by_rules(self, df):
        """分析完成后：按「自动已读规则中心」配置，把命中任意启用规则的未读行自动标为已读，
        并逐条规则报告命中数（清晰 toast + 状态栏，解决「自动已读没告诉我」的盲区）。

        判定：多条规则 OR 并存；命中行若已读过则跳过（不重复打扰，数据变动会自动翻回未读）。
        落库：复用与手动标已读同一套 snapshot + mark_read_batch。
        """
        try:
            if df is None or df.empty or '_read' not in df.columns or 'data_id' not in df.columns:
                return
            from core.auto_read_rules import load_auto_read_rules_config, compute_auto_read_mask
            cfg = load_auto_read_rules_config()
            if not cfg.get('enabled', True):
                toast("ℹ️ 自动已读已关闭（规则中心总开关）", "info", parent=self, duration=6000)
                return
            union_mask, per_rule = compute_auto_read_mask(df, cfg)
            unread = (df['_read'] == 0)
            target = union_mask & unread
            n_auto = int(target.sum())
            n_would = int(union_mask.sum())
            if n_auto == 0:
                if n_would == 0:
                    toast("ℹ️ 本次无符合自动已读规则的行", "info", parent=self, duration=6000)
                else:
                    toast(f"ℹ️ 符合自动已读规则共 {n_would} 条，均已读过，无需自动已读", "info", parent=self, duration=6000)
                return

            # —— 建立变更检测基线（向量化 dict(zip)，避免逐行 df.loc 的 O(n²)）——
            from core.read_status import mark_read_batch
            qty_col = self.data_service._find_real_qty_col(df)
            note_col = self.data_service._find_remark_col(df)
            yield_col = self.data_service._find_yield_col(df)
            qty_lookup = {str(k): v for k, v in zip(df['data_id'], df[qty_col])} if qty_col else {}
            note_lookup = {str(k): str(v) for k, v in zip(df['data_id'], df[note_col].astype(str))} if note_col else {}
            yield_lookup = {str(k): v for k, v in zip(df['data_id'], df[yield_col])} if yield_col else {}

            dids = [str(x) for x in df.loc[target, 'data_id'].tolist()]
            snapshot_map = {}
            for did in dids:
                q = qty_lookup.get(did)
                n = note_lookup.get(did, '')
                y = yield_lookup.get(did)
                snapshot_map[did] = (
                    self.data_service._safe_qty(q) if qty_col else None,
                    self.data_service._norm_note(n) if note_col else '',
                    self.data_service._safe_qty(y) if yield_col else None,
                )
            if dids:
                mark_read_batch(dids, snapshot_map, read_source='auto')
                df.loc[target, '_read'] = 1
                df.loc[target, '_read_source'] = 'auto'
                self._auto_read_count += n_auto
                self._update_read_counter()

            # —— 逐规则命中数（仅在未读范围内统计，供反馈）——
            parts = []
            for rule, m in per_rule:
                cnt = int((m & unread).sum())
                if cnt > 0:
                    parts.append("「%s」%d" % (rule.get('name', '未命名'), cnt))

            toast(
                f"✅ 自动已读 {n_auto} 条｜" + "｜".join(parts),
                "success", parent=self, duration=6000,
            )
            self.statusBar().showMessage(
                f"自动已读 {n_auto} 条（" + "；".join(parts)
                + f"）｜符合规则共 {n_would} 条",
                6000,
            )
        except Exception as e:
            print(f"[WARN] 自动已读失败(不影响主流程): {e}", flush=True)

    def _update_read_counter(self):
        """刷新状态栏常驻的「已读计数」标签（自动 N / 手动 M）。"""
        try:
            self._read_counter_label.setText(
                f"📖 已读：自动 {self._auto_read_count} / 手动 {self._manual_read_count}"
            )
        except RuntimeError:
            # 标签已被 deleteLater 回收（关窗时序），忽略
            pass

    def _update_analysis_time_label(self, mode):
        """刷新状态栏常驻的「分析时间」标签。mode 为 '自动' 或 '手动'。"""
        try:
            ts = time.strftime("%m-%d %H:%M:%S")
            self._analysis_time_label.setText(f"🕒 分析：{mode} {ts}")
        except RuntimeError:
            # 标签已被 deleteLater 回收（关窗时序），忽略
            pass

    def _on_manual_marked(self, n):
        """手动标记已读后累计计数并刷新标签（来自 audit_controller / 两个弹窗的回调）。"""
        if n:
            self._manual_read_count += int(n)
            self._update_read_counter()

    def _on_analysis_error_ui(self, error_msg):
        self._heavy_busy = False
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        # 状态栏「分析时间」：标失败 + 触发方式 + 时刻
        try:
            _analysis_mode = "自动" if getattr(self, "_monitor_auto_loading", False) else "手动"
            self._analysis_time_label.setText(
                f"🕒 分析失败（{_analysis_mode}）{time.strftime('%m-%d %H:%M:%S')}"
            )
        except RuntimeError:
            pass
        # 若是监控文件夹自动加载失败，不弹模态错误框，避免"未响应"；改为 toast + 日志，并允许重试
        if getattr(self, "_monitor_auto_loading", False):
            self._monitor_auto_loading = False
            self.start_btn.setEnabled(True)
            self.progress_label.setText("❌ 监控加载失败")
            self.main_table.reset_step_icons()
            # 从已加载指纹中移除，让监控下次扫描继续尝试
            if self._monitor_current_key:
                self._monitor_loaded.discard(self._monitor_current_key)
                self._monitor_pending.discard(self._monitor_current_key)
                self._monitor_current_key = None
            _fn = os.path.basename(self.current_input_file or "新文件")
            if "被占用" in error_msg or "锁文件" in error_msg:
                toast(f"⚠️ 文件仍被占用，监控将自动重试：{_fn}", "warning", parent=self)
                self.log(f"监控自动加载失败（将重试）：{error_msg}", "warning")
            else:
                toast(f"⚠️ 监控自动加载失败：{error_msg}", "warning", parent=self)
                self.log(f"监控自动加载失败：{error_msg}", "error")
            return
        self.progress_label.setText("❌ 错误（可重试）")
        self.start_btn.setEnabled(True)
        self.main_table.reset_step_icons()
        QMessageBox.critical(self, "错误", error_msg)

    def _on_ai_ui_start(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self._countdown_seconds = 0
        self._analysis_start_ts = time.perf_counter()
        self._current_step = "AI审核"
        self.timer_lbl.setText("⏱ 00:00")
        if not hasattr(self, "_countdown_timer"):
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

    def _on_ai_progress_ui(self, current, total):
        percent = int(current / total * 100) if total else 0
        self.progress_bar.setValue(percent)
        elapsed = int(time.perf_counter() - getattr(self, "_analysis_start_ts", 0))
        m, s = divmod(elapsed, 60)
        self.timer_lbl.setText(f"⏱ {m:02d}:{s:02d}")
        self.progress_label.setText(f"AI审核: {current}/{total}")

    def _on_ai_finished_ui(self, updated_df):
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        elapsed = self._format_elapsed()
        self.progress_label.setText(f"✅ AI审核完成 ({elapsed})")
        toast(f"✅ AI审核完成 ({elapsed})", "success", parent=self)

        if "AI建议" in updated_df.columns:
            non_empty = updated_df["AI建议"].replace("", pd.NA).notna().sum()
            total = len(updated_df)
            self.log(f"AI审核完成：共 {total} 条记录，{non_empty} 条有AI建议", "info")
            if non_empty == 0:
                self.log("警告：AI建议列为空", "warning")
        else:
            self.log("警告：AI建议列不存在", "warning")
        # 弹窗条件（原始逻辑：AI建议列缺失 或 有非空建议时才弹）
        self._ai_box_condition = ("AI建议" not in updated_df.columns or
                                   updated_df["AI建议"].replace("", pd.NA).notna().sum() > 0)

        # 预处理（恢复已读状态+审核结果）直接同步执行，DB 操作 ~0.2s 不卡
        try:
            updated_df = self.data_service.preprocess_audit_data(updated_df, self.view_model.df)
        except Exception:
            pass  # 降级，用原始 updated_df

        self.source_model.setDataFrame(updated_df)
        self._apply_column_visibility_by_name()
        self.view_model.df = updated_df
        self.progress_bar.setVisible(False)
        self.progress_label.setText("就绪")
        if getattr(self, "_ai_box_condition", True):
            QMessageBox.information(self, "完成", "AI审核已完成")

    def _on_ai_preprocess_error(self, error_msg, updated_df):
        self.log(f"AI审核后预处理失败，降级用原始结果: {error_msg}", "error")
        self.source_model.setDataFrame(updated_df)
        self._apply_column_visibility_by_name()
        self.view_model.df = updated_df
        self.progress_bar.setVisible(False)
        self.progress_label.setText("就绪")
        if getattr(self, "_ai_box_condition", True):
            QMessageBox.information(self, "完成", "AI审核已完成")
        if self._ai_preprocess_worker is not None:
            self._ai_preprocess_worker.deleteLater()
            self._ai_preprocess_worker = None

    def _on_ai_error_ui(self, error_msg):
        self.progress_bar.setVisible(False)
        self.progress_label.setText("错误")
        QMessageBox.critical(self, "错误", error_msg)

    def _on_new_alerts(self, alerts_df):
        # 自动弹窗已关闭（self._auto_pop_alerts=False），避免阻塞主线程导致「未响应」。
        # 手动打开「替代料看板」仍可见同样的预警明细。
        if not getattr(self, "_auto_pop_alerts", False):
            return
        count = len(alerts_df)
        # 先刷新一次事件队列，避免主线程因前面积压的 UI 更新被 Windows 标记为未响应
        QApplication.processEvents()
        box = QMessageBox(self)
        box.setWindowTitle("⚠️ 预警通知")
        box.setIcon(QMessageBox.Question)
        box.setText(f"发现 {count} 条新替代料预警（含差异/超阈值），是否查看明细？")
        yes_btn = box.addButton("是", QMessageBox.YesRole)
        no_btn = box.addButton("否", QMessageBox.NoRole)
        box.setDefaultButton(yes_btn)
        box.exec()
        if box.clickedButton() != yes_btn:
            return
        try:
            # 直接用 AlertMonitor 传过来的 alerts_df，已经过滤过替代料了
            all_alerts = alerts_df.copy()
            if all_alerts is None or all_alerts.empty:
                QMessageBox.information(self, "提示", "没有替代料预警记录")
                return
            # 只保留关键列，避免显示乱七八糟
            required_cols = [c for c in [
                "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
                "备注", "备注来源",
                "车间", "定额", "实际", "偏差数量", "偏差率(%)",
                "净偏差数量", "净偏差金额", "净偏差率(%)",
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
            df = self._get_master_df()  # 与未读弹窗同源，避免两边数对不上
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
            # 只保留关键列（含"工厂"以便 dialog 生成正确的 data_id 与主表匹配）
            required_cols = [c for c in [
                "工厂", "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
                "备注", "备注来源",
                "车间", "定额", "实际", "偏差数量", "偏差率(%)",
                "净偏差数量", "净偏差金额", "净偏差率(%)",
                "是否替代料", "_post_audit_changed", "_quarantined",
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

    def _show_deviation_warning_dialog(self):
        """手动打开偏差率预警看板（|偏差率| >= 10%）"""
        try:
            df = self._get_master_df()  # 与未读弹窗同源，避免两边数对不上
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            if "偏差率(%)" not in df.columns:
                QMessageBox.information(self, "提示", "当前数据无偏差率列")
                return
            # 偏差率预警：|偏差率| >= 10%，且排除「实际=0 且 定额>0」的行
            # （偏差率恒为 -100%，是未真实投料的机械结果，不是真偏差；与主表橙色高亮、颜色筛选一致）
            rates = pd.to_numeric(df["偏差率(%)"], errors='coerce').fillna(0)
            act_col = '数量-实际' if '数量-实际' in df.columns else ('实际' if '实际' in df.columns else None)
            qty_col = '数量-定额' if '数量-定额' in df.columns else ('定额' if '定额' in df.columns else None)
            if act_col and qty_col:
                a = pd.to_numeric(df[act_col], errors='coerce').fillna(0)
                q = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
                no_input = (a.abs() <= 0.001) & (q > 0.001)
                mask = (rates.abs() >= 10) & (~no_input)
            else:
                mask = rates.abs() >= 10
            warnings_df = df[mask].copy()
            if warnings_df.empty:
                QMessageBox.information(self, "提示", "没有偏差率预警记录（|偏差率| ≥ 10%）")
                return
            # 只保留关键列（兼容两种命名：数量-实际/实际、组件物料号/物料编码 等，含"工厂"保证 data_id 匹配）
            candidates = [
                "工厂", "订单日期", "流程订单", "组件物料号", "物料编码", "物料名称", "物料描述", "车间",
                "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "净偏差率(%)", "是否替代料",
                "备注", "备注原因", "备注来源", "预警", "_read",
            ]
            required_cols = [c for c in candidates if c in warnings_df.columns]
            warnings_df = warnings_df[required_cols]
            if "_read" in warnings_df.columns:
                warnings_df["状态"] = warnings_df["_read"].map({0: "未读", 1: "已读"})
                warnings_df = warnings_df[["状态"] + [c for c in warnings_df.columns if c != "状态"]]
            dialog = DeviationWarningDialog(warnings_df, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开偏差率预警看板失败: {e}")

    def _show_neg_loss_dashboard(self):
        """手动打开负损(含未投料)看板：名称含关键词 且 负损(含未投料)，独立于隔离区。"""
        try:
            df = self._get_master_df()  # 与主表同源，避免两边数对不上
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            # 保留关键列（含数量-实际/数量-定额 供负损计算，备注列供优先展示）
            candidates = [
                "订单日期", "流程订单", "组件物料号", "物料编码", "物料名称", "物料描述",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
                "备注", "备注原因", "备注来源", "_read",
            ]
            keep = [c for c in candidates if c in df.columns]
            sub = df[keep].copy() if keep else df.copy()
            dialog = NegLossDashboardDialog(sub, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开负损看板失败: {e}")

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
            self.progress_bar.setVisible(False)
            self.progress_label.setText("已取消")
            self.start_btn.setEnabled(True)
            self._heavy_busy = False
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

    # -----------------------------------------------------------
    # 文件与目录
    # -----------------------------------------------------------
    def _select_input_file(self):
        default_dir = r"E:\ZPP011导出文件原数据"
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 SAP Excel 文件", default_dir, "Excel files (*.xlsx *.xls)")
        if not file_path:
            return
        self.current_input_file = os.path.normpath(file_path)
        self.input_file_edit.setText(self.current_input_file)
        self.input_file_edit.setToolTip(file_path)
        # 后台读取，避免大文件阻塞主线程导致"未响应"
        if hasattr(self, 'preview_label') and self.preview_label:
            self.preview_label.setText("📂 正在读取文件…")
        self._file_worker = _FileReadWorker(file_path)
        self._file_worker.loaded.connect(self._on_file_loaded)
        self._file_worker.failed.connect(self._on_file_failed)
        self._file_worker.start()

    def _on_file_loaded(self, df, file_path):
        try:
            # 新一批数据：清零已读计数（每批数据清零口径）
            self._auto_read_count = 0
            self._manual_read_count = 0
            self._update_read_counter()
            # 新一批数据：分析时间标签重置（上一批的分析结果不再适用）
            if hasattr(self, "_analysis_time_label"):
                self._analysis_time_label.setText("🕒 分析：—")
            # 缓存 Data sheet DataFrame，点击分析时直接复用，跳过 ~20-30s 重复文件 IO
            self._cached_input_df = df
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.setText(self._format_preview_stats(df))
        except Exception as e:
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.setText(f"读取失败：{e}")
        finally:
            if self._file_worker is not None:
                self._file_worker.deleteLater()
                self._file_worker = None

    def _on_file_failed(self, msg):
        if hasattr(self, 'preview_label') and self.preview_label:
            self.preview_label.setText(f"读取失败：{msg}")
        if self._file_worker is not None:
            self._file_worker.deleteLater()
            self._file_worker = None

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

    def _filter_semi_materials(self, category: str):
        """从左侧面板筛选材料半成品：按名称精确匹配"半成品重分类"列"""
        df = self._get_master_df()
        if df is None or df.empty:
            QMessageBox.information(self, "提示", "暂无数据，请先加载并分析")
            return
        if '半成品重分类' not in df.columns:
            QMessageBox.warning(self, "提示", "当前数据缺少「半成品重分类」列，请先重新分析")
            return
        mask = df['半成品重分类'].astype(str) == category
        title = category
        count = int(mask.sum())
        if count == 0:
            QMessageBox.information(self, "提示", f"{title}：无匹配记录")
            return
        rows = [i for i, v in enumerate(mask.values) if v]
        proxy = self.table_view.model()
        src_model = proxy.sourceModel() if hasattr(proxy, "sourceModel") else None
        sel = QItemSelection()
        for i in rows:
            if src_model is not None:
                idx = proxy.mapFromSource(src_model.index(i, 0))
            else:
                idx = proxy.index(i, 0)
            if idx.isValid():
                sel.select(idx, idx)
        if not sel.isEmpty():
            self.table_view.selectionModel().select(
                sel, QItemSelectionModel.Select | QItemSelectionModel.Rows
            )
        self.statusBar().showMessage(f"已筛选 {title}：{count} 条记录")

    def _reset_semi_filter(self):
        """重置半成品筛选：清除主表行选中状态"""
        if not hasattr(self, 'table_view'):
            return
        self.table_view.selectionModel().clearSelection()
        self.statusBar().showMessage("已重置半成品筛选", 2000)

    # -----------------------------------------------------------
    # 半成品类目管理（持久化到 config/semi_user_categories.json）
    # JSON 格式: [{"name": "分类名", "factory": "工厂"}, ...]
    # 兼容旧格式: {"name":..., "col":..., "cond":..., "val":...}
    # -----------------------------------------------------------
    def _load_semi_categories(self):
        """从 config/semi_user_categories.json 加载类目列表"""
        candidates = []
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            candidates.append(os.path.join(sys._MEIPASS, 'config', 'semi_user_categories.json'))
        _here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(_here, '..', 'config', 'semi_user_categories.json'))
        _path = next((p for p in candidates if os.path.exists(p)), None)
        if not _path:
            return []
        try:
            with open(_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            # 兼容旧格式，转换为新格式
            result = []
            for item in data:
                if isinstance(item, dict):
                    result.append({
                        'name': item.get('name', ''),
                        'factory': item.get('factory', ''),
                    })
            return result
        except Exception:
            return []

    def _save_semi_categories(self, categories):
        """将类目列表写回 config/semi_user_categories.json"""
        _here = os.path.dirname(os.path.abspath(__file__))
        _path = os.path.join(_here, '..', 'config', 'semi_user_categories.json')
        try:
            os.makedirs(os.path.dirname(_path), exist_ok=True)
            with open(_path, 'w', encoding='utf-8') as f:
                json.dump(categories, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _refresh_semi_list_ui(self):
        """根据当前 _semi_categories 刷新左侧面板半成品列表显示"""
        if not hasattr(self, 'left_panel_component') or not hasattr(self.left_panel_component, 'semi_table'):
            return
        table = self.left_panel_component.semi_table
        table.setSortingEnabled(False)
        table.setRowCount(len(self._semi_categories))
        for i, cat in enumerate(self._semi_categories):
            factory = cat.get('factory', '')
            name = cat.get('name', '')
            factory_item = QTableWidgetItem(factory)
            factory_item.setFlags(factory_item.flags() & ~Qt.ItemIsEditable)
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setData(Qt.ItemDataRole.UserRole, name)
            table.setItem(i, 0, factory_item)
            table.setItem(i, 1, name_item)
        table.setSortingEnabled(True)
        table.sortByColumn(0, Qt.AscendingOrder)
        table.clearSelection()
        if hasattr(self, 'semi_count_label'):
            self.semi_count_label.setText(f"共 {len(self._semi_categories)} 项")

    def _add_semi_category(self):
        """弹出添加分类对话框：输入名称 + 选择工厂"""
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QLabel, QLineEdit,
            QComboBox, QVBoxLayout, QHBoxLayout,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("添加半成品分类")
        dlg.setFixedSize(400, 180)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        # 分类名
        name_label = QLabel("分类名称：")
        name_input = QLineEdit()
        name_input.setPlaceholderText("例如：冷链原料半成品")
        layout.addWidget(name_label)
        layout.addWidget(name_input)

        # 工厂
        factory_label = QLabel("工厂：")
        factory_combo = QComboBox()
        factory_combo.addItems(["1101", "1102"])
        layout.addWidget(factory_label)
        layout.addWidget(factory_combo)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return

        cat_name = name_input.text().strip()
        if not cat_name:
            QMessageBox.warning(dlg, "提示", "分类名称不能为空")
            return
        # 检查重复
        if any(c['name'] == cat_name for c in self._semi_categories):
            QMessageBox.warning(dlg, "提示", f"分类「{cat_name}」已存在")
            return

        factory = factory_combo.currentText()
        new_cat = {'name': cat_name, 'factory': factory}
        self._semi_categories.append(new_cat)
        self._save_semi_categories(self._semi_categories)
        self._refresh_semi_list_ui()
        QMessageBox.information(dlg, "成功", f"已添加分类「{cat_name}」")

    def _delete_semi_category(self):
        """删除选中的半成品分类"""
        table = getattr(self.left_panel_component, 'semi_table', None)
        if table is None:
            return
        current_row = table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先选中要删除的分类")
            return
        name = self._semi_categories[current_row]['name']
        self._semi_categories.pop(current_row)
        self._save_semi_categories(self._semi_categories)
        self._refresh_semi_list_ui()
        QMessageBox.information(self, "成功", f"已删除分类「{name}」")

    def _reset_semi_categories(self):
        """重置半成品分类为默认值"""
        if not QMessageBox.question(self, "确认", "确定要重置所有半成品分类吗？",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return
        self._semi_categories = []
        self._save_semi_categories(self._semi_categories)
        self._refresh_semi_list_ui()
        QMessageBox.information(self, "成功", "已重置所有半成品分类")

    def _import_semi_categories(self):
        """从 JSON 文件导入半成品分类"""
        file_path, _ = QFileDialog.getOpenFileName(self, "导入半成品分类", "", "JSON files (*.json)")
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                QMessageBox.warning(self, "错误", "文件格式不正确")
                return
            # 兼容旧格式
            imported = []
            for item in data:
                if isinstance(item, dict):
                    imported.append({
                        'name': item.get('name', ''),
                        'factory': item.get('factory', ''),
                    })
            # 合并去重
            existing_names = {c['name'] for c in self._semi_categories}
            for cat in imported:
                if cat['name'] and cat['name'] not in existing_names:
                    self._semi_categories.append(cat)
                    existing_names.add(cat['name'])
            self._save_semi_categories(self._semi_categories)
            self._refresh_semi_list_ui()
            QMessageBox.information(self, "成功", f"已导入 {len(imported)} 个分类")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {e}")

    def _export_semi_categories(self):
        """导出半成品分类到 JSON 文件"""
        file_path, _ = QFileDialog.getSaveFileName(self, "导出半成品分类", "semi_categories.json", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self._semi_categories, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", f"已导出到 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _open_output_dir(self):
        dir_path = self.output_dir_edit.text()
        if not dir_path:
            dir_path = os.path.expanduser("~/Documents/ZPP011分析报告")
        if os.path.exists(dir_path):
            os.startfile(dir_path)
        else:
            QMessageBox.warning(self, "提示", "输出目录不存在")

    # -----------------------------------------------------------
    # 文件夹监控自动加载
    # -----------------------------------------------------------
    # 监控自动加载文件名白名单：只自动加载符合 SAP 导出命名的真实文件，
    # 排除测试产物（如 _verify_fallback.xlsx）、分析报告、临时锁文件（~$ 开头）。
    # 接受两类：
    #   1) ZPP011_导出范围.xlsx  -> ZPP011_YYYYMMDD[-YYYYMMDD].xlsx（容忍 Excel 副本后缀 (1)）
    #   2) ZPP011_SAP_*.xlsx     -> SAP 自动拉取输出（当前为时间戳命名，鲁棒兼容任意后缀）
    _MONITOR_ACCEPT_RE = re.compile(
        r'^ZPP011_(?:\d{8}(?:-\d{8})?(?:\s*\(\d+\))?|SAP_.*)\.xlsx?$',
        re.IGNORECASE,
    )

    def _is_monitor_accepted_file(self, fname):
        """监控自动加载白名单：该文件名是否应被自动加载。"""
        base = os.path.basename(fname)
        if base.startswith("~$"):
            return False
        return bool(self._MONITOR_ACCEPT_RE.match(base))

    def _toggle_folder_monitor(self, checked):
        """工具栏/菜单开关：监控 E:/ZPP011导出文件原数据 目录，发现新 Excel 自动加载。"""
        self._monitor_enabled = checked
        if checked:
            # 开始监控：重置稳定性缓存，保留已加载指纹（同名文件重新导出仍可识别）
            self._monitor_last_size = {}
            if not os.path.isdir(self._monitor_dir):
                toast(f"⚠️ 监控目录不存在：{self._monitor_dir}", "warning", parent=self)
            else:
                toast(f"👁 已开始监控文件夹：{self._monitor_dir}", "info", parent=self)
            self._monitor_timer.start()
        else:
            self._monitor_timer.stop()
            toast("⏹ 已停止监控文件夹", "info", parent=self)

    def _seed_monitor_baseline(self):
        """默认开启时调用：把当前目录里最新文件登记为基线，避免启动即触发一次分析，
        之后只有比基线更新的导出文件才会被自动加载。"""
        d = self._monitor_dir
        if not os.path.isdir(d):
            return
        try:
            files = [os.path.join(d, f) for f in os.listdir(d)
                     if f.lower().endswith((".xlsx", ".xls")) and self._is_monitor_accepted_file(f)]
        except Exception:
            return
        if not files:
            return
        def _mtime(fp):
            try:
                return os.stat(fp).st_mtime
            except Exception:
                return 0
        files.sort(key=_mtime, reverse=True)
        fp = os.path.normpath(files[0])
        try:
            st = os.stat(fp)
        except Exception:
            return
        self._monitor_last_size[fp] = st.st_size
        self._monitor_loaded.add((fp, int(st.st_mtime), st.st_size))

    def _scan_monitor_dir(self):
        if not self._monitor_enabled:
            return
        d = self._monitor_dir
        if not os.path.isdir(d):
            return
        try:
            files = [os.path.join(d, f) for f in os.listdir(d)
                     if f.lower().endswith((".xlsx", ".xls")) and self._is_monitor_accepted_file(f)]
        except Exception:
            return
        if not files:
            return
        # 只盯「最新」文件：按 mtime 降序取第一个，避免 NTFS 下列出顺序不定导致加载到旧文件
        def _mtime(fp):
            try:
                return os.stat(fp).st_mtime
            except Exception:
                return 0
        files.sort(key=_mtime, reverse=True)
        fp = os.path.normpath(files[0])
        try:
            st = os.stat(fp)
        except Exception:
            return
        # 稳定性判定：与上次的 size 比较，连续两次相同且 >0 视为写完，避免读半截文件
        prev = self._monitor_last_size.get(fp)
        if prev is None:
            self._monitor_last_size[fp] = st.st_size
            return
        if prev != st.st_size:
            self._monitor_last_size[fp] = st.st_size
            return
        key = (fp, int(st.st_mtime), st.st_size)
        if key in self._monitor_loaded:
            return
        # 已在等待加载队列中，避免重复排队
        if key in self._monitor_pending:
            return
        # 新稳定文件（且是当前目录最新）-> 延迟加载
        # 延迟目的：下载工具常自动打开文件预览，用户还没关闭就被监控到，
        # 立刻加载会因文件被占用而报「被占用」。延迟 5 秒给关闭窗口留时间，
        # 即使仍被占用，_monitor_try_load 也会自动重试而不直接报错。
        self._monitor_pending.add(key)
        toast(f"📥 监控到新文件，{self._monitor_delay_ms // 1000} 秒后自动加载："
              f"{os.path.basename(fp)}（若已自动打开请先关闭）", "info", parent=self)
        QTimer.singleShot(self._monitor_delay_ms, lambda: self._monitor_try_load(fp, key))

    def _monitor_file_busy(self, fp):
        """检测文件是否被占用（与 analyzer 的占用判定一致：以 r+b 方式打开尝试）。"""
        try:
            with open(fp, "r+b"):
                pass
            return False
        except PermissionError:
            return True
        except Exception:
            return False

    def _monitor_try_load(self, fp, key, attempt=0):
        """延迟后真正加载：若文件仍被占用（预览窗口未关闭），自动重试若干次；
        重试耗尽则放弃本次，等下次扫描重新触发，避免直接报「被占用」。"""
        if not self._monitor_enabled:
            self._monitor_pending.discard(key)
            return
        if self._monitor_file_busy(fp):
            if attempt < self._monitor_busy_retry:
                QTimer.singleShot(self._monitor_busy_interval,
                                  lambda: self._monitor_try_load(fp, key, attempt + 1))
                return
            # 重试耗尽：移除排队标记，下次扫描会重新检测到该文件并再次尝试
            self._monitor_pending.discard(key)
            toast(f"⚠️ 文件仍被占用，暂未加载：{os.path.basename(fp)}"
                  f"（关闭预览后将被自动重新检测）", "warning", parent=self)
            return
        # 文件可用 -> 正式加载（记录指纹 + 移除排队 + 标记为监控自动加载）
        self._monitor_pending.discard(key)
        self._monitor_loaded.add(key)
        self._monitor_current_key = key
        self._monitor_auto_loading = True
        self._auto_load_from_monitor(fp)

    def _auto_load_from_monitor(self, fp):
        """监控到新文件：写入当前输入文件并触发分析加载（复用主流程）。"""
        fp = os.path.normpath(fp)
        # 若分析/缓存/导出等重型操作正在进行，稍后重试（避免并发 do_analysis_v2 卡死 UI）
        if self._heavy_busy or (self.analysis_controller.worker and self.analysis_controller.worker.isRunning()):
            # 延迟 3 秒再试一次，期间仍视为监控自动加载
            QTimer.singleShot(3000, lambda: self._auto_load_from_monitor(fp))
            return
        self.current_input_file = fp
        if hasattr(self, "input_file_edit") and self.input_file_edit:
            self.input_file_edit.setText(os.path.basename(fp))
            self.input_file_edit.setToolTip(fp)
        toast(f"📥 监控到新文件，自动加载：{os.path.basename(fp)}", "info", parent=self)
        self._monitor_auto_loading = True
        self._start_analysis()


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

    def _add_alt_pair_from_selection(self):
        """智能添加替代料：从主表选中 2 行自动提取工厂/编码/名称，弹窗核对后写入。"""
        if self.view_model is None or self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "请先加载并分析数据")
            return
        if self.proxy_model is None or self.source_model is None:
            QMessageBox.warning(self, "提示", "主表尚未就绪，无法读取选中行")
            return
        # 选中行（proxy 行号）→ 去重 → 映射源行号，保留选中顺序
        sel = self.table_view.selectionModel().selectedRows()
        src_rows = []
        seen = set()
        for idx in sel:
            r = self.proxy_model.mapToSource(idx).row()
            if r not in seen:
                seen.add(r)
                src_rows.append(r)
        if len(src_rows) != 2:
            QMessageBox.warning(
                self, "提示",
                f"请在主表选中恰好 2 行（当前选中 {len(src_rows)} 行）\n"
                "选中两行后，将自动提取它们的物料信息作为替代料配对。"
            )
            return
        df = self.source_model.getDataFrame()

        def extract(r):
            row = df.iloc[r]
            return (
                str(row.get('factory', '') or '').strip(),
                str(row.get('code', '') or '').strip(),
                str(row.get('name', '') or '').strip(),
            )

        a = extract(src_rows[0])
        b = extract(src_rows[1])
        if not a[1] or not b[1]:
            QMessageBox.warning(self, "提示", "选中的两行中至少有一行「物料号」为空，无法作为替代料配对")
            return
        if a[1] == b[1]:
            QMessageBox.warning(self, "提示", f"两行「物料号」均为 {a[1]}，是同一物料，不能作为替代料配对")
            return
        if self.alt_controller.show_add_from_rows_dialog(self, a, b):
            # add_pair 已 emit data_changed → 刷新替代料列表并重算净偏差
            toast(f"✅ 已添加替代料配对：{a[1]} ↔ {b[1]}", "success", parent=self)

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

    def _zoom_semi_table(self):
        """弹出半成品分类放大窗口，支持双击筛选"""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("半成品分类详情")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)

        # 说明标签
        tip_label = QLabel("双击任意行可筛选该分类。点击「关闭」退出。")
        tip_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(tip_label)

        # 表格
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["工厂", "分类名称", "操作"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.sortByColumn(0, Qt.AscendingOrder)

        # 填充数据
        categories = self._semi_categories
        table.setRowCount(len(categories))
        for i, cat in enumerate(categories):
            factory = cat.get('factory', '')
            name = cat.get('name', '')
            table.setItem(i, 0, QTableWidgetItem(str(factory)))
            table.setItem(i, 1, QTableWidgetItem(name))
            # 操作按钮
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(4, 2, 4, 2)
            filter_btn = QPushButton("筛选")
            filter_btn.clicked.connect(lambda checked, n=name: self._filter_semi_material(n))
            delete_btn = QPushButton("删除")
            delete_btn.clicked.connect(lambda checked, idx=i: self._delete_semi_category(idx))
            btn_layout.addWidget(filter_btn)
            btn_layout.addWidget(delete_btn)
            btn_layout.addStretch()
            widget = QWidget()
            widget.setLayout(btn_layout)
            table.setCellWidget(i, 2, widget)

        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().resizeSection(0, 80)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.horizontalHeader().resizeSection(2, 140)

        # 双击筛选
        table.cellDoubleClicked.connect(lambda row, col: self._filter_semi_material(table.item(row, 1).text()))

        layout.addWidget(table)

        # 按钮区
        btn_row = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

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
            # 全屏时保留底部合计栏，隐藏系统状态栏
            if hasattr(self, 'filter_panel') and self.filter_panel:
                self.filter_panel.setVisible(False)
            self.statusBar().hide()
            QApplication.processEvents()
            self.statusBar().showMessage("全屏模式 (F11 退出)", 3000)
        else:
            self.left_panel.setVisible(True)
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
        self._hidden_column_names.update({
            '_post_audit_changed', 'data_id', 'fingerprint', '_quarantined',
        })  # 内部技术列始终隐藏（即使用户在列显隐对话框里勾选显示）
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
        self.proxy_model.setDynamicSortFilter(False)  # 关键性能修复：关闭 dataChanged 触发的整表重过滤风暴
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)
        try:
            self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass
        self.source_model.dataChanged.connect(self._update_summary)
        self.source_model.dataRefreshed.connect(self._update_summary)
        # self.source_model.dataChanged.connect(self._refresh_stats_cards)  # stats_cards 已删除
        # 标记已读/加隔离等会走 source_model.setDataFrame → 实时刷新未读弹窗条数
        self.source_model.dataChanged.connect(self._refresh_unread_popup)
        self.source_model.dataRefreshed.connect(self._refresh_unread_popup)
        self.proxy_model.layoutChanged.connect(self._update_summary)
        self.proxy_model.layoutChanged.connect(self._update_mark_stats)
        # self.proxy_model.layoutChanged.connect(self._refresh_stats_cards)  # stats_cards 已删除
        self.source_model.dataChanged.connect(self._update_mark_stats)
        self.source_model.dataRefreshed.connect(self._update_mark_stats)
        self.source_model.modelReset.connect(self._update_mark_stats)
        # 三态排序：禁用 Qt 自动排序，改用列头点击（sectionClicked）自行管理 升/降/取消
        self.table_view.setSortingEnabled(False)
        self.table_view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self._natural_df = None          # 原始（加载时）顺序，供"取消排序"恢复
        self._in_sort = False            # 排序过程中的 setDataFrame 不刷新 _natural_df
        self.source_model.modelReset.connect(self._capture_natural_df)
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
        else:
            self._update_summary()
            self.stats_cards.refresh(df)
            self.filter_panel.update_options(df)
        # 真实数据载入后，弹未读汇总（非模态 + 延迟到渲染完成后，避免卡顿）
        if getattr(self, '_pending_unread_summary', False):
            self._pending_unread_summary = False
            if df is not None and not df.empty:
                QTimer.singleShot(0, self._show_unread_summary)
        # 数据变化（隔离/标记已读等）→ 实时刷新已弹出的未读汇总弹窗
        try:
            self._refresh_unread_popup()
        except Exception:
            pass

    def _schedule_unread_summary(self):
        """标记「本次为真实数据载入」，待 _on_view_model_data_changed 末尾弹未读汇总。"""
        self._pending_unread_summary = True

    def _get_master_df(self):
        """未读计数 / 各看板的唯一取数口径。

        source_model 持有的才是主表实际显示的那份数据：DataFrameModel.setDataFrame
        内部做了 df.copy()，因此「标记已读 / 加隔离」等操作只会改到 source_model，
        view_model.df 不会同步。两者一旦分叉，就会出现「弹窗数 ≠ 看板数」
        （用户实测：隔离区 2 条未读，弹窗只报 1 条）。
        故统一以 source_model 为准，仅在其不可用时回退 view_model.df。
        """
        try:
            if getattr(self, 'source_model', None) is not None:
                df = self.source_model.getDataFrame()
                if df is not None and not df.empty:
                    return df
        except Exception:
            pass
        return getattr(self.view_model, 'df', None)

    def _count_unread_items(self):
        """统计 4 类未读条数，返回 items 列表（供弹窗构建 + 实时刷新共用）。

        4 类未读统一用主表 _read 列判定，口径与各看板一致：
        - 隔离区未读     = _quarantined==1 且 _read==0
        - 变动提醒未读   = _post_audit_changed==1 且 _read==0（已改动且未读的行）
        - 替代料未读     = filter_alt_alerts 命中 且 _read==0（与替代料看板一致）
        - 偏差率预警未读 = |偏差率|>=10% 且非「实际0定额>0」且 _read==0
        无数据时返回 None。
        """
        df = self._get_master_df()
        if df is None or df.empty:
            return None

        # 未读掩码
        if '_read' in df.columns:
            read_mask = pd.to_numeric(
                df['_read'], errors='coerce').fillna(0).astype(int) == 0
        else:
            read_mask = pd.Series(True, index=df.index)

        # 列探测
        qty_col = next((c for c in ['数量-定额', '定额'] if c in df.columns), None)
        act_col = next((c for c in ['数量-实际', '实际'] if c in df.columns), None)
        rate_col = next((c for c in ['偏差率(%)', '偏差率', 'dev_rate'] if c in df.columns), None)
        alt_col = '是否替代料' if '是否替代料' in df.columns else None

        a = pd.to_numeric(df[act_col], errors='coerce').fillna(0) if act_col else pd.Series(0, index=df.index)
        q = pd.to_numeric(df[qty_col], errors='coerce').fillna(0) if qty_col else pd.Series(0, index=df.index)
        no_input = (a.abs() <= 0.001) & (q > 0.001)

        # 1. 隔离区未读
        if '_quarantined' in df.columns:
            n_q = int(((pd.to_numeric(df['_quarantined'], errors='coerce').fillna(0).astype(int) == 1) & read_mask).sum())
        else:
            n_q = 0
        # 2. 变动提醒未读（已改动且未读的行）
        if '_post_audit_changed' in df.columns:
            n_c = int(((pd.to_numeric(df['_post_audit_changed'], errors='coerce').fillna(0).astype(int) == 1) & read_mask).sum())
        else:
            n_c = 0
        # 3. 替代料未读（与替代料看板口径一致：超阈值/组内有差异 且 未读）
        threshold = getattr(self.alert_monitor, 'threshold', 10)
        alt_alerts = filter_alt_alerts(df, threshold) if alt_col else pd.DataFrame()
        n_a = int(read_mask.loc[alt_alerts.index].sum()) if not alt_alerts.empty else 0
        # 4. 偏差率预警未读
        if rate_col:
            rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
            alert_mask = (rates.abs() >= 10) & (~no_input)
            n_d = int((alert_mask & read_mask).sum())
        else:
            n_d = 0

        return [
            {"icon": "📦", "label": "隔离区", "count": n_q,
             "callback": self._open_quarantine_dialog},
            {"icon": "📝", "label": "变动提醒", "count": n_c,
             "callback": self._show_audit_changes_dialog},
            {"icon": "🔄", "label": "替代料", "count": n_a,
             "callback": self._show_alert_dashboard},
            {"icon": "⚠️", "label": "偏差率预警", "count": n_d,
             "callback": self._show_deviation_warning_dialog},
        ]

    def _show_unread_summary(self, force=False):
        """分析/加载完成后，弹常驻非模态未读汇总弹窗。

        force=False（默认，分析后自动调）：全部已读则不弹，避免无意义打扰。
        force=True（工具栏按钮/用户主动调）：不论是否全已读都弹，全已读时显示
                  0 条 + 「全清零啦」提示语，方便用户随时复查。
        """
        try:
            items = self._count_unread_items()
            if not items:
                if force:
                    toast("ℹ️ 主表无任何未读数据可统计", "info", parent=self, duration=4000)
                return
            all_zero = all(it["count"] == 0 for it in items)
            if all_zero and not force:
                return  # 分析后自动调：全已读不弹，避免无意义打扰

            # 单例：已有弹窗就地刷新并置前，不重复弹、不销毁重建（避免闪烁/引用环）
            existing = getattr(self, '_unread_popup', None)
            if existing is not None:
                try:
                    if all_zero:
                        # 全已读：把现有弹窗刷成 0 条，并在标题旁加 "全清零啦"
                        existing.update_counts(items)
                        existing.mark_all_clear()
                    else:
                        existing.update_counts(items)
                        existing.clear_all_clear()
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                    return
                except RuntimeError:
                    self._unread_popup = None

            popup = UnreadSummaryPopup(items, self)
            if all_zero:
                popup.mark_all_clear()
            popup.closed.connect(self._on_unread_popup_closed)
            self._unread_popup = popup
            popup.show()
            popup.raise_()
            popup.activateWindow()
        except Exception:
            import traceback as _tb
            _tb.print_exc()

    def show_unread_summary(self, force=False):
        """工具栏「📋 未读概览」按钮入口——用户主动复查。"""
        self._show_unread_summary(force=force)

    def _on_unread_popup_closed(self):
        """弹窗关闭（用户点「关闭」或清零自动关）→ 清掉单例引用。"""
        self._unread_popup = None

    def _refresh_unread_popup(self):
        """数据变化（加隔离 / 标记已读等）→ 实时刷新已弹出的未读汇总弹窗。

        - 弹窗不存在：什么都不做（不主动弹，避免打扰）。
        - 4 类全部清零：自动关闭（满足「信息清零自动关闭」）。
        - 否则：就地刷新条数（满足「没清零就一直挂着」）。
        """
        popup = getattr(self, '_unread_popup', None)
        if popup is None:
            return
        try:
            items = self._count_unread_items()
            if not items:
                return
            if all(it["count"] == 0 for it in items):
                popup._safe_close()
                self._unread_popup = None
                return
            popup.update_counts(items)
        except RuntimeError:
            # C++ 对象已销毁，丢弃引用即可
            self._unread_popup = None
        except Exception:
            pass

    def _on_stats_card_clicked(self, card_type: str):
        """统计卡片点击：切换对应筛选（审核后变更 / 隔离区卡可过滤对应行）

        注意：这里绝不能直接改写 proxy._custom_filters（旧实现拿 proxy 旧字典
        改一改再 setCustomFilters 写回，会把面板已清掉的条件重新塞回 proxy，
        造成「界面没勾选、proxy 却在暗中过滤」的状态残留 bug——表现为筛选
        结果莫名为 0 行/假数据，重启才恢复）。
        唯一数据源 = 筛选面板：只操作面板控件，由面板 _emit_filter 用完整
        状态整体替换 proxy 条件。
        """
        if self.proxy_model is None or self.view_model.df is None:
            return
        if card_type == 'changed':
            cb = self.filter_panel.color_checks.get('_changed_only')
            if cb is not None and cb.isChecked():
                self.filter_panel.set_color_filter('all')
                msg = "已显示全部记录"
            else:
                self.filter_panel.set_color_filter('changed')
                msg = "已过滤：仅显示审核后变更的记录"
            self.statusBar().showMessage(msg, 3000)
        elif card_type == 'quarantine':
            cb = self.filter_panel.color_checks.get('_quarantined_only')
            if cb is not None and cb.isChecked():
                self.filter_panel.set_color_filter('all')
                msg = "已显示全部记录"
            else:
                self.filter_panel.set_color_filter('quarantine')
                msg = "已过滤：仅显示隔离区记录"
            self.statusBar().showMessage(msg, 3000)
        elif card_type == 'anomaly':
            df = self.view_model.df
            rate_col = next((c for c in ['偏差率(%)', '偏差率', 'dev_rate'] if c in df.columns), None)
            if rate_col:
                rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
                count = int((rates.abs() > 30).sum())
                self.statusBar().showMessage(f"🔴 真异常 {count} 条（已排除替代料）", 5000)
        elif card_type == 'unread':
            if self.filter_panel.read_status_combo.currentText() == '未读':
                self.filter_panel.set_read_status_filter('全部')
                msg = "已显示全部记录"
            else:
                self.filter_panel.set_read_status_filter('未读')
                msg = "已过滤：仅显示未读记录"
            self.statusBar().showMessage(msg, 3000)
        elif card_type == 'deviation':
            self._show_deviation_warning_dialog()

    def log(self, msg, level="info"):
        """运行日志面板已移除，保留接口为空操作，避免各处 self.log(...) 调用崩溃。
        如需重新启用日志，恢复 bottom_bar 与 _v_splitter 中的日志项即可。"""
        pass

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

        # 无配置文件时用默认逻辑。
        # 注意：不再调用 resizeColumnsToContents()——万行级表格会逐行测量宽度，
        # 导致主线程卡顿/未响应。改为按列名设定合理最小宽度，让用户可手动拖动。
        self.table_view.setColumnWidth(0, 35)
        for col in range(1, model.columnCount()):
            col_name = model.headerData(col, Qt.Horizontal) if hasattr(model, 'headerData') else ''
            self._apply_default_width(col, col_name)

    def _apply_default_width(self, col, col_name):
        """对单列应用默认宽度逻辑（按列名给最小宽度，避免 ResizeToContents 扫描全表）"""
        if isinstance(col_name, str):
            if '名称' in col_name or '描述' in col_name or col_name == '物料':
                if self.table_view.columnWidth(col) < 200:
                    self.table_view.setColumnWidth(col, 200)
            elif '编码' in col_name or '号' in col_name or '订单' in col_name or col_name == '半成品重分类':
                if self.table_view.columnWidth(col) < 120:
                    self.table_view.setColumnWidth(col, 120)
            elif '备注' in col_name or '原因' in col_name:
                if self.table_view.columnWidth(col) < 150:
                    self.table_view.setColumnWidth(col, 150)
            else:
                # 数字/日期等列给一个保底宽度，避免太窄
                if self.table_view.columnWidth(col) < 80:
                    self.table_view.setColumnWidth(col, 80)

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
        # 记录生效的筛选条件，方便排查"有数据但表格空白"等问题
        active = {k: v for k, v in filters.items() if v not in (None, '', [], {})}
        if active:
            self.log(f"[筛选] 当前条件: {active}", "debug")
        else:
            self.log("[筛选] 条件已清空", "debug")
        self.proxy_model.setCustomFilters(filters)
        self._update_summary()

    def _on_header_clicked(self, logical_index):
        """列头点击：单列为【未排 → 升序 → 降序 → 未排】三态循环；Ctrl+点击为多列多级排序。"""
        modifiers = QApplication.keyboardModifiers()
        ctrl_pressed = bool(modifiers & Qt.ControlModifier)
        col = logical_index
        if col <= 0:
            return  # 第一列(_read)不参与排序
        if ctrl_pressed:
            found = False
            for i, (c, asc) in enumerate(self.sort_columns):
                if c == col:
                    self.sort_columns[i] = (col, not asc)
                    found = True
                    break
            if not found:
                self.sort_columns.append((col, True))
        else:
            active = [(c, a) for (c, a) in self.sort_columns if c == col]
            if not active:
                self.sort_columns = [(col, True)]
            elif active[0][1]:
                self.sort_columns = [(col, False)]
            else:
                self.sort_columns = []
        self._apply_multi_sort()
        self._update_sort_indicators()

    def _apply_multi_sort(self):
        """按 self.sort_columns 重排主表（基于原始顺序，避免多次排序叠加）。
        空列表时恢复加载时的原始顺序（取消排序）。"""
        if not hasattr(self, "source_model") or self.source_model is None:
            return
        if not self.sort_columns:
            # 取消排序：恢复原始（加载时）顺序
            if self._natural_df is not None:
                self._in_sort = True
                try:
                    self.source_model.setDataFrame(self._natural_df.copy())
                finally:
                    self._in_sort = False
                self._apply_column_visibility_by_name()
            return
        natural = self._natural_df if self._natural_df is not None else self.source_model.getDataFrame()
        if natural is None or natural.empty:
            return
        df = natural.copy()
        sort_args = []
        for col, asc in self.sort_columns:
            if col <= 0 or col >= len(df.columns):
                continue
            sort_args.append((df.columns[col], asc))
        if not sort_args:
            return
        cols = [c for c, _ in sort_args]
        asc_list = [a for _, a in sort_args]
        sort_keys = {}
        for c in cols:
            has_pct = df[c].astype(str).str.contains("%", na=False).any()
            if has_pct:
                numeric_vals = pd.to_numeric(df[c].astype(str).str.replace("%", "").str.strip(), errors="coerce").fillna(0)
                sort_keys[c] = numeric_vals
        if sort_keys:
            df_sorted = df.sort_values(by=cols, ascending=asc_list, key=lambda col: sort_keys.get(col.name, col), na_position="last")
        else:
            df_sorted = df.sort_values(by=cols, ascending=asc_list, na_position="last")
        self._in_sort = True
        try:
            self.source_model.setDataFrame(df_sorted)
        finally:
            self._in_sort = False
        self._apply_column_visibility_by_name()

    def _capture_natural_df(self):
        """数据（重新）加载时记录原始顺序，供"取消排序"恢复；排序过程中的 setDataFrame 忽略。"""
        if getattr(self, "_in_sort", False):
            return
        if self.source_model is not None:
            df = self.source_model.getDataFrame()
            if df is not None:
                self._natural_df = df.copy()

    def _update_sort_indicators(self):
        """同步列头排序箭头（单/多列升/降态）。
        PySide6/Qt6 无 setSortIndicatorClear，用 setSortIndicatorShown 代替。"""
        header = self.table_view.horizontalHeader()
        header.blockSignals(True)
        try:
            if not self.sort_columns:
                header.setSortIndicatorShown(False)
                return
            header.setSortIndicatorShown(True)
            # QHeaderView 只支持单箭头，多列时显示最后一级
            col, asc = self.sort_columns[-1]
            header.setSortIndicator(col, Qt.AscendingOrder if asc else Qt.DescendingOrder)
        finally:
            header.blockSignals(False)

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
            # 后台线程已预处理过（带 _read 列）→ 直接复用，避免主线程再跑 31s 卡顿；
            # 仅在拿到原始 dev_df（无 _read 列）时才在主线程预处理（兜底）。
            if '_read' in df.columns:
                processed_df = df
            else:
                processed_df = self.data_service.preprocess_audit_data(df)
            if self.source_model is None:
                self.source_model = DataFrameModel()
                self.proxy_model = AuditProxyModel()
                self.proxy_model.setDynamicSortFilter(False)  # 同上，关闭重过滤风暴
                self.proxy_model.setSourceModel(self.source_model)
                self.table_view.setModel(self.proxy_model)
                self.proxy_model.layoutChanged.connect(self._update_mark_stats)
                self.source_model.dataChanged.connect(self._update_mark_stats)
                self.source_model.dataRefreshed.connect(self._update_mark_stats)
                self.source_model.modelReset.connect(self._update_mark_stats)
            try:
                self.source_model.setDataFrame(processed_df)
            except Exception as _e:
                import traceback as _tb
                _tb.print_exc()
                raise
            self._apply_column_visibility_by_name()
            self._schedule_unread_summary()
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

    def _update_mark_stats(self):
        """更新主表上方『标记统计』标签：当前筛选后可见行中，各类颜色标记的行数。

        三类标记来自 source_model 的私有集合（set of 源行号）：
          - 偏差预警(橙) = _alert_rows（|偏差率|>=10% 且非未投料）
          - 替代料(蓝)   = _substitute_rows（是否替代料=是）
          - 未投料(灰)   = _unused_rows（实际≈0 且 定额>0 且非替代料）
        计数按 proxy_model 当前可见行统计，故筛选/搜索变化即动态刷新。
        触发：proxy.layoutChanged（筛选/排序）+ source.dataChanged/modelReset（数据重算）。
        """
        lbl = getattr(self.main_table, "mark_stats_label", None)
        if lbl is None:
            return
        if self.source_model is None or self.proxy_model is None:
            lbl.setText("标记统计：—")
            return
        sm = self.source_model
        pm = self.proxy_model
        alert = getattr(sm, "_alert_rows", set())
        sub = getattr(sm, "_substitute_rows", set())
        unused = getattr(sm, "_unused_rows", set())
        n_alert = n_sub = n_unused = 0
        rows = pm.rowCount()
        if rows:
            for r in range(rows):
                sr = pm.mapToSource(pm.index(r, 0)).row()
                if sr in alert:
                    n_alert += 1
                if sr in sub:
                    n_sub += 1
                if sr in unused:
                    n_unused += 1
        lbl.setText(
            "🔴 偏差预警 %d 条    🔵 替代料 %d 条    ⚪ 未投料 %d 条"
            % (n_alert, n_sub, n_unused)
        )

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

        # 若分析/缓存/上次报告生成仍在进行，避免再叠加一个 do_analysis_v2 导致 UI 卡死
        if self._heavy_busy:
            QMessageBox.information(self, "提示", "分析/报告生成进行中，请稍候再导出")
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
            from gui_pyside6.save_guard import safe_save
            saved = safe_save(
                self, save_path,
                lambda p: audit_data.to_excel(p, sheet_name='完整偏差明细', index=False),
                what="表格",
            )
            if not saved:
                self.log("导出已取消（目标文件被占用）", "warning")
                return
            save_path = saved
            if QMessageBox.question(
                self, "导出成功", f"文件已导出到：\n{save_path}\n是否打开？"
            ) == QMessageBox.Yes:
                os.startfile(save_path)
            self.log(f"已导出完整Excel到 {save_path}", "info")
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
            self.log(f"导出失败: {e}", "error")

    def _export_full_analysis_inline(self, save_path, analysis_params, cache_path):
        """生成完整多Sheet Excel（优先使用缓存）"""
        import shutil
        from PySide6.QtWidgets import QApplication, QProgressDialog

        # 缓存命中：直接复制
        if cache_path and os.path.exists(cache_path):
            try:
                from gui_pyside6.save_guard import safe_save
                _saved = safe_save(self, save_path,
                                   lambda p: shutil.copy2(cache_path, p),
                                   what="报告")
                if not _saved:
                    self.log("导出已取消（目标文件被占用）", "warning")
                    return
                save_path = _saved
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
            except Exception as e:
                QMessageBox.warning(
                    self, "缓存复制失败",
                    f"缓存复制失败：{e}\n\n将重新分析生成报告。"
                )
                self.log(f"缓存复制失败，回退重新分析: {e}", "warning")

        # 重新分析要跑几十秒，先确认目标文件写得进去，免得白算一场
        from gui_pyside6.save_guard import precheck_save_path
        save_path = precheck_save_path(self, save_path, what="报告")
        if not save_path:
            self.log("导出已取消（目标文件被占用）", "warning")
            return

        # 重新分析生成（转后台线程，避免主线程冻结）
        self._export_full_analysis_background(
            save_path, analysis_params, cache_path
        )

    def _export_full_analysis_background(self, save_path, analysis_params, cache_path):
        """后台线程重新分析生成完整报告，完成后弹窗通知；界面不锁。"""
        from PySide6.QtWidgets import QProgressDialog, QApplication
        from analysis.analyzer import do_analysis_v2

        # 导出前确认目标文件写得进去（后台线程里弹不了窗，必须在这拦）
        from gui_pyside6.save_guard import precheck_save_path
        save_path = precheck_save_path(self, save_path, what="报告")
        if not save_path:
            self.log("导出已取消（目标文件被占用）", "warning")
            return

        progress_dlg = QProgressDialog("正在后台生成完整报告...", "取消", 0, 100, self)
        progress_dlg.setWindowTitle("导出中")
        progress_dlg.setWindowModality(Qt.NonModal)  # 不锁界面，可继续操作主表
        progress_dlg.setMinimumDuration(0)
        progress_dlg.show()

        worker = _FullReportWorker(
            input_file=analysis_params['input_file'],
            alt_pairs=analysis_params['alt_pairs'],
            start_date=analysis_params.get('start_date'),
            end_date=analysis_params.get('end_date'),
            material_search=analysis_params.get('material_search'),
            output_path=save_path,
        )
        # 进度回调（主线程）
        worker.progress.connect(
            lambda pct, txt: (progress_dlg.setValue(pct),
                              progress_dlg.setLabelText(f"{txt} ({pct}%)"))[0]
        )
        # 取消：进度对话框 wasCanceled → worker 取消标志
        progress_dlg.canceled.connect(worker.request_cancel)
        # 完成/失败回调（主线程）
        worker.finished_ok.connect(
            lambda out_path: self._on_full_report_done(out_path, cache_path, progress_dlg)
        )
        worker.failed.connect(
            lambda err: (progress_dlg.close(),
                         setattr(self, '_heavy_busy', False),
                         QMessageBox.critical(self, "错误", f"导出完整报告失败: {err}"),
                         self.log(f"导出完整报告失败: {err}", "error"))
        )
        self._full_report_worker = worker  # 防止被 GC
        self._heavy_busy = True
        worker.start()

    def _on_full_report_done(self, save_path, cache_path, progress_dlg):
        """后台生成完成：回存缓存 + 弹窗通知（不锁界面）"""
        self._heavy_busy = False
        progress_dlg.close()
        # 回存缓存
        if cache_path and not os.path.exists(cache_path):
            try:
                import shutil
                shutil.copy2(save_path, cache_path)
            except Exception:
                pass
        reply = QMessageBox.question(
            self, "导出成功",
            f"完整分析报告已生成：\n{save_path}\n\n"
            "包含Sheet:\n"
            "📋 分析说明 · 汇总统计(带预警颜色)\n"
            "完整偏差明细 · 替代料明细 · 无备注预警\n"
            "中间地带明细 · 异常预警 · 偏差金额分析\n"
            "偏差原因汇总 · 偏差原因分析 · 趋势分析\n\n"
            "是否立即打开？"
        )
        if reply == QMessageBox.Yes:
            os.startfile(save_path)
        self.log(f"已导出完整分析报告到 {save_path}", "info")

    # -----------------------------------------------------------
    # 净偏差
    # -----------------------------------------------------------
    def _sync_alt_pairs_for_full_report(self):
        """重算净偏差后，把当前替代料配对同步给完整报告并失效旧缓存，
        保证「加料 → 刷新净偏差 → 导出完整报告」三者一致。

        背景：完整报告导出(_export_full_analysis_inline)优先复制上次分析生成的缓存，
        或重跑分析时使用 analysis_params['alt_pairs']（上次「分析」快照）。
        仅改内存 df 不会更新这两者，导致新增的替代料不进完整报告。"""
        # 1. 同步最新配对到完整报告所用分析参数（导出读取的就是它）
        if isinstance(self._analysis_params, dict):
            self._analysis_params['alt_pairs'] = list(self.alt_controller.get_pairs())
        # 2. 失效完整报告缓存（否则下次导出直接复制不含新料的旧缓存）
        cp = getattr(self, '_full_analysis_cache_path', None)
        if cp and os.path.exists(cp):
            try:
                os.remove(cp)
            except OSError:
                pass
        self._full_analysis_cache_path = None

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
            self._schedule_unread_summary()
            self.view_model.df = df
            if self.source_model is not None:
                self.source_model.setDataFrame(df)
                self._apply_column_visibility_by_name()
                self.proxy_model.invalidate()
            self._on_view_model_data_changed()
            self._sync_alt_pairs_for_full_report()
            if not silent:
                self.statusBar().showMessage("净偏差已重置为原始值", 2000)
            return
        try:
            new_df = apply_net_offset(df, alt_pairs, group_key=["订单日期", "流程订单"])
            self._schedule_unread_summary()
            self.view_model.df = new_df
            if self.source_model is not None:
                self.source_model.setDataFrame(new_df)
                self._apply_column_visibility_by_name()
                self.proxy_model.invalidate()
            self._on_view_model_data_changed()
            self._sync_alt_pairs_for_full_report()
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
        add_sel_action = menu.addAction("➕ 添加为替代料配对（选中2行）")
        add_sel_action.triggered.connect(lambda: self._add_alt_pair_from_selection())
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
        batch_export = menu.addAction("批量导出")
        batch_export.triggered.connect(lambda: self._batch_export_wrapper(selected_rows))
        menu.addSeparator()
        # 隔离区：按选中行是否已隔离显示不同操作
        already_q = False
        if self.view_model.df is not None and '_quarantined' in self.view_model.df.columns:
            try:
                first_id = self.view_model.df.iloc[selected_rows[0]].get('data_id')
                already_q = bool(first_id) and int(self.view_model.df.loc[self.view_model.df['data_id'] == first_id, '_quarantined'].iloc[0]) == 1
            except Exception:
                already_q = False
        if already_q:
            q_action = menu.addAction("↩ 取消隔离（选中行）")
            q_action.triggered.connect(lambda: self._set_quarantine(selected_rows, False))
        else:
            q_action = menu.addAction("⚠️ 移入隔离区（选中行）")
            q_action.triggered.connect(lambda: self._set_quarantine(selected_rows, True))
        menu.addSeparator()
        repair_action = menu.addAction("🔧 修复隔离区一致性（补写库内缺失行）")
        repair_action.triggered.connect(lambda: self._repair_quarantine_consistency())
        copy_region_action = menu.addAction("复制选中区域")
        copy_region_action.triggered.connect(self.copy_selected_cells)
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _get_displayed_dataframe(self):
        """返回当前主表筛选+排序后「正在显示」的数据（按显示顺序）。

        主表显示走 proxy_model（在 source_model 之上做筛选/排序），
        而 view_model.df 是全量、未筛选的 DataFrame。
        导出应取的是屏幕上看得见的子集，故遍历 proxy_model 可见行 mapToSource 回源表取数。
        若无 proxy / 无数据，回退为 view_model.df 全量。
        """
        if self.proxy_model is None or self.source_model is None:
            return self.view_model.df
        src_rows = []
        for r in range(self.proxy_model.rowCount()):
            src_idx = self.proxy_model.mapToSource(self.proxy_model.index(r, 0))
            src_rows.append(src_idx.row())
        df_full = self.source_model.getDataFrame()
        if df_full is None or df_full.empty:
            return df_full
        if not src_rows:
            # 筛选后无可见行：返回空表（保留列结构）
            return df_full.iloc[0:0].copy()
        return df_full.iloc[src_rows].copy()

    def _batch_export_wrapper(self, rows):
        df_subset = self._get_displayed_dataframe()
        if df_subset is None or (hasattr(df_subset, 'empty') and df_subset.empty):
            QMessageBox.warning(self, "提示", "当前筛选后没有可导出的数据")
            return
        self.audit_controller.batch_export(rows, df_subset, self)

    def _set_quarantine(self, rows, flag: bool):
        """右键菜单：将选中行移入/移出隔离区，并同步主表与卡片"""
        df = self.view_model.df
        if df is None or 'data_id' not in df.columns:
            return
        ids = set()
        for r in rows:
            if r >= len(df):
                continue
            uid = df.iloc[r].get('data_id')
            if uid:
                ids.add(str(uid))
        if not ids:
            return
        if flag:
            reason = _ask_quarantine_reason(self, "移入隔离区")
            if reason is None:
                return
            basis = "手动:" + (reason.strip() if reason.strip() else "手动隔离")
            add_quarantine_batch([(uid, reason, basis) for uid in ids])
        else:
            for uid in ids:
                remove_quarantine(uid)
        df.loc[df['data_id'].isin(ids), '_quarantined'] = 1 if flag else 0
        self.view_model.df = df
        if self.source_model:
            # 就地更新隔离标记，不整表 setDataFrame → 保留滚动/排序/选中/筛选视图
            self.source_model.mark_quarantine(ids, flag)
            if hasattr(self, '_apply_column_visibility_by_name'):
                self._apply_column_visibility_by_name()
        if hasattr(self, 'stats_cards') and self.stats_cards is not None:
            self.stats_cards.refresh(df)
        toast(f"{'⚠️ 已移入隔离区' if flag else '↩ 已取消隔离'} {len(ids)} 条", parent=self)

    def _repair_quarantine_consistency(self, silent=False):
        """修复隔离区一致性：把界面中标记隔离(_quarantined==1)但 SQLite 库内缺失的行补写进库。

        救回因旧版本写库未落盘、或数据重导后复合主键漂移造成的「内存孤儿」记录——
        否则重载数据后这些行因水合读不到库而消失，且永远进不了基于库的统计/失效复核。
        返回修复条数。
        """
        df = self.view_model.df
        if df is None or '_quarantined' not in df.columns or 'data_id' not in df.columns:
            return 0
        try:
            qids = get_quarantined_ids()
        except Exception as e:
            self.statusBar().showMessage(f"修复隔离区一致性失败: {e}")
            return 0
        mask = pd.to_numeric(df['_quarantined'], errors='coerce').fillna(0).astype(int) == 1
        orphan_ids = []
        for d in df.loc[mask, 'data_id']:
            s = str(d)
            if s in qids or s in ('', 'nan', 'None') or not pd.notna(d):
                continue
            orphan_ids.append(s)
        if not orphan_ids:
            if not silent:
                toast("隔离区一致性正常，无需修复", parent=self)
            return 0
        items = [(uid, "自动修复:界面标记隔离但库内缺失", "手动:自动修复") for uid in orphan_ids]
        try:
            add_quarantine_batch(items)
        except Exception as e:
            self.statusBar().showMessage(f"修复隔离区一致性写库失败: {e}")
            return 0
        msg = f"🔧 已修复隔离区一致性，补写 {len(orphan_ids)} 条到库"
        self.statusBar().showMessage(msg)
        if not silent:
            toast(msg, parent=self)
        return len(orphan_ids)

    def _auto_move_to_quarantine(self, manual=False):
        """按 config/auto_quarantine_config.json 配置把符合条件的记录移入隔离区。
        配置项：关键词 / 是否限定包材 / 是否排除替代料 / 是否要求负损。
        manual=True 来自工具栏手动按钮（弹窗反馈）；False 为分析完成后静默执行。"""
        cfg = load_auto_quarantine_config()
        if not cfg.get("enabled", True):
            if manual:
                QMessageBox.information(
                    self, "自动整理隔离区",
                    "自动隔离已关闭（配置 enabled=false），可在工具栏「⚙ 规则」中开启。")
            return
        df = self.view_model.df
        if df is None or 'data_id' not in df.columns:
            if manual:
                QMessageBox.information(self, "自动整理隔离区", "暂无数据，无法执行。")
            return
        matched = compute_auto_quarantine_ids(df, cfg)
        if not matched:
            if manual:
                QMessageBox.information(
                    self, "自动整理隔离区",
                    "没有符合规则的记录（%s）。" % build_all_summary(cfg))
            return
        # 仅对「尚未在隔离区」的新记录执行，避免重复打扰 / 覆盖用户手动取消隔离的行
        already = set()
        if '_quarantined' in df.columns:
            already = set(df.loc[df['_quarantined'] == 1, 'data_id'].astype(str))
        new_ids = set(matched) - already
        if not new_ids:
            if manual:
                QMessageBox.information(
                    self, "自动整理隔离区",
                    f"符合规则的 {len(matched)} 条均已在隔离区，无需重复移入。")
            return
        # 批量写入 SQLite：单事务 executemany，替代逐行 connect/commit/close（12K 行下卡死的根因之一）
        from core.quarantine_manager import add_quarantine_batch
        # basis 用自动规则 reason 文本（含「自动规则」标识），供失效复核重跑规则判定
        add_quarantine_batch([(uid, matched[uid], matched[uid]) for uid in new_ids])
        df.loc[df['data_id'].isin(new_ids), '_quarantined'] = 1
        self.view_model.df = df
        if self.source_model:
            self.source_model.setDataFrame(df)
            if hasattr(self, '_apply_column_visibility_by_name'):
                self._apply_column_visibility_by_name()
        self.stats_cards.refresh(df)
        msg = f"🧹 自动移入隔离区 {len(new_ids)} 条（{build_all_summary(cfg)}）"
        toast(msg, parent=self)
        if manual:
            QMessageBox.information(self, "自动整理隔离区", msg)

    # ------------------------------------------------------------------ #
    # 隔离区失效复核（监控旧数据改动：负损→补投相符 / 自动规则不再命中）
    # ------------------------------------------------------------------ #
    def _update_quarantine_badge(self, expired_list):
        """更新隔离区按钮角标：显示当前失效记录数。无失效则去掉角标。"""
        if not hasattr(self, 'action_btn_quarantine'):
            return
        n = len(expired_list) if expired_list else 0
        if n > 0:
            self.action_btn_quarantine.setText(f"⚠️ 隔离区 ({n}失效)")
            self.action_btn_quarantine.setToolTip(
                f"隔离区：{n} 条记录的入区原因已失效（如负损已补投相符），点击查看")
        else:
            self.action_btn_quarantine.setText("⚠️ 隔离区")
            self.action_btn_quarantine.setToolTip("隔离区：查看/管理疑难记录")

    def _scan_expired_quarantine_after_analysis(self):
        """分析完成后静默扫描隔离区失效。仅当「新增」失效记录出现时才弹窗告知。"""
        df = self.view_model.df
        if df is None or 'data_id' not in df.columns:
            return
        cfg = load_auto_quarantine_config()
        expired = scan_expired_quarantine(df, cfg)
        # 缓存当前失效集，供隔离区弹窗与角标复用
        self._expired_q_cache = {r['uid']: r for r in expired}
        self._update_quarantine_badge(expired)
        # 仅对新出现的失效 uid 弹窗（避免每次分析重复打扰）
        notified = getattr(self, '_expired_q_notified', set())
        new_uids = [r['uid'] for r in expired if r['uid'] not in notified]
        if new_uids:
            notified.update(new_uids)
            self._expired_q_notified = notified
            self._notify_expired_quarantine(new_uids, expired)

    def _notify_expired_quarantine(self, new_uids, expired_all):
        """弹窗告知失效记录（仅列出本次新增的）。"""
        df = self.view_model.df
        # 用 data_id → 行的索引，避免每条都全表扫描
        _idx = {}
        if df is not None and "data_id" in df.columns:
            try:
                _idx = dict(zip(df["data_id"].astype(str), range(len(df))))
            except Exception:
                pass

        detail_lines = []
        for r in expired_all:
            if r['uid'] not in new_uids:
                continue
            actual = r.get('actual')
            quota = r.get('quota')
            aq = ""
            if actual is not None and quota is not None:
                aq = f"（实际={actual:g}，定额={quota:g}）"
            # 用物料编码+物料名称替代裸 data_id（uid 格式：日期|流程订单|物料编码）
            label = r['uid']
            row_idx = _idx.get(r['uid'])
            if row_idx is not None:
                row = df.iloc[row_idx]
                mat_code = str(row.get("物料编码", "") or "").strip()
                mat_name = str(row.get("物料名称", "") or row.get("物料描述", "") or "").strip()
                if mat_code:
                    label = mat_code
                    if mat_name:
                        label = f"{mat_code}  {mat_name}"
            detail_lines.append(f"• {label}：{r['detail']}{aq}")
        if not detail_lines:
            return
        msg = ("以下隔离区记录的「入区原因已失效」，建议复核并移出隔离区：\n\n"
               + "\n".join(detail_lines)
               + "\n\n可在「⚠️ 隔离区」弹窗的「失效复核」页一键移出。")
        QMessageBox.information(self, "隔离区失效复核", msg)

    def _open_auto_quarantine_rule_dialog(self):
        """打开自动隔离规则配置对话框（独立入口，保留兼容）。保存成功后提示。"""
        from PySide6.QtWidgets import QDialog
        from gui_pyside6.dialogs.auto_quarantine_rule_dialog import AutoQuarantineRuleDialog
        dlg = AutoQuarantineRuleDialog(self)
        if dlg.exec_() == QDialog.DialogCode.Accepted:
            cfg = load_auto_quarantine_config()
            self.action_btn_auto_q.setToolTip("按规则自动移入隔离区：" + build_all_summary(cfg))
            toast("✅ 自动隔离规则已更新", parent=self)

    def _open_rule_center(self, open_tab=0):
        """打开「规则中心」：Tab1 自动隔离区 + Tab2 自动已读，两页共享保存。"""
        from PySide6.QtWidgets import QDialog
        from gui_pyside6.dialogs.auto_rules_center_dialog import AutoRulesCenterDialog
        dlg = AutoRulesCenterDialog(self, open_tab=open_tab)
        if dlg.exec_() == QDialog.DialogCode.Accepted:
            toast("✅ 规则已更新（自动隔离 + 自动已读）", parent=self)

    def _open_quarantine_dialog(self):
        """顶部按钮：打开隔离区弹窗"""
        df = self._get_master_df()  # 与未读弹窗同源，避免两边数对不上
        if df is None or '_quarantined' not in df.columns:
            QMessageBox.information(self, "隔离区", "暂无数据，无法打开隔离区")
            return
        qdf = df[df['_quarantined'] == 1].copy().reset_index(drop=True)
        if qdf.empty:
            QMessageBox.information(self, "隔离区", "隔离区当前为空")
            return
        dlg = QuarantineDialog(qdf, self, self)
        dlg.exec_()

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
        for label, keys in [("工厂", ["工厂", "工厂名称"]), ("车间", ["车间"]), ("订单日期", ["订单日期"]), ("流程订单", ["流程订单"]), ("物料编码", ["物料编码", "物料号"]), ("物料描述", ["物料描述", "物料名称"]), ("组件物料类型", ["组件物料类型"]), ("组件物料类型描述", ["组件物料类型描述"])]:
            fl1.addRow(f"{label}：", _mk_label(_val(*keys)))
        layout.addWidget(gb1)
        gb2 = QGroupBox("偏差数据")
        fl2 = QFormLayout(gb2)
        for label, keys in [("定额用量", ["定额"]), ("实际用量", ["实际"]), ("偏差数量", ["偏差数量"]), ("偏差率", ["偏差率", "偏差率(%)"]), ("偏差金额", ["偏差金额"]), ("总偏差金额(含税)", ["总偏差金额(含税)", "偏差金额"]), ("审核结果", ["审核结果", "audit_result"])]:
            val = _val(*keys)
            display = str(val)
            if "偏差率" in label and val:
                try:
                    display = f"{float(val):.2f}%"
                except Exception as e:
                    logging.warning("偏差率格式转换失败: %s", e)
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
        # 用真实时间戳差值，比每秒累加更准，也不受 UI 阻塞影响
        elapsed = int(time.perf_counter() - getattr(self, "_analysis_start_ts", 0))
        if elapsed != self._countdown_seconds:
            self._countdown_seconds = elapsed
        m, s = divmod(self._countdown_seconds, 60)
        self.timer_lbl.setText(f"⏱ {m:02d}:{s:02d}")

    def _stop_countdown(self):
        if hasattr(self, "_countdown_timer") and self._countdown_timer is not None:
            try:
                self._countdown_timer.stop()
            except Exception:
                pass

    def _format_elapsed(self):
        elapsed = int(time.perf_counter() - getattr(self, "_analysis_start_ts", 0))
        m, s = divmod(elapsed, 60)
        return f"{m:02d}:{s:02d}"

    def _generate_ppt_report(self):
        """生成 PPT 偏差分析报告（后台线程，完成后弹窗，界面不冻结）。"""
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "请先完成分析，暂无数据可生成 PPT")
            return
        default_name = f"ZPP011偏差分析_{datetime.now():%Y%m%d_%H%M}.pptx"
        default_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'ZPP011分析报告')
        os.makedirs(default_dir, exist_ok=True)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "生成 PPT 报告", os.path.join(default_dir, default_name),
            "PPT files (*.pptx)",
        )
        if not save_path:
            return
        if not save_path.lower().endswith('.pptx'):
            save_path += '.pptx'
        # PPT 生成较慢且在后台线程落盘，先确认目标文件没被 PowerPoint 占着
        from gui_pyside6.save_guard import precheck_save_path
        save_path = precheck_save_path(self, save_path, what="PPT 报告")
        if not save_path:
            self.log("PPT 生成已取消（目标文件被占用）", "warning")
            return

        # 进度条（非模态，不锁界面；PPT 生成本身不可中断，故不提供取消按钮）
        self._ppt_progress = QProgressDialog("正在生成 PPT 报告...", None, 0, 100, self)
        self._ppt_progress.setWindowTitle("生成中")
        self._ppt_progress.setWindowModality(Qt.NonModal)
        self._ppt_progress.setMinimumDuration(0)
        self._ppt_progress.setCancelButton(None)
        self._ppt_progress.show()

        src_name = None
        ap = getattr(self, 'analysis_params', None)
        if ap and ap.get('output_path'):
            src_name = os.path.basename(ap['output_path'])
        self._ppt_worker = _PptReportWorker(
            self.view_model.df.copy(), save_path, src_name)
        self._ppt_worker.progress.connect(
            lambda p, s: (self._ppt_progress.setValue(p), self._ppt_progress.setLabelText(s))
        )
        self._ppt_worker._log.connect(lambda m, lvl: self.log(m, lvl))
        self._ppt_worker.finished_ok.connect(self._on_ppt_done)
        self._ppt_worker.failed.connect(self._on_ppt_fail)
        self._ppt_worker.start()

    def _on_ppt_done(self, path):
        if hasattr(self, '_ppt_progress'):
            self._ppt_progress.setValue(100)
            self._ppt_progress.close()
        if QMessageBox.question(
            self, "生成成功",
            f"PPT 报告已生成：\n{path}\n\n是否立即打开？"
        ) == QMessageBox.Yes:
            os.startfile(path)
        self.log(f"已生成 PPT 报告：{path}", "info")

    def _on_ppt_fail(self, err):
        if hasattr(self, '_ppt_progress'):
            self._ppt_progress.close()
        QMessageBox.critical(self, "错误", f"生成 PPT 失败：{err}")
        self.log(f"生成 PPT 失败：{err}", "error")

    def _resolve_smart_ppt_excel(self):
        """智能PPT 取数：优先用最近分析生成的完整报告缓存；没有则返回 None（由控制器弹框手选）。"""
        cp = getattr(self, '_full_analysis_cache_path', None)
        if cp and os.path.exists(cp):
            return cp
        ap = getattr(self, 'analysis_output_path', None)
        if ap and os.path.exists(ap):
            return ap
        return None

    def _generate_smart_ppt_simple(self):
        """智能PPT(试用) — 简明版。底层 advanced_ppt_generator_v2，需完整分析 Excel。"""
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "请先完成分析，暂无数据可生成 PPT")
            return
        excel_path = self._resolve_smart_ppt_excel()
        self.export_controller.generate_simple_ppt(
            self.view_model.df, excel_path, None, self, log_cb=self.log)

    def _generate_smart_ppt_pro(self):
        """智能PPT(试用) — 专业版(20+页)。底层 advanced_ppt_generator_v2，需完整分析 Excel。"""
        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "请先完成分析，暂无数据可生成 PPT")
            return
        excel_path = self._resolve_smart_ppt_excel()
        self.export_controller.generate_advanced_report(
            self.view_model.df, excel_path, None, self, log_cb=self.log)

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
        desc_label = QLabel("功能：偏差分析 · AI审核 · 批量操作")
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

    def _toggle_left_panel(self):
        """切换左侧栏（文件选择 / 替代料配对 / 数据预览）的显示与隐藏"""
        if self.left_panel.isVisible():
            self.left_panel.setVisible(False)
            prev_sizes = self.body_splitter.sizes()
            # 将左侧栏宽度让给右侧表格区域
            self.body_splitter.setSizes([0, prev_sizes[1], prev_sizes[2] + prev_sizes[0]])
            self.action_btn_left_panel.setText("☰ 显示左侧栏")
            self.action_btn_left_panel.setChecked(False)
        else:
            self.left_panel.setVisible(True)
            prev_sizes = self.body_splitter.sizes()
            # left_panel | filter_panel | table_area，左侧栏恢复约 360px
            self.body_splitter.setSizes([360, prev_sizes[1], max(prev_sizes[2] - 360, 200)])
            self.action_btn_left_panel.setText("☰ 隐藏左侧栏")
            self.action_btn_left_panel.setChecked(True)

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
            # 展开时给筛选面板合适宽度（360px），与 FilterPanel 自身最大宽度一致
            self.filter_panel.setFixedWidth(440)
            prev_sizes = self.body_splitter.sizes()
            # left_panel | filter_panel | table_area
            self.body_splitter.setSizes([prev_sizes[0], 440, prev_sizes[2]])
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
        # v42.26: 补齐完整报告 / PPT 生成 / 文件读取三个后台线程的收尾。
        # 此前关窗时它们若仍在跑，主窗口先析构、线程回调再触发，可能崩溃。
        # 一律只 quit + wait(3000)，超时就放行，不用 terminate 强杀（同 v42.23 口径）。
        for _attr in ("_full_report_worker", "_ppt_worker", "_file_worker"):
            _w = getattr(self, _attr, None)
            if _w is None:
                continue
            try:
                if _w.isRunning():
                    # 支持协作式取消的 worker（如完整报告）先置取消标志，
                    # 让它在下一个检查点自行退出，比硬等 3 秒快得多
                    if hasattr(_w, "request_cancel"):
                        _w.request_cancel()
                    _w.quit()
                    _w.wait(3000)
                else:
                    _w.wait(3000)
            except RuntimeError:
                # 底层 C++ 对象已被 deleteLater 回收，忽略即可
                pass
            setattr(self, _attr, None)
        # v42.91: 关闭前 flush 隔离区一致性——把界面标记隔离但库内缺失的行补写库，
        # 杜绝「内存孤儿」在重载数据后消失。
        try:
            self._repair_quarantine_consistency(silent=True)
        except Exception:
            pass
        event.accept()


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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    sys.exit(app.exec())
