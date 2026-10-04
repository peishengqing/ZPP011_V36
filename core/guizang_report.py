# -*- coding: utf-8 -*-
"""
归藏网页版报告 · 数据构建层
============================

从 ZPP011 分析结果 Excel（含「完整偏差明细」等 sheet）实时计算归藏-Magazine /
归藏-Swiss 两份网页报告所需的全部数字。

口径（与 2026-10-04 人工校验版完全一致，零幻觉）：
- 主口径：      「完整偏差明细」净偏差金额列逐行加总（万 = /1e4）
- 两厂区分：    工厂列 contains('食品') / contains('饮料')
- 备注覆盖率：  明细「备注」列 notna 占比
- 物料 TOP：    按物料名称分组；"负偏差TOP"金额 = 该物料**负偏差行合计**（不抵扣正行），
                条数 = 该物料全部行数；正偏差 TOP 同理取正行合计
- 车间条形宽：  round(|净额| / 最大负额绝对值 * 100)
- 无备注预警：  直接读「无备注预警」sheet（勿用明细 isna 自算，口径不同）
- 原因结构：    读「偏差原因分析」sheet 按备注原因分组；排除「替代料」；
                合并「非正常生产」+「包装材料问题」；净影响 = (多耗+少耗)/1e4；按净影响降序
- 趋势五分类：  读「趋势分析（自然日分组）」sheet 的「趋势」列 value_counts
                （首行说明行需剔除）
- 汇总统计质量页：直接读「汇总统计」sheet 三列合计（总/正/负偏差金额(含税)）

唯一与人工首版不同处：第 02 页"正/负偏差"原写 +102.4/−102.4（无法复现），
现改为净偏差金额列口径（正 = 净>0 行合计，负 = 净<0 行合计）。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

W = 1e4  # 元 -> 万

MINUS = "\u2212"  # − 与原 HTML 一致，使用 Unicode minus

REQUIRED_SHEETS = (
    "完整偏差明细",
    "汇总统计",
    "无备注预警",
    "偏差原因分析",
    "趋势分析（自然日分组）",
)


# ---------------------------------------------------------------- 格式化工具

def wan(x: float, digits: int = 1, signed: bool = False) -> str:
    """金额(元)->万，负数用 Unicode minus。signed=True 时正数带 +。"""
    v = x / W
    s = f"{abs(v):,.{digits}f}"
    if v < 0:
        return f"{MINUS}{s}"
    if signed:
        return f"+{s}"
    return s


def wan_signed(x: float, digits: int = 1) -> str:
    """带符号万（负 − / 正 +）。"""
    return wan(x, digits, signed=True)


def wan2(x: float) -> str:
    """固定 2 位小数带符号万（物料 TOP 用，−4.80 保留尾零）。"""
    return wan(x, 2, signed=True)


def wan_auto(x: float) -> str:
    """2 位小数去尾零（无备注金额用：12.00→12.0、0.88→0.88）。"""
    v = x / W
    s = f"{abs(v):.2f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return (f"{MINUS}{s}" if v < 0 else s)


def wan_tier(x: float) -> str:
    """车间条形金额：常规 1 位；不足 0.05 万的微小值用 2 位（−0.01万）。"""
    return wan_signed(x, 2) if abs(x) < 500 else wan_signed(x, 1)


def int_fmt(n) -> str:
    """17,647 千分位。"""
    return f"{int(n):,}"


def pct(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}"


def bar_width(amount: float, max_amount: float) -> int:
    """条形宽度百分比：|amount| / max_amount * 100，取整，夹在 0.3~100。"""
    if not max_amount:
        return 0
    w = round(abs(amount) / abs(max_amount) * 100)
    return max(1, min(100, w)) if abs(amount) > 0 else 0


def ratio_1(x: float) -> str:
    """保留 1 位小数的倍数（1.6 倍 / 13 倍判断）。"""
    return f"{x:.1f}"


# ---------------------------------------------------------------- sheet 读取

def _read_sheet(xl: pd.ExcelFile, name: str, log_cb=None) -> pd.DataFrame:
    if name not in xl.sheet_names:
        raise ValueError(f"分析结果 Excel 缺少工作表「{name}」，请先在软件内完成分析并导出。")
    df = pd.read_excel(xl, name)
    if log_cb:
        log_cb(f"已读取「{name}」{len(df)} 行")
    return df


def _parse_period(xl: pd.ExcelFile, detail: pd.DataFrame) -> tuple:
    """返回 (period, period_range)，如 ('2026-09', '2026-09-01 — 09-30')。"""
    period, start_s, end_s = None, None, None
    try:
        dates = pd.to_datetime(detail["订单日期"], errors="coerce").dropna()
        if len(dates):
            period = dates.min().strftime("%Y-%m")
            start_s = dates.min().strftime("%Y-%m-%d")
            end_s = dates.max().strftime("%m-%d")
    except Exception:
        pass
    if period is None:
        try:
            head = pd.read_excel(xl, "偏差原因汇总", nrows=1, header=None)
            m = re.search(r"(\d{4}-\d{2})-\d{2}\s*~\s*(\d{4}-\d{2}-\d{2})", str(head.iloc[0, 0]))
            if m:
                period = m.group(1)
                start_s, end_s = m.group(1) + "-01", m.group(2)[5:]
        except Exception:
            pass
    if period is None:
        period = datetime.now().strftime("%Y-%m")
        start_s, end_s = period + "-01", "—"
    return period, f"{start_s} — {end_s}"


# ---------------------------------------------------------------- 主构建函数

def build_report_data(excel_path, log_cb: Optional[Callable[[str], None]] = None) -> dict:
    """读分析结果 Excel，返回两份归藏报告共用的数据 dict。所有字符串已按 HTML 原格式化。"""
    log = log_cb or (lambda msg: None)
    path = Path(str(excel_path))
    if not path.exists():
        raise FileNotFoundError(f"分析结果 Excel 不存在：{path}")

    xl = pd.ExcelFile(path)
    d = _read_sheet(xl, "完整偏差明细", log)
    summary = _read_sheet(xl, "汇总统计", log)
    noremark = _read_sheet(xl, "无备注预警", log)
    causes = _read_sheet(xl, "偏差原因分析", log)
    trend = _read_sheet(xl, "趋势分析（自然日分组）", log)

    for col in ("工厂", "车间", "物料类型", "物料名称", "净偏差金额", "备注"):
        if col not in d.columns:
            raise ValueError(f"「完整偏差明细」缺少必需列「{col}」")

    period, period_range = _parse_period(xl, d)
    net = d["净偏差金额"]

    # ---------------- 全厂 ----------------
    total_rows = len(d)
    total_net = net.sum()
    total_pos = net[net > 0].sum()
    total_neg = net[net < 0].sum()

    food_mask = d["工厂"].astype(str).str.contains("食品", na=False)
    bev_mask = d["工厂"].astype(str).str.contains("饮料", na=False)
    f, b = d[food_mask], d[bev_mask]

    remark_n = int(d["备注"].notna().sum())

    # ---------------- 汇总统计质量页 ----------------
    q_total = summary["总偏差金额(含税)"].sum()
    q_pos = summary["正偏差金额(含税)"].sum()
    q_neg = summary["负偏差金额(含税)"].sum()

    # ---------------- 食品厂 ----------------
    fd = _plant_block(f, digits=1)
    # 车间条形（净升序：负在上/正在下）
    fws = f.groupby("车间")["净偏差金额"].agg(["count", "sum"])
    fws = fws.sort_values("sum")
    max_neg_f = abs(min(0.0, float(fws["sum"].min())))
    food_bars = [
        {
            "name": name,
            "amt": wan_tier(float(row["sum"])),
            "rows": int_fmt(row["count"]),
            "neg": float(row["sum"]) < 0,
            # 视觉分档：正偏差、或负偏差但金额不足 0.1 万的微小车间 → 淡色
            "dim": (float(row["sum"]) >= 0) or (abs(float(row["sum"])) < 1000),
            "width": bar_width(float(row["sum"]), max_neg_f),
        }
        for name, row in fws.iterrows()
    ]
    ws_sorted = fws["sum"].sort_values()
    top2_sum = float(ws_sorted.iloc[0] + ws_sorted.iloc[1])
    # 其余车间合计：显示值口径（读者可用页面条形数字直接加总复核）
    top2_names = set(map(str, ws_sorted.index[:2]))
    rest_sum_disp = sum(round(float(fws.loc[n, "sum"]) / W, 1) for n in fws.index if str(n) not in top2_names)
    pos_ws = [str(n) for n, r in fws.sort_values("sum", ascending=False).iterrows() if r["sum"] > 0]
    fd.update(
        bars=food_bars,
        ws_top_name=str(ws_sorted.index[0]),
        ws_top_amt=wan_signed(ws_sorted.iloc[0]),
        ws_second_name=str(ws_sorted.index[1]),
        ws_second_amt=wan_signed(ws_sorted.iloc[1]),
        ws_top_rows=int_fmt(fws.loc[ws_sorted.index[0], "count"]),
        ws_second_rows=int_fmt(fws.loc[ws_sorted.index[1], "count"]),
        top2_sum=wan_signed(top2_sum),
        top2_share=round(abs(top2_sum) / max(1e-9, abs(float(f["净偏差金额"].sum()))) * 100),
        rest_sum=wan_signed(rest_sum_disp * W),
        rest_ws_n=max(0, len(fws) - 2),
        pos_ws_names="、".join(pos_ws),
        eat_ratio=ratio_1(abs(ws_sorted.iloc[0]) / abs(float(f["净偏差金额"].sum()))),
    )

    # 食品厂物料 TOP（负行合计口径 + 全部行数）
    fd["neg_top"] = _material_top(f, "neg", 5)
    fd["pos_note"] = _pos_note(f, 3)

    # 无备注预警（食品厂）
    fnr = noremark[noremark["工厂"].astype(str).str.contains("食品", na=False)]
    gnr = fnr.groupby("车间").agg(rows=("车间", "count"), net=("偏差金额(含税)", "sum"))
    gnr = gnr.sort_values("rows", ascending=False)
    fd["noremark_total"] = int(len(fnr))
    fd["noremark_rows"] = [
        {"name": str(name), "rows": int(row["rows"]), "amt": wan_auto(float(row["net"])), "amt_raw": float(row["net"])}
        for name, row in gnr.iterrows()
    ]
    fd["dup_rows"] = int((noremark["重复行"].astype(str) == "整行重复").sum()) if "重复行" in noremark.columns else 0
    nr1 = fd["noremark_rows"][0] if fd["noremark_rows"] else {"name": "—", "rows": 0, "amt": "0", "amt_raw": 0.0}
    fd["nr_top_name"], fd["nr_top_rows"], fd["nr_top_amt"] = nr1["name"], int_fmt(nr1["rows"]), nr1["amt"].lstrip("+-")

    # ---------------- 饮料厂 ----------------
    bd = _plant_block(b, digits=2)
    bws = b.groupby("车间")["净偏差金额"].agg(["count", "sum"]).sort_values("sum")
    bev_ws_rows = [
        {
            "name": str(name),
            "rows": int_fmt(row["count"]),
            "amt": wan_signed(float(row["sum"]), 2),
            "neg": float(row["sum"]) < 0,
        }
        for name, row in bws.iterrows()
    ]
    bd["ws_rows"] = bev_ws_rows
    # 标题用 1 位（原文"就亏 6.7 万"），表格用 2 位（原文 −6.72万）
    bd["ws_top"] = dict(bev_ws_rows[0], amt=wan_signed(float(bws["sum"].iloc[0]), 1)) if bev_ws_rows else {"name": "—", "rows": "0", "amt": "0"}
    bd["ws_second"] = dict(bev_ws_rows[1], amt=wan_signed(float(bws["sum"].iloc[1]), 1)) if len(bev_ws_rows) > 1 else bd["ws_top"]
    # "高频且净亏"是否唯一：条数最多且净额为负的车间仅一个
    max_ws_rows = int(bws["count"].max()) if len(bws) else 0
    bd["hf_unique"] = bool(len(bws[(bws["count"] == max_ws_rows) & (bws["sum"] < 0)]) == 1) if len(bws) else False

    # 半成品 TOP4（负行合计）
    bh = b[b["物料类型"].astype(str) == "半成品"]
    bd["half_rows_fmt"] = int_fmt(len(bh))
    bd["half_net"] = wan_signed(float(bh["净偏差金额"].sum()), 2) if len(bh) else "0"
    bd["half_top"] = _material_top(bh, "neg", 4)

    # 饮料厂物料 TOP5 + 汇总（显示值之和，读者可用页面数字复核）
    bd["neg_top"] = _material_top(b, "neg", 5)
    top5_sum_disp = sum(round(abs(float(str(x["amt_raw"]))) / W, 2) for x in bd["neg_top"])
    bd["top5_sum"] = wan_signed(-top5_sum_disp * W, 2)
    bd["top5_share"] = pct(top5_sum_disp / abs(float(b["净偏差金额"].sum()) / W) * 100, 1) if float(b["净偏差金额"].sum()) else "0"

    pgh = bd["neg_top"][0] if bd["neg_top"] else {"name": "—", "rows": 0, "amt": "0", "amt_raw": 0}
    bd["pgh_name"], bd["pgh_rows"], bd["pgh_amt"] = pgh["name"], int_fmt(pgh["rows"]), pgh["amt"]
    bd["pgh_share"] = pct(abs(float(str(pgh["amt_raw"]))) / abs(float(b["净偏差金额"].sum())) * 100, 0) if float(b["净偏差金额"].sum()) else "0"
    top_ws_cnt = max(1, int(bws["count"].iloc[0]))
    per_item = int(abs(float(bws["sum"].iloc[0])) / top_ws_cnt) // 100 * 100  # 取整到百
    bd["ws_top_per_item"] = int_fmt(per_item)

    # 两厂对照比率
    food_net = float(f["净偏差金额"].sum())
    bev_net = float(b["净偏差金额"].sum())
    bev_rows_n = max(1, len(b))
    food_rows_n = max(1, len(f))
    bd["strength"] = int(round((abs(bev_net) / bev_rows_n) / max(1e-9, abs(food_net) / food_rows_n)))
    bd["rows_ratio"] = pct(bev_rows_n / food_rows_n * 100, 1)
    bd["net_ratio"] = pct(abs(bev_net) / max(1e-9, abs(food_net)) * 100, 1)

    # 糖类（饮料负行合计前二，显示值口径 2 位）：sugar_pair = [(清洗名, "−X.XX"), …]
    bcode = _name_code_map(b)
    bsug = b[(b["净偏差金额"] < 0) & b["物料名称"].astype(str).str.contains("糖", na=False)]
    gs = (bsug.groupby("物料名称")["净偏差金额"].sum().sort_values() / W).round(2)
    bd["sugar_sum"] = wan_signed(float(gs.iloc[:2].sum() * W), 2) if len(gs) else "0"
    bd["sugar_pair"] = [(_clean_name(n, bcode.get(n)), wan_signed(v * W, 2)) for n, v in gs.iloc[:2].items()]

    # 食品厂糖类（行动页引用，2 位）
    fcode = _name_code_map(f)
    fsug = f[(f["净偏差金额"] < 0) & f["物料名称"].astype(str).str.contains("糖", na=False)]
    fgs = (fsug.groupby("物料名称")["净偏差金额"].sum().sort_values() / W).round(2)
    fd["sugar_pair"] = [(_clean_name(n, fcode.get(n)), wan_signed(v * W, 2)) for n, v in fgs.iloc[:2].items()]

    # ---------------- 原因结构 ----------------
    cd = causes[causes["备注原因"].astype(str) != "替代料"].copy()
    cd["备注原因"] = cd["备注原因"].replace({"非正常生产": "非正常生产 / 包装材料问题", "包装材料问题": "非正常生产 / 包装材料问题"})
    gc = cd.groupby("备注原因").agg(rows=("备注原因", "count"), over=("多耗", "sum"), less=("少耗", "sum"))
    gc["impact"] = (gc["over"] + gc["less"]) / W
    gc = gc.sort_values("impact", ascending=False)
    cause_rows = [
        {
            "name": str(name),
            "rows": int_fmt(row["rows"]),
            "over": f"{row['over'] / W:.2f}万",
            "impact": wan_signed(float(row["over"] + row["less"]), 2),
            "impact_raw": float(row["over"] + row["less"]),
        }
        for name, row in gc.iterrows()
    ]
    top_cause = cause_rows[0] if cause_rows else {"name": "—", "rows": "0", "over": "0", "impact": "0"}

    # 替代料（数量与金额混列，不计入本页统计；口径提示需引用其多耗/少耗/条数）
    sub = causes[causes["备注原因"].astype(str) == "替代料"]
    if "替代料明细" in xl.sheet_names:
        sub_rows = len(pd.read_excel(xl, "替代料明细"))  # 与原文一致：条数取「替代料明细」页
        log(f"已读取「替代料明细」{sub_rows} 行")
    else:
        sub_rows = len(sub)
    if len(sub):
        substitute = {
            "rows": int_fmt(sub_rows),
            "over": f"{abs(float(sub['多耗'].sum())) / W:,.0f}",
            "less": f"{abs(float(sub['少耗'].sum())) / W:,.0f}",
        }
    else:
        substitute = {"rows": "0", "over": "0", "less": "0"}

    # ---------------- 趋势 ----------------
    tr = trend[trend["趋势"].notna()].copy()
    tc = tr["趋势"].value_counts()

    def _tc(key: str) -> int:
        # 精确匹配优先，再退回前缀匹配
        for k, v in tc.items():
            if str(k).strip() == key:
                return int(v)
        for k, v in tc.items():
            if str(k).strip().startswith(key):
                return int(v)
        return 0

    t_flat = _tc("→")
    t_imp = _tc("↓ 近期改善")
    t_wor = _tc("↑ 近期变差")
    t_imp2 = _tc("↓↓ 持续改善")
    t_wor2 = _tc("↑↑ 持续变差")
    t_total = max(1, len(tr))
    good_sum, bad_sum = t_imp + t_imp2, t_wor + t_wor2

    # ---------------- 汇总 dict ----------------
    data = {
        "period": period,
        "period_range": period_range,
        "gen_date": datetime.now().strftime("%Y.%m.%d"),
        "total": {
            "rows_fmt": int_fmt(total_rows),
            "net": wan(total_net),
            "net_raw": total_net,
            "pos": wan_signed(total_pos),
            "neg": wan_signed(total_neg),
            "food_rows": int_fmt(len(f)),
            "bev_rows": int_fmt(len(b)),
            "food_pct": pct(len(f) / total_rows * 100, 1),
            "bev_pct": pct(len(b) / total_rows * 100, 1),
            "remark_pct": pct(remark_n / total_rows * 100, 1),
            "combo_count": int(f.groupby(["车间", "物料类型"]).ngroups + b.groupby(["车间", "物料类型"]).ngroups),
        },
        "quality": {
            "sum_total": wan(q_total),
            "sum_pos": wan_signed(q_pos),
            "sum_neg": wan_signed(q_neg),
            "sum_calc": wan_signed(q_pos + q_neg),
            "gap": wan(q_total - (q_pos + q_neg)),
            "detail_net": wan(total_net),
        },
        "food": fd,
        "bev": bd,
        "causes": {
            "total_rows": int_fmt(len(causes)),
            "rows": cause_rows,
            "top": top_cause,
            "substitute": substitute,
        },
        "trend": {
            "materials": int_fmt(t_total),
            "flat": int_fmt(t_flat), "flat_pct": pct(t_flat / t_total * 100, 1),
            "imp": int_fmt(t_imp), "imp_pct": pct(t_imp / t_total * 100, 1),
            "wor": int_fmt(t_wor), "wor_pct": pct(t_wor / t_total * 100, 1),
            "imp2": int_fmt(t_imp2), "imp2_pct": pct(t_imp2 / t_total * 100, 1),
            "wor2": int_fmt(t_wor2), "wor2_pct": pct(t_wor2 / t_total * 100, 1),
            "good_sum": int_fmt(good_sum), "good_pct": pct(good_sum / t_total * 100, 1),
            "bad_sum": int_fmt(bad_sum), "bad_pct": pct(bad_sum / t_total * 100, 1),
            "ratio": ratio_1(good_sum / max(1, bad_sum)),
        },
    }
    log("归藏报告数据构建完成")
    return data


# ---------------------------------------------------------------- 子块

def _plant_block(p: pd.DataFrame, digits: int = 1) -> dict:
    """单厂基础 KPI 块（总览页 / 对照页共用）。digits 控制分类构成金额位数：食品 1 位、饮料 2 位。"""
    net = p["净偏差金额"]
    rows_n = len(p)
    remark_n = int(p["备注"].notna().sum())
    by_type = p.groupby("物料类型")["净偏差金额"].agg(["count", "sum"])
    raw = by_type.loc[by_type.index.astype(str).str.contains("原材料|原辅料", na=False)]
    pkg = by_type.loc[by_type.index.astype(str).str.contains("包材|包装材料", na=False)]
    half = by_type.loc[by_type.index.astype(str) == "半成品"]
    return {
        "rows_fmt": int_fmt(rows_n),
        "net": wan_signed(net.sum()),
        "net_raw": float(net.sum()),
        "pos": wan_signed(net[net > 0].sum()),
        "neg": wan_signed(net[net < 0].sum()),
        "remark_pct": f"{remark_n / max(1, rows_n) * 100:.2f}",
        "remark_n": int_fmt(remark_n),
        "ws_count": int(p["车间"].nunique()),
        "raw_rows": int_fmt(raw["count"].sum()) if len(raw) else "0",
        "raw_net": wan_signed(float(raw["sum"].sum()), digits) if len(raw) else "0",
        "pkg_rows": int_fmt(pkg["count"].sum()) if len(pkg) else "0",
        "pkg_net": wan_signed(float(pkg["sum"].sum()), digits) if len(pkg) else "0",
        "half_rows": int_fmt(half["count"].sum()) if len(half) else "0",
        "half_net": wan_signed(float(half["sum"].sum()), 2) if len(half) else "0",
    }


def _clean_name(name, code=None) -> str:
    """清洗物料名称用于显示：剔除物料编码子串、规格括号段与供应商色号尾段。

    与人工首版显示一致：
    - "珠光黄色色油CC10269955L5"→"珠光黄色色油"（编码列是 20000048，
      CC…L5 是供应商色号 → 按大写字母开头+6位以上数字的尾段剔除）
    - "PE白内袋(75x70x2C)"→"PE白内袋"（规格括号段）
    - 保留"华栋番茄味调味料82960A-4"（数字开头，不匹配色号模式）
    分组仍按原始物料名称，金额口径不受影响。
    """
    raw = str(name).strip()
    s = raw
    c = "" if code is None else str(code).strip()
    if c and c.lower() != "nan":
        s = s.replace(c, "").strip()
    s = re.sub(r"[（(][^）)]*[）)]", "", s).strip()
    s = re.sub(r"[A-Z]{2,}\d{6,}[A-Z0-9]*$", "", s).strip()
    return s or raw


def _name_code_map(p: pd.DataFrame) -> pd.Series:
    """物料名称 -> 物料编码 映射（清洗名称用）。"""
    if "物料编码" in p.columns:
        return p.drop_duplicates("物料名称").set_index("物料名称")["物料编码"]
    return pd.Series(dtype=object)


def _material_top(p: pd.DataFrame, side: str, n: int) -> list:
    """物料 TOP：金额 = 负(正)行合计，条数 = 全部行数。amt_raw 为元。name 已清洗。"""
    mask = p["净偏差金额"] < 0 if side == "neg" else p["净偏差金额"] > 0
    rows = p[mask]
    all_rows = p.groupby("物料名称")["净偏差金额"].count()
    codes = _name_code_map(p)
    g = rows.groupby("物料名称")["净偏差金额"].sum().sort_values(ascending=(side == "neg"))
    out = []
    for name, amt in g.iloc[:n].items():
        out.append(
            {
                "name": _clean_name(name, codes.get(name)),
                "rows": int(all_rows.get(name, 0)),
                "neg_rows": int(rows[rows["物料名称"] == name].shape[0]) if side == "neg" else 0,
                "amt": wan2(float(amt)),
                "amt_raw": float(amt),
            }
        )
    return out


def _pos_note(p: pd.DataFrame, n: int) -> str:
    """正偏差 TOP 句子：'物料 +X.XX 万(N条)、…'。"""
    tops = _material_top(p, "pos", n)
    return "、".join(f"{t['name']} {t['amt']} 万({t['rows']}条)" for t in tops)


def report_title(data: dict) -> str:
    return f"ZPP011 生产偏差分析 · 食品厂 / 饮料厂分厂报告 · {data['period']}"


# ---------------------------------------------------------------- 总装

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources" / "guizang"


def render_html(style: str, data: dict) -> str:
    """读 template.html，注入 slides 与标题，返回完整 HTML 字符串。"""
    if style == "swiss":
        from core.guizang_swiss import render_swiss

        slides = render_swiss(data)
    else:
        from core.guizang_magazine import render_magazine

        slides = render_magazine(data)
    tpl_path = RESOURCES_DIR / style / "template.html"
    html = tpl_path.read_text(encoding="utf-8")
    html = html.replace("%%GZ_SLIDES%%", slides)
    html = html.replace("%%TITLE%%", report_title(data))
    if "%%GZ_SLIDES%%" in html or "%%TITLE%%" in html:
        raise RuntimeError("归藏模板占位符替换失败，请检查 template.html 完整性")
    return html


def generate(excel_path, style: str, out_path) -> Path:
    """一键生成：Excel -> 数据 -> HTML 文件。返回输出路径。"""
    data = build_report_data(excel_path)
    out = Path(str(out_path))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(style, data), encoding="utf-8")
    return out
