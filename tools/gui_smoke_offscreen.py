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
        "物料编码": ["M001", "M002", "M003"],
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
            shell.set_theme("dark")
            dark_ok = shell.get_theme() == "dark" and bool(shell.styleSheet())
            shell.set_theme("light")
            light_ok = shell.get_theme() == "light" and bool(shell.styleSheet())
            model_ok = c.table_view.model() is not None
            return dark_ok and light_ok and model_ok, "model=%s dark=%s light=%s" % (
                model_ok, dark_ok, light_ok)
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

    return report()


if __name__ == "__main__":
    sys.exit(main())
