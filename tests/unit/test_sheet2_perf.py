# -*- coding: utf-8 -*-
"""性能优化回归：sheet2 无配对早退、有配对语义不变、行号缓存。"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from analysis.excel_builder.sheet2_alt import build_sheet2  # noqa: E402
from analysis import analyzer as az  # noqa: E402


def _cb_log():
    seq = []
    return seq, (lambda i, n, p: seq.append((i, n, p)))


def test_sheet2_no_pairs_returns_empty_fast(tmp_path):
    """无配对：直接返回空结果（不做全量 groupby 建索引），进度发 100。"""
    import time

    df = pd.DataFrame({
        "流程订单": [1, 1, 2, 2, 3],
        "组件物料描述": ["甲", "乙", "甲", "丙", "丁"],
        "组件物料编码": ["A1", "B1", "A1", "C1", "D1"],
    })
    seq, cb = _cb_log()
    t0 = time.perf_counter()
    alt_df, alt_set = build_sheet2(df, [], cb)
    dt = time.perf_counter() - t0
    assert alt_df is not None and len(alt_df) == 0
    assert alt_set == set()
    assert seq[-1][2] == 100
    assert dt < 0.5, "无配对应直接返回（%.2fs）" % dt


def test_sheet2_matching_semantics_unchanged(tmp_path):
    """有配对：三级匹配（精确）与净偏差计算结果不变。"""
    df = pd.DataFrame({
        "流程订单": [1, 1, 2, 2],
        "组件物料描述": ["甲材料", "辅料", "甲材料", "乙材料"],
        "组件物料编码": ["A1", "B1", "A1", "B2"],
        "订单开始日期": pd.to_datetime(["2026-09-01"] * 4),
        "车间": ["一车间"] * 4,
        "组件单位": ["KG"] * 4,
        "材料偏差": [10.0, 1.0, -4.0, 2.0],
        "偏差率(%)": [5.0, 1.0, -2.0, 1.0],
        "数量-定额": [100.0, 10.0, 200.0, 50.0],
        "偏差金额(含税)": [100.0, 10.0, -40.0, 20.0],
    })
    seq, cb = _cb_log()
    alt_df, alt_set = build_sheet2(df, [("甲材料", "乙材料")], cb)
    # 订单 1 有甲无乙（B 列表为空不产行）；订单 2 甲+乙 → 共 1 行
    assert len(alt_df) == 1, "应只有 1 行（订单 2）: %s" % alt_df.to_dict("records")
    # 订单 2：A=甲材料(偏差-4), B=乙材料(偏差+2) → 净数量 -2、净金额 -20
    o2 = alt_df[alt_df["订单号"].astype(str) == "2"]
    assert len(o2) == 1, "订单 2 应产生 1 行替代料明细: %s" % alt_df.to_dict("records")
    assert o2.iloc[0]["净偏差数量"] == -2.0
    assert o2.iloc[0]["净偏差金额"] == -20.0
    assert o2.iloc[0]["物料A"] == "甲材料" and o2.iloc[0]["物料B"] == "乙材料"
    # alt_order_mat：订单2 的 A 与 B 都进集合
    assert ("2", "甲材料") in alt_set and ("2", "乙材料") in alt_set
    # 订单 1：有甲但无乙 → 无匹配 B → 不产生行
    assert not (alt_df["订单号"].astype(str) == "1").any()


def test_excel_rownum_cache(tmp_path):
    """同一文件第二次分析走行号缓存（openpyxl 不再全表扫），结果一致。"""
    import time

    # 用完整 schema 的样例（analyzer 需要 组件物料类型 等列）
    from tests.fixtures.sample_data import build_sample_df

    path = str(tmp_path / "rows.xlsx")
    build_sample_df().to_excel(path, index=False)

    az._EXCEL_ROWNUM_CACHE.clear()
    p1 = az.do_analysis_v2(path, output_dir=None, alt_pairs=[], return_dataframe=True)
    assert len(az._EXCEL_ROWNUM_CACHE) == 1, "首次分析后应写入行号缓存"
    key = next(iter(az._EXCEL_ROWNUM_CACHE))
    first_rows = list(az._EXCEL_ROWNUM_CACHE[key])

    t0 = time.perf_counter()
    p2 = az.do_analysis_v2(path, output_dir=None, alt_pairs=[], return_dataframe=True)
    dt = time.perf_counter() - t0
    assert len(az._EXCEL_ROWNUM_CACHE[key]) == len(first_rows)
    # 第二次分析命中缓存（不再扫 openpyxl）：原表行号结果一致
    assert list(p2["原表行号"]) == list(range(2, len(p2) + 2))
    assert dt < 2.0, "缓存命中后第二次分析应很快（%.2fs）" % dt
