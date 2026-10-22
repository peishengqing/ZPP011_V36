# -*- coding: utf-8 -*-
"""
云南达利积压分析 v2.0 优化版（基于 v1.9，版面/格式/内容全面优化）

页面骨架（基础 13 页，明细页可按数据量自动扩展）：
   0  封面（标题 / 对比月份 / 数据源 / 生成时间）
   1  积压材料总览（工厂 × 仓库类型，m1 vs m2）
   2  1.1 食品按大类汇总（含 TOP3 速览面板）
   3  1.2 食品积压明细 · 大类/仓库（两层，单页；超 22 行才分页）
   4  1.2 食品积压明细 · 大类/仓库/分类（扁平行 15 行/页，末页 KPI；最多少量续页）
   5  1.3 食品包装材料积压（表格 + 柱图 + 饼图）
   6  1.4 食品原料材料积压（表格 + 柱图 + 饼图）
   7  1.5 食品积压账龄分布（<=90/91-180/181-365/>365 天）
   8  1.6 食品物料积压 TOP20（含不流动标记/报废风险/责任人）
   9  1.7 食品不流动预警清单（>180 天未领用，自动建议）
   10 2.1 饮料按大类汇总（含 TOP3 速览面板）
   11 2.2 饮料积压明细 · 大类/仓库（两层，单页；超 22 行才分页）
   12 2.2 饮料积压明细 · 大类/仓库/分类（三级拼音，可分页）
   13 2.3 饮料包装材料积压（表格 + 柱图 + 饼图）
   14 2.4 饮料原料材料积压（表格 + 柱图 + 饼图）
   15 2.5 饮料积压账龄分布
   16 2.6 饮料物料积压 TOP15
   17 2.7 饮料不流动预警清单
   18 核心结论与建议（数据驱动：TOP 占比 / 涨幅 / 清零与新增）
   注：以上为基础页（19 页），明细页超限时自动续页；食品/饮料缺数据时对应节出占位页
"""
import os
import re
import json
import time
import sys
import math
import traceback
import logging
import calendar
from datetime import date
from typing import List, Optional, Tuple
from dataclasses import dataclass, asdict

import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.chart.data import CategoryChartData

# pypinyin 可选依赖：缺省时自动退化为 Unicode 排序（不影响生成）
try:
    from pypinyin import pinyin, Style
    _HAS_PINYIN = True
except ImportError:
    _HAS_PINYIN = False

# ============================================================
# 日志
# ============================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("zyp")

# ============================================================
# 配色 / 版式常量
# ============================================================
FONT_CN = "微软雅黑"
C_TITLE_BG = RGBColor(0x00, 0x33, 0x66)     # 深蓝标题 #003366
C_TITLE_FG = RGBColor(0xFF, 0xFF, 0xFF)
C_ACCENT = RGBColor(0xE6, 0x7E, 0x22)        # 橙色点缀（封面/强调）
C_HEADER_BG = RGBColor(0x4B, 0xAC, 0xC6)    # 表头青绿（用户主题色 #4BACC6）
C_HEADER_FG = RGBColor(0xFF, 0xFF, 0xFF)
C_BODY_FG = RGBColor(0x22, 0x22, 0x22)
C_SUB_FG = RGBColor(0x66, 0x66, 0x66)
C_FOOT_FG = RGBColor(0x8A, 0x97, 0xA5)       # 页脚浅灰
C_BAND = RGBColor(0xE9, 0xF1, 0xF5)         # 隔行浅灰蓝（用户主题 #E9F1F5）
C_TOTAL_BG = RGBColor(0xD9, 0xED, 0xF3)     # 小计浅青（主题色）
C_GRAND_BG = RGBColor(0x96, 0xBD, 0xC8)     # 总计青（用户主题实测 #96BDC8）
C_CARD_BG = RGBColor(0xF5, 0xF8, 0xFC)      # 卡片浅底
C_CARD_LINE = RGBColor(0xD6, 0xE3, 0xF0)    # 卡片描边
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C_UP = RGBColor(0xC0, 0x39, 0x2B)           # 红：积压增加（恶化）
C_DOWN = RGBColor(0x1E, 0x84, 0x49)         # 绿：积压减少（改善）
C_DARK_BLUE = RGBColor(0x2E, 0x7D, 0x9A)    # 数字/标题深青（主题色）
C_SERIES_OLD = RGBColor(0x9A, 0xCF, 0xDD)   # 柱图：旧月（浅青）
C_SERIES_NEW = RGBColor(0x2E, 0x7D, 0x9A)   # 柱图：新月（深青）

WAN = 1e4
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
FOOTER_TEXT = "云南达利 · 积压材料分析报告（单位：万元）"

FOOD_LABEL = "食品"
BEV_LABEL = "饮料"


# ============================================================
# 拼音排序
# ============================================================
def _pinyin_key(s: str) -> str:
    """拼音排序键；未装 pypinyin 时退化为按字符串排序。"""
    if not s:
        return ""
    if _HAS_PINYIN:
        try:
            return "".join(p[0] for p in pinyin(str(s), style=Style.NORMAL) if p)
        except Exception:
            return str(s)
    return str(s)


# ============================================================
# 配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "积压分析配置_v2.json")
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "云南达利积压分析报告")
APP_VERSION = "v2.0"   # 界面标题 / 产出文件名共用，改版本时只改这一处
# 报表数据目录（默认扫描目录 + 自动补充扫描的候选目录）
# 说明：月份不写死，全部由文件名里的 6 位年月自动识别；这里只登记「报表可能存放的位置」，
#       界面会把所有存在目录合并扫描，因此 6/7/8/9… 月都能列出来滚着选。
DEFAULT_SCAN_DIR = r"H:\26年报表\积压表"
KNOWN_DATA_DIRS = [
    r"H:\26年报表\积压表",
    os.path.join(os.path.expanduser("~"), "Desktop", "积压"),
]


@dataclass
class FileMatchResult:
    f1: Optional[str] = None
    d1: Optional[str] = None
    f2: Optional[str] = None
    d2: Optional[str] = None

    @property
    def matched_count(self) -> int:
        return sum(1 for x in (self.f1, self.d1, self.f2, self.d2) if x)


@dataclass
class AppConfig:
    last_f1: Optional[str] = None
    last_d1: Optional[str] = None
    last_f2: Optional[str] = None
    last_d2: Optional[str] = None
    last_output: Optional[str] = None
    scan_dir: str = DEFAULT_SCAN_DIR

    def save(self, path: str = CONFIG_PATH) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = CONFIG_PATH) -> "AppConfig":
        if not os.path.isfile(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            valid = {k: d[k] for k in d if k in cls.__dataclass_fields__}
            return cls(**valid)
        except Exception as e:
            logger.warning(f"load config fail: {e}")
            return cls()


# ============================================================
# 数据读取
# ============================================================
COL_CANDIDATES = {
    "大类": ["大类", "类别", "品类大类", "材料大类"],
    "分类": ["分类", "品类", "物料分类", "品种"],
    "仓库": ["归属仓库", "仓库", "存储仓库", "库位"],
    "合计积压金额": ["合计积压金额", "积压金额", "合计金额", "合计", "金额", "余额", "总金额"],
    "工厂": ["工厂", "厂家", "生产工厂", "公司"],
}


def _resolve_col(df: pd.DataFrame, key: str) -> Optional[str]:
    for c in COL_CANDIDATES[key]:
        if c in df.columns:
            return c
    return None


def read_inventory_file(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    xl = pd.ExcelFile(path)
    sh = None
    for s in xl.sheet_names:
        if "明细" in s:
            sh = s
            break
    if not sh:
        sh = xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sh)
    # 真实源表列名常带前后空格（如 " 合计积压金额 "），先去空格再匹配别名
    df.columns = [str(c).strip() for c in df.columns]
    mapping = {}
    for k in COL_CANDIDATES:
        c = _resolve_col(df, k)
        if c:
            mapping[c] = k
    # 保住原生 M列 "仓库"（明细表 M列，值=包装/原辅料，物料类型维度）：
    # 它常被 D列"归属仓库"挤掉，但总览页需按 M列真实"仓库"分组，故另存为 '仓库类型'
    raw_wh_series = None
    if "仓库" in df.columns and mapping.get("仓库") != "仓库":
        # 存在字面量名为"仓库"的 M列，且 canonical 仓库 实际来自别的别名(归属仓库等)
        raw_wh_series = df["仓库"].astype(str).fillna("未分类")
    # 重命名前，删掉会与目标 canonical 名冲突的原生列，避免重名
    # （如源同时含 归属仓库 与 仓库，保留物理仓 归属仓库 的值作为 canonical '仓库'=D列）
    for src, tgt in list(mapping.items()):
        if src != tgt and tgt in df.columns:
            df = df.drop(columns=[tgt])
    df = df.rename(columns=mapping)
    # 另存 M列'仓库'为 '仓库类型'，供总览按真实仓库分组使用
    if raw_wh_series is not None:
        df["仓库类型"] = raw_wh_series
    missing = [k for k in ("大类", "分类", "仓库", "合计积压金额") if k not in df.columns]
    if missing:
        raise ValueError(
            f"{os.path.basename(path)} 缺少必需列 {missing}; 实际列: {list(df.columns)}"
        )
    df["合计积压金额"] = pd.to_numeric(df["合计积压金额"], errors="coerce").fillna(0)
    if "工厂" not in df.columns:
        df["工厂"] = FOOD_LABEL
    for c in ("大类", "分类", "仓库", "工厂"):
        df[c] = df[c].astype(str).fillna("未分类")
    return df


def split_food_bev(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """根据'分类'/'大类'/'仓库'(读取自归属仓库/D列)是否含饮料关键词切分。"""
    bev_kw = ("饮料", "茶饮", "凉茶", "果汁", "功能饮料", "植物饮料", "复合饮料")
    mask_bev = df["分类"].str.contains("|".join(bev_kw), na=False) | df["大类"].str.contains("|".join(bev_kw), na=False)
    if "工厂" in df.columns:
        mask_bev = mask_bev | df["工厂"].str.contains(BEV_LABEL, na=False)
    if "仓库" in df.columns:
        mask_bev = mask_bev | df["仓库"].str.contains(BEV_LABEL, na=False)
    food = df[~mask_bev].copy()
    bev = df[mask_bev].copy()
    food["_cat"] = "食品"
    bev["_cat"] = "饮料"
    return food, bev


# ============================================================
# 智能匹配（递归 + 2026MM 精确）
# ============================================================
EXCLUDE_KW = [
    "仓库", "包装", "原料", "辅材", "主辅", "明细",
    "主料", "辅料", "内包装", "外包装", "副本", "改",
    "对照", "备份",
]


def _parse_ym(path: str) -> int:
    """从文件名解析 6 位年月 YYYYMM（如 202607），返回整数 202607。固定格式，识别不到抛 ValueError。"""
    bn = os.path.basename(path or "")
    m = re.search(r"(?<!\d)(20\d{4})(?!\d)", bn)
    if not m:
        raise ValueError(f"未识别到 6 位年月(YYYYMM): {bn}")
    return int(m.group(1))


def parse_month_from_filename(path: str) -> str:
    """从文件名 6 位年月解析 'X月'（如 202607 -> '7月'）。"""
    return f"{_parse_ym(path) % 100}月"


def smart_match_files(directory: str) -> FileMatchResult:
    """扫描目录，按文件名 6 位年月自动分组食品/饮料，取最近两个「实际存在」的月份填充（不受相邻限制）。"""
    result = FileMatchResult()
    if not os.path.isdir(directory):
        logger.warning(f"目录不存在: {directory}")
        return result
    files = []
    for root, _, fs in os.walk(directory):
        for f in fs:
            if f.startswith("~$"):
                continue
            if f.endswith((".xlsx", ".xls")):
                files.append(os.path.join(root, f))
    ym_map = {}
    for fp in files:
        bn = os.path.basename(fp)
        if any(kw in bn for kw in EXCLUDE_KW):
            continue
        try:
            ym = _parse_ym(fp)
        except ValueError:
            continue
        is_food = "食品" in bn and "饮料" not in bn
        is_bev = "饮料" in bn and "食品" not in bn
        if not (is_food or is_bev):
            continue
        d = ym_map.setdefault(ym, {})
        if is_food:
            d.setdefault("food", fp)
        if is_bev:
            d.setdefault("bev", fp)
    if not ym_map:
        logger.warning("智能匹配: 未找到任何含年月的食品/饮料文件")
        return result
    yms = sorted(ym_map.keys())
    m2_ym = yms[-1]                                    # 最新月 = 月2（较新）
    m1_ym = yms[-2] if len(yms) >= 2 else m2_ym - 1     # 次新「实际存在」的月 = 月1（较早）
    d2 = ym_map.get(m2_ym, {})
    result.f2 = d2.get("food")
    result.d2 = d2.get("bev")
    d1 = ym_map.get(m1_ym, {})
    result.f1 = d1.get("food")
    result.d1 = d1.get("bev")
    logger.info(f"智能匹配 {result.matched_count}/4  ←  {directory}  (对比 {m1_ym} vs {m2_ym})")
    return result


def _scan_ym_map(directory: str) -> dict:
    """扫描目录，返回 {YYYYMM: {"food": path, "bev": path}}（含文件名过滤，逻辑同 smart_match_files）。"""
    ym_map = {}
    if not os.path.isdir(directory):
        return ym_map
    files = []
    for root, _, fs in os.walk(directory):
        for f in fs:
            if f.startswith("~$"):
                continue
            if f.endswith((".xlsx", ".xls")):
                files.append(os.path.join(root, f))
    for fp in files:
        bn = os.path.basename(fp)
        if any(kw in bn for kw in EXCLUDE_KW):
            continue
        try:
            ym = _parse_ym(fp)
        except ValueError:
            continue
        is_food = "食品" in bn and "饮料" not in bn
        is_bev = "饮料" in bn and "食品" not in bn
        if not (is_food or is_bev):
            continue
        d = ym_map.setdefault(ym, {})
        if is_food:
            d.setdefault("food", fp)
        if is_bev:
            d.setdefault("bev", fp)
    return ym_map


def scan_month_files_multi(dirs: List[str]) -> dict:
    """多目录合并，返回 {ym: {"food": path, "bev": path}}（同月不同目录按 slot 补齐）。"""
    merged = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for ym, slots in _scan_ym_map(d).items():
            mm = merged.setdefault(ym, {})
            for kind in ("food", "bev"):
                if not mm.get(kind) and slots.get(kind):
                    mm[kind] = slots[kind]
    return merged


def latest_two_months(merged: dict) -> Optional[Tuple[int, int]]:
    """从已合并的扫描结果里取最近两个「实际存在」的月份 (m1_ym, m2_ym)，m2 较新；不足两个返回 None。

    只认扫描到的实际月份，不做相邻假设、不跨年猜测。
    """
    yms = sorted(merged.keys())
    if len(yms) < 2:
        return None
    return yms[-2], yms[-1]


def match_files_for_months(dirs: List[str], m1_ym: int, m2_ym: int) -> FileMatchResult:
    """在多个目录里，为指定月对 (m1_ym, m2_ym) 找齐食品/饮料文件。"""
    result = FileMatchResult()
    merged = scan_month_files_multi(dirs)
    d1 = merged.get(m1_ym, {})
    d2 = merged.get(m2_ym, {})
    result.f1 = d1.get("food")
    result.d1 = d1.get("bev")
    result.f2 = d2.get("food")
    result.d2 = d2.get("bev")
    return result


# ============================================================
# 版式：标题条 / KPI 框 / 表格
# ============================================================
def _set_run(r, text, size=10, bold=False, color=C_BODY_FG, font=FONT_CN):
    r.text = str(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = font
    # 中文字体（DrawingML 字体元素为 a:latin / a:ea / a:cs）
    try:
        from pptx.oxml.ns import qn
        rPr = r._r.get_or_add_rPr()
        for tag in ("a:latin", "a:ea", "a:cs"):
            el = rPr.find(qn(tag))
            if el is None:
                el = rPr.makeelement(qn(tag), {})
                rPr.append(el)
            el.set("typeface", font)
    except Exception:
        pass


def _delta_color(v: float) -> RGBColor:
    """积压语境：增加=红（恶化），减少=绿（改善），持平=灰。"""
    if v > 1e-9:
        return C_UP
    if v < -1e-9:
        return C_DOWN
    return C_SUB_FG


def _delta_mark(v: float) -> str:
    if v > 1e-9:
        return "▲ "
    if v < -1e-9:
        return "▼ "
    return ""


def add_title_bar(slide, title_text: str, page_no: int = 0, page_total: int = 0,
                  show_unit: bool = True) -> None:
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.72))
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_TITLE_BG
    bar.line.fill.background()
    tf = bar.text_frame
    tf.margin_left = Inches(0.35)
    tf.margin_top = Inches(0.08)
    tf.margin_right = Inches(0.3)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    _set_run(r, title_text, size=20, bold=True, color=C_TITLE_FG)

    # 橙色点缀线
    acc = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(0.72), SLIDE_W, Inches(0.035))
    acc.fill.solid()
    acc.fill.fore_color.rgb = C_ACCENT
    acc.line.fill.background()

    # 单位（右上）
    if show_unit:
        ub = slide.shapes.add_textbox(Inches(11.3), Inches(0.18), Inches(1.85), Inches(0.36))
        up = ub.text_frame.paragraphs[0]
        up.alignment = PP_ALIGN.RIGHT
        ur = up.add_run()
        _set_run(ur, "单位：万元", size=10, color=RGBColor(0xBF, 0xD3, 0xE6))

    # 页脚：左=报告名，右=页码（不占 KPI 条空间，互不重叠）
    fy = Inches(7.16)
    fl = slide.shapes.add_textbox(Inches(0.3), fy, Inches(6), Inches(0.3))
    fp = fl.text_frame.paragraphs[0]
    fp.alignment = PP_ALIGN.LEFT
    fr = fp.add_run()
    _set_run(fr, FOOTER_TEXT, size=8, color=C_FOOT_FG)
    if page_total:
        pn = slide.shapes.add_textbox(Inches(11.6), fy, Inches(1.4), Inches(0.3))
        pp = pn.text_frame.paragraphs[0]
        pp.alignment = PP_ALIGN.RIGHT
        pr = pp.add_run()
        _set_run(pr, f"{page_no} / {page_total}", size=9, bold=True, color=C_SUB_FG)


def add_kpi_row(slide, items, top=Inches(6.5), left=Inches(0.3),
                width=Inches(12.7), height=Inches(0.55)):
    """items: [(label, value_text), ...] 或 [(label, value_text, delta), ...]
    delta 为原始数值：>0 红色▲ / <0 绿色▼ / 0 灰色，用于「环比」类指标。"""
    n = max(1, len(items))
    bw = width / n
    for k, item in enumerate(items):
        lbl, val = item[0], item[1]
        delta = item[2] if len(item) > 2 else None
        x = left + bw * k
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(0.06), top,
                                     bw - Inches(0.12), height)
        box.fill.solid()
        box.fill.fore_color.rgb = C_CARD_BG
        box.line.color.rgb = C_CARD_LINE
        box.line.width = Pt(0.75)
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.1)
        tf.margin_right = Inches(0.1)
        tf.margin_top = Inches(0.04)
        tf.margin_bottom = Inches(0.04)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p1 = tf.paragraphs[0]
        p1.alignment = PP_ALIGN.CENTER
        r1 = p1.add_run()
        _set_run(r1, lbl, size=9, color=C_SUB_FG)
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        if delta is not None:
            txt = _delta_mark(delta) + str(val)
            _set_run(r2, txt, size=14, bold=True, color=_delta_color(delta))
        else:
            _set_run(r2, str(val), size=14, bold=True, color=C_DARK_BLUE)


def add_table(
    slide,
    headers: List[str],
    rows: List[List],
    left=Inches(0.3),
    top=Inches(1.0),
    width=Inches(12.7),
    height: Optional[Emu] = None,
    band: bool = True,
    left_cols: Optional[set] = None,
    col_ratios: Optional[List[float]] = None,
    delta_cols: Optional[set] = None,
    warn_cols: Optional[set] = None,
    bottom_limit=Inches(6.4),
    font_size: int = 10,
    row_cap: float = 0.34,
) -> Emu:
    """紧凑表格：显式行高（不拉伸/不溢出）、按列宽比例、数值列右对齐、环比列红绿着色。
    返回实际表格高度。"""
    left_cols = left_cols or set()
    delta_cols = delta_cols or set()
    warn_cols = warn_cols or set()
    nrows = len(rows) + 1
    ncols = len(headers)

    # 行高：表头 0.36"，数据行取「紧凑」与「可容纳」的较小值（统一按英寸计算，避免 EMU/英寸混用）
    hdr_h = 0.36
    EMU_PER_INCH = 914400.0
    if height is not None:
        # 显式指定总高时，按行均分（仍不小于 0.24"）
        total_h = float(height) / EMU_PER_INCH
        row_h = max(0.24, (total_h - hdr_h) / max(1, len(rows)))
        hdr_h = total_h / nrows
    else:
        top_in = float(top) / EMU_PER_INCH
        limit_in = float(bottom_limit) / EMU_PER_INCH
        avail = max(0.6, limit_in - top_in - hdr_h)
        row_h = min(row_cap, avail / max(1, len(rows)))
    total_h = hdr_h + row_h * len(rows)

    tbl_shape = slide.shapes.add_table(nrows, ncols, left, top, width, Emu(int(Inches(total_h))))
    tbl = tbl_shape.table
    # 列宽按比例
    if col_ratios and len(col_ratios) == ncols:
        s = sum(col_ratios)
        for j in range(ncols):
            tbl.columns[j].width = Emu(int(width * col_ratios[j] / s))
    else:
        for j in range(ncols):
            tbl.columns[j].width = Emu(int(width / ncols))
    # 行高
    for i in range(nrows):
        tbl.rows[i].height = Emu(int(Inches(hdr_h if i == 0 else row_h)))

    num_cols = {j for j in range(ncols) if j not in left_cols}

    # 表头
    for j, h in enumerate(headers):
        c = tbl.cell(0, j)
        c.fill.solid()
        c.fill.fore_color.rgb = C_HEADER_BG
        c.text = ""
        tf = c.text_frame
        tf.margin_left = Inches(0.06)
        tf.margin_right = Inches(0.06)
        tf.margin_top = Inches(0.02)
        tf.margin_bottom = Inches(0.02)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        _set_run(r, h, size=10.5, bold=True, color=C_HEADER_FG)

    # 数据
    for i, row in enumerate(rows, start=1):
        is_total = isinstance(row, tuple) and len(row) >= 2 and row[1] is True
        is_subtotal = isinstance(row, tuple) and len(row) >= 2 and row[1] == "sub"
        vals = row[0] if isinstance(row, tuple) else row
        for j, v in enumerate(vals):
            c = tbl.cell(i, j)
            c.text = ""
            tf = c.text_frame
            tf.margin_left = Inches(0.06)
            tf.margin_right = Inches(0.06)
            tf.margin_top = Inches(0.01)
            tf.margin_bottom = Inches(0.01)
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            if is_total:
                c.fill.solid()
                c.fill.fore_color.rgb = C_GRAND_BG
            elif is_subtotal:
                c.fill.solid()
                c.fill.fore_color.rgb = C_TOTAL_BG
            elif band and i % 2 == 0:
                c.fill.solid()
                c.fill.fore_color.rgb = C_BAND
            else:
                c.fill.solid()
                c.fill.fore_color.rgb = C_WHITE
            p = tf.paragraphs[0]
            txt = str(v)
            if j in left_cols:
                p.alignment = PP_ALIGN.LEFT
            elif j in num_cols:
                p.alignment = PP_ALIGN.RIGHT
            else:
                p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            if is_total or is_subtotal:
                _set_run(r, txt, size=font_size, bold=True, color=C_BODY_FG)
            elif j in delta_cols:
                color = C_UP if txt.startswith("+") else (C_DOWN if txt.startswith("-") else C_SUB_FG)
                _set_run(r, txt, size=font_size, color=color)
            elif j in warn_cols:
                if txt and txt != "—":
                    _set_run(r, txt, size=font_size, bold=True, color=C_UP)
                else:
                    _set_run(r, txt, size=font_size, color=C_SUB_FG)
            else:
                _set_run(r, txt, size=font_size, color=C_BODY_FG)
    _table_borders(tbl, nrows, ncols)
    return tbl


def _table_borders(tbl, nrows: int, ncols: int, color: str = "4BACC6", width_pt: float = 0.75) -> None:
    """给每个单元格写横向底边框（a:lnB）作为分割线。
    - 边框贴在表格真实网格线上，不会切到文字（替代之前"独立线条"的方案）。
    - 只写单元格属性、不改表格样式（tableStyleId 保持默认）→ 文件可正常打开。
    - python-pptx 无表格边框 API，直接写 tcPr/a:lnB XML（须插在 solidFill 之前）。"""
    from pptx.oxml.ns import qn

    def _add_lnB(cell):
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        for old in tcPr.findall(qn("a:lnB")):
            tcPr.remove(old)
        ln = tcPr.makeelement(qn("a:lnB"), {"w": str(int(width_pt * 12700)), "cap": "flat"})
        sf = ln.makeelement(qn("a:solidFill"), {})
        clr = sf.makeelement(qn("a:srgbClr"), {"val": color})
        sf.append(clr)
        ln.append(sf)
        fill = tcPr.find(qn("a:solidFill"))
        if fill is not None:
            fill.addprevious(ln)
        else:
            tcPr.append(ln)

    for i in range(nrows):
        for j in range(ncols):
            _add_lnB(tbl.cell(i, j))


# ============================================================
# 图表
# ============================================================
def _style_chart(chart, title: Optional[str], tick_size: int = 9):
    """统一的图表样式：标题字号、轴/图例字号、网格线。"""
    if title:
        chart.has_title = True
        chart.chart_title.text_frame.text = title
        try:
            for p in chart.chart_title.text_frame.paragraphs:
                for r in p.runs:
                    _set_run(r, r.text, size=12, bold=True, color=C_DARK_BLUE)
        except Exception:
            pass
    else:
        chart.has_title = False
    chart.has_legend = True
    chart.legend.include_in_layout = False
    try:
        chart.legend.font.size = Pt(tick_size)
    except Exception:
        pass
    try:
        for ax in (chart.category_axis, chart.value_axis):
            ax.tick_labels.font.size = Pt(tick_size)
            ax.has_major_gridlines = ax is not chart.category_axis
            if ax.has_major_gridlines:
                ax.major_gridlines.format.line.color.rgb = RGBColor(0xD8, 0xDE, 0xE6)
                ax.major_gridlines.format.line.width = Pt(0.5)
    except Exception:
        pass


def _topn_with_other(cats, vals, topn: int = 4):
    """前 topn 名 + 「其他」合并（仅超限才合并）；不超限时保持调用方给定的原始顺序。"""
    if len(cats) <= topn:
        return list(cats), [float(v) for v in vals]
    keep = set(sorted(range(len(cats)), key=lambda i: -float(vals[i]))[:topn])
    keep_in_order = [i for i in range(len(cats)) if i in keep]
    rest = [i for i in range(len(cats)) if i not in keep]
    return ([cats[i] for i in keep_in_order] + ["其他"],
            [float(vals[i]) for i in keep_in_order] + [sum(float(vals[i]) for i in rest)])


def _pie_series(cats, vals):
    """饼图口径：保留 ≥5% 的大扇区（最多 4 个）+「其他」；防止小扇区标签互相压盖。
    只 1-2 个扇区时不合并；全部 <5% 时退化为 top3 + 其他。"""
    order = sorted(range(len(cats)), key=lambda i: float(vals[i]), reverse=True)
    live = [i for i in order if float(vals[i]) > 1e-9]
    total = sum(float(vals[i]) for i in live) or 1.0
    if len(live) <= 2:
        keep, rest = live, []
    else:
        keep = [i for i in live if float(vals[i]) / total >= 0.05][:4]
        if not keep:
            keep = live[:3]
        rest = [i for i in live if i not in keep]
    out_c = [cats[i] for i in keep]
    out_v = [float(vals[i]) for i in keep]
    if rest:
        out_c.append("其他")
        out_v.append(sum(float(vals[i]) for i in rest))
    return out_c, out_v


def add_bar_chart(
    slide,
    categories: List[str],
    s1_vals: List[float],
    s2_vals: List[float],
    s1_name: str = "旧月",
    s2_name: str = "新月",
    left=Inches(7.5),
    top=Inches(1.0),
    width=Inches(5.5),
    height=Inches(2.8),
    title: Optional[str] = None,
    topn: int = 6,
) -> None:
    # 两个系列用同一分组口径：按较新月取 topn，旧月对齐
    cats_f, _ = _topn_with_other(categories, s2_vals, topn)
    if not cats_f:
        return
    idx = {c: i for i, c in enumerate(categories)}
    def _reorder(vals):
        out = [0.0] * len(cats_f)
        for i, c in enumerate(cats_f):
            if c == "其他":
                out[i] = sum(vals[idx[cc]] for cc in categories if cc not in cats_f[:-1])
            else:
                out[i] = vals[idx[c]]
        return out
    cd = CategoryChartData()
    cd.categories = cats_f
    cd.add_series(s1_name, _reorder(s1_vals))
    cd.add_series(s2_name, _reorder(s2_vals))
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, left, top, width, height, cd)
    chart = gf.chart
    _style_chart(chart, title)
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    plot = chart.plots[0]
    plot.has_data_labels = False
    try:
        plot.gap_width = 80
    except Exception:
        pass
    plot.series[0].format.fill.solid()
    plot.series[0].format.fill.fore_color.rgb = C_SERIES_OLD
    plot.series[1].format.fill.solid()
    plot.series[1].format.fill.fore_color.rgb = C_SERIES_NEW


def add_pie_chart(
    slide,
    categories: List[str],
    vals: List[float],
    left=Inches(7.5),
    top=Inches(4.0),
    width=Inches(5.5),
    height=Inches(2.5),
    title: Optional[str] = None,
) -> None:
    cats, pv = _pie_series(categories, vals)
    if not cats or all(v <= 0 for v in pv):
        return
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("占比", [float(v) for v in pv])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.PIE, left, top, width, height, cd)
    chart = gf.chart
    _style_chart(chart, title)
    chart.legend.position = XL_LEGEND_POSITION.RIGHT
    plot = chart.plots[0]
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.show_percentage = True
    dl.show_category_name = False
    dl.show_value = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    try:
        dl.font.size = Pt(9)
        dl.font.bold = True
        dl.font.color.rgb = C_BODY_FG
    except Exception:
        pass


# ============================================================
# 计算 helpers
# ============================================================
def _to_wan(x: float) -> str:
    w = float(x) / WAN
    if abs(w) < 0.005:      # 归一 -0.00 / 0.00 浮点噪声
        w = 0.0
    return f"{w:,.2f}"


def _pct(a: float, b: float) -> str:
    if b == 0:
        return "新增" if a != 0 else "—"
    p = (a - b) / b * 100
    if abs(p) < 0.005:      # 归一浮点噪声：-0.00% / +0.00% → 0.00%（灰色，不误导红绿）
        return "0.00%"
    return f"{p:+.2f}%"


def _sum_wan(df: pd.DataFrame, key: str = "合计积压金额") -> float:
    return float(df[key].sum())


# ============================================================
# 页面函数
# ============================================================
def _slide(prs) -> object:
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_cover_slide(prs, month1: str, month2: str, src_files: List[str], page_total: int = 0) -> None:
    """封面：深蓝满版 + 橙色点缀 + 数据源/生成时间。"""
    slide = _slide(prs)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = C_TITLE_BG
    bg.line.fill.background()
    # 左侧橙色竖条
    stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(2.1),
                                    Inches(0.09), Inches(2.6))
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = C_ACCENT
    stripe.line.fill.background()

    tb = slide.shapes.add_textbox(Inches(1.3), Inches(2.0), Inches(10.8), Inches(2.8))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    _set_run(r, "云南达利 · 积压材料分析报告", size=40, bold=True, color=C_WHITE)
    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    _set_run(r2, f"食品 & 饮料  |  {month1} vs {month2}  月度对比", size=18,
             color=RGBColor(0x9F, 0xC1, 0xE0))
    p3 = tf.add_paragraph()
    p3.space_before = Pt(10)
    r3 = p3.add_run()
    _set_run(r3, "按 大类 / 仓库 / 分类 三级透视，含环比变动、占比与处置建议", size=12,
             color=RGBColor(0x7F, 0x9B, 0xBB))

    # 底部信息区
    infos = [f"对比月份：{month1} → {month2}",
             f"数据源：{'；'.join(os.path.basename(s) for s in src_files if s) or '未指定'}"]
    tb2 = slide.shapes.add_textbox(Inches(1.3), Inches(5.3), Inches(10.8), Inches(1.4))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    for i, info in enumerate(infos):
        pi = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
        ri = pi.add_run()
        _set_run(ri, info, size=11, color=RGBColor(0x9F, 0xB8, 0xD0))
    p3 = tf2.add_paragraph()
    p3.space_before = Pt(8)
    r3 = p3.add_run()
    _set_run(r3, f"单位：万元    生成时间：{time.strftime('%Y-%m-%d %H:%M')}    {APP_VERSION}",
             size=10, color=RGBColor(0x7F, 0x9B, 0xBB))


# ---- 1. 总览 ----
def add_overview_slide(prs, m1_df: pd.DataFrame, m2_df: pd.DataFrame,
                       month1: str, month2: str, page_no: int, page_total: int):
    slide = _slide(prs)
    add_title_bar(slide, f"积压材料总览（{month1} vs {month2}）", page_no, page_total)

    # 按"工厂 × 仓库类型(M列原生'仓库'，值=包装/原辅料)"汇总；缺省回退 D列'仓库'(归属仓库)
    def wh_col(df: pd.DataFrame) -> str:
        return "仓库类型" if "仓库类型" in df.columns else "仓库"

    f1, b1 = split_food_bev(m1_df)
    f2, b2 = split_food_bev(m2_df)

    rows = []
    leaf_delta = []   # (label, cat, delta) 明细项，供要点提示
    for label, d1, d2 in (("食品", f1, f2), ("饮料", b1, b2)):
        d1 = d1.copy()
        d2 = d2.copy()
        c1, c2 = wh_col(d1), wh_col(d2)
        types = sorted(set(d1[c1].unique()) | set(d2[c2].unique()))
        for cat in types:
            v1 = d1.loc[d1[c1] == cat, "合计积压金额"].sum()
            v2 = d2.loc[d2[c2] == cat, "合计积压金额"].sum()
            if v1 == 0 and v2 == 0:
                continue
            leaf_delta.append((label, cat, float(v2 - v1)))
            rows.append([label, cat, _to_wan(v1), _to_wan(v2), _to_wan(v2 - v1), _pct(v2, v1)])
        sub1 = d1["合计积压金额"].sum()
        sub2 = d2["合计积压金额"].sum()
        rows.append(([f"{label} 小计", "", _to_wan(sub1), _to_wan(sub2),
                      _to_wan(sub2 - sub1), _pct(sub2, sub1)], "sub"))

    grand1 = m1_df["合计积压金额"].sum()
    grand2 = m2_df["合计积压金额"].sum()
    rows.append((["合计", "", _to_wan(grand1), _to_wan(grand2),
                  _to_wan(grand2 - grand1), _pct(grand2, grand1)], True))

    headers = ["工厂", "仓库", f"{month1}（万）", f"{month2}（万）", "环比增长（万）", "环比增长率"]
    add_table(slide, headers, rows, top=Inches(1.05),
              col_ratios=[1.0, 1.4, 1.1, 1.1, 1.2, 1.1],
              left_cols={0, 1}, delta_cols={4, 5}, bottom_limit=Inches(5.5))

    # 要点提示（数据驱动，填补下方空间）
    fdiff = float(f2["合计积压金额"].sum() - f1["合计积压金额"].sum())
    bdiff = float(b2["合计积压金额"].sum() - b1["合计积压金额"].sum())
    notes = [
        f"食品积压 {fdiff / WAN:+,.2f} 万（{'上升' if fdiff > 0 else '下降' if fdiff < 0 else '持平'}），"
        f"饮料积压 {bdiff / WAN:+,.2f} 万（{'上升' if bdiff > 0 else '下降' if bdiff < 0 else '持平'}）",
    ]
    if leaf_delta:
        lab, cat, dv = max(leaf_delta, key=lambda x: abs(x[2]))
        if abs(dv) > 1e-9:
            notes.append(f"波动最大项：{lab}·{cat}  {dv / WAN:+,.2f} 万（{'增加' if dv > 0 else '减少'}）")
    nb = slide.shapes.add_textbox(Inches(0.4), Inches(5.62), Inches(12.5), Inches(0.8))
    tfn = nb.text_frame
    tfn.word_wrap = True
    for i, nt in enumerate(notes):
        pi = tfn.paragraphs[0] if i == 0 else tfn.add_paragraph()
        ri = pi.add_run()
        _set_run(ri, "◆ " + nt, size=11, color=C_SUB_FG, bold=(i == 0))

    add_kpi_row(slide, [
        (f"{month2} 积压总额", f"{_to_wan(grand2)} 万"),
        ("环比变动", f"{abs(grand2 - grand1) / WAN:,.2f} 万", grand2 - grand1),
        ("环比增长率", _pct(grand2, grand1).strip("+-"), grand2 - grand1),
    ])


# ---- 1.1 / 2.1 大类汇总（通用：左侧表格 + 右侧 TOP 面板，可分页）----
def _class_summary_rows(m1_df, m2_df, factory: str):
    """返回 (rows, t1, t2, g1, g2)：大类取两月并集、按较新月金额降序；rows 不含合计行。"""
    if factory == FOOD_LABEL:
        d1, _ = split_food_bev(m1_df)
        d2, _ = split_food_bev(m2_df)
    else:
        _, d1 = split_food_bev(m1_df)
        _, d2 = split_food_bev(m2_df)
    g1 = d1.groupby("大类")["合计积压金额"].sum()
    g2 = d2.groupby("大类")["合计积压金额"].sum()
    cats = sorted(set(g1.index) | set(g2.index),
                  key=lambda c: (float(g2.get(c, 0)), float(g1.get(c, 0))), reverse=True)
    rows = []
    for k in cats:
        v1 = float(g1.get(k, 0))
        v2 = float(g2.get(k, 0))
        share = v2 / g2.sum() * 100 if g2.sum() else 0.0
        rows.append([k, _to_wan(v1), _to_wan(v2), _to_wan(v2 - v1), _pct(v2, v1), f"{share:.2f}%"])
    t1 = float(g1.sum())
    t2 = float(g2.sum())
    return rows, t1, t2, g1, g2


def _paginate_simple(rows, max_rows):
    """无分组结构时按固定行数切页；空表返回一个空页（占位用）。"""
    return [rows[i:i + max_rows] for i in range(0, len(rows), max_rows)] or [[]]


def _paginate_tail(rows, page_cap: int = 15, last_cap: int = 16):
    """扁平行明细分页：中间页 page_cap 行（无 KPI，可延伸到 7.05"），
    末页 ≤ last_cap 行（带 KPI，表底 ≤ 6.4"）；取最少页数。空表返回一个空页。"""
    n = len(rows)
    if n == 0:
        return [[]]
    if n <= last_cap:
        return [rows]
    k = (n - last_cap + page_cap - 1) // page_cap + 1
    pages = [rows[i * page_cap:(i + 1) * page_cap] for i in range(k - 1)]
    pages.append(rows[(k - 1) * page_cap:])
    return pages


def _info_card(slide, x, y, w, h, title: str, lines, size: int = 10) -> None:
    """浅色信息卡：标题 + 若干着色文本行。lines 元素: (text, color) 或 (text, color, bold)。"""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = C_CARD_BG
    card.line.color.rgb = C_CARD_LINE
    card.line.width = Pt(0.75)
    tb = slide.shapes.add_textbox(x + Inches(0.18), y + Inches(0.12), w - Inches(0.36), h - Inches(0.24))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    _set_run(r, title, size=12, bold=True, color=C_DARK_BLUE)
    for item in lines:
        txt, color = item[0], item[1]
        bold = item[2] if len(item) > 2 else color in (C_UP, C_DOWN)
        pi = tf.add_paragraph()
        pi.space_before = Pt(5)
        ri = pi.add_run()
        _set_run(ri, txt, size=size, color=color, bold=bold)


def _add_top_panel(slide, g1, g2, month2: str) -> None:
    """大类汇总页右侧面板：TOP 大类 + 环比涨幅/降幅 TOP。"""
    px, pw = Inches(8.75), Inches(4.25)
    cats_all = sorted(set(g1.index) | set(g2.index),
                      key=lambda c: (float(g2.get(c, 0)), float(g1.get(c, 0))), reverse=True)
    tot2 = float(g2.sum())
    top3 = [(c, float(g2.get(c, 0))) for c in cats_all if float(g2.get(c, 0)) > 0][:3]
    lines = []
    if top3:
        for i, (c, v) in enumerate(top3, 1):
            share = v / tot2 * 100 if tot2 else 0.0
            lines.append((f"TOP{i}　{c}　{v / WAN:,.2f} 万（{share:.1f}%）", C_BODY_FG))
    else:
        lines.append(("本月无大类积压数据", C_SUB_FG))
    _info_card(slide, px, Inches(1.05), pw, Inches(1.85), f"{month2} TOP 大类", lines)

    deltas = [(c, float(g2.get(c, 0)) - float(g1.get(c, 0))) for c in cats_all]
    up = sorted([x for x in deltas if x[1] > 1e-9], key=lambda x: -x[1])
    dn = sorted([x for x in deltas if x[1] < -1e-9], key=lambda x: x[1])
    lines2 = [("环比涨幅 TOP", C_SUB_FG)]
    if up:
        c, dv = up[0]
        lines2.append((f"▲ {c}　+{dv / WAN:,.2f} 万（{_pct(float(g2.get(c, 0)), float(g1.get(c, 0)))}）", C_UP))
    else:
        lines2.append(("本月无上升大类", C_SUB_FG))
    lines2.append(("　", C_SUB_FG))
    lines2.append(("环比降幅 TOP", C_SUB_FG))
    if dn:
        c, dv = dn[0]
        lines2.append((f"▼ {c}　{dv / WAN:,.2f} 万（{_pct(float(g2.get(c, 0)), float(g1.get(c, 0)))}）", C_DOWN))
    else:
        lines2.append(("本月无下降大类", C_SUB_FG))
    _info_card(slide, px, Inches(3.05), pw, Inches(2.0), "环比变动", lines2)


def add_class_summary_pages(prs, pages, t1, t2, g1, g2, month1, month2, page_no, page_total,
                            chapter: str, factory: str):
    """大类汇总页（可多页）：首页带 TOP 面板，末页带合计行 + KPI 条。"""
    headers = ["大类", f"{month1}（万）", f"{month2}（万）", "环比增长（万）", "环比增长率", f"{month2}占比"]
    n = len(pages)
    for pi, pg in enumerate(pages):
        slide = _slide(prs)
        title = f"{chapter} {factory}按大类汇总（{month1} vs {month2}）"
        if pi > 0:
            title += f"（续{pi + 1}）"
        add_title_bar(slide, title, page_no + pi, page_total)
        pg_rows = [list(r) for r in pg]
        if pi == n - 1:
            _tot_pct = "100.00%" if t2 > 0 else "—"
            pg_rows.append((["合计", _to_wan(t1), _to_wan(t2), _to_wan(t2 - t1),
                             _pct(t2, t1), _tot_pct], True))
        add_table(slide, headers, pg_rows, left=Inches(0.3), width=Inches(8.15),
                  col_ratios=[1.6, 1.0, 1.0, 1.15, 1.1, 1.0],
                  left_cols={0}, delta_cols={3, 4}, bottom_limit=Inches(6.4))
        if pi == 0 and n == 1:
            _add_top_panel(slide, g1, g2, month2)
        if pi == n - 1:
            add_kpi_row(slide, [
                (f"{factory}总额", f"{_to_wan(t2)} 万"),
                ("环比变动", f"{abs(t2 - t1) / WAN:,.2f} 万", t2 - t1),
                ("环比增长率", _pct(t2, t1).strip("+-"), t2 - t1),
            ])


def add_food_class_summary(prs, m1_df, m2_df, month1, month2, slide_num, total):
    """兼容旧接口：转通用大类汇总（食品）。"""
    rows, t1, t2, g1, g2 = _class_summary_rows(m1_df, m2_df, FOOD_LABEL)
    add_class_summary_pages(prs, _paginate_simple(rows, MAX_ROWS_PER_PAGE),
                            t1, t2, g1, g2, month1, month2, slide_num, total,
                            "1.1", FOOD_LABEL)


# ---- 1.2 / 2.2 三级缩进透视（分页）----
# 单页放不下时分页；明细表行高按渲染引擎取 ~0.34-0.41"，12 行 + 表头不撞 KPI 条
MAX_ROWS_PER_PAGE = 12


def _build_class_warehouse_rows(m1_df, m2_df, month1, month2, factory, flat: bool = False):
    """返回 (rows, t1, t2)：大类→仓库→分类 明细。
    flat=False：大类/仓库小计行（黄底）+ 分类缩进行，页数多。
    flat=True：仅分类明细行（大类/仓库名重复，无小计行），配合并单元格单页/双页展示。"""
    if factory == FOOD_LABEL:
        f1, _ = split_food_bev(m1_df)
        f2, _ = split_food_bev(m2_df)
    else:
        _, f1 = split_food_bev(m1_df)
        _, f2 = split_food_bev(m2_df)
    # 优先用 M列"仓库类型"(包装/原辅料)，与 P1 总览和范表一致；缺省回退 D列"仓库"
    wh_key = "仓库类型" if "仓库类型" in f1.columns else "仓库"
    g1 = f1.groupby(["大类", wh_key, "分类"])["合计积压金额"].sum()
    g2 = f2.groupby(["大类", wh_key, "分类"])["合计积压金额"].sum()
    all_keys = sorted(set(g1.keys()) | set(g2.keys()), key=_pinyin_key)
    # 大类按本月(month2)积压金额降序
    class_total_m2 = g2.groupby(level=0).sum()
    class_order = sorted({k[0] for k in all_keys},
                         key=lambda c: float(class_total_m2.get(c, 0)),
                         reverse=True)
    rows = []
    for cls in class_order:
        cls_keys = [k for k in all_keys if k[0] == cls]
        wh_order = sorted({k[1] for k in cls_keys}, key=_pinyin_key)
        # 先算每仓库的明细与小计
        wh_data = []
        cls_v1 = 0.0; cls_v2 = 0.0
        for wh in wh_order:
            wh_keys = [k for k in cls_keys if k[1] == wh]
            wh_v1 = 0.0; wh_v2 = 0.0
            leaves = []
            for k in sorted(wh_keys, key=_pinyin_key):
                v1 = float(g1.get(k, 0)); v2 = float(g2.get(k, 0))
                if v1 == 0 and v2 == 0:
                    continue
                leaves.append((k[2], v1, v2))
                wh_v1 += v1; wh_v2 += v2
            if wh_v1 or wh_v2:
                wh_data.append((wh, wh_v1, wh_v2, leaves))
                cls_v1 += wh_v1; cls_v2 += wh_v2
        if not (cls_v1 or cls_v2):
            continue
        if flat:
            # 扁平行：大类/仓库名在每行重复（后续纵向合并单元格），无小计行
            for wh, wh_v1, wh_v2, leaves in wh_data:
                for cat, v1, v2 in leaves:
                    rows.append([cls, wh, cat,
                                 _to_wan(v1), _to_wan(v2),
                                 _to_wan(v2 - v1), _pct(v2, v1)])
        else:
            # 大类小计置顶
            rows.append(([cls, "", "",
                          _to_wan(cls_v1), _to_wan(cls_v2),
                          _to_wan(cls_v2 - cls_v1), _pct(cls_v2, cls_v1)], "sub"))
            # 仓库小计 → 分类明细
            for wh, wh_v1, wh_v2, leaves in wh_data:
                rows.append((["", "　" + wh, "",
                              _to_wan(wh_v1), _to_wan(wh_v2),
                              _to_wan(wh_v2 - wh_v1), _pct(wh_v2, wh_v1)], "sub"))
                for cat, v1, v2 in leaves:
                    rows.append(["", "", "　　" + cat,
                                 _to_wan(v1), _to_wan(v2),
                                 _to_wan(v2 - v1), _pct(v2, v1)])
    t1 = float(g1.sum()); t2 = float(g2.sum())
    rows.append((["总计" if flat else "", "", "总计" if not flat else "",
                  _to_wan(t1), _to_wan(t2), _to_wan(t2 - t1), _pct(t2, t1)], True))
    return rows, t1, t2


def _build_class_warehouse_rows_2level(m1_df, m2_df, month1, month2, factory, flat: bool = False):
    """返回 (rows, t1, t2)：大类→仓库 两级明细。
    flat=False：大类行=小计（黄底），仓库行=普通明细（缩进），末行总计。
    flat=True：每行重复大类名（无小计行），行数减半，供单页密集展示。"""
    if factory == FOOD_LABEL:
        f1, _ = split_food_bev(m1_df)
        f2, _ = split_food_bev(m2_df)
    else:
        _, f1 = split_food_bev(m1_df)
        _, f2 = split_food_bev(m2_df)
    # 优先用 M列"仓库类型"(包装/原辅料)，与总览页一致；缺省回退 D列"仓库"(归属仓库)
    wh_key = "仓库类型" if "仓库类型" in f1.columns else "仓库"
    g1 = f1.groupby(["大类", wh_key])["合计积压金额"].sum()
    g2 = f2.groupby(["大类", wh_key])["合计积压金额"].sum()
    all_keys = sorted(set(g1.keys()) | set(g2.keys()), key=_pinyin_key)
    class_total_m2 = g2.groupby(level=0).sum()
    class_order = sorted({k[0] for k in all_keys},
                         key=lambda c: float(class_total_m2.get(c, 0)), reverse=True)
    rows = []
    for cls in class_order:
        cls_keys = [k for k in all_keys if k[0] == cls]
        wh_order = sorted({k[1] for k in cls_keys}, key=_pinyin_key)
        cls_v1 = cls_v2 = 0.0
        wh_data = []
        for wh in wh_order:
            v1 = float(g1.get((cls, wh), 0))
            v2 = float(g2.get((cls, wh), 0))
            if v1 or v2:
                wh_data.append((wh, v1, v2))
                cls_v1 += v1
                cls_v2 += v2
        if not (cls_v1 or cls_v2):
            continue
        if flat:
            # 扁平行：大类名重复在每行（无小计行），行数减半，便于单页容纳
            for wh, v1, v2 in wh_data:
                rows.append([cls, wh, _to_wan(v1), _to_wan(v2),
                             _to_wan(v2 - v1), _pct(v2, v1)])
        else:
            rows.append(([cls, "", _to_wan(cls_v1), _to_wan(cls_v2),
                          _to_wan(cls_v2 - cls_v1), _pct(cls_v2, cls_v1)], "sub"))
            for wh, v1, v2 in wh_data:
                rows.append(["", "　" + wh, _to_wan(v1), _to_wan(v2),
                             _to_wan(v2 - v1), _pct(v2, v1)])
    t1 = float(g1.sum())
    t2 = float(g2.sum())
    rows.append((["总计", "", _to_wan(t1), _to_wan(t2), _to_wan(t2 - t1), _pct(t2, t1)], True))
    return rows, t1, t2


def _paginate_rows_2level(rows, max_rows):
    """两层明细与三层明细同样的切页规则（小计行不悬页尾）。"""
    return _paginate_rows(rows, max_rows)


# （两级明细页渲染已并入下方 add_detail_pages，level=2）


def _paginate_rows(rows, max_rows):
    """按固定行数切页；小计行（sub）尽量不留在页尾（避免「小计在本页、明细在下页」）。
    仅当当前页接近满（>= max_rows-3）时才把小计行移到下页，防止切出过多半空页。"""
    pages, cur = [], []
    n = len(rows)
    near_full = max(4, max_rows - 3)
    for i, r in enumerate(rows):
        cur.append(r)
        is_sub = isinstance(r, tuple) and r[1] == "sub"
        if len(cur) >= max_rows:
            pages.append(cur)
            cur = []
        elif is_sub and i < n - 1 and len(cur) >= near_full:
            pages.append(cur[:-1])
            cur = [cur[-1]]
    if cur:
        pages.append(cur)
    return pages or [[]]


def _merge_class_col(tbl, rows: List, is_2level: bool) -> None:
    """扁平行两级表：纵向合并同类相邻的大类单元格（首列）。"""
    if not is_2level:
        return
    n = len(rows)
    i = 0
    while i < n:
        r = rows[i]
        if isinstance(r, tuple):      # 小计/总计行不参与合并
            i += 1
            continue
        name = str(r[0]).strip()
        if not name or name == "总计":
            i += 1
            continue
        j = i
        while j + 1 < n:
            r2 = rows[j + 1]
            if isinstance(r2, tuple) or str(r2[0]).strip() != name:
                break
            j += 1
        if j > i:
            try:
                # 先清空被合并单元格（数据行 i+1..j）的重复文字，合并后只显示首格内容
                for k in range(i + 1, j + 1):
                    tbl.cell(k + 1, 0).text_frame.clear()
                tbl.cell(i + 1, 0).merge(tbl.cell(j + 1, 0))
            except Exception:
                pass
        i = j + 1


def _merge_group_cols(tbl, rows, specs):
    """通用纵向合并：specs = [(列号, key 函数), ...]。
    对每一列，把「相邻且 key 相同」的普通行单元格合并（小计/总计元组行不参与）。
    被合并格先清空文字，避免合并后重复显示。"""
    n = len(rows)
    for col, keyf in specs:
        i = 0
        while i < n:
            r = rows[i]
            if isinstance(r, tuple):
                i += 1
                continue
            k0 = keyf(r)
            if not k0 or (isinstance(k0, str) and k0.strip() in ("", "总计")):
                i += 1
                continue
            j = i
            while j + 1 < n:
                r2 = rows[j + 1]
                if isinstance(r2, tuple) or keyf(r2) != k0:
                    break
                j += 1
            if j > i:
                try:
                    for k in range(i + 1, j + 1):
                        tbl.cell(k + 1, col).text_frame.clear()
                    tbl.cell(i + 1, col).merge(tbl.cell(j + 1, col))
                except Exception:
                    pass
            i = j + 1


def add_detail_pages(prs, pages, t1, t2, month1, month2, page_no, page_total,
                     chapter: str, factory: str, level: int):
    """明细页渲染（可多页）。level=2：大类/仓库；level=3：大类/仓库/分类。末页带 KPI 条。"""
    if level == 2:
        headers = ["大类", "仓库", f"{month1}（万）", f"{month2}（万）", "环比增长（万）", "环比增长率"]
        ratios = [1.35, 1.5, 1.0, 1.0, 1.2, 1.1]
        sub = "大类/仓库"
    else:
        headers = ["大类", "仓库", "分类", f"{month1}（万）", f"{month2}（万）", "环比增长（万）", "环比增长率"]
        ratios = [1.25, 1.4, 1.6, 0.95, 0.95, 1.15, 1.0]
        sub = "大类/仓库/分类"
    n = len(pages)
    carry_class = None   # 跨页跟踪「当前大类」，续页标题标注上下文
    for pi, pg in enumerate(pages):
        slide = _slide(prs)
        title = f"{chapter} {factory}积压明细 · {sub}（{month1} vs {month2}）"
        if pi > 0:
            # 本页开头的大类：首行大类非空取首行，否则沿用上页的大类
            first_cells = pg[0][0] if pg else []
            start_class = str(first_cells[0]).strip() or carry_class
            suffix = f"（续{pi + 1}"
            if start_class and start_class != "总计":
                suffix += f"· {start_class}"
            title += suffix + "）"
        add_title_bar(slide, title, page_no + pi, page_total)
        # 行高/字号自适应：行数多时自动压缩（避免溢出到 KPI 条/页脚）
        dense = level == 2 and len(pg) >= 12
        l3 = level == 3
        if dense or l3:
            # 密集页：8pt、表顶 0.95"、行高 0.26" 上限；
            # 两级单页延伸到 7.05"（无 KPI）；三级中间页 7.05"（无 KPI），三级末页 6.4"（带 KPI 条）
            bottom = Inches(6.4 if (l3 and pi == n - 1) else 7.05)
            tbl = add_table(slide, headers, pg, top=Inches(0.95),
                            left_cols={0, 1, 2} if l3 else {0, 1},
                            col_ratios=ratios, delta_cols={len(headers) - 2, len(headers) - 1},
                            bottom_limit=bottom, font_size=8, row_cap=0.26)
            if l3:
                _merge_group_cols(tbl, pg, [(0, lambda r: r[0]), (1, lambda r: (r[0], r[1]))])
            else:
                _merge_class_col(tbl, pg, level == 2)
        else:
            fs = 9 if len(pg) > 12 else 10
            add_table(slide, headers, pg,
                      left_cols={0, 1, 2} if level == 3 else {0, 1},
                      col_ratios=ratios, delta_cols={len(headers) - 2, len(headers) - 1},
                      bottom_limit=Inches(6.4), font_size=fs)
        for r in pg:
            cells = r[0] if isinstance(r, tuple) else r
            if str(cells[0]).strip() and str(cells[0]).strip() != "总计":
                carry_class = str(cells[0]).strip()
        if pi == n - 1 and not dense:
            add_kpi_row(slide, [
                (f"{factory}总额", f"{_to_wan(t2)} 万"),
                ("环比变动", f"{abs(t2 - t1) / WAN:,.2f} 万", t2 - t1),
                ("环比增长率", _pct(t2, t1).strip("+-"), t2 - t1),
            ])


def add_food_class_warehouse_slide(prs, pages, t1, t2, month1, month2, slide_num, total):
    """兼容旧接口：食品三级明细页。"""
    add_detail_pages(prs, pages, t1, t2, month1, month2, slide_num, total, "1.2", FOOD_LABEL, 3)


# ---- 1.3 食品包装材料积压 ----
def _material_slide(prs, m1_df, m2_df, month1, month2, page_no, page_total,
                    title: str, chapter: str, factory: str, kw_in: List[str], kw_out: List[str]):
    """包装/原料材料页：大类表格 + 柱图（较新月前 6）+ 饼图（前 3 + 其他）；空数据给友好提示。"""
    slide = _slide(prs)
    add_title_bar(slide, f"{chapter} {title}（{month1} vs {month2}）", page_no, page_total)
    if factory == FOOD_LABEL:
        f1, _ = split_food_bev(m1_df)
        f2, _ = split_food_bev(m2_df)
    else:
        _, f1 = split_food_bev(m1_df)
        _, f2 = split_food_bev(m2_df)

    def _pick(d):
        text = (d["分类"].astype(str) + d["大类"].astype(str))
        mask = text.apply(lambda s: any(k in s for k in kw_in)) & ~text.apply(lambda s: any(k in s for k in kw_out))
        return d[mask]

    p1, p2 = _pick(f1), _pick(f2)
    g1 = p1.groupby("大类")["合计积压金额"].sum()
    g2 = p2.groupby("大类")["合计积压金额"].sum()
    # 两月并集（修 v1.9 只取旧月大类的缺陷），按较新月金额降序
    cats = sorted(set(g1.index) | set(g2.index),
                  key=lambda c: (float(g2.get(c, 0)), float(g1.get(c, 0))), reverse=True)
    rows = []
    for k in cats:
        v1 = float(g1.get(k, 0))
        v2 = float(g2.get(k, 0))
        if v1 == 0 and v2 == 0:
            continue
        share = v2 / g2.sum() * 100 if g2.sum() else 0.0
        rows.append([k, _to_wan(v1), _to_wan(v2), _to_wan(v2 - v1), _pct(v2, v1), f"{share:.2f}%"])
    t1 = float(g1.sum())
    t2 = float(g2.sum())
    if not rows:
        rows.append((["合计", "0.00", "0.00", "0.00", "—", "—"], True))
    else:
        _tot_pct = "100.00%" if t2 > 0 else "—"
        rows.append((["合计", _to_wan(t1), _to_wan(t2), _to_wan(t2 - t1), _pct(t2, t1), _tot_pct], True))
    headers = ["大类", f"{month1}（万）", f"{month2}（万）", "环比增长（万）", "环比增长率", f"{month2}占比"]
    add_table(slide, headers, rows, left=Inches(0.3), width=Inches(6.5),
              col_ratios=[1.2, 1.0, 1.0, 1.35, 1.15, 0.95],
              left_cols={0}, delta_cols={3, 4}, bottom_limit=Inches(6.4))

    if cats and (t1 > 0 or t2 > 0):
        add_bar_chart(slide, cats,
                      [float(g1.get(c, 0)) / WAN for c in cats],
                      [float(g2.get(c, 0)) / WAN for c in cats],
                      s1_name=month1, s2_name=month2,
                      left=Inches(7.0), top=Inches(1.0), width=Inches(6.0), height=Inches(2.5),
                      title=f"{title}金额对比（万）", topn=6)
        if t2 > 0:
            add_pie_chart(slide, cats, [float(g2.get(c, 0)) for c in cats],
                          left=Inches(7.0), top=Inches(3.65), width=Inches(6.0), height=Inches(2.6),
                          title=f"{month2} 占比")
        else:
            add_pie_chart(slide, cats, [float(g1.get(c, 0)) for c in cats],
                          left=Inches(7.0), top=Inches(3.65), width=Inches(6.0), height=Inches(2.6),
                          title=f"{month1} 占比（{month2} 已清零）")
    else:
        _info_card(slide, Inches(7.0), Inches(2.8), Inches(6.0), Inches(1.5),
                   f"{title}：本月无数据",
                   [("两月均无相关积压记录，无处置风险。", C_SUB_FG, False)])
    add_kpi_row(slide, [
        (f"{title}总额", f"{_to_wan(t2)} 万"),
        ("环比变动", f"{abs(t2 - t1) / WAN:,.2f} 万", t2 - t1),
        ("环比增长率", _pct(t2, t1).strip("+-"), t2 - t1),
    ])


def add_food_packaging_slide(prs, m1_df, m2_df, month1, month2, slide_num, total):
    _material_slide(prs, m1_df, m2_df, month1, month2, slide_num, total,
                    title="食品包装材料积压", chapter="1.3", factory=FOOD_LABEL,
                    kw_in=["包装", "纸箱", "纸盒", "纸杯", "塑料膜", "铝箔", "标签"],
                    kw_out=["原料"])


def add_food_raw_slide(prs, m1_df, m2_df, month1, month2, slide_num, total):
    _material_slide(prs, m1_df, m2_df, month1, month2, slide_num, total,
                    title="食品原料材料积压", chapter="1.4", factory=FOOD_LABEL,
                    kw_in=["原辅料", "原料"],
                    kw_out=["包装"])


# ---- 2.1 饮料按大类汇总 ----
def add_bev_class_summary(prs, m1_df, m2_df, month1, month2, slide_num, total):
    """兼容旧接口：转通用大类汇总（饮料）。"""
    rows, t1, t2, g1, g2 = _class_summary_rows(m1_df, m2_df, BEV_LABEL)
    add_class_summary_pages(prs, _paginate_simple(rows, MAX_ROWS_PER_PAGE),
                            t1, t2, g1, g2, month1, month2, slide_num, total,
                            "2.1", BEV_LABEL)


# ---- 2.2 饮料积压分类明细（拼音三级汇总）----
def add_bev_class_warehouse_slide(prs, pages, t1, t2, month1, month2, slide_num, total):
    """兼容旧接口：饮料三级明细页。"""
    add_detail_pages(prs, pages, t1, t2, month1, month2, slide_num, total, "2.2", BEV_LABEL, 3)


def add_bev_packaging_slide(prs, m1_df, m2_df, month1, month2, slide_num, total):
    _material_slide(prs, m1_df, m2_df, month1, month2, slide_num, total,
                    title="饮料包装材料积压", chapter="2.3", factory=BEV_LABEL,
                    kw_in=["包装", "纸箱", "纸盒", "纸杯", "塑料膜", "铝箔", "标签"],
                    kw_out=["原料"])


def add_bev_raw_slide(prs, m1_df, m2_df, month1, month2, slide_num, total):
    _material_slide(prs, m1_df, m2_df, month1, month2, slide_num, total,
                    title="饮料原料材料积压", chapter="2.4", factory=BEV_LABEL,
                    kw_in=["原辅料", "原料"],
                    kw_out=["包装"])


# ============================================================
# 处置跟踪 3 页：账龄分布 / 物料 TOP N / 不流动预警
# （全部取自明细 sheet 原列；缺列自动降级，不硬算）
# ============================================================
IDLE_DAYS = 180        # 不流动判定：最后领用距今 > 180 天，或从未领用
OLD_AGE_DAYS = 365     # 老账龄预警阈值
TRACK_IDLE_PER_PAGE = 16
TRACK_IDLE_MAX_PAGES = 3


def _to_date(v):
    """明细日期列（Timestamp/str）→ date；无效返回 None。"""
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    t = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(t) else t.date()


def _ym_to_date(v):
    """'2026年1月' / '202601' → 月中（15 日），作最后领用缺省。"""
    s = str(v or "")
    m = re.search(r"(\d{4})\D{0,2}(\d{1,2})月?", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return date(int(m.group(1)), int(m.group(2)), 15)
    return None


def _cell(v):
    """明细原值 → 干净字符串（NaN/空 → ''）。"""
    if v is None:
        return ""
    try:
        if isinstance(v, float) and math.isnan(v):
            return ""
    except Exception:
        pass
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _fmt_qty(v):
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else f"{f:.1f}"
    except Exception:
        return _cell(v)


def _truncate(s, n=15):
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def _item_records(df: pd.DataFrame, as_of: date) -> List[dict]:
    """每个物料一行：原列 + 派生（账龄天数/不流动/停用月数）。全部取自明细 sheet。"""
    recs = []
    has_start = "开始积压时间" in df.columns
    has_inbound = "入库日期" in df.columns
    has_last = "最后领用日期" in df.columns
    has_last_ym = "最后领用年月" in df.columns
    for _, row in df.iterrows():
        amt = 0.0
        try:
            amt = float(row.get("合计积压金额", 0) or 0)
        except Exception:
            amt = 0.0
        start = _to_date(row.get("开始积压时间")) if has_start else None
        if start is None and has_inbound:
            start = _to_date(row.get("入库日期"))
        age_days = (as_of - start).days if start else None
        last = _to_date(row.get("最后领用日期")) if has_last else None
        if last is None and has_last_ym:
            last = _ym_to_date(row.get("最后领用年月"))
        idle_days = (as_of - last).days if last else None
        is_idle = (idle_days is None) or (idle_days > IDLE_DAYS)
        recs.append({
            "code": _cell(row.get("物料编码")),
            "name": _cell(row.get("物料名称")),
            "wh": _cell(row.get("归属仓库")) or _cell(row.get("仓库")),
            "qty": row.get("数量"),
            "amt": amt,
            "risk": _cell(row.get("是否存在报废风险")),
            "reason": _cell(row.get("报废原因")),
            "opinion": _cell(row.get("拟处理意见")),
            "owner": _cell(row.get("责任人")),
            "age_days": age_days,
            "start": start,
            "last": last,
            "idle_days": idle_days,
            "idle_months": (None if idle_days is None else max(1, round(idle_days / 30.44))),
            "is_idle": is_idle,
        })
    return recs


def _idle_advice(r: dict) -> str:
    """建议（自动）：源表报废风险优先，其次按账龄/意见推导。"""
    if "可能报废" in r["risk"]:
        return "建议报废评审"
    if r["age_days"] is not None and r["age_days"] > OLD_AGE_DAYS and "自行消耗" in r["opinion"]:
        return "建议报废评审"
    if "调拨" in r["opinion"]:
        return "建议限期调拨"
    if "自行消耗" in r["opinion"]:
        return "建议纳入下月计划"
    return "需明确处理意见"


_AGE_BUCKETS = [
    ("≤90 天", 0, 90),
    ("91–180 天", 91, 180),
    ("181–365 天", 181, 365),
    (">365 天", 366, None),
]


def _aging_summary(recs, as_of: date):
    """返回 (per_bucket [(amt, cnt)], unknown_amt, unknown_cnt, old180_amt)。"""
    out = []
    for name, lo, hi in _AGE_BUCKETS:
        a = sum(r["amt"] for r in recs if r["age_days"] is not None
                and r["age_days"] >= lo and (hi is None or r["age_days"] <= hi))
        c = sum(1 for r in recs if r["age_days"] is not None
                and r["age_days"] >= lo and (hi is None or r["age_days"] <= hi))
        out.append((a, c))
    u_amt = sum(r["amt"] for r in recs if r["age_days"] is None)
    u_cnt = sum(1 for r in recs if r["age_days"] is None)
    old180 = out[2][0] + out[3][0]
    return out, u_amt, u_cnt, old180


def add_aging_slide(prs, recs1, recs2, month1, month2, as_of1, as_of2,
                    page_no, page_total, chapter: str, factory: str):
    slide = _slide(prs)
    add_title_bar(slide, f"{chapter} {factory}积压账龄分布（{month1} vs {month2}）", page_no, page_total)
    s1, u1a, u1c, old1 = _aging_summary(recs1, as_of1)
    s2, u2a, u2c, old2 = _aging_summary(recs2, as_of2)
    tot2 = sum(a for a, _ in s2) + u2a
    headers = ["账龄段", f"{month1}金额（万）", f"{month2}金额（万）", "环比变动（万）", f"{month2}占比", f"{month2}项数"]
    rows = []
    names = [b[0] for b in _AGE_BUCKETS]
    for i, name in enumerate(names):
        a1, c1 = s1[i]
        a2, c2 = s2[i]
        share = a2 / tot2 * 100 if tot2 else 0.0
        rows.append([name, _to_wan(a1), _to_wan(a2), _to_wan(a2 - a1),
                     f"{share:.1f}%", f"{c2} 项"])
    if u2a > 0 or u1a > 0:
        rows.append(["无起始时间", _to_wan(u1a), _to_wan(u2a), _to_wan(u2a - u1a), "—", f"{u2c} 项"])
    add_table(slide, headers, rows, left=Inches(0.3), width=Inches(6.5),
              col_ratios=[1.3, 1.0, 1.0, 1.0, 0.9, 0.8],
              left_cols={0}, delta_cols={3}, bottom_limit=Inches(6.4))
    add_bar_chart(slide, names,
                  [a1 / WAN for a1, _ in s1], [a2 / WAN for a2, _ in s2],
                  s1_name=month1, s2_name=month2,
                  left=Inches(7.0), top=Inches(1.0), width=Inches(6.0), height=Inches(2.5),
                  title=f"账龄段积压金额（万）", topn=4)
    old_share = old2 / tot2 * 100 if tot2 else 0.0
    _info_card(slide, Inches(7.0), Inches(3.75), Inches(6.0), Inches(2.4),
               f"老账龄预警（≥180 天，{month2}）",
               [
                   (f">180 天积压 {old2 / WAN:,.2f} 万，占 {old_share:.1f}%", C_UP if old_share > 30 else C_BODY_FG, old_share > 30),
                   (f"其中 >{OLD_AGE_DAYS} 天：{s2[3][0] / WAN:,.2f} 万", C_UP, False),
                   (f"两月环比：{_to_wan(old2 - old1)} 万", C_BODY_FG, False),
               ])
    add_kpi_row(slide, [
        (f">180 天金额（{month2}）", f"{_to_wan(old2)} 万"),
        ("占总积压", f"{old_share:.1f}%" if tot2 else "—"),
        (">180 天环比", f"{abs(old2 - old1) / WAN:,.2f} 万", old2 - old1),
    ])


def add_top_items_slide(prs, recs2, month2, page_no, page_total, chapter: str,
                        factory: str, topn: int = 20):
    slide = _slide(prs)
    add_title_bar(slide, f"{chapter} {factory}物料积压 TOP {topn}（{month2}）", page_no, page_total)
    items = sorted((r for r in recs2 if r["amt"] > 0), key=lambda r: -r["amt"])[:topn]
    headers = ["#", "物料", "仓库", "数量", "金额（万）", "账龄", "最后领用", "不流动", "报废风险", "处理意见", "责任人"]
    ratios = [0.45, 2.6, 1.1, 0.8, 0.9, 0.8, 0.95, 0.9, 0.9, 1.1, 0.9]
    rows = []
    for i, r in enumerate(items, 1):
        age = "—"
        if r["age_days"] is not None:
            age = f"{r['age_days']} 天" if r["age_days"] < 90 else f"{round(r['age_days'] / 30.44)} 月"
        last = "从未领用" if r["last"] is None else r["last"].strftime("%Y-%m")
        idle = f"⚠ {r['idle_months']} 个月" if r["is_idle"] else "—"
        rows.append([str(i), _truncate(r["name"], 15), r["wh"], _fmt_qty(r["qty"]),
                     _to_wan(r["amt"]), age, last, idle, r["risk"] or "—",
                     r["opinion"] or "—", r["owner"] or "—"])
    dense = len(rows) >= 12
    add_table(slide, headers, rows,
              left_cols={1, 2, 9, 10}, warn_cols={7},
              col_ratios=ratios, bottom_limit=Inches(7.05 if dense else 6.4),
              top=Inches(0.95 if dense else 1.0), font_size=8 if dense else 10,
              row_cap=0.26 if dense else 0.34)
    if not dense:
        tot2 = sum(r["amt"] for r in recs2)
        kpi_amt = sum(r["amt"] for r in items)
        add_kpi_row(slide, [
            (f"TOP{len(items)} 金额", f"{_to_wan(kpi_amt)} 万"),
            ("占工厂积压", f"{(kpi_amt / tot2 * 100 if tot2 else 0):.1f}%"),
            ("含不流动", f"{sum(1 for r in items if r['is_idle'])} 项"),
        ])


def add_idle_pages(prs, recs2, month2, page_no, page_total, chapter: str, factory: str):
    idle = sorted((r for r in recs2 if r["is_idle"] and r["amt"] > 0), key=lambda r: -r["amt"])
    if not idle:
        slide = _slide(prs)
        add_title_bar(slide, f"{chapter} {factory}不流动预警清单（>{IDLE_DAYS} 天未领用，{month2}）",
                      page_no, page_total)
        _info_card(slide, Inches(0.6), Inches(3.0), Inches(11.0), Inches(1.4),
                   f"{month2} 无不流动物料",
                   [("全部物料最近 180 天内均有领用记录，无需处置预警。", C_DOWN, False)])
        return 1
    shown_cap = TRACK_IDLE_PER_PAGE * TRACK_IDLE_MAX_PAGES
    shown = idle[:shown_cap]
    pages = _paginate_simple(shown, TRACK_IDLE_PER_PAGE)
    tot_all = sum(r["amt"] for r in recs2)
    tot_idle = sum(r["amt"] for r in idle)
    n = len(pages)
    for pi, pg in enumerate(pages):
        slide = _slide(prs)
        title = f"{chapter} {factory}不流动预警清单（>{IDLE_DAYS} 天未领用，{month2}）"
        if pi > 0:
            title += f"（续{pi + 1}）"
        add_title_bar(slide, title, page_no + pi, page_total)
        headers = ["物料", "仓库", "金额（万）", "停用了", "报废风险", "报废原因", "处理意见", "责任人", "建议"]
        rows = []
        for r in pg:
            idle_txt = f"{r['idle_months']} 个月" if r["idle_months"] is not None else "从未领用"
            rows.append([_truncate(r["name"], 15), r["wh"], _to_wan(r["amt"]), idle_txt,
                         r["risk"] or "—", r["reason"] or "—", r["opinion"] or "—",
                         r["owner"] or "—", _idle_advice(r)])
        add_table(slide, headers, rows,
                  left_cols={0, 1, 4, 5, 6, 7, 8},
                  col_ratios=[2.4, 1.0, 0.9, 0.9, 0.9, 1.0, 1.0, 0.9, 1.2],
                  bottom_limit=Inches(7.05), top=Inches(0.95), font_size=8, row_cap=0.26)
        if pi == n - 1:
            if len(idle) > len(shown):
                rest_amt = sum(r["amt"] for r in idle[len(shown):])
                nb = slide.shapes.add_textbox(Inches(0.3), Inches(6.55), Inches(12.7), Inches(0.35))
                p = nb.text_frame.paragraphs[0]
                rr = p.add_run()
                _set_run(rr, f"其余 {len(idle) - len(shown)} 项不流动物料未列出，金额 {_to_wan(rest_amt)} 万（见明细附表）",
                         size=9, color=C_SUB_FG)
            share = tot_idle / tot_all * 100 if tot_all else 0.0
            n_adv = sum(1 for r in shown if "报废" in _idle_advice(r))
            add_kpi_row(slide, [
                ("不流动总额", f"{_to_wan(tot_idle)} 万"),
                ("占总积压", f"{share:.1f}%"),
                ("建议报废评审（列示）", f"{n_adv} 项"),
            ])
    return n


# ---- 10 核心结论与建议 ----
def add_conclusion_slide(prs, m1_df, m2_df, month1, month2, page_no, page_total, material_warn=None):
    """核心结论与建议：双卡片版式（核心结论 / 管理建议），内容全部数据驱动。"""
    slide = _slide(prs)
    add_title_bar(slide, f"核心结论与建议（{month1} vs {month2}）", page_no, page_total)

    grand1 = float(m1_df["合计积压金额"].sum())
    grand2 = float(m2_df["合计积压金额"].sum())
    diff = grand2 - grand1
    pct = diff / grand1 * 100 if grand1 else 0.0
    f1, b1 = split_food_bev(m1_df)
    f2, b2 = split_food_bev(m2_df)
    food1 = float(f1["合计积压金额"].sum())
    food2 = float(f2["合计积压金额"].sum())
    bev1 = float(b1["合计积压金额"].sum())
    bev2 = float(b2["合计积压金额"].sum())
    food_diff = food2 - food1
    bev_diff = bev2 - bev1

    # 大类维度（食品 + 饮料并集）
    all1 = pd.concat([f1, b1], ignore_index=True)
    all2 = pd.concat([f2, b2], ignore_index=True)
    g1 = all1.groupby("大类")["合计积压金额"].sum()
    g2 = all2.groupby("大类")["合计积压金额"].sum()
    cats = sorted(set(g1.index) | set(g2.index), key=lambda c: float(g2.get(c, 0)), reverse=True)
    deltas = {c: float(g2.get(c, 0)) - float(g1.get(c, 0)) for c in cats}
    top3 = [c for c in cats if float(g2.get(c, 0)) > 0][:3]
    risers = sorted((c for c in cats if deltas[c] > 1e-9), key=lambda c: -deltas[c])[:3]
    warn20 = [c for c in cats if float(g1.get(c, 0)) > 0 and deltas[c] / float(g1.get(c, 0)) > 0.2]
    cleared = [c for c in cats if float(g1.get(c, 0)) > 0 and float(g2.get(c, 0)) <= 1e-9]
    newcats = [c for c in cats if float(g1.get(c, 0)) <= 1e-9 and float(g2.get(c, 0)) > 0]

    def _share(c):
        return float(g2.get(c, 0)) / grand2 * 100 if grand2 else 0.0

    concl = [
        (f"{month2} 积压总额 {grand2 / WAN:,.2f} 万，较 {month1} {diff / WAN:+,.2f} 万（{pct:+.1f}%）", C_DARK_BLUE, True),
        (f"食品 {food_diff / WAN:+,.2f} 万（{food_diff / food1 * 100 if food1 else 0:+.1f}%），"
         f"饮料 {bev_diff / WAN:+,.2f} 万（{bev_diff / bev1 * 100 if bev1 else 0:+.1f}%）", C_BODY_FG, False),
    ]
    if top3:
        concl.append(("占比前三：" + "、".join(f"{c}（{_share(c):.0f}%）" for c in top3), C_BODY_FG, False))
    if risers:
        concl.append(("环比增长最多：" + "、".join(f"{c} +{deltas[c] / WAN:,.2f} 万" for c in risers), C_UP, False))
    if cleared:
        concl.append((f"已清零大类 {len(cleared)} 个：" + "、".join(cleared[:6]), C_DOWN, False))
    if newcats:
        concl.append((f"新增大类 {len(newcats)} 个：" + "、".join(newcats[:6]), C_UP, False))
    if not risers and not cleared and not newcats and not top3:
        concl.append(("大类结构基本稳定，无显著变动", C_SUB_FG, False))

    adv = []
    if warn20:
        adv.append((f"环比增长 >20% 大类 {len(warn20)} 个（{'、'.join(warn20[:4])}），建议启动专项盘点并明确处置方案与时间", C_UP, False))
    adv.append(("包装材料积压反映销售预测与订单偏差，建议月度复盘销售计划与包装订购量", C_BODY_FG, False))
    adv.append(("对不流动（>180 天）物料加强预警与跨厂调拨/处置，控制资金占用", C_BODY_FG, False))
    if bev_diff < 0 and food_diff > 0:
        adv.append(("饮料积压下降、食品积压上升：总结饮料侧处置经验，推广至食品端", C_DOWN, False))
    elif food_diff < 0 and bev_diff > 0:
        adv.append(("食品积压下降、饮料积压上升：总结食品侧处置经验，推广至饮料端", C_DOWN, False))
    else:
        adv.append(("两厂积压方向一致，建议设定月度积压压降目标并跟踪执行", C_BODY_FG, False))

    _info_card(slide, Inches(0.3), Inches(1.05), Inches(6.35), Inches(5.1), "核心结论", concl, size=11)
    _info_card(slide, Inches(6.95), Inches(1.05), Inches(6.05), Inches(5.1), "管理建议", adv, size=11)

    add_kpi_row(slide, [
        (f"{month2} 积压总额", f"{_to_wan(grand2)} 万"),
        ("环比变动", f"{abs(diff) / WAN:,.2f} 万", diff),
        ("环比增长率", (f"{abs(pct):.2f}%" if grand1 else ("新增" if diff else "—")), diff),
    ])


# ============================================================
# 缺数据占位
# ============================================================
def add_placeholder_box(slide, text: str):
    tb = slide.shapes.add_textbox(Inches(2), Inches(3), Inches(9.3), Inches(1.5))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    _set_run(r, text, size=18, color=C_SUB_FG)


# ============================================================
# 生成 PPT 主流程
# ============================================================
def _placeholder_slide(prs, title: str, page_no: int, page_total: int, note: str):
    """缺数据占位页。"""
    slide = _slide(prs)
    add_title_bar(slide, title, page_no, page_total)
    add_placeholder_box(slide, note)


def generate_ppt(f1_path: str, d1_path: str, f2_path: str, d2_path: str,
                 month1: Optional[str] = None, month2: Optional[str] = None, out: str = "") -> str:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    def need(path, label):
        if not path or not os.path.isfile(path):
            return None
        return read_inventory_file(path)

    m1_food_df = need(f1_path, "f1")
    m1_bev_df = need(d1_path, "d1")
    m2_food_df = need(f2_path, "f2")
    m2_bev_df = need(d2_path, "d2")

    # 月份自动识别（不写死）：从文件名 6 位年月解析；相邻月/跨月都支持，月2 须较新（反了自动对调）
    m1_ym = m2_ym = None
    if month1 is None or month2 is None:
        if month1 is None:
            if f1_path:
                m1_ym, month1 = _parse_ym(f1_path), parse_month_from_filename(f1_path)
            elif d1_path:
                m1_ym, month1 = _parse_ym(d1_path), parse_month_from_filename(d1_path)
            else:
                raise ValueError("缺少月1(较早月)的食品/饮料文件路径，无法自动识别月份")
        if month2 is None:
            if f2_path:
                m2_ym, month2 = _parse_ym(f2_path), parse_month_from_filename(f2_path)
            elif d2_path:
                m2_ym, month2 = _parse_ym(d2_path), parse_month_from_filename(d2_path)
            else:
                raise ValueError("缺少月2(较新月)的食品/饮料文件路径，无法自动识别月份")
        # 校验食品/饮料同月
        for p, who, grp in ((f1_path, "月1食品", "月1"), (d1_path, "月1饮料", "月1"),
                            (f2_path, "月2食品", "月2"), (d2_path, "月2饮料", "月2")):
            if p:
                ym = _parse_ym(p)
                if grp == "月1" and m1_ym is not None and ym != m1_ym:
                    raise ValueError(f"{who} 月份({ym})与月1({m1_ym})不一致")
                if grp == "月2" and m2_ym is not None and ym != m2_ym:
                    raise ValueError(f"{who} 月份({ym})与月2({m2_ym})不一致")
        # 相邻月、跨月（如 5月 vs 8月）都允许，只要求「月2 比 月1 新」；顺序反了自动对调
        if m1_ym is not None and m2_ym is not None:
            if m2_ym == m1_ym:
                raise ValueError(f"对比两月不能相同：{month1} vs {month2}")
            if m2_ym < m1_ym:
                logger.info(f"月份顺序反了（{month1} vs {month2}），已自动对调为「较早月 vs 较新月」")
                f1_path, f2_path = f2_path, f1_path
                d1_path, d2_path = d2_path, d1_path
                m1_food_df, m2_food_df = m2_food_df, m1_food_df
                m1_bev_df, m2_bev_df = m2_bev_df, m1_bev_df
                m1_ym, m2_ym = m2_ym, m1_ym
                month1, month2 = month2, month1

    # 合并食品+饮料到 m1_df / m2_df，供总览/结论使用
    m1_df = pd.concat([d for d in (m1_food_df, m1_bev_df) if d is not None], ignore_index=True) if (m1_food_df is not None or m1_bev_df is not None) else None
    m2_df = pd.concat([d for d in (m2_food_df, m2_bev_df) if d is not None], ignore_index=True) if (m2_food_df is not None or m2_bev_df is not None) else None

    # 账龄/不流动基准日：两月各自月末（显式传月份标签时回退到文件名 6 位年月）
    def _eff_ym(label, path):
        try:
            return _parse_ym(path)
        except Exception:
            mm = re.search(r"(\d{1,2})月", str(label or ""))
            yy = pd.Timestamp.now().year
            return yy * 100 + (int(mm.group(1)) if mm else 12)

    def _ym_end(ym):
        y, m = divmod(ym, 100)
        return date(y, m, calendar.monthrange(y, m)[1])

    m1_ym_eff = m1_ym if m1_ym is not None else _eff_ym(month1, f1_path or d1_path)
    m2_ym_eff = m2_ym if m2_ym is not None else _eff_ym(month2, f2_path or d2_path)
    as_of1, as_of2 = _ym_end(m1_ym_eff), _ym_end(m2_ym_eff)

    # —— 预计算各节数据与分页（页脚页码 = 真实总页数）——
    def _idle_n_pages(n_idle: int) -> int:
        shown = min(n_idle, TRACK_IDLE_PER_PAGE * TRACK_IDLE_MAX_PAGES)
        return max(1, math.ceil(shown / TRACK_IDLE_PER_PAGE)) if shown else 1

    def precalc(df1, df2, factory, topn: int):
        rows, t1, t2, g1, g2 = _class_summary_rows(df1, df2, factory)
        d2l, dv1, dv2 = _build_class_warehouse_rows_2level(df1, df2, month1, month2, factory)
        # 两级明细：行数多时改扁平行（大类名重复、无小计行），单页即可容纳
        if len(d2l) >= 14:
            d2l, dv1, dv2 = _build_class_warehouse_rows_2level(df1, df2, month1, month2, factory, flat=True)
        d3l, sv1, sv2 = _build_class_warehouse_rows(df1, df2, month1, month2, factory, flat=True)
        recs1 = _item_records(df1, as_of1)
        recs2 = _item_records(df2, as_of2)
        n_idle = sum(1 for r in recs2 if r["is_idle"] and r["amt"] > 0)
        return {
            "pg11": _paginate_simple(rows, MAX_ROWS_PER_PAGE),
            # 两层明细：默认单页自动容纳（行高/字号自适应）；超过 22 行才分页
            "pg22": [d2l] if len(d2l) <= 22 else _paginate_rows_2level(d2l, MAX_ROWS_PER_PAGE),
            "pg33": _paginate_tail(d3l),
            "sum": (t1, t2, g1, g2),
            "d2": (dv1, dv2),
            "d3": (sv1, sv2),
            "recs1": recs1, "recs2": recs2, "topn": topn,
            "idle_pages": _idle_n_pages(n_idle),
        }

    st_food = precalc(m1_food_df, m2_food_df, FOOD_LABEL, 20) if (m1_food_df is not None and m2_food_df is not None) else None
    st_bev = precalc(m1_bev_df, m2_bev_df, BEV_LABEL, 15) if (m1_bev_df is not None and m2_bev_df is not None) else None

    def npg(st, key):
        return len(st[key]) if st else 1

    def nidle(st):
        return st["idle_pages"] if st else 1

    page_total = (1                                   # 封面
                  + 1                                 # 总览
                  + npg(st_food, "pg11") + npg(st_food, "pg22") + npg(st_food, "pg33") + 1 + 1
                  + 1 + 1 + nidle(st_food)            # 账龄 / TOP / 不流动
                  + npg(st_bev, "pg11") + npg(st_bev, "pg22") + npg(st_bev, "pg33") + 1 + 1
                  + 1 + 1 + nidle(st_bev)             # 账龄 / TOP / 不流动
                  + 1)                                 # 结论

    pn = 0

    # 0 封面
    pn += 1
    add_cover_slide(prs, month1, month2, [p for p in (f1_path, d1_path, f2_path, d2_path) if p])

    if m1_df is None or m2_df is None:
        # 缺数据：封面 + 一页占位
        slide = _slide(prs)
        add_title_bar(slide, f"积压材料总览（{month1} vs {month2}）", 2, 2)
        add_placeholder_box(slide, f"暂无 {month1}-{month2} 对比数据（请在 GUI 中指定文件）")
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        prs.save(out)
        logger.info(f"生成完成: {out}（缺数据占位）")
        return out

    def factory_block(st, factory, ch11, ch12, ch13, ch14, m1f, m2f, miss_note,
                      ch15="?", ch16="?", ch17="?"):
        """食品/饮料八节：大类汇总 → 两层明细（单页） → 三层明细 → 包装 → 原料
        → 账龄分布 → 物料TOP N → 不流动预警；缺数据自动占位。"""
        nonlocal pn
        if st:
            pn += 1
            s = st["sum"]
            add_class_summary_pages(prs, st["pg11"], s[0], s[1], s[2], s[3],
                                    month1, month2, pn, page_total, ch11, factory)
            pn += len(st["pg11"]) - 1
        else:
            pn += 1
            _placeholder_slide(prs, f"{ch11} {factory}按大类汇总（{month1} vs {month2}）",
                               pn, page_total, miss_note)
        # 两层明细：单页自动容纳（行多时自动缩字号/行高）；仅超 22 行才分页
        if st:
            pn += 1
            add_detail_pages(prs, st["pg22"], st["d2"][0], st["d2"][1], month1, month2,
                             pn, page_total, ch12, factory, 2)
            pn += len(st["pg22"]) - 1
        else:
            pn += 1
            _placeholder_slide(prs, f"{ch12} {factory}积压明细 · 大类/仓库（{month1} vs {month2}）",
                               pn, page_total, miss_note)
        if st:
            pn += 1
            add_detail_pages(prs, st["pg33"], st["d3"][0], st["d3"][1], month1, month2,
                             pn, page_total, ch12, factory, 3)
            pn += len(st["pg33"]) - 1
        else:
            pn += 1
            _placeholder_slide(prs, f"{ch12} {factory}积压明细 · 大类/仓库/分类（{month1} vs {month2}）",
                               pn, page_total, miss_note)
        pn += 1
        if st:
            (add_food_packaging_slide if factory == FOOD_LABEL else add_bev_packaging_slide)(
                prs, m1f, m2f, month1, month2, pn, page_total)
        else:
            _placeholder_slide(prs, f"{ch13} {factory}包装材料积压（{month1} vs {month2}）",
                               pn, page_total, miss_note)
        pn += 1
        if st:
            (add_food_raw_slide if factory == FOOD_LABEL else add_bev_raw_slide)(
                prs, m1f, m2f, month1, month2, pn, page_total)
        else:
            _placeholder_slide(prs, f"{ch14} {factory}原料材料积压（{month1} vs {month2}）",
                               pn, page_total, miss_note)
        # 处置跟踪：账龄分布 → 物料 TOP N → 不流动预警（全部取自明细 sheet）
        if st:
            pn += 1
            add_aging_slide(prs, st["recs1"], st["recs2"], month1, month2, as_of1, as_of2,
                            pn, page_total, ch15, factory)
            pn += 1
            add_top_items_slide(prs, st["recs2"], month2, pn, page_total, ch16, factory, st["topn"])
            n_idle = add_idle_pages(prs, st["recs2"], month2, pn + 1, page_total, ch17, factory)
            pn += n_idle
        else:
            for ch, ttl in (
                (ch15, f"{ch15} {factory}积压账龄分布（{month1} vs {month2}）"),
                (ch16, f"{ch16} {factory}物料积压 TOP（{month2}）"),
                (ch17, f"{ch17} {factory}不流动预警清单（>{IDLE_DAYS} 天，{month2}）"),
            ):
                pn += 1
                _placeholder_slide(prs, ttl, pn, page_total, miss_note)

    # 1 总览
    pn += 1
    add_overview_slide(prs, m1_df, m2_df, month1, month2, pn, page_total)
    # 2~5 食品
    factory_block(st_food, FOOD_LABEL, "1.1", "1.2", "1.3", "1.4",
                  m1_food_df, m2_food_df, "源数据缺少食品 sheet 或文件不存在",
                  ch15="1.5", ch16="1.6", ch17="1.7")
    # 6~9 饮料
    factory_block(st_bev, BEV_LABEL, "2.1", "2.2", "2.3", "2.4",
                  m1_bev_df, m2_bev_df, "源数据缺少饮料 sheet 或文件不存在",
                  ch15="2.5", ch16="2.6", ch17="2.7")
    # 10 结论
    pn += 1
    add_conclusion_slide(prs, m1_df, m2_df, month1, month2, pn, page_total)

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    prs.save(out)
    logger.info(f"生成完成: {out}（共 {sum(1 for _ in prs.slides)} 页）")
    return out


# ============================================================
# GUI
# ============================================================
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    cfg = AppConfig.load()

    root = tk.Tk()
    root.title(f"云南达利积压分析 {APP_VERSION}")
    try:
        root.state("zoomed")
    except Exception:
        pass

    # 顶部标题栏（logo 占位 + 主副标题 + 版本水印）
    title_frame = tk.Frame(root, bg="#003366")
    title_frame.pack(fill=tk.X)
    tinner = tk.Frame(title_frame, bg="#003366")
    tinner.pack(fill=tk.X, padx=16, pady=12)
    tk.Label(tinner, text="达", fg="white", bg="#1F6FB2", font=("微软雅黑", 18, "bold"),
             width=2, height=1).pack(side=tk.LEFT, padx=(0, 10))
    ttxt = tk.Frame(tinner, bg="#003366")
    ttxt.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Label(ttxt, text="云南达利积压分析 · PPT 生成器", fg="white", bg="#003366",
             font=("微软雅黑", 15, "bold"), anchor="w").pack(anchor="w")
    tk.Label(ttxt, text=f"{APP_VERSION} 增强版   |   Ctrl+G 生成   Ctrl+M 智能匹配",
             fg="#BBD3EA", bg="#003366", font=("微软雅黑", 9)).pack(anchor="w", pady=(2, 0))
    tk.Label(tinner, text=APP_VERSION, fg="#BBD3EA", bg="#003366", font=("微软雅黑", 9)).pack(side=tk.RIGHT, padx=(10, 0))

    body = tk.Frame(root, padx=20, pady=14)
    body.pack(fill=tk.X)

    scan_dir_var = tk.StringVar(value=cfg.scan_dir)

    rows = [
        ("扫描目录", scan_dir_var, "dir", "scan"),  # 支持用 ; 分隔多个目录
        ("较早月·食品", cfg.last_f1, "file", "f1"),
        ("较早月·饮料", cfg.last_d1, "file", "d1"),
        ("较新月·食品", cfg.last_f2, "file", "f2"),
        ("较新月·饮料", cfg.last_d2, "file", "d2"),
    ]

    entry_vars = {}
    for i, (label, val, kind, key) in enumerate(rows):
        lw = tk.Label(body, text=label, font=("微软雅黑", 11))
        lw.grid(row=i, column=0, sticky=tk.W, pady=8)
        v = tk.StringVar(value=val if isinstance(val, str) else "")
        entry_vars[key] = v
        e = tk.Entry(body, textvariable=v, width=80, font=("微软雅黑", 10))
        e.grid(row=i, column=1, padx=8, pady=8, sticky=tk.EW)
        if kind == "dir":
            def browse_dir():
                p = filedialog.askdirectory(initialdir=v.get() or os.path.expanduser("~"))
                if p:
                    v.set(p); scan_dir_var.set(p)
                    refresh_month_lists()
            tk.Button(body, text="浏览...", command=browse_dir).grid(row=i, column=2, padx=4)
        else:
            def browse_file(_v=v):
                p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")],
                                               initialdir=os.path.dirname(_v.get()) or scan_dir_var.get())
                if p:
                    _v.set(p); refresh_month_lists(True)
            tk.Button(body, text="浏览...", command=browse_file).grid(row=i, column=2, padx=4)

    body.columnconfigure(1, weight=1)

    # 月份自动识别状态（不写死，从文件名 6 位年月解析）
    month_status_var = tk.StringVar(value="对比月份（自动识别）：未指定文件")
    ms = tk.Label(body, textvariable=month_status_var, font=("微软雅黑", 10), fg="#1F6FB2")
    ms.grid(row=len(rows) + 2, column=0, columnspan=3, sticky="w", pady=(0, 6))

    def refresh_months():
        try:
            m1 = (parse_month_from_filename(entry_vars["f1"].get()) if entry_vars["f1"].get()
                  else (parse_month_from_filename(entry_vars["d1"].get()) if entry_vars["d1"].get() else None))
            m2 = (parse_month_from_filename(entry_vars["f2"].get()) if entry_vars["f2"].get()
                  else (parse_month_from_filename(entry_vars["d2"].get()) if entry_vars["d2"].get() else None))
            if m1 and m2:
                # 相邻/跨月都能对比：只提示相隔几个月，不做限制
                try:
                    ym1 = _parse_ym(entry_vars["f1"].get() if entry_vars["f1"].get() else entry_vars["d1"].get())
                    ym2 = _parse_ym(entry_vars["f2"].get() if entry_vars["f2"].get() else entry_vars["d2"].get())
                    gap = ym2 - ym1
                except ValueError:
                    gap = 1
                if gap == 1:
                    suffix = "（相邻月）"
                elif gap > 1:
                    suffix = f"（相隔 {gap} 个月，可对比）"
                elif gap == 0:
                    suffix = "（⚠ 两月相同）"
                else:
                    suffix = "（⚠ 月份1 比 月份2 新，请核对左右）"
                month_status_var.set(f"对比月份（自动识别）：{m1} vs {m2} {suffix}")
            elif m1 or m2:
                month_status_var.set(f"对比月份（自动识别）：仅识别到 {'/'.join(x for x in (m1, m2) if x)}，请补全另一月文件")
            else:
                month_status_var.set("对比月份（自动识别）：未指定文件")
        except ValueError as e:
            month_status_var.set(f"月份识别失败：{e}")

    def _collect_dirs():
        dirs = []
        seen = set()

        def _add(d):
            if d and os.path.isdir(d):
                key = os.path.normcase(os.path.abspath(d))
                if key not in seen:
                    seen.add(key)
                    dirs.append(d)

        # 主扫描目录（支持用 ; 或换行分隔多个目录）
        for part in re.split(r"[;\n]", scan_dir_var.get().strip()):
            _add(part.strip())
        # 四个文件所在目录
        for k in ("f1", "d1", "f2", "d2"):
            fp = entry_vars[k].get().strip()
            if fp:
                _add(os.path.dirname(fp))
        # 已知报表目录（补充扫描，存在才加）：保证 H 盘报表目录里的新月份也能列出来
        for d in KNOWN_DATA_DIRS:
            _add(d)
        return dirs

    # ---- 年份 / 月份选择：较早月=年+月、较新月=年+月（数字框带上下箭头，可点可滚）----
    _month_files = {}   # ym -> {"food":..,"bev":..}
    _cur_year = pd.Timestamp.now().year
    YEAR_MIN, YEAR_MAX = _cur_year - 5, _cur_year + 1

    y1_var = tk.IntVar(value=_cur_year)
    m1_var = tk.IntVar(value=1)
    y2_var = tk.IntVar(value=_cur_year)
    m2_var = tk.IntVar(value=2)

    def _ym_from_entries(keys):
        for k in keys:
            v = entry_vars[k].get().strip()
            if v:
                try:
                    return _parse_ym(v)
                except ValueError:
                    return None
        return None

    def _apply_month_widgets_to_entries():
        """年/月框 → 精确找当月文件 → 填四个文件框（不跨年猜、不自动换月）。"""
        for keys, ym in ((("f1", "d1"), y1_var.get() * 100 + m1_var.get()),
                         (("f2", "d2"), y2_var.get() * 100 + m2_var.get())):
            info = _month_files.get(ym) or {}
            entry_vars[keys[0]].set(info.get("food") or "")
            entry_vars[keys[1]].set(info.get("bev") or "")
        refresh_months()

    def _on_huanbi():
        """环比：较早月 = 较新月的上一月（自动跨年）。"""
        y2, m2 = y2_var.get(), m2_var.get()
        m1, y1 = m2 - 1, y2
        if m1 < 1:
            m1, y1 = 12, y2 - 1
        y1_var.set(y1)
        m1_var.set(m1)
        _apply_month_widgets_to_entries()

    month_holder = tk.Frame(body)
    month_holder.grid(row=len(rows), column=1, padx=8, pady=6, sticky="w")

    def _spinbox(parent, text_var, from_, to_):
        # 注意：形参加 to_，这里必须用 to_（写成 to 会 NameError，v1.9 就栽在这）
        tk.Spinbox(parent, from_=from_, to=to_, width=4, font=("微软雅黑", 10),
                   textvariable=text_var, justify="center",
                   command=_apply_month_widgets_to_entries,
                   buttonbackground="#D6E3F0").pack(side=tk.LEFT, padx=(2, 0))

    tk.Label(month_holder, text="较早月", font=("微软雅黑", 11)).pack(side=tk.LEFT, padx=(0, 6))
    _spinbox(month_holder, y1_var, YEAR_MIN, YEAR_MAX)
    tk.Label(month_holder, text="年", font=("微软雅黑", 9), fg="#888888").pack(side=tk.LEFT, padx=(2, 0))
    _spinbox(month_holder, m1_var, 1, 12)
    tk.Label(month_holder, text="月", font=("微软雅黑", 9), fg="#888888").pack(side=tk.LEFT)
    tk.Label(month_holder, text="较新月", font=("微软雅黑", 11), fg="#1F3A5F").pack(side=tk.LEFT, padx=(18, 6))
    _spinbox(month_holder, y2_var, YEAR_MIN, YEAR_MAX)
    tk.Label(month_holder, text="年", font=("微软雅黑", 9), fg="#888888").pack(side=tk.LEFT, padx=(2, 0))
    _spinbox(month_holder, m2_var, 1, 12)
    tk.Label(month_holder, text="月", font=("微软雅黑", 9), fg="#888888").pack(side=tk.LEFT)
    tk.Button(month_holder, text="🔄 环比（较早月=较新月上一月）", command=_on_huanbi,
              font=("微软雅黑", 9), bg="#1F7A3D", fg="white", padx=10, pady=3).pack(side=tk.LEFT, padx=12)

    month_count_var = tk.StringVar(value="正在扫描可用月份…")
    tk.Label(body, textvariable=month_count_var, font=("微软雅黑", 9),
             fg="#1F7A3D").grid(row=len(rows) + 1, column=1, sticky="w", padx=8)

    def refresh_month_lists(set_latest=True):
        """重新扫描可用月份。

        set_latest=True（启动/刷新月份）：把年/月框重置成最近两个「实际存在」的月；
        set_latest=False（改完年/月想重扫时）：保留你当前选的年月。
        默认行为是每次启动都回到最近两个实际存在的月份。
        """
        _month_files.clear()
        _month_files.update(scan_month_files_multi(_collect_dirs()))
        yms = sorted(_month_files.keys())
        if set_latest:
            pair = latest_two_months(_month_files)
            if pair:
                y1_var.set(pair[0] // 100); m1_var.set(pair[0] % 100)
                y2_var.set(pair[1] // 100); m2_var.set(pair[1] % 100)
        _apply_month_widgets_to_entries()
        if yms:
            shown = sorted({ym % 100 for ym in yms})
            years = sorted({ym // 100 for ym in yms})
            year_range = f"{min(years)}~{max(years)}" if len(years) > 1 else str(years[0])
            month_count_var.set(
                f"扫到可对比月份：{'、'.join(str(m) for m in shown)}（{len(shown)} 个不同月份，年份 {year_range}；改动年/月框自动填文件）")
        else:
            month_count_var.set("⚠ 未扫描到月份文件，请把「扫描目录」指到报表所在文件夹")

    # 报告设置（利用原先空白区）
    setting_frame = tk.LabelFrame(root, text="报告设置", font=("微软雅黑", 11, "bold"),
                                  fg="#003366", padx=16, pady=10)
    setting_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

    tk.Label(setting_frame, text="输出目录", font=("微软雅黑", 10)).grid(row=0, column=0, sticky="w", pady=4)
    out_dir_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
    out_entry = tk.Entry(setting_frame, textvariable=out_dir_var, width=62, font=("微软雅黑", 10))
    out_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

    def browse_out():
        p = filedialog.askdirectory(initialdir=out_dir_var.get() or os.path.expanduser("~"))
        if p:
            out_dir_var.set(p)
    tk.Button(setting_frame, text="浏览...", command=browse_out).grid(row=0, column=2, padx=4)

    tk.Label(setting_frame, text="输出文件名", font=("微软雅黑", 10)).grid(row=1, column=0, sticky="w", pady=4)
    tk.Label(setting_frame, text="云南达利积压分析_<较早月>vs<较新月>_<时间戳>.pptx（月份自动识别）",
             font=("微软雅黑", 10), fg="#1F3A5F").grid(row=1, column=1, columnspan=2, sticky="w", pady=4)

    auto_open_var = tk.BooleanVar(value=True)
    tk.Checkbutton(setting_frame, text="生成完成后自动打开 PPT", variable=auto_open_var,
                   font=("微软雅黑", 10)).grid(row=2, column=0, columnspan=3, sticky="w", pady=4)
    setting_frame.columnconfigure(1, weight=1)

    # 使用说明（填充底部空白）
    help_frame = tk.LabelFrame(root, text="使用说明", font=("微软雅黑", 11, "bold"),
                               fg="#003366", padx=16, pady=10)
    help_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
    help_text = ("· 月份自动从文件名（6 位年月 YYYYMM）识别，无需手输；「较早月」「较新月」各配一个年份、一个月份数字框（可点上下箭头、也可滚鼠标滚轮），改完自动把上面四个文件换掉；旁边「🔄 环比」一按钮把较早月设成较新月的上一月（自动跨年）。\n"
                 "· 打开界面自动回到最近两个「实际存在」的月，每月出了新报表刷新一下就跟上；相邻月、跨月（如 5月 vs 8月）都能比。\n"
                 "· 月份来源＝合并扫描「扫描目录 + 已选文件所在目录 + 已知报表目录（H:\\26年报表\\积压表、桌面\\积压）」，各月文件放不同文件夹也能一起扫到；「扫描目录」还支持用 ; 分隔多个目录。\n"
                 "· 点「智能匹配」按所选年月找齐食品/饮料四个文件（某个月没文件会如实报 x/4，不会偷偷抓别的年份同月）；月份选反了会自动对调。\n"
                 "· 输出目录默认在桌面「云南达利积压分析报告」文件夹，生成后可直接打开或复制。\n"
                 "· 生成完成后弹窗可一键「打开 PPT / 打开所在文件夹 / 复制文件路径」。\n"
                 "· 快捷键：Ctrl+G 生成 PPT，Ctrl+M 智能匹配文件。")
    tk.Label(help_frame, text=help_text, font=("微软雅黑", 10), fg="#444444",
             justify="left", anchor="nw").pack(fill=tk.BOTH, expand=True)

    # ---- 完成弹窗（4 按钮）----
    def show_success_window(out, elapsed, n_slides=0):
        w = tk.Toplevel(root)
        w.title("生成完成")
        w.geometry("540x300")
        w.resizable(False, False)
        hdr = tk.Frame(w, bg="#1F7A3D")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="🎉 生成完成", fg="white", bg="#1F7A3D",
                 font=("微软雅黑", 15, "bold")).pack(pady=10)
        size_mb = os.path.getsize(out) / (1024 * 1024)
        info = (f"📄 文件：{os.path.basename(out)}\n\n"
                f"📂 位置：{os.path.dirname(out)}\n\n"
                f"📊 共 {n_slides} 页 / {size_mb:.1f} MB / 用时 {elapsed:.1f} 秒")
        tk.Label(w, text=info, font=("微软雅黑", 10), justify="left", anchor="w",
                 fg="#222222", padx=18, pady=12).pack(fill=tk.X)
        bf = tk.Frame(w)
        bf.pack(pady=8)

        def open_ppt():
            try:
                os.startfile(out)
            except Exception:
                pass
            w.destroy()

        def open_folder():
            try:
                os.system(f'explorer /select,"{out}"')
            except Exception:
                pass

        def copy_path():
            try:
                root.clipboard_clear()
                root.clipboard_append(out)
            except Exception:
                pass

        tk.Button(bf, text="🚀 打开 PPT", command=open_ppt, bg="#003366", fg="white",
                  font=("微软雅黑", 11), padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="📂 打开文件夹", command=open_folder, bg="#1F3A5F", fg="white",
                  font=("微软雅黑", 11), padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="📋 复制路径", command=copy_path, bg="#5A6B7B", fg="white",
                  font=("微软雅黑", 11), padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="关闭", command=w.destroy, font=("微软雅黑", 11),
                  padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        w.transient(root)
        try:
            w.grab_set()
        except Exception:
            pass
        w.update_idletasks()
        w.geometry(f"+{root.winfo_x()+180}+{root.winfo_y()+140}")

    # ---- 失败弹窗 ----
    def show_error_window(detail):
        w = tk.Toplevel(root)
        w.title("生成失败")
        w.geometry("540x260")
        w.resizable(False, False)
        hdr = tk.Frame(w, bg="#C0392B")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="❌ 生成失败", fg="white", bg="#C0392B",
                 font=("微软雅黑", 15, "bold")).pack(pady=10)
        tk.Label(w, text=f"原因：\n{detail[:600]}", font=("微软雅黑", 10), justify="left",
                 anchor="w", fg="#A02020", wraplength=500, padx=18, pady=12).pack(fill=tk.X)

        def copy_err():
            try:
                root.clipboard_clear()
                root.clipboard_append(detail)
            except Exception:
                pass

        bf = tk.Frame(w)
        bf.pack(pady=8)
        tk.Button(bf, text="📋 复制错误详情", command=copy_err, bg="#5A6B7B", fg="white",
                  font=("微软雅黑", 11), padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="关闭", command=w.destroy, font=("微软雅黑", 11),
                  padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        w.transient(root)
        try:
            w.grab_set()
        except Exception:
            pass
        w.update_idletasks()
        w.geometry(f"+{root.winfo_x()+180}+{root.winfo_y()+140}")

    def do_generate():
        cfg.last_f1 = entry_vars["f1"].get().strip() or None
        cfg.last_d1 = entry_vars["d1"].get().strip() or None
        cfg.last_f2 = entry_vars["f2"].get().strip() or None
        cfg.last_d2 = entry_vars["d2"].get().strip() or None
        cfg.scan_dir = scan_dir_var.get()
        if not (cfg.last_f1 or cfg.last_d1) or not (cfg.last_f2 or cfg.last_d2):
            messagebox.showwarning("缺少文件", "请至少选择「较早月」和「较新月」各一个食品/饮料文件再生成。")
            return
        out_dir = out_dir_var.get().strip() or DEFAULT_OUTPUT_DIR
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        # 月份从年/月框读取（与 do_smart_match 保持同一套逻辑）
        m1_ym = y1_var.get() * 100 + m1_var.get()
        m2_ym = y2_var.get() * 100 + m2_var.get()
        m1l = f"{m1_ym % 100}月"
        m2l = f"{m2_ym % 100}月"
        # 若月份顺序反了，文件名按实际「较早 vs 较新」命名（生成时会自动对调数据）
        if m1_ym > m2_ym:
            m1l, m2l = m2l, m1l
        out = os.path.join(out_dir, f"云南达利积压分析_{APP_VERSION}_{m1l}vs{m2l}_{ts}.pptx")
        try:
            t0 = time.time()
            generate_ppt(cfg.last_f1, cfg.last_d1, cfg.last_f2, cfg.last_d2, out=out)
            cfg.last_output = out
            cfg.save()
            elapsed = time.time() - t0
            n_slides = len(Presentation(out).slides)
            show_success_window(out, elapsed, n_slides)
            if auto_open_var.get():
                try:
                    os.startfile(out)
                except Exception:
                    pass
        except Exception:
            logger.exception("生成失败")
            show_error_window(traceback.format_exc())

    def do_smart_match(silent=False):
        cfg.scan_dir = scan_dir_var.get()
        dirs = _collect_dirs()
        # 目标月对 = 年/月框当前值（v1.9 的坑：这里若不做反序处理，会静默换成别的月对）
        m1_ym = y1_var.get() * 100 + m1_var.get()
        m2_ym = y2_var.get() * 100 + m2_var.get()
        if m1_ym == m2_ym:
            messagebox.showwarning("月份没选对", f"「较早月」和「较新月」是同一个月：{m1_ym} 年 {m1_ym % 100} 月")
            return
        if m2_ym < m1_ym:
            _old1, _old2 = (y1_var.get(), m1_var.get()), (y2_var.get(), m2_var.get())
            y1_var.set(_old2[0]); m1_var.set(_old2[1])
            y2_var.set(_old1[0]); m2_var.set(_old1[1])
            m1_ym, m2_ym = m2_ym, m1_ym
            logger.info(f"月份顺序反了，已自动对调为 {m1_ym} → {m2_ym}")
        result = match_files_for_months(dirs, m1_ym, m2_ym)
        logger.info(f"智能匹配(按对比月份 {m1_ym}→{m2_ym})  {result.matched_count}/4")
        # 回退到 config 已有路径
        if result.f1 is None and cfg.last_f1: result.f1 = cfg.last_f1
        if result.d1 is None and cfg.last_d1: result.d1 = cfg.last_d1
        if result.f2 is None and cfg.last_f2: result.f2 = cfg.last_f2
        if result.d2 is None and cfg.last_d2: result.d2 = cfg.last_d2
        if result.f1: entry_vars["f1"].set(result.f1)
        if result.d1: entry_vars["d1"].set(result.d1)
        if result.f2: entry_vars["f2"].set(result.f2)
        if result.d2: entry_vars["d2"].set(result.d2)
        refresh_months()
        refresh_month_lists()
        if silent:
            return
        msg = ""
        if m1_ym is not None:
            msg += f"按对比月份：{m1_ym} → {m2_ym}\n"
        msg += f"匹配 {result.matched_count}/4\n"
        if result.f1: msg += f"  较早月食品: {os.path.basename(result.f1)}\n"
        if result.d1: msg += f"  较早月饮料: {os.path.basename(result.d1)}\n"
        if result.f2: msg += f"  较新月食品: {os.path.basename(result.f2)}\n"
        if result.d2: msg += f"  较新月饮料: {os.path.basename(result.d2)}\n"
        msg += "实际扫描目录:\n" + "\n".join(f"  - {d}" for d in dirs)
        msg += "\n排除词: 仓库/包装/原料/辅材/主辅/明细/主料/辅料/内包装/外包装/副本/改"
        messagebox.showinfo("智能匹配结果", msg)

    btn_frame = tk.Frame(root, pady=14)
    btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
    tk.Button(btn_frame, text="🔄 刷新月份（回最近两月）", command=lambda: refresh_month_lists(True),
              font=("微软雅黑", 11), bg="#1F7A3D", fg="white", padx=18, pady=6).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="🔍 智能匹配 (Ctrl+M)", command=do_smart_match,
              font=("微软雅黑", 11), bg="#1F3A5F", fg="white", padx=18, pady=6).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="▶ 生成 PPT (Ctrl+G)", command=do_generate,
              font=("微软雅黑", 11), bg="#003366", fg="white", padx=18, pady=6).pack(side=tk.LEFT, padx=10)

    root.bind("<Control-g>", lambda e: do_generate())
    root.bind("<Control-G>", lambda e: do_generate())
    root.bind("<Control-m>", lambda e: do_smart_match())
    root.bind("<Control-M>", lambda e: do_smart_match())

    refresh_month_lists(True)   # 启动：年/月框自动跳到最近两个实际存在的月
    refresh_months()
    root.mainloop()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--f1", default=None)
    parser.add_argument("--d1", default=None)
    parser.add_argument("--f2", default=None)
    parser.add_argument("--d2", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()

    if args.gui or len(sys.argv) == 1:
        run_gui()
    else:
        cfg = AppConfig.load()
        f1 = args.f1 or cfg.last_f1
        d1 = args.d1 or cfg.last_d1
        f2 = args.f2 or cfg.last_f2
        d2 = args.d2 or cfg.last_d2
        # 月份自动识别（不写死）
        m1l = parse_month_from_filename(f1) if f1 else "月1"
        m2l = parse_month_from_filename(f2) if f2 else "月2"
        out = args.out or os.path.join(DEFAULT_OUTPUT_DIR,
                                       f"云南达利积压分析_{APP_VERSION}_{m1l}vs{m2l}.pptx")
        generate_ppt(f1, d1, f2, d2, out=out)
