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
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QHeaderView,
    QDialog,
    QDialogButtonBox,
    QSplitter,
    QScrollArea,
    QComboBox,
    QAbstractItemView,
    QMessageBox,
    QTableWidgetItem,
    QMenu,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QTimer
from PySide6.QtGui import QFont, QShortcut, QKeySequence, QAction

# 导入组件
from gui_pyside6.components.menu_bar import MenuBarComponent
from gui_pyside6.components.left_panel import LeftPanelComponent
from gui_pyside6.components.main_table import MainTableComponent
from gui_pyside6.components.bottom_bar import BottomBarComponent

# 导入自定义模块
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
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
from core.alert_monitor import AlertMonitor
from domain.alt_material.alt_manager import (
    load_alt_pairs,
    save_alt_pairs,
    DEFAULT_ALT_PAIRS,
)
from core.config_manager import ConfigManager

# 导入已读/未读状态管理模块
from core.fingerprint import calc_fingerprint
from core.read_status import load_read_status, record_deviation_change
from gui_pyside6.services.data_service import DataService
from utils.version_history import get_current_version

# 导入控制器和服务
from gui_pyside6.controllers.analysis_controller import AnalysisController
from gui_pyside6.controllers.audit_controller import AuditController
from gui_pyside6.controllers.export_controller import ExportController
from gui_pyside6.controllers.alt_controller import AltController


class MainWindow(QMainWindow):
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
        self.loading_dialog = None
        self.sort_columns = []
        self._countdown_seconds = 0
        self._countdown_timer = None

        # ============================================
        # 创建控制器（顺序重要）
        # ============================================
        self.analysis_controller = AnalysisController(self)
        self.audit_controller = AuditController(self)
        self.export_controller = ExportController(self)
        self.alt_controller = AltController(self)
        self.data_service = DataService(self.alt_controller)
        self.data_service.log_signal.connect(self._on_data_service_log)

        # ============================================
        # 创建组件（顺序重要：必须在使用前创建）
        # ============================================
        self.menu_bar = MenuBarComponent(self)
        self.left_panel_component = LeftPanelComponent(self)
        self.main_table = MainTableComponent(self)
        self.stats_cards = StatsCardsWidget(self)
        self.bottom_bar = BottomBarComponent(self)

        # 连接按钮信号
        self._setup_connections()

        # 初始化 UI 引用
        self.left_panel = self.left_panel_component.left_panel
        self.filter_panel = None
        self.progress_bar = self.main_table.progress_bar
        self.progress_label = self.main_table.progress_label
        self.stat_total = self.main_table.stat_total
        self.stat_high = self.main_table.stat_high
        self.stat_need_note = self.main_table.stat_need_note
        self.stat_ok = self.main_table.stat_ok
        self.table_view = self.main_table.table_view
        self.summary_quota = self.main_table.summary_quota
        self.summary_actual = self.main_table.summary_actual
        self.lock_btn = self.main_table.lock_btn
        self.fullscreen_btn = self.main_table.fullscreen_btn
        self.progress_group = self.main_table.progress_group
        self.action_group = self.main_table.action_group
        self.progress_bar = self.main_table.progress_bar
        self.progress_label = self.main_table.progress_label
        self.stat_total = self.main_table.stat_total
        self.stat_high = self.main_table.stat_high
        self.stat_need_note = self.main_table.stat_need_note
        self.stat_ok = self.main_table.stat_ok
        self.table_view = self.main_table.table_view
        self.summary_quota = self.main_table.summary_quota
        self.summary_actual = self.main_table.summary_actual
        self.summary_amount = self.main_table.summary_amount
        self.summary_qty = self.main_table.summary_qty
        self.start_btn = self.main_table.start_btn
        self.cancel_btn = self.main_table.cancel_btn
        self.log_group = self.bottom_bar.log_group

        # 组装主布局
        self._assemble_layout()

        # 刷新替代料视图
        self._refresh_alt_view()

        # 全局快捷键
        QShortcut(QKeySequence("F5"), self).activated.connect(
            self._start_analysis
        )
        QShortcut(QKeySequence("F6"), self).activated.connect(
            lambda: self.export_controller.export_current_table(
                self.view_model.df, self
            )
        )
        QShortcut(QKeySequence("F7"), self).activated.connect(
            self._show_benefit_report
        )
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            lambda: self._batch_mark_selected_read(1)
        )
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(
            self._copy_previous_remark
        )
        QShortcut(QKeySequence("F11"), self).activated.connect(
            self._toggle_table_fullscreen
        )

        self.statusBar().showMessage("就绪")

        # ViewModel (MVVM 状态管理)
        self.view_model = AnalysisViewModel(self)
        self.view_model.df = pd.DataFrame()
        self.view_model.data_changed.connect(self._on_view_model_data_changed)

        # 工厂数据缓存
        self.factory_data = {}
        self.factory_combo = QComboBox()

        # 预警监控
        from core.config_loader import config

        self.alert_monitor = AlertMonitor(
            data_source_func=lambda: self.view_model.df,
            threshold=config.get("alert.threshold_percent", 10.0),
            interval=config.get("alert.scan_interval_seconds", 60),
            only_alt=config.get("alert.only_alt_materials", True),
        )
        self.alert_monitor.alert_triggered.connect(self._on_new_alerts)

        # 初始化输出目录
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)

        # 初始化日期编辑控件
        self.start_date_edit = QLineEdit()
        self.end_date_edit = QLineEdit()
        
        # 初始化物料搜索
        self.material_search_edit = QLineEdit()
        
        # 初始化替代料表格和计数标签
        self.alt_table = None
        self.alt_count_label = None

        # 初始化表格模型
        self._init_table_model()

        # 所有组件初始化完成后才显示窗口，避免布局反复重算
        self.show()

    # -----------------------------------------------------------
    # 布局组装
    # -----------------------------------------------------------
    def _assemble_layout(self):
        """组装所有组件到主窗口"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 自定义标题栏
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            "background-color: #42a5f5; border-bottom: 2px solid #1976d2;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 0, 16, 0)

        maker_label = QLabel("制作人：裴盛清")
        maker_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.9); font-size: 13px; font-weight: bold; padding: 2px 8px; background-color: rgba(255, 255, 255, 0.15); border-radius: 3px;"
        )
        icon_label = QLabel("🏭")
        icon_label.setStyleSheet("font-size: 20px;")
        title_label = QLabel(f"云南达利ZPP011生产偏差分析器 {get_current_version()}")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")

        header_layout.addWidget(maker_label)
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addWidget(header)

        spacer = QWidget()
        spacer.setFixedHeight(5)
        main_layout.addWidget(spacer)

        # 主体区域
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(4, 4, 4, 4)

        # 左侧面板
        body_layout.addWidget(self.left_panel)

        # FilterPanel
        from gui_pyside6.widgets.filter_panel import FilterPanel

        self.filter_panel = FilterPanel()
        self.filter_panel.filter_changed.connect(self._on_filter_panel_changed)

        # 右侧内容
        self.right_splitter = QSplitter(Qt.Horizontal)
        self.right_splitter.setSizes([260, 740])
        self.right_splitter.addWidget(self.filter_panel)

        right_container = QWidget()
        right_container_layout = QVBoxLayout(right_container)
        right_container_layout.setContentsMargins(6, 6, 6, 6)

        # 添加主表格区和底部栏
        right_container_layout.addWidget(self.main_table.progress_group)
        right_container_layout.addWidget(self.main_table.action_group)
        right_container_layout.addWidget(self.stats_cards)
        self.audit_group = self.main_table.audit_group
        right_container_layout.addWidget(self.audit_group, 1)
        right_container_layout.addWidget(self.bottom_bar.log_group)

        self.right_splitter.addWidget(right_container)
        body_layout.addWidget(self.right_splitter, 1)

        main_layout.addWidget(body_widget, 1)

    # -----------------------------------------------------------
    # 信号连接
    # -----------------------------------------------------------
    def _setup_connections(self):
        """连接按钮点击信号"""
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
        self.main_table.export_full_btn.clicked.connect(
            lambda: self.export_controller.export_full_excel(
                self.view_model.df, self.current_input_file, self._analysis_params, self
            )
        )
        self.main_table.refresh_net_btn.clicked.connect(self._recalculate_net_offset)
        self.main_table.table_view.doubleClicked.connect(self._on_cell_double_clicked)

        # Ctrl+C 复制选中单元格
        self._install_table_copy_handler()

        # 连接控制器信号
        self.analysis_controller.analysis_started.connect(self._on_analysis_ui_start)
        self.analysis_controller.progress_updated.connect(self._on_analysis_progress_ui)
        self.analysis_controller.log_message.connect(self.log)
        self.analysis_controller.analysis_finished.connect(self._on_analysis_finished_ui)
        self.stats_cards.card_clicked.connect(self._on_stats_card_clicked)
        self.analysis_controller.analysis_error.connect(self._on_analysis_error_ui)
        self.audit_controller.progress_started.connect(self._on_ai_ui_start)
        self.audit_controller.progress_updated.connect(self._on_ai_progress_ui)
        self.audit_controller.progress_finished.connect(self._on_ai_finished_ui)
        self.audit_controller.progress_error.connect(self._on_ai_error_ui)

    # -----------------------------------------------------------
    # 业务方法（原有方法，保持向后兼容）
    # -----------------------------------------------------------
    def _on_data_service_log(self, msg, level):
        """处理 DataService 的日志信号"""
        if level == "alert" and msg.startswith("变动提醒|"):
            count = msg.split("|")[1]
            QMessageBox.information(
                self,
                "变动提醒",
                f"发现 {count} 条已审核记录发生数值变动，已强制设为'未读'。",
            )
        else:
            self.log(msg, level)

    # ------------------- 分析启动 -------------------
    def _start_analysis(self):
        """启动分析（委托给 AnalysisController）"""
        if not self.current_input_file:
            QMessageBox.warning(self, "提示", "请先选择输入文件")
            return
        if (
            self.analysis_controller.worker
            and self.analysis_controller.worker.isRunning()
        ):
            QMessageBox.information(self, "提示", "分析任务已在后台运行")
            return

        self.loading_dialog = LoadingDialog("正在分析数据，请稍候...", self)
        self.loading_dialog.show()
        QApplication.processEvents()

        start_date = self.start_date_edit.text().strip()
        end_date = self.end_date_edit.text().strip()
        material_search = self.material_search_edit.text().strip()
        self.analysis_controller.start_analysis(
            self.current_input_file,
            self.alt_controller.get_pairs(),
            start_date,
            end_date,
            material_search,
        )

    # ------------------- 分析 UI 回调 -------------------
    def _on_analysis_ui_start(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.start_btn.setEnabled(False)
        self._countdown_seconds = 0
        self._current_step = "准备中"
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
        self.factory_combo.clear()
        if factory_list:
            self.factory_combo.addItems(factory_list)
            self.factory_combo.setEnabled(True)
            if factory_list:
                self._on_factory_changed(factory_list[0])
        else:
            self.factory_combo.setEnabled(False)

        try:
            if "偏差率" in df.columns:
                df["偏差率"] = pd.to_numeric(df["偏差率"], errors="coerce")
            
            # 通过 data_service 预处理：创建 data_id、恢复已读状态、计算指纹等
            processed_df = self.data_service.preprocess_audit_data(df)
            self.source_model.setDataFrame(processed_df)
            self.view_model.df = processed_df
            self._analysis_params = self.analysis_controller.get_analysis_params()

            import tempfile

            temp_dir = os.path.join(tempfile.gettempdir(), "zpp011_analysis")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(
                temp_dir, f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            df.to_excel(temp_path, sheet_name="完整偏差明细", index=False)
            self._analysis_output_path = temp_path
            
            # 刷新表格显示
            self.table_view.resizeColumnsToContents()
            self.table_view.setColumnWidth(0, 35)
            
            self.statusBar().showMessage(f"分析完成，共加载 {len(df)} 条记录")
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

    def _on_analysis_cancelled_ui(self):
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self.progress_bar.setVisible(False)
        self.progress_label.setText("已取消")
        self.start_btn.setEnabled(True)
        self.log("分析已取消", "info")

    def _on_new_alerts(self, alerts_df):
        """收到新预警，弹窗询问是否查看"""
        count = len(alerts_df)
        reply = QMessageBox.question(
            self,
            "⚠️ 预警通知",
            f"发现 {count} 条新超阈值偏差（替代料），是否查看明细？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            try:
                current_df = self.view_model.df
                if current_df is not None and not current_df.empty and "偏差率(%)" in current_df.columns:
                    if "是否替代料" in current_df.columns:
                        all_alerts = current_df[
                            (current_df["偏差率(%)"].abs() > 10)
                            & (current_df["是否替代料"] == "是")
                        ].copy()
                    else:
                        all_alerts = current_df[current_df["偏差率(%)"].abs() > 10].copy()

                if all_alerts.empty:
                    QMessageBox.information(self, "提示", "没有替代料预警记录")
                    return

                required_cols = [
                    "订单日期", "流程订单", "物料编码", "物料名称", "车间",
                    "定额", "实际", "偏差数量", "净偏差数量", "净偏差金额",
                    "偏差金额", "偏差金额(含税)", "备注原因", "备注",
                    "_read", "data_id",
                ]
                available_cols = [c for c in required_cols if c in all_alerts.columns]
                all_alerts = all_alerts[available_cols]

                if "_read" in all_alerts.columns:
                    all_alerts["状态"] = all_alerts["_read"].map({0: "○ 未读", 1: "✓ 已读"})
                    cols = ["状态"] + [c for c in all_alerts.columns if c != "状态"]
                    all_alerts = all_alerts[cols]

                if "备注" in all_alerts.columns and "备注原因" not in all_alerts.columns:
                    all_alerts["备注原因"] = all_alerts["备注"]

                dialog = AlertDialog(all_alerts, self)
                dialog.exec()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"显示预警失败: {e}")

    def _on_analysis_error_ui(self, error_msg):
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
        self._stop_countdown()
        self.progress_bar.setVisible(False)
        self.progress_label.setText("错误")
        QMessageBox.critical(self, "错误", error_msg)

    # ------------------- AI 审核 UI 回调 -------------------
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
                self.log("警告：AI建议列为空，可能是所有记录偏差率<1%被跳过", "warning")
                QMessageBox.warning(
                    self,
                    "AI审核结果",
                    f"AI审核已完成，但所有记录的AI建议均为空。\n"
                    f"可能原因：\n"
                    f"1. 所有记录偏差率 < 1%，被自动跳过\n"
                    f"2. 所有记录已有备注且偏差率 < 10%\n"
                    f"3. AI客户端调用失败\n\n"
                    f"请检查数据或重试。",
                )
        else:
            self.log("警告：AI建议列不存在", "warning")

        processed_df = self.data_service.preprocess_audit_data(
            updated_df, self.view_model.df
        )
        self.source_model.setDataFrame(processed_df)
        self.view_model.df = processed_df
        self.progress_bar.setVisible(False)
        self.progress_label.setText("就绪")
        if (
            "AI建议" not in updated_df.columns
            or updated_df["AI建议"].replace("", pd.NA).notna().sum() > 0
        ):
            QMessageBox.information(self, "完成", "AI审核已完成")

    def _on_ai_error_ui(self, error_msg):
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
        processed_df = self.data_service.preprocess_audit_data(
            updated_df, self.view_model.df
        )
        self.source_model.setDataFrame(processed_df)
        self.view_model.df = processed_df

    # ------------------- 排序 -------------------
    def _on_sort_indicator_changed(self, logical_index, order):
        """多列联动排序（Ctrl+点击追加排序）"""
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
        """将多列排序应用到 DataFrameModel"""
        if not self.sort_columns:
            return
        if not hasattr(self, "source_model") or self.source_model is None:
            return
        df = self.source_model.getDataFrame()
        if df is None or df.empty:
            return

        sort_args = []
        for col, asc in self.sort_columns:
            if col == 0:
                continue
            if col < 0 or col >= len(df.columns):
                continue
            col_name = df.columns[col]
            sort_args.append((col_name, asc))

        if sort_args:
            cols = [c for c, _ in sort_args]
            asc = [a for _, a in sort_args]
            for c in cols:
                if df[c].dtype == object:
                    df[c] = df[c].apply(
                        lambda x: (
                            x.decode("utf-8", errors="replace")
                            if isinstance(x, bytes)
                            else str(x)
                            if not isinstance(x, str)
                            else x
                        )
                    )
            sort_keys = {}
            for c in cols:
                has_pct = df[c].astype(str).str.contains("%", na=False).any()
                if has_pct:
                    numeric_vals = pd.to_numeric(
                        df[c].astype(str).str.replace("%", "").str.strip(),
                        errors="coerce",
                    ).fillna(0)
                    sort_keys[c] = numeric_vals
            if sort_keys:
                df_sorted = df.sort_values(
                    by=cols,
                    ascending=asc,
                    key=lambda col: sort_keys.get(col.name, col),
                    na_position="last",
                )
            else:
                df_sorted = df.sort_values(by=cols, ascending=asc, na_position="last")
            self.source_model.setDataFrame(df_sorted)

    # ------------------- 文件与目录 -------------------
    def _select_input_file(self):
        default_dir = r"E:\zpp011_dev\ZPP011导出文件原数据"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 SAP Excel 文件", default_dir, "Excel files (*.xlsx *.xls)"
        )
        if file_path:
            self.current_input_file = file_path
            self.input_file_edit.setText(file_path)
            try:
                xl = pd.ExcelFile(file_path)
                sheets = xl.sheet_names
                target = "Data" if "Data" in sheets else sheets[0]
                df = pd.read_excel(file_path, sheet_name=target)
                self.preview_label.setText(
                    f"{os.path.basename(file_path)}\n总行数：{len(df)} 行\n列数：{len(df.columns)} 列"
                )
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
    def _refresh_alt_view(self):
        """刷新左侧替代料表格（从 controller 获取数据）"""
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
        self.alt_table.resizeColumnsToContents()
        self.alt_table.setColumnWidth(0, max(80, self.alt_table.columnWidth(0)))
        self.alt_table.setColumnWidth(2, max(80, self.alt_table.columnWidth(2)))

    def _on_alt_pairs_changed(self):
        """替代料配对变化时：刷新显示 + 重算净偏差"""
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
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入替代料配对",
            "",
            "JSON files (*.json);;Excel files (*.xlsx *.xls)",
        )
        if not file_path:
            return
        if file_path.endswith(".json"):
            if self.alt_controller.import_from_file(file_path, self):
                pass
        else:
            wizard = ImportWizard(
                self,
                self.alt_controller.get_pairs(),
                None,
                on_alt_changed=self._refresh_alt_view,
                on_rules_changed=None,
            )
            wizard.exec()

    def _export_alt_pairs(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出替代料配对", "alt_pairs.json", "JSON (*.json)"
        )
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
        """切换审核表格全屏模式"""
        full = not getattr(self, '_is_fullscreen', False)
        self._is_fullscreen = full
        self.fullscreen_btn.setChecked(full)
        
        if full:
            # 隐藏侧边元素
            self.left_panel.setVisible(False)
            self.progress_group.setVisible(False)
            self.action_group.setVisible(False)
            self.log_group.setVisible(False)
            self.filter_panel.setVisible(False)

            # 强制布局刷新
            QApplication.processEvents()
            self.right_splitter.updateGeometry()

            # 固定合计行高度，确保不被挤压
            self.audit_group.summary_layout.setFixedHeight(40)

            # 确保滚动条显示
            hbar = self.table_view.horizontalScrollBar()
            hbar.show()
            self.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            
            self.fullscreen_btn.setText("⛶ 退出全屏")
            self.statusBar().showMessage("全屏模式 (F11 退出)", 3000)
        else:
            # 恢复所有元素
            self.left_panel.setVisible(True)
            self.progress_group.setVisible(True)
            self.action_group.setVisible(True)
            self.log_group.setVisible(True)
            self.filter_panel.setVisible(True)

            # 恢复合计行动态高度
            self.audit_group.summary_layout.setFixedHeight(-1)
            
            self.fullscreen_btn.setText("⛶ 全屏")
            self.statusBar().showMessage("已退出全屏", 2000)

    # ------------------- 数据加载与表格 -------------------
    def _init_table_model(self):
        """Initialize table model (one-time setup)"""
        self.source_model = DataFrameModel()
        self.proxy_model = AuditProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)

        try:
            self.table_view.selectionModel().selectionChanged.connect(
                self._on_selection_changed
            )
        except Exception:
            pass

        self.source_model.dataChanged.connect(self._update_summary)
        self.source_model.dataChanged.connect(self._refresh_stats_cards)
        self.proxy_model.layoutChanged.connect(self._update_summary)
        self.proxy_model.layoutChanged.connect(self._refresh_stats_cards)
        
        # 连接表头排序信号
        self.table_view.horizontalHeader().sortIndicatorChanged.connect(
            self._on_sort_indicator_changed
        )

        self.table_view.resizeColumnsToContents()
        self.table_view.setColumnWidth(0, 35)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.lock_btn.setChecked(False)
        self.log("Table model initialized", "info")

    def _on_view_model_data_changed(self):
        """ViewModel 数据变化时，刷新所有依赖的 UI 组件"""
        df = self.view_model.df
        if df is None or df.empty:
            self._update_summary()
            self._update_stat_cards(pd.DataFrame())
            self.filter_panel.update_options(pd.DataFrame())
            return

        self._update_summary()
        self._update_stat_cards(df)
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

        self.loading_dialog = LoadingDialog("AI 正在审核，请稍候...", self)
        self.loading_dialog.show()
        QApplication.processEvents()

        self.audit_controller.run_ai_audit(self.view_model.df)

    # ------------------- 右键菜单 -------------------
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
            lambda: self.audit_controller.copy_material_code(
                row_data, self.statusBar().showMessage
            )
        )
        menu.addSeparator()

        menu.addSeparator()
        mark_read_action = menu.addAction("标记为已读")
        mark_read_action.triggered.connect(
            lambda: self.audit_controller.batch_mark_read(
                selected_rows, self.source_model, 1, self.statusBar().showMessage
            )
        )
        mark_unread_action = menu.addAction("标记为未读")
        mark_unread_action.triggered.connect(
            lambda: self.audit_controller.batch_mark_read(
                selected_rows, self.source_model, 0, self.statusBar().showMessage
            )
        )

        menu.addSeparator()
        batch_status = menu.addAction("批量改状态")
        batch_status.triggered.connect(
            lambda: self.audit_controller.batch_change_status(selected_rows, self)
        )
        batch_remark = menu.addAction("批量填备注")
        batch_remark.triggered.connect(
            lambda: self.audit_controller.batch_remark(selected_rows, self)
        )
        batch_export = menu.addAction("批量导出")
        batch_export.triggered.connect(
            lambda: self._batch_export_wrapper(selected_rows)
        )

        menu.addSeparator()
        copy_region_action = menu.addAction("复制选中区域")
        copy_region_action.triggered.connect(self.copy_selected_cells)

        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _batch_export_wrapper(self, rows):
        """批量导出包装方法"""
        df_subset = self.view_model.df.iloc[rows].copy()
        self.audit_controller.batch_export(rows, df_subset, self)

    # ------------------- 其他功能 -------------------
    def _open_rule_config(self):
        rules_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "system", "rules.json"
        )

        def on_rules_changed():
            self.audit_controller.rule_engine.load_rules()
            if self.view_model.df is not None:
                processed_df = self.data_service.preprocess_audit_data(
                    self.view_model.df, self.view_model.df
                )
                self.source_model.setDataFrame(processed_df)
                self.view_model.df = processed_df

        dialog = RuleConfigDialog(
            self, rules_path, self.config_manager, on_rules_changed
        )
        dialog.exec()

    def _open_import_wizard(self):
        rules_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "system", "rules.json"
        )

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

        current_threshold = config.get("alert.threshold_percent", 10.0)
        current_only_alt = config.get("alert.only_alt_materials", True)

        dialog = AlertRuleConfigDialog(self, current_threshold, current_only_alt)
        if dialog.exec() != QDialog.Accepted:
            return

        new_cfg = dialog.get_config()
        try:
            full_config = config._config
            full_config.setdefault("alert", {})
            full_config["alert"]["threshold_percent"] = new_cfg["threshold"]
            full_config["alert"]["only_alt_materials"] = new_cfg["only_alt"]

            cfg_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.dump(full_config, f, allow_unicode=True)

            config.reload()

            if hasattr(self, "alert_monitor"):
                self.alert_monitor.update_config(
                    threshold=new_cfg["threshold"], only_alt=new_cfg["only_alt"]
                )

            if self.proxy_model is not None:
                if hasattr(self.proxy_model, "set_alert_threshold"):
                    self.proxy_model.set_alert_threshold(new_cfg["threshold"])
                self.proxy_model.invalidateFilter()
                self.proxy_model.layoutChanged.emit()

            QMessageBox.information(self, "成功", "预警规则已更新，实时生效。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")

    def _show_history_compare(self):
        dialog = HistoryCompareDialog(self)
        dialog.exec()

    def _open_dashboard(self):
        dialog = DashboardDialog(
            self._get_current_audit_data(), None, self, main_window=self
        )
        dialog.drill_down_signal.connect(self._on_drill_down)
        dialog.exec()

    def _open_source_backup(self):
        """打开历史源码备份目录"""
        import os
        from PySide6.QtWidgets import QMessageBox
        backup_dir = os.path.join(
            os.path.expanduser("~"), ".zpp011_audit", "source_backups"
        )
        if os.path.exists(backup_dir):
            os.startfile(backup_dir)
        else:
            QMessageBox.information(self, "提示", "还没有任何源码备份，请先执行打包操作")

    def _on_factory_changed(self, factory_name):
        """切换工厂，更新表格数据"""
        if not factory_name:
            return
        df = self.analysis_controller.factory_data.get(factory_name)
        if df is not None:
            # 通过 data_service 预处理
            processed_df = self.data_service.preprocess_audit_data(df)
            
            if self.source_model is None:
                from gui_pyside6.models.data_frame_model import DataFrameModel
                from gui_pyside6.models.audit_proxy_model import AuditProxyModel

                self.source_model = DataFrameModel()
                self.proxy_model = AuditProxyModel()
                self.proxy_model.setSourceModel(self.source_model)
                self.table_view.setModel(self.proxy_model)
            self.source_model.setDataFrame(processed_df)
            self.view_model.df = processed_df
            self._update_summary()
            self._update_stat_cards(processed_df)
            self.filter_panel.update_options(processed_df)
            self.statusBar().showMessage(f"已切换到工厂：{factory_name}", 2000)
        else:
            self.statusBar().showMessage(f"工厂 {factory_name} 数据为空", 2000)

    def _get_current_audit_data(self):
        return (
            self.view_model.df.copy()
            if self.view_model.df is not None
            else pd.DataFrame()
        )

    def _on_filter_panel_changed(self, filters: dict):
        """侧边栏筛选条件变化时的处理"""
        if self.proxy_model is None or self.view_model.df is None:
            return
        self.proxy_model.setCustomFilters(filters)
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
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出当前表格", "偏差明细.xlsx", "Excel files (*.xlsx)"
        )
        if file_path:
            try:
                self.view_model.df.to_excel(file_path, index=False)
                QMessageBox.information(self, "成功", f"已导出到 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _show_about(self):
        """显示关于对话框"""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
            QPushButton, QFrame,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("关于 - ZPP011 生产偏差分析器")
        dialog.setMinimumSize(680, 520)
        dialog.setStyleSheet("QDialog { background-color: #F5F5F5; }")
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        about_frame = QFrame()
        about_frame.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2B5EA7, stop:1 #1A3A6B);"
        )
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

        ver_label = QLabel(f"PySide6 迁移版 {get_current_version()}")
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

        date_label = QLabel("更新日期：2026-06-10")
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
## v42.7 (2026-06-10)
### 🐛 修复问题
- 修复 QSS box-shadow 报错（Qt 不支持 box-shadow 属性）
- 修复 QSS 加载失败导致启动报错
- 清理冗余代码，重构 main_window.py 到 ~800 行

## v42.6 (2026-06-08)
### ✨ 新增功能
- MVVM 架构重构
- 多工厂支持
- 预警监控系统
- PPT 生成器专业版美化
        """)
        text_edit.setStyleSheet(
            "border: 1px solid #E0E0E0; border-radius: 6px; padding: 8px;"
        )
        log_layout.addWidget(text_edit)
        main_layout.addWidget(log_frame)

        btn_frame = QFrame()
        btn_frame.setStyleSheet(
            "background-color: #F0F0F0; border-top: 1px solid #E0E0E0;"
        )
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(88, 34)
        close_btn.setStyleSheet(
            "background-color: #2B5EA7; color: white; border-radius: 6px;"
        )
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

    def _refresh_stats_cards(self):
        """刷新统计卡片（从 source_model 取数据计算）"""
        try:
            df = self.source_model.getDataFrame() if self.source_model else None
            self.stats_cards.refresh(df)
        except Exception:
            pass

    def _on_stats_card_clicked(self, card_type: str):
        """处理统计卡片点击事件"""
        if card_type == "anomaly":
            try:
                df = self.source_model.getDataFrame() if self.source_model else None
                if df is not None and not df.empty:
                    # 统计异常条数
                    rate_col = next((c for c in ['偏差率(%)', '偏差率', 'dev_rate'] if c in df.columns), None)
                    if rate_col:
                        rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
                        alt_col = next((c for c in ['是否替代料', 'is_alt', '_替代料组', '替代料组'] if c in df.columns), None)
                        if alt_col and alt_col in df.columns:
                            if alt_col in ['是否替代料', 'is_alt']:
                                is_alt = df[alt_col].astype(str).str.strip().isin(['是', 'True', 'true', '1'])
                                mask = (~is_alt) & (rates.abs() > 30)
                            else:
                                has_alt = df[alt_col].notna() & (df[alt_col].astype(str).str.strip() != '')
                                mask = (~has_alt) & (rates.abs() > 30)
                        else:
                            mask = rates.abs() > 30
                        count = int(mask.sum())
                        self.statusBar().showMessage(f"🔴 真异常 {count} 条（已排除替代料）", 5000)
            except Exception:
                pass

    def _update_summary(self):
        """更新底部合计行（定额、实际、偏差金额、偏差数量）"""
        if self.view_model.df is None or self.view_model.df.empty:
            self.summary_quota.setText("定额: 0.00")
            self.summary_actual.setText("实际: 0.00")
            self.summary_amount.setText("偏差金额: 0.00")
            self.summary_qty.setText("偏差数量: 0.00")
            return
        df = self.view_model.df
        quota_col = next(
            (c for c in ["定额", "数量-定额", "quota"] if c in df.columns), None
        )
        actual_col = next(
            (c for c in ["实际", "数量-实际", "actual"] if c in df.columns), None
        )
        amount_col = next(
            (
                c
                for c in ["净偏差金额", "净偏差", "偏差金额(含税)", "偏差金额", "deviation_amount"]
                if c in df.columns
            ),
            None,
        )
        qty_col = next(
            (c for c in ["偏差数量", "数量偏差", "dev_qty"] if c in df.columns), None
        )
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
        if amount_col in ("净偏差", "净偏差金额"):
            self.summary_amount.setText(f"净偏差(抵消后): {amount_sum:,.2f}")
        else:
            self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")
        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")

    def _recalculate_net_offset(self, silent=False):
        """重算净偏差（基于当前数据重新应用替代料配对）"""
        df = self.view_model.df
        if df is None or df.empty:
            if not silent:
                QMessageBox.warning(self, "提示", "无数据")
            return
        from analysis.net_offset import apply_net_offset

        alt_pairs = self.alt_controller.get_pairs()
        if not alt_pairs:
            if not silent:
                QMessageBox.information(
                    self,
                    "提示",
                    "没有替代料配对，已删除所有配对，净偏差列将恢复为原始值",
                )
            df = df.copy()
            df["净偏差数量"] = df.get("偏差数量", 0)
            if "偏差金额(含税)" in df.columns:
                df["净偏差金额"] = df["偏差金额(含税)"]
            elif "偏差金额" in df.columns:
                df["净偏差金额"] = df["偏差金额"]
            else:
                df["净偏差金额"] = 0
            self.view_model.df = df
            if self.source_model is not None:
                self.source_model.setDataFrame(df)
                self.proxy_model.invalidate()
                self.table_view.resizeColumnsToContents()
            self._on_view_model_data_changed()
            if not silent:
                self.statusBar().showMessage("净偏差已重置为原始值", 2000)
            return
        try:
            new_df = apply_net_offset(df, alt_pairs, group_key=["订单日期", "流程订单"])
            self.view_model.df = new_df
            if self.source_model is not None:
                self.source_model.setDataFrame(new_df)
                self.proxy_model.invalidate()
                self.table_view.resizeColumnsToContents()
            self._on_view_model_data_changed()
            if not silent:
                self.statusBar().showMessage("净偏差已重新计算", 2000)
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "错误", f"重算净偏差失败: {e}")
            else:
                self.log(f"重算净偏差失败: {e}", "error")

    def _update_stat_cards(self, df):
        """更新统计卡片（总记录、偏差>10%、需补备注、已审核）"""
        total = len(df)
        high = (df["偏差率(%)"].abs() > 10).sum() if "偏差率(%)" in df.columns else 0
        if "备注原因" in df.columns:
            need_note = (df["备注原因"].isna() | (df["备注原因"] == "")).sum()
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
        numeric_cols = [
            "定额", "实际", "偏差数量", "偏差金额", "净偏差数量", "净偏差金额",
        ]
        col_sums = {}
        for idx in indexes:
            source_idx = self.proxy_model.mapToSource(idx)
            row = source_idx.row()
            col = source_idx.column()
            if col == 0:
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
            msg = "选中合计：" + " | ".join(
                [f"{k}: {v:,.2f}" for k, v in col_sums.items()]
            )
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().showMessage("选中合计：无有效数值", 2000)

    # ------------------- 取消分析 -------------------
    def _cancel_analysis(self):
        """取消分析和AI审核"""
        cancelled = False
        if (
            self.analysis_controller.worker
            and self.analysis_controller.worker.isRunning()
        ):
            self.analysis_controller.cancel()
            cancelled = True
        if (
            self.audit_controller.ai_worker
            and self.audit_controller.ai_worker.isRunning()
        ):
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
        """批量标记选中行为已读/未读"""
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            self.statusBar().showMessage("请先选中要标记的行", 2000)
            return
        rows = set()
        for idx in selection:
            source_idx = self.proxy_model.mapToSource(idx)
            rows.add(source_idx.row())
        self.audit_controller.batch_mark_read(
            list(rows), self.source_model, is_read, self.statusBar().showMessage
        )

    # ------------------- 复制上一行备注（快捷键） -------------------
    def _copy_previous_remark(self):
        """复制当前选中行的上一行备注到当前行"""
        current = self.table_view.currentIndex()
        if not current.isValid():
            self.statusBar().showMessage("请先选中一行", 2000)
            return
        source_idx = self.proxy_model.mapToSource(current)
        row = source_idx.row()
        self.audit_controller.copy_previous_remark(
            row, self.source_model, self.statusBar().showMessage
        )

    def closeEvent(self, event):
        if (
            self.analysis_controller.worker
            and self.analysis_controller.worker.isRunning()
        ):
            self.analysis_controller.cancel()
        if (
            self.audit_controller.ai_worker
            and self.audit_controller.ai_worker.isRunning()
        ):
            self.audit_controller.cancel_ai_audit()
        if hasattr(self, "alert_monitor") and self.alert_monitor.isRunning():
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
        if hasattr(self, "_countdown_timer") and self._countdown_timer is not None:
            try:
                self._countdown_timer.stop()
            except Exception:
                pass

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
        clipboard_text = "\n".join(lines)

        clipboard = QApplication.clipboard()
        clipboard.setText(clipboard_text)

        self.statusBar().showMessage(f"已复制 {len(rows)} 行 × {len(cols)} 列", 2000)

    def _generate_advanced_report(self):
        """生成详细分析报告(专业版) - 直接从内存DataFrame生成"""
        from core.advanced_ppt_generator_v3 import generate_advanced_report_v3

        if self.view_model.df is None or self.view_model.df.empty:
            QMessageBox.warning(self, "提示", "无数据，请先完成分析")
            return

        output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"ZPP011专业报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx",
        )

        self.log("正在从内存数据生成专业版 PPT 报告...", "info")
        try:
            success = generate_advanced_report_v3(
                output_path=output_path, log_cb=self.log, df=self.view_model.df
            )
            if success:
                self.log(f"专业版报告生成成功：{output_path}", "info")
                reply = QMessageBox.question(
                    self,
                    "生成成功",
                    f"报告已生成：\n{output_path}\n是否打开？",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    os.startfile(output_path)
            else:
                QMessageBox.warning(self, "生成失败", "报告生成失败，请查看日志")
        except Exception as e:
            self.log(f"专业版报告生成失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"生成失败: {e}")

    # ------------------- 表格复制 -------------------
    def _install_table_copy_handler(self):
        """安装 Ctrl+C 复制选中单元格的事件过滤器"""
        tv = self.main_table.table_view
        tv.installEventFilter(self)

    def eventFilter(self, obj, event):
        """事件过滤器：处理 Ctrl+C 复制表格选中区域"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        if obj is self.main_table.table_view and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.matches(QKeySequence.Copy):
                self._copy_selected_cells()
                return True
        return super().eventFilter(obj, event)

    def _copy_selected_cells(self):
        """将表格选中区域复制到剪贴板（TSV 格式，兼容 Excel）"""
        tv = self.main_table.table_view
        model = tv.model()
        selection = tv.selectionModel()
        indexes = selection.selectedIndexes()

        if not indexes:
            return

        # 按 (row, col) 组织选中的单元格
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

        # 构建 TSV 文本（Tab 分隔，Excel 可直接粘贴）
        lines = []
        for r in range(min_row, max_row + 1):
            row_vals = []
            for c in range(min_col, max_col + 1):
                row_vals.append(str(cells.get((r, c), "")))
            lines.append("\t".join(row_vals))

        QApplication.clipboard().setText("\n".join(lines))
        rows = max_row - min_row + 1
        cols = max_col - min_col + 1
        self.statusBar().showMessage(f"已复制 {rows} 行 × {cols} 列", 2000)

    def _on_cell_double_clicked(self, index):
        """双击弹出明细对话框"""
        try:
            if self.proxy_model and self.source_model:
                source_index = self.proxy_model.mapToSource(index)
                row = source_index.row()
                df = self.source_model.getDataFrame()
                if row < len(df):
                    row_data = df.iloc[row]
                    self._show_row_detail(row_data)
        except Exception as e:
            self.log(f"双击弹窗失败: {e}", "error")

    def _show_row_detail(self, row_data):
        """弹出单行明细对话框"""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox,
            QGroupBox, QTextEdit,
        )
        from PySide6.QtCore import Qt

        # ── 列名模糊匹配 ──
        def _val(*keys):
            """按优先级查找列值，支持带空格列名"""
            for k in keys:
                # 精确匹配
                if k in row_data.index:
                    v = row_data[k]
                    if not (v is None or (pd.isna(v) if not isinstance(v, str) else False)):
                        return v
                # 带前后空格的匹配
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
            """创建可选中复制的标签"""
            lbl = QLabel(str(text))
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return lbl

        # ── 基本信息 ──
        gb1 = QGroupBox("基本信息")
        fl1 = QFormLayout(gb1)
        basic_fields = [
            ("工厂", ["工厂", "工厂名称"]),
            ("车间", ["车间"]),
            ("订单日期", ["订单日期"]),
            ("流程订单", ["流程订单"]),
            ("物料编码", ["物料编码", "物料号"]),
            ("物料描述", ["物料描述", "物料名称"]),
            ("物料大类", ["物料大类", "物料类型"]),
        ]
        for label, keys in basic_fields:
            fl1.addRow(f"{label}：", _mk_label(_val(*keys)))
        layout.addWidget(gb1)

        # ── 偏差数据 ──
        gb2 = QGroupBox("偏差数据")
        fl2 = QFormLayout(gb2)
        dev_fields = [
            ("定额用量", ["定额"]),
            ("实际用量", ["实际"]),
            ("偏差数量", ["偏差数量"]),
            ("偏差率", ["偏差率", "偏差率(%)"]),
            ("偏差金额", ["偏差金额"]),
            ("总偏差金额(含税)", ["总偏差金额(含税)", "偏差金额"]),
            ("审核结果", ["审核结果", "audit_result"]),
        ]
        for label, keys in dev_fields:
            val = _val(*keys)
            display = str(val)
            if "偏差率" in label and val:
                try:
                    display = f"{float(val):.2f}%"
                except Exception:
                    pass
            fl2.addRow(f"{label}：", _mk_label(display))
        layout.addWidget(gb2)

        # ── 备注 / AI 建议 ──
        gb3 = QGroupBox("备注与建议")
        fl3 = QFormLayout(gb3)

        remark_label = _mk_label(_val("备注原因", "备注"))
        remark_label.setWordWrap(True)
        fl3.addRow("备注：", remark_label)

        ai_label = _mk_label(_val("AI建议"))
        ai_label.setWordWrap(True)
        ai_label.setStyleSheet("color: #0056b3;")
        fl3.addRow("AI建议：", ai_label)

        remark_src = _val("备注来源")
        if remark_src:
            fl3.addRow("来源：", _mk_label(remark_src))

        layout.addWidget(gb3)

        # ── 按钮 ──
        btn = QDialogButtonBox(QDialogButtonBox.Ok)
        btn.accepted.connect(dialog.accept)
        layout.addWidget(btn)

        dialog.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
