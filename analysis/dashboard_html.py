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
from urllib.parse import quote

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
/* ===== 「到主表」芯片（联动钻取入口） ===== */
.chip{
  display:inline-block;margin-top:6px;
  font-size:11.5px;font-weight:600;color:var(--c-accent);
  background:var(--c-accent-light);
  border:1px solid rgba(9,105,218,.35);
  border-radius:12px;padding:2px 10px;
  text-decoration:none;transition:all .18s ease;
}
.chip:hover{background:var(--c-accent);color:#fff;box-shadow:0 2px 8px rgba(9,105,218,.3)}
/* ===== 分组折叠（原生 details，降级模式也兼容） ===== */
details.group{margin-bottom:18px}
details.group > summary.grp{
  cursor:pointer;list-style:none;
  font-size:14px;font-weight:700;
  border-left:4px solid var(--c-accent);
  padding:6px 10px 6px 10px;margin:0 0 12px;
  color:#0f172a;letter-spacing:.01em;
  background:linear-gradient(90deg,rgba(9,105,218,.06),transparent 60%);
  border-radius:0 8px 8px 0;
}
details.group > summary.grp::before{content:'▸ ';color:var(--c-accent);font-size:12px}
details.group[open] > summary.grp::before{content:'▾ '}
details.group > summary::-webkit-details-marker{display:none}
details.group > .grid{margin-top:4px}
/* ===== 小结卡 ===== */
.focus-list{margin:12px 0 0;padding:0 0 0 18px;font-size:13.5px;color:#334155}
.focus-list li{margin:5px 0;line-height:1.55}
.focus-list li::marker{color:var(--c-pos)}
.summary-card.top{margin:0 0 24px}
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
    # dpi=150：卡片内 600px 宽显示更清晰（原 110 放大发虚）
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
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
#  统一图表主题（2026-09-30 风格翻新）：白底卡片风格、左对齐标题、
#  去顶/右边框、细网格、统一字号。所有 12 图共用，观感与页面 CSS 协调。
# =====================================================================
def _style_ax(ax, title, xlabel=""):
    """统一图表外观：标题左对齐加粗、去顶右边框、细网格、统一刻度字号。"""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d0d7de")
    ax.spines["bottom"].set_color("#d0d7de")
    ax.set_title(title, fontsize=11, fontweight="bold", color="#0f172a", loc="left", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color="#475569")
    ax.tick_params(labelsize=9, colors="#475569")
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.75)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontsize(8.5)


def _num(v):
    """万/千分位标签（柱端数值用）。"""
    return f"{v:,.0f}"


def _bar_labels(ax, bars, values, vmax):
    """水平柱图柱端标签：正值放柱外（右）、负值放柱内（白字），避免压到轴名。"""
    for b, v in zip(bars, values):
        if v >= 0:
            ax.text(v + vmax * 0.015, b.get_y() + b.get_height() / 2, _num(v),
                    va="center", ha="left", fontsize=8.5, color="#334155")
        else:
            ax.text(v + abs(v) * 0.96, b.get_y() + b.get_height() / 2, _num(v),
                    va="center", ha="right", fontsize=8.5, color="white",
                    fontweight="bold")


# =====================================================================
#  12 张图
# =====================================================================
def chart_daily_trend(df):
    """①-1 每日偏差金额趋势：哪天最乱。"""
    d = df.copy()
    d["_dt"] = pd.to_datetime(d["订单日期"])
    g = d.groupby(d["_dt"].dt.date)["偏差金额"].sum()
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    # 原始日线：变轻（细线小点、半透明），避免锯齿噪声抢焦点
    ax.plot(list(g.index), g.values, color=C_ACCENT, alpha=0.35, linewidth=1.0,
            marker="o", markersize=3)
    # 7 日均：加粗主线 + 面积填充，趋势一眼可见
    roll = g.rolling(window=7, min_periods=1).mean()
    ax.plot(list(roll.index), roll.values, color=C_ACCENT, linewidth=2.4,
            label="7 日均值", zorder=3)
    ax.fill_between(list(roll.index), 0, roll.values, color=C_ACCENT, alpha=0.08)
    ax.axhline(0, color=C_GRAY, linewidth=1, linestyle="--")
    _style_ax(ax, "每日偏差金额趋势", "偏差金额（含税）")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(fontsize=8, loc="upper left")
    return fig_to_b64(fig)


def chart_pos_neg_stack(df):
    """①-2 正/负偏差金额构成：多耗 vs 少耗各占多少。"""
    g = df.groupby("偏差区间")["偏差金额"].sum()
    pos = g.get("正偏差", 0.0)
    neg = g.get("负偏差", 0.0)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    bars = ax.bar(["正偏差（多耗）", "负偏差（少耗）"], [pos, neg], color=[C_POS, C_NEG], width=0.5)
    ax.set_ylabel("偏差金额（含税）", fontsize=9, color="#475569")
    _style_ax(ax, "正 / 负偏差金额构成")
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
    ax.set_ylabel("条数", fontsize=9, color="#475569")
    _style_ax(ax, "偏差率(%) 分布", "偏差率(%)")
    return fig_to_b64(fig)


def chart_workshop_bar(df):
    """②-1 各车间偏差金额对比：哪个车间最该盯（按 |金额| 排序，最严重在上）。"""
    g = df.groupby("车间")["偏差金额"].sum()
    # barh 把第 0 项画在最下行：要「最严重在上」须按 |值| 升序排列（最大者排最后）
    g = g.reindex(g.abs().sort_values(ascending=True).index)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    colors = [C_POS if v > 0 else C_NEG for v in g.values]
    bars = ax.barh(g.index, g.values, color=colors, height=0.62)
    _bar_labels(ax, bars, g.values, max(abs(g.max()), abs(g.min()), 1.0))
    _style_ax(ax, "各车间偏差金额对比（最严重在上）", "偏差金额（含税）")
    return fig_to_b64(fig)


def chart_material_type_pie(df):
    """②-2 物料类型偏差金额占比：钱压在哪类料。"""
    g = df.groupby("物料类型")["偏差金额"].apply(lambda s: s.abs().sum())
    g = g[g > 0]
    if g.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.pie(g.values, labels=g.index, autopct="%1.1f%%", startangle=90,
           colors=["#0969da", "#d4392f", "#2e8b57", "#bf8700", "#8250df"][: len(g)],
           textprops={"fontsize": 9}, pctdistance=0.75)
    _style_ax(ax, "物料类型偏差金额占比")
    return fig_to_b64(fig)


def chart_product_top10(df):
    """②-3 成品线（产品物料描述）偏差 Top10。"""
    g = df.groupby("产品物料描述")["偏差金额"].apply(lambda s: s.abs().sum()).sort_values(ascending=False).head(10)
    if g.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    bars = ax.barh(g.index[::-1], g.values[::-1], color=C_ACCENT, height=0.65)
    for b, v in zip(bars, g.values[::-1]):
        ax.text(v + g.values.max() * 0.015, b.get_y() + b.get_height() / 2, _num(v),
                va="center", fontsize=8.5, color="#334155")
    _style_ax(ax, "成品线偏差 Top10", "|偏差金额|（含税）")
    ax.tick_params(axis="y", labelsize=8)
    return fig_to_b64(fig)


def chart_component_top10(df):
    """③-1 偏差金额 Top10 组件物料：哪些料最烧钱。"""
    g = df.groupby("物料名称")["偏差金额"].apply(lambda s: s.abs().sum()).sort_values(ascending=False).head(10)
    if g.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    bars = ax.barh(g.index[::-1], g.values[::-1], color=C_POS, height=0.65)
    for b, v in zip(bars, g.values[::-1]):
        ax.text(v + g.values.max() * 0.015, b.get_y() + b.get_height() / 2, _num(v),
                va="center", fontsize=8.5, color="#334155")
    _style_ax(ax, "组件物料偏差 Top10", "|偏差金额|（含税）")
    ax.tick_params(axis="y", labelsize=8)
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
    bars = ax.barh(g.index[::-1], g.values[::-1], color=colors, height=0.65)
    for b, v in zip(bars, g.values[::-1]):
        ax.text(v + max(g.values.max(), 1) * 0.015, b.get_y() + b.get_height() / 2, _num(v),
                va="center", fontsize=8.5, color="#334155")
    _style_ax(ax, "替代料净偏差 Top10", "净偏差金额（含税）")
    ax.tick_params(axis="y", labelsize=8)
    return fig_to_b64(fig)


def chart_no_remark_by_workshop(df):
    """③-3 无备注预警偏差金额（by 车间）：高风险未解释偏差。"""
    nr = df[df["备注"].astype(str).str.strip() == ""]
    if nr.empty:
        return None
    g = nr.groupby("车间")["偏差金额"].apply(lambda s: s.abs().sum())
    g = g.reindex(g.abs().sort_values(ascending=True).index)  # 升序 → 最大者画在最上
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    bars = ax.barh(g.index, g.values, color="#bf8700", height=0.62)
    for b, v in zip(bars, g.values):
        ax.text(v + g.values.max() * 0.015, b.get_y() + b.get_height() / 2, _num(v),
                va="center", fontsize=8.5, color="#334155")
    _style_ax(ax, "无备注预警偏差金额（by 车间，最严重在上）", "|偏差金额|（含税）")
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
        ax.plot(phases, means, marker="o", label=mat[:10], color=palette[i % len(palette)],
                linewidth=1.8, markersize=5)
        ax.annotate(f"{means[-1]:.1f}%", (2, means[-1]), textcoords="offset points",
                    xytext=(4, 0), fontsize=7.5, color=palette[i % len(palette)])
    _style_ax(ax, "Top5 物料偏差率 早/中/近期（端点为近期值）", "平均偏差率(%)")
    ax.set_ylabel("平均偏差率(%)", fontsize=9, color="#475569")
    ax.legend(fontsize=7, loc="best")
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
    ax.bar(x, piv["正偏差"], color=C_POS, label="正偏差", width=0.6)
    ax.bar(x, piv["负偏差"], bottom=piv["正偏差"], color=C_NEG, label="负偏差", width=0.6)
    for i, (p, n) in enumerate(zip(piv["正偏差"], piv["负偏差"])):
        ax.text(i, p + n + abs(p + n) * 0.02 + 1, _num(p + n), ha="center",
                fontsize=8, color="#334155")
    ax.set_xticks(list(x))
    ax.set_xticklabels(piv.index, rotation=45, ha="right", fontsize=8)
    _style_ax(ax, "各车间正/负偏差构成", "偏差金额（含税）")
    ax.legend(fontsize=8)
    return fig_to_b64(fig)


def chart_remark_coverage(df):
    """④-3 备注覆盖率（by 车间）：管理盲区在哪。"""
    cov = df.assign(has=lambda x: x["备注"].astype(str).str.strip() != "").groupby("车间")["has"].mean() * 100
    cov = cov.sort_values(ascending=True)  # 升序 → 覆盖率最低的画在最上
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    colors = ["#bf8700" if v < 80 else C_NEG for v in cov.values]
    bars = ax.barh(cov.index, cov.values, color=colors, height=0.62)
    for b, v in zip(bars, cov.values):
        ax.text(v + 2, b.get_y() + b.get_height() / 2, f"{v:.0f}%",
                va="center", fontsize=8.5, color="#334155")
    _style_ax(ax, "备注覆盖率（by 车间，低在上）", "覆盖率(%)")
    ax.set_xlim(0, 104)
    return fig_to_b64(fig)


# ---------- 12 图登记表（顺序即展示顺序） ----------
# 第 4 项 link_key：卡片「到主表」芯片的钻取类型（None = 不挂芯片）
CHARTS = [
    ("偏差规模与分布", [
        ("chart_daily_trend", "每日偏差金额趋势", "哪一天偏差最集中、最乱", None),
        ("chart_pos_neg_stack", "正/负偏差金额构成", "多耗（正）与少耗（负）各自规模", None),
        ("chart_devrate_hist", "偏差率(%)分布", "整体数据质量，是否大量贴近 0", None),
    ]),
    ("结构拆解", [
        ("chart_workshop_bar", "各车间偏差金额对比", "哪个车间最该盯", "worst_workshop"),
        ("chart_material_type_pie", "物料类型偏差占比", "钱压在原料还是包材", None),
        ("chart_product_top10", "成品线偏差 Top10", "哪些成品线带出的偏差最大", "top_product"),
    ]),
    ("重点风险", [
        ("chart_component_top10", "组件物料偏差 Top10", "哪些料最烧钱", "top_material"),
        ("chart_altnet_top10", "替代料净偏差 Top10", "A/B 料互换的净影响（无则跳过）", "top_material"),
        ("chart_no_remark_by_workshop", "无备注预警偏差", "高风险未解释偏差集中在哪（无则跳过）", "worst_workshop"),
    ]),
    ("趋势与归因", [
        ("chart_material_3phase", "物料偏差率 早/中/近期", "Top5 物料是否在持续变差", None),
        ("chart_workshop_posneg_stack", "各车间正/负偏差构成", "各车间正负偏差双高吗", None),
        ("chart_remark_coverage", "备注覆盖率 by 车间", "管理盲区在哪", "lowest_coverage_workshop"),
    ]),
]

CHART_FUNCS = {item[0]: globals()[item[0]] for grp in CHARTS for item in grp[1]}

# 芯片文案（link_key -> 按钮文字）
LINK_LABELS = {
    "worst_workshop": "盯最严重车间 →",
    "top_material": "盯最大物料 →",
    "top_product": "盯最大成品线 →",
    "lowest_coverage_workshop": "盯盲区车间 →",
}


def _link_values(df):
    """预计算各钻取类型的目标值（缺失列/空数据时安全跳过）。"""
    out = {}
    try:
        g = df.groupby("车间")["偏差金额"].sum()
        if len(g):
            out["worst_workshop"] = str(g.reindex(g.abs().sort_values(ascending=False).index).index[0])
    except Exception:
        pass
    try:
        mcol = "物料名称" if "物料名称" in df.columns else ("组件物料描述" if "组件物料描述" in df.columns else None)
        if mcol:
            g2 = df.groupby(mcol)["偏差金额"].apply(lambda s: s.abs().sum()).sort_values(ascending=False)
            if len(g2):
                out["top_material"] = str(g2.index[0])
    except Exception:
        pass
    try:
        if "产品物料描述" in df.columns:
            gp = df.groupby("产品物料描述")["偏差金额"].apply(lambda s: s.abs().sum())
            if len(gp):
                out["top_product"] = str(gp.abs().idxmax())
    except Exception:
        pass
    try:
        cov = df.assign(_has=df["备注"].astype(str).str.strip() != "").groupby("车间")["_has"].mean()
        if len(cov):
            out["lowest_coverage_workshop"] = str(cov.idxmin())
    except Exception:
        pass
    return out


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
    # 净偏差颜色：净额为正（多耗）红、为负（少耗）绿、近零灰
    net_color = C_POS if metrics["net"] > 1 else (C_NEG if metrics["net"] < -1 else "#64748b")
    cards = [
        ("偏差明细条数", f"{metrics['n']:,}", C_ACCENT),
        ("正偏差金额", f"{metrics['pos']:,.0f}", C_POS),
        ("负偏差金额", f"{metrics['neg']:,.0f}", C_NEG),
        ("净偏差金额", f"{metrics['net']:+,.0f}", net_color),
        ("平均偏差率", f"{metrics['avg_rate']:.2f}%", "#8250df"),
        ("备注覆盖率", f"{metrics['coverage']:.1f}%", "#bf8700"),
    ]
    return "".join(
        f'<div class="card" style="border-left:4px solid {c}">'
        f'<div class="card-val" style="color:{c}">{v}</div>'
        f'<div class="card-key">{k}</div></div>'
        for k, v, c in cards
    )






def _charts_html(dev_df, factory=""):
    """12 图按 CHARTS 登记顺序渲染，全部用 matplotlib PNG（无外部依赖）。
    单图失败显示占位；带 link_key 的卡片挂「到主表」芯片（自定义 scheme，
    GUI 侧 QWebEngineUrlRequestInterceptor 拦截 → 主表联动钻取）。"""
    vals = _link_values(dev_df)
    sections = []
    for grp_name, items in CHARTS:
        figs = []
        for item in items:
            fn_name, title, desc, link_key = item
            b64 = _safe(CHART_FUNCS[fn_name], dev_df, title)
            chip = ""
            if link_key and vals.get(link_key):
                v = quote(str(vals[link_key]))
                fac = quote(str(factory))
                chip = (f'<a class="chip" href="zpp011:link?type={link_key}&v={v}&fac={fac}" '
                        f'title="点击后主表将钻取到该车间/物料（联动横幅可一键清除）">'
                        f'{LINK_LABELS.get(link_key, "到主表 →")}</a>')
            cap = f'<div class="cap"><div><b>{title}</b><span>{desc}</span>{chip}</div></div>'
            if not b64:
                figs.append(f'<div class="cell">{cap}<div class="placeholder">「{title}」本期无数据</div></div>')
                continue
            imgs = (
                f'<img src="data:image/png;base64,{b64}" alt="{title}" '
                f'onclick="zoomChart(this.src,\'{title}\')" '
                f'style="cursor:zoom-in"/>'
            )
            figs.append(f'<div class="cell">{cap}{imgs}</div>')
        # 分组折叠（C）：重点风险默认展开，其余折叠；原生 details，降级模式也能用
        open_attr = " open" if grp_name == "重点风险" else ""
        sections.append(
            f'<details class="group"{open_attr}><summary class="grp">{grp_name}</summary>'
            f'<div class="grid">{"".join(figs)}</div></details>'
        )
    return sections





def _focus_lines(df, m):
    """「重点盯什么」自动文案：最坏车间 / 最大物料 / 最乱一天 / 覆盖盲区。"""
    lines = []
    try:
        g = df.groupby("车间")["偏差金额"].sum()
        w = g.reindex(g.abs().sort_values(ascending=False).index)
        name, val = str(w.index[0]), float(w.iloc[0])
        kind = "多耗" if val > 0 else "少耗"
        lines.append(f"<b>最该盯的车间</b>：{name}（偏差 {abs(val):,.0f} 元，{kind}）")
    except Exception:
        pass
    try:
        mcol = "物料名称" if "物料名称" in df.columns else ("组件物料描述" if "组件物料描述" in df.columns else None)
        if mcol:
            g2 = df.groupby(mcol)["偏差金额"].apply(lambda s: s.abs().sum()).sort_values(ascending=False)
            if len(g2):
                lines.append(f"<b>最烧钱的物料</b>：{g2.index[0]}（|偏差| {g2.iloc[0]:,.0f} 元，可点卡片「盯最大物料」进主表）")
    except Exception:
        pass
    try:
        d2 = df.copy()
        d2["_dt"] = pd.to_datetime(d2["订单日期"])
        gd = d2.groupby(d2["_dt"].dt.date)["偏差金额"].sum()
        gd = gd.reindex(gd.abs().sort_values(ascending=False).index)
        if len(gd):
            lines.append(f"<b>偏差最集中的一天</b>：{gd.index[0]}（当日偏差 {abs(gd.iloc[0]):,.0f} 元）")
    except Exception:
        pass
    if m.get("coverage", 100) < 70:
        lines.append(f"备注覆盖率 <b>{m['coverage']:.0f}%</b> 偏低，未解释偏差存在管理盲区，建议先补备注再谈归因")
    if not lines:
        lines.append("本期无明显集中风险，保持日常监控即可")
    return lines


def _summary_html(m, meta, df):
    """小结 + 重点盯什么（结论先行，置顶展示）。"""
    focus = "".join(f"<li>{s}</li>" for s in _focus_lines(df, m))
    return (
        f'<div class="summary-card top">'
        f'<div class="summary-header">'
        f'<span class="summary-icon">&#128202;</span>'
        f'<b>分析小结 · 重点盯什么</b>'
        f'</div>'
        f'<div class="summary-body">'
        f'<span>窗口 <b>{meta["start"]} ~ {meta["end"]}</b></span>'
        f'<span>明细 <b>{m["n"]:,}</b> 条</span>'
        f'<span>净偏差 <b style="color:{C_POS if m["net"] > 1 else (C_NEG if m["net"] < -1 else "#64748b")}">{m["net"]:+,.0f}</b></span>'
        f'<span>平均偏差率 <b>{m["avg_rate"]:.2f}%</b></span>'
        f'<span>备注覆盖率 <b>{m["coverage"]:.1f}%</b></span>'
        f'</div>'
        f'<ul class="focus-list">{focus}</ul>'
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
        sections = _charts_html(df, fac)
        summary = _summary_html(m, meta, df)
        fac_html += (
            f'<div class="factory-block" data-factory="{fac}">'
            f'<h2 class="fac-title">{fac}</h2>'
            f'<div class="cards">{card_html}</div>'
            f'{summary}'
            f'{ "".join(sections) }'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZPP011 偏差分析看板</title>
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
