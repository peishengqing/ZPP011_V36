"""独立重算对账网 CLI（ARC-002 治理工具，方案②）。

裴哥零参与即可运行：给一个 SAP 原始导出 xlsx，工具自动跑 analyzer 得到权威输出，
做三类一致性对账 + 自洽扫描，直接回答「analyzer 算错没有」。

公式溯源（已对照 analyzer 源码核实，非臆测）：
- dev「偏差数量」= 原始(数量-实际 − 数量-定额)。analyzer 直接搬原始数量差，是数量维度。
  （analyzer 内部把 数量-实际/数量-定额 改名为 实际/定额，故 dev 的「实际」「定额」是数量不是金额）
- dev「偏差率(%)」= SAP 原始导出「偏差率(%)」直透传，analyzer 不重算该列。
- dev「偏差金额」= 偏差数量 × 单价(含税)。源码 sheet5：_偏差金额 = 材料偏差 × 单价 × 1.13(税)，
  即 偏差数量 × (金额-实际(含税)/数量-实际)。数量偏差为零时金额强制为零（设计如此，非算错）。

设计原则（零跨口径假阳性）：
- 数量对账用「原始数量差」，不受税率影响，可干净证伪 analyzer 是否取错数量。
- 金额对账用「独立重算 = 原始数量差 × 原始实际单价(含税)」，与 dev 偏差金额同一恒等式，
  其余差异仅来自 analyzer 对偏差数量保留 2 位小数后再乘单价的正常舍入（≤0.05 量级）。
- 率对账用「原始偏差率透传」，任何差异都意味 analyzer 改动了该列。

用法：
  python tools/recompute_check.py --input "E:/ZPP011导出文件原数据/ZPP011_20261001-20261014.xlsx"
  python tools/recompute_check.py --input <xlsx> --out-dir sample_out

依赖：analyze 用 analysis.analyzer.do_analysis_v2（只读调用冻结区入口，不修改任何代码）。
对齐：dev 保留「原表行号」列（data_service 加载时加，2-based Excel 物理行号，表头占第1行），
原始 df 行号 +2 = 原表行号，据此关联比对。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.verify_recompute import (  # noqa: E402
    selfcheck,
)
from analysis.analyzer import do_analysis_v2  # noqa: E402  # 只读调用，不改冻结区


ALT_PATHS = [
    os.path.expanduser("~/AppData/Roaming/ZPP011/config/alt_pairs.json"),
    os.path.expanduser("~/.zpp011_audit/config/alt_pairs.json"),
]

# 容差：≤0.05 视为舍入噪声（analyzer 偏差数量保留 2 位小数后×单价导致）；
# >0.05 且 ≤0.5 为需关注；(>0.5 视为实质计算错误，本工具会重点标红)
TOL_ROUNDING = 0.05
TOL_REVIEW = 0.5


def load_alt():
    for p in ALT_PATHS:
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="ZPP011 独立重算对账网")
    ap.add_argument("--input", required=True, help="SAP 原始导出 xlsx")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "sample_out"),
                    help="报告输出目录（默认 sample_out/）")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"[recompute_check] 输入文件不存在: {args.input}")
        return 2

    raw = args.input
    df = pd.read_excel(raw)
    alt = load_alt()
    print(f"[analyzer] 跑 do_analysis_v2，输入 {df.shape[0]} 行，alt_pairs {len(alt)} 组")

    dev = do_analysis_v2(
        input_file=raw,
        output_dir=tempfile.gettempdir(),
        alt_pairs=alt,
        return_dataframe=True,
        input_df=df,
    )
    print(f"[analyzer] 输出 {dev.shape[0]} 行 × {dev.shape[1]} 列")
    assert "原表行号" in dev.columns, "analyzer 输出无 原表行号 列，无法关联对齐"
    assert dev.shape[0] == df.shape[0], (
        f"行数不一致 dev={dev.shape[0]} raw={df.shape[0]}"
    )

    name = os.path.splitext(os.path.basename(raw))[0]
    os.makedirs(args.out_dir, exist_ok=True)
    rows: list = []

    n = len(df)
    src_index = pd.Index(range(2, n + 2))  # 原表行号 2-based（Excel 物理行，表头占第1行）
    dev_src = dev["原表行号"].values

    def align(col):
        s = pd.to_numeric(df[col], errors="coerce")
        s.index = src_index
        return s.reindex(dev_src).values

    # ---------- ① 数量偏差对账（跨原始，真证伪；最强）----------
    # 注意：偏差数量 是 dev 输出列，原始 df 只有 数量-实际/数量-定额
    if {"数量-实际", "数量-定额"}.issubset(df.columns) and "偏差数量" in dev.columns:
        base_q = align("数量-实际") - align("数量-定额")
        dev_q = pd.to_numeric(dev["偏差数量"], errors="coerce").values
        d_q = np.abs(base_q - dev_q)
        for i in np.where(d_q > 0.01)[0]:
            rows.append({
                "check": "qty_mismatch", "excel_row": int(dev_src[i]),
                "existing": round(float(dev_q[i]), 4),
                "recomputed": round(float(base_q[i]), 4),
                "abs_diff": round(float(d_q[i]), 4),
                "category": "实质差异",
                "note": "dev偏差数量 ≠ 原始(数量-实际−数量-定额)",
            })
        print(f"[①数量偏差] dev偏差数量 vs 原始(数量-实际−数量-定额)：{(d_q > 0.01).sum()} 行差>0.01 / 共{len(d_q)}")

    # ---------- ② 偏差率对账（跨原始，透传完整性）----------
    if {"偏差率(%)"}.issubset(df.columns) and "偏差率(%)" in dev.columns:
        base_r = align("偏差率(%)")
        dev_r = pd.to_numeric(dev["偏差率(%)"], errors="coerce").values
        d_r = np.abs(base_r - dev_r)
        for i in np.where(d_r > 0.05)[0]:
            rows.append({
                "check": "rate_mismatch", "excel_row": int(dev_src[i]),
                "existing": round(float(dev_r[i]), 4),
                "recomputed": round(float(base_r[i]), 4),
                "abs_diff": round(float(d_r[i]), 4),
                "category": "实质差异",
                "note": "dev偏差率(%) ≠ 原始偏差率(%)，analyzer 可能改动了该透传列",
            })
        print(f"[②偏差率]   dev偏差率(%) vs 原始偏差率(%)：{(d_r > 0.05).sum()} 行差>0.05 / 共{len(d_r)}")

    # ---------- ③ 偏差金额对账（独立重算 = 原始数量差 × 原始实际单价含税）----------
    amt_col = "偏差金额" if "偏差金额" in dev.columns else "偏差金额(含税)"
    if {"数量-实际", "数量-定额", "金额-实际(含税)"}.issubset(df.columns) and amt_col in dev.columns:
        raw_act_qty = align("数量-实际")
        raw_quo_qty = align("数量-定额")
        raw_act_amt = align("金额-实际(含税)")
        # 单价(含税) = 金额-实际(含税) / 数量-实际；除零填 NaN（后续按行判）
        with np.errstate(divide="ignore", invalid="ignore"):
            unit_price = np.where(raw_act_qty != 0, raw_act_amt / raw_act_qty, np.nan)
        raw_qty_diff = raw_act_qty - raw_quo_qty
        expected_amt = raw_qty_diff * unit_price  # 独立重算的偏差金额
        dev_a = pd.to_numeric(dev[amt_col], errors="coerce").values
        d_a = np.abs(expected_amt - dev_a)

        for i in np.where(d_a > 0.01)[0]:
            diff = float(d_a[i])
            # 显示舍入提示：原始数量差极小(<0.005)被四舍五入成 0.00，但金额按真实值计算
            rounding_hidden = abs(float(raw_qty_diff[i])) < 0.005 and abs(float(dev_a[i])) > 0.01
            if rounding_hidden:
                cat = "显示舍入(非算错)"
                note = "数量偏差<0.005被显示为0.00，金额仍按真实数量偏差计算（数据质量提示）"
            elif diff <= TOL_ROUNDING:
                cat = "舍入噪声"
                note = "偏差数量保留2位小数后×单价的正常舍入，非计算错误"
            elif diff <= TOL_REVIEW:
                cat = "需关注"
                note = "金额差异 0.05~0.5，建议人工复核"
            else:
                cat = "实质差异"
                note = "金额差异>0.5，疑似 analyzer 金额列/单价取错"
            rows.append({
                "check": "amount_mismatch", "excel_row": int(dev_src[i]),
                "existing": round(float(dev_a[i]), 4),
                "recomputed": round(float(expected_amt[i]), 4) if not np.isnan(expected_amt[i]) else "",
                "abs_diff": round(diff, 4),
                "category": cat,
                "note": note,
            })
        n_round = int(((d_a > 0.01) & (d_a <= TOL_ROUNDING)).sum())
        n_hidden = int(((np.abs(raw_qty_diff) < 0.005) & (np.abs(dev_a) > 0.01) & (d_a > 0.01)).sum())
        n_review = int(((d_a > TOL_ROUNDING) & (d_a <= TOL_REVIEW)).sum())
        n_real = int((d_a > TOL_REVIEW).sum())
        print(f"[③偏差金额] dev{amt_col} vs 独立重算(数量差×实际单价含税)："
              f"差异>0.01 共{(d_a > 0.01).sum()} 行 "
              f"[舍入噪声 {n_round} / 显示舍入 {n_hidden} / 需关注 {n_review} / 实质差异 {n_real}]")

    # ---------- ④ 自洽扫描（在 dev 上）----------
    findings = selfcheck(dev, amount_col=amt_col)
    for f in findings:
        rows.append({
            "check": f["rule"], "excel_row": "",
            "existing": "", "recomputed": "", "abs_diff": f.get("n", ""),
            "category": "自洽扫描", "note": f["desc"],
        })
    if findings:
        print(f"[④自洽] 发现 {len(findings)} 类矛盾：")
        for f in findings:
            print(f"  - {f['rule']}: {f['desc']} (n={f.get('n')})")
    else:
        print("[④自洽] 未发现矛盾")

    out = os.path.join(args.out_dir, f"{name}_recompute_report.csv")
    cols = ["check", "excel_row", "existing", "recomputed", "abs_diff", "category", "note"]
    pd.DataFrame(rows, columns=cols).to_csv(out, index=False, encoding="utf-8-sig")

    # 汇总
    real = [r for r in rows if r["category"] == "实质差异"]
    print(f"\n[完成] 报告已写: {out}  (共 {len(rows)} 条，其中实质差异 {len(real)} 条)")
    print("结论速览：数量偏差/偏差率 只要 0 实质差异即证明 analyzer 数量与率忠于源；"
          "金额无>0.5实质差异即无计算错误（≤0.05为正常舍入）。")
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())
