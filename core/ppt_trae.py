#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ppt_trae.py — 「智能PPT · TRAE 分厂版」（9 页）

来源：本模块版式/配色 1:1 移植自 TRAE SOLO 生成的
      `make_ppt.py`（食品厂 / 饮料厂分厂专题，16:9 widescreen）。
      原脚本把全部数据硬编码在 `D = {...}` 字典里，本模块改为**从分析结果
      Excel 实时计算**，换任何一期数据出的报告数字都会跟着变。

数据口径（已对 `ZPP011偏差分析最终版_20261004_164358.xlsx` 逐值核实）：
  · `汇总统计`        —— 唯一主数据源。含 工厂/车间/物料分类 × 正负偏差金额(含税)/
                         总条数/备注覆盖率/预警分级。TRAE 的 -446.4万、-201.7万、
                         -244.8万、17647条、车间数、预警红黄绿全部出自此表。
  · `偏差原因分析`    —— 原因 TOP。列 `备注原因` + `净偏差数量`（**数量口径**，
                         不是金额，故页面标签写「净偏差数量」而非「金额」）。
  · `📋 分析说明`     —— `分析日期范围` / `动态阈值数值`，用于封面与页脚。

⚠ 与「偏差金额分析」「完整偏差明细」的区别（易踩坑）：
  `汇总统计`/`偏差金额分析` 走 **`偏差金额(含税)`**；
  `完整偏差明细` 走 **`偏差金额`**（且另有扣掉替代料抵扣的 `净偏差金额`）。
  三者数值不可混用，本模块只用前两者 + 明细的日期列。

对外接口：`generate_trae_report(excel_path, output_path, log_cb=None) -> bool`
"""
import os
import traceback

import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

# ---------------- 配色（与 TRAE 脚本一致，勿改） ----------------
NAVY       = RGBColor(0x00, 0x33, 0x66)
TEAL       = RGBColor(0x4B, 0xAC, 0xC6)
DARK       = RGBColor(0x21, 0x2B, 0x36)
GRAY       = RGBColor(0x5A, 0x66, 0x72)
BAND       = RGBColor(0xE9, 0xF1, 0xF5)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
RED        = RGBColor(0xC0, 0x39, 0x2B)
YEL        = RGBColor(0xE1, 0xB0, 0x10)
GRN        = RGBColor(0x2E, 0x9E, 0x5B)
LIGHT_BLUE = RGBColor(0xC5, 0xE4, 0xF2)
DEEP_NAVY  = RGBColor(0x00, 0x22, 0x4C)
FOOD       = RGBColor(0x2E, 0x7D, 0x9A)   # 食品厂代表色
BEV        = RGBColor(0xC0, 0x39, 0x2B)   # 饮料厂代表色
LINE_GRAY  = RGBColor(0xE0, 0xE5, 0xEA)

FONT_CN = "微软雅黑"

SW, SH = 13.333, 7.5

# 工厂识别：名称含「食品」→ 食品厂；含「饮料」→ 饮料厂
FACTORY_SPECS = [
    {"key": "food", "name": "食品厂", "color": FOOD, "kw": "食品"},
    {"key": "bev",  "name": "饮料厂", "color": BEV,  "kw": "饮料"},
]

TOP_N_WORKSHOP = 8      # 车间排名最多几条
TOP_N_REASON   = 6      # 原因 TOP 几条
N_FACTORY_SLOT = 2      # 期望工厂数（少于此数则补「本期无数据」页）


# ============================================================================
# 数据装载：Excel  →  D 字典
# ============================================================================
def _safe_log(log_cb, msg, level="info"):
    """调用外部 log_cb，且绝不因日志本身的问题让生成流程崩掉。

    v43.156 血的教训：GUI 侧传入的回调签名是 `(msg, level)`，
    旧代码只传 1 个参 → 失败时这行本身抛 TypeError，把原始异常顶掉。
    这里做三层兜底：正规 → 降级单参 → 静默吞掉。
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


def _fmt_wan(v):
    """金额 → 万元，保留 2 位小数（裴哥 2026-10-04 确认）。"""
    try:
        return round(float(v) / 10000.0, 2)
    except Exception:
        return 0.0


def _num(v):
    """安全转 float，NaN/None/非数一律 0.0。"""
    try:
        f = float(v)
        if pd.isna(f):
            return 0.0
        return f
    except Exception:
        return 0.0


class DataError(Exception):
    """输入数据不满足生成条件（对外只报这个，别的都算内部 bug）。"""


def _read_meta(excel_path):
    """从「📋 分析说明」表读分析日期范围与动态阈值。读不到给默认值。"""
    info = {"range": "未知周期", "threshold": "±10% (固定阈值)"}
    try:
        raw = pd.read_excel(excel_path, sheet_name="📋 分析说明", header=None)
    except Exception:
        return info
    kv = {}
    for _, row in raw.iterrows():
        if row.empty:
            continue
        k = str(row.iloc[0]).strip()
        if k and len(row) > 1:
            kv[k] = str(row.iloc[1]).strip()
    rng = kv.get("分析日期范围", "")
    if rng:
        info["range"] = rng.replace("～", "~").strip()
    thr = kv.get("动态阈值数值", "")
    if thr and "%" in thr:
        info["threshold"] = f"{thr.strip()} (固定阈值)"
    return info


def _read_summary(excel_path):
    """读「汇总统计」表 —— 本模块唯一主数据源。"""
    try:
        df = pd.read_excel(excel_path, sheet_name="汇总统计")
    except Exception as e:
        raise DataError(
            f"读取「汇总统计」表失败：{e}\n\n"
            "本报告需要**分析结果 Excel**（含 12 个 Sheet 的完整报告），"
            "不是原始导入表。请先在软件里执行「导出完整分析报告」。"
        )
    if df is None or df.empty:
        raise DataError("「汇总统计」表为空，没有可分析的数据。")

    need = ["工厂名称", "车间", "物料分类", "总偏差金额(含税)", "总条数"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise DataError(
            f"「汇总统计」表缺少必要列：{', '.join(missing)}\n"
            f"实际列：{list(df.columns)}"
        )
    return df


def _read_reasons(excel_path):
    """读「偏差原因分析」表，返回 {工厂名: DataFrame}；读不到返回空 dict。"""
    try:
        rdf = pd.read_excel(excel_path, sheet_name="偏差原因分析")
    except Exception:
        return {}
    if rdf is None or rdf.empty:
        return {}
    if "备注原因" not in rdf.columns:
        return {}
    out = {}
    fcol = "工厂" if "工厂" in rdf.columns else None
    if fcol:
        for fac, sub in rdf.groupby(fcol):
            out[str(fac).strip()] = sub
    else:
        out["*"] = rdf
    return out


def _build_factory(sub, reasons_sub, spec, meta):
    """把某工厂的汇总统计行聚成 TRAE 需要的结构。"""
    total_amt = _num(sub["总偏差金额(含税)"].sum())
    pos_amt = _num(sub["正偏差金额(含税)"].sum()) if "正偏差金额(含税)" in sub.columns else 0.0
    neg_amt = _num(sub["负偏差金额(含税)"].sum()) if "负偏差金额(含税)" in sub.columns else 0.0
    cnt = int(_num(sub["总条数"].sum()))

    # 备注覆盖率：TRAE 用的是算术均值（已核实 32.8%/27.1% 即均值口径）
    cov = 0.0
    if "备注覆盖率" in sub.columns:
        vals = pd.to_numeric(sub["备注覆盖率"], errors="coerce").dropna()
        if len(vals):
            cov = round(float(vals.mean()) * 100, 1)

    # 车间排名：净偏差为负的，按绝对值降序取 TOP_N
    ws = (sub.groupby("车间", dropna=False)
             .agg(amt=("总偏差金额(含税)", "sum"), cnt=("总条数", "sum"))
             .reset_index())
    ws = ws[ws["amt"] < 0].copy()
    ws["abs_amt"] = ws["amt"].abs()
    ws = ws.sort_values("abs_amt", ascending=False).head(TOP_N_WORKSHOP)
    workshop_top = [(str(r["车间"]), round(_num(r["amt"]) / 10000.0, 2))
                    for _, r in ws.iterrows()]

    # 物料分类
    ct = (sub.groupby("物料分类", dropna=False)
             .agg(amt=("总偏差金额(含税)", "sum")).reset_index()
             .sort_values("amt"))
    categories = [{"name": str(r["物料分类"]),
                   "amt_wan": round(_num(r["amt"]) / 10000.0, 2)}
                  for _, r in ct.iterrows()]

    # 预警分级：优先用表里的「预警」列；缺列则按偏差率分档（3% 红 / 2% 黄 / 其余绿）
    alerts = {"红色预警": 0, "黄色预警": 0, "绿色预警": 0}
    if "预警" in sub.columns:
        vc = sub["预警"].astype(str).str.strip().value_counts()
        for k in alerts:
            hits = vc[[i for i in vc.index if k in i]].sum()
            alerts[k] = int(hits)
    else:
        alerts = _alerts_by_rate(sub)

    # 原因 TOP：按 `备注原因` 聚合 `净偏差数量`（数量口径，非金额）
    reasons = []
    if reasons_sub is not None and len(reasons_sub):
        col = "净偏差数量" if "净偏差数量" in reasons_sub.columns else None
        if col:
            g = (reasons_sub.groupby("备注原因", dropna=False)[col]
                       .sum().reset_index(name="q"))
            g["abs_q"] = g["q"].abs()
            g = g.sort_values("abs_q", ascending=False).head(TOP_N_REASON)
            reasons = [(str(r["备注原因"]), round(_num(r["q"]) / 10000.0, 2))
                       for _, r in g.iterrows()]

    return {
        "name": spec["name"],
        "color": spec["color"],
        "has_data": True,
        "amt_wan": round(total_amt / 10000.0, 2),
        "pos_wan": round(pos_amt / 10000.0, 2),
        "neg_wan": round(neg_amt / 10000.0, 2),
        "cnt": cnt,
        "workshops": int(sub["车间"].nunique()),
        "cov": cov,
        "alerts": alerts,
        "categories": categories,
        "workshop_top": workshop_top,
        "reasons": reasons,
        "_raw_amt": total_amt,
    }


def _alerts_by_rate(sub):
    """缺「预警」列时的兜底：按 `偏差率` 分档（红 ≥3% / 黄 ≥2% / 其余绿）。

    只在极老版本 Excel（无预警列）时启用，正常分析结果都有该列。
    """
    out = {"红色预警": 0, "黄色预警": 0, "绿色预警": 0}
    if "偏差率" not in sub.columns:
        return out
    r = pd.to_numeric(sub["偏差率"], errors="coerce").abs() / 100.0
    out["红色预警"] = int((r >= 0.03).sum())
    out["黄色预警"] = int(((r >= 0.02) & (r < 0.03)).sum())
    out["绿色预警"] = int((r < 0.02).sum())
    return out


def _empty_factory(spec):
    """某工厂本期无数据时的占位结构（页面照样出，内容写「本期无数据」）。"""
    return {
        "name": spec["name"], "color": spec["color"], "has_data": False,
        "amt_wan": 0.0, "pos_wan": 0.0, "neg_wan": 0.0, "cnt": 0,
        "workshops": 0, "cov": 0.0,
        "alerts": {"红色预警": 0, "黄色预警": 0, "绿色预警": 0},
        "categories": [], "workshop_top": [], "reasons": [],
        "_raw_amt": 0.0,
    }


def build_dataset(excel_path):
    """读 Excel → 完整 D 字典。口径见模块 docstring。"""
    meta = _read_meta(excel_path)
    df = _read_summary(excel_path)
    reasons_by_fac = _read_reasons(excel_path)

    total_amt = _num(df["总偏差金额(含税)"].sum())
    total_cnt = int(_num(df["总条数"].sum()))
    # 全局备注覆盖率：TRAE 口径 = 各厂均值的平均
    covs = []
    if "备注覆盖率" in df.columns:
        vals = pd.to_numeric(df["备注覆盖率"], errors="coerce").dropna()
        covs = [float(v) * 100 for v in vals]
    total_cov = round(sum(covs) / len(covs), 1) if covs else 0.0

    D = {
        "month": _month_label(meta["range"]),
        "range": meta["range"],
        "threshold": meta["threshold"],
        "total": {
            "amt_wan": round(total_amt / 10000.0, 2),
            "cnt": total_cnt,
            "cov": total_cov,
            # 按「车间 × 工厂」对数计，不做车间名全局去重：
            # 「综合组」两个厂都有，全局去重会少算 1（15），而页面 KPI 卡写的是
            # 「食品 9 + 饮料 7」，口径必须一致，故用相加（16）。
            "workshops": int(sum(
                sub["车间"].nunique() for _, sub in df.groupby("工厂名称"))),
        },
        "food": _empty_factory(FACTORY_SPECS[0]),
        "bev": _empty_factory(FACTORY_SPECS[1]),
    }

    for spec in FACTORY_SPECS:
        mask = df["工厂名称"].astype(str).str.contains(spec["kw"], na=False)
        sub = df[mask]
        if sub.empty:
            # 无数据不报错：占位结构会让对应页输出「本期无数据」说明页
            continue
        # 原因表按工厂名匹配（原因表工厂列存的是「云南达利-食品厂」这类全名）
        rsub = None
        for key, val in reasons_by_fac.items():
            if key == "*":
                rsub = val
                break
            if spec["kw"] in key:
                rsub = val
                break
        D[spec["key"]] = _build_factory(sub, rsub, spec, meta)
    return D


def _month_label(rng):
    """「2026-09-01 ~ 2026-09-30」→「2026 年 9 月」；跨月则显示完整区间。"""
    try:
        txt = str(rng).replace("～", "~").strip()
        if "~" not in txt:
            return txt
        a, b = [x.strip() for x in txt.split("~", 1)]
        ya, ma, _ = a.split("-")
        yb, mb, _ = b.split("-")
        if ya == yb and ma == mb:
            return f"{int(ya)} 年 {int(ma)} 月"
        return f"{int(ya)} 年 {int(ma)} 月 - {int(yb)} 年 {int(mb)} 月"
    except Exception:
        return str(rng)


# ============================================================================
# 绘图工具（与 TRAE 脚本一致）
# ============================================================================
def set_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def rect(slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = color
    sp.line.fill.background()
    sp.shadow.inherit = False
    return sp


def text(slide, x, y, w, h, t, size, color, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT_CN):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, ln in enumerate(str(t).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.bold = bold
        r.font.name = font
    return tb


def header(slide, title, sub=""):
    rect(slide, 0, 0, SW, 1.0, NAVY)
    rect(slide, 0, 0.95, SW, 0.06, TEAL)
    rect(slide, 0.5, 0.18, 0.14, 0.64, TEAL)
    text(slide, 0.85, 0.22, 8.5, 0.6, title, 26, WHITE, bold=True,
         anchor=MSO_ANCHOR.MIDDLE)
    text(slide, 9.2, 0.32, 3.5, 0.45, sub, 12, LIGHT_BLUE,
         align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def footer(slide, idx, D):
    text(slide, 0.5, 7.05, 8, 0.3, "ZPP011 生产偏差分析 · " + D["month"], 9, GRAY)
    text(slide, 11.5, 7.05, 1.3, 0.3, f"{idx:02d}", 9, GRAY, align=PP_ALIGN.RIGHT)


def bar_chart(slide, x, y, w, h, cats, vals, colors):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("金额(万元)", vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,
                                Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = False
    ser = ch.plots[0].series[0]
    for i, c in enumerate(colors):
        try:
            pt = ser.points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = c
        except Exception:
            pass
    try:
        ch.value_axis.tick_labels.font.size = Pt(10)
        ch.value_axis.tick_labels.font.color.rgb = GRAY
    except Exception:
        pass
    try:
        ch.category_axis.tick_labels.font.size = Pt(11)
        ch.category_axis.tick_labels.font.color.rgb = DARK
    except Exception:
        pass
    return ch


def kpi_card(slide, x, y, w, h, label, value, desc, color):
    rect(slide, x, y, w, h, BAND)
    rect(slide, x, y, w, 0.1, color)
    text(slide, x + 0.25, y + 0.3, w - 0.5, 0.35, label, 12, GRAY, bold=True)
    text(slide, x + 0.25, y + 0.7, w - 0.5, 0.6, value, 28, color, bold=True)
    text(slide, x + 0.25, y + 1.35, w - 0.5, 0.35, desc, 9, GRAY)


def _ratio_bar(slide, x, y, name_w, val_x, bar_w, row, name, disp_v, maxv,
               base_color, top_color, sign_prefix="-"):
    """排行条：斑马底 + 名称 + 长度按绝对值缩放的条 + 数值。"""
    yy = y + row * 0.52
    rect(slide, x, yy, name_w, 0.42, BAND if row % 2 == 0 else LIGHT_BLUE)
    text(slide, x + 0.15, yy + 0.06, name_w - 0.25, 0.3, name, 10.5, DARK,
         bold=True, anchor=MSO_ANCHOR.MIDDLE)
    frac = (abs(disp_v) / maxv) if maxv else 0
    bw = max(bar_w * frac, 0.02)
    rect(slide, val_x, yy + 0.08, bw, 0.26, top_color if row < 3 else base_color)
    text(slide, val_x + bw + 0.1, yy + 0.04, 1.3, 0.3,
         f"{sign_prefix}{abs(disp_v):.2f}", 11, DARK, bold=True,
         anchor=MSO_ANCHOR.MIDDLE)


# ============================================================================
# 9 页正文
# ============================================================================
def _p1_cover(prs, D):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(s, NAVY)
    rect(s, 11.6, 0, 1.73, SH, DEEP_NAVY)
    rect(s, 0, 5.6, SW, 0.09, TEAL)
    text(s, 1.1, 2.0, 9.0, 0.5, "云南达利食品 · 生产物料偏差分析", 16, TEAL, bold=True)
    text(s, 1.1, 2.7, 9.5, 1.2, "ZPP011 生产偏差分析", 42, WHITE, bold=True)
    text(s, 1.1, 4.0, 9.0, 0.5, "食品厂 · 饮料厂 分厂专题", 18, LIGHT_BLUE)
    text(s, 1.1, 5.85, 8.0, 0.4, f"分析周期: {D['range']}", 13, TEAL)
    text(s, 1.1, 6.3, 8.0, 0.4, f"偏差判定阈值: {D['threshold']}", 13, TEAL)


def _p2_toc(prs, D):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(s, WHITE)
    header(s, "目录", "Agenda")
    toc = [
        ("01", "总体概览", "两厂核心数据对比"),
        ("02", "食品厂专题", "车间排名 / 物料分类 / 原因 TOP"),
        ("03", "饮料厂专题", "车间排名 / 物料分类 / 原因 TOP"),
        ("04", "预警对比 & 综合建议", "红黄绿预警 + 改进方向"),
    ]
    y = 1.7
    for num, t, d in toc:
        rect(s, 0.7, y, 1.0, 0.8, BAND)
        text(s, 0.7, y, 1.0, 0.8, num, 24, NAVY, bold=True,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, 2.0, y + 0.1, 6, 0.45, t, 20, DARK, bold=True)
        text(s, 2.0, y + 0.55, 8, 0.3, d, 12, GRAY)
        rect(s, 2.0, y + 0.95, 10.2, 0.02, LINE_GRAY)
        y += 1.2
    footer(s, 2, D)


def _p3_overview(prs, D):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(s, WHITE)
    header(s, "总体概览 · 两厂对比", "Overview")
    t = D["total"]
    f, b = D["food"], D["bev"]

    kpi_card(s, 0.7, 1.4, 2.9, 1.8, "总净偏差金额",
             f"{t['amt_wan']:.2f} 万元", "净多耗 (含税)", RED)
    desc = f"食品 {f['cnt']:,} / 饮料 {b['cnt']:,}" if f["has_data"] and b["has_data"] else "—"
    kpi_card(s, 3.78, 1.4, 2.9, 1.8, "偏差记录条数", f"{t['cnt']:,}", desc, NAVY)
    kpi_card(s, 6.86, 1.4, 2.9, 1.8, "平均备注覆盖率",
             f"{t['cov']}%", "低于 50% 健康线", YEL)
    kpi_card(s, 9.94, 1.4, 2.9, 1.8, "涉及车间",
             f"{t['workshops']} 个",
             f"食品 {f['workshops']} + 饮料 {b['workshops']}", TEAL)

    for i, key in enumerate(["food", "bev"]):
        fac = D[key]
        x = 0.7 + i * 6.15
        rect(s, x, 3.55, 5.85, 2.9, BAND)
        rect(s, x, 3.55, 5.85, 0.55, fac["color"])
        text(s, x + 0.3, 3.65, 5.0, 0.4, fac["name"], 18, WHITE, bold=True)
        if not fac["has_data"]:
            text(s, x + 0.3, 4.6, 5.0, 0.6, "本期无数据", 18, GRAY, bold=True)
            continue
        items = [
            ("净偏差", f"{fac['amt_wan']:+.2f} 万", RED),
            ("偏差条数", f"{fac['cnt']:,}", DARK),
            ("备注覆盖率", f"{fac['cov']}%", YEL),
        ]
        for j, (lab, val, col) in enumerate(items):
            cx = x + 0.3 + j * 1.85
            text(s, cx, 4.3, 1.8, 0.3, lab, 10, GRAY)
            text(s, cx, 4.6, 1.8, 0.55, val, 18, col, bold=True)
        text(s, x + 0.3, 5.35, 5.0, 0.3, "预警分级", 10, GRAY)
        ax = x + 0.3
        for lvl in ("红色预警", "黄色预警", "绿色预警"):
            cnt = fac["alerts"][lvl]
            c = RED if lvl == "红色预警" else (YEL if lvl == "黄色预警" else GRN)
            rect(s, ax, 5.7, 0.35, 0.35, c, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
            text(s, ax + 0.45, 5.7, 0.6, 0.35, f"{lvl[:1]} {cnt}", 11, DARK,
                 bold=True, anchor=MSO_ANCHOR.MIDDLE)
            ax += 1.5

    rect(s, 0.7, 6.65, 12.0, 0.4, NAVY)
    text(s, 1.0, 6.7, 11.5, 0.35, _overview_conclusion(f, b), 11, WHITE)
    footer(s, 3, D)


def _overview_conclusion(f, b):
    """自动生成分厂对比结论句（不再硬编码具体数字）。"""
    if not (f["has_data"] and b["has_data"]):
        live = [x["name"] for x in (f, b) if x["has_data"]]
        return f"本期仅 {'、'.join(live) or '无'} 有偏差数据，另一工厂本期无记录"
    parts = []
    bigger = "饮料厂" if b["amt_wan"] < f["amt_wan"] else "食品厂"
    parts.append(f"{bigger}净偏差金额更大 ({min(f['amt_wan'], b['amt_wan']):.2f}万)")
    more = "食品厂" if f["cnt"] > b["cnt"] else "饮料厂"
    parts.append(f"{more}偏差条数更多 ({max(f['cnt'], b['cnt']):,}条)")
    return "，".join(parts) + "，两者偏差特征差异显著"


def _p4_workshop(prs, D, fac_key, page_no):
    """第 4 / 6 页：单厂车间排名。"""
    f = D[fac_key]
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(s, WHITE)
    header(s, f"{f['name']}专题 · 车间偏差排名",
           f"{f['name']} · Workshop Ranking")

    if not f["has_data"]:
        rect(s, 0.7, 3.0, 12.0, 1.2, BAND)
        text(s, 1.0, 3.4, 11.4, 0.6, f"{f['name']}本期无偏差数据", 20,
             f["color"], bold=True, align=PP_ALIGN.CENTER)
        footer(s, page_no, D)
        return

    text(s, 0.7, 1.25, 4, 0.4, "核心指标", 14, DARK, bold=True)
    kpi_card(s, 0.7, 1.7, 4.0, 1.55, "净偏差金额",
             f"{f['amt_wan']:+.2f} 万", "净多耗", f["color"])
    kpi_card(s, 0.7, 3.4, 1.95, 1.4, "偏差条数",
             f"{f['cnt']:,}", f"{f['workshops']} 个车间", DARK)
    kpi_card(s, 2.75, 3.4, 1.95, 1.4, "备注覆盖率",
             f"{f['cov']}%", "低于 50% 健康线", YEL)

    text(s, 0.7, 5.0, 4, 0.4, "预警分级", 13, DARK, bold=True)
    ax = 0.7
    for lvl in ("红色预警", "黄色预警", "绿色预警"):
        cnt = f["alerts"][lvl]
        c = RED if lvl == "红色预警" else (YEL if lvl == "黄色预警" else GRN)
        rect(s, ax, 5.45, 1.25, 0.9, c, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        text(s, ax, 5.55, 1.25, 0.3, lvl, 9, WHITE, align=PP_ALIGN.CENTER)
        text(s, ax, 5.8, 1.25, 0.5, str(cnt), 18, WHITE, bold=True,
             align=PP_ALIGN.CENTER)
        ax += 1.35

    text(s, 5.2, 1.25, 7.5, 0.4,
         f"车间净偏差金额 TOP{TOP_N_WORKSHOP} (万元, 绝对值降序)", 14, DARK, bold=True)
    top = f["workshop_top"]
    if not top:
        text(s, 5.2, 1.75, 7.5, 0.4, "本期无负偏差车间", 12, GRAY)
    else:
        maxv = max(abs(v) for _, v in top)
        for i, (name, v) in enumerate(top):
            _ratio_bar(s, 5.2, 1.75, 2.3, 7.6, 4.5, i, name, v, maxv,
                       f["color"], RED)
    footer(s, page_no, D)


def _p5_category(prs, D, fac_key, page_no):
    """第 5 / 7 页：单厂物料分类 + 原因 TOP。"""
    f = D[fac_key]
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(s, WHITE)
    header(s, f"{f['name']}专题 · 物料分类 & 偏差原因",
           f"{f['name']} · Category & Reason")

    if not f["has_data"]:
        rect(s, 0.7, 3.0, 12.0, 1.2, BAND)
        text(s, 1.0, 3.4, 11.4, 0.6, f"{f['name']}本期无偏差数据", 20,
             f["color"], bold=True, align=PP_ALIGN.CENTER)
        footer(s, page_no, D)
        return

    text(s, 0.7, 1.25, 5.5, 0.4, "按物料分类 · 净偏差金额 (万元)", 14, DARK, bold=True)
    cats = f["categories"]
    if cats:
        bar_chart(s, 0.7, 1.7, 5.5, 2.9,
                  cats=[c["name"] for c in cats],
                  vals=[c["amt_wan"] for c in cats],
                  colors=[RED if c["amt_wan"] < 0 else GRN for c in cats])
    else:
        text(s, 0.7, 2.8, 5.5, 0.4, "本期无分类数据", 12, GRAY)

    rect(s, 0.7, 4.8, 5.5, 1.6, BAND)
    text(s, 0.9, 4.95, 5.0, 0.35, f"{f['name']}特征", 12, f["color"], bold=True)
    text(s, 0.9, 5.3, 5.0, 1.0, _category_summary(f), 11, DARK)

    text(s, 6.7, 1.25, 6, 0.4,
         f"偏差原因 TOP{TOP_N_REASON} (按净偏差数量)", 14, DARK, bold=True)
    rt = f["reasons"]
    if not rt:
        text(s, 6.7, 1.7, 6, 0.4, "本期无原因归因数据（备注覆盖率过低）", 12, GRAY)
    else:
        maxr = max(abs(v) for _, v in rt)
        for i, (name, v) in enumerate(rt):
            _ratio_bar(s, 6.7, 1.7, 3.0, 9.8, 4.2, i, name, v, maxr,
                       TEAL, RED, sign_prefix="+" if v > 0 else "-")

    rect(s, 6.7, 4.95, 6.0, 1.45, NAVY)
    text(s, 6.9, 5.1, 5.6, 0.35, "首要根因", 13, TEAL, bold=True)
    text(s, 6.9, 5.5, 5.6, 0.75, _root_cause(f), 11, WHITE)
    footer(s, page_no, D)


def _category_summary(f):
    """自动生成「XX厂特征」文字。"""
    cats = f["categories"]
    if not cats:
        return "本期无物料分类数据。"
    worst = min(cats, key=lambda c: c["amt_wan"])
    others = [c for c in cats if c is not worst]
    if others and abs(others[0]["amt_wan"]) < 5:
        tail = "、".join(f"{c['name']} {c['amt_wan']:+.2f} 万" for c in others)
        tail_txt = f"{tail}，偏差相对很小"
    else:
        tail_txt = "、".join(f"{c['name']} {c['amt_wan']:+.2f} 万" for c in others)
    avg = f["amt_wan"] / f["cnt"] if f["cnt"] else 0
    return (f"{worst['name']}净偏差 {worst['amt_wan']:+.2f} 万，是绝对主体；"
            f"{tail_txt}。共 {f['cnt']:,} 条，单条平均 {avg:+.2f} 万元。")


def _root_cause(f):
    """自动生成「首要根因」文字。"""
    rt = f["reasons"]
    if not rt:
        return (f"{f['name']}备注覆盖率仅 {f['cov']}%，本期缺少可归因的备注，"
                f"建议优先补齐偏差原因记录。")
    top = max(rt, key=lambda kv: abs(kv[1]))
    share = abs(top[1]) / abs(f["_raw_amt"] / 10000.0) if f["_raw_amt"] else 0
    pct = share * 100 if share <= 1.5 else 0
    pct_txt = f"，占该厂偏差约 {pct:.0f}%" if pct > 0 else ""
    return (f"「{top[0]}」净偏差 {top[1]:+.2f} 万{pct_txt} —— "
            f"为该厂偏差量最大的可治理方向，建议优先排查。")


def _p8_alerts(prs, D):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(s, WHITE)
    header(s, "预警对比 & 改进建议", "Alerts & Actions")

    text(s, 0.7, 1.25, 12, 0.4, "两厂预警分级对比", 14, DARK, bold=True)
    rect(s, 0.7, 1.75, 12.0, 0.5, NAVY)
    for cx, label in ((1.0, "工厂"), (4.0, "红色预警"),
                      (7.0, "黄色预警"), (10.0, "绿色预警")):
        text(s, cx, 1.82, 2.5, 0.4, label, 12, WHITE, bold=True,
             align=PP_ALIGN.CENTER if cx != 1.0 else PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.MIDDLE)

    rows = [(D["food"]["name"], D["food"], FOOD),
            (D["bev"]["name"], D["bev"], BEV)]
    for i, (name, fac, color) in enumerate(rows):
        yy = 2.25 + i * 0.55
        rect(s, 0.7, yy, 12.0, 0.5, BAND if i % 2 == 0 else LIGHT_BLUE)
        rect(s, 0.7, yy, 0.08, 0.5, color)
        text(s, 1.0, yy + 0.1, 2.5, 0.35, name, 13, DARK, bold=True,
             anchor=MSO_ANCHOR.MIDDLE)
        for cx, lvl, col in ((4.0, "红色预警", RED),
                             (7.0, "黄色预警", YEL),
                             (10.0, "绿色预警", GRN)):
            text(s, cx, yy + 0.1, 2.5, 0.35, str(fac["alerts"][lvl]), 14,
                 col, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    cols = [(D["food"]["name"] + "改进方向", FOOD, _build_actions(D["food"])),
            (D["bev"]["name"] + "改进方向", BEV, _build_actions(D["bev"]))]
    x = 0.7
    for title, color, items in cols:
        rect(s, x, 3.6, 6.0, 3.2, BAND)
        rect(s, x, 3.6, 6.0, 0.5, color)
        text(s, x + 0.3, 3.7, 5.0, 0.35, title, 14, WHITE, bold=True)
        iy = 4.35
        for it in items:
            rect(s, x + 0.3, iy + 0.1, 0.12, 0.12, color, shape=MSO_SHAPE.OVAL)
            text(s, x + 0.6, iy, 5.2, 0.55, it, 11, DARK)
            iy += 0.62
        x += 6.15
    footer(s, 8, D)


def _build_actions(f):
    """自动生成某厂 4 条改进建议（全部基于真实数据，不写死数字）。"""
    if not f["has_data"]:
        return ["本期无偏差数据，无需改进动作"]
    acts = []
    if f["reasons"]:
        top = max(f["reasons"], key=lambda kv: abs(kv[1]))
        if "定额" in top[0]:
            acts.append(f"定额维护：{top[0]} 净偏差 {top[1]:+.2f} 万，优先梳理无定额品项")
        elif "替代料" in top[0]:
            acts.append(f"替代料规范化：{top[0]} 净偏差 {top[1]:+.2f} 万，统一映射与抵消口径")
        else:
            acts.append(f"首要根因：{top[0]} 净偏差 {top[1]:+.2f} 万，集中力量排查")
    else:
        acts.append("原因归因：本期无可归因备注，先补齐偏差原因记录")

    if f["workshop_top"]:
        names = " / ".join(n for n, _ in f["workshop_top"][:3])
        acts.append(f"重点车间：{names} 为 TOP3 风险点")

    if f["cov"] < 50:
        acts.append(f"提升备注率：覆盖率 {f['cov']}%，红预警车间责任到人")

    reds = f["alerts"]["红色预警"]
    if reds:
        acts.append(f"红色预警 {reds} 项（车间×分类），建议列入下周专项跟进")
    if len(acts) < 4:
        acts.append(f"合计净偏差 {f['amt_wan']:+.2f} 万，建议纳入月度考核跟踪")
    return acts[:4]


def _p9_end(prs, D):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(s, NAVY)
    rect(s, 11.6, 0, 1.73, SH, DEEP_NAVY)
    rect(s, 0, 5.6, SW, 0.09, TEAL)
    text(s, 1.1, 2.5, 11.0, 0.9, "谢谢  ·  欢迎评审", 42, WHITE, bold=True)
    text(s, 1.1, 3.8, 11.0, 0.5, "ZPP011 生产偏差分析 · " + D["month"], 16, TEAL)
    text(s, 1.1, 4.4, 11.0, 0.5,
         f"{D['food']['name']} / {D['bev']['name']} · 分厂专题报告", 13, LIGHT_BLUE)
    text(s, 1.1, 5.0, 11.0, 0.5,
         f"数据源: ZPP011 偏差分析工作簿  |  阈值 {D['threshold']}", 13, LIGHT_BLUE)


# ============================================================================
# 对外入口
# ============================================================================
def generate_trae_report(excel_path, output_path, log_cb=None):
    """生成「智能PPT · TRAE 分厂版」（9 页）。

    参数:
        excel_path:   分析结果 Excel（须含「汇总统计」sheet）
        output_path:  输出 pptx 路径
        log_cb:       日志回调，签名 (msg, level)
    返回:
        True 成功 / False 失败（失败原因已通过 log_cb 和 stderr 输出）
    """
    try:
        _safe_log(log_cb, f"[TRAE版] 读取数据：{excel_path}")
        D = build_dataset(excel_path)
        _safe_log(log_cb,
                  f"[TRAE版] 数据就绪：总净偏差 {D['total']['amt_wan']:.2f} 万 / "
                  f"{D['total']['cnt']:,} 条 / {D['total']['workshops']} 个车间")

        prs = Presentation()
        prs.slide_width = Inches(SW)
        prs.slide_height = Inches(SH)

        _p1_cover(prs, D)
        _p2_toc(prs, D)
        _p3_overview(prs, D)
        _p4_workshop(prs, D, "food", 4)
        _p5_category(prs, D, "food", 5)
        _p4_workshop(prs, D, "bev", 6)
        _p5_category(prs, D, "bev", 7)
        _p8_alerts(prs, D)
        _p9_end(prs, D)

        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        prs.save(output_path)
        _safe_log(log_cb, f"[TRAE版] 生成成功：{output_path}（{len(prs.slides)} 页）")
        return True
    except DataError as e:
        _safe_log(log_cb, f"[TRAE版] 数据不满足要求：{e}", "error")
        traceback.print_exc()
        return False
    except Exception as e:
        _safe_log(log_cb, f"[TRAE版] 生成失败：{e}", "error")
        traceback.print_exc()
        return False
