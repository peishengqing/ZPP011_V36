# -*- coding: utf-8 -*-
"""utils/excel_io 读表加速层测试：calamine/openpyxl 结果一致、缺失时静默兜底。"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


def _write_sample(tmp_path, name="t.xlsx"):
    path = str(tmp_path / name)
    df = pd.DataFrame({"a": [1, 2, None], "b": ["x", "y", ""]})
    df.to_excel(path, index=False)
    return path


def test_open_excel_book_values_match_openpyxl(tmp_path):
    """open_excel_book（calamine 优先）读出的值必须与 openpyxl 一致。"""
    from utils import excel_io

    path = _write_sample(tmp_path)
    got = excel_io.open_excel_book(path).parse("Sheet1")
    ref = pd.read_excel(path, engine="openpyxl")
    g = got.astype(object).fillna("__NA__")
    r = ref.astype(object).fillna("__NA__")
    assert (g == r).all().all(), "引擎结果不一致:\n%s\n---\n%s" % (g, r)
    assert excel_io.available_engine() in ("calamine", "openpyxl")


def test_fallback_when_calamine_unavailable(tmp_path, monkeypatch):
    """模拟未装 calamine（打包 exe 默认场景）：必须退回 openpyxl 且结果可用。"""
    from utils import excel_io

    monkeypatch.setattr(excel_io, "HAS_CALAMINE", False)
    path = _write_sample(tmp_path, "t2.xlsx")
    assert excel_io.available_engine() == "openpyxl"
    got = excel_io.open_excel_book(path).parse("Sheet1")
    assert got["a"].dropna().tolist() == [1, 2]


def test_read_sheet_helper(tmp_path):
    from utils import excel_io

    path = _write_sample(tmp_path, "t3.xlsx")
    got = excel_io.read_sheet(path, "Sheet1")
    assert got["b"].tolist()[:2] == ["x", "y"]
