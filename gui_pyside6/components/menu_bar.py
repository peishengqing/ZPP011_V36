# -*- coding: utf-8 -*-
"""菜单栏组件"""
from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QAction


class MenuBarComponent:
    """菜单栏组件：创建并设置菜单栏到 MainWindow"""

    def __init__(self, main_window):
        self.mw = main_window
        self._setup()

    def _setup(self):
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
        history_menu.addSeparator()
        source_action = QAction("历史源码", self.mw)
        source_action.triggered.connect(self.mw._open_source_backup)
        history_menu.addAction(source_action)

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
