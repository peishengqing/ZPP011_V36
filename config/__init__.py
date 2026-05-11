# -*- coding: utf-8 -*-
"""
config 包（v36 抽取）
"""

from config.settings import (
    DEFAULT_THRESHOLD,
    THRESHOLD_DESC,
    COLORS,
    FONTS,
    ANOMALY_TYPES,
    ANOMALY_DESC,
)

from config.paths import (
    BASE_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
)

from config.constants import (
    APP_NAME,
    APP_NAME_EN,
    VERSION,
    BUILD_DATE,
    WINDOW_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    TREE_COL_WIDTH,
    TREE_ROW_HEIGHT,
    AUDIT_COL_WIDTH,
    MAX_EXCEL_ROWS,
    DEFAULT_PAGE_SIZE,
    ANALYSIS_TIMEOUT_SEC,
    AUDIT_DB_NAME,
    AUDIT_TABLE_NAME,
    MAX_BACKUP_FILES,
    EXCEL_EXTENSIONS,
    OUTPUT_EXCEL_NAME,
    PPT_TEMPLATE_SUFFIX,
)

__all__ = [
    # settings
    'DEFAULT_THRESHOLD',
    'THRESHOLD_DESC',
    'COLORS',
    'FONTS',
    'ANOMALY_TYPES',
    'ANOMALY_DESC',
    # paths
    'BASE_DIR',
    'OUTPUT_DIR',
    'TEMP_DIR',
    # constants
    'APP_NAME',
    'APP_NAME_EN',
    'VERSION',
    'BUILD_DATE',
    'WINDOW_TITLE',
    'WINDOW_WIDTH',
    'WINDOW_HEIGHT',
    'WINDOW_MIN_WIDTH',
    'WINDOW_MIN_HEIGHT',
    'TREE_COL_WIDTH',
    'TREE_ROW_HEIGHT',
    'AUDIT_COL_WIDTH',
    'MAX_EXCEL_ROWS',
    'DEFAULT_PAGE_SIZE',
    'ANALYSIS_TIMEOUT_SEC',
    'AUDIT_DB_NAME',
    'AUDIT_TABLE_NAME',
    'MAX_BACKUP_FILES',
    'EXCEL_EXTENSIONS',
    'OUTPUT_EXCEL_NAME',
    'PPT_TEMPLATE_SUFFIX',
]
