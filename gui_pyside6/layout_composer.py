# -*- coding: utf-8 -*-
"""
Layout 组装器 (LayoutComposer) - 纯 UI 组装，逻辑下沉

负责：MainWindow 的 UI 布局组装，将所有 UI 边框、容器、布局、Widget 创建移动到这里，
让 MainWindow 只保留薄壳状态管理。

目标：替 _assemble_layout 瘦身，将 UI 相关的繁杂操作集中到一个类，逻辑往下沉。

v43.264：操作栏/菜单 emoji → 内联 SVG 线性图标（icons.py），按钮文本去 emoji 前缀。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QToolButton, QMenu, QWidgetAction,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from gui_pyside6.themes.tokens import SIZE_PX
from gui_pyside6.utils.icons import get_icon
from utils.theme_manager import Thm


def _icon_action(menu: QMenu, icon: str, text: str, handler) -> QAction:
    """带线性图标的菜单项（v43.264 起统一入口，替掉各处的 emoji addAction）"""
    act = QAction(get_icon(icon), text, menu)
    act.triggered.connect(handler)
    menu.addAction(act)
    return act


def _on_audit_action(mw):
    """审核入口 = 打开「审核队列」（未读/待核对汇总弹窗）。

    v43.349 第五期B：原先这里直连 `self._on_audit_action`（模块级函数挂 self 上，
    一点就 AttributeError），且它要打开的 AuditDialog 本身就是死路 —— 构造即崩
    （`_setup_ui` 用了未定义的 self.value_label/note_label），调用方还把 data_id
    当成 df 传进去，后端 `AuditService.audit_complete` 走的是另一套
    `~/.zpp011_audit/audit.db`，全仓无人 mark 过「待审核」，永远返回 False。
    本项目真正在用的核对流程是「未读 → 逐行核对 → 标记已读」（core/read_status），
    所以按设计稿把这颗主操作按钮接到那个真能用的队列上，死弹窗留待后续单独一期处理。
    """
    mw.show_unread_summary(force=True)


class LayoutComposer:
    """UI 布局组装器，纯 UI 相关组装逻辑，零业务逻辑."""

    def __init__(self):
        self.compiled = False

    def assemble(self, mw) -> QWidget:
        """组装完整 UI 布局并返回中央 Widgets.

        参数
        ----
        mw : MainWindow
            主窗口对象，持有所有子组件引用（self.title_bar, self.left_panel 等）

        返回
        ----
        central : QWidget
            已设置好所有子布局的中央容器，可直接 setCentralWidget
        """
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 自定义标题栏
        main_layout.addWidget(mw.title_bar)

        # 2. 操作栏（按钮）
        action_bar = self._make_action_bar(mw)
        main_layout.addWidget(action_bar)

        # 3. 主体区域（侧栏 + 数据表格+日志）
        body_area = self._make_body_area(mw)
        main_layout.addWidget(body_area, 1)

        # 将 body_splitter 引用保存到主窗口，供控制器和外部的 _toggle_left_panel/_toggle_filter_panel 访问
        mw.body_splitter = body_area

        # v43.349 第五期F：底部状态条不再挂进中央布局 —— 它本身就是主窗口的
        # QStatusBar（main_window 里 setStatusBar），由 QMainWindow 放在最下方，
        # 原生那条已被它顶替，不会再叠出第二条状态条。

        self.compiled = True
        return central

    def _make_action_bar(self, mw) -> QWidget:
        """制作操作栏 —— 设计稿 v43.333 第五期第 2 项（Tier 2，44px 三段）。

        分组：主操作（分析 / 审核）│ 视图开关（数据表 / 筛选抽屉 / 列头过滤 /
        概览面板）│ 收纳（看板 / 导出 / ⋮更多）……右端提示（共 N 条 · F5 分析 · F11 全屏）。
        改造前是 38px 一排混排：主操作和 4 个带文字的收纳菜单挤在一起，低频按钮
        藏在「更多」弹出面板里靠文字辨认，右端只剩一行快捷键说明。
        """
        action_bar = QWidget()
        action_bar.setObjectName("actionBar")
        # QWidget 子类不自绘 QSS 底色，必须显式开这个属性（同 components/title_bar.py）
        action_bar.setAttribute(Qt.WA_StyledBackground, True)
        action_bar.setFixedHeight(SIZE_PX["actionBar"])
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(12, 0, 12, 0)
        action_layout.setSpacing(SIZE_PX["gridGap"])

        # ═══ 第 1 段：主操作（设计稿 .btn-primary + .btn-outline）═══
        mw.action_btn_analyze = QPushButton("分析")
        mw.action_btn_analyze.setIcon(get_icon("play", 15, Thm.color("onPrimary")))
        mw.action_btn_analyze.setObjectName("actionBtnAnalyze")
        mw.action_btn_analyze.setFixedHeight(30)
        action_layout.addWidget(mw.action_btn_analyze)

        # 审核从「更多」面板提到主操作位（设计稿：审核是日常工作流的第一跳）
        mw.action_btn_audit = QToolButton()
        mw.action_btn_audit.setIcon(get_icon("edit", 14))
        mw.action_btn_audit.setText("审核")
        mw.action_btn_audit.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_audit.setToolTip("打开审核队列（未读 / 待核对清单）")
        mw.action_btn_audit.setObjectName("actionBtnAudit")
        mw.action_btn_audit.setFixedHeight(30)
        # 模块级函数，不能用 self. 取（v43.341 之前一直挂在 self 上，点了就报错）
        mw.action_btn_audit.clicked.connect(lambda: _on_audit_action(mw))
        action_layout.addWidget(mw.action_btn_audit)

        action_layout.addWidget(self._make_separator())

        # ═══ 第 2 段：视图开关（4 个 icon-only，设计稿 .tool-btn）═══
        # 对象名/属性名沿用旧名（main_window 与控制器都挂在 mw.action_btn_* 上），
        # 只换视觉与文案；文本保留是给读屏与「更多」菜单同步用的，按钮本身不显示。
        for _attr, _icon, _text, _tip in (
            ("action_btn_left_panel", "table", "数据表", "显示/隐藏左栏（数据表与导航）"),
            ("action_btn_filter", "search", "筛选抽屉", "显示/隐藏筛选抽屉"),
            ("action_btn_col_filter", "funnel-lines", "列头过滤", "列头取值过滤模式"),
            ("action_btn_toggle_stats", "gauge", "概览面板", "显示/隐藏本次分析概览"),
        ):
            btn = QToolButton()
            btn.setIcon(get_icon(_icon, 15))
            btn.setText(_text)
            btn.setToolTip(_tip)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            btn.setCheckable(True)
            btn.setFixedSize(30, 30)
            btn.setObjectName("toolViewBtn")
            setattr(mw, _attr, btn)
            action_layout.addWidget(btn)
        # 数据表默认 on（左栏默认可见）、概览默认 on（旧版即默认展开）
        mw.action_btn_left_panel.setChecked(True)
        mw.action_btn_toggle_stats.setChecked(True)

        action_layout.addWidget(self._make_separator())
        # ═══ 第 3 段：收纳（设计稿 .btn-ghost 看板 / 导出 + ⋮更多）═══
        mw.action_btn_boards = QToolButton()
        mw.action_btn_boards.setObjectName("actionMenuBtn")
        mw.action_btn_boards.setIcon(get_icon("chart", 14))
        mw.action_btn_boards.setText("看板")
        mw.action_btn_boards.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_boards.setFixedHeight(30)
        mw.action_btn_boards.setToolTip("打开看板")

        # 为看板按钮添加下拉菜单
        mw.action_btn_boards.setPopupMode(QToolButton.MenuButtonPopup)
        boards_menu = QMenu(mw)
        _icon_action(boards_menu, "bell", "替代料看板", lambda: mw._show_alert_dashboard())
        _icon_action(boards_menu, "alert", "偏差率预警", lambda: mw._show_deviation_warning_dialog())
        _icon_action(boards_menu, "trending-down", "负损看板", lambda: mw._show_neg_loss_dashboard())
        _icon_action(boards_menu, "trending-up", "正损看板", lambda: mw._show_pos_loss_dashboard())
        _icon_action(boards_menu, "lock", "隔离区", lambda: mw._open_quarantine_dialog())
        _icon_action(boards_menu, "clipboard", "数据稳定性", lambda: mw._show_data_stability_dashboard())
        _icon_action(boards_menu, "link", "替代料长链", lambda: mw._show_alt_chain_dashboard())
        _icon_action(boards_menu, "box", "半成品看板", lambda: mw._show_semi_dashboard())
        _icon_action(boards_menu, "refresh", "翻箱守恒", lambda: mw._show_flip_check_dashboard())
        mw.action_btn_boards.setMenu(boards_menu)
        action_layout.addWidget(mw.action_btn_boards)

        mw.action_btn_export = QToolButton()
        mw.action_btn_export.setObjectName("actionMenuBtn")
        mw.action_btn_export.setIcon(get_icon("download", 14))
        mw.action_btn_export.setText("导出")
        mw.action_btn_export.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_export.setFixedHeight(30)
        mw.action_btn_export.setToolTip("导出当前表格")

        # 为导出按钮添加下拉菜单
        export_menu = QMenu(mw)
        _icon_action(export_menu, "file-text", "导出当前表格",
                     lambda: mw.export_controller.export_current_table(mw.view_model.df, mw))
        _icon_action(export_menu, "table", "导出完整偏差", lambda: mw._on_export_full_excel())
        mw.action_btn_export.setMenu(export_menu)
        mw.action_btn_export.setPopupMode(QToolButton.MenuButtonPopup)
        action_layout.addWidget(mw.action_btn_export)

        # 原「维护」菜单按钮（自动隔离规则 / 物料画像）退役，两项并入「更多」——
        # 设计稿这一段只留 看板 / 导出 / ⋮ 三颗，第四颗会把主操作挤远。
        # 注意：mw.action_btn_maint 已不再创建，main_window 里对它的连接一并删除。

        # ═══ 「更多」⋮：低频开关 + 原「维护」两项 + 输出目录 ═══
        # v43.341 起这 5 个按钮就搬进了弹出面板（对象与连接保留，只换 parent）；
        # 本期把 概览 / 审核 请回主操作与视图开关位，「未读」与「审核」现在是同
        # 一个队列（见 _on_audit_action），不再留第三颗重复按钮 → 面板只剩 2 个开关。
        mw.action_btn_toggle_progress = QToolButton()
        mw.action_btn_toggle_progress.setIcon(get_icon("zap"))
        mw.action_btn_toggle_progress.setText("进度")
        mw.action_btn_toggle_progress.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_toggle_progress.setCheckable(True)
        mw.action_btn_toggle_progress.setChecked(True)
        mw.action_btn_toggle_progress.setToolTip("切换分析进度")
        mw.action_btn_toggle_progress.setObjectName("toolGhostBtn")

        # 自动隔离规则按钮（ARC-003 第七刀，需额外创建）
        mw.action_btn_auto_q = QToolButton()
        mw.action_btn_auto_q.setIcon(get_icon("shield"))
        mw.action_btn_auto_q.setText("自动隔离")
        mw.action_btn_auto_q.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mw.action_btn_auto_q.setToolTip("按规则自动移入隔离区")
        mw.action_btn_auto_q.setObjectName("toolGhostBtn")

        more_panel = QWidget()
        more_layout = QVBoxLayout(more_panel)
        more_layout.setContentsMargins(10, 10, 10, 10)
        more_layout.setSpacing(4)
        for _btn in (
            mw.action_btn_toggle_progress, mw.action_btn_auto_q,
        ):
            _btn.setMinimumWidth(150)
            more_layout.addWidget(_btn)
        more_layout.addStretch(1)

        mw.action_btn_more = QToolButton()
        # 设计稿这一段第三颗是 icon-only 的 ⋮（.tool-btn），不再占一颗带文字的菜单位
        mw.action_btn_more.setObjectName("toolViewBtn")
        mw.action_btn_more.setIcon(get_icon("dots", 16))
        mw.action_btn_more.setText("更多")
        mw.action_btn_more.setToolButtonStyle(Qt.ToolButtonIconOnly)
        mw.action_btn_more.setFixedSize(30, 30)
        mw.action_btn_more.setPopupMode(QToolButton.InstantPopup)
        mw.action_btn_more.setToolTip(
            "进度 / 自动隔离 · 规则中心（隔离/已读/阈值）/ 物料画像 · 输出目录 · 收起左栏展开项\n"
            "快捷键：F5 分析 · F6 导出 · F7 效益报告 · F11 全屏")
        more_menu = QMenu(mw)
        _more_widget_action = QWidgetAction(more_menu)
        _more_widget_action.setDefaultWidget(more_panel)
        more_menu.addAction(_more_widget_action)
        more_menu.addSeparator()
        # 原「维护」菜单两项 + 输出目录（裴哥定：左栏改纯导航后，输出目录进「更多」）
        # v43.356 第四期E：这一项不再另开窗口，而是打开规则中心的 Tab①——
        # 隔离/已读/阈值三套规则只能有一个编辑处，否则又回到「各写各的」。
        _icon_action(more_menu, "shield", "自动隔离规则（规则中心）",
                     lambda: mw._open_auto_quarantine_rule_dialog())
        _icon_action(more_menu, "id-card", "物料画像", lambda: mw._show_material_profile())
        _icon_action(more_menu, "folder-open", "输出目录…", lambda: mw._select_output_dir())
        more_menu.addSeparator()
        _collapse_act = QAction("收起左栏展开项", more_menu)
        # v43.341 的「紧凑左栏 236/360 双模式」已被第五期C 取代：左栏恒为 236px 纯
        # 导航，展开某块表单时才临时拉宽，所以这里只剩「把展开项收回去」这一个动作。
        _collapse_act.triggered.connect(lambda: mw.left_panel_component.collapse_all())
        more_menu.addAction(_collapse_act)
        mw.action_btn_more.setMenu(more_menu)
        mw.action_collapse_nav = _collapse_act
        action_layout.addWidget(mw.action_btn_more)

        # 一次性面板按钮点完收起菜单，避免遮住主界面
        for _once in (mw.action_btn_auto_q,):
            _once.clicked.connect(lambda _c=False, m=more_menu: m.close())

        action_layout.addStretch(1)

        # ═══ 右端提示（设计稿 .hint）：共 N 条 + 快捷键胶囊 ═══
        # 条数与底部状态条同源：bottom_bar.set_records() 顺手刷新这颗标签，
        # 避免出现两处「记录数」各说各话。
        # 三段（共 / 数字 / 条）拆开而不是富文本：数字要单独吃 #actionHintCount 的
        # 等宽字体与正文色，写死 inline style 的话切主题就不跟着 QSS 变了。
        count_box = QWidget()
        count_box.setObjectName("actionHint")
        count_layout = QHBoxLayout(count_box)
        count_layout.setContentsMargins(0, 0, 0, 0)
        count_layout.setSpacing(3)
        for _txt, _obj in (("共", "actionHintText"), ("—", "actionHintCount"),
                           ("条", "actionHintText")):
            _lbl = QLabel(_txt)
            _lbl.setObjectName(_obj)
            count_layout.addWidget(_lbl)
        mw.action_hint_count = count_box.findChildren(QLabel)[1]
        mw.action_hint_count.setToolTip("当前主表条数（与底部状态条同源）")
        action_layout.addWidget(count_box)

        for _key, _label in (("F5", "分析"), ("F11", "全屏")):
            _kbd = QLabel(_key)
            _kbd.setObjectName("kbdChip")
            action_layout.addWidget(_kbd)
            _txt = QLabel(_label)
            _txt.setObjectName("actionHintText")
            action_layout.addWidget(_txt)

        # 底部按钮行已删除，start_btn 别名指向顶部工具栏分析按钮（供分析起止启用/禁用）
        mw.start_btn = mw.action_btn_analyze

        return action_bar

    def _make_separator(self) -> QWidget:
        """制作工具栏分隔符."""
        w = QWidget()
        w.setObjectName("toolbarSep")
        w.setFixedWidth(1)
        w.setFixedHeight(20)
        return w

    def _make_body_area(self, mw) -> QWidget:
        """制作主体区域（侧栏 + 表格 + 日志）."""
        body_splitter = QSplitter(Qt.Horizontal)

        # 左侧面板
        body_splitter.addWidget(mw.left_panel)

        # 右侧筛选面板（FilterPanel）
        body_splitter.addWidget(mw.filter_panel)
        mw.filter_panel.setVisible(False)  # 默认隐藏

        # 右侧：审核表格 + 日志面板
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        # 上半部分：KPI 概览带 + 分析进度（用户可拖动）
        top_panel = QWidget()
        top_panel.setObjectName("topPanel")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        top_layout.addWidget(mw.stats_cards)                # KPI 概览带（固定 54px）
        top_layout.addWidget(mw.main_table.progress_group)  # 分析进度
        # v43.349 第五期D：不再限高 235。概览带自己钉死 54px，进度面板收起后
        # top_panel 的最大高度就跟着缩到 54，多出来的高度自动回到表格里
        # （以前靠一个写死的数字压着，收起进度也腾不出空间）。

        # 将 top_panel 引用保存到主窗口，以便控制器访问
        mw.top_panel = top_panel

        # 垂直分割器：仅表格（运行日志已移除，空间全部给表格）
        _v_splitter = QSplitter(Qt.Vertical)
        _v_splitter.setChildrenCollapsible(True)
        _v_splitter.addWidget(mw.main_table.audit_widget)
        _v_splitter.setStretchFactor(0, 1)

        # 右侧整体垂直分割器：上面概览/进度，下面表格
        _right_v_splitter = QSplitter(Qt.Vertical)
        _right_v_splitter.setChildrenCollapsible(True)
        _right_v_splitter.addWidget(top_panel)
        _right_v_splitter.addWidget(_v_splitter)
        _right_v_splitter.setSizes([110, 690])   # 54 KPI 带 + 6 间距 + 进度条一小截
        _right_v_splitter.setStretchFactor(0, 0)
        _right_v_splitter.setStretchFactor(1, 1)

        right_layout.addWidget(_right_v_splitter, 1)
        right_layout.addWidget(mw.main_table.summary_container, 0)

        body_splitter.addWidget(right_container)
        # v43.349 第五期C：左栏改 236px 纯导航，首值须与 setFixedWidth 匹配，
        # 否则 splitter 约束和控件约束打架（v43.337 时代是 360）。
        body_splitter.setSizes([236, 440, 860])

        return body_splitter
