# -*- coding: utf-8 -*-
"""测试 analysis/analyzer.py 可独立测试的函数"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import pandas as pd


class TestBuildDeviationSummary:
    """测试 _build_deviation_summary 函数"""

    def test_basic_grouping(self):
        """按物料编码汇总偏差金额"""
        from analysis.analyzer import _build_deviation_summary

        dev_df = pd.DataFrame({
            '物料编码': ['A', 'A', 'B'],
            '物料名称': ['物料A', '物料A', '物料B'],
            '物料类型': ['原料', '原料', '包材'],
            '偏差金额': [100.0, -50.0, 200.0],
        })
        result = _build_deviation_summary(dev_df, None)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert '总偏差金额' in result.columns
        row_a = result[result['物料编码'] == 'A'].iloc[0]
        assert row_a['正偏差金额'] == 100.0
        assert row_a['负偏差金额'] == -50.0
        assert row_a['总偏差金额'] == 50.0

    def test_no_deviation_column(self):
        """没有偏差金额列时尝试用数量计算"""
        from analysis.analyzer import _build_deviation_summary

        dev_df = pd.DataFrame({
            '物料编码': ['A'],
            '数量-实际': [110],
            '数量-定额': [100],
        })
        result = _build_deviation_summary(dev_df, None)
        assert '总偏差金额' in result.columns

    def test_only_code_column_empty_fallback(self):
        """只有物料编码列仍可运行"""
        from analysis.analyzer import _build_deviation_summary

        dev_df = pd.DataFrame({'物料编码': ['A'], '偏差金额': [100.0]})
        result = _build_deviation_summary(dev_df, None)
        assert len(result) == 1
        assert result['总偏差金额'].iloc[0] == 100.0

    def test_sort_by_abs_amount(self):
        """按总偏差金额绝对值降序排序"""
        from analysis.analyzer import _build_deviation_summary

        dev_df = pd.DataFrame({
            '物料编码': ['A', 'B', 'C'],
            '物料名称': ['A', 'B', 'C'],
            '偏差金额': [100.0, -500.0, 50.0],
        })
        result = _build_deviation_summary(dev_df, None)
        assert result.iloc[0]['物料编码'] == 'B'


class TestInferMaterialType:
    """测试 infer_material_type 顶层函数"""

    def test_material_20_packaging(self):
        """20 开头 → 包材"""
        from analysis.analyzer import infer_material_type
        assert infer_material_type('20000123') == '包材'

    def test_material_30_raw(self):
        """30 开头 → 原料"""
        from analysis.analyzer import infer_material_type
        assert infer_material_type('30004567') == '原料'

    def test_material_other_prefix(self):
        """其他数字开头 → 其他"""
        from analysis.analyzer import infer_material_type
        assert infer_material_type('40008999') == '其他'

    def test_material_empty_string(self):
        """空字符串 → 其他"""
        from analysis.analyzer import infer_material_type
        assert infer_material_type('') == '其他'

    def test_material_none(self):
        """None → 未知"""
        from analysis.analyzer import infer_material_type
        assert infer_material_type(None) == '未知'

    def test_material_non_string(self):
        """非字符串（如 int）→ 未知"""
        from analysis.analyzer import infer_material_type
        assert infer_material_type(12345) == '未知'
