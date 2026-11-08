# -*- coding: utf-8 -*-
"""
core/rule_snapshot.py — F07 规则版本快照（v43.325）

目标
------------------------------------
导出成品能被追溯：用的是哪个版本规则、哪份源文件、源文件指纹、关键参数 hash、
生成时间。优先**只写 wb.properties 的 description/keywords**（openpyxl 标准
文档属性），不新增 sheet —— 表数不变、目录动态扫描与重复 decorate 幂等零影响。

设计铁律
------------------------------------
1. **不新增 sheet**（除非标准属性不可行，实测可行故不退回隐藏表）。
2. 内容：rules_version / 源文件名 / 源文件 sha256 前 12 位 / 关键参数 hash
   前 12 位 / 生成北京时间（zoneinfo Asia/Shanghai，不用本机 TZ）。
3. `write_snapshot()` 只写 properties，不改任何单元格值、不删行。
4. `set_source()` 由 analyzer 在读表前调用（登记源路径），decorate_workbook
   在导出收尾调用 `write_snapshot(wb)`；两者解耦，源文件指纹按路径惰性计算。
5. 任何失败都不阻断导出，但必须 print 诊断（禁裸 except: pass）。
6. 可被 `read_snapshot()` 读回校验：导出 → reload → 读回值一致。
"""
import hashlib
import json
import os
import traceback
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Py<3.9 兜底
    ZoneInfo = None

# 由 analyzer 在读表前登记；decorate 时惰性计算 sha256
_SOURCE = {'path': None}

# 关键参数（规则版本快照 hash 的输入）。改动任一参数都会让 hash 变化。
_PARAMS = {
    'rules_version': 'v43.325',
    'metric_tol': 0.01,
    'metric_required_sheets': ('汇总统计', '偏差金额分析', '完整偏差明细'),
    'source_required_cols': ('订单类型', '流程订单', '组件物料类型', '数量-实际'),
    'fac_food': ('1101', '云南达利-食品厂'),
    'fac_drink': ('1102', '云南达利-饮料厂'),
    'reason_codes': ('SPEC_PARSE_FAIL', 'NO_VALID_INPUT',
                     'CROSS_CONTAINER', 'BUSINESS_REVIEW'),
}


def _now_bj():
    """生成北京时间（zoneinfo，不用本机 TZ，避免 Git Bash 下慢 8 小时）。"""
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    return datetime.utcnow().isoformat(timespec='seconds') + '+00:00'


def params_hash():
    """关键参数 hash 前 12 位（稳定：sort_keys + ensure_ascii=False）。"""
    blob = json.dumps(_PARAMS, sort_keys=True, ensure_ascii=False,
                      default=list).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()[:12]


def current_version():
    """从 utils.version_history 读当前版本号（单一来源，不硬编码）。"""
    try:
        from utils.version_history import VERSION_HISTORY
        return str(VERSION_HISTORY[0]['version']) if VERSION_HISTORY else 'unknown'
    except Exception:
        return 'unknown'


def set_source(src_file):
    """登记本次导出的源文件路径（读表前调用，O(1)，不读文件内容）。"""
    _SOURCE['path'] = src_file


def source_fingerprint():
    """返回 (源文件名, sha256 前 12 位)；不可用时 ('unknown','unknown')。"""
    p = _SOURCE.get('path')
    if not p or not os.path.isfile(p):
        return 'unknown', 'unknown'
    try:
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return os.path.basename(p), h.hexdigest()[:12]
    except Exception as e:
        print('[rule_snapshot] 计算源文件指纹失败: %s' % e)
        traceback.print_exc()
        return os.path.basename(p), 'unknown'


def _payload():
    name, sha = source_fingerprint()
    return {
        'rules_version': current_version(),
        'source_file': name,
        'source_sha256_12': sha,
        'params_hash_12': params_hash(),
        'generated_at': _now_bj(),
    }


def _encode(d):
    return ';'.join('%s=%s' % (k, d[k]) for k in sorted(d))


def _decode(text):
    out = {}
    for part in str(text or '').split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            out[k.strip()] = v.strip()
    return out


def write_snapshot(wb):
    """只写 wb.properties.description / keywords，返回 payload dict（失败返回 {}）。

    ✅ 不新增 sheet、不改任何单元格 —— 表数、目录、幂等零影响。
    """
    try:
        d = _payload()
        text = _encode(d)
        wb.properties.description = text
        wb.properties.keywords = 'rules_version=%s;params_hash_12=%s' % (
            d['rules_version'], d['params_hash_12'])
        return d
    except Exception as e:
        print('[rule_snapshot] 写 wb.properties 失败（不影响导出）: %s' % e)
        traceback.print_exc()
        return {}


def read_snapshot(wb):
    """从 wb.properties.description 读回 payload dict（reload 后仍可读）。"""
    return _decode(getattr(wb.properties, 'description', '') or '')
