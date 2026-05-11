# -*- coding: utf-8 -*-
"""
单元测试：utils.helpers
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.helpers import standardize_remark


def test_standardize_remark():
    # 空值/NaN -> "未填写"
    assert standardize_remark('') == '未填写'
    assert standardize_remark(None) == '未填写'
    assert standardize_remark('   ') == '未填写'

    # 关键词匹配
    assert standardize_remark('堵料') == '工艺/设备调整'
    assert standardize_remark('无定额') == '定额/系统问题'
    assert standardize_remark('替代料') == '替代料'
    assert standardize_remark('水分不稳定') == '原材料质量波动'
    assert standardize_remark('试产') == '非正常生产'
    assert standardize_remark('消毒') == '卫生/消毒'

    # 未知/未归类 -> "其他"
    assert standardize_remark('正常') == '其他'
    assert standardize_remark('无') == '其他'
    assert standardize_remark('暂无') == '其他'
    assert standardize_remark('随机文本xyz') == '其他'

    print('[OK] test_standardize_remark')


if __name__ == '__main__':
    test_standardize_remark()
    print('\n[ALL PASS] utils unit tests passed!')
