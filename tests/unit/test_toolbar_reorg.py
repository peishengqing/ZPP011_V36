# -*- coding: utf-8 -*-
_CJK_FONT_OK = False

"""工具栏重组回归：18 平级按钮 → 8 平铺 + 3 收纳菜单（看板/导出/维护）。

锁定 2026-09-30 的整理结果：
- 窗口最小宽度不再被工具栏顶到 1795px（1366 屏可用）
- 高频视图开关（隐藏左侧栏/隐藏筛选/列头筛选）保留平铺（用户明确要求）
- 替代料卡片默认折叠，「共 N 对」摘要在卡片头
- 分析完成后自动收起进度面板（新一轮分析进行中不收起）
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
    """工具栏：8 个平铺按钮 + 3 个收纳菜单，高频视图开关保留平铺。"""
    from PySide6.QtWidgets import QToolButton

    w = main_window
    bar = _action_bar(w)
    assert bar is not None and bar.objectName() == "actionBar"

    menu_texts = [b.text() for b in bar.findChildren(QToolButton) if b.objectName() == "actionMenuBtn"]
    assert menu_texts == ["📊 看板 ▾", "📤 导出 ▾", "🔧 维护 ▾"], "收纳菜单异常: %s" % menu_texts

    flat = [b.text() for b in bar.findChildren(QPushButton) if b.parentWidget() is bar]
    for must in ["📊 分析", "☰ 隐藏左侧栏", "☰ 隐藏筛选", "🔽 列头筛选",
                 "📊 概览", "⚡ 进度", "📋 未读概览"]:
        assert must in flat, "平铺按钮缺失: %s（现有 %s）" % (must, flat)
    for gone in ["管理看板", "隔离区", "变动提醒", "替代料看板", "偏差率预警",
                 "负损看板", "完整报告", "自动整理隔离区", "🤖 AI审核"]:
        assert gone not in flat, "%s 不应再平铺（应收进菜单或已移除）" % gone


def test_menu_contents(main_window):
    """三个收纳菜单内容：看板 6 项 / 导出 3 项 / 维护 2 项。"""
    from PySide6.QtWidgets import QToolButton

    w = main_window
    menus = {}
    for b in _action_bar(w).findChildren(QToolButton):
        m = b.menu()
        menus[b.text()] = [a.text() for a in m.actions() if not a.isSeparator()] if m else []

    assert len(menus.get("📊 看板 ▾", [])) == 6, menus.get("📊 看板 ▾")
    assert len(menus.get("📤 导出 ▾", [])) == 3, menus.get("📤 导出 ▾")
    assert len(menus.get("🔧 维护 ▾", [])) == 2, menus.get("🔧 维护 ▾")
    assert "📊 管理看板" in menus["📊 看板 ▾"]
    assert "⚠️ 隔离区" in menus["📊 看板 ▾"]
    assert "🧹 自动整理隔离区" in menus["🔧 维护 ▾"]
    assert "📋 完整报告" in menus["📤 导出 ▾"]


def test_window_fits_1366_screen(main_window):
    """窗口最小宽度必须 ≤ 1300（改动前 1795，1366 屏放不下）。"""
    if not _CJK_FONT_OK:
        pytest.skip("无 CJK 字体，sizeHint 不可信")
    m = main_window.minimumSizeHint().width()
    assert m <= 1300, "窗口最小宽度回到 >1300：%d" % m


def test_alt_card_collapsed_by_default_with_count_in_header(main_window):
    """替代料卡片默认折叠；「共 N 对」摘要在卡片头（折叠时仍可见）。"""
    w = main_window
    container = w.left_panel_component.alt_group.container
    body = [c for c in container.children() if c.objectName() == "cardBody"][0]
    assert not body.isVisible(), "替代料卡片必须默认折叠"
    assert w.alt_count_label.parent().objectName() == "cardHeader", \
        "计数标签应在卡片头（当前 parent=%s）" % w.alt_count_label.parent().objectName()


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
