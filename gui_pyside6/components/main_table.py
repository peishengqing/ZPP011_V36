# -*- coding: utf-8 -*-
"""主表格区组件 — 暗色主题"""
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTableView, QHeaderView, QFrame,
    QWidget, QSizePolicy, QToolButton,
)
import re

from PySide6.QtCore import Qt, Signal, QObject

# 分析进度步骤图标（沿用 v31 经典布局：一排图标 + 进度条 + 状态文字）
# 分析进度步骤图标（沿用 v31 经典布局：一排图标 + 进度条 + 状态文字）
# 顺序固定：0=主表计算（读取/解析/计算/匹配），1~10=Sheet1~10，11=生成Excel。
# 图标本体用「数字 + √」状态文字（不用 emoji：跨字体易渲染成方框/乱码，
# 且旧表里 🖖 代表中间地带、💰 代表偏差金额，语义与观感都不统一）。
ANALYSIS_STEPS = [
    "主表计算", "汇总统计", "替代料明细", "无备注预警", "中间地带", "完整偏差",
    "异常预警", "偏差金额", "原因汇总", "原因分析", "趋势分析", "生成Excel",
]


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


class MainTableComponent(QObject):
    """主表格区组件：分析进度、操作按钮、统计卡片、表格"""

    # 分析进度面板整体显隐变化（True=显示, False=隐藏）
    progress_visibility_changed = Signal(bool)
    link_banner_cleared = Signal()  # 联动横幅「清除」按钮点击

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self._create_widgets()

    def _create_widgets(self):
        # 分析进度（可折叠：标题栏 + 内容容器）
        self.progress_group = QWidget()
        self.progress_group.setObjectName("statsGroup")
        self.progress_group.setMinimumHeight(34)
        self.progress_group.setMaximumHeight(170)
        self._progress_hidden = False

        # 标题栏
        progress_title_layout = QHBoxLayout()
        progress_title_layout.setContentsMargins(8, 4, 8, 4)
        progress_title = QLabel("⚡ 分析进度")
        progress_title.setProperty("class", "statsCardTitle")
        progress_title_layout.addWidget(progress_title)
        progress_title_layout.addStretch()

        self.progress_toggle_btn = QToolButton(self.progress_group)
        self.progress_toggle_btn.setCheckable(True)
        self.progress_toggle_btn.setChecked(True)
        self.progress_toggle_btn.setText("隐藏")
        self.progress_toggle_btn.setToolTip("隐藏分析进度")
        self.progress_toggle_btn.setStyleSheet(
            "QToolButton { border: none; color: #666; font-size: 12px; padding: 2px 6px; }\n"
            "QToolButton:hover { color: #333; background: #eee; }")
        self.progress_toggle_btn.toggled.connect(self._toggle_progress)
        progress_title_layout.addWidget(self.progress_toggle_btn)

        # 内容容器（可隐藏）
        self.progress_content = QWidget()
        self.progress_content.setObjectName("progressContent")
        progress_layout = QVBoxLayout(self.progress_content)
        progress_layout.setSpacing(8)
        progress_layout.setContentsMargins(8, 4, 8, 8)

        # 步骤图标行（v31 经典：一排图标，当前步骤高亮）
        self.step_icons = []
        self._step_icon_pos = 0  # 步骤图标指针（只进不退）
        step_row = QHBoxLayout()
        step_row.setSpacing(6)
        step_row.setContentsMargins(0, 4, 0, 4)
        for idx, name in enumerate(ANALYSIS_STEPS):
            btn = QToolButton()
            btn.setText(str(idx + 1))  # 待办=数字；完成后变 √（见 update_step_icons）
            btn.setToolTip(f"{idx + 1}. {name}")
            btn.setProperty("step_idx", idx)
            btn.setAutoRaise(True)
            btn.setStyleSheet("""
                QToolButton {
                    color: #888780;
                    background-color: #25242E;
                    border: 1px solid #3A3847;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0px;
                    min-width: 22px;
                    max-width: 22px;
                    min-height: 22px;
                    max-height: 22px;
                }
                QToolButton:hover { background-color: #35334A; }
                QToolButton[active="true"] {
                    color: #EAE8E4;
                    background-color: #7F77DD;
                    border-color: #7F77DD;
                }
                QToolButton[done="true"] {
                    color: #7F77DD;
                    background-color: #25242E;
                    border-color: #7F77DD;
                }
            """)
            self.step_icons.append(btn)
            step_row.addWidget(btn)
        step_row.addStretch()

        # 分析进度状态文字（与图标同一行，放在图标与计时器之间）
        self.progress_label = QLabel("就绪")
        self.progress_label.setObjectName("progressLabel")
        self.progress_label.setStyleSheet("color: #888780; font-size: 12px; font-weight: bold; padding-left: 8px;")
        self.progress_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        step_row.addWidget(self.progress_label)

        # 计时器放在步骤图标同一行右侧
        self.timer_lbl = QLabel("⏱ 00:00")
        self.timer_lbl.setObjectName("timerLabel")
        self.timer_lbl.setStyleSheet("color: #888780; font-family: Consolas; font-size: 12px; font-weight: bold;")
        step_row.addWidget(self.timer_lbl)

        progress_layout.addLayout(step_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        progress_layout.addWidget(self.progress_bar)

        # 组装进度面板
        progress_main = QVBoxLayout(self.progress_group)
        progress_main.setContentsMargins(0, 0, 0, 0)
        progress_main.setSpacing(0)
        progress_main.addLayout(progress_title_layout)
        progress_main.addWidget(self.progress_content)


        # 表格
        self.table_view = QTableView()
        self.table_view.setObjectName("tableView")
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().setSortIndicatorShown(True)
        self.table_view.horizontalHeader().sectionClicked.connect(self.mw._on_header_clicked)
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
        audit_layout.setSpacing(4)

        # 标记统计常驻标签：显示当前可见行中各类颜色标记的行数（偏差预警/替代料/未投料）
        # 文本由 main_window._update_mark_stats 实时刷新，随筛选/排序/数据变化动态更新
        self.mark_stats_label = QLabel("标记统计：—")
        self.mark_stats_label.setObjectName("markStatsLabel")
        self.mark_stats_label.setStyleSheet(
            "QLabel#markStatsLabel{"
            "padding:3px 8px;border-radius:4px;"
            "background:#f3f4f6;color:#374151;font-size:12px;"
            "}"
        )
        self.mark_stats_label.setFixedHeight(22)
        audit_layout.addWidget(self.mark_stats_label)

        # 联动横幅（看板钻取）：表格上方提示当前联动筛选上下文，可一键清除
        self.link_banner = QFrame()
        self.link_banner.setObjectName("linkBanner")
        self.link_banner.setVisible(False)
        _link_row = QHBoxLayout(self.link_banner)
        _link_row.setContentsMargins(8, 3, 8, 3)
        self.link_banner_label = QLabel("")
        self.link_banner_label.setObjectName("linkBannerLabel")
        self.link_banner_clear_btn = QPushButton("清除")
        self.link_banner_clear_btn.setObjectName("linkBannerClearBtn")
        self.link_banner_clear_btn.setCursor(Qt.OpenHandCursor)
        self.link_banner_clear_btn.clicked.connect(self.link_banner_cleared.emit)
        _link_row.addWidget(self.link_banner_label, 1)
        _link_row.addWidget(self.link_banner_clear_btn)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.insertWidget(0, self.link_banner)

        main_layout.addWidget(self.table_view, 1)

        audit_layout.addLayout(main_layout, 1)

        self.audit_widget = QWidget()
        self.audit_widget.setLayout(audit_layout)

    # ------------------------------------------------------------------ #
    # 分析进度面板折叠
    # ------------------------------------------------------------------ #
    def _toggle_progress(self, visible):
        """标题栏隐藏按钮：点击后整个分析进度面板消失"""
        self._progress_hidden = not visible
        self.progress_content.setVisible(visible)
        self.progress_toggle_btn.setText("隐藏" if visible else "显示")
        self.progress_toggle_btn.setToolTip("隐藏分析进度" if visible else "显示分析进度")
        self.progress_group.setVisible(visible)
        self.progress_visibility_changed.emit(visible)

    # ------------------------------------------------------------------ #
    # 联动横幅（看板 → 主表钻取）
    # ------------------------------------------------------------------ #
    def show_link_banner(self, text):
        """显示联动提示条（text 例：'订单 17001234 · 偏差率预警'）。"""
        self.link_banner_label.setText("联动视图：" + text + "（点击「清除」恢复原筛选）")
        self.link_banner.setVisible(True)

    def clear_link_banner(self):
        self.link_banner.setVisible(False)

    def set_progress_visible(self, visible: bool):
        """外部（如开始分析时）强制展开/折叠进度面板，并同步按钮状态"""
        self._progress_hidden = not visible
        self.progress_content.setVisible(visible)
        self.progress_toggle_btn.setChecked(visible)
        self.progress_toggle_btn.setText("隐藏" if visible else "显示")
        self.progress_toggle_btn.setToolTip("隐藏分析进度" if visible else "显示分析进度")
        self.progress_group.setVisible(visible)
        self.progress_visibility_changed.emit(visible)

    def show_progress(self):
        """外部调用：显示整个分析进度面板"""
        self.set_progress_visible(True)

    # ------------------------------------------------------------------ #
    # 分析进度步骤图标
    # ------------------------------------------------------------------ #
    def reset_step_icons(self):
        """分析开始前重置所有步骤图标（全部回到数字态，指针归零）。"""
        for idx, btn in enumerate(self.step_icons):
            btn.setProperty("active", False)
            btn.setProperty("done", False)
            btn.setText(str(idx + 1))
            self._refresh_step_btn_style(btn)
        self._step_icon_pos = 0

    # 步骤名 → 图标索引映射（ANALYSIS_STEPS 顺序：0=主表计算，1~10=Sheet1~10，11=生成Excel）
    _STEP_NAME_RE = re.compile(r"^Sheet(\d+)-")

    @classmethod
    def _map_step_name(cls, name):
        """把 analyzer 发射的真实步骤名映射到图标索引；通知/里程碑返回 None（图标停住）。"""
        name = (name or "").strip()
        m = cls._STEP_NAME_RE.match(name)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 11:
                return n
        if name.startswith(("1/5", "2/5", "3/5", "4/5")):
            return 0  # 读取/解析/计算/匹配 都属主表计算阶段
        if "正在生成审核表格" in name:
            return 11
        return None  # 过滤/搜索通知、里程碑（主表计算完成/分析完成）、错误：图标不动

    def update_step_icons(self, percent, current_step_name=""):
        """按真实步骤点亮图标：由 analyzer 发射的步骤名驱动（不再是百分比切段），只进不退。"""
        if not self.step_icons:
            return
        idx = self._map_step_name(current_step_name)
        if idx is None:
            return  # 通知/里程碑：图标停留在最近一个真实步骤
        # 只进不退：乱序发射（如缓存重放、回退值）不允许把图标指针打回去
        idx = max(idx, self._step_icon_pos)
        self._step_icon_pos = idx
        for i, btn in enumerate(self.step_icons):
            if i < idx:
                btn.setProperty("active", False)
                btn.setProperty("done", True)
                btn.setText("\u221a")  # √
            elif i == idx:
                btn.setProperty("active", True)
                btn.setProperty("done", False)
                btn.setText(str(i + 1))
            else:
                btn.setProperty("active", False)
                btn.setProperty("done", False)
                btn.setText(str(i + 1))
            self._refresh_step_btn_style(btn)
    def complete_step_icons(self):
        """分析完成后所有步骤图标标记为完成（全部 √，指针到底）。"""
        for idx, btn in enumerate(self.step_icons):
            btn.setProperty("active", False)
            btn.setProperty("done", True)
            btn.setText("\u221a")  # √
            self._refresh_step_btn_style(btn)
        self._step_icon_pos = len(self.step_icons)

    @staticmethod
    def _refresh_step_btn_style(btn):
        """刷新动态属性样式。"""
        style = btn.style()
        if style:
            style.unpolish(btn)
            style.polish(btn)
        btn.update()
