# -*- coding: utf-8 -*-
"""看板/弹窗展示职责测试（ARC-003 第四刀，v43.196）。

本刀的特殊风险是「外部绑定」：menu_bar.py:76 与 left_panel.py:316 直接绑定
MainWindow 上的方法，故测试除结构护栏外，还要钉住两处绑定的签名兼容性
（_show_alert_dashboard 无参、_show_semi_detail_window 单参）。
"""
import ast
import inspect
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.controllers.dashboard_controller import DashboardController  # noqa: E402

SHELLS = [
    "_show_alert_dashboard", "_show_deviation_warning_dialog",
    "_show_neg_loss_dashboard", "_show_pos_loss_dashboard",
    "_show_data_stability_dashboard", "_show_quarantine_review_dashboard",
    "_show_alt_chain_dashboard", "_show_material_profile",
    "_show_semi_dashboard", "_show_semi_detail_window",
    "_show_dashboard",
]


def _load_main_window_cls():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from gui_pyside6.main_window import MainWindow
    return MainWindow


# ---------- 1. 结构护栏 ----------

def test_all_11_shells_exist():
    MW = _load_main_window_cls()
    missing = [m for m in SHELLS if not callable(getattr(MW, m, None))]
    assert not missing, f"MainWindow 缺失看板薄壳: {missing}"


def test_all_11_methods_on_controller():
    missing = [m for m in SHELLS if not callable(getattr(DashboardController, m, None))]
    assert not missing, f"DashboardController 缺失方法: {missing}"


def test_controller_holds_mw_backref():
    ctrl = DashboardController(object())
    assert hasattr(ctrl, "mw")


def test_shells_forward_not_stubbed():
    """防假通：薄壳必须真转发，而非 return None。"""
    import types
    from unittest import mock
    MW = _load_main_window_cls()
    sentinel = object()
    for m in SHELLS:
        fake = types.SimpleNamespace(dashboard_controller=mock.Mock())
        getattr(fake.dashboard_controller, m).return_value = sentinel
        fn = MW.__dict__.get(m)
        assert fn is not None, f"{m} 未定义在 MainWindow 上"
        args = ["X", "Y"][: len(_params(fn))]
        assert fn(fake, *args) is sentinel, f"{m} 薄壳未透传（疑似空实现）"


def _params(fn):
    """取函数除 self 外的可接受参数（MW.__dict__ 拿到的是未绑定函数，含 self）。"""
    sig = inspect.signature(fn)
    return [p for p in sig.parameters.values()
            if p.name != "self"
            and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]


# ---------- 2. 外部绑定签名兼容（本刀的核心风险） ----------

def test_menu_bar_binding_signature_still_no_arg():
    """menu_bar.py:76  `alert_action.triggered.connect(self.mw._show_alert_dashboard)`
    triggered 信号不传参，故薄壳必须零可接受参数。"""
    MW = _load_main_window_cls()
    params = _params(MW.__dict__["_show_alert_dashboard"])
    assert not params, f"_show_alert_dashboard 不应有可接受参数：{params}"


def test_semi_detail_window_binding_signature_one_arg():
    """left_panel.py:316 `self.mw._show_semi_detail_window(category)` 单参调用。"""
    MW = _load_main_window_cls()
    params = _params(MW.__dict__["_show_semi_detail_window"])
    assert len(params) == 1, f"_show_semi_detail_window 应恰好 1 参（category）：{params}"
    assert params[0].default is inspect.Parameter.empty, "category 应为必填"


def test_material_profile_keeps_optional_defaults():
    """_show_material_profile(code=None, name=None) 被多处无参/带参调用，默认参数须保留。"""
    MW = _load_main_window_cls()
    MW_c = DashboardController
    for owner, label in ((MW.__dict__["_show_material_profile"], "MainWindow 薄壳"),
                         (MW_c.__dict__["_show_material_profile"], "DashboardController")):
        sig = inspect.signature(owner)
        names = [p for p in sig.parameters]
        assert names[-2:] == ["code", "name"], f"{label} 参数名应含 code,name：{sig}"
        assert all(sig.parameters[n].default is None for n in ("code", "name")), (
            f"{label} code/name 应保留 None 默认值：{sig}"
        )


def test_source_still_importable_and_methods_unique():
    """AST 层校验：搬迁后 MainWindow 只剩薄壳（每个 1-3 行），实现不再重复。"""
    MW = _load_main_window_cls()
    src_file = inspect.getfile(MW)
    with open(src_file, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    for m in cls.body:
        if isinstance(m, ast.FunctionDef) and m.name in SHELLS:
            body = [s for s in m.body if not isinstance(s, ast.Expr)]
            assert len(body) == 1 and isinstance(body[0], ast.Return), (
                f"MainWindow.{m.name} 应只剩一条 return 转发，实际 {len(body)} 条语句"
            )


def test_mainwindow_under_line_threshold():
    MW = _load_main_window_cls()
    with open(inspect.getfile(MW), encoding="utf-8") as fh:
        lines = len(fh.readlines())
    assert lines < 4700, f"MainWindow 回升到 {lines} 行（阈值 4700），看板拆分可能已回退"
