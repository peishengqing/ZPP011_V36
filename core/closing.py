# -*- coding: utf-8 -*-
"""D4 月报关账：按月粒度的关账状态机（纯逻辑，无 PyQt，可 offscreen 单测）。

关账规则（2026-11-06 裴哥拍板）：
  - 关账人：裴哥本人手动点「关账」（不自动、不需上级审批）。
  - 关账条件：该月所有「未完结」偏差都完结（未完结订单数 == 0）才允许关；否则按钮禁用并提示剩余未完结数。
  - 关账后：锁定不可改；事后要改走「修订版」另出一份（原定稿保留）。

状态机（按月 month='YYYY-MM'）：
  draft  —— 未关账，可多次导出「草稿 v1/v2/v3...」（标「数据未关账可能变动」）
  closed —— 已关账，导出即为「定稿」
  revised —— 定稿后再次导出，走「修订版 v1/v2...」

状态落在 audit.db 的 closing_status 表（与 read_status/quarantine_records 同库）。
GUI 侧按钮在 gui_pyside6/utils/change_summary_panel.py。
"""
import sqlite3
import datetime
from typing import Dict, List, Optional, Tuple

from core.read_status import DB_PATH
import core.snapshot as snapshot
import pandas as pd


# ----------------------------------------------------------------------------
# DB / schema
# ----------------------------------------------------------------------------
def _ensure_table() -> None:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS closing_status ("
        " month TEXT PRIMARY KEY,"
        " status TEXT NOT NULL DEFAULT 'draft',"   # draft | closed | revised
        " closed_at TEXT,"
        " closed_by TEXT,"
        " final_pdf TEXT,"
        " last_pdf TEXT,"
        " draft_count INTEGER NOT NULL DEFAULT 0,"
        " revised_count INTEGER NOT NULL DEFAULT 0"
        ")")
    conn.commit()
    conn.close()


def _connect() -> sqlite3.Connection:
    _ensure_table()
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# ----------------------------------------------------------------------------
# 月份工具
# ----------------------------------------------------------------------------
def _month_of(value) -> Optional[str]:
    try:
        d = pd.to_datetime(value, errors="coerce")
        if pd.isna(d):
            return None
        return d.strftime("%Y-%m")
    except Exception:
        return None


def months_in_df(df: pd.DataFrame) -> List[str]:
    """返回主表订单日期覆盖的去重月份列表（升序，'YYYY-MM'）。"""
    if df is None or len(df) == 0 or "订单日期" not in df.columns:
        return []
    dts = pd.to_datetime(df["订单日期"], errors="coerce").dropna()
    if len(dts) == 0:
        return []
    return sorted({d.strftime("%Y-%m") for d in dts})


def _filter_month(df: pd.DataFrame, month: str) -> pd.DataFrame:
    if df is None or "订单日期" not in df.columns:
        return df if df is not None else pd.DataFrame()
    mask = df["订单日期"].apply(lambda v: _month_of(v) == month)
    return df[mask]


# ----------------------------------------------------------------------------
# 状态读写
# ----------------------------------------------------------------------------
def get_status(month: str) -> Dict:
    conn = _connect()
    row = conn.execute(
        "SELECT status, closed_at, closed_by, final_pdf, last_pdf, draft_count, revised_count "
        "FROM closing_status WHERE month=?", (month,)).fetchone()
    conn.close()
    if row is None:
        return {"status": "draft", "closed_at": None, "closed_by": None,
                "final_pdf": None, "last_pdf": None,
                "draft_count": 0, "revised_count": 0}
    return {"status": row[0], "closed_at": row[1], "closed_by": row[2],
            "final_pdf": row[3], "last_pdf": row[4],
            "draft_count": row[5] or 0, "revised_count": row[6] or 0}


def _upsert(month: str, **fields) -> None:
    conn = _connect()
    exists = conn.execute(
        "SELECT month FROM closing_status WHERE month=?", (month,)).fetchone()
    if exists:
        sets = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE closing_status SET {sets} WHERE month=?",
                     list(fields.values()) + [month])
    else:
        cols = ["month"] + list(fields.keys())
        ph = ", ".join(["?"] * len(cols))
        conn.execute(f"INSERT INTO closing_status ({', '.join(cols)}) VALUES ({ph})",
                     [month] + list(fields.values()))
    conn.commit()
    conn.close()


def can_close(df: pd.DataFrame, month: str) -> Tuple[bool, str]:
    """未完结清零才允许关账（复用 D1 compute_unfinished 口径）。"""
    sub = _filter_month(df, month)
    unf = snapshot.compute_unfinished(sub)
    n = unf["unfinished_orders"]
    if n == 0:
        return True, ""
    return False, f"本月还有 {n} 个未完结订单，无法关账（须未完结清零）"


def record_draft_export(month: str, pdf: str) -> int:
    st = get_status(month)
    n = st["draft_count"] + 1
    _upsert(month, status="draft", last_pdf=pdf, draft_count=n)
    return n


def record_revised_export(month: str, pdf: str) -> int:
    st = get_status(month)
    n = st["revised_count"] + 1
    _upsert(month, status="revised", last_pdf=pdf, revised_count=n)
    return n


def close_month(month: str, by: str, final_pdf: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    _upsert(month, status="closed", closed_at=now, closed_by=by,
            final_pdf=final_pdf, last_pdf=final_pdf)


def next_label(month: str, force_final: bool = False) -> str:
    """预览下一次导出会得到的标注（草稿/定稿/修订版），用于默认文件名。"""
    st = get_status(month)
    if force_final:
        return "定稿"
    if st["status"] == "closed":
        return f"修订版 v{st['revised_count'] + 1}"
    return f"草稿 v{st['draft_count'] + 1}"
