# -*- coding: utf-8 -*-
"""
单元测试：storage.storage
"""

import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.storage import init_audit_db, save_audit_to_db, restore_audit_from_db, get_audit_db_path
import storage.storage as ss


def test_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        original_get = ss.get_audit_db_path
        ss.get_audit_db_path = lambda: db_path
        try:
            init_audit_db()
            assert os.path.exists(db_path), 'DB file not created'
        finally:
            ss.get_audit_db_path = original_get
    print('[OK] test_init')


def test_save_and_restore():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        original_get = ss.get_audit_db_path
        ss.get_audit_db_path = lambda: db_path
        try:
            init_audit_db()
            import pandas as pd
            test_df = pd.DataFrame([{
                '订单日期': '2026-01-01',
                '订单号': 'TEST001',
                '组件物料号': 'MAT01',
                '备注原因': 'test note',
            }])
            save_audit_to_db(test_df, auditor='test_user')
            restored = restore_audit_from_db(test_df.copy())
            assert len(restored) == 1 and restored.iloc[0]['订单号'] == 'TEST001'
            print('[OK] test_save_and_restore')
        finally:
            ss.get_audit_db_path = original_get


if __name__ == '__main__':
    test_init()
    test_save_and_restore()
    print('\n[ALL PASS] storage unit tests passed!')
