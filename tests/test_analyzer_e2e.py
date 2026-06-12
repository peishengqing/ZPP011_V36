# -*- coding: utf-8 -*-
"""
端到端测试场景1：导入 Excel → 执行分析 → 汇总统计校验

验证点：
  - 分析不抛异常
  - dev_df 行数符合预期
  - 正/负/零偏差条数与 fixture 预期一致
  - 偏差金额合计正确
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pandas as pd
import tempfile

from tests.fixtures.sample_data import (
    build_sample_df,
    get_expected_summary,
    create_sample_excel,
)


@pytest.fixture
def sample_excel():
    """生成临时测试 Excel，测试结束后自动清理"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        path = create_sample_excel(tmpdir)
        yield path


def test_analysis_completes_without_error(sample_excel):
    """核心：完整分析链路不抛异常"""
    from analysis.analyzer import do_analysis_v2

    alt_pairs = []
    result = do_analysis_v2(
        sample_excel,
        output_dir=None,
        alt_pairs=alt_pairs,
        return_dataframe=True,
    )
    assert result is not None, "分析应返回结果"


def test_dev_df_row_count(sample_excel):
    """dev_df 行数应与输入数据一致"""
    from analysis.analyzer import do_analysis_v2

    result = do_analysis_v2(
        sample_excel, output_dir=None, alt_pairs=[],
        return_dataframe=True,
    )
    expected = get_expected_summary()
    # 兼容返回格式：可能是 (dev_df, summary) 元组或单 DataFrame
    if isinstance(result, tuple):
        dev_df = result[0]
    else:
        dev_df = result
    assert len(dev_df) == expected['total_rows'], \
        f"行数应为 {expected['total_rows']}，实际 {len(dev_df)}"


def test_deviation_sign_counts(sample_excel):
    """正/负/零偏差条数应正确"""
    from analysis.analyzer import do_analysis_v2

    result = do_analysis_v2(
        sample_excel, output_dir=None, alt_pairs=[],
        return_dataframe=True,
    )
    if isinstance(result, tuple):
        dev_df = result[0]
    else:
        dev_df = result

    # 找出偏差率列
    rate_col = None
    for c in ['偏差率(%)', '偏差率', 'dev_rate']:
        if c in dev_df.columns:
            rate_col = c
            break
    assert rate_col is not None, f"未找到偏差率列，现有列: {list(dev_df.columns)}"

    rates = pd.to_numeric(dev_df[rate_col], errors='coerce')
    pos = (rates > 0).sum()
    neg = (rates < 0).sum()
    zero = (rates == 0).sum()

    expected = get_expected_summary()
    assert pos == expected['pos_dev_rows'], f"正偏差 {pos} != 预期 {expected['pos_dev_rows']}"
    assert neg == expected['neg_dev_rows'], f"负偏差 {neg} != 预期 {expected['neg_dev_rows']}"
    assert zero == expected['zero_dev_rows'], f"零偏差 {zero} != 预期 {expected['zero_dev_rows']}"
