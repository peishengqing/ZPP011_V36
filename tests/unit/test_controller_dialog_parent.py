# -*- coding: utf-8 -*-
"""控制器里的静态对话框父窗口必须是 QWidget（v43.263 修复回归网）

背景：ARC-003 把看板/弹窗逻辑从 ``MainWindow`` 搬进 ``DashboardController`` 等
纯 Python 控制器后，``QMessageBox.information(self, ...)`` 这类调用里的 ``self``
不再是 QWidget —— PySide6 直接抛 ``TypeError: called with wrong argument types``。
后果是「请先点分析」这种友好提示反而变成崩溃弹窗（裴哥 2026-10-26 实测踩到）。

两层保护：
* L1 静态扫描：controllers 目录里不允许再出现「裸 self 当父窗口」。
* L2 行为验证：真实走一遍空数据分支，确认提示框拿到的是主窗口而不是抛异常。
"""
import ast
import os
import sys
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

CONTROLLER_DIR = os.path.join(ROOT, "gui_pyside6", "controllers")

DIALOG_FUNCS = {
    "QMessageBox": {"information", "warning", "critical", "question", "about"},
    "QFileDialog": {"getOpenFileName", "getSaveFileName", "getOpenFileNames",
                    "getExistingDirectory"},
    "QInputDialog": {"getText", "getItem", "getInt", "getDouble", "getMultiLineText"},
}


def _bare_self_calls(path):
    """返回该文件里「静态对话框调用第一个参数是裸 self」的行号列表。"""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            continue
        owner = func.value.id
        if owner not in DIALOG_FUNCS or func.attr not in DIALOG_FUNCS[owner]:
            continue
        first = node.args[0] if node.args else None
        if isinstance(first, ast.Name) and first.id == "self":
            bad.append(node.lineno)
    return bad


def test_controllers_never_pass_bare_self_as_dialog_parent():
    """L1：控制器不是 QWidget，父窗口必须写 self.mw（或 None）。"""
    offenders = []
    for name in sorted(os.listdir(CONTROLLER_DIR)):
        if not name.endswith(".py") or name == "__init__.py":
            continue
        path = os.path.join(CONTROLLER_DIR, name)
        for lineno in _bare_self_calls(path):
            offenders.append("%s:%d" % (name, lineno))
    assert not offenders, (
        "静态对话框父窗口传了裸 self（运行期必然 TypeError），应改为 self.mw："
        + ", ".join(offenders)
    )


def test_empty_data_branch_shows_hint_instead_of_crashing(qapp):
    """L2：没数据时点看板 → 弹「暂无数据，请先分析」，而不是抛异常。"""
    from PySide6.QtWidgets import QWidget
    from gui_pyside6.controllers.dashboard_controller import DashboardController

    class _FakeMW(QWidget):
        def _get_master_df(self):
            return None

    mw = _FakeMW()
    ctrl = DashboardController(mw)

    with patch("gui_pyside6.controllers.dashboard_controller.QMessageBox.information") as info:
        ctrl._show_alert_dashboard()

    assert info.call_count == 1, "空数据分支应当弹出提示框"
    parent = info.call_args[0][0]
    assert parent is mw, "提示框父窗口必须是主窗口（原来传了控制器自身 → 崩溃）"
