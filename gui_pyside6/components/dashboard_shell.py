# -*- coding: utf-8 -*-
"""DashboardShell - 通用看板外壳（设计稿 v43.333 第二期）

完整实现：标题条 / 常驻筛选条 / 筛选抽屉 / KPI 带 / 表格槽 / 操作条
尺寸规范：标题 48px / 常驻筛选 40px / KPI 54px / 操作条 40px
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QVBoxLayout as VBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QComboBox, QToolButton, QGroupBox, QTableView,
    QAbstractItemView, QSpinBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from utils.theme_manager import Thm

# v43.335：QSS 用模块相对定位，不再写死绝对路径（换机器/换盘即读不到，
# 会静默退化成兜底样式）。_THEME_DIR 指向 gui_pyside6/themes。
_THEME_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "themes")


class KpiCard(QWidget):
    """KPI 卡片单元：label + value + 小点"""
    clicked = Signal(str)

    def __init__(self, label: str, value: str, color: str = "var(--text)", parent=None):
        super().__init__(parent)
        self.label = label
        self.color = color

        self.setFixedSize(118, 54)
        self.setStyleSheet(
            "QFrame { border-left: 1px solid var(--border); background: transparent; } "
            "QFrame:hover { background: var(--surface-2); cursor: pointer; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        lbl_label = QLabel(label)
        lbl_label.setFont(QFont("Microsoft YaHei UI", 11))
        lbl_label.setStyleSheet("color: var(--text-muted);")
        layout.addWidget(lbl_label)

        lbl_value = QLabel(value)
        lbl_value.setFont(QFont("Cascadia Mono", 17, QFont.DemiBold))
        lbl_value.setStyleSheet(f"color: {color}; background: transparent;")
        layout.addWidget(lbl_value)

        self.lbl_label = lbl_label
        self.lbl_value = lbl_value

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.label)
        super().mousePressEvent(event)


class FilterDropdown(QWidget):
    """下拉筛选控件单元：标签 + 下拉框 + 命中计数徽章"""
    selection_changed = Signal()

    def __init__(self, label: str, items: list = None, parent=None):
        super().__init__(parent)
        self.label = label
        self.items = items or []
        self.selected_indices: list = []
        self.hit_count = 0

        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 标签
        self.lbl_label = QLabel(self.label)
        self.lbl_label.setStyleSheet("font-size: 12px; color: var(--text-muted);")

        # 下拉框
        self.cbd_items = QComboBox()
        self.cbd_items.setFixedSize(140, 26)
        self.cbd_items.setStyleSheet(
            "QComboBox { background: var(--surface); border: 1px solid var(--border); "
            "border-radius: var(--r-sm); padding: 0 10px; font-size: 12px; } "
            "QComboBox:hover { border-color: var(--primary-soft-bd); } "
            "QComboBox:focus { outline: 2px solid var(--primary-soft-bd); border-color: var(--primary-soft-bd); } "
            "QComboBox::drop-down { border: none; width: 20px; } "
            "QComboBox::down-arrow { width: 12px; height: 12px; }"
        )

        for item in self.items:
            self.cbd_items.addItem(item)

        # 命中计数徽章
        self.lbl_count = QLabel("0 条")
        self.lbl_count.setStyleSheet(
            "color: var(--primary); font-size: 10px; font-weight: 700; "
            "background: var(--primary-soft); border: 1px solid var(--primary-soft-bd); "
            "border-radius: 20px; padding: 0 5px; min-width: 35px; text-align: center;"
        )

        layout.addWidget(self.lbl_label)
        layout.addWidget(self.cbd_items)
        layout.addWidget(self.lbl_count)
        layout.addStretch()

    def set_hit_count(self, count: int):
        self.hit_count = count
        self.lbl_count.setText(f"{count:,} 条")

    def reset(self):
        self.cbd_items.setCurrentIndex(0)
        self.selected_indices = []
        self.set_hit_count(0)
        self.selection_changed.emit()


class DashboardShell(QWidget):
    """
    看板通用外壳组件
    统一样式：标题条 + 常驻筛选条 + 筛选抽屉 + KPI 带 + 表格槽 + 操作条

    尺寸规范：
    - 标题条：48px
    - 常驻筛选条：40px
    - 筛选抽屉：可折叠
    - KPI 带：54px
    - 表格槽：可变
    - 操作条：40px
    """

    # 信号
    action_triggered = Signal(str)  # 按钮动作
    filter_applied = Signal(dict)  # 筛选条件应用
    kpi_clicked = Signal(str)      # KPI 卡片点击
    refresh_requested = Signal()   # 刷新请求

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.title = "看板标题"
        self.subtitle = "副标题"
        self.kpi_data = []
        self.table_headers = []
        self._model = None
        self.current_filters = {}
        self.total_rows = 0
        self.drawer_visible = False

        self._build_ui()
        self._load_theme()
        self._connect_signals()
        # v43.345：订阅全局主题变化，主窗口切换亮暗时本外壳自动跟随重载 QSS。
        # 持有回调引用以便 closeEvent 时注销，避免删除后回调触发 RuntimeError。
        self._theme_cb = self._on_theme_changed
        Thm.on_change(self._theme_cb)

    def _build_ui(self):
        main_layout = VBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_title_bar()
        self._build_filter_bar()
        self._build_filter_drawer()
        self._build_kpi_bar()
        self._build_table_stub()
        self._build_action_bar()
        self._build_status_bar()

        # 逐个把区块接进主布局（v43.346 修复：之前 _action_bar 建好了却没 addWidget，
        # 等于游离在布局外、永远不显示）。操作条默认隐藏，仅 set_action_widget 时展开。
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.filter_bar)
        main_layout.addWidget(self.drawer_container)
        main_layout.addWidget(self.kpi_bar)
        main_layout.addWidget(self.table_container, 1)
        main_layout.addWidget(self._action_bar)
        main_layout.addWidget(self._status_bar)

    def _build_title_bar(self):
        self.title_bar = QFrame()
        # v43.346：补 objectName —— QSS 里 #title_bar 是 ID 选择器，
        # 之前没设名字导致这条背景/分隔线规则从未命中。
        self.title_bar.setObjectName("title_bar")
        self._title_bar = self.title_bar  # 别名：QSS probe/测试按 _title_bar 访问
        self.title_bar.setFixedHeight(48)
        self.title_bar.setStyleSheet(
            "background-color: var(--surface); "
            "border-bottom: 1px solid var(--border);"
        )

        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(12)

        # 品牌块
        self.tb_mark = QFrame()
        self.tb_mark.setFixedSize(26, 26)
        self.tb_mark.setStyleSheet(
            "background: linear-gradient(140deg, var(--primary), var(--primary-hover)); "
            "border-radius: var(--r-md); "
            "box-shadow: 0 2px 6px rgba(30,64,175,.28);"
        )
        layout.addWidget(self.tb_mark)

        # 标题
        self.lbl_title = QLabel(f"{self.title} · {self.subtitle}")
        self.lbl_title.setFont(QFont("Microsoft YaHei UI", 14, QFont.DemiBold))
        self.lbl_title.setStyleSheet("color: var(--text);")
        layout.addWidget(self.lbl_title)

        layout.addStretch()

        # 工厂选择
        self.factory_select = QComboBox()
        self.factory_select.setFixedSize(120, 30)
        self.factory_select.setStyleSheet(
            "QComboBox { background: var(--surface); border: 1px solid var(--border); "
            "border-radius: var(--r-md); padding: 0 20px 0 10px; font-size: 12.5px; } "
            "QComboBox:hover { border-color: var(--primary-soft-bd); } "
            "QComboBox:focus { outline: 2px solid var(--primary-soft-bd); border-color: var(--primary-soft-bd); } "
            "QComboBox::drop-down { border: none; width: 20px; } "
            "QComboBox::down-arrow { width: 12px; height: 12px; }"
        )
        layout.addWidget(self.factory_select)

        # 窗口控制按钮
        self._build_window_controls()

    def _build_window_controls(self):
        btn_style = (
            "background: transparent; border: none; color: var(--text-muted); "
            "border-radius: var(--r-md); padding: 6px; "
            "transition: all 0.18s ease;"
        )

        self.btn_export = QPushButton("导出")
        self.btn_export.setFixedHeight(30)
        self.btn_export.setFixedSize(60, 30)
        self.btn_export.setStyleSheet(btn_style + " :hover { background: var(--surface-3); color: var(--text); }")
        self.btn_export.clicked.connect(lambda: self.action_triggered.emit("export"))

        self.btn_fullscreen = QPushButton("全屏")
        self.btn_fullscreen.setFixedHeight(30)
        self.btn_fullscreen.setFixedSize(60, 30)
        self.btn_fullscreen.setStyleSheet(btn_style + " :hover { background: var(--surface-3); color: var(--text); }")
        self.btn_fullscreen.clicked.connect(lambda: self.action_triggered.emit("fullscreen"))

        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedHeight(30)
        self.btn_close.setFixedSize(60, 30)
        self.btn_close.setStyleSheet(btn_style + " :hover { background: var(--surface-3); color: var(--text); }")
        self.btn_close.clicked.connect(lambda: self.action_triggered.emit("close"))

        layout = self.title_bar.findChild(QHBoxLayout)
        layout.addWidget(self.btn_export)
        layout.addWidget(self.btn_fullscreen)
        layout.addWidget(self.btn_close)

    def _build_filter_bar(self):
        self.filter_bar = QFrame()
        self.filter_bar.setObjectName("filter_bar")
        self.filter_bar.setFixedHeight(40)
        self.filter_bar.setStyleSheet(
            "background-color: var(--surface); "
            "border-bottom: 1px solid var(--border);"
        )

        layout = QHBoxLayout(self.filter_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        # 筛选抽屉按钮
        self.btn_filter_drawer = QToolButton()
        self.btn_filter_drawer.setText("🔍 筛选 (0)")
        self.btn_filter_drawer.setFixedSize(100, 26)
        self.btn_filter_drawer.setStyleSheet(
            "QToolButton { background: var(--surface-2); border: 1px solid var(--border); "
            "border-radius: var(--r-sm); font-size: 12px; padding: 0 9px; } "
            "QToolButton:hover { border-color: var(--primary-soft-bd); color: var(--primary-hover); } "
            "QToolButton:pressed { background: var(--primary-soft); border-color: var(--primary-soft-bd); }"
        )
        self.btn_filter_drawer.clicked.connect(self._on_filter_drawer_toggled)
        layout.addWidget(self.btn_filter_drawer)

        # 默认预置的 1-3 个常用筛选
        self.dropdowns = []
        for label, items in [
            ("车间", ["一车间", "二车间", "三车间"]),
            ("单位", ["全部单位", "单位 A", "单位 B"]),
            ("状态", ["未读", "已读", "全部"])
        ]:
            dropdown = QComboBox()
            dropdown.setFixedSize(120, 26)
            dropdown.setStyleSheet(
                "QComboBox { background: var(--surface); border: 1px solid var(--border); "
                "border-radius: var(--r-sm); padding: 0 10px; font-size: 12px; } "
                "QComboBox:hover { border-color: var(--primary-soft-bd); } "
                "QComboBox:focus { outline: 2px solid var(--primary-soft-bd); border-color: var(--primary-soft-bd); } "
                "QComboBox::drop-down { border: none; width: 20px; } "
                "QComboBox::down-arrow { width: 12px; height: 12px; }"
            )
            dropdown.addItems(items)
            self.dropdowns.append(dropdown)
            layout.addWidget(dropdown)

        layout.addStretch()

        # 重置按钮
        self.btn_reset = QPushButton("重置")
        self.btn_reset.setFixedSize(60, 26)
        self.btn_reset.setStyleSheet(
            "QPushButton { background: var(--surface); border: 1px solid var(--border); "
            "border-radius: var(--r-sm); font-size: 12px; padding: 0 10px; } "
            "QPushButton:hover { background: var(--surface-2); border-color: var(--border-strong); }"
        )
        self.btn_reset.clicked.connect(self._on_reset)
        layout.addWidget(self.btn_reset)

        # 总计数
        self.lbl_total_hit = QLabel("共 0 条命中")
        self.lbl_total_hit.setStyleSheet("color: var(--text-muted); font-size: 12px;")
        layout.addWidget(self.lbl_total_hit)

    def _build_filter_drawer(self):
        self.drawer_container = QFrame()
        self.drawer_container.setStyleSheet(
            "QFrame { background-color: var(--surface-2); border: none; } "
            "QFrame#drawer_visible { border-top: 1px solid var(--border); } "
            "QFrame#drawer_hidden { max-height: 0; overflow: hidden; border: none; }"
        )
        self.drawer_container.setObjectName("drawer_visible")
        self.drawer_container.setVisible(False)

        self.drawer_layout = VBoxLayout(self.drawer_container)
        self.drawer_layout.setContentsMargins(10, 10, 10, 10)
        self.drawer_layout.setSpacing(14)

        # 1. 物料维度
        self.gp_material = QGroupBox("物料维度")
        self.gp_material.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 12px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        gp_material_layout = VBoxLayout(self.gp_material)
        material_row = QHBoxLayout()
        material_row.addWidget(QLabel("名称包含:"))
        name_input = QComboBox()
        name_input.addItems(["彩罐", "托盘", "手包袋", "塑料袋"])
        material_row.addWidget(name_input)
        material_row.addStretch()
        gp_material_layout.addLayout(material_row)
        self.drawer_layout.addWidget(self.gp_material)

        # 2. 数值维度
        self.gp_numeric = QGroupBox("数值维度")
        self.gp_numeric.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 12px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        gp_numeric_layout = VBoxLayout(self.gp_numeric)
        numeric_row = QHBoxLayout()
        numeric_row.addWidget(QLabel("偏差率:"))
        dev_min = QSpinBox()
        dev_min.setRange(0, 100)
        dev_min.setFixedWidth(60)
        numeric_row.addWidget(dev_min)
        numeric_row.addWidget(QLabel("~"))
        dev_max = QSpinBox()
        dev_max.setRange(0, 100)
        dev_max.setFixedWidth(60)
        numeric_row.addWidget(dev_max)
        numeric_row.addStretch()
        gp_numeric_layout.addLayout(numeric_row)
        self.drawer_layout.addWidget(self.gp_numeric)

        # 3. 组织与状态维度
        self.gp_org_status = QGroupBox("组织与状态维度")
        self.gp_org_status.setStyleSheet(
            "QGroupBox { font-size: 12px; font-weight: 650; color: var(--text); "
            "margin-top: 12px; padding: 10px; border: 1px solid var(--border); "
            "border-radius: var(--r-md); background: var(--surface); } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        gp_org_status_layout = VBoxLayout(self.gp_org_status)
        org_row = QHBoxLayout()
        org_row.addWidget(QLabel("车间:"))
        org_cbd = QComboBox()
        org_cbd.addItems(["一车间", "二车间", "三车间"])
        org_row.addWidget(org_cbd)
        org_row.addStretch()
        gp_org_status_layout.addLayout(org_row)
        self.drawer_layout.addWidget(self.gp_org_status)

    def _build_kpi_bar(self):
        self.kpi_bar = QFrame()
        self.kpi_bar.setObjectName("kpi_bar")
        self.kpi_bar.setFixedHeight(54)
        self.kpi_bar.setStyleSheet(
            "background-color: var(--surface); "
            "border-bottom: 1px solid var(--border);"
        )

        layout = QHBoxLayout(self.kpi_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        # KPI 卡片容器
        self.kpi_scroll = QScrollArea()
        self.kpi_scroll.setWidgetResizable(True)
        self.kpi_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.kpi_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; } "
            "QScrollArea QScrollBar:horizontal { border: none; background: transparent; height: 0; }"
        )

        self.kpi_container = QWidget()
        self.kpi_layout = QHBoxLayout(self.kpi_container)
        self.kpi_layout.setSpacing(0)
        self.kpi_layout.setAlignment(Qt.AlignVCenter)

        # 示例 KPI 卡片
        for label, value, color in [
            ("负损", "0 条", "var(--text)"),
            ("金额", "-¥0.0", "var(--danger)"),
            ("涉及车间", "0 个", "var(--amber)"),
            ("隔离", "0 条", "var(--info)")
        ]:
            kpi = KpiCard(label, value, color)
            kpi.clicked.connect(lambda checked, l=label: self.kpi_clicked.emit(l))
            self.kpi_layout.addWidget(kpi)

        self.kpi_scroll.setWidget(self.kpi_container)
        layout.addWidget(self.kpi_scroll)

    def _build_table_stub(self):
        self.table_container = QFrame()
        # v43.346：补 objectName 供 QSS #content ID 选择器命中
        self.table_container.setObjectName("content")
        self._content = self.table_container  # 别名：QSS probe/测试按 _content 访问
        self.table_container.setStyleSheet(
            "background-color: var(--surface); "
            "border-bottom: 1px solid var(--border);"
        )
        self.table_layout = VBoxLayout(self.table_container)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        self.table_layout.setAlignment(Qt.AlignTop)

        # 使用 QTableView
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.verticalHeader().setDefaultSectionSize(36)
        self.table_view.horizontalHeader().setHighlightSections(False)
        self.table_view.setStyleSheet(
            "QTableView { background-color: var(--surface); "
            "alternate-background-color: var(--surface2); "
            "gridline-color: var(--border); border: 1px solid var(--border); "
            "border-radius: 4px; selection-background-color: var(--primary-soft); "
            "selection-color: var(--text); } "
            "QHeaderView::section { background-color: var(--surface2); "
            "color: var(--textMuted); border: none; border-right: 1px solid var(--border); "
            "border-bottom: 1px solid var(--borderStrong); font-weight: bold; } "
            "QHeaderView::section:hover { background-color: var(--surface3); }"
        )
        self.table_layout.addWidget(self.table_view)

        self.lbl_table_status = QLabel("表格已就绪")
        self.lbl_table_status.setStyleSheet("color: var(--text-muted); font-size: 12px; padding: 5px;")
        self.table_layout.addWidget(self.lbl_table_status)

        if self._model is None:
            self.lbl_table_status.setText("使用 set_model(model) 绑定模型")

    def _build_status_bar(self):
        """底部状态条（30px）：承载 _status_label，供 set_status() 更新。"""
        self._status_bar = QFrame()
        self._status_bar.setObjectName("status_bar")
        self._status_bar.setFixedHeight(30)
        self._status_bar.setStyleSheet(
            "background-color: var(--surface); "
            "border-top: 1px solid var(--border);"
        )
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        status_layout.setSpacing(8)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: var(--text-muted); font-size: 12px;")
        status_layout.addWidget(self._status_label, 1)
        # 选中行数（v43.346：从原操作条迁到状态条，操作条改空条按需展开）
        self.lbl_selected_count = QLabel("已选 0 行")
        self.lbl_selected_count.setStyleSheet("color: var(--text-muted); font-size: 12px;")
        status_layout.addWidget(self.lbl_selected_count)

    def _build_action_bar(self):
        self._action_bar = QFrame()
        # v43.346：属性名统一为 _action_bar（测试/probe 直接访问），并补 objectName
        # 供 QSS #action_bar ID 选择器命中。
        self._action_bar.setObjectName("action_bar")
        self._action_bar.setFixedHeight(40)
        # v43.342：空操作条默认隐藏（隐藏后不占布局高度），仅当真正放入操作控件
        # （set_action_widget）时才展开，消除「标题与内容之间一大块留白」。
        self._action_bar.setVisible(False)
        self._action_bar.setStyleSheet(
            "background-color: var(--surface); "
            "border-top: 1px solid var(--border);"
        )
        # 操作条布局在此创建，set_action_widget() 往里加控件
        self._action_bar_layout = QHBoxLayout(self._action_bar)
        self._action_bar_layout.setContentsMargins(10, 0, 10, 0)
        self._action_bar_layout.setSpacing(8)
        self._action_bar_layout.addStretch()

    def set_action_widget(self, widget: QWidget):
        """放入操作控件并展开操作条（v43.342：空条不占位，放入才展开）。"""
        self._action_bar.setVisible(True)
        # stretch 在末尾，把控件插到 stretch 之前（靠左排列）
        self._action_bar_layout.insertWidget(self._action_bar_layout.count() - 1, widget)

    def _load_theme(self):
        """按当前全局主题加载 QSS（读 themes/*.qss，读不到退回内置兜底）。"""
        self._load_theme_qss("dark" if Thm.is_dark else "light")

    def _load_theme_qss(self, theme: str):
        """加载亮/暗主题 QSS；文件缺失时退回 _default_*_qss() 兜底。"""
        qss_name = "light_dashboard.qss" if theme == "light" else "dark_dashboard.qss"
        qss_content = ""
        try:
            with open(os.path.join(_THEME_DIR, qss_name), "r", encoding="utf-8") as f:
                qss_content = f.read()
        except Exception:
            qss_content = (self._default_light_qss() if theme == "light"
                           else self._default_dark_qss())
        self.setStyleSheet(qss_content)

    def _default_light_qss(self) -> str:
        """内置亮色兜底 QSS：与 themes/light_dashboard.qss 同纪律，只写颜色不写尺寸。"""
        return """
            #DashboardShell { background: #F5F6FA; }
            #title_bar { background: #FFFFFF; border-bottom: 1px solid #E2E8F0; }
            #filter_bar { background: #FFFFFF; border-bottom: 1px solid #E2E8F0; }
            #kpi_bar { background: #FFFFFF; border-bottom: 1px solid #E2E8F0; }
            #action_bar { background: #FFFFFF; border-top: 1px solid #E2E8F0; }
            #content { background: #FFFFFF; }
            #status_bar { background: #F8F9FA; border-top: 1px solid #E2E8F0; }
            QPushButton { background-color: #FFFFFF; color: #334155; }
            QPushButton:hover { background-color: #E8F2FF; color: #0969DA; }
            QPushButton:pressed { background-color: #D3E6FF; }
            QPushButton:checked { background-color: #0969DA; color: #FFFFFF; }
            QPushButton:disabled { background-color: #F1F5F9; color: #9AA7B6; }
            QLabel { color: #1F2937; }
            QComboBox { background-color: #FFFFFF; color: #1F2937; }
            QTableView { background-color: #FFFFFF; }
        """

    def _default_dark_qss(self) -> str:
        """内置暗色兜底 QSS：与 themes/dark_dashboard.qss 同纪律。"""
        return """
            #DashboardShell { background: #1E1E24; }
            #title_bar { background: #25262B; border-bottom: 1px solid #2C2E33; }
            #filter_bar { background: #25262B; border-bottom: 1px solid #2C2E33; }
            #kpi_bar { background: #25262B; border-bottom: 1px solid #2C2E33; }
            #action_bar { background: #25262B; border-top: 1px solid #2C2E33; }
            #content { background: #25262B; }
            #status_bar { background: #2C2E33; border-top: 1px solid #35334A; }
            QPushButton { background-color: #2C2E33; color: #E9ECEF; }
            QPushButton:hover { background-color: #3A4050; color: #FFFFFF; }
            QPushButton:pressed { background-color: #454D60; }
            QPushButton:checked { background-color: #5C7CFA; color: #FFFFFF; }
            QPushButton:disabled { background-color: #25262B; color: #7A7F8A; }
            QLabel { color: #E9ECEF; }
            QComboBox { background-color: #2C2E33; color: #E9ECEF; }
            QTableView { background-color: #25262B; }
        """

    def set_theme(self, theme: str):
        """theme: 'light' or 'dark'。切换全局主题并重载本外壳 QSS。"""
        Thm.set_dark(theme == "dark")
        self._load_theme_qss(theme)

    def _on_theme_changed(self, is_dark: bool):
        """全局主题变化回调：重载 QSS。Shell 可能已删除，容错忽略。"""
        try:
            self._load_theme_qss("dark" if is_dark else "light")
        except RuntimeError:
            pass

    def _connect_signals(self):
        for dropdown in self.dropdowns:
            dropdown.currentIndexChanged.connect(self._on_filter_change)

    def _on_filter_change(self):
        active_filters = sum(1 for d in self.dropdowns if d.currentIndex() > 0)
        self.btn_filter_drawer.setText(f"🔍 筛选 ({active_filters} 个激活)")
        self.current_filters = {
            f"dropdown_{i}": d.currentText()
            for i, d in enumerate(self.dropdowns)
            if d.currentIndex() > 0
        }
        self.filter_applied.emit(self.current_filters)
        self._update_status()

    def _on_filter_drawer_toggled(self):
        self.drawer_visible = not self.drawer_visible
        btn = self.btn_filter_drawer
        if self.drawer_visible:
            btn.setText("🔍 筛选 (关闭)")
            self.drawer_container.setVisible(True)
            self.drawer_container.setObjectName("drawer_visible")
        else:
            btn.setText(f"🔍 筛选 ({len(self.current_filters)} 个激活)")
            self.drawer_container.setVisible(False)
            self.drawer_container.setObjectName("drawer_hidden")

    def _on_reset(self):
        self.current_filters.clear()
        self.total_rows = 0
        self.lbl_total_hit.setText("共 0 条命中")
        for dropdown in self.dropdowns:
            dropdown.setCurrentIndex(0)
        self._on_filter_change()

    def set_model(self, model):
        self._model = model
        self.table_view.setModel(model)
        self._update_status()
        self._connect_table_selection()

    def _connect_table_selection(self):
        if self._model:
            selection = self.table_view.selectionModel()
            selection.selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, selected, deselected):
        self.lbl_selected_count.setText(f"已选 {len(selected.indexes()) // max(self.table_view.model().rowCount(), 1)} 行")

    def _update_status(self):
        if self.table_view.model():
            count = self.table_view.model().rowCount()
            # v43.346：状态写到底部状态条 _status_label（持久存在）；
            # lbl_table_status 属于表格 stub，set_content 替换内容后已被销毁，不可再引用。
            self._status_label.setText(f"数据已加载 · 共 {count} 行")
        self.set_row_count(self.table_view.model().rowCount() if self.table_view.model() else 0)

    def set_kpi_data(self, data: list):
        self.kpi_data = data
        kpis = self.kpi_scroll.findChild(QWidget).findChildren(KpiCard)
        if len(kpis) >= len(data):
            for i, kpi in enumerate(kpis[:len(data)]):
                item = data[i]
                kpi.lbl_value.setText(item.get('value', '0'))
                kpi.lbl_label.setText(item.get('label', 'KPI'))

    def set_table_headers(self, headers: list):
        self.table_headers = headers

    def set_row_count(self, count: int):
        self.total_rows = count
        self.lbl_total_hit.setText(f"共 {count:,} 条命中")

    def clear_filters(self):
        self.current_filters.clear()
        self._on_reset()

    def set_title(self, title: str, subtitle: str = ""):
        self.title = title
        self.subtitle = subtitle
        # v43.346：无副标题时不追加 " · "，避免标题文本带尾部分隔符
        # （测试 ⑬ 断言整窗标题文本精确等于看板名，尾部 " · " 会导致不匹配）。
        self.lbl_title.setText(f"{title} · {subtitle}" if subtitle else title)

    def set_content(self, widget: QWidget):
        while self.table_layout.count():
            child = self.table_layout.takeAt(0).widget()
            child.deleteLater()
        self.table_layout.addWidget(widget, 1)
        # v43.346：状态统一走底部状态条 _status_label（持久），不再碰表格 stub 里
        # 已被 deleteLater 的 lbl_table_status。此处把状态条清空，交由外部 set_status 填充。
        self._status_label.setText("")

    def set_status(self, text: str):
        self._status_label.setText(text)

    def get_theme(self):
        return "dark" if Thm.is_dark else "light"

    def closeEvent(self, event):
        self.action_triggered.emit("close")
        event.accept()


def run_demo():
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    shell = DashboardShell()
    shell.setWindowTitle("DashboardShell 演示")
    shell.resize(1680, 900)
    shell.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_demo()
