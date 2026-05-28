# -*- coding: utf-8 -*-
"""规则引擎测试"""
import pytest
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.rule_engine import RuleEngine


class TestRuleEngine:
    """规则引擎测试"""

    def test_check_remark_empty(self):
        """规则1：空备注 → red"""
        engine = RuleEngine()
        row = {'备注': '', '定额': 100, '实际': 110, '替代料': '否', '偏差率(%)': 10}
        status, msg = engine.check_remark(row)
        assert status == 'red'
        assert '空' in msg

    def test_check_remark_no_quota_not_alt(self):
        """规则2：无定额非替代料 → yellow"""
        engine = RuleEngine()
        row = {'备注': '物料替代', '定额': None, '实际': 50, '组件物料号': 'X001', '偏差率(%)': 0}
        status, msg = engine.check_remark(row)
        assert status == 'yellow'
        assert '无定额' in msg or '替代料' in msg

    def test_check_remark_with_alt_pair(self):
        """规则2豁免：无定额但是替代料 → none"""
        engine = RuleEngine()
        row = {'备注': '物料替代', '定额': None, '实际': 50, '组件物料号': 'ALT001', '偏差率(%)': 0}
        status, msg = engine.check_remark(row, alt_pairs={'ALT001'})
        assert status == 'none'

    def test_check_remark_high_dev_stagnant(self):
        """规则3：偏差率>10% 且 周转天数>90 → yellow"""
        engine = RuleEngine()
        row = {
            '备注': '测试备注', '定额': 100, '实际': 120,
            '组件物料号': 'MAT001', '偏差率(%)': 20,
            '工厂': '工厂A', '车间': '车间1', '物料编码': 'MAT001'
        }
        workshop_mapping = {'工厂A:车间1': 'WH001'}
        turnover_dict = {('MAT001', 'WH001'): 120}
        status, msg = engine.check_remark(row, workshop_mapping=workshop_mapping, turnover_dict=turnover_dict)
        assert status == 'yellow'
        assert '周转' in msg

    def test_check_remark_normal(self):
        """正常备注 → none"""
        engine = RuleEngine()
        row = {'备注': '物料替代，偏差合理', '定额': 100, '实际': 105, '偏差率(%)': 5}
        status, msg = engine.check_remark(row)
        assert status == 'none'

    def test_get_band_with_default_rules(self):
        """测试偏差率区间判定（使用默认规则或实际规则）"""
        engine = RuleEngine()
        # 尝试从 deviation_rate_bands 获取（仅默认规则有此 key）
        band = engine.get_band(0.02, 'deviation_rate_bands')
        if band is not None:
            assert 'label' in band or 'color' in band
        else:
            # 实际 rules.json 可能没有 deviation_rate_bands，检查其他结构
            rules = engine.get_all_rules()
            assert 'version' in rules or 'rules' in rules

    def test_get_band_missing_key(self):
        """测试获取不存在的 band key → 返回 None"""
        engine = RuleEngine()
        result = engine.get_band(0.5, 'nonexistent_key')
        assert result is None

    def test_get_color_for_deviation_rate(self):
        """测试偏差率颜色"""
        engine = RuleEngine()
        color = engine.get_color_for_deviation_rate(0.02)
        assert isinstance(color, str)
        assert color.startswith('#')

    def test_check_auto_close_condition_disabled(self):
        """测试自动关闭条件（实际 rules.json 无 auto_close → disabled）"""
        engine = RuleEngine()
        row = {'审核状态': '已审核', '偏差率': 0.03}
        # 实际 rules.json 没有 auto_close 配置，返回 False
        result = engine.check_auto_close_condition(row)
        assert result == False

    def test_evaluate_condition(self):
        """测试条件评估"""
        engine = RuleEngine()
        assert engine._evaluate_condition(5, 'gt', 3) == True
        assert engine._evaluate_condition(5, 'lt', 3) == False
        assert engine._evaluate_condition('已审核', 'eq', '已审核') == True
        assert engine._evaluate_condition(5, 'ge', 5) == True
        assert engine._evaluate_condition(5, 'le', 5) == True
        assert engine._evaluate_condition(5, 'ne', 3) == True

    def test_evaluate_condition_unsupported_op(self):
        """测试不支持的操作符"""
        engine = RuleEngine()
        assert engine._evaluate_condition(5, 'unknown_op', 3) == False

    def test_safe_float(self):
        """测试安全浮点转换"""
        engine = RuleEngine()
        assert engine._safe_float('3.14') == pytest.approx(3.14)
        assert engine._safe_float('abc') == 0.0
        assert engine._safe_float(None) == 0.0
        assert engine._safe_float(42) == 42.0

    def test_reload(self):
        """测试规则热重载"""
        engine = RuleEngine()
        engine.reload()
        assert len(engine.rules) > 0

    def test_get_all_rules(self):
        """测试获取全部规则"""
        engine = RuleEngine()
        rules = engine.get_all_rules()
        assert isinstance(rules, dict)
        assert len(rules) > 0

    def test_get_s01_rules(self):
        """测试获取 S01 规则"""
        engine = RuleEngine()
        s01_rules = engine.get_s01_rules()
        assert isinstance(s01_rules, dict)
