# -*- coding: utf-8 -*-
"""
ZPP011 主窗口 (PySide6 迁移版)
布局：标题栏 + 操作栏 + 侧栏 + 数据表格 + 日志面板
暗色主题 v43.0 | 裴哥 2026-06-23
"""

import os
import time
import json
from datetime import datetime
import pandas as pd
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QHeaderView, QDialog, QDialogButtonBox, QSplitter,
    QComboBox, QAbstractItemView, QMessageBox, QTableWidgetItem, QTableWidget,
    QMenu, QProgressDialog, QInputDialog,
    QToolButton,
    QTreeWidget, QTreeWidgetItem,      # v43.165 半成品分类树
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QTimer, QItemSelection, QItemSelectionModel, QModelIndex
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
from gui_pyside6.workers.report_workers import (
    _FullReportWorker, _PptReportWorker, _FileReadWorker,
)
from gui_pyside6.widgets.filter_panel import FilterPanel
from gui_pyside6.widgets.stats_cards import StatsCardsWidget
from gui_pyside6.widgets.unread_summary_popup import UnreadSummaryPopup
from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader
from gui_pyside6.dialogs.unit_summary_dialog import UnitSummaryDialog
from gui_pyside6.dialogs.alert_dialog import AlertDialog
from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog
from gui_pyside6.dialogs.neg_loss_dashboard_dialog import NegLossDashboardDialog
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog

from gui_pyside6.dialogs.quarantine_dialog import QuarantineDialog
from gui_pyside6.dialogs.pos_loss_dashboard_dialog import PosLossDashboardDialog
from gui_pyside6.dialogs.data_stability_dialog import DataStabilityDialog
from gui_pyside6.dialogs.quarantine_review_dialog import QuarantineReviewDialog
from gui_pyside6.dialogs.alt_chain_dialog import AltChainDialog
from gui_pyside6.dialogs.material_profile_dialog import MaterialProfileDialog, normalize_text
from core.auto_quarantine import (
    build_all_summary,
    load_auto_quarantine_config,
)
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
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
from core.read_status import record_deviation_change, upsert_material_names, get_material_names
from gui_pyside6.services.data_service import DataService
from utils.version_history import VERSION_HISTORY, APP_NAME, AUTHOR

from gui_pyside6.controllers.analysis_controller import AnalysisController
from gui_pyside6.controllers.audit_controller import AuditController
from gui_pyside6.controllers.export_controller import ExportController
from gui_pyside6.controllers.alt_controller import AltController
from gui_pyside6.controllers.column_controller import ColumnController
from gui_pyside6.controllers.filter_preset_controller import FilterPresetController
from gui_pyside6.controllers.dashboard_controller import DashboardController
from gui_pyside6.controllers.semi_category_controller import SemiCategoryController
from gui_pyside6.controllers.interaction_controller import InteractionController
from gui_pyside6.controllers.quarantine_manager_controller import QuarantineManagerController
from gui_pyside6.controllers.uisettings_controller import UISettingsController
from gui_pyside6.controllers.ppt_controller import PptController
from gui_pyside6.controllers.file_monitor_controller import FileMonitorController


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
        """运行日志输出到状态栏，便于调试"""
        try:
            if self.statusBar():
                self.statusBar().showMessage(f"{msg} [{level}]", 3000)
        except Exception:
            pass


class _FullCacheWorker(QThread):
    """完整报告缓存生成线程。

    ARC-003 第二刀（v43.194）：此前内联定义在 _on_analysis_finished_ui 方法体内，
    每次分析重建类对象、线程生命周期不受模块管理；现提升到模块级。
    v43.198：补协作式取消（request_cancel/_cancel_check，范式同 _FullReportWorker）。
    此前 run() 两分支都不传 cancel_check、_cancel_analysis/closeEvent 也不碰它，
    点「取消」停不下完整报告缓存生成；现主线程置位后由下一分析检查点自行退出。
    """
    progress = Signal(int, str)  # 缓存阶段进度 (percent, step_name)，跨线程排队到主线程

    def __init__(self, input_file, alt_pairs, start_date, end_date, material_search, output_path, dyn_thresh=None):
        super().__init__()
        self.input_file = os.path.normpath(input_file)
        self.alt_pairs = alt_pairs
        self.start_date = start_date
        self.end_date = end_date
        self.material_search = material_search
        self.output_path = output_path
        self.dyn_thresh = dyn_thresh
        self._cancel = False

    def request_cancel(self):
        """主线程调用：置取消标志，worker 在下一检查点自行退出（协作式，不硬杀）。"""
        self._cancel = True

    def _cancel_check(self, *args):
        return self._cancel

    def run(self):
        import analysis.analyzer as _az
        from analysis.analyzer import export_full_report_from_intermediates
        from core.config_manager import ConfigManager
        _cfg = ConfigManager()

        def _cb(step_idx, step_name, percent):
            self.progress.emit(int(percent), str(step_name))
        try:
            _li = _az.LATEST_INTERMEDIATES
            if _li is not None:
                # 复用 worker 已算好的 Sheet1~5 中间结果，只生成 Sheet6~10 + 保存，避免重算
                export_full_report_from_intermediates(
                    _li, output_path=self.output_path,
                    progress_callback=_cb, cancel_check=self._cancel_check)
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
                    progress_callback=_cb,
                    cancel_check=self._cancel_check,
                )
        except KeyboardInterrupt:
            # 协作式取消：analyzer 的 check_cancel() 抛 KeyboardInterrupt，
            # 它是 BaseException 子类、except Exception 兜不住，须单独捕获。
            # 优雅返回后 finished 信号照常触发 _on_cache_done 收口（_heavy_busy
            # 清零 + 计时器收口）；缓存文件不会落盘，导出完整报告时自然回退
            # 到重新生成，不会留下半成品缓存。
            print("[_FullCacheWorker] 完整报告缓存生成已取消")
        except Exception:
            import traceback as _tb
            _tb.print_exc()


def _open_file(filepath):
    """跨平台打开文件（唯一实现在 gui_pyside6/utils/file_launcher.py，v43.257 收口 GUI-001）"""
    from gui_pyside6.utils.file_launcher import open_path

    return open_path(filepath)


class MainWindow(QMainWindow):
    """ZPP011 主窗口 — 暗色主题"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ZPP011 生产偏差分析器 {VERSION_HISTORY[0]['version']} (PySide6)")

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
        # 列头筛选模式（Excel式）：开启后点列头=弹取值勾选浮层，Ctrl+点列头仍排序
        self._col_filter_mode = False
        self._filtered_col_set = set()  # 当前已设取值过滤的列号集合（供表头画漏斗标，与 SortBadgeHeader 对齐）
        self._col_filter_popup = None   # 当前打开的列头筛选浮层（避免被 GC）
        # Ctrl 状态由键盘事件流实时跟踪（最可靠），用于多级排序判定。
        # 原因：Qt 在 mousePressEvent/sectionClicked 时机读 Ctrl 修饰符极不可靠
        # （实测真实环境 event.modifiers() 常读不到 Ctrl，导致 Ctrl+多级排序永不生效）。
        # 故改为从 KeyPress/KeyRelease 自行维护 _ctrl_down，彻底绕开该坑。
        self._ctrl_down = False
        self._countdown_seconds = 0
        self._countdown_timer = None
        self._analysis_start_ts = 0.0
        # 按"列名"记录需要隐藏的列（避免 setDataFrame 重排列后索引错位导致列丢失）
        self._hidden_column_names = {
            '_post_audit_changed', 'data_id', 'fingerprint', '_quarantined',
        }  # 内部技术列默认隐藏（用户无需看到）

        # 控制器
        # ARC-003 第五刀：半成品分类管理职责已切出到 SemiCategoryController。
        # 必须先于 self._semi_categories = self._load_semi_categories() 装配——
        # 该初始化会经薄壳转发到本 controller（见下方半成品分类列表初始化）。
        self.semi_category_controller = SemiCategoryController(self)

        # 半成品分类列表（从 config/semi_user_categories.json 加载，运行时可追加）
        # 必须在 SemiCategoryController 装配之后：加载动作经薄壳转发到 controller。
        self._semi_categories = self._load_semi_categories()
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

        # 状态栏常驻「列头筛选提示」：显示当前已设取值过滤的列名（N 列）
        # 修复（2026-10-01）：列头筛选后原本只有表头小漏斗标，无法判断哪些列被筛过；
        # 现常驻显示已筛选列名，_update_col_filter_hint() 在筛选增减/重置/重新分析时同步刷新。
        self._col_filter_hint_label = QLabel("🔽 列头筛选：0 列")
        self._col_filter_hint_label.setObjectName("colFilterHintLabel")
        self._col_filter_hint_label.setToolTip("当前已设列头取值过滤的列（橙色三角标记）；点 🔽 列头筛选 按钮后点任意列头弹取值勾选浮层")
        self._col_filter_hint_label.setStyleSheet(
            "QLabel#colFilterHintLabel{padding:2px 10px;font-weight:bold;color:#8a5a00;"
            "border-left:1px solid #b8c4d0;}"
        )
        self._col_filter_hint_label.show()  # 无筛选时显示「0 列」，让用户知道哪些列被筛过
        # v43.143：提示标签改为「可点即清除」入口。此前它只是纯 QLabel，用户想取消筛选
        # 只能开浮层重新勾选一遍，且关掉筛选模式也不清筛选（实测），观感=「无法取消」。
        # 现在左键/右键点它都弹菜单：逐列清除 + 清除全部。
        self._col_filter_hint_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self._col_filter_hint_label.customContextMenuRequested.connect(
            lambda pos: self._show_col_filter_clear_menu(self._col_filter_hint_label, pos))
        self._col_filter_hint_label.setToolTip(
            "当前已设列头取值过滤的列（表头橙色三角标记）。\n"
            "点此标签 → 菜单里可「清除此列」或「清除全部列头筛选」。")
        self.statusBar().addPermanentWidget(self._col_filter_hint_label)

        self.export_controller = ExportController(self)
        self.alt_controller = AltController(self)
        # ARC-003 拆分：列过滤/排序/宽度职责已切出到 ColumnController（纯 UI 逻辑）
        self.column_controller = ColumnController(self)
        # ARC-003 第三刀：筛选预设职责已切出到 FilterPresetController
        self.filter_preset_controller = FilterPresetController(self)
        # ARC-003 第四刀：11 个看板/弹窗展示职责已切出到 DashboardController
        self.dashboard_controller = DashboardController(self)
        # ARC-003 第六刀：交互职责（定位/选中/复制）已切出到 InteractionController
        self.interaction_controller = InteractionController(self)
        # ARC-003 第七刀：隔离区管理职责（自动已读/读写/失效复核/自动移入）已切出到 QuarantineManagerController
        self.quarantine_manager_controller = QuarantineManagerController(self)
        # ARC-003 第八刀：UI 状态更新职责已切出到 UISettingsController
        self.ui_settings_controller = UISettingsController(self)
        # ARC-003 第九刀：PPT 报告职责已切出到 PptController
        self.ppt_controller = PptController(self)
        # ARC-003 第十刀：文件监控职责已切出到 FileMonitorController
        self.file_monitor_controller = FileMonitorController(self)
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
        self.title_bar = TitleBarWidget(VERSION_HISTORY[0]['version'], self)
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

        # 组装布局（必须在 show 之前，且必须先于 _setup_connections，因为按钮由 LayoutComposer 创建）
        self._assemble_layout()

        # 连接按钮信号（必须在布局组装之后，因为按钮是由布局组件创建的）
        self._setup_connections()
        self._setup_shortcuts()

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
        # 使用 LayoutComposer 进行纯 UI 组装，逻辑下沉
        from gui_pyside6.layout_composer import LayoutComposer
        composer = LayoutComposer()
        central = composer.assemble(self)
        self.setCentralWidget(central)


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
        self.filter_panel.reset_filters_requested.connect(self._on_filter_reset_requested)
        # 筛选预设（实现预留的 filter_history 配置）+ 看板联动横幅
        self.filter_panel.save_preset_requested.connect(self._prompt_save_preset)
        self.filter_panel.apply_preset_requested.connect(self._apply_filter_preset)
        self.filter_panel.apply_last_requested.connect(lambda: self._apply_filter_preset("___last___"))
        self.filter_panel.delete_preset_requested.connect(self._delete_filter_preset)
        self.main_table.link_banner_cleared.connect(self._clear_link_drilldown)
        self._link_snapshot = None  # 联动钻取前的筛选快照（清除时恢复）
        self._refresh_filter_preset_menu()

        # 分析按钮点击连接（ARC-003 第八刀，必须创建）
        self.action_btn_analyze.clicked.connect(self._start_analysis)

        # 工具栏信号连接（解决按钮失效问题）
        self.action_btn_left_panel.clicked.connect(self._toggle_left_panel)
        self.action_btn_filter.clicked.connect(self._toggle_filter_panel)
        self.action_btn_col_filter.clicked.connect(self._toggle_col_filter_mode)
        self.action_btn_boards.clicked.connect(self._show_dashboard)
        self.action_btn_export.clicked.connect(self._on_export_full_excel)
        self.action_btn_maint.clicked.connect(self._open_auto_quarantine_rule_dialog)
        self.action_btn_toggle_stats.clicked.connect(self._toggle_stats_from_toolbar)
        self.action_btn_toggle_progress.clicked.connect(self._toggle_progress_from_toolbar)
        self.action_btn_unread_summary.clicked.connect(self._show_unread_summary)
        self.action_btn_auto_q.clicked.connect(self._auto_move_to_quarantine)



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
        # v43.152：原代码 self._audit_changes_dialog_open = False 只在 dlg.exec()
        # 正常返回后执行，没有 try/finally 保护。建 UI 或 exec 中途抛一次异常，
        # 该标志就永久卡在 True，此后所有点击都在开头的防重入判断处静默 return，
        # 表现为「变动提醒点不动」且零线索。此处用 try/finally 保证必重置。
        self._audit_changes_dialog_open = True
        try:
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
                    # 兼容 4 段（工厂|日期|流程订单|物料编码）和 3 段（日期|流程订单|物料编码）格式
                    if len(parts) == 4:
                        date, order, mat = parts[1], parts[2], parts[3]
                    elif len(parts) >= 3:
                        date, order, mat = parts[0], parts[1], parts[2]
                    else:
                        date, order, mat = '', '', ''
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
                    # v43.257：内联平台分发收敛到 _open_file（第五份重复实现）
                    _open_file(path)
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
        finally:
            self._audit_changes_dialog_open = False


    def _select_source_row(self, src_row):
        """选中主表某一行（源行位置 → 代理行映射），供各定位方法复用。"""
        return self.interaction_controller._select_source_row(src_row)

    def _locate_row_by_index(self, row_index):
        """按 DataFrame index 标签定位主表行（兼容旧调用方）"""
        return self.interaction_controller._locate_row_by_index(row_index)

    def _locate_row_by_excel_no(self, excel_row):
        """按「原表行号」列的取值定位主表行。

        与 _locate_row_by_index 的区别：后者按 DataFrame 索引标签匹配，而主表索引是
        RangeIndex，拿 Excel 行号去匹配会失配或错位（行号 5 → 第 6 行）；这里按列值
        精确匹配，是看板双击定位最可靠的一条路径。
        """
        return self.interaction_controller._locate_row_by_excel_no(excel_row)

    def _locate_row_in_main_table(self, data_id, silent=False):
        """变动提醒弹窗双击某行时，定位并选中主表对应行（经 proxy_model 映射）"""
        return self.interaction_controller._locate_row_in_main_table(data_id, silent)

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
        # 发起分析前记录当前筛选为「上次使用」预设（面板在分析完成后会重置）
        self._capture_last_used_filter()
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

        # v43.180：源文件被外部改过 → 先丢弃陈旧缓存，再**后台重新读取**，
        #   等读完再续跑分析（不能直接把缓存传 None 让analyzer 前台读文件，那会
        #   卡住主线程 20~30秒，表现为「点了分析没反应」）。
        if self._drop_stale_input_cache():
            if self._heavy_busy:
                QMessageBox.information(self, "提示", "分析/报告生成进行中，请稍候")
                return
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.setText("📂 源文件已修改，正在重新读取…")
            self._pending_analysis_after_reread = True
            self._file_worker = _FileReadWorker(self.current_input_file)
            self._file_worker.loaded.connect(self._on_reread_then_analyze)
            self._file_worker.failed.connect(self._on_file_failed)
            self._file_worker.start()
            return

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

    def _on_reread_then_analyze(self, df, file_path):
        """v43.180：源文件重读完成后，自动续跑刚才挂起的那次分析。"""
        self._on_file_loaded(df, file_path)          # 复用原有装载逻辑（会刷新缓存与预览）
        if getattr(self, '_pending_analysis_after_reread', False):
            self._pending_analysis_after_reread = False
            QTimer.singleShot(0, self._start_analysis)  # 等事件循环转一圈再跑，避开信号回调栈

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
        # 进度必须单调不减：低值通知（过滤/搜索类 percent=0）或任何乱序发射都
        # 不允许把进度条与 12 格步骤图标打回去（源端已做区间映射，这里是兜底防线）。
        current = self.progress_bar.value()
        if percent < current:
            # 通知类发射：只更新标签提示，进度条与图标停在当前位置
            self._current_step = step_name
            self.progress_label.setText(f"{step_name}  （进度 {current}%）")
            return
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
        # 计时器不停：完整报告缓存（Sheet6~10 + Excel，可能数分钟）还在后台跑，
        # 在这里停掉就是曾经的「后面的时间卡住」；改由 _finish_cache_phase 收口
        # 状态栏「分析时间」：标触发方式 + 完成时刻（Finish 时刻）
        self._update_analysis_time_label(_analysis_mode)
        self.progress_bar.setValue(100)
        self.main_table.complete_step_icons()
        # 分析完成 6 秒后自动收起进度面板（表格空间还给数据）；工具栏「进度」按钮可随时展开
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
            # 同步清掉列头筛选漏斗标（取值过滤已在 clearFilters 内清空，这里清列号集合并重绘）
            if self._filtered_col_set:
                self._filtered_col_set.clear()
                if hasattr(self, "_sort_header"):
                    # Qt6 QHeaderView 自绘画在表头本体上，必须 header.update() 才能重画
                    # （viewport().update() 只刷内部 viewport，漏斗/角标不会重画）
                    self._sort_header.update()
            self._update_col_filter_hint()
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
            # 新增：隔离区已读对账（仅管理隔离区记录的已读/未读，与规则中心互斥）
            self._reconcile_quarantine_read_status(processed_df)
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
                self._cache_worker.finished.connect(self._finish_cache_phase)
                self.progress_label.setText("主分析完成 · 完整报告缓存生成中…")
            else:
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
                    self._finish_cache_phase()  # 计时器收口 + 6s 后自动收起进度面板
                self._cache_worker.finished.connect(_on_cache_done)
                self._cache_worker.progress.connect(self._on_cache_progress_ui)
                self._cache_worker.start()
                self.progress_label.setText("主分析完成 · 完整报告缓存生成中…")

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
            self._stop_countdown()  # 兜底：加载失败也停表，避免计时器空转
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
        self.ui_settings_controller.toggle_stats_from_toolbar(not self.stats_cards._user_hidden)

    def _toggle_progress_from_toolbar(self):
        self.ui_settings_controller.toggle_progress_from_toolbar(not self.main_table._progress_hidden)

    def _auto_collapse_progress_after_analysis(self):
        self.ui_settings_controller.auto_collapse_progress_after_analysis()

    def _on_cache_progress_ui(self, percent, step_name):
        """完整报告缓存阶段进度（worker 线程发射，跨线程排队到主线程）。

        只更新标签：进度条已停在 100%（主分析完成值），图标已全部点亮，
        计时器由 _countdown_timer 继续走（不再卡住）。
        """
        try:
            self.progress_label.setText(f"📦 完整报告缓存：{step_name}（{percent}%）")
        except RuntimeError:
            pass  # 窗口已销毁（worker 可能比窗口活得久）

    def _finish_cache_phase(self):
        """完整报告缓存结束（新生成或复用已有缓存）：计时器收口，6s 后自动收起进度面板。"""
        _w = getattr(self.analysis_controller, "worker", None)
        if _w is not None and _w.isRunning():
            return  # 新一轮分析进行中：它的计时器不能动
        self._stop_countdown()
        QTimer.singleShot(6000, self._auto_collapse_progress_after_analysis)
        try:
            self.statusBar().showMessage("完整报告缓存已生成（Sheet6~10 + Excel）", 4000)
        except RuntimeError:
            pass

    def _on_stats_visibility_changed(self, visible: bool):
        self.ui_settings_controller.on_stats_visibility_changed(visible)

    def _on_progress_visibility_changed(self, visible: bool):
        self.ui_settings_controller.on_progress_visibility_changed(visible)

    def _update_top_panel_visibility(self):
        self.ui_settings_controller.update_top_panel_visibility()

    def _auto_read_by_rules(self, df):
        """薄壳：自动已读规则中心（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._auto_read_by_rules(df)

    def _reconcile_quarantine_read_status(self, df):
        """薄壳：隔离区已读对账（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._reconcile_quarantine_read_status(df)

    def _update_read_counter(self):
        self.ui_settings_controller.update_read_counter()

    def _update_analysis_time_label(self, mode):
        self.ui_settings_controller.update_analysis_time_label(mode)

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
        """AI审核（仅本地分类）完成回调。

        AI建议功能已停用（2026-10-01）：只刷新「审核结果/备注来源」，
        并强制把可能残留的「AI建议」列清空/隐藏，避免 mock 文案继续显示。
        """
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        elapsed = self._format_elapsed()
        self.progress_label.setText(f"✅ 审核完成 ({elapsed})")
        toast(f"✅ 审核完成 ({elapsed})", "success", parent=self)

        total = len(updated_df)
        self.log(f"审核完成：共 {total} 条记录（AI建议功能已停用）", "info")

        # 预处理（恢复已读状态+审核结果）直接同步执行，DB 操作 ~0.2s 不卡
        try:
            updated_df = self.data_service.preprocess_audit_data(updated_df, self.view_model.df)
        except Exception:
            pass  # 降级，用原始 updated_df

        # 强制清理 AI建议列：有则清空，确保主表不再出现 mock/胡说八道文案
        if "AI建议" in updated_df.columns:
            updated_df["AI建议"] = ""

        self.source_model.setDataFrame(updated_df)
        self._apply_column_visibility_by_name()
        self.view_model.df = updated_df
        self.progress_bar.setVisible(False)
        self.progress_label.setText("就绪")
        QMessageBox.information(self, "完成", "审核已完成（AI建议已停用）")

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
            # 只保留关键列（含"工厂"以便 dialog 生成正确的 data_id 与主表匹配）
            required_cols = [c for c in [
                "工厂", "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
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

    def _update_all_summary(self):
        """恢复整体合计"""
        self._update_summary()

    def _on_selection_changed(self, selected, deselected):
        """选中变化时，显示选中合计"""
        return self.interaction_controller._on_selection_changed(selected, deselected)

    def _cancel_analysis(self):
        cancelled = False
        if self.analysis_controller.worker and self.analysis_controller.worker.isRunning():
            self.analysis_controller.cancel()
            cancelled = True
        if self.audit_controller.ai_worker and self.audit_controller.ai_worker.isRunning():
            self.audit_controller.cancel_ai_audit()
            cancelled = True
        if self._cache_worker is not None and self._cache_worker.isRunning():
            # v43.198：补上完整报告缓存生成线程的取消。此前这里只碰主分析与
            # AI 审核，_FullCacheWorker 没有任何取消入口，点「取消」后它仍算到底。
            self._cache_worker.request_cancel()
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

    @staticmethod
    def _file_mtime_signature(path):
        """取源文件的「修改时间 + 大小」作为变更指纹（v43.180）。

        用于判断 `_cached_input_df` 是否已过期：
        只看 mtime 不够——同一秒内改两次、或某些工具会重写 mtime 而内容变化，
        故叠加文件大小一起比。任一不同即视为「源文件已变」。
        读不到（文件被移动/删除/无权限）返回 None，调用方按「已变」处理（重读失败会报错，
        比静默用陈旧数据更安全）。
        """
        if not path:
            return None
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except (OSError, ValueError):
            return None

    def _drop_stale_input_cache(self):
        """源文件已被外部修改 → 丢弃内存缓存，返回 True（调用方需重新读盘）。

        没有这一步的话：用户改完 Excel 直接点「分析」，程序拿的还是选文件那一刻
        读进来的旧 DataFrame（`main_window.py:1113` 直接复用缓存、跳过文件 IO），
        于是「改了数据必须关软件重开」才生效 —— v43.180 修掉。
        """
        cached = getattr(self, '_cached_input_df', None)
        if cached is None:
            return False
        cur = self._file_mtime_signature(self.current_input_file)
        old = getattr(self, '_cached_input_mtime', None)
        if old is not None and cur is not None and cur == old:
            return False                      # 没变，沿用缓存（保留秒开优势）
        # 变了 / 指纹拿不到 → 缓存作废
        self._cached_input_df = None
        self._cached_input_mtime = None
        try:
            self.log("[分析] 源文件已修改，丢弃旧缓存并重新读取", "info")
        except Exception:
            pass
        return True

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
            # v43.180：连同源文件的修改时间/大小一起记下，供分析前比对
            #   （发现问题：改了源文件后点分析仍显示旧数据，必须关软件重开才生效 ——
            #    因为 _start_analysis 直接复用这份缓存、根本不读磁盘）。
            self._cached_input_mtime = self._file_mtime_signature(file_path)
            # v43.186：把源数据里的「编码→名称」沉淀进 audit.db 持久缓存，
            # 供数据稳定性看板 / 物料画像跨月份复用（deviation_history 三表均无名称列）。
            # 失败时静默降级（名称只是锦上添花，绝不阻断加载主流程）。
            try:
                self._persist_material_names(df)
            except Exception:
                pass
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.setText(self._format_preview_stats(df))
        except Exception as e:
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.setText(f"读取失败：{e}")
        finally:
            if self._file_worker is not None:
                self._file_worker.deleteLater()
                self._file_worker = None

    def _persist_material_names(self, df):
        """v43.186：从当前 DataFrame 抽「编码→名称」，沉淀进 audit.db 持久缓存。

        兼容两种列名：分析后的主表用「物料编码/物料名称」，原始 Data sheet
        用「组件物料号/组件物料描述」。`_on_file_loaded` 拿到的是原始 Data sheet，
        故两列都要探测。空值/脏值经 normalize_text 归一后再写入。
        """
        code_key = next((c for c in ('物料编码', '组件物料号', '物料号')
                         if c in df.columns), None)
        name_key = next((c for c in ('物料名称', '组件物料描述', '物料描述')
                         if c in df.columns), None)
        if not code_key or not name_key:
            return
        mapping = {}
        for code, nm in zip(df[code_key], df[name_key]):
            c = normalize_text(code)
            n = normalize_text(nm)
            if c and n:
                mapping[c] = n   # 后出现的覆盖先出现的，取到非空
        if mapping:
            upsert_material_names(mapping)

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

    # -----------------------------------------------------------
    # 半成品类目管理（持久化到 config/semi_user_categories.json）
    # JSON 格式: [{"name": "分类名", "factory": "工厂"}, ...]
    # 兼容旧格式: {"name":..., "col":..., "cond":..., "val":...}
    # -----------------------------------------------------------
    def _open_output_dir(self):
        dir_path = self.output_dir_edit.text()
        if not dir_path:
            dir_path = os.path.expanduser("~/Documents/ZPP011分析报告")
        if os.path.exists(dir_path):
            _open_file(dir_path)
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
        """薄壳：文件系统接受规则（ARC-003 第十刀切出到 FileMonitorController）。
"""
        return self.file_monitor_controller._is_monitor_accepted_file(fname)

    def _toggle_folder_monitor(self, checked):
        """薄壳：文件夹监控开关（ARC-003 第十刀切出到 FileMonitorController）。
"""
        return self.file_monitor_controller._toggle_folder_monitor(checked)

    def _seed_monitor_baseline(self):
        """薄壳：设置监控基线（ARC-003 第十刀切出到 FileMonitorController）。
"""
        return self.file_monitor_controller._seed_monitor_baseline()

    def _scan_monitor_dir(self):
        """薄壳：扫描监控目录（ARC-003 第十刀切出到 FileMonitorController）。
"""
        return self.file_monitor_controller._scan_monitor_dir()

    def _monitor_file_busy(self, fp):
        """薄壳：检测文件占用（ARC-003 第十刀切出到 FileMonitorController）。
"""
        return self.file_monitor_controller._monitor_file_busy(fp)

    def _monitor_try_load(self, fp, key, attempt=0):
        """薄壳：监控加载重试（ARC-003 第十刀切出到 FileMonitorController）。
"""
        return self.file_monitor_controller._monitor_try_load(fp, key, attempt)

    def _auto_load_from_monitor(self, fp):
        """薄壳：监控自动加载（ARC-003 第十刀切出到 FileMonitorController）。
"""
        return self.file_monitor_controller._auto_load_from_monitor(fp)


    # -----------------------------------------------------------
    # 替代料配对
    # -----------------------------------------------------------
    def _refresh_alt_view(self):
        self.alt_controller.refresh_view(self.alt_table, self.alt_count_label)

    def _on_alt_pairs_changed(self):
        self.alt_controller.on_pairs_changed(self)

    def _on_alt_rows_moved(self, parent, start, end, destination, row):
        self.alt_controller.on_rows_moved(self, parent, start, end, destination, row)

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
        # 使用 selectedIndexes() 而非 selectedRows()，兼容右键点击无显式选中的场景
        selected_rows = set()
        for idx in self.table_view.selectionModel().selectedIndexes():
            source_index = self.proxy_model.mapToSource(idx)
            selected_rows.add(source_index.row())
        # 若无显式选中行，则取右键点击位置对应的行
        if not selected_rows:
            return
        src_rows = sorted(selected_rows)
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
            # 兼容多种列名：优先中文列名，降级英文列名
            def get_col(*keys):
                for k in keys:
                    if k in df.columns:
                        return str(row.get(k, '') or '').strip()
                return ''
            factory = get_col('工厂', '工厂名称', 'plant', 'factory')
            # 工厂名转数字编码（兼容手动添加的 1101/1102 格式）
            if factory in ('云南达利-食品厂',):
                factory = '1101'
            elif factory in ('云南达利-饮料厂',):
                factory = '1102'
            code = get_col('物料编码', '物料号', 'code', '组件物料号')
            name = get_col('物料名称', '物料描述', 'name')
            return (factory, code, name)

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
        self.alt_controller.import_from_file(file_path, self)

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
        """弹出半成品分类放大窗口，支持双击筛选。

        历史坑：v43.222 重构把方法体从 MainWindow 迁出时漏了这条（薄壳指向
        不存在的 alt_controller.zoom_semi_table，left_panel 放大按钮一按就
        AttributeError）。v43.243 起把实现直接恢复在 MainWindow，不再转发。
        数据源用 _get_semi_category_list()（与左侧 semi_tree 同源，含
        name/factory/codes/code_count），避免重复实现分类提取逻辑。
        """
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
        )
        from PySide6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("半成品分类详情")
        dialog.resize(720, 480)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)

        tip_label = QLabel("双击任意行可筛选该分类。点击「关闭」退出。")
        tip_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(tip_label)

        # 表格：列 = [工厂 · 分类 / 物料数 / 示例物料]
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["工厂 · 分类", "物料数", "示例物料（前 3 个编码）"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

        # 数据源：与左侧 semi_tree 同源（_get_semi_category_list），零重复逻辑
        categories = self._get_semi_category_list()
        table.setRowCount(len(categories))
        for r, cat in enumerate(categories):
            label = f"{cat.get('factory', '')} · {cat.get('name', '')}".strip(' ·')
            codes = cat.get('codes') or []
            name_item = QTableWidgetItem(label)
            name_item.setData(Qt.UserRole, cat.get('name', ''))
            table.setItem(r, 0, name_item)
            table.setItem(r, 1, QTableWidgetItem(str(cat.get('code_count', len(codes)))))
            example = '、'.join(codes[:3]) + (' …' if len(codes) > 3 else '')
            ex_item = QTableWidgetItem(example)
            ex_item.setToolTip('、'.join(codes))
            table.setItem(r, 2, ex_item)

        layout.addWidget(table)

        # 双击筛选（_filter_semi_materials 按"分类名"匹配，不是"工厂·分类"全标签）
        def _on_double_click(row_idx, _col):
            item = table.item(row_idx, 0)
            if item:
                cat_name = item.data(Qt.UserRole)
                self._filter_semi_materials(cat_name)
        table.doubleClicked.connect(
            lambda idx: _on_double_click(idx.row(), idx.column()))

        # 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _sort_alt_pairs(self):
        self.alt_controller.sort_pairs()
        QMessageBox.information(self, "排序完成", "已按物料A编码升序排列")

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
        # 自定义表头：在已排序列角上叠加 1/2/3 层级角标 + 升降箭头，让 Ctrl+多级排序可见
        self._sort_header = SortBadgeHeader(Qt.Horizontal, self.table_view)
        self._sort_header.set_sort_columns_getter(lambda: self.sort_columns)
        self._sort_header.set_filtered_columns_getter(lambda: self._filtered_col_set)
        # 点击已筛选列左侧漏斗图标 → 直接打开该列筛选浮层（无需先开启「列头筛选」模式）
        self._sort_header.set_funnel_clicked(
            lambda col: QTimer.singleShot(0, lambda c=col: self._open_column_filter(c)))
        self.table_view.setHorizontalHeader(self._sort_header)
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
        # 关键修复：setSortingEnabled(False) 会把表头 sectionsClickable 一并关成 False，
        # 导致列头点击不再发 sectionClicked 信号、排序引擎(_on_header_clicked→_apply_multi_sort)
        # 完全不被触发（"排序彻底失效"根因）。重新打开可点击：原生自动排序仍由
        # setSortingEnabled(False) 关闭，不会双排序，排序只走我们自己的 handler。
        self.table_view.horizontalHeader().setSectionsClickable(True)
        # 排序状态完全自绘（SortBadgeHeader.paintEvent 画「层级数字+▲▼」角标），不依赖原生
        # sortIndicator（setSortingEnabled(False) 下原生箭头不可靠）。原生自动排序仍由
        # setSortingEnabled(False) 关闭，不会双排序，排序只走我们自己的 handler。
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
            # v43.250：与主表橙色高亮 / 偏差率预警看板 / 颜色筛选同口径，排除
            # |偏差率| 恰为 100% 的 SAP 除零钳位假值（定额=0 恒 +100.0%）；
            # -100.0%（实际=0 且 定额>0）已由 ~no_input 排除。
            alert_mask = (rates.abs() >= 10) & ((rates - 100.0).abs() >= 1e-6) & (~no_input)
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
        """统计卡片点击：隔离区/偏差率预警开对应窗口，其余切换筛选

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
            # v43.151：原先只 set_color_filter('quarantine') 勾主表颜色标记、不开窗口，
            # 用户点卡片看不到任何「跳转」，且隔离区的失效复核/按原因筛选/导出/取消隔离
            # 等能力全在窗口里用不到。改为与顶部「⚠️ 隔离区」菜单一致：直接开窗口。
            self._open_quarantine_dialog()
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
        """运行日志面板已移除（v43.235 前为空操作 pass）。

        历史坑：空实现导致「双击定位主表」等自诊断路径完全静默——用户侧看起来
        「功能失效」却无任何提示，排查无从下手。v43.239 起回显到状态栏 + 落盘
        logs/（复用 core.logger.get_logger，避免重复造轮子 / 重复加 handler）。

        行为约定：
          - 状态栏瞬时提示 5s（level=info/debug 也显示，便于现场看）；
          - 文件写 logs/YYYY-MM-DD.log（get_logger 已配 TimedRotatingFileHandler，
            按天滚动保留 30 天）；
          - 任何一步失败都不抛——日志接口本身绝不能成为新的故障源。
        """
        # 1) 状态栏回显（最直观的现场反馈）
        try:
            self.statusBar().showMessage(f"[{level}] {msg}", 5000)
        except Exception:
            pass
        # 2) 落盘（复用项目统一 logger，自动去重 handler）
        try:
            from core.logger import get_logger
            get_logger("ZPP011").info("%s", f"[{level}] {msg}")
        except Exception:
            pass

    # -----------------------------------------------------------
    # 数据相关
    # -----------------------------------------------------------
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

    def _on_filter_reset_requested(self):
        """重置筛选：面板已归位，这里同步清理 proxy 残留的列头取值过滤。

        修复（2026-10-01）：侧栏「重置筛选」原先只复位面板控件，没有清理 proxy_model
        里的列头取值过滤残留（_value_filters / _filters），导致「点重置后表格仍空白、
        必须重新分析才恢复」。
        性能（2026-10-02）：面板 reset_filters() 在发本信号前已经 _emit_filter() 应用过
        重置后的 _custom_filters（一遍完整重筛），故这里只清「列头取值/顶部行」残留
        （clearHeaderFilters，无残留时零重筛），不再 clearFilters() + 重复 setCustomFilters
        多打两遍 17k 行全表。
        """
        try:
            if self.proxy_model is not None:
                self.proxy_model.clearHeaderFilters()
            if getattr(self, "_filtered_col_set", None):
                self._filtered_col_set.clear()
                if getattr(self, "_sort_header", None) is not None:
                    # 同分析完成路径：自绘画在表头本体，必须 header.update()
                    self._sort_header.update()
            self._link_snapshot = None  # 清除联动钻取快照（重置后不应再保留钻取）
            self._update_col_filter_hint()
        except Exception as e:
            self.log(f"[重置筛选] 清理 proxy 残留失败: {e}", "warning")

    # ------------------------------------------------------------------ #
    # 看板 → 主表 联动钻取（可撤销）
    # ------------------------------------------------------------------ #
    def _apply_link_drilldown(self, record, source_label):
        """看板行定位后：主表叠加「流程订单 + 物料 + 工厂上下文」筛选钻取到该条，"""
        """并显示联动横幅；清除按钮恢复联动前快照。联动失败不影响定位本身。"""
        if self.proxy_model is None or record is None:
            return
        try:
            order = record.get("流程订单")
        except Exception:
            return
        if order is None:
            return
        order_text = str(order).strip()
        if not order_text or order_text.lower() in ("nan", "none"):
            return
        try:
            ep = self.filter_panel.process_order_edit
            ep.blockSignals(True)
            ep.setText(order_text)
            ep.blockSignals(False)
        except Exception:
            pass
        keys = {"_process_order": order_text}
        # v43.153：记下「本次联动前」的条件，作为 0 行回退的基底。
        # 不能用 _link_snapshot（那是首次联动前的快照，可能已含上一轮联动条件），
        # 也不能用当前条件（已含刚失败的 _material_code）——都会让回退失效。
        try:
            pre_base = dict(self.proxy_model.getCustomFilters())
        except Exception:
            pre_base = {}
        try:
            factory_val = record.get("工厂")
            if factory_val is not None and str(factory_val).strip():
                keys["工厂"] = str(factory_val).strip()
        except Exception:
            pass

        # v43.150：v43.149 及之前只按订单过滤 → 一个订单几十行时联动视图无法定位到具体物料
        # （原辅料订单本机实测最多 39 行）。这里叠加物料条件，把钻取收敛到「该订单的该物料」。
        # _link_material_condition 返回的是「待合并的 dict」而不是 (key, value) 序列。
        # v43.153 修复：原写法 mat_key[0] / mat_key[1] 是在按整数下标取 dict 的键，
        # 必然抛 KeyError: 1，异常又被 locate.py 静默吞掉 → 表现为
        # 「会跳转到主表、但不筛选、也没有联动横幅」。正确写法是 update 整个 dict。
        mat_key, mat_label = self._link_material_condition(record)
        if mat_key:
            keys.update(mat_key)
        label = "订单 %s · %s" % (order_text, source_label)
        if mat_label:
            label += " · " + mat_label
        self._apply_focus_filters(keys, label)

        # v43.150：叠加物料条件后若一行都没命中（编码异常 / 列缺失 / 名称有前后差异），
        # 自动回退到纯订单过滤，绝不给用户一张空表。
        if mat_key and not self._link_hit_any_row():
            self.log("[联动钻取] 叠加物料条件命中 0 行，回退为纯订单过滤", "warning")
            fallback = {"_process_order": order_text}
            if "工厂" in keys:
                fallback["工厂"] = keys["工厂"]
            label_fb = "订单 %s · %s" % (order_text, source_label)
            if mat_label:
                label_fb += " · " + mat_label
            # base=pre_base：以本次联动前的条件为基底重建，
            # 否则刚失败的 _material_code 仍留在条件里，回退后依旧 0 行。
            self._apply_focus_filters(fallback, label_fb, replace=True, base=pre_base)

    @staticmethod
    def _link_material_condition(record):
        """从看板行记录里取出用于精确定位的物料条件。

        返回 (keys_dict_for_merge, 显示用标签)；无可用物料条件时返回 (None, "")。
        物料编码是 8 位等长，proxy 的子串匹配等价于精确匹配，故优先用编码；
        编码缺失时才退到物料名称（子串，宽松些但仍远窄于整个订单）。
        """
        def _txt(key):
            try:
                v = record.get(key)
            except Exception:
                return ""
            if v is None:
                return ""
            s = str(v).strip()
            if not s or s.lower() in ("nan", "none", "nat"):
                return ""
            return s

        code = _txt("物料编码")
        if code:
            name = _txt("物料名称")
            label = code + ((" " + name) if name else "")
            return {"_material_code": code}, label
        name = _txt("物料名称")
        if name:
            return {"_material_names": name}, name
        return None, ""

    def _link_hit_any_row(self):
        """当前联动筛选下主表是否还有可见行（用于物料条件兜底回退）。"""
        if self.proxy_model is None:
            return True
        try:
            sm = self.proxy_model.sourceModel()
            if sm is None:
                return True
            for row in range(sm.rowCount()):
                if self.proxy_model.filterAcceptsRow(row, QModelIndex()):
                    return True
            return False
        except Exception:
            return True

    def _clear_link_drilldown(self):
        """清除联动：恢复钻取前的筛选快照，隐藏横幅。"""
        if self._link_snapshot is not None and self.proxy_model is not None:
            self.proxy_model.setCustomFilters(self._link_snapshot)
            self._update_summary()
        self._link_snapshot = None
        self.main_table.clear_link_banner()

    def _apply_focus_filters(self, filter_keys, label, replace=False, base=None):
        """通用焦点钻取：在现有筛选上叠加 filter_keys 并显示联动横幅（可撤销）。

        filter_keys 与 AuditProxyModel._custom_filters 同构：
          普通列名（车间/工厂…）→ 精确匹配；"_material_names"/"_process_order" 等
          特殊键 → proxy 内置语义。缺列键由 proxy 自动跳过，不会报错。

        replace=True 时不再叠加当前条件，而是以 base（缺省取联动前快照）为基底重建。
        v43.153 必需：0 行兜底回退时若仍走叠加语义，刚失败的 _material_code 会
        留在条件里 → 回退后依旧 0 行（死循环空表）。
        """
        if self.proxy_model is None:
            return
        if replace:
            if base is None:
                base = self._link_snapshot if self._link_snapshot is not None else {}
        else:
            base = self.proxy_model.getCustomFilters()
            if self._link_snapshot is None:
                self._link_snapshot = base
        merged = dict(base or {})
        merged.update(filter_keys)
        self.proxy_model.setCustomFilters(merged)
        self._update_summary()
        self.main_table.show_link_banner(label)

    def _apply_board_focus(self, url):
        """管理看板「到主表」芯片：zpp011://link?type=…&v=…&fac=… → 主表联动钻取。"""
        if not url or not url.startswith("zpp011:"):
            return
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(url).query)
            t = q.get("type", [""])[0]
            v = q.get("v", [""])[0].strip()
            fac = q.get("fac", [""])[0].strip()
            if not t or not v:
                return
            keys = {}
            parts = []
            if t in ("worst_workshop", "lowest_coverage_workshop"):
                keys["车间"] = v
                parts.append("车间 " + v)
            elif t == "top_material":
                keys["_material_names"] = v
                parts.append("物料 " + v)
            elif t == "top_product":
                keys["_material_names"] = v
                parts.append("成品线 " + v)
            else:
                return
            if fac:
                keys["工厂"] = fac
                parts.insert(0, fac.split("-")[-1])
            self._apply_focus_filters(keys, " · ".join(parts) + "（来自管理看板）")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    def _capture_natural_df(self):
        """数据（重新）加载时记录原始顺序，供"取消排序"恢复；排序过程中的 setDataFrame 忽略。"""
        if getattr(self, "_in_sort", False):
            return
        if self.source_model is not None:
            df = self.source_model.getDataFrame()
            if df is not None:
                self._natural_df = df.copy()

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
        self.ui_settings_controller.update_summary()

    def _update_mark_stats(self):
        self.ui_settings_controller.update_mark_stats()

    def _update_selection_summary(self, col_sums: dict):
        """更新选中行合计到底部栏"""
        return self.interaction_controller._update_selection_summary(col_sums)

    def _clear_selection_summary(self):
        """清空选中合计，恢复默认"""
        return self.interaction_controller._clear_selection_summary()


    # _update_stat_cards 已删除（统计卡片不再使用）

    def _on_export_full_excel(self):
        """点击「导出完整Excel」"""
        audit_data = self.view_model.df
        if audit_data is None or audit_data.empty:
            QMessageBox.warning(self, "提示", "无数据，请先进行分析")
            return

        if self._heavy_busy:
            QMessageBox.information(self, "提示", "分析/报告生成进行中，请稍候再导出")
            return

        _ap = getattr(self, '_analysis_params', None) or {}
        _sd = str(_ap.get('start_date') or '').strip()
        _ed = str(_ap.get('end_date') or '').strip()
        if _sd and _ed:
            _rng = f"{_sd.replace('-', '')}-{_ed.replace('-', '')}"
            default_name = f"ZPP011偏差分析最终版_{_rng}_（{_rng}）.xlsx"
        else:
            default_name = f"ZPP011偏差分析最终版_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存完整Excel文件", default_name, "Excel files (*.xlsx)"
        )
        if not save_path:
            return

        analysis_params = self._analysis_params
        current_input_file = self.current_input_file
        cache_path = self._full_analysis_cache_path

        has_valid_params = (
            analysis_params
            and isinstance(analysis_params, dict)
            and analysis_params.get('input_file')
            and current_input_file
        )

        if has_valid_params:
            reply = QMessageBox.question(
                self, "导出选项",
                "是否生成完整多Sheet分析报告（含汇总统计、预警颜色等）？\n\n"
                "点击「是」→ 生成完整多Sheet Excel（缓存命中则秒传，否则重新分析）\n"
                "点击「否」→ 仅导出当前表格数据（快速）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.export_controller.export_full_analysis_inline(
                    save_path, analysis_params, cache_path, self
                )
                return

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
                _open_file(save_path)
            self.log(f"已导出完整Excel到 {save_path}", "info")
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
            self.log(f"导出失败: {e}", "error")

    def _sync_alt_pairs_for_full_report(self):
        self.export_controller.sync_alt_pairs_for_full_report()

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
            # v43.240 修复：净偏差重算不改变被变更检测比对的「实际数量/备注原因/产量」，
            # 但本函数读的是 view_model.df——其 _read 副本未被「变动提醒-全设为已读」更新（仍是 0），
            # 若直接 setDataFrame 会把刚标好的已读(_read=1)覆盖回未读，导致变动提醒又翻回未读。
            # 故重算后从 DB 重新派生 _read/_post_audit_changed，让已读状态跨净偏差重算存活。
            if '_read' in df.columns and 'data_id' in df.columns:
                df = self.data_service._restore_read_status(df)
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
            # v43.240 修复：与空配对分支同理，重算后从 DB 重新对账已读状态，
            # 避免把「变动提醒-全设为已读」标好的 _read=1 覆盖回 0（清空替代料看板→变动提醒又变未读）。
            if '_read' in new_df.columns and 'data_id' in new_df.columns:
                new_df = self.data_service._restore_read_status(new_df)
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
        # 右键先选中命中行：否则批量操作会作用在上一次的选择上（所见非所改）
        clicked_row = index.row()
        _cur_rows = {ix.row() for ix in self.table_view.selectionModel().selectedIndexes()}
        if clicked_row not in _cur_rows:
            self.table_view.selectRow(clicked_row)
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
        profile_action = menu.addAction("🪪 查看物料画像")
        profile_action.triggered.connect(
            lambda: self._show_material_profile(row_data.get('物料编码', ''))
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
        # 复制为微信草稿（用于快速沟通）
        wechat_action = menu.addAction("📋 复制为微信草稿")
        wechat_action.triggered.connect(lambda: self._copy_wechat_draft(selected_rows))
        # 复制选中区域（原功能保留）
        copy_region_action = menu.addAction("复制选中区域")
        copy_region_action.triggered.connect(self.copy_selected_cells)
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _copy_wechat_draft(self, rows):
        """将选中行整理成微信沟通草稿，复制到剪贴板"""
        if not rows or self.source_model is None:
            return
        df = self.source_model.getDataFrame()
        if df is None or df.empty:
            return
        lines = ["【偏差沟通】"]
        for row in rows[:10]:
            if row >= len(df):
                continue
            r = df.iloc[row]
            # 兼容多种列名
            def get_col(*keys):
                for k in keys:
                    if k in df.columns:
                        v = r.get(k, '')
                        if v is None:
                            v = ''
                        return str(v).strip()
                return ''
            order = get_col('流程订单', 'order', 'SAP订单', '订单号')
            # 日期使用订单号，或者获取订单中的日期部分，如果没有则显示今天
            from datetime import datetime
            date_val = get_col('订单日期', 'order_date', 'date')
            if not date_val:
                # 尝试从流程订单中提取 (比如 "SAP20260512001" -> 2026-05-12)
                import re
                match = re.search(r'\d{8}', order)
                if match:
                    d = match.group()
                    date_val = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                else:
                    date_val = datetime.now().strftime("%Y-%m-%d")
            code = get_col('物料编码', '物料号', 'code', '组件物料号')
            name = get_col('物料名称', '物料描述', 'name', '组件物料描述')[:20]
            quota = get_col('定额', '标准用量')
            actual = get_col('实际', '实际用量')
            dev_qty = get_col('偏差数量', 'dev_qty')
            dev_rate = get_col('偏差率(%)', 'deviation_rate', '偏差率') or get_col('偏差率', '')
            dev_amt = get_col('偏差金额(含税)', '偏差金额')
            remark = get_col('备注', '备注原因')
            lines.append(f"订单日期：{date_val}")
            lines.append(f"订单号：{order}")
            lines.append(f"物料：{code} {name}")
            lines.append(f"定额：{quota}，实际：{actual}，偏差数量：{dev_qty}")
            if dev_rate:
                lines.append(f"偏差率：{dev_rate}%")
            if dev_amt:
                lines.append(f"偏差金额：¥{dev_amt}")
            lines.append(f"备注：{remark or '无'}")
            lines.append("")
        if len(rows) > 10:
            lines.append(f"... 共 {len(rows)} 条，仅显示前10条")
        lines.append("请核实处理，谢谢！")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"已复制 {len(rows)} 条记录的微信草稿", 3000)

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
        """薄壳：手动移入/移出隔离区（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._set_quarantine(rows, flag)

    def _repair_quarantine_consistency(self, silent=False):
        """薄壳：修复隔离区一致性（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._repair_quarantine_consistency(silent)

    def _auto_move_to_quarantine(self, manual=False):
        """薄壳：按规则自动移入隔离区（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._auto_move_to_quarantine(manual)

    # ------------------------------------------------------------------ #
    # 隔离区失效复核（监控旧数据改动：负损→补投相符 / 自动规则不再命中）
    # —— ARC-003 第七刀：主体已切出到 QuarantineManagerController，此处保留薄壳
    # ------------------------------------------------------------------ #
    def _update_quarantine_badge(self, expired_list):
        """薄壳：隔离区角标刷新（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._update_quarantine_badge(expired_list)

    def _scan_expired_quarantine_after_analysis(self):
        """薄壳：分析完成后失效扫描（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._scan_expired_quarantine_after_analysis()

    def _notify_expired_quarantine(self, new_uids, expired_all):
        """薄壳：失效记录弹窗（ARC-003 第七刀切出到 QuarantineManagerController）。"""
        return self.quarantine_manager_controller._notify_expired_quarantine(new_uids, expired_all)

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
        # 同时在应用级安装事件过滤器：跟踪 Ctrl 按下状态（多级排序判定用）。
        # 关键：从键盘事件流自行维护 _ctrl_down，彻底绕开 Qt「鼠标事件读不到 Ctrl 修饰符」的坑。
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    @staticmethod
    def _mod_has_ctrl(mods):
        mv = mods.value if hasattr(mods, "value") else int(mods)
        return bool(mv & int(Qt.ControlModifier.value))

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        et = event.type()
        # —— Ctrl 状态跟踪（多级排序用）——
        if et == QEvent.KeyPress and event.key() == Qt.Key_Control:
            self._ctrl_down = True
        elif et == QEvent.KeyRelease and event.key() == Qt.Key_Control:
            self._ctrl_down = False
        elif et in (QEvent.KeyPress, QEvent.KeyRelease):
            # 其它按键时同步修饰符态（例如 Ctrl 已按住但焦点切换）
            self._ctrl_down = self._mod_has_ctrl(event.modifiers())
        # —— 原有：表格复制快捷键 ——
        if obj is self.table_view and et == QEvent.KeyPress:
            key_event = event
            if key_event.matches(QKeySequence.Copy):
                self.copy_selected_cells()
                return True
        return super().eventFilter(obj, event)

    def copy_selected_cells(self):
        """复制选中区域到剪贴板（Excel 式：按选中矩形输出，空洞填空）。

        原先 main_window 有两份实现：菜单连这份、Ctrl+C 连 _copy_selected_cells，
        两者行为不一致；现统一为本实现，两条入口共用。
        """
        return self.interaction_controller._copy_selected_cells()

    # -----------------------------------------------------------
    # 双击明细
    # -----------------------------------------------------------
    def _on_cell_double_clicked(self, index):
        # v43.236 调试增强：log() 目前是空实现（运行日志面板已移除），仅靠它无法确认
        # 双击信号是否真的到达。这里同时写状态栏 + 打 traceback，保证任何路径（成功/
        # 越界/异常）都留可见痕迹，便于定位"双击无响应"。
        try:
            self.statusBar().showMessage(
                f"[双击] row={index.row() if index.isValid() else 'invalid'}", 4000)
        except Exception:
            pass
        self.log("双击事件触发：index={}".format(index), "info")
        try:
            return self.interaction_controller._on_cell_double_clicked(index)
        except Exception:
            import traceback
            traceback.print_exc()
            raise

    def _show_row_detail(self, row_data):
        return self.interaction_controller._show_row_detail(row_data)

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
        """薄壳：PPT 生成入口（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._generate_ppt_report()

    def _on_ppt_done(self, path):
        """薄壳：PPT 完成回调（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._on_ppt_done(path)

    def _on_ppt_fail(self, err):
        """薄壳：PPT 失败回调（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._on_ppt_fail(err)

    def _resolve_smart_ppt_excel(self):
        """薄壳：智能 PPT 取数（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._resolve_smart_ppt_excel()

    def _generate_smart_ppt_simple(self):
        """薄壳：分厂版智能 PPT（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._generate_smart_ppt_simple()

    def _generate_smart_ppt_pro(self):
        """薄壳：专业版智能 PPT（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._generate_smart_ppt_pro()

    def _open_guizang_magazine(self):
        """薄壳：归藏-Magazine（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._open_guizang_magazine()

    def _open_guizang_swiss(self):
        """薄壳：归藏-Swiss（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._open_guizang_swiss()

    def _open_guizang(self, style):
        """薄壳：归藏报告通用方法（ARC-003 第九刀切出到 PptController）。"""
        return self.ppt_controller._open_guizang(style)

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
        dialog.setWindowTitle(f"关于 - ZPP011 v{VERSION_HISTORY[0]['version']}")
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
        title_label = QLabel(f"{APP_NAME} v{VERSION_HISTORY[0]['version']}")
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
            for section_key, section_title in [("features", "✦ 新功能"), ("fixes", "🔧 修复"), ("optimizations", "⚡ 优化"), ("lessons", "⚠ 教训"), ("notes", "📌 说明")]:
                items = v.get(section_key, [])
                # ⚠ 兼容 str 与 list 两种写法（v43.166）。
                #   version_history 里 features/fixes 历来写成**字符串**，而下面
                #   `for item in items` 对字符串是**逐字符迭代** —— 每个汉字各包一个
                #   <li>，整段被拆成几百行单列，就是「版本日志文字竖排成一列单字」。
                #   实测 v43.165 修复前 features 生成 265 个 <li>、fixes 301 个；
                #   v43.163 的 fixes 更夸张（451 个）。短文案时不明显，长文案即暴露。
                #   归一化：str 视作单个列表项（保留其内部换行语义）。
                if isinstance(items, str):
                    items = [items]
                elif not isinstance(items, (list, tuple)):
                    items = [str(items)]
                if items:
                    html_parts.append(f'<div class="section">{section_title}</div><ul>')
                    for item in items:
                        # ⚠ 转义 < 与 >：版本日志正文里可能引用 HTML 标签名
                        #   （如 v43.166 自己的 fixes 里就写了 `<li>`），不转义会被
                        #   QTextBrowser 当成未知标签 —— 要么吞掉、要么把后面的文本吃掉。
                        #   只转这两个字符，**加粗** 等 Markdown 记号保持原样（它们本就
                        #   是给日志窗口看的字面文本，不是真Markdown）。
                        _txt = (str(item).replace('&', '&amp;')
                                .replace('<', '&lt;').replace('>', '&gt;'))
                        html_parts.append(f'<li>{_txt}</li>')
                    html_parts.append('</ul>')
        return "".join(html_parts)

    def _show_import_wizard(self):
        dialog = ImportWizard(self)
        dialog.exec()

    def _show_source_backup(self):
        """打开历史源码备份目录"""
        from PySide6.QtWidgets import QMessageBox
        
        backup_dir = os.path.expanduser("~/.zpp011_audit/source_backups")
        if not os.path.exists(backup_dir):
            QMessageBox.information(self, "提示", f"源码备份目录不存在:\n{backup_dir}\n\n请先运行一次打包脚本以生成备份")
            return
        
        # 尝试打开文件夹（v43.257：内联的平台分发收敛到 _open_file，不再重复第四份）
        _open_file(backup_dir)
        
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
                # v43.198：quit() 对正在执行 run() 的 QThread 是空操作，先置取消
                # 标志让它在下一分析检查点自行退出，再 quit()+wait() 收尾
                if hasattr(self._cache_worker, "request_cancel"):
                    self._cache_worker.request_cancel()
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

    # ------------------------------------------------------------------ #
    # 列头筛选取消入口（v43.143）
    # 说明：这三个方法必须放在 class 末尾。0 缩进 def 会让 Python 判定上层 class
    # 在此提前结束，若插在 __init__ 等方法序列中间，其后所有语句会被吸进新方法体，
    # __init__ 提前 return → 组件装配全部缺失（proxy_model 为 None）。
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # ARC-003 薄壳转发层（v43.193）：列过滤/排序/宽度 24 个方法已切出到
    # controllers/column_controller.py。以下薄壳仅为保持既有外部调用签名不变
    # （components/main_table.py 信号绑定 self.mw._on_header_clicked 等、
    #  各看板 dialog 的 self.main_window._apply_column_visibility_by_name()），
    # 逻辑零改动。禁止在薄壳内新增业务逻辑。
    # ------------------------------------------------------------------ #
    # ARC-003 第三刀薄壳（v43.195）：筛选预设 9 个方法已切出到
    # controllers/filter_preset_controller.py。其中 _filters_to_jsonable /
    # _jsonable_to_filters 在 controller 侧仍为 @staticmethod，此处经实例转发亦合法。
    # ------------------------------------------------------------------ #
    def _filter_preset_store(self):
        return self.filter_preset_controller._filter_preset_store()

    @staticmethod
    def _filters_to_jsonable(state):
        return FilterPresetController._filters_to_jsonable(state)

    @staticmethod
    def _jsonable_to_filters(state):
        return FilterPresetController._jsonable_to_filters(state)

    def _capture_last_used_filter(self):
        return self.filter_preset_controller._capture_last_used_filter()

    def _save_filter_preset(self, name):
        return self.filter_preset_controller._save_filter_preset(name)

    def _prompt_save_preset(self):
        return self.filter_preset_controller._prompt_save_preset()

    def _apply_filter_preset(self, name):
        return self.filter_preset_controller._apply_filter_preset(name)

    def _delete_filter_preset(self, name):
        return self.filter_preset_controller._delete_filter_preset(name)

    def _refresh_filter_preset_menu(self):
        return self.filter_preset_controller._refresh_filter_preset_menu()

    # ------------------------------------------------------------------ #
    # ARC-003 第四刀薄壳（v43.196）：11 个看板/弹窗展示方法已切出到
    # controllers/dashboard_controller.py。保持签名不变，故既有绑定照旧：
    #   components/menu_bar.py:76  alert_action -> self.mw._show_alert_dashboard
    #   components/left_panel.py:316  self.mw._show_semi_detail_window(category)
    # _show_material_profile 保留 code=None, name=None 默认参数。
    # ------------------------------------------------------------------ #
    def _show_alert_dashboard(self):
        return self.dashboard_controller._show_alert_dashboard()

    def _show_deviation_warning_dialog(self):
        return self.dashboard_controller._show_deviation_warning_dialog()

    def _show_neg_loss_dashboard(self):
        return self.dashboard_controller._show_neg_loss_dashboard()

    def _show_pos_loss_dashboard(self):
        return self.dashboard_controller._show_pos_loss_dashboard()

    def _show_data_stability_dashboard(self):
        return self.dashboard_controller._show_data_stability_dashboard()

    def _show_quarantine_review_dashboard(self):
        return self.dashboard_controller._show_quarantine_review_dashboard()

    def _show_alt_chain_dashboard(self):
        return self.dashboard_controller._show_alt_chain_dashboard()

    def _show_material_profile(self, code=None, name=None):
        return self.dashboard_controller._show_material_profile(code, name)

    def _show_semi_dashboard(self):
        return self.dashboard_controller._show_semi_dashboard()

    def _show_semi_detail_window(self, category):
        return self.dashboard_controller._show_semi_detail_window(category)

    def _show_dashboard(self):
        return self.dashboard_controller._show_dashboard()

    # ------------------------------------------------------------------ #
    # ARC-003 第五刀薄壳（v43.197）：半成品分类管理 11 个方法已切出到
    # controllers/semi_category_controller.py。保持签名不变，故既有绑定照旧：
    #   components/left_panel.py:285-289  添加/删除/重置/导入/导出 五个按钮
    #   components/left_panel.py:316     _show_semi_detail_window（已在第四刀切出）
    # 状态字段 self._semi_categories 仍留在 MainWindow（__init__:224 初始化，
    # 早于本 controller 装配点，且经 view_model 间接读），controller 经
    # self.mw._semi_categories 访问。
    # ------------------------------------------------------------------ #
    def _filter_semi_materials(self, category):
        return self.semi_category_controller._filter_semi_materials(category)

    def _reset_semi_filter(self):
        return self.semi_category_controller._reset_semi_filter()

    def _load_semi_categories(self):
        return self.semi_category_controller._load_semi_categories()

    def _get_semi_category_list(self):
        return self.semi_category_controller._get_semi_category_list()

    def _save_semi_categories(self, mapping):
        return self.semi_category_controller._save_semi_categories(mapping)

    def _refresh_semi_list_ui(self):
        return self.semi_category_controller._refresh_semi_list_ui()

    def _add_semi_category(self):
        return self.semi_category_controller._add_semi_category()

    def _delete_semi_category(self):
        return self.semi_category_controller._delete_semi_category()

    def _reset_semi_categories(self):
        return self.semi_category_controller._reset_semi_categories()

    def _import_semi_categories(self):
        return self.semi_category_controller._import_semi_categories()

    def _export_semi_categories(self):
        return self.semi_category_controller._export_semi_categories()

    def _toggle_column_lock(self, *args, **kwargs):
        return self.column_controller._toggle_column_lock(*args, **kwargs)

    def _toggle_table_fullscreen(self, *args, **kwargs):
        return self.column_controller._toggle_table_fullscreen(*args, **kwargs)

    def _show_column_hide_dialog(self, *args, **kwargs):
        return self.column_controller._show_column_hide_dialog(*args, **kwargs)

    def _is_column_effectively_hidden(self, *args, **kwargs):
        return self.column_controller._is_column_effectively_hidden(*args, **kwargs)

    def _ensure_column_visible_width(self, *args, **kwargs):
        return self.column_controller._ensure_column_visible_width(*args, **kwargs)

    def _apply_column_visibility_by_name(self, *args, **kwargs):
        return self.column_controller._apply_column_visibility_by_name(*args, **kwargs)

    def _set_column_widths(self, *args, **kwargs):
        return self.column_controller._set_column_widths(*args, **kwargs)

    def _apply_default_width(self, *args, **kwargs):
        return self.column_controller._apply_default_width(*args, **kwargs)

    def _get_user_config_dir(self, *args, **kwargs):
        return self.column_controller._get_user_config_dir(*args, **kwargs)

    def _get_config_path(self, *args, **kwargs):
        return self.column_controller._get_config_path(*args, **kwargs)

    def _get_default_config_path(self, *args, **kwargs):
        return self.column_controller._get_default_config_path(*args, **kwargs)

    def _save_column_widths(self, *args, **kwargs):
        return self.column_controller._save_column_widths(*args, **kwargs)

    def _load_column_widths(self, *args, **kwargs):
        return self.column_controller._load_column_widths(*args, **kwargs)

    def _on_header_clicked(self, *args, **kwargs):
        return self.column_controller._on_header_clicked(*args, **kwargs)

    def _update_col_filter_hint(self, *args, **kwargs):
        return self.column_controller._update_col_filter_hint(*args, **kwargs)

    def _toggle_col_filter_mode(self, *args, **kwargs):
        return self.column_controller._toggle_col_filter_mode(*args, **kwargs)

    def _open_column_filter(self, *args, **kwargs):
        return self.column_controller._open_column_filter(*args, **kwargs)

    def _open_empty_column_filter_popup(self, *args, **kwargs):
        return self.column_controller._open_empty_column_filter_popup(*args, **kwargs)

    def _apply_multi_sort(self, *args, **kwargs):
        return self.column_controller._apply_multi_sort(*args, **kwargs)

    def _update_sort_indicators(self, *args, **kwargs):
        return self.column_controller._update_sort_indicators(*args, **kwargs)

    def _show_col_filter_clear_menu(self, *args, **kwargs):
        return self.column_controller._show_col_filter_clear_menu(*args, **kwargs)

    def _clear_col_filter_by_name(self, *args, **kwargs):
        return self.column_controller._clear_col_filter_by_name(*args, **kwargs)

    def _clear_all_col_filters(self, *args, **kwargs):
        return self.column_controller._clear_all_col_filters(*args, **kwargs)

    def _drop_sort_columns(self, *args, **kwargs):
        return self.column_controller._drop_sort_columns(*args, **kwargs)


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
