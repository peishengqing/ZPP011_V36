# -*- coding: utf-8 -*-
"""
Layout 组装器 (LayoutComposer) - 纯 UI 组装，逻辑下沉

负责：MainWindow 的 UI 布局组装，将所有 UI 边框、容器、布局、Widget 创建移动到这里，
让 MainWindow 只保留薄壳状态管理。

目标：替 _assemble_layout 瘦身，将 UI 相关的繁杂操作集中到一个类，逻辑往下沉。

v43.264：操作栏/菜单 emoji → 内联 SVG 线性图标（icons.py），按钮文本去 emoji 前缀。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QToolButton, QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from gui_pyside6.utils.icons import get_icon


def _icon_action(menu: QMenu, icon: str, text: str, handler) -> QAction:
    """带线性图标的菜单项（v43.264 起统一入口，替掉各处的 emoji addAction）"""
    act = QAction(get_icon(icon), text, menu)
    act.triggered.connect(handler)
    menu.addAction(act)
    return act


class LayoutComposer:
    """UI 布局组装器，纯 UI 相关组装逻辑，零业务逻辑."""

    def __init__(self):
        self.compiled = False

    def assemble(self, mw) -> QWidget:
        """组装完整 UI 布局并返回中央 Widgets.

        参数
        ----
        mw : MainWindow
            主窗口对象，持有所有子组件引用（self.title_bar, self.left_panel 等）

        返回
        ----
        central : QWidget
            已设置好所有子布局的中央容器，可直接 setCentralWidget
        """
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 自定义标题栏
        main_layout.addWidget(mw.title_bar)

        # 2. 操作栏（按钮）
        action_bar = self._make_action_bar(mw)
        main_layout.addWidget(action_bar)

        # 3. 主体区域（侧栏 + 数据表格+日志）
        body_area = self._make_body_area(mw)
        main_layout.addWidget(body_area, 1)

        # 将 body_splitter 引用保存到主窗口，供控制器和外部的 _toggle_left_panel/_toggle_filter_panel 访问
        mw.body_splitter = body_area

        self.compiled = True
        return central

    def _make_action_bar(self, mw) -> QWidget:
        """制作操作栏（按钮组）.

        分组顺序：主操作 │ 视图开关 │ 收纳菜单 │ 面板开关/通知 …… 快捷键提示
        v43.264：图标化（SVG 线性图标 + 文字，ToolButtonTextBesideIcon）。
        """
        action_bar = QWidget()
        action_bar.setObjectName("actionBar")
        action_bar.setFixedHeight(38)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(8, 4, 8, 4)
        action_layout.setSpacing(6)

        # ═══ 主操作（高频，平铺 + 强调色）═══
        # 创建分析按钮
        mw.action_btn_analyze = QPushButton("分析")
        mw.action_btn_analyze.setIcon(get_icon("play", 15, "#FFFFFF"))
        mw.action_btn_analyze.setObjectName("actionBtnAnalyze")
        action_layout.addWidget(mw.action_btn_analyze)

        action_layout.addWidget(self._make_separator())
        # ═══ 视图开关（用户常用，按需求保留在工具栏）═══
        # 创建视图开关按钮
        mw.action_btn_left_panel = QToolButton()
        mw.action_btn_left_panel.setIcon(get_icon("panel-left"))
        mw.action_btn_left_panel.setText("左侧栏")
        mw.action_btn_left_panel.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_left_panel.setCheckable(True)
        mw.action_btn_left_panel.setToolTip("切换左侧栏显示")
        mw.action_btn_left_panel.setObjectName("toolGhostBtn")
        action_layout.addWidget(mw.action_btn_left_panel)

        mw.action_btn_filter = QToolButton()
        mw.action_btn_filter.setIcon(get_icon("search"))
        mw.action_btn_filter.setText("筛选")
        mw.action_btn_filter.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_filter.setCheckable(True)
        mw.action_btn_filter.setToolTip("切换筛选面板")
        mw.action_btn_filter.setObjectName("toolGhostBtn")
        action_layout.addWidget(mw.action_btn_filter)

        mw.action_btn_col_filter = QToolButton()
        mw.action_btn_col_filter.setIcon(get_icon("funnel-lines"))
        mw.action_btn_col_filter.setText("列头筛选")
        mw.action_btn_col_filter.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_col_filter.setCheckable(True)
        mw.action_btn_col_filter.setToolTip("列头取值过滤模式")
        mw.action_btn_col_filter.setObjectName("toolGhostBtn")
        action_layout.addWidget(mw.action_btn_col_filter)

        action_layout.addWidget(self._make_separator())
        # ═══ 收纳菜单：看板 / 导出 / 维护 ═══
        # 创建菜单按钮
        mw.action_btn_boards = QToolButton()
        mw.action_btn_boards.setObjectName("actionMenuBtn")
        mw.action_btn_boards.setIcon(get_icon("chart"))
        mw.action_btn_boards.setText("看板")
        mw.action_btn_boards.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_boards.setToolTip("打开看板")

        # 为看板按钮添加下拉菜单
        mw.action_btn_boards.setPopupMode(QToolButton.MenuButtonPopup)
        boards_menu = QMenu(mw)
        _icon_action(boards_menu, "bell", "替代料看板", lambda: mw._show_alert_dashboard())
        _icon_action(boards_menu, "alert", "偏差率预警", lambda: mw._show_deviation_warning_dialog())
        _icon_action(boards_menu, "trending-down", "负损看板", lambda: mw._show_neg_loss_dashboard())
        _icon_action(boards_menu, "trending-up", "正损看板", lambda: mw._show_pos_loss_dashboard())
        _icon_action(boards_menu, "lock", "隔离区", lambda: mw._open_quarantine_dialog())
        _icon_action(boards_menu, "clipboard", "数据稳定性", lambda: mw._show_data_stability_dashboard())
        _icon_action(boards_menu, "link", "替代料长链", lambda: mw._show_alt_chain_dashboard())
        _icon_action(boards_menu, "box", "半成品看板", lambda: mw._show_semi_dashboard())
        mw.action_btn_boards.setMenu(boards_menu)
        action_layout.addWidget(mw.action_btn_boards)

        mw.action_btn_export = QToolButton()
        mw.action_btn_export.setObjectName("actionMenuBtn")
        mw.action_btn_export.setIcon(get_icon("download"))
        mw.action_btn_export.setText("导出")
        mw.action_btn_export.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_export.setToolTip("导出当前表格")

        # 为导出按钮添加下拉菜单
        export_menu = QMenu(mw)
        _icon_action(export_menu, "file-text", "导出当前表格",
                     lambda: mw.export_controller.export_current_table(mw.view_model.df, mw))
        _icon_action(export_menu, "table", "导出完整偏差", lambda: mw._on_export_full_excel())
        mw.action_btn_export.setMenu(export_menu)
        mw.action_btn_export.setPopupMode(QToolButton.MenuButtonPopup)
        action_layout.addWidget(mw.action_btn_export)

        mw.action_btn_maint = QToolButton()
        mw.action_btn_maint.setObjectName("actionMenuBtn")
        mw.action_btn_maint.setIcon(get_icon("sliders"))
        mw.action_btn_maint.setText("维护")
        mw.action_btn_maint.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_maint.setToolTip("维护工具")
        # 维护按钮改为下拉菜单（自动隔离规则 + 物料画像）
        mw.action_btn_maint.setPopupMode(QToolButton.MenuButtonPopup)
        maint_menu = QMenu(mw)
        _icon_action(maint_menu, "shield", "自动隔离规则", lambda: mw._open_auto_quarantine_rule_dialog())
        _icon_action(maint_menu, "id-card", "物料画像", lambda: mw._show_material_profile())
        mw.action_btn_maint.setMenu(maint_menu)
        action_layout.addWidget(mw.action_btn_maint)

        action_layout.addWidget(self._make_separator())
        # ═══ 面板开关 + 通知（低频，保留平铺，置于分组尾端）═══
        # 创建面板开关按钮
        mw.action_btn_toggle_stats = QToolButton()
        mw.action_btn_toggle_stats.setIcon(get_icon("gauge"))
        mw.action_btn_toggle_stats.setText("概览")
        mw.action_btn_toggle_stats.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_toggle_stats.setCheckable(True)
        mw.action_btn_toggle_stats.setChecked(True)
        mw.action_btn_toggle_stats.setToolTip("切换概览面板")
        mw.action_btn_toggle_stats.setObjectName("toolGhostBtn")
        action_layout.addWidget(mw.action_btn_toggle_stats)

        mw.action_btn_toggle_progress = QToolButton()
        mw.action_btn_toggle_progress.setIcon(get_icon("zap"))
        mw.action_btn_toggle_progress.setText("进度")
        mw.action_btn_toggle_progress.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_toggle_progress.setCheckable(True)
        mw.action_btn_toggle_progress.setChecked(True)
        mw.action_btn_toggle_progress.setToolTip("切换分析进度")
        mw.action_btn_toggle_progress.setObjectName("toolGhostBtn")
        action_layout.addWidget(mw.action_btn_toggle_progress)

        mw.action_btn_unread_summary = QToolButton()
        mw.action_btn_unread_summary.setIcon(get_icon("megaphone"))
        mw.action_btn_unread_summary.setText("未读")
        mw.action_btn_unread_summary.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_unread_summary.setToolTip("未读汇总")
        mw.action_btn_unread_summary.setObjectName("toolGhostBtn")
        action_layout.addWidget(mw.action_btn_unread_summary)

        # 自动隔离规则按钮（ARC-003 第七刀，需额外创建）
        mw.action_btn_auto_q = QToolButton()
        mw.action_btn_auto_q.setIcon(get_icon("shield"))
        mw.action_btn_auto_q.setText("自动隔离")
        mw.action_btn_auto_q.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_auto_q.setToolTip("按规则自动移入隔离区")
        mw.action_btn_auto_q.setObjectName("toolGhostBtn")
        action_layout.addWidget(mw.action_btn_auto_q)

        action_layout.addStretch()
        shortcut_hint = QLabel("F5:分析 | F6:导出 | F7:效益 | F11:全屏")
        shortcut_hint.setObjectName("shortcutHint")
        action_layout.addWidget(shortcut_hint)

        # 底部按钮行已删除，start_btn 别名指向顶部工具栏分析按钮（供分析起止启用/禁用）
        mw.start_btn = mw.action_btn_analyze

        return action_bar

    def _make_separator(self) -> QWidget:
        """制作工具栏分隔符."""
        w = QWidget()
        w.setObjectName("toolbarSep")
        w.setFixedWidth(1)
        w.setFixedHeight(20)
        return w

    def _make_body_area(self, mw) -> QWidget:
        """制作主体区域（侧栏 + 表格 + 日志）."""
        body_splitter = QSplitter(Qt.Horizontal)

        # 左侧面板
        body_splitter.addWidget(mw.left_panel)

        # 右侧筛选面板（FilterPanel）
        body_splitter.addWidget(mw.filter_panel)
        mw.filter_panel.setVisible(False)  # 默认隐藏

        # 右侧：审核表格 + 日志面板
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        # 上半部分：本次分析概览 + 分析进度（用户可拖动，默认占较小空间）
        top_panel = QWidget()
        top_panel.setObjectName("topPanel")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        top_layout.addWidget(mw.stats_cards)                # 本次分析概览
        top_layout.addWidget(mw.main_table.progress_group)  # 分析进度
        top_panel.setMaximumHeight(260)                       # 限制最大高度，不抢表格空间

        # 将 top_panel 引用保存到主窗口，以便控制器访问
        mw.top_panel = top_panel

        # 垂直分割器：仅表格（运行日志已移除，空间全部给表格）
        _v_splitter = QSplitter(Qt.Vertical)
        _v_splitter.setChildrenCollapsible(True)
        _v_splitter.addWidget(mw.main_table.audit_widget)
        _v_splitter.setStretchFactor(0, 1)

        # 右侧整体垂直分割器：上面概览/进度，下面表格
        _right_v_splitter = QSplitter(Qt.Vertical)
        _right_v_splitter.setChildrenCollapsible(True)
        _right_v_splitter.addWidget(top_panel)
        _right_v_splitter.addWidget(_v_splitter)
        _right_v_splitter.setSizes([175, 625])   # v43.264：顶部给 KPI 条留够高度（否则卡片被压扁）
        _right_v_splitter.setStretchFactor(0, 0)
        _right_v_splitter.setStretchFactor(1, 1)

        right_layout.addWidget(_right_v_splitter, 1)
        right_layout.addWidget(mw.main_table.summary_container, 0)

        body_splitter.addWidget(right_container)
        body_splitter.setSizes([260, 440, 860])

        return body_splitter
