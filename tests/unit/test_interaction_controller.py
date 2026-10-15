# -*- coding: utf-8 -*-
"""InteractionController 测试（ARC-003 第六刀，v43.199）。

验证：controller 方法存在、MainWindow 薄壳存在且真转发、AST 层只剩薄壳、
以及「薄壳 → controller」真实链路可跑。

v43.198 教训的正面应用：接线/转发类断言必须配行为层用例——
AST 源码包含性看不见「薄壳被改成 return None」之外的执行可达性问题，
故 test_shell_reaches_controller_logic 用真 controller 实调打穿整条链路。
"""
import ast
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui_pyside6.controllers.interaction_controller import InteractionController  # noqa: E402

# 本刀迁出 MainWindow 的 10 个交互方法。
# 注意命名映射：MainWindow 侧公开名为 copy_selected_cells（eventFilter/菜单在调），
# controller 侧沿用下划线私有名 _copy_selected_cells，其余 9 个两侧同名。
SHELLS = [
    "_select_source_row", "_locate_row_by_index", "_locate_row_by_excel_no",
    "_locate_row_in_main_table", "_on_selection_changed", "_update_selection_summary",
    "_clear_selection_summary", "copy_selected_cells", "_on_cell_double_clicked",
    "_show_row_detail",
]

SHELL_TO_CTRL = {
    "copy_selected_cells": "_copy_selected_cells",
}


def _load_main_window_cls():
    from gui_pyside6.main_window import MainWindow
    return MainWindow


# ---------- 1. 结构护栏 ----------

def test_controller_has_all_methods():
    methods = {m for m in dir(InteractionController) if not m.startswith("__")}
    missing = [SHELL_TO_CTRL.get(m, m) for m in SHELLS
               if SHELL_TO_CTRL.get(m, m) not in methods]
    assert not missing, f"InteractionController 缺失方法：{missing}"


def test_mainwindow_shells_exist():
    MW = _load_main_window_cls()
    missing = [m for m in SHELLS if not callable(getattr(MW, m, None))]
    assert not missing, f"MainWindow 缺失薄壳：{missing}"


def test_controller_holds_mw_backref():
    mw = object()
    ctrl = InteractionController(mw)
    assert ctrl.mw is mw


# ---------- 2. 行为层：薄壳真转发 ----------

def test_shells_forward_not_stubbed():
    """行为层：bare MainWindow + mock controller，实调每个薄壳，返回值必须透传。"""
    import inspect
    MW = _load_main_window_cls()
    sentinel = object()
    mw = MW.__new__(MW)  # 不跑 __init__，只预设薄壳要用的属性（PySide6 类禁止 object.__new__）
    mw.interaction_controller = type(
        "FakeCtrl", (), {SHELL_TO_CTRL.get(m, m): (lambda self, *a, **k: sentinel) for m in SHELLS}
    )()
    for m in SHELLS:
        fn = getattr(mw, m)
        # getattr 拿到的是绑定方法，signature 已不含 self，直接数参即可
        n_args = len(inspect.signature(fn).parameters)
        result = fn(*([None] * n_args))
        assert result is sentinel, f"薄壳 {m} 未透传 controller 返回值（疑似被改成 return None）"


def test_shell_reaches_controller_logic():
    """行为层：装配真 controller 跑 miss 链路，证明薄壳打穿到 controller 逻辑。

    只测 miss 路径（原表行号不存在 → 返回 False，仅经 source_model/log），
    桩对象最简；命中链路（_select_source_row → 表格选中）由
    test_locate_row.py 的两个真实方法级测试覆盖，不在此重复造轮子。
    """
    import pandas as pd
    MW = _load_main_window_cls()

    df = pd.DataFrame({"原表行号": ["1", "2"], "data_id": ["a", "b"]})
    logs = []

    class _SM:
        def getDataFrame(self):
            return df

    class _Stub:
        pass

    stub = _Stub()
    stub.source_model = _SM()
    stub.log = lambda *a, **k: logs.append(a)
    stub.interaction_controller = InteractionController(stub)

    # 经 MainWindow 薄壳调用，miss → False，不抛异常（打穿薄壳→controller）
    assert MW._locate_row_by_excel_no(stub, "999") is False


# ---------- 3. AST 层：MainWindow 只剩薄壳 ----------

def _strip_docstring(body):
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1:]
    return body


def test_mainwindow_only_shells_remaining():
    """MainWindow 中这 10 个方法去掉 docstring 后必须只剩一条
    `return self.interaction_controller.<同名>(...)`。"""
    with open(os.path.join(ROOT, "gui_pyside6", "main_window.py"), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    mw_methods = {n.name: n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name in SHELLS}
    assert set(mw_methods) == set(SHELLS), (
        f"MainWindow 中薄壳集合不符：缺 {set(SHELLS) - set(mw_methods)}，"
        f"多 {set(mw_methods) - set(SHELLS)}"
    )
    for name, node in mw_methods.items():
        ctrl_name = SHELL_TO_CTRL.get(name, name)
        body = _strip_docstring(list(node.body))
        assert len(body) == 1 and isinstance(body[0], ast.Return), (
            f"{name} 去 docstring 后应只剩一条 return（当前 {len(body)} 条语句），"
            "实现未迁干净或薄壳被改坏"
        )
        call = body[0].value
        assert isinstance(call, ast.Call), f"{name} 的 return 不是函数调用"
        # 必须是 self.interaction_controller.<controller 名>(...) 三级属性链
        func = call.func
        assert isinstance(func, ast.Attribute) and func.attr == ctrl_name, (
            f"{name} 转发目标不是 interaction_controller.{ctrl_name}"
        )
        assert isinstance(func.value, ast.Attribute) and func.value.attr == "interaction_controller"
        assert isinstance(func.value.value, ast.Name) and func.value.value.id == "self"


def test_controller_file_has_real_implementations():
    """反向护栏：controller 里这些方法不能是 `return self.mw.<同名>(...)` 纯转发
    （那等于把实现原样留在 MainWindow、迁了个空壳）。

    注意判据不用「语句数≥2」——`_locate_row_by_index` 真实现就是单条 try 包裹，
    展开计数会误伤；直接识别「唯一语句是 return self.mw.<名>()」这一空壳特征。
    """
    path = os.path.join(ROOT, "gui_pyside6", "controllers", "interaction_controller.py")
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "InteractionController")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    for shell in SHELLS:
        ctrl_name = SHELL_TO_CTRL.get(shell, shell)
        body = _strip_docstring(list(methods[ctrl_name].body))
        is_passthrough = (
            len(body) == 1
            and isinstance(body[0], ast.Return)
            and isinstance(body[0].value, ast.Call)
            and isinstance(body[0].value.func, ast.Attribute)
            and isinstance(body[0].value.func.value, ast.Attribute)
            and body[0].value.func.value.attr == "mw"
            and body[0].value.func.attr == shell
        )
        assert not is_passthrough, (
            f"controller.{ctrl_name} 是 return self.mw.{shell}(...) 纯转发——"
            "实现没有真迁过来"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
