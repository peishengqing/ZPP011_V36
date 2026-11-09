# -*- coding: utf-8 -*-
"""F04 输入数据预检判据回归（v43.329，R1–R6 反证）。

钉死 v43.325 的判据退化：当时写成「三核心列一个都没有才拒」，
实测带 1 列 / 2 列的错表会直接放行。本测试用真实 validate_source 反证，
旧逻辑下 R2/R3 必然失败。

同时覆盖：订单类型全表扫描、Data 表缺失容错、温和提示收集器接到 F01 sheet。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from core.source_guard import (  # noqa: E402
    validate_source, collect_warnings, reset_warnings, _CORE_COLS,
)
from analysis.excel_builder.analysis_metric_check import (  # noqa: E402
    build_metric_check_sheet, SHEET_METRIC_CHECK,
)


def _make(path, headers, rows=None, sheet='Data'):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for r in (rows or []):
        ws.append(r)
    wb.save(path)
    wb.close()  # Windows 下必须显式释放句柄，否则临时目录清理报 WinError 32
    return path


# ---------------------------------------------------------------- R1–R4 判据反证
def test_r1_no_core_col_rejected(tmp_path):
    """R1：三列全无（典型 ZMM062 收发存表）→ 硬拒绝且点名。"""
    p = _make(str(tmp_path / 'zmm.xlsx'),
              ['公司代码', '库存地点', '结束数量'], [[1, 2, 3]])
    with pytest.raises(ValueError) as e:
        validate_source(p)
    assert 'ZMM062' in str(e.value)
    assert all(c in str(e.value) for c in _CORE_COLS)


@pytest.mark.parametrize('headers', [
    ['流程订单', '库存地点', '结束数量'],                       # R2：仅 1 列
    ['流程订单', '组件物料类型', '结束数量'],                   # R3a：仅 2 列
    ['流程订单', '数量-实际', '结束数量'],                      # R3b：仅 2 列
    ['组件物料类型', '数量-实际', '结束数量'],                  # R3c：仅 2 列
])
def test_r2_r3_partial_core_cols_rejected(tmp_path, headers):
    """R2/R3：只带 1~2 个核心列也必须硬拒绝（旧退化逻辑会放行 → 反证）。"""
    p = _make(str(tmp_path / 'partial.xlsx'), headers,
              [[1] * len(headers)])
    with pytest.raises(ValueError) as e:
        validate_source(p)
    assert 'ZMM062' in str(e.value)


def test_r4_all_core_cols_pass(tmp_path):
    """R4：三列齐全 → 放行，返回核心列命中 3/3。"""
    p = _make(str(tmp_path / 'real.xlsx'),
              list(_CORE_COLS) + ['订单类型'],
              [['A', 'Z002', 10, 'ZP01']])
    r = validate_source(p)
    assert r['core_hit'] == 3
    assert r['zp_hit'] == 'ZP01'


# ---------------------------------------------------------------- R5 全表扫描
def test_r5_order_type_scanned_whole_table(tmp_path):
    """R5：ZPFX 出现在第 250 行之后仍须命中（旧版只扫前 200 行会漏）。"""
    hdr = list(_CORE_COLS) + ['订单类型']
    # 前 250 行订单类型为空（不构成 ZPxx 命中），唯一的 ZPFX 放在第 251 行：
    # 旧版只扫前 200 行时 zp_hit 恒为 None，全表扫描才会命中 ZPFX。
    rows = [['A', 'Z002', 1, ''] for _ in range(250)]
    rows.append(['B', 'Z002', 1, 'ZPFX'])
    p = _make(str(tmp_path / 'late.xlsx'), hdr, rows)
    r = validate_source(p)
    assert r['zp_hit'] == 'ZPFX', '订单类型必须全表扫描，不能只扫前 200 行'


# ---------------------------------------------------------------- R6 容错 + 收集器
def test_r6_missing_data_sheet_warns_but_passes(tmp_path):
    """R6：缺 Data 表沿用旧容错取第一张表，放行但留痕（不阻断）。"""
    p = _make(str(tmp_path / 'sheet1.xlsx'),
              list(_CORE_COLS), [['A', 'Z002', 1]], sheet='Sheet1')
    r = validate_source(p)
    assert r['sheet'] == 'Sheet1'
    warns = collect_warnings()
    assert any('Data' in w and '工作表' in w for w in warns), warns


def test_warnings_reset_per_call(tmp_path):
    """收集器按轮清空，不跨文件累积。"""
    a = _make(str(tmp_path / 'a.xlsx'), list(_CORE_COLS),
              [['A', 'Z002', 1]], sheet='Sheet1')
    b = _make(str(tmp_path / 'b.xlsx'),
              list(_CORE_COLS) + ['订单类型'], [['A', 'Z002', 1, 'ZP01']])
    validate_source(a)
    assert collect_warnings()
    validate_source(b)
    assert collect_warnings() == [], '第二轮预检应清空上一轮告警'


def test_guard_infos_written_into_metric_check_sheet():
    """F01「口径自检」sheet 必须出现 SOURCE_GUARD 的 INFO 行。"""
    reset_warnings()
    wb = Workbook()
    a = wb.active
    a.title = '汇总统计'
    a.append(['总偏差金额(含税)'])
    a.append([100.0])
    wb.create_sheet('偏差金额分析').append(['总偏差金额(含税)', 100.0])
    wb.create_sheet('完整偏差明细').append(['偏差金额', 100.0])
    n = build_metric_check_sheet(wb, alerts=[], guard_infos=['[source_guard] 测试留痕'])
    ws = wb[SHEET_METRIC_CHECK]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    info_rows = [r for r in rows[1:] if r[0] == 'SOURCE_GUARD 输入预检']
    assert len(info_rows) == 1
    assert info_rows[0][2] == '[source_guard] 测试留痕'
    assert info_rows[0][4] == 'INFO'
    assert n == len(rows) - 1
