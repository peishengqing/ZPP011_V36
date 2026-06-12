# -*- coding: utf-8 -*-
"""测试 analysis/net_offset.py 净偏差抵消逻辑"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import pandas as pd


class TestApplyNetOffset:
    """测试 apply_net_offset 函数"""

    # 需要有: 订单日期, 流程订单(or 流程日期), 物料编码, 偏差数量, 偏差金额(含税)

    def test_basic_net_offset(self):
        """基础净偏差抵消：同组抵消计算"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '订单日期': ['2026-05-01', '2026-05-01'],
            '流程订单': ['PO001', 'PO001'],
            '物料编码': ['A', 'B'],
            '偏差数量': [10, -20],
            '偏差金额(含税)': [100.0, -80.0],
            '数量-定额': [100, 100],
            '数量-实际': [200, 20],
        })
        result = apply_net_offset(df, [('A', 'B')], group_key=['订单日期', '流程订单'])
        assert '净偏差金额' in result.columns
        # A(100) + B(-80) = 20
        assert result['净偏差金额'].iloc[0] == 20.0
        assert result['净偏差金额'].iloc[1] == 20.0

    def test_no_offset_when_disabled(self):
        """当 enable=False 时，净偏差 = 原偏差金额"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '物料编码': ['A', 'B'],
            '偏差金额(含税)': [100.0, -50.0],
            '偏差数量': [10, -5],
            '数量-定额': [100, 100],
            '数量-实际': [200, 50],
        })
        result = apply_net_offset(df, [('A', 'B')], enable=False)
        assert '净偏差金额' in result.columns
        assert result['净偏差金额'].iloc[0] == 100.0
        assert result['净偏差金额'].iloc[1] == -50.0

    def test_empty_alt_pairs(self):
        """空替代料配对不抵消"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '物料编码': ['A'],
            '偏差金额(含税)': [100.0],
            '偏差数量': [10],
            '数量-定额': [100],
            '数量-实际': [200],
        })
        result = apply_net_offset(df, [], group_key=[])
        assert result['净偏差金额'].iloc[0] == 100.0

    def test_missing_required_column(self):
        """缺少偏差数量列不应崩溃（为0）"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '物料编码': ['A'],
            '偏差金额(含税)': [100.0],
            '数量-定额': [100],
            '数量-实际': [200],
        })
        result = apply_net_offset(df, [], group_key=[])
        assert '净偏差金额' in result.columns
        assert result['净偏差金额'].iloc[0] == 100.0

    def test_explicit_group_key(self):
        """显式传入 group_key 时正确分组"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '订单日期': ['2026-05-01', '2026-05-01'],
            '流程订单': ['PO001', 'PO001'],
            '物料编码': ['A', 'B'],
            '偏差金额(含税)': [100.0, -100.0],
            '偏差数量': [10, -10],
            '数量-定额': [100, 100],
            '数量-实际': [200, 0],
        })
        result = apply_net_offset(df, [('A', 'B')], group_key=['订单日期', '流程订单'])
        assert result['净偏差金额'].iloc[0] == 0.0
        assert result['净偏差金额'].iloc[1] == 0.0


class TestNetOffsetEdgeCases:
    """补充场景：替代料净偏差边界条件"""

    def test_three_way_alt_group(self):
        """三物料互替（A↔B, B↔C），分组正确且金额抵消按顺序叠加"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '订单日期':       ['2026-05-01'] * 3,
            '流程订单':       ['PO001'] * 3,
            '物料编码':       ['A', 'B', 'C'],
            '偏差金额(含税)':  [150.0, -80.0, -40.0],
            '偏差数量':       [15, -8, -4],
            '数量-定额':      [100, 100, 100],
            '数量-实际':      [200, 20, 60],
        })
        # A↔B, B↔C → 三物料同一组，净金额 = 150 - 80 - 40 = 30
        result = apply_net_offset(df, [('A', 'B'), ('B', 'C')],
                                  group_key=['订单日期', '流程订单'])
        assert '净偏差金额' in result.columns
        for i in range(3):
            assert result['净偏差金额'].iloc[i] == 30.0, \
                f"物料{df['物料编码'].iloc[i]} 净偏差应为 30.0，实际 {result['净偏差金额'].iloc[i]}"

    def test_one_sided_alt_only(self):
        """单边替代：A 替代 B，但 B 未出现 → 不抵消"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '订单日期':     ['2026-05-01'],
            '流程订单':     ['PO001'],
            '物料编码':     ['A'],
            '偏差金额(含税)': [200.0],
            '偏差数量':     [20],
            '数量-定额':    [100],
            '数量-实际':    [120],
        })
        result = apply_net_offset(df, [('A', 'B')], group_key=['订单日期', '流程订单'])
        assert result['净偏差金额'].iloc[0] == 200.0, "单边不应抵消"

    def test_zero_deviation_no_offset(self):
        """偏差数量为 0 时，净偏差不变"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '订单日期':     ['2026-05-01', '2026-05-01'],
            '流程订单':     ['PO001', 'PO001'],
            '物料编码':     ['A', 'B'],
            '偏差金额(含税)': [0.0, 0.0],
            '偏差数量':     [0, 0],
            '数量-定额':    [100, 100],
            '数量-实际':    [100, 100],
        })
        result = apply_net_offset(df, [('A', 'B')], group_key=['订单日期', '流程订单'])
        assert result['净偏差金额'].iloc[0] == 0.0
        assert result['净偏差金额'].iloc[1] == 0.0

    def test_multi_group_independent(self):
        """不同订单组的替代料不应互相影响"""
        from analysis.net_offset import apply_net_offset

        df = pd.DataFrame({
            '订单日期':     ['2026-05-01', '2026-05-01', '2026-05-02', '2026-05-02'],
            '流程订单':     ['PO001', 'PO001', 'PO002', 'PO002'],
            '物料编码':     ['A', 'B', 'A', 'B'],
            '偏差金额(含税)': [200.0, -50.0, 100.0, -80.0],
            '偏差数量':     [20, -5, 10, -8],
            '数量-定额':    [100, 100, 100, 100],
            '数量-实际':    [120, 20, 110, 20],
        })
        result = apply_net_offset(df, [('A', 'B')],
                                  group_key=['订单日期', '流程订单'])
        # 第一组：200 - 50 = 150；第二组：100 - 80 = 20
        assert result['净偏差金额'].iloc[0] == 150.0
        assert result['净偏差金额'].iloc[1] == 150.0
        assert result['净偏差金额'].iloc[2] == 20.0
        assert result['净偏差金额'].iloc[3] == 20.0
