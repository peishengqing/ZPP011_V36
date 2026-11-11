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
import sys
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

import pandas as pd
from PySide6.QtWidgets import QApplication, QStyleFactory, QLabel, QWidget
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

    # ① 标题栏：48px + 动态副标题
    def _title():
        tb = win.title_bar
        subs = [l for l in tb.findChildren(QLabel) if l.objectName() == "titleSub"]
        before = subs[0].text() if subs else "<no titleSub>"
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        tb.set_subtitle("数据源：smoke.xlsx | 分析时间：%s" % stamp)
        after = subs[0].text() if subs else "<no titleSub>"
        ok = tb.maximumHeight() == 48 and bool(subs) and "数据源" in after and before != after
        return ok, "height=%s 副标题 '%s' -> '%s'" % (tb.maximumHeight(), before, after)
    check("① 标题栏 48px + 副标题动态化", _title)

    # ② 底部状态条
    def _bottom():
        bb = win.bottom_bar
        ok = bb is not None and bb.maximumHeight() == 30 and bb.parent() is not None
        return ok, "height=%s 记录='%s' 选中='%s' 偏差='%s' 未读='%s'" % (
            bb.maximumHeight(), bb.lbl_records.text(), bb.lbl_selected.text(),
            bb.lbl_deviation.text(), bb.lbl_unread.text())
    check("② 底部状态条常驻 + 已挂布局", _bottom)

    # ③ 操作栏三开关 icon-only
    def _toggles():
        names = ["action_btn_left_panel", "action_btn_filter", "action_btn_col_filter"]
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
                ok = ok and icon_ok and style_ok
                detail.append("%s(icon=%s,style=%s)" % (n, icon_ok, style_ok))
        return ok, " ".join(detail)
    check("③ 操作栏三开关 icon-only", _toggles)

    # ④ 概览 KPI 带 52px
    def _kpi():
        cards = [w for w in win.stats_cards.findChildren(QWidget)
                 if w.minimumHeight() == 52 and w is not win.stats_cards]
        return len(cards) >= 7, "52px 卡片数=%d（期望7）" % len(cards)
    check("④ 概览 KPI 带 52px", _kpi)

    # ⑤ 左栏 360 + splitter 首值匹配
    def _left():
        lp = getattr(win, "left_panel", None)
        sp = getattr(win, "body_splitter", None)
        w = lp.width() if lp is not None else -1
        sizes = sp.sizes() if sp is not None else []
        ok = lp is not None and w == 360 and bool(sizes) and sizes[0] == 360
        return ok, "left_panel.width=%s splitter.sizes=%s" % (w, sizes[:3])
    check("⑤ 左栏固定宽 360 + splitter 匹配", _left)

    # ⑥ 灌小数据：data_changed -> 底部状态条联动
    def _data():
        win.view_model.df = df
        app.processEvents()
        bb = win.bottom_bar
        rec = bb.lbl_records.text()
        dev = bb.lbl_deviation.text()
        unr = bb.lbl_unread.text()
        ok = rec == "记录：3" and "¥" in dev and unr == "未读：2"
        return ok, "记录='%s' 偏差='%s' 未读='%s'" % (rec, dev, unr)
    check("⑥ 灌 3 行真实数据 → 底部状态条联动", _data)

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
        return txt != "选中：0", "选中='%s'" % txt
    check("⑥b 选中行数联动（SelectItems 全选）", _sel)

    # ⑦ 三看板 Content + Shell + 亮暗主题
    for label, cls in boards:
        def _content(cls=cls, label=label):
            c = cls(win)
            c.set_data(df)
            shell = DashboardShell()
            shell.set_title("%s看板 · 冒烟" % label)
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

    # ⑨ 操作栏 13→8（v43.341 设计稿第2项）
    def _action_bar():
        from PySide6.QtWidgets import QToolButton, QPushButton
        more = getattr(win, 'action_btn_more', None)
        assert more is not None, '「更多」按钮未创建'
        bar = more.parent()
        lay = bar.layout()
        direct = [lay.itemAt(i).widget() for i in range(lay.count())]
        visible_btns = [w for w in direct
                        if isinstance(w, (QToolButton, QPushButton))]
        names = ('action_btn_toggle_stats', 'action_btn_toggle_progress',
                 'action_btn_audit', 'action_btn_unread_summary',
                 'action_btn_auto_q')
        low = [getattr(win, n, None) for n in names]
        kept = all(b is not None for b in low)
        moved = all(b.parent() is not bar for b in low if b is not None)
        # 按钮对象没被重建：checkable 状态仍可切换（外部 setChecked 同步不断链）
        togglable = False
        if low[0] is not None:
            old = low[0].isChecked()
            low[0].setChecked(not old)
            togglable = low[0].isChecked() == (not old)
            low[0].setChecked(old)
        compact_act = getattr(win, 'action_compact_left', None)
        act_ok = compact_act is not None and compact_act.isCheckable()
        menu_ok = more.menu() is not None and len(more.menu().actions()) >= 2
        ok = (len(visible_btns) == 8 and kept and moved and togglable
              and act_ok and menu_ok)
        return ok, ("可见按钮=%d(期望8) 5对象保留=%s 已搬入菜单=%s 可切换=%s "
                    "紧凑开关=%s 菜单项=%s" % (len(visible_btns), kept, moved,
                                       togglable, act_ok, menu_ok))
    check("⑨ 操作栏 13→8 收拢进「更多」", _action_bar)

    # ⑩ 左栏 236px 紧凑纯导航（v43.341 设计稿第4项）
    def _left_compact():
        lp = win.left_panel_component
        bodies = [lp.file_group.body, lp.alt_group.body,
                  lp.semi_group.body, lp.preview_group.body]
        sp = win.body_splitter
        lp.set_compact(True)
        w236, s236 = lp.left_panel.width(), sp.sizes()[0]
        hidden = all(b.isHidden() for b in bodies)
        # 模拟点开第一张卡片头：互斥展开 + 临时拉回 360 保证表单不挤
        lp._compact_toggle(lp.file_group.body, lp.file_group.arrow_btn)
        w360 = lp.left_panel.width()
        opened = (not lp.file_group.body.isHidden()) and all(
            b.isHidden() for b in bodies[1:])
        lp._compact_toggle(lp.file_group.body, lp.file_group.arrow_btn)
        back236 = lp.left_panel.width()
        lp.set_compact(False)
        w_restore, s_restore = lp.left_panel.width(), sp.sizes()[0]
        ok = (w236 == 236 and s236 == 236 and hidden and w360 == 360
              and opened and back236 == 236 and w_restore == 360
              and s_restore == 360)
        return ok, ("紧凑=%d/split%d 全收=%s 展开=%d 互斥=%s 收起=%d 还原=%d/split%d"
                    % (w236, s236, hidden, w360, opened, back236,
                       w_restore, s_restore))
    check("⑩ 左栏 236px 紧凑导航双模式", _left_compact)

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
        tabs_ok = dlg.tabs.count() == 3
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

    # ⑬ v43.342：重复标题清理 + 空操作条按需（裴哥 11-11 反馈）
    def _title_cleanup():
        from PySide6.QtWidgets import QScrollArea, QLabel as _QLabel
        detail = []
        ok = True
        for label, cls, board_title in (
            ("负损", NegLossContent, "负损(含未投料)看板"),
            ("正损", PosLossContent, "正损(超投)看板"),
        ):
            c = cls(win)
            c.set_data(df)
            # ① Content 内不得再画同名标题（旧剥壳残留）
            dup = [l for l in c.findChildren(_QLabel)
                   if l.text().strip() == board_title]
            no_attr = not hasattr(c, '_title_label')
            # ② 筛选区必须是主布局第一项 —— 控件确实顶到最上，不再隔一行标题
            first = c.layout().itemAt(0)
            first_scroll = (first is not None and
                            isinstance(first.widget(), QScrollArea))
            # ③ 组合后整窗里该标题只出现一次（只由外壳标题栏提供）
            s = DashboardShell()
            s.set_title(board_title)
            s.set_content(c)
            shell_titles = [l for l in s.findChildren(_QLabel)
                            if l.text().strip() == board_title]
            one_title = len(shell_titles) == 1
            # ④ 空操作条默认隐藏，放入控件后才展开
            hidden = s._action_bar.isHidden()
            s.set_action_widget(_QLabel("操作"))
            expanded = not s._action_bar.isHidden()
            good = (not dup and no_attr and first_scroll and one_title
                    and hidden and expanded)
            ok = ok and good
            detail.append("%s(重复=%d,首项筛选=%s,唯一标题=%s,空条隐藏=%s,放入展开=%s)"
                          % (label, len(dup), first_scroll, one_title,
                             hidden, expanded))
        return ok, " ".join(detail)
    check("⑬ 重复标题清理 + 控件上移 + 空条不占位", _title_cleanup)

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

    return report()


if __name__ == "__main__":
    sys.exit(main())
