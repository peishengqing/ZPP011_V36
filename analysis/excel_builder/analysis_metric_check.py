# -*- coding: utf-8 -*-
"""
analysis_metric_check.py — F01 三表口径自检（v43.325）

业务背景（裴哥 2026-11-09 确认）
------------------------------------
成品工作簿里「总偏差金额」在三张表各出现一次，正常期必须相等（主闭合）。
历史上靠人肉记忆里的金额常量核对，换期就全错（10-04 期与 11-03 期数字
完全不同），且错把「汇总统计正负两列」「替代料明细净偏差金额」当必过项，
导致每期误报 FAIL。

设计铁律
------------------------------------
1. **所有金额按当前工作簿逐列动态重算**，绝不硬编码任何期别的金额常量。
2. **CHECK-1 主闭合是唯一必过项**（容差 0.01）：
   汇总统计.总偏差金额(含税) == 偏差金额分析.总偏差金额(含税)
   == 完整偏差明细.偏差金额。
3. **CHECK-2 / CHECK-3 是 INFO，不算 FAIL**：
   - CHECK-2：完整偏差明细.偏差金额 − 净偏差金额 的抵扣差值，工作簿里
     找不到独立抵扣列时标「需人工核对」，绝不硬判 FAIL、绝不拿
     替代料明细.净偏差金额当代扣额。
   - CHECK-3：分别算 汇总统计 / 偏差金额分析 的「正+负 对 总」残差；
     汇总统计那两列是**已知禁用列**（分析说明原文已写明
     「总偏差金额 ≠ 正偏差金额+负偏差金额」属设计口径），残差非零只提示。
4. 缺表/缺列 → CHECK-1 判 FAIL 并留痕，绝不静默 PASS。
5. 只写数据，不改任何业务数值；表现层交给 post_process 逐表流水线。
6. 幂等：同名 sheet 先删再写。
7. 可被 tests/ 与 tools/pre_push_gate.py **独立调用**（只依赖 openpyxl，
   不依赖 post_process / analyzer 上下文）。
"""
from openpyxl.styles import Font

# ---------------------------------------------------------------- 常量
SHEET_METRIC_CHECK = '口径自检'
_TOL = 0.01

_SUMMARY = '汇总统计'
_ANALYSIS = '偏差金额分析'
_DETAIL = '完整偏差明细'

_C_TOTAL = '总偏差金额(含税)'
_C_POS = '正偏差金额(含税)'
_C_NEG = '负偏差金额(含税)'
_C_DEV = '偏差金额'
_C_NET = '净偏差金额'

# 可能的「独立抵扣列」列名（用于 CHECK-2 判断是否可自动核对）
_DEDUCT_HINTS = ('抵扣', '替代料抵扣', '净额抵扣')


def _to_float(v):
    """单元格值 → float；非数值返回 None（绝不硬猜、绝不当 0 算）。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(',', '')
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _header_row(ws, names, max_scan=10):
    """在前 max_scan 行里找含任一目标列名的表头行。返回 (行号, 列名列表)。

    用 iter_rows(values_only=True) 只读已存在的单元格，绝不 ws.cell() 扫空白格
    （post_process 既有纪律：ws.cell() 会把空单元格实体化）。
    """
    scanned = []
    for row in ws.iter_rows(min_row=1, max_row=min(max_scan, ws.max_row or 1),
                            values_only=True):
        scanned.append(['' if v is None else str(v).strip() for v in row])
    for i, hdr in enumerate(scanned, 1):
        if any(n in hdr for n in names):
            return i, hdr
    return 1, (scanned[0] if scanned else [])


def _col_sum(ws, name):
    """按表头名精确找列并求数据区数值合计。

    返回 (合计, 数值行数)；表或列不存在返回 (None, 0)。
    """
    hr, hdr = _header_row(ws, (name,))
    if name not in hdr:
        return None, 0
    ci = hdr.index(name) + 1
    total = 0.0
    n = 0
    for row in ws.iter_rows(min_row=hr + 1, min_col=ci, max_col=ci,
                            values_only=True):
        v = _to_float(row[0] if row else None)
        if v is not None:
            total += v
            n += 1
    return total, n


def _has_deduct_col(ws):
    """「完整偏差明细」是否存在独立抵扣列（决定 CHECK-2 能否自动核对）。"""
    _hr, hdr = _header_row(ws, _DEDUCT_HINTS)
    return any(any(h in str(h1) for h in _DEDUCT_HINTS) for h1 in hdr)


def _fmt(v):
    return '缺列/缺表' if v is None else ('%.2f' % v)


def check_metric_closure(wb):
    """三表口径自检主函数（纯读、纯算，不写任何 sheet）。

    返回 dict：
      checks          list[dict]（检查项/期望/实测/差值/结论）
      main_closure_ok bool（CHECK-1 是否 PASS）
      fail_count      FAIL 行数
      values          各列实测原始数值（便于测试/门禁断言）
    """
    values = {
        'summary_total': None, 'summary_pos': None, 'summary_neg': None,
        'analysis_total': None, 'analysis_pos': None, 'analysis_neg': None,
        'detail_dev': None, 'detail_net': None,
    }
    missing = []
    for nm in (_SUMMARY, _ANALYSIS, _DETAIL):
        if nm not in wb.sheetnames:
            missing.append(nm)

    if _SUMMARY in wb.sheetnames:
        ws = wb[_SUMMARY]
        values['summary_total'], _ = _col_sum(ws, _C_TOTAL)
        values['summary_pos'], _ = _col_sum(ws, _C_POS)
        values['summary_neg'], _ = _col_sum(ws, _C_NEG)
    if _ANALYSIS in wb.sheetnames:
        ws = wb[_ANALYSIS]
        values['analysis_total'], _ = _col_sum(ws, _C_TOTAL)
        values['analysis_pos'], _ = _col_sum(ws, _C_POS)
        values['analysis_neg'], _ = _col_sum(ws, _C_NEG)
    has_deduct = False
    if _DETAIL in wb.sheetnames:
        ws = wb[_DETAIL]
        values['detail_dev'], _ = _col_sum(ws, _C_DEV)
        values['detail_net'], _ = _col_sum(ws, _C_NET)
        has_deduct = _has_deduct_col(ws)

    v = values
    checks = []

    # ---- CHECK-1（唯一必过项）：三表总偏差金额主闭合 ----
    trio = (v['summary_total'], v['analysis_total'], v['detail_dev'])
    if any(x is None for x in trio):
        spread = None
        c1_ok = False
        diff_txt = '缺表/缺列：%s' % (', '.join(missing) if missing else '列合计不可用')
    else:
        spread = max(trio) - min(trio)
        c1_ok = spread <= _TOL
        diff_txt = '%.2f' % spread
    checks.append({
        '检查项': 'CHECK-1 主闭合（三表总偏差金额）',
        '期望': '汇总统计 = 偏差金额分析 = 完整偏差明细（容差 %.2f）' % _TOL,
        '实测': '汇总 %s ｜ 分析 %s ｜ 明细 %s'
                % (_fmt(v['summary_total']), _fmt(v['analysis_total']),
                   _fmt(v['detail_dev'])),
        '差值': diff_txt,
        '结论': 'PASS' if c1_ok else 'FAIL',
    })

    # ---- CHECK-2（INFO）：净偏差抵扣差额 ----
    if v['detail_dev'] is None or v['detail_net'] is None:
        c2_txt = '缺列/缺表，无法计算'
        c2_diff = '—'
    else:
        c2_diff = '%.2f' % (v['detail_dev'] - v['detail_net'])
        c2_txt = '明细.偏差金额 − 净偏差金额 = %s − (%s)' % (
            _fmt(v['detail_dev']), _fmt(v['detail_net']))
    if has_deduct:
        c2_verdict = 'INFO 存在独立抵扣列，可自动核对'
    else:
        c2_verdict = 'INFO 需人工核对（无独立抵扣列，不拿替代料明细净偏差金额当代扣）'
    checks.append({
        '检查项': 'CHECK-2 净偏差抵扣差额',
        '期望': '仅记录差值，不判 FAIL；找不到独立抵扣列则标「需人工核对」',
        '实测': c2_txt,
        '差值': c2_diff,
        '结论': c2_verdict,
    })

    # ---- CHECK-3（INFO）：正+负 对 总 的残差 ----
    def residual(pos, neg, total):
        if pos is None or neg is None or total is None:
            return None
        r = round((pos + neg) - total, 2)
        # 浮点累加顺序可能因汇总统计重排行而变，残差会出现 -0.0；'%+.2f'
        # 会写成 '-0.00'，与 '+0.00' 字符串不一致而破坏重复 decorate 幂等。
        # 数值上都是 0，统一归一化为 0.0。
        return 0.0 if r == 0 else r

    r_sum = residual(v['summary_pos'], v['summary_neg'], v['summary_total'])
    r_ana = residual(v['analysis_pos'], v['analysis_neg'], v['analysis_total'])
    checks.append({
        '检查项': 'CHECK-3a 汇总统计 正+负 vs 总',
        '期望': '已知禁用列，不闭合属正常（分析说明原文口径）',
        '实测': '%s + (%s) vs %s' % (_fmt(v['summary_pos']),
                                    _fmt(v['summary_neg']),
                                    _fmt(v['summary_total'])),
        '差值': '—' if r_sum is None else ('%+.2f' % r_sum),
        '结论': ('INFO 禁用列已核实不闭合' if r_sum not in (None, 0)
                 else 'INFO 禁用列本期恰好闭合'),
    })
    checks.append({
        '检查项': 'CHECK-3b 偏差金额分析 正+负 vs 总',
        '期望': '正负列对总列闭合',
        '实测': '%s + (%s) vs %s' % (_fmt(v['analysis_pos']),
                                    _fmt(v['analysis_neg']),
                                    _fmt(v['analysis_total'])),
        '差值': '—' if r_ana is None else ('%+.2f' % r_ana),
        '结论': ('PASS 闭合' if r_ana is not None and abs(r_ana) <= _TOL
                 else 'INFO 未闭合，需人工核对'),
    })

    if missing:
        checks.append({
            '检查项': 'CHECK-0 源表完整性',
            '期望': '汇总统计 / 偏差金额分析 / 完整偏差明细 三表齐全',
            '实测': '缺失：%s' % ', '.join(missing),
            '差值': '—',
            '结论': 'FAIL',
        })

    fail_count = sum(1 for c in checks if c['结论'].startswith('FAIL'))
    return {
        'checks': checks,
        'main_closure_ok': c1_ok,
        'fail_count': fail_count,
        'values': values,
    }


def build_metric_check_sheet(wb, alerts=None, guard_infos=None):
    """生成「口径自检」sheet。返回写入数据行数。

    alerts: F06 静默失败哨兵的告警文本列表（可选），追加为 WARN 行。
    guard_infos: F04 输入预检温和提示列表（可选），追加为 INFO 行，
                 让「Data 表缺失 / 订单类型未命中 ZPxx / 列名疑似被改」等
                 放行但需留痕的情况能在导出结果里被看见（v43.329）。
    FAIL 行整行红字。任何一步失败都不抛异常（调用方已包 try），
    但异常必须能被看见 —— 由调用方 print 诊断，本函数不裸吞。
    """
    res = check_metric_closure(wb)
    headers = ['检查项', '期望', '实测', '差值', '结论']
    data = [[c['检查项'], c['期望'], c['实测'], c['差值'], c['结论']]
            for c in res['checks']]
    for msg in (alerts or []):
        data.append(['SENTINEL 静默失败哨兵', '规则应有命中且结论不应全落待确认',
                     msg, '—', 'WARN'])
    for msg in (guard_infos or []):
        data.append(['SOURCE_GUARD 输入预检', '源表为 SAP 生产明细（放行但留痕）',
                     msg, '—', 'INFO'])

    if SHEET_METRIC_CHECK in wb.sheetnames:
        del wb[SHEET_METRIC_CHECK]
    ws = wb.create_sheet(SHEET_METRIC_CHECK)
    ws.append(headers)
    for j in range(1, len(headers) + 1):
        ws.cell(row=1, column=j).font = Font(bold=True, size=11)
    for row in data:
        ws.append(row)
    # FAIL / WARN 行红字（逐行只改「结论」单元格与整行字体，不改任何值）
    for i, row in enumerate(data, 2):
        verdict = str(row[4])
        if verdict.startswith('FAIL') or verdict.startswith('WARN'):
            for j in range(1, len(headers) + 1):
                ws.cell(row=i, column=j).font = Font(
                    bold=True, color='C00000' if verdict.startswith('FAIL')
                    else 'B26A00')
    for col, w in zip('ABCDE', (34, 52, 66, 16, 56)):
        ws.column_dimensions[col].width = w
    return len(data)
