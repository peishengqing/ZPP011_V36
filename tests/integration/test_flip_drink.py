# -*- coding: utf-8 -*-
"""
F02 真表回归黄金集（v43.325）

数据：tests/fixtures/golden/_drink9_zpp011_wx.xlsx —— 9 月微信版完整
ZPP011 源表（Data sheet 1179 数据行 / 27 列，ZPFX 6 行 1 单，订单 500004300）。
这是唯一可用的饮料真表；桌面「9月报表用数据/」那份是裁剪版（ZPFX 只剩 2 行），不用。

用例全部带「回滚修复即失败」的反证说明：每条断言对应的实现一旦被回退或
改错口径，该用例立即失败，防止「改了实现但测试还绿」的假回归。

测试自包含：从真表读 ZPFX 行 → 按成品工作簿「完整偏差明细」的真实列名
映射成最小成品 wb → 走 build_flip_sheets（完整入口，经 _scan_flip_source），
不依赖外部临时产物、不跑 analyzer 全流程（快、可重复）。
"""
import os

import openpyxl

from analysis.excel_builder.analysis_extra_flip import (
    build_flip_sheets, split_by_factory,
    SHEET_DRINK_CHECK, SHEET_DRINK_DETAIL, _FAC_DRINK,
)
from analysis.excel_builder.analysis_metric_check import check_metric_closure

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, '..', 'fixtures', 'golden', '_drink9_zpp011_wx.xlsx')

# 成品工作簿「完整偏差明细」列名（_scan_flip_source 读的就是这些）
DETAIL_HEADERS = ['订单日期', '流程订单', '工厂', '车间', '订单类型',
                  '产品物料号码', '产品物料描述', '物料编码', '物料名称',
                  '组件物料类型', '组件物料类型描述', '单位', '实际',
                  '产量', '产量单位', '备注']
# 微信版源表列名 → 成品工作簿列名（注意「数量-实际」带连字符）
SRC_MAP = {
    '订单日期': '订单开始日期',
    '流程订单': '流程订单',
    '工厂': '工厂名称',                 # 成品工作簿是中文厂名
    '车间': '生产管理员描述',
    '订单类型': '订单类型',
    '产品物料号码': '产品物料号码',
    '产品物料描述': '产品物料描述',
    '物料编码': '组件物料号',
    '物料名称': '组件物料描述',
    '组件物料类型': '组件物料类型',
    '组件物料类型描述': '组件物料类型描述',
    '单位': '组件单位',
    '实际': '数量-实际',
    '产量': '产量',
    '产量单位': '产量单位',
    '备注': '备注原因',
}


def _load_zpfx_rows():
    """从 golden 真表读全部 ZPFX 行，映射成「完整偏差明细」列名字典。"""
    assert os.path.isfile(GOLDEN), '黄金集真表缺失: %s' % GOLDEN
    wb = openpyxl.load_workbook(GOLDEN, read_only=True, data_only=True)
    assert 'Data' in wb.sheetnames
    ws = wb['Data']
    it = ws.iter_rows(values_only=True)
    hdr = ['' if v is None else str(v).strip() for v in next(it)]
    idx = {h: i for i, h in enumerate(hdr) if h}
    out = []
    for row in it:
        ot = row[idx['订单类型']] if '订单类型' in idx else None
        if 'ZPFX' not in str(ot or '').upper():
            continue
        rec = {}
        for dh, src in SRC_MAP.items():
            j = idx.get(src)
            rec[dh] = row[j] if j is not None and j < len(row) else ''
        out.append(rec)
    wb.close()
    return out


def _build_wb(rows):
    """构造只含「完整偏差明细」的最小成品 wb（列名与真实成品一致）。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '完整偏差明细'
    ws.append(DETAIL_HEADERS)
    for r in rows:
        ws.append([r.get(h, '') for h in DETAIL_HEADERS])
    return wb


def _main_row(wb):
    ws = wb[SHEET_DRINK_CHECK]
    hdr = [c.value for c in ws[1]]
    vals = [c.value for c in ws[2]]
    return dict(zip(hdr, vals))


def _minimal_metric_wb(total=-1000.0):
    """F01 用最小三表 wb（数值自造，绝不硬编码任何期别金额常量）。"""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    s = wb.create_sheet('汇总统计')
    s.append(['序号', '工厂', '正偏差金额(含税)', '负偏差金额(含税)',
              '总偏差金额(含税)'])
    s.append([1, '1101', 300.0, -1300.0, total])
    a = wb.create_sheet('偏差金额分析')
    a.append(['物料编码', '正偏差金额(含税)', '负偏差金额(含税)',
              '总偏差金额(含税)'])
    a.append(['X', 200.0, -1200.0, total])
    d = wb.create_sheet('完整偏差明细')
    d.append(['流程订单', '偏差金额', '净偏差金额'])
    d.append(['PO1', total * 0.6, total * 0.6 - 50.0])
    d.append(['PO2', total * 0.4, total * 0.4 - 50.0])
    return wb


# ---------------------------------------------------------------- 用例
def test_golden_zpfx_extraction_and_factory_split():
    """回滚修复即失败：若 split_by_factory 把中文厂名当未知厂，或 ZPFX 提取漏行，
    本例（6 行 / 1101=0、1102=6、未知=0）立即失败。"""
    rows = _load_zpfx_rows()
    assert len(rows) == 6, '真表 ZPFX 应为 6 行'
    assert all(str(r['订单类型']).upper() == 'ZPFX' for r in rows)
    assert all(r['工厂'] in _FAC_DRINK for r in rows)
    assert len({str(r['流程订单']) for r in rows}) == 1, '饮料 ZPFX 应 1 单'
    assert str(rows[0]['流程订单']) == '500004300'
    food, drink, unknown = split_by_factory(
        [{'fac': r['工厂']} for r in rows])
    assert (len(food), len(drink), len(unknown)) == (0, 6, 0)


def test_golden_conserved_7125():
    """① 真单：产出 475 件 × 15 瓶 = 7125.0，投入 Z008 475 件 × 15 瓶 = 7125.0，
    差 0.0 → 守恒/正常。

    回滚修复即失败：若把 _drink_container_of 的「只认 Z008 成品、实际>0」主判据
    去掉（改回按件数比、或把 Z005 半成品也算投入），7125/7125 与差 0 立即不成立。
    """
    wb = _build_wb(_load_zpfx_rows())
    res = build_flip_sheets(wb)
    assert SHEET_DRINK_CHECK in res and res[SHEET_DRINK_CHECK] == 1
    assert SHEET_DRINK_DETAIL in res and res[SHEET_DRINK_DETAIL] == 6
    row = _main_row(wb)
    assert str(row['流程订单']) == '500004300'
    assert float(row['产量(件)']) == 475.0
    assert float(row['单件容器数']) == 15.0
    assert float(row['产出总容器数']) == 7125.0
    assert float(row['投入总容器数']) == 7125.0
    assert float(row['差额容器数']) == 0.0
    assert row['结论'] == '守恒/正常'


def test_golden_underfill_400_detected():
    """② 反证 A：Z008 投入改 400 件 → 投入 6000.0、差 +1125.0 → 疑似漏记。

    回滚修复即失败：若把差>0 判成「守恒/正常」，或不再按「实际件数 × 单件容器数」
    累加投入，+1125 与「疑似漏记」立即不成立。
    """
    rows = _load_zpfx_rows()
    hit = 0
    for r in rows:
        if str(r['组件物料类型']).upper() == 'Z008':
            r['实际'] = 400
            hit += 1
    assert hit == 1
    wb = _build_wb(rows)
    build_flip_sheets(wb)
    row = _main_row(wb)
    assert float(row['投入总容器数']) == 6000.0
    assert float(row['差额容器数']) == 1125.0
    assert row['结论'] == '疑似漏记'


def test_golden_only_z005_stays_unresolved():
    """③ 反证 B：只留 Z005 半成品（实际 0、备注「翻箱订单，未使用」）→
    投入 0.0、待人工确认，绝不硬判漏记。

    回滚修复即失败：若把 Z005 半成品误当有效成品耗用、或把「投入侧无有效成品
    耗用行」硬判成漏记，本例（结论必须是待人工确认）立即失败。
    """
    rows = [r for r in _load_zpfx_rows()
            if str(r['组件物料类型']).upper() == 'Z005']
    assert rows, '真表应含 Z005 半成品行'
    assert all(float(r['实际']) == 0 and '未使用' in str(r['备注'])
               for r in rows)
    wb = _build_wb(rows)
    build_flip_sheets(wb)
    row = _main_row(wb)
    assert float(row['投入总容器数']) == 0.0
    assert row['结论'] == '待人工确认'
    assert row['结论'] != '疑似漏记'


def test_factory_code_1102_also_routes_to_drink():
    """工厂码 1102（源表形态）与中文厂名（成品工作簿形态）两套都认。

    回滚修复即失败：若 split_by_factory 只认中文厂名、丢掉 1102 码，
    本例饮料主表不会生成。
    """
    rows = _load_zpfx_rows()
    for r in rows:
        r['工厂'] = '1102'
    wb = _build_wb(rows)
    build_flip_sheets(wb)
    assert SHEET_DRINK_CHECK in wb.sheetnames
    assert _main_row(wb)['结论'] == '守恒/正常'


def test_metric_closure_pass_and_counterproof():
    """④ F01 闭合断言 + 回滚修复即失败：改一个数必须出 FAIL。

    回滚修复即失败：若 check_metric_closure 把三表合计比对改成恒 True，
    改数后的 main_closure_ok 就不会变 False。
    """
    wb = _minimal_metric_wb()
    res = check_metric_closure(wb)
    assert res['main_closure_ok'] is True
    assert res['fail_count'] == 0
    assert abs(res['values']['summary_total'] - (-1000.0)) < 0.01

    wb2 = _minimal_metric_wb()
    ws = wb2['汇总统计']
    hdr = [c.value for c in ws[1]]
    ci = hdr.index('总偏差金额(含税)') + 1
    ws.cell(row=2, column=ci).value = -999.0   # 人为改一格
    res2 = check_metric_closure(wb2)
    assert res2['main_closure_ok'] is False
    assert res2['fail_count'] >= 1
