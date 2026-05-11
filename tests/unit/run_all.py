# -*- coding: utf-8 -*-
"""
运行所有单元测试
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ===== test_config =====
from config import (
    DEFAULT_THRESHOLD, THRESHOLD_DESC, COLORS, FONTS,
    ANOMALY_TYPES, ANOMALY_DESC,
    BASE_DIR, OUTPUT_DIR, TEMP_DIR,
    APP_NAME, VERSION, WINDOW_WIDTH, WINDOW_HEIGHT,
    AUDIT_DB_NAME, MAX_EXCEL_ROWS
)

assert isinstance(DEFAULT_THRESHOLD, float) and DEFAULT_THRESHOLD == 10.0
assert 'pos_fill' in COLORS and 'neg_fill' in COLORS
assert len(ANOMALY_TYPES) == 5
assert os.path.isdir(BASE_DIR) and os.path.isdir(OUTPUT_DIR) and os.path.isdir(TEMP_DIR)
assert APP_NAME == "ZPP011 偏差分析器" and VERSION == "v36"
assert WINDOW_WIDTH == 1200 and WINDOW_HEIGHT == 700
print('[OK] test_config')

# ===== test_utils =====
from utils.helpers import standardize_remark
assert standardize_remark('') == '未填写'
assert standardize_remark(None) == '未填写'
assert standardize_remark('堵料') == '工艺/设备调整'
assert standardize_remark('无定额') == '定额/系统问题'
assert standardize_remark('替代料') == '替代料'
assert standardize_remark('试产') == '非正常生产'
assert standardize_remark('正常') == '其他'
assert standardize_remark('随机xyz') == '其他'
print('[OK] test_utils')

# ===== test_storage =====
import tempfile
import pandas as pd
from storage.storage import init_audit_db, save_audit_to_db, restore_audit_from_db
import storage.storage as ss

with tempfile.TemporaryDirectory() as tmpdir:
    db_path = os.path.join(tmpdir, 'test.db')
    original_get = ss.get_audit_db_path
    ss.get_audit_db_path = lambda: db_path
    try:
        init_audit_db()
        assert os.path.exists(db_path), 'DB not created'

        # save_audit_to_db expects Chinese column names
        test_df = pd.DataFrame([{
            '订单日期': '2026-01-01',
            '订单号': 'TEST001',
            '组件物料号': 'MAT01',
            '备注原因': 'test note',
        }])
        save_audit_to_db(test_df, auditor='test_user')

        # restore modifies DataFrame in-place
        restore_df = pd.DataFrame([{
            '订单日期': '2026-01-01',
            '订单号': 'TEST001',
            '组件物料号': 'MAT01',
            '备注原因': '',
        }])
        restore_audit_from_db(restore_df)
        assert restore_df.iloc[0]['备注原因'] == 'test note', \
            f"Expected 'test note', got '{restore_df.iloc[0]['备注原因']}'"
        assert '_audit_status' in restore_df.columns
        print('[OK] test_storage_save_restore')
    finally:
        ss.get_audit_db_path = original_get

# ===== test_alt_manager =====
from unittest.mock import patch
from domain.alt_material.alt_manager import (
    load_alt_pairs, save_alt_pairs,
    build_code_name_map, get_display_name,
)

# Pure function tests
df = pd.DataFrame([
    {'组件物料号': 'MAT001', '组件物料描述': 'Desc A'},
    {'组件物料号': 'MAT002', '组件物料描述': 'Desc B'},
])
result = build_code_name_map(df)
assert result == {'MAT001': 'Desc A', 'MAT002': 'Desc B'}
assert build_code_name_map(None) == {}

assert get_display_name('MAT001', 'Desc A') == 'MAT001（Desc A）'
assert get_display_name('', 'Desc A') == 'Desc A'
assert get_display_name('MAT001', 'MAT001') == 'MAT001'
assert get_display_name(None, None) == '未知'
print('[OK] test_build_code_name_map + test_get_display_name')

# save/load with mocked _get_config_path
with tempfile.TemporaryDirectory() as tmpdir:
    tmp_path = os.path.join(tmpdir, 'alt_pairs.json')
    with patch('domain.alt_material.alt_manager._get_config_path', return_value=tmp_path):
        with patch('domain.alt_material.alt_manager._get_config_dir', return_value=tmpdir):
            pairs = load_alt_pairs()
            assert isinstance(pairs, list)
            # alt_manager saves as list-of-tuples, NOT dicts
            test_pairs = [('MAT001', 'MAT002'), ('MAT003', 'MAT004')]
            save_alt_pairs(test_pairs)
            assert os.path.exists(tmp_path), f'File not created'
            loaded = load_alt_pairs()
            assert len(loaded) == 2
            # _normalize_pairs returns tuples: (code, name)
            assert loaded[0] == ('MAT001', 'MAT002')
            assert loaded[1] == ('MAT003', 'MAT004')
print('[OK] test_alt_manager_save_load')

print('\n========== ALL UNIT TESTS PASSED ==========')
