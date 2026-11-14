# -*- coding: utf-8 -*-
"""跨月趋势图 HTML 构建（matplotlib Agg 后端 → base64 内嵌 → 自包含 HTML）。

裴哥 2026-11-14 · 跨月趋势对比功能

为什么 HTML 不直接嵌 Qt 画布：项目统一走 matplotlib→HTML→QWebEngineView 管线
（见 dashboard_html.py / dashboard_dialog.py），亮暗主题、字体、导出 HTML 都能复用。

口径（承接 core/monthly_archive.py）：
  - 默认画 **峰值线 peak_dev**（盯反复出问题的物料，黄原胶式补投归零不会漏）；
  - 可切 **期末线 period_dev**（对账口径，看月底真实剩多少偏差）；
  - 双线同图：峰值线实心、期末线虚线，被修正的月份在峰值点标一圈高亮。

纯函数：build_trend_html(trend_rows, meta) → HTML 字符串，不碰 Qt、不碰 DB。
"""
import base64
import io
from typing import Dict, List

# 亮/暗两套配色（HTML 自带，不依赖 Qt 主题运行时，导出后独立可看）
_THEME = {
    "light": {"bg": "#ffffff", "fg": "#1f2328", "grid": "#e1e4e8",
              "peak": "#cf222e", "period": "#0969da", "fixed": "#bf8700"},
    "dark": {"bg": "#0d1117", "fg": "#e6edf3", "grid": "#30363d",
             "peak": "#ff7b72", "period": "#58a6ff", "fixed": "#d29922"},
}


def _render_fig(trend_rows: List[Dict], dark: bool, show_period: bool) -> str:
    """画趋势折线图，返回 PNG 的 base64。trend_rows 按 biz_month 升序。"""
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    # 中文字体：交给 matplotlib 找系统字体，找不到也不报错（缺字只影响标签显示）
    try:
        matplotlib.rcParams["font.sans-serif"] = [
            "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:  # noqa: BLE001
        pass

    c = _THEME["dark" if dark else "light"]
    months = [r["biz_month"] for r in trend_rows]
    peak = [r.get("peak_dev", 0.0) for r in trend_rows]
    period = [r.get("period_dev", 0.0) for r in trend_rows]
    corrected = [bool(r.get("corrected")) for r in trend_rows]

    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=110)
    fig.patch.set_facecolor(c["bg"])
    ax.set_facecolor(c["bg"])

    ax.plot(months, peak, marker="o", linewidth=2.2, color=c["peak"],
            label="峰值偏差（盯反复出问题）", zorder=3)
    # 被修正的月份：峰值点外加一圈金色高亮，一眼看出「这里补投归零过」
    for i, is_fixed in enumerate(corrected):
        if is_fixed:
            ax.scatter(months[i], peak[i], s=210, facecolors="none",
                       edgecolors=c["fixed"], linewidths=2.4, zorder=4)
    if show_period:
        ax.plot(months, period, marker="s", linewidth=1.8, linestyle="--",
                color=c["period"], label="期末偏差（对账口径）", zorder=2)

    ax.axhline(0, color=c["grid"], linewidth=1, zorder=1)
    ax.grid(True, axis="y", color=c["grid"], linewidth=0.7, alpha=0.6)
    ax.set_title("跨月偏差趋势（圈注 = 该月曾被修正归零）",
                 color=c["fg"], fontsize=13, pad=12)
    ax.set_xlabel("业务月", color=c["fg"], fontsize=10)
    ax.set_ylabel("偏差", color=c["fg"], fontsize=10)
    ax.tick_params(colors=c["fg"], labelsize=9)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color(c["grid"])
    leg = ax.legend(loc="best", fontsize=9)
    if leg:
        leg.get_frame().set_facecolor(c["bg"])
        for t in leg.get_texts():
            t.set_color(c["fg"])
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=c["bg"])
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_trend_html(trend_rows: List[Dict], meta: Dict,
                     dark: bool = False, show_period: bool = True) -> str:
    """趋势看板 HTML。meta: {material_code, material_name, factory}。

    trend_rows 为空时给占位文案，不画空图。
    """
    c = _THEME["dark" if dark else "light"]
    name = meta.get("material_name") or meta.get("material_code", "")
    code = meta.get("material_code", "")
    factory = meta.get("factory", "")
    months_n = len(trend_rows)
    fixed_n = sum(1 for r in trend_rows if r.get("corrected"))
    peak_max = max((r.get("peak_dev", 0.0) for r in trend_rows), default=0.0)

    if not trend_rows:
        body = ("<div class='empty'>该物料暂无跨月归档数据。<br>"
                "<small>请先在工具里执行一次「回填归档」。</small></div>")
        img = ""
    else:
        b64 = _render_fig(trend_rows, dark, show_period)
        img = f"<img src='data:image/png;base64,{b64}' alt='trend'/>"
        body = ""

    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<style>
  body {{ margin:0; padding:18px 20px; background:{c['bg']}; color:{c['fg']};
          font-family:"Microsoft YaHei","Segoe UI",sans-serif; }}
  h2 {{ margin:0 0 4px; font-size:18px; }}
  .sub {{ color:{c['fg']}; opacity:.7; font-size:12px; margin-bottom:14px; }}
  .cards {{ display:flex; gap:12px; margin-bottom:12px; flex-wrap:wrap; }}
  .card {{ border:1px solid {c['grid']}; border-radius:8px; padding:8px 14px;
           min-width:110px; }}
  .card .k {{ font-size:11px; opacity:.65; }}
  .card .v {{ font-size:18px; font-weight:600; margin-top:2px; }}
  .fixed .v {{ color:{c['fixed']}; }}
  img {{ max-width:100%; height:auto; }}
  .empty {{ padding:60px 0; text-align:center; opacity:.6; font-size:14px; }}
</style></head>
<body>
  <h2>{name}</h2>
  <div class="sub">物料 {code} · 工厂 {factory} · 覆盖 {months_n} 个业务月</div>
  <div class="cards">
    <div class="card"><div class="k">历史峰值</div><div class="v">{peak_max:g}</div></div>
    <div class="card fixed"><div class="k">被修正月数</div><div class="v">{fixed_n}</div></div>
    <div class="card"><div class="k">覆盖月数</div><div class="v">{months_n}</div></div>
  </div>
  {img}{body}
</body></html>"""
    return html