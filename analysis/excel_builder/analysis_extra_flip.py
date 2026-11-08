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
- v43.323 起输出两张表：「翻箱守恒预警」（一单一行结论）+「翻箱组件明细」
  （一行一组件，全组件含包材，带「是否计入食物投入」标记）。
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
SHEET_FLIP_DETAIL = '翻箱组件明细'

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

def _food_kg_of(r):
    """单个组件行「是否计入食物投入」+ 折算 KG。

    ⚠️ 单一口径来源：_check_order（守恒主表）与 _build_flip_detail（组件明细表）
    共用本函数，绝不两处各写一套判别 —— 否则明细页会跟主表数字对不上。
    返回 (标记, KG)：标记 ∈ {'是', '否', '否(规格解析失败)'}。
    """
    mtype = r['mtype'].upper()
    mname = r['mname']
    act = r['actual']
    if mtype == 'Z007':
        # 成品件：实际件数 × 单件净含量（从组件规格名解析）
        each = parse_net_kg(mname)
        if each is not None:
            return '是', act * each
        return '否(规格解析失败)', 0.0
    # 非 Z007（多为 Z002 包材类）：只认「散货食物且单位 KG」
    if _FOOD_KG.search(mname) and not _PKG.search(mname) \
            and r['unit'].upper() == 'KG':
        return '是', act
    return '否', 0.0


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

    # 投入侧：逐组件行累加食物净含量。判别统一走 _food_kg_of，
    # 与「翻箱组件明细」共用同一口径，避免两套逻辑打架。
    in_finished_kg = 0.0   # Z007 成品件投入
    in_loose_kg = 0.0      # Z002 散货食物投入
    for r in rows_of_order:
        flag, kg = _food_kg_of(r)
        if r['mtype'].upper() == 'Z007':
            in_finished_kg += kg
        elif flag == '是':
            in_loose_kg += kg
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

    headers = ['订单日期', '流程订单', '工厂', '车间', '产品物料编码', '产品物料描述',
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
            first['date'], k, first['fac'], first['ws'], first['pno'], first['pdesc'],
            first['yield'],
            net_each if net_each is not None else '解析失败',
            out_txt,
            res['in_fin'], res['in_loose'], res['in_food'],
            diff_txt, rate_txt, res['verdict'], first['note'],
        ])
    widths = [12, 14, 8, 14, 14, 30, 10, 14, 16, 14, 14, 14, 16, 10, 12, 24]
    return headers, data, widths


def _build_flip_detail(rows):
    """一行一组件的翻箱明细：产品/组件编码名称 + 是否计入食物投入。

    v43.323：全组件都列（含包材、实际=0 的 Z004），不丢信息；另用
    「是否计入食物投入」+「计入KG(参考)」标出哪些行真正参与守恒计算，
    便于与主表逐单对账。判别统一走 _food_kg_of，与主表同源。
    """
    headers = ['订单日期', '流程订单', '工厂', '车间',
               '产品物料编码', '产品物料描述',
               '组件物料编码', '组件物料名称', '组件物料类型', '组件物料类型描述',
               '单位', '实际', '是否计入食物投入', '计入KG(参考)', '备注']
    data = []
    for r in rows:
        flag, kg = _food_kg_of(r)
        data.append([
            r['date'], r['ord'], r['fac'], r['ws'],
            r['pno'], r['pdesc'],
            r['mcode'], r['mname'], r['mtype'], r['mtdesc'],
            # 6 位而非 4 位：逐单汇总要能对回主表 round(sum,4)，
            # 每行先砍到 4 位会让 57 行累积误差超过 1e-3 的对账容差。
            r['unit'], r['actual'], flag, round(kg, 6), r['note'],
        ])
    widths = [12, 14, 8, 14, 14, 30, 14, 34, 12, 16, 8, 12, 16, 14, 24]
    return headers, data, widths


# ---------------------------------------------------------------- 入口

def build_flip_sheets(wb):
    """生成翻箱守恒表：食品厂走净含量KG守恒、饮料厂走总容器数守恒。

    返回 {表名: 写入行数}；源表缺失或无翻箱单返回 {}。
    v43.324：先 `_scan_flip_source` 得全量 ZPFX 行 → `split_by_factory` 分流 →
    食品行沿用 v43.323 原逻辑（_build_flip_check/_build_flip_detail 零改动）；
    饮料行按流程订单分组走新增两张表；未知厂不写表、print 诊断留痕。
    没有饮料 ZPFX 时不生成饮料两张表（保持现有单厂报告 20 张表不变）。
    饮料新增函数统一定义在文件末尾（模块加载完即全部就位，运行时解析，
    无定义先后依赖）。每张表独立 try + traceback.print_exc()，任何一张失败
    不阻断其它表；任何一步失败都不抛异常，必须 print 诊断。
    """
    result = {}
    if _SRC_SHEET not in wb.sheetnames:
        _log('源表「%s」不存在，跳过翻箱守恒表' % _SRC_SHEET)
        return result
    try:
        rows = _scan_flip_source(wb[_SRC_SHEET])
    except Exception as e:
        import traceback
        _log('扫描翻箱源表失败: %s' % e)
        traceback.print_exc()
        return result

    if not rows:
        _log('本期无翻箱（%s）订单，跳过翻箱守恒表' % _FLIP_ORDER_TYPE)
        # v43.325 F06：零命中也要留痕，否则静默失败不可见
        try:
            from core.rule_hit_monitor import record_hit
            record_hit('ZPFX翻箱守恒', 0)
        except Exception:
            import traceback
            traceback.print_exc()
        return result

    # v43.324：按工厂分流（纯判定；失败也绝不把饮料行塞进食品表）。
    try:
        food_rows, drink_rows, unknown_rows = split_by_factory(rows)
    except Exception as e:
        import traceback
        _log('按工厂分流失败（保守跳过全部翻箱表，绝不混算）: %s' % e)
        traceback.print_exc()
        return result
    _log('ZPFX 分流：食品 %d 行 / 饮料 %d 行 / 未知厂 %d 行'
         % (len(food_rows), len(drink_rows), len(unknown_rows)))
    if unknown_rows:
        _log('未知工厂 ZPFX 行 %d 条不写表（不猜厂，单独留痕）:' % len(unknown_rows))
        for r in unknown_rows:
            print('    [未知厂] 流程订单=%s 工厂=%s 产品=%s 组件=%s'
                  % (r['ord'], r['fac'], r['pdesc'], r['mname']))

    # 食品厂（1101）：两张表名与全部计算逻辑沿用 v43.323，零改动。
    if food_rows:
        try:
            headers, data, widths = _build_flip_check(food_rows)
            result[SHEET_FLIP_CHECK] = _write_sheet(
                wb, SHEET_FLIP_CHECK, headers, data, widths)
        except Exception as e:
            import traceback
            _log('生成「%s」失败: %s' % (SHEET_FLIP_CHECK, e))
            traceback.print_exc()
        # v43.323：一行一组件的明细页。单独 try —— 明细页失败绝不拖累主结论页。
        try:
            dh, dd, dw = _build_flip_detail(food_rows)
            result[SHEET_FLIP_DETAIL] = _write_sheet(
                wb, SHEET_FLIP_DETAIL, dh, dd, dw)
        except Exception as e:
            import traceback
            _log('生成「%s」失败: %s' % (SHEET_FLIP_DETAIL, e))
            traceback.print_exc()

    # 饮料厂（1102）：只在有饮料 ZPFX 时生成两张表；无饮料 ZPFX 时不生成
    # （保持现有单厂报告 20 张表不变）。每张表独立 try。
    if drink_rows:
        try:
            headers, data, widths = _build_drink_check(drink_rows)
            result[SHEET_DRINK_CHECK] = _write_sheet(
                wb, SHEET_DRINK_CHECK, headers, data, widths)
        except Exception as e:
            import traceback
            _log('生成「%s」失败: %s' % (SHEET_DRINK_CHECK, e))
            traceback.print_exc()
        try:
            dh, dd, dw = _build_drink_detail(drink_rows)
            result[SHEET_DRINK_DETAIL] = _write_sheet(
                wb, SHEET_DRINK_DETAIL, dh, dd, dw)
        except Exception as e:
            import traceback
            _log('生成「%s」失败: %s' % (SHEET_DRINK_DETAIL, e))
            traceback.print_exc()
        # v43.325 F05：未判定原因四类枚举分布（独立 sheet，零列契约变动）。
        # 按订单分组复用 check_drink_order 的 verdict/why，判别单一来源
        # core/unresolved_reason.classify；明细侧由分布模块读已生成明细表，
        # 主表与明细共用同一 classify()。
        try:
            from core.unresolved_reason import (
                build_distribution_sheet, SHEET_UNRESOLVED)
            _groups = {}
            for _r in drink_rows:
                _groups.setdefault(_r['ord'], []).append(_r)
            _order_results = [check_drink_order(g) for g in _groups.values()]
            result[SHEET_UNRESOLVED] = build_distribution_sheet(
                wb, _order_results)
        except Exception as e:
            import traceback
            _log('生成「未判定原因分布」失败: %s' % e)
            traceback.print_exc()
    else:
        # 无饮料 ZPFX：若工作簿里残留上一轮的饮料表，删掉，保证「不生成」且幂等。
        for _nm in (SHEET_DRINK_CHECK, SHEET_DRINK_DETAIL):
            if _nm in wb.sheetnames:
                try:
                    del wb[_nm]
                    _log('本期无饮料 ZPFX，删除残留表「%s」' % _nm)
                except Exception as e:
                    import traceback
                    _log('删除残留表「%s」失败: %s' % (_nm, e))
                    traceback.print_exc()
    # v43.325 F06：记录本期命中行数 + 结论分布（纯读已生成表，不改计算）
    try:
        from core.rule_hit_monitor import record_hit
        record_hit('ZPFX翻箱守恒', len(rows), wb=wb,
                   check_sheets=(SHEET_FLIP_CHECK, SHEET_DRINK_CHECK))
    except Exception:
        import traceback
        _log('[flip] 规则命中埋点失败（不影响导出）')
        traceback.print_exc()
    return result


# ================================================================
# v43.324 饮料厂（1102 / 云南达利-饮料厂）翻箱「总容器数守恒」
# ----------------------------------------------------------------
# 新函数统一写在文件末尾，不打断上方食品侧既有函数序列（阅读/维护）。
# 与食品侧（净含量 KG 守恒）完全独立：不复用也不改动 parse_net_kg /
# _food_kg_of / _check_order / _build_flip_check / _build_flip_detail。
# 业务口径（裴哥 2026-11-09 确认）：
#   1. 唯一入口 订单类型含 ZPFX；只有 1101 食品 / 1102 饮料两厂，不做映射表。
#   2. 饮料不套 KG 规则（已反证：parse_net_kg('380mlx3瓶x5组…')=None、
#      饮料单无 Z007，旧逻辑会静默落「待人工确认」），改按总容器数守恒：
#      差 = 产出件数×单件容器数 − Σ(投入件数×单件容器数)；
#      差>0 疑似漏记，差≤0 守恒/正常。不比件数、不比KG、
#      禁止任何 ml↔g / 体积→质量密度折算（源表无密度字段，是假精度）。
#   3. 饮料翻箱只用成品不拿半成品：投入侧只认 组件物料类型=='Z008' 且
#      实际>0；备注含「未使用」辅助排除（主判据是实际>0，Z005 半成品真单
#      实际就是 0）。Z005/Z002/Z001 全部排除但在明细「排除原因」留痕，
#      绝不静默丢行。
#   4. 瓶装只翻瓶装、罐装只翻罐装：容器形式或净含量单位不一致的行不计入，
#      标「待人工确认」，不静默丢行。
#   5. 净含量单位只读规格名里的 ml/g/l/kg（由内容物决定、不由容器决定，
#      同一个「罐」字既有 240mlx20罐 花生牛奶 也有 360gx12罐 八宝粥）。
#      规格解析不出单位或容器数 → 返回 None → 该单「待人工确认」，
#      绝不硬猜、绝不当 0 算。
#   6. 「是否计入容器数」判别单一来源 _drink_container_of(r, out_pack)，
#      主表（check_drink_order）与明细表（_build_drink_detail）共用，
#      杜绝两套逻辑打架（历史事故 v43.183 / v43.323 均要求同源）。
# ================================================================

SHEET_DRINK_CHECK = '饮料翻箱守恒'
SHEET_DRINK_DETAIL = '饮料翻箱组件明细'

# 只有两个厂：码（源表 1101/1102）与中文厂名
# （成品工作簿「完整偏差明细」云南达利-食品厂/云南达利-饮料厂）两套都认。
# 不做可扩展工厂映射表；未知厂不猜。
_FAC_FOOD = {'1101', '云南达利-食品厂'}
_FAC_DRINK = {'1102', '云南达利-饮料厂'}

# 规格解析正则（本地草案 _web_flip_aligned.py 实测 5 个用例全过）。
# 括号加法 (24+4)→28 先整体替换，避免 x(16+2) 被拆错。
_PAREN_ADD = re.compile(r'\((\d+(?:\+\d+)+)\)')
# 净含量基准：第一个「数字+单位」。单位只读 ml/毫升/l/升/kg/千克/g/克；
# 由内容物决定，不由容器词（瓶/罐）决定。
_DRINK_UNIT = re.compile(
    r'(\d+(?:\.\d+)?)\s*(ml|毫升|l|升|kg|千克|g|克)', re.IGNORECASE)
# 乘数：x3 / ×3 / 3瓶 / 3组 …（数字只消费一次，避免 x18 与 18包 把 18 抓两遍）
_DRINK_MULT = re.compile(
    r'(?:x|×)\s*(\d+)|(\d+)\s*(?:瓶|罐|包|组|提|袋|盒|箱)', re.IGNORECASE)
# 容器形式（单件装几个容器后面的那个容器词）；组/提是包装层级，不是容器。
_DRINK_CONTAINER = re.compile(r'\d+\s*(瓶|罐|包|袋|盒|箱)')

# 排除原因留痕：Z005 半成品 / Z002 包材 / Z001 原辅料，以及其它非 Z008。
_DRINK_EXCLUDE_REASON = {
    'Z005': 'Z005 半成品（饮料翻箱只用成品，不拿半成品翻箱）',
    'Z002': 'Z002 包材（不计容器数）',
    'Z001': 'Z001 原辅料（不计容器数）',
}


def parse_pack(spec):
    """从成品规格名解析单件容器信息与净含量单位。解析不出返回 None，绝不硬猜。

    返回 dict：
      n          单件容器数（如 380mlx3瓶x5组 → 15）
      container  容器形式词（瓶/罐/包/袋/盒/箱）
      unit       净含量单位 'ml'（ml/毫升/l/升）或 'g'（g/克/kg/千克）
      per        单容器净含量数值（数值！l/kg 换算成 1000，如 '1l' → 1000）
      item       单件净含量数值 = per × n
    支持：括号加法 (24+4)→28、多级乘数 x3瓶x5组→15、
          250mlx(16+2)包x3提→54、360gx12罐→12/g、1lx12瓶→12/ml 且 per=1000。
    """
    if spec is None:
        return None
    s = str(spec).strip()
    if not s:
        return None
    # ① 括号加法先整体替换成其和，例 (16+2)→18
    s = _PAREN_ADD.sub(
        lambda m: str(sum(int(x) for x in m.group(1).split('+'))), s)
    # ② 净含量基准（第一个「数字+单位」）
    m = _DRINK_UNIT.search(s)
    if not m:
        return None
    # ③ 容器形式：规格里必须出现「数字+容器词」，否则容器数无从谈起
    cm = _DRINK_CONTAINER.search(s)
    if not cm:
        return None
    # ④ 乘数：只从基准单位之后扫，数字只消费一次
    n = 1
    for mo in _DRINK_MULT.finditer(s[m.end():]):
        v = int(mo.group(1) or mo.group(2))
        if v:
            n *= v
    if n < 1:
        return None
    u = m.group(2).lower()
    unit = 'ml' if u in ('ml', '毫升', 'l', '升') else 'g'
    # per 必须是数值：l/kg 换算成 1000，其余原值
    per = float(m.group(1)) * (1000 if u in ('l', '升', 'kg', '千克') else 1)
    return {'n': n, 'container': cm.group(1), 'unit': unit,
            'per': per, 'item': round(per * n, 4)}


def split_by_factory(rows):
    """按工厂把全量 ZPFX 行分成 (食品行, 饮料行, 未知厂行)。

    用 r['fac'] 判定；工厂码（1101/1102，源表）与中文厂名
    （云南达利-食品厂/云南达利-饮料厂，成品工作簿「完整偏差明细」）两套都认。
    只有两个厂，不做可扩展工厂映射表；未知厂不猜，单独返回留痕。
    """
    food, drink, unknown = [], [], []
    for r in rows:
        fac = str(r['fac']).strip()
        if fac in _FAC_FOOD:
            food.append(r)
        elif fac in _FAC_DRINK:
            drink.append(r)
        else:
            unknown.append(r)
    return food, drink, unknown


def _drink_container_of(r, out_pack):
    """单个组件行「是否计入容器数」+ 该行贡献的容器数 + 排除原因。

    ⚠️ 单一口径来源：check_drink_order（饮料守恒主表）与 _build_drink_detail
    （饮料组件明细表）共用本函数，绝不两处各写一套判别 —— 否则明细页会跟
    主表数字对不上（历史事故 v43.183 / v43.323 都要求同源）。

    返回 (标记, 容器数, 排除原因)：标记 ∈ {'是', '否'}；
    容器数 = 实际件数 × 该组件单件容器数（仅标记='是' 时非零）。
    """
    mtype = r['mtype'].upper()
    note = r['note']
    act = r['actual']
    # 主判据：饮料翻箱只用成品（Z008），不拿半成品翻箱。
    if mtype != 'Z008':
        reason = _DRINK_EXCLUDE_REASON.get(
            mtype, '%s 非 Z008 成品投入（不计容器数）' % mtype)
        if r['mtdesc']:
            reason += '｜%s' % r['mtdesc']   # 留痕：类型描述
        return '否', 0.0, reason
    # 辅助判据：备注含「未使用」排除（成品工作簿列名是「备注」，可能不带该字样，
    # 故只作辅助，绝不依赖它做唯一过滤）。
    if '未使用' in note:
        return '否', 0.0, '备注含「未使用」'
    # 主判据：实际 > 0（Z005 半成品真单实际就是 0；实际=0 的成品行也不算耗用）
    if act <= 0:
        return '否', 0.0, '实际耗用=0（未投料）'
    # 产出规格解析失败时无法比对容器形式/单位，绝不硬猜
    if out_pack is None:
        return '否', 0.0, '产出规格解析失败（无法确认容器形式/单位）'
    pack = parse_pack(r['mname'])
    if pack is None:
        return '否', 0.0, '组件规格解析失败（单位/容器数不明，绝不硬猜当 0）'
    # 瓶装只翻瓶装、罐装只翻罐装：形式或单位不一致 → 不计入、标待人工确认
    if pack['container'] != out_pack['container'] \
            or pack['unit'] != out_pack['unit']:
        return '否', 0.0, (
            '容器形式/单位不一致（产出 %s/%s vs 投入 %s/%s）'
            % (out_pack['container'], out_pack['unit'],
               pack['container'], pack['unit']))
    return '是', round(act * pack['n'], 4), ''


def check_drink_order(rows_of_order):
    """对一个饮料翻箱订单（同流程订单的多组件行）做总容器数守恒校验。

    返回 dict（含 verdict 与各项数值）：产出/投入/差额容器数、偏差率、结论、
    待人工确认原因，以及产出侧的 容器形式 / 净含量单位 / 单件容器数 /
    单容器净含量。
    差额 = 产出件数×单件容器数 − Σ(投入件数×单件容器数)；
    差>0 疑似漏记，差≤0 守恒/正常。
    任何「无法确认」的情况（规格解析失败 / 投入侧无有效成品耗用行 /
    容器形式或单位不一致）一律标「待人工确认」，绝不硬猜、绝不当 0 算。
    """
    first = rows_of_order[0]
    out_pack = parse_pack(first['pdesc'])
    yield_qty = first['yield']
    out_containers = (round(yield_qty * out_pack['n'], 4)
                      if out_pack else None)

    in_containers = 0.0
    n_candidate = 0     # Z008 且 实际>0 且 非「未使用」的候选投入行
    n_badspec = 0       # 候选中规格解析失败
    n_cross = 0         # 候选中容器形式/单位不一致
    n_counted = 0       # 真正计入容器数的行
    for r in rows_of_order:
        flag, containers, reason = _drink_container_of(r, out_pack)
        if (r['mtype'].upper() == 'Z008' and r['actual'] > 0
                and '未使用' not in r['note']):
            n_candidate += 1
            if '解析失败' in reason:
                n_badspec += 1
            elif '不一致' in reason:
                n_cross += 1
        if flag == '是':
            in_containers += containers
            n_counted += 1
    in_containers = round(in_containers, 4)

    diff = None if out_containers is None else round(
        out_containers - in_containers, 4)
    rate = ((diff / in_containers) if (diff is not None and in_containers > 0)
            else None)

    # 结论：任何不确定一律留人工，绝不硬判漏记、绝不把解析失败当 0 算。
    if out_pack is None:
        verdict, why = '待人工确认', '产出规格解析失败'
    elif n_candidate == 0:
        verdict, why = '待人工确认', '投入侧无有效成品耗用行（Z008 且 实际>0）'
    elif n_badspec > 0:
        verdict, why = '待人工确认', '投入组件规格解析失败（单位/容器数不明）'
    elif n_cross > 0:
        verdict, why = '待人工确认', '存在容器形式/单位不一致的投入行'
    else:
        verdict = '疑似漏记' if diff > 0 else '守恒/正常'
        why = ''
    return {
        'container': out_pack['container'] if out_pack else None,
        'unit': out_pack['unit'] if out_pack else None,
        'n': out_pack['n'] if out_pack else None,
        'per': out_pack['per'] if out_pack else None,
        'out_containers': out_containers,
        'in_containers': in_containers,
        'diff_containers': diff,
        'rate': rate,
        'verdict': verdict,
        'reason': why,
        'n_candidate': n_candidate,
        'n_counted': n_counted,
        'n_cross': n_cross,
        'n_badspec': n_badspec,
    }


def _build_drink_check(rows):
    """饮料守恒主表：按流程订单分组，一单一行。返回 (headers, data, widths)。

    ⚠️ 列顺序与网页版字段契约固定，不许改名/改序（17 列）。
    """
    groups = {}
    order_keys = []
    for r in rows:
        k = r['ord']
        if k not in groups:
            groups[k] = []
            order_keys.append(k)
        groups[k].append(r)

    headers = ['订单日期', '流程订单', '工厂', '车间', '产品物料编码',
               '产品物料描述', '产量(件)', '容器形式', '净含量单位',
               '单件容器数', '单容器净含量', '产出总容器数', '投入总容器数',
               '差额容器数', '偏差率', '结论', '备注']
    data = []
    for k in order_keys:
        g = groups[k]
        res = check_drink_order(g)
        first = g[0]
        rate_txt = (('%.1f%%' % (res['rate'] * 100))
                    if res['rate'] is not None else '—')
        # 备注：把待人工确认原因写进去，便于审核员一眼看到；原备注附后。
        notes = [x for x in (res['reason'], first['note']) if x]
        data.append([
            first['date'], k, first['fac'], first['ws'], first['pno'],
            first['pdesc'],
            first['yield'],
            res['container'] if res['container'] is not None else '解析失败',
            res['unit'] if res['unit'] is not None else '—',
            res['n'] if res['n'] is not None else '—',
            res['per'] if res['per'] is not None else '—',
            (res['out_containers']
             if res['out_containers'] is not None else '待解析'),
            res['in_containers'],
            (res['diff_containers']
             if res['diff_containers'] is not None else '—'),
            rate_txt, res['verdict'],
            '；'.join(notes),
        ])
    widths = [12, 14, 16, 14, 14, 34, 10, 10, 12, 12, 14, 14, 14, 12, 10,
              12, 30]
    return headers, data, widths


def _build_drink_detail(rows):
    """饮料组件明细：一行一组件，全组件都列（含 Z005 半成品/Z002 包材/
    Z001 原辅料/实际=0 行），被排除的都在「排除原因」留痕，绝不静默丢行。

    「是否计入容器数」+「计入容器数(参考)」判别统一走 _drink_container_of，
    与主表 check_drink_order 同源，可逐单对账到主表「投入总容器数」。
    """
    headers = ['订单日期', '流程订单', '工厂', '车间',
               '产品物料编码', '产品物料描述',
               '组件物料编码', '组件物料名称', '组件物料类型',
               '组件物料类型描述', '单位', '实际',
               '是否计入容器数', '计入容器数(参考)', '排除原因', '备注']
    # 每单先算产出 pack，供 _drink_container_of 比对容器形式/单位。
    out_pack_by_order = {}
    for r in rows:
        if r['ord'] not in out_pack_by_order:
            out_pack_by_order[r['ord']] = parse_pack(r['pdesc'])
    data = []
    for r in rows:
        flag, containers, reason = _drink_container_of(
            r, out_pack_by_order[r['ord']])
        data.append([
            r['date'], r['ord'], r['fac'], r['ws'],
            r['pno'], r['pdesc'],
            r['mcode'], r['mname'], r['mtype'], r['mtdesc'],
            r['unit'], r['actual'], flag, round(containers, 6),
            reason, r['note'],
        ])
    widths = [12, 14, 16, 14, 14, 34, 14, 34, 12, 16, 8, 12, 14, 16, 40, 24]
    return headers, data, widths
