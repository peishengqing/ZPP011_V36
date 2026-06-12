# -*- coding: utf-8 -*-
"""主表格区组件：进度条、操作按钮、统计卡片、偏差明细表格"""
        from PySide6.QtWidgets import (
            QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QProgressBar, QTableView, QHeaderView, QWidget,
        )
from PySide6.QtCore import Qt


class MainTableComponent:
    """主表格区组件：分析进度、操作按钮、统计卡片、表格"""

    def __init__(self, main_window):
        self.mw = main_window
        self._create_widgets()

    def _create_widgets(self):
        """创建主表格区的所有控件"""
        # 1. 分析进度
        self.progress_group = QGroupBox("分析进度")
        progress_layout = QVBoxLayout(self.progress_group)
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        # 2. 操作按钮
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

        # 3. 偏差明细与审核
        self.audit_group = QGroupBox("偏差明细与审核")
        audit_layout = QVBoxLayout(self.audit_group)
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
        self.table_view.setSortingEnabled(False)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().sortIndicatorChanged.connect(
            self.mw._on_sort_indicator_changed
        )
        self.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.mw._show_context_menu)

        # 多选模式
        self.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.table_view.setSelectionBehavior(QTableView.SelectItems)

        # 行高 28px
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        audit_layout.addWidget(self.table_view)

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
        unit_summary_btn.clicked.connect(self.mw._show_unit_summary)
        summary_layout.addWidget(unit_summary_btn)

        self.lock_btn = QPushButton("🔒 锁定列宽")
        self.lock_btn.setCheckable(True)
        self.lock_btn.clicked.connect(self.mw._toggle_column_lock)
        summary_layout.addWidget(self.lock_btn)

        self.fullscreen_btn = QPushButton("⛶ 全屏")
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.clicked.connect(self.mw._toggle_table_fullscreen)
        summary_layout.addWidget(self.fullscreen_btn)
        self.summary_layout = summary_layout
        audit_layout.addLayout(summary_layout)

        # 合计行外层的容器，用于控制高度
        self.summary_container = QWidget()
        self.summary_container.setLayout(summary_layout)
        audit_layout.addWidget(self.summary_container)
        self.summary_layout = summary_layout

        # 合计行容器固定高度策略
        self.summary_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.summary_container.setFixedHeight(40)

        # 固定合计行高度，确保始终可见
        self.summary_layout.setContentsMargins(4, 4, 4, 4)
