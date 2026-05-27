# -*- coding: utf-8 -*-
"""
AuditLogger — 操作审计日志（非阻塞队列 + 异步 CSV 导出）

设计要点：
- 队列满时直接写降级文件 audit_fallback.log，不阻塞调用线程
- 导出 CSV 使用异步线程 + 分页查询，避免 UI 冻结
- 不修改 storage.py（冷冻区）
"""
import os
import json
import queue
import threading
import csv
import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path

_DEFAULT_DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit_log.db")
_FALLBACK_PATH = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "ZPP011", "audit_fallback.log")
_QUEUE_SIZE = 5000
_BATCH_SIZE = 100


class AuditLogger:
    """
    操作审计日志。

    用法：
        logger = AuditLogger()
        logger.log("save_audit", material_code="ABC123", old_value="", new_value="已备注")
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self.queue = queue.Queue(maxsize=_QUEUE_SIZE)
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        self._ensure_db()

    # ── 公共 API ──────────────────────────────────────────────────────

    def log(self, action: str, material_code: str = None,
             old_value: str = None, new_value: str = None,
             source: str = "manual", extra: dict = None):
        """
        记录一条审计日志（非阻塞）。
        队列满时写降级文件，不抛异常。
        """
        import getpass
        username = getpass.getuser()
        timestamp = datetime.now().isoformat(timespec="seconds")

        try:
            self.queue.put_nowait((
                timestamp, username, material_code or "",
                action, old_value or "", new_value or "",
                source, json.dumps(extra, ensure_ascii=False) if extra else None
            ))
        except queue.Full:
            # 队列满：直接写降级文件（不阻塞）
            try:
                fallback_dir = os.path.dirname(_FALLBACK_PATH)
                os.makedirs(fallback_dir, exist_ok=True)
                with open(_FALLBACK_PATH, "a", encoding="utf-8") as f:
                    f.write(
                        f"{timestamp},{username},"
                        f"{material_code or ''},{action},"
                        f"{old_value or ''},{new_value or ''},"
                        f"{source},{extra or ''}\n"
                    )
            except Exception:
                pass

    def export_csv_async(self, output_path: str, callback=None):
        """
        异步导出审计日志到 CSV。
        使用分页查询避免内存爆炸。
        完成后调用 callback(output_path, error)。
        """
        def task():
            error = None
            try:
                self._export_csv_paginated(output_path)
            except Exception as e:
                error = e
            if callback:
                # 切回主线程调用回调（tkinter 安全）
                try:
                    root = tk._default_root
                    if root:
                        root.after(0, lambda: callback(output_path, error))
                    else:
                        callback(output_path, error)
                except Exception:
                    callback(output_path, error)

        threading.Thread(target=task, daemon=True).start()

    def get_stats(self) -> dict:
        """返回统计信息（供健康检查用）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
                return {"total": total, "db_path": self.db_path, "ok": True}
        except Exception as e:
            return {"total": 0, "error": str(e), "ok": False}

    def shutdown(self):
        """优雅关闭（写入剩余队列）。"""
        self._stop_event.set()
        self._worker_thread.join(timeout=5)

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _ensure_db(self):
        """确保 audit_log 表存在。"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    timestamp     TEXT NOT NULL,
                    username      TEXT NOT NULL,
                    material_code TEXT,
                    action        TEXT NOT NULL,
                    old_value     TEXT,
                    new_value     TEXT,
                    source        TEXT,
                    extra         TEXT
                )
            """)
            conn.commit()

    def _worker(self):
        """
        后台线程：从队列取日志批量写入 DB。
        每次最多取 _BATCH_SIZE 条，减少提交次数。
        """
        batch = []
        while not self._stop_event.is_set() or not self.queue.empty():
            try:
                record = self.queue.get(timeout=1)
                batch.append(record)
                if len(batch) >= _BATCH_SIZE:
                    self._flush(batch)
                    batch = []
            except queue.Empty:
                if batch:
                    self._flush(batch)
                    batch = []
        # 退出前刷完
        if batch:
            self._flush(batch)

    def _flush(self, batch: list):
        """批量写入一条 SQL。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    """INSERT INTO audit_log
                       (timestamp, username, material_code, action,
                        old_value, new_value, source, extra)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    batch
                )
                conn.commit()
        except Exception:
            pass

    def _export_csv_paginated(self, output_path: str):
        """
        分页导出 CSV（避免大表撑爆内存）。
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

        page_size = 5000
        header_written = False

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            for offset in range(0, total, page_size):
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        "SELECT * FROM audit_log ORDER BY timestamp LIMIT ? OFFSET ?",
                        (page_size, offset)
                    ).fetchall()
                if not header_written and rows:
                    writer.writerow(rows[0].keys())
                    header_written = True
                for row in rows:
                    writer.writerow(tuple(row))
