# -*- coding: utf-8 -*-
"""菜单栏组件"""
from PySide6.QtWidgets import QMenuBar, QMenu
from PySide6.QtGui import QAction


class MenuBarComponent:
    """菜单栏组件：负责所有菜单项、工具栏、快捷键的创建"""

    def __init__(self, main_window):
        self.mw = main_window
        self._setup_menu_bar()
        self._setup_controllers()

    def _setup_menu_bar(self):
        """创建菜单栏"""
        menubar = self.mw.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开 Excel", self.mw)
        open_action.triggered.connect(self.mw._select_input_file)
        file_menu.addAction(open_action)

        export_action = QAction("导出当前表格", self.mw)
        export_action.triggered.connect(self.mw._export_current_table)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("退出", self.mw)
        exit_action.triggered.connect(self.mw.close)
        file_menu.addAction(exit_action)

        # 分析菜单
        analysis_menu = menubar.addMenu("分析")
        start_action = QAction("开始分析", self.mw)
        start_action.triggered.connect(self.mw._start_analysis)
        analysis_menu.addAction(start_action)

        # 审核菜单
        audit_menu = menubar.addMenu("审核")
        ai_action = QAction("AI 审核", self.mw)
        ai_action.triggered.connect(self.mw._run_ai_audit)
        audit_menu.addAction(ai_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        rule_action = QAction("规则配置", self.mw)
        rule_action.triggered.connect(self.mw._open_rule_config)
        tools_menu.addAction(rule_action)

        import_action = QAction("模板导入向导", self.mw)
        import_action.triggered.connect(self.mw._open_import_wizard)
        tools_menu.addAction(import_action)

        benefit_action = QAction("效益报告", self.mw)
        benefit_action.triggered.connect(self.mw._show_benefit_report)
        tools_menu.addAction(benefit_action)

        alert_rule_action = QAction("预警规则配置", self.mw)
        alert_rule_action.triggered.connect(self.mw._configure_alert_rules)
        tools_menu.addAction(alert_rule_action)

        # 历史菜单
        history_menu = menubar.addMenu("历史")
        compare_action = QAction("历史对比", self.mw)
        compare_action.triggered.connect(self.mw._show_history_compare)
        history_menu.addAction(compare_action)

        dashboard_action = QAction("管理看板", self.mw)
        dashboard_action.triggered.connect(self.mw._open_dashboard)
        history_menu.addAction(dashboard_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self.mw)
        about_action.triggered.connect(self.mw._show_about)
        help_menu.addAction(about_action)

        help_menu.addSeparator()
        health_action = QAction("系统健康检查", self.mw)
        health_action.triggered.connect(self.mw._show_health_check)
        help_menu.addAction(health_action)

        help_menu.addSeparator()
        advanced_ppt_action = QAction("生成详细分析报告(专业版)", self.mw)
        advanced_ppt_action.triggered.connect(self.mw._generate_advanced_report)
        help_menu.addAction(advanced_ppt_action)

    def _setup_controllers(self):
        """创建所有 Controller（原本在 _setup_menu_bar 末尾）"""
        # AnalysisController
        from gui_pyside6.controllers.analysis_controller import AnalysisController

        self.mw.analysis_controller = AnalysisController(self.mw)
        self.mw.analysis_controller.analysis_started.connect(
            self.mw._on_analysis_ui_start
        )
        self.mw.analysis_controller.progress_updated.connect(
            self.mw._on_analysis_progress_ui
        )
        self.mw.analysis_controller.log_message.connect(self.mw.log)
        self.mw.analysis_controller.analysis_finished.connect(
            self.mw._on_analysis_finished_ui
        )
        self.mw.analysis_controller.analysis_error.connect(
            self.mw._on_analysis_error_ui
        )
        self.mw.analysis_controller.analysis_cancelled.connect(
            self.mw._on_analysis_cancelled_ui
        )

        # AltController
        from gui_pyside6.controllers.alt_controller import AltController

        self.mw.alt_controller = AltController(self.mw)
        self.mw.alt_controller.data_changed.connect(
            self.mw._on_alt_pairs_changed
        )

        # DataService
        from gui_pyside6.services.data_service import DataService

        self.mw.data_service = DataService(alt_controller=self.mw.alt_controller)
        self.mw.data_service.log_signal.connect(self.mw.log)
        self.mw.data_service.log_signal.connect(self.mw._on_data_service_log)

        # AuditController
        from gui_pyside6.controllers.audit_controller import AuditController

        self.mw.audit_controller = AuditController(self.mw)
        self.mw.audit_controller.log_message.connect(self.mw.log)
        self.mw.audit_controller.progress_started.connect(self.mw._on_ai_ui_start)
        self.mw.audit_controller.progress_updated.connect(self.mw._on_ai_progress_ui)
        self.mw.audit_controller.progress_finished.connect(self.mw._on_ai_finished_ui)
        self.mw.audit_controller.progress_error.connect(self.mw._on_ai_error_ui)
        self.mw.audit_controller.audit_data_changed.connect(
            self.mw._on_audit_data_changed
        )

        # ExportController
        from gui_pyside6.controllers.export_controller import ExportController

        self.mw.export_controller = ExportController(self.mw)
        self.mw.export_controller.log_message.connect(self.mw.log)
