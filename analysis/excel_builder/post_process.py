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

from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
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
_COUNT_KEYS = ('条数', '总数量', '数量', '定额', '实际')

# 比率字段（这些列在源表里是文本 '19.60%'，需转真数值）
_RATIO_KEYS = ('率', '占比')

_FMT_DATE = 'yyyy-mm-dd'
_FMT_AMOUNT = '#,##0.00'
_FMT_COUNT = '#,##0.###'
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


def _apply_number_formats(ws, hdr_row, headers, last_row):
    """按列名套数字格式。只改 number_format，保留字体/填充/边框等其它样式。"""
    specs = []
    for col, name in headers.items():
        if not name:
            continue
        if any(k in name for k in _DATE_KEYS):
            specs.append((col, _FMT_DATE))
        elif any(k in name for k in _AMOUNT_KEYS):
            specs.append((col, _FMT_AMOUNT))
        elif any(k in name for k in _COUNT_KEYS):
            specs.append((col, _FMT_COUNT))
    if not specs:
        return
    map_ = _cells_of(ws)
    for col, fmt in specs:
        for r in range(hdr_row + 1, last_row + 1):
            c = map_.get((r, col))
            if c is None or c.value in (None, ''):
                continue
            if str(c.number_format) != fmt:
                c.number_format = fmt


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
    """新建「📊 驾驶舱」页，集中 3 张图。已存在则跳过（幂等）。"""
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
                ws_dash.add_chart(ch, 'B4')
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
                ws_dash.add_chart(ch, 'B24')
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
                ws_dash.add_chart(ch, 'B50')
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


# ---------------------------------------------------------------- 入口

def decorate_workbook(wb, add_dashboard=True):
    """导出后处理总入口。返回统计 dict（便于日志/自测）。

    任何一步失败都不抛异常——美化问题绝不能阻断导出。
    """
    stats = {'sheets': 0, 'dates': 0, 'ids': 0, 'blanks': 0, 'flags': 0,
             'ratios': 0, 'dups': 0, 'charts': 0}
    if _is_skipped():
        _log('[post_process] 已按 ZPP011_SKIP_POST_PROCESS 跳过')
        return stats
    try:
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
                ('dup', lambda: _mark_duplicate_rows(ws, hdr_row, headers, last_row), 'dups'),
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
    except Exception as e:
        _log('[post_process] 整体失败（已吞掉，不影响导出）: %s' % e)
    _log('[post_process] 完成 %s' % stats)
    return stats
