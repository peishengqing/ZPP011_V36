"""
Tests for Attribution Engine (Task Card 013)
"""
import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.attribution import calculate_contribution


class TestCalculateContribution:
    """Test suite for calculate_contribution function"""

    def test_empty_dataframe(self):
        """Test handling empty DataFrame"""
        result = calculate_contribution(pd.DataFrame(), history_df=None)
        assert 'error' in result or result.get('current_total', 0) == 0

    def test_none_dataframe(self):
        """Test handling None input"""
        result = calculate_contribution(None, history_df=None)
        assert 'error' in result

    def test_current_data_only(self):
        """Test with current data only (no history)"""
        df = pd.DataFrame({
            '偏差金额': [100, 200, 300],
            'material_category': ['包材', '原辅料', '包材']
        })
        result = calculate_contribution(df, history_df=None)
        assert isinstance(result, dict)
        assert result['has_history'] is False
        assert result['current_total'] == 600.0
        assert '包材' in result['report_text']

    def test_with_history(self):
        """Test with both current and history data"""
        current_df = pd.DataFrame({
            '偏差金额': [100, 200, 300],
            'material_category': ['包材', '原辅料', '包材']
        })
        history_df = pd.DataFrame({
            '偏差金额': [50, 100, 150],
            'material_category': ['包材', '原辅料', '包材']
        })
        result = calculate_contribution(current_df, history_df=history_df)
        assert isinstance(result, dict)
        assert result['has_history'] is True
        assert result['current_total'] == 600.0
        assert result['history_total'] == 300.0
        assert result['change'] == 300.0

    def test_missing_amount_column(self):
        """Test handling missing deviation amount column"""
        df = pd.DataFrame({
            '物料号': ['M001', 'M002'],
            '偏差率(%)': [10.5, 8.3]
        })
        result = calculate_contribution(df, history_df=None)
        assert 'error' in result

    def test_with_material_category(self):
        """Test analysis with material category"""
        df = pd.DataFrame({
            '偏差金额': [1000, 2000, 1500],
            'material_category': ['包材', '原辅料', '包材']
        })
        result = calculate_contribution(df, history_df=None)
        assert isinstance(result, dict)
        assert '包材' in result['report_text']
        assert '原辅料' in result['report_text']
        assert '%' in result['report_text']

    def test_zero_total_current(self):
        """Test handling zero total current amount"""
        df = pd.DataFrame({
            '偏差金额': [0, 0, 0],
            'material_category': ['包材', '原辅料', '包材']
        })
        result = calculate_contribution(df, history_df=None)
        assert isinstance(result, dict)
        assert result['current_total'] == 0.0

    def test_zero_total_history(self):
        """Test handling zero total history amount"""
        current_df = pd.DataFrame({
            '偏差金额': [100, 200],
            'material_category': ['包材', '原辅料']
        })
        history_df = pd.DataFrame({
            '偏差金额': [0, 0],
            'material_category': ['包材', '原辅料']
        })
        result = calculate_contribution(current_df, history_df=history_df)
        assert isinstance(result, dict)
        assert result['has_history'] is True
        assert result['history_total'] == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])