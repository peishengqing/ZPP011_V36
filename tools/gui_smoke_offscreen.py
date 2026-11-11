# -*- coding: utf-8 -*-
"""ZPP011 GUI offscreen 冒烟（v43.339，纳入推送门禁第⑤步）。

真实构建 MainWindow 并跑一段事件循环，逐项验证主界面 6 项结构与三看板外壳，
并专门断言「列宽自适应真装上 / set_data 没有吞掉异常」——
v43.338 抓到的 UnboundLocalError 就是被 try/except 吞掉、表面全绿却功能失效，
pytest 381 全过也没能发现。本工具的存在就是堵住这类漏网。

用法：
    python tools/gui_smoke_offscreen.py
退出码：0=全部通过，1=存在失败项。
QT_QPA_PLATFORM=offscreen 由脚本自行设置，无需外部指定。
"""
import contextlib
import datetime
import io
import os
import re
import sys
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QStyleFactory, QLabel, QPushButton, QWidget,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTimer

from gui_pyside6.components.dashboard_shell import DashboardShell
from gui_pyside6.utils.table_autofit import get_adaptive

RESULTS = []


def check(name, fn):
    try:
        ok, info = fn()
        RESULTS.append((name, bool(ok), str(info)))
    except Exception as exc:
        RESULTS.append((name, False, "%s: %s" % (type(exc).__name__, exc)))
        traceback.print_exc()


def _receiver_count(owner, sig):
    """信号接收者数量（与 tests/test_main_window_smoke.py 同一手法）。

    PySide6 的 ``QObject.receivers()`` 只认 C++ 签名字符串，SignalInstance 没有
    ``.signal`` 属性，所以从 repr 里反解 ``name(args)``。
    """
    m = re.search(r"SignalInstance (\w+)\((.*?)\)", repr(sig))
    if not m:
        return -1
    return owner.receivers("2%s(%s)" % (m.group(1), m.group(2)))


def build_app():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("ZPP011")
    app.setOrganizationName("云南达利食品有限公司")
    app.setFont(QFont("Microsoft YaHei", 9))
    if "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))
    return app


def sample_df():
    return pd.DataFrame({
        # 400/410 开头：保证 _show_semi_dashboard 的 400/410 子集非空（v43.340 多开验证）
        "物料编码": ["400001", "410001", "M003"],
        "数量-定额": [100.0, 200.0, 300.0],
        "数量-实际": [90.0, 210.0, 300.0],
        "净偏差金额": [-1000.0, 500.0, 0.0],
        "_read": [0, 0, 1],
    })


def report():
    print("\n" + "=" * 68)
    print("GUI SMOKE RESULT  (QT_QPA_PLATFORM=offscreen)")
    print("=" * 68)
    npass = 0
    for name, ok, info in RESULTS:
        print("[%s] %-44s %s" % ("PASS" if ok else "FAIL", name, info))
        npass += int(ok)
    print("-" * 68)
    print("TOTAL: %d/%d PASS" % (npass, len(RESULTS)))
    print("=" * 68)
    return 0 if npass == len(RESULTS) else 1


def main():
    app = build_app()

    # 滞后到 QApplication 建立后再导入，避免模块 import 期触碰 Qt 组件
    from gui_pyside6.main_window import MainWindow
    from gui_pyside6.widgets.neg_loss_content import NegLossContent
    from gui_pyside6.widgets.pos_loss_content import PosLossContent
    from gui_pyside6.widgets.semi_content import SemiContent

    boards = [("负损", NegLossContent), ("正损", PosLossContent),
              ("半成品", SemiContent)]

    win = None
    try:
        win = MainWindow()
        win.show()
        QTimer.singleShot(1500, app.quit)
        app.exec()
        check("MainWindow 真实构建 + 1.5s 事件循环",
              lambda: (True, "win=%s visible=%s size=%sx%s" %
                       (type(win).__name__, win.isVisible(), win.width(), win.height())))
    except Exception as exc:
        boot_err = "%s: %s" % (type(exc).__name__, exc)
        check("MainWindow 真实构建 + 1.5s 事件循环", lambda: (False, boot_err))
        traceback.print_exc()

    if win is None:
        return report()

    df = sample_df()

    # ① 标题栏（v43.349 第五期A：设计稿 Tier 1 四段式）
    def _title():
        tb = win.title_bar
        by_name = {}
        for lbl in tb.findChildren(QLabel):
            by_name.setdefault(lbl.objectName(), lbl)
        for btn in tb.findChildren(QPushButton):
            by_name.setdefault(btn.objectName(), btn)
        parts = ["titleBrand", "titleMain", "titleBrandSub", "titleCtx",
                 "titleCtxValue", "titleSourceBtn", "themeBtn"]
        missing = [p for p in parts if p not in by_name]
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        before = by_name["titleCtxValue"].text()
        tb.set_data_context("smoke.xlsx", stamp)
        after = by_name["titleCtxValue"].text()
        src_text = by_name["titleSourceBtn"].text()
        # 「数据源」胶囊必须真接到选文件入口（裴哥定：左栏改纯导航后选文件在标题栏）
        wired = _receiver_count(tb, tb.source_requested) >= 1
        ok = (tb.maximumHeight() == 48 and not missing and before != after
              and stamp in after and "smoke.xlsx" in src_text and wired
              and win._version_label.text().startswith("v"))
        return ok, ("height=%s 缺段=%s 上下文 '%s'->'%s' 胶囊='%s' 接线=%s 版本=%s" % (
            tb.maximumHeight(), missing or "无", before, after, src_text, wired,
            win._version_label.text()))
    check("① 标题栏四段式 + 数据源胶囊可选文件", _title)

    # ② 底部状态条（v43.349 第五期F：本组件就是主窗口唯一的 QStatusBar，不再两条叠加）
    def _bottom():
        bb = win.bottom_bar
        one_bar = win.statusBar() is bb
        # 左端高频指标：前缀标签（已选/共/偏差合计/未读）+ 状态文字
        high_freq = [w for w in bb.findChildren(QLabel)
                     if w.objectName() == "bottomStatusLabel"]
        # 右端低频：原先挂在原生状态条上的四个常驻标签，现在必须落进这一根条里
        low_freq = [getattr(win, "_analysis_time_label", None),
                    getattr(win, "_read_counter_label", None),
                    getattr(win, "_col_filter_hint_label", None),
                    getattr(win, "_version_label", None)]
        in_bar = [w for w in low_freq if w is not None and bb.isAncestorOf(w)]
        ok = (bb is not None and bb.maximumHeight() == 30 and bb.parent() is not None
              and one_bar and len(high_freq) >= 4 and len(in_bar) == 4)
        return ok, "height=%s 唯一状态栏=%s 高频=%d 低频常驻=%d/4 状态='%s' 已选='%s' 共='%s' 偏差='%s' 未读='%s'" % (
            bb.maximumHeight(), one_bar, len(high_freq), len(in_bar),
            bb.lbl_state.text(),
            bb.lbl_selected.text(), bb.lbl_records.text(),
            bb.lbl_deviation.text(), bb.lbl_unread.text())
    check("② 底部状态条=唯一 QStatusBar（高频左/低频右）", _bottom)

    # ③ 操作栏四开关 icon-only 30×30（v43.349 第五期B）
    def _toggles():
        names = ["action_btn_left_panel", "action_btn_filter",
                 "action_btn_col_filter", "action_btn_toggle_stats"]
        detail = []
        ok = True
        for n in names:
            b = getattr(win, n, None)
            if b is None:
                ok = False
                detail.append("%s=MISSING" % n)
            else:
                icon_ok = not b.icon().isNull()
                style_ok = b.toolButtonStyle() == Qt.ToolButtonIconOnly
                size_ok = b.maximumWidth() == 30 and b.maximumHeight() == 30
                name_ok = b.objectName() == "toolViewBtn"
                ok = ok and icon_ok and style_ok and size_ok and name_ok
                detail.append("%s(icon=%s,style=%s,30=%s,name=%s)"
                              % (n, icon_ok, style_ok, size_ok, name_ok))
        return ok, " ".join(detail)
    check("③ 操作栏四开关 icon-only 30×30", _toggles)

    # ④ 概览 = 54px KPI 带（v43.349 第五期D：照抄设计稿 .kpi-bar，无标题行）
    def _kpi():
        from PySide6.QtWidgets import QFrame
        sc = win.stats_cards
        cells = [w for w in sc.findChildren(QFrame) if w.objectName() == "statsCard"]
        dots = [w for w in sc.findChildren(QFrame) if w.objectName() == "kpiDot"]
        dividers = [w for w in sc.findChildren(QFrame) if w.objectName() == "kpiDivider"]
        marks = [w for w in sc.findChildren(QLabel) if w.objectName() == "kpiMore"]
        height_ok = (sc.minimumHeight() == 54 and sc.maximumHeight() == 54)
        cells_ok = len(cells) == 7 and all(c.minimumWidth() == 118 for c in cells)
        label_ok = [c.findChildren(QLabel)[0].text() for c in cells] == [
            "AI 通过率", "未读", "真异常", "替代料", "审核后变更", "隔离区", "偏差率预警"]
        accent_ok = len(dots) == 7 and all(d.property("kpiAccent") for d in dots)
        divider_ok = len(dividers) == 6
        mark_ok = sum(1 for m in marks if not m.isHidden()) == 5
        no_title_ok = not any(m.text() == "本次分析概览"
                              for m in win.findChildren(QLabel))
        ok = all((height_ok, cells_ok, label_ok, accent_ok, divider_ok,
                  mark_ok, no_title_ok))
        return ok, ("带高=%s 格=%d 标签序=%s 圆点=%d 竖线=%d 可点标记=%d 无标题行=%s"
                    % (sc.minimumHeight(), len(cells), label_ok, len(dots),
                       len(dividers), sum(1 for m in marks if not m.isHidden()),
                       no_title_ok))
    check("④ 概览 54px KPI 带（7 格 + 圆点 + 竖线 + 可点标记）", _kpi)

    # ⑤ 左栏 236 纯导航 + splitter 首值匹配（v43.349 第五期C：360 → 236）
    def _left():
        lp = getattr(win, "left_panel", None)
        sp = getattr(win, "body_splitter", None)
        w = lp.width() if lp is not None else -1
        sizes = sp.sizes() if sp is not None else []
        ok = lp is not None and w == 236 and bool(sizes) and sizes[0] == 236
        return ok, "left_panel.width=%s splitter.sizes=%s" % (w, sizes[:3])
    check("⑤ 左栏固定宽 236 + splitter 匹配", _left)

    # ⑥ 灌小数据：data_changed -> 底部状态条联动（操作栏「共 N 条」同源）
    def _data():
        win.view_model.df = df
        app.processEvents()
        bb = win.bottom_bar
        rec = bb.lbl_records.text()
        dev = bb.lbl_deviation.text()
        unr = bb.lbl_unread.text()
        hint = getattr(win, "action_hint_count", None)
        hint_txt = hint.text() if hint is not None else "?"
        ok = (rec == "3" and "¥" in dev and unr == "2"
              and hint_txt == "3" and bb.dot.property("dotState") == "warn")
        return ok, "共='%s' 偏差='%s' 未读='%s' 操作栏条数='%s' 状态='%s/%s'" % (
            rec, dev, unr, hint_txt, bb.dot.property("dotState"), bb.lbl_state.text())
    check("⑥ 灌 3 行真实数据 → 状态条 + 操作栏条数同源", _data)

    # ⑥b 选中行数联动（主表为 SelectItems，必须按行号去重统计）
    def _sel():
        if win.proxy_model is None or win.table_view.model() is None:
            return True, "SKIP（proxy_model 未建立，需完整分析链路）"
        try:
            win.source_model.setDataFrame(df)
            win.proxy_model.invalidate()
            app.processEvents()
        except Exception as e:
            return False, "喂表格失败: %s: %s" % (type(e).__name__, e)
        sm = win.table_view.selectionModel()
        if sm is None:
            return False, "selectionModel 为 None"
        try:
            sm.selectionChanged.connect(win._on_selection_changed)
        except Exception:
            pass
        win.table_view.clearSelection()
        app.processEvents()
        win.table_view.selectAll()
        app.processEvents()
        txt = win.bottom_bar.lbl_selected.text()
        return txt != "0", "选中='%s'" % txt
    check("⑥b 选中行数联动（SelectItems 全选）", _sel)

    # ⑦ 三看板 Content + Shell + 亮暗主题
    for label, cls in boards:
        def _content(cls=cls, label=label):
            c = cls(win)
            c.set_data(df)
            shell = DashboardShell()
            shell.set_title("%s看板 · 冒烟" % label)
            c.attach_shell(shell)          # 真实链路：控件交给外壳归位
            shell.set_content(c)
            shell.set_status("已加载 · 共 %d 条" % len(df))
            from utils.theme_manager import Thm
            # 先在亮色基线上设置亮色
            Thm.set_dark(False)
            shell.set_theme("light")
            light_ok = shell.get_theme() == "light" and bool(shell.styleSheet())
            # 再切暗色
            Thm.set_dark(True)
            shell.set_theme("dark")
            dark_ok = shell.get_theme() == "dark" and bool(shell.styleSheet())
            model_ok = c.table_view.model() is not None
            return light_ok and dark_ok and model_ok, "model=%s light=%s dark=%s" % (
                model_ok, light_ok, dark_ok)
        check("⑦ %s看板 Content+Shell+亮暗主题" % label, _content)

    # ⑦b 关键防护：列宽自适应必须真装上，且 set_data 不许吞掉异常。
    # v43.338 的 UnboundLocalError 正是被 try/except 吞掉 → 上面 ⑦ 三项照样全绿，
    # 只有这条断言能抓到「表面能开、功能其实没生效」。
    def _adaptive():
        detail = []
        ok = True
        for label, cls in boards:
            c = cls(win)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                c.set_data(df)
            err = buf.getvalue()
            clean = "Traceback" not in err and "UnboundLocalError" not in err
            ctrl_ok = get_adaptive(c.table_view) is not None
            ok = ok and clean and ctrl_ok
            detail.append("%s(自适应=%s,吞异常=%s)" %
                          (label, ctrl_ok, "有" if not clean else "无"))
        return ok, " ".join(detail)
    check("⑦b 三看板列宽自适应真装上 + 无吞异常", _adaptive)

    # ⑧ 看板多开（v43.340）：端到端走三个真实菜单入口，
    # 验证非模态并存、重复打开复用、关闭后引用清理。
    def _multi_board():
        import gui_pyside6.controllers.dashboard_controller as dc_mod

        # _get_master_df 优先 source_model；先喂数据，三个入口才都能取到
        win.source_model.setDataFrame(df)
        app.processEvents()

        # offscreen 下模态 QMessageBox 会阻塞，临时替换为记录器
        msgs = []

        class _FakeMB:
            @staticmethod
            def information(*a, **k):
                msgs.append(("info", a[-1] if a else ""))

            @staticmethod
            def critical(*a, **k):
                msgs.append(("crit", a[-1] if a else ""))

        orig = dc_mod.QMessageBox
        dc_mod.QMessageBox = _FakeMB
        try:
            ctrl = win.dashboard_controller
            ctrl._show_neg_loss_dashboard()
            ctrl._show_pos_loss_dashboard()
            ctrl._show_semi_dashboard()
            app.processEvents()
            windows = dict(ctrl._board_windows)
            keys_ok = set(windows) == {"neg_loss", "pos_loss", "semi"}
            nonmodal = all(not d.isModal() for d in windows.values())
            distinct = len({id(d) for d in windows.values()}) == 3
            titles = [d.windowTitle() for d in windows.values()]
            ver_ok = bool(titles) and all("v43." in t for t in titles)
            # 重复打开同一看板 → 复用同一实例，不新增
            before = dict(windows)
            ctrl._show_neg_loss_dashboard()
            app.processEvents()
            reused = (len(ctrl._board_windows) == 3 and
                      ctrl._board_windows.get("neg_loss") is before.get("neg_loss"))
            # 关闭一个 → destroyed 信号清理字典引用
            closing = ctrl._board_windows.get("semi")
            if closing is not None:
                closing.close()
                for _ in range(6):
                    app.processEvents()
            cleaned = "semi" not in ctrl._board_windows
            no_error = not any(m[0] == "crit" for m in msgs)
            ok = (keys_ok and nonmodal and distinct and ver_ok and
                  reused and cleaned and no_error)
            return ok, ("keys=%s 非模态=%s 独立=%s 动态版本=%s 复用=%s 关闭清理=%s 提示=%s"
                        % (sorted(windows), nonmodal, distinct, ver_ok,
                           reused, cleaned, msgs))
        finally:
            dc_mod.QMessageBox = orig
            leftover = getattr(win, 'dashboard_controller', None)
            if leftover is not None:
                for d in list(leftover._board_windows.values()):
                    try:
                        d.close()
                    except RuntimeError:
                        pass
                for _ in range(6):
                    app.processEvents()
    check("⑧ 看板多开：三看板非模态并存/复用/清理", _multi_board)

    # ⑨ 操作栏三段分层：主操作2 │ 视图开关4 │ 收纳3 + 右端提示（v43.349 第五期B）
    def _action_bar():
        from PySide6.QtWidgets import QToolButton, QPushButton, QWidgetAction
        more = getattr(win, 'action_btn_more', None)
        assert more is not None, '「更多」按钮未创建'
        bar = more.parent()
        lay = bar.layout()
        direct = [w for w in (lay.itemAt(i).widget() for i in range(lay.count()))
                  if w is not None]  # 尾部 addStretch 的 item 没有 widget
        visible_btns = [w for w in direct
                        if isinstance(w, (QToolButton, QPushButton))]
        seps = [w for w in direct if w.objectName() == "toolbarSep"]
        bar_ok = len(visible_btns) == 9 and len(seps) == 2
        # 低频 3 开关：对象没重建（外部 setChecked 同步不断链），parent 已进弹出面板
        names = ('action_btn_toggle_progress', 'action_btn_auto_q')
        low = [getattr(win, n, None) for n in names]
        kept = all(b is not None for b in low)
        moved = all(b.parent() is not bar for b in low if b is not None)
        # 概览/审核 已请回主操作位（第 2 段视图开关 / 第 1 段主操作）
        promoted = (getattr(win, 'action_btn_toggle_stats', None) in visible_btns
                    and getattr(win, 'action_btn_audit', None) in visible_btns)
        # 按钮对象没被重建：checkable 状态仍可切换
        togglable = False
        if low[0] is not None:
            old = low[0].isChecked()
            low[0].setChecked(not old)
            togglable = low[0].isChecked() == (not old)
            low[0].setChecked(old)
        collapse_act = getattr(win, 'action_collapse_nav', None)
        act_ok = (collapse_act is not None and not collapse_act.isCheckable()
                  and collapse_act.text() == "收起左栏展开项")
        menu_acts = more.menu().actions() if more.menu() is not None else []
        items = [a.text() for a in menu_acts if not a.isSeparator() and a.text()]
        menu_ok = (any(isinstance(a, QWidgetAction) for a in menu_acts) and
                   all(t in items for t in ("自动隔离规则（规则中心）", "物料画像",
                                            "输出目录…", "收起左栏展开项")))
        hint = getattr(win, 'action_hint_count', None)
        hint_ok = hint is not None and hint.objectName() == "actionHintCount"
        ok = (bar_ok and kept and moved and promoted and togglable
              and act_ok and menu_ok and hint_ok)
        return ok, ("可见按钮=%d(期望9) 分隔=%d(期望2) 3对象保留=%s 已搬入菜单=%s "
                    "概览/审核归位=%s 可切换=%s 收起展开项=%s 菜单项=%s 条数提示=%s"
                    % (len(visible_btns), len(seps), kept, moved, promoted,
                       togglable, act_ok, menu_ok, hint_ok))
    check("⑨ 操作栏三段分层 9 可见按钮 + 低频进「更多」", _action_bar)

    # ⑩ 左栏 236px 纯导航：9 行 nav-item + 互斥展开 + 徽标档位（v43.349 第五期C）
    def _left_nav():
        from PySide6.QtWidgets import QPushButton
        lp = win.left_panel_component
        sp = win.body_splitter
        panel = lp.left_panel
        rows = [w for w in panel.findChildren(QPushButton)
                if w.objectName() == "navItem"]
        want = ["偏差明细", "审核队列", "隔离区", "替代料配对",
                "数据源", "材料半成品", "数据预览", "列管理", "筛选预设"]
        rows_ok = [r.text() for r in rows] == want
        on_ok = rows[0].property("navOn") is True and rows[1].property("navOn") != True
        body_of = dict((btn, body) for btn, body in lp._expandables)
        w236, s236 = panel.width(), sp.sizes()[0]
        closed0 = all(b.isHidden() for b in body_of.values())

        # 展开项：点「数据源」拉宽到 360，再点「材料半成品」互斥收起前者
        src = [b for b in body_of if b.text() == "数据源"][0]
        src.click()
        opened = not body_of[src].isHidden()
        w_open = panel.width()
        semi = [b for b in body_of if b.text() == "材料半成品"][0]
        semi.click()
        excl = (not body_of[semi].isHidden() and body_of[src].isHidden()
                and not src.isChecked())
        # 点纯导航项（偏差明细）= 收起全部 + 宽度回 236
        rows[0].click()
        collapsed = all(b.isHidden() for b in body_of.values())
        w_back, s_back = panel.width(), sp.sizes()[0]

        pill = lp.badges["unread"]
        lp.set_badge("unread", 37)
        alert_on = pill.text() == "37" and pill.property("alert") == "true"
        lp.set_badge("unread", 0)
        alert_off = pill.text() == "0" and pill.property("alert") == "false"

        ok = (rows_ok and on_ok and w236 == 236 and s236 == 236 and closed0
              and opened and w_open == 360 and excl and collapsed and w_back == 236
              and s_back == 236 and alert_on and alert_off)
        return ok, ("行数=%d(期望9) 顺序=%s 当前区标记=%s 初始=%d/split%d 全收=%s "
                    "展开宽=%d 互斥=%s 收起宽=%d/split%d 徽标=%s/%s"
                    % (len(rows), rows_ok, on_ok, w236, s236, closed0, w_open,
                       excl, w_back, s_back, alert_on, alert_off))
    check("⑩ 左栏 236px 纯导航：互斥展开 + 待办徽标", _left_nav)

    # ⑪ 规则中心：组间 AND / 组内 OR + 只读命中预览（第四期）
    def _rule_preview():
        import os
        from gui_pyside6.dialogs.auto_rules_center_dialog import AutoRulesCenterDialog
        rules_path = os.path.join(REPO, 'config', 'system', 'rules.json')
        try:
            with open(rules_path, 'rb') as fh:
                before_rules = fh.read()
        except OSError:
            before_rules = b''
        dlg = AutoRulesCenterDialog(win, df=df)
        tabs_ok = dlg.tabs.count() == 4
        p = dlg.tab_preview
        g1 = p._groups[0]
        r1 = g1._rows[0]
        r1.col.setCurrentText('物料编码')
        r1.op.setCurrentText('包含')
        r1.val.setText('400')
        p.evaluate()
        hit1 = p.result.text()
        # 组内 OR：再加「物料编码 等于 M003」→ 命中 2 行
        g1.add_row()
        r2 = g1._rows[1]
        r2.col.setCurrentText('物料编码')
        r2.op.setCurrentText('等于')
        r2.val.setText('M003')
        p.evaluate()
        hit2 = p.result.text()
        # 组间 AND：第二组「净偏差金额 大于 0」只命中 410001 → 交集为空
        g2 = p.add_group()
        r3 = g2._rows[0]
        r3.col.setCurrentText('净偏差金额')
        r3.op.setCurrentText('大于')
        r3.val.setText('0')
        p.evaluate()
        hit3 = p.result.text()
        try:
            with open(rules_path, 'rb') as fh:
                after_rules = fh.read()
        except OSError:
            after_rules = before_rules
        readonly = (p.df is df and len(df) == 3
                    and before_rules == after_rules
                    and p.table.model() is p._model)
        dlg.close()
        ok = (tabs_ok and '命中 1 / 共 3 条' in hit1
              and '命中 2 / 共 3 条' in hit2
              and '命中 0 / 共 3 条' in hit3 and readonly)
        return ok, ("tabs=%d 单条件='%s' 组内OR='%s' 组间AND='%s' 只读=%s"
                    % (dlg.tabs.count(), hit1, hit2, hit3, readonly))
    check("⑪ 规则中心 组间AND/组内OR 只读命中预览", _rule_preview)

    # ⑫ 重型弹窗统一外壳（v43.341：不剥壳，原窗口钩子全保留）
    def _heavy_shell():
        from gui_pyside6.dialogs.alert_dialog import AlertDialog
        from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog
        heavy = pd.DataFrame({
            "物料编码": ["400001", "410001", "M003"],
            "物料名称": ["原料A", "原料B", "原料C"],
            "数量-定额": [100.0, 200.0, 300.0],
            "数量-实际": [90.0, 210.0, 300.0],
            "偏差率(%)": [12.0, -15.0, 20.0],
            "净偏差金额": [-1000.0, 500.0, 0.0],
            "_read": [0, 1, 0],
            "data_id": ["d1", "d2", "d3"],
            "备注": ["", "", ""],
            "车间": ["A", "B", "A"],
            "工厂": ["F1", "F1", "F1"],
            "物料类型": ["原料", "包材", "原料"],
            "半成品重分类": ["", "", ""],
            "是否替代料": ["否", "是", "否"],
        })
        detail = []
        ok = True
        cases = (
            ("替代料看板", AlertDialog, ("mark_row_read", "batch_mark_read")),
            ("偏差率预警", DeviationWarningDialog,
             ("open_maximized", "_bind", "closeEvent")),
        )
        for label, cls, required in cases:
            dlg = cls(heavy, win)
            shell = getattr(dlg, 'dashboard_shell', None)
            root_ok = dlg.layout() is not None and dlg.layout().count() == 1
            shell_ok = shell is not None and shell.get_theme() in ('light', 'dark')
            status_ok = (shell is not None
                         and '已加载' in shell._status_label.text())
            host_ok = getattr(dlg, 'shell_host', None) is not None
            table_ok = getattr(dlg, 'table_view', None) is not None
            hooks_ok = all(hasattr(dlg, m) for m in required)
            detail.append("%s(shell=%s,根=%s,状态=%s,host=%s,表=%s,钩子=%s)"
                          % (label, shell_ok, root_ok, status_ok,
                             host_ok, table_ok, hooks_ok))
            ok = ok and all((shell_ok, root_ok, status_ok,
                             host_ok, table_ok, hooks_ok))
            dlg.close()
        return ok, " ".join(detail)
    check("⑫ 重型弹窗统一外壳（原窗口逻辑保留）", _heavy_shell)

    # ⑬ v43.347（第二期）：看板筛选结构验收
    #   旧版断言「筛选区必须是主布局第一项 QScrollArea」正是改造前的病根本身 ——
    #   筛选栏被装进横向滚动区，条件多到拖不完。现在改成结构上限 + 可达性断言。
    def _board_filter_structure():
        from PySide6.QtWidgets import QScrollArea, QLabel as _QLabel
        from utils.theme_manager import Thm
        Thm.set_dark(False)
        detail = []
        ok = True
        for label, cls, board_title in (
            ("负损", NegLossContent, "负损(含未投料)看板"),
            ("正损", PosLossContent, "正损(超投)看板"),
            ("半成品", SemiContent, "半成品看板"),
        ):
            c = cls(win)
            c.set_data(df)
            s = DashboardShell()
            s.set_title(board_title)
            c.attach_shell(s)
            s.set_content(c)
            app.processEvents()
            # ① 永不允许横向滚动筛选栏（设计稿红线：常驻条不可滚动）。
            #    Content 里一个 QScrollArea 都不该有；外壳只保留 KPI 带那条
            #    ScrollBarAlwaysOff 的容器（看板没数据时整条还是隐藏的）。
            content_scroll = len(c.findChildren(QScrollArea))
            loose_scroll = [sa for sa in s.findChildren(QScrollArea)
                            if sa.horizontalScrollBarPolicy() != Qt.ScrollBarAlwaysOff]
            no_scroll = content_scroll == 0 and not loose_scroll
            # ② 常驻条控件数不超上限，其余条件进抽屉
            drawer_keys = [k for k, slot in s._filters.items() if slot.zone == "drawer"]
            bar_n = len(s._filters) - len(drawer_keys)
            bar_ok = 0 < bar_n <= DashboardShell.MAX_PERSISTENT_FILTERS
            # ③ 抽屉条件全部可达：展开时每个控件可见，收起时整组让位。
            #    冒烟样本里没有对应列的条件（如组件物料类型描述）按设计收起，不计入。
            tucked_keys = set(drawer_keys) & getattr(c, "_hidden_filters", set())
            s._on_filter_drawer_toggled()
            app.processEvents()
            reach = sum(1 for k in drawer_keys if s._filters[k].widget.isVisibleTo(s))
            expect = len(drawer_keys) - len(tucked_keys)
            s._on_filter_drawer_toggled()
            app.processEvents()
            tucked = all(not s._filters[k].widget.isVisibleTo(s) for k in drawer_keys)
            # ④ 看板标题只出现一次（外壳标题栏那份，Content 不再自绘）
            dup = len([l for l in c.findChildren(_QLabel)
                       if l.text().strip() == board_title])
            # ⑤ 空操作条不占位：没放控件就隐藏，放了才展开
            probe = DashboardShell()
            act_hidden = probe._action_bar.isHidden()
            probe.set_action_widget(_QLabel("操作"))
            act_shown = not probe._action_bar.isHidden()
            act_ok = (not s._action_bar.isHidden()) and act_hidden and act_shown
            good = (no_scroll and bar_ok and reach == expect and tucked
                    and dup == 0 and act_ok)
            ok = ok and good
            detail.append("%s(内容滚动区=%d,可横滚=%d,常驻=%d,抽屉可达=%d/%d,收起=%s,"
                          "重复标题=%d,操作条=%s)"
                          % (label, content_scroll, len(loose_scroll), bar_n,
                             reach, expect, tucked, dup,
                             "开" if act_ok else "关"))
            s.deleteLater()
            c.deleteLater()
        return ok, " ".join(detail)
    check("⑬ 看板筛选结构：无横滚+常驻≤5+抽屉可达+唯一标题", _board_filter_structure)

    # ⑭ v43.343：QSS 尺寸纪律（对齐 board_visual.py v43.299 红线）
    #        v43.346：探测对象改为 tokens 生成器输出（唯一真源）
    def _qss_discipline():
        from PySide6.QtWidgets import (QPushButton as _QPushButton,
                                      QComboBox as _QComboBox,
                                      QLineEdit as _QLineEdit)
        probe = DashboardShell()
        # v43.346 起外壳 QSS 只有 tokens.build_dashboard_qss() 一个真源：
        # themes/*.qss 是它的落盘产物，兜底副本已删，故探测路径从四条并为两条。
        from gui_pyside6.themes.tokens import build_dashboard_qss
        sources = [("生成亮", build_dashboard_qss("light")),
                   ("生成暗", build_dashboard_qss("dark"))]

        def _size(w):
            s = w.sizeHint()
            return (s.width(), s.height())

        def _make(kind):
            if kind == 'btn':
                return _QPushButton("全部")
            if kind == 'combo':
                w = _QComboBox()
                w.addItems(["全部", "是", "否"])
                return w
            return _QLineEdit("关键字")

        detail = []
        ok = True
        for label, qss in sources:
            changed = []
            for kind in ('btn', 'combo', 'edit'):
                bare = _size(_make(kind))
                w = _make(kind)
                w.setStyleSheet(qss)
                if _size(w) != bare:
                    changed.append("%s %s→%s" % (kind, bare, _size(w)))
            checked_ok = 'QPushButton:checked' in qss
            table_ok = ('QTableView {' in qss) and ('QTableWidget {' not in qss)
            detail.append("%s(尺寸变更=%s,选中态=%s,表格选择器=%s)"
                          % (label, changed or '无', checked_ok, table_ok))
            ok = ok and not changed and checked_ok and table_ok

        # 四个 ID 选择器要有对应的 objectName，否则规则写了也不命中
        pairs = (("_title_bar", "title_bar"), ("_action_bar", "action_bar"),
                 ("_content", "content"), ("_status_bar", "status_bar"))
        names_ok = all(getattr(probe, attr).objectName() == name
                       for attr, name in pairs)
        detail.append("objectName=%s" % names_ok)
        ok = ok and names_ok
        return ok, " ".join(detail)
    check("⑭ QSS 尺寸纪律：两条生成路径零 sizeHint 变更", _qss_discipline)

    # ⑮ v43.345：暗色全链路跟随（真实走 _toggle_theme，且通过 Thm 驱动）
    def _dark_chain():
        from gui_pyside6.dialogs.alert_dialog import AlertDialog
        from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog
        from utils.theme_manager import Thm
        # 显式重置为亮色基线（避免前任测试留下暗色状态）
        Thm.set_dark(False)
        app.processEvents()
        for _ in range(8):
            app.processEvents()
        heavy = pd.DataFrame({
            "物料编码": ["400001", "410002", "M003"],
            "物料名称": ["A", "B", "C"],
            "数量-定额": [100.0, 200.0, 300.0],
            "数量-实际": [90.0, 210.0, 300.0],
            "偏差率(%)": [12.0, -15.0, 20.0],
            "净偏差金额": [-1000.0, 500.0, 0.0],
            "_read": [0, 1, 0],
            "data_id": ["d1", "d2", "d3"],
            "备注": ["", "", ""],
            "车间": ["X", "Y", "X"],
            "工厂": ["F1", "F1", "F1"],
            "物料类型": ["原料", "包材", "原料"],
            "半成品重分类": ["", "", ""],
            "是否替代料": ["否", "是", "否"],
        })
        # 亮色基线：Thm 应为亮
        assert not Thm.is_dark
        light_alert = AlertDialog(heavy, win)
        light_shell = light_alert.findChildren(DashboardShell)[0]
        light_ok = (light_shell.get_theme() == 'light'
                    and len(light_shell.styleSheet()) > 0)
        light_alert.close()

        # 真实切暗色
        win._toggle_theme()
        app.processEvents()
        for _ in range(10):
            app.processEvents()
        dark_active = Thm.is_dark

        ctrl = win.dashboard_controller
        ctrl._show_neg_loss_dashboard()
        ctrl._show_pos_loss_dashboard()
        ctrl._show_semi_dashboard()
        for _ in range(10):
            app.processEvents()
        board_themes = {}
        for key in ("neg_loss", "pos_loss", "semi"):
            d = ctrl._board_windows.get(key)
            shells = d.findChildren(DashboardShell) if d is not None else []
            board_themes[key] = shells[0].get_theme() if shells else "NONE"
        boards_ok = all(v == 'dark' for v in board_themes.values())

        dark_alert = AlertDialog(heavy, win)
        dark_devi = DeviationWarningDialog(heavy, win)
        heavy_ok = True
        for dlg in (dark_alert, dark_devi):
            shells = dlg.findChildren(DashboardShell)
            theme = shells[0].get_theme() if shells else "NONE"
            # 暗色下 dialog 级亮色 BOARD_QSS 必须已被清空
            clean = len(dlg.styleSheet()) == 0
            heavy_ok = heavy_ok and theme == 'dark' and clean
        dark_alert.close()
        dark_devi.close()

        for d in list(ctrl._board_windows.values()):
            try:
                d.close()
            except RuntimeError:
                pass
        for _ in range(6):
            app.processEvents()

        # 切回亮色，避免污染后续/本进程其它断言
        win._toggle_theme()
        for _ in range(8):
            app.processEvents()
        restored = not Thm.is_dark

        ok = dark_active and light_ok and boards_ok and heavy_ok and restored
        return ok, ("切换=%s 亮色基线=%s 三看板=%s 两重型弹窗(暗色且无亮QSS)=%s 切回亮色=%s"
                    % (dark_active, light_ok, board_themes, heavy_ok, restored))
    check("⑮ 暗色全链路：五外壳跟随 + 亮色路径不受影响", _dark_chain)

    # ⑯ v43.348（第三期）：专题看板弹窗的外壳规范在真实构造下成立
    #    标题无 emoji + 尺寸命中 DIALOG_SIZES 档 + 内容真的装进了 DashboardShell。
    def _dialog_chrome():
        import re
        from PySide6.QtWidgets import QMessageBox
        from gui_pyside6.themes.tokens import DIALOG_SIZES
        from gui_pyside6.dialogs.data_stability_dialog import DataStabilityDialog
        from gui_pyside6.dialogs.material_profile_dialog import MaterialProfileDialog

        # 构造期可能弹「没找到审计库」之类提示，离屏下 exec 会阻塞，临时放行
        orig_exec = QMessageBox.exec
        QMessageBox.exec = lambda self: 0
        made = []
        try:
            for make in (lambda: DataStabilityDialog(),
                         lambda: MaterialProfileDialog("100327825")):
                made.append(make())
            # 与门禁测试同一套黑名单：图形 emoji 区 + 杂项符号/装饰符 + 变体选择符
            emoji = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF"
                               "\u2B00-\u2BFF\uFE00-\uFE0F\u200D]")
            titles = [d.windowTitle() for d in made]
            sizes = [(d.width(), d.height()) for d in made]
            no_emoji = not any(emoji.search(t) for t in titles)
            tier_ok = all(sz in set(DIALOG_SIZES.values()) for sz in sizes)
            # 壳真装上：shell_host 挂在 DashboardShell 里，而不是直接挂在弹窗上
            shell_ok = all(getattr(d, "dashboard_shell", None) is not None
                           and d.shell_host.parent() is not d for d in made)
            ok = no_emoji and tier_ok and shell_ok
            return ok, "标题=%s 尺寸=%s emoji无=%s 档位中=%s 已装壳=%s" % (
                titles, sizes, no_emoji, tier_ok, shell_ok)
        finally:
            QMessageBox.exec = orig_exec
            for d in made:
                d.deleteLater()
    check("⑯ 弹窗外壳规范：标题无emoji+尺寸命档+内容进壳", _dialog_chrome)

    # ⑰ v43.348（第三期）：真实 QMessageBox 下的统一模板 —— 按钮写动作、点「先不清空」
    #     什么都不删、错误框「复制详情」真的把技术详情送进剪贴板。
    #     pytest 那层是 mock 返回值，这里跑的是真 Qt 按钮角色（DestructiveRole 布局）。
    def _message_box_live():
        from PySide6.QtWidgets import QMessageBox
        from gui_pyside6.components import message_box

        def click_by_text(label):
            def _exec(self):
                self.show()
                try:
                    for b in self.buttons():
                        if b.text().replace("&", "") == label:
                            b.click()
                            return 0
                    raise AssertionError("没有按钮 %r，实有 %s"
                                         % (label, [x.text() for x in self.buttons()]))
                finally:
                    self.hide()
            return _exec

        orig_exec = QMessageBox.exec
        mw = win
        # 手动播一份分类，保证「取消不能清空」这条断言不是拿空字典自证
        real = getattr(mw, "_semi_categories", None)
        mw._semi_categories = {"400001": "彩罐", "410001": "托盘"}
        saved = dict(mw._semi_categories)
        try:
            # 1) 点「先不清空」→ 分类必须原样保留
            QMessageBox.exec = click_by_text("先不清空")
            mw._reset_semi_categories()
            kept = dict(getattr(mw, "_semi_categories", {}) or {}) == saved

            # 2) 错误框：复制详情按钮走 ActionRole，点了不关窗，剪贴板拿到标题+异常
            QMessageBox.exec = click_by_text("复制详情")
            QApplication.clipboard().setText("")
            try:
                raise ValueError("列 偏差数量 不存在")
            except ValueError as e:
                message_box.error(mw, "导出没成功", "表里的数据没有改动。", exc=e)
            clip = QApplication.clipboard().text()
            copied = "导出没成功" in clip and "ValueError" in clip \
                and "列 偏差数量 不存在" in clip
        finally:
            QMessageBox.exec = orig_exec
            if real is not None:
                mw._semi_categories = real
        ok = kept and copied
        return ok, "点取消不清空=%s 复制详情含标题+异常=%s" % (kept, copied)
    check("⑰ 真实弹窗模板：动作按钮 + 取消不破坏 + 详情进剪贴板", _message_box_live)

    # ⑱ v43.349（第五期E）：主表格格式照抄设计稿 .tbl —— 36px 行 / 32px 单行表头
    #     左对齐 / 关竖网格线改画 1px 行下边框 / 悬浮行叠色 + 选中左 3px 主色条 +
    #     状态胶囊的自绘代理。像素断言走 viewport().grab()，字体在这台机器上是方框，
    #     所以只验"该出现什么颜色"，不验文字。
    def _table_fmt():
        from PySide6.QtCore import QItemSelection
        from PySide6.QtGui import QColor
        from gui_pyside6.themes.tokens import SIZE_PX, TOKENS
        from gui_pyside6.widgets.row_style_delegate import RowStyleDelegate
        try:
            win.source_model.setDataFrame(df)
            win.proxy_model.invalidate()
        except Exception as e:
            return False, "喂表格失败: %s: %s" % (type(e).__name__, e)
        app.processEvents()
        tv = win.table_view
        hdr = tv.horizontalHeader()
        m = tv.model()
        vis = [i for i in range(m.columnCount()) if not tv.isColumnHidden(i)]
        if not vis:
            return False, "无可见列"

        def near(px, hexs, tol=26):
            c = QColor(hexs)
            return (abs(px.red() - c.red()) <= tol and abs(px.green() - c.green()) <= tol
                    and abs(px.blue() - c.blue()) <= tol)

        row_ok = tv.rowHeight(0) == SIZE_PX["tableRow"]
        grid_ok = not tv.showGrid()
        hdr_ok = (hdr.height() == SIZE_PX["tableHeader"] and not tv.wordWrap()
                  and hdr.defaultAlignment() == (Qt.AlignLeft | Qt.AlignVCenter))
        deg = tv.itemDelegate()
        deg_ok = isinstance(deg, RowStyleDelegate)
        oneline_ok = all("\n" not in str(m.headerData(i, Qt.Horizontal, Qt.DisplayRole) or "")
                         for i in range(m.columnCount()))
        idx = m.index(0, vis[-1] if len(vis) > 1 else vis[0])
        r = tv.visualRect(idx)
        img = tv.viewport().grab().toImage()
        border_ok = r.height() > 2 and near(img.pixelColor(r.center().x(), r.bottom()),
                                            TOKENS["light"]["border"])
        sm = tv.selectionModel()
        sm.select(QItemSelection(idx, idx), sm.SelectionFlag.ClearAndSelect)
        app.processEvents()
        img2 = tv.viewport().grab().toImage()
        bar_ok = all(near(img2.pixelColor(r.left() + 1, r.center().y() + d),
                         TOKENS["light"]["primary"], 30) for d in (-4, 0, 4))
        sel_ok = near(img2.pixelColor(r.center().x(), r.center().y() - 8),
                      TOKENS["light"]["primarySoft"], 16)
        sm.clearSelection()
        before = tv.viewport().grab().toImage()
        deg._set_hover_row(0)
        app.processEvents()
        after = tv.viewport().grab().toImage()
        hover_ok = any(before.pixelColor(r.center().x(), y) != after.pixelColor(r.center().x(), y)
                       for y in range(r.top() + 2, r.bottom() - 2, 2))
        deg._set_hover_row(-1)
        # 状态胶囊：灌一份带「偏差区间」的数据，看该格左缘是否画出了 dangerSoft 浅底
        df_pill = df.copy()
        df_pill["偏差区间"] = ["正偏差"] * len(df_pill)
        win.source_model.setDataFrame(df_pill)
        win.proxy_model.invalidate()
        app.processEvents()
        m2 = tv.model()
        pcol = [i for i in range(m2.columnCount())
                if str(m2.headerData(i, Qt.Horizontal, Qt.DisplayRole) or "") == "偏差区间"]
        pill_ok = False
        if pcol and not tv.isColumnHidden(pcol[0]):
            pr = tv.visualRect(m2.index(0, pcol[0]))
            pimg = tv.viewport().grab().toImage()
            hits = sum(1 for y in range(pr.top() + 4, pr.bottom() - 3, 2)
                       for x in range(pr.left() + 4, pr.left() + 30, 2)
                       if near(pimg.pixelColor(x, y), TOKENS["light"]["dangerSoft"], 22))
            pill_ok = hits >= 8
        win.source_model.setDataFrame(df)
        win.proxy_model.invalidate()
        app.processEvents()
        ok = all([row_ok, grid_ok, hdr_ok, deg_ok, oneline_ok, border_ok,
                  bar_ok, sel_ok, hover_ok, pill_ok])
        info = ("行=%d 表头=%d 竖线=%s 代理=%s 单行=%s 下边框=%s 蓝条=%s 选中底=%s 悬浮=%s 胶囊=%s"
                % (tv.rowHeight(0), hdr.height(), "关" if grid_ok else "开",
                   type(deg).__name__, oneline_ok, border_ok, bar_ok, sel_ok, hover_ok, pill_ok))
        return ok, info
    check("⑱ 表格格式照抄：36px行/32px表头/行下边框/蓝条/悬浮/胶囊", _table_fmt)

    # ⑲ v43.350（第五期G1）：行首勾选道 —— 设计稿表格首列那颗 .chk。
    #     做成垂直表头（不是真列），所以模型列数/列号必须一个都不动；勾选=该行被选中，
    #     角标（左上交叉区，PySide6 的 setCornerWidget 只会放右下角，靠 MainTableView 摆）
    #     三态全选只作用于筛选后可见的行。
    def _check_lane():
        from PySide6.QtGui import QColor
        from gui_pyside6.themes.tokens import SIZE_PX, TOKENS
        from gui_pyside6.widgets.row_check_header import RowCheckHeader, SelectAllCheck, _OFF, _ON, _PART
        from gui_pyside6.widgets.main_table_view import MainTableView
        tv = win.table_view
        lane = tv.verticalHeader()
        corner = tv.corner_widget()
        m = tv.model()
        n = m.rowCount()
        ok_struct = (isinstance(lane, RowCheckHeader) and isinstance(corner, SelectAllCheck)
                     and isinstance(tv, MainTableView)
                     and lane.width() == SIZE_PX["tableCheckLane"]
                     and m.columnCount() == len(df.columns) + 1)
        # 交叉角摆位：x/y/宽/高 = 垂直表头x / 水平表头y / 垂直表头宽 / 水平表头高
        hh = tv.horizontalHeader()
        ok_corner = (corner.x() == lane.x() and corner.y() == hh.y()
                     and corner.width() == lane.width() and corner.height() == hh.height())
        ok_rowh = all(lane.sectionSize(r) == SIZE_PX["tableRow"] for r in range(n))
        # 勾选 = 选中（不引入第二套状态）
        sm = tv.selectionModel()
        sm.clearSelection()
        lane.toggle_row(1)
        app.processEvents()
        rows = sorted({i.row() for i in sm.selectedIndexes()})
        ok_toggle = (rows == [1] and lane.is_row_checked(1)
                     and not lane.is_row_checked(0) and lane.check_state() == _PART)
        lane.toggle_row(1)
        app.processEvents()
        ok_uncheck = (not sm.hasSelection() and lane.check_state() == _OFF)
        corner.toggled.emit(True)
        app.processEvents()
        ok_all = (lane.check_state() == _ON
                  and len(sm.selectedRows()) == n
                  and all(lane.is_row_checked(r) for r in range(n)))
        corner.toggled.emit(False)
        app.processEvents()
        ok_clear = lane.check_state() == _OFF and not sm.hasSelection()
        # 像素：道底色 = surface2，勾上的框里确有 primary 实心（这台机器无字体，只看色）
        # paintEvent 里有 isVisible 守卫（隐藏时不画，免得对无渲染引擎的控件刷告警），
        # 而本冒烟全程不 show 主窗，所以这一段临时显一下再取像素。
        tk = TOKENS["light"]
        lane.toggle_row(0)
        win.show()
        app.processEvents()
        img = lane.viewport().grab().toImage()
        win.hide()
        app.processEvents()
        y0 = lane.sectionViewportPosition(0)

        def near(px, hexs, tol=26):
            c = QColor(hexs)
            return (abs(px.red() - c.red()) <= tol and abs(px.green() - c.green()) <= tol
                    and abs(px.blue() - c.blue()) <= tol)
        ok_bg = near(img.pixelColor(30, y0 + SIZE_PX["tableRow"] - 4), tk["surface2"], 10)
        by = y0 + (SIZE_PX["tableRow"] - 13) // 2
        hits = sum(1 for x in range(8, 21) for y in range(by, by + 13)
                   if near(img.pixelColor(x, y), tk["primary"], 30))
        ok_box = hits > 30
        lane.toggle_row(0)
        app.processEvents()
        ok = all([ok_struct, ok_corner, ok_rowh, ok_toggle, ok_uncheck,
                  ok_all, ok_clear, ok_bg, ok_box])
        return ok, ("结构=%s 角标摆位=%s 行高=%s 勾选=选中=%s 取消=%s 全选=%s 清空=%s "
                    "道底色=%s 勾=%dpx" % (ok_struct, ok_corner, ok_rowh, ok_toggle,
                                          ok_uncheck, ok_all, ok_clear, ok_bg, hits))
    check("⑲ 行首勾选道：勾选=选中/三态全选/列号不动/交叉角摆位", _check_lane)

    # ⑳ v43.351（第五期G2）：行尾悬浮操作道 —— 设计稿最后那列 74px 的 .rowact。
    #     道不是列（列号 == DataFrame 列号 这条 1:1 老墙不能动），而是表格在
    #     QFrame#tableShell 里的并排兄弟；划过哪一行才在哪一行露出「审核/更多」，
    #     两颗按钮只是既有入口：铅笔=审核证据卡、三点=右键菜单，不新写任何业务。
    def _row_actions():
        from PySide6.QtCore import QEvent, QPoint, QPointF
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QFrame
        from gui_pyside6.themes.tokens import SIZE_PX
        from gui_pyside6.widgets.row_action_lane import AUDIT, MORE, RowActionLane
        tv = win.table_view
        lane = win.row_action_lane
        shell = win.table_shell
        # 接线先查（挂探针之前）：每颗按钮各只有一个真插槽，不重复也不空挂
        ok_wired = (_receiver_count(lane, lane.audit_clicked) == 1
                    and _receiver_count(lane, lane.more_clicked) == 1)
        ok_struct = (isinstance(lane, RowActionLane)
                     and lane.objectName() == "rowActionLane"
                     and isinstance(shell, QFrame) and shell.objectName() == "tableShell"
                     and lane.parentWidget() is shell and tv.parentWidget() is shell
                     and lane.width() == SIZE_PX["tableRowActions"] == 74)
        # 行尾多一列 data_id：模型列数仍 = DataFrame 列数 + 1（道没加成列）
        df2 = df.copy()
        df2["data_id"] = ["D1", "D2", "D3"]
        win.source_model.setDataFrame(df2)
        win.proxy_model.invalidate()
        win.show()
        app.processEvents()
        ok_columns = tv.model().columnCount() == len(df2.columns) + 1
        ok_adjacent = (lane.x() == tv.x() + tv.width() and lane.y() == tv.y())
        n = tv.model().rowCount()
        # 视口里露得出的行才谈得上对齐/画按钮（主窗 796 高时表格只容得下两行）
        vis = [r for r in range(n) if lane._row_rect(r) is not None]
        # 行对齐：道里第 r 行的中心换算回视口，仍应是第 r 行
        ok_align = bool(vis) and all(
            tv.rowAt(lane._row_rect(r).center().y() - lane._rows_top()) == r for r in vis)
        ok_bottom = lane._rows_bottom() == (tv.y() + tv.viewport().y()
                                           + tv.viewport().height() - lane.y())

        def send(ev_type, pos, button=Qt.NoButton):
            QApplication.sendEvent(lane, QMouseEvent(
                ev_type, QPointF(pos), QPointF(lane.mapToGlobal(pos)),
                Qt.LeftButton, button, Qt.NoModifier))

        def click(row, kind):
            center = dict(lane._btn_rects(lane._row_rect(row)))[kind].center()
            send(QEvent.MouseMove, center)
            send(QEvent.MouseButtonPress, center, Qt.LeftButton)
            send(QEvent.MouseButtonRelease, center, Qt.LeftButton)
            app.processEvents()

        # 只画在该划过的行上：别的行为零变化
        r_a = vis[0]
        r_b = vis[-1] if len(vis) > 1 else -1
        cold = lane.grab().toImage()
        send(QEvent.MouseMove, lane._btn_rects(lane._row_rect(r_a))[0][1].center())
        app.processEvents()
        hot = lane.grab().toImage()

        def changed(row):
            rect = lane._row_rect(row).adjusted(1, 1, -1, -1)
            return sum(1 for x in range(rect.left(), rect.right())
                       for y in range(rect.top(), rect.bottom())
                       if cold.pixelColor(x, y) != hot.pixelColor(x, y))
        ok_paint = (r_b >= 0 and changed(r_a) > 60 and changed(r_b) == 0)
        ok_hover_only = (tv.itemDelegate().hover_row() == r_a
                         and not tv.selectionModel().hasSelection())
        # 两颗按钮 = 既有入口：证据卡收到的是该行 data_id，三点转发的坐标在视口内
        seen = {}
        origin = win._show_evidence_card
        origin_menu = win._show_context_menu

        def _spy_card(data_id=None):
            seen["data_id"] = data_id

        def _spy_menu(pt):
            seen["pt"] = pt
            return None

        want_id = str(df2.iloc[win._source_row_of_view_row(r_a)]["data_id"])
        win._show_evidence_card = _spy_card
        win._show_context_menu = _spy_menu
        try:
            click(r_a, AUDIT)
            click(r_a, MORE)
        finally:
            win._show_evidence_card = origin
            win._show_context_menu = origin_menu
        ok_audit = seen.get("data_id") == want_id
        pt = seen.get("pt")
        ok_more = (isinstance(pt, QPoint) and pt.x() > 0
                   and tv.viewport().rect().contains(pt))
        # 没划过按钮的位置不该发（道里空白处）
        seen.clear()
        win._show_evidence_card = _spy_card
        try:
            blank = QPoint(2, lane._row_rect(r_a).center().y())
            send(QEvent.MouseMove, blank)
            send(QEvent.MouseButtonPress, blank, Qt.LeftButton)
            send(QEvent.MouseButtonRelease, blank, Qt.LeftButton)
            app.processEvents()
        finally:
            win._show_evidence_card = origin
        ok_blank = "data_id" not in seen
        win.hide()
        app.processEvents()
        win.source_model.setDataFrame(df)
        win.proxy_model.invalidate()
        app.processEvents()
        ok = all([ok_wired, ok_struct, ok_columns, ok_adjacent, ok_align, ok_bottom,
                  ok_paint, ok_hover_only, ok_audit, ok_more, ok_blank])
        return ok, ("接线=%s 结构=%s 列数=%s 紧贴=%s 行对齐=%s 下界=%s 划过才画=%s "
                    "悬浮唯一真源=%s 铅笔=%s 三点=%s 空白不发=%s"
                    % (ok_wired, ok_struct, ok_columns, ok_adjacent, ok_align,
                       ok_bottom, ok_paint, ok_hover_only, ok_audit, ok_more, ok_blank))
    check("⑳ 行尾悬浮操作道：并排兄弟/划过才画/两颗按钮走既有入口", _row_actions)

    return report()


if __name__ == "__main__":
    sys.exit(main())
