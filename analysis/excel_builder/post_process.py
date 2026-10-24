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
    '完全未投料订单': (
        '某流程订单在「完整偏差明细」里所有组件行的实际用量均为 0（该单完全没投料）。'
        '这类订单通常产量已报、实际零投料（虚报产量），且**原始备注原因为空** → '
        '本应进「无备注预警」，却因偏差率恒为 -100% 被「≠100%」规则排除，报表里根本看不到。'
        '⚠️ 本表**不含偏差金额列**：「完整偏差明细」的金额用「实际单价反算法」'
        '（sheet5_full.py：金额-实际(含税) ÷ 数量-实际），未投料行数量-实际=0 → 单价反算失败 '
        '→ 金额被整列清零，故工作簿内取不到订单粒度的真实金额；整单缺口金额需回 SAP 源表，'
        '或修正该算法后再由本表补上。「实际数量合计」恒为 0，是判定结果本身。'),
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


# ---------------------------------------------------------------- 完全未投料订单

# 判定「实际用量为 0」的容差（与项目其它处一致：|实际| <= 0.001 视作 0）
_ZERO_TOL = 0.001


def _add_unfed_orders_sheet(wb):
    """新增「完全未投料订单」表：列出**所有组件实际用量全为 0** 的流程订单。

    为什么需要这张表（v43.253）：
      这类订单最严重 —— 通常**产量已报、实际却零投料**，属「虚报产量」；
      而且它们往往**已经填了备注原因**，所以现有的「无备注预警」「异常预警」
      都不会突出它 → 报表里根本看不出这个系统性问题。
      实测（2026-10-01~10-23，9268 行）：**35 单** / 82 行明细 / 偏差金额
      **-332.40 万元**，占全期总偏差（-592.91 万）的 **56.1%**；且 35 单
      **全部报产但没投料**。

    口径：某流程订单在「完整偏差明细」里**所有组件行的实际用量都是 0**。
    数据源只用「完整偏差明细」+「替代料明细」（取其订单号集合，用于标注
    「是否含替代料」）—— **不改任何业务数值、不碰 analyzer.py 红线**。

    误判/漏判实测均为 0（这 35 单既不含「实际>0 且材料偏差=0」的正常行，
    也不含被完整明细剔除的替代料行）。

    ⚠️ **本表不含偏差金额列**：「完整偏差明细」的金额是「实际单价反算法」
    （sheet5_full.py：金额-实际(含税) ÷ 数量-实际），未投料行数量-实际=0 →
    单价反算失败 → 金额被整列清零，工作簿内取不到订单粒度真实金额。
    修 sheet5_full 的该算法（未投料行改用 -金额-定额(含税)）后，本表即可补金额列；
    本表也不含产量列（产量只在 SAP 源表），「是否报产」需回源表核对。
    """
    src_name = '完整偏差明细'
    if src_name not in wb.sheetnames:
        return 0
    src = wb[src_name]
    try:
        hdr_row, headers = _header_info(src)
        last_row = _last_data_row(src, hdr_row)
    except Exception as e:
        _log('[post_process] 完全未投料订单：源表解析失败 %s' % e)
        return 0
    c_ord = _find_col(headers, '流程订单')
    c_act = _find_col(headers, '实际')
    if not c_ord or not c_act:
        return 0
    c_q = _find_col(headers, '定额')
    c_qty = _find_col(headers, '偏差数量')
    c_date = _find_col(headers, '订单日期')
    c_type = _find_col(headers, '订单类型')
    c_fac = _find_col(headers, '工厂')
    c_ws = _find_col(headers, '车间')
    c_pno = _find_col(headers, '产品物料号码')
    c_pde = _find_col(headers, '产品物料描述')
    c_mcode = _find_col(headers, '物料编码')
    c_note = _find_col(headers, '备注')

    map_ = _cells_of(src)

    def _v(r, col):
        if not col:
            return None
        c = map_.get((r, col))
        return c.value if c is not None else None

    def _num(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        return float(v)

    # 按订单聚合
    orders = {}
    for r in range(hdr_row + 1, last_row + 1):
        o = _v(r, c_ord)
        if o in (None, ''):
            continue
        o = str(o)
        a = _num(_v(r, c_act))
        if a is None:
            a = 0.0
        d = orders.setdefault(o, {
            'rows': 0, 'zero': 0, 'q': 0.0, 'qty': 0.0, 'mats': set(),
            'notes': set(), 'date': _v(r, c_date), 'type': _v(r, c_type),
            'fac': _v(r, c_fac), 'ws': _v(r, c_ws),
            'pno': _v(r, c_pno), 'pde': _v(r, c_pde),
        })
        d['rows'] += 1
        if abs(a) <= _ZERO_TOL:
            d['zero'] += 1
        qv = _num(_v(r, c_q))
        if qv is not None:
            d['q'] += qv
        dv = _num(_v(r, c_qty))
        if dv is not None:
            d['qty'] += dv
        if c_mcode:
            mv = _v(r, c_mcode)
            if mv not in (None, ''):
                d['mats'].add(str(mv))
        if c_note:
            nv = _v(r, c_note)
            if nv not in (None, '') and str(nv).strip() not in ('nan', 'None'):
                d['notes'].add(str(nv).strip())

    unfed = [(o, d) for o, d in orders.items()
             if d['rows'] > 0 and d['zero'] == d['rows']]
    if not unfed:
        return 0
    unfed.sort(key=lambda kv: kv[1]['qty'])   # 偏差数量小（缺料少）的在前

    # 含替代料的订单（替代料明细有订单号列）
    alt_ords = set()
    if '替代料明细' in wb.sheetnames:
        try:
            a2 = wb['替代料明细']
            h2, hd2 = _header_info(a2)
            l2 = _last_data_row(a2, h2)
            c_o2 = _find_col(hd2, '订单号', '流程订单')
            m2 = _cells_of(a2)
            if c_o2:
                for r in range(h2 + 1, l2 + 1):
                    cc = m2.get((r, c_o2))
                    if cc is not None and cc.value not in (None, ''):
                        alt_ords.add(str(cc.value).strip())
        except Exception as e:
            _log('[post_process] 完全未投料订单：替代料明细读取失败 %s' % e)

    name = '完全未投料订单'
    if name in wb.sheetnames:
        try:
            del wb[name]
        except Exception:
            return 0
    ws = wb.create_sheet(name)
    heads = ['流程订单', '订单日期', '工厂', '车间', '订单类型', '产品物料号码',
             '产品物料描述', '组件行数', '组件数(去重)', '定额数量合计',
             '实际数量合计', '偏差数量合计', '是否含替代料', '是否有备注', '备注原因']
    for j, h in enumerate(heads, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = Font(bold=True, size=11)
        c.alignment = Alignment(horizontal='center', vertical='center')
    r = 2
    for o, d in unfed:
        vals = [
            o, d['date'], d['fac'], d['ws'], d['type'], d['pno'], d['pde'],
            d['rows'], len(d['mats']), round(d['q'], 3), 0.0,
            round(d['qty'], 3),
            '是' if o in alt_ords else '否',
            '有' if d['notes'] else '无',
            ' / '.join(sorted(d['notes'])),
        ]
        for j, v in enumerate(vals, 1):
            ws.cell(row=r, column=j, value=v)
        r += 1
    # ⚠️ 这里**不能**在数据区下方加说明行：_last_data_row 只探前 8 列，
    # 说明行会被当成数据行（35 变 36），连带事实卡的「数据行数」也错。
    # 口径说明统一放进「📋 分析说明」页的事实卡口径列（见 _EXTRA_CALIBER），
    # 与其它表的口径同处一处，不两处打架。
    for letter, w in (('A', 14), ('B', 12), ('C', 18), ('D', 16), ('E', 10),
                      ('F', 13), ('G', 30), ('H', 9), ('I', 11), ('J', 14),
                      ('K', 13), ('L', 14), ('M', 11), ('N', 11), ('O', 40)):
        ws.column_dimensions[letter].width = w
    return len(unfed)


# ---------------------------------------------------------------- 入口

def decorate_workbook(wb, add_dashboard=True):
    """导出后处理总入口。返回统计 dict（便于日志/自测）。

    任何一步失败都不抛异常——美化问题绝不能阻断导出。
    """
    stats = {'sheets': 0, 'dates': 0, 'ids': 0, 'blanks': 0, 'flags': 0,
             'ratios': 0, 'dups': 0, 'charts': 0, 'cards': 0,
             'severity': 0, 'afilter': 0, 'unfed': 0}
    if _is_skipped():
        _log('[post_process] 已按 ZPP011_SKIP_POST_PROCESS 跳过')
        return stats
    try:
        # v43.253：先建「完全未投料订单」表 —— 放在逐表流水线**之前**，
        # 这样它能自动获得标准待遇（数字格式/冻结/自动筛选/条件格式），
        # 并自动出现在「📋 分析说明」的事实卡区块里。
        try:
            stats['unfed'] = _add_unfed_orders_sheet(wb)
        except Exception as e:
            _log('[post_process] 完全未投料订单表失败: %s' % e)
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
        # v43.248：各表事实卡（可对账的统计摘要），写在「📋 分析说明」里
        try:
            stats['cards'] = _add_fact_cards(wb)
        except Exception as e:
            _log('[post_process] 事实卡失败: %s' % e)
    except Exception as e:
        _log('[post_process] 整体失败（已吞掉，不影响导出）: %s' % e)
    _log('[post_process] 完成 %s' % stats)
    return stats
