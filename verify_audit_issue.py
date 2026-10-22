# -*- coding: utf-8 -*-
"""
快速检查 audit_changes 数据问题
"""
import sqlite3
import pandas as pd
from pathlib import Path

# 数据库路径
db_path = Path(r"C:\Users\Administrator\.zpp011_audit\audit.db")

if not db_path.exists():
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))

# 查询 read_status 表中基线缺失的记录
query = """
SELECT data_id, is_read, fingerprint, snapshot_qty, snapshot_note, snapshot_yield, read_time, user, read_source
FROM read_status
WHERE snapshot_qty IS NULL OR snapshot_note IS NULL OR snapshot_yield IS NULL
ORDER BY data_id DESC;
"""

df_status = pd.read_sql_query(query, conn)
print(f"=== 基线缺失记录数: {len(df_status)} ===")
print(df_status.head(10))

# 查询 deviation_history 统计
query2 = """
SELECT data_id, COUNT(*) as cnt, COUNT(DISTINCT field) as fields
FROM deviation_history
GROUP BY data_id
ORDER BY cnt DESC
LIMIT 20;
"""
df_hist = pd.read_sql_query(query2, conn)
print(f"=== 变动历史条目最多的20条 ===")
print(df_hist)

conn.close()

# 从内存中模拟 get_audit_changes 逻辑来检查
# 读取 Excel 文件路径（假设用户提供的）
excel_path = r"E:/zpp011_v2/audit_changes_20261020_091037.xlsx"
if Path(excel_path).exists():
    df_export = pd.read_excel(excel_path)
    print(f"=== 导出的变动提醒表共 {len(df_export)} 行 ===")
    print(f"旧值为空的行数: {df_export['old_value'].isna().sum()}")
    print(f"新值为空的行数: {df_export['new_value'].isna().sum()}")
    print(df_export.head(10))
else:
    print(f"Excel 文件不存在: {excel_path}")
