# -*- coding: utf-8 -*-
"""筛选引擎测试"""
import pytest
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.audit.filters.filter_engine import FilterEngine


class TestFilterEngine:
    """筛选引擎测试"""

    def test_factory_filter(self):
        """测试工厂筛选"""
        df = pd.DataFrame({
            '工厂': ['工厂A', '工厂B', '工厂A', '工厂C']
        })
        engine = FilterEngine()
        filters = {'factory': '工厂A'}
        result = engine.apply(filters, df)
        assert len(result) == 2

    def test_factory_filter_all(self):
        """测试工厂=全部，返回所有"""
        df = pd.DataFrame({
            '工厂': ['工厂A', '工厂B', '工厂A', '工厂C']
        })
        engine = FilterEngine()
        filters = {'factory': '全部'}
        result = engine.apply(filters, df)
        assert len(result) == 4

    def test_workshop_filter(self):
        """测试车间筛选"""
        df = pd.DataFrame({
            '车间': ['车间1', '车间2', '车间1', '车间3']
        })
        engine = FilterEngine()
        filters = {'workshop': '车间1'}
        result = engine.apply(filters, df)
        assert len(result) == 2

    def test_dev_rate_filter(self):
        """测试偏差率筛选"""
        df = pd.DataFrame({
            '偏差率(%)': [5.0, 15.0, 25.0, -15.0]
        })
        engine = FilterEngine()
        filters = {'dev_rate': '>10%'}
        result = engine.apply(filters, df)
        assert len(result) == 2  # 15 and 25

    def test_dev_rate_filter_abs(self):
        """测试偏差率绝对值筛选"""
        df = pd.DataFrame({
            '偏差率(%)': [5.0, 15.0, 25.0, -15.0]
        })
        engine = FilterEngine()
        filters = {'dev_rate': '绝对值≥10%'}
        result = engine.apply(filters, df)
        assert len(result) == 3  # 15, 25, -15

    def test_amount_range_filter(self):
        """测试金额范围筛选"""
        df = pd.DataFrame({
            '偏差金额': [500.0, 1500.0, 5000.0, 100.0]
        })
        engine = FilterEngine()
        filters = {'amount_min': '1000', 'amount_max': '5000'}
        result = engine.apply(filters, df)
        assert len(result) == 2  # 1500 and 5000

    def test_empty_filter(self):
        """测试空筛选条件（返回全部）"""
        df = pd.DataFrame({
            '工厂': ['工厂A', '工厂B', '工厂C']
        })
        engine = FilterEngine()
        filters = {}
        result = engine.apply(filters, df)
        assert len(result) == 3

    def test_stat_big_dev(self):
        """测试大偏差统计筛选"""
        df = pd.DataFrame({
            '偏差率(%)': [5.0, 15.0, 25.0, -15.0]
        })
        engine = FilterEngine()
        filters = {'stat': 'big_dev'}
        result = engine.apply(filters, df)
        assert len(result) == 3  # 15, 25, -15

    def test_stat_no_note(self):
        """测试无备注统计筛选"""
        df = pd.DataFrame({
            '备注原因': ['有备注', '', None, '其他']
        })
        engine = FilterEngine()
        filters = {'stat': 'no_note'}
        result = engine.apply(filters, df)
        assert len(result) == 2  # '' and None

    def test_search_filter(self):
        """测试关键词搜索"""
        df = pd.DataFrame({
            '物料名称': ['瓶子A', '盖子B', '标签C', '瓶子D']
        })
        engine = FilterEngine()
        filters = {'search': '瓶子'}
        result = engine.apply(filters, df)
        assert len(result) == 2

    def test_empty_df(self):
        """测试空 DataFrame"""
        df = pd.DataFrame()
        engine = FilterEngine()
        result = engine.apply({}, df)
        assert len(result) == 0

    def test_material_category_filter(self):
        """测试物料大类筛选"""
        df = pd.DataFrame({
            '物料编码': ['200001', '100001', '200002', '400001'],
        })
        engine = FilterEngine()
        filters = {'material_category': '包材'}
        result = engine.apply(filters, df)
        assert len(result) == 2  # 200xxx → 包材

    def test_date_range_filter(self):
        """测试日期范围筛选"""
        df = pd.DataFrame({
            '订单日期': ['2024-01-15', '2024-02-15', '2024-03-15']
        })
        engine = FilterEngine()
        filters = {'date_start': '2024-02-01', 'date_end': '2024-03-01'}
        result = engine.apply(filters, df)
        assert len(result) == 1

    def test_alt_filter(self):
        """测试替代料筛选"""
        df = pd.DataFrame({
            '_is_alt': [True, False, True, False]
        })
        engine = FilterEngine()
        filters = {'is_alt': '是'}
        result = engine.apply(filters, df)
        assert len(result) == 2

    def test_remark_empty_filter(self):
        """测试备注为空筛选"""
        df = pd.DataFrame({
            '备注原因': ['有备注', '', None, '其他']
        })
        engine = FilterEngine()
        filters = {'remark': '为空'}
        result = engine.apply(filters, df)
        assert len(result) == 2
