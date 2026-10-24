import sqlite3, threading, queue, json, csv, getpass, os
from datetime import datetime, timedelta

def _get_default_db_path():
    """返回 ~/.zpp011_audit/audit_log.db，确保目录存在"""
    app_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "audit_log.db")


class AuditLogger:
    # 连接忙等超时（秒）：写线程与导出线程并发时，读侧最多等这么久而不是立刻报错。
    # sqlite3 默认就是 5 秒，这里显式写出来是为了让这个意图可见、且不随默认值变化。
    _BUSY_TIMEOUT = 10.0

    def __init__(self, db_path=None, max_queue_size=1000):
        self.db_path = db_path or _get_default_db_path()
        self._app_dir = os.path.dirname(self.db_path)
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()
        self._init_db()
        self._cleanup_old_logs()

    # ---------------------------------------------------------------- 连接

    def _connect(self):
        """新建一个连接（**调用方负责关闭**）。

        注意：`with sqlite3.connect(...) as conn:` **不会关闭连接** ——
        with 块只负责提交/回滚事务，连接对象要等被 GC 回收才真正 close。
        原实现在写日志的循环里用 with，每次循环都泄漏一个连接对象，
        所以本模块统一改成显式 try/finally + close()。
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout = %d" % int(self._BUSY_TIMEOUT * 1000))
        return conn

    def _init_db(self):
        conn = self._connect()
        try:
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
            conn.commit()
        finally:
            conn.close()

    def _cleanup_old_logs(self, days=180):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = self._connect()
        try:
            conn.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))
            conn.commit()
        finally:
            conn.close()

    # ---------------------------------------------------------------- 写日志

    def _worker(self):
        """后台写日志线程。

        **连接复用（v43.254 修复 CORE-10 N+1 连接）**：
        原实现在循环体内 `with sqlite3.connect(...)` —— 每写一条日志就
        新建一个 SQLite 连接（open 文件 + 读 WAL + 关文件），实测写 50 条
        日志 = 50 次 connect。日志是高频路径（每次改备注/改状态都写一条），
        这个开销纯属浪费，且连接对象还被 with 块泄漏（with 不负责 close）。

        现在改成：**整个 worker 生命周期只开一个连接**，逐条复用。
        50 条日志 → 1 次 connect。

        容错不变：单条写失败仍降级到 fallback 文件，不中断 worker；
        若失败原因是连接本身损坏，则丢弃该连接，下一条重新建（自愈）。
        """
        conn = None
        try:
            while True:
                item = self.queue.get()
                if item is None:
                    break
                try:
                    if conn is None:
                        conn = self._connect()
                    conn.execute("""
                        INSERT INTO audit_log (timestamp, username, material_code, action, old_value, new_value, source, extra)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, item)
                    conn.commit()
                except Exception as e:
                    # 连接可能已损坏 → 丢弃，下一条重建（自愈），不影响后续写入
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        conn = None
                    fallback = os.path.join(self._app_dir, "audit_fallback.log")
                    with open(fallback, "a") as f:
                        f.write(f"{item} | error: {e}\n")
        finally:
            # worker 退出（含 shutdown 收到 None）时关掉复用的连接，避免句柄泄漏
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

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
            # 导出读全表 —— 用只读连接，且**必须显式关闭**
            # （with sqlite3.connect 不关连接，导出完还留着文件句柄）
            conn = self._connect()
            try:
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
            except Exception as e:
                if callback:
                    callback(output_path, e)
                return
            finally:
                conn.close()
            if callback:
                callback(output_path, None)
        threading.Thread(target=task, daemon=True).start()
