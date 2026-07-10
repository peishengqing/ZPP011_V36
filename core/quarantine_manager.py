# -*- coding: utf-8 -*-
"""
隔离区状态管理
使用 SQLite 持久化存储（与 read_status 共用同一数据库文件）

设计核心：引用模式
- 只存 data_id（即 uid），不存数据副本
- 隔离行的实际数量/状态实时从主表读取
- 因此主表某行被改（如 实际数量 500 -> 550）后重新导入，隔离区记录自动同步，无需额外代码
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Set

from core.read_status import DB_PATH


def _get_conn():
    """获取数据库连接，自动创建隔离区表结构（与 read_status 共用同一 DB 文件）"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quarantine_records (
            uid TEXT PRIMARY KEY,
            reason TEXT DEFAULT '',
            quarantined_at TIMESTAMP,
            restored_at TIMESTAMP NULL
        )
    """)
    return conn


def add_quarantine(uid: str, reason: str = ""):
    """将一条记录移入隔离区（uid 即 data_id）。已存在则刷新为活跃状态。"""
    conn = _get_conn()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO quarantine_records (uid, reason, quarantined_at, restored_at)
        VALUES (?, ?, ?, NULL)
        ON CONFLICT(uid) DO UPDATE SET
            reason=excluded.reason,
            quarantined_at=excluded.quarantined_at,
            restored_at=NULL
    """, (str(uid), str(reason), now))
    conn.commit()
    conn.close()


def remove_quarantine(uid: str):
    """将一条记录移出隔离区（软删除：记录恢复时间，便于追溯）"""
    conn = _get_conn()
    conn.execute(
        "UPDATE quarantine_records SET restored_at = ? WHERE uid = ?",
        (datetime.now().isoformat(), str(uid))
    )
    conn.commit()
    conn.close()


def is_quarantined(uid: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT 1 FROM quarantine_records WHERE uid = ? AND restored_at IS NULL",
        (str(uid),)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_quarantined_ids() -> Set[str]:
    """返回当前处于隔离区（未恢复）的 uid 集合，供数据加载时水合 _quarantined 列"""
    conn = _get_conn()
    cur = conn.execute("SELECT uid FROM quarantine_records WHERE restored_at IS NULL")
    result = {row[0] for row in cur.fetchall()}
    conn.close()
    return result


def get_quarantine_records() -> List[Dict]:
    """返回当前隔离区明细（供弹窗展示），含 reason / quarantined_at"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT uid, reason, quarantined_at FROM quarantine_records "
        "WHERE restored_at IS NULL ORDER BY quarantined_at DESC"
    )
    columns = ['uid', 'reason', 'quarantined_at']
    result = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return result
