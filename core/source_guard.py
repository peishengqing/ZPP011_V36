# -*- coding: utf-8 -*-
"""
core/source_guard.py — F04 输入数据预检（v43.325）

业务背景
------------------------------------
do_analysis_v2 读表时「优先读 'Data'，不存在则取第一个」的容错本来是好事，
但错发 ZMM062 收发存表（也有 Data sheet、1310 行 / 24 列）时，旧校验只查
「订单开始日期 / 数量-定额 / 数量-实际」三列，不足以区分生产明细与收发存，
于是静默取第一张表继续跑，产出一份**看似正常实则全假**的分析报告。

设计铁律（v43.329 收尾，修复 v43.325 的判据退化）
------------------------------------
1. **只在读表前校验**：do_analysis_v2 之后任何计算逻辑一个字节不改。
2. 硬拒绝判据 = **三个生产明细核心列必须全部存在，缺任意一列即拒绝**
   （流程订单 / 组件物料类型 / 数量-实际，精确列名、注意连字符）。
   ⚠️ v43.325 曾被退化成「三列一个都没有才拒」，实测带 1 列或 2 列的错表
   会直接放行（反证 R1–R6 见 tests/unit/test_source_guard.py）。生产明细的
   最小身份判据不能减到零，本版恢复为「缺一即拒」。
3. 硬拒绝必须抛明确异常并**点名**「这像 ZMM062 收发存表，不是 ZPP011 生产明细」。
4. 其余一律温和提示（print + log_cb）、**不阻断**：Data sheet 缺失（沿用旧容错
   取第一张表）、订单类型列缺失、订单类型全表未命中 ZPxx、列名被改、格式异常、
   空行过多。订单类型扫描**全表**（不限前 N 行），避免 ZPFX 集中在表尾时误报。
   「必含三列」与真表/既有测试的合法简化表均兼容（它们三列齐全）。
5. log_cb 一律走 `_safe_log(cb, msg, level)` 三层兜底
   （正规 2 参 → 降级 1 参 → 静默），绝不因日志回调把原始异常顶掉。
6. 温和提示同时写入模块级收集器，供导出时 F01「口径自检」sheet 追加 INFO 行
   （collect_warnings / reset_warnings，纯收集、不改任何业务数值）。
7. 禁裸 `except Exception: pass`；意外读取异常要 traceback.print_exc() + 诊断输出。
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
_SAMPLE_MAX = 200        # 仅用于「空行占比」抽样的行数上限（订单类型仍全表扫描）
_EMPTY_RATIO = 0.3       # 空行占比超过此值才温和提示

_ZMM_HINT = (
    '这像 ZMM062 收发存表（或分析报告），不是 ZPP011 生产明细；'
    '请选择 SAP 原始导出文件（如 ZPP011_YYYYMMDD.xlsx / 微信版 9 月源表），'
    '生产明细核心列为 流程订单 / 组件物料类型 / 数量-实际（精确列名）。')

# 温和提示收集器：只存文本，供导出时 F01「口径自检」sheet 追加 INFO 行。
# 纯收集、幂等（每次 validate_source 开头 reset），绝不反向影响校验结果。
_WARNINGS = []


def reset_warnings():
    """清空本轮预检告警（每次 validate_source 开头调用，避免跨文件累积）。"""
    _WARNINGS.clear()


def collect_warnings():
    """返回本轮预检温和提示副本（供 F01 口径自检 sheet 展示）。"""
    return list(_WARNINGS)


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
    """温和提示：既走 _safe_log，也 print 一份确保诊断可见（不阻断）。

    v43.329：同时进收集器，导出时由 F01「口径自检」sheet 追加 INFO 行。
    """
    text = '[source_guard] 温和提示：%s' % msg
    _safe_log(log_cb, text, 'warning')
    print(text)
    if text not in _WARNINGS:
        _WARNINGS.append(text)


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
    reset_warnings()
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

        # 硬拒绝：三核心列必须全部存在，缺任意一列即拒绝
        missing_core = [c for c in _CORE_COLS if c not in hdr]
        if missing_core:
            raise ValueError(_fail(
                src_file,
                '缺少生产明细核心列：%s（这像 ZMM062 收发存表，不是 ZPP011 生产明细）' % ', '.join(sorted(missing_core)), hdr))

        # 订单类型 ZPxx 全表扫描（不限前 N 行，防 ZPFX 集中在表尾被漏判）；
        # 空行占比抽样只保留前 _SAMPLE_MAX 行，避免整表常驻内存。
        sample = []
        zp_hit = None
        has_type = '订单类型' in hdr
        i_type = hdr.index('订单类型') if has_type else None
        for row in it:
            if len(sample) < _SAMPLE_MAX:
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
            _warn('订单类型列全表未命中 ZPxx：ZPFX 翻箱分流本期将无数据，'
                  '预检不阻断', log_cb)

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
