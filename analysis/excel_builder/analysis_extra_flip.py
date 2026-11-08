# -*- coding: utf-8 -*-
"""
analysis_extra_flip.py — 翻箱净含量守恒预警表

业务背景（裴哥 2026-11-08 确认口径）
------------------------------------
翻箱（订单类型 ZPFX）是把 A 规格成品拆包 → 重新装成 B 规格成品。
正常物理上应「净含量守恒」：拆出来多少 KG 食物，装回去就多少 KG（顶多正常损耗）。

漏洞模式：产出 KG **大于** 投入食物 KG → 凭空多出食物 → 说明拆包投入被**漏记**
（翻箱单的拆包投入定额多为 0、全靠手填，最易漏记，之前 10 月就是这问题）。

口径铁律
------------------------------------
1. **净含量守恒，不是件数守恒**：拆大装小件数必然膨胀（1 大件拆成多小件），
   件数不可比；只有重量（KG）可比。产出 KG = 产量 × 单件净含量。
2. **只有产出 KG > 投入食物 KG 才是真漏记**：产出 < 投入是正常损耗，不报。
3. **单件净含量从规格名解析**：如「30gx60包」→ 30g × 60 = 1.8KG/件。
   解析不出来（规格不规范）→ 该单标「待人工确认」，绝不硬猜、绝不当 0 算。
4. **投入侧只算食物，不算包材**：Z007（成品件）计入；Z002 里描述含
   散货食物关键词（自动包/薯片/原切/面包/瑞士卷）且单位 KG 的计入；
   真包材（箱/袋/胶带/内袋膜）不计入。

设计约束（与 analysis_extra_sheets.py 同一套纪律）
------------------------------------
- 只读「完整偏差明细」一张源表，不碰 analyzer / sheet1~10 / post_process 计算。
- 表现层（数字格式/冻结/自动筛选）交给 post_process 逐表流水线，本模块只写数据。
- 数据区下方不加说明行（会被当成数据行，污染事实卡的行数）。
- 幂等：同名 sheet 先删再写。
- 任何一步失败都不许阻断导出，且禁止裸 except: pass，必须 print 诊断。
"""
import re

from analysis.excel_builder.post_process import (
    _cells_of,
    _find_col,
    _header_info,
    _last_data_row,
    _num,
)
from analysis.excel_builder.analysis_extra_sheets import (
    _cell_value,
    _id_str,
    _is_blank,
    _write_sheet,
)


# ---------------------------------------------------------------- 常量

_SRC_SHEET = '完整偏差明细'
SHEET_FLIP_CHECK = '翻箱守恒预警'

# 翻箱订单类型关键词（订单类型列含 ZPFX 即翻箱单）
_FLIP_ORDER_TYPE = 'ZPFX'

# 散货食物识别：标 Z002（包材类）但描述含这些词的，实为食物散货，计入投入
_FOOD_KG = re.compile(r'自动包|薯片|原切|面包|瑞士卷')
# 真包材识别：描述含这些词的不计入食物
_PKG = re.compile(r'内袋|箱|胶带|白内袋')


def _log(msg):
    """诊断输出：出错必须能被看见，禁止裸吞异常。"""
    print('[analysis_extra_flip] %s' % msg)


# ---------------------------------------------------------------- 净含量解析

def parse_net_kg(spec):
    """从规格名解析单件净含量（KG）。

    例：'30gx60包' → 0.03KG × 60 = 1.8KG/件
        '2.5kg'     → 2.5KG/件
        '160gx18包' → 0.16 × 18 = 2.88KG/件

    规则：先抓第一个「数字+g/kg」作基准重量，再从基准之后顺序扫
    「x数字」或「数字包/袋/盒」作乘数（每个数字只吃一次，避免 x18 和 18包
    把同一个 18 抓两遍算成平方）。解析不出基准重量返回 None（不硬猜）。
    """
    if spec is None:
        return None
    s = str(spec).strip()
    if not s:
        return None
    m = re.search(r'(\d+\.?\d*)\s*(kg|g)', s, re.IGNORECASE)
    if not m:
        return None
    base = float(m.group(1))
    unit = m.group(2).lower()
    base_g = base * 1000 if unit == 'kg' else base
    rest = s[m.end():]
    # 顺序扫乘数：x18 / 18包 / 18袋 / 18盒，每个数字只消费一次
    mults = [int(mo.group(1) or mo.group(2)) for mo in re.finditer(
        r'(?:x\s*(\d+))|(?:\b(\d+)\s*(?:包|袋|盒))', rest, re.IGNORECASE)]
    total_g = base_g
    for x in mults:
        total_g *= x
    return round(total_g / 1000.0, 4)


# ---------------------------------------------------------------- 读源表

def _scan_flip_source(ws):
    """扫「完整偏差明细」，只保留翻箱（ZPFX）行，补齐守恒所需的全部列。

    与 analysis_extra_sheets._scan_source 的区别：那边只扫 20 列（不含产量/
    组件物料类型），本函数专门为翻箱守恒补扫「产量/产量单位/组件物料类型/
    组件物料类型描述」。底层工具（_header_info/_find_col/_cells_of/_cell_value/
    _num/_id_str）全部复用，不重复造轮子、不改 _scan_source（动了会影响另外 6 张表）。

    返回 list[dict]，每个 dict 是一个翻箱组件行；源表缺失或无翻箱行返回 []。
    """
    hdr_row, headers = _header_info(ws)
    last_row = _last_data_row(ws, hdr_row)
    col = {
        'ord': _find_col(headers, '流程订单'),
        'date': _find_col(headers, '订单日期'),
        'fac': _find_col(headers, '工厂'),
        'ws': _find_col(headers, '车间'),
        'otype': _find_col(headers, '订单类型'),
        'pno': _find_col(headers, '产品物料号码'),
        'pdesc': _find_col(headers, '产品物料描述'),
        'mcode': _find_col(headers, '物料编码'),
        'mname': _find_col(headers, '物料名称'),
        'mtype': _find_col(headers, '组件物料类型'),
        'mtdesc': _find_col(headers, '组件物料类型描述'),
        'unit': _find_col(headers, '单位'),
        'actual': _find_col(headers, '实际'),
        'yield': _find_col(headers, '产量'),
        'yunit': _find_col(headers, '产量单位'),
        'note': _find_col(headers, '备注'),
    }
    # 翻箱守恒的命门列：订单号 / 产品物料描述(解析产出净含量) / 产量 / 组件物料类型 / 实际
    fatal = [k for k in ('ord', 'pdesc', 'yield', 'mtype', 'actual') if col[k] is None]
    if fatal:
        _log('源表缺少翻箱守恒必要列: %s，跳过翻箱守恒预警' % ', '.join(fatal))
        return []

    cells = _cells_of(ws)
    rows = []
    for r in range(hdr_row + 1, last_row + 1):
        otype = _id_str(_cell_value(cells, r, col['otype']))
        # 只保留翻箱单（订单类型含 ZPFX），其余订单跳过
        if _FLIP_ORDER_TYPE not in otype.upper():
            continue
        actual = _num(_cell_value(cells, r, col['actual']))
        yv = _num(_cell_value(cells, r, col['yield']))
        note = _cell_value(cells, r, col['note'])
        rows.append({
            'ord': _id_str(_cell_value(cells, r, col['ord'])),
            'date': _id_str(_cell_value(cells, r, col['date'])),
            'fac': _id_str(_cell_value(cells, r, col['fac'])),
            'ws': _id_str(_cell_value(cells, r, col['ws'])),
            'otype': otype,
            'pno': _id_str(_cell_value(cells, r, col['pno'])),
            'pdesc': _id_str(_cell_value(cells, r, col['pdesc'])),
            'mcode': _id_str(_cell_value(cells, r, col['mcode'])),
            'mname': _id_str(_cell_value(cells, r, col['mname'])),
            'mtype': _id_str(_cell_value(cells, r, col['mtype'])),
            'mtdesc': _id_str(_cell_value(cells, r, col['mtdesc'])) if col['mtdesc'] else '',
            'unit': _id_str(_cell_value(cells, r, col['unit'])) if col['unit'] else '',
            'actual': 0.0 if actual is None else actual,
            'yield': 0.0 if yv is None else yv,
            'yunit': _id_str(_cell_value(cells, r, col['yunit'])) if col['yunit'] else '',
            'note': '' if _is_blank(note) else str(note).strip(),
        })
    return rows


# ---------------------------------------------------------------- 守恒校验

def _check_order(rows_of_order):
    """对一个翻箱订单（同流程订单的多组件行）做净含量守恒校验。

    返回 dict：
      产出KG / 投入成品KG / 投入散货KG / 投入食物KG / 差额KG / 偏差率 / 结论
    差额KG = 产出KG − 投入食物KG；> 0 表示凭空多出（疑似漏记）。
    偏差率 = 差额KG / 投入食物KG（投入为 0 时给 None）。
    """
    first = rows_of_order[0]
    # 产出侧：产量 × 单件净含量（净含量从产品物料描述解析，全订单同一产品）
    net_each = parse_net_kg(first['pdesc'])
    yield_qty = first['yield']
    out_kg = None
    if net_each is not None:
        out_kg = round(yield_qty * net_each, 4)

    # 投入侧：逐组件行累加食物净含量
    in_finished_kg = 0.0   # Z007 成品件投入
    in_loose_kg = 0.0      # Z002 散货食物投入
    for r in rows_of_order:
        mtype = r['mtype'].upper()
        mname = r['mname']
        act = r['actual']
        if mtype == 'Z007':
            # 成品件：实际件数 × 单件净含量
            each = parse_net_kg(mname)
            if each is not None:
                in_finished_kg += act * each
        else:
            # 非 Z007（多为 Z002 包材类）：只认「散货食物且单位 KG」
            desc = mname
            if _FOOD_KG.search(desc) and not _PKG.search(desc) and r['unit'].upper() == 'KG':
                in_loose_kg += act
    in_food_kg = round(in_finished_kg + in_loose_kg, 4)

    if out_kg is None:
        return {
            'out_kg': None, 'in_fin': round(in_finished_kg, 4),
            'in_loose': round(in_loose_kg, 4), 'in_food': in_food_kg,
            'diff': None, 'rate': None, 'verdict': '待人工确认',
        }
    diff = round(out_kg - in_food_kg, 4)
    rate = (diff / in_food_kg) if in_food_kg > 0 else None
    # 只有产出 > 投入（差额 > 0）才是疑似漏记；产出 < 投入是正常损耗
    verdict = '疑似漏记' if diff > 0 else '守恒/正常'
    return {
        'out_kg': out_kg, 'in_fin': round(in_finished_kg, 4),
        'in_loose': round(in_loose_kg, 4), 'in_food': in_food_kg,
        'diff': diff, 'rate': rate, 'verdict': verdict,
    }


def _build_flip_check(rows):
    """把翻箱组件行按流程订单聚合，一单算一行守恒结果。返回 (headers, data, widths)。"""
    # 按流程订单分组，保持首次出现顺序
    groups = {}
    order_keys = []
    for r in rows:
        k = r['ord']
        if k not in groups:
            groups[k] = []
            order_keys.append(k)
        groups[k].append(r)

    headers = ['订单日期', '流程订单', '工厂', '车间', '产品物料描述',
               '产量(件)', '单件净含量(KG)', '产出总净含量(KG)',
               '投入成品件折KG', '投入散货食物KG', '投入食物合计KG',
               '差额KG(产出-投入)', '偏差率', '结论', '备注']
    data = []
    for k in order_keys:
        g = groups[k]
        res = _check_order(g)
        first = g[0]
        net_each = parse_net_kg(first['pdesc'])
        rate_txt = ('%.1f%%' % (res['rate'] * 100)) if res['rate'] is not None else '—'
        out_txt = res['out_kg'] if res['out_kg'] is not None else '待解析'
        diff_txt = res['diff'] if res['diff'] is not None else '—'
        data.append([
            first['date'], k, first['fac'], first['ws'], first['pdesc'],
            first['yield'],
            net_each if net_each is not None else '解析失败',
            out_txt,
            res['in_fin'], res['in_loose'], res['in_food'],
            diff_txt, rate_txt, res['verdict'], first['note'],
        ])
    widths = [12, 14, 8, 14, 30, 10, 14, 16, 14, 14, 14, 16, 10, 12, 24]
    return headers, data, widths


# ---------------------------------------------------------------- 入口

def build_flip_sheets(wb):
    """生成翻箱守恒预警表。返回 {表名: 写入行数}；源表缺失或无翻箱单返回 {}。

    任何一步失败都不抛异常（附加分析表出问题不该让整个导出失败），必须 print 诊断。
    """
    result = {}
    if _SRC_SHEET not in wb.sheetnames:
        _log('源表「%s」不存在，跳过翻箱守恒预警' % _SRC_SHEET)
        return result
    try:
        rows = _scan_flip_source(wb[_SRC_SHEET])
    except Exception as e:
        import traceback
        _log('扫描翻箱源表失败: %s' % e)
        traceback.print_exc()
        return result

    if not rows:
        _log('本期无翻箱（%s）订单，跳过翻箱守恒预警' % _FLIP_ORDER_TYPE)
        return result

    try:
        headers, data, widths = _build_flip_check(rows)
        result[SHEET_FLIP_CHECK] = _write_sheet(wb, SHEET_FLIP_CHECK, headers, data, widths)
    except Exception as e:
        import traceback
        _log('生成「%s」失败: %s' % (SHEET_FLIP_CHECK, e))
        traceback.print_exc()
    return result
