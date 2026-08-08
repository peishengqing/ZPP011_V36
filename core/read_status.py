# -*- coding: utf-8 -*-
"""
已读/未读状态管理 + 审核结果持久化 + 偏差变动历史记录
使用 SQLite 持久化存储

性能设计（2026-07-30 修复）：
- _get_conn() 主线程仍用进程级单例（DDL 只跑一次）
- 子线程（QThread）用 threading.local() 独立连接，消除跨线程 sqlite3 内部竞争
- 所有大 IN 子句拆成 _CHUNK_SIZE=500 一批，避免 SQLite 对过多参数选择全表扫描路径
- WAL + NORMAL synchronous + 64MB cache
"""
import sqlite3
import logging
import os
import threading
import time as _time
from datetime import datetime
from typing import Dict, List, Tuple


_CHUNK_SIZE = 500  # IN 子句一次最多查 500 个 data_id，避免 SQLite 查询计划退化


DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit.db")

# 主线程单例连接
_CONN = None
_DDL_DONE = False
_CONN_LOCK = threading.Lock()

# 子线程独立连接（threading.local）
_THREAD_CONNS = threading.local()
_CHILD_DDL_DONE = threading.local()


def _get_conn():
    """获取数据库连接。

    设计：
    - 主线程 → 进程级单例 _CONN（DDL 只跑一次，避免每次重走 5 ALTER + 1 UPDATE + 1 INDEX）
    - 子线程（QThread）→ threading.local() 独立连接，不与主线程共享 sqlite3 连接对象，
      消除跨线程内部竞争（原版 fetchall 被拖慢 100+ 秒）。
    """
    if threading.current_thread() is not threading.main_thread():
        try:
            conn = _THREAD_CONNS.conn
            return conn
        except AttributeError:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA cache_size=-65536")  # 64MB
            except sqlite3.Error:
                pass
            _THREAD_CONNS.conn = conn
            try:
                if not _CHILD_DDL_DONE.done:
                    pass  # 子线程不跑 DDL，表已存在
            except AttributeError:
                _CHILD_DDL_DONE.done = True
            return conn

    # 主线程
    global _CONN, _DDL_DONE
    if _CONN is not None and _DDL_DONE:
        return _CONN

    with _CONN_LOCK:
        if _CONN is not None and _DDL_DONE:
            return _CONN
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA cache_size=-65536")
        except sqlite3.Error:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS read_status (
                data_id TEXT PRIMARY KEY,
                is_read INTEGER DEFAULT 0,
                fingerprint TEXT,
                read_time TIMESTAMP,
                user TEXT DEFAULT 'default'
            )
        """)

        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(read_status)").fetchall()}
        for col_name, col_def in [
            ('audit_result', 'TEXT DEFAULT ""'),
            ('ai_suggestion', 'TEXT DEFAULT ""'),
            ('note_source', 'TEXT DEFAULT ""'),
            ('snapshot_qty', 'REAL DEFAULT NULL'),
            ('snapshot_note', 'TEXT DEFAULT NULL'),
            ('read_source', 'TEXT DEFAULT ""'),  # 已读来源：'auto' 自动规则 / 'manual' 手动（默认空）
        ]:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE read_status ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass

        conn.execute("UPDATE read_status SET snapshot_note = NULL WHERE snapshot_note = ''")
        conn.commit()

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
        existing_dh_cols = {row[1] for row in conn.execute("PRAGMA table_info(deviation_history)").fetchall()}
        for col_name, col_def in [
            ('field', 'TEXT DEFAULT NULL'),
            ('old_value', 'TEXT DEFAULT ""'),
            ('new_value', 'TEXT DEFAULT ""'),
        ]:
            if col_name not in existing_dh_cols:
                try:
                    conn.execute(f"ALTER TABLE deviation_history ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deviation_history_data_id ON deviation_history(data_id)")

        _CONN = conn
        _DDL_DONE = True
        return _CONN


def close_db():
    """显式关闭数据库连接（通常不需要——进程退出时 OS 回收；测试/迁移场景调用）"""
    global _CONN, _DDL_DONE
    with _CONN_LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except Exception:
                pass
        _CONN = None
        _DDL_DONE = False


def _migrate_add_column(conn, table, col_name, col_def):
    """安全添加列：如果列不存在则 ALTER TABLE ADD COLUMN（兼容旧调用）"""
    try:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col_name in existing:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
    except sqlite3.OperationalError:
        pass


def init_db():
    """初始化数据库（供外部调用）"""
    _get_conn()


# ========== 辅助：批量 chunked IN 查询 ==========

_CHUNK = _CHUNK_SIZE  # 简写


def _chunked_load(conn, sql_template, data_ids, id_cols):
    """把大 IN 子句拆成 _CHUNK_SIZE 一批，避免 SQLite 查询计划退化到全表扫描。

    sql_template: "SELECT ... FROM read_status WHERE data_id IN ({placeholders})"
    data_ids: 完整 id 列表
    id_cols: 返回的列数（去掉 data_id 后的列数）
    """
    _t0 = _time.perf_counter()
    result = {}
    total = len(data_ids)
    n_chunk = 0
    for start in range(0, total, _CHUNK):
        chunk = data_ids[start:start + _CHUNK]
        placeholders = ','.join(['?' for _ in chunk])
        sql = sql_template.format(placeholders=placeholders)
        for row in conn.execute(sql, chunk).fetchall():
            result[row[0]] = row[1:]
        n_chunk += 1
    return result


# ── 已读状态 ──

def load_read_status(data_ids: List[str]) -> Dict[str, Tuple]:
    """
    批量加载已读状态
    返回: {data_id: (is_read, fingerprint, snapshot_qty, snapshot_note, read_source)}
    read_source: 'auto' 自动规则标已读 / 'manual' 手动标已读 / '' 无（老数据或新行）
    """
    if not data_ids:
        return {}

    _t0 = _time.perf_counter()
    conn = _get_conn()

    # 用 chunked 查询替代单条大 IN 子句
    return _chunked_load(
        conn,
        "SELECT data_id, is_read, fingerprint, snapshot_qty, snapshot_note, read_source "
        "FROM read_status WHERE data_id IN ({placeholders})",
        data_ids, 5
    )


def save_read_status(data_id: str, is_read: int, fingerprint: str, snapshot_qty=None, snapshot_note=None, read_source='manual'):
    """保存已读状态。read_source: 'manual' 手动（默认） / 'auto' 自动规则"""
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO read_status (data_id, is_read, fingerprint, snapshot_qty, snapshot_note, read_time, user, read_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(data_id), int(is_read), str(fingerprint),
              None if snapshot_qty is None else float(snapshot_qty),
              '' if snapshot_note is None else str(snapshot_note),
              datetime.now().isoformat(), 'default', str(read_source)))
        conn.commit()
    except Exception as e:
        logging.warning("[read_status] save_read_status 失败 (data_id=%s): %s", data_id, e)


def save_read_status_batch(records):
    """
    批量保存已读状态

    records: [(data_id, is_read, fingerprint[, snapshot_qty[, snapshot_note[, read_source]]])]
    read_source 默认 'manual'（手动）。
    """
    if not records:
        return
    try:
        conn = _get_conn()
        now = datetime.now().isoformat()
        norm = []
        for rec in records:
            did = rec[0]
            is_read = rec[1]
            fp = rec[2] if len(rec) > 2 else ''
            snap = rec[3] if len(rec) > 3 else None
            note = rec[4] if len(rec) > 4 else None
            src = rec[5] if len(rec) > 5 else 'manual'
            norm.append((str(did), int(is_read), str(fp),
                         None if snap is None else float(snap),
                         '' if note is None else str(note), now, 'default', str(src)))
        conn.executemany("""
            INSERT OR REPLACE INTO read_status (data_id, is_read, fingerprint, snapshot_qty, snapshot_note, read_time, user, read_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, norm)
        conn.commit()
    except Exception as e:
        logging.warning("[read_status] save_read_status_batch 失败 (%d 条): %s", len(records), e)


def mark_read_batch(data_ids, snapshot_map, read_source='auto'):
    """
    批量把已审核记录标记为已读，并同步更新 snapshot 基线。
    read_source: 'auto' 自动规则标已读（默认） / 'manual' 手动标已读。
    行已存在时（如翻回未读后再标）也会同步更新 read_source，保证来源真实。
    """
    if not data_ids:
        return
    try:
        conn = _get_conn()
        now = datetime.now().isoformat()
        src = str(read_source)
        # 向量化归一化：避免 Python 逐行 execute 在主线程阻塞（零偏差行可能上千）
        insert_rows = [(str(did), now, src) for did in data_ids]
        norm = []
        for did in data_ids:
            snap_qty, snap_note = snapshot_map.get(did, (None, None))
            norm.append((
                None if snap_qty is None else float(snap_qty),
                '' if snap_note is None else str(snap_note),
                now, str(did),
            ))
        # 新行插入 source；已存在行（如数据变动翻回未读又标已读）用 ON CONFLICT 更新 source
        conn.executemany("""
            INSERT INTO read_status (data_id, is_read, read_time, user, read_source)
            VALUES (?, 0, ?, 'default', ?)
            ON CONFLICT(data_id) DO UPDATE SET read_source = excluded.read_source
        """, insert_rows)
        conn.executemany("""
            UPDATE read_status SET is_read = 1, snapshot_qty = ?, snapshot_note = ?, read_time = ?
            WHERE data_id = ?
        """, norm)
        conn.commit()
    except Exception as e:
        logging.warning("[read_status] mark_read_batch 失败 (%d 条): %s", len(data_ids), e)


def save_snapshot(data_id: str, snapshot_qty, snapshot_note=None):
    """延迟初始化/更新基线"""
    try:
        conn = _get_conn()
        conn.execute("""
            UPDATE read_status SET snapshot_qty = ?, snapshot_note = ? WHERE data_id = ?
        """, (None if snapshot_qty is None else float(snapshot_qty),
              '' if snapshot_note is None else str(snapshot_note),
              str(data_id)))
        conn.commit()
    except Exception as e:
        # v42.26: 不再静默吞错。基线写失败会导致「偏差变动」判断失真，
        # 必须留下痕迹；但仍不向上抛，避免打断主流程。
        print(f"[read_status] save_snapshot 失败 (data_id={data_id}): "
              f"{type(e).__name__}: {e}")


def save_snapshot_batch(records):
    """
    批量延迟初始化/更新基线。

    records: [(data_id, snapshot_qty, snapshot_note), ...]
    """
    if not records:
        return
    try:
        _t0 = _time.perf_counter()
        conn = _get_conn()
        norm = []
        for did, snap_qty, snap_note in records:
            norm.append((
                None if snap_qty is None else float(snap_qty),
                '' if snap_note is None else str(snap_note),
                str(did),
            ))
        _t = _time.perf_counter()
        conn.executemany("""
            UPDATE read_status SET snapshot_qty = ?, snapshot_note = ? WHERE data_id = ?
        """, norm)
        _t = _time.perf_counter()
        conn.commit()
    except Exception as e:
        # v42.26: 同 save_snapshot，批量基线写失败必须留痕，不再静默吞掉
        print(f"[read_status] save_snapshot_batch 失败 ({len(records)} 条): "
              f"{type(e).__name__}: {e}")


# ── 审核结果持久化 ──

def load_audit_results(data_ids: List[str]) -> Dict[str, Dict[str, str]]:
    """
    批量加载审核结果
    返回: {data_id: {'audit_result': str, 'ai_suggestion': str, 'note_source': str}}
    """
    if not data_ids:
        return {}

    conn = _get_conn()
    raw = _chunked_load(
        conn,
        "SELECT data_id, audit_result, ai_suggestion, note_source "
        "FROM read_status WHERE data_id IN ({placeholders})",
        data_ids, 3
    )
    result = {}
    for did, vals in raw.items():
        ar, ai, ns = vals
        result[did] = {
            'audit_result': ar or '',
            'ai_suggestion': ai or '',
            'note_source': ns or '',
        }
    return result


def save_audit_results_batch(records: List[Dict[str, str]]):
    """批量保存审核结果"""
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


# ── 偏差变动历史 ──

def _to_float(v):
    """安全转 float，NaN 返回 None"""
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:
            return None
        return f
    except (ValueError, TypeError):
        return None


def record_deviation_change(data_id: str, field: str, old_value, new_value, reason: str = "审核后数据被修改"):
    """记录审核后/重新分析的数据变动历史"""
    conn = _get_conn()
    conn.execute("""
        INSERT INTO deviation_history (data_id, field, old_value, new_value, old_qty, new_qty, change_time, change_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(data_id), str(field), str(old_value), str(new_value),
          _to_float(old_value), _to_float(new_value),
          datetime.now().isoformat(), reason))
    conn.commit()


def get_deviation_history_batch(data_ids: List[str]) -> List[Dict]:
    """批量查询一批 data_id 的最新变动历史（用于去重）"""
    if not data_ids:
        return []
    conn = _get_conn()
    placeholders = ','.join(['?' for _ in data_ids])
    cur = conn.execute(
        f"SELECT data_id, field, new_value FROM deviation_history "
        f"WHERE data_id IN ({placeholders}) ORDER BY change_time DESC",
        data_ids
    )
    columns = ['data_id', 'field', 'new_value']
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def record_deviation_change_batch(changes: List[Tuple], reason: str = "审核后数据被修改"):
    """批量记录变动历史，自动去重"""
    if not changes:
        return
    data_ids = list(set(c[0] for c in changes))
    history = get_deviation_history_batch(data_ids)
    seen = set((h['data_id'], h['field'], str(h['new_value'])) for h in history)

    conn = _get_conn()
    now = datetime.now().isoformat()
    norm = []
    for data_id, field, old_value, new_value in changes:
        key = (str(data_id), str(field), str(new_value))
        if key in seen:
            continue
        seen.add(key)
        norm.append((str(data_id), str(field), str(old_value), str(new_value), now, reason))
    if norm:
        conn.executemany("""
            INSERT INTO deviation_history (data_id, field, old_value, new_value, change_time, change_reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, norm)
        conn.commit()


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

    columns = ['id', 'data_id', 'field', 'old_value', 'new_value',
               'old_qty', 'new_qty', 'old_amount', 'new_amount',
               'old_rate', 'new_rate', 'change_time', 'change_reason']
    return [dict(zip(columns, row)) for row in cur.fetchall()]
