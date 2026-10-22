# -*- coding: utf-8 -*-
"""
真实问题调查：检查是否存在 _post_audit_changed=1 但基线缺失的记录
"""
import sqlite3
import pandas as pd

db_path = r"C:\Users\Administrator\.zpp011_audit\audit.db"
conn = sqlite3.connect(db_path)

# 1. 检查 deviation_history 中大量变动的记录
print("=== 变动记录最多的前10条 data_id ===")
df = pd.read_sql_query("""
    SELECT data_id, COUNT(*) as change_cnt,
           GROUP_CONCAT(DISTINCT field) as fields
    FROM deviation_history
    GROUP BY data_id
    HAVING change_cnt > 10
    ORDER BY change_cnt DESC
    LIMIT 10
""", conn)
print(df)

# 2. 检查这些记录的 read_status 基线状态
data_ids = df['data_id'].tolist()
if data_ids:
    placeholders = ','.join('?' * len(data_ids))
    query = f"""
        SELECT data_id, is_read, snapshot_qty, snapshot_note, snapshot_yield
        FROM read_status
        WHERE data_id IN ({placeholders})
    """
    df_status = pd.read_sql_query(query, conn, params=data_ids)
    print("\n=== 这些变动频繁记录的基线状态 ===")
    print(df_status)

# 3. 特别检查：是否有记录 _post_audit_changed 存在但基线全 null
# 需要模拟主表数据读取 - 看看这些数据是否真的存在 _post_audit_changed=1
print("\n=== 特殊记录采样 (read_status) ===")
special_df = pd.read_sql_query("""
    SELECT data_id, is_read, snapshot_qty, snapshot_note, snapshot_yield, read_time
    FROM read_status
    WHERE snapshot_qty IS NULL
    LIMIT 20
""", conn)
print(special_df)

# 4. 检查 deviation_history 的数据保存格式
print("\n=== deviation_history 样例 ===")
sample = pd.read_sql_query("""
    SELECT * FROM deviation_history
    LIMIT 20
""", conn)
print(sample)

# 5. 检查占位符数据 (以 'id_' 开头的)
print("\n=== 非真实数据记录采样 ===")
non_real = pd.read_sql_query("""
    SELECT data_id, is_read, snapshot_qty, snapshot_note, snapshot_yield
    FROM read_status
    WHERE data_id LIKE 'id_%' OR data_id LIKE 'test_%'
    LIMIT 10
""", conn)
print(non_real)

conn.close()

print("\n" + "="*80)
print("🔍 结论:")
print("1. 大量非真实数据记录（id_xxx）存在，这些可能是测试数据")
print("2. 这些测试记录的基线可能从未正确初始化")
print("3. 需要检查是否真实业务记录也有类似问题")
print("="*80)
