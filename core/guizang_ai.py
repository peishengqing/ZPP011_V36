# -*- coding: utf-8 -*-
"""guizang_ai.py — 归藏报告「AI 每期重新设计」模块（v43.258）

是什么
------
让 AI（Agnes）每期现场设计一份全新的报告版式并写出完整 HTML，取代
「template.html + Python 注入」那套固定外壳。数据仍然全部来自
core.guizang_report.build_report_data() 算出的数据字典，AI 不接触任何原始数据。

为什么需要数字护栏（本模块的核心）
----------------------------------
归藏报告第 04 页整页都在讲一件事：「每一个数都能落到具体明细行」。
AI 排版数字有两种死法：抄错（把 −592.9 写成 −529.9）、自己算（把两个数一除
得出一个字典里没有的比例）。前者毁掉的是单个数字，后者毁掉的是整套审计逻辑。

因此本模块对 AI 输出的 HTML 做**硬门校验**：
  · 白名单 = 数据字典 JSON 文本里出现过的每一个数字（含格式化串里的），
    外加页码/年份等常量；
  · 校验对象 = HTML 的**可见文本**（去 script/style、去标签，连属性一起剥掉，
    所以 CSS 里的 1.2fr / 11.6vw 不会被误判）；
  · HTML 里任何一个数字不在白名单 → 记为一条违规，附上下文；
  · 有违规就不算通过：由调用方决定重试 / 回退到 Python 渲染 / 强行接受。

这把「AI 可能编错数」从不可控变成了「当场抓住」。宁可多一次生成，不可错一个数。

离线约束
--------
公司网络有 DNS 劫持，Google Fonts / unpkg / jsdelivr 全部打不开，所以 prompt
里硬性要求零外链：字体用系统字体栈、图标用内联 SVG 或 Unicode、动效用原生
CSS/JS。既有报告也是全离线的，这条不能破。
"""

from __future__ import annotations

import json
import random
import re
import time
from html import unescape
from typing import Optional

# ── 设计方向池：每次生成挑一个，保证「每期不一样」──────────────────
# 这些只是**视觉/结构方向**，不影响任何数字；数字永远来自数据字典。
DESIGN_DIRECTIONS = [
    "瑞士国际主义：严格网格、无衬线、大量留白、单一强调色、信息层级靠字重与字号",
    "暗色数据大屏：深底、等宽数字、荧光强调色、仪表盘式分区、高对比",
    "编辑部报纸风：衬线标题、多栏排版、竖排分隔线、印章式标注、黑白为主",
    "包豪斯几何：原色块（红黄蓝）、粗横线、圆形与方形构成、强构成感",
    "日式简约：极窄边框、竖排标题、大量负空间、细线分割、克制配色",
    "终端极客风：等宽字体、命令行提示符、ASCII 分隔线、绿/琥珀单色",
    "年报图表向：以图表为主体、每页一个核心图表、注释式图注、数据墨水比高",
    "杂志专题风：大图式留白封面、跨页大标题、引文式结论、编号小节",
]

# ── 归藏（guizang）双风格：裴哥 2026-10-24 点名「用归藏做，都 AI、不套模板」。
# 视觉规范提炼自 guizang-ppt-skill 的 references/themes.md + layouts.md（杂志风）
# 与 themes-swiss.md + layouts-swiss.md（瑞士风）；AI 按规范自由设计版式，
# 不复制 skill 的 template.html，数字仍全部来自数据字典 + 过数字护栏。
GZ_MAGAZINE = """归藏 · 电子杂志 × 电子墨水（Guizang Magazine × E-ink）。严格遵循以下规范，规范内自由发挥：
【主题色】从归藏 5 套预设选一套，一份 deck 只用一套不混搭：① 墨水经典 ink#0a0a0b/paper#f1efea/paper-tint#e8e5de ② 靛蓝瓷 ink#0a1f3d/paper#f1f3f5/tint#e4e8ec ③ 森林墨 ink#1a2e1f/paper#f5f1e8/tint#ece7da ④ 牛皮纸 ink#2a1e13/paper#eedfc7/tint#e0d0b6 ⑤ 沙丘 ink#1f1a14/paper#f0e6d2/tint#e3d7bf。数据审核类报告推荐靛蓝瓷或墨水经典。不许自定义 hex。
【排版】大标题用系统衬线栈（Noto Serif SC/Source Han Serif SC/Georgia/Songti SC），正文无衬线，元数据与数字标签用等宽栈（JetBrains Mono/SFMono/Consolas）。纸感底色 + 墨字，发丝细分割线（currentColor 驱动）。
【语言】西式版式语言只影响字体/网格/色彩，**不影响语言**：所有可见文字必须是简体中文（标题/栏目标签/表头/图例/注释/结论建议），禁止英文标题与英文标签（Net Deviation/Top 5/Factory Detail 一类全不许）；等宽字体只渲染数字与编码，不写英文标语。唯一例外：ZPP011、SAP、ERP、A/B、物料编码/订单号。
【编辑元素】每页 kicker 小栏目标签 + meta-row（期号/日期/页码）；核心数字用 stat-card 组合（大数字+单位+标签+注脚）；重要结论用 callout 引述块；流程用 pipeline 步骤条（编号+标题+描述）。
【布局】杂志式不对称网格分栏（如 2-7-5 / 2-6-6 / 2-8-4 / 3-3），大量留白；hero 封面页可用原生 Canvas/WebGL 做流体/等高线/色散背景（零外链），也可用纸感纯色+细线网格；内页保持纸面安静。
【动效】原生 CSS/JS 级联淡入（元素带 data-anim，翻到当前页依次淡入），hero 页更慢更有仪式感，大引用页逐句揭示；必须保留键盘 ←→/空格/PageUp/PageDown 翻页、ESC 总览、B 静态模式（关动效）。"""

GZ_SWISS = """归藏 · 瑞士国际主义（Guizang Swiss / International Typographic Style）。严格遵循以下规范，规范内自由发挥：
【主题色】单一高饱和锚点色只选一个、绝不混搭：克莱因蓝 #002FA7（推荐，数据/商业）、柠檬黄 #FFD500、柠檬绿 #C5E803、安全橙 #FF6B35。底色 #fafaf8 纸白，文字 #0a0a0a 近黑，灰阶 #f0f0ee（浅灰块）/#d4d4d2（分割线）/#737373（辅助文字）。浅色 accent（黄/绿）上文字必须用纯黑。
【排版】Inter / Helvetica Neue 系统无衬线栈 + JetBrains Mono 等宽；大标题 font-weight 200（极细）配 letter-spacing:-0.04em、line-height:0.9，重点词/数字 300；正文 300；小标签 t-cat 600。中文大标题按长度降字号：1 行≤8 字 min(6.4vw,11.2vh)；2 行每行≤8 字 min(5.8vw,10.2vh)；任一行 9-12 字 min(5.2vw,9.2vh)；更长就改写标题。
【语言】瑞士的西式设计语言（Inter/Helvetica/Mono、网格、字重、单一锚点色）只影响版式，**不影响语言**：所有可见文字必须是简体中文（标题/栏目标签/表头/图例/注释/结论建议），禁止英文标题与英文标签（Net Deviation/Top 5/Factory Detail/Overage 一类全不许——实测有整份报告中文仅占 18% 的废版）；等宽字体只渲染数字与编码，不写英文标语。唯一例外：ZPP011、SAP、ERP、A/B、物料编码/订单号。
【网格】16 列 grid（grid-template-columns:repeat(16,1fr) + gap:16px）；画布卡 100vw×100vh、直角无圆角、padding 5.6vh 5vw 4.4vh；页眉/主体/脚注共用同一条 5vw 边线，主体绝不二次加水平 padding；不用 WebGL 背景，body 即纸白。
【硬规则】直角、纯色、不透明；禁止渐变、禁止圆角、禁止阴影；accent 只做局部高亮不满屏；SVG 只画几何不写可见文字（标签一律放 HTML）。
【锚点色唯一性】只允许定义一个强调色变量（--accent = 选定的那一个），**不许定义或使用任何第二个强调色**（如 --accent-light / 辅助黄 / 辅助绿 / 第二高亮）——页面上出现的强调色必须且只能是选定的那一个，这是瑞士风的灵魂。需要“浅色强调块”时用 --accent 的低透明度叠在纸白上（如 color-mix 或手算同色系浅 tint），不许换成另一个色相。
【动效】原生 CSS/JS 入场（级联淡入/方向性揭示），保留键盘翻页 + B 静态模式（low-power 停 WebGL/RAF/动画，localStorage 记忆选择）。"""

DESIGN_DIRECTIONS += [GZ_MAGAZINE, GZ_SWISS]

# 页码/年份等常量白名单：这些不是业务数字，AI 一定会用
_CONSTANT_NUMBERS = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",  # 月日
    "50", "100",  # 阈值类常见常量
    "2024", "2025", "2026", "2027",
}

# 数字 token 正则：支持千分位、小数、前导 −（U+2212）/ - / +
# (?<![A-Za-z])：不让 "ZPP011" 被切出 "011"（实测第一次生成就踩到）
_NUM_RE = re.compile(r"(?<![A-Za-z])[+\-\u2212]?\d[\d,]*(?:\.\d+)?")

# 完整日期（2026.10.24 / 2026-10-03 / 2026/10/3）不是业务数字，先整段去掉
_DATE_RE = re.compile(r"\d{4}[.\-/]\d{1,2}(?:[.\-/]\d{1,2})?")

# 没年份的月日（"10-31 前补齐" / "10-23"）也不是业务数字。
# ⚠️ 只剥连字符与斜杠两种日期写法，**绝不剥点号**——"26.39" 这种小数会被
# \d{1,2}[.]\d{1,2} 误吞，把真违规（−26.39 被写成 −26.4）放过去，那是护栏的命门。
_MD_RE = re.compile(r"(?<!\d)\d{1,2}[-\/]\d{1,2}(?!\d)")

# "U+2212" 这类 Unicode 码位说明（AI 常在口径说明里写「负号用 U+2212 表示」）
# 会被数字正则从 "U+2212" 里切出 "2212"（前一个字符是 + 不是字母，lookbehind 拦不住），
# 必须整段去掉（第三次实跑就踩到这个坑）
_UNI_ESC_RE = re.compile(r"[Uu]\+[0-9A-Fa-f]{4,6}")

# 行文单位豁免：数字后面紧跟这些单位时，它几乎一定是行文（"48小时内"）而非业务数据。
# 刻意不含 条/个/吨/万/%/元 —— 那些是真数据单位，必须照样核对。
_PROSE_UNITS = ("小时", "分钟", "秒钟", "秒", "天", "周", "页", "版", "期", "次", "年", "月")
_PROSE_UNIT_RE = re.compile(
    r"(?<![A-Za-z])[+\-\u2212]?\d[\d,]*(?:\.\d+)?(?:\s*(?:%s))" % "|".join(_PROSE_UNITS)
)

# 可见文本下限：低于此值说明内容被藏进 <script> 用 JS 注入（v43.259 实测，
# AI 把整份报告塞进单个 script → 总字符 35,438 但可见文本仅 82 → 护栏真空通过）
MIN_VISIBLE_TEXT = 3000
# 中文门（v43.260 实测）：瑞士风一版全文英文（中文仅 363 字 / 占比 18%），
# 数字全对但用户看不懂。12~16 页中文管理报告不可能低于 600 个汉字；
# 汉字占（汉字+英文）比例低于 50% 同样判废。
MIN_CJK_CHARS = 600
MIN_CJK_RATIO = 0.5

# 系统提示词：把「不许自己算数」放到最前，这是全模块的命门
SYSTEM_PROMPT = """你是一位世界级的编辑设计师 + 前端工程师，专做数据驱动的年度/月度报告。

你的任务：根据用户给出的「数据字典」（JSON，唯一数据来源），为一份名为
《ZPP011 生产偏差分析》的中文报告**现场设计并写出一个完整的单文件 HTML**——
横向翻页幻灯片形式，默认 12~16 页。

═══════════ 硬性约束（违反任何一条都算失败）═══════════

【数字纪律 —— 最重要，没有之一】
1. 所有数字必须**原样取自数据字典**。禁止你做任何算术：不许相加、不许相除、
   不许求百分比、不许四舍五入到别的位数。字典里没有的数字，一个字都不许出现。
2. 需要某个比例/合计但字典里没有时：改用字典里已有的数字来描述，
   或者直接不写这个数（写「见明细」「以工作簿为准」都可以）。
3. 金额单位是万元，负数用 −（U+2212，不是 ASCII 连字符）。正=多耗、负=节约。
4. 数字格式（千分位、小数位数）照抄字典里的格式化字符串，不要自己改。
5. **行文、结论、建议里同样不许出现字典没有的数字**。以下都是违规（实测踩过）：
   · 把多行相加（「三条记录合计 −268.84 万」——字典只有各行的数，没有合计）；
   · 求平均或占比（「单行平均 2.38 万」——字典写 23,800 元就原样写 23,800 元）；
   · 做单位换算（23,800 元 ≠ 2.38 万，字典是什么单位就照抄）；
   · 在目标/建议里编数（「收敛至 −300 万以内」——字典里没有这个数）。
   要强调程度时，改用字典里已有的数字描述，或写「见明细」「以工作簿为准」。

【离线约束】
6. 单文件 HTML，**零外链**：不许引用任何 http/https 的 CSS/JS/字体/图片/图标库。
   字体用系统字体栈；图标用内联 SVG 或 Unicode 符号；动效用原生 CSS/JS。
7. 不许用 <img src="http...">、@import、url(https://...)。

【内容纪律】
8. **中文——所有可见文字必须是简体中文**：标题、副标题、栏目标签、表头、
   图例、图表注释、按钮文案、页码指示器、结论与建议，一律中文。
   禁止英文标题与英文标签——「Net Deviation」「Top 5」「Factory Detail」
   「Overage」这类全部不许出现（实测踩过：瑞士风一版中文仅占 18%，用户看不懂）。
   等宽字体（JetBrains Mono 等）只用于渲染数字与编码，不用于英文标语。
   唯一例外：ZPP011、SAP、ERP、A/B、物料编码/订单号等专有名词与代码。
   西式设计语言（网格/字重/色彩）只影响版式，**不影响语言**。
   语气专业、客观、可执行，像给管理层看的月度审核报告。
9. 必须覆盖：封面、总览（头条数字）、口径说明（明细逐行加总 vs 汇总统计）、
   食品厂、饮料厂、车间排名、重点物料、无备注风险、替代料、趋势、结论与建议。
   「替代料」一节必须引用数据字典 causes.substitute 里的真实数字（明细条数 /
   净偏差金额），字典是多少就写多少；本期为 0 条时才可写「本期无替代料」。
10. 必须写清两个口径：① 正=多耗 / 负=节约；② 本报告数字来自「完整偏差明细」
   净偏差金额逐行加总。若数据字典 quality 里 sum_total 与 detail_net 相差很小
   （见 closed 字段），说明明细与汇总已闭合，就按闭合写；否则按「不采用汇总统计
   那个数、采用明细逐行加总」写。
11. 结论必须具体到车间/物料，不许只写「建议加强管理」这类空话。

【交互】
12. 键盘 ← → / 空格 / PageUp PageDown 翻页；ESC 出全页总览；按 B 切换静态模式
    （关动效，适合投影录屏）。
13. 版式自适应窗口，投影不越界；打印友好。

【输出格式】
14. 只输出完整 HTML：从 <!DOCTYPE html> 开始，到 </html> 结束。
    不要 Markdown 代码围栏，不要任何解释文字。
15. **所有报告内容（标题/正文/数字/表格/图表标签）必须直接写在 HTML 标签里**
    （<section>/<div>/<p>/<table>…）。不许把内容或数据字典塞进 <script>、
    用 JS 字符串或模板字面量注入 DOM——那样数字将无法被核对，整份作废。
    <script> 只许写交互逻辑（翻页/键盘/静态模式/总览），其中不许出现任何业务数字。
"""


# ─────────────────────────────────────────────────────────── 工具

def _json_default(o):
    """numpy / pandas 类型转 JSON 安全值。"""
    try:
        import numpy as np
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
    except Exception:
        pass
    return str(o)


def serialize_data(data: dict) -> str:
    """数据字典 → JSON 文本（numpy 安全）。"""
    return json.dumps(data, ensure_ascii=False, indent=1, default=_json_default)


def _norm_num(tok: str) -> str:
    """数字 token 归一化：− → -、去千分位、去前导 +、去小数尾零、去整数前导零。

    保留符号：−593.3 与 +593.3 归一化后不同，正是为了抓住「AI 把符号写反」。
    小数尾零等价：−26.40 与 −26.4 归一化后相同（AI 常把 2 位小数写成 1 位，
    但 −26.39 → −26.4 是**真违规**，归一化救不了它，护栏照样抓）。
    整数前导零等价：页码 "01" 与 "1" 视为同一个数（实测 AI 会写「01 / 12」页码）。
    """
    t = tok.replace("\u2212", "-").replace(",", "")
    sign = "-" if t.startswith("-") else ""
    if t.startswith(("+", "-")):
        t = t[1:]
    if "." in t:
        int_part, frac = t.split(".", 1)
        int_part = int_part.lstrip("0") or "0"
        frac = frac.rstrip("0")
        t = int_part + (("." + frac) if frac else "")
    else:
        t = t.lstrip("0") or "0"
    if t == "0":
        sign = ""      # -0 与 0 视为同一个数
    return sign + t


def _numeric_variants(value: float) -> set:
    """一个数值 → 各种可能的书写形态（整数/1位/2位小数），都算同一个数。"""
    out = set()
    try:
        v = float(value)
    except Exception:
        return out
    for digits in (0, 1, 2):
        s = f"{abs(v):,.{digits}f}".rstrip(".")
        if not s:
            continue
        out.add(_norm_num(("-" if v < 0 else "") + s))
    if v == int(v):
        out.add(_norm_num(str(int(v))))
    return out


def visible_text(html: str) -> str:
    """抽取 HTML 可见文本（去 script/style、去标签连属性、反转义实体、去日期）。

    只取标签之间的文本节点，CSS 里的 1.2fr / font-size:11.6vw 不会被当成业务数字；
    完整日期（2026.10.24 / 2026-10-03）整段去掉，避免把年月日当成越界数字；
    没年份的月日（10-31 / 10/23）同样整段去掉（只剥 - 与 /，不剥 .，免得吞小数）；
    "U+2212" 这类码位说明也整段去掉，避免 "2212" 被切出来误报。
    """
    s = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)   # 连属性一起剥掉
    s = unescape(s)
    s = _DATE_RE.sub(" ", s)
    s = _MD_RE.sub(" ", s)
    s = _UNI_ESC_RE.sub(" ", s)
    return s


def extract_numbers(text: str) -> list:
    """从文本抽出所有数字 token（保留原始形态，供上下文展示）。"""
    return _NUM_RE.findall(text)


def collect_allowed_numbers(data: dict) -> set:
    """白名单：数据字典 JSON 文本里出现过的所有数字 + 常量。

    扫描的是 JSON **文本**，所以格式化字符串里的数字（如 "8,191"、"−357.1"）
    也会被收进来；再对纯数值字段补充其整数/1位/2位小数形态。
    """
    allowed = set(_CONSTANT_NUMBERS)

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _walk(k)
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                _walk(v)
        elif isinstance(obj, bool):
            return
        elif isinstance(obj, (int, float)):
            allowed.update(_numeric_variants(obj))
        elif obj is None:
            return
        else:
            for tok in extract_numbers(str(obj)):
                allowed.add(_norm_num(tok))

    _walk(data)
    return {a for a in allowed if a not in ("", "-", ".", "+")}


def extract_html(raw: str) -> Optional[str]:
    """从模型输出里抠出完整 HTML（容忍 ```html 围栏和前后废话）。"""
    if not raw:
        return None
    s = raw.strip()
    # 去掉 markdown 代码围栏
    s = re.sub(r"(?is)^\s*```(?:html)?\s*", "", s)
    s = re.sub(r"(?is)\s*```\s*$", "", s)
    low = s.lower()
    i = low.find("<!doctype")
    if i < 0:
        i = low.find("<html")
    if i < 0:
        return None
    j = low.rfind("</html>")
    if j < 0:
        return None
    return s[i:j + len("</html>")].strip()


def cjk_stats(text: str) -> tuple:
    """(汉字数, 英文字符数) —— 语言门判定用。"""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    en = sum(len(w) for w in re.findall(r"[A-Za-z][A-Za-z\-/&\.']{2,}", text))
    return cjk, en


def looks_complete(html: str) -> bool:
    """粗校验：像一份完整 HTML（首尾标签齐全、有一定体量、内容真的在标签里、是中文报告）。

    ⚠️ v43.259 新增可见文本下限：实测第 6 次生成 AI 把整份报告（含数据字典）
    塞进单个 <script> 用 JS 注入 DOM —— 总字符 35,438 但可见文本只有 82，
    数字护栏只扫可见文本 → **真空通过**。12~16 页中文报告可见文本不可能低于
    3,000 字符（实测正常生成 13,000~17,000），低于即判定结构不合格。
    ⚠️ v43.260 新增中文门：实测瑞士风一版全文英文（汉字 363、占比 18%），
    数字全对但管理层看不懂——低于 600 汉字或汉字占比低于 50% 判废。
    """
    if not html or len(html) < 20000:   # 12+ 页的报告不可能更小
        return False
    low = html.lower()
    if not low.startswith("<!doctype") and not low.startswith("<html"):
        return False
    if not low.rstrip().endswith("</html>"):
        return False
    if low.count("<section") + low.count("<div") < 20:
        return False
    vt = visible_text(html)
    if len(vt) < MIN_VISIBLE_TEXT:
        return False
    cjk, en = cjk_stats(vt)
    if cjk < MIN_CJK_CHARS:
        return False
    if cjk < MIN_CJK_RATIO * (cjk + en):
        return False
    return True


def verify_numbers(html: str, allowed: set, max_report: int = 40) -> list:
    """数字护栏：返回违规列表（空 = 通过）。

    每条违规 = {"number": 原样token, "context": 前后文}。
    行文数字（"48小时内"这类紧跟时间/序数单位的）不计违规。
    """
    text = visible_text(html)
    # 行文单位豁免：整段替换掉，避免 "48小时" 被当成越界业务数字
    text_for_check = _PROSE_UNIT_RE.sub(" ", text)
    violations = []
    for m in _NUM_RE.finditer(text_for_check):
        tok = m.group(0)
        norm = _norm_num(tok)
        if norm in allowed:
            continue
        # 形如 "1.2.3" 的误匹配直接跳过（不是数）
        if tok.count(".") > 1:
            continue
        ctx = text_for_check[max(0, m.start() - 30):m.end() + 30].replace("\n", " ").strip()
        violations.append({"number": tok, "context": ctx})
        if len(violations) >= max_report:
            break
    return violations


# ─────────────────────────────────────────────────────────── 主入口

def build_prompts(data: dict, design_direction: Optional[str] = None) -> tuple:
    """组 prompt。design_direction 为空则从池里随机挑一个（保证每期不一样）。"""
    direction = design_direction or random.choice(DESIGN_DIRECTIONS)
    period = data.get("period_range") or data.get("period") or ""
    user = (
        f"请为 ZPP011 生产偏差分析报告设计并输出完整 HTML。\n\n"
        f"【本期设计方向】{direction}\n"
        f"（在此方向内自由发挥，但上面 13 条硬性约束优先于你的个人风格偏好）\n\n"
        f"【报告期】{period}\n\n"
    )
    fix_hint = data.get("_fix_hint")
    if fix_hint:
        user += f"【上一次的修正要求 —— 必须遵守】\n{fix_hint}\n\n"
    user += (
        f"【数据字典 —— 唯一数据来源，所有数字必须原样取自这里】\n"
        f"{serialize_data(data)}\n\n"
        f"现在输出完整 HTML（从 <!DOCTYPE html> 到 </html>，不要任何其他文字）："
    )
    return SYSTEM_PROMPT, user


def generate_ai_html(data: dict, client=None, design_direction: Optional[str] = None,
                     max_attempts: int = 2, log_cb=None) -> dict:
    """AI 现场设计并生成报告 HTML。

    返回 {
        "ok": bool,                 # 是否拿到通过数字护栏的 HTML
        "html": str|None,
        "violations": [..],         # 未通过时给出违规数字清单
        "attempts": int,
        "model": str,
        "error": str|None,          # 失败原因
        "fallback_recommended": bool,
    }

    失败时绝不静默：ok=False 时 error/violations 至少有一个有值，
    由调用方决定重试或回退到 Python 渲染（render_html）。
    """
    from core.ai_client import AIClient

    result = {
        "ok": False, "html": None, "violations": [], "attempts": 0,
        "model": "", "error": None, "fallback_recommended": True,
    }
    if client is None:
        try:
            client = AIClient()
        except Exception as e:
            result["error"] = f"AI 客户端初始化失败：{e}"
            return result

    result["model"] = getattr(client, "_agnes_model", "") or ""
    allowed = collect_allowed_numbers(data)

    for attempt in range(1, max_attempts + 1):
        result["attempts"] = attempt
        system, user = build_prompts(data, design_direction)
        try:
            if log_cb:
                log_cb(f"AI 设计第 {attempt}/{max_attempts} 次尝试（{result['model']}）…", "info")
            # 540s：实测 agnes-3.0-flash 生成 3~6 万字符 HTML 需 3~5 分钟，
            # 300s 会被整次掐断（第一次实跑就是 300s 整超时）；v43.260 起 prompt
            # 增至 15 条硬约束 + 归藏双风格详细规范，连续 4 跑有 3 跑在 420s 被
            # 读超时打断（修正机会白丢一轮）→ 提到 540s，宁可慢不可断。
            raw = client.generate_text(system, user, max_tokens=60000, timeout=540)
        except Exception as e:
            result["error"] = f"AI 调用失败：{e}"
            if log_cb:
                log_cb(f"AI 调用失败：{e}", "error")
            continue

        html = extract_html(raw)
        if html is None or not looks_complete(html):
            # 多成因诊断，各自给专属修正提示（v43.259 script 洞 / v43.260 英文版）
            _reasons, _hints = [], []
            if html:
                _vt = visible_text(html)
                _cjk, _en = cjk_stats(_vt)
                if len(_vt) < MIN_VISIBLE_TEXT:
                    _reasons.append(f"可见文本仅 {len(_vt)} 字符（内容被藏进 <script>）")
                    _hints.append("所有内容必须直接写在 HTML 标签里（<section>/<div>/<p>/<table>…），"
                                  "不许塞进 <script> 用 JS 注入 DOM")
                if _cjk < MIN_CJK_CHARS or _cjk < MIN_CJK_RATIO * (_cjk + _en):
                    _ratio = 100.0 * _cjk / max(1, _cjk + _en)
                    _reasons.append(f"中文仅 {_cjk} 字（占比 {_ratio:.0f}%）")
                    _hints.append("所有可见文字必须是简体中文（标题/栏目标签/表头/图例/注释/结论建议），"
                                  "禁止英文标题与英文标签（Net Deviation/Top 5/Factory Detail 一类全不许），"
                                  "等宽字体只渲染数字与编码，西式版式不影响语言")
            if not _reasons:
                _reasons.append("不是完整 HTML（代码围栏包裹或被截断）")
            result["error"] = "AI 输出结构不合格：" + "；".join(_reasons)
            if log_cb:
                log_cb(f"第 {attempt} 次：结构不合格——{'；'.join(_reasons)}", "warning")
            if attempt < max_attempts:
                data = dict(data)
                data["_fix_hint"] = (
                    "上一次输出未通过结构检查（" + "；".join(_reasons) + "）。"
                    "请重新输出完整 HTML：" + "；".join(_hints) + "。"
                )
            continue

        violations = verify_numbers(html, allowed)
        if violations:
            result["html"] = html          # 保留，供「仍要使用」与人工检查
            result["violations"] = violations
            result["error"] = (
                f"数字护栏未通过：发现 {len(violations)} 个字典里不存在的数字"
                f"（AI 可能抄错或自行计算）"
            )
            if log_cb:
                log_cb(f"第 {attempt} 次：数字护栏未通过，{len(violations)} 个越界数字", "warning")
            # 第二次尝试时把违规数字回喂给 AI，让它自己改
            if attempt < max_attempts:
                data = dict(data)
                # 带上上下文片段：光给数字，AI 3000 行 HTML 里根本找不到在哪
                _items = []
                for v in violations[:15]:
                    _ctx = " ".join(v["context"].split())[:46]
                    _items.append(f"{v['number']}（{_ctx}）")
                data["_fix_hint"] = (
                    "上一次生成里有这些数字与数据字典不符，请逐一改正后重新输出完整 HTML："
                    + "；".join(_items)
                    + "。\n\n特别注意：数字必须**按字典原样逐字符抄写**，"
                    "包括小数位数（字典写 −26.39 就必须写 −26.39，不许四舍五入成 −26.4）、"
                    "千分位、正负号（负号用 −）。字典里没有的数字一律不许出现，"
                    "也不许自己相加、相除或求百分比。"
                )
            continue

        result["ok"] = True
        result["html"] = html
        result["error"] = None
        result["fallback_recommended"] = False
        result["violations"] = []
        if log_cb:
            log_cb(f"AI 设计完成：{len(html):,} 字符，数字护栏通过（{attempt} 次尝试）", "info")
        return result

    return result


if __name__ == "__main__":
    # 手工自测：python -m core.guizang_ai <分析结果.xlsx>
    import sys as _sys
    from core.guizang_report import build_report_data

    if len(_sys.argv) < 2:
        print("用法: python -m core.guizang_ai <分析结果.xlsx> [设计方向]")
        raise SystemExit(2)
    _data = build_report_data(_sys.argv[1])
    # 设计方向：支持方向名快捷映射（magazine/swiss → 归藏双风格规范），
    # 也可直接传任意方向文本；不传则从池里随机挑（保证每期不一样）。
    _raw = _sys.argv[2] if len(_sys.argv) > 2 else None
    _GZ_MAP = {
        "magazine": GZ_MAGAZINE, "gz-magazine": GZ_MAGAZINE, "归藏杂志": GZ_MAGAZINE,
        "swiss": GZ_SWISS, "gz-swiss": GZ_SWISS, "归藏瑞士": GZ_SWISS,
    }
    _dir = _GZ_MAP.get((_raw or "").strip().lower(), _raw)
    _t0 = time.time()
    _r = generate_ai_html(_data, design_direction=_dir,
                          log_cb=lambda m, l: print(f"[{l}] {m}"))
    print(f"\n用时 {time.time() - _t0:.1f}s | ok={_r['ok']} | attempts={_r['attempts']} | model={_r['model']}")
    if _r["ok"]:
        _out = _sys.argv[1].rsplit(".", 1)[0] + "_ai.html"
        with open(_out, "w", encoding="utf-8") as f:
            f.write(_r["html"])
        print(f"已写出 {_out}")
    else:
        # 失败也把最后一次的 HTML 落盘，便于人工检查 AI 到底设计了什么、错在哪
        if _r.get("html"):
            _dbg = _sys.argv[1].rsplit(".", 1)[0] + "_ai_last_attempt.html"
            with open(_dbg, "w", encoding="utf-8") as f:
                f.write(_r["html"])
            print(f"（AI 最后版本已落盘供检查：{_dbg}）")
        print("error:", _r["error"])
        for v in _r["violations"][:20]:
            print("  越界数字:", v["number"], "|", v["context"][:60])
        raise SystemExit(1)
