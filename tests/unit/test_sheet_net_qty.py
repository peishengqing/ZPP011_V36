# -*- coding: utf-8 -*-
"""v44.10 回归：「无备注预警」「中间地带明细」补「净偏差数量」列。

覆盖四条路径：
1. builder 输出携带内部定位键 _净偏差键（流程订单|物料编码）；
2. attach_net_qty_column 查 net_offset_map 命中 → 取替代料组净偏差；
3. 未命中（非替代料行）→ 回退毛口径「偏差数量」；
4. 空表 / 缺键列 / 空 map 兜底不炸，且非空输出恒有「净偏差数量」列。

注意：含连字符/括号的列名（数量-实际、偏差率(%)）不能作关键字参数，
一律走 **{} 字典解包。
"""
import pandas as pd

from analysis.analyzer import attach_net_qty_column
from analysis.excel_builder.sheet3_no_note import build_sheet3
from analysis.excel_builder.sheet4_middle import build_sheet4


def _row(**over):
    """构造一条满足 builder 输入列要求的主数据行。"""
    row = {
        '订单开始日期': '2026-11-01',
        '工厂名称': '达利一厂',
        '车间': '车间A',
        '组件物料描述': '物料甲',
        '物料分类': '原料',
        '组件单位': 'KG',
        '数量-定额': 100.0,
        '数量-实际': 120.0,
        '材料偏差': 20.0,
        '偏差率(%)': 20.0,
        '偏差金额(含税)': 226.0,
        # 无备注 = NaN（与生产一致：Excel 空单元格读入即 NaN）；
        # 空字符串会被 sheet3 的「无备注」过滤误判为有备注（既有口径，勿改）
        '备注原因': None,
        '标准原因': '',
        '流程订单': '1000001',
        '组件物料号': 'M001',
    }
    row.update(over)
    return row


_NOP_PROGRESS = lambda *a, **k: None  # noqa: E731

# 一对替代料配对（(编码, 描述) 元组形式），仅供 sheet4 的排除过滤使用
_ALT_PAIRS = [(('MX01', '物料X'), ('MB02', '物料乙'))]


def test_sheet3_carries_net_key():
    """无备注预警 builder 输出应携带 _净偏差键（流程订单|物料编码）。"""
    df = pd.DataFrame([
        _row(),
        _row(组件物料描述='物料乙', 流程订单='1000002', 组件物料号='M002',
             材料偏差=30.0, **{'偏差率(%)': 30.0, '数量-实际': 130.0}),
    ])
    out = build_sheet3(df, _NOP_PROGRESS)
    assert not out.empty
    assert '_净偏差键' in out.columns
    assert set(out['_净偏差键']) == {'1000001|M001', '1000002|M002'}


def test_sheet4_carries_net_key():
    """中间地带 builder 输出应携带 _净偏差键（|偏差率|<10 才进中间地带）。"""
    df = pd.DataFrame([
        _row(材料偏差=5.0, 流程订单='1000003', 组件物料号='M003',
             **{'偏差率(%)': 5.0, '数量-实际': 105.0}),
    ])
    out = build_sheet4(df, pd.DataFrame(), _ALT_PAIRS, _NOP_PROGRESS)
    assert not out.empty
    assert '_净偏差键' in out.columns
    assert list(out['_净偏差键']) == ['1000003|M003']


def test_attach_net_qty_map_hit_then_gross_fallback():
    """替代料组行取 map 净值；未命中行回退毛口径偏差数量。"""
    df = pd.DataFrame([
        _row(),  # 1000001|M001 → 在 map 里
        _row(组件物料描述='物料乙', 流程订单='1000002', 组件物料号='M002',
             材料偏差=30.0, **{'偏差率(%)': 30.0, '数量-实际': 130.0}),
    ])
    sheet = build_sheet3(df, _NOP_PROGRESS)
    mapping = {('1000001', 'M001'): (15.5, 999.0)}
    out = attach_net_qty_column(sheet, mapping)
    assert '净偏差数量' in out.columns
    by_name = out.set_index('物料名称')
    assert float(by_name.loc['物料甲', '净偏差数量']) == 15.5          # 查表命中
    assert float(by_name.loc['物料乙', '净偏差数量']) == 30.0          # 回退毛口径
    # 原帧不被原地修改（缓存线程复用安全）
    assert '净偏差数量' not in sheet.columns


def test_attach_net_qty_fallbacks():
    """空 map / 缺键列 / 空表三条兜底路径：不炸，非空输出恒有净偏差数量列。"""
    df = pd.DataFrame([_row()])
    sheet = build_sheet3(df, _NOP_PROGRESS)

    # ① 空 map → 全部回退毛口径
    out = attach_net_qty_column(sheet, {})
    assert float(out['净偏差数量'].iloc[0]) == 20.0

    # ② 缺键列（如旧版缓存帧）→ 回退毛口径，列仍补上
    no_key = sheet.drop(columns=['_净偏差键'])
    out2 = attach_net_qty_column(no_key, {('1000001', 'M001'): (15.5, 999.0)})
    assert float(out2['净偏差数量'].iloc[0]) == 20.0

    # ③ 空表 → 原样返回
    empty = pd.DataFrame([])
    assert attach_net_qty_column(empty, {}).empty
