# -*- coding: utf-8 -*-
"""pytest 共享 fixtures"""
import os, sys, tempfile, shutil
import pytest
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    """临时目录 fixture"""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def sample_dataframe():
    """样本数据 DataFrame（100 行）"""
    np.random.seed(42)
    df = pd.DataFrame({
        '工厂': np.random.choice(['工厂A', '工厂B', '工厂C'], 100),
        '车间': np.random.choice(['车间1', '车间2', '车间3', '车间4'], 100),
        '订单日期': pd.date_range('2024-01-01', periods=100).strftime('%Y-%m-%d'),
        '流程订单': [f'PO{i:05d}' for i in range(100)],
        '物料编码': [f'MAT{i:05d}' for i in range(100)],
        '物料描述': [f'物料描述{i}' for i in range(100)],
        '物料大类': np.random.choice(['包材', '原料', '辅料', '成品'], 100),
        '定额': np.random.uniform(100, 1000, 100),
        '实际': np.random.uniform(90, 1100, 100),
        '偏差率%': np.random.uniform(-20, 50, 100),
        '替代料': np.random.choice(['是', '否'], 100),
        '备注': [''] * 100,
        '审核结果': np.random.choice(['通过', '不通过', ''], 100),
        'AI建议': [''] * 100,
        '审核状态': np.random.choice(['已审核', '待审核'], 100),
        '审核来源': np.random.choice(['系统', '手动', 'AI'], 100),
        '偏差金额': np.random.uniform(100, 5000, 100),
    })
    return df


@pytest.fixture
def large_dataframe():
    """大数据 DataFrame（10000 行，用于性能测试）"""
    np.random.seed(42)
    df = pd.DataFrame({
        '工厂': np.random.choice(['工厂A', '工厂B', '工厂C'], 10000),
        '车间': np.random.choice(['车间1', '车间2', '车间3', '车间4'], 10000),
        '订单日期': pd.date_range('2024-01-01', periods=10000).strftime('%Y-%m-%d'),
        '流程订单': [f'PO{i:05d}' for i in range(10000)],
        '物料编码': [f'MAT{i:05d}' for i in range(10000)],
        '物料描述': [f'物料描述{i}' for i in range(10000)],
        '物料大类': np.random.choice(['包材', '原料', '辅料', '成品'], 10000),
        '定额': np.random.uniform(100, 1000, 10000),
        '实际': np.random.uniform(90, 1100, 10000),
        '偏差率%': np.random.uniform(-20, 50, 10000),
        '替代料': np.random.choice(['是', '否'], 10000),
        '备注': [''] * 10000,
        '审核结果': np.random.choice(['通过', '不通过', ''], 10000),
        'AI建议': [''] * 10000,
        '审核状态': np.random.choice(['已审核', '待审核'], 10000),
        '审核来源': np.random.choice(['系统', '手动', 'AI'], 10000),
        '偏差金额': np.random.uniform(100, 5000, 10000),
    })
    return df


@pytest.fixture
def temp_db():
    """临时数据库 fixture"""
    import sqlite3
    db_path = tempfile.mktemp(suffix='.db')
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)
