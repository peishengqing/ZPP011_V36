# -*- coding: utf-8 -*-
"""
单元测试：config 模块
"""

# 让 tests 包能找到项目根目录
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config
from config import (
    DEFAULT_THRESHOLD,
    THRESHOLD_DESC,
    COLORS,
    FONTS,
    ANOMALY_TYPES,
    ANOMALY_DESC,
    BASE_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    APP_NAME,
    VERSION,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    AUDIT_DB_NAME,
    MAX_EXCEL_ROWS,
)


def test_settings():
    assert isinstance(DEFAULT_THRESHOLD, float)
    assert DEFAULT_THRESHOLD == 10.0
    assert 'pos_fill' in COLORS
    assert 'neg_fill' in COLORS
    assert 'header' in COLORS
    print('[OK] test_settings')


def test_paths():
    assert os.path.isdir(BASE_DIR)
    assert os.path.isdir(OUTPUT_DIR)
    assert os.path.isdir(TEMP_DIR)
    print('[OK] test_paths')


def test_constants():
    assert APP_NAME == "ZPP011 偏差分析器"
    assert VERSION == "v36"
    assert WINDOW_WIDTH == 1200
    assert WINDOW_HEIGHT == 700
    assert AUDIT_DB_NAME == "zpp011_audit.db"
    assert MAX_EXCEL_ROWS == 65530
    print('[OK] test_constants')


def test_anomaly_types():
    assert len(ANOMALY_TYPES) == 5
    assert "系统无定额" in ANOMALY_TYPES
    assert "替代料超阈值" in ANOMALY_TYPES
    print('[OK] test_anomaly_types')


if __name__ == '__main__':
    test_settings()
    test_paths()
    test_constants()
    test_anomaly_types()
    print('\n[ALL PASS] config 单元测试通过！')