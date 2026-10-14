# -*- coding: utf-8 -*-
"""半成品分类职责测试（ARC-003 第五刀，v43.197）。

本刀踩过一个真实的装配顺序坑（已被现有 smoke 测试抓到 26 个 error）：
`self._semi_categories = self._load_semi_categories()` 若早于
`self.semi_category_controller = SemiCategoryController(self)` 执行，
薄壳转发会 AttributeError。故 test_wiring_precedes_state_init 专门钉住此顺序。
"""
import ast
import inspect
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.controllers.semi_category_controller import SemiCategoryController  # noqa: E402

SHELLS = [
    "_filter_semi_materials", "_reset_semi_filter", "_load_semi_categories",
    "_get_semi_category_list", "_save_semi_categories", "_refresh_semi_list_ui",
    "_add_semi_category", "_delete_semi_category", "_reset_semi_categories",
    "_import_semi_categories", "_export_semi_categories",
]


def _load_main_window_cls():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from gui_pyside6.main_window import MainWindow
    return MainWindow


# ---------- 1. 结构护栏 ----------

def test_all_11_shells_exist():
    MW = _load_main_window_cls()
    missing = [m for m in SHELLS if not callable(getattr(MW, m, None))]
    assert not missing, f"MainWindow 缺失半成品分类薄壳: {missing}"


def test_all_11_methods_on_controller():
    missing = [m for m in SHELLS if not callable(getattr(SemiCategoryController, m, None))]
    assert not missing, f"SemiCategoryController 缺失方法: {missing}"


def test_controller_holds_mw_backref():
    ctrl = SemiCategoryController(object())
    assert hasattr(ctrl, "mw")


def test_shells_forward_not_stubbed():
    import types
    from unittest import mock
    MW = _load_main_window_cls()
    sentinel = object()
    for m in SHELLS:
        fake = types.SimpleNamespace(semi_category_controller=mock.Mock())
        getattr(fake.semi_category_controller, m).return_value = sentinel
        fn = MW.__dict__[m]
        nargs = len([p for p in inspect.signature(fn).parameters if p != "self"])
        args = ["测试分类", {"k": "v"}][:nargs]
        assert fn(fake, *args) is sentinel, f"{m} 薄壳未透传（疑似空实现）"


def test_source_shells_are_single_return():
    MW = _load_main_window_cls()
    with open(inspect.getfile(MW), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    for m in cls.body:
        if isinstance(m, ast.FunctionDef) and m.name in SHELLS:
            body = [s for s in m.body if not isinstance(s, ast.Expr)]
            assert len(body) == 1 and isinstance(body[0], ast.Return), (
                f"MainWindow.{m.name} 应只剩一条 return 转发"
            )


# ---------- 2. 装配顺序（本刀真实踩过的坑） ----------

def test_wiring_precedes_state_init():
    """SemiCategoryController 必须先于 self._semi_categories 初始化装配。

    否则 _load_semi_categories() 经薄壳转发时 controller 属性尚不存在，
    __init__ 直接 AttributeError（实测曾致 26 个 smoke error）。
    """
    MW = _load_main_window_cls()
    with open(inspect.getfile(MW), encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    init = next(m for m in ast.walk(tree)
                if isinstance(m, ast.Assign)
                and any(getattr(t, "attr", None) == "_semi_categories" for t in m.targets))
    wiring = [n for n in ast.walk(tree)
              if isinstance(n, ast.Assign)
              and any(getattr(t, "attr", None) == "semi_category_controller"
                      for t in n.targets)]
    assert wiring, "未找到 semi_category_controller 装配语句"
    assert wiring[0].lineno < init.lineno, (
        f"装配行 {wiring[0].lineno} 必须早于 _semi_categories 初始化行 {init.lineno}"
    )


def test_state_field_stays_on_mainwindow():
    """状态字段 _semi_categories 仍归属 MainWindow（经 view_model 间接读）。"""
    MW = _load_main_window_cls()
    assert "_semi_categories" in inspect.getsource(MW.__init__), (
        "_semi_categories 应仍在 MainWindow.__init__ 中初始化"
    )


# ---------- 3. left_panel 绑定签名兼容 ----------

def test_left_panel_five_buttons_take_no_arg():
    """left_panel.py:285-289 五个按钮均为无参回调。"""
    MW = _load_main_window_cls()
    for m in ("_add_semi_category", "_delete_semi_category",
              "_reset_semi_categories", "_import_semi_categories",
              "_export_semi_categories"):
        params = [p for p in inspect.signature(MW.__dict__[m]).parameters if p != "self"]
        assert not params, f"{m} 不应有可接受参数：{params}"


def test_filter_semi_materials_takes_one_arg():
    """_filter_semi_materials(category) 单参调用。"""
    MW = _load_main_window_cls()
    params = [p for p in inspect.signature(MW.__dict__["_filter_semi_materials"]).parameters
              if p != "self"]
    assert len(params) == 1, f"应恰好 1 参（category）：{params}"


def test_save_semi_categories_takes_one_mapping_arg():
    MW = _load_main_window_cls()
    params = [p for p in inspect.signature(MW.__dict__["_save_semi_categories"]).parameters
              if p != "self"]
    assert len(params) == 1, f"应恰好 1 参（mapping）：{params}"


def test_mainwindow_under_line_threshold():
    MW = _load_main_window_cls()
    with open(inspect.getfile(MW), encoding="utf-8") as fh:
        lines = len(fh.readlines())
    # v43.198：阈值 4400 → 4450。本轮给 _FullCacheWorker 补协作式取消点
    # （request_cancel/_cancel_check + run() 两分支 cancel_check + KeyboardInterrupt
    # 收尾 + _cancel_analysis/closeEvent 接线）净增 31 行（4375 → 4406），属真实
    # 缺陷修复的必要开销。护栏目的仍是拦住数百行级倒退回膨胀，50 行缓冲够用。
    assert lines < 4450, f"MainWindow 回升到 {lines} 行（阈值 4450），分类拆分可能已回退"
