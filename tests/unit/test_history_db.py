"""
Tests for History Database (Task Card 009)
"""
import pytest
import sqlite3
import pandas as pd
import tempfile
import os
from unittest.mock import Mock, MagicMock
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.history_db import (
    init_db,
    save_analysis_result,
    get_analysis_list,
    get_analysis_data,
    get_monthly_trend,
    cleanup_old_records,
    DB_PATH
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing"""
    db_path = str(tmp_path / "test_history.db")
    init_db(db_path)
    yield db_path


class TestHistoryDB:
    """Test suite for history_db functions"""

    def test_init_db(self, temp_db):
        """Test database initialization"""
        assert os.path.exists(temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert 'analysis_meta' in tables
        assert 'deviation_details' in tables

    def test_save_and_get_analysis(self, temp_db):
        """Test saving and retrieving analysis"""
        metadata = {
            'file_name': 'test.xlsx',
            'file_path': '/path/to/test.xlsx',
            'file_mtime': 1234567890,
            'total_rows': 100,
            'high_dev_rows': 15,
            'need_note_rows': 10,
            'approved_rows': 8,
            'dev_rate_distribution': {'high': 15, 'medium': 30, 'low': 55},
            'filter_condition': '',
            'extra': {}
        }
        df = pd.DataFrame({
            '工厂': ['工厂A', '工厂A', '工厂B'],
            '车间': ['车间1', '车间2', '车间1'],
            '订单日期': ['2026-01-01', '2026-01-02', '2026-01-03'],
            '流程订单': ['ORD001', 'ORD002', 'ORD003'],
            '物料编码': ['M001', 'M002', 'M003'],
            '物料描述': ['物料1', '物料2', '物料3'],
            '定额': [100, 200, 150],
            '实际': [120, 180, 160],
            '偏差率(%)': [20.0, -10.0, 6.7],
            '替代料': ['否', '是', '否'],
            '备注原因': ['', '', ''],
            '审核结果': ['待审核', '通过', '待审核'],
            'AI建议': ['', '', ''],
            '审核状态': ['pending', 'approved', 'pending'],
            '审核来源': ['', '', ''],
            '偏差金额': [20, -20, 10]
        })
        analysis_id = save_analysis_result(metadata, df, db_path=temp_db)
        assert analysis_id > 0
        analyses = get_analysis_list(db_path=temp_db)
        assert len(analyses) == 1
        assert analyses[0]['file_name'] == 'test.xlsx'
        retrieved_df = get_analysis_data(analysis_id, db_path=temp_db)
        assert len(retrieved_df) == 3
        assert '工厂' in retrieved_df.columns

    def test_get_monthly_trend(self, temp_db):
        """Test getting monthly trend data"""
        for i in range(3):
            metadata = {
                'file_name': f'test_{i}.xlsx',
                'file_path': f'/path/to/test_{i}.xlsx',
                'file_mtime': 1234567890 + i,
                'total_rows': 100,
                'high_dev_rows': 15,
                'need_note_rows': 10,
                'approved_rows': 8,
                'dev_rate_distribution': {},
                'filter_condition': '',
                'extra': {}
            }
            df = pd.DataFrame({
                '工厂': ['工厂A'],
                '偏差金额': [100 * (i + 1)]
            })
            save_analysis_result(metadata, df, db_path=temp_db)
        trend = get_monthly_trend(months=3, db_path=temp_db)
        assert len(trend) <= 3
        if len(trend) > 0:
            assert 'month' in trend[0]
            assert 'avg_deviation' in trend[0]

    def test_cleanup_old_records(self, temp_db):
        """Test cleaning up old records (180-day cleanup)"""
        result = cleanup_old_records(days=180, db_path=temp_db)
        assert isinstance(result, int)

    def test_idempotent_save(self, temp_db):
        """Test that saving the same file twice doesn't create duplicates"""
        metadata = {
            'file_name': 'idempotent_test.xlsx',
            'file_path': '/path/to/idempotent_test.xlsx',
            'file_mtime': 9999999,
            'total_rows': 10,
            'high_dev_rows': 0,
            'need_note_rows': 0,
            'approved_rows': 0,
            'dev_rate_distribution': {},
            'filter_condition': '',
            'extra': {}
        }
        df = pd.DataFrame({'工厂': ['工厂A'], '偏差金额': [100]})
        id1 = save_analysis_result(metadata, df, db_path=temp_db)
        id2 = save_analysis_result(metadata, df, db_path=temp_db)
        assert id1 == id2
        analyses = get_analysis_list(db_path=temp_db)
        assert len(analyses) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])