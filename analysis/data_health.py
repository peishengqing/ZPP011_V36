# -*- coding: utf-8 -*-
"""导入前数据体检（只读，不参与任何计算）。

为什么需要
----------
`core/source_guard.py` 只回答“这张表是不是 ZPP011 生产明细”（拒绝错表），
不回答“这张表脏到什么程度、脏在哪”。而现场绝大多数“数字不对”都源自输入：
数量列里混了文本、日期解析失败、整行重复、定额为 0、税率离谱。

本模块只做体检并出报告：不修改 DataFrame、不写库、不触发分析。
可以单独跑（CLI），也可以在导入向导里先跑一遍再决定是否继续。

用法
----
    python -m analysis.data_health tests/fixtures/golden/_drink9_zpp011_wx.xlsx
    python -m analysis.data_health <xlsx> --out output/体检单.html
    python -m analysis.data_health <xlsx> --json

退出码：0 = 无阻断项（可能有警告）；1 = 存在阻断项（不建议继续分析）；2 = 运行失败。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 与 analyzer 的读表前置校验保持一致（缺一即拒绝）
REQUIRED_COLUMNS = ["订单开始日期", "数量-定额", "数量-实际"]
# source_guard 的核心列（用于识别错表，这里只做提示级复核）
CORE_COLUMNS = ["流程订单", "组件物料类型", "数量-实际"]
# 需要做“文本污染”检查的数值列（analyzer 会在读取后 coerce，但 coerced 的行等于丢数）
NUMERIC_COLUMNS = [
    "数量-定额", "数量-实际", "材料偏差", "偏差率(%)",
    "金额-定额(含税)", "金额-实际(含税)", "实际成本", "产量", "组件数量",
]
KEY_COLUMNS = ["工厂", "物料编码", "组件物料号", "组件物料描述", "组件单位"]
DATE_COLUMN = "订单开始日期"
TAX_COLUMN = "税率"
QUOTA_COLUMN = "数量-定额"

LEVEL_WEIGHT = {"error": 25, "warn": 5, "info": 0}


# ---------------------------------------------------------------- 单表体检

def _pct(n, total):
    return round(n * 100.0 / total, 2) if total else 0.0


def _blank_mask(series):
    return series.isna() | series.astype(str).str.strip().eq("")


def _check(level, cid, title, detail, evidence=None):
    return {"level": level, "id": cid, "title": title,
            "detail": detail, "evidence": evidence or {}}


def check_dataframe(df, source_name="(内存表)"):
    """对一张明细表做体检，返回报告字典（纯函数，不改 df）。"""
    rows = int(len(df))
    checks = []

    if rows == 0:
        checks.append(_check("error", "rows", "表内没有数据行",
                             "只有表头或完全为空，无法分析。"))
    missing_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_required:
        checks.append(_check("error", "required", "缺少必需列",
                             "缺少：" + "、".join(missing_required) +
                             "；这类表不是 ZPP011 生产明细。",
                             {"missing": missing_required}))
    missing_core = [c for c in CORE_COLUMNS if c not in df.columns]
    if missing_core and not missing_required:
        # 少核心列通常意味着错表（如 ZMM062 收发存），但保留为提示，不替代 source_guard
        checks.append(_check("error", "core", "缺少生产明细核心列",
                             "缺少：" + "、".join(missing_core) +
                             "；请确认导入的是 SAP 原始导出。",
                             {"missing": missing_core}))

    if rows:
        # 1) 整行空白
        blank_rows = int(df.isna().all(axis=1).sum())
        if blank_rows:
            checks.append(_check("warn", "blank_rows", "存在整行空白",
                                 f"{blank_rows} 行（占 {_pct(blank_rows, rows)}%）全列为空。",
                                 {"rows": blank_rows}))

        # 2) 完全重复行
        dup = int(df.duplicated().sum())
        if dup:
            checks.append(_check("warn", "duplicate_rows", "存在完全重复的行",
                                 f"{dup} 行与前面某行完全相同；重复会被重复计入偏差。",
                                 {"rows": dup}))

        # 3) 关键列缺失
        key_stats = {}
        for col in KEY_COLUMNS:
            if col in df.columns:
                n = int(_blank_mask(df[col]).sum())
                if n:
                    key_stats[col] = n
        if key_stats:
            checks.append(_check("warn", "key_missing", "关键列有空值",
                                 "；".join(f"{c} {n} 行" for c, n in key_stats.items()),
                                 {"columns": key_stats}))

        # 4) 数值列被文本污染（coerce 会把这些行变成 0，等于悄悄改数）
        polluted = {}
        samples = {}
        for col in NUMERIC_COLUMNS:
            if col not in df.columns:
                continue
            raw = df[col]
            non_blank = ~_blank_mask(raw)
            as_num = pd.to_numeric(raw, errors="coerce")
            bad = non_blank & as_num.isna()
            n = int(bad.sum())
            if n:
                polluted[col] = n
                samples[col] = [str(v)[:24] for v in raw[bad].head(3).tolist()]
        if polluted:
            checks.append(_check("warn", "numeric_text", "数值列混入非数字内容",
                                 "这些行会被强制转成 0：" +
                                 "；".join(f"{c} {n} 行" for c, n in polluted.items()),
                                 {"columns": polluted, "samples": samples}))

        # 5) 日期解析
        if DATE_COLUMN in df.columns:
            parsed = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
            non_blank = ~_blank_mask(df[DATE_COLUMN])
            bad_date = int((non_blank & parsed.isna()).sum())
            if bad_date:
                level = "error" if bad_date == int(non_blank.sum()) else "warn"
                checks.append(_check(level, "date_parse", "订单开始日期无法解析",
                                     f"{bad_date} 行（占 {_pct(bad_date, rows)}%）；"
                                     "日期为空会导致周次与区间统计失真。",
                                     {"rows": bad_date}))

        # 6) 定额为 0（偏差率除零，虽然计算层已钳位，但占比高说明数据可疑）
        if QUOTA_COLUMN in df.columns:
            quota = pd.to_numeric(df[QUOTA_COLUMN], errors="coerce").fillna(0)
            zero = int((quota == 0).sum())
            if zero:
                ratio = _pct(zero, rows)
                level = "warn" if ratio >= 5 else "info"
                checks.append(_check(level, "zero_quota", "定额为 0",
                                     f"{zero} 行（占 {ratio}%）；偏差率按 0 处理。",
                                     {"rows": zero, "ratio_pct": ratio}))

        # 7) 税率 / 含税系数两种表示法都可能出现（现场表里 1.13 = 13%）
        if TAX_COLUMN in df.columns:
            tax = pd.to_numeric(df[TAX_COLUMN], errors="coerce")
            valid_rate = tax.between(0, 0.5)          # 0.13 形式
            valid_coef = tax.between(1.0, 1.5)        # 1.13 形式
            odd = int((~valid_rate & ~valid_coef).fillna(False).sum())
            if odd:
                checks.append(_check("warn", "tax_range", "税率/含税系数超出合理范围",
                                     f"{odd} 行既不落在 0~0.5（税率）也不落在 1.0~1.5（含税系数）。",
                                     {"rows": odd}))
            elif int(valid_coef.sum()) and not int(valid_rate.sum()):
                checks.append(_check("info", "tax_form", "税率列为含税系数",
                                     "取值形如 1.13 / 1.09（表示 13% / 9%），按系数解读即可。",
                                     {"values": sorted({round(float(v), 3) for v in tax.dropna().unique()})[:6]}))

        # 8) 工厂分布（多工厂时提示按工厂复核，不阻断）
        if "工厂" in df.columns:
            vc = df["工厂"].fillna("").astype(str).value_counts()
            factories = {str(k): int(v) for k, v in vc.head(10).items()}
            if len(vc) > 1:
                checks.append(_check("info", "factories", "包含多个工厂",
                                     "；".join(f"{k} {v} 行" for k, v in factories.items()),
                                     {"factories": factories}))
            elif len(vc) == 1:
                checks.append(_check("info", "factories", "单一工厂",
                                     f"{next(iter(factories))}（{rows} 行）",
                                     {"factories": factories}))

    errors = sum(1 for c in checks if c["level"] == "error")
    warns = sum(1 for c in checks if c["level"] == "warn")
    infos = sum(1 for c in checks if c["level"] == "info")
    score = max(0, 100 - sum(LEVEL_WEIGHT[c["level"]] for c in checks))

    return {
        "source": source_name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows": rows,
        "columns": int(len(df.columns)),
        "score": score,
        "summary": {"error": errors, "warn": warns, "info": infos},
        "blocking": errors > 0,
        "checks": checks,
        "column_list": [str(c) for c in df.columns],
    }


def check_file(path, sheet=None):
    """读一张 xlsx 并体检；读表与 analyzer 同源（calamine 优先，openpyxl 兜底）。"""
    from utils.excel_io import open_excel_book

    if not os.path.isfile(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    xl = open_excel_book(path)
    try:
        names = list(xl.sheet_names)
        use = sheet or ("Data" if "Data" in names else names[0])
        df = xl.parse(use)
    finally:
        close = getattr(xl, "close", None)
        if callable(close):
            close()
    report = check_dataframe(df, source_name=os.path.basename(path))
    report["sheet"] = use
    report["sheets"] = names
    report["file_size"] = os.path.getsize(path)
    return report


# ---------------------------------------------------------------- HTML 渲染

_CSS = """
body{margin:0;padding:28px 16px 56px;background:#f5f7fa;color:#1f2933;
     font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.7;font-size:15px}
.page{max-width:900px;margin:0 auto}
h1{font-size:22px;margin:0 0 6px}
.sub{color:#5a6675;font-size:13px;margin-bottom:18px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0 20px}
.kpi{background:#fff;border:1px solid #dfe5ec;border-radius:8px;padding:12px;text-align:center}
.kpi .v{font-size:20px;font-weight:700}
.kpi .l{font-size:12px;color:#5a6675}
table{width:100%;border-collapse:collapse;background:#fff;font-size:14px}
th,td{border:1px solid #dfe5ec;padding:8px 10px;text-align:left;vertical-align:top}
th{background:#eef3f8}
code{background:#f0f3f7;padding:1px 5px;border-radius:4px;font-size:13px}
.err{color:#b42318;font-weight:600}
.warn{color:#b54708;font-weight:600}
.info{color:#5a6675}
.note{margin-top:18px;font-size:13px;color:#5a6675}
"""

_LEVEL_TEXT = {"error": "阻断", "warn": "警告", "info": "提示"}


def render_html(report):
    esc = html.escape
    cls = {"error": "err", "warn": "warn", "info": "info"}
    rows_html = []
    for c in report["checks"]:
        rows_html.append(
            "<tr>"
            f"<td class='{cls[c['level']]}'>{_LEVEL_TEXT[c['level']]}</td>"
            f"<td>{esc(c['title'])}</td>"
            f"<td>{esc(c['detail'])}</td>"
            "</tr>"
        )
    if not rows_html:
        rows_html.append("<tr><td colspan='3'>未发现异常项。</td></tr>")

    verdict = "不建议直接分析" if report["blocking"] else "可以继续分析"
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数据体检单 · {esc(report['source'])}</title>
<style>{_CSS}</style></head>
<body><div class="page">
<h1>ZPP011 导入前数据体检单</h1>
<div class="sub">{esc(report['source'])}　|　工作表 {esc(str(report.get('sheet', '-')))}　|　
生成于 {esc(report['created_at'])}　|　结论：<b>{verdict}</b></div>
<div class="kpis">
  <div class="kpi"><div class="v">{report['rows']:,}</div><div class="l">数据行</div></div>
  <div class="kpi"><div class="v">{report['columns']}</div><div class="l">列数</div></div>
  <div class="kpi"><div class="v">{report['score']}</div><div class="l">体检分（100 满分）</div></div>
  <div class="kpi"><div class="v">{report['summary']['error']} / {report['summary']['warn']}</div>
       <div class="l">阻断 / 警告</div></div>
</div>
<table>
  <tr><th style="width:70px">级别</th><th style="width:220px">检查项</th><th>说明</th></tr>
  {''.join(rows_html)}
</table>
<div class="note">体检只读：不修改源文件、不改数据、不触发分析。
阻断项建议修正源表后重新导入；警告项会在分析时被静默 coerce，需自行确认是否可接受。</div>
</div></body></html>"""


# ---------------------------------------------------------------- CLI

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="导入前数据体检（只读）")
    ap.add_argument("input", help="xlsx 路径")
    ap.add_argument("--sheet", help="工作表名（默认 Data，缺失则取第一张）")
    ap.add_argument("--out", help="输出 HTML 路径")
    ap.add_argument("--json", action="store_true", help="只输出 JSON 摘要")
    args = ap.parse_args(argv)

    try:
        report = check_file(args.input, args.sheet)
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[体检] {report['source']}  行={report['rows']}  列={report['columns']}  "
              f"分={report['score']}  阻断={report['summary']['error']}  "
              f"警告={report['summary']['warn']}")
        for c in report["checks"]:
            print(f"  [{_LEVEL_TEXT[c['level']]}] {c['title']}：{c['detail']}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(render_html(report))
        print(f"[写入] {args.out}")

    return 1 if report["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
