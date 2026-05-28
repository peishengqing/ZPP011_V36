# -*- coding: utf-8 -*-
"""偏差计算模块测试"""
import pytest
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.bias_calculator import BiasCalculator


class TestBiasCalculator:
    """偏差计算测试"""

    def test_calculate_row_normal(self):
        """测试单行正常计算（正偏差）"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=120, standard=100)
        assert result['bias_qty'] == pytest.approx(20.0)
        assert result['bias_rate'] == pytest.approx(0.2, rel=0.01)
        assert result['bias_rate_pct'] == pytest.approx(20.0, rel=0.01)
        assert result['bias_level'] == 'critical'

    def test_calculate_row_negative_bias(self):
        """测试单行负偏差（少耗）"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=80, standard=100)
        assert result['bias_qty'] == pytest.approx(-20.0)
        assert result['bias_rate'] == pytest.approx(0.2, rel=0.01)
        assert result['bias_level'] == 'critical'

    def test_calculate_row_zero_standard(self):
        """测试定额为 0 → 偏差率 inf，等级 critical"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=50, standard=0)
        assert result['bias_rate'] == float('inf')
        assert result['bias_level'] == 'critical'

    def test_calculate_row_zero_actual(self):
        """测试实际为 0"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=0, standard=100)
        assert result['bias_qty'] == pytest.approx(-100.0)
        assert result['bias_rate'] == pytest.approx(1.0)
        assert result['bias_level'] == 'critical'

    def test_calculate_row_both_zero(self):
        """测试定额和实际都为 0 → 偏差率 inf, critical"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=0, standard=0)
        assert result['bias_rate'] == float('inf')
        assert result['bias_level'] == 'critical'

    def test_calculate_row_normal_level(self):
        """测试偏差率 < 1% → normal"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=100.5, standard=100)
        assert result['bias_level'] == 'normal'

    def test_calculate_row_minor_level(self):
        """测试偏差率 1%-5% → minor"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=103, standard=100)
        assert result['bias_level'] == 'minor'

    def test_calculate_row_major_level(self):
        """测试偏差率 5%-10% → major"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=108, standard=100)
        assert result['bias_level'] == 'major'

    def test_calculate_row_with_price(self):
        """测试带单价的偏差金额"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=120, standard=100, price=10.0)
        assert result['bias_amount'] == pytest.approx(200.0)

    def test_calculate_row_with_amount(self):
        """测试带含税金额的偏差金额"""
        calc = BiasCalculator()
        result = calc.calculate_row(actual=120, standard=100,
                                     amount_actual=1200.0, amount_standard=1000.0)
        assert result['bias_amount'] == pytest.approx(200.0)

    def test_calculate_df_basic(self):
        """测试 DataFrame 向量化计算"""
        calc = BiasCalculator()
        df = pd.DataFrame({
            '数量-实际': [120.0, 80.0, 100.0],
            '数量-定额': [100.0, 100.0, 100.0],
        })
        result = calc.calculate_df(df)
        assert '偏差数量' in result.columns
        assert '偏差率(%)' in result.columns
        assert '_bias_level' in result.columns
        assert result['偏差数量'].iloc[0] == pytest.approx(20.0)
        assert result['偏差数量'].iloc[1] == pytest.approx(-20.0)

    def test_calculate_df_zero_quota(self):
        """测试 DataFrame 中定额为 0 的行"""
        calc = BiasCalculator()
        df = pd.DataFrame({
            '数量-实际': [50.0],
            '数量-定额': [0.0],
        })
        result = calc.calculate_df(df)
        assert result['_bias_level'].iloc[0] == 'critical'

    def test_classify_level(self):
        """测试等级分类"""
        calc = BiasCalculator()
        assert calc._classify_level(0.005) == 'normal'
        assert calc._classify_level(0.03) == 'minor'
        assert calc._classify_level(0.08) == 'major'
        assert calc._classify_level(0.15) == 'critical'
        assert calc._classify_level(float('inf')) == 'critical'
