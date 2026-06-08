# -*- coding: utf-8 -*-
"""测试 core/fingerprint.py 指纹计算"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest


class TestCalcFingerprint:
    """测试 calc_fingerprint 函数"""

    def test_identical_inputs_same_fingerprint(self):
        """相同输入应产生相同指纹"""
        from core.fingerprint import calc_fingerprint

        fp1 = calc_fingerprint(100.5, 10.2)
        fp2 = calc_fingerprint(100.5, 10.2)
        assert fp1 == fp2

    def test_different_amounts_different_fingerprint(self):
        """不同偏差金额应产生不同指纹"""
        from core.fingerprint import calc_fingerprint

        fp1 = calc_fingerprint(100.5, 10.2)
        fp2 = calc_fingerprint(200.5, 10.2)
        assert fp1 != fp2

    def test_different_rates_different_fingerprint(self):
        """不同偏差率应产生不同指纹"""
        from core.fingerprint import calc_fingerprint

        fp1 = calc_fingerprint(100.5, 10.2)
        fp2 = calc_fingerprint(100.5, 10.3)
        assert fp1 != fp2

    def test_contains_pipe_separator(self):
        """指纹应包含 '|' 分隔符"""
        from core.fingerprint import calc_fingerprint

        fp = calc_fingerprint(100.5, 10.2)
        assert '|' in fp

    def test_negative_values(self):
        """负数输入不应出错"""
        from core.fingerprint import calc_fingerprint

        fp = calc_fingerprint(-100.5, -10.2)
        assert fp is not None
        assert isinstance(fp, str)
        assert len(fp) > 0

    def test_zero_values(self):
        """零值输入不应出错"""
        from core.fingerprint import calc_fingerprint

        fp = calc_fingerprint(0.0, 0.0)
        assert fp is not None
        assert isinstance(fp, str)

    def test_large_values(self):
        """大数值输入不应出错"""
        from core.fingerprint import calc_fingerprint

        fp = calc_fingerprint(1e10, 1e3)
        assert fp is not None
        assert isinstance(fp, str)
