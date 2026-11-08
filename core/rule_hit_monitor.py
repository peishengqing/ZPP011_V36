# -*- coding: utf-8 -*-
"""
core/rule_hit_monitor.py — F06 静默失败哨兵（v43.325）

背景
------------------------------------
规则型分析最危险的失败不是报错，而是**静默成功**：源表被换、过滤条件写错、
解析器退化 → 规则命中 0 行、或所有结论 100% 落「待人工确认」，报表照常导出，
看不出任何异常。F06 收集每条规则本期命中行数与结论分布，命中 0 行或结论
全落待确认时，在 F01「口径自检」sheet 出 WARN 告警行（也可供
health_check_dialog._run_checks 读取）。

设计铁律
------------------------------------
1. **纯收集器**：只记录，不改任何业务计算、不改任何工作表数值。
2. 埋点只加 1-2 行（规则调用处），计算逻辑零改动。
3. `collect_alerts()` 返回告警文本列表，由 F01 建表时追加为 WARN 行。
4. 禁裸 `except Exception: pass`；读结论列失败要 traceback.print_exc() 留痕。
5. 幂等：`record_hit` 按规则名覆盖，不累加；`reset()` 供测试隔离。
"""
import traceback

# rule_name -> {'hit_rows': int, 'verdicts': list[str]}
_HITS = {}


def _read_verdicts(wb, sheet_names):
    """从已生成的表读「结论」列（纯读 iter_rows，绝不 ws.cell 扫空白格）。"""
    out = []
    for nm in sheet_names:
        if nm not in wb.sheetnames:
            continue
        ws = wb[nm]
        hdr = [c.value for c in ws[1]]
        if '结论' not in hdr:
            continue
        ci = hdr.index('结论')
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) > ci and row[ci] not in (None, ''):
                out.append(str(row[ci]))
    return out


def record_hit(rule_name, hit_rows, verdicts=None, wb=None, check_sheets=()):
    """记录一条规则本期命中行数与结论分布（按规则名覆盖，不累加）。

    verdicts 可直接传；未传时若给了 wb + check_sheets，则从已生成表读「结论」列。
    """
    if verdicts is None and wb is not None:
        try:
            verdicts = _read_verdicts(wb, check_sheets)
        except Exception:
            traceback.print_exc()
            verdicts = []
    _HITS[rule_name] = {
        'hit_rows': int(hit_rows or 0),
        'verdicts': list(verdicts or []),
    }
    return dict(_HITS[rule_name])


def collect_alerts():
    """返回告警文本列表：命中 0 行 / 结论 100% 落待确认。"""
    alerts = []
    for name, info in sorted(_HITS.items()):
        n = info['hit_rows']
        vs = info['verdicts']
        if n <= 0:
            alerts.append(
                '规则「%s」本期命中 0 行（疑似静默失败，请核查源表与过滤条件）'
                % name)
        if vs and all(('待人工确认' in v or '待确认' in v) for v in vs):
            alerts.append(
                '规则「%s」本期 %d 单结论 100%% 落待确认（疑似静默失败）'
                % (name, len(vs)))
    return alerts


def reset():
    """清空收集器（测试隔离用；生产链路不调用，保证告警可读回）。"""
    _HITS.clear()


def snapshot():
    return {k: {'hit_rows': v['hit_rows'], 'verdicts': list(v['verdicts'])}
            for k, v in _HITS.items()}
