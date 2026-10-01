# -*- coding: utf-8 -*-
"""分析进度单调性回归。

历史缺陷：各 Sheet 构建器沿用「自身 0-100%」约定，总进度序列变成
50→0→100→0→100→70→0→100…（来回弹跳），进度条与 12 格步骤图标被反复打回，
与用户看到的实际进度不一致。修复后：
- analyzer 端：Sheet1~10 通过 _ranged_progress 映射到互不重叠的全局区间；
- UI 端：_on_analysis_progress_ui 单调保护，低值通知不回退进度条。
"""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from tests.fixtures.sample_data import create_sample_excel  # noqa: E402


def _collector():
    seq = []

    def cb(step_idx, step_name, percent):
        seq.append((int(step_idx), str(step_name), int(percent)))

    return seq, cb


def _assert_monotonic(seq, label):
    percents = [p for _, _, p in seq]
    assert len(percents) >= 5, "%s 发射过少：%s" % (label, percents)
    for a, b in zip(percents, percents[1:]):
        assert a <= b, "%s 进度回退：%d → %d（序列 %s）" % (label, a, b, percents)
    assert percents[-1] == 100, "%s 末值应为 100，实际 %s" % (label, percents[-1])


def test_main_path_percent_monotonic(tmp_path):
    """主表快速路径（return_dataframe=True）：percent 序列单调不减、止于 100。"""
    from analysis.analyzer import do_analysis_v2

    excel = create_sample_excel(str(tmp_path))
    seq, cb = _collector()
    do_analysis_v2(excel, output_dir=None, alt_pairs=[],
                   return_dataframe=True, progress_callback=cb)
    _assert_monotonic(seq, "主表路径")


def _sample_excel_with_real_columns(tmp_path):
    """完整报告路径需要「订单类型」等真实数据列（样例 fixture 只覆盖主表路径），
    在生成的 Excel 上补列，避免动共享 fixture。"""
    import pandas as pd

    excel = create_sample_excel(str(tmp_path))
    df = pd.read_excel(excel)
    for col, val in (("订单类型", "1"), ("产品物料号码", "P-001"),
                     ("产品物料描述", "产品物料")):
        if col not in df.columns:
            df[col] = val
    df.to_excel(excel, index=False)
    return excel


def test_full_report_path_percent_monotonic(tmp_path):
    """完整报告路径（Sheet1~10 + 保存）：percent 序列单调不减、止于 100。"""
    from analysis.analyzer import do_analysis_v2

    excel = _sample_excel_with_real_columns(tmp_path)
    out_dir = str(tmp_path / "report")
    seq, cb = _collector()
    result = do_analysis_v2(excel, output_dir=out_dir, alt_pairs=[],
                            return_dataframe=False, progress_callback=cb)
    _assert_monotonic(seq, "完整报告路径")
    # 报告文件确实生成
    import glob
    files = glob.glob(os.path.join(out_dir, "ZPP011偏差分析最终版_*.xlsx"))
    assert files, "完整报告未生成: %s" % out_dir


def test_ranged_progress_maps_and_clamps():
    """_ranged_progress：内部 0-100 → 全局 [lo, hi] 线性映射，越界钳制。"""
    from analysis.analyzer import _ranged_progress

    out = []
    cb = _ranged_progress(lambda i, n, p: out.append(p), 25, 35)
    cb(1, "Sheet1", 0)
    cb(1, "Sheet1", 50)
    cb(1, "Sheet1", 100)
    cb(1, "Sheet1", -10)   # 越界下限 → 钳制到 lo
    cb(1, "Sheet1", 999)   # 越界上限 → 钳制到 hi
    assert out[0] == 25, "0% 应映射到区间起点 25"
    assert out[1] == 30, "50% 应映射到区间中点 30"
    assert out[2] == 35, "100% 应映射到区间终点 35"
    assert out[3] == 25
    assert out[4] == 35
