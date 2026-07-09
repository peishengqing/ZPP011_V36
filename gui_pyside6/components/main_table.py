# -*- coding: utf-8 -*-
"""主表格区组件 — 暗色主题"""
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTableView, QHeaderView,
    QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt

TABLE_STYLESHEET = """
QTableView {
    background-color: #2C2C2A;
    color: #EAE8E4;
    border: none;
    gridline-color: #444441;
    font-family: 'Microsoft YaHei';
    font-size: 11px;
}
QTableView::item { padding: 4px 6px; }
QTableView::item:selected { background-color: #3C3489; color: #EAE8E4; }
QTableView::item:selected:active { background-color: #534AB7; }
QHeaderView::section {
    background-color: #1A1830;
    color: #888780;
    border: none;
    border-bottom: 0.5px solid #444441;
    border-right: 0.5px solid #444441;
    padding: 6px 8px;
    font-family: 'Microsoft YaHei';
    font-size: 11px;
    font-weight: 500;
}
QScrollBar:vertical {
    background-color: #2C2C2A;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #5F5E5A;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #888780;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

PROGRESS_STYLE = """
QProgressBar {
    background-color: #1A1830;
    color: #EAE8E4;
    border: 0.5px solid #444441;
    border-radius: 4px;
    text-align: center;
    font-family: 'Microsoft YaHei';
    font-size: 11px;
    height: 16px;
}
QProgressBar::chunk {
    background-color: #7F77DD;
    border-radius: 3px;
}
"""


class MainTableComponent:
    """主表格区组件：分析进度、操作按钮、统计卡片、表格"""

    def __init__(self, main_window):
        self.mw = main_window
        self._create_widgets()

    def _create_widgets(self):
        # 分析进度
        self.progress_group = QGroupBox("分析进度")
        self.progress_group.setObjectName("statsGroup")
        progress_layout = QVBoxLayout(self.progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_label = QLabel("就绪")
        self.progress_label.setObjectName("progressLabel")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        # 操作按钮
        self.action_group = QGroupBox("")
        self.action_group.setObjectName("actionGroup")
        action_layout = QHBoxLayout(self.action_group)
        action_layout.setContentsMargins(4, 4, 4, 4)
        action_layout.setSpacing(6)

        self.start_btn = QPushButton("开始分析")
        self.start_btn.setObjectName("startBtn")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("cancelBtn")
        self.open_dir_btn = QPushButton("打开目录")
        self.open_dir_btn.setObjectName("openDirBtn")
        self.ppt_btn = QPushButton("生成PPT")
        self.ppt_btn.setObjectName("pptBtn")
        self.excel_btn = QPushButton("导出Excel")
        self.excel_btn.setObjectName("excelBtn")
        self.export_full_btn = QPushButton("导出完整Excel")
        self.export_full_btn.setObjectName("exportFullBtn")
        self.refresh_net_btn = QPushButton("重算净偏差")
        self.refresh_net_btn.setObjectName("refreshNetBtn")

        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.cancel_btn)
        action_layout.addWidget(self.open_dir_btn)
        action_layout.addWidget(self.ppt_btn)
        action_layout.addWidget(self.excel_btn)
        action_layout.addWidget(self.export_full_btn)
        action_layout.addWidget(self.refresh_net_btn)
        action_layout.addStretch()

        # 表格
        self.table_view = QTableView()
        self.table_view.setObjectName("tableView")
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().setSortIndicatorShown(True)
        self.table_view.horizontalHeader().sortIndicatorChanged.connect(self.mw._on_sort_indicator_changed)
        self.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.mw._show_context_menu)
        self.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.table_view.setSelectionBehavior(QTableView.SelectItems)
        self.table_view.verticalHeader().setDefaultSectionSize(28)

        # 合计行（单行）
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(4, 0, 4, 0)
        summary_layout.setSpacing(4)

        self.summary_quota = QLabel("定额: 0")
        self.summary_actual = QLabel("实际: 0")
        self.summary_amount = QLabel("偏差金额: 0")
        self.summary_qty = QLabel("偏差量: 0")
        self.summary_net_rate = QLabel("净偏差率: 0.00%")
        for lbl in [self.summary_quota, self.summary_actual, self.summary_amount, self.summary_qty, self.summary_net_rate]:
            lbl.setObjectName("summaryLabel")
            lbl.setMinimumWidth(0)
        summary_layout.addWidget(self.summary_quota)
        summary_layout.addWidget(self.summary_actual)
        summary_layout.addWidget(self.summary_amount)
        summary_layout.addWidget(self.summary_qty)
        summary_layout.addWidget(self.summary_net_rate)
        summary_layout.addStretch()

        self.unit_summary_btn = QPushButton("单位汇总")
        self.unit_summary_btn.setObjectName("unitSummaryBtn")
        self.unit_summary_btn.clicked.connect(self.mw._show_unit_summary)
        self.unit_summary_btn.setMaximumWidth(80)
        summary_layout.addWidget(self.unit_summary_btn)

        self.lock_btn = QPushButton("🔒")
        self.lock_btn.setCheckable(True)
        self.lock_btn.setObjectName("lockBtn")
        self.lock_btn.setToolTip("锁定/解锁列宽")
        self.lock_btn.setMaximumWidth(32)
        self.lock_btn.clicked.connect(self.mw._toggle_column_lock)
        summary_layout.addWidget(self.lock_btn)

        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.setObjectName("fullscreenBtn")
        self.fullscreen_btn.setToolTip("全屏")
        self.fullscreen_btn.setMaximumWidth(32)
        self.fullscreen_btn.clicked.connect(self.mw._toggle_table_fullscreen)
        summary_layout.addWidget(self.fullscreen_btn)

        self.col_hide_btn = QPushButton("👁")
        self.col_hide_btn.setObjectName("colHideBtn")
        self.col_hide_btn.setToolTip("隐藏列")
        self.col_hide_btn.setMaximumWidth(32)
        self.col_hide_btn.clicked.connect(self.mw._show_column_hide_dialog)
        summary_layout.addWidget(self.col_hide_btn)

        self.summary_container = QWidget()
        self.summary_container.setObjectName("summaryContainer")
        self.summary_container.setLayout(summary_layout)
        self.summary_container.setFixedHeight(28)
        self.summary_container.setMinimumHeight(28)
        self.summary_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 组装：表格区（不含合计栏，合计栏由 main_window 固定在底部）
        audit_layout = QVBoxLayout()
        audit_layout.setContentsMargins(0, 0, 0, 0)
        audit_layout.setSpacing(0)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.table_view, 1)

        audit_layout.addLayout(main_layout, 1)

        self.audit_widget = QWidget()
        self.audit_widget.setLayout(audit_layout)
