# -*- coding: utf-8 -*-
"""左侧面板组件 — 暗色主题 260px 设计
包含：文件选择 + 筛选选项（日期范围、物料搜索）+ 替代料配对 + 数据预览
筛选条件由右侧 FilterPanel 独立管理，负责工厂/车间/物料类型等详细筛选
"""
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QComboBox, QDateEdit,
)
from PySide6.QtCore import Qt, QDate


class LeftPanelComponent:
    """左侧面板组件：创建并返回 self.left_panel"""

    def __init__(self, main_window):
        self.mw = main_window
        self.left_panel = self._create_panel()

    def _create_panel(self):
        panel = QWidget()
        panel.setFixedWidth(260)
        panel.setObjectName("leftPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # 1. 文件选择组
        self.file_group = self._create_collapsible_group("文件选择", True)
        self._build_file_selection(self.file_group.body_layout)
        layout.addWidget(self.file_group.container)

        # 2. 筛选选项组（保留用于控制偏差分析日期范围和物料搜索）
        self.filter_group = self._create_collapsible_group("筛选选项", True)
        self._build_filter_options(self.filter_group.body_layout)
        layout.addWidget(self.filter_group.container)

        # 3. 替代料管理组
        self.alt_group = self._create_collapsible_group("替代料配对", True)
        self._build_alternative_materials(self.alt_group.body_layout)
        layout.addWidget(self.alt_group.container)

        # 4. 数据预览组
        self.preview_group = self._create_collapsible_group("数据预览", False)
        self.preview_label = QLabel("未选择文件")
        self.preview_label.setStyleSheet("color: #888780; font-size: 11px; padding: 8px;")
        self.preview_group.body_layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_group.container)

        layout.addStretch()
        return panel

    def _create_collapsible_group(self, title: str, expanded: bool):
        """创建可折叠分组"""
        container = QWidget()
        container.setObjectName("collapsibleContainer")
        container.setStyleSheet("")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部（可点击）
        header = QWidget()
        header.setObjectName("collapsibleHeader")
        header.setStyleSheet("")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        
        title_label = QLabel(title)
        title_label.setObjectName("collapsibleTitle")
        title_label.setStyleSheet("color: #CECBF6; font-size: 12px; font-weight: 600;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        arrow_btn = QPushButton("▼")
        arrow_btn.setObjectName("collapseArrow")
        arrow_btn.setFixedSize(20, 20)
        arrow_btn.setStyleSheet("""
            QPushButton#collapseArrow {
                background: transparent;
                color: #CECBF6;
                font-size: 10px;
                border: none;
            }
            QPushButton#collapseArrow:hover {
                background-color: #3C3489;
                color: #ffffff;
            }
        """)
        arrow_btn.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(arrow_btn)

        # 内容区域
        body = QWidget()
        body.setObjectName("collapsibleBody")
        body.setStyleSheet("")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(10)

        if not expanded:
            body.setVisible(False)
            arrow_btn.setText("▶")

        # 连接折叠逻辑
        def toggle_state():
            is_visible = body.isVisible()
            body.setVisible(not is_visible)
            arrow_btn.setText("▶" if is_visible else "▼")

        header.mousePressEvent = lambda e: toggle_state()  # type: ignore
        layout.addWidget(header)
        layout.addWidget(body)

        class CollapsibleGroup:
            pass
        group = CollapsibleGroup()
        group.container = container
        group.body_layout = body_layout
        return group

    def _build_file_selection(self, layout: QVBoxLayout):
        """构建文件选择表单"""
        # 输入文件
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        input_field = QLineEdit()
        input_field.setMinimumWidth(150)
        input_field.setObjectName("inputFileEdit")
        input_field.setReadOnly(True)
        self.mw.input_file_edit = input_field
        
        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("browseBtn")
        browse_btn.clicked.connect(self.mw._select_input_file)

        input_row.addWidget(input_field, 1)
        input_row.addWidget(browse_btn)

        input_label = QLabel("输入")
        input_label.setObjectName("filterLabel")
        input_label.setStyleSheet("color: #CECBF6; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(input_label)
        layout.addLayout(input_row)

        # 工厂选择
        factory_container = QWidget()
        factory_layout = QVBoxLayout(factory_container)
        factory_layout.setSpacing(4)
        
        factory_label = QLabel("工厂选择")
        factory_label.setObjectName("filterLabel")
        factory_label.setStyleSheet("color: #CECBF6; font-size: 11px;")
        factory_layout.addWidget(factory_label)

        factory_combo = QComboBox()
        factory_combo.setObjectName("factoryCombo")
        factory_layout.addWidget(factory_combo)
        layout.addWidget(factory_container)

        # 输出目录
        output_row = QHBoxLayout()
        output_row.setSpacing(6)

        output_field = QLineEdit()
        output_field.setPlaceholderText("请选择输出目录...")
        output_field.setObjectName("outputDirEdit")
        output_field.setReadOnly(True)
        self.mw.output_dir_edit = output_field
        
        output_browse_btn = QPushButton("浏览")
        output_browse_btn.setObjectName("browseBtn")
        output_browse_btn.clicked.connect(self.mw._select_output_dir)

        output_row.addWidget(output_field)
        output_row.addWidget(output_browse_btn)

        output_label = QLabel("输出")
        output_label.setObjectName("filterLabel")
        output_label.setStyleSheet("color: #CECBF6; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(output_label)
        layout.addLayout(output_row)

    def _build_filter_options(self, layout: QVBoxLayout):
        """构建筛选选项表单（偏差分析日期范围 + 物料搜索）"""
        # 日期范围
        date_label = QLabel("日期范围")
        date_label.setObjectName("filterLabel")
        date_label.setStyleSheet("color: #CECBF6; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(date_label)

        date_row = QHBoxLayout()
        date_row.setSpacing(6)

        self.mw.start_date_edit = QDateEdit()
        self.mw.start_date_edit.setCalendarPopup(True)
        self.mw.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.mw.start_date_edit.setObjectName("startDateEdit")
        self.mw.start_date_edit.setDate(QDate.currentDate().addMonths(-1))

        sep_label = QLabel("-")
        sep_label.setObjectName("dateSep")

        self.mw.end_date_edit = QDateEdit()
        self.mw.end_date_edit.setCalendarPopup(True)
        self.mw.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.mw.end_date_edit.setObjectName("endDateEdit")
        self.mw.end_date_edit.setDate(QDate.currentDate())

        date_row.addWidget(self.mw.start_date_edit)
        date_row.addWidget(sep_label)
        date_row.addWidget(self.mw.end_date_edit)
        layout.addLayout(date_row)

        # 物料搜索
        search_label = QLabel("物料搜索")
        search_label.setObjectName("searchLabel")
        search_label.setStyleSheet("color: #CECBF6; font-size: 11px; margin: 10px 0 4px 0;")
        layout.addWidget(search_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)

        self.mw.material_code_edit = QLineEdit()
        self.mw.material_code_edit.setPlaceholderText("编码")
        self.mw.material_code_edit.setObjectName("materialCodeEdit")

        self.mw.material_name_edit = QLineEdit()
        self.mw.material_name_edit.setPlaceholderText("名称")
        self.mw.material_name_edit.setObjectName("materialNameEdit")

        search_row.addWidget(self.mw.material_code_edit)
        search_row.addWidget(self.mw.material_name_edit)
        layout.addLayout(search_row)

    def _build_alternative_materials(self, layout: QVBoxLayout):
        """构建替代料管理表单"""
        # 计数标签
        self.mw.alt_count_label = QLabel("共 0 对")
        self.mw.alt_count_label.setObjectName("altCountLabel")
        self.mw.alt_count_label.setStyleSheet("color: #CECBF6; font-size: 11px;")
        layout.addWidget(self.mw.alt_count_label)

        # 替代料表格
        self.mw.alt_table = QTableWidget()
        self.mw.alt_table.setColumnCount(3)
        self.mw.alt_table.setHorizontalHeaderLabels(["物料A", " ", "物料B"])
        self.mw.alt_table.setObjectName("altTable")
        self.mw.alt_table.horizontalHeader().setStretchLastSection(True)
        self.mw.alt_table.verticalHeader().setVisible(False)
        self.mw.alt_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mw.alt_table.setDragEnabled(True)
        self.mw.alt_table.setAcceptDrops(True)
        self.mw.alt_table.setDragDropMode(QTableWidget.InternalMove)
        self.mw.alt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mw.alt_table.setAlternatingRowColors(True)
        # 不再内联设置样式，由 QSS 主题统一控制
        self.mw.alt_table.setMaximumHeight(120)
        layout.addWidget(self.mw.alt_table)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        for label, handler in [
            ("添加", self.mw._add_alt_pair),
            ("删除", self.mw._delete_alt_pair),
            ("重置", self.mw._reset_alt_pairs),
            ("导入", self.mw._import_alt_pairs),
            ("导出", self.mw._export_alt_pairs),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("altActionBtn")
            # 样式由 QSS 统一控制
            btn.clicked.connect(handler)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        btn_layout2 = QHBoxLayout()
        btn_layout2.setSpacing(6)
        for label, handler in [("排序", self.mw._sort_alt_pairs), ("放大", self.mw._zoom_alt_table)]:
            btn = QPushButton(label)
            btn.setObjectName("altActionBtn")
            btn.clicked.connect(handler)
            btn_layout2.addWidget(btn)
        btn_layout2.addStretch()
        layout.addLayout(btn_layout2)

    def _create_input_row(self, parent_layout: QVBoxLayout, label_text: str, 
                         placeholder: str, has_browse: bool = False) -> QWidget:
        """创建 label + 输入框行"""
        container = QWidget()
        row_layout = QVBoxLayout(container)
        row_layout.setSpacing(4)
        row_layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label = QLabel(label_text)
        label.setStyleSheet("color: #888780; font-size: 11px;")
        row_layout.addWidget(label)

        # Input + Browse
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setObjectName(f"{label_text.lower()}Input")
        input_field.setStyleSheet("""
            QLineEdit {
                background-color: #2C2C2A;
                color: #EAE8E4;
                border: 1px solid #444441;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #7F77DD;
            }
        """)
        input_row.addWidget(input_field)

        if has_browse:
            browse_btn = QPushButton("浏览")
            browse_btn.setObjectName("browseBtn")
            browse_btn.setStyleSheet("""
                QPushButton#browseBtn {
                    background-color: #7F77DD;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
                    font-size: 11px;
                }
                QPushButton#browseBtn:hover {
                    background-color: #6B63D5;
                }
            """)
            input_row.addWidget(browse_btn)

        row_layout.addLayout(input_row)
        parent_layout.addWidget(container)
        return container
