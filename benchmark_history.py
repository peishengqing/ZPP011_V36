# -*- coding: utf-8 -*-
"""历史数据库性能测试"""
import os, sys, time, tempfile
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.history_db import init_db, save_analysis_result

def benchmark_10000_rows():
    """测试 1 万行数据写入性能"""
    # 生成 1 万行测试数据
    print("生成 10000 行测试数据...")
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

    metadata = {
        'file_name': 'benchmark_10000.xlsx',
        'file_path': '/path/to/benchmark.xlsx',
        'file_mtime': 1234567890.0,
        'total_rows': 10000,
        'high_dev_rows': len(df[abs(df['偏差率%']) > 10]),
        'need_note_rows': len(df[df['备注'] == '']),
        'approved_rows': len(df[df['审核状态'] == '已审核']),
    }

    temp_db = tempfile.mktemp(suffix='.db')
    init_db(temp_db)

    print("开始性能测试...")
    start_time = time.time()

    analysis_id = save_analysis_result(metadata, df, temp_db)

    elapsed = time.time() - start_time

    print(f"写入完成！")
    print(f"  耗时：{elapsed:.2f} 秒")
    print(f"  目标：< 1 秒")
    if elapsed < 1:
        print(f"  结果：通过")
    else:
        print(f"  结果：未通过")

    # 清理
    os.remove(temp_db)

    return elapsed < 1

if __name__ == '__main__':
    success = benchmark_10000_rows()
    sys.exit(0 if success else 1)
