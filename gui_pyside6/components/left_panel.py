# -*- coding: utf-8 -*-
"""左侧面板组件：文件选择、工厂选择、日期、物料、替代料配对、数据预览"""
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QComboBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction


class LeftPanelComponent:
    """左侧面板组件：创建并返回 self.left_panel"""

    def __init__(self, main_window):
        self.mw = main_window
        self.left_panel = self._create_panel()

    def _create_panel(self):
        panel = QWidget()
        panel.setFixedWidth(360)
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        # 1. 文件选择
        file_group = QGroupBox("📁 文件选择")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(4)

        # 输入文件
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("输入:"))
        self.mw.input_file_edit = QLineEdit()
        self.mw.input_file_edit.setReadOnly(True)
        row1.addWidget(self.mw.input_file_edit, 1)
        browse_input_btn = QPushButton("浏览")
        browse_input_btn.clicked.connect(self.mw._select_input_file)
        row1.addWidget(browse_input_btn)
        file_layout.addLayout(row1)

        # 工厂选择
        factory_group = QGroupBox("🏭 工厂选择")
        factory_layout = QVBoxLayout(factory_group)
        self.mw.factory_combo = QComboBox()
        self.mw.factory_combo.setEnabled(False)
        self.mw.factory_combo.currentTextChanged.connect(self.mw._on_factory_changed)
        factory_layout.addWidget(self.mw.factory_combo)
        file_layout.addWidget(factory_group)

        # 输出目录
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("输出:"))
        self.mw.output_dir_edit = QLineEdit()
        self.mw.output_dir_edit.setReadOnly(True)
        row2.addWidget(self.mw.output_dir_edit, 1)
        browse_output_btn = QPushButton("浏览")
        browse_output_btn.clicked.connect(self.mw._select_output_dir)
        row2.addWidget(browse_output_btn)
        file_layout.addLayout(row2)

        layout.addWidget(file_group)

        # 2. 筛选选项
        filter_group = QGroupBox("🔍 筛选选项（可选）")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(4)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("开始:"))
        self.mw.start_date_edit = QLineEdit()
        self.mw.start_date_edit.setPlaceholderText("例：2026-04-01")
        date_row.addWidget(self.mw.start_date_edit, 1)
        date_row.addWidget(QLabel("结束:"))
        self.mw.end_date_edit = QLineEdit()
        self.mw.end_date_edit.setPlaceholderText("例：2026-04-30")
        date_row.addWidget(self.mw.end_date_edit, 1)
        filter_layout.addLayout(date_row)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("物料:"))
        self.mw.material_search_edit = QLineEdit()
        self.mw.material_search_edit.setPlaceholderText("编码/名称")
        search_row.addWidget(self.mw.material_search_edit, 1)
        filter_layout.addLayout(search_row)

        layout.addWidget(filter_group)

        # 3. 替代料配对
        alt_group = QGroupBox("替代料配对")
        alt_layout = QVBoxLayout(alt_group)
        self.mw.alt_count_label = QLabel("共 0 对")
        alt_layout.addWidget(self.mw.alt_count_label)

        self.mw.alt_table = QTableWidget()
        self.mw.alt_table.setColumnCount(3)
        self.mw.alt_table.setHorizontalHeaderLabels(["物料A", " ", "物料B"])
        self.mw.alt_table.horizontalHeader().setStretchLastSection(True)
        self.mw.alt_table.verticalHeader().setVisible(False)
        self.mw.alt_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mw.alt_table.setDragEnabled(True)
        self.mw.alt_table.setAcceptDrops(True)
        self.mw.alt_table.setDragDropMode(QTableWidget.InternalMove)
        self.mw.alt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mw.alt_table.model().rowsMoved.connect(self.mw._on_alt_rows_moved)
        alt_layout.addWidget(self.mw.alt_table)

        alt_btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.mw._add_alt_pair)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self.mw._delete_alt_pair)
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.mw._reset_alt_pairs)
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self.mw._import_alt_pairs)
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self.mw._export_alt_pairs)
        zoom_btn = QPushButton("🔍 放大")
        zoom_btn.clicked.connect(self.mw._zoom_alt_table)
        sort_btn = QPushButton("排序")
        sort_btn.clicked.connect(self.mw._sort_alt_pairs)
        alt_btn_layout.addWidget(add_btn)
        alt_btn_layout.addWidget(del_btn)
        alt_btn_layout.addWidget(reset_btn)
        alt_btn_layout.addWidget(import_btn)
        alt_btn_layout.addWidget(export_btn)
        alt_btn_layout.addWidget(sort_btn)
        alt_btn_layout.addWidget(zoom_btn)
        alt_layout.addLayout(alt_btn_layout)

        layout.addWidget(alt_group)

        # 4. 数据预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        self.mw.preview_label = QLabel("未选择文件")
        self.mw.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.mw.preview_label)
        layout.addWidget(preview_group)

        layout.addStretch()
        return panel
