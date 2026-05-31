# -*- coding: utf-8 -*-
"""轻量操作日志 - 记录关键用户操作（下钻、导入导出等），90天自动清理"""
import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Any


class OperationLogger:
    """轻量操作日志，单例模式"""
    _instance = None

    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path=None):
        if self._initialized:
            return
        self._initialized = True
        self.db_path = db_path or os.path.expanduser('~/.zpp011_audit/operation_log.db')
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    details TEXT,
                    level TEXT DEFAULT 'info'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_op_timestamp ON logs(timestamp)")
            # 清理 90 天前的日志 [Trae·增强]
            cutoff = (datetime.now() - timedelta(days=90)).isoformat()
            conn.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))

    def log(self, operation: str, details: Any = None, level: str = 'info'):
        """记录操作日志
        
        Args:
            operation: 操作类型，如 'drill_down', 'view_export', 'view_import'
            details: 操作详情（会被截断到500字符）
            level: 日志级别 info/warn/error
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO logs (timestamp, operation, details, level)
                    VALUES (?, ?, ?, ?)
                """, (datetime.now().isoformat(), operation, str(details)[:500], level))
        except Exception:
            pass  # 日志写入失败不应影响主流程

    def query(self, operation: Optional[str] = None, days: int = 7,
              limit: int = 100) -> list:
        """查询操作日志
        
        Args:
            operation: 筛选操作类型，None 表示全部
            days: 查询最近 N 天
            limit: 最大返回条数
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if operation:
                rows = conn.execute(
                    "SELECT * FROM logs WHERE timestamp >= ? AND operation = ? ORDER BY timestamp DESC LIMIT ?",
                    (cutoff, operation, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM logs WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?",
                    (cutoff, limit)
                ).fetchall()
        return [dict(r) for r in rows]

    def cleanup(self, days: int = 90):
        """手动清理 N 天前的日志"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            deleted = conn.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,)).rowcount
        return deleted
