# -*- coding: utf-8 -*-
"""隔离区管理控制器（ARC-003 第七刀，v43.203）回归测试。

验证 8 个隔离区方法切出到 QuarantineManagerController 后：
  1. 结构：controller 有 8 方法、MainWindow 有 8 薄壳。
  2. 行为层：bare MW + mock controller，实调 8 薄壳验返回值透传 + 参数透传。
  3. AST：MainWindow 侧每个薄壳去 docstring 后只剩一条 return 转发语句。
  4. AST 反向护栏：controller 侧方法非纯 `return self.mw.<名>()` 空壳（真实现）。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from gui_pyside6.main_window import MainWindow as MW
from gui_pyside6.controllers.quarantine_manager_controller import QuarantineManagerController

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SHELLS = [
    "_auto_read_by_rules",
    "_reconcile_quarantine_read_status",
    "_set_quarantine",
    "_repair_quarantine_consistency",
    "_auto_move_to_quarantine",
    "_update_quarantine_badge",
    "_scan_expired_quarantine_after_analysis",
    "_notify_expired_quarantine",
]

# 每个薄壳的实参（按签名造参；带默认值的方法传空元组）
SHELL_ARGS = {
    "_auto_read_by_rules": (None,),
    "_reconcile_quarantine_read_status": (None,),
    "_set_quarantine": ([], True),
    "_repair_quarantine_consistency": (False,),
    "_auto_move_to_quarantine": (False,),
    "_update_quarantine_badge": (None,),
    "_scan_expired_quarantine_after_analysis": (),
    "_notify_expired_quarantine": ([], []),
}


def _class_func_map(path, cls_name):
    tree = ast.parse(open(path, encoding="utf-8").read())
    cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name][0]
    return {f.name: f for f in cls.body if isinstance(f, ast.FunctionDef)}


def _body_without_docstring(fn):
    stmts = list(fn.body)
    if stmts and isinstance(stmts[0], ast.Expr) and isinstance(stmts[0].value, ast.Constant):
        stmts = stmts[1:]
    return stmts


def test_controller_has_8_methods():
    for name in SHELLS:
        assert hasattr(QuarantineManagerController, name), f"controller 缺 {name}"


def test_mainwindow_has_8_thin_shells():
    for name in SHELLS:
        assert hasattr(MW, name), f"MainWindow 缺薄壳 {name}"


def test_all_8_shells_forward_return():
    """bare MW + mock controller，实调 8 薄壳验返回值 + 参数透传。"""
    bare = MW.__new__(MW)
    mock_ctrl = MagicMock()
    for name in SHELLS:
        getattr(mock_ctrl, name).return_value = "OK_" + name
    bare.quarantine_manager_controller = mock_ctrl
    for name in SHELLS:
        args = SHELL_ARGS[name]
        ret = getattr(MW, name)(bare, *args)
        assert ret == ("OK_" + name), f"{name} 薄壳未透传 controller 返回值"
        getattr(mock_ctrl, name).assert_called_once_with(*args)

def test_thin_shells_are_single_forward():
    """AST：MainWindow 侧每个薄壳去 docstring 后只剩一条 return 转发语句。"""
    fmap = _class_func_map(os.path.join(ROOT, "gui_pyside6", "main_window.py"), "MainWindow")
    for name in SHELLS:
        stmts = _body_without_docstring(fmap[name])
        assert len(stmts) == 1, f"{name} 薄壳应只剩一条语句，实际 {len(stmts)}"
        dump = ast.dump(stmts[0])
        assert "quarantine_manager_controller" in dump and "Return" in dump, \
            f"{name} 薄壳非单条转发 controller"


def test_controller_methods_are_real_impl():
    """AST 反向护栏：controller 侧方法须为真实现，不能退化成「回弹到 self.mw.<同名>」的
    纯转发薄壳（那样等于没真搬方法体）。判据：方法体不能全部是 `return self.mw.<同名>(...)`。
    （不用「语句数≥N」——_auto_read_by_rules 等整个体是一条 try，会被误杀，见 v43.199 教训。）"""
    fmap = _class_func_map(
        os.path.join(ROOT, "gui_pyside6", "controllers", "quarantine_manager_controller.py"),
        "QuarantineManagerController",
    )
    for name in SHELLS:
        stmts = _body_without_docstring(fmap[name])
        assert len(stmts) >= 1, f"controller {name} 方法体为空（未搬迁）"
        # 若方法体只有一条语句且是 return self.mw.<同名>() 纯转发 → 退化成空壳
        if len(stmts) == 1 and isinstance(stmts[0], ast.Return) and stmts[0].value is not None:
            val = stmts[0].value
            is_pure_forward = (
                isinstance(val, ast.Call)
                and isinstance(val.func, ast.Attribute)
                and isinstance(val.func.value, ast.Attribute)
                and val.func.value.attr == "mw"
                and val.func.attr == name  # self.mw.<同名>()
            )
            assert not is_pure_forward, \
                f"controller {name} 退化成 return self.mw.{name}() 纯转发（方法体未真搬迁）"
