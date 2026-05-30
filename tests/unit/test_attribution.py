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

from core.attribution import calculate_attribution


class TestCalculateAttribution:
    """Test suite for calculate_attribution function"""
    
    def test_empty_dataframe(self):
        """Test handling empty DataFrame"""
        result = calculate_attribution(pd.DataFrame(), history_df=None)
        assert "当前无分析数据" in result
    
    def test_none_dataframe(self):
        """Test handling None input"""
        result = calculate_attribution(None, history_df=None)
        assert "当前无分析数据" in result
    
    def test_current_data_only(self):
        """Test with current data only (no history)"""
        df = pd.DataFrame({
            '偏差金额': [100, 200, 300],
            'material_category': ['包材', '原辅料', '包材']
        })
        
        result = calculate_attribution(df, history_df=None)
        
        assert "当前偏差总额" in result
        assert "600.00" in result
        assert "偏差金额按物料大类分布" in result
        assert "包材" in result
    
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
        
        result = calculate_attribution(current_df, history_df=history_df)
        
        assert "历史偏差总额" in result
        assert "当前偏差总额" in result
        assert "变化" in result
    
    def test_missing_amount_column(self):
        """Test handling missing deviation amount column"""
        df = pd.DataFrame({
            '物料号': ['M001', 'M002'],
            '偏差率(%)': [10.5, 8.3]
        })
        
        result = calculate_attribution(df, history_df=None)
        assert "数据中缺少偏差金额列" in result
    
    def test_with_material_category(self):
        """Test analysis with material category"""
        df = pd.DataFrame({
            '偏差金额': [1000, 2000, 1500],
            'material_category': ['包材', '原辅料', '包材']
        })
        
        result = calculate_attribution(df, history_df=None)
        
        assert "包材" in result
        assert "原辅料" in result
        # Check percentage calculation
        assert "%" in result
    
    def test_zero_total_current(self):
        """Test handling zero total current amount"""
        df = pd.DataFrame({
            '偏差金额': [0, 0, 0],
            'material_category': ['包材', '原辅料', '包材']
        })
        
        result = calculate_attribution(df, history_df=None)
        assert "当前偏差总额" in result
    
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
        
        result = calculate_attribution(current_df, history_df=history_df)
        assert "变化" in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
