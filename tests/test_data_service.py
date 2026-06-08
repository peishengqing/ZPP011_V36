# -*- coding: utf-8 -*-
"""测试 DataService 数据预处理逻辑"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import pandas as pd


class TestDataService:
    """测试 DataService 核心方法"""

    @pytest.fixture
    def service(self):
        from gui_pyside6.services.data_service import DataService
        return DataService()

    def test_preprocess_adds_data_id(self, service):
        """preprocess_audit_data 应生成带工厂的 data_id"""
        df = pd.DataFrame({
            '订单日期': ['2026-05-01'],
            '流程订单': ['PO001'],
            '物料编码': ['MAT001'],
            '工厂': ['F1'],
            '偏差金额(含税)': [100.0],
            '偏差率(%)': [10.0],
        })
        result = service.preprocess_audit_data(df)
        assert 'data_id' in result.columns
        assert result['data_id'].iloc[0] == 'F1|2026-05-01|PO001|MAT001'

    def test_preprocess_adds_data_id_no_factory(self, service):
        """没有工厂列时也用订单日期+流程订单+物料编码"""
        df = pd.DataFrame({
            '订单日期': ['2026-05-01'],
            '流程订单': ['PO001'],
            '物料编码': ['MAT001'],
            '偏差金额(含税)': [100.0],
            '偏差率(%)': [10.0],
        })
        result = service.preprocess_audit_data(df)
        assert 'data_id' in result.columns
        assert result['data_id'].iloc[0] == '2026-05-01|PO001|MAT001'

    def test_preprocess_adds_fingerprint(self, service):
        """preprocess_audit_data 应生成 fingerprint 列"""
        df = pd.DataFrame({
            '订单日期': ['2026-05-01'],
            '流程订单': ['PO001'],
            '物料编码': ['MAT001'],
            '偏差金额(含税)': [100.0],
            '偏差率(%)': [10.0],
        })
        result = service.preprocess_audit_data(df)
        assert 'fingerprint' in result.columns
        assert '|' in str(result['fingerprint'].iloc[0])

    def test_normalize_alt_flag(self, service):
        """_normalize_alt_flag 标准化替代料标记"""
        df = pd.DataFrame({
            '物料编码': ['A', 'B', 'C', 'D'],
            '是否替代料': ['是', None, '替代', '否'],
        })
        result = service._normalize_alt_flag(df)
        assert result['是否替代料'].tolist() == ['是', '否', '是', '否']

    def test_normalize_alt_flag_fills_missing(self, service):
        """没有是否替代料列时填充默认值'否'"""
        df = pd.DataFrame({'物料编码': ['A']})
        result = service._normalize_alt_flag(df)
        assert '是否替代料' in result.columns
        assert result['是否替代料'].iloc[0] == '否'

    def test_emtpy_dataframe(self, service):
        """空 DataFrame 返回空"""
        df = pd.DataFrame()
        result = service.preprocess_audit_data(df)
        assert len(result) == 0

    def test_data_ids_are_unique(self, service):
        """不同订单和物料的 data_id 应不同"""
        df = pd.DataFrame({
            '工厂': ['F1', 'F1'],
            '订单日期': ['2026-05-01', '2026-05-02'],
            '流程订单': ['PO001', 'PO002'],
            '物料编码': ['MAT001', 'MAT001'],
            '偏差金额(含税)': [100.0, 200.0],
            '偏差率(%)': [10.0, 20.0],
        })
        result = service.preprocess_audit_data(df)
        assert result['data_id'].iloc[0] != result['data_id'].iloc[1]
