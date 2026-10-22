# -*- coding: utf-8 -*-
"""
检查 read_status 表基线数据
"""
import sqlite3
import pandas as pd

db_path = r"C:\Users\Administrator\.zpp011_audit\audit.db"
conn = sqlite3.connect(db_path)

# 统计
query1 = "SELECTเป็นอย่าง COUNT(*) FROM read_status WHERE snapshot_qty IS NULL AND is_read=1"
query2 = "SELECT COUNT(*) FROM read_status WHERE snapshot_qty IS NOT NULL AND is_read=1"
query3 = "SELECT COUNT(*) FROM read_status WHERE snapshot_qty IS NULL AND is_read=0"
query4 = "SELECT COUNT(*) FROM read_status WHERE snapshot_qty IS NOT NULL AND is_read=0"

with conn:
    c = conn.cursor()
    r1 = c.execute(query1).fetchone()[0]
    r2 = c.execute(query2).fetchone()[0]
    r3 = c.execute(query3).fetchone()[0]
    r4 = c.execute(query4).fetchone()[0]

print(f"基线缺失且未读: {r1}")
print(f"基线完整且未读: {r2}")
print(f"基线缺失且已读: {r3}")
print(f"基线完整且已读: {r4}")

# 采样查看基线缺失记录
df = pd.read_sql_query("SELECT * FROM read_status WHERE snapshot_qty IS NULL AND is_read=1 LIMIT 20", conn)
print("\n=== 基线缺失且已读的 sample ===")
print(df)

# 查询 deviation_history 中哪些数据 ID 有多个变更
df_hist = pd.read_sql_query("SELECT data_id, COUNT(*) as changes_count FROM deviation_history GROUP BY data_id ORDER BY changes_count DESC LIMIT 20", conn)
print("\n=== 变动记录最多的 data_id ===")
print(df_hist)

conn.close()
