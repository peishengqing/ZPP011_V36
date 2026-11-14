# -*- coding: utf-8 -*-
"""跨月偏差归档表持久化（SQLite）。

裴哥 2026-11-14 · 跨月趋势对比功能地基

落库位置 ~/.zpp011_audit/monthly_archive.db（独立库，不挤 audit.db）。
表 monthly_deviation_archive：一行 = 工厂×物料×业务月，字段见 core/monthly_archive.py。

连接约定照抄 core/read_status.py：主线程进程级单例 + 子线程 threading.local 独立连接，
WAL + NORMAL synchronous，消除跨线程 sqlite 内部竞争。

回填策略（upsert）：同一 (factory, material_code, biz_month) 重复回填时覆盖，
保证「再点一次刷新」幂等 —— 源文件增量导出只会更全，覆盖即取最新口径。
"""
import os
import sqlite3
import threading
from typing import Dict, List

DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "monthly_archive.db")

_CONN = None
_DDL_DONE = False
_CONN_LOCK = threading.Lock()
_THREAD_CONNS = threading.local()

_DDL = """
CREATE TABLE IF NOT EXISTS monthly_deviation_archive (
    factory        TEXT NOT NULL,
    material_code  TEXT NOT NULL,
    biz_month      TEXT NOT NULL,
    material_name  TEXT,
    period_dev     REAL NOT NULL DEFAULT 0,
    peak_dev       REAL NOT NULL DEFAULT 0,
    corrected      INTEGER NOT NULL DEFAULT 0,
    file_count     INTEGER NOT NULL DEFAULT 0,
    last_file      TEXT,
    PRIMARY KEY (factory, material_code, biz_month)
);
CREATE INDEX IF NOT EXISTS idx_ma_material ON monthly_deviation_archive(material_code);
CREATE INDEX IF NOT EXISTS idx_ma_month    ON monthly_deviation_archive(biz_month);
"""


def _get_conn():
    """主线程单例 / 子线程独立连接（同 read_status._get_conn 的设计）。"""
    if threading.current_thread() is not threading.main_thread():
        conn = getattr(_THREAD_CONNS, "conn", None)
        if conn is not None:
            return conn
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-16384")
        except sqlite3.Error:
            pass
        _init_db(conn)
        _THREAD_CONNS.conn = conn
        return conn

    global _CONN, _DDL_DONE
    if _CONN is not None and _DDL_DONE:
        return _CONN
    with _CONN_LOCK:
        if _CONN is not None and _DDL_DONE:
            return _CONN
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _CONN = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            _CONN.execute("PRAGMA journal_mode=WAL")
            _CONN.execute("PRAGMA synchronous=NORMAL")
            _CONN.execute("PRAGMA cache_size=-16384")
        except sqlite3.Error:
            pass
        _init_db(_CONN)
        _DDL_DONE = True
        return _CONN


def _init_db(conn):
    """建表 + 索引（幂等）。"""
    conn.executescript(_DDL)
    conn.commit()


def save_archive(rows: List[Dict]) -> int:
    """把聚合行 upsert 进归档表，返回写入行数。

    rows 为 aggregate_file_snapshots().values()（见 core/monthly_archive.py）。
    INSERT OR REPLACE：同主键覆盖，回填幂等。
    """
    if not rows:
        return 0
    conn = _get_conn()
    data = [
        (r.get("factory", ""), r.get("material_code", ""), r.get("biz_month", ""),
         r.get("material_name", ""), float(r.get("period_dev", 0.0)),
         float(r.get("peak_dev", 0.0)), int(r.get("corrected", 0)),
         int(r.get("file_count", 0)), r.get("last_file", ""))
        for r in rows
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO monthly_deviation_archive "
        "(factory, material_code, biz_month, material_name, period_dev, peak_dev, "
        " corrected, file_count, last_file) VALUES (?,?,?,?,?,?,?,?,?)",
        data,
    )
    conn.commit()
    return len(data)


def load_archive(factory: str = "", material_keyword: str = "") -> List[Dict]:
    """读归档表，可按工厂/物料名关键字过滤（物料名模糊匹配，方便看板挑物料）。

    返回按 biz_month 升序的行列表。
    """
    conn = _get_conn()
    sql = ("SELECT factory, material_code, material_name, biz_month, period_dev, "
           "peak_dev, corrected, file_count, last_file FROM monthly_deviation_archive")
    conds, params = [], []
    if factory:
        conds.append("factory = ?")
        params.append(factory)
    if material_keyword:
        # 名称或编码模糊匹配（看板搜「黄原胶」「10001119」都能中）
        conds.append("(material_name LIKE ? OR material_code LIKE ?)")
        kw = f"%{material_keyword}%"
        params.extend([kw, kw])
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY material_code, biz_month"
    out = []
    for row in conn.execute(sql, params):
        out.append({
            "factory": row[0], "material_code": row[1], "material_name": row[2],
            "biz_month": row[3], "period_dev": row[4], "peak_dev": row[5],
            "corrected": row[6], "file_count": row[7], "last_file": row[8],
        })
    return out


def list_factories() -> List[str]:
    """归档表里出现过的工厂列表（看板顶部切换用）。"""
    conn = _get_conn()
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT factory FROM monthly_deviation_archive "
        "WHERE factory != '' ORDER BY factory")]


def list_materials(factory: str = "") -> List[Dict]:
    """物料清单（去重），看板物料选择器用。含最近业务月与累计峰值，便于排序找重点。"""
    conn = _get_conn()
    where = "WHERE factory = ?" if factory else ""
    params = [factory] if factory else []
    sql = (
        "SELECT material_code, MAX(material_name) AS name, COUNT(DISTINCT biz_month) AS months, "
        "MAX(peak_dev) AS max_peak, MAX(biz_month) AS last_month "
        f"FROM monthly_deviation_archive {where} "
        "GROUP BY material_code ORDER BY max_peak DESC"
    )
    return [{"material_code": r[0], "material_name": r[1], "months": r[2],
             "max_peak": r[3], "last_month": r[4]} for r in conn.execute(sql, params)]


def archive_stats() -> Dict:
    """归档概况：总行数、覆盖月份数、被修正行数（看板副标题/健康度用）。"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT biz_month), "
        "COALESCE(SUM(corrected),0), MIN(biz_month), MAX(biz_month) "
        "FROM monthly_deviation_archive")
    r = cur.fetchone()
    return {"rows": r[0] or 0, "months": r[1] or 0, "corrected": r[2] or 0,
            "first_month": r[3] or "", "last_month": r[4] or ""}