# -*- coding: utf-8 -*-
_CJK_FONT_OK = False

"""工具栏重组回归：18 平级按钮 → 三段分层 9 平铺（主操作│视图开关│收纳）。

锁定 2026-09-30 的整理结果（v43.262 对齐裴哥此后的有意演化）：
- 窗口最小宽度不再被工具栏顶到 1795px（1366 屏可用）
- 高频视图开关（隐藏左侧栏/隐藏筛选/列头筛选）保留平铺（用户明确要求）
- 左栏默认全收起（v43.349 第五期C 起为 236px 纯导航，计数走行尾胶囊；更早的
  卡片时代是「替代料卡片默认折叠 + 「共 N 对」在卡片头」）
- 分析完成后自动收起进度面板（新一轮分析进行中不收起）

演化史（测试为何是现在这副模样）：
- v43.218 LayoutComposer 重建操作栏：视图开关改 QToolButton、文本改为
  「分析 / ☰ 左侧栏 / 🔍 筛选 / 📢 未读」（旧文本「📊 分析 / ☰ 隐藏左侧栏 /
  ☰ 隐藏筛选 / 📋 未读概览」作废）；
- v43.228 裴哥亲手提交「恢复看板与导出的下拉菜单选项」：收纳菜单不带 ▾
  （MenuButtonPopup 模式自带箭头）、看板菜单重建；
- ARC-003 加「🔒 自动隔离」平铺按钮、物料画像挪进维护菜单。
  本文件自 v43.228 起假红数日，v43.262 对齐现行设计并补 objectName 定位；
- v43.264 裴哥选「A 全做」UI 现代化：全仓 emoji → 内联 SVG 线性图标
  （utils/icons.py），按钮/菜单文本去 emoji 前缀（图标承担语义），本文件
  同步对齐纯文本断言（图标本身由 icons.py 单测与离屏渲染保障）。
- v43.341 设计稿第2项「13→8」：概览/进度/审核/未读/自动隔离 5 个低频按钮
  收进「更多」QWidgetAction 弹出面板（按钮对象与连接全部保留，只换 parent），
  收纳菜单随之变为 4 个；本文件改为断言「高频仍平铺 + 低频已收拢且对象仍在」，
  并新增左栏收纳菜单里那条动作（当时叫「紧凑左栏（236px 导航）」）。
- v43.349 第五期B「操作栏三段分层」（照抄设计稿 Tier 2）：审核/概览请回主操作与
  视图开关位，视图开关统一 icon-only 30×30（toolViewBtn），「维护」菜单退役
  （自动隔离规则/物料画像并入「更多」），「更多」改 ⋮ icon-only，右端加
  「共 N 条 + F5/F11 胶囊」提示；平铺控件定型为 9 颗。
- v43.349 第五期C「左栏纯导航」（照抄设计稿 Tier 3）：卡片体系删除，左栏恒为
  236px 九行 nav-item；「紧凑左栏」双模式开关作废，改为「收起左栏展开项」。
- v43.349 第五期D「概览压成 54px KPI 带」：卡片 + 「本次分析概览」标题行（含标题行里
  那颗重复的「隐藏」按钮）一起删除，改为 7 格等宽、格间 1px 竖线的等高带。本文件里
  凡按「卡片/标题行」定位概览的断言，改为按 KPI 带（高 54、7 格、可点格带右向箭头）断言。
- v43.349 第五期E「表格格式照抄」：行高 28→36、表头两行居中→单行 32px 左对齐、
  关竖网格线改每行 1px 下边框；悬浮淡色/选中 3px 蓝条/「偏差区间」状态胶囊由
  RowStyleDelegate 自绘（QSS 做不到：行底色带数据语义，只能用半透明叠加）。
  第 0 列（状态）宽度 35→52，因为表头左缘 20px 是筛选漏斗角标的槽。
- v43.349 第五期F「底部状态条并成一条」：改造前中央布局挂一根自制条、原生
  QStatusBar 又挂四个常驻标签，两条叠着多吃 30px。现在 BottomBarComponent 本身就是
  主窗口唯一的 QStatusBar —— 高频指标（状态点/已选/共/偏差合计/未读）在左，
  低频（分析时间/已读计数/列头筛选/版本号）经 addPermanentWidget 落在右，
  等价设计稿的 .status-right{margin-left:auto}。布局因此少一项，中央布局高度分配
  随之变化，本文件的 1366×768 可用性断言按新分配复核。
- v43.350 第五期G1「行首勾选列」：设计稿表格首列那颗 .chk 做成**垂直表头**（勾选道，
  宽 46 = 13px 框 + 行号），不是真加一列 —— 模型列号 == DataFrame 列号的 1:1 映射一旦
  集体 +1，列宽持久化、自适应、列头筛选、复制区域全要重算。勾选 = 该行在 selectionModel
  里被选中，所以「已选 n 行」与批量已读/导出/隔离零改动复用。左上角三态全选框由新的
  MainTableView 手工摆到两块表头交叉区（PySide6 6.6.3 的 setCornerWidget 只会放右下角）。
  主表视图因此从 QTableView 变成它的子类，test_main_window_smoke 的关键属性契约同步改名。
- v43.351 第五期G2「行尾悬浮操作按钮」：设计稿最后那列 74px 的 .rowact（划过某行才在该行
  右端露出铅笔/三点）同样**不是真列**。曾试让视口右端让出 74px：setViewportMargins 会被
  QTableView::layoutViews() 每次重排打回基准值（道成为视口子控件后 ChildAdded 触发的那次
  延迟重排把补位彻底吃掉），叠在视口里又会盖住最后一列。故新控件 RowActionLane 是表格在
  QFrame#tableShell 里的并排兄弟，边框从 #tableView 挪到壳上；自适应列宽预算取
  viewport().width() 因此自动少 74px，无需改动。悬浮行仍只有 RowStyleDelegate 一个真源
  （新增 hover_row_changed / set_hover_row 给道复用），划过不改选择；两颗按钮只是既有入口
  （审核证据卡 / _show_context_menu），不新增业务。主表因此多包了一层壳，全屏切换只做
  visibility 翻转不动父子关系，故不受影响。
"""
import os
import shutil
import sys

import pytest
from pytest import MonkeyPatch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="module")
def main_window(qapp, tmp_path_factory):
    """离屏构造一个真实 MainWindow，副作用全部指向临时目录。"""
    import core.read_status as rs
    import gui_pyside6.main_window as mw
    from core.alert_monitor import AlertMonitor
    from core.config_manager import ConfigManager as _CM

    # 审核库 → 临时副本，避免测试读写用户真实数据
    db_tmp = tmp_path_factory.mktemp("audit_db")
    real_db = rs.DB_PATH
    if os.path.exists(real_db):
        shutil.copy2(real_db, str(db_tmp / "audit.db"))
    rs.DB_PATH = str(db_tmp / "audit.db")

    # 配置管理器 → 临时文件
    cfg_tmp = tmp_path_factory.mktemp("cfg") / "cm.json"

    def _mk_cm(*a, **k):
        return _CM(config_path=cfg_tmp)

    # 屏蔽碰真实磁盘的副作用（文件夹监控 / 告警线程）
    mp = MonkeyPatch()
    mw.MainWindow._seed_monitor_baseline = lambda self: None
    mw.MainWindow._scan_monitor_dir = lambda self, *a, **k: None
    AlertMonitor.start = lambda self: None
    AlertMonitor.stop = lambda self, *a, **k: None
    mp.setattr(mw, "ConfigManager", _mk_cm)

    # 加载 CJK 字体再构造窗口：字体影响 sizeHint，无 CJK 字体时回退字形更宽，
    # 宽度断言只在字体加载成功时才可信
    global _CJK_FONT_OK
    _CJK_FONT_OK = False
    try:
        from PySide6.QtGui import QFontDatabase, QFont
        for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
            fid = QFontDatabase.addApplicationFont(fp)
            if fid >= 0 and any("YaHei" in f or "SimHei" in f for f in QFontDatabase.applicationFontFamilies(fid)):
                qapp.setFont(QFont("Microsoft YaHei" if "YaHei" in "".join(QFontDatabase.applicationFontFamilies(fid)) else "SimHei", 9))
                _CJK_FONT_OK = True
                break
    except Exception:
        pass

    w = mw.MainWindow()
    w.show()
    yield w
    rs.DB_PATH = real_db
    mp.undo()


def _action_bar(w):
    return w.findChild(QPushButton_ref(), "actionBtnAnalyze").parentWidget()


from PySide6.QtWidgets import QPushButton  # noqa: E402

def QPushButton_ref():
    return QPushButton


def test_toolbar_grouped_layout(main_window):
    """工具栏三段分层：主操作 │ 视图开关 │ 收纳（v43.349 第五期B，照抄设计稿 Tier 2）。

    可见控件 9 颗：分析(实心) / 审核(描边) │ 数据表 / 筛选抽屉 / 列头过滤 / 概览面板
    （4 颗 icon-only 30×30）│ 看板 / 导出（描边文字）/ ⋮更多（icon-only）。
    低频开关 进度 / 未读 / 自动隔离 仍在「更多」弹出面板里，对象与连接不变。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QToolButton, QPushButton, QWidgetAction

    w = main_window
    bar = _action_bar(w)
    assert bar is not None and bar.objectName() == "actionBar"

    # 收纳菜单只剩 看板 / 导出（维护并入「更多」，「更多」改 icon-only 不再算菜单位）
    menu_texts = [b.text() for b in bar.findChildren(QToolButton)
                  if b.objectName() == "actionMenuBtn"]
    assert menu_texts == ["看板", "导出"], "收纳菜单异常: %s" % menu_texts

    # 平铺控件 = 工具栏直接子级里的按钮（9 颗，设计稿 Tier 2 一条不多一条不少）
    flat = [b.text() for b in (bar.findChildren(QPushButton) + bar.findChildren(QToolButton))
            if b.parentWidget() is bar]
    assert flat == ["分析", "审核", "数据表", "筛选抽屉", "列头过滤", "概览面板",
                    "看板", "导出", "更多"], "平铺控件异常: %s" % flat

    # 视图开关一律 icon-only + 30×30（文字只给读屏与状态同步用）
    for attr in ("action_btn_left_panel", "action_btn_filter",
                 "action_btn_col_filter", "action_btn_toggle_stats"):
        btn = getattr(w, attr)
        assert btn.toolButtonStyle() == Qt.ToolButtonIconOnly, "%s 应 icon-only" % attr
        assert (btn.maximumWidth(), btn.maximumHeight()) == (30, 30), "%s 应 30×30" % attr

    # 左栏默认可见 → 数据表开关默认 on；概览默认 on
    assert w.action_btn_left_panel.isChecked(), "左栏默认可见，数据表开关应处于 on"
    assert w.action_btn_toggle_stats.isChecked(), "概览默认展开，开关应处于 on"

    # 「更多」面板里 3 个按钮对象仍在（连接 / setChecked 同步不断链）
    more = w.action_btn_more
    widget_actions = [a for a in more.menu().actions()
                      if isinstance(a, QWidgetAction)]
    assert widget_actions, "「更多」菜单缺少 QWidgetAction 弹出面板"
    panel_texts = [b.text() for b in
                   widget_actions[0].defaultWidget().findChildren(QToolButton)]
    for must in ["进度", "自动隔离"]:
        assert must in panel_texts, "「更多」面板缺失: %s（现有 %s）" % (must, panel_texts)
    assert any(a.text() == "收起左栏展开项"
               for a in more.menu().actions()), "「更多」菜单缺少收起展开项动作"


def test_menu_contents(main_window):
    """收纳菜单内容：看板 8 项 / 导出 2 项；「更多」= 面板 + 原「维护」两项 + 输出目录。

    历史：v43.189 工具栏收纳改造时看板菜单为 6 项，断言一直停在 6（假红数日，
    v43.198 修正为逐项断言）；v43.218 LayoutComposer 重建操作栏、v43.228 裴哥
    亲手恢复下拉菜单并重建看板菜单（9 项）、ARC-003 加自动隔离按钮、物料画像
    挪进维护菜单 → 看板定型为 8 项。除总数外逐个断言关键项，防将来再扩菜单时
    数字对但内容错。v43.349 第五期B：「维护」菜单退役，两项并入「更多」。
    """
    from PySide6.QtWidgets import QToolButton

    w = main_window
    menus = {}
    for b in _action_bar(w).findChildren(QToolButton):
        m = b.menu()
        if b.objectName() == "actionMenuBtn":
            menus[b.text()] = ([a.text() for a in m.actions() if not a.isSeparator()]
                               if m else [])

    assert len(menus.get("看板", [])) == 8, menus.get("看板")
    assert len(menus.get("导出", [])) == 2, menus.get("导出")
    assert "维护" not in menus, "「维护」菜单已退役（两项并入「更多」）"
    for must in ["替代料看板", "偏差率预警", "负损看板", "正损看板",
                 "隔离区", "数据稳定性", "替代料长链", "半成品看板"]:
        assert must in menus["看板"], "%s 不在看板菜单（现有 %s）" % (must, menus["看板"])
    for must in ["导出当前表格", "导出完整偏差"]:
        assert must in menus["导出"], "%s 不在导出菜单（现有 %s）" % (must, menus["导出"])

    more_texts = [a.text() for a in w.action_btn_more.menu().actions()
                  if not a.isSeparator() and a.text()]
    for must in ["自动隔离规则", "物料画像", "输出目录…"]:
        assert must in more_texts, "%s 不在「更多」菜单（现有 %s）" % (must, more_texts)


def test_window_fits_1366_screen(main_window):
    """窗口最小宽度必须 ≤ 1300（改动前 1795，1366 屏放不下）。"""
    if not _CJK_FONT_OK:
        pytest.skip("无 CJK 字体，sizeHint 不可信")
    m = main_window.minimumSizeHint().width()
    assert m <= 1300, "窗口最小宽度回到 >1300：%d" % m


def test_nav_sidebar_default_collapsed_with_count_pills(main_window):
    """左栏纯导航（v43.349 第五期C）：表单默认全收起，计数走行尾胶囊。

    替代旧契约「四张卡片 + 「共 N 对」在卡片头」：卡片体系已删，摘要改由
    nav-item 右端的 .count 胶囊承载，完整口径（共 N 对 / 共 N 类·M 个物料）
    留在展开后的 navBody 里。
    """
    w = main_window
    lp = w.left_panel_component
    assert w.left_panel.width() == 236, "左栏必须是设计稿的 236px 导航宽"
    assert lp._expandables, "四个可展开表单不能丢"
    assert all(body.isHidden() for _btn, body in lp._expandables), \
        "导航态必须默认全收起"
    assert w.alt_count_label.parent().objectName() == "navBody", \
        "「共 N 对」说明应在展开表单内（当前 parent=%s）" \
        % w.alt_count_label.parent().objectName()
    assert set(lp.badges) == {"unread", "quarantine", "alt", "semi"}, \
        "四颗待办/配置胶囊缺一不可（现有 %s）" % sorted(lp.badges)


def test_progress_autocollapse_guarded_by_heavy_busy(main_window):
    """自动收起进度面板：新一轮分析进行中（_heavy_busy）时不得收起。"""
    w = main_window
    w.main_table.set_progress_visible(True)
    w._heavy_busy = True
    w._auto_collapse_progress_after_analysis()
    assert w.main_table._progress_hidden is False, "分析进行中不应收起进度面板"

    w._heavy_busy = False
    w._auto_collapse_progress_after_analysis()
    assert w.main_table._progress_hidden is True, "空闲 6s 后应自动收起"


def test_progress_notifications_do_not_regress_bar(main_window):
    """进度守卫：低值通知（过滤/搜索 percent=0）不回退进度条与步骤图标。"""
    w = main_window
    w._on_analysis_ui_start()
    try:
        w._on_analysis_progress_ui(60, "3/5 正在计算偏差金额和偏差率")
        assert w.progress_bar.value() == 60

        w._on_analysis_progress_ui(0, "已按开始日期 2026-01-01 过滤")
        assert w.progress_bar.value() == 60, "低值通知不得回退进度条"
        assert "过滤" in w.progress_label.text(), "标签应显示通知文字"

        w._on_analysis_progress_ui(80, "5/5 主表计算完成")
        assert w.progress_bar.value() == 80, "通知后正常发射应继续前进"
    finally:
        w._stop_countdown()
        w.progress_bar.setValue(0)


def test_step_icons_follow_real_step_names(main_window):
    """步骤图标由 analyzer 发射的真实步骤名驱动（不再是百分比切段），且只进不退。"""
    mt = main_window.main_table
    mt.reset_step_icons()

    def active():
        return [i for i, b in enumerate(mt.step_icons) if b.property("active")]

    def done():
        return [i for i, b in enumerate(mt.step_icons) if b.property("done")]

    # 主表计算阶段 → 图标 0
    mt.update_step_icons(5, "1/5 正在读取 Excel 文件")
    assert active() == [0]
    # SheetN → 对应图标 N
    mt.update_step_icons(25, "Sheet1-汇总统计")
    assert active() == [1] and done() == [0]
    mt.update_step_icons(70, "Sheet5-完整偏差明细")
    assert active() == [5] and done() == [0, 1, 2, 3, 4]
    # 里程碑「主表计算完成」不动图标
    mt.update_step_icons(85, "5/5 主表计算完成")
    assert active() == [5], "里程碑不应点亮新图标"
    # 完整报告路径：Sheet6→生成Excel 逐级前进
    mt.update_step_icons(85, "Sheet6-异常预警")
    assert active() == [6]
    mt.update_step_icons(96, "5/5 正在生成审核表格")
    assert active() == [11] and done() == list(range(11))
    # 乱序/通知发射：图标不得回退
    mt.update_step_icons(0, "已按开始日期 2026-01-01 过滤")
    assert active() == [11]
    mt.update_step_icons(5, "1/5 正在读取 Excel 文件")
    assert active() == [11], "乱序发射不得把图标打回去"

    # 状态文字：完成=√，进行中/待办=数字（不依赖 emoji 字体）
    mt.reset_step_icons()
    mt.update_step_icons(70, "Sheet5-完整偏差明细")
    texts = [b.text() for b in mt.step_icons]
    assert texts[:5] == ["\u221a"] * 5, "前 5 格应为 √: %s" % texts
    assert texts[5] == "6" and texts[6] == "7", "进行中/待办应为数字: %s" % texts


def test_step_icons_reset_between_runs(main_window):
    """新一轮分析开始时图标指针归零、文字回到数字态。"""
    mt = main_window.main_table
    mt.complete_step_icons()
    assert [b.text() for b in mt.step_icons] == ["\u221a"] * len(mt.step_icons)
    mt.reset_step_icons()
    assert mt._step_icon_pos == 0
    assert [b.text() for b in mt.step_icons] == [str(i + 1) for i in range(len(mt.step_icons))]
    assert not [b for b in mt.step_icons if b.property("done") or b.property("active")]


def test_cache_phase_keeps_timer_and_updates_label(main_window):
    """缓存阶段：计时器不停、标签显示缓存步骤、进度条不被 85~96 的回发打回 100 之下。"""
    w = main_window
    w._on_analysis_ui_start()
    w._on_analysis_progress_ui(100, "5/5 分析完成")
    assert w._countdown_timer is not None and w._countdown_timer.isActive()

    w._on_cache_progress_ui(88, "Sheet7-偏差金额分析")
    assert "完整报告缓存" in w.progress_label.text() and "Sheet7" in w.progress_label.text()
    assert w.progress_bar.value() == 100, "缓存阶段发射不得把进度条打回"
    assert w._countdown_timer.isActive(), "缓存阶段计时器必须继续走"


def test_finish_cache_phase_stops_timer(main_window):
    """缓存结束收口计时器；但新一轮分析进行中时不得停表。"""
    import types

    w = main_window
    w._on_analysis_ui_start()
    w._finish_cache_phase()
    assert not w._countdown_timer.isActive(), "空闲时缓存结束应停表"

    w._on_analysis_ui_start()
    assert w._countdown_timer.isActive()
    orig = w.analysis_controller.worker
    w.analysis_controller.worker = types.SimpleNamespace(isRunning=lambda: True)
    try:
        w._finish_cache_phase()
        assert w._countdown_timer.isActive(), "新一轮分析进行中不得停它的计时器"
    finally:
        w.analysis_controller.worker = orig
        w._stop_countdown()
