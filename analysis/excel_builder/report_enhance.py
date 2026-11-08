# -*- coding: utf-8 -*-
"""
report_enhance.py — 导出报表增强：可点击目录 + 每页回链 + 分厂左右分栏 + 就地嵌图

设计规格：docs/superpowers/specs/2026-10-28-export-factory-split-toc-design.md
决策记录：裴哥 2026-11-08 选方案 C（整份规格全做）。

设计约束（改本模块前先读）
--------------------------
1. **只做表现层，不改任何业务数值**：目录/回链只加超链接与文字；分栏只把已有
   数据行按工厂搬运到左/右块并复制样式，不重算、不聚合、不改任何一个值。
2. **不碰重聚合页**：设计规格 §1 里「偏差金额分析 / 趋势分析」要求从完整偏差明细
   按 (工厂×物料) 重聚合得到分厂数据源 —— 那是**重新计算业务口径**，违背
   「核心计算零改动 / 数值零幻觉」铁律，本模块明确不做，保留原样。
   「替代料明细」无工厂列、需订单号→工厂映射，同样跳过。
3. **每项独立 try**，任何一步失败只记日志，绝不阻断导出；分栏写入前先做整表
   快照，中途异常自动还原到分栏前状态（最坏情况=原表一字不变）。
4. **幂等**：重复 decorate 不叠加目录/回链/分栏/图。
5. **目录用 openpyxl 原生内部超链接**（cell.hyperlink = Hyperlink(location=...)），
   **不用 =HYPERLINK() 公式**：公式会把「各Sheet说明」A 列的纯表名变成公式文本，
   而 post_process._add_fact_cards 靠 `a in wb.sheetnames` 读口径文案 —— 一旦变成
   公式字符串，事实卡「口径」列会整片空掉。原生超链接的 cell.value 仍是纯文本，
   事实卡零影响。
6. **动态生成，无硬编码清单**：目录扫描实际 sheet 名；分栏扫描实际工厂数与
   工厂列位置；新增页自动进目录，单厂自动跳过分栏。
7. 逃生开关：环境变量 ZPP011_SKIP_REPORT_ENHANCE=1 整体跳过。
"""
import os
from copy import copy

from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.formatting import ConditionalFormattingList
from openpyxl.utils import get_column_letter

# 复用 post_process 的工具函数：post_process 在**函数体内**延迟 import 本模块，
# 所以这里顶层 import 它不会循环导入（与 analysis_extra_sheets.py 同一约定）。
from analysis.excel_builder.post_process import (
    _header_info, _cells_of, _find_col, _last_data_row, _log,
    _EXTRA_CALIBER,
)

_SKIP_ENV = 'ZPP011_SKIP_REPORT_ENHANCE'

# ── 目录 ────────────────────────────────────────────────────────────────
_TOC_MARKER = '📑 可点击目录'
_INFO_KEY = '分析说明'
_DASH_KEY = '驾驶舱'
_BACK_TEXT = '⬆ 目录'

# 三层分组（未列出的归「⚪ 数据」）；色点单独占一列，绝不写进 A 列表名 ——
# A 列必须是纯 sheet 名，_add_fact_cards 才认得。
_TIER_CONCLUSION = ('📊 驾驶舱', '汇总统计', '偏差原因汇总', '异常预警',
                    '系统问题与真实超耗', '翻箱守恒预警')
_TIER_ACTION = ('订单级汇总', '车间维度', '无备注预警')
_TIER_ORDER = ('🟢 结论', '🟠 派活', '⚪ 数据')

_FILL_SECTION = PatternFill('solid', fgColor='E8F5E9')   # 区块标题：浅绿
_FILL_CONCLUSION = PatternFill('solid', fgColor='F1F8E9')
_FILL_ACTION = PatternFill('solid', fgColor='FFF3E0')
_FILL_DATA = PatternFill('solid', fgColor='FAFAFA')
_FILL_SPLIT_HEAD = PatternFill('solid', fgColor='C8E6C9')  # 分栏块头
_THIN = Side(style='thin', color='BDBDBD')
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

# ── 分栏 ────────────────────────────────────────────────────────────────
# 只处理「有工厂列」的窄表；宽表/明细类不动（设计规格 §1 的 5+5 不拆清单）。
_SPLIT_MAX_COLS = 18
_SPLIT_MAX_ROWS = 2000
_SPLIT_SKIP_KEYS = ('完整偏差明细', '驾驶舱', '分析说明', '中间地带',
                    '异常预警', '无备注预警', '替代料明细', '备注归类映射',
                    '翻箱守恒预警', '翻箱组件明细', '趋势分析', '偏差金额分析',
                    # v43.324：饮料翻箱两表保持单块全表可筛选（含「工厂」列的窄表，
                    # 且主表一单一行、明细一行一组件，分栏会把容器数口径打散）。
                    '饮料翻箱守恒', '饮料翻箱组件明细')
_FACTORY_COLS = ('工厂名称', '工厂')
_FOOD_KEYS = ('食品', '1101')
_BEVERAGE_KEYS = ('饮料', '1102')
# 分栏页 A1 横幅前缀：既是版式标识，也是 _already_split 的幂等判据
_SPLIT_BANNER = '分厂对照'


def _skip():
    return str(os.environ.get(_SKIP_ENV, '') or '').strip().lower() in (
        '1', 'true', 'yes', 'on')


def _info_sheet(wb):
    for nm in wb.sheetnames:
        if _INFO_KEY in nm:
            return wb[nm]
    return None


def _hyperlink_to(cell, target_sheet, anchor='A1', tooltip=None):
    """给单元格挂一个指向工作簿内其他 sheet 的**原生内部超链接**。

    value 不变（保持纯文本），只设 hyperlink 属性；location 用单引号包住表名，
    兼容含 emoji / 中文括号 / 空格的 sheet 名。幂等：重复设置只是覆盖同一属性。
    """
    try:
        cell.hyperlink = Hyperlink(
            ref=cell.coordinate,
            location="'%s'!%s" % (target_sheet, anchor),
            display=str(cell.value) if cell.value is not None else target_sheet,
            tooltip=tooltip or ('跳到 %s' % target_sheet))
        cell.font = Font(size=11, color='1565C0', underline='single', bold=True)
    except Exception as e:
        _log('[report_enhance] 超链接设置失败 %s: %s' % (cell.coordinate, e))


def _tier_of(name):
    if name in _TIER_CONCLUSION:
        return '🟢 结论'
    if name in _TIER_ACTION:
        return '🟠 派活'
    return '⚪ 数据'


# ============================================================ 目录 + 回链
def build_toc(wb):
    """返回 dict：{'toc': 目录条数, 'info_links': 说明区链接数}。

    放在 decorate_workbook **最后** 调用（_add_fact_cards 之后），此时所有建表
    阶段（扩展表/翻箱表/驾驶舱）都已完成，扫描到的 sheet 清单才是最终态。
    """
    out = {'toc': 0, 'info_links': 0}
    if _skip():
        return out
    ws_info = _info_sheet(wb)
    if ws_info is None:
        return out

    # ① 「各Sheet说明」区：给已有的纯表名加超链接（不改 value，事实卡零影响）。
    #    严格限定在「各Sheet说明」标题行之后、事实卡/目录标记之前 ——
    #    否则会误给事实卡区块里的表名也加链接（那不是导航区）。
    try:
        map_ = _cells_of(ws_info)
        title_row, end_row = None, ws_info.max_row + 1
        for (r, c), cell in map_.items():
            if c == 1 and isinstance(cell.value, str) and cell.value.strip() == '各Sheet说明':
                title_row = r
        for (r, c), cell in map_.items():
            if c == 1 and isinstance(cell.value, str) and title_row and r > title_row:
                s = cell.value.strip()
                if s.startswith('各表事实卡') or s == _TOC_MARKER:
                    end_row = min(end_row, r)
        for (r, c), cell in map_.items():
            if c != 1 or not isinstance(cell.value, str):
                continue
            if title_row is None or not (title_row < r < end_row):
                continue
            name = cell.value.strip()
            if name and name in wb.sheetnames and name != ws_info.title:
                _hyperlink_to(cell, name)
                out['info_links'] += 1
    except Exception as e:
        _log('[report_enhance] 说明区超链接失败: %s' % e)

    # ② 追加「📑 可点击目录」区块（幂等：先删旧块再写）
    try:
        # 幂等删除
        marker_row = None
        for (r, c), cell in _cells_of(ws_info).items():
            if c == 1 and isinstance(cell.value, str) \
                    and cell.value.strip() == _TOC_MARKER:
                marker_row = r
                break
        if marker_row:
            ws_info.delete_rows(marker_row, ws_info.max_row - marker_row + 1)
        start = ws_info.max_row + 2

        title = ws_info.cell(row=start, column=1, value=_TOC_MARKER)
        title.font = Font(bold=True, size=12, color='1B5E20')
        title.fill = _FILL_SECTION
        ws_info.row_dimensions[start].height = 22

        hdr = start + 1
        for col, txt in ((1, '工作表'), (2, '说明'), (3, '层级'), (4, '数据行')):
            c = ws_info.cell(row=hdr, column=col, value=txt)
            c.font = Font(bold=True, size=10)
            c.fill = _FILL_SECTION
            c.border = _BORDER

        # 口径文案：说明区原文 + post_process 给新增页补的 _EXTRA_CALIBER
        caliber = {}
        for (r, c), cell in _cells_of(ws_info).items():
            if c == 1 and isinstance(cell.value, str) and cell.value.strip() in wb.sheetnames:
                bc = _cells_of(ws_info).get((r, 2))
                if bc is not None and isinstance(bc.value, str) and bc.value.strip():
                    caliber.setdefault(cell.value.strip(), bc.value.strip())
        for nm, txt in _EXTRA_CALIBER.items():
            caliber.setdefault(nm, txt)
        caliber.setdefault('翻箱守恒预警',
                           'ZPFX 翻箱单净含量守恒校验：产出KG vs 投入食物KG，'
                           '差额为正=疑似拆包投入漏记。')
        caliber.setdefault('翻箱组件明细',
                           'ZPFX 翻箱单一行一组件（含包材/零用量组件），列齐产品物料编码、'
                           '组件物料编码与名称；「是否计入食物投入」+「计入KG(参考)」可逐单'
                           '对账到「翻箱守恒预警」的投入食物合计KG。')
        # v43.324：饮料厂（1102）翻箱按「总容器数守恒」，与食品厂 KG 口径分列。
        # 目录文案随 sheet 动态扫描（names 取自 wb.sheetnames），此处只补说明文字，
        # 不硬编码表数；无饮料 ZPFX 时这两张表不生成，setdefault 不会凭空造目录项。
        caliber.setdefault('饮料翻箱守恒',
                           '饮料厂（1102/云南达利-饮料厂）ZPFX 翻箱单按「总容器数守恒」校验：'
                           '差 = 产出件数×单件容器数 − Σ(投入件数×单件容器数)；差>0 疑似漏记、'
                           '差≤0 守恒/正常。不比件数、不比KG、不做 ml↔g 密度折算；'
                           '只认 Z008 成品投入，规格解析不出或容器形式/单位不一致→待人工确认。')
        caliber.setdefault('饮料翻箱组件明细',
                           '饮料厂 ZPFX 翻箱单一行一组件（含 Z005 半成品/Z002 包材/Z001 原辅料等'
                           '被排除行，全部在「排除原因」留痕，不静默丢行）；「是否计入容器数」'
                           '+「计入容器数(参考)」与主表同源（_drink_container_of），可逐单对账到'
                           '「饮料翻箱守恒」的投入总容器数。')
        caliber.setdefault('📊 驾驶舱', '全期 KPI 与分厂 Top 榜、周趋势双线图。')

        names = [nm for nm in wb.sheetnames if nm != ws_info.title]
        names.sort(key=lambda n: (_TIER_ORDER.index(_tier_of(n)), wb.sheetnames.index(n)))

        r = hdr + 1
        for nm in names:
            tier = _tier_of(nm)
            c1 = ws_info.cell(row=r, column=1, value=nm)
            _hyperlink_to(c1, nm)
            c2 = ws_info.cell(row=r, column=2, value=caliber.get(nm, ''))
            c2.alignment = Alignment(vertical='center', wrap_text=True)
            ws_info.cell(row=r, column=3, value=tier)
            c4 = ws_info.cell(row=r, column=4)
            try:
                ws = wb[nm]
                hr, _ = _header_info(ws)
                c4.value = max(0, _last_data_row(ws, hr) - hr)
            except Exception:
                c4.value = ''
            fill = {'🟢 结论': _FILL_CONCLUSION, '🟠 派活': _FILL_ACTION,
                    '⚪ 数据': _FILL_DATA}[tier]
            for col in (1, 2, 3, 4):
                cc = ws_info.cell(row=r, column=col)
                cc.fill = fill
                cc.border = _BORDER
            ws_info.row_dimensions[r].height = 20
            r += 1
            out['toc'] += 1

        ws_info.column_dimensions['A'].width = max(28, ws_info.column_dimensions['A'].width or 0)
        ws_info.column_dimensions['B'].width = max(62, ws_info.column_dimensions['B'].width or 0)
        ws_info.column_dimensions['C'].width = 11
        ws_info.column_dimensions['D'].width = 9
    except Exception as e:
        _log('[report_enhance] 目录区块失败: %s' % e)

    return out


def build_backlinks(wb):
    """每页表头行右侧空一格写「⬆ 目录」回链。返回 {'back': n}。

    必须在 **_add_fact_cards 之前** 调用：回链会新增一列，若放在事实卡之后，
    第二次 decorate 时事实卡统计到的「列数」会比第一次多 2，产生幂等漂移
    （实测 10 张事实卡的列数 16→18 / 8→10）。提前后两次统计一致。
    """
    out = {'back': 0}
    if _skip():
        return out
    ws_info = _info_sheet(wb)
    target = ws_info.title if ws_info is not None else '📋 分析说明'
    try:
        for ws in wb.worksheets:
            if ws.title == target or _DASH_KEY in ws.title:
                continue
            try:
                hr, _headers = _header_info(ws)
                # 幂等：已存在则只更新链接，不新增列
                exist = None
                for (rr, cc), cell in _cells_of(ws).items():
                    if rr == hr and isinstance(cell.value, str) \
                            and cell.value.strip() == _BACK_TEXT:
                        exist = cc
                        break
                col = exist if exist else ws.max_column + 2
                c = ws.cell(row=hr, column=col, value=_BACK_TEXT)
                c.hyperlink = Hyperlink(
                    ref=c.coordinate,
                    location="'%s'!A%d" % (target, 2),
                    display=_BACK_TEXT, tooltip='回到 分析说明')
                c.font = Font(size=10, color='1565C0', underline='single', bold=True)
                c.alignment = Alignment(horizontal='center')
                out['back'] += 1
            except Exception as e:
                _log('[report_enhance] 回链失败 %s: %s' % (ws.title, e))
    except Exception as e:
        _log('[report_enhance] 回链阶段失败: %s' % e)
    return out


def build_toc_and_backlinks(wb):
    """兼容包装：一次做完目录 + 回链（顺序不影响正确性，幂等同样成立）。"""
    a = build_toc(wb)
    b = build_backlinks(wb)
    a.update(b)
    return a


# ============================================================ 分厂左右分栏
def _detect_factories(wb):
    """从「完整偏差明细」读工厂列的唯一值；返回 (列号, [值...]) 或 (None, [])。"""
    for nm in ('完整偏差明细', '汇总统计', '车间维度'):
        if nm not in wb.sheetnames:
            continue
        ws = wb[nm]
        hr, headers = _header_info(ws)
        fc = _find_col(headers, *_FACTORY_COLS)
        if not fc:
            continue
        vals = []
        for (r, c), cell in _cells_of(ws).items():
            if c == fc and r > hr:
                v = cell.value
                if v not in (None, '') and v not in vals:
                    vals.append(v)
        if len(vals) >= 2:
            return fc, vals
    return None, []


def _factory_side(v):
    """把工厂值归到「食品 / 饮料」两侧；无法归类的进食品侧（保守，不丢行）。"""
    s = str(v)
    if any(k in s for k in _BEVERAGE_KEYS):
        return '饮料'
    return '食品'


def _snapshot(ws):
    """整表快照：值 + 样式 + 数字格式 + 超链接，供分栏失败时还原。"""
    snap = []
    for (r, c), cell in _cells_of(ws).items():
        snap.append((r, c, cell.value, copy(cell._style), cell.number_format,
                     cell.hyperlink, cell.alignment, cell.font, cell.fill,
                     cell.border, cell.protection))
    return snap, list(ws.merged_cells.ranges), len(ws.conditional_formatting), \
        list(ws._charts), ws.auto_filter.ref, ws.freeze_panes


def _restore(ws, snap):
    """把 ws 还原到快照状态（清空现有内容后按快照重写）。"""
    rows, merges, charts, afilter, freeze = snap[0], snap[1], snap[3], \
        snap[4], snap[5]
    try:
        ws.delete_rows(1, max(ws.max_row, 1))
    except Exception:
        pass
    for (r, c, v, st, _nf, hl, _al, _fo, _fi, _bo, _pr) in rows:
        cell = ws.cell(row=r, column=c, value=v)
        try:
            cell._style = copy(st)
        except Exception:
            pass
        if hl is not None:
            cell.hyperlink = hl
    for mc in merges:
        try:
            ws.merge_cells(str(mc))
        except Exception:
            pass
    ws.auto_filter.ref = afilter
    ws.freeze_panes = freeze
    for ch in charts:
        try:
            ws.add_chart(ch)
        except Exception:
            pass


def _already_split(ws, hdr_row, headers):
    """幂等判据：已左右分栏过 —— **只认 A1 横幅前缀**（本模块写的稳定标记）。

    分栏后第 1 行是「一整条合并横幅」（只有 A1 一个非空格），第 2 行才是
    左右两块表头，故既不依赖 _header_info 的返回值，也不需要额外兜底。

    ⚠️ 历史坑 1：旧版式把两个块头写在第 1 行（2 个非空格），_header_info
       会把第 1 行误判成表头行，「重复表头名」判据随之失效 —— 实测第 2 次
       decorate 有 4 张表被重复分栏。改为合并横幅后表头自然落回第 2 行。
    ⚠️ 历史坑 2：曾加过「扫第 1/2 行重复文本」兜底，结果**未分栏表的第 2 行
       是数据行**，相同车间/日期/0 等重复值极常见，被误判成已分栏 —— 双厂
       7 张窄表只分了 3 张。兜底必须删掉，绝不扫数据行。
    """
    a1 = ws.cell(1, 1).value
    return isinstance(a1, str) and a1.strip().startswith(_SPLIT_BANNER)


def build_factory_views(wb):
    """7 张窄表按工厂左右分栏 + 每块一张 BarChart。

    工厂数 < 2 时整体跳过（单厂绝不画空右栏）。返回统计 dict。
    放在 decorate_workbook 里 **_add_fact_cards 之前** 调用。
    """
    out = {'split': 0, 'charts': 0, 'factories': 0, 'skipped': 0}
    if _skip():
        return out
    fc, factories = _detect_factories(wb)
    out['factories'] = len(factories)
    if len(factories) < 2:
        _log('[report_enhance] 工厂数 %d < 2，跳过分栏（不画空右栏）' % len(factories))
        return out

    labels = ('食品厂', '饮料厂')
    for ws in list(wb.worksheets):
        try:
            if any(k in ws.title for k in _SPLIT_SKIP_KEYS):
                out['skipped'] += 1
                continue
            # 幂等判据放最前：已分栏的静态表直接跳过，不依赖下面
            # ncols > _SPLIT_MAX_COLS 的巧合（分栏后列数翻倍会误打误撞挡住）。
            # ⚠️ build_extra_sheets 每次 decorate 都会 del+create 重建 4 张动态
            # 扩展表（订单级汇总/车间维度/物料画像/产品维度），它们是全新的
            # 原始表 → 每次都会重新分栏一次。这是 v43.254 既有架构行为，
            # 最终形态不叠加（图表数/目录/回链均不增长），不是重复分栏 bug。
            if _already_split(ws, 1, {}):
                out['skipped'] += 1
                continue
            hr, headers = _header_info(ws)
            last = _last_data_row(ws, hr)
            ncols = ws.max_column
            if ncols > _SPLIT_MAX_COLS or last - hr > _SPLIT_MAX_ROWS:
                out['skipped'] += 1
                continue
            factory_col = _find_col(headers, *_FACTORY_COLS)
            if not factory_col or factory_col > ncols:
                out['skipped'] += 1
                continue

            # 读全部数据行（值+样式），按工厂分两侧
            map_ = _cells_of(ws)
            head_vals = [(c, map_.get((hr, c)).value if map_.get((hr, c)) else '')
                         for c in range(1, ncols + 1)]
            groups = {'食品': [], '饮料': []}
            for r in range(hr + 1, last + 1):
                fv = map_.get((r, factory_col))
                side = _factory_side(fv.value if fv is not None else '')
                row = []
                for c in range(1, ncols + 1):
                    cell = map_.get((r, c))
                    row.append((cell.value, copy(cell._style) if cell else None))
                groups[side].append(row)
            if not groups['食品'] or not groups['饮料']:
                out['skipped'] += 1
                continue

            snap = _snapshot(ws)
            try:
                # 清页（保留列宽）
                ws.delete_rows(1, max(ws.max_row, 1))
                ws.conditional_formatting = ConditionalFormattingList()
                ws._charts = []
                for mc in list(ws.merged_cells.ranges):
                    try:
                        ws.unmerge_cells(str(mc))
                    except Exception:
                        pass
                ws.auto_filter.ref = None

                right_start = ncols + 2          # 中间空 1 列
                # 横幅：整条合并，第 1 行只剩 A1 一个非空格 —— 让 _header_info
                # 自然把第 2 行认作表头（旧版两个块头让第 1 行有 2 个非空格，
                # 会被误判成表头行，连带回链落点/事实卡列名/目录数据行全错位）。
                banner_last = right_start + ncols - 1
                banner = ws.cell(
                    row=1, column=1,
                    value='%s · %s（%d 行）　｜　%s（%d 行）' % (
                        _SPLIT_BANNER, labels[0], len(groups['食品']),
                        labels[1], len(groups['饮料'])))
                banner.font = Font(bold=True, size=12, color='1B5E20')
                banner.fill = _FILL_SPLIT_HEAD
                banner.alignment = Alignment(horizontal='center', vertical='center')
                ws.merge_cells(start_row=1, start_column=1,
                               end_row=1, end_column=banner_last)
                ws.row_dimensions[1].height = 24
                for idx, side in enumerate(('食品', '饮料')):
                    base = 1 if idx == 0 else right_start
                    # 表头
                    for off, (c, hv) in enumerate(head_vals):
                        cc = ws.cell(row=2, column=base + off, value=hv)
                        cc.font = Font(bold=True, size=10)
                        cc.fill = _FILL_SECTION
                        cc.border = _BORDER
                    # 数据
                    for ri, row in enumerate(groups[side], start=3):
                        for off, (v, st) in enumerate(row):
                            cc = ws.cell(row=ri, column=base + off, value=v)
                            if st is not None:
                                try:
                                    cc._style = copy(st)
                                except Exception:
                                    pass
                            cc.border = _BORDER
                    # 小计行（只对比值合计，纯展示，不改原数）
                    srow = 3 + len(groups[side])
                    sc = ws.cell(row=srow, column=base, value='小计')
                    sc.font = Font(bold=True, size=10)
                    sc.fill = _FILL_SPLIT_HEAD

                    # 每块一张 BarChart：取块内第一个数值列做 Top 条形图
                    try:
                        chart_col = None
                        for off, (c, hv) in enumerate(head_vals):
                            hname = str(hv or '')
                            if any(k in hname for k in ('金额', '数量', '条数')) \
                                    and '率' not in hname and '占比' not in hname:
                                chart_col = off
                                break
                        if chart_col is not None:
                            n = min(10, len(groups[side]))
                            data = Reference(ws, min_col=base + chart_col,
                                             min_row=2, max_row=2 + n)
                            cats = Reference(ws, min_col=base,
                                             min_row=3, max_row=2 + n)
                            ch2 = BarChart()
                            ch2.type = 'bar'
                            ch2.title = '%s · %s Top10' % (labels[idx],
                                        str(head_vals[chart_col][1] or '数值'))
                            ch2.height, ch2.width = 6, 12
                            ch2.add_data(data, titles_from_data=True)
                            ch2.set_categories(cats)
                            ch2.legend = None
                            ws.add_chart(ch2, '%s%d' % (
                                get_column_letter(base), srow + 2))
                            out['charts'] += 1
                    except Exception as e:
                        _log('[report_enhance] 嵌图失败 %s/%s: %s' % (ws.title, side, e))

                # 列宽：右块沿用左块
                for off in range(ncols):
                    src = get_column_letter(1 + off)
                    dst = get_column_letter(right_start + off)
                    w = ws.column_dimensions[src].width
                    if w:
                        ws.column_dimensions[dst].width = w
                ws.freeze_panes = 'A3'
                # autofilter 只罩左块（Excel 每 sheet 单筛选区限制）
                ws.auto_filter.ref = 'A2:%s%d' % (
                    get_column_letter(ncols), 2 + len(groups['食品']))

                out['split'] += 1
            except Exception as e:
                _log('[report_enhance] 分栏失败 %s，还原原表: %s' % (ws.title, e))
                try:
                    _restore(ws, snap)
                except Exception as e2:
                    _log('[report_enhance] 还原也失败 %s: %s' % (ws.title, e2))
                out['skipped'] += 1
        except Exception as e:
            _log('[report_enhance] 分栏阶段异常 %s: %s' % (ws.title, e))
            out['skipped'] += 1
    return out


def build_all(wb):
    """总入口（若调用方只想接一行）。分栏需 _add_fact_cards 之前、目录需之后，
    故推荐分别调用；此入口仅用于不介意顺序的场景。"""
    if _skip():
        return {'split': 0, 'charts': 0, 'factories': 0, 'skipped': 0,
                'toc': 0, 'info_links': 0, 'back': 0}
    a = build_factory_views(wb)
    b = build_toc_and_backlinks(wb)
    a.update(b)
    return a
