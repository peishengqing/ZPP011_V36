import sqlite3, threading, queue, json, csv, time, getpass, os
from datetime import datetime, timedelta

def _get_default_db_path():
    """返回 ~/.zpp011_audit/audit_log.db，确保目录存在"""
    app_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "audit_log.db")


class AuditLogger:
    def __init__(self, db_path=None, max_queue_size=1000):
        self.db_path = db_path or _get_default_db_path()
        self._app_dir = os.path.dirname(self.db_path)
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()
        self._init_db()
        self._cleanup_old_logs()

    def _init_db(self):
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    username TEXT NOT NULL,
                    material_code TEXT,
                    action TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    source TEXT,
                    extra TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)")

    def _cleanup_old_logs(self, days=180):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))

    def _worker(self):
        while True:
            item = self.queue.get()
            if item is None:
                break
            try:
                with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                    conn.execute("""
                        INSERT INTO audit_log (timestamp, username, material_code, action, old_value, new_value, source, extra)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, item)
            except Exception as e:
                fallback = os.path.join(self._app_dir, "audit_fallback.log")
                with open(fallback, "a") as f:
                    f.write(f"{item} | error: {e}\n")

    def log(self, action, material_code=None, old_value=None, new_value=None, source='manual', extra=None):
        username = getpass.getuser()
        timestamp = datetime.now().isoformat()
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
        try:
            self.queue.put_nowait((timestamp, username, material_code, action, old_value, new_value, source, extra_json))
        except queue.Full:
            fallback = os.path.join(self._app_dir, "audit_fallback.log")
            with open(fallback, "a", encoding='utf-8') as f:
                f.write(f"{timestamp},{username},{material_code},{action},{old_value},{new_value},{source},{extra_json}\n")

    def shutdown(self):
        self.queue.put(None)
        self.worker.join()

    def export_csv_async(self, output_path, callback=None):
        """异步导出，避免 UI 卡顿"""
        def task():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
                page_size = 5000
                with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    header_written = False
                    for offset in range(0, total, page_size):
                        rows = conn.execute("SELECT * FROM audit_log ORDER BY timestamp LIMIT ? OFFSET ?", (page_size, offset)).fetchall()
                        if not header_written and rows:
                            writer.writerow(rows[0].keys())
                            header_written = True
                        writer.writerows([tuple(row) for row in rows])
            if callback:
                callback(output_path, None)
        threading.Thread(target=task, daemon=True).start()
