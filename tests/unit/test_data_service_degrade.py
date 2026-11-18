# -*- coding: utf-8 -*-
"""整改回归：预处理失败必须可被调用方感知（v43.406，审核报告 P0-3）。

背景：`DataService.preprocess_audit_data()` 原先整体套 try/except，失败时只
打日志然后**把半成品 DataFrame 原样返回**，调用方无法区分“成功”与“降级”。
整改后：

- `last_preprocess_error` 为 None 表示成功；
- 失败时置为 "类型: 消息"，并在 df.attrs['preprocess_failed'] 留痕；
- 同时以 level="error" 发 log_signal。
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def df():
    return pd.DataFrame({
        "工厂": ["A"], "订单日期": ["2026-01-01"], "流程订单": ["PO1"],
        "物料编码": ["100001"], "定额": [10.0], "实际": [11.0],
    })


def test_success_clears_error_flag(qapp, df):
    from gui_pyside6.services.data_service import DataService
    svc = DataService()
    out = svc.preprocess_audit_data(df.copy())
    assert svc.last_preprocess_error is None
    assert "preprocess_failed" not in out.attrs


def test_failure_is_observable_not_silent(qapp, df, monkeypatch):
    from gui_pyside6.services.data_service import DataService
    svc = DataService()

    def _boom(_df):
        raise ValueError("模拟清洗失败")

    monkeypatch.setattr(svc.preprocessor, "clean_columns", _boom)

    levels = []
    svc.log_signal.connect(lambda msg, level: levels.append(level))
    out = svc.preprocess_audit_data(df.copy())

    assert isinstance(out, pd.DataFrame), "降级仍应返回 DataFrame（避免界面白屏）"
    assert svc.last_preprocess_error is not None
    assert "模拟清洗失败" in svc.last_preprocess_error
    assert out.attrs.get("preprocess_failed") == svc.last_preprocess_error
    assert "error" in levels, "失败必须发 error 级日志，而不是只 print traceback"
