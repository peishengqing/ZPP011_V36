# -*- coding: utf-8 -*-
"""_FullCacheWorker 协作式取消点测试（v43.198）。

背景：v43.125  smoke 探针证实 `_FullCacheWorker` 全程无取消点——run() 给
export_full_report_from_intermediates 传 cancel_check=None、兜底 do_analysis_v2
也不传、_cancel_analysis 与 closeEvent 都不碰 _cache_worker，点「取消」后
完整报告缓存仍算到底。v43.198 修复：补 request_cancel/_cancel_check（范式同
_FullReportWorker），run() 两分支传 cancel_check=self._cancel_check，
_cancel_analysis/closeEvent 接线，KeyboardInterrupt 单独捕获优雅收尾。

本文件把「修复存在」钉死：删方法 / 改回 cancel_check=None / 接线被重构丢掉，
均有对应用例精确失败。
"""
import ast
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

MW_PATH = os.path.join(ROOT, "gui_pyside6", "main_window.py")


def _load_worker_cls():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from gui_pyside6.main_window import _FullCacheWorker
    return _FullCacheWorker


def _parse_main_window():
    with open(MW_PATH, "r", encoding="utf-8") as f:
        src = f.read()
    return ast.parse(src), src


def _method_src(tree, src, cls_name, m_name):
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == cls_name)
    m = next(m for m in node.body
             if isinstance(m, ast.FunctionDef) and m.name == m_name)
    return ast.get_source_segment(src, m)


# ---------- 1. 行为层：取消二件套真能翻标志 ----------

def test_request_cancel_flips_check():
    """实例化→默认不取消→request_cancel()→_cancel_check() 为真。"""
    W = _load_worker_cls()
    w = W("in.xlsx", None, "", "", "", "out.xlsx")
    assert w._cancel_check() is False
    w.request_cancel()
    assert w._cancel_check() is True
    # 幂等：重复调用不报错、标志保持
    w.request_cancel()
    assert w._cancel_check() is True


# ---------- 2. AST 层：run() 两分支都传取消检查 ----------

def test_run_passes_cancel_check_in_both_branches():
    """intermediates 分支与兜底分支都必须传 cancel_check=self._cancel_check。"""
    tree, src = _parse_main_window()
    run_src = _method_src(tree, src, "_FullCacheWorker", "run")
    assert run_src.count("cancel_check=self._cancel_check") == 2, (
        "run() 应有 2 处 cancel_check=self._cancel_check（intermediates 分支 + "
        f"兜底分支），实际 {run_src.count('cancel_check=self._cancel_check')} 处"
    )
    assert "cancel_check=None" not in run_src, (
        "run() 又出现 cancel_check=None——取消点被改回无"
    )
    assert "except KeyboardInterrupt" in run_src, (
        "run() 缺 KeyboardInterrupt 捕获：取消时 analyzer 抛的是 "
        "BaseException 子类，except Exception 兜不住，会裸死线程"
    )


# ---------- 3. AST 层：取消入口接线 ----------

def test_cancel_analysis_wires_cache_worker():
    """_cancel_analysis 必须调 _cache_worker.request_cancel()。"""
    tree, src = _parse_main_window()
    ca_src = _method_src(tree, src, "MainWindow", "_cancel_analysis")
    assert "_cache_worker.request_cancel()" in ca_src, (
        "_cancel_analysis 未接线 _cache_worker.request_cancel()——"
        "点「取消」仍停不下完整报告缓存生成"
    )
    assert "_cache_worker.isRunning()" in ca_src, (
        "_cancel_analysis 取消缓存线程前应先查 isRunning()"
    )


def test_cancel_analysis_actually_calls_request_cancel():
    """行为层：_cancel_analysis 必须真的调到 _cache_worker.request_cancel()。

    上面那条 AST 源码包含性断言拦不住「接线被包进 if False and 死分支」——
    反证测试实测放过该退化，故补本用例：假 self 实调，request_cancel 是真
    Mock，短路/死分支/拼写错误立刻现形。
    """
    from unittest import mock
    import types
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from gui_pyside6.main_window import MainWindow as MW

    cache_worker = types.SimpleNamespace(
        isRunning=lambda: True,
        request_cancel=mock.Mock(),
    )
    fake = types.SimpleNamespace(
        analysis_controller=types.SimpleNamespace(worker=None),
        audit_controller=types.SimpleNamespace(ai_worker=None),
        _cache_worker=cache_worker,
        progress_bar=mock.Mock(),
        progress_label=mock.Mock(),
        start_btn=mock.Mock(),
        log=mock.Mock(),
    )
    MW.__dict__["_cancel_analysis"](fake)
    cache_worker.request_cancel.assert_called_once_with()
    # 取消后必须走「已取消」UI 反馈分支（进度条隐藏 + 标签置位 + 按钮恢复）
    fake.progress_bar.setVisible.assert_called_once_with(False)
    fake.progress_label.setText.assert_called_once_with("已取消")
    fake.start_btn.setEnabled.assert_called_once_with(True)


def test_close_event_requests_cancel_before_quit():
    """closeEvent 收尾 _cache_worker 时必须先 request_cancel 再 quit()。"""
    tree, src = _parse_main_window()
    ce_src = _method_src(tree, src, "MainWindow", "closeEvent")
    block = ce_src[ce_src.index("if self._cache_worker:"):]
    block = block[:block.index("self._cache_worker = None")]
    assert "request_cancel" in block, (
        "closeEvent 的 _cache_worker 收尾块没有 request_cancel——"
        "quit() 对执行中的 run() 是空操作，只能白等 3 秒"
    )
    assert block.index("request_cancel") < block.index(".quit()"), (
        "closeEvent 必须先 request_cancel() 再 quit()，顺序反了取消就失效"
    )


# ---------- 4. 行为层：KeyboardInterrupt 被优雅吞掉 ----------

def test_keyboard_interrupt_is_swallowed(monkeypatch, capsys):
    """取消时 analyzer 抛 KeyboardInterrupt，run() 直接调用不得外泄异常。"""
    import analysis.analyzer as az
    W = _load_worker_cls()

    def _boom(*a, **kw):
        raise KeyboardInterrupt("用户取消")

    monkeypatch.setattr(az, "export_full_report_from_intermediates", _boom)
    monkeypatch.setattr(az, "LATEST_INTERMEDIATES", object())  # 走 intermediates 分支

    w = W("in.xlsx", None, "", "", "", "out.xlsx")
    # 直接调 run()（不起线程）：异常若外泄，本测试立即失败
    w.run()
    out = capsys.readouterr().out
    assert "已取消" in out, f"取消时应打「已取消」日志，实际输出: {out!r}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
