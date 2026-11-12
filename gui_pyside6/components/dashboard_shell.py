# -*- coding: utf-8 -*-
"""DashboardShell - 通用看板外壳（设计稿 v43.333 第二期）

完整实现：标题条 / 常驻筛选条 / 筛选抽屉 / KPI 带 / 表格槽 / 操作条
尺寸规范：标题 48px / 常驻筛选 40px / KPI 54px / 操作条 40px

样式只有一个来源：``themes/tokens.build_dashboard_qss()``。本文件不再写任何
``setStyleSheet``——v43.346 之前这里散落着 70 多处 ``var(--token)``，那是设计稿
HTML 的 CSS 变量写法，Qt QSS 不认识，整条声明被静默丢弃，只剩 padding /
font-size / ``::drop-down { border: none }`` 这些"碰巧合法"的片段生效，
结果是下拉箭头消失、筛选控件尺寸被内距改写。控件侧只留 objectName 与
dynamic property 挂钩。
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QVBoxLayout as VBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QToolButton, QGroupBox, QTableView,
    QAbstractItemView
)
from PySide6.QtCore import Qt, Signal

from gui_pyside6.themes.tokens import SIZE_PX, build_dashboard_qss, ui_font
from gui_pyside6.utils.row_number_gutter import enable_row_numbers
from utils.theme_manager import Thm

from collections import namedtuple

# 外壳替每个筛选控件记的三件套：控件本体、标签、命中徽章（常驻条没有徽章）
_FilterSlot = namedtuple("_FilterSlot", "widget label badge zone")


def pack_row(widgets):
    """把一组同行控件（如「全部/是/否」三态按钮）装进一个横向容器。

    抽屉一行只放得下一个控件，而看板里的三态按钮、颜色勾选组天然是"一组"。
    addWidget 会自动 reparent，容器随后交给外壳，原来那块自建布局即可销毁。
    """
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    for w in widgets:
        row.addWidget(w)
    row.addStretch()
    return box


class KpiCard(QWidget):
    """KPI 卡片单元：小标签 + 数值。数值颜色用 status 动态属性挂钩（5.1 纪律）。"""
    clicked = Signal(str)

    def __init__(self, label: str, value: str, status: str = "", parent=None):
        super().__init__(parent)
        self.label = label
        self.status = status

        self.setFixedSize(118, 54)
        self.setProperty("kpiCard", True)   # → QSS QWidget[kpiCard="1"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        lbl_label = QLabel(label)
        lbl_label.setProperty("kpiLabel", True)
        layout.addWidget(lbl_label)

        lbl_value = QLabel(value)
        lbl_value.setProperty("kpiValue", True)
        if status:
            lbl_value.setProperty("status", status)
        layout.addWidget(lbl_value)

        self.lbl_label = lbl_label
        self.lbl_value = lbl_value

    def set_status(self, status: str):
        """改数值语义色：重设 status 属性后必须重新抛光，QSS 才会重算。"""
        self.status = status
        self.lbl_value.setProperty("status", status)
        self.lbl_value.style().unpolish(self.lbl_value)
        self.lbl_value.style().polish(self.lbl_value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.label)
        super().mousePressEvent(event)


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

    # 常驻筛选条里的看板控件上限（加外壳自己的抽屉按钮/重置/总命中 = 6，设计稿 4.3.1）
    MAX_PERSISTENT_FILTERS = 5
    # 抽屉分组固定顺序与标题（设计稿：物料维度 / 数值维度 / 组织与状态维度）
    _GROUP_TITLES = {"material": "物料维度", "numeric": "数值维度", "org": "组织与状态维度"}

    # 信号
    action_triggered = Signal(str)  # 标题条窗口按钮（export / fullscreen / close）
    kpi_clicked = Signal(str)       # KPI 卡片点击（下钻入口）

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        # QSS 里 #DashboardShell 是 ID 选择器，此前一直没设 objectName，也没开
        # WA_StyledBackground —— 自定义 QWidget 子类不开这个属性，QSS 的
        # background 根本不画，外壳底色（各区之间的那几道缝）在暗色下留成原生亮色。
        self.setObjectName("DashboardShell")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.title = "看板标题"
        self.subtitle = "副标题"
        self._model = None
        self.drawer_visible = False

        self._build_ui()
        self._load_theme()
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
        self.title_bar.setFixedHeight(SIZE_PX["titleBar"])

        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(12)

        # 品牌块
        self.tb_mark = QFrame()
        self.tb_mark.setObjectName("tb_mark")
        self.tb_mark.setFixedSize(26, 26)
        layout.addWidget(self.tb_mark)

        # 标题
        self.lbl_title = QLabel(f"{self.title} · {self.subtitle}")
        self.lbl_title.setFont(ui_font(14, bold=True))
        layout.addWidget(self.lbl_title)

        layout.addStretch()

        # 窗口控制按钮（改造前这里还挂着一个空的「工厂」下拉，既无选项也无接线，
        # 每个看板标题条右侧都多出一个灰空的控件；工厂筛选本就在各看板自己的筛选条里）
        self._build_window_controls()

    def _build_window_controls(self):
        for attr, text, action in (
            ("btn_export", "导出", "export"),
            ("btn_fullscreen", "全屏", "fullscreen"),
            ("btn_close", "关闭", "close"),
        ):
            btn = QPushButton(text)
            btn.setFixedSize(60, 30)
            btn.setObjectName("titleToolBtn")
            btn.clicked.connect(lambda _checked=False, a=action: self.action_triggered.emit(a))
            setattr(self, attr, btn)
            self.title_bar.findChild(QHBoxLayout).addWidget(btn)

    def _build_filter_bar(self):
        """常驻筛选条（40px）：抽屉开关 + 看板塞入的常用控件 + 重置 + 总命中数。

        改造前这里预置了「车间/单位/状态」三个假下拉，而各看板的内容组件里又各自
        带着十几个真下拉，等于同一个看板两套筛选、两套口径。现在常驻条只放外壳
        自己的三件东西（抽屉按钮 / 重置 / 总命中），真控件全部由 add_filter() 塞。
        """
        self.filter_bar = QFrame()
        self.filter_bar.setObjectName("filter_bar")
        self.filter_bar.setFixedHeight(SIZE_PX["boardFilterBar"])

        layout = QHBoxLayout(self.filter_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        self.btn_filter_drawer = QToolButton()
        self.btn_filter_drawer.setText("筛选 (0)")
        self.btn_filter_drawer.setCheckable(True)
        self.btn_filter_drawer.setFixedSize(100, 26)
        self.btn_filter_drawer.clicked.connect(self._on_filter_drawer_toggled)
        layout.addWidget(self.btn_filter_drawer)

        # 常驻控件永远插在 stretch 之前（末尾三项固定为 stretch / 重置 / 总命中），
        # 这样右侧两个元素保持贴右，中间不会被拉开空隙。
        layout.addStretch()

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setFixedSize(60, 26)
        self.btn_reset.clicked.connect(self._on_reset)
        layout.addWidget(self.btn_reset)

        self.lbl_total_hit = QLabel("共 0 条命中")
        self.lbl_total_hit.setProperty("class", "mutedText")
        layout.addWidget(self.lbl_total_hit)

        # key → _FilterSlot(widget, label, badge, zone)；由 add_filter 填充
        self._filters = {}
        self._active_keys = set()
        self._reset_cb = None

    def _build_filter_drawer(self):
        """筛选抽屉：分组卡按需创建，没有条件就没有分组（不再预置示例控件）。

        抽屉里的控件不受常驻条 sizeHint 精算约束，可以带标签列/徽章列的表格化布局。
        """
        self.drawer_container = QFrame()
        self.drawer_container.setObjectName("drawer_container")
        self.drawer_container.setVisible(False)

        self.drawer_layout = VBoxLayout(self.drawer_container)
        self.drawer_layout.setContentsMargins(10, 10, 10, 10)
        self.drawer_layout.setSpacing(14)

        self._drawer_groups = {}   # group_key → (QGroupBox, QGridLayout)
        self._drawer_rows = {}     # group_key → 下一行号
        # 尾部弹性项：分组卡按内容收紧贴顶，不被拉成一大块空白
        self.drawer_layout.addStretch()

    # ── 筛选接线 API（第二期真接入：看板只描述控件归位，布局与配色归外壳）────

    def add_filter(self, key: str, label: str, widget: QWidget,
                   zone: str = "bar", group: str = "", badge: bool = None):
        """把一个筛选控件放进入驻条或抽屉分组。

        zone="bar"    常驻条，最多 MAX_PERSISTENT_FILTERS 个（设计稿红线：含抽屉
                      按钮在内一行不超过 6 个控件，且整条不允许横向滚动）
        zone="drawer" 抽屉，group 取 _GROUP_TITLES 的 key（material/numeric/org）
        badge=None    常驻条默认无徽章（宽度金贵），抽屉默认带命中计数徽章
        """
        if key in self._filters:
            raise ValueError(f"筛选控件 key 重复: {key}")
        if zone not in ("bar", "drawer"):
            raise ValueError(f"未知筛选区域: {zone}")
        if zone == "bar" and len([s for s in self._filters.values() if s.zone == "bar"]) \
                >= self.MAX_PERSISTENT_FILTERS:
            raise ValueError(
                f"常驻筛选条最多 {self.MAX_PERSISTENT_FILTERS} 个控件，"
                "其余条件请放抽屉（设计稿 4.3.1：常驻区永不超过 6 个控件）")
        if zone == "drawer" and group not in self._GROUP_TITLES:
            raise ValueError(f"未知抽屉分组: {group}（可用: {list(self._GROUP_TITLES)}）")

        if badge is None:
            badge = zone == "drawer"

        # 常驻条里的控件保持原生 sizeHint（红线 #3：不给它们写样式表/内距），
        # 宽度仍由看板自己的 setMinimumWidth/setMaximumWidth 决定。
        lbl = QLabel(label)
        hit = None
        if zone == "bar":
            bar = self.filter_bar.layout()
            at = bar.count() - 3          # 末尾三项固定为 stretch / 重置 / 总命中
            bar.insertWidget(at, lbl)
            bar.insertWidget(at + 1, widget)
        else:
            box, grid = self._drawer_group(group)
            row = self._drawer_rows[group]
            self._drawer_rows[group] = row + 1
            grid.addWidget(lbl, row, 0)
            grid.addWidget(widget, row, 1)
            if badge:
                hit = QLabel("—")
                hit.setObjectName("hitBadge")
                hit.setAlignment(Qt.AlignCenter)
                grid.addWidget(hit, row, 2)

        self._filters[key] = _FilterSlot(widget, lbl, hit, zone)
        return widget

    def _drawer_group(self, group):
        """取（或建）抽屉分组卡。分组顺序恒为 物料 → 数值 → 组织与状态。"""
        if group in self._drawer_groups:
            return self._drawer_groups[group]
        box = QGroupBox(self._GROUP_TITLES[group])
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 72)
        grid.setColumnStretch(1, 1)
        self._drawer_groups[group] = (box, grid)
        self._drawer_rows[group] = 0
        # 分组卡按固定语义顺序插入（物料→数值→组织与状态），而不是按看板塞入的先后
        order = list(self._GROUP_TITLES)
        pos = sum(1 for g in order[:order.index(group)] if g in self._drawer_groups)
        self.drawer_layout.insertWidget(pos, box)
        return box, grid

    def set_filter_hits(self, key: str, count: int):
        """某条件在当前数据下的命中行数（抽屉徽章）。"""
        slot = self._filters.get(key)
        if slot is None or slot.badge is None:
            return
        slot.badge.setText(f"{count:,} 条")

    def set_filter_active(self, keys):
        """当前生效的条件数 → 抽屉按钮文案「筛选 (3)」。"""
        self._active_keys = set(keys)
        n = len(self._active_keys)
        if self.drawer_visible:
            self.btn_filter_drawer.setText("收起筛选")
        else:
            self.btn_filter_drawer.setText(f"筛选 ({n})")

    def set_total_hits(self, count: int):
        self.lbl_total_hit.setText(f"共 {count:,} 条命中")

    def set_reset_callback(self, fn):
        """「重置」按钮回调：由各看板把自己的复位逻辑交进来。"""
        self._reset_cb = fn

    def set_filter_enabled(self, key: str, enabled: bool):
        slot = self._filters.get(key)
        if slot is not None:
            slot.widget.setEnabled(enabled)

    def set_filter_visible(self, key: str, visible: bool):
        """整条条件收起（标签/控件/徽章一起消失）。

        数据里没有对应列时，看板不希望留下一排灰掉的空控件 —— 隐藏单个控件会留下
        标签与徽章的空位，所以由外壳统一按 key 处理整行。
        """
        slot = self._filters.get(key)
        if slot is None:
            return
        for w in (slot.widget, slot.label, slot.badge):
            if w is not None:
                w.setVisible(visible)

    def _build_kpi_bar(self):
        """KPI 带（54px）：默认隐藏，看板调 set_kpi_items 后才出现。

        改造前这里预置了 4 张写死的示例卡（负损 0 条 / 金额 -¥0.0 / 涉及车间 0 个 /
        隔离 0 条），而生产路径从没调过 set_kpi_data —— 于是每个看板顶部都横着一条
        永远不会变的假数字。现在没有真数据就没有这一行。
        """
        self.kpi_bar = QFrame()
        self.kpi_bar.setObjectName("kpi_bar")
        self.kpi_bar.setFixedHeight(SIZE_PX["boardKpiBar"])
        self.kpi_bar.setVisible(False)

        layout = QHBoxLayout(self.kpi_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        # KPI 卡片容器（横向不留滚动条：卡片数由看板控制在 4-6 张）
        self.kpi_scroll = QScrollArea()
        self.kpi_scroll.setObjectName("kpiScroll")
        self.kpi_scroll.setWidgetResizable(True)
        self.kpi_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.kpi_container = QWidget()
        self.kpi_layout = QHBoxLayout(self.kpi_container)
        self.kpi_layout.setContentsMargins(0, 0, 0, 0)
        self.kpi_layout.setSpacing(0)
        self.kpi_layout.setAlignment(Qt.AlignVCenter)
        self.kpi_scroll.setWidget(self.kpi_container)
        layout.addWidget(self.kpi_scroll)

    def set_kpi_data(self, items: list):
        """用真实数据重建 KPI 卡。items: [{'label','value','status'}]，空列表收起整行。"""
        while self.kpi_layout.count():
            self.kpi_layout.takeAt(0).widget().deleteLater()
        if not items:
            self.kpi_bar.setVisible(False)
            return
        for item in items:
            card = KpiCard(item.get("label", "KPI"), item.get("value", "—"),
                           item.get("status", ""))
            card.clicked.connect(self.kpi_clicked.emit)
            self.kpi_layout.addWidget(card)
        self.kpi_bar.setVisible(True)

    def _build_table_stub(self):
        """表格槽：内容组件（自带表格）走 set_content，裸模型走 set_model。

        改造前这里预置了一个空 QTableView + 一行提示文字，而明细看板全部用
        set_content 塞自己的组件进来 —— set_content 又会清空槽内所有子控件，
        于是这块占位表格的唯一起作用就是"被销毁"，顺带让 _update_status 里的
        self.table_view 变成已删除的 C++ 对象引用。
        """
        self.table_container = QFrame()
        # v43.346：补 objectName 供 QSS #content ID 选择器命中
        self.table_container.setObjectName("content")
        self._content = self.table_container  # 别名：QSS probe/测试按 _content 访问
        self.table_layout = VBoxLayout(self.table_container)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        self.table_view = None      # 仅 set_model 路径下惰性创建
        self._content_widget = None

    def _build_status_bar(self):
        """底部状态条（30px）：承载 _status_label，供 set_status() 更新。"""
        self._status_bar = QFrame()
        self._status_bar.setObjectName("status_bar")
        self._status_bar.setFixedHeight(SIZE_PX["statusBar"])
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        status_layout.setSpacing(8)
        self._status_label = QLabel("")
        self._status_label.setProperty("class", "mutedText")
        status_layout.addWidget(self._status_label, 1)
        # 选中行数（v43.346：从原操作条迁到状态条，操作条改空条按需展开）
        self.lbl_selected_count = QLabel("已选 0 行")
        self.lbl_selected_count.setProperty("class", "mutedText")
        status_layout.addWidget(self.lbl_selected_count)

    def _build_action_bar(self):
        self._action_bar = QFrame()
        # v43.346：属性名统一为 _action_bar（测试/probe 直接访问），并补 objectName
        # 供 QSS #action_bar ID 选择器命中。
        self._action_bar.setObjectName("action_bar")
        self._action_bar.setFixedHeight(SIZE_PX["boardActBar"])
        # v43.342：空操作条默认隐藏（隐藏后不占布局高度），仅当真正放入操作控件
        # （set_action_widget）时才展开，消除「标题与内容之间一大块留白」。
        self._action_bar.setVisible(False)
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

    def add_action_button(self, text: str, slot):
        """操作条上放一个按钮（看板把原先贴在表格下的按钮行交进来）。"""
        btn = QPushButton(text)
        btn.clicked.connect(slot)
        self.set_action_widget(btn)
        return btn

    def _load_theme(self):
        """按当前全局主题加载 QSS（读 themes/*.qss，读不到退回内置兜底）。"""
        self._load_theme_qss("dark" if Thm.is_dark else "light")

    def _load_theme_qss(self, theme: str):
        """外壳 QSS 只由 tokens.build_dashboard_qss() 生成，不再读文件、不再有兜底副本。

        改造前这里先读 themes/{light,dark}_dashboard.qss、读不到再退回本文件内
        又写死一份 _default_*_qss()——那份兜底里的主色还停留在 #0969DA/#5C7CFA，
        等于全项目第 6 份颜色真源。换机器/换盘读不到文件时就会静默用上它。
        """
        self.setStyleSheet(build_dashboard_qss(theme))

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

    def _on_filter_drawer_toggled(self):
        self.drawer_visible = not self.drawer_visible
        self.drawer_container.setVisible(self.drawer_visible)
        self.btn_filter_drawer.setText("收起筛选" if self.drawer_visible
                                       else f"筛选 ({len(self._active_keys)})")

    def _on_reset(self):
        """「重置」交回看板：条件语义（默认关键字、默认未读档位）只有内容组件自己知道。"""
        if self._reset_cb is not None:
            self._reset_cb()

    def set_model(self, model):
        """裸模型进槽（外壳代建 QTableView）；内容组件自带表格时用 set_content。"""
        if self.table_view is None:
            self.table_view = QTableView()
            self.table_view.setAlternatingRowColors(True)
            self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.table_view.verticalHeader().setDefaultSectionSize(SIZE_PX["tableRow"])
            # v43.366：外壳代建的表格，行号道与各看板同款 44px 右对齐
            enable_row_numbers(self.table_view)
            self.table_view.horizontalHeader().setHighlightSections(False)
            self.table_layout.addWidget(self.table_view)
        self._model = model
        self.table_view.setModel(model)
        selection = self.table_view.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self._on_selection_changed)
        self.set_row_count(model.rowCount() if model else 0)

    def _on_selection_changed(self, selected, deselected):
        sm = self.table_view.selectionModel() if self.table_view else None
        rows = len(sm.selectedRows()) if sm is not None else 0
        self.set_selected_count(rows, self._model.rowCount() if self._model else 0)

    def set_row_count(self, count: int):
        self.lbl_total_hit.setText(f"共 {count:,} 条命中")

    def set_selected_count(self, rows: int, total: int = 0):
        """状态条「已选 n / N 行」：内容组件自带表格时由看板回报（外壳看不到它的选择）。"""
        self.lbl_selected_count.setText(f"已选 {rows} / {total} 行")

    def set_title(self, title: str, subtitle: str = ""):
        self.title = title
        self.subtitle = subtitle
        # v43.346：无副标题时不追加 " · "，避免标题文本带尾部分隔符
        # （测试 ⑬ 断言整窗标题文本精确等于看板名，尾部 " · " 会导致不匹配）。
        self.lbl_title.setText(f"{title} · {subtitle}" if subtitle else title)

    def set_content(self, widget: QWidget):
        """内容组件进槽；重复调用会先清掉上一份，不会叠两层表格。"""
        if self._content_widget is not None:
            self.table_layout.removeWidget(self._content_widget)
            self._content_widget.deleteLater()
        self._content_widget = widget
        self.table_layout.addWidget(widget, 1)
        # 状态统一走底部状态条 _status_label（持久），进新内容时清空待外部 set_status 填
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
