"""
storage/stock_db.py
收发存数据库操作
"""

import sqlite3
import os
import pandas as pd
from datetime import datetime

class StockDatabase:
    DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "stock_summary.db")

    def __init__(self):
        self.conn = None
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(self.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zmm062_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_month DATE NOT NULL,
                company_code TEXT,
                plant_code TEXT,
                plant_name TEXT,
                group_warehouse_category TEXT NOT NULL,
                storage_location TEXT,
                storage_desc TEXT,
                material_group TEXT,
                material_code TEXT,
                material_desc TEXT,
                spec_desc TEXT,
                unit TEXT,
                opening_qty REAL,
                opening_amount REAL,
                inbound_qty REAL,
                inbound_amount REAL,
                outbound_qty REAL,
                outbound_amount REAL,
                closing_qty REAL,
                closing_amount REAL,
                unit_price REAL,
                turnover_days INTEGER,
                turnover_rate REAL,
                flags TEXT,
                remark TEXT,
                created_by TEXT,
                modified_by TEXT,
                imported_at TIMESTAMP,
                UNIQUE(report_month, plant_code, group_warehouse_category, material_code)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_plant_period_cat_mat ON zmm062_summary(plant_code, report_month, group_warehouse_category, material_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_material_group ON zmm062_summary(material_group)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_category ON zmm062_summary(group_warehouse_category)')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zmm062_summary_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_month DATE NOT NULL,
                company_code TEXT,
                plant_code TEXT,
                plant_name TEXT,
                group_warehouse_category TEXT NOT NULL,
                storage_location TEXT,
                storage_desc TEXT,
                material_group TEXT,
                material_code TEXT,
                material_desc TEXT,
                spec_desc TEXT,
                unit TEXT,
                opening_qty REAL,
                opening_amount REAL,
                inbound_qty REAL,
                inbound_amount REAL,
                outbound_qty REAL,
                outbound_amount REAL,
                closing_qty REAL,
                closing_amount REAL,
                unit_price REAL,
                turnover_days INTEGER,
                turnover_rate REAL,
                flags TEXT,
                remark TEXT,
                created_by TEXT,
                modified_by TEXT,
                imported_at TIMESTAMP,
                archived_at TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                report_month TEXT,
                total_rows INTEGER,
                success_rows INTEGER,
                unknown_category_count INTEGER,
                error_message TEXT,
                imported_at TIMESTAMP
            )
        ''')
        self.conn.commit()

    def get_distinct_categories(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT group_warehouse_category FROM zmm062_summary ORDER BY group_warehouse_category")
        return [row[0] for row in cursor.fetchall()]

    def get_distinct_material_groups(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT material_group FROM zmm062_summary ORDER BY material_group")
        return [row[0] for row in cursor.fetchall()]

    def get_latest_month(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(report_month) FROM zmm062_summary")
        row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def query_summary(self, plant_code=None, group_category=None, material_group=None,
                      start_month=None, end_month=None, search_text=None):
        query = """
            SELECT 
                group_warehouse_category,
                material_code,
                material_desc,
                unit,
                closing_qty,
                closing_amount,
                outbound_amount,
                turnover_days,
                flags
            FROM zmm062_summary
            WHERE 1=1
        """
        params = []
        if plant_code:
            query += " AND plant_code = ?"
            params.append(plant_code)
        if group_category:
            query += " AND group_warehouse_category = ?"
            params.append(group_category)
        if material_group:
            query += " AND material_group = ?"
            params.append(material_group)
        if start_month:
            query += " AND report_month >= ?"
            params.append(start_month)
        if end_month:
            query += " AND report_month <= ?"
            params.append(end_month)
        if search_text:
            query += " AND (material_code LIKE ? OR material_desc LIKE ?)"
            params.append(f"%{search_text}%")
            params.append(f"%{search_text}%")
        query += " ORDER BY group_warehouse_category, material_code"
        return pd.read_sql_query(query, self.conn, params=params)

    def insert_summary(self, df):
        cursor = self.conn.cursor()
        success_count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO zmm062_summary (
                        report_month, company_code, plant_code, plant_name,
                        group_warehouse_category, storage_location, storage_desc,
                        material_group, material_code, material_desc, spec_desc, unit,
                        opening_qty, opening_amount, inbound_qty, inbound_amount,
                        outbound_qty, outbound_amount, closing_qty, closing_amount,
                        unit_price, turnover_days, turnover_rate, flags, remark,
                        created_by, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['report_month'], row.get('company_code'), row.get('plant_code'), row.get('plant_name'),
                    row['group_warehouse_category'], row.get('storage_location'), row.get('storage_desc'),
                    row.get('material_group'), row['material_code'], row.get('material_desc'), row.get('spec_desc'), row.get('unit'),
                    row.get('opening_qty', 0), row.get('opening_amount', 0),
                    row.get('inbound_qty', 0), row.get('inbound_amount', 0),
                    row.get('outbound_qty', 0), row.get('outbound_amount', 0),
                    row.get('closing_qty', 0), row.get('closing_amount', 0),
                    row.get('unit_price', 0), row.get('turnover_days', 0), row.get('turnover_rate', 0),
                    '', '', 'system', datetime.now().isoformat()
                ))
                success_count += 1
            except Exception as e:
                pass  # 插入失败，跳过该行
        self.conn.commit()
        return success_count

    def close(self):
        if self.conn:
            self.conn.close()