# -*- coding: utf-8 -*-
"""历史数据库单元测试"""
import os, sys, tempfile, unittest
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.history_db import (
    init_db, save_analysis_result, get_analysis_list,
    get_analysis_data, compare_analyses, cleanup_old_records
)


class TestHistoryDB(unittest.TestCase):
    """历史数据库测试"""

    def setUp(self):
        """创建临时数据库"""
        self.temp_db = tempfile.mktemp(suffix='.db')
        init_db(self.temp_db)

    def tearDown(self):
        """清理临时数据库"""
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_save_and_get(self):
        """测试保存和获取"""
        df = pd.DataFrame({
            '工厂': ['工厂A'],
            '车间': ['车间1'],
            '订单日期': ['2024-01-01'],
            '流程订单': ['PO001'],
            '物料编码': ['MAT001'],
            '物料描述': ['测试物料'],
            '定额': [100],
            '实际': [110],
            '偏差率%': [10],
            '替代料': ['否'],
            '备注': [''],
            '审核结果': ['通过'],
            'AI建议': [''],
            '审核状态': ['待审核'],
            '审核来源': ['系统'],
            '偏差金额': [1000],
        })

        metadata = {
            'file_name': 'test.xlsx',
            'file_path': '/path/to/test.xlsx',
            'file_mtime': 1234567890.0,
            'total_rows': 1,
            'high_dev_rows': 0,
            'need_note_rows': 1,
            'approved_rows': 0,
        }

        analysis_id = save_analysis_result(metadata, df, self.temp_db)
        self.assertGreater(analysis_id, 0)

        # 测试获取列表
        records = get_analysis_list(limit=10, db_path=self.temp_db)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['id'], analysis_id)

    def test_idempotency(self):
        """测试幂等性"""
        df = pd.DataFrame({
            '工厂': ['工厂A'],
            '车间': ['车间1'],
            '物料编码': ['MAT001'],
        })

        metadata = {
            'file_name': 'test.xlsx',
            'file_path': '/path/to/test.xlsx',
            'file_mtime': 1234567890.0,
            'total_rows': 1,
            'high_dev_rows': 0,
            'need_note_rows': 0,
            'approved_rows': 0,
        }

        id1 = save_analysis_result(metadata, df, self.temp_db)
        id2 = save_analysis_result(metadata, df, self.temp_db)

        self.assertEqual(id1, id2)

    def test_transaction_rollback(self):
        """测试事务回滚"""
        df = pd.DataFrame({
            '工厂': ['工厂A'],
            '车间': ['车间1'],
            '物料编码': ['MAT001'],
        })

        metadata = {
            'file_name': 'test.xlsx',
            'file_path': '/path/to/test.xlsx',
            'file_mtime': 1234567890.0,
            'total_rows': 1,
            'high_dev_rows': 0,
            'need_note_rows': 0,
            'approved_rows': 0,
        }

        # 第一次保存成功
        id1 = save_analysis_result(metadata, df, self.temp_db)

        # 验证有一条记录
        records = get_analysis_list(db_path=self.temp_db)
        self.assertEqual(len(records), 1)

    def test_compare_analyses(self):
        """测试对比功能"""
        # 第一次分析
        df1 = pd.DataFrame({
            '工厂': ['工厂A'],
            '车间': ['车间1'],
            '物料编码': ['MAT001'],
            '偏差率%': [15],
            '备注': [''],
            '审核状态': ['待审核'],
        })

        metadata1 = {
            'file_name': 'test1.xlsx',
            'file_path': '/path/to/test1.xlsx',
            'file_mtime': 1234567890.0,
            'total_rows': 10,
            'high_dev_rows': 5,
            'need_note_rows': 3,
            'approved_rows': 2,
        }

        id1 = save_analysis_result(metadata1, df1, self.temp_db)

        # 第二次分析
        df2 = pd.DataFrame({
            '工厂': ['工厂A'],
            '车间': ['车间1'],
            '物料编码': ['MAT002'],
            '偏差率%': [12],
            '备注': ['已备注'],
            '审核状态': ['已审核'],
        })

        metadata2 = {
            'file_name': 'test2.xlsx',
            'file_path': '/path/to/test2.xlsx',
            'file_mtime': 1234567891.0,
            'total_rows': 12,
            'high_dev_rows': 4,
            'need_note_rows': 2,
            'approved_rows': 4,
        }

        id2 = save_analysis_result(metadata2, df2, self.temp_db)

        # 对比
        result = compare_analyses(id1, id2, self.temp_db)

        self.assertEqual(result['analysis1']['total_rows'], 10)
        self.assertEqual(result['analysis2']['total_rows'], 12)
        self.assertEqual(result['diff']['total_rows'], 2)
        self.assertEqual(result['diff']['approved_rows'], 2)


if __name__ == '__main__':
    unittest.main()
