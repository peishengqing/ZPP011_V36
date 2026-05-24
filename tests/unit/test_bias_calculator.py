# -*- coding: utf-8 -*-
"""
tests/unit/test_bias_calculator.py
BiasCalculator 单元测试
"""
import sys
import os
import pandas as pd
import json
import shutil

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.bias_calculator import BiasCalculator


def test_normal_values():
    """正常值（分母≠0）"""
    calc = BiasCalculator()
    df = pd.DataFrame({
        '数量-实际': [110, 95, 105],
        '数量-定额': [100, 100, 100],
    })

    result = calc.calculate_df(df.copy())

    # 偏差数量 = 实际 - 定额
    assert abs(result['偏差数量'].iloc[0] - 10) < 0.01
    assert abs(result['偏差数量'].iloc[1] - (-5)) < 0.01
    assert abs(result['偏差数量'].iloc[2] - 5) < 0.01

    # 偏差率(%) = |偏差数量| / 定额 × 100
    assert abs(result['偏差率(%)'].iloc[0] - 10.0) < 0.01
    assert abs(result['偏差率(%)'].iloc[1] - 5.0) < 0.01
    assert abs(result['偏差率(%)'].iloc[2] - 5.0) < 0.01

    print("[PASS] test_normal_values")


def test_denominator_zero():
    """分母=0 → bias_rate = 0, bias_level = 'critical'"""
    calc = BiasCalculator()
    df = pd.DataFrame({
        '数量-实际': [0, 10],
        '数量-定额': [0, 0],  # 分母为0
    })

    result = calc.calculate_df(df.copy())

    # 分母为0时，偏差率应为0（通过mask避免除零）
    assert result['偏差率(%)'].iloc[0] == 0.0
    assert result['偏差率(%)'].iloc[1] == 0.0

    # 偏差等级应为 'critical'（因为 standard=0 导致 bias_rate=inf）
    assert result['_bias_level'].iloc[0] == 'critical'
    assert result['_bias_level'].iloc[1] == 'critical'

    print("[PASS] test_denominator_zero")


def test_actual_eq_standard():
    """实际=标准 → bias_qty=0, bias_rate=0"""
    calc = BiasCalculator()
    df = pd.DataFrame({
        '数量-实际': [100, 200],
        '数量-定额': [100, 200],
    })

    result = calc.calculate_df(df.copy())

    assert result['偏差数量'].iloc[0] == 0
    assert result['偏差率(%)'].iloc[0] == 0.0
    assert result['_bias_level'].iloc[0] == 'normal'

    print("[PASS] test_actual_eq_standard")


def test_boundary_thresholds():
    """边界阈值（normal, minor, major, critical）"""
    calc = BiasCalculator()

    # 测试不同偏差率对应的等级
    test_cases = [
        (0.5, 'normal'),   # 0.5% < 1%
        (3.0, 'minor'),    # 1% <= 3% < 5%
        (7.0, 'major'),    # 5% <= 7% < 10%
        (12.0, 'critical'),  # 12% >= 10%
    ]

    for bias_rate_pct, expected_level in test_cases:
        # 构造数据：定额=100，实际=100 + bias_qty
        bias_qty = bias_rate_pct  # 近似
        actual = 100 + bias_qty
        df = pd.DataFrame({
            '数量-实际': [actual],
            '数量-定额': [100.0],
        })

        result = calc.calculate_df(df.copy())
        actual_level = result['_bias_level'].iloc[0]

        print(f"  偏差率 {bias_rate_pct}% → 等级 {actual_level} (期望 {expected_level})")
        assert actual_level == expected_level, f"期望 {expected_level}，实际 {actual_level}"

    print("[PASS] test_boundary_thresholds")


def test_amount_calculation():
    """金额计算（优先含税差值，降级用量×单价）"""
    calc = BiasCalculator()

    # 测试 calculate_row() 的金额计算
    row_result = calc.calculate_row(
        actual=110,
        standard=100,
        amount_actual=1100,
        amount_standard=1000
    )
    assert abs(row_result['bias_amount'] - 100) < 0.01  # 1100 - 1000 = 100

    # 方法2：材料偏差 × 单价（降级）
    row_result2 = calc.calculate_row(
        actual=110,
        standard=100,
        price=10.5,
        amount_actual=None,  # 缺失，触发降级
        amount_standard=None   # 缺失，触发降级
    )
    # bias_qty = 10, price = 10.5 → bias_amount = 105
    assert abs(row_result2['bias_amount'] - 105) < 0.01

    print("[PASS] test_amount_calculation")


def test_config_missing_use_defaults():
    """配置缺失时使用默认阈值（通过 mock 测试）"""
    # 创建临时配置文件（缺失 bias 节点）
    temp_config = {
        "some_other_key": "value"
    }

    # 写入临时文件
    temp_path = os.path.join(os.path.dirname(__file__), '_temp_config.json')
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(temp_config, f, ensure_ascii=False, indent=2)

    # Mock：让 BiasCalculator 读取临时配置文件
    original_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config', 'defaults.json')
    backup_path = original_path + '.bak'

    try:
        # 备份原始配置
        shutil.move(original_path, backup_path)
        # 使用临时配置
        shutil.move(temp_path, original_path)

        calc = BiasCalculator()
        # 应该使用默认阈值
        assert calc.thresholds['normal'] == 0.01
        assert calc.thresholds['minor'] == 0.05
        assert calc.thresholds['major'] == 0.10

        # 测试计算仍能正常工作
        df = pd.DataFrame({
            '数量-实际': [110],
            '数量-定额': [100],
        })

        result = calc.calculate_df(df.copy())
        assert '_bias_level' in result.columns

        print("[PASS] test_config_missing_use_defaults")

    finally:
        # 恢复原始配置文件
        shutil.move(backup_path, original_path)


def test_calculate_row():
    """测试 calculate_row() 方法"""
    calc = BiasCalculator()

    # 正常情况：偏差率 10% → critical（≥10% 为严重）
    result = calc.calculate_row(actual=110, standard=100)
    assert abs(result['bias_qty'] - 10) < 0.01
    assert abs(result['bias_rate'] - 0.10) < 0.01  # 10 / 100 = 0.10
    assert abs(result['bias_rate_pct'] - 10.0) < 0.01
    assert result['bias_level'] == 'critical'  # 10% >= 10% → critical

    # 实际=标准
    result2 = calc.calculate_row(actual=100, standard=100)
    assert result2['bias_qty'] == 0
    assert result2['bias_rate'] == 0
    assert result2['bias_level'] == 'normal'

    # 分母=0
    result3 = calc.calculate_row(actual=10, standard=0)
    assert result3['bias_rate'] == float('inf')
    assert result3['bias_level'] == 'critical'

    print("[PASS] test_calculate_row")


if __name__ == '__main__':
    test_normal_values()
    test_denominator_zero()
    test_actual_eq_standard()
    test_boundary_thresholds()
    test_amount_calculation()
    test_config_missing_use_defaults()
    test_calculate_row()

    print("\n" + "="*50)
    print("所有测试通过 [PASS]")
    print("="*50)
