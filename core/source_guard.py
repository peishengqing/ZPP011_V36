# -*- coding: utf-8 -*-
"""
core/source_guard.py — F04 输入数据预检（v43.325）

业务背景
------------------------------------
do_analysis_v2 读表时「优先读 'Data'，不存在则取第一个」的容错本来是好事，
但错发 ZMM062 收发存表（也有 Data sheet、1310 行 / 24 列）时，旧校验只查
「订单开始日期 / 数量-定额 / 数量-实际」三列，不足以区分生产明细与收发存，
于是静默取第一张表继续跑，产出一份**看似正常实则全假**的分析报告。

设计铁律
------------------------------------
1. **只在读表前校验**：do_analysis_v2 之后任何计算逻辑一个字节不改。
2. 硬拒绝判据 = **三个生产明细核心列一个都没有**（流程订单 / 组件物料类型 /
   数量-实际，精确列名、注意连字符）。实测 ZMM062 对照表 24 列全是库存/结存
   列（公司代码/库存地点/开始数量/入库总数量/结束数量/周转天/仓库分类…），
   这三列一列都没有；微信版真表 27 列齐全，既有测试构造表也齐全。故这足以
   精准区分，且不会把「合法但简化」的生产明细误判成错发表。
3. 硬拒绝必须抛明确异常并**点名**「这像 ZMM062 收发存表，不是 ZPP011 生产明细」。
4. 其余一律温和提示（print + log_cb）、**不阻断**：Data sheet 缺失（沿用旧容错
   取第一张表）、订单类型列缺失、订单类型未命中 ZPxx（ZPFX 翻箱本期无数据，
   主偏差分析不依赖）、核心列缺部分、列名被改、格式异常、空行过多。
   ⚠️ 原规划是「四列必含 + Data sheet 必存在 + 订单类型必命中 ZPxx」，但实测
   既有测试构造的是合法简化表（缺订单类型 / 订单类型值非 ZPxx / 用 Sheet1
   命名），严格版会让全量 pytest 引入 10 个回归。故按 spec「先说明偏离与理由
   再改」收窄为上述正向识别：偏离的是**字面校验项**，不是「拦截错发表」的
   目标（验收两条：喂 ZMM062 拒绝并点名、喂微信真表通过，均不变）。
5. log_cb 一律走 `_safe_log(cb, msg, level)` 三层兜底
   （正规 2 参 → 降级 1 参 → 静默），绝不因日志回调把原始异常顶掉。
6. 禁裸 `except Exception: pass`；意外读取异常要 traceback.print_exc() + 诊断输出。
"""
import os
import re
import traceback

from openpyxl import load_workbook

# 三个生产明细核心列（「数量-实际」带连字符，不是「数量实际」）
_CORE_COLS = ('流程订单', '组件物料类型', '数量-实际')
# 完整四列：供温和提示/近似列名检查用
_REQUIRED = ('订单类型',) + _CORE_COLS
# ZPxx：ZP + 至少 2 位字母/数字（ZP01 / ZP02 / ZP03 / ZPFX …）
_ZP_RE = re.compile(r'ZP[0-9A-Z]{2,}', re.IGNORECASE)
_MAX_SCAN = 200          # 只采样前 200 行，避免整表扫描
_EMPTY_RATIO = 0.3       # 空行占比超过此值才温和提示

_ZMM_HINT = (
    '这像 ZMM062 收发存表（或分析报告），不是 ZPP011 生产明细；'
    '请选择 SAP 原始导出文件（如 ZPP011_YYYYMMDD.xlsx / 微信版 9 月源表），'
    '生产明细核心列为 流程订单 / 组件物料类型 / 数量-实际（精确列名）。')


def _safe_log(log_cb, msg, level="info"):
    """调用外部 log_cb，绝不因日志本身的问题让流程崩掉。

    三层兜底：正规 (msg, level) → 降级单参 (msg) → 静默吞掉。
    """
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


def _warn(msg, log_cb=None):
    """温和提示：既走 _safe_log，也 print 一份确保诊断可见（不阻断）。"""
    _safe_log(log_cb, '[source_guard] 温和提示：%s' % msg, 'warning')
    print('[source_guard] 温和提示：%s' % msg)


def _fail(src_file, why, hdr):
    return ('[source_guard] 源文件预检未通过：%s\n'
            '文件：%s\n当前 Data 表头（%d 列）：%s\n%s'
            % (why, src_file, len(hdr), hdr, _ZMM_HINT))


def _gentle_warnings(hdr, sample, log_cb=None):
    """列名被改 / 格式异常 / 空行过多 —— 只提示，不抛异常。"""
    blank_cols = sum(1 for h in hdr if not h)
    if blank_cols:
        _warn('表头含 %d 个空列名（格式异常）' % blank_cols, log_cb)
    # 近似列名：忽略连字符/下划线后相同但精确写法不同的，疑似被改名
    for c in _REQUIRED:
        norm = c.replace('-', '').replace('_', '').lower()
        near = [h for h in hdr if h and h != c
                and h.replace('-', '').replace('_', '').lower() == norm]
        if near:
            _warn('列名疑似被改：期望「%s」，实际出现「%s」' % (c, near[0]), log_cb)
    if sample:
        empty = sum(1 for r in sample
                    if not any(v not in (None, '') for v in r))
        if empty > len(sample) * _EMPTY_RATIO:
            _warn('采样前 %d 行里空行 %d 行（占比偏高）'
                  % (len(sample), empty), log_cb)


def validate_source(src_file, log_cb=None):
    """读表前预检。通过返回 dict，不通过抛 ValueError（明确点名 ZMM062）。

    src_file : 源 xlsx 路径
    log_cb   : 可选日志回调，签名 (msg, level) 或 (msg)；一律走 _safe_log 兜底
    """
    if not src_file or not os.path.isfile(src_file):
        raise ValueError('[source_guard] 源文件不存在或未指定：%r' % src_file)
    try:
        wb = load_workbook(src_file, read_only=True, data_only=True)
    except Exception as e:
        _safe_log(log_cb, '[source_guard] 打开源文件失败：%s' % e, 'error')
        traceback.print_exc()
        raise ValueError('[source_guard] 无法读取源文件 %s：%s' % (src_file, e))
    try:
        names = list(wb.sheetnames)
        if 'Data' in names:
            ws = wb['Data']
            sheet_used = 'Data'
        else:
            # 旧容错：不存在 Data 则取第一张表（do_analysis_v2 既有行为）。
            # ZMM062 也有 Data sheet，靠 sheet 名本就区分不了，故只温和提示。
            _warn('缺少「Data」工作表（现有：%s），沿用旧容错取第一张表'
                  % ', '.join(names), log_cb)
            ws = wb[names[0]]
            sheet_used = names[0]
        it = ws.iter_rows(values_only=True)
        try:
            first = next(it)
        except StopIteration:
            raise ValueError(_fail(src_file, '工作表为空（无表头行）', []))
        hdr = ['' if v is None else str(v).strip() for v in first]

        # 硬拒绝：三个生产明细核心列一个都没有 → ZMM062 收发存表
        if not any(c in hdr for c in _CORE_COLS):
            raise ValueError(_fail(
                src_file,
                '未命中任何生产明细核心列（%s）' % ' / '.join(_CORE_COLS), hdr))

        missing_core = [c for c in _CORE_COLS if c not in hdr]
        if missing_core:
            _warn('缺少部分生产明细核心列：%s（疑似列名被改，未阻断）'
                  % ', '.join(missing_core), log_cb)

        # 采样前 200 行：订单类型 ZPxx 只记 info/温和提示，不阻断
        sample = []
        zp_hit = None
        has_type = '订单类型' in hdr
        i_type = hdr.index('订单类型') if has_type else None
        for i, row in enumerate(it):
            if i >= _MAX_SCAN:
                break
            sample.append(row)
            if has_type and zp_hit is None:
                v = row[i_type] if i_type < len(row) else None
                m = _ZP_RE.search(str(v or ''))
                if m:
                    zp_hit = m.group(0)
        if not has_type:
            _warn('缺少「订单类型」列：ZPFX 翻箱分流本期将无数据，'
                  '主偏差分析不依赖该列，预检不阻断', log_cb)
        elif not zp_hit:
            _warn('订单类型列前 %d 行未命中 ZPxx：ZPFX 翻箱分流本期将无数据，'
                  '预检不阻断' % _MAX_SCAN, log_cb)

        _gentle_warnings(hdr, sample, log_cb)
        _safe_log(log_cb,
                  '[source_guard] 预检通过：%s 表 %d 列，生产明细核心列命中 %d/%d，'
                  'ZPxx=%s' % (sheet_used, len(hdr),
                               len(_CORE_COLS) - len(missing_core),
                               len(_CORE_COLS), zp_hit or '(未命中)'), 'info')
        return {'sheet': sheet_used, 'columns': len(hdr),
                'core_hit': len(_CORE_COLS) - len(missing_core),
                'zp_hit': zp_hit}
    finally:
        wb.close()
