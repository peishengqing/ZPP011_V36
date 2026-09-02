#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
dashboard_html.py — ZPP011 偏差分析 12 图 HTML 看板（可视化核心）
================================================================
把 dev_df（偏差明细）渲染成单个自包含 HTML（base64 内嵌图片，无外部依赖）。

CLI（tools/gen_dashboard.py）与 GUI（gui_pyside6/dialogs/dashboard_dialog.py）
共用本模块 —— 改图只改这一处，两处同时生效。

重要约定：本模块**不**设置 matplotlib 后端，由调用方决定：
  - CLI 入口：matplotlib.use("Agg")（无界面，纯出图）
  - GUI 环境：项目已在 dashboard_dialog 顶部设 qtagg（PySide6）
fig.savefig 两种后端都能把图写进内存缓冲，互不干扰，因此本模块保持后端无关。

优化说明（v43.65）：
  - CSS 全面升级：现代配色、渐变卡片、平滑动画、更好的视觉层级
  - 引入 Chart.js：关键图表（每日趋势、正负构成）换成交互图，鼠标悬停显示数值
  - 其余 10 图保持 matplotlib，确保离线可用
"""
import base64
import io

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------- 中文显示 ----------
try:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
except Exception:
    pass
plt.rcParams["axes.unicode_minus"] = False

# ---------- 配色（中国习惯：涨/正偏差=红，跌/负偏差=绿） ----------
C_POS = "#d4392f"      # 正偏差 红
C_NEG = "#2e8b57"      # 负偏差 绿
C_ACCENT = "#0969da"   # 强调蓝
C_GRAY = "#8b949e"
GRID = "#eaecef"

# =====================================================================
#  看板 CSS 样式（常量，避免 f-string 花括号冲突）
# =====================================================================
DASHBOARD_CSS = """
/* ===== 基础重置 & 变量 ===== */
:root {
  --c-pos: #d4392f;
  --c-neg: #2e8b57;
  --c-accent: #0969da;
  --c-accent-light: #0969da14;
  --c-gray: #656d76;
  --c-muted: #8b949e;
  --c-border: #d0d7de;
  --c-bg: #f0f4f8;
  --c-card: #ffffff;
  --shadow-sm: 0 1px 3px rgba(15,23,42,0.06);
  --shadow-md: 0 4px 16px rgba(15,23,42,0.10);
  --shadow-lg: 0 8px 32px rgba(15,23,42,0.14);
  --radius: 14px;
  --transition: all 0.22s cubic-bezier(0.4,0,0.2,1);
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  font-family:'PingFang SC','Microsoft YaHei','Segoe UI',system-ui,sans-serif;
  background:var(--c-bg);
  color:#0f172a;
  line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1200px;margin:0 auto;padding:28px 24px 48px}
h1{
  font-size:24px;font-weight:700;letter-spacing:-0.02em;
  background:linear-gradient(135deg,#0f172a 0%,#334155 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  margin:0 0 6px;
}
.sub{color:var(--c-muted);font-size:13px;margin-bottom:18px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.sub::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--c-accent);display:inline-block}
/* ===== 工具栏 ===== */
.toolbar{
  position:sticky;top:0;z-index:100;
  background:rgba(240,244,248,0.92);
  backdrop-filter:blur(12px) saturate(1.6);
  padding:12px 0;margin:0 0 22px;
  border-bottom:1px solid var(--c-border);
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  box-shadow:0 2px 12px rgba(15,23,42,0.06);
}
.tlabel{font-size:13px;color:var(--c-gray);font-weight:500}
.fbtn{
  font-family:inherit;font-size:13px;font-weight:500;
  padding:7px 18px;border:1.5px solid var(--c-border);
  background:#fff;border-radius:22px;cursor:pointer;
  color:var(--c-gray);transition:all 0.22s cubic-bezier(0.4,0,0.2,1);
  box-shadow:0 1px 3px rgba(15,23,42,0.06);
}
.fbtn:hover{border-color:var(--c-accent);color:var(--c-accent);box-shadow:0 2px 10px rgba(9,105,218,0.15);transform:translateY(-1px)}
.fbtn.active{background:var(--c-accent);color:#fff;border-color:var(--c-accent);box-shadow:0 4px 14px rgba(9,105,218,0.32);transform:translateY(-1px)}
/* ===== 指标卡 ===== */
.cards{display:flex;gap:14px;margin-bottom:28px;flex-wrap:wrap}
.card{
  flex:1;min-width:170px;
  background:var(--c-card);
  border:1px solid var(--c-border);
  border-radius:14px;
  padding:20px 22px;
  box-shadow:0 1px 3px rgba(15,23,42,0.06);
  transition:all 0.22s cubic-bezier(0.4,0,0.2,1);
  position:relative;overflow:hidden;
}
.card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,var(--c-accent),var(--c-pos));
  opacity:0;transition:opacity 0.2s;
}
.card:hover{box-shadow:0 4px 16px rgba(15,23,42,0.10);transform:translateY(-3px);border-color:transparent}
.card:hover::before{opacity:1}
.card-val{font-size:26px;font-weight:800;letter-spacing:-0.02em;line-height:1.2}
.card-key{color:var(--c-muted);font-size:12.5px;margin-top:6px;font-weight:500}
/* ===== 工厂区块 ===== */
.factory-block{animation:fadeSlideIn 0.35s ease both}
@keyframes fadeSlideIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.fac-title{
  font-size:17px;font-weight:700;margin:32px 0 14px;
  padding-left:14px;
  border-left:4px solid var(--c-pos);
  color:#0f172a;
  display:flex;align-items:center;gap:10px;
}
/* ===== 图表分组 ===== */
.group{margin-bottom:28px}
.grp{
  font-size:14px;font-weight:700;
  border-left:4px solid var(--c-accent);
  padding-left:10px;margin:0 0 14px;
  color:#0f172a;letter-spacing:0.01em;
}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.cell{
  background:var(--c-card);
  border:1px solid var(--c-border);
  border-radius:14px;
  padding:14px;
  box-shadow:0 1px 3px rgba(15,23,42,0.06);
  transition:all 0.22s cubic-bezier(0.4,0,0.2,1);
}
.cell:hover{box-shadow:0 4px 16px rgba(15,23,42,0.10);border-color:rgba(9,105,218,0.25)}
.cap{margin-bottom:8px;display:flex;justify-content:space-between;align-items:flex-start}
.cap b{font-size:13.5px;font-weight:650;color:#0f172a}
.cap span{display:block;color:var(--c-muted);font-size:11.5px;margin-top:3px;line-height:1.4}
.chart-wrap{position:relative;width:100%;height:240px}
.chart-wrap img{width:100%;height:220px;object-fit:cover;border-radius:10px;cursor:zoom-in;transition:transform 0.2s}
.chart-wrap img:hover{transform:scale(1.02)}
.chart-wrap canvas{width:100%!important;height:220px!important}
.placeholder{
  height:120px;display:flex;align-items:center;justify-content:center;
  color:var(--c-muted);background:linear-gradient(135deg,#f8fafc,#f1f5f9);
  border-radius:10px;font-size:13px;
  border:1.5px dashed var(--c-border);
}
/* ===== 小结卡 ===== */
.summary-card{
  background:linear-gradient(135deg,#f0f7ff 0%,#e8f4fd 50%,#fff 100%);
  border:1.5px solid #b6d4fe;
  border-radius:14px;
  padding:20px 24px;margin-top:10px;
  box-shadow:0 1px 3px rgba(15,23,42,0.06);
}
.summary-header{display:flex;align-items:center;gap:10px;margin-bottom:12px;font-size:15px;font-weight:650;color:#0f172a}
.summary-icon{font-size:22px}
.summary-body{display:flex;flex-wrap:wrap;gap:20px;font-size:14px;color:#334155}
.summary-body span b{font-weight:700}
.summary-src{color:var(--c-muted);font-size:12px;margin-top:12px;padding-top:10px;border-top:1px solid #e2e8f0;font-style:italic}
/* ===== 图表放大遮罩 ===== */
.chart-overlay{
  display:none;position:fixed;top:0;left:0;width:100%;height:100%;
  background:rgba(15,23,42,0.88);z-index:9999;
  justify-content:center;align-items:center;cursor:zoom-out;
  backdrop-filter:blur(4px);
}
.chart-overlay.show{display:flex}
.chart-overlay .overlay-inner{text-align:center;max-width:94%;max-height:94%;animation:zoomIn 0.2s ease}
@keyframes zoomIn{from{opacity:0;transform:scale(0.92)}to{opacity:1;transform:scale(1)}}
.chart-overlay .overlay-cap{color:#fff;font-size:16px;margin-bottom:12px;font-weight:500}
.chart-overlay img{max-width:94vw;max-height:88vh;border-radius:12px;box-shadow:0 16px 64px rgba(0,0,0,0.4)}
/* ===== 响应式 ===== */
@media(max-width:768px){
  .grid{grid-template-columns:1fr !important}
  .cards{flex-direction:column}
  .wrap{padding:16px 12px 36px}
  .toolbar{flex-direction:column;align-items:flex-start;gap:8px}
  .fbtn{font-size:12px;padding:5px 14px}
  h1{font-size:20px}
  .summary-body{flex-direction:column;gap:10px}
  .chart-wrap{height:200px}
  .chart-wrap img{height:180px}
}
/* ===== 打印 ===== */
@media print{
  .toolbar{display:none !important}
  .factory-block{animation:none !important;break-inside:avoid}
  .chart-overlay{display:none !important}
  .card{break-inside:avoid;box-shadow:none;border:1px solid #ccc}
  .cell{break-inside:avoid;box-shadow:none}
  .grid{grid-template-columns:1fr 1fr}
  body{background:#fff}
  .cell img{height:180px}
}
"""


def fig_to_b64(fig):
    """把 matplotlib figure 转成 base64 PNG 字符串，关闭 figure 释放内存。"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _safe(func, dev_df, title):
    """任何图绘制失败都不让整个脚本崩，返回 None 由上层显示占位。"""
    try:
        return func(dev_df)
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 画图失败 [{title}]: {e}")
        return None


# =====================================================================
#  12 张图
# =====================================================================
def chart_daily_trend(df):
    """①-1 每日偏差金额趋势：哪天最乱。"""
    d = df.copy()
    d["_dt"] = pd.to_datetime(d["订单日期"])
    g = d.groupby(d["_dt"].dt.date)["偏差金额"].sum()
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(list(g.index), g.values, marker="o", color=C_ACCENT, linewidth=1.8)
    ax.axhline(0, color=C_GRAY, linewidth=1, linestyle="--")
    ax.set_title("每日偏差金额趋势", fontsize=12, fontweight="bold")
    ax.set_ylabel("偏差金额（含税）")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, color=GRID)
    return fig_to_b64(fig)


def chart_pos_neg_stack(df):
    """①-2 正/负偏差金额构成：多耗 vs 少耗各占多少。"""
    g = df.groupby("偏差区间")["偏差金额"].sum()
    pos = g.get("正偏差", 0.0)
    neg = g.get("负偏差", 0.0)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    bars = ax.bar(["正偏差（多耗）", "负偏差（少耗）"], [pos, neg], color=[C_POS, C_NEG])
    ax.set_title("正 / 负偏差金额构成", fontsize=12, fontweight="bold")
    ax.set_ylabel("偏差金额（含税）")
    for b, v in zip(bars, [pos, neg]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=9)
    ax.grid(True, axis="y", color=GRID)
    return fig_to_b64(fig)


def chart_devrate_hist(df):
    """①-3 偏差率(%)分布直方图：整体数据质量。"""
    vals = pd.to_numeric(df["偏差率(%)"], errors="coerce").dropna()
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.hist(vals, bins=30, color=C_ACCENT, alpha=0.85)
    ax.axvline(0, color=C_GRAY, linestyle="--", linewidth=1)
    ax.set_title("偏差率(%) 分布", fontsize=12, fontweight="bold")
    ax.set_xlabel("偏差率(%)")
    ax.set_ylabel("条数")
    ax.grid(True, axis="y", color=GRID)
    return fig_to_b64(fig)


def chart_workshop_bar(df):
    """②-1 各车间偏差金额对比：哪个车间最该盯。"""
    g = df.groupby("车间")["偏差金额"].sum().sort_values()
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    colors = [C_POS if v > 0 else C_NEG for v in g.values]
    ax.barh(g.index, g.values, color=colors)
    ax.set_title("各车间偏差金额对比", fontsize=12, fontweight="bold")
    ax.set_xlabel("偏差金额（含税）")
    ax.grid(True, axis="x", color=GRID)
    return fig_to_b64(fig)


def chart_material_type_pie(df):
    """②-2 物料类型偏差金额占比：钱压在哪类料。"""
    g = df.groupby("物料类型")["偏差金额"].apply(lambda s: s.abs().sum())
    g = g[g > 0]
    if g.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.pie(g.values, labels=g.index, autopct="%1.1f%%", startangle=90,
           colors=["#0969da", "#d4392f", "#2e8b57", "#bf8700", "#8250df"][: len(g)])
    ax.set_title("物料类型偏差金额占比", fontsize=12, fontweight="bold")
    return fig_to_b64(fig)


def chart_product_top10(df):
    """②-3 成品线（产品物料描述）偏差 Top10。"""
    g = df.groupby("产品物料描述")["偏差金额"].apply(lambda s: s.abs().sum()).sort_values(ascending=False).head(10)
    if g.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.barh(g.index[::-1], g.values[::-1], color=C_ACCENT)
    ax.set_title("成品线偏差 Top10", fontsize=12, fontweight="bold")
    ax.set_xlabel("|偏差金额|（含税）")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(True, axis="x", color=GRID)
    return fig_to_b64(fig)


def chart_component_top10(df):
    """③-1 偏差金额 Top10 组件物料：哪些料最烧钱。"""
    g = df.groupby("物料名称")["偏差金额"].apply(lambda s: s.abs().sum()).sort_values(ascending=False).head(10)
    if g.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.barh(g.index[::-1], g.values[::-1], color=C_POS)
    ax.set_title("组件物料偏差 Top10", fontsize=12, fontweight="bold")
    ax.set_xlabel("|偏差金额|（含税）")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(True, axis="x", color=GRID)
    return fig_to_b64(fig)


def chart_altnet_top10(df):
    """③-2 替代料净偏差 Top10：A/B 料互换带来的净影响。"""
    alt = df[df["是否替代料"].astype(str).str.strip() == "是"]
    if alt.empty:
        return None
    g = alt.groupby("物料名称")["净偏差金额"].sum().sort_values(ascending=False).head(10)
    if g.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    colors = [C_POS if v > 0 else C_NEG for v in g.values]
    ax.barh(g.index[::-1], g.values[::-1], color=colors)
    ax.set_title("替代料净偏差 Top10", fontsize=12, fontweight="bold")
    ax.set_xlabel("净偏差金额（含税）")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(True, axis="x", color=GRID)
    return fig_to_b64(fig)


def chart_no_remark_by_workshop(df):
    """③-3 无备注预警偏差金额（by 车间）：高风险未解释偏差。"""
    nr = df[df["备注"].astype(str).str.strip() == ""]
    if nr.empty:
        return None
    g = nr.groupby("车间")["偏差金额"].apply(lambda s: s.abs().sum()).sort_values()
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.barh(g.index, g.values, color="#bf8700")
    ax.set_title("无备注预警偏差金额（by 车间）", fontsize=12, fontweight="bold")
    ax.set_xlabel("|偏差金额|（含税）")
    ax.grid(True, axis="x", color=GRID)
    return fig_to_b64(fig)


def chart_material_3phase(df):
    """④-1 物料偏差率 早期/中期/近期 三线：哪些在持续变差。"""
    d = df.copy()
    d["_dt"] = pd.to_datetime(d["订单日期"])
    d["_rate"] = pd.to_numeric(d["偏差率(%)"], errors="coerce")
    d = d.dropna(subset=["_rate"])
    if d.empty:
        return None
    lo, hi = d["_dt"].min(), d["_dt"].max()
    span = max((hi - lo).days, 1)
    cut1 = lo + pd.Timedelta(days=span // 3)
    cut2 = lo + pd.Timedelta(days=2 * span // 3)
    d["_phase"] = np.where(d["_dt"] <= cut1, "早期", np.where(d["_dt"] <= cut2, "中期", "近期"))

    top_mats = d.groupby("物料名称")["_rate"].apply(lambda s: s.abs().mean()).sort_values(ascending=False).head(5).index
    phases = ["早期", "中期", "近期"]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    palette = [C_POS, C_ACCENT, "#8250df"]
    for i, mat in enumerate(top_mats):
        sub = d[d["物料名称"] == mat]
        means = [sub[sub["_phase"] == p]["_rate"].mean() for p in phases]
        ax.plot(phases, means, marker="o", label=mat[:10], color=palette[i % len(palette)], linewidth=1.6)
    ax.set_title("Top5 物料偏差率 早/中/近期", fontsize=12, fontweight="bold")
    ax.set_ylabel("平均偏差率(%)")
    ax.legend(fontsize=7, loc="best")
    ax.grid(True, color=GRID)
    return fig_to_b64(fig)


def chart_workshop_posneg_stack(df):
    """④-2 各车间正/负偏差构成（堆叠柱）：各车间正负都高吗。"""
    piv = df.pivot_table(index="车间", columns="偏差区间", values="偏差金额", aggfunc="sum", fill_value=0)
    for c in ["正偏差", "负偏差"]:
        if c not in piv.columns:
            piv[c] = 0
    piv = piv[["正偏差", "负偏差"]].sort_values("正偏差", ascending=False)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    x = range(len(piv))
    ax.bar(x, piv["正偏差"], color=C_POS, label="正偏差")
    ax.bar(x, piv["负偏差"], bottom=piv["正偏差"], color=C_NEG, label="负偏差")
    ax.set_xticks(list(x))
    ax.set_xticklabels(piv.index, rotation=45, ha="right", fontsize=8)
    ax.set_title("各车间正/负偏差构成", fontsize=12, fontweight="bold")
    ax.set_ylabel("偏差金额（含税）")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", color=GRID)
    return fig_to_b64(fig)


def chart_remark_coverage(df):
    """④-3 备注覆盖率（by 车间）：管理盲区在哪。"""
    cov = df.assign(has=lambda x: x["备注"].astype(str).str.strip() != "").groupby("车间")["has"].mean() * 100
    cov = cov.sort_values()
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    colors = ["#bf8700" if v < 80 else C_NEG for v in cov.values]
    ax.barh(cov.index, cov.values, color=colors)
    ax.set_title("备注覆盖率（by 车间）", fontsize=12, fontweight="bold")
    ax.set_xlabel("覆盖率(%)")
    ax.set_xlim(0, 100)
    ax.grid(True, axis="x", color=GRID)
    return fig_to_b64(fig)


# ---------- 12 图登记表（顺序即展示顺序） ----------
CHARTS = [
    ("偏差规模与分布", [
        ("chart_daily_trend", "每日偏差金额趋势", "哪一天偏差最集中、最乱"),
        ("chart_pos_neg_stack", "正/负偏差金额构成", "多耗（正）与少耗（负）各自规模"),
        ("chart_devrate_hist", "偏差率(%)分布", "整体数据质量，是否大量贴近 0"),
    ]),
    ("结构拆解", [
        ("chart_workshop_bar", "各车间偏差金额对比", "哪个车间最该盯"),
        ("chart_material_type_pie", "物料类型偏差占比", "钱压在原料还是包材"),
        ("chart_product_top10", "成品线偏差 Top10", "哪些成品线带出的偏差最大"),
    ]),
    ("重点风险", [
        ("chart_component_top10", "组件物料偏差 Top10", "哪些料最烧钱"),
        ("chart_altnet_top10", "替代料净偏差 Top10", "A/B 料互换的净影响（无则跳过）"),
        ("chart_no_remark_by_workshop", "无备注预警偏差", "高风险未解释偏差集中在哪（无则跳过）"),
    ]),
    ("趋势与归因", [
        ("chart_material_3phase", "物料偏差率 早/中/近期", "Top5 物料是否在持续变差"),
        ("chart_workshop_posneg_stack", "各车间正/负偏差构成", "各车间正负偏差双高吗"),
        ("chart_remark_coverage", "备注覆盖率 by 车间", "管理盲区在哪"),
    ]),
]

CHART_FUNCS = {name: globals()[name] for grp in CHARTS for (name, _, _) in grp[1]}


# =====================================================================
#  指标卡 & HTML
# =====================================================================
def compute_metrics(df):
    n = len(df)
    pos = pd.to_numeric(df.loc[df["偏差区间"].astype(str).str.contains("正"), "偏差金额"], errors="coerce").sum()
    neg = pd.to_numeric(df.loc[df["偏差区间"].astype(str).str.contains("负"), "偏差金额"], errors="coerce").sum()
    net = pos + neg
    has_remark = (df["备注"].astype(str).str.strip() != "").mean() * 100
    avg_rate = pd.to_numeric(df["偏差率(%)"], errors="coerce").mean()
    return {
        "n": n,
        "pos": pos,
        "neg": neg,
        "net": net,
        "coverage": has_remark,
        "avg_rate": avg_rate,
    }


def short_name(fac):
    """工厂全名 -> 短名：'云南达利-食品厂' -> '食品厂'。"""
    return fac.split("-", 1)[-1] if "-" in fac else fac


def _cards_html(metrics):
    cards = [
        ("偏差明细条数", f"{metrics['n']:,}", C_ACCENT),
        ("正偏差金额", f"{metrics['pos']:,.0f}", C_POS),
        ("负偏差金额", f"{metrics['neg']:,.0f}", C_NEG),
        ("备注覆盖率", f"{metrics['coverage']:.1f}%", "#bf8700"),
    ]
    return "".join(
        f'<div class="card" style="border-left:4px solid {c}">'
        f'<div class="card-val" style="color:{c}">{v}</div>'
        f'<div class="card-key">{k}</div></div>'
        for k, v, c in cards
    )


def _build_chart_js_daily_trend(labels, values, chart_id):
    """构建每日趋势 Chart.js 脚本"""
    labels_str = repr(labels)
    values_str = repr(values)
    return f'''<div class="chart-wrap"><canvas id="{chart_id}"></canvas></div>
<script>
(function(){{
  var ctx = document.getElementById('{chart_id}').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {labels_str},
      datasets: [{{
        label: '偏差金额（含税）',
        data: {values_str},
        borderColor: '{C_ACCENT}',
        backgroundColor: '{C_ACCENT}22',
        borderWidth: 2.2,
        pointRadius: 3.5,
        pointHoverRadius: 6,
        pointBackgroundColor: '{C_ACCENT}',
        fill: true,
        tension: 0.35
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ color: '{GRID}' }}, ticks: {{ font: {{ size: 10 }}, rotate: 35 }}, border: {{ display: false }} }},
        y: {{ grid: {{ color: '{GRID}' }}, ticks: {{ font: {{ size: 10 }}, callback: v => v.toLocaleString() }}, border: {{ display: false }} }},
      }}
    }}
  }});
}})();
</script>'''



def _build_chart_js_posneg(pos, neg):
    """构建正负偏差构成 Chart.js 脚本"""
    return f'''<div class="chart-wrap"><canvas id="c_posneg"></canvas></div>
<script>
(function(){{
  var ctx = document.getElementById('c_posneg').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: ['正偏差\\n（多耗）', '负偏差\\n（少耗）'],
      datasets: [{{
        data: [{pos}, {neg}],
        backgroundColor: ['{C_POS}', '{C_NEG}'],
        borderRadius: 8,
        borderSkipped: false,
        barThickness: 56
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ font: {{ size: 11, weight: '600' }} }} }},
        y: {{ grid: {{ color: '{GRID}' }}, ticks: {{ font: {{ size: 10 }}, callback: v => v.toLocaleString() }}, border: {{ display: false }} }},
      }}
    }}
  }});
}})();
</script>'''



def _charts_html(dev_df):
    """12 图按 CHARTS 登记顺序渲染，前 2 张用 Chart.js 交互图，其余用 matplotlib PNG。
    单图失败显示占位。"""
    sections = []
    for grp_name, items in CHARTS:
        figs = []
        for fn_name, title, desc in items:
            b64 = _safe(CHART_FUNCS[fn_name], dev_df, title)
            if not b64:
                figs.append(f'<div class="cell"><div class="cap"><b>{title}</b><span>{desc}</span></div><div class="placeholder">「{title}」本期无数据</div></div>')
                continue
            # 前两张图用 Chart.js 交互渲染，其余用 matplotlib PNG
            if fn_name == 'chart_daily_trend':
                d = dev_df.copy()
                d["_dt"] = pd.to_datetime(d["订单日期"])
                g = d.groupby(d["_dt"].dt.date)["偏差金额"].sum()
                labels = [x.strftime("%m-%d") for x in g.index]
                values = [round(v, 0) for v in g.values]
                chart_id = f"c_dt_{abs(hash(str(labels))) % 10000}"
                chart_js = _build_chart_js_daily_trend(labels, values, chart_id)
                figs.append(f'<div class="cell"><div class="cap"><b>{title}</b><span>{desc}</span></div>{chart_js}</div>')
            elif fn_name == 'chart_pos_neg_stack':
                g = dev_df.groupby("偏差区间")["偏差金额"].sum()
                pos = round(g.get("正偏差", 0.0), 0)
                neg = round(g.get("负偏差", 0.0), 0)
                chart_js = _build_chart_js_posneg(pos, neg)
                figs.append(f'<div class="cell"><div class="cap"><b>{title}</b><span>{desc}</span></div>{chart_js}</div>')
            else:
                imgs = (
                    f'<img src="data:image/png;base64,{b64}" alt="{title}" '
                    f'onclick="zoomChart(this.src,\'{title}\')" '
                    f'style="cursor:zoom-in"/>'
                )
                figs.append(f'<div class="cell"><div class="cap"><b>{title}</b><span>{desc}</span></div>{imgs}</div>')
        sections.append(
            f'<div class="group"><h3 class="grp">{grp_name}</h3><div class="grid">{"".join(figs)}</div></div>'
        )
    return sections





def _summary_html(m, meta):
    return (
        f'<div class="summary-card">'
        f'<div class="summary-header">'
        f'<span class="summary-icon">&#128202;</span>'
        f'<b>分析小结</b>'
        f'</div>'
        f'<div class="summary-body">'
        f'<span>分析窗口 <b>{meta["start"]} ~ {meta["end"]}</b></span>'
        f'<span>偏差明细 <b>{m["n"]:,}</b> 条</span>'
        f'<span>正偏差 <b style="color:{C_POS}">{m["pos"]:,.0f}</b></span>'
        f'<span>负偏差 <b style="color:{C_NEG}">{m["neg"]:,.0f}</b></span>'
        f'<span>平均偏差率 <b>{m["avg_rate"]:.2f}%</b></span>'
        f'<span>备注覆盖率 <b>{m["coverage"]:.1f}%</b></span>'
        f'</div>'
        f'<div class="summary-src">数据来源：{meta["src"]}</div>'
        f'</div>'
    )


def build_html(blocks, meta):
    """blocks: 工厂名 -> (metrics, dev_df_sub)。每个工厂独立出一套 指标卡+12图，
    顶部按钮可切换「全部 / 单厂」，互不干扰。"""
    # 顶部切换按钮（吸顶）
    btns = ['<button class="fbtn active" data-name="all" onclick="showFactory(\'all\')">全部</button>']
    for fac in blocks:
        btns.append(
            f'<button class="fbtn" data-name="{fac}" onclick="showFactory(\'{fac}\')">{short_name(fac)}</button>'
        )
    toolbar = f'<div class="toolbar"><span class="tlabel">切换工厂：</span>{"".join(btns)}</div>'

    fac_html = ""
    for fac, (m, df) in blocks.items():
        card_html = _cards_html(m)
        sections = _charts_html(df)
        summary = _summary_html(m, meta)
        fac_html += (
            f'<div class="factory-block" data-factory="{fac}">'
            f'<h2 class="fac-title">{fac}</h2>'
            f'<div class="cards">{card_html}</div>'
            f'{ "".join(sections) }'
            f'{summary}'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZPP011 偏差分析看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>{DASHBOARD_CSS}</style></head><body><div class="wrap">
<h1>ZPP011 偏差分析看板</h1>
<div class="sub">分析窗口 {meta['start']} ~ {meta['end']} ｜ 数据来源 {meta['src']} ｜ 生成时间 {meta['gen']}</div>
{toolbar}
{fac_html}
<!-- 图表放大遮罩 -->
<div class="chart-overlay" id="chartOverlay" onclick="this.classList.remove('show')">
  <div class="overlay-inner">
    <div class="overlay-cap" id="overlayCap"></div>
    <img id="overlayImg" src=""/>
  </div>
</div>
<script>
function showFactory(name){{
  document.querySelectorAll('.factory-block').forEach(function(b){{
    b.style.display = (name==='all' || b.getAttribute('data-factory')===name) ? 'block' : 'none';
  }});
  document.querySelectorAll('.fbtn').forEach(function(b){{
    b.classList.toggle('active', b.getAttribute('data-name')===name);
  }});
}}
function zoomChart(src,title){{
  var o=document.getElementById('chartOverlay');
  document.getElementById('overlayImg').src=src;
  document.getElementById('overlayCap').textContent=title;
  o.classList.add('show');
}}
</script>
</div></body></html>"""
    return html
