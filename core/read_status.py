# -*- coding: utf-8 -*-
"""
已读/未读状态管理 + 偏差变动历史记录
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

    # 已读状态表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS read_status (
            data_id TEXT PRIMARY KEY,
            is_read INTEGER DEFAULT 0,
            fingerprint TEXT,
            read_time TIMESTAMP,
            user TEXT DEFAULT 'default'
        )
    """)

    # 偏差变动历史表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deviation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_id TEXT NOT NULL,
            old_amount REAL,
            new_amount REAL,
            old_rate REAL,
            new_rate REAL,
            change_time TIMESTAMP,
            change_reason TEXT
        )
    """)

    return conn

def init_db():
    """初始化数据库（供外部调用）"""
    conn = _get_conn()
    conn.close()

def load_read_status(data_ids: List[str]) -> Dict[str, Tuple[int, str]]:
    """
    批量加载已读状态
    返回: {data_id: (is_read, fingerprint)}
    """
    if not data_ids:
        return {}

    conn = _get_conn()
    placeholders = ','.join(['?' for _ in data_ids])
    cur = conn.execute(
        f"SELECT data_id, is_read, fingerprint FROM read_status WHERE data_id IN ({placeholders})",
        data_ids
    )
    result = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    conn.close()
    return result

def save_read_status(data_id: str, is_read: int, fingerprint: str):
    """保存已读状态"""
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO read_status (data_id, is_read, fingerprint, read_time, user)
        VALUES (?, ?, ?, ?, ?)
    """, (str(data_id), int(is_read), str(fingerprint), datetime.now().isoformat(), 'default'))
    conn.commit()
    conn.close()

def record_deviation_change(data_id: str, old_amount: float, new_amount: float,
                            old_rate: float, new_rate: float, reason: str = "重新分析"):
    """记录偏差变动历史"""
    conn = _get_conn()
    conn.execute("""
        INSERT INTO deviation_history (data_id, old_amount, new_amount, old_rate, new_rate, change_time, change_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (data_id, old_amount, new_amount, old_rate, new_rate, datetime.now().isoformat(), reason))
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

    columns = ['id', 'data_id', 'old_amount', 'new_amount', 'old_rate', 'new_rate', 'change_time', 'change_reason']
    result = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return result
