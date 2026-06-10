# -*- coding: utf-8 -*-
"""主表格区组件：进度条、操作按钮、统计卡片、偏差明细表格"""
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTableView, QHeaderView,
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
        self.mw.progress_bar = QProgressBar()
        self.mw.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.mw.progress_bar)
        progress_layout.addWidget(self.mw.progress_label)

        # 2. 操作按钮
        self.action_group = QGroupBox("操作")
        action_layout = QHBoxLayout(self.action_group)
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

        # 3. 偏差明细与审核
        self.audit_group = QGroupBox("偏差明细与审核")
        audit_layout = QVBoxLayout(self.audit_group)
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

        # 多选模式
        self.mw.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.mw.table_view.setSelectionBehavior(QTableView.SelectItems)

        # 行高 28px
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
