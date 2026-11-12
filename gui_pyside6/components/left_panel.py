# -*- coding: utf-8 -*-
"""左侧面板组件 —— 236px 纯导航侧栏（v43.349 第五期C，照抄设计稿 Tier-3 .sidebar）

设计稿逐条落地（index.html 446-494 结构 + 184-206 CSS）：
  side-sec「工作区」   偏差明细(.on) · 审核队列(未读徽标) · 隔离区(徽标) · 替代料配对(徽标)
  side-sec「快捷入口」 数据源 · 材料半成品(徽标) · 数据预览
  side-foot           列管理 · 筛选预设

nav-item 统一 30px 高、14px 图标、左对齐文字，右端挂 .count 数字胶囊。
带表单的项（替代料配对/数据源/材料半成品/数据预览）点开后在行下方展开 body：
同一时刻只展开一个，展开瞬间把栏宽临时拉回 360px（表单控件的列宽是 360 时代调好
的，236px 会把表格挤扁），全部收起即回 236px。

保留的外部契约（其他地方直接引用，勿改属性名）：
  mw.input_file_edit / output_dir_edit / alt_table / alt_count_label /
  semi_count_label / preview_label / left_panel_component.semi_tree
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QHeaderView, QTreeWidget, QAbstractItemView,
)
from PySide6.QtCore import Qt, QSize

from gui_pyside6.themes.tokens import SIZE_PX
from gui_pyside6.utils.icons import get_icon
from gui_pyside6.utils.table_autofit import install_adaptive


class LeftPanelComponent:
    """左侧面板组件：创建并返回 self.left_panel"""

    NAV_W = SIZE_PX["navPanel"]  # 236，设计稿 --sidebar-w
    OPEN_W = 360                 # 展开表单时的临时栏宽
    ITEM_H = 30                  # 设计稿 .nav-item{height:30px}
    ALERT_KEYS = ("unread",)     # 计数 > 0 时用 danger 胶囊（设计稿 .count.alert）

    def __init__(self, main_window):
        self.mw = main_window
        self.badges = {}          # badge_key -> QLabel 胶囊
        self._alert_state = {}    # badge_key -> bool，避免每次刷新都 re-polish
        self._expandables = []    # [(btn, body)] 可展开项（互斥）
        self.left_panel = self._create_panel()

    # ── 骨架 ──

    def _create_panel(self):
        panel = QWidget()
        panel.setObjectName("leftPanel")
        # QWidget 子类不绘 QSS 背景，必须显式打开（标题栏/操作栏同套路）
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setFixedWidth(self.NAV_W)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        sec = self._add_section(lay, "工作区")
        self._nav(sec, "偏差明细", "table", on=True, clicked=self._show_dev_table)
        self._nav(sec, "审核队列", "clipboard", badge="unread",
                  clicked=self._open_audit_queue)
        self._nav(sec, "隔离区", "lock", badge="quarantine",
                  clicked=self._open_quarantine)
        self._nav(sec, "替代料配对", "exchange", badge="alt",
                  body=self._build_alternative_materials)

        sec = self._add_section(lay, "快捷入口")
        self._nav(sec, "数据源", "folder-open", body=self._build_file_selection)
        self._nav(sec, "材料半成品", "layers", badge="semi",
                  body=self._build_semi_materials)
        self.preview_nav_btn = self._nav(sec, "数据预览", "chart",
                                         body=self._build_preview)

        foot = self._add_foot(lay)
        self._nav(foot, "列管理", "menu", clicked=self._open_column_manager)
        self._nav(foot, "筛选预设", "funnel-lines", clicked=self._open_presets)
        return panel

    def _add_section(self, lay, label):
        """设计稿 .side-sec（padding 10/10/4）+ .side-label（10.5px 大写字距标题）"""
        box = QWidget()
        box.setObjectName("sideSec")
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 10, 10, 4)
        v.setSpacing(1)
        cap = QLabel(label)
        cap.setObjectName("sideLabel")
        v.addWidget(cap)
        lay.addWidget(box)
        return v

    def _add_foot(self, lay):
        """设计稿 .side-foot：margin-top:auto → Qt 里用 stretch 顶到底部"""
        lay.addStretch(1)
        box = QWidget()
        box.setObjectName("sideFoot")
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(1)
        lay.addWidget(box)
        return v

    def _nav(self, lay, label, icon, *, badge=None, on=False, clicked=None, body=None):
        """一颗 nav-item：按钮本体负责图标+左对齐文字，右端挂计数胶囊，下方可选 body。"""
        btn = QPushButton(label)
        btn.setObjectName("navItem")
        btn.setFixedHeight(self.ITEM_H)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)      # 导航行不参与 Tab 链，空格键留给表格
        btn.setIcon(get_icon(icon, 14))
        btn.setIconSize(QSize(14, 14))
        if on:
            btn.setProperty("navOn", True)  # 设计稿 .nav-item.on（当前工作区）

        if badge:
            # 按钮自身的图标+文字由 style 绘制，这里只摆右端胶囊：
            # stretch 把胶囊顶到最右，鼠标事件穿透给按钮（点胶囊也算点这行）。
            pill_row = QHBoxLayout(btn)
            pill_row.setContentsMargins(0, 0, 8, 0)
            pill_row.setSpacing(0)
            pill_row.addStretch(1)
            pill = QLabel("0")
            pill.setObjectName("navCount")
            pill.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            pill_row.addWidget(pill)
            self.badges[badge] = pill
            self._alert_state[badge] = False

        if body is not None:
            btn.setCheckable(True)
            body_w = QWidget()
            body_w.setObjectName("navBody")
            bv = QVBoxLayout(body_w)
            bv.setContentsMargins(10, 2, 10, 12)
            bv.setSpacing(8)
            body(bv)
            body_w.setVisible(False)
            btn.toggled.connect(
                lambda checked, b=body_w, bb=btn: self._on_toggle(b, bb, checked))
            self._expandables.append((btn, body_w))

        lay.addWidget(btn)
        if body is not None:
            lay.addWidget(body_w)
        if clicked is not None:
            btn.clicked.connect(clicked)
        return btn

    # ── 展开/收起 ──

    def _on_toggle(self, body, btn, checked):
        if checked:
            for btn2, body2 in self._expandables:
                if body2 is not body:
                    btn2.setChecked(False)  # 互斥：递归进 else 分支把别处收干净
            self._apply_width(self.OPEN_W)
        body.setVisible(checked)
        if not checked and all(b.isHidden() for _, b in self._expandables):
            self._apply_width(self.NAV_W)

    def collapse_all(self):
        """收起全部展开项（点纯导航项、「收起全部展开项」菜单共用）"""
        for btn, _ in self._expandables:
            btn.setChecked(False)

    def open_data_preview(self):
        """导入数据后把「数据预览」自己展开，统计不用人再点一次才看得到。

        走 setChecked 而不是直接显示 body：互斥收起别项、栏宽拉回 360px 都写在
        _on_toggle 里，绕过它就得到「两个 body 同时开着、栏宽还是 236」的畸形态。
        已经开着就什么都不做——否则用户刚手动收起来，下一次刷新又给他弹开。
        """
        btn = getattr(self, 'preview_nav_btn', None)
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)

    def _apply_width(self, width):
        """改左栏固定宽并同步 splitter 首值，避免两者约束打架。"""
        self.left_panel.setFixedWidth(width)
        sp = getattr(self.mw, 'body_splitter', None)
        if sp is not None:
            try:
                sizes = sp.sizes()
                if len(sizes) >= 3:
                    sizes[0] = width
                    sp.setSizes(sizes)
            except Exception:
                pass

    # ── 徽标（待办类计数） ──

    def set_badge(self, key, value):
        pill = self.badges.get(key)
        if pill is None:
            return
        n = value if isinstance(value, int) and value > 0 else 0
        pill.setText(str(n))
        alert = key in self.ALERT_KEYS and n > 0
        if self._alert_state.get(key) != alert:
            # QSS 靠 [alert="true"] 属性选择器命中，改属性后必须重 polish 才生效
            pill.setProperty("alert", "true" if alert else "false")
            pill.style().unpolish(pill)
            pill.style().polish(pill)
            self._alert_state[key] = alert

    def refresh_counts(self, df=None):
        """未读 / 隔离区徽标的单一出口（数据变化后由 MainWindow 调用）。

        替代料、半成品是配置项而非待办，计数由 alt/semi 各自的刷新漏斗就地写入。
        """
        if df is None:
            getter = getattr(self.mw, '_get_master_df', None)
            df = getter() if callable(getter) else None
        if df is None or getattr(df, "empty", True):
            self.set_badge("unread", 0)
            self.set_badge("quarantine", 0)
            return
        self.set_badge("unread", int((df["_read"] == 0).sum()) if "_read" in df.columns else 0)
        self.set_badge("quarantine",
                       int((df["_quarantined"] == 1).sum()) if "_quarantined" in df.columns else 0)

    # ── 导航动作 ──

    def _show_dev_table(self):
        self.collapse_all()
        self.mw.table_view.setFocus()

    def _open_audit_queue(self):
        self.collapse_all()
        # 审核队列 = 未读/待核对汇总弹窗（AuditDialog 是死路，见 layout_composer 注释）
        self.mw.show_unread_summary(force=True)

    def _open_quarantine(self):
        self.collapse_all()
        self.mw._open_quarantine_dialog()

    def _open_column_manager(self):
        self.collapse_all()
        self.mw._show_column_hide_dialog()

    def _open_presets(self):
        self.collapse_all()
        self.mw._open_filter_preset_manager()

    # ── 三块可展开表单（控件与绑定沿用旧版，仅换容器） ──

    def _build_file_selection(self, layout: QVBoxLayout):
        """构建文件选择表单"""
        # 输入文件
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        input_field = QLineEdit(self.mw)
        input_field.setPlaceholderText("点击「浏览」选择 Excel 文件")
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
        layout.addWidget(input_label)
        layout.addLayout(input_row)

        # 输出目录
        output_row = QHBoxLayout()
        output_row.setSpacing(6)

        output_field = QLineEdit(self.mw)
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
        layout.addWidget(output_label)
        layout.addLayout(output_row)

    def _build_alternative_materials(self, layout: QVBoxLayout):
        """构建替代料管理表单"""
        # 计数说明（徽标只显示数字，这里保留完整口径供表单内查看）
        self.mw.alt_count_label = QLabel("共 0 对")
        self.mw.alt_count_label.setObjectName("altCountLabel")
        layout.addWidget(self.mw.alt_count_label)

        # 替代料表格
        self.mw.alt_table = QTableWidget()
        self.mw.alt_table.setColumnCount(3)
        self.mw.alt_table.setHorizontalHeaderLabels(["物料A", "↔", "物料B"])
        self.mw.alt_table.setObjectName("altTable")
        header = self.mw.alt_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 30)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.mw.alt_table.verticalHeader().setVisible(False)
        self.mw.alt_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mw.alt_table.setDragEnabled(True)
        self.mw.alt_table.setAcceptDrops(True)
        self.mw.alt_table.setDragDropMode(QTableWidget.InternalMove)
        self.mw.alt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mw.alt_table.setAlternatingRowColors(True)
        # 不再内联设置样式，由 QSS 主题统一控制
        self.mw.alt_table.setMinimumHeight(100)
        self.mw.alt_table.setMaximumHeight(150)
        layout.addWidget(self.mw.alt_table)

        # v43.300：替代料表格列宽自适应（列0/2 Stretch、列1 Fixed 的精算布局，
        # 故 mode='off' 仅注册控制器、保留原布局，避免破坏 ↔ 中间列 30px 固定宽）。
        install_adaptive(self.mw.alt_table, mode='off', key='alt_table')

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

        # 智能添加：从主表选中 2 行自动提取工厂/编码/名称
        sel_row = QHBoxLayout()
        sel_btn = QPushButton("从主表选中2行添加")
        sel_btn.setIcon(get_icon("pin", 14))
        sel_btn.setObjectName("altActionBtn")
        sel_btn.setToolTip("在主表选中恰好 2 行，自动提取它们的工厂/编码/名称作为替代料配对")
        sel_btn.clicked.connect(self.mw._add_alt_pair_from_selection)
        sel_row.addWidget(sel_btn)
        layout.addLayout(sel_row)

    def _build_semi_materials(self, layout: QVBoxLayout):
        """构建材料半成品分类表单 —— QTreeWidget 两级：工厂·分类 / 物料编码"""
        # 计数说明（徽标只放数字，这里给完整口径）
        self.mw.semi_count_label = QLabel("共 0 项")
        self.mw.semi_count_label.setObjectName("semiCountLabel")
        layout.addWidget(self.mw.semi_count_label)

        # 树形（v43.165 由 QTableWidget 改QTreeWidget）
        # 两级结构：父节点 = 「工厂 · 分类」，子节点 = 该分类下的物料编码。
        # 实测（offscreen Qt）：栏宽 236/360、可见高有限，全展开 4父+69子=73 行远超
        # 可视范围，故**默认折叠** + 高度上限 320px（约 26 行，常见分类可完整展开不需滚）。
        self.semi_tree = QTreeWidget()
        self.semi_tree.setColumnCount(2)
        self.semi_tree.setHeaderLabels(["分类 / 物料编码", "物料数"])
        self.semi_tree.setObjectName("semiTable")   # 复用原样式名，避免重写 QSS
        hdr = self.semi_tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.resizeSection(1, 52)
        self.semi_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.semi_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.semi_tree.setAlternatingRowColors(True)
        self.semi_tree.setMinimumHeight(100)
        self.semi_tree.setMaximumHeight(320)
        self.semi_tree.itemClicked.connect(self._on_semi_tree_click)
        layout.addWidget(self.semi_tree)

        # 操作按钮（仿替代料配对风格）
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        for label, handler in [
            ("添加", self.mw._add_semi_category),
            ("删除", self.mw._delete_semi_category),
            ("重置", self.mw._reset_semi_categories),
            ("导入", self.mw._import_semi_categories),
            ("导出", self.mw._export_semi_categories),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("semiBtn")
            btn.clicked.connect(handler)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        # 放大按钮
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(6)
        zoom_btn = QPushButton("放大")
        zoom_btn.setObjectName("semiBtn")
        zoom_btn.clicked.connect(self.mw._zoom_semi_table)
        zoom_layout.addWidget(zoom_btn)
        zoom_layout.addStretch()
        layout.addLayout(zoom_layout)

    def _build_preview(self, layout: QVBoxLayout):
        """数据预览：纯文字统计（行列数、工厂/日期跨度），与主表口径一致"""
        self.mw.preview_label = QLabel("")
        self.mw.preview_label.setObjectName("previewLabel")
        self.mw.preview_label.setWordWrap(True)
        layout.addWidget(self.mw.preview_label)

    def _on_semi_tree_click(self, item, _column):
        """点击树节点：仅**父节点**（分类级）触发明细窗，子节点（单个物料编码）不触发。
        v43.165：原 QTableWidget 的 cellClicked 语义是「点分类行→筛该分类」，
        树形下需显式区分层级 —— 用 childCount()==0 判断是否为叶子（编码）。"""
        if item is None:
            return
        if item.childCount() > 0:
            category = item.data(0, Qt.ItemDataRole.UserRole)
            if category:
                self.mw._show_semi_detail_window(category)
