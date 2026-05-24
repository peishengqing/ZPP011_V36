# -*- coding: utf-8 -*-
"""单元测试：core.rule_engine.RuleEngine.check_remark"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.rule_engine import RuleEngine


def make_row(remark='', quota=None, code='MAT001', deviation_rate=0.0, stagnant_days=0, actual=0):
    return {
        '备注': remark,
        '定额': quota,
        '组件物料号': code,
        '偏差率': deviation_rate,
        '呆滞天数': stagnant_days,
        '实际': actual,
    }


def test_empty_remark():
    engine = RuleEngine()
    row = make_row(remark='', code='MAT001')
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'red'
    print('[OK] test_empty_remark')


def test_non_quota_non_alt():
    engine = RuleEngine()
    row = make_row(remark='有备注', quota=None, code='MAT002', actual=100)
    status, msg = engine.check_remark(row, alt_pairs={'MAT001'})
    assert status == 'yellow'
    print('[OK] test_non_quota_non_alt')


def test_non_quota_zero_actual():
    engine = RuleEngine()
    row = make_row(remark='有备注', quota=None, code='MAT002', actual=0)
    status, msg = engine.check_remark(row, alt_pairs={'MAT001'})
    assert status == 'none'
    print('[OK] test_non_quota_zero_actual')


def test_deviation_and_stagnant():
    engine = RuleEngine()
    row = make_row(remark='有备注', quota=100, code='MAT003', deviation_rate=0.15, stagnant_days=100, actual=100)
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'red'
    print('[OK] test_deviation_and_stagnant')


def test_alt_material_exempt():
    engine = RuleEngine()
    row = make_row(remark='有备注', quota=None, code='MAT001', actual=100)
    status, msg = engine.check_remark(row, alt_pairs={'MAT001', 'MAT002'})
    assert status == 'none'
    print('[OK] test_alt_material_exempt')


def test_all_pass():
    engine = RuleEngine()
    row = make_row(remark='正常备注', quota=100, code='MAT004', deviation_rate=0.05, stagnant_days=50, actual=100)
    status, msg = engine.check_remark(row, alt_pairs=None)
    assert status == 'none'
    print('[OK] test_all_pass')


if __name__ == '__main__':
    test_empty_remark()
    test_non_quota_non_alt()
    test_non_quota_zero_actual()
    test_deviation_and_stagnant()
    test_alt_material_exempt()
    test_all_pass()
    print('\n✅ 全部测试通过！')
