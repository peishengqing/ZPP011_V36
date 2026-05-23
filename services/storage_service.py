#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Storage Service - 存储服务层

职责：
- SQLite 审计记录存储
- 历史数据恢复
- 数据持久化

依赖：
- FileService（数据库文件管理）
"""

import sqlite3
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime
import os


class StorageService:
    """存储服务类"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.expanduser("~/.zpp011_audit/audit_history.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
        return self._conn
    
    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 创建审计记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_date TEXT,
                order_no TEXT,
                material_code TEXT,
                material_name TEXT,
                factory TEXT,
                workshop TEXT,
                deviation_rate REAL,
                deviation_amount REAL,
                remark TEXT,
                remark_source TEXT,
                audit_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_no ON audit_records(order_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_material ON audit_records(material_code)")
        
        conn.commit()
    
    def save_audit_records(self, df: pd.DataFrame) -> int:
        """保存审计记录
        
        Args:
            df: DataFrame（含审计结果）
        
        Returns:
            保存的记录数
        """
        conn = self._get_connection()
        
        # 映射列名
        column_mapping = {
            '订单日期': 'order_date',
            '流程订单': 'order_no',
            '组件物料号': 'material_code',
            '组件物料描述': 'material_name',
            '工厂': 'factory',
            '车间': 'workshop',
            '偏差率': 'deviation_rate',
            '偏差金额': 'deviation_amount',
            '备注原因': 'remark',
            '备注来源': 'remark_source',
            'audit_result': 'audit_result',
        }
        
        # 选择需要的列
        columns_to_save = [col for col in column_mapping.keys() if col in df.columns]
        df_save = df[columns_to_save].copy()
        df_save.columns = [column_mapping[col] for col in columns_to_save]
        
        # 写入数据库
        df_save.to_sql('audit_records', conn, if_exists='append', index=False)
        conn.commit()
        
        return len(df_save)
    
    def load_audit_records(self, days: int = 30) -> pd.DataFrame:
        """加载历史审计记录
        
        Args:
            days: 加载最近 N 天的记录
        
        Returns:
            DataFrame
        """
        conn = self._get_connection()
        
        query = """
            SELECT * FROM audit_records
            WHERE created_at >= datetime('now', '-' || ? || ' days')
            ORDER BY created_at DESC
        """
        
        df = pd.read_sql_query(query, conn, params=(days,))
        return df
    
    def restore_audit_from_db(self, df: pd.DataFrame, log_cb=None) -> int:
        """从数据库恢复审计记录到 DataFrame
        
        Args:
            df: 当前数据 DataFrame
            log_cb: 日志回调函数
        
        Returns:
            恢复的记录数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 查询历史审计记录
        cursor.execute("""
            SELECT order_no, material_code, remark, remark_source, audit_result
            FROM audit_records
            ORDER BY updated_at DESC
        """)
        
        history_records = cursor.fetchall()
        restored_count = 0
        
        # 匹配并恢复
        for idx, row in df.iterrows():
            order_no = row.get('流程订单', '')
            material_code = row.get('组件物料号', '')
            
            # 查找匹配的历史记录
            for hist in history_records:
                if hist[0] == order_no and hist[1] == material_code:
                    df.at[idx, '备注原因'] = hist[2]
                    df.at[idx, '备注来源'] = hist[3]
                    df.at[idx, 'audit_result'] = hist[4]
                    restored_count += 1
                    break
        
        conn.commit()
        
        if log_cb:
            log_cb(f"📌 恢复 {restored_count} 条历史审计记录", "info")
        
        return restored_count
    
    def clear_old_records(self, days: int = 90) -> int:
        """清理旧记录
        
        Args:
            days: 清理 N 天前的记录
        
        Returns:
            清理的记录数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM audit_records
            WHERE created_at < datetime('now', '-' || ? || ' days')
        """, (days,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        return deleted_count
