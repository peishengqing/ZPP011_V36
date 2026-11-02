# -*- coding: utf-8 -*-
"""
AI 归因摘要与相似案例功能（v1）
结合历史频率数据，为 AI 审核提供相似案例参考。
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

from core.history_freq import _get_db_path, _init_table


class AIReasonAnalyzer:
    """AI 归因分析器"""

    def __init__(self):
        self.db_path = _get_db_path()
        self.conn = None

    def connect(self):
        """连接到历史频率数据库"""
        self.conn = sqlite3.connect(self.db_path)
        _init_table(self.conn)

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_similar_cases(self, material_code: str, factory: str, workshop: str,
                         reason_keyword: str = '', max_cases: int = 5) -> List[Dict]:
        """
        获取相似案例（基于物料、工厂、车间和关键词）
        """
        self.connect()
        try:
            # 如果没有关键词，只返回前 N 个高频案例
            if not reason_keyword:
                query = """
                    SELECT material_code, factory, workshop, remark, count, last_seen
                    FROM history_remarks
                    WHERE material_code = ? AND factory = ? AND workshop = ?
                    ORDER BY count DESC
                    LIMIT ?
                """
                params = (material_code.strip(), factory.strip(), workshop.strip(), max_cases)
            else:
                # 关键词匹配备注原因
                query = """
                    SELECT material_code, factory, workshop, remark, count, last_seen
                    FROM history_remarks
                    WHERE material_code = ? AND factory = ? AND workshop = ?
                      AND remark LIKE ?
                    ORDER BY count DESC
                    LIMIT ?
                """
                params = (material_code.strip(), factory.strip(), workshop.strip(),
                         f'%{reason_keyword}%', max_cases)

            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()

            cases = []
            for row in rows:
                case = {
                    'material_code': row[0],
                    'factory': row[1],
                    'workshop': row[2],
                    'reason': row[3],
                    'count': row[4],
                    'last_seen': datetime.fromisoformat(row[5]).strftime('%Y-%m-%d')
                }
                cases.append(case)

            return cases

        finally:
            self.close()

    def get_top_reasons_for_material(self, material_code: str, max_reasons: int = 10) -> List[str]:
        """获取某物料的前 N 个高频原因"""
        self.connect()
        try:
            query = """
                SELECT remark, SUM(count) as total_count
                FROM history_remarks
                WHERE material_code = ?
                GROUP BY remark
                ORDER BY total_count DESC
                LIMIT ?
            """
            cursor = self.conn.execute(query, (material_code, max_reasons))
            return [row[0] for row in cursor.fetchall()]
        finally:
            self.close()

    def get_top_reasons_for_workshop(self, workshop: str, max_reasons: int = 10) -> List[str]:
        """获取某车间的前 N 个高频原因"""
        self.connect()
        try:
            query = """
                SELECT remark, SUM(count) as total_count
                FROM history_remarks
                WHERE workshop = ?
                GROUP BY remark
                ORDER BY total_count DESC
                LIMIT ?
            """
            cursor = self.conn.execute(query, (workshop, max_reasons))
            return [row[0] for row in cursor.fetchall()]
        finally:
            self.close()

    def generate_reason_summary(self, material_code: str, factory: str, workshop: str) -> str:
        """生成归因摘要（基于历史数据）"""
        cases = self.get_similar_cases(material_code, factory, workshop, max_cases=3)
        if not cases:
            return ""

        summary_lines = []
        for i, case in enumerate(cases[:3]):
            count = case['count']
            reason = case['reason']
            last_day = case['last_seen']

            summary_lines.append(
                f"• 历史出现 {count} 次：{reason} (最近: {last_day})"
            )

        return "相似偏差的历史原因：\n" + "\n".join(summary_lines)
