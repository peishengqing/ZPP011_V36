# -*- coding: utf-8 -*-
"""归藏-Swiss（瑞士国际主义风·安全橙）15 页 slides 渲染层。
版式忠实复刻 2026-10-04 人工校验版（S01-S22 布局锁 + validator 通过版），数字全部动态注入。
"""

from __future__ import annotations

from .guizang_report import MINUS


def _chrome(l_text: str, n: int) -> str:
    return f'''    <div class="chrome-min">
      <div class="l">{l_text}</div>
      <div class="r">{n:02d} / 15</div>
    </div>'''


def _p01(d):
    t = d["total"]
    return f'''<!-- 01 · Cover · slide accent + ASCII -->
<section class="slide accent" data-animate="hero" data-layout="SWISS-COVER-ASCII">
  <div class="canvas-card">
    <canvas class="ascii-bg" aria-hidden="true"></canvas>
    <div class="chrome-min">
      <div class="l">ZPP011 生产偏差分析 · 分厂报告 · {d["period"]}</div>
      <div class="r">DY · {d["gen_date"][2:].replace(".", ".")} · 01 / 15</div>
    </div>

    <div style="flex:1;padding:0;display:grid;grid-template-rows:auto 1fr auto;gap:2.6vh">
      <div data-anim="kicker" class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em">PRODUCTION DEVIATION AUDIT · FOOD &amp; BEVERAGE</div>

      <h1 data-anim="title" style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(11.6vw,19vh);line-height:.94;letter-spacing:-.025em;color:#fff">食品与饮料<br/><span style="font-style:italic;font-weight:300">分开算这笔账</span></h1>

      <div data-anim="bottom" style="display:grid;grid-template-rows:auto auto;gap:1.6vh;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh">
        <div data-anim="lead" class="lead" style="max-width:52ch;color:rgba(255,255,255,.86);font-weight:300">{t["rows_fmt"]} 条偏差、两个厂、两套完全不同的省法。这份报告不合并口径,谁的问题归谁——省得是否真实,也要查。</div>
        <div style="display:flex;justify-content:space-between;align-items:end">
          <div class="t-meta" style="color:rgba(255,255,255,.6)">云南达利 · 材料审核 · {d["period"].split("-")[0]} 年 {int(d["period"].split("-")[1])} 月</div>
          <div class="t-meta" style="color:rgba(255,255,255,.6)">→ 方向键翻页 / B 静态</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p02(d):
    t, q = d["total"], d["quality"]
    return f'''<!-- 02 · 总览 · slide light · KPI Hero + 口径标注 -->
<section class="slide light" data-animate="progression" data-layout="S03">
  <div class="canvas-card">
{_chrome("总览 / OVERVIEW", 2)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker" style="margin-bottom:1.4vh">{d["period_range"]} · 全厂</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:26ch">净节约收口在<span style="color:var(--accent)">可解释区间</span></h2>

      <div style="display:grid;grid-template-rows:auto auto 1fr;gap:3.4vh;padding-top:3.4vh">
        <div data-anim="kpi" style="display:flex;align-items:flex-end;gap:2.4vw;border-bottom:1px solid var(--border-subtle);padding-bottom:2.6vh">
          <div class="kpi-hero" style="font-size:min(11.6vw,19vh);color:var(--text-primary)">{t["net"]}<span class="unit">万</span></div>
          <div style="padding-bottom:1.6vh;max-width:30ch">
            <div class="t-meta" style="margin-bottom:.8vh">净偏差金额 · NET DEVIATION（负=节约）</div>
            <div class="body">多耗 {t["pos"]} 万与节约 {t["neg"]} 万对冲后净省。这不是"偏差消失了",而是<b>多耗与节约在同一盘账里互相抵消</b>——省得是否真实,本报告逐页核查。</div>
          </div>
        </div>

        <div data-anim="stats" style="display:grid;grid-template-columns:repeat(4,1fr);gap:2.4vw">
          <div class="stat-card"><div class="stat-label">偏差条数</div><div class="stat-nb">{t["rows_fmt"]}</div><div class="stat-note">覆盖 {t["combo_count"]} 个车间×分类组合</div></div>
          <div class="stat-card"><div class="stat-label">食品厂占比</div><div class="stat-nb">{t["food_pct"]}<span class="stat-unit">%</span></div><div class="stat-note">{t["food_rows"]} 条 · 问题在"面"</div></div>
          <div class="stat-card accent-top"><div class="stat-label">饮料厂条数占比</div><div class="stat-nb" style="color:var(--accent)">{t["bev_pct"]}<span class="stat-unit">%</span></div><div class="stat-note">{t["bev_rows"]} 条 · 问题在"点"</div></div>
          <div class="stat-card"><div class="stat-label">备注覆盖率</div><div class="stat-nb">{t["remark_pct"]}<span class="stat-unit">%</span></div><div class="stat-note">近七成偏差无原因说明</div></div>
        </div>

        <div data-anim="note" style="align-self:end;border-left:3px solid var(--accent);padding-left:1.4vw">
          <div class="body-sm" style="color:var(--text-secondary)"><b>口径说明：</b>本报告全部数字由「完整偏差明细」净偏差金额列逐行加总得出,可逐条复核。工作簿「汇总统计」页的"总偏差金额"合计({q["sum_total"]} 万)与其自身正/负分项相加不符,本报告不采用,详见第 04 页。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p03(d):
    f, b = d["food"], d["bev"]
    return f'''<!-- 03 · 两厂对照 · slide light · 对照双栏 -->
<section class="slide light" data-animate="duo-mirror" data-layout="S09">
  <div class="canvas-card">
{_chrome("两厂对照 / FOOD VS BEVERAGE", 3)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker" style="margin-bottom:1.4vh">同样在省,省法完全不同</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">饮料厂用 <span style="color:var(--accent)">{b["rows_ratio"]}%</span> 的条数,省下了食品厂 {round(float(b["net_ratio"]))}% 的钱</h2>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0;margin-top:3.4vh;border-top:2px solid var(--ink)">
        <div data-anim="left" style="padding:3.2vh 2.6vw 0 0;border-right:1px solid var(--border-subtle)">
          <div class="t-cat" style="margin-bottom:1.6vh">云南达利 · 食品厂</div>
          <div class="kpi-big" style="font-size:min(8.4vw,14vh);margin-bottom:2.4vh">{f["net"]}<span class="unit" style="font-size:.2em;font-weight:500;opacity:.5">万</span></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.6vw 1.4vw;padding-bottom:2.4vh">
            <div class="stat-card thin"><div class="stat-label">条数</div><div class="stat-nb" style="font-size:2.6vw">{f["rows_fmt"]}</div></div>
            <div class="stat-card thin"><div class="stat-label">备注覆盖</div><div class="stat-nb" style="font-size:2.6vw">{f["remark_pct"]}%</div></div>
            <div class="stat-card thin"><div class="stat-label">多耗</div><div class="stat-nb" style="font-size:2.6vw">{f["pos"]}万</div></div>
            <div class="stat-card thin"><div class="stat-label">节约</div><div class="stat-nb" style="font-size:2.6vw">{f["neg"]}万</div></div>
          </div>
          <div class="body-sm" style="color:var(--text-secondary)">车间多、条数密,靠 <b>2 个车间</b>撑起大头:{f["ws_top_name"]} {f["ws_top_amt"]} 万、{f["ws_second_name"]} {f["ws_second_amt"]} 万。省得呈"面状"分布,真假要靠逐单核查。</div>
        </div>

        <div data-anim="right" style="padding:3.2vh 0 0 2.6vw">
          <div class="t-cat" style="margin-bottom:1.6vh;color:var(--accent)">云南达利 · 饮料厂</div>
          <div class="kpi-big accent" style="font-size:min(8.4vw,14vh);margin-bottom:2.4vh;color:var(--accent)">{b["net"]}<span class="unit" style="font-size:.2em;font-weight:500;opacity:.5">万</span></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.6vw 1.4vw;padding-bottom:2.4vh">
            <div class="stat-card thin"><div class="stat-label">条数</div><div class="stat-nb" style="font-size:2.6vw">{b["rows_fmt"]}</div></div>
            <div class="stat-card thin"><div class="stat-label">备注覆盖</div><div class="stat-nb" style="font-size:2.6vw">{b["remark_pct"]}%</div></div>
            <div class="stat-card thin"><div class="stat-label">多耗</div><div class="stat-nb" style="font-size:2.6vw">{b["pos"]}万</div></div>
            <div class="stat-card thin"><div class="stat-label">节约</div><div class="stat-nb" style="font-size:2.6vw">{b["neg"]}万</div></div>
          </div>
          <div class="body-sm" style="color:var(--text-secondary)">条数只有食品厂的 <b>{b["rows_ratio"]}%</b>,省的却是其 <b>{b["net_ratio"]}%</b>。单条强度是食品厂的 <b>{b["strength"]} 倍</b>——省得"点状"且单点极重:{b["pgh_name"]} {b["pgh_rows"]} 条就省 {b["pgh_amt"]} 万。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p04(d):
    q = d["quality"]
    return f'''<!-- 04 · 数据质量说明 · slide dark · 差异表 -->
<section class="slide dark" data-animate="field-notes" data-layout="S18">
  <div class="canvas-card">
{_chrome("数据质量说明 / DATA CAVEAT", 4)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker accent" style="margin-bottom:1.4vh;color:var(--accent-bright);opacity:1">先说清楚:哪个数字不能用</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">工作簿里那个 <span style="color:var(--accent-bright)">{q["sum_total"]} 万</span> 加不起来</h2>

      <div style="display:grid;grid-template-columns:1.15fr .85fr;gap:3.4vw;margin-top:3.4vh;align-items:start">
        <div data-anim="table">
          <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:1.2vw;font-family:var(--mono);font-size:max(10px,.76vw);letter-spacing:.16em;text-transform:uppercase;opacity:.6;padding-bottom:1.4vh;border-bottom:1px solid rgba(255,255,255,.25)">
            <div>来源</div><div style="text-align:right">金额</div><div style="text-align:right">可复核</div>
          </div>
          <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:1.2vw;padding:1.8vh 0;border-bottom:1px solid rgba(255,255,255,.14);align-items:baseline">
            <div class="body" style="opacity:.92">汇总统计表「总偏差金额」合计</div>
            <div class="body" style="text-align:right;font-family:var(--mono);opacity:.92">{q["sum_total"]} 万</div>
            <div class="body-sm" style="text-align:right;color:var(--accent-bright)">否</div>
          </div>
          <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:1.2vw;padding:1.8vh 0;border-bottom:1px solid rgba(255,255,255,.14);align-items:baseline">
            <div class="body" style="opacity:.92">该表自身正偏差合计</div>
            <div class="body" style="text-align:right;font-family:var(--mono);opacity:.92">{q["sum_pos"]} 万</div>
            <div class="body-sm" style="text-align:right;opacity:.7">部分</div>
          </div>
          <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:1.2vw;padding:1.8vh 0;border-bottom:1px solid rgba(255,255,255,.14);align-items:baseline">
            <div class="body" style="opacity:.92">该表自身负偏差合计</div>
            <div class="body" style="text-align:right;font-family:var(--mono);opacity:.92">{q["sum_neg"]} 万</div>
            <div class="body-sm" style="text-align:right;opacity:.7">部分</div>
          </div>
          <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:1.2vw;padding:1.8vh 0;border-bottom:2px solid var(--accent);align-items:baseline">
            <div class="body" style="opacity:.92">本报告采用:明细逐行加总</div>
            <div class="body" style="text-align:right;font-family:var(--mono);color:var(--accent-bright)">{q["detail_net"]} 万</div>
            <div class="body-sm" style="text-align:right;color:var(--accent-bright)">是</div>
          </div>
          <div class="body-sm" style="margin-top:2.2vh;opacity:.72">正 {q["sum_pos"].lstrip("+")} + 负 {q["sum_neg"]} = {q["sum_calc"]} 万,与 {q["sum_total"]} 万相差 {q["gap"]} 万。该差额通常来自半成品(正/负列留空,走"产量偏差×单价")与汇总行自身矛盾。</div>
        </div>

        <div data-anim="right" style="border-left:3px solid var(--accent);padding-left:2vw">
          <div class="t-meta" style="margin-bottom:1.6vh;opacity:.72">为什么这件事值得单开一页</div>
          <div class="body" style="opacity:.88;line-height:1.75">偏差报告的价值全在"经得起查"。<br/><br/>如果首页写 {q["sum_total"]} 万,任何一个人把正负两列加一遍就会得到 {q["sum_calc"]} 万,那一刻整份报告的可信度一起归零。<br/><br/>所以本报告宁可数字小,也要<b>每一个数都能落到具体明细行</b>。</div>
          <div class="t-meta" style="margin-top:2.6vh;padding-top:1.8vh;border-top:1px solid rgba(255,255,255,.18);opacity:.6">建议:反馈给系统方核查汇总层算法</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _stat(label, nb, note, accent=False, nb_style=""):
    cls = "stat-card accent-top" if accent else "stat-card"
    return f'''          <div class="{cls}">
            <div class="stat-label">{label}</div>
            <div class="stat-nb"{nb_style}>{nb}</div>
            <div class="stat-note">{note}</div>
          </div>'''


def _p05(d):
    f, t = d["food"], d["total"]
    share = abs(f["net_raw"]) / max(1e-9, abs(float(t["net_raw"]))) * 100
    return f'''<!-- 05 · 食品厂总览 · slide light · 大字 KPI -->
<section class="slide light" data-animate="hero" data-layout="S02">
  <div class="canvas-card">
{_chrome("云南达利 · 食品厂 / FOOD PLANT", 5)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker accent" style="margin-bottom:1.4vh">第一部分 · 食品厂</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:32ch">{f["rows_fmt"]} 条偏差里,<span style="color:var(--accent)">两个车间</span>省掉大头</h2>

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:2.4vw;align-items:end;padding-top:4vh">
{_stat("净偏差", f'{f["net"]}<span class="stat-unit">万</span>', f"占全厂净偏差 {share:.1f}%", accent=True, nb_style=' style="color:var(--accent)"')}
{_stat("偏差条数", f["rows_fmt"], f'全厂 {t["food_pct"]}%,涉及 {f["ws_count"]} 个车间')}
{_stat("多耗 / 节约", f'{f["pos"]} / {f["neg"]}', "单位:万元 · 净额为负(节约)", nb_style=' style="font-size:3.4vw"')}
{_stat("备注覆盖率", f'{f["remark_pct"]}<span class="stat-unit">%</span>', f'{f["remark_n"]} / {f["rows_fmt"]} 条有说明')}
      </div>

      <div data-anim="bottom" style="align-self:end;display:grid;grid-template-columns:1fr 1fr;gap:2.4vw;border-top:1px solid var(--border-subtle);padding-top:2.4vh">
        <div>
          <div class="t-meta" style="margin-bottom:1vh">分类构成</div>
          <div class="body-sm" style="color:var(--text-secondary)">原材料 {f["raw_rows"]} 条 → 净 <b>{f["raw_net"]} 万</b>（节约大头）<br/>包材 {f["pkg_rows"]} 条 → 净 <b>{f["pkg_net"]} 万</b>（基本平衡）</div>
        </div>
        <div>
          <div class="t-meta" style="margin-bottom:1vh">一句话诊断</div>
          <div class="body-sm" style="color:var(--text-secondary)">食品厂省得<b>面广而单点轻</b>——节约与多耗大面积对冲,真正要看的是两个车间的节约是否真实:投料不足与定额虚高都会伪装成节约。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p06(d):
    f = d["food"]
    bars = []
    for i, b in enumerate(f["bars"]):
        dim = b.get("dim", not b["neg"])
        label_op = "" if not dim else ";opacity:.62"
        fill_op = "" if not dim else ";opacity:.62"
        meta_op = "" if not dim else ";opacity:.62"
        if b["neg"] and not dim:
            fill = f'<div class="bar-fill" style="width:{b["width"]}%"></div>'
        elif b["neg"] and dim:
            fill = f'<div class="bar-fill" style="width:{b["width"]}%;opacity:.4"></div>'
        else:
            fill = f'<div class="bar-fill" style="width:0;left:auto;right:0;width:{b["width"]}%"></div>'
        border = ' style="border-top:1px solid var(--border-subtle);padding-top:1.5vh"' if i == 4 else ""
        bars.append(
            f'          <div class="bar-row"{border}><div class="body-sm" style="font-weight:500{label_op}">{b["name"]}</div><div style="position:relative;height:1.5vh;background:var(--grey-1)">{fill}</div><div class="body-sm" style="font-family:var(--mono);text-align:right{fill_op}{meta_op}">{b["amt"]}万</div></div>'
        )
    return f'''<!-- 06 · 食品厂车间排名 · slide light · bar chart -->
<section class="slide light" data-animate="bar-grow" data-layout="S07">
  <div class="canvas-card">
{_chrome("食品厂 · 车间偏差排名 / BY WORKSHOP", 6)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker" style="margin-bottom:1.4vh">{f["ws_count"]} 个车间 · 按净偏差升序</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">{f["ws_top_name"]}一个车间,扛下 <span style="color:var(--accent)">全厂 {f["eat_ratio"]} 倍</span> 的节约</h2>

      <div style="display:grid;grid-template-rows:auto 1fr;gap:2.6vh;padding-top:3.4vh;align-content:start">
        <div data-anim="bars" style="display:flex;flex-direction:column;gap:1.5vh">
{chr(10).join(bars)}
        </div>

        <div data-anim="note" style="display:grid;grid-template-columns:1fr 1fr;gap:2.4vw;border-top:1px solid var(--border-subtle);padding-top:2.2vh">
          <div class="body-sm" style="color:var(--text-secondary)"><b>读数：</b>橙色为净额为负(节约)、灰色为净额为正(多耗)。{f["ws_top_name"]}({f["ws_top_rows"]} 条)+ {f["ws_second_name"]}({f["ws_second_rows"]} 条)合计 {f["top2_sum"]} 万,其余 {f["rest_ws_n"]} 个车间合计 {f["rest_sum"]} 万。</div>
          <div class="body-sm" style="color:var(--text-secondary)"><b>下一步：</b>{f["pos_ws_names"]}为多耗,要么定额偏紧要么确实超用,需复核标定;{f["ws_top_name"]}与{f["ws_second_name"]}需逐单排查——节约是真实节省,还是投料不足/定额虚高伪装的假节约。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p07(d):
    f = d["food"]
    rows = []
    for m in f["neg_top"]:
        rows.append(
            f'          <div style="display:grid;grid-template-columns:1.8fr .7fr .9fr;gap:1.2vw;padding:1.5vh 0;border-bottom:1px solid var(--border-subtle);align-items:baseline">\n            <div class="body-sm">{m["name"]}</div><div class="body-sm" style="text-align:right;font-family:var(--mono);opacity:.7">{m["rows"]}</div><div class="body-sm" style="text-align:right;font-family:var(--mono)">{m["amt"]}万</div>\n          </div>'
        )
    nrr = []
    for i, r in enumerate(f["noremark_rows"]):
        color = ';color:var(--accent)' if i == 0 else ''
        border = "2px solid var(--accent)" if i == len(f["noremark_rows"]) - 1 else "1px solid var(--border-subtle)"
        nrr.append(
            f'            <div style="display:flex;justify-content:space-between;align-items:baseline;border-bottom:{border};padding-bottom:1.2vh"><span class="body" style="font-weight:500">{r["name"]}</span><span class="body" style="font-family:var(--mono){color}">{r["rows"]} 条 · {r["amt"]}万</span></div>'
        )
    return f'''<!-- 07 · 食品厂物料 TOP + 无备注风险 · slide light -->
<section class="slide light" data-animate="stacked-ledger" data-layout="S13">
  <div class="canvas-card">
{_chrome("食品厂 · 重点物料 &amp; 无备注风险", 7)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker" style="margin-bottom:1.4vh">谁在省 &amp; 谁没写原因</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">{f["nr_top_name"]} <span style="color:var(--accent)">{f["nr_top_rows"]} 条</span> 无备注,金额 {f["nr_top_amt"]} 万</h2>

      <div style="display:grid;grid-template-columns:1.1fr .9fr;gap:3.4vw;margin-top:3.4vh;align-items:start">
        <div data-anim="left">
          <div class="t-meta" style="margin-bottom:1.6vh">节约物料 TOP {len(f["neg_top"])}（净额为负）</div>
          <div style="display:grid;grid-template-columns:1.8fr .7fr .9fr;gap:1.2vw;font-family:var(--mono);font-size:max(10px,.74vw);letter-spacing:.14em;text-transform:uppercase;opacity:.55;padding-bottom:1.2vh;border-bottom:1px solid var(--border-subtle)">
            <div>物料</div><div style="text-align:right">条数</div><div style="text-align:right">净偏差</div>
          </div>
{chr(10).join(rows)}
          <div class="body-sm" style="margin-top:2.4vh;padding-top:2vh;border-top:1px solid var(--border-subtle);color:var(--text-secondary)"><b>多耗 TOP：</b>{f["pos_note"]}。油脂类大额多耗,指向定额偏紧或超用,建议核对标定。</div>
        </div>

        <div data-anim="right" style="border-left:3px solid var(--accent);padding-left:2vw">
          <div class="t-meta" style="margin-bottom:1.6vh">无备注预警 · {f["noremark_total"]} 条全部在食品厂</div>
          <div style="display:flex;flex-direction:column;gap:1.5vh">
{chr(10).join(nrr)}
          </div>
          <div class="body-sm" style="margin-top:2.4vh;color:var(--text-secondary)">另有 <b>{f["dup_rows"]} 行整行重复</b>记录混在无备注预警中,建议先去重再统计。{f["nr_top_name"]}省得最多、又最不愿写原因,是本次核查的第一顺位。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p08(d):
    b, t = d["bev"], d["total"]
    share = abs(b["net_raw"]) / max(1e-9, abs(float(t["net_raw"]))) * 100
    return f'''<!-- 08 · 饮料厂总览 · slide light · 大字 KPI -->
<section class="slide light" data-animate="hero" data-layout="S02">
  <div class="canvas-card">
{_chrome("云南达利 · 饮料厂 / BEVERAGE PLANT", 8)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker accent" style="margin-bottom:1.4vh">第二部分 · 饮料厂</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:32ch">{b["rows_fmt"]} 条偏差,却省出 <span style="color:var(--accent)">{b["net"].lstrip(MINUS)} 万</span></h2>

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:2.4vw;align-items:end;padding-top:4vh">
{_stat("净偏差", f'{b["net"]}<span class="stat-unit">万</span>', f"占全厂净偏差 {share:.1f}%", accent=True, nb_style=' style="color:var(--accent)"')}
{_stat("偏差条数", b["rows_fmt"], f'全厂 {t["bev_pct"]}%,仅 {b["ws_count"]} 个车间')}
{_stat("单条偏差强度", f'{b["strength"]}<span class="stat-unit">×</span>', f"食品厂的 {b['strength']} 倍")}
{_stat("备注覆盖率", f'{b["remark_pct"]}<span class="stat-unit">%</span>', f'{b["remark_n"]} / {b["rows_fmt"]} 条有说明')}
      </div>

      <div data-anim="bottom" style="align-self:end;display:grid;grid-template-columns:1fr 1fr;gap:2.4vw;border-top:1px solid var(--border-subtle);padding-top:2.4vh">
        <div>
          <div class="t-meta" style="margin-bottom:1vh">分类构成</div>
          <div class="body-sm" style="color:var(--text-secondary)">原材料 {b["raw_rows"]} 条 → 净 <b>{b["raw_net"]} 万</b><br/>半成品 {b["half_rows"]} 条 → 净 <b>{b["half_net"]} 万</b>（饮料厂独有）<br/>包材 {b["pkg_rows"]} 条 → 净 <b>{b["pkg_net"]} 万</b>（基本平衡）</div>
        </div>
        <div>
          <div class="t-meta" style="margin-bottom:1vh">一句话诊断</div>
          <div class="body-sm" style="color:var(--text-secondary)">饮料厂省得<b>点少而单点极重</b>——几乎没有大面积小额偏差,但少数物料一次就省几万。适合按物料逐个溯源,而非流程整改。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p09(d):
    b = d["bev"]
    ws = []
    for i, r in enumerate(b["ws_rows"]):
        label_op = "" if r["neg"] else ';opacity:.68'
        v_op = ".7" if r["neg"] else ".55"
        m_style = ';color:var(--accent)' if i < 2 and r["neg"] else (';opacity:.68' if not r["neg"] else "")
        border = "2px solid var(--accent)" if i == len(b["ws_rows"]) - 1 else "1px solid var(--border-subtle)"
        ws.append(
            f'          <div style="display:grid;grid-template-columns:1.5fr .6fr .95fr;gap:1.2vw;padding:1.5vh 0;border-bottom:{border};align-items:baseline">\n            <div class="body-sm" style="font-weight:500{label_op}">{r["name"]}</div><div class="body-sm" style="text-align:right;font-family:var(--mono);opacity:{v_op}">{r["rows"]}</div><div class="body-sm" style="text-align:right;font-family:var(--mono){m_style}">{r["amt"]}万</div>\n          </div>'
        )
    half = []
    for i, h in enumerate(b["half_top"]):
        border = "2px solid var(--accent)" if i == len(b["half_top"]) - 1 else "1px solid var(--border-subtle)"
        half.append(
            f'            <div style="display:flex;justify-content:space-between;align-items:baseline;border-bottom:{border};padding-bottom:1.1vh"><span class="body-sm">{h["name"]}</span><span class="body-sm" style="font-family:var(--mono)">{h["amt"]}万 · {h["rows"]}条</span></div>'
        )
    return f'''<!-- 09 · 饮料厂车间 + 半成品 · slide light · 账单式 -->
<section class="slide light" data-animate="stacked-ledger" data-layout="S13">
  <div class="canvas-card">
{_chrome("饮料厂 · 车间与半成品 / BY WORKSHOP", 9)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker" style="margin-bottom:1.4vh">{b["ws_count"]} 个车间 · {b["ws_top"]["name"]}与{b["ws_second"]["name"]}是节约主力</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">{b["ws_top"]["name"]} <span style="color:var(--accent)">{b["ws_top"]["rows"]} 条</span> 就省 {b["ws_top"]["amt"].lstrip(MINUS)} 万</h2>

      <div style="display:grid;grid-template-columns:1.05fr .95fr;gap:3.4vw;margin-top:3.4vh;align-items:start">
        <div data-anim="left">
          <div class="t-meta" style="margin-bottom:1.6vh">车间净偏差排名</div>
          <div style="display:grid;grid-template-columns:1.5fr .6fr .95fr;gap:1.2vw;font-family:var(--mono);font-size:max(10px,.74vw);letter-spacing:.14em;text-transform:uppercase;opacity:.55;padding-bottom:1.2vh;border-bottom:1px solid var(--border-subtle)">
            <div>车间</div><div style="text-align:right">条数</div><div style="text-align:right">净偏差</div>
          </div>
{chr(10).join(ws)}
          <div class="body-sm" style="margin-top:2.4vh;padding-top:2vh;border-top:1px solid var(--border-subtle);color:var(--text-secondary)"><b>读数：</b>{b["ws_top"]["name"]}只有 {b["ws_top"]["rows"]} 条却排第一,单条省超 {b["ws_top_per_item"]} 元;{b["ws_second"]["name"]}条数最多({b["ws_second"]["rows"]})且净额为负,属"高频+高额节约"组合,最值得深挖真假。</div>
        </div>

        <div data-anim="right" style="border-left:3px solid var(--accent);padding-left:2vw">
          <div class="t-meta" style="margin-bottom:1.6vh">半成品 · {b["half_rows_fmt"]} 条 · 净 {b["half_net"]} 万</div>
          <div class="body-sm" style="color:var(--text-secondary);margin-bottom:2.2vh">半成品是饮料厂独有分类（食品厂无此类）。它<strong>不按金额列记录</strong>,而按"产量偏差×单价"计算,正/负金额列全部为 0——这正是工作簿汇总层数字加不起来的原因之一。</div>
          <div style="display:flex;flex-direction:column;gap:1.4vh">
{chr(10).join(half)}
          </div>
          <div class="body-sm" style="margin-top:2.4vh;opacity:.72">集中在<strong>中间品环节</strong>,指向同一工艺环节的理论产量与实际产量口径差。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p10(d):
    b = d["bev"]
    bars = []
    for m in b["neg_top"]:
        w = min(100, round(abs(m["amt_raw"]) / max(1e-9, abs(b["neg_top"][0]["amt_raw"])) * 100))
        bars.append(
            f'          <div class="bar-row"><div class="body-sm" style="font-weight:500">{m["name"]}</div><div style="position:relative;height:1.5vh;background:var(--grey-1)"><div class="bar-fill" style="width:{w}%"></div></div><div class="body-sm" style="font-family:var(--mono);text-align:right">{m["amt"]}万</div></div>'
        )
    return f'''<!-- 10 · 饮料厂物料 TOP · slide light · bar -->
<section class="slide light" data-animate="bar-grow" data-layout="S08">
  <div class="canvas-card">
{_chrome("饮料厂 · 重点物料 / TOP MATERIALS", 10)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker" style="margin-bottom:1.4vh">单点极重 · {b["pgh_rows"]} 条偏差 = {round(abs(b["neg_top"][0]["amt_raw"]) / 1e4)} 万</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:32ch">{b["pgh_name"]} <span style="color:var(--accent)">{b["pgh_rows"]} 条记录</span>,省下 {b["pgh_amt"].lstrip(MINUS)} 万</h2>

      <div style="display:grid;grid-template-columns:1.08fr .92fr;gap:3.4vw;margin-top:3.4vh;align-items:start">
        <div data-anim="bars" style="display:flex;flex-direction:column;gap:1.6vh">
{chr(10).join(bars)}
          <div class="body-sm" style="margin-top:1vh;color:var(--text-secondary)">上述 {len(b["neg_top"])} 项合计 <b>{b["top5_sum"]} 万</b>,占饮料厂净偏差的 <b>{b["top5_share"]}%</b>。</div>
        </div>

        <div data-anim="right" style="border-left:3px solid var(--accent);padding-left:2vw">
          <div class="t-meta" style="margin-bottom:1.6vh">值得单独追问的三件事</div>
          <div style="display:flex;flex-direction:column;gap:1.8vh">
            <div>
              <div class="body-sm" style="font-weight:500;color:var(--text-primary);margin-bottom:.5vh">① {b["pgh_name"]}为何只有 {b["pgh_rows"]} 条?</div>
              <div class="body-sm" style="color:var(--text-secondary)">{b["pgh_rows"]} 条记录省下 {b["pgh_amt"].lstrip(MINUS)} 万,单条省超 1 万元。是定额单位口径不一致（KG 与吨）,还是投料不足?单笔大额要先排除错单。</div>
            </div>
            <div>
              <div class="body-sm" style="font-weight:500;color:var(--text-primary);margin-bottom:.5vh">② {b["sugar_pair"][0][0]}与{b["sugar_pair"][1][0]}两项同时为负</div>
              <div class="body-sm" style="color:var(--text-secondary)">{b["sugar_pair"][0][0]} {b["sugar_pair"][0][1]} 万、{b["sugar_pair"][1][0]} {b["sugar_pair"][1][1]} 万,合计 {b["sugar_sum"]} 万。糖是饮料主要成本项,大幅节约要么是配方优化,要么是投料不足,建议核对。</div>
            </div>
            <div>
              <div class="body-sm" style="font-weight:500;color:var(--text-primary);margin-bottom:.5vh">③ {b["neg_top"][1]["name"]}单点大额</div>
              <div class="body-sm" style="color:var(--text-secondary)">{b["neg_top"][1]["name"]} {b["neg_top"][1]["rows"]} 条 {b["neg_top"][1]["amt"]} 万,属单点大额节约,优先核对单位口径与定额基准——确认是真实节省还是口径错位。</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p11(d):
    c = d["causes"]
    rows = []
    for i, r in enumerate(c["rows"]):
        border = "2px solid var(--accent)" if i == len(c["rows"]) - 1 else "1px solid var(--border-subtle)"
        name_style = ' style="font-weight:500"' if i == 0 else (' style="opacity:.68"' if i == len(c["rows"]) - 1 else "")
        imp_style = ';color:var(--accent)' if i == 0 else (';opacity:.68' if i == len(c["rows"]) - 1 else "")
        rows.append(
            f'          <div style="display:grid;grid-template-columns:1.7fr .6fr 1fr 1fr;gap:1.4vw;padding:1.5vh 0;border-bottom:{border};align-items:baseline">\n            <div class="body-sm"{name_style}>{r["name"]}</div><div class="body-sm" style="text-align:right;font-family:var(--mono);opacity:.7">{r["rows"]}</div><div class="body-sm" style="text-align:right;font-family:var(--mono)">{r["over"]}</div><div class="body-sm" style="text-align:right;font-family:var(--mono){imp_style}">{r["impact"]}万</div>\n          </div>'
        )
    top = c["top"]
    return f'''<!-- 11 · 原因结构 · slide light · 表格 -->
<section class="slide light" data-animate="manifesto" data-layout="S12">
  <div class="canvas-card">
{_chrome("偏差原因结构 / ROOT CAUSES", 11)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker accent" style="margin-bottom:1.4vh">{c["total_rows"]} 条有原因记录的偏差</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">{top["rows"]} 条「{top["name"]}」,影响 <span style="color:var(--accent)">{abs(top["impact_raw"]) / 1e4:.1f} 万</span></h2>

      <div style="display:grid;grid-template-rows:auto 1fr;gap:3vh;padding-top:3.4vh;align-content:start">
        <div data-anim="table">
          <div style="display:grid;grid-template-columns:1.7fr .6fr 1fr 1fr;gap:1.4vw;font-family:var(--mono);font-size:max(10px,.76vw);letter-spacing:.16em;text-transform:uppercase;opacity:.55;padding-bottom:1.3vh;border-bottom:1px solid var(--border-subtle)">
            <div>原因类别</div><div style="text-align:right">条数</div><div style="text-align:right">多耗</div><div style="text-align:right">净影响</div>
          </div>
{chr(10).join(rows)}
        </div>

        <div data-anim="note" style="display:grid;grid-template-columns:1fr 1fr;gap:2.4vw;border-top:1px solid var(--border-subtle);padding-top:2.2vh">
          <div class="body-sm" style="color:var(--text-secondary)"><b>结论：</b>「{top["name"]}」只占 {top["rows"]} 条记录,却贡献了 {abs(top["impact_raw"]) / 1e4:.1f} 万的影响量,单条平均超 {abs(top["impact_raw"]) / max(1, int(top["rows"].replace(",", ""))):,.0f} 元。<b>这是全场"少量记录、巨大金额"的首要原因类别</b>——它几乎必然是定额设定或系统换算的问题,而非现场操作问题。</div>
          <div class="body-sm" style="color:var(--text-secondary)"><b>口径提示：</b>「替代料」类别因数量与金额混列（多耗 {c["substitute"]["over"]} 万 / 少耗 {c["substitute"]["less"]} 万,系计量单位差异）,不计入本页金额统计。其明细共 {c["substitute"]["rows"]} 条,单独见工作簿「替代料明细」页。</div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p12(d):
    tr = d["trend"]
    cards = [
        ("→ 横盘", tr["flat"], tr["flat_pct"], False),
        ("↓ 近期改善", tr["imp"], tr["imp_pct"], False),
        ("↑ 近期变差", tr["wor"], tr["wor_pct"], True),
        ("↓↓ 持续改善", tr["imp2"], tr["imp2_pct"], False),
        ("↑↑ 持续变差", tr["wor2"], tr["wor2_pct"], True),
    ]
    out = []
    for label, n, p, accent in cards:
        border = "var(--accent)" if accent else "rgba(255,255,255,.4)"
        nb_style = ';color:var(--accent-bright)' if accent else ""
        out.append(
            f'          <div class="stat-card thin" style="border-top-color:{border}">\n            <div class="stat-label" style="opacity:.6">{label}</div>\n            <div class="stat-nb" style="font-size:min(4.6vw,8.5vh){nb_style}">{n}</div>\n            <div class="stat-note" style="color:rgba(255,255,255,.7)">{p}%</div>\n          </div>'
        )
    return f'''<!-- 12 · 趋势 · slide dark · 时间轴 -->
<section class="slide dark" data-animate="timeline-walk" data-layout="S16">
  <div class="canvas-card">
{_chrome("趋势 / TREND", 12)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker" style="margin-bottom:1.4vh;color:var(--accent-bright);opacity:1">{tr["materials"]} 个物料 · 按早/中/近期偏差率分组</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:32ch">近六成物料 <span style="color:var(--accent-bright)">纹丝不动</span></h2>

      <div style="display:grid;grid-template-rows:auto auto 1fr;gap:3vh;padding-top:3.2vh;align-content:start">
        <div data-anim="bars" style="display:grid;grid-template-columns:repeat(5,1fr);gap:1.6vw">
{chr(10).join(out)}
        </div>

        <div data-anim="note" style="display:grid;grid-template-columns:1fr 1fr;gap:2.4vw;border-top:1px solid rgba(255,255,255,.22);padding-top:2.2vh">
          <div class="body-sm" style="color:rgba(255,255,255,.8)"><b>好消息：</b>改善类合计 {tr["good_sum"]} 个物料（{tr["good_pct"]}%），是恶化类（{tr["bad_sum"]} 个，{tr["bad_pct"]}%）的 {tr["ratio"]} 倍。说明多数问题在被处理。</div>
          <div class="body-sm" style="color:rgba(255,255,255,.8)"><b>要盯的：</b>{tr["wor2"]} 个「持续变差」物料是唯一持续恶化的一组,建议逐项列入下月重点核查清单,而非泛泛整改。</div>
        </div>

        <div data-anim="foot" class="body-sm" style="align-self:end;color:rgba(255,255,255,.6);border-top:1px solid rgba(255,255,255,.14);padding-top:1.8vh">说明：趋势按自然日切分为早/中/近三段偏差率比较得出,仅覆盖有连续订单记录的物料。</div>
      </div>
    </div>
  </div>
</section>'''


def _p13(d):
    f = d["food"]
    return f'''<!-- 13 · 行动建议 · 食品厂 · slide light -->
<section class="slide light" data-animate="four-cards" data-layout="S14">
  <div class="canvas-card">
{_chrome("行动建议 · 食品厂 / ACTION · FOOD", 13)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker accent" style="margin-bottom:1.4vh">四条 · 按优先级排序</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">先查 {f["ws_top_name"]} 与 {f["ws_second_name"]} <span style="color:var(--accent)">省得是否真实</span></h2>

      <div style="display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:2.6vh 2.6vw;padding-top:3.4vh">
        <div data-anim="c1" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:3px solid var(--accent);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--accent)">01</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">{f["ws_top_name"]} + {f["ws_second_name"]}逐单复盘</div>
            <div class="body-sm" style="color:var(--text-secondary)">两车间合计省 {f["top2_sum"]} 万,占食品厂净节约 {f["top2_share"]}%。建议调取近三个月全部订单,区分"真实节省"与"投料不足/定额虚高",30 天内出具单车间归因报告。</div>
          </div>
        </div>

        <div data-anim="c2" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:1px solid var(--border-subtle);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">02</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">强制补录 {f["nr_top_name"]} {f["nr_top_rows"]} 条备注</div>
            <div class="body-sm" style="color:var(--text-secondary)">{f["nr_top_name"]} {f["nr_top_rows"]} 条无备注、涉及 {f["nr_top_amt"]} 万,是全场金额最大的未解释节约。要求 15 个工作日内补齐原因,逾期纳入车间考核。</div>
          </div>
        </div>

        <div data-anim="c3" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:1px solid var(--border-subtle);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">03</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">复核大额多耗物料定额</div>
            <div class="body-sm" style="color:var(--text-secondary)">{f["pos_note"]}。均为大额多耗——多耗意味着实际用量高于定额,要么定额偏紧,要么确实超用,建议重新标定。</div>
          </div>
        </div>

        <div data-anim="c4" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:1px solid var(--border-subtle);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">04</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">清理 {f["dup_rows"]} 行重复记录</div>
            <div class="body-sm" style="color:var(--text-secondary)">无备注预警中存在 {f["dup_rows"]} 行整行重复数据,会同时虚增条数与金额。建议在系统导出层增加去重,避免每月重复污染统计口径。</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p14(d):
    b = d["bev"]
    return f'''<!-- 14 · 行动建议 · 饮料厂 · slide light -->
<section class="slide light" data-animate="four-cards" data-layout="S14">
  <div class="canvas-card">
{_chrome("行动建议 · 饮料厂 / ACTION · BEVERAGE", 14)}

    <div style="flex:1;display:grid;grid-template-rows:auto auto 1fr;gap:0">
      <div data-anim="kicker" class="kicker accent" style="margin-bottom:1.4vh">四条 · 按优先级排序</div>
      <h2 data-anim="title" class="h-xl-zh" style="max-width:30ch">{b["pgh_rows"]} 条偏差省 {round(abs(b["neg_top"][0]["amt_raw"]) / 1e4)} 万,<span style="color:var(--accent)">先查这一笔</span></h2>

      <div style="display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:2.6vh 2.6vw;padding-top:3.4vh">
        <div data-anim="c1" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:3px solid var(--accent);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--accent)">01</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">{b["pgh_name"]} {b["pgh_rows"]} 条 → 专项核查</div>
            <div class="body-sm" style="color:var(--text-secondary)">{b["pgh_rows"]} 条记录省下 {b["pgh_amt"].lstrip(MINUS)} 万,单条省超 1 万元,属异常量级。优先确认是否存在单位口径错误（KG/吨）、单笔漏投或定额录入失误。单笔即可解释饮料厂 {b["pgh_share"]}% 的净节约。</div>
          </div>
        </div>

        <div data-anim="c2" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:1px solid var(--border-subtle);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">02</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">{b["ws_second"]["name"]}列入重点</div>
            <div class="body-sm" style="color:var(--text-secondary)">{b["ws_second"]["rows"]} 条 + 净省 {b["ws_rows"][1]["amt"]} 万,是饮料厂{"唯一" if b["hf_unique"] else "代表性"}"高频且高额节约"车间。建议按周跟踪,并检查该线半成品的产量偏差口径。</div>
          </div>
        </div>

        <div data-anim="c3" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:1px solid var(--border-subtle);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">03</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">统一半成品计算口径</div>
            <div class="body-sm" style="color:var(--text-secondary)">半成品 {b["half_rows_fmt"]} 条净 {b["half_net"]} 万,但正/负金额列为 0,走"产量偏差×单价"另一套算法。建议在报表中单列半成品口径,避免与原材料金额混加。</div>
          </div>
        </div>

        <div data-anim="c4" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;border-top:1px solid var(--border-subtle);padding-top:2vh">
          <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">04</div>
          <div>
            <div class="body" style="font-weight:500;margin-bottom:.8vh">糖类定额复核</div>
            <div class="body-sm" style="color:var(--text-secondary)">{b["sugar_pair"][0][0]} {b["sugar_pair"][0][1]} 万 + {b["sugar_pair"][1][0]} {b["sugar_pair"][1][1]} 万,合计 {b["sugar_sum"]} 万。糖为饮料主要成本项,建议与食品厂糖类偏差（{d["food"]["sugar_pair"][0][0]} {d["food"]["sugar_pair"][0][1]} 万、{d["food"]["sugar_pair"][1][0]} {d["food"]["sugar_pair"][1][1]} 万）合并做一次集团级定额复核。</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p15(d):
    c = d["causes"]
    return f'''<!-- 15 · Closing · slide split · 左 ASCII 橙 / 右白底 takeaway -->
<section class="slide split" data-animate="split-statement" data-layout="SWISS-CLOSING-ASCII">
  <div class="canvas-card">
    <div class="split-half">
      <div class="half b-accent" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between;position:relative;overflow:hidden">
        <canvas class="ascii-bg" aria-hidden="true"></canvas>
        <div class="chrome-min" style="margin-bottom:0;position:relative;z-index:1">
          <div class="l">15 / 15</div>
          <div class="r">CLOSING</div>
        </div>

        <div data-anim="manifesto" style="display:flex;flex-direction:column;gap:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em;margin-bottom:1.6vh">DATA FIRST</div>
          <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(8vw,14vh);line-height:.94;letter-spacing:-.025em;font-weight:200;color:#fff">数字可以被质疑,<br/>但要<span style="font-style:italic;font-weight:300">经得起查</span>。</h2>
          <div style="font-family:var(--sans),var(--sans-zh);font-size:max(13px,1vw);line-height:1.6;color:rgba(255,255,255,.86);font-weight:300;max-width:36ch;margin-top:1.4vh">本报告全部数字由明细逐行加总,任一条均可回溯到原始订单行。</div>
        </div>

        <div data-anim="signature" style="display:flex;justify-content:space-between;align-items:end;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.62)">云南达利 · 材料审核</div>
          <div class="t-meta" style="color:rgba(255,255,255,.62)">{d["gen_date"]}</div>
        </div>
      </div>

      <div class="half" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min">
          <div class="l">三条结论</div>
          <div class="r">03 TAKEAWAYS</div>
        </div>

        <div data-anim="rules" style="display:flex;flex-direction:column;gap:0">
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">01</div>
            <div>
              <h3 style="font-family:var(--sans),var(--sans-zh);font-weight:400;font-size:max(18px,1.8vw);line-height:1.2;letter-spacing:-.015em;color:var(--text-primary);margin-bottom:1vh">两厂要分开下药</h3>
              <p style="font-family:var(--sans),var(--sans-zh);font-size:max(12px,.92vw);line-height:1.6;color:var(--text-secondary);font-weight:300">食品厂面广点轻,靠流程标准化与定额复核;饮料厂点少极重,靠逐笔物料溯源。用同一套办法治两个厂,一定有一边白费力气。</p>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">02</div>
            <div>
              <h3 style="font-family:var(--sans),var(--sans-zh);font-weight:400;font-size:max(18px,1.8vw);line-height:1.2;letter-spacing:-.015em;color:var(--text-primary);margin-bottom:1vh">真正的病根在定额</h3>
              <p style="font-family:var(--sans),var(--sans-zh);font-size:max(12px,.92vw);line-height:1.6;color:var(--text-secondary);font-weight:300">「{c["top"]["name"]}」仅 {c["top"]["rows"]} 条却多耗 {abs(c["top"]["impact_raw"]) / 1e4:.1f} 万,是"少量记录、巨大金额"的首要多耗来源。它指向制度层面,不是现场操作层面。</p>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle);border-bottom:2px solid var(--accent)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--accent)">03</div>
            <div>
              <h3 style="font-family:var(--sans),var(--sans-zh);font-weight:400;font-size:max(18px,1.8vw);line-height:1.2;letter-spacing:-.015em;color:var(--accent);margin-bottom:1vh">先修报表,再谈管理</h3>
              <p style="font-family:var(--sans),var(--sans-zh);font-size:max(12px,.92vw);line-height:1.6;color:var(--text-secondary);font-weight:300">汇总层 {d["quality"]["sum_total"]} 万加不起来、{d["food"]["dup_rows"]} 行整行重复、半成品口径混列——报表本身的问题会让所有管理动作失去准星。建议优先反馈系统方。</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>'''


_PAGES = (_p01, _p02, _p03, _p04, _p05, _p06, _p07, _p08, _p09, _p10, _p11, _p12, _p13, _p14, _p15)


def render_swiss(d) -> str:
    """返回 15 个 <section> 拼接的 slides HTML。"""
    return "\n\n".join(page(d) for page in _PAGES)
