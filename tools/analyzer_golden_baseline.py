# -*- coding: utf-8 -*-
"""分析结果黄金基线：建立 / 比对（只读工具，不触碰计算逻辑）。

背景
----
`analysis/analyzer.py::do_analysis_v2` 是红区核心计算入口（约 700 行、分支≈156）。
在拆分或改动它之前，必须先有"改动前后输出是否一致"的判据——否则任何重构都是
闭眼改账。本工具就是那条判据。

它做什么
--------
以 `return_dataframe=True` 走主表快速路径（与 GUI 加载完全同一条路径，
不生成 Excel、不写项目数据），把关键口径指标快照成 JSON：行数、列清单、
偏差率正/负/零/空计数、各金额与数量列合计、NaN 数、分组计数、data_id 唯一性。

它不做什么
----------
不改任何计算、不写 audit.db、不生成报表。唯一副作用是 analyzer 自身既有的
行为：向 %TEMP%/zpp011_trace.log 追加追踪日志（GUI 每次分析也会写）。

用法
----
    # 1) 建立基线（会把结果写入 tests/fixtures/golden/analysis_baseline.json）
    python tools/analyzer_golden_baseline.py --input tests/fixtures/golden/_drink9_zpp011_wx.xlsx --write

    # 2) 比对（用基线里记录的输入；也可显式 --input）
    python tools/analyzer_golden_baseline.py --compare

    # 3) 换一份真实导出重建基线（建议在红区改动前做）
    python tools/analyzer_golden_baseline.py --input "E:/ZPP011导出文件原数据/xxx.xlsx" --write

退出码：0 = 一致；1 = 存在差异；2 = 运行失败（输入/基线不可用）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DEFAULT_BASELINE = os.path.join(ROOT, "tests", "fixtures", "golden", "analysis_baseline.json")
DEFAULT_INPUT = os.path.join(ROOT, "tests", "fixtures", "golden", "_drink9_zpp011_wx.xlsx")
SCHEMA_VERSION = 1

# 需要快照合计的列（存在才采，列名可能因数据版本不同而缺失）
SUM_CANDIDATES = [
    "定额", "数量-定额", "实际", "数量-实际",
    "偏差数量", "偏差金额", "偏差金额(含税)",
    "净偏差数量", "净偏差金额", "净偏差率(%)",
]
# 需要快照取值分布的分组列
GROUP_CANDIDATES = ["物料类型", "工厂", "是否替代料", "车间"]
RATE_CANDIDATES = ["偏差率(%)", "偏差率"]

# 比对容差：同一份输入、同一台机器重跑应当逐位相同；
# 留 1e-3 绝对 / 1e-6 相对，只为吸收浮点求和顺序造成的末位抖动。
TOL_ABS = 1e-3
TOL_REL = 1e-6


# ---------------------------------------------------------------- 指标采集

def _first_present(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_metrics(df):
    """把一个分析结果 DataFrame 压缩成可稳定比对的指标字典。"""
    import pandas as pd

    metrics = {
        "rows": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns],
    }

    # 1) 偏差率分布（正/负/零/空 + 超阈值条数）
    rate_col = _first_present(df, RATE_CANDIDATES)
    if rate_col is not None:
        rates = pd.to_numeric(df[rate_col], errors="coerce")
        metrics["rate"] = {
            "column": rate_col,
            "positive": int((rates > 0).sum()),
            "negative": int((rates < 0).sum()),
            "zero": int((rates == 0).sum()),
            "nan": int(rates.isna().sum()),
            "abs_ge_10": int((rates.abs() >= 10).sum()),
            "abs_ge_100": int((rates.abs() >= 100).sum()),
            "sum": round(float(rates.sum()), 4),
            "abs_max": round(float(rates.abs().max()), 4) if len(rates) else 0.0,
        }

    # 2) 金额 / 数量列合计（口径回归最直接的发现在这里）
    sums = {}
    for col in SUM_CANDIDATES:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        sums[col] = {
            "sum": round(float(s.sum()), 4),
            "nan": int(s.isna().sum()),
            "nonzero": int((s.fillna(0) != 0).sum()),
        }
    metrics["sums"] = sums

    # 3) 分组计数（前 50 个取值，按键名排序保证可比）
    groups = {}
    for col in GROUP_CANDIDATES:
        if col not in df.columns:
            continue
        vc = df[col].fillna("").astype(str).value_counts()
        items = sorted(vc.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))[:50]
        groups[col] = {str(k): int(v) for k, v in items}
    metrics["groups"] = groups

    # 4) 主键唯一性（重复 data_id 会让已读/隔离匹配错行）
    if "data_id" in df.columns:
        ids = df["data_id"].astype(str)
        metrics["data_id"] = {
            "nunique": int(ids.nunique()),
            "duplicates": int(len(ids) - ids.nunique()),
        }

    # 5) 关键列缺失率（列存在性变化往往先在这里显形）
    missing = {}
    for col in ("data_id", "物料编码", "物料名称", "工厂", "订单日期", "定额", "实际"):
        if col in df.columns:
            missing[col] = int(df[col].isna().sum())
    metrics["missing"] = missing

    return metrics


# ---------------------------------------------------------------- 运行分析

def _pairs_sha(pairs):
    return hashlib.sha256(
        json.dumps(pairs, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def resolve_alt_pairs(spec="auto", verbose=True):
    """把 --alt-pairs 解析成 (pairs, source_label)。

    auto  : 读用户配置（%APPDATA%/ZPP011/config/alt_pairs.json），无配置时回退内置默认
    none  : 空表
    <path>: 指定 JSON 配置文件（固定口径、便于复现）
    """
    spec = (spec or "auto").strip()
    if spec == "none":
        return [], "none"
    if spec != "auto":
        if not os.path.isfile(spec):
            raise FileNotFoundError(f"替代料配置不存在: {spec}")
        with open(spec, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        pairs = data if isinstance(data, list) else data.get("pairs", [])
        label = (os.path.relpath(spec, ROOT)
                 if os.path.abspath(spec).startswith(ROOT) else spec)
        return list(pairs or []), label

    try:
        from domain.alt_material.alt_manager import load_alt_pairs
        pairs = load_alt_pairs() or []
    except Exception as exc:  # 替代料配置缺失不应阻断基线流程
        if verbose:
            print(f"[WARN] 读取替代料配置失败，按空表运行：{exc}")
        pairs = []
    return list(pairs), "auto"


def run_analysis(input_path, alt_pairs=None, alt_source="auto", verbose=True):
    """以生产同款参数跑一次主表分析，返回 (df, params, elapsed)。"""
    from analysis.analyzer import do_analysis_v2
    from core.config_manager import ConfigManager

    if alt_pairs is None:
        alt_pairs, alt_source = resolve_alt_pairs(alt_source, verbose=verbose)

    cfg = ConfigManager()
    net_offset = bool(cfg.get_net_offset_enabled())

    def _progress(step_idx, step_name, percent):
        if verbose and percent in (0, 100):
            print(f"  · [{step_idx}] {step_name} ({percent}%)")

    t0 = time.perf_counter()
    df = do_analysis_v2(
        input_file=input_path,
        output_dir=None,
        alt_pairs=alt_pairs,
        enable_net_offset=net_offset,
        return_dataframe=True,
        progress_callback=_progress,
    )
    elapsed = round(time.perf_counter() - t0, 3)

    params = {
        "alt_pairs_source": alt_source,
        "alt_pairs_count": len(alt_pairs),
        "alt_pairs_sha256": _pairs_sha(alt_pairs),
        "enable_net_offset": net_offset,
        "return_dataframe": True,
        "start_date": "",
        "end_date": "",
        "material_search": "",
    }
    return df, params, elapsed


# ---------------------------------------------------------------- 比对

def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _diff(exp, act, path, out):
    """递归比对；数值走容差，其余严格相等。"""
    if isinstance(exp, dict) and isinstance(act, dict):
        for k in sorted(set(exp) | set(act)):
            if k not in exp:
                out.append((f"{path}.{k}", "<基线无此键>", act[k], "新增"))
            elif k not in act:
                out.append((f"{path}.{k}", exp[k], "<结果无此键>", "缺失"))
            else:
                _diff(exp[k], act[k], f"{path}.{k}", out)
        return

    if isinstance(exp, list) and isinstance(act, list):
        if exp != act:
            out.append((path, f"<{len(exp)} 项>", f"<{len(act)} 项>", "列清单/顺序变化"))
        return

    if _is_number(exp) and _is_number(act):
        delta = abs(float(exp) - float(act))
        limit = max(TOL_ABS, TOL_REL * max(abs(float(exp)), abs(float(act))))
        if delta > limit:
            out.append((path, exp, act, f"Δ={delta:.6g}"))
        return

    if exp != act:
        out.append((path, exp, act, "取值不同"))


def compare_metrics(expected, actual):
    diffs = []
    _diff(expected, actual, "", diffs)
    return [tuple(x) for x in diffs]


# ---------------------------------------------------------------- 基线读写

def _input_meta(path):
    return {
        "path": os.path.relpath(path, ROOT) if os.path.abspath(path).startswith(ROOT) else path,
        "name": os.path.basename(path),
        "size": os.path.getsize(path),
        "sha256": _sha256(path),
    }


def write_baseline(input_path, baseline_path, alt_spec="auto", verbose=True):
    from utils.version_history import VERSION_HISTORY

    if not os.path.isfile(input_path):
        print(f"[ERROR] 输入文件不存在：{input_path}")
        return 2

    if verbose:
        print(f"[运行] {os.path.basename(input_path)}")
    alt_pairs, alt_source = resolve_alt_pairs(alt_spec, verbose=verbose)
    if verbose:
        print(f"[替代料] 来源={alt_source}  组数={len(alt_pairs)}")
    df, params, elapsed = run_analysis(
        input_path, alt_pairs=alt_pairs, alt_source=alt_source, verbose=verbose)
    if df is None or len(df) == 0:
        print("[ERROR] 分析结果为空，拒绝写入基线（否则基线本身不可信）")
        return 2

    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app_version": VERSION_HISTORY[0]["version"],
        "input": _input_meta(input_path),
        "params": params,
        "elapsed_sec": elapsed,
        "metrics": collect_metrics(df),
    }

    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
    tmp = baseline_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, baseline_path)

    if verbose:
        m = payload["metrics"]
        print(f"[写入] {os.path.relpath(baseline_path, ROOT)}")
        print(f"       行数={m['rows']}  列数={m['column_count']}  "
              f"偏差率+/-/0={m.get('rate', {}).get('positive', '-')}/"
              f"{m.get('rate', {}).get('negative', '-')}/"
              f"{m.get('rate', {}).get('zero', '-')}  耗时={elapsed}s")
    return 0


def compare_with_baseline(input_path, baseline_path, alt_spec=None, verbose=True):
    if not os.path.isfile(baseline_path):
        print(f"[ERROR] 基线不存在：{baseline_path}（先跑 --write）")
        return 2
    # utf-8-sig：手工用编辑器/PowerShell 改过基线时不至于因 BOM 直接崩
    with open(baseline_path, "r", encoding="utf-8-sig") as f:
        baseline = json.load(f)

    if input_path is None:
        recorded = baseline.get("input", {}).get("path")
        if not recorded:
            print("[ERROR] 基线未记录输入路径，请用 --input 指定")
            return 2
        input_path = recorded if os.path.isabs(recorded) else os.path.join(ROOT, recorded)
    if not os.path.isfile(input_path):
        print(f"[ERROR] 输入文件不存在：{input_path}")
        return 2

    # 输入指纹不同 → 基线失效，不能拿 A 文件的基线去卡 B 文件
    if baseline.get("input", {}).get("sha256") and _sha256(input_path) != baseline["input"]["sha256"]:
        print("[ERROR] 输入文件与基线记录不一致（sha256 不同）。")
        print("        换文件后必须重建基线：--input <新文件> --write")
        return 2

    # 替代料配置指纹：基线绑定的是“当时那份配置”，配置变了不能算口径回归
    stored = baseline.get("params", {}) or {}
    want_source = stored.get("alt_pairs_source", "auto")
    spec = alt_spec if alt_spec is not None else want_source
    if spec != want_source:
        print(f"[ERROR] 替代料配置来源不一致：基线={want_source}，本次={spec}")
        print("        请使用与基线相同的来源，或用 --write 重建基线。")
        return 2
    pairs, _src = resolve_alt_pairs(spec, verbose=False)
    if stored.get("alt_pairs_sha256") and _pairs_sha(pairs) != stored["alt_pairs_sha256"]:
        print("[ERROR] 替代料配置内容与基线不一致，本次比对无意义（会被误判为口径变化）：")
        print(f"        基线 {stored.get('alt_pairs_count')} 组 / 当前 {len(pairs)} 组（来源={want_source}）")
        print("        重建基线：--write；或指定基线当时的配置：--alt-pairs <路径>")
        return 2

    if verbose:
        print(f"[比对] {os.path.basename(input_path)}  "
              f"基线={os.path.basename(baseline_path)}  "
              f"建立于 {baseline.get('created_at')} / {baseline.get('app_version')}")

    df, _params, elapsed = run_analysis(
        input_path, alt_pairs=pairs, alt_source=want_source, verbose=False)
    actual = collect_metrics(df)
    diffs = compare_metrics(baseline.get("metrics", {}), actual)

    if not diffs:
        print(f"[OK] 全部指标一致（{_count_leaves(actual)} 个口径点，耗时 {elapsed}s）")
        return 0

    print(f"[DIFF] 发现 {len(diffs)} 处差异（本次耗时 {elapsed}s）：")
    for path, exp, act, note in diffs[:80]:
        print(f"  - {path or '<root>'}")
        print(f"      期望={exp!r}")
        print(f"      实际={act!r}   {note}")
    if len(diffs) > 80:
        print(f"  … 其余 {len(diffs) - 80} 处省略")
    return 1


def _count_leaves(d):
    if isinstance(d, dict):
        return sum(_count_leaves(v) for v in d.values())
    if isinstance(d, list):
        return 1
    return 1


# ---------------------------------------------------------------- CLI

def main(argv=None):
    try:  # Windows 控制台默认 GBK，中文/箭头可能崩，尽量切 UTF-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="分析结果黄金基线：建立或比对（只读，不改计算逻辑）")
    parser.add_argument("--input", help="SAP 导出 xlsx 路径")
    parser.add_argument("--baseline", default=DEFAULT_BASELINE, help="基线 JSON 路径")
    parser.add_argument("--write", action="store_true", help="建立/重建基线")
    parser.add_argument("--compare", action="store_true", help="与基线比对")
    parser.add_argument("--alt-pairs", default=None, metavar="auto|none|JSON",
                        help="替代料配置来源（默认 auto：读用户配置）")
    args = parser.parse_args(argv)

    if not args.write and not args.compare:
        parser.print_help()
        return 2
    if args.write and args.compare:
        print("[ERROR] --write 与 --compare 只能二选一")
        return 2

    try:
        if args.write:
            return write_baseline(args.input or DEFAULT_INPUT, args.baseline,
                                  alt_spec=args.alt_pairs or "auto")
        return compare_with_baseline(args.input, args.baseline,
                                     alt_spec=args.alt_pairs)
    except KeyboardInterrupt:
        print("[CANCELLED] 用户中断")
        return 2
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] 运行失败：{type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
