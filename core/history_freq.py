# -*- coding: utf-8 -*-
"""
历史频率推荐 — 基于物料+工厂+车间的备注原因频率统计

在 AI 审核时查询历史高频备注原因，作为参考附加到建议中。
零新依赖，基于 groupby + value_counts，数据从实际审核结果中积累。
"""
import sqlite3
import os
import logging

logger = logging.getLogger("HistoryFreq")

FREQ_DB_NAME = "zpp011_history_freq.db"


def _get_db_path() -> str:
    """返回 ~/.zpp011_audit/zpp011_history_freq.db"""
    app_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, FREQ_DB_NAME)


def _init_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history_remarks (
            material_code TEXT NOT NULL,
            factory       TEXT NOT NULL DEFAULT '',
            workshop      TEXT NOT NULL DEFAULT '',
            remark        TEXT NOT NULL,
            count         INTEGER NOT NULL DEFAULT 1,
            last_seen     TEXT NOT NULL,
            PRIMARY KEY (material_code, factory, workshop, remark)
        )
    """)
    conn.commit()


def update_history(material_code: str, factory: str, workshop: str, remark: str):
    """记录一条备注到历史库（如果存在则 count+1，否则插入）"""
    if not remark or not material_code:
        return
    from datetime import datetime
    conn = sqlite3.connect(_get_db_path())
    _init_table(conn)
    try:
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO history_remarks (material_code, factory, workshop, remark, count, last_seen)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(material_code, factory, workshop, remark)
            DO UPDATE SET count = count + 1, last_seen = excluded.last_seen
        """, (material_code.strip(), str(factory).strip(), str(workshop).strip(),
              str(remark).strip(), now))
        conn.commit()
    except Exception as e:
        logger.warning(f"更新历史备注频率失败: {e}")
    finally:
        conn.close()


def batch_update(df):
    """从 DataFrame 批量更新历史备注频率"""
    import pandas as pd
    needed = ['物料编码', '工厂', '车间', '备注原因']
    if not all(c in df.columns for c in needed):
        logger.debug(f"缺少必要列，跳过历史频率更新。已有列: {list(df.columns)}")
        return

    # 过滤掉空备注
    mask = df['备注原因'].notna() & (df['备注原因'].astype(str).str.strip() != '') & \
           (df['备注原因'].astype(str).str.strip().isin(['nan', 'NaN', 'None']) == False)
    valid = df.loc[mask]
    if valid.empty:
        return

    conn = sqlite3.connect(_get_db_path())
    _init_table(conn)
    from datetime import datetime
    now = datetime.now().isoformat()
    for _, row in valid.iterrows():
        try:
            conn.execute("""
                INSERT INTO history_remarks (material_code, factory, workshop, remark, count, last_seen)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(material_code, factory, workshop, remark)
                DO UPDATE SET count = count + 1, last_seen = excluded.last_seen
            """, (
                str(row.get('物料编码', '')).strip(),
                str(row.get('工厂', '')).strip(),
                str(row.get('车间', '')).strip(),
                str(row.get('备注原因', '')).strip(),
                now
            ))
        except Exception as e:
            logger.warning(f"批量更新历史备注失败: {e}")
    conn.commit()
    conn.close()


def get_top_remarks(material_code: str, factory: str = '', workshop: str = '',
                    top_n: int = 3, min_count: int = 1) -> list:
    """查询 Top N 高频备注原因

    Args:
        material_code: 物料编码
        factory: 工厂（可选）
        workshop: 车间（可选）
        top_n: 返回前 N 条
        min_count: 最低出现次数过滤

    Returns:
        [(remark, count), ...] 按频率降序
    """
    conn = sqlite3.connect(_get_db_path())
    _init_table(conn)
    try:
        if workshop:
            rows = conn.execute("""
                SELECT remark, count FROM history_remarks
                WHERE material_code = ? AND factory = ? AND workshop = ? AND count >= ?
                ORDER BY count DESC LIMIT ?
            """, (material_code.strip(), str(factory).strip(),
                  str(workshop).strip(), min_count, top_n)).fetchall()
        elif factory:
            rows = conn.execute("""
                SELECT remark, count FROM history_remarks
                WHERE material_code = ? AND factory = ? AND count >= ?
                ORDER BY count DESC LIMIT ?
            """, (material_code.strip(), str(factory).strip(),
                  min_count, top_n)).fetchall()
        else:
            rows = conn.execute("""
                SELECT remark, count FROM history_remarks
                WHERE material_code = ? AND count >= ?
                ORDER BY count DESC LIMIT ?
            """, (material_code.strip(), min_count, top_n)).fetchall()
        return [(r[0], r[1]) for r in rows]
    finally:
        conn.close()


def format_history_hint(material_code: str, factory: str, workshop: str) -> str:
    """格式化为 AI 建议中附加的提示文本

    返回如: "📊 历史高频原因参考：①设备换型废品(7次) ②来料不良(3次)"
    无数据时返回空字符串。
    """
    items = get_top_remarks(material_code, factory, workshop)
    if not items:
        return ""

    parts = []
    for i, (remark, cnt) in enumerate(items, 1):
        label = f"{'①②③④⑤'[i-1]}{remark}({cnt}次)"
        part = f"{'①②③④⑤'[i-1]} {remark}({cnt}次)"
        parts.append(part)
    return "📊 历史高频原因参考：" + " ".join(parts)
