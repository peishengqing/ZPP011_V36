# -*- coding: utf-8 -*-
"""历史分析数据持久化到 SQLite"""
import sqlite3, json, os, pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import traceback

# 数据库路径
DB_PATH = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'history.db')

# 中文列名 → 数据库字段映射
COLUMN_MAP = {
    '工厂': 'factory',
    '车间': 'workshop',
    '订单日期': 'order_date',
    '流程订单': 'order_no',
    '物料编码': 'material_code',
    'material_category': 'material_category',
    '物料描述': 'material_name',
    '定额': 'quota',
    '实际': 'actual',
    '偏差率(%)': 'dev_rate',
    '替代料': 'is_alt',  # 需转换：'是'→1, '否'→0
    '备注原因': 'remark',
    '审核结果': 'audit_result',
    'AI建议': 'ai_suggestion',
    '审核状态': 'audit_status',
    '审核来源': 'audit_source',
    '偏差金额': 'deviation_amount',
}

# 数据库字段 → 中文列名（逆向映射）
REVERSE_COLUMN_MAP = {v: k for k, v in COLUMN_MAP.items()}


def init_db(db_path: str = DB_PATH) -> None:
    """创建表结构，设置 PRAGMA"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        
        # 分析元数据表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT,
                file_mtime REAL,
                total_rows INTEGER,
                high_dev_rows INTEGER,
                need_note_rows INTEGER,
                approved_rows INTEGER,
                dev_rate_distribution TEXT,
                filter_condition TEXT,
                extra TEXT
            )
        """)
        
        # 偏差明细表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deviation_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                factory TEXT,
                workshop TEXT,
                order_date TEXT,
                order_no TEXT,
                material_code TEXT,
                material_category TEXT,
                material_name TEXT,
                quota REAL,
                actual REAL,
                dev_rate REAL,
                is_alt INTEGER,
                remark TEXT,
                audit_result TEXT,
                ai_suggestion TEXT,
                audit_status TEXT,
                audit_source TEXT,
                deviation_amount REAL,
                FOREIGN KEY (analysis_id) REFERENCES analysis_meta(id) ON DELETE CASCADE
            )
        """)
        
        # 索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_meta(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_details_analysis_id ON deviation_details(analysis_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_details_material_category ON deviation_details(material_category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_details_dev_rate ON deviation_details(dev_rate)")
        
        conn.commit()
    finally:
        conn.close()


def _transform_alt_material(value) -> Optional[int]:
    """转换替代料字段"""
    if value is None or value == '' or pd.isna(value):
        return 0
    if str(value).strip() in ('是', 'YES', 'True', 'true', '1'):
        return 1
    return 0


def save_analysis_result(metadata: dict, df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    """
    幂等保存：基于 file_name 和 file_mtime 检查是否已存在。
    返回 analysis_id
    """
    file_name = metadata.get('file_name', '')
    file_mtime = metadata.get('file_mtime', 0)

    conn = sqlite3.connect(db_path)
    try:
        # 幂等性检查
        cursor = conn.execute(
            "SELECT id FROM analysis_meta WHERE file_name=? AND file_mtime=? LIMIT 1",
            (file_name, file_mtime)
        )
        existing = cursor.fetchone()
        if existing:
            return existing[0]

        # 开启事务
        try:
            # 插入元数据
            timestamp = datetime.now().isoformat()
            dev_dist = json.dumps(metadata.get('dev_rate_distribution', {}), ensure_ascii=False)
            filter_cond = metadata.get('filter_condition', '')
            extra = json.dumps(metadata.get('extra', {}), ensure_ascii=False)

            cursor = conn.execute(
                """INSERT INTO analysis_meta
                   (timestamp, file_name, file_path, file_mtime, total_rows, high_dev_rows,
                    need_note_rows, approved_rows, dev_rate_distribution, filter_condition, extra)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, file_name, metadata.get('file_path', ''), file_mtime,
                 metadata.get('total_rows', 0), metadata.get('high_dev_rows', 0),
                 metadata.get('need_note_rows', 0), metadata.get('approved_rows', 0),
                 dev_dist, filter_cond, extra)
            )
            analysis_id = cursor.lastrowid

            # 批量插入明细
            rows_to_insert = []
            for _, row in df.iterrows():
                row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)

                is_alt = _transform_alt_material(row_dict.get('替代料', row_dict.get('is_alt', 0)))

                rows_to_insert.append((
                    analysis_id,
                    row_dict.get('工厂', ''),
                    row_dict.get('车间', ''),
                    str(row_dict.get('订单日期', '')),
                    row_dict.get('流程订单', ''),
                    row_dict.get('物料编码', ''),
                    row_dict.get('material_category', row_dict.get('物料大类', '')),
                    row_dict.get('物料描述', row_dict.get('物料名称', '')),
                    _to_float(row_dict.get('定额', 0)),
                    _to_float(row_dict.get('实际', 0)),
                    _to_float(row_dict.get('偏差率(%)', row_dict.get('偏差率%', 0))),
                    is_alt,
                    row_dict.get('备注原因', row_dict.get('备注', '')),
                    row_dict.get('审核结果', ''),
                    row_dict.get('AI建议', ''),
                    row_dict.get('审核状态', ''),
                    row_dict.get('审核来源', ''),
                    _to_float(row_dict.get('偏差金额', 0)),
                ))

            conn.executemany(
                """INSERT INTO deviation_details
                   (analysis_id, factory, workshop, order_date, order_no, material_code,
                    material_category, material_name, quota, actual, dev_rate, is_alt,
                    remark, audit_result, ai_suggestion, audit_status, audit_source, deviation_amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )

            conn.commit()
            return analysis_id

        except Exception as e:
            conn.rollback()
            raise e
    finally:
        conn.close()


def _to_float(value) -> Optional[float]:
    """安全转换为浮点数"""
    if value is None or value == '' or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_analysis_list(limit: int = 100, db_path: str = DB_PATH) -> List[dict]:
    """返回历史分析列表"""
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """SELECT id, timestamp, file_name, total_rows, high_dev_rows,
                      need_note_rows, approved_rows, filter_condition
               FROM analysis_meta
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,)
        )

        result = []
        for row in cursor.fetchall():
            result.append({
                'id': row[0],
                'timestamp': row[1],
                'file_name': row[2],
                'total_rows': row[3],
                'high_dev_rows': row[4],
                'need_note_rows': row[5],
                'approved_rows': row[6],
                'filter_condition': row[7] or '',
            })
        return result
    finally:
        conn.close()


def get_analysis_data(analysis_id: int, db_path: str = DB_PATH) -> pd.DataFrame:
    """返回 DataFrame，列名使用中文"""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """SELECT factory, workshop, order_date, order_no, material_code,
                      material_category, material_name, quota, actual, dev_rate, is_alt,
                      remark, audit_result, ai_suggestion, audit_status, audit_source, deviation_amount
               FROM deviation_details
               WHERE analysis_id = ?
               ORDER BY id""",
            (analysis_id,)
        )

        rows = cursor.fetchall()
        if not rows:
            return pd.DataFrame()

        # 转换为 DataFrame，列名使用中文
        columns = ['工厂', '车间', '订单日期', '流程订单', '物料编码',
                   '物料大类', '物料描述', '定额', '实际', '偏差率(%)',
                   '替代料', '备注原因', '审核结果', 'AI建议', '审核状态', '审核来源', '偏差金额']

        df = pd.DataFrame(rows, columns=columns)

        # 转换替代料字段
        df['替代料'] = df['is_alt'].map({1: '是', 0: '否'})
        df = df.drop(columns=['is_alt'])

        return df
    finally:
        conn.close()


def compare_analyses(id1: int, id2: int, db_path: str = DB_PATH) -> dict:
    """返回对比结果"""
    conn = sqlite3.connect(db_path)
    try:
        # 获取两次分析的元数据
        meta1 = conn.execute(
            "SELECT * FROM analysis_meta WHERE id=?", (id1,)
        ).fetchone()
        meta2 = conn.execute(
            "SELECT * FROM analysis_meta WHERE id=?", (id2,)
        ).fetchone()

        if not meta1 or not meta2:
            raise ValueError("分析记录不存在")

        # 提取字段
        meta_cols = ['id', 'timestamp', 'file_name', 'file_path', 'file_mtime',
                     'total_rows', 'high_dev_rows', 'need_note_rows', 'approved_rows',
                     'dev_rate_distribution', 'filter_condition', 'extra']

        m1 = dict(zip(meta_cols, meta1))
        m2 = dict(zip(meta_cols, meta2))

        # 计算差异
        result = {
            'analysis1': {
                'id': m1['id'],
                'timestamp': m1['timestamp'],
                'file_name': m1['file_name'],
                'total_rows': m1['total_rows'],
                'high_dev_rows': m1['high_dev_rows'],
                'need_note_rows': m1['need_note_rows'],
                'approved_rows': m1['approved_rows'],
                'approved_rate': m1['approved_rows'] / m1['total_rows'] if m1['total_rows'] > 0 else 0,
                'need_note_rate': m1['need_note_rows'] / m1['total_rows'] if m1['total_rows'] > 0 else 0,
                'filter_condition': m1['filter_condition'] or '',
            },
            'analysis2': {
                'id': m2['id'],
                'timestamp': m2['timestamp'],
                'file_name': m2['file_name'],
                'total_rows': m2['total_rows'],
                'high_dev_rows': m2['high_dev_rows'],
                'need_note_rows': m2['need_note_rows'],
                'approved_rows': m2['approved_rows'],
                'approved_rate': m2['approved_rows'] / m2['total_rows'] if m2['total_rows'] > 0 else 0,
                'need_note_rate': m2['need_note_rows'] / m2['total_rows'] if m2['total_rows'] > 0 else 0,
                'filter_condition': m2['filter_condition'] or '',
            },
            'diff': {
                'total_rows': m2['total_rows'] - m1['total_rows'],
                'high_dev_rows': m2['high_dev_rows'] - m1['high_dev_rows'],
                'need_note_rows': m2['need_note_rows'] - m1['need_note_rows'],
                'approved_rows': m2['approved_rows'] - m1['approved_rows'],
            },
            'filter_warning': m1['filter_condition'] != m2['filter_condition'],
        }

        return result
    finally:
        conn.close()


def cleanup_old_records(months: int = 6, db_path: str = DB_PATH) -> int:
    """清理超过 months 个月的记录，返回删除的 analysis 数量"""
    if not os.path.exists(db_path):
        return 0

    import time
    from datetime import timedelta

    cutoff = (datetime.now() - timedelta(days=30 * months)).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        # 获取要删除的 ID 列表（受外键约束 CASCADE 影响，明细会自动删除）
        cursor = conn.execute(
            "SELECT COUNT(*) FROM analysis_meta WHERE timestamp < ?",
            (cutoff,)
        )
        count = cursor.fetchone()[0]

        if count > 0:
            conn.execute("DELETE FROM analysis_meta WHERE timestamp < ?", (cutoff,))
            conn.commit()

        return count
    finally:
        conn.close()
