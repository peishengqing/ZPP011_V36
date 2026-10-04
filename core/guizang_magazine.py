# -*- coding: utf-8 -*-
"""归藏-Magazine（电子杂志风）15 页 slides 渲染层。
版式忠实复刻 2026-10-04 人工校验版，数字全部由 build_report_data 注入。
注意：封面/收尾 <section> 严禁加 data-anim="hero"（会被 body.motion-ready 藏死整页）。
"""

from __future__ import annotations

from .guizang_report import MINUS


def _neg_loss_cheng(flat_pct: float) -> str:
    """趋势标题的"近六成"口径。"""
    if 55 <= flat_pct < 65:
        return "近六成物料 <span class=\"hi\">纹丝不动</span>"
    return f"约 {flat_pct}% 物料 <span class=\"hi\">纹丝不动</span>"


def _p01(d):
    t = d["total"]
    return f'''<!-- 01 · 封面 · hero.dark -->
<section class="slide hero dark" data-theme="dark">
  <div class="tag" style="position:absolute;top:6vh;left:6vw">ZPP011 · 分厂报告 · {d["period"]}</div>
  <div style="display:flex;flex-direction:column;justify-content:center;flex:1">
    <div class="kicker" data-anim="kicker">PRODUCTION DEVIATION AUDIT · FOOD &amp; BEVERAGE</div>
    <h1 class="display-zh" data-anim="title" style="max-width:20ch">食品与饮料<br/>分开算这笔账</h1>
    <div style="margin-top:4.2vh;max-width:56ch">
      <p class="lead" data-anim="lead">{t["rows_fmt"]} 条偏差、两个厂、两套完全不同的病。这份报告不合并口径,谁的问题归谁。</p>
    </div>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:flex-end;border-top:1px solid rgba(var(--paper-rgb),.2);padding-top:2.4vh">
    <div class="meta" data-anim="meta">云南达利 · 材料审核 · {d["gen_date"]}</div>
    <div class="meta" data-anim="meta">→ 方向键翻页 / B 静态 / ESC 总览</div>
  </div>
</section>'''


def _p02(d):
    t = d["total"]
    return f'''<!-- 02 · 总览 · light · 大数字 -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">总览 / OVERVIEW</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:24ch">净偏差收口在<span class="hi">可解释区间</span></h2>

  <div style="display:grid;grid-template-columns:1.15fr 1fr;gap:5vw;margin-top:5vh;align-items:start">
    <div>
      <div class="stat" data-anim="kpi">
        <div class="m">净偏差金额 · NET DEVIATION</div>
        <div class="n" style="font-size:9vw">{t["net"]}<span style="font-size:.28em;font-family:var(--sans-zh);font-weight:400;opacity:.6;margin-left:.15em">万</span></div>
        <div class="l" style="opacity:.72;max-width:34ch">正 {t["pos"]} 万与负 {t["neg"]} 万大幅对冲后净亏。这不是"偏差消失了",而是多耗与少耗在同一盘账里互相抵消,只剩净口子。</div>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:2.6vh" data-anim="stats">
      <div class="rowline"><div class="k">条数</div><div class="v">{t["rows_fmt"]} 条,覆盖 {t["combo_count"]} 个车间×分类组合</div><div class="m">FULL</div></div>
      <div class="rowline"><div class="k">食品厂</div><div class="v">{t["food_rows"]} 条 · 占 {t["food_pct"]}% · 问题在"面"</div><div class="m">{t["food_pct"]}%</div></div>
      <div class="rowline"><div class="k">饮料厂</div><div class="v">{t["bev_rows"]} 条 · 占 {t["bev_pct"]}% · 问题在"点"</div><div class="m">{t["bev_pct"]}%</div></div>
      <div class="rowline"><div class="k">备注覆盖</div><div class="v">仅 {t["remark_pct"]}% 的偏差有原因说明</div><div class="m">{t["remark_pct"]}%</div></div>
    </div>
  </div>

  <div style="margin-top:auto;padding-top:3vh">
    <div class="callout" data-anim="note">
      <span class="q-big">口径说明</span> —— 本报告全部数字由「完整偏差明细」净偏差金额列逐行加总得出,可逐条复核。工作簿「汇总统计」页的"总偏差金额"合计({d["quality"]["sum_total"]} 万)与其自身正/负分项相加不符,本报告不采用,详见第 04 页。
    </div>
  </div>
</section>'''


def _p03(d):
    f, b = d["food"], d["bev"]
    return f'''<!-- 03 · 两厂对照 · light · A/B -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">两厂对照 / FOOD VS BEVERAGE</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{b["rows_ratio"]}% 的条数,亏掉 <span class="hi">{round(float(b["net_ratio"]))}%</span> 的钱</h2>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:0;margin-top:5vh;border-top:2px solid currentColor" data-anim="duo">
    <div style="padding:3.6vh 3vw 0 0;border-right:1px solid rgba(127,127,127,.3)">
      <div class="tag" style="opacity:.7">云南达利 · 食品厂</div>
      <div class="stat" style="margin-top:2.4vh">
        <div class="n" style="font-size:6.6vw">{f["net"]}<span style="font-size:.3em;font-family:var(--sans-zh);font-weight:400;opacity:.6;margin-left:.12em">万</span></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:2.2vh 2vw;margin-top:3vh">
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">条数</div><div class="plat"><div class="nb" style="font-size:2.1vw">{f["rows_fmt"]}</div></div></div>
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">备注覆盖</div><div class="plat"><div class="nb" style="font-size:2.1vw">{f["remark_pct"]}%</div></div></div>
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">正偏差</div><div class="plat"><div class="nb" style="font-size:2.1vw">{f["pos"]}万</div></div></div>
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">负偏差</div><div class="plat"><div class="nb" style="font-size:2.1vw">{f["neg"]}万</div></div></div>
      </div>
      <p class="body-zh" style="margin-top:3.2vh;opacity:.76;max-width:36ch">车间多、条数密,靠 <b>2 个车间</b>拖住全局:{f["ws_top_name"]} {f["ws_top_amt"]} 万、{f["ws_second_name"]} {f["ws_second_amt"]} 万。问题呈"面状"分布,治理要靠流程标准化。</p>
    </div>

    <div style="padding:3.6vh 0 0 3vw">
      <div class="tag" style="opacity:.7">云南达利 · 饮料厂</div>
      <div class="stat" style="margin-top:2.4vh">
        <div class="n" style="font-size:6.6vw">{b["net"]}<span style="font-size:.3em;font-family:var(--sans-zh);font-weight:400;opacity:.6;margin-left:.12em">万</span></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:2.2vh 2vw;margin-top:3vh">
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">条数</div><div class="plat"><div class="nb" style="font-size:2.1vw">{b["rows_fmt"]}</div></div></div>
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">备注覆盖</div><div class="plat"><div class="nb" style="font-size:2.1vw">{b["remark_pct"]}%</div></div></div>
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">正偏差</div><div class="plat"><div class="nb" style="font-size:2.1vw">{b["pos"]}万</div></div></div>
        <div><div class="m" style="font-family:var(--mono);font-size:10px;letter-spacing:.22em;opacity:.5">负偏差</div><div class="plat"><div class="nb" style="font-size:2.1vw">{b["neg"]}万</div></div></div>
      </div>
      <p class="body-zh" style="margin-top:3.2vh;opacity:.76;max-width:36ch">条数只有食品厂的 <b>{b["rows_ratio"]}%</b>,净额却达到其 <b>{b["net_ratio"]}%</b>。单条偏差强度是食品厂的 <b>{b["strength"]} 倍</b>——问题呈"点状"且单点极重:{b["pgh_name"]} {b["pgh_rows"]} 条就 {b["pgh_amt"]} 万。</p>
    </div>
  </div>
</section>'''


def _p04(d):
    q = d["quality"]
    return f'''<!-- 04 · 数据质量说明 · dark -->
<section class="slide dark" data-theme="dark">
  <div class="kicker" data-anim="kicker">数据质量说明 / DATA CAVEAT</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">工作簿里那个 <span class="hi">{q["sum_total"]} 万</span> 加不起来</h2>

  <div style="display:grid;grid-template-columns:1.2fr .8fr;gap:5vw;margin-top:4.6vh;align-items:start">
    <div data-anim="table">
      <div style="display:grid;grid-template-columns:1.6fr 1fr .8fr;gap:1.6vw;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;opacity:.55;padding-bottom:1.4vh;border-bottom:1px solid rgba(var(--paper-rgb),.3)">
        <div>来源</div><div style="text-align:right">金额</div><div style="text-align:right">可复核</div>
      </div>
      <div style="display:grid;grid-template-columns:1.6fr 1fr .8fr;gap:1.6vw;padding:1.9vh 0;border-bottom:1px solid rgba(var(--paper-rgb),.14);align-items:baseline">
        <div class="body-zh">汇总统计表「总偏差金额」合计</div>
        <div class="body-zh" style="text-align:right;font-family:var(--mono)">{q["sum_total"]} 万</div>
        <div class="body-zh" style="text-align:right;opacity:.55">否</div>
      </div>
      <div style="display:grid;grid-template-columns:1.6fr 1fr .8fr;gap:1.6vw;padding:1.9vh 0;border-bottom:1px solid rgba(var(--paper-rgb),.14);align-items:baseline">
        <div class="body-zh">该表自身正偏差合计</div>
        <div class="body-zh" style="text-align:right;font-family:var(--mono)">{q["sum_pos"]} 万</div>
        <div class="body-zh" style="text-align:right;opacity:.55">部分</div>
      </div>
      <div style="display:grid;grid-template-columns:1.6fr 1fr .8fr;gap:1.6vw;padding:1.9vh 0;border-bottom:1px solid rgba(var(--paper-rgb),.14);align-items:baseline">
        <div class="body-zh">该表自身负偏差合计</div>
        <div class="body-zh" style="text-align:right;font-family:var(--mono)">{q["sum_neg"]} 万</div>
        <div class="body-zh" style="text-align:right;opacity:.55">部分</div>
      </div>
      <div style="display:grid;grid-template-columns:1.6fr 1fr .8fr;gap:1.6vw;padding:1.9vh 0;border-bottom:2px solid currentColor;align-items:baseline">
        <div class="body-zh"><b>本报告采用:明细逐行加总</b></div>
        <div class="body-zh" style="text-align:right;font-family:var(--mono)"><b>{q["detail_net"]} 万</b></div>
        <div class="body-zh" style="text-align:right"><b>是</b></div>
      </div>
      <p class="body-zh" style="margin-top:2.6vh;opacity:.68;max-width:52ch">正 {q["sum_pos"].lstrip("+")} + 负 {q["sum_neg"]} = {q["sum_calc"]} 万,与 {q["sum_total"]} 万相差 {q["gap"]} 万。该差额通常来自半成品(正/负列留空,走"产量偏差×单价")与汇总行自身矛盾,请以软件「汇总统计」核查结果为准。</p>
    </div>

    <div data-anim="right" style="border-left:3px solid currentColor;padding-left:2.4vw">
      <div class="kicker" style="margin-bottom:2vh">为什么这件事值得单开一页</div>
      <p class="body-zh" style="opacity:.84;line-height:1.75">偏差报告的价值全在"经得起查"。<br/><br/>如果首页写 {q["sum_total"]} 万,任何一个人把正负两列加一遍就会得到 {q["sum_calc"]} 万,那一刻整份报告的可信度一起归零。<br/><br/>所以本报告宁可数字小,也要<b>每一个数都能落到具体明细行</b>。</p>
      <div class="meta" style="margin-top:3vh;padding-top:2vh;border-top:1px solid rgba(var(--paper-rgb),.2);opacity:.6">建议:反馈系统方核查汇总层算法</div>
    </div>
  </div>
</section>'''


def _p05(d):
    f = d["food"]
    return f'''<!-- 05 · 食品厂总览 · hero.light -->
<section class="slide hero light" data-theme="light">
  <div class="kicker" data-anim="kicker">第一部分 · 食品厂 / FOOD PLANT</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{f["rows_fmt"]} 条偏差里,藏着 <span class="hi">两个失控车间</span></h2>

  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:3vw;margin-top:auto;padding-bottom:2vh" data-anim="stats">
    <div class="stat"><div class="m">净偏差</div><div class="n" style="font-size:4.6vw">{f["net"]}万</div><div class="l">占全厂净偏差 {abs(f["net_raw"]) / max(1e-9, abs(float(d["total"]["net_raw"]))) * 100:.1f}%</div></div>
    <div class="stat"><div class="m">偏差条数</div><div class="n" style="font-size:4.6vw">{f["rows_fmt"]}</div><div class="l">全厂 {d["total"]["food_pct"]}%,涉及 {f["ws_count"]} 个车间</div></div>
    <div class="stat"><div class="m">正 / 负偏差</div><div class="n" style="font-size:3.2vw">{f["pos"]} / {f["neg"]}</div><div class="l">单位:万元 · 净额为负</div></div>
    <div class="stat"><div class="m">备注覆盖率</div><div class="n" style="font-size:4.6vw">{f["remark_pct"]}%</div><div class="l">{f["remark_n"]} / {f["rows_fmt"]} 条有说明</div></div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4vw;border-top:1px solid rgba(127,127,127,.3);padding-top:2.6vh" data-anim="bottom">
    <div><div class="kicker" style="margin-bottom:1.2vh">分类构成</div><p class="body-zh" style="opacity:.76">原材料 {f["raw_rows"]} 条 → 净 <b>{f["raw_net"]} 万</b>（主要拖累）<br/>包材 {f["pkg_rows"]} 条 → 净 <b>{f["pkg_net"]} 万</b>（基本平衡）</p></div>
    <div><div class="kicker" style="margin-bottom:1.2vh">一句话诊断</div><p class="body-zh" style="opacity:.76">食品厂的问题是<b>面广而单点轻</b>——原材料多耗与少耗大面积对冲,真正需要盯的是两个车间的系统性偏差。</p></div>
  </div>
</section>'''


def _p06(d):
    f = d["food"]
    bars = []
    for i, b in enumerate(f["bars"]):
        dim = b.get("dim", not b["neg"])
        label_op = "" if not dim else ";opacity:.55"
        fill_op = ".85" if not dim else ".4"
        meta_op = ".8" if not dim else ".5"
        extra = ";display:flex;justify-content:flex-end" if b["neg"] and dim else ""
        border = "border-top:1px solid rgba(127,127,127,.25);" if i == 4 else ""
        bars.append(
            f'    <div style="{border}display:grid;grid-template-columns:6em 1fr 5.5em;gap:1.8vw;align-items:center;padding:.7vh 0">'
            f'<div class="body-zh" style="font-weight:500{label_op}">{b["name"]}</div>'
            f'<div style="height:1.5vh;background:rgba(127,127,127,.15){extra}">'
            f'<div style="width:{b["width"]}%;height:100%;background:currentColor;opacity:{fill_op}"></div></div>'
            f'<div class="meta" style="text-align:right;opacity:{meta_op}">{b["amt"]}万</div></div>'
        )
    bars_html = "\n".join(bars)
    return f'''<!-- 06 · 食品厂车间排名 · light · 条形榜 -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">食品厂 · 车间偏差排名 / BY WORKSHOP</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{f["ws_top_name"]}吃掉<span class="hi">全厂 {f["eat_ratio"]} 倍</span>的净偏差</h2>

  <div style="display:flex;flex-direction:column;gap:1.5vh;margin-top:4vh" data-anim="bars">
{bars_html}
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4vw;margin-top:auto;border-top:1px solid rgba(127,127,127,.3);padding-top:2.4vh" data-anim="note">
    <p class="body-zh" style="opacity:.76"><b>读数:</b>深色为净偏差为负(拖累)、浅色为正(贡献)。{f["ws_top_name"]}({f["ws_top_rows"]} 条)+ {f["ws_second_name"]}({f["ws_second_rows"]} 条)合计 {f["top2_sum"]} 万,其余 {f["rest_ws_n"]} 个车间合计 {f["rest_sum"]} 万。</p>
    <p class="body-zh" style="opacity:.76"><b>下一步:</b>{f["pos_ws_names"]}为正偏差,说明定额偏保守;{f["ws_top_name"]}与{f["ws_second_name"]}需逐单排查是定额问题还是实际超耗。</p>
  </div>
</section>'''


def _p07(d):
    f = d["food"]
    mrows = []
    for m in f["neg_top"]:
        mrows.append(
            f'      <div class="rowline" style="grid-template-columns:2fr .6fr .9fr"><div class="k" style="font-size:1.15vw">{m["name"]}</div><div class="v" style="font-size:.95vw;opacity:.6">{m["rows"]} 条</div><div class="m">{m["amt"]}万</div></div>'
        )
    nrr = []
    for i, r in enumerate(f["noremark_rows"]):
        border = "2px solid currentColor" if i == len(f["noremark_rows"]) - 1 else "1px solid rgba(127,127,127,.25)"
        nrr.append(
            f'        <div style="display:flex;justify-content:space-between;align-items:baseline;border-bottom:{border};padding-bottom:1.2vh"><span class="body-zh" style="font-weight:500">{r["name"]}</span><span class="meta" style="opacity:.85">{r["rows"]} 条 · {r["amt"]}万</span></div>'
        )
    return f'''<!-- 07 · 食品厂物料 + 无备注 · light -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">食品厂 · 重点物料 &amp; 无备注风险</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{f["nr_top_name"]} <span class="hi">{f["nr_top_rows"]} 条</span> 无备注,金额 {f["nr_top_amt"]} 万</h2>

  <div style="display:grid;grid-template-columns:1.15fr .85fr;gap:5vw;margin-top:4.4vh;align-items:start">
    <div data-anim="left">
      <div class="kicker" style="margin-bottom:1.6vh">负偏差物料 TOP {len(f["neg_top"])}</div>
{chr(10).join(mrows)}
      <p class="body-zh" style="margin-top:3vh;opacity:.76;border-top:1px solid rgba(127,127,127,.25);padding-top:2.2vh"><b>正偏差 TOP:</b>{f["pos_note"]}。油脂类大额正向偏差,指向定额设定偏高。</p>
    </div>

    <div data-anim="right" style="border-left:3px solid currentColor;padding-left:2.4vw">
      <div class="kicker" style="margin-bottom:2vh">无备注预警 · {f["noremark_total"]} 条全部在食品厂</div>
      <div style="display:flex;flex-direction:column;gap:1.5vh">
{chr(10).join(nrr)}
      </div>
      <p class="body-zh" style="margin-top:3vh;opacity:.76">另有 <b>{f["dup_rows"]} 行整行重复</b>记录混在无备注预警中,建议先去重再统计。{f["nr_top_name"]}既亏得多、又最不愿写原因,是本次审计的第一顺位。</p>
    </div>
  </div>
</section>'''


def _p08(d):
    b, t = d["bev"], d["total"]
    return f'''<!-- 08 · 饮料厂总览 · hero.light -->
<section class="slide hero light" data-theme="light">
  <div class="kicker" data-anim="kicker">第二部分 · 饮料厂 / BEVERAGE PLANT</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{b["rows_fmt"]} 条偏差,却亏出 <span class="hi">{b["net"].lstrip(MINUS)} 万</span></h2>

  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:3vw;margin-top:auto;padding-bottom:2vh" data-anim="stats">
    <div class="stat"><div class="m">净偏差</div><div class="n" style="font-size:4.6vw">{b["net"]}万</div><div class="l">占全厂净偏差 {abs(b["net_raw"]) / max(1e-9, abs(float(t["net_raw"]))) * 100:.1f}%</div></div>
    <div class="stat"><div class="m">偏差条数</div><div class="n" style="font-size:4.6vw">{b["rows_fmt"]}</div><div class="l">全厂 {t["bev_pct"]}%,仅 {b["ws_count"]} 个车间</div></div>
    <div class="stat"><div class="m">单条偏差强度</div><div class="n" style="font-size:4.6vw">{b["strength"]}×</div><div class="l">是食品厂的 {b["strength"]} 倍</div></div>
    <div class="stat"><div class="m">备注覆盖率</div><div class="n" style="font-size:4.6vw">{b["remark_pct"]}%</div><div class="l">{b["remark_n"]} / {b["rows_fmt"]} 条有说明</div></div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4vw;border-top:1px solid rgba(127,127,127,.3);padding-top:2.6vh" data-anim="bottom">
    <div><div class="kicker" style="margin-bottom:1.2vh">分类构成</div><p class="body-zh" style="opacity:.76">原材料 {b["raw_rows"]} 条 → 净 <b>{b["raw_net"]} 万</b><br/>半成品 {b["half_rows"]} 条 → 净 <b>{b["half_net"]} 万</b>（饮料厂独有）<br/>包材 {b["pkg_rows"]} 条 → 净 <b>{b["pkg_net"]} 万</b>（基本平衡）</p></div>
    <div><div class="kicker" style="margin-bottom:1.2vh">一句话诊断</div><p class="body-zh" style="opacity:.76">饮料厂的问题是<b>点少而单点极重</b>——几乎没有大面积小额偏差,但少数物料一次就亏几万。适合按物料逐个溯源,而非流程整改。</p></div>
  </div>
</section>'''


def _p09(d):
    b = d["bev"]
    ws = []
    for i, r in enumerate(b["ws_rows"]):
        dim = not r["neg"]
        label_op = "" if not dim else ";opacity:.62"
        v_op = ".6" if not dim else ".45"
        m_op = "" if r["neg"] else ' style="opacity:.55"'
        ws.append(
            f'      <div class="rowline" style="grid-template-columns:1.6fr .6fr 1fr"><div class="k" style="font-size:1.15vw{label_op}">{r["name"]}</div><div class="v" style="font-size:.95vw;opacity:{v_op}">{r["rows"]} 条</div><div class="m"{m_op}>{r["amt"]}万</div></div>'
        )
    half = []
    for i, h in enumerate(b["half_top"]):
        border = "2px solid currentColor" if i == len(b["half_top"]) - 1 else "1px solid rgba(127,127,127,.25)"
        half.append(
            f'        <div style="display:flex;justify-content:space-between;align-items:baseline;border-bottom:{border};padding-bottom:1.1vh"><span class="body-zh">{h["name"]}</span><span class="meta" style="opacity:.8">{h["amt"]}万 · {h["rows"]}条</span></div>'
        )
    return f'''<!-- 09 · 饮料厂车间 + 半成品 · light -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">饮料厂 · 车间与半成品 / BY WORKSHOP</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{b["ws_top"]["name"]} <span class="hi">{b["ws_top"]["rows"]} 条</span> 就亏 {b["ws_top"]["amt"].lstrip(MINUS)} 万</h2>

  <div style="display:grid;grid-template-columns:1.05fr .95fr;gap:5vw;margin-top:4.4vh;align-items:start">
    <div data-anim="left">
      <div class="kicker" style="margin-bottom:1.6vh">车间净偏差排名</div>
{chr(10).join(ws)}
      <p class="body-zh" style="margin-top:3vh;opacity:.76;border-top:1px solid rgba(127,127,127,.25);padding-top:2.2vh"><b>读数:</b>{b["ws_top"]["name"]}只有 {b["ws_top"]["rows"]} 条却排第一,单条偏差超 {b["ws_top_per_item"]} 元;{b["ws_second"]["name"]}条数最多({b["ws_second"]["rows"]})且净额为负,属"高频+净亏"双差,优先级最高。</p>
    </div>

    <div data-anim="right" style="border-left:3px solid currentColor;padding-left:2.4vw">
      <div class="kicker" style="margin-bottom:2vh">半成品 · {b["half_rows_fmt"]} 条 · 净 {b["half_net"]} 万</div>
      <p class="body-zh" style="opacity:.78;margin-bottom:2.8vh">半成品是饮料厂独有分类（食品厂无此类）。它<b>不按金额列记录</b>,而按"产量偏差×单价"计算,正/负金额列全部为 0——这正是工作簿汇总层数字加不起来的原因之一。</p>
      <div style="display:flex;flex-direction:column;gap:1.4vh">
{chr(10).join(half)}
      </div>
      <p class="body-zh" style="margin-top:3vh;opacity:.72">集中在<b>中间品环节</b>,指向同一工艺环节的理论产量与实际产量口径差。</p>
    </div>
  </div>
</section>'''


def _p10(d):
    b = d["bev"]
    bars = []
    for i, m in enumerate(b["neg_top"]):
        w = min(100, round(abs(m["amt_raw"]) / max(1e-9, abs(b["neg_top"][0]["amt_raw"])) * 100))
        bars.append(
            f'      <div style="display:grid;grid-template-columns:9em 1fr 5em;gap:1.8vw;align-items:center"><div class="body-zh" style="font-weight:500">{m["name"]}</div><div style="height:1.5vh;background:rgba(127,127,127,.15)"><div style="width:{w}%;height:100%;background:currentColor;opacity:.85"></div></div><div class="meta" style="text-align:right;opacity:.85">{m["amt"]}万</div></div>'
        )
    return f'''<!-- 10 · 饮料厂物料 TOP · light -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">饮料厂 · 重点物料 / TOP MATERIALS</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{b["pgh_name"]} <span class="hi">{b["pgh_rows"]} 条记录</span>,亏掉 {b["pgh_amt"].lstrip(MINUS)} 万</h2>

  <div style="display:grid;grid-template-columns:1.1fr .9fr;gap:5vw;margin-top:4.4vh;align-items:start">
    <div data-anim="bars" style="display:flex;flex-direction:column;gap:1.9vh;margin-top:1vh">
{chr(10).join(bars)}
      <p class="body-zh" style="margin-top:2.4vh;opacity:.76">上述 {len(b["neg_top"])} 项合计 <b>{b["top5_sum"]} 万</b>,占饮料厂净偏差的 <b>{b["top5_share"]}%</b>。</p>
    </div>

    <div data-anim="right" style="border-left:3px solid currentColor;padding-left:2.4vw">
      <div class="kicker" style="margin-bottom:2.2vh">值得单独追问的三件事</div>
      <div style="display:flex;flex-direction:column;gap:2.4vh">
        <div>
          <div class="body-zh" style="font-weight:600;margin-bottom:.6vh">① {b["pgh_name"]}为何只有 {b["pgh_rows"]} 条?</div>
          <p class="body-zh" style="opacity:.76">{b["pgh_rows"]} 条记录产生 {b["pgh_amt"].lstrip(MINUS)} 万偏差,单条超 1 万元。是单笔大额错发,还是定额单位口径不一致（KG 与吨）?</p>
        </div>
        <div>
          <div class="body-zh" style="font-weight:600;margin-bottom:.6vh">② {b["sugar_pair"][0][0]}与{b["sugar_pair"][1][0]}两项同时为负</div>
          <p class="body-zh" style="opacity:.76">{b["sugar_pair"][0][0]} {b["sugar_pair"][0][1]} 万、{b["sugar_pair"][1][0]} {b["sugar_pair"][1][1]} 万,合计 {b["sugar_sum"]} 万。糖是饮料主要成本项,建议核对配方定额。</p>
        </div>
        <div>
          <div class="body-zh" style="font-weight:600;margin-bottom:.6vh">③ {b["neg_top"][1]["name"]}单点大额</div>
          <p class="body-zh" style="opacity:.76">{b["neg_top"][1]["name"]} {b["neg_top"][1]["rows"]} 条 {b["neg_top"][1]["amt"]} 万,属单点大额偏差,通常与调机废料相关;建议核对当月调机记录与废料登记。</p>
        </div>
      </div>
    </div>
  </div>
</section>'''


def _p11(d):
    c = d["causes"]
    rows = []
    for i, r in enumerate(c["rows"]):
        border = "2px solid currentColor" if i == len(c["rows"]) - 1 else "1px solid rgba(var(--paper-rgb),.14)"
        rows.append(
            f'      <div style="display:grid;grid-template-columns:1.8fr .6fr 1fr 1fr;gap:1.8vw;padding:1.1vh 0;border-bottom:{border};align-items:baseline"><div class="body-zh" style="font-weight:{"600" if i == 0 else "400"}{"" if i == 0 else ";opacity:.85"}">{r["name"]}</div><div class="body-zh" style="text-align:right;font-family:var(--mono);opacity:.7">{r["rows"]}</div><div class="body-zh" style="text-align:right;font-family:var(--mono)">{r["over"]}</div><div class="body-zh" style="text-align:right;font-family:var(--mono)"><b>{r["impact"]}万</b></div></div>'
        )
    top = c["top"]
    return f'''<!-- 11 · 原因结构 · dark -->
<section class="slide dark" data-theme="dark">
  <div class="kicker" data-anim="kicker">偏差原因结构 / ROOT CAUSES</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{top["rows"]} 条「{top["name"]}」,影响 <span class="hi">{abs(top["impact_raw"]) / 1e4:.1f} 万</span></h2>

  <div style="display:grid;grid-template-rows:auto auto;gap:2.4vh;margin-top:3vh" data-anim="table">
    <div>
      <div style="display:grid;grid-template-columns:1.8fr .6fr 1fr 1fr;gap:1.8vw;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;opacity:.55;padding-bottom:1.3vh;border-bottom:1px solid rgba(var(--paper-rgb),.3)">
        <div>原因类别</div><div style="text-align:right">条数</div><div style="text-align:right">多耗</div><div style="text-align:right">净影响</div>
      </div>
{chr(10).join(rows)}
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:4vw;border-top:1px solid rgba(var(--paper-rgb),.22);padding-top:2.4vh">
      <p class="body-zh" style="opacity:.82"><b>结论:</b>「{top["name"]}」只占 {top["rows"]} 条记录,却贡献了 {abs(top["impact_raw"]) / 1e4:.1f} 万的影响量,单条平均超 {abs(top["impact_raw"]) / max(1, int(top["rows"].replace(",", ""))):,.0f} 元。<b>这是全场"少量记录、巨大金额"的首要原因类别</b>——它几乎必然是定额设定或系统换算的问题,而非现场操作问题。</p>
      <p class="body-zh" style="opacity:.82"><b>口径提示:</b>「替代料」类别因数量与金额混列（多耗 {c["substitute"]["over"]} 万 / 少耗 {c["substitute"]["less"]} 万,系计量单位差异）,不计入本页金额统计。其明细共 {c["substitute"]["rows"]} 条,单独见工作簿「替代料明细」页。</p>
    </div>
  </div>
</section>'''


def _p12(d):
    tr = d["trend"]
    return f'''<!-- 12 · 趋势 · light -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">趋势 / TREND · {tr["materials"]} 个物料</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{_neg_loss_cheng(float(tr["flat_pct"]))}</h2>

  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:2.6vw;margin-top:5vh" data-anim="stats">
    <div class="stat"><div class="m">→ 横盘</div><div class="n" style="font-size:4.2vw">{tr["flat"]}</div><div class="l">{tr["flat_pct"]}%</div></div>
    <div class="stat"><div class="m">↓ 近期改善</div><div class="n" style="font-size:4.2vw">{tr["imp"]}</div><div class="l">{tr["imp_pct"]}%</div></div>
    <div class="stat"><div class="m">↑ 近期变差</div><div class="n" style="font-size:4.2vw">{tr["wor"]}</div><div class="l">{tr["wor_pct"]}%</div></div>
    <div class="stat"><div class="m">↓↓ 持续改善</div><div class="n" style="font-size:4.2vw">{tr["imp2"]}</div><div class="l">{tr["imp2_pct"]}%</div></div>
    <div class="stat"><div class="m">↑↑ 持续变差</div><div class="n" style="font-size:4.2vw">{tr["wor2"]}</div><div class="l">{tr["wor2_pct"]}%</div></div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4vw;margin-top:auto;border-top:1px solid rgba(127,127,127,.3);padding-top:2.6vh" data-anim="note">
    <p class="body-zh" style="opacity:.78"><b>好消息:</b>改善类合计 {tr["good_sum"]} 个物料（{tr["good_pct"]}%）,是恶化类（{tr["bad_sum"]} 个,{tr["bad_pct"]}%）的 {tr["ratio"]} 倍。说明多数问题在被处理。</p>
    <p class="body-zh" style="opacity:.78"><b>要盯的:</b>{tr["wor2"]} 个「持续变差」物料是唯一真正失控的一组,建议逐项列入下月重点核查清单,而非泛泛整改。</p>
  </div>
  <p class="body-zh" style="margin-top:2.4vh;opacity:.5;font-size:max(12px,.9vw)">说明:趋势按自然日切分为早/中/近三段偏差率比较得出,仅覆盖有连续订单记录的物料。</p>
</section>'''


def _p13(d):
    f = d["food"]
    return f'''<!-- 13 · 行动建议 · 食品厂 · light -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">行动建议 · 食品厂 / ACTION · FOOD</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">先把 {f["ws_top_name"]} 与 {f["ws_second_name"]} <span class="hi">关进笼子</span></h2>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4vh 4vw;margin-top:4.4vh" data-anim="cards">
    <div style="border-top:3px solid currentColor;padding-top:2.2vh">
      <div class="pillar"><div class="ic">01</div><div class="t" style="font-size:1.7vw">{f["ws_top_name"]} + {f["ws_second_name"]}逐单复盘</div><div class="d">两车间合计 {f["top2_sum"]} 万,占食品厂净偏差 {f["top2_share"]}%。建议调取近三个月全部订单,区分"定额偏差"与"实际超耗",30 天内出具单车间归因报告。</div></div>
    </div>
    <div style="border-top:1px solid rgba(127,127,127,.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">02</div><div class="t" style="font-size:1.7vw">强制补录 {f["nr_top_name"]} {f["nr_top_rows"]} 条备注</div><div class="d">{f["nr_top_name"]} {f["nr_top_rows"]} 条无备注、涉及 {f["nr_top_amt"]} 万,是全场金额最大的未解释偏差。要求 15 个工作日内补齐原因,逾期纳入车间考核。</div></div>
    </div>
    <div style="border-top:1px solid rgba(127,127,127,.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">03</div><div class="t" style="font-size:1.7vw">复核大额正偏差物料定额</div><div class="d">{f["pos_note"]}。均为大额正偏差——正偏差意味着实际用量低于定额,指向定额偏高,建议重新标定。</div></div>
    </div>
    <div style="border-top:1px solid rgba(127,127,127,.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">04</div><div class="t" style="font-size:1.7vw">清理 {f["dup_rows"]} 行重复记录</div><div class="d">无备注预警中存在 {f["dup_rows"]} 行整行重复数据,会同时虚增条数与金额。建议在系统导出层增加去重,避免每月重复污染统计口径。</div></div>
    </div>
  </div>
</section>'''


def _p14(d):
    b = d["bev"]
    return f'''<!-- 14 · 行动建议 · 饮料厂 · light -->
<section class="slide light" data-theme="light">
  <div class="kicker" data-anim="kicker">行动建议 · 饮料厂 / ACTION · BEVERAGE</div>
  <h2 class="h1-zh" data-anim="title" style="max-width:28ch">{b["pgh_rows"]} 条偏差亏 {round(abs(b["neg_top"][0]["amt_raw"]) / 1e4)} 万,<span class="hi">先查这一笔</span></h2>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4vh 4vw;margin-top:4.4vh" data-anim="cards">
    <div style="border-top:3px solid currentColor;padding-top:2.2vh">
      <div class="pillar"><div class="ic">01</div><div class="t" style="font-size:1.7vw">{b["pgh_name"]} {b["pgh_rows"]} 条 → 专项核查</div><div class="d">{b["pgh_rows"]} 条记录产生 {b["pgh_amt"].lstrip(MINUS)} 万偏差,单条超 1 万元,属异常量级。优先确认是否存在单位口径错误（KG/吨）、单笔错发或定额录入失误。单笔即可解释饮料厂 {b["pgh_share"]}% 的净偏差。</div></div>
    </div>
    <div style="border-top:1px solid rgba(127,127,127,.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">02</div><div class="t" style="font-size:1.7vw">{b["ws_second"]["name"]}列入重点</div><div class="d">{b["ws_second"]["rows"]} 条 + 净 {b["ws_rows"][1]["amt"]} 万,是饮料厂{"唯一" if b["hf_unique"] else "代表性"}"高频且净亏"车间。建议按周跟踪,并检查该线半成品的产量偏差口径。</div></div>
    </div>
    <div style="border-top:1px solid rgba(127,127,127,.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">03</div><div class="t" style="font-size:1.7vw">统一半成品计算口径</div><div class="d">半成品 {b["half_rows_fmt"]} 条净 {b["half_net"]} 万,但正/负金额列为 0,走"产量偏差×单价"另一套算法。建议在报表中单列半成品口径,避免与原材料金额混加。</div></div>
    </div>
    <div style="border-top:1px solid rgba(127,127,127,.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">04</div><div class="t" style="font-size:1.7vw">糖类定额复核</div><div class="d">{b["sugar_pair"][0][0]} {b["sugar_pair"][0][1]} 万 + {b["sugar_pair"][1][0]} {b["sugar_pair"][1][1]} 万,合计 {b["sugar_sum"]} 万。糖为饮料主要成本项,建议与食品厂糖类偏差（{d["food"]["sugar_pair"][0][0]} {d["food"]["sugar_pair"][0][1]} 万、{d["food"]["sugar_pair"][1][0]} {d["food"]["sugar_pair"][1][1]} 万）合并做一次集团级定额复核。</div></div>
    </div>
  </div>
</section>'''


def _p15(d):
    c = d["causes"]
    return f'''<!-- 15 · 收尾 · hero.dark -->
<section class="slide hero dark" data-theme="dark">
  <div class="kicker" data-anim="kicker">DATA FIRST · 三条结论</div>
  <h2 class="display-zh" data-anim="title" style="max-width:18ch;font-size:6.4vw">数字可以被质疑,<br/>但要经得起查。</h2>

  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:3.4vw;margin-top:auto;padding-bottom:3vh" data-anim="rules">
    <div style="border-top:1px solid rgba(var(--paper-rgb),.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">01</div><div class="t" style="font-size:1.8vw">两厂要分开下药</div><div class="d">食品厂面广点轻,靠流程标准化与定额复核;饮料厂点少极重,靠逐笔物料溯源。用同一套办法治两个厂,一定有一边白费力气。</div></div>
    </div>
    <div style="border-top:1px solid rgba(var(--paper-rgb),.35);padding-top:2.2vh">
      <div class="pillar"><div class="ic">02</div><div class="t" style="font-size:1.8vw">真正的病根在定额</div><div class="d">「{c["top"]["name"]}」仅 {c["top"]["rows"]} 条却影响 {abs(c["top"]["impact_raw"]) / 1e4:.1f} 万,是"少量记录、巨大金额"的首要原因。它指向制度层面,不是现场操作层面。</div></div>
    </div>
    <div style="border-top:3px solid currentColor;padding-top:2.2vh">
      <div class="pillar"><div class="ic">03</div><div class="t" style="font-size:1.8vw">先修报表,再谈管理</div><div class="d">汇总层 {d["quality"]["sum_total"]} 万加不起来、{d["food"]["dup_rows"]} 行整行重复、半成品口径混列——报表本身的问题会让所有管理动作失去准星。建议优先反馈系统方。</div></div>
    </div>
  </div>

  <div style="display:flex;justify-content:space-between;align-items:flex-end;border-top:1px solid rgba(var(--paper-rgb),.2);padding-top:2.4vh">
    <div class="meta">云南达利 · 材料审核</div>
    <div class="meta">{d["gen_date"]} · 完</div>
  </div>
</section>'''


_PAGES = (_p01, _p02, _p03, _p04, _p05, _p06, _p07, _p08, _p09, _p10, _p11, _p12, _p13, _p14, _p15)


def render_magazine(d) -> str:
    """返回 15 个 <section> 拼接的 slides HTML。"""
    return "\n\n".join(page(d) for page in _PAGES)
