# -*- coding: utf-8 -*-
"""
post_process.py — 导出后处理：表现层美化 + 安全类型规范化（v43.120）

挂载点
------
analysis/analyzer.py :: export_full_report_from_intermediates()
在 `_apply_warning_colors(wb)` 之后、`wb.save(final_output_path)` 之前调用：

    from analysis.excel_builder.post_process import decorate_workbook
    decorate_workbook(wb)

设计约束（务必遵守，改本文件前先读）
------------------------------------
1. **只做「表现层 + 类型规范化」**：不改任何数值、不碰计算逻辑、不删任何行；
2. **每项独立 try 捕获**：单点失败只记日志，绝不让美化把整个导出搞崩；
3. **幂等**：重复调用不产生副作用（不会重复加列、重复加图）；
4. **绝不调用 ws.cell() 去「扫」空白格**：openpyxl 的 ws.cell(row,col) 对不存在的位置
   会按需创建单元格，大表全量扫描会把空单元格实体化（17K×34 约 60 万格），
   直接把文件体积与保存耗时干上去。本模块一律通过 `_cells_of(ws)`（内部真实
   单元格映射）遍历，只处理**已存在**的单元格；
5. **不重复全表扫描**：每张表只解析一次表头、只算一次有效末行，结果在各步骤间复用；
6. 可用环境变量 `ZPP011_SKIP_POST_PROCESS=1` 一键跳过（出问题时的逃生开关）。

刻意**未**做的事（留待业务确认，别擅自补上）
--------------------------------------------
- **删行去重**：无备注预警 35 行 / 中间地带明细 10 行 / 替代料明细 7 行为整行重复。
  本模块只**标记**（`重复行` 列）不删 —— 删行会改报表合计，属业务口径变更，
  且根因大概率在上游取数/关联，应在源端修，出口兜底只会把上游 bug 遮得更深。
- **G/KG 数值静默折算**：单位列 G 与 KG 并存（G 55 行）有 1000 倍量纲风险，
  但静默 ×0.001 会把源数据单位错误改得更难查 —— 故只**标记**不改数。
- **替代料明细「偏差率A/B」量纲折算**：这两列是原始数值（209.523 / 100 / -0.027），
  究竟是「百分数」还是「倍数」尚未经业务确认 —— 不做任何折算，只由条件格式按
  数值口径（阈值 100）标红。口径一旦确认再回来改。

已知数据事实（实测，避免后人踩坑）
----------------------------------
- **偏差率 ±100.0% 是钳位标记值**：定额=0 → 恒 +100.0%（2390 行）；实际=0 → 恒
  -100.0%（246 行），合计 2636 行，均已由「系统无定额」「实际为零」标签覆盖。
  因此越界判定必须用严格 `> 100`，用 `>= 100` 会多刷 2636 个重复标签。
- **「标签次数 ≠ 行数」**：本份数据 2895 = 标签出现次数（2392+248+200+55），
  实际打标行数 2893（有 2 行同时挂两个标签）。对比数字时先确认比的是哪个口径。
- **汇总统计勾稽**：该表「总条数/总偏差金额(含税)」只统计异常记录、偏差为 0 的不进表，
  所以「正+负 ≠ 总」是**设计如此**，不是勾稽错误 —— 不要在此表做勾稽检查或重算。
"""
import os
import re
from copy import copy

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.formatting.rule import CellIsRule, FormulaRule


# ---------------------------------------------------------------- 列名关键词

# 标识类字段：必须按文本存放，否则长编码会被当数字截断/丢前导零
_TEXT_ID_KEYS = (
    '流程订单', '原表行号', '物料编码', '产品物料号码', '订单号',
    '物料A编码', '物料B编码',
)
# 日期字段
_DATE_KEYS = ('订单日期', '订单开始日期')
# 金额字段（千分位）
_AMOUNT_KEYS = ('金额',)
# 数量/条数字段
_COUNT_KEYS = ('条数', '总数量', '数量', '定额', '实际',
               # v43.252：以下四列是**数量**口径，但列名不含上面任一关键词，
               # 导致 number_format 全是 General（表里显示裸值）：
               #   多耗 / 少耗   —— 偏差原因分析里的正/负偏差数量合计
               #   偏差A / 偏差B —— 替代料明细里 A/B 两料各自的偏差数量
               # ⚠️ '偏差A' 不会误伤 '偏差率A'（'偏差率A' 里 '率' 夹在中间，
               #    不是子串）；'偏差率A' 仍归比率小数类。
               '多耗', '少耗', '偏差A', '偏差B')

# 比率字段（这些列在源表里是文本 '19.60%'，需转真数值）
_RATIO_KEYS = ('率', '占比')

# ---------------------------------------------------------------- 百分点数值列
#
# 「百分点数值」与「比率小数」是**两种不同的存储形态**，数字格式必须分开：
#   比率小数  = 0.143  表示 14.3%  → 套 0.00%    （显示 14.30%）
#   百分点数值 = 14.57  表示 14.57% → 套 0.00"%"  （显示 14.57%）
# 套错就是 100 倍误差：
#   · 百分点列套 0.00%   → 14.57 显示成 1457.00%
#   · 比率小数列套 0.00"%" → 0.143 显示成 0.14%
#
# ⚠️ **绝不能靠「值是否 > 1」判断形态**：比率小数的值域是 (−∞,+∞)，
#    真实超耗 240% 就是 2.4060、673% 就是 6.736（实测），用它判定会把
#    240.60% 误判成百分点而显示成 2.41%。**只能靠列名语义**。
# 判据：列名以 '%' 结尾 → 百分点数值列（当前工作簿里只有「占车间偏差比%」）。
_FMT_PCT_POINT = '0.00"%"'

_FMT_DATE = 'yyyy-mm-dd'
_FMT_AMOUNT = '#,##0.00'
_FMT_COUNT = '#,##0.###'
_FMT_COUNT_INT = '#,##0'
_FMT_RATIO = '0.00%'


def _log(msg):
    try:
        from analysis.debug_util import dprint
        dprint(msg)
    except Exception:
        pass


def _is_skipped():
    v = str(os.environ.get('ZPP011_SKIP_POST_PROCESS', '') or '').strip().lower()
    return v in ('1', 'true', 'yes', 'on')


# ---------------------------------------------------------------- 基础工具

def _cells_of(ws):
    """openpyxl 内部 {(row, col): Cell} 映射，**只含真实存在**的单元格。

    用它代替 ws.cell() 遍历是刻意的性能取舍：ws.cell() 对空位置会按需创建，
    全表扫描会把空单元格实体化，文件体积与保存耗时都会涨。
    """
    return getattr(ws, '_cells', None) or {}


def _header_info(ws):
    """返回 (表头行号, {列号: 表头文本})。

    兼容两种版式：
      - 常规：第 1 行即表头；
      - 标题行版式（如「偏差原因汇总」）：第 1 行只有 1 个非空格（大标题），
        第 2 行才是表头。
    """
    map_ = _cells_of(ws)
    if not map_:
        return 1, {}

    def _nonempty_in_row(r):
        return {c: cell.value for (rr, c), cell in map_.items()
                if rr == r and cell.value not in (None, '')}

    r1 = _nonempty_in_row(1)
    hdr_row = 1
    if len(r1) <= 1:
        r2 = _nonempty_in_row(2)
        if len(r2) > len(r1):
            hdr_row = 2

    max_col = ws.max_column
    headers = {}
    for i in range(1, max_col + 1):
        cell = map_.get((hdr_row, i))
        if cell is None:
            headers[i] = ''
        else:
            v = cell.value
            headers[i] = '' if v is None else str(v).strip()
    return hdr_row, headers


def _find_col(headers, *names):
    """按表头名找列号（精确匹配优先，其次子串）。找不到返回 None。"""
    for want in names:
        for col, name in headers.items():
            if name == want:
                return col
    for want in names:
        for col, name in headers.items():
            if want and want in name:
                return col
    return None


def _last_data_row(ws, hdr_row):
    """有效末行：从 ws.max_row 向上找到第一行有内容的行。

    只探尾部有限行、只读少量列，避免整表扫描；同时把 openpyxl 维护的
    「历史包围边界」（删行后不缩，例如无备注预警会虚报 599 行）修掉，
    否则自动筛选的箭头会拖到一片空白行上。
    """
    mr = ws.max_row
    if mr <= hdr_row:
        return mr
    map_ = _cells_of(ws)
    probe_cols = range(1, min(ws.max_column, 8) + 1)
    scanned = 0
    for r in range(mr, hdr_row, -1):
        if any((map_.get((r, c)) is not None and map_[(r, c)].value not in (None, ''))
               for c in probe_cols):
            return r
        scanned += 1
        if scanned > 2000:   # 防御：尾部异常大面积空白时不无限回溯
            break
    return hdr_row


def _row2_merged(ws):
    """第 2 行是否存在横跨多列的合并单元格（说明行/图例行版式特征）。"""
    try:
        for rng in ws.merged_cells.ranges:
            if rng.min_row == 2 and rng.max_col - rng.min_col >= 2:
                return True
    except Exception:
        pass
    return False


def _num(v):
    """宽容取数：'' / '-' / '19.6%' / 数字 都能读；读不出来返回 None。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == '' or s in ('-', '—'):
        return None
    if s.endswith('%'):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------- 表现层

def _apply_layout(ws, hdr_row, last_row):
    """冻结表头 + 自动筛选 + 补齐缺失列宽。"""
    # 冻结：表头行下面一行
    if not ws.freeze_panes:
        ws.freeze_panes = 'A%d' % (hdr_row + 1)

    # 自动筛选：说明行版式（第 2 行合并）跳过，否则会把说明行当数据行，很难看
    if not _row2_merged(ws) and last_row > hdr_row:
        if not ws.auto_filter.ref:
            ws.auto_filter.ref = 'A%d:%s%d' % (
                hdr_row, get_column_letter(ws.max_column), last_row)

    # 列宽：只补「没设过」的列，已设过的一律不动（尊重 builder 的排版决策）
    map_ = _cells_of(ws)
    for i in range(1, ws.max_column + 1):
        letter = get_column_letter(i)
        dim = ws.column_dimensions.get(letter)
        if dim is not None and dim.width:
            continue
        hc = map_.get((hdr_row, i))
        w = (len(str(hc.value)) * 2 + 2) if (hc is not None and hc.value) else 8
        # 抽样估宽：只看前 60 行真实存在的单元格
        for r in range(hdr_row + 1, min(last_row, hdr_row + 60) + 1):
            c = map_.get((r, i))
            if c is not None and c.value is not None:
                w = max(w, len(str(c.value)) * 1.1 + 2)
        ws.column_dimensions[letter].width = max(8.0, min(42.0, round(w, 1)))


def _count_fmt(v):
    """数量列按**单元格实际值**选格式，绝不能整列共用一个格式串。

    坑（裴哥 2026-10-02 截图实测）：Excel 格式串里的小数点是写死的 '.'，
    没有小数它也会显示出来 —— '#,##0.###' 下 294 显示成 '294.'、0 显示成 '0.'，
    整列都拖个尾巴。原始导出是 General（干净），是后处理把它改坏的。
    故：整数值给 '#,##0'，带小数才给 '#,##0.###'（千分位保留）。
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return _FMT_COUNT
    return _FMT_COUNT_INT if float(v).is_integer() else _FMT_COUNT


def _is_pct_point_col(name):
    """列名是否「以 % 结尾」的百分点数值列（值本身已是百分数的数值部分）。"""
    return isinstance(name, str) and name.strip().endswith('%')


def _col_max_abs(ws, hdr_row, last_row, col, sample=200):
    """采样某列非空数值的最大绝对值（判定百分比列的存储形态时用）。"""
    map_ = _cells_of(ws)
    mx = 0.0
    for r in range(hdr_row + 1, min(last_row, hdr_row + sample) + 1):
        c = map_.get((r, col))
        if c is None:
            continue
        v = c.value
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        a = abs(float(v))
        if a > mx:
            mx = a
    return mx


def _apply_number_formats(ws, hdr_row, headers, last_row):
    """按列名套数字格式。只改 number_format，保留字体/填充/边框等其它样式。

    金额/日期整列一个格式没问题（#,##0.00 固定两位小数是记账惯例、yyyy-mm-dd
    没有可选小数位的问题）；**数量列必须逐格选**（见 _count_fmt），否则整数会
    拖出一个小数点尾巴。

    比率列（含「率」「占比」，如 偏差率A/B、净偏差率、备注覆盖率、偏差率）：
    值是**比率小数**（0.08171 表 8.17%），必须套 0.00% 格式才会显示成百分比。
    漏掉这一步的坑（v43.242 修复，用户截图反馈）：v43.241 把 替代料明细
    偏差率A/B/净偏差率 的值折算成了比率小数，但 _apply_number_formats 只认
    日期/金额/数量三类，比率列落在哪个都不套 → 0.08171 原样显示。注意与
    _normalize_ratio_columns 的区别：后者只处理「以 % 结尾的文本」（如 '19.6%'
    → 0.196），处理不了已经是真数值的列；本处按列名补套，两者互补。
    """
    date_cols, amount_cols, count_cols, ratio_cols, pct_cols = [], [], [], [], []
    for col, name in headers.items():
        if not name:
            continue
        if any(k in name for k in _DATE_KEYS):
            date_cols.append(col)
        elif any(k in name for k in _AMOUNT_KEYS):
            amount_cols.append(col)
        elif _is_pct_point_col(name):
            # 百分点数值列必须**先于**数量/比率判定：它的列名（如「占车间偏差比%」）
            # 不含「数量/率/占比」，靠后判定会被漏掉。
            pct_cols.append(col)
        elif any(k in name for k in _COUNT_KEYS):
            count_cols.append(col)
        elif any(k in name for k in _RATIO_KEYS):
            ratio_cols.append(col)
    if not (date_cols or amount_cols or count_cols or ratio_cols or pct_cols):
        return
    map_ = _cells_of(ws)

    def _set(col, fmt):
        for r in range(hdr_row + 1, last_row + 1):
            c = map_.get((r, col))
            if c is None or c.value in (None, ''):
                continue
            if str(c.number_format) != fmt:
                c.number_format = fmt

    for col in date_cols:
        _set(col, _FMT_DATE)
    for col in amount_cols:
        _set(col, _FMT_AMOUNT)
    for col in count_cols:
        for r in range(hdr_row + 1, last_row + 1):
            c = map_.get((r, col))
            if c is None or c.value in (None, ''):
                continue
            fmt = _count_fmt(c.value)
            if str(c.number_format) != fmt:
                c.number_format = fmt
    for col in ratio_cols:
        _set(col, _FMT_RATIO)
    for col in pct_cols:
        # 安全阀：百分点列的值几乎必然 >1（实测「占车间偏差比%」0~97.84）；
        # 若整列都 ≤1，说明它其实是**比率小数**形态，套字面百分号会错 100 倍
        # （0.143 会显示成 0.14%），此时改回 0.00%。
        fmt = (_FMT_PCT_POINT
               if _col_max_abs(ws, hdr_row, last_row, col) > 1.000001
               else _FMT_RATIO)
        _set(col, fmt)


def _has_rule(ws, rng, operator):
    """该区域是否已存在同 operator 的规则——保证条件格式幂等，重复调用不叠加。"""
    try:
        for cf in ws.conditional_formatting:
            if str(cf.sqref) != rng:
                continue
            for rule in cf.rules:
                if getattr(rule, 'operator', None) == operator:
                    return True
    except Exception:
        pass
    return False


def _apply_conditional_formats(ws, hdr_row, headers, last_row, ratio_cols=None):
    """关键列条件格式：偏差率越界标红、异常标记非空标黄。配色沿用项目 COLORS 语义。

    阈值口径随列的**实际存储形态**自动切换，否则必然错一边：
      - 文本 '19.60%' 已被 _normalize_ratio_columns 转成小数 0.196 的列 → 阈值 1.0（=100%）；
      - 仍是原始百分数数值的列（如替代料明细 偏差率A = 209.523）           → 阈值 100。
    """
    if last_row <= hdr_row:
        return
    ratio_cols = ratio_cols or set()
    red_fill = PatternFill(start_color='FFCDD2', end_color='FFCDD2', fill_type='solid')   # = anomaly_1
    amber_fill = PatternFill(start_color='FEFFD6', end_color='FEFFD6', fill_type='solid')  # = anomaly_5
    red_font = Font(size=10, color='C00000')
    amber_font = Font(size=10, color='854F0B')

    rate_col = _find_col(headers, '偏差率')
    if rate_col:
        letter = get_column_letter(rate_col)
        rng = '%s%d:%s%d' % (letter, hdr_row + 1, letter, last_row)
        # 严格大于：±100% 是钳位标记值（定额=0 / 实际=0），全列标红会把 2836 格
        # 刷成红色、信号淹没；严格大于只剩 200 格真越界，一眼可辨。
        lo, hi = (-1.0, 1.0) if rate_col in ratio_cols else (-100, 100)
        if not _has_rule(ws, rng, 'greaterThan'):
            ws.conditional_formatting.add(
                rng, CellIsRule(operator='greaterThan', formula=[str(hi)],
                                fill=red_fill, font=red_font))
            ws.conditional_formatting.add(
                rng, CellIsRule(operator='lessThan', formula=[str(lo)],
                                fill=red_fill, font=red_font))

    flag_col = _find_col(headers, '异常标记')
    if flag_col:
        letter = get_column_letter(flag_col)
        rng = '%s%d:%s%d' % (letter, hdr_row + 1, letter, last_row)
        if not _has_rule(ws, rng, 'LEN(TRIM())>0'):
            ws.conditional_formatting.add(
                rng, FormulaRule(formula=['LEN(TRIM($%s%d))>0' % (letter, hdr_row + 1)],
                                 fill=amber_fill, font=amber_font))


# ---------------------------------------------------------------- 安全清洗

def _normalize_dates(ws, hdr_row, headers, last_row):
    """日期列：文本 'YYYY-MM-DD' / 'YYYY/M/D' → 真日期（值等价，只是类型变了）。"""
    import datetime as _dt
    cols = [c for c, n in headers.items() if n and any(k in n for k in _DATE_KEYS)]
    if not cols:
        return 0
    map_ = _cells_of(ws)
    fixed = 0
    for col in cols:
        for r in range(hdr_row + 1, last_row + 1):
            c = map_.get((r, col))
            if c is None:
                continue
            v = c.value
            if v is None or v == '' or isinstance(v, (_dt.datetime, _dt.date)):
                continue
            s = str(v).strip()
            if s == '' or s in ('-', '—'):
                continue
            parsed = None
            for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y-%m-%d %H:%M:%S'):
                try:
                    parsed = _dt.datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                continue
            c.value = parsed
            c.number_format = _FMT_DATE
            fixed += 1
    return fixed


def _normalize_text_ids(ws, hdr_row, headers, last_row):
    """标识列：数字 → 文本（字面等价）。防长编码丢前导零 / 被当数字截断。"""
    cols = [c for c, n in headers.items() if n and any(k in n for k in _TEXT_ID_KEYS)]
    if not cols:
        return 0
    map_ = _cells_of(ws)
    fixed = 0
    for col in cols:
        hc = map_.get((hdr_row, col))
        if hc is not None and str(hc.number_format) != '@':
            hc.number_format = '@'
        for r in range(hdr_row + 1, last_row + 1):
            c = map_.get((r, col))
            if c is None:
                continue
            v = c.value
            if v is None or v == '':
                continue
            if isinstance(v, str):
                if str(c.number_format) != '@':
                    c.number_format = '@'
                continue
            if isinstance(v, float) and v.is_integer():
                c.value = str(int(v))
            else:
                c.value = str(v)
            c.number_format = '@'
            fixed += 1
    return fixed


def _normalize_empties(ws, hdr_row, last_row):
    """空值规范化：纯空格串 / '-' / '—' / 'nan' 占位 → 真空白。

    只遍历**已存在**的单元格（_cells_of），不做全栅格扫描。
    """
    map_ = _cells_of(ws)
    fixed = 0
    for (r, _c), cell in list(map_.items()):
        if r <= hdr_row:
            continue
        v = cell.value
        if not isinstance(v, str):
            continue
        t = v.strip()
        if t == '' and v != '':
            cell.value = None
            fixed += 1
        elif t in ('-', '—', 'nan', 'NaN', 'None'):
            cell.value = None
            fixed += 1
    return fixed


def _normalize_ratio_columns(ws, hdr_row, headers, last_row):
    """比率列：文本 '19.60%' -> 真数值 0.196 + '0.00%' 格式（**显示完全等价**）。

    为什么必须动它（这不是美化，是修隐患）：
      源表里 偏差率 / 净偏差率 / 早期偏差率 / 备注覆盖率 等都是**文本**。Excel 里
      「文本 > 数字」恒为真，任何 `大于 100` 之类的数值型条件格式会把整列误标红；
      而且文本列无法按数值排序、筛选、画图。转成真数值后显示一模一样（19.60%），
      但可排序、可比大小、可正确套条件格式。

    安全阀：**只处理以 % 结尾的文本**——这是唯一无歧义的判定，绝不会把已经是真数值
    的比率列（如替代料明细 偏差率A = 209.523）再除一次 100。

    返回 {列号: 已转换单元格数}，供条件格式决定阈值口径（小数口径下 1.0 = 100%）。
    """
    cols = [c for c, n in headers.items() if n and any(k in n for k in _RATIO_KEYS)]
    if not cols:
        return {}
    map_ = _cells_of(ws)
    out = {}
    for col in cols:
        n = 0
        for r in range(hdr_row + 1, last_row + 1):
            c = map_.get((r, col))
            if c is None or not isinstance(c.value, str):
                continue
            s = c.value.strip()
            if not s.endswith('%'):
                continue
            try:
                num = float(s[:-1])
            except ValueError:
                continue
            c.value = num / 100.0
            c.number_format = _FMT_RATIO
            n += 1
        if n:
            out[col] = n
    return out


def _append_col_header(ws, hdr_row, col, title):
    """在 hdr_row 行 col 列写表头，样式尽量沿用 builder 的默认表头样式。"""
    hc = ws.cell(row=hdr_row, column=col, value=title)
    try:
        from analysis.excel_builder.write_sheet_util import get_default_styles
        st = get_default_styles()
        hc.font = st['header_font']
        hc.fill = st['header_fill']
        hc.alignment = st['center']
    except Exception:
        hc.font = Font(bold=True, size=11, color='FFFFFF')
    return hc


def _mark_duplicate_rows(ws, hdr_row, headers, last_row):
    """整行**完全相同**的重复行 -> 追加「重复行」列打标。已存在则跳过（幂等）。

    刻意只标记、绝不删行：
      删行会改变报表合计与条数，属业务口径变更；重复行的根因大概率在上游
      取数/关联（JOIN 放大），应回源端修，而不是在出口"擦掉"——
      出口兜底只会把上游 bug 遮得更深。故在此仅**暴露**，由人决定。
    """
    if last_row <= hdr_row:
        return 0
    if '重复行' in headers.values():
        return 0
    map_ = _cells_of(ws)
    ncol = ws.max_column
    if ncol <= 0:
        return 0

    seen = set()
    dups = []
    for r in range(hdr_row + 1, last_row + 1):
        vals = []
        blank = True
        for c in range(1, ncol + 1):
            cell = map_.get((r, c))
            v = None if cell is None else cell.value
            if v not in (None, ''):
                blank = False
            vals.append(v)
        if blank:
            continue
        key = tuple(vals)
        if key in seen:
            dups.append(r)
        else:
            seen.add(key)
    if not dups:
        return 0

    col = ncol + 1
    _append_col_header(ws, hdr_row, col, '重复行')
    for r in dups:
        ws.cell(row=r, column=col, value='整行重复')
    ws.column_dimensions[get_column_letter(col)].width = 12
    return len(dups)


def _add_anomaly_flag(ws, hdr_row, headers, last_row):
    """主表追加「异常标记」列。已存在则跳过（幂等）。

    标记口径（可叠加，用「；」连接）：
      系统无定额 / 实际为零 / 偏差率越界 / 单位量纲G

    关于 ±100% 这个坑（实测数据事实，别改成 >=100）：
      偏差率在 ±100.0% 处是**钳位标记值**，不是真实比率——定额=0 时恒为 +100.0%
      （2390 行）、实际=0 时恒为 -100.0%（246 行）。这 2636 行**已经被
      「系统无定额」「实际为零」两个标签精确覆盖**。若越界判定写成 >=100，
      就会给这 2636 行再多刷一个重复标签（合计多 2636 个），把真正越界的
      200 行信号彻底淹没。故此处必须用**严格大于**。
    """
    if '异常标记' in headers.values():
        return 0
    if '完整偏差明细' not in str(ws.title):
        return 0

    c_quota = _find_col(headers, '定额')
    c_actual = _find_col(headers, '实际')
    c_rate = _find_col(headers, '偏差率')
    c_unit = _find_col(headers, '单位')
    if not c_quota:
        return 0

    col = ws.max_column + 1
    hc = ws.cell(row=hdr_row, column=col, value='异常标记')
    try:
        from analysis.excel_builder.write_sheet_util import get_default_styles
        st = get_default_styles()
        hc.font = st['header_font']
        hc.fill = st['header_fill']
        hc.alignment = st['center']
    except Exception:
        hc.font = Font(bold=True, size=11, color='FFFFFF')

    map_ = _cells_of(ws)

    def _val(r, c):
        cell = map_.get((r, c)) if c else None
        return None if cell is None else cell.value

    n = 0
    for r in range(hdr_row + 1, last_row + 1):
        tags = []
        q = _num(_val(r, c_quota))
        a = _num(_val(r, c_actual))
        rt = _num(_val(r, c_rate))
        unit = str(_val(r, c_unit) or '').strip().upper()
        if q == 0:
            tags.append('系统无定额')
        if a == 0:
            tags.append('实际为零')
        # 严格大于：±100% 是钳位标记值，已由上面两个标签覆盖（见函数 docstring）
        if rt is not None and abs(rt) > 100:
            tags.append('偏差率越界')
        if unit in ('G', '克'):
            tags.append('单位量纲G')
        if tags:
            ws.cell(row=r, column=col, value='；'.join(tags))
            n += 1
    ws.column_dimensions[get_column_letter(col)].width = 26
    return n


# ---------------------------------------------------------------- 驾驶舱

def _add_dashboard(wb):
    """新建「📊 驾驶舱」页：KPI 数字块 + 3 张图。已存在则跳过（幂等）。"""
    from openpyxl.chart import BarChart, Reference
    name = '📊 驾驶舱'
    if name in wb.sheetnames:
        return 0

    ws_dash = wb.create_sheet(name, index=1)
    ws_dash.sheet_view.showGridLines = False
    ws_dash.column_dimensions['A'].width = 3
    for col in 'BCDEFGHIJKLMN':
        ws_dash.column_dimensions[col].width = 11
    t = ws_dash.cell(row=1, column=2, value='ZPP011 生产偏差分析 · 驾驶舱')
    t.font = Font(bold=True, size=14, color='1B5E20')
    ws_dash.cell(row=2, column=2,
                 value='图表数据源：本工作簿「汇总统计」「偏差金额分析」；随每次导出自动生成'
                 ).font = Font(size=10, color='666666')

    # ── KPI 数字块（v43.233 优化）：驾驶舱原先只有 3 张图、没有任何数字，
    # 打开文件第一眼看不到总条数/总偏差金额/无备注占比。现从「汇总统计」
    # 直接求合写出 4 个 KPI，与图表排成一行，补充管理层速览。──
    _kpi_row = 4
    try:
        if '汇总统计' in wb.sheetnames:
            src = wb['汇总统计']
            h_row, hds = _header_info(src)
            l_row = _last_data_row(src, h_row)
            def _col_sum(names):
                c_ = _find_col(hds, *names)
                if not c_:
                    return 0.0
                s = 0.0
                for r in range(h_row + 1, l_row + 1):
                    v = src.cell(row=r, column=c_).value
                    if isinstance(v, (int, float)):
                        s += v
                return s
            k_total = _col_sum(('总偏差金额(含税)',))
            k_cnt = _col_sum(('总条数',))
            # 备注覆盖率：按「总条数」加权（Σ覆盖率×条数 ÷ Σ条数）。
            # 直接平均各行覆盖率会把条数少的车间算重，不是本期口径。
            k_cov = None
            c_cov = _find_col(hds, '备注覆盖率')
            c_rows = _find_col(hds, '总条数')
            if c_cov and c_rows:
                num = den = 0.0
                for r in range(h_row + 1, l_row + 1):
                    cv = src.cell(row=r, column=c_cov).value
                    rv = src.cell(row=r, column=c_rows).value
                    if isinstance(cv, (int, float)) and isinstance(rv, (int, float)) and rv:
                        num += float(cv) * float(rv)
                        den += float(rv)
                if den:
                    k_cov = num / den
            k_unread = 0
            try:
                if '无备注预警' in wb.sheetnames:
                    s2 = wb['无备注预警']
                    h2, _ = _header_info(s2)
                    k_unread = _last_data_row(s2, h2) - h2
            except Exception:
                k_unread = 0
            # KPI 只摆**闭合口径**：「正偏差金额 + 负偏差金额 ≠ 总偏差金额」
            # （差额 = 价格差异行，属设计口径），并排摆出来会被业务方直接相加、
            # 发现「对不上总偏差」而误判为数据错误。故只给「总偏差金额(含税)」，
            # 多耗/少耗的分解交给下方图2。
            kpis = [
                ('总偏差记录', f'{int(k_cnt):,}', '条'),
                ('总偏差金额(含税)', f'{k_total:,.2f}', '元'),
                ('偏差率超阈未填备注', f'{k_unread:,}', '条'),
                ('备注覆盖率', ('%.1f%%' % (k_cov * 100)) if k_cov is not None else '—', ''),
            ]
            for k, (lab, val, unit) in enumerate(kpis):
                col = 2 + k * 3
                lc = ws_dash.cell(row=_kpi_row, column=col, value=lab)
                lc.font = Font(bold=True, size=11, color='1B5E20')
                lc.alignment = Alignment(horizontal='center')
                vc = ws_dash.cell(row=_kpi_row + 1, column=col, value=val)
                vc.font = Font(bold=True, size=16, color='1B5E20')
                vc.alignment = Alignment(horizontal='center')
                uc = ws_dash.cell(row=_kpi_row + 2, column=col, value=unit)
                uc.font = Font(size=9, color='666666')
                uc.alignment = Alignment(horizontal='center')
                # 列宽：KPI 落在第 2/5/8/11 列（B/E/H/K）。原先用 chr(ord('A')+col)
                # 算出来是 C/F/I/L，**整体偏移一列**，等于没设到 KPI 上；改用
                # get_column_letter 按真实列号取。数字带千分位两位小数，16 太窄。
                ws_dash.column_dimensions[get_column_letter(col)].width = 18
            # 口径注：把「正/负不闭合」这件事写在脸上，避免被误读为数据错误
            nc = ws_dash.cell(row=_kpi_row + 3, column=2, value=(
                '口径：总偏差金额(含税)为全量合计（汇总统计「正/负偏差金额」两列不闭合，'
                '差额=价格差异行，故不单列）；多耗/少耗分解见下方图2；备注覆盖率按总条数加权。'))
            nc.font = Font(size=9, color='666666')
    except Exception as e:
        _log('[post_process] 驾驶舱KPI失败: %s' % e)

    charts = 0

    # 图1：各车间总偏差金额（柱）
    try:
        if '汇总统计' in wb.sheetnames:
            src = wb['汇总统计']
            hdr_row, headers = _header_info(src)
            last_row = _last_data_row(src, hdr_row)
            c_cat = _find_col(headers, '车间')
            c_val = _find_col(headers, '总偏差金额(含税)', '总偏差金额')
            if c_cat and c_val and last_row > hdr_row:
                ch = BarChart()
                ch.type = 'col'
                ch.title = '各车间总偏差金额（含税）'
                ch.y_axis.title = '元'
                ch.x_axis.title = '车间'
                ch.add_data(Reference(src, min_col=c_val, min_row=hdr_row, max_row=last_row),
                            titles_from_data=True)
                ch.set_categories(Reference(src, min_col=c_cat, min_row=hdr_row + 1,
                                            max_row=last_row))
                ch.height, ch.width = 9, 22
                # 锚点下移 4 行：KPI 数字块占 row4-6，原 B4 会让图压住 KPI 标签
                ws_dash.add_chart(ch, 'B8')
                charts += 1
    except Exception as e:
        _log('[post_process] 驾驶舱图1失败: %s' % e)

    # 图2：Top10 物料偏差金额（横条）
    try:
        if '偏差金额分析' in wb.sheetnames:
            src = wb['偏差金额分析']
            hdr_row, headers = _header_info(src)
            last_row = _last_data_row(src, hdr_row)
            c_cat = _find_col(headers, '物料名称')
            c_val = _find_col(headers, '总偏差金额(含税)', '总偏差金额')
            if c_cat and c_val and last_row > hdr_row:
                end = min(last_row, hdr_row + 10)
                ch = BarChart()
                ch.type = 'bar'
                ch.title = 'Top10 物料偏差金额（含税）'
                ch.add_data(Reference(src, min_col=c_val, min_row=hdr_row, max_row=end),
                            titles_from_data=True)
                ch.set_categories(Reference(src, min_col=c_cat, min_row=hdr_row + 1,
                                            max_row=end))
                ch.height, ch.width = 12, 22
                ws_dash.add_chart(ch, 'B28')
                charts += 1
    except Exception as e:
        _log('[post_process] 驾驶舱图2失败: %s' % e)

    # 图3：各车间正/负偏差金额对比（柱，2 系列）
    try:
        if '汇总统计' in wb.sheetnames:
            src = wb['汇总统计']
            hdr_row, headers = _header_info(src)
            last_row = _last_data_row(src, hdr_row)
            c_cat = _find_col(headers, '车间')
            c_pos = _find_col(headers, '正偏差金额(含税)')
            c_neg = _find_col(headers, '负偏差金额(含税)')
            if c_cat and c_pos and c_neg and last_row > hdr_row:
                ch = BarChart()
                ch.type = 'col'
                ch.grouping = 'clustered'
                ch.title = '各车间正 / 负偏差金额对比（含税）'
                ch.y_axis.title = '元'
                ch.add_data(Reference(src, min_col=c_pos, max_col=c_neg,
                                      min_row=hdr_row, max_row=last_row),
                            titles_from_data=True)
                ch.set_categories(Reference(src, min_col=c_cat, min_row=hdr_row + 1,
                                            max_row=last_row))
                ch.height, ch.width = 9, 22
                ws_dash.add_chart(ch, 'B54')
                charts += 1
    except Exception as e:
        _log('[post_process] 驾驶舱图3失败: %s' % e)

    if charts == 0:
        # 一张图都没成，不留空页
        try:
            del wb[name]
        except Exception:
            pass
    return charts


# ------------------------------------------------------------ 驾驶舱升级 v43.283

# 布局常量：_add_dashboard 的 3 张图占 B8~M72 浮动区；
# Top 表写在图右侧 P 列区，周趋势写/画在图下方 B76 起。幂等 = 固定区域先清后写。
_DASH_TBL_COL = 16          # P 列
_DASH_TBL_TOP = 8
_DASH_TBL_CLEAR = (8, 46)   # 清理 P8:U46
_DASH_WK_ROW = 76           # 周趋势数据起始行
_DASH_WK_CLEAR_ROWS = (76, 140)


def _clear_region(ws, r1, r2, c1, c2):
    """清空固定区域单元格值（幂等重写前置；不动区域外内容/图表）。"""
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = ws.cell(r, c)
            if cell.value is not None:
                cell.value = None


def _upgrade_dashboard(wb):
    """v43.283 规格 §3：驾驶舱补 Top5 车间表 / Top10 物料表（帕累托累计占比）
    / 周趋势线图 + 页签绿。只读「汇总统计」「完整偏差明细」「趋势分析」派生
    呈现，零口径计算。幂等：重复调用先清固定区域再重写。"""
    from openpyxl.styles import Border, Font, Side
    from openpyxl.formatting.rule import DataBarRule
    name = '📊 驾驶舱'
    if name not in wb.sheetnames:
        return 0
    ws = wb[name]
    ws.sheet_properties.tabColor = '2E7D32'   # 结论层=绿（规格 §6）
    _thin = Side(style='thin', color='CCCCCC')
    _bd = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
    P = _DASH_TBL_COL
    _clear_region(ws, _DASH_TBL_CLEAR[0], _DASH_TBL_CLEAR[1], P, P + 5)
    for col in range(P, P + 6):
        ws.column_dimensions[get_column_letter(col)].width = 14

    row = _DASH_TBL_TOP
    # ── Top 5 车间（|总偏差金额| 降序）──
    ws.cell(row=row, column=P,
            value='Top 5 车间（按 |偏差金额| 降序）').font = Font(bold=True, size=11)
    row += 1
    for j, h in enumerate(['车间', '总条数', '总偏差金额(含税)', '备注覆盖率']):
        c = ws.cell(row=row, column=P + j, value=h)
        c.font = Font(bold=True, size=10)
        c.border = _bd
    row += 1
    top5_start = row
    if '汇总统计' in wb.sheetnames:
        src = wb['汇总统计']
        h_row, hds = _header_info(src)
        l_row = _last_data_row(src, h_row)
        c_ws = _find_col(hds, '车间')
        c_cnt = _find_col(hds, '总条数')
        c_amt = _find_col(hds, '总偏差金额(含税)')
        c_cov = _find_col(hds, '备注覆盖率')
        recs = []
        for r in range(h_row + 1, l_row + 1):
            amt = src.cell(r, c_amt).value if c_amt else None
            if isinstance(amt, (int, float)):
                recs.append((
                    src.cell(r, c_ws).value if c_ws else '',
                    src.cell(r, c_cnt).value if c_cnt else '',
                    amt,
                    src.cell(r, c_cov).value if c_cov else ''))
        recs.sort(key=lambda x: -abs(x[2]))
        for w, cnt, amt, cov in recs[:5]:
            ws.cell(row=row, column=P, value=w).border = _bd
            ws.cell(row=row, column=P + 1, value=cnt).border = _bd
            ca = ws.cell(row=row, column=P + 2, value=round(amt, 2))
            ca.number_format = '#,##0.00'
            ca.border = _bd
            cc = ws.cell(row=row, column=P + 3, value=cov)
            if isinstance(cov, (int, float)):
                cc.number_format = '0%'
            cc.border = _bd
            row += 1
    if row > top5_start:
        ws.conditional_formatting.add(
            '%s%d:%s%d' % (get_column_letter(P + 2), top5_start,
                           get_column_letter(P + 2), row - 1),
            DataBarRule(start_type='min', end_type='max', color='C62828'))
    row += 2

    # ── Top 10 物料（帕累托：|偏差金额| 聚合降序 + 累计占比）──
    ws.cell(row=row, column=P,
            value='Top 10 物料（按 |偏差金额| 降序，含累计占比）').font = Font(bold=True, size=11)
    row += 1
    for j, h in enumerate(['物料编码', '物料名称', '偏差金额', '占总额比', '累计占比']):
        c = ws.cell(row=row, column=P + j, value=h)
        c.font = Font(bold=True, size=10)
        c.border = _bd
    row += 1
    m_start = row
    if '完整偏差明细' in wb.sheetnames:
        src = wb['完整偏差明细']
        h_row, hds = _header_info(src)
        l_row = _last_data_row(src, h_row)
        c_code = _find_col(hds, '物料编码')
        c_name = _find_col(hds, '物料名称')
        c_amt = _find_col(hds, '偏差金额')
        agg = {}
        for r in range(h_row + 1, l_row + 1):
            amt = src.cell(r, c_amt).value if c_amt else None
            if not isinstance(amt, (int, float)):
                continue
            code = str(src.cell(r, c_code).value or '') if c_code else ''
            if code not in agg:
                agg[code] = [src.cell(r, c_name).value if c_name else '', 0.0]
            agg[code][1] += amt
        total_abs = sum(abs(v[1]) for v in agg.values()) or 1.0
        top = sorted(agg.items(), key=lambda kv: -abs(kv[1][1]))[:10]
        cum = 0.0
        for code, (nm, amt) in top:
            share = abs(amt) / total_abs
            cum += share
            ws.cell(row=row, column=P, value=code).border = _bd
            ws.cell(row=row, column=P + 1, value=nm).border = _bd
            ca = ws.cell(row=row, column=P + 2, value=round(amt, 2))
            ca.number_format = '#,##0.00'
            ca.border = _bd
            cs = ws.cell(row=row, column=P + 3, value=round(share, 4))
            cs.number_format = '0.0%'
            cs.border = _bd
            cu = ws.cell(row=row, column=P + 4, value=round(cum, 4))
            cu.number_format = '0.0%'
            cu.border = _bd
            row += 1
        if top:
            ws.cell(row=row, column=P,
                    value='前 10 合计占比 %.1f%%' % (cum * 100)).font = Font(bold=True, size=10)
            row += 1
    if row > m_start:
        ws.conditional_formatting.add(
            '%s%d:%s%d' % (get_column_letter(P + 2), m_start,
                           get_column_letter(P + 2), row - 1),
            DataBarRule(start_type='min', end_type='max', color='C62828'))

    # ── 周趋势（自然周聚合替代日级噪声；数据 B76 起，图画 D76）──
    try:
        _clear_region(ws, _DASH_WK_CLEAR_ROWS[0], _DASH_WK_CLEAR_ROWS[1], 2, 14)
        trend_name = '趋势分析（自然日分组）'
        if trend_name in wb.sheetnames:
            src = wb[trend_name]
            h_row, hds = _header_info(src)
            l_row = _last_data_row(src, h_row)
            c_date = _find_col(hds, '订单日期', '日期')
            c_amt = _find_col(hds, '偏差金额合计', '偏差金额')
            if c_date and c_amt:
                import pandas as _pd
                weeks = {}
                for r in range(h_row + 1, l_row + 1):
                    dv = src.cell(r, c_date).value
                    av = src.cell(r, c_amt).value
                    if dv is None or not isinstance(av, (int, float)):
                        continue
                    try:
                        iso = _pd.Timestamp(dv).isocalendar()
                    except Exception:
                        continue
                    key = (int(iso[0]), int(iso[1]))
                    weeks[key] = weeks.get(key, 0.0) + av
                if weeks:
                    wr = _DASH_WK_ROW
                    ws.cell(row=wr - 1, column=2,
                            value='偏差金额 · 自然周趋势（ISO 周）').font = Font(bold=True, size=11)
                    keys = sorted(weeks)
                    for i, k in enumerate(keys):
                        ws.cell(row=wr + i, column=2, value='%d-W%02d' % k)
                        ws.cell(row=wr + i, column=3, value=round(weeks[k], 2)).number_format = '#,##0.00'
                    from openpyxl.chart import LineChart, Reference
                    ch = LineChart()
                    ch.title = '偏差金额 · 周趋势'
                    ch.height, ch.width = 8, 22
                    data = Reference(ws, min_col=3, min_row=wr, max_row=wr + len(keys) - 1)
                    cats = Reference(ws, min_col=2, min_row=wr, max_row=wr + len(keys) - 1)
                    ch.add_data(data, titles_from_data=False)
                    ch.set_categories(cats)
                    ws.add_chart(ch, 'E%d' % (wr - 1))
    except Exception as e:
        _log('[post_process] 周趋势失败: %s' % e)
    return 1


# ------------------------------------------------------------ 数据层降噪 v43.283

def _resort_summary(wb):
    """v43.283 规格 §5：「汇总统计」展示行按 |总偏差金额| 降序整行重排。
    只搬行（值+样式随行走），数值零改动；序号列随行走（保留原生成序作
    对账锚点）。放在逐表流水线之后跑，避免重排让条件格式区间指错行——
    汇总统计页的条件格式按列整区挂（G 列预警等随行换内容不换位），
    实测其 CF 区间为整列区，重排后语义仍正确。"""
    name = '汇总统计'
    if name not in wb.sheetnames:
        return 0
    ws = wb[name]
    h_row, headers = _header_info(ws)
    last_row = _last_data_row(ws, h_row)
    c_amt = _find_col(headers, '总偏差金额(含税)')
    if not c_amt or last_row <= h_row + 1:
        return 0
    ncol = ws.max_column
    map_ = _cells_of(ws)
    rows = []
    for r in range(h_row + 1, last_row + 1):
        cells = []
        for c in range(1, ncol + 1):
            src = map_.get((r, c))
            cells.append((src.value if src is not None else None,
                          copy(src._style) if src is not None else None))
        src_amt = map_.get((r, c_amt))
        amt = src_amt.value if src_amt is not None else None
        rows.append((abs(amt) if isinstance(amt, (int, float)) else 0.0, cells))
    rows.sort(key=lambda x: -x[0])
    for i, (_, cells) in enumerate(rows):
        for c, (v, st) in enumerate(cells, 1):
            tgt = ws.cell(h_row + 1 + i, c)
            tgt.value = v
            if st is not None:
                tgt._style = st
    ws.sheet_properties.tabColor = '9E9E9E'   # 数据层=灰（规格 §6）
    return 1


def _denoise_trend_sheet(wb):
    """v43.283 规格 §5：趋势分析页降噪。
    1) R1 区间说明（合并单元格）挪出数据区 → 解合并、清值、挂表头首格批注；
    2) 偏差率列空白格填 '—'（全空杂行不填）；
    3) autofilter 重建覆盖数据区。
    **不删行**：条件格式区间（G3:G1086）不随行移动，删行会整体错位。
    返回填充 '—' 的格数。"""
    name = '趋势分析（自然日分组）'
    if name not in wb.sheetnames:
        return 0
    ws = wb[name]
    h_row, headers = _header_info(ws)
    last_row = _last_data_row(ws, h_row)
    # 1) 表头上方杂行挪入批注（数据区不夹文本）
    stray = []
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row < h_row:
            ws.unmerge_cells(str(rng))
    for r in range(1, h_row):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if v not in (None, ''):
                stray.append(str(v))
                ws.cell(r, c).value = None
    if stray:
        from openpyxl.comments import Comment
        note = ws.cell(h_row, 1)
        note.comment = Comment(' '.join(stray), 'ZPP011', height=80, width=300)
    # 2) 数值列（表头含 数量/金额/率）空白填 —；整行全空的杂行跳过
    numeric_cols = [c for c, nm in headers.items()
                    if nm and any(k in str(nm) for k in ('数量', '金额', '率'))]
    filled = 0
    map_ = _cells_of(ws)
    for r in range(h_row + 1, last_row + 1):
        row_has_data = any(map_.get((r, c)) is not None
                           and map_[(r, c)].value not in (None, '')
                           for c in headers if c <= ws.max_column)
        if not row_has_data:
            continue
        for c in numeric_cols:
            cell = ws.cell(r, c)
            if cell.value in (None, ''):
                cell.value = '—'
                cell.alignment = Alignment(horizontal='right')
                filled += 1
    # 3) autofilter 重建（覆盖旧 ref，含杂行清除后的范围不变——不删行）
    try:
        ws.auto_filter.ref = '%s%d:%s%d' % (
            get_column_letter(1), h_row,
            get_column_letter(ws.max_column), last_row)
    except Exception as e:
        _log('[post_process] 趋势页 autofilter 失败: %s' % e)
    ws.sheet_properties.tabColor = '9E9E9E'
    return filled


# ---------------------------------------------------------------- 各表事实卡

# 事实卡「关键度量」列的候选优先级：按顺序取第一个能匹配上的列。
# 为什么不取「率」类：同一本工作簿里「占车间偏差比%」是**百分点**（14.57），
# 而「偏差率/净偏差率」是**比率小数**（0.143），两者数字格式不同，混进候选必踩口径坑。
# 另：匹配到的列一律以**表头原文**作标签（_find_col 允许子串命中，如「净偏差金额」
# 会被 '偏差金额' 命中），避免标签与实际列对不上。
_FACT_METRIC_COLS = (
    '总偏差金额(含税)', '偏差金额(含税)', '偏差金额',
    '净偏差金额', '净偏差数量', '偏差数量',
)

# 不做事实卡的表：驾驶舱（其 KPI 另有出处，且图表锚点与数据行混排）
_FACT_SKIP_SHEETS = ('📊 驾驶舱',)

# 事实卡区块标题前缀（兼作幂等标记）
_FACT_MARKER = '各表事实卡'

# post_process 新增的表（analyzer 不知道它们，故说明块里没有对应行），
# 口径说明在这里补上 → 事实卡「口径」列有内容，且只此一处，不与说明区打架。
_EXTRA_CALIBER = {
    '订单级汇总': (
        '按流程订单汇总（原来 12 张表全是行级明细，缺「一单怎么看」的视角）。'
        '投料状态三选一：完全未投料（该单所有组件实际用量都是 0）/ 部分未投料 / 正常。'
        '「完全未投料」实测本期 35 单、缺料金额 -332.40 万元（占全期总偏差 56.1%），'
        '这类单通常产量已报（虚报产量）且原始备注原因为空，报表中已用主明细的'
        '「未投料订单」列标出，可直接筛选。'),
    '车间维度': (
        '按「工厂+车间」两个维度一起汇总（不按车间名单独分组）—— 车间名跨厂同名时'
        '（实测「综合组」食品厂与饮料厂都有）按名单独汇总会串味。'
        '「跨厂同名」= 该车间名在源表里出现在多于一个工厂。'
        '「车间类型」按名称判定：含「线」→产线、含「车间」→车间、其余（如综合组/配料中心）→班组。'),
    '备注归类映射': (
        '原始备注写法 → 标准原因 的对照（标准原因用项目统一的 standardize_remark 归类）。'
        '只统计**非空**备注；「占非空备注比」= 该写法条数 ÷ 全部非空备注条数。'
        '本表可直接看出哪些写法其实是同一类（如「系统无额定」与「系统无定额」），'
        '用于统一填报口径、从源头降低空备注率。'),
    '系统问题与真实超耗': (
        '把「该谁负责」分开：系统无定额（定额=0 且 实际>0）/ 完全未投料（实际=0 且 定额>0）'
        '/ 真实超耗（|偏差率|>100% 且不属于前两类）/ 其他偏差。'
        '前两类是**系统问题**（SAP 没推定额、料没投），不是审核员没写备注的责任，'
        '故与真实超耗分列。⚠️ 偏差率是**比率小数**形态（-1 表示 -100%），不是百分点。'),
    '物料画像': (
        '按组件物料编码聚合：涉及订单数/偏差条数/偏差数量与金额/最大偏差率绝对值/'
        '备注覆盖率/是否含替代料 —— 用于定位「最烧钱」的料与「最没人写备注」的料。'),
}


def _fact_col_stats(ws, hdr_row, last_row, col):
    """统计某列的 合计/最大/最小（**只读**已渲染单元格，不改任何值）。

    返回 (sum, mx, mn, n_num, n_skip)：
      - n_num  = 参与统计的数值单元格数
      - n_skip = 非数值占位（如导出把 0 写成 '-'）的单元格数，**不计入统计**
    """
    map_ = _cells_of(ws)
    s = 0.0
    mx = None
    mn = None
    n_num = 0
    n_skip = 0
    for r in range(hdr_row + 1, last_row + 1):
        c = map_.get((r, col))
        if c is None:
            continue
        v = c.value
        if v is None or v == '':
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            n_skip += 1
            continue
        fv = float(v)
        s += fv
        n_num += 1
        if mx is None or fv > mx:
            mx = fv
        if mn is None or fv < mn:
            mn = fv
    return s, mx, mn, n_num, n_skip


def _fact_numfmt(metric_name):
    """按度量名给数字格式：金额两位小数千分位；数量最多三位小数。

    百分点数值列（列名以 '%' 结尾）用 `0.00"%"`，比率小数用 0.00% —— 与
    `_apply_number_formats` 同一套判据，两处不能打架（否则事实卡与数据表显示不同值）。
    """
    if '金额' in metric_name:
        return '#,##0.00'
    if _is_pct_point_col(metric_name):
        return _FMT_PCT_POINT
    if '率' in metric_name:
        return '0.00%'
    return '#,##0.###'


# ---------------------------------------------------------------- 预警等级列

def _add_severity_column(ws, hdr_row, headers, last_row):
    """给「无备注预警」表追加「预警等级」列（v43.249）。

    为什么在 post_process 做、而不是改 analyzer 的写表头：
      `analysis/analyzer.py` 是**红线区**（核心计算模块零改动）。而
      `analysis/excel_builder/sheet3_no_note.py` 的 build_sheet3 早已把等级算进
      DataFrame，只是 analyzer 写表时那张**写死的列清单**里没有它 → v43.243
      引入的严重度分级功能**从未落到 Excel 上**。post_process 是既定的「表现层
      后处理」，在这里补列既不动红线，也不改任何数值。

    等级怎么算：不用表内「偏差率」列 —— 它只保留 1 位小数（49.96 → '50.0%'），
    拿它判 50 这条线会误判一档；改用表内**数量列**重算
    |偏差率| = |偏差数量| / 定额 × 100（原始 float，无精度损失）。
    本 sheet 的行必然「定额 != 0」（定额=0 的行偏差率恒 100%，已被 !=100 规则
    排除在外），故除法安全。

    分档规则来自 `sheet3_no_note.severity_level`（**单一来源**，不重复实现）。
    """
    from analysis.excel_builder.sheet3_no_note import severity_level
    if '无备注预警' not in (ws.title or ''):
        return 0
    c_q = _find_col(headers, '定额')
    c_d = _find_col(headers, '偏差数量')
    if not c_q or not c_d:
        return 0
    map_ = _cells_of(ws)
    # 幂等：已有「预警等级」列就**就地重写**，不追加第二列。
    # （v43.249 初版只管追加，第二次调用 decorate_workbook 会多出一列 —— 已修）
    c_lv = _find_col(headers, '预警等级')
    if c_lv:
        col = c_lv
    else:
        col = ws.max_column + 1
        # 表头：复用本表首个表头单元格的样式（字体/填充/对齐/边框），保持版式一致
        hc = ws.cell(row=hdr_row, column=col, value='预警等级')
        ref = map_.get((hdr_row, 1))
        if ref is not None:
            try:
                hc._style = copy(ref._style)
            except Exception:
                pass
        else:
            hc.font = Font(bold=True, size=11)
            hc.alignment = Alignment(horizontal='center', vertical='center')
        ws.column_dimensions[get_column_letter(col)].width = 12

    rates = []
    rows = []
    for r in range(hdr_row + 1, last_row + 1):
        cq = map_.get((r, c_q))
        cd = map_.get((r, c_d))
        q = cq.value if cq is not None else None
        d = cd.value if cd is not None else None
        rows.append(r)
        if (not isinstance(q, (int, float)) or isinstance(q, bool) or not q
                or not isinstance(d, (int, float)) or isinstance(d, bool)):
            rates.append(float('nan'))
        else:
            rates.append(abs(float(d)) / abs(float(q)) * 100.0)
    if not rows:
        return 0
    levels = severity_level(rates)
    for r, lv in zip(rows, levels):
        cell = ws.cell(row=r, column=col, value=str(lv))
        cell.alignment = Alignment(horizontal='center')
    return len(rows)


def _extend_autofilter(ws, hdr_row, last_row):
    """把自动筛选的**末列**补到当前最大列（v43.249）。

    背景：builder 在写表时就设好了 `auto_filter`，但 post_process 之后还会给表
    **追加列** —— 完整偏差明细→「异常标记」、无备注预警/中间地带明细→「重复行」、
    无备注预警（v43.249）再→「预警等级」。而 autofilter 的范围是写死的旧宽度，
    追加的列落在筛选范围**之外**：点表头漏斗根本选不到它（实测 3 张表各短 1 列，
    加上预警等级后无备注预警会短 2 列）。

    只改末列，不动首行/末行；「📋 分析说明」页排除在外（它的筛选器是给 2 列
    说明块用的，把后面的事实卡列卷进来反而更难用）。
    """
    if '分析说明' in (ws.title or ''):
        return 0
    ref = ws.auto_filter.ref
    if not ref:
        return 0
    try:
        min_c, min_r, max_c, max_r = range_boundaries(ref)
    except Exception:
        return 0
    if ws.max_column <= max_c:
        return 0
    ws.auto_filter.ref = '%s%d:%s%d' % (
        get_column_letter(min_c), min_r, get_column_letter(ws.max_column), max_r)
    return 1


def _add_fact_cards(wb):
    """在「📋 分析说明」页追加「各表事实卡」区块：每张表的行数/列数/关键度量统计。

    设计约束（改本函数前先读）：
    1. **只统计、不改数**：所有数字取自各表**已渲染的单元格**（_cells_of），不重算
       任何业务口径 —— 这样「事实卡 = 表内数字」可逐格对账，不会两套算法打架。
    2. **口径文案复用**：直接读「各Sheet说明」区块里已有的说明文字，不另写一份，
       避免同一口径在两处说法不一致。
    3. **不新增 sheet**：sheet 数不变，下游按 sheet 名取数的报表（归藏报告/PPT）零影响。
    4. **幂等**：区块标题已存在则先删旧区块再重写。
    5. **非数值占位透明**：导出时把 0 写成 '-' 的行不计入统计，并在「统计备注」列写明
       跳过多少行，避免合计被误读成全量口径。
    """
    info_name = None
    for nm in wb.sheetnames:
        if '分析说明' in nm:
            info_name = nm
            break
    if not info_name:
        return 0
    ws_info = wb[info_name]
    map_ = _cells_of(ws_info)

    # 0) 读动态阈值（分析说明里有一行「动态阈值数值」=「±10.0%」）——
    #    下面修正文案要用同一个数字，**不写死 10**，免得与 GUI 改的阈值脱钩。
    thresh = None
    for (r, c), cell in map_.items():
        if c == 1 and isinstance(cell.value, str) \
                and cell.value.strip() == '动态阈值数值':
            bc = map_.get((r, 2))
            if bc is not None and isinstance(bc.value, str):
                m = re.search(r'(\d+(?:\.\d+)?)\s*%', bc.value)
                if m:
                    try:
                        thresh = float(m.group(1))
                    except ValueError:
                        thresh = None
            break

    # 1) 读「各Sheet说明」的口径文案（列A=表名 → 列B=说明），并记住所在行
    caliber = {}
    caliber_row = {}
    for (r, c), cell in map_.items():
        if c != 1:
            continue
        a = cell.value
        if not isinstance(a, str):
            continue
        a = a.strip()
        if not a or a.startswith(_FACT_MARKER) or a not in wb.sheetnames:
            continue
        bc = map_.get((r, 2))
        if bc is not None and isinstance(bc.value, str) and bc.value.strip():
            caliber[a] = bc.value.strip()
            if a not in caliber_row or r < caliber_row[a]:
                caliber_row[a] = r

    # 1b) v43.249：修正两处与实现不符的说明文案，并**回写**到「各Sheet说明」原行，
    #     使「说明区」与「事实卡口径列」两处说法一致（否则又是一处口径打架）。
    #     · 无备注预警：旧文案写「超过 ±10%」但实现是「≥」（含边界）；排序实为
    #       「预警等级→偏差金额绝对值降序」，旧文案却写「按偏差金额降序」。
    #     · 中间地带明细：旧文案写「在 ±10% 区间内」（闭区间），与无备注预警的 ≥
    #       边界重叠；v43.249 起改为开区间 < 10%，两边互补不双计。
    if thresh is not None:
        fixes = {
            '无备注预警': (
                '|偏差率| ≥ %.1f%% 且 ≠100%% 但未填备注原因的记录'
                '（按预警等级→偏差金额绝对值降序）' % thresh),
            '中间地带明细': (
                '|偏差率| < %.1f%% 的记录（不纳入汇总统计；'
                '|偏差率| ≥ %.1f%% 归入「无备注预警」）' % (thresh, thresh)),
        }
        for _nm, _txt in fixes.items():
            caliber[_nm] = _txt
            _r0 = caliber_row.get(_nm)
            if _r0:
                try:
                    ws_info.cell(row=_r0, column=2, value=_txt)
                except Exception as e:
                    _log('[post_process] 说明文案回写失败 %s: %s' % (_nm, e))
        # post_process 新增的表：口径说明补进来（说明块里没有它们的行）
        for _nm, _txt in _EXTRA_CALIBER.items():
            caliber.setdefault(_nm, _txt)

    # 2) 幂等：找到旧区块标题就整块删掉重写
    marker_row = None
    for (r, c), cell in map_.items():
        if c == 1 and isinstance(cell.value, str) \
                and cell.value.strip().startswith(_FACT_MARKER):
            marker_row = r
            break
    if marker_row:
        start = marker_row
        try:
            ws_info.delete_rows(marker_row, ws_info.max_row - marker_row + 1)
        except Exception as e:
            _log('[post_process] 事实卡旧区块删除失败: %s' % e)
            return 0
    else:
        start = ws_info.max_row + 2      # 空一行分隔

    # 3) 逐表统计
    cards = []
    for nm in wb.sheetnames:
        if nm == info_name or nm in _FACT_SKIP_SHEETS:
            continue
        ws = wb[nm]
        try:
            hdr_row, headers = _header_info(ws)
            last_row = _last_data_row(ws, hdr_row)
        except Exception:
            continue
        n_rows = last_row - hdr_row
        if n_rows <= 0:
            continue
        col = None
        actual = ''
        for cand in _FACT_METRIC_COLS:
            c_ = _find_col(headers, cand)
            if c_:
                col = c_
                actual = headers.get(c_) or cand
                break
        s = mx = mn = None
        n_num = n_skip = 0
        if col:
            s, mx, mn, n_num, n_skip = _fact_col_stats(ws, hdr_row, last_row, col)
        cards.append({
            'name': nm, 'rows': n_rows, 'cols': ws.max_column,
            'metric': actual, 'col': col,
            'sum': s, 'max': mx, 'min': mn, 'n_num': n_num, 'n_skip': n_skip,
            'caliber': caliber.get(nm, ''),
        })
    if not cards:
        return 0

    # 4) 写区块
    title = ws_info.cell(row=start, column=1, value=(
        '%s（导出后处理自动生成：行数/列数/度量统计均取自本工作簿各表已渲染单元格，'
        '可与表内数字逐格对账；口径沿用上方「各Sheet说明」，两处一致）' % _FACT_MARKER))
    title.font = Font(bold=True, size=12, color='1B5E20')
    title.alignment = Alignment(horizontal='left', vertical='center')
    ws_info.row_dimensions[start].height = 22

    hdr = start + 1
    heads = ['表名', '口径（与「各Sheet说明」一致）', '数据行数', '列数',
             '关键度量', '合计', '最大', '最小', '统计备注']
    for j, h in enumerate(heads, 1):
        c = ws_info.cell(row=hdr, column=j, value=h)
        c.font = Font(bold=True, size=10, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='1B5E20')
        c.alignment = Alignment(horizontal='center', vertical='center')
    ws_info.row_dimensions[hdr].height = 20

    r = hdr + 1
    for cd in cards:
        ws_info.cell(row=r, column=1, value=cd['name']).font = Font(bold=True, size=10)
        ws_info.cell(row=r, column=2, value=cd['caliber']).font = Font(size=9)
        ws_info.cell(row=r, column=3, value=int(cd['rows'])).font = Font(size=10)
        ws_info.cell(row=r, column=4, value=int(cd['cols'])).font = Font(size=10)
        ws_info.cell(row=r, column=5, value=cd['metric']).font = Font(size=10)
        if cd['col']:
            fmt = _fact_numfmt(cd['metric'])
            for j, v in ((6, cd['sum']), (7, cd['max']), (8, cd['min'])):
                cc = ws_info.cell(row=r, column=j,
                                  value=(None if v is None else round(float(v), 2)))
                cc.number_format = fmt
                cc.font = Font(size=10)
        else:
            for j in (6, 7, 8):
                cc = ws_info.cell(row=r, column=j, value='—')
                cc.font = Font(size=10, color='888888')
                cc.alignment = Alignment(horizontal='center')
        note = ''
        if cd['n_skip']:
            note = '另有 %d 行为非数值占位（"-"），未计入合计/最大/最小' % cd['n_skip']
        elif cd['col'] and cd['n_num'] < cd['rows']:
            note = '仅 %d/%d 行有数值' % (cd['n_num'], cd['rows'])
        ws_info.cell(row=r, column=9, value=note).font = Font(size=9, color='666666')
        r += 1

    tip = ws_info.cell(row=r, column=1, value=(
        '注：合计/最大/最小仅统计数值单元格；导出时把 0 写成 "-" 的占位行不计入，'
        '各表跳过行数见「统计备注」列（已逐表标注）。'))
    tip.font = Font(size=9, color='666666')
    tip.alignment = Alignment(horizontal='left', vertical='center')

    # 列宽：A/B 沿用分析说明既有版式（28/62），C-I 为本区块专用
    for letter, w in (('C', 11), ('D', 8), ('E', 20), ('F', 18),
                      ('G', 16), ('H', 16), ('I', 40)):
        ws_info.column_dimensions[letter].width = w
    return len(cards)


# ---------------------------------------------------------------- 未投料订单标记

def _add_unfed_flag(ws, hdr_row, headers, last_row):
    """给「完整偏差明细」追加「未投料订单」列（是/否）。已存在则跳过（幂等）。

    口径：某流程订单在明细里**所有行**的实际用量都是 0 → 该订单的所有行都标「是」。

    为什么必须在主明细里显式标记（v43.254）：
      这类订单整单零投料 —— 通常**产量已报**（虚报产量），且**原始备注原因为空**；
      偏差率恒为 -100%，既被「无备注预警」的「≠100%」规则排除，又在明细里
      没有任何提示，报表中完全隐形。实测本期 35 单、缺料金额 -332.40 万元，
      占全期总偏差 56.1%。标记后可在主表直接筛出这批订单。
    """
    if '未投料订单' in headers.values():
        return 0
    if '完整偏差明细' not in str(ws.title):
        return 0
    c_ord = _find_col(headers, '流程订单')
    c_act = _find_col(headers, '实际')
    if not c_ord or not c_act:
        return 0
    map_ = _cells_of(ws)

    def _v(r, col):
        c = map_.get((r, col))
        return None if c is None else c.value

    # 第一遍：每订单的总行数与「实际=0」行数
    tot = {}
    zero = {}
    for r in range(hdr_row + 1, last_row + 1):
        o = _v(r, c_ord)
        if o in (None, ''):
            continue
        o = str(o)
        tot[o] = tot.get(o, 0) + 1
        a = _v(r, c_act)
        if (isinstance(a, (int, float)) and not isinstance(a, bool)
                and abs(float(a)) <= 0.001):
            zero[o] = zero.get(o, 0) + 1
    unfed = set(o for o, t in tot.items() if t > 0 and zero.get(o, 0) == t)
    if not unfed:
        return 0

    col = ws.max_column + 1
    hc = ws.cell(row=hdr_row, column=col, value='未投料订单')
    try:
        from analysis.excel_builder.write_sheet_util import get_default_styles
        st = get_default_styles()
        hc.font = st['header_font']
        hc.fill = st['header_fill']
        hc.alignment = st['center']
    except Exception:
        hc.font = Font(bold=True, size=11, color='FFFFFF')
        hc.alignment = Alignment(horizontal='center', vertical='center')

    n = 0
    for r in range(hdr_row + 1, last_row + 1):
        o = _v(r, c_ord)
        if o in (None, ''):
            continue
        if str(o) in unfed:
            ws.cell(row=r, column=col, value='是')
            n += 1
    try:
        ws.column_dimensions[get_column_letter(col)].width = 12
    except Exception:
        pass
    return n


# ---------------------------------------------------------------- 入口

def decorate_workbook(wb, add_dashboard=True):
    """导出后处理总入口。返回统计 dict（便于日志/自测）。

    任何一步失败都不抛异常——美化问题绝不能阻断导出。
    """
    stats = {'sheets': 0, 'dates': 0, 'ids': 0, 'blanks': 0, 'flags': 0,
             'ratios': 0, 'dups': 0, 'charts': 0, 'cards': 0,
             'severity': 0, 'afilter': 0, 'unfed': 0, 'extra': 0,
             'resort': 0, 'trendfill': 0}
    if _is_skipped():
        _log('[post_process] 已按 ZPP011_SKIP_POST_PROCESS 跳过')
        return stats
    try:
        # v43.254：先建 5 张偏差分析扩展表（订单级汇总/车间维度/备注归类映射/
        # 系统问题与真实超耗/物料画像）—— 放在逐表流水线**之前**，这样它们能自动
        # 获得标准待遇（数字格式/冻结/自动筛选/条件格式），并自动进事实卡。
        # 延迟 import：新模块顶层 import 本模块，函数体内 import 才不会循环导入。
        try:
            from analysis.excel_builder.analysis_extra_sheets import build_extra_sheets
            stats['extra'] = len(build_extra_sheets(wb) or {})
        except Exception as e:
            _log('[post_process] 偏差分析扩展表失败: %s' % e)
        for ws in list(wb.worksheets):
            stats['sheets'] += 1
            try:
                hdr_row, headers = _header_info(ws)
                last_row = _last_data_row(ws, hdr_row)
            except Exception as e:
                _log('[post_process] 表头/末行解析失败 %s: %s' % (ws.title, e))
                continue
            ratio_cols = set()
            # 顺序有讲究：ratios 必须排在 flags 之后——flags 读的是**原始文本偏差率**，
            # 若先把 '19.60%' 转成 0.196，'abs(rt) >= 100' 就永远不成立，越界会全部漏标。
            steps = (
                ('layout', lambda: _apply_layout(ws, hdr_row, last_row), None),
                ('dates', lambda: _normalize_dates(ws, hdr_row, headers, last_row), 'dates'),
                ('ids', lambda: _normalize_text_ids(ws, hdr_row, headers, last_row), 'ids'),
                ('blanks', lambda: _normalize_empties(ws, hdr_row, last_row), 'blanks'),
                ('numfmt', lambda: _apply_number_formats(ws, hdr_row, headers, last_row), None),
                ('flags', lambda: _add_anomaly_flag(ws, hdr_row, headers, last_row), 'flags'),
                ('ratios', lambda: _normalize_ratio_columns(ws, hdr_row, headers, last_row), 'ratios'),
                ('condfmt', lambda: _apply_conditional_formats(
                    ws, hdr_row, headers, last_row, ratio_cols), None),
                # v43.249：给「无备注预警」补「预警等级」列（须在 dup 之前，
                # 使等级列排在「重复行」之前，版式更顺），并补齐 autofilter 末列
                ('severity', lambda: _add_severity_column(
                    ws, hdr_row, headers, last_row), 'severity'),
                # v43.254：给「完整偏差明细」标出「整单零投料」的订单（合并入口，
                # 不再单开一张表）。须在 dup 之前，标记列排在「重复行」之前。
                ('unfedflag', lambda: _add_unfed_flag(
                    ws, hdr_row, headers, last_row), 'unfed'),
                ('dup', lambda: _mark_duplicate_rows(ws, hdr_row, headers, last_row), 'dups'),
                ('afilter', lambda: _extend_autofilter(ws, hdr_row, last_row), 'afilter'),
            )
            for name, fn, key in steps:
                try:
                    n = fn()
                    if key == 'ratios':
                        d = n or {}
                        ratio_cols |= set(d.keys())
                        stats['ratios'] += sum(d.values())
                    elif key and isinstance(n, int):
                        stats[key] += n
                except Exception as e:
                    _log('[post_process] %s/%s 失败: %s' % (ws.title, name, e))
        if add_dashboard:
            try:
                stats['charts'] = _add_dashboard(wb)
            except Exception as e:
                _log('[post_process] 驾驶舱失败: %s' % e)
            # v43.283 规格 §3：驾驶舱升级独立于建页（_add_dashboard 幂等短路时
            # 页已存在，升级仍须执行——Top表/周趋势/页签色不因此缺失）
            try:
                _upgrade_dashboard(wb)
            except Exception as e:
                _log('[post_process] 驾驶舱升级失败: %s' % e)
        # v43.283 规格 §5：数据层降噪（放逐表流水线之后——汇总重排只搬
        # 值+样式，条件格式按列区间挂不受行序影响；趋势填—在 numfmt 之后
        # 才不会把 '—' 当数字处理）
        for _fn, _key in ((_resort_summary, 'resort'), (_denoise_trend_sheet, 'trendfill')):
            try:
                stats[_key] = _fn(wb)
            except Exception as e:
                _log('[post_process] %s 失败: %s' % (_fn.__name__, e))
        # v43.248：各表事实卡（可对账的统计摘要），写在「📋 分析说明」里
        try:
            stats['cards'] = _add_fact_cards(wb)
        except Exception as e:
            _log('[post_process] 事实卡失败: %s' % e)
    except Exception as e:
        _log('[post_process] 整体失败（已吞掉，不影响导出）: %s' % e)
    _log('[post_process] 完成 %s' % stats)
    return stats
