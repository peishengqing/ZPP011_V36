# -*- coding: utf-8 -*-
"""跨月偏差归档 + 趋势聚合（纯逻辑，无 PyQt，可 offscreen 单测）。

裴哥 2026-11-14 · 跨月趋势对比功能地基

为什么直读源文件、不反推：
  deviation_history 记的是「实际数量」的逐次变动（且每次重导文件会重复记账，
  实测重复膨胀 2.18 倍），本身不含偏差值（偏差=定额-实际，定额不在库里）。
  而 ZPP011 源 Excel 本身就是一次完整快照、自带「材料偏差」列 —— 同一订单在
  9 月文件偏差 10、10 月文件偏差 0，趋势直接可读，零反推、零脏数据。

数据模型（归档表 monthly_deviation_archive，一行 = 工厂×物料×业务月）：
  factory        工厂（data_id 第 1 段，缺失归空）
  material_code  组件物料号（data_id 末段）
  material_name  物料名（material_names 缓存，可空）
  biz_month      业务月 YYYY-MM（取 data_id 里订单日期，非文件导出时间）
  period_dev     期末偏差：该月**最新一个文件**里此物料偏差合计
  peak_dev       峰值偏差：该月**所有文件**里此物料偏差合计的最大绝对值
  corrected      被修正标志：峰值非 0 但期末为 0（黄原胶式补投归零）
  file_count     该月纳入几个文件
  last_file      期末取自哪个文件

口径要点：
  - 归月用 data_id 里的**订单日期**（业务月），绝不用文件导出时间 —— 9 月订单
    即使在 10 月补投，仍归 9 月（裴哥「9 月不止 1004」教训）。
  - 只看偏差 ≠ 0 的行参与合计；偏差列解析失败的行跳过并计数。
"""
import os
import re
from typing import Dict, List, Optional, Tuple

# 源文件名形如 ZPP011_20261101-20261114.xlsx / ZPP011_20260601-20260630.xlsx
_FILE_RE = re.compile(r"ZPP011_(\d{8})-(\d{8})", re.IGNORECASE)
# data_id 形如 工厂|2026-09-07|流程订单|物料编码（工厂段可能缺）
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

# 源 Excel 关键列名（按列名定位，不写死列序，避免导出模板微调后错位）
_COL_FACTORY = "工厂"
_COL_ORDER_DATE = "订单开始日期"
_COL_ORDER_NO = "流程订单"
_COL_MAT_CODE = "组件物料号"
_COL_MAT_DESC = "组件物料描述"
_COL_DEVIATION = "材料偏差"


def read_file_snapshot(path: str, month: Optional[str] = None) -> Dict:
    """读一个 ZPP011 源 Excel，解析成 aggregate_file_snapshots 要的快照结构。

    返回 {"file": 路径, "month": 业务月, "rows": [...], "skipped": 跳过行数}。
    rows 每元素：{factory, material_code, material_name, order_no, biz_month, deviation}。
      biz_month 取行内「订单开始日期」（业务月，最准），缺失时回退入参 month。
    month 缺省时用文件名起始日的年月（parse 不到则为 None，靠行内日期兜）。

    只用 openpyxl read_only 顺读一遍，几十 MB 文件也是秒级；解析失败的偏差行
    计入 skipped，不参与合计（避免脏数据污染趋势）。
    """
    import openpyxl  # 延迟导入：核心模块不强制依赖 Excel 库，按需加载

    rows: List[Dict] = []
    skipped = 0
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = next(it, None)
        if not header:
            return {"file": path, "month": month, "rows": [], "skipped": 0}
        # 列名 -> 索引（去空格，容错）
        idx = {str(h).strip(): i for i, h in enumerate(header) if h is not None}
        need = (_COL_FACTORY, _COL_ORDER_DATE, _COL_MAT_CODE, _COL_DEVIATION)
        if any(c not in idx for c in need):
            # 表头缺关键列（非标准导出），整文件跳过
            return {"file": path, "month": month, "rows": [], "skipped": 0}
        i_fac = idx[_COL_FACTORY]
        i_date = idx.get(_COL_ORDER_DATE)
        i_ono = idx.get(_COL_ORDER_NO)
        i_code = idx[_COL_MAT_CODE]
        i_desc = idx.get(_COL_MAT_DESC)
        i_dev = idx[_COL_DEVIATION]
        for r in it:
            code = r[i_code] if i_code is not None and i_code < len(r) else None
            if code is None or str(code).strip() == "":
                continue
            dev_raw = r[i_dev] if i_dev < len(r) else None
            if dev_raw is None or str(dev_raw).strip() == "":
                skipped += 1
                continue
            # 行内业务月：订单开始日期（如 2026-09-04 00:00 → 2026-09）
            row_month = month
            if i_date is not None and i_date < len(r):
                m = _DATE_RE.search(str(r[i_date] or ""))
                if m:
                    row_month = f"{m.group(1)}-{m.group(2)}"
            factory = str(r[i_fac]).strip() if i_fac < len(r) and r[i_fac] is not None else ""
            ono = str(r[i_ono]).strip() if (i_ono is not None and i_ono < len(r) and r[i_ono] is not None) else ""
            desc = str(r[i_desc]).strip() if (i_desc is not None and i_desc < len(r) and r[i_desc] is not None) else ""
            rows.append({
                "factory": factory,
                "material_code": str(code).strip(),
                "material_name": desc,
                "order_no": ono,
                "biz_month": row_month,
                "deviation": _to_float(dev_raw),
            })
    finally:
        wb.close()
    return {"file": path, "month": month, "rows": rows, "skipped": skipped}


def biz_month_of_data_id(data_id: str) -> Optional[str]:
    """从 data_id 取业务月 YYYY-MM（订单日期，非导出时间）。取不到返回 None。"""
    m = _DATE_RE.search(str(data_id or ""))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def parse_file_range(filename: str) -> Optional[Tuple[str, str]]:
    """从文件名解析 (起始日, 结束日)，如 ZPP011_20261101-20261114 → ('20261101','20261114')。

    取不到（非标准命名）返回 None —— 这类文件不参与「选当月最新」。
    """
    m = _FILE_RE.search(os.path.basename(filename or ""))
    return (m.group(1), m.group(2)) if m else None


def biz_month_of_file(filename: str) -> Optional[str]:
    """文件所属业务月 = 起始日的年月（ZPP011_20261101-… → 2026-11）。"""
    rng = parse_file_range(filename)
    if not rng:
        return None
    start = rng[0]
    return f"{start[:4]}-{start[4:6]}"


def pick_latest_file_per_month(files: List[str]) -> Dict[str, str]:
    """每个月只留一个「最新」的文件（结束日最大的），返回 {业务月: 文件路径}。

    6 月有 20260601-20260610 … 20260601-20260630 一串增量导出，趋势只取最全的
    20260630 那个即可（它含整月所有订单）。同结束日取文件名字典序最大兜底。
    """
    best: Dict[str, Tuple[str, str]] = {}  # month -> (结束日, 路径)
    for f in files:
        rng = parse_file_range(f)
        if not rng:
            continue
        month = f"{rng[0][:4]}-{rng[0][4:6]}"
        key = (rng[1], os.path.basename(f))
        if month not in best or key > best[month]:
            best[month] = key
    return {m: best[m][1] for m in sorted(best)}


def aggregate_file_snapshots(
    snapshots: List[Dict],
) -> Dict[Tuple[str, str, str], Dict]:
    """把「多文件 × 多行」快照聚合成 归档表行。

    参数 snapshots：每个元素是一个已解析的文件快照：
        {
          "file": 文件路径,
          "month": 业务月（调用方按文件名或行 data_id 定，见下）,
          "rows": [ {"factory","material_code","biz_month","deviation"}, ... ],
        }
      其中 rows 的 biz_month 优先用**行内 data_id 的订单日期**（最准），
      缺失时回退文件级 month。

    返回 {(factory, material_code, biz_month): 聚合行}。

    聚合规则（承接设计稿）：
      - period_dev：该 (工厂,物料,月) 在**最新文件**（按文件名结束日排序最后）里的偏差合计
      - peak_dev ：该组合在**所有文件**里偏差合计的最大绝对值
      - corrected：peak_dev != 0 且 period_dev == 0
    """
    # (factory, material, month) -> {"per_file": {file: 偏差合计}, "name": 物料名}
    combo: Dict[Tuple[str, str, str], Dict] = {}
    for snap in snapshots:
        fname = snap.get("file", "")
        for row in snap.get("rows", []):
            factory = str(row.get("factory") or "").strip()
            mat = str(row.get("material_code") or "").strip()
            month = str(row.get("biz_month") or snap.get("month") or "").strip()
            if not mat or not month:
                continue
            dev = _to_float(row.get("deviation"))
            key = (factory, mat, month)
            slot = combo.setdefault(
                key, {"per_file": {}, "name": row.get("material_name") or ""}
            )
            if row.get("material_name") and not slot["name"]:
                slot["name"] = row["material_name"]
            slot["per_file"][fname] = slot["per_file"].get(fname, 0.0) + dev

    # 第二遍：按组合出期末/峰值
    out: Dict[Tuple[str, str, str], Dict] = {}
    for (factory, mat, month), slot in combo.items():
        per_file = slot["per_file"]
        if not per_file:
            continue
        # 最新文件 = 文件名结束日最大（parse 不到的排最后，仍可作期末兜底）
        latest_file = max(per_file.keys(), key=lambda f: _sort_key(f))
        period_dev = round(per_file[latest_file], 4)
        peak_dev = round(max(abs(v) for v in per_file.values()), 4)
        out[(factory, mat, month)] = {
            "factory": factory,
            "material_code": mat,
            "material_name": slot["name"],
            "biz_month": month,
            "period_dev": period_dev,
            "peak_dev": peak_dev,
            "corrected": 1 if (peak_dev != 0 and period_dev == 0) else 0,
            "file_count": len(per_file),
            "last_file": os.path.basename(latest_file),
        }
    return out


def month_trend(archive_rows: List[Dict], material_code: str,
                factory: str = "") -> List[Dict]:
    """取某物料（可限定工厂）跨月的趋势序列，按业务月升序。

    返回 [{biz_month, period_dev, peak_dev, corrected}, ...]，给趋势图画线用。
    默认画 peak_dev（盯反复出问题的），可切 period_dev（对账口径）。
    """
    rows = [r for r in archive_rows
            if r.get("material_code") == material_code
            and (not factory or r.get("factory") == factory)]
    rows.sort(key=lambda r: r.get("biz_month") or "")
    return [{"biz_month": r["biz_month"],
             "period_dev": r.get("period_dev", 0.0),
             "peak_dev": r.get("peak_dev", 0.0),
             "corrected": r.get("corrected", 0)} for r in rows]


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------
def _to_float(v) -> float:
    """把偏差单元格转 float；解析失败返回 0.0（调用方另行计数跳过）。"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("%", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _sort_key(filename: str) -> str:
    """文件排序键 = 结束日（取不到用文件名本身，保证稳定）。"""
    rng = parse_file_range(filename)
    return rng[1] if rng else "00000000" + os.path.basename(filename)
