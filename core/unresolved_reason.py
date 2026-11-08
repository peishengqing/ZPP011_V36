# -*- coding: utf-8 -*-
"""
core/unresolved_reason.py — F05 未判定原因码（v43.325）

背景
------------------------------------
v43.324 的 check_drink_order() 已经有 `why` 自由文本字段：
  '产出规格解析失败'
  '投入侧无有效成品耗用行（Z008 且 实际>0）'
  '投入组件规格解析失败（单位/容器数不明）'
  '存在容器形式/单位不一致的投入行'
并已写进饮料主表「备注」列。F05 的任务**不是造新字段**，而是把这些自由文本
**规范化成四类枚举码**，从而能按「系统健康度 / 人工队列」分派。

设计铁律
------------------------------------
1. `classify()` 是**唯一判别来源**：主表侧（按单 verdict/why）与明细侧
   （组件排除原因）都调同一个函数，杜绝两套口径。
2. 前三类归「系统健康度」（规则/解析器该修），最后一类归「人工队列」。
3. **不改饮料主表 17 列 / 明细 16 列契约，也不改两张食品表**：分布用独立
   sheet「未判定原因分布」承载（零列契约变动）。
4. 幂等：同名 sheet 先删再写。
5. 只统计、不改任何业务数值；任何异常都不裸吞（调用方已包 try + 诊断）。
"""
from openpyxl.styles import Font

SHEET_UNRESOLVED = '未判定原因分布'
DETAIL_SHEET = '饮料翻箱组件明细'

# 四类枚举码 → (中文类别, 归属队列, 说明)
CODES = {
    'SPEC_PARSE_FAIL': (
        '规格解析失败', '系统健康度',
        '产出/投入规格解析不出单位或容器数（parse_pack 返回 None）'),
    'NO_VALID_INPUT': (
        '投入侧无有效成品耗用行', '系统健康度',
        'Z008 成品且实际>0 的投入行不存在（如只剩 Z005 半成品）'),
    'CROSS_CONTAINER': (
        '跨容器形式', '系统健康度',
        '容器形式或净含量单位不一致（瓶装 vs 罐装、ml vs g）'),
    'BUSINESS_REVIEW': (
        '业务待核', '人工队列',
        '其余待人工确认原因，以及组件级正常排除（包材/半成品等）'),
}
_CODE_ORDER = ('SPEC_PARSE_FAIL', 'NO_VALID_INPUT', 'CROSS_CONTAINER',
               'BUSINESS_REVIEW')


def classify(why):
    """单一判别来源：把 why 自由文本 / 组件排除原因 映射到四类枚举码。

    关键词优先级：解析失败 > 无有效耗用 > 跨形式/不一致 > 其余。
    任何无法识别的文本一律归 BUSINESS_REVIEW（人工队列），绝不硬猜。
    """
    s = str(why or '')
    if '解析失败' in s or '规格' in s:
        return 'SPEC_PARSE_FAIL'
    if '无有效成品耗用' in s or '投入侧' in s:
        return 'NO_VALID_INPUT'
    if '不一致' in s or '容器形式' in s or '跨容器' in s:
        return 'CROSS_CONTAINER'
    return 'BUSINESS_REVIEW'


def _safe_log(log_cb, msg, level="info"):
    """log_cb 三层兜底（与 core/ppt_trae.py 同款），绝不因日志崩掉主流程。"""
    if not log_cb:
        return
    try:
        log_cb(msg, level)
        return
    except TypeError:
        pass
    except Exception:
        return
    try:
        log_cb(msg)
    except Exception:
        pass


def distribution_counts(wb, order_results):
    """统计各原因码的主表待确认单数与组件排除行数（纯读、纯算）。

    order_results: list[dict]，每项含 verdict / why（来自 check_drink_order）。
    返回 {code: {'orders': n, 'details': n}}。
    """
    counts = {c: {'orders': 0, 'details': 0} for c in _CODE_ORDER}

    # 主表侧：只统计「待人工确认」单，自由文本 → 码走单一 classify()。
    # check_drink_order 返回的是 `reason` 键（局部变量名才是 why），
    # 兼容两种写法，绝不因键名取错把系统未判定错分到人工队列。
    for res in (order_results or []):
        if str(res.get('verdict')) != '待人工确认':
            continue
        why = res.get('reason')
        if why is None:
            why = res.get('why')
        counts[classify(why)]['orders'] += 1

    # 明细侧：从已生成的「饮料翻箱组件明细」读「排除原因」，同一 classify()
    if DETAIL_SHEET in wb.sheetnames:
        ws = wb[DETAIL_SHEET]
        hdr = [c.value for c in ws[1]]
        if '是否计入容器数' in hdr and '排除原因' in hdr:
            i_flag = hdr.index('是否计入容器数')
            i_reason = hdr.index('排除原因')
            for row in ws.iter_rows(min_row=2, values_only=True):
                if len(row) > max(i_flag, i_reason) \
                        and row[i_flag] == '否':
                    counts[classify(row[i_reason])]['details'] += 1
    return counts


def system_unresolved_total(counts):
    """系统未判定数 = 前三类（系统健康度）的主表待确认单数之和。

    F05 验收反证：把 parse_pack 临时改成恒返 None，该数字必须上升。
    """
    return sum(counts[c]['orders'] for c in _CODE_ORDER
               if CODES[c][1] == '系统健康度')


def build_distribution_sheet(wb, order_results, log_cb=None):
    """生成「未判定原因分布」sheet。返回写入数据行数。"""
    counts = distribution_counts(wb, order_results)
    headers = ['原因码', '原因类别', '归属队列', '主表待确认单数',
               '组件排除行数', '说明']
    data = []
    for code in _CODE_ORDER:
        name, queue, desc = CODES[code]
        data.append([code, name, queue,
                     counts[code]['orders'], counts[code]['details'], desc])

    if SHEET_UNRESOLVED in wb.sheetnames:
        del wb[SHEET_UNRESOLVED]
    ws = wb.create_sheet(SHEET_UNRESOLVED)
    ws.append(headers)
    for j in range(1, len(headers) + 1):
        ws.cell(row=1, column=j).font = Font(bold=True, size=11)
    for row in data:
        ws.append(row)
    # 系统健康度三类高亮（橙），人工队列保持默认
    for i, row in enumerate(data, 2):
        if row[2] == '系统健康度' and row[3]:
            ws.cell(row=i, column=4).font = Font(bold=True, color='B26A00')
    for col, w in zip('ABCDEF', (22, 24, 14, 18, 16, 62)):
        ws.column_dimensions[col].width = w
    _safe_log(log_cb,
              '[unresolved_reason] 分布已生成，系统未判定单数=%d'
              % system_unresolved_total(counts), 'info')
    return len(data)
