# -*- coding: utf-8 -*-
"""导入前数据体检（analysis/data_health.py）用例。"""
import os

import pandas as pd
import pytest

from analysis.data_health import check_dataframe, check_file, render_html

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "fixtures", "golden", "_drink9_zpp011_wx.xlsx")


def _df(**over):
    base = {
        "工厂": ["1102", "1102", "1101"],
        "流程订单": ["1001", "1002", "1003"],
        "订单开始日期": ["2026-01-05", "2026-01-06", "2026-01-07"],
        "组件物料号": ["M1", "M2", "M3"],
        "组件物料描述": ["糖", "盐", "醋"],
        "组件物料类型": ["ROH", "ROH", "ROH"],
        "组件单位": ["KG", "KG", "KG"],
        "数量-定额": [10.0, 20.0, 30.0],
        "数量-实际": [9.0, 21.0, 30.0],
        "材料偏差": [-1.0, 1.0, 0.0],
        "偏差率(%)": [-10.0, 5.0, 0.0],
        "税率": [1.13, 1.13, 1.09],
    }
    base.update(over)
    return pd.DataFrame(base)


def _ids(report):
    return {c["id"] for c in report["checks"]}


def _by_id(report, cid):
    for c in report["checks"]:
        if c["id"] == cid:
            return c
    raise AssertionError(f"未产生检查项 {cid}")


def test_clean_table_has_no_blocking_or_warning():
    r = check_dataframe(_df())
    assert r["blocking"] is False
    assert r["summary"]["error"] == 0
    assert r["summary"]["warn"] == 0
    assert r["rows"] == 3 and r["columns"] == 12
    assert r["score"] == 100


def test_missing_required_column_blocks():
    df = _df().drop(columns=["数量-实际"])
    r = check_dataframe(df)
    assert r["blocking"] is True
    assert "数量-实际" in _by_id(r, "required")["detail"]


def test_missing_core_column_blocks():
    df = _df().drop(columns=["流程订单"])
    r = check_dataframe(df)
    assert r["blocking"] is True
    assert _by_id(r, "core")["level"] == "error"


def test_empty_table_blocks():
    r = check_dataframe(pd.DataFrame(columns=["订单开始日期", "数量-定额", "数量-实际",
                                              "流程订单", "组件物料类型"]))
    assert r["blocking"] is True
    assert "rows" in _ids(r)


def test_numeric_text_pollution_is_warned_with_samples():
    df = _df()
    df["数量-实际"] = pd.Series(["约9", 21.0, 30.0], dtype=object)
    r = check_dataframe(df)
    item = _by_id(r, "numeric_text")
    assert item["level"] == "warn"
    assert item["evidence"]["columns"]["数量-实际"] == 1
    assert "约9" in item["evidence"]["samples"]["数量-实际"][0]


def test_all_dates_unparsable_is_error():
    df = _df(**{"订单开始日期": ["另行", "待定", "未知"]})
    r = check_dataframe(df)
    assert _by_id(r, "date_parse")["level"] == "error"
    assert r["blocking"] is True


def test_partial_date_failure_is_warn_only():
    df = _df(**{"订单开始日期": ["2026-01-05", "BAD", "2026-01-07"]})
    r = check_dataframe(df)
    assert _by_id(r, "date_parse")["level"] == "warn"
    assert r["blocking"] is False


def test_duplicate_rows_warned():
    df = pd.concat([_df(), _df().iloc[[0]]], ignore_index=True)
    r = check_dataframe(df)
    assert _by_id(r, "duplicate_rows")["evidence"]["rows"] == 1


def test_zero_quota_ratio_decides_level():
    df = _df(**{"数量-定额": [0.0, 0.0, 30.0]})          # 2/3 ≥ 5% → warn
    assert _by_id(check_dataframe(df), "zero_quota")["level"] == "warn"
    df2 = pd.concat([_df()] * 20, ignore_index=True)
    df2.loc[0, "数量-定额"] = 0.0                        # 1/60 < 5% → info
    assert _by_id(check_dataframe(df2), "zero_quota")["level"] == "info"


def test_tax_coefficient_style_is_info_not_warning():
    r = check_dataframe(_df(**{"税率": [1.13, 1.13, 1.09]}))
    assert "tax_range" not in _ids(r)
    assert _by_id(r, "tax_form")["level"] == "info"


def test_tax_rate_style_is_accepted():
    r = check_dataframe(_df(**{"税率": [0.13, 0.13, 0.09]}))
    assert "tax_range" not in _ids(r)
    assert "tax_form" not in _ids(r)


def test_tax_out_of_range_warned():
    r = check_dataframe(_df(**{"税率": [13.0, 1.13, 1.09]}))
    assert _by_id(r, "tax_range")["level"] == "warn"


def test_multi_factory_listed_as_info():
    r = check_dataframe(_df())
    item = _by_id(r, "factories")
    assert item["level"] == "info"
    assert set(item["evidence"]["factories"]) == {"1102", "1101"}


def test_render_html_contains_verdict_and_rows():
    r = check_dataframe(_df().drop(columns=["组件单位"]))
    out = render_html(r)
    assert "<!DOCTYPE html>" in out
    assert "数据体检单" in out
    assert "可以继续分析" in out
    assert "单一工厂" in out or "包含多个工厂" in out


@pytest.mark.skipif(not os.path.isfile(FIXTURE), reason="缺少黄金基线样本表")
def test_check_file_on_golden_fixture():
    r = check_file(FIXTURE)
    assert r["rows"] > 1000
    assert r["sheet"] == "Data"
    assert r["blocking"] is False
    # 现场表税率为含税系数，不应被判为越界
    assert "tax_range" not in _ids(r)
