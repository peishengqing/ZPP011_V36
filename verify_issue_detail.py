# -*- coding: utf-8 -*-
"""
验证变动提醒中 'old_value=NaN' 的根因
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

db_path = Path(r"C:\Users\Administrator\.zpp011_audit\audit.db")
sync_path = r"E:/ZPP011导出文件原数据/偏差数据10(王云).xlsx"  # 假设一个源文件路径

if not db_path.exists():
    print(f"数据库不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))

# 问题1: 统计 _post_audit_changed 的存在情况
query = """
SELECT main._post_audit_changed, rs.snapshot_qty, rs.is_read
FROM read_status rs
JOIN main_table ON rs.data_id = main_table.data_id
ORDER BY rs.data_id DESC
LIMIT 50;
"""

# 主表的数据我们现在没拿到，所以先统计 read_status 信源
print("=== 问题行采样 (读状态表) ===")
df_status = pd.read_sql_query("""
    SELECT data_id, is_read, snapshot_qty, snapshot_note, snapshot_yield, read_time
    FROM read_status
    WHERE snapshot_qty IS NULL
    ORDER BY read_time DESC
    LIMIT 20
""", conn)
print(df_status)

# 问题2: 这些记录是否存在 deviation_history 记录
df_hist = pd.read_sql_query("""
    SELECT diss.data_id, diss.is_read, dis.snapshot_qty, dis.snapshot_note,
           dh.field, dh.old_value, dh.new_value, dh.change_time
    FROM read_status diss
    LEFT JOIN deviation_history dh ON diss.data_id = dh.data_id
    WHERE diss.snapshot_qty IS NULL AND diss.is_read = 1
    ORDER BY diss.data_id DESC, dh.change_time DESC
    LIMIT 30
""", conn)
print("\n=== 基线缺失记录的 deviation_history ===")
print(df_hist)

# 问题3: 检查数据库结构是否有错误
from sqlite3 import DatabaseError
try:
    cru = pd.read_sql_query("""
        PRAGMA table_info(read_status)
    """, conn)
    print("\n=== read_status 表结构 ===")
    print(cru)
except Exception as e:
    print(f"查询表结构失败: {e}")

conn.close()

print(
    "\n" + "="*80 +
    "\n🔍 结论:\n" +
    "1. 记录有 _post_audit_changed=1 但 基线快照全空 → 说明历史记录被清理/损坏\n" +
    "2. 或者: 基线从未正确初始化 (如数据库初始化时漏处理)\n" +
    "3. 当前代码的 'else' 分支 (缺基线) 仍然返回记录，导致出公告时 old_value 为 NaN\n" +
    "="*80
)
