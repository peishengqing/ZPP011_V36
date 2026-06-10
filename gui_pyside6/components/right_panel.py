# -*- coding: utf-8 -*-
"""右侧面板组件：进度、按钮、表格、统计、合计行、日志"""
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, QTableView,
    QHeaderView, QScrollArea, QTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction


class RightPanelComponent:
    """右侧面板组件：创建并返回 self.right_container"""

    def __init__(self, main_window):
        self.mw = main_window
        self.right_container = self._create_container()

    def _create_container(self):
        right_container = QWidget()
        right_container_layout = QVBoxLayout(right_container)
        right_container_layout.setContentsMargins(6, 6, 6, 6)

        # 右侧内部面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(4)

        # 1. 分析进度
        self.mw.progress_group = QGroupBox("分析进度")
        progress_layout = QVBoxLayout(self.mw.progress_group)
        self.mw.progress_bar = QProgressBar()
        self.mw.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.mw.progress_bar)
        progress_layout.addWidget(self.mw.progress_label)
        right_layout.addWidget(self.mw.progress_group)

        # 2. 操作按钮
        self.mw.action_group = QGroupBox("操作")
        action_layout = QHBoxLayout(self.mw.action_group)
        self.mw.start_btn = QPushButton("开始分析")
        self.mw.cancel_btn = QPushButton("取消")
        self.mw.open_dir_btn = QPushButton("打开目录")
        self.mw.ppt_btn = QPushButton("生成PPT")
        self.mw.excel_btn = QPushButton("生成表格")
        self.mw.export_full_btn = QPushButton("导出完整Excel")
        self.mw.refresh_net_btn = QPushButton("重算净偏差")
        action_layout.addWidget(self.mw.start_btn)
        action_layout.addWidget(self.mw.cancel_btn)
        action_layout.addWidget(self.mw.open_dir_btn)
        action_layout.addWidget(self.mw.ppt_btn)
        action_layout.addWidget(self.mw.excel_btn)
        action_layout.addWidget(self.mw.export_full_btn)
        action_layout.addWidget(self.mw.refresh_net_btn)
        right_layout.addWidget(self.mw.action_group)

        # 3. 偏差明细与审核
        self.mw.audit_group = QGroupBox("偏差明细与审核")
        audit_layout = QVBoxLayout(self.mw.audit_group)
        audit_layout.setSpacing(4)
        audit_layout.setContentsMargins(6, 6, 6, 6)

        # 统计卡片
        stat_layout = QHBoxLayout()
        self.mw.stat_total = QLabel("0")
        self.mw.stat_high = QLabel("0")
        self.mw.stat_need_note = QLabel("0")
        self.mw.stat_ok = QLabel("0")
        stat_layout.addWidget(QLabel("总记录:"))
        stat_layout.addWidget(self.mw.stat_total)
        stat_layout.addWidget(QLabel("偏差>10%:"))
        stat_layout.addWidget(self.mw.stat_high)
        stat_layout.addWidget(QLabel("需补备注:"))
        stat_layout.addWidget(self.mw.stat_need_note)
        stat_layout.addWidget(QLabel("已审核:"))
        stat_layout.addWidget(self.mw.stat_ok)
        stat_layout.addStretch()
        audit_layout.addLayout(stat_layout)

        # 表格
        self.mw.table_view = QTableView()
        self.mw.table_view.setAlternatingRowColors(True)
        self.mw.table_view.setSortingEnabled(False)
        self.mw.table_view.horizontalHeader().setStretchLastSection(False)
        self.mw.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.mw.table_view.horizontalHeader().sortIndicatorChanged.connect(
            self.mw._on_sort_indicator_changed
        )
        self.mw.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mw.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mw.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mw.table_view.customContextMenuRequested.connect(self.mw._show_context_menu)

        self.mw.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.mw.table_view.setSelectionBehavior(QTableView.SelectItems)

        copy_action = QAction("复制", self.mw.table_view)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.mw.copy_selected_cells)
        self.mw.table_view.addAction(copy_action)

        self.mw.table_view.verticalHeader().setDefaultSectionSize(28)
        audit_layout.addWidget(self.mw.table_view, 1)

        # 合计行
        summary_layout = QHBoxLayout()
        self.mw.summary_quota = QLabel("定额: 0.00")
        self.mw.summary_actual = QLabel("实际: 0.00")
        self.mw.summary_amount = QLabel("偏差金额: 0.00")
        self.mw.summary_qty = QLabel("偏差数量: 0.00")
        summary_layout.addWidget(self.mw.summary_quota)
        summary_layout.addWidget(self.mw.summary_actual)
        summary_layout.addWidget(self.mw.summary_amount)
        summary_layout.addWidget(self.mw.summary_qty)
        summary_layout.addStretch()
        unit_summary_btn = QPushButton("单位汇总")
        unit_summary_btn.clicked.connect(self.mw._show_unit_summary)
        summary_layout.addWidget(unit_summary_btn)
        self.mw.lock_btn = QPushButton("🔒 锁定列宽")
        self.mw.lock_btn.setCheckable(True)
        self.mw.lock_btn.clicked.connect(self.mw._toggle_column_lock)
        summary_layout.addWidget(self.mw.lock_btn)
        self.mw.fullscreen_btn = QPushButton("⛶ 全屏")
        self.mw.fullscreen_btn.setCheckable(True)
        self.mw.fullscreen_btn.clicked.connect(self.mw._toggle_table_fullscreen)
        summary_layout.addWidget(self.mw.fullscreen_btn)
        audit_layout.addLayout(summary_layout)

        right_container_layout.addWidget(self.mw.audit_group)

        # 4. 运行日志
        self.mw.log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(self.mw.log_group)
        self.mw.log_text = QTextEdit()
        self.mw.log_text.setReadOnly(True)
        self.mw.log_text.setFixedHeight(400)
        log_layout.addWidget(self.mw.log_text)
        right_layout.addWidget(self.mw.log_group)

        # 用 QScrollArea 包裹
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right_panel)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_layout.addWidget(right_scroll, 1)

        return right_container
