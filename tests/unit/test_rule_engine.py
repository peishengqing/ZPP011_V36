# -*- coding: utf-8 -*-
"""RuleEngine.check_remark unit tests"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.rule_engine import RuleEngine


def make_row(remark='', quota=None, code='MAT001', deviation_rate=0.0,
             actual=0, workshop='', material_code=''):
    return {
        '备注': remark,
        '定额': quota,
        '组件物料号': code,
        '偏差率(%)': deviation_rate,
        '实际': actual,
        '车间': workshop,
        '物料编码': material_code,
    }


def test_empty_remark():
    engine = RuleEngine()
    status, msg = engine.check_remark(make_row(remark=''), alt_pairs=None)
    assert status == 'red', f'expected red, got {status}'
    print('[OK] test_empty_remark')


def test_non_quota_non_alt():
    engine = RuleEngine()
    status, msg = engine.check_remark(
        make_row(remark='有备注', quota=None, code='MAT002', actual=100),
        alt_pairs={'MAT001'})
    assert status == 'yellow', f'expected yellow, got {status}'
    print('[OK] test_non_quota_non_alt')


def test_non_quota_zero_actual():
    engine = RuleEngine()
    status, msg = engine.check_remark(
        make_row(remark='有备注', quota=None, code='MAT002', actual=0),
        alt_pairs={'MAT001'})
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_non_quota_zero_actual')


def test_alt_material_exempt():
    engine = RuleEngine()
    status, msg = engine.check_remark(
        make_row(remark='有备注', quota=None, code='MAT001', actual=100),
        alt_pairs={'MAT001', 'MAT002'})
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_alt_material_exempt')


def test_all_pass():
    engine = RuleEngine()
    status, msg = engine.check_remark(
        make_row(remark='正常备注', quota=100, code='MAT004', deviation_rate=5.0, actual=100),
        alt_pairs=None)
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_all_pass')


# ---- Rule 3: turnover-based ----

def test_rule3_turnover_trigger():
    """deviation_rate=15 > 10, turnover_days=95 > 90 -> yellow"""
    engine = RuleEngine()
    wm = {'1车间': '食品主原料仓'}
    td = {('10000000', '食品主原料仓'): 95}
    status, msg = engine.check_remark(
        make_row(remark='有备注', deviation_rate=15.0, workshop='1车间', material_code='10000000'),
        alt_pairs=[], workshop_mapping=wm, turnover_dict=td)
    assert status == 'yellow', f'expected yellow, got {status}: {msg}'
    assert '周转天数' in msg
    print('[OK] test_rule3_turnover_trigger')


def test_rule3_turnover_no_mapping():
    """No workshop_mapping -> rule3 skipped"""
    engine = RuleEngine()
    status, msg = engine.check_remark(
        make_row(remark='有备注', deviation_rate=15.0, workshop='1车间'),
        alt_pairs=[], workshop_mapping=None, turnover_dict={})
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_rule3_turnover_no_mapping')


def test_rule3_turnover_no_dict():
    """No turnover_dict -> rule3 skipped"""
    engine = RuleEngine()
    status, msg = engine.check_remark(
        make_row(remark='有备注', deviation_rate=15.0, workshop='1车间'),
        alt_pairs=[], workshop_mapping={'1车间': '仓'}, turnover_dict=None)
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_rule3_turnover_no_dict')


def test_rule3_turnover_low_rate():
    """deviation_rate=5 <= 10 -> rule3 not triggered"""
    engine = RuleEngine()
    wm = {'1车间': '食品主原料仓'}
    td = {('10000000', '食品主原料仓'): 95}
    status, msg = engine.check_remark(
        make_row(remark='有备注', deviation_rate=5.0, workshop='1车间', material_code='10000000'),
        alt_pairs=[], workshop_mapping=wm, turnover_dict=td)
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_rule3_turnover_low_rate')


def test_rule3_turnover_low_days():
    """turnover_days=50 <= 90 -> rule3 not triggered"""
    engine = RuleEngine()
    wm = {'1车间': '食品主原料仓'}
    td = {('10000000', '食品主原料仓'): 50}
    status, msg = engine.check_remark(
        make_row(remark='有备注', deviation_rate=15.0, workshop='1车间', material_code='10000000'),
        alt_pairs=[], workshop_mapping=wm, turnover_dict=td)
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_rule3_turnover_low_days')


def test_rule3_turnover_workshop_not_mapped():
    """workshop not in mapping -> rule3 skipped for this row"""
    engine = RuleEngine()
    wm = {'1车间': '食品主原料仓'}
    td = {('10000000', '食品主原料仓'): 95}
    status, msg = engine.check_remark(
        make_row(remark='有备注', deviation_rate=15.0, workshop='99车间', material_code='10000000'),
        alt_pairs=[], workshop_mapping=wm, turnover_dict=td)
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_rule3_turnover_workshop_not_mapped')


def test_rule3_backward_compat():
    """Old call without new params still works"""
    engine = RuleEngine()
    status, msg = engine.check_remark(
        make_row(remark='有备注', quota=100, deviation_rate=15.0, actual=100),
        alt_pairs=None)
    assert status == 'none', f'expected none, got {status}'
    print('[OK] test_rule3_backward_compat')


if __name__ == '__main__':
    test_empty_remark()
    test_non_quota_non_alt()
    test_non_quota_zero_actual()
    test_alt_material_exempt()
    test_all_pass()
    test_rule3_turnover_trigger()
    test_rule3_turnover_no_mapping()
    test_rule3_turnover_no_dict()
    test_rule3_turnover_low_rate()
    test_rule3_turnover_low_days()
    test_rule3_turnover_workshop_not_mapped()
    test_rule3_backward_compat()
    print('\nAll tests passed!')
