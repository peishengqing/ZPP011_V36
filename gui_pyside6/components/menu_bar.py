# -*- coding: utf-8 -*-
"""菜单栏组件 — 暗色主题 v43.0
裴哥 2026-06-23
"""
from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QAction


class MenuBarComponent:
    """菜单栏组件：创建并设置菜单栏到 MainWindow"""

    def __init__(self, main_window):
        self.mw = main_window
        self._setup()

    def _setup(self):
        menubar = self.mw.menuBar()
        menubar.setObjectName("menuBar")

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开 Excel", self.mw)
        open_action.triggered.connect(self.mw._select_input_file)
        file_menu.addAction(open_action)

        export_action = QAction("导出当前表格", self.mw)
        export_action.triggered.connect(
            lambda: self.mw.export_controller.export_current_table(
                self.mw.view_model.df, self.mw
            )
        )
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

        refresh_action = QAction("刷新净偏差", self.mw)
        refresh_action.triggered.connect(self.mw._recalculate_net_offset)
        analysis_menu.addAction(refresh_action)

        # 审核菜单
        audit_menu = menubar.addMenu("审核")
        ai_action = QAction("AI 审核", self.mw)
        ai_action.triggered.connect(
            lambda: self.mw.audit_controller.run_ai_audit(self.mw.view_model.df)
        )
        audit_menu.addAction(ai_action)

        mark_read_action = QAction("批量标记已读", self.mw)
        mark_read_action.triggered.connect(
            lambda: self.mw._batch_mark_selected_read(1)
        )
        audit_menu.addAction(mark_read_action)

        mark_unread_action = QAction("批量标记未读", self.mw)
        mark_unread_action.triggered.connect(
            lambda: self.mw._batch_mark_selected_read(0)
        )
        audit_menu.addAction(mark_unread_action)

        audit_menu.addSeparator()
        rule_action = QAction("规则配置", self.mw)
        rule_action.triggered.connect(self.mw._open_rule_config)
        audit_menu.addAction(rule_action)

        alert_action = QAction("🔔 替代料看板", self.mw)
        alert_action.triggered.connect(self.mw._show_alert_dashboard)
        audit_menu.addAction(alert_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        import_action = QAction("模板导入向导", self.mw)
        import_action.triggered.connect(self.mw._show_import_wizard)
        tools_menu.addAction(import_action)

        benefit_action = QAction("效益报告", self.mw)
        benefit_action.triggered.connect(self.mw._show_benefit_report)
        tools_menu.addAction(benefit_action)

        alt_action = QAction("备选料管理", self.mw)
        alt_action.triggered.connect(self.mw._toggle_alt_panel)
        tools_menu.addAction(alt_action)

        tools_menu.addSeparator()
        monitor_action = QAction("监控文件夹自动加载", self.mw)
        monitor_action.setCheckable(True)
        monitor_action.setChecked(True)  # 默认开启
        monitor_action.setObjectName("monitor_action")
        monitor_action.triggered.connect(self.mw._toggle_folder_monitor)
        tools_menu.addAction(monitor_action)

        # 历史菜单
        history_menu = menubar.addMenu("历史")
        compare_action = QAction("历史对比", self.mw)
        compare_action.triggered.connect(self.mw._show_history_compare)
        history_menu.addAction(compare_action)

        dashboard_action = QAction("管理看板", self.mw)
        dashboard_action.triggered.connect(self.mw._show_dashboard)
        history_menu.addAction(dashboard_action)

        source_backup_action = QAction("历史源码", self.mw)
        source_backup_action.triggered.connect(self.mw._show_source_backup)
        history_menu.addAction(source_backup_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self.mw)
        about_action.triggered.connect(self.mw._show_about)
        help_menu.addAction(about_action)

        help_menu.addSeparator()
        health_action = QAction("系统健康检查", self.mw)
        health_action.triggered.connect(self.mw._show_health_check)
        help_menu.addAction(health_action)
