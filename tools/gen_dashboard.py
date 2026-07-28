#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gen_dashboard.py — ZPP011 偏差分析 12 图 HTML 看板生成器（CLI 入口）
==================================================================
薄壳：调用 analysis.analyzer.do_analysis_v2 拿到偏差明细 dev_df，
按工厂拆分后交给 analysis.dashboard_html 渲染成自包含 HTML。

所有 12 图绘制与 HTML 拼装逻辑都在 analysis/dashboard_html.py（CLI 与 GUI 共用）。

用法:
    python tools/gen_dashboard.py \
        --input "E:/ZPP011导出文件原数据/ZPP011_20260701-20260722.xlsx" \
        --start 2026-07-11 --end 2026-07-20 \
        --output "ZPP011偏差看板_20260723.html"
"""
import argparse
import contextlib
import os
import sys
import tempfile
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # CLI 无界面，纯出图
import pandas as pd

# ---------- 让项目 analysis 模块可 import ----------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from analysis.analyzer import do_analysis_v2  # noqa: E402
from analysis.dashboard_html import build_html, compute_metrics, short_name  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="ZPP011 偏差分析 12 图看板生成器")
    ap.add_argument("--input", required=True, help="原始 SAP 导出 xlsx（如 ZPP011_20260701-20260722.xlsx）")
    ap.add_argument("--start", default=None, help="分析开始日期 YYYY-MM-DD（仅算窗口内）")
    ap.add_argument("--end", default=None, help="分析结束日期 YYYY-MM-DD")
    ap.add_argument("--factory", default=None, help="只看某工厂，如 '云南达利-饮料厂'（不传则按工厂分区块出全部）")
    ap.add_argument("--output", default=None, help="输出 HTML 路径（默认同目录 偏差看板_时间戳.html）")
    ap.add_argument("--work-dir", default=None, help="do_analysis_v2 写中间报告的目录（默认系统临时目录）")
    args = ap.parse_args()

    work_dir = args.work_dir or tempfile.mkdtemp(prefix="zpp011_dash_")
    os.makedirs(work_dir, exist_ok=True)

    print(f"[1/3] 调用 do_analysis_v2 计算偏差明细（窗口 {args.start}~{args.end}）...")
    log_path = os.path.join(tempfile.gettempdir(), "gen_dashboard_run.log")
    dev_df = None
    # 吞掉 do_analysis_v2 内部的大量 DEBUG 打印，避免刷屏
    with contextlib.redirect_stdout(open(log_path, "w", encoding="utf-8")):
        dev_df = do_analysis_v2(
            input_file=args.input,
            output_dir=work_dir,
            alt_pairs=[],            # 无替代料配对时传空；如需可扩展为读取配置文件
            start_date=args.start,
            end_date=args.end,
            return_dataframe=True,
            enable_net_offset=True,
        )

    if dev_df is None or dev_df.empty:
        print("[ERR] 未拿到偏差明细数据，请检查输入文件与日期窗口。")
        sys.exit(1)
    print(f"[2/3] 拿到 dev_df：{len(dev_df)} 行 × {len(dev_df.columns)} 列")

    # 按工厂拆分：食品厂 / 饮料厂 互不干扰（--factory 可只看一家）
    factories = [args.factory] if args.factory else list(dev_df["工厂"].dropna().unique())
    blocks = {}
    for fac in factories:
        sub = dev_df[dev_df["工厂"] == fac]
        if sub.empty:
            continue
        blocks[fac] = (compute_metrics(sub), sub)
    if not blocks:
        print("[ERR] 按工厂拆分后没有可用数据。")
        sys.exit(1)
    print("       工厂拆分：" + "，".join(f"{k}={len(v[1])}条" for k, v in blocks.items()))
    meta = {
        "start": args.start or "全量",
        "end": args.end or "全量",
        "src": os.path.basename(args.input),
        "gen": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    out = args.output or os.path.join(
        os.path.dirname(os.path.abspath(args.input)),
        f"偏差看板_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
    )
    html = build_html(blocks, meta)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[3/3] 看板已生成：{out}")
    for fac, (m, _) in blocks.items():
        print(f"      [{short_name(fac)}] 条数={m['n']:,} 正={m['pos']:,.0f} 负={m['neg']:,.0f} 覆盖率={m['coverage']:.1f}%")


if __name__ == "__main__":
    main()
