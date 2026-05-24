# -*- coding: utf-8 -*-
"""
单元测试：core.rule_engine.RuleEngine.check_remark

测试三条备注校验规则及替代料豁免。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.rule_engine import RuleEngine


def make_row(remark='', quota=None, code='MAT001', deviation_rate=0.0, stagnant_days=0):
    """构造单行数据字典"""
    return {
        '备注': remark,
        '定额': quota,
        '组件物料号': code,
        '偏差率': deviation_rate,
        '呆滞天数': stagnant_days,
    }


def test_empty_remark():
    """规则1：空备注 → red"""
    engine = RuleEngine()
    row = make_row(remark='', code='MAT001')
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'red'
    assert '备注为空' in msg
    print('[OK] test_empty_remark')


def test_non_quota_non_alt():
    """规则2：无定额非替代料 → yellow"""
    engine = RuleEngine()
    # 无定额，不在替代料集合中
    row = make_row(remark='有备注', quota=None, code='MAT002')
    status, msg = engine.check_remark(row, alt_pairs={'MAT001'})  # MAT002 不在替代料中
    assert status == 'yellow'
    assert '无定额且非替代料' in msg
    print('[OK] test_non_quota_non_alt')


def test_deviation_and_stagnant():
    """规则3：偏差>10%且呆滞>90天 → red"""
    engine = RuleEngine()
    row = make_row(
        remark='有备注',
        quota=100,
        code='MAT003',
        deviation_rate=0.15,   # >10%
        stagnant_days=100        # >90
    )
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'red'
    assert '偏差>10%且呆滞>90天' in msg
    print('[OK] test_deviation_and_stagnant')


def test_alt_material_exempt():
    """替代料豁免：无定额但属于替代料 → 不触发规则2"""
    engine = RuleEngine()
    # MAT001 是替代料，规则2不触发
    row = make_row(remark='有备注', quota=None, code='MAT001')
    status, msg = engine.check_remark(row, alt_pairs={'MAT001', 'MAT002'})
    assert status == 'none'  # 不应是 yellow
    assert msg == ''
    print('[OK] test_alt_material_exempt')


def test_all_pass():
    """全部规则通过 → none"""
    engine = RuleEngine()
    row = make_row(
        remark='正常备注',
        quota=100,
        code='MAT004',
        deviation_rate=0.05,   # <10%
        stagnant_days=50         # <90
    )
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'none'
    assert msg == ''
    print('[OK] test_all_pass')


def test_deviation_only():
    """仅偏差>10%，但呆滞<90天 → 不触发规则3"""
    engine = RuleEngine()
    row = make_row(
        remark='有备注',
        quota=100,
        code='MAT005',
        deviation_rate=0.15,   # >10%
        stagnant_days=50         # <90
    )
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'none'  # 规则3需要同时满足两个条件
    print('[OK] test_deviation_only')


def test_stagnant_only():
    """仅呆滞>90天，但偏差<10% → 不触发规则3"""
    engine = RuleEngine()
    row = make_row(
        remark='有备注',
        quota=100,
        code='MAT006',
        deviation_rate=0.05,   # <10%
        stagnant_days=100        # >90
    )
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'none'  # 规则3需要同时满足两个条件
    print('[OK] test_stagnant_only')


if __name__ == '__main__':
    test_empty_remark()
    test_non_quota_non_alt()
    test_deviation_and_stagnant()
    test_alt_material_exempt()
    test_all_pass()
    test_deviation_only()
    test_stagnant_only()
    print('\n✅ 全部测试通过！')
