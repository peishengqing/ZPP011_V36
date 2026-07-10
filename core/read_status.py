# -*- coding: utf-8 -*-
"""
已读/未读状态管理 + 审核结果持久化 + 偏差变动历史记录
使用 SQLite 持久化存储
"""
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Tuple


DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit.db")

def _get_conn():
    """获取数据库连接，自动创建表结构"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # 已读状态表（含审核结果）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS read_status (
            data_id TEXT PRIMARY KEY,
            is_read INTEGER DEFAULT 0,
            fingerprint TEXT,
            read_time TIMESTAMP,
            user TEXT DEFAULT 'default'
        )
    """)

    # 自动迁移：添加审核结果列
    _migrate_add_column(conn, 'read_status', 'audit_result', 'TEXT DEFAULT ""')
    _migrate_add_column(conn, 'read_status', 'ai_suggestion', 'TEXT DEFAULT ""')
    _migrate_add_column(conn, 'read_status', 'note_source', 'TEXT DEFAULT ""')
    # 自动迁移：添加实际数量基线列（方案A：审核后变更检测只盯实际数量）
    _migrate_add_column(conn, 'read_status', 'snapshot_qty', 'REAL DEFAULT NULL')

    # 偏差变动历史表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deviation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_id TEXT NOT NULL,
            field TEXT,
            old_qty REAL,
            new_qty REAL,
            old_amount REAL,
            new_amount REAL,
            old_rate REAL,
            new_rate REAL,
            change_time TIMESTAMP,
            change_reason TEXT
        )
    """)

    return conn


def _migrate_add_column(conn, table, col_name, col_def):
    """安全添加列：如果列不存在则 ALTER TABLE ADD COLUMN"""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
    except sqlite3.OperationalError:
        pass  # 列已存在，跳过


def init_db():
    """初始化数据库（供外部调用）"""
    conn = _get_conn()
    conn.close()


# ── 已读状态 ──────────────────────────────────────────

def load_read_status(data_ids: List[str]) -> Dict[str, Tuple]:
    """
    批量加载已读状态
    返回: {data_id: (is_read, fingerprint, snapshot_qty)}
        snapshot_qty 为审核时保存的实际数量基线；None 表示旧记录（基线未初始化）
    """
    if not data_ids:
        return {}

    conn = _get_conn()
    placeholders = ','.join(['?' for _ in data_ids])
    cur = conn.execute(
        f"SELECT data_id, is_read, fingerprint, snapshot_qty FROM read_status WHERE data_id IN ({placeholders})",
        data_ids
    )
    result = {row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()}
    conn.close()
    return result


def save_read_status(data_id: str, is_read: int, fingerprint: str, snapshot_qty=None):
    """保存已读状态（snapshot_qty=审核时实际数量基线，用于方案A变更检测）"""
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO read_status (data_id, is_read, fingerprint, snapshot_qty, read_time, user)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (str(data_id), int(is_read), str(fingerprint),
          None if snapshot_qty is None else float(snapshot_qty),
          datetime.now().isoformat(), 'default'))
    conn.commit()
    conn.close()


def save_read_status_batch(records):
    """
    批量保存已读状态（一次连接、一次提交，避免逐行开库）

    records: [(data_id, is_read, fingerprint)] 或 [(data_id, is_read, fingerprint, snapshot_qty)]
    """
    if not records:
        return
    conn = _get_conn()
    now = datetime.now().isoformat()
    norm = []
    for rec in records:
        did = rec[0]
        is_read = rec[1]
        fp = rec[2] if len(rec) > 2 else ''
        snap = rec[3] if len(rec) > 3 else None
        norm.append((str(did), int(is_read), str(fp),
                     None if snap is None else float(snap), now, 'default'))
    conn.executemany("""
        INSERT OR REPLACE INTO read_status (data_id, is_read, fingerprint, snapshot_qty, read_time, user)
        VALUES (?, ?, ?, ?, ?, ?)
    """, norm)
    conn.commit()
    conn.close()


def save_snapshot_qty(data_id: str, snapshot_qty):
    """延迟初始化/更新实际数量基线（方案A：首次遇到旧记录时用当前数量建立基线）"""
    try:
        conn = _get_conn()
        conn.execute("""
            UPDATE read_status SET snapshot_qty = ? WHERE data_id = ?
        """, (None if snapshot_qty is None else float(snapshot_qty), str(data_id)))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── 审核结果持久化 ─────────────────────────────────────

def load_audit_results(data_ids: List[str]) -> Dict[str, Dict[str, str]]:
    """
    批量加载审核结果
    返回: {data_id: {'audit_result': str, 'ai_suggestion': str, 'note_source': str}}
    """
    if not data_ids:
        return {}

    conn = _get_conn()
    placeholders = ','.join(['?' for _ in data_ids])
    cur = conn.execute(
        f"SELECT data_id, audit_result, ai_suggestion, note_source "
        f"FROM read_status WHERE data_id IN ({placeholders})",
        data_ids
    )
    result = {}
    for row in cur.fetchall():
        did, ar, ai, ns = row
        result[did] = {
            'audit_result': ar or '',
            'ai_suggestion': ai or '',
            'note_source': ns or '',
        }
    conn.close()
    return result


def save_audit_results_batch(records: List[Dict[str, str]]):
    """
    批量保存审核结果
    records: [{'data_id': str, 'audit_result': str, 'ai_suggestion': str, 'note_source': str, 'fingerprint': str}, ...]
    """
    if not records:
        return

    conn = _get_conn()
    now = datetime.now().isoformat()
    for r in records:
        did = str(r.get('data_id', ''))
        if not did:
            continue
        conn.execute("""
            INSERT INTO read_status (data_id, audit_result, ai_suggestion, note_source, fingerprint, read_time, user)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(data_id) DO UPDATE SET
                audit_result=excluded.audit_result,
                ai_suggestion=excluded.ai_suggestion,
                note_source=excluded.note_source,
                fingerprint=COALESCE(excluded.fingerprint, read_status.fingerprint),
                read_time=excluded.read_time
        """, (
            did,
            str(r.get('audit_result', '')),
            str(r.get('ai_suggestion', '')),
            str(r.get('note_source', '')),
            str(r.get('fingerprint', '')),
            now,
            'default',
        ))
    conn.commit()
    conn.close()


# ── 偏差变动历史 ───────────────────────────────────────

def record_deviation_change(data_id: str, field: str, old_qty: float, new_qty: float, reason: str = "审核后数据被修改"):
    """记录审核后/重新分析的数据变动历史（方案A：只盯实际数量）

    field: 变动字段名（如 '实际数量'）
    old_qty/new_qty: 变动前后的实际数量
    """
    conn = _get_conn()
    conn.execute("""
        INSERT INTO deviation_history (data_id, field, old_qty, new_qty, change_time, change_reason)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (str(data_id), str(field), float(old_qty or 0), float(new_qty or 0),
          datetime.now().isoformat(), reason))
    conn.commit()
    conn.close()


def get_deviation_history(data_id: str = None) -> List[Dict]:
    """查询偏差变动历史"""
    conn = _get_conn()
    if data_id:
        cur = conn.execute(
            "SELECT * FROM deviation_history WHERE data_id = ? ORDER BY change_time DESC",
            (data_id,)
        )
    else:
        cur = conn.execute("SELECT * FROM deviation_history ORDER BY change_time DESC LIMIT 100")

    columns = ['id', 'data_id', 'field', 'old_qty', 'new_qty', 'old_amount', 'new_amount', 'old_rate', 'new_rate', 'change_time', 'change_reason']
    result = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return result
