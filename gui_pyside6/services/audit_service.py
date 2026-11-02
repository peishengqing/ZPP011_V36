# -*- coding: utf-8 -*-
"""
审计服务系统 - 简化版（单机最终决策者）

状态流：待审核 → 已审核（完成）

功能：
- 标记待审核
- 完成审核（最终决策者直接确认）
- 查询审核状态
- 获取审计记录
- 审计时间线追踪
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

# 使用现有的数据库路径
DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit.db")


class AuditService:
    """审计服务（单机版简化流程）"""
    
    def __init__(self):
        self._init_db()
        
    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        
        # 创建审计记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_records (
                data_id TEXT PRIMARY KEY,
                status TEXT DEFAULT '待审核',
                audit_reason TEXT,
                auditor TEXT,
                audit_time TIMESTAMP,
                original_value REAL,
                new_value REAL,
                audit_note TEXT,
                updated_at TIMESTAMP
            )
        """)
        
        # 创建审计操作日志表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT,
                user TEXT,
                comment TEXT,
                op_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        
        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_records_status ON audit_records(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_data_id ON audit_logs(data_id)")
        conn.close()
    
    def _get_conn(self):
        """获取数据库连接"""
        return sqlite3.connect(DB_PATH)
    
    def mark_auditing_needed(self, df: pd.DataFrame, data_id: str, reason: str, auditor: str = "system"):
        """标记为待审核"""
        current_time = datetime.now()
        conn = self._get_conn()
        
        # 插入或更新记录
        conn.execute("""
            INSERT INTO audit_records (data_id, status, audit_reason, auditor, audit_time, updated_at)
            VALUES (?, '待审核', ?, ?, ?, ?)
            ON CONFLICT(data_id) DO UPDATE SET
                status = '待审核',
                audit_reason = excluded.audit_reason,
                auditor = excluded.auditor,
                audit_time = excluded.audit_time,
                updated_at = excluded.updated_at
        """, (data_id, reason, auditor, current_time, current_time))
        
        # 记录日志
        conn.execute('''
            INSERT INTO audit_logs (data_id, from_status, to_status, user, comment)
            VALUES (?, NULL, '待审核', ?, ?)
        ''', (data_id, auditor, f"标记为待审核: {reason}"))
        
        conn.commit()
        conn.close()
    
    def audit_complete(self, df: pd.DataFrame, data_id: str, new_value: float, audit_note: str, user_id: str):
        """完成审核（最终决策者）"""
        current_time = datetime.now()
        
        # 查询当前记录
        current = self.get_audit_record(data_id)
        
        if not current or current['status'] != '待审核':
            return False
            
        # 获取原值
        original_value = current['original_value']
        if original_value is None:
            # 从DataFrame中获取
            for idx, row in df.iterrows():
                data_id_col = row.get('data_id')
                if data_id_col == data_id:
                    # 尝试多个可能的数值列
                    for col in ['实际', '名义数量', '数量-实际', 'actual', 'quantity']:
                        if col in row.index and row[col] is not None:
                            try:
                                original_value = float(row[col])
                                break
                            except (TypeError, ValueError):
                                pass
        
        conn = self._get_conn()
        
        # 更新记录
        conn.execute("""
            UPDATE audit_records SET
                status = '已审核',
                new_value = ?,
                audit_note = ?,
                auditor = ?,
                audit_time = ?,
                original_value = ?,
                updated_at = ?
            WHERE data_id = ?
        """, (new_value, audit_note, user_id, current_time, original_value, current_time, data_id))
        
        # 记录日志
        conn.execute('''
            INSERT INTO audit_logs (data_id, from_status, to_status, user, comment)
            VALUES (?, '待审核', '已审核', ?, ?)
        ''', (data_id, user_id, f"完成审核: {new_value}, 备注: {audit_note}"))
        
        conn.commit()
        conn.close()
        return True
    
    def get_audit_record(self, data_id: str) -> Optional[Dict]:
        """获取审计记录"""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT data_id, status, audit_reason, auditor, audit_time, original_value, new_value, audit_note, updated_at
            FROM audit_records WHERE data_id = ?
        """, (data_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        return {
            'data_id': row[0],
            'status': row[1],
            'audit_reason': row[2],
            'auditor': row[3],
            'audit_time': row[4],
            'original_value': row[5],
            'new_value': row[6],
            'audit_note': row[7],
            'updated_at': row[8]
        }
    
    def get_audit_history(self, data_id: str) -> List[Dict]:
        """获取审计时间线"""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT id, data_id, from_status, to_status, user, comment, op_time
            FROM audit_logs WHERE data_id = ?
            ORDER BY op_time DESC
        """, (data_id,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'id': row[0],
                'data_id': row[1],
                'from_status': row[2],
                'to_status': row[3],
                'user': row[4],
                'comment': row[5],
                'time': row[6]
            })
        
        conn.close()
        return history
    
    def mark_cancel(self, data_id: str, user_id: str):
        """取消审核，退回到待审核"""
        current_time = datetime.now()
        conn = self._get_conn()
        
        # 更新记录
        conn.execute("""
            UPDATE audit_records SET
                status = '待审核',
                auditor = NULL,
                audit_time = NULL,
                updated_at = ?
            WHERE data_id = ?
        """, (current_time, data_id))
        
        # 记录日志
        conn.execute('''
            INSERT INTO audit_logs (data_id, from_status, to_status, user, comment)
            VALUES (?, '已审核', '待审核', ?, '取消审核，退回待审核队列')
        ''', (data_id, user_id))
        
        conn.commit()
        conn.close()
    
    def get_auditing_needed_count(self) -> int:
        """获取待审核数量"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM audit_records WHERE status = '待审核'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def mark_all_audited(self, data_ids: List[str], new_values: Dict[str, float], audit_note: str, user_id: str):
        """批量完成审核"""
        current_time = datetime.now()
        
        for data_id in data_ids:
            if data_id not in new_values:
                continue
                
            self.audit_complete(None, data_id, new_values[data_id], audit_note, user_id)
        
        return True


# 全局实例
audit_service = AuditService()
