# -*- coding: utf-8 -*-
"""
智能搜索服务 - 支持自然语言查询

主要功能：
- 解析自然语言查询语句
- 生成查询条件
- 搜索关键词匹配
- 时间范围查询
"""

import re
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


class SmartSearchService:
    """智能搜索服务"""
    
    def __init__(self):
        # 定义字段映射
        self.field_mapping = {
            '工厂': ['工厂', '厂', '公司'],
            '车间': ['车间', '车'],
            '物料名称': ['物料', '物料名称', '材料', '料'],
            '实际': ['实际'],
            '偏差率': ['偏差率', '偏差'],
            '读取日期': ['日期', '天', '期', '号'],
        }
        
        # 定义时间范围解析器
        self.time_patterns = [
            (r'近(\d+)天', self._parse_recent_days),
            (r'最近(\d+)天', self._parse_recent_days),
            (r'(\d+)天前', self._parse_past_days),
            (r'自(\d+)年(\d+)月(\d+)日', self._parse_start_date),
            (r'从(\d+)月(\d+)日', self._parse_month_day),
        ]
    
    def _parse_recent_days(self, match):
        """解析'近N天'"""
        days = int(match.group(1))
        return datetime.now() - timedelta(days=days)
    
    def _parse_past_days(self, match):
        """解析'N天前'"""
        days = int(match.group(1))
        return datetime.now() - timedelta(days=days)
    
    def _parse_start_date(self, match):
        """解析'自X年X月X日'"""
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        return datetime(year, month, day)
    
    def _parse_month_day(self, match):
        """解析'从X月X日' (默认为当前年份)"""
        month = int(match.group(1))
        day = int(match.group(2))
        return datetime.now().replace(month=month, day=day)
    
    def parse_query(self, query: str) -> Tuple[bool, List[str]]:
        """
        解析自然语言查询
        :param query: 查询字符串
        :return: (是否匹配，匹配的data_id列表)
        """
        # 清理查询
        query = query.lower().strip()
        
        # 关键词匹配逻辑
        conditions = []
        
        # V1: 简单关键词匹配
        for field, keywords in self.field_mapping.items():
            for keyword in keywords:
                if keyword in query:
                    conditions.append({'field': field, 'value': None, 'op': 'contains'})
        
        # 时间过滤
        for pattern, parser in self.time_patterns:
            match = re.search(pattern, query)
            if match:
                conditions.append({
                    'field': '读取日期',
                    'value': parser(match),
                    'op': 'between'
                })
                break
        
        if not conditions:
            return True, []  # 无条件，返回所有
        
        # 执行查询
        return self._execute_conditions(conditions)
    
    def _execute_conditions(self, conditions: List[Dict]) -> Tuple[bool, List[str]]:
        """
        执行条件查询
        用于功能展示，不真正连接数据库
        """
        # 这是一个简化的实现，只返回示例结果
        # 实际应该从 DataFrame 或数据库中查询
        print(f"智能搜索条件: {conditions}")
        return True, ['示例ID1', '示例ID2']
    
    def search_df(self, df: pd.DataFrame, query: str) -> pd.DataFrame:
        """
        在 DataFrame 中搜索
        :param df: 数据 DataFrame
        :param query: 查询字符串
        :return: 匹配的行
        """
        # 简单文本搜索（先实现基础功能）
        match_mask = pd.Series([False] * len(df))
        
        for col in ['data_id', '工厂', '车间', '物料名称', '备注', '备注原因']:
            if col in df.columns:
                try:
                    col_mask = df[col].str.contains(query, case=False, na=False)
                    match_mask = match_mask | col_mask
                except (ValueError, AttributeError):
                    pass
        
        return df[match_mask].copy()
    
    def smart_search(self, df: pd.DataFrame, text: str) -> pd.DataFrame:
        """
        高级智能搜索
        :param df: 数据 DataFrame
        :param text: 搜索文本
        :return: 匹配的数据
        """
        query = text.lower().strip()
        
        # 1. 日期范围过滤
        date_ranges = []
        if '近7天' in query or '近一周' in query:
            date_ranges.append(('读取日期', datetime.now() - timedelta(days=7)))
        elif '近3天' in query or '近三日' in query:
            date_ranges.append(('读取日期', datetime.now() - timedelta(days=3)))
        
        # 2. 工厂筛选
        factories = ['南京', '上海', '北京', '广州', '深圳', '杭州']
        factory_matches = [f for f in factories if f in query]
        
        # 3. 文本关键词
        text_matches = []
        for col in ['数据ID', '工厂', '车间', '物料名称', '备注']:
            if col in df.columns:
                text_matches.append(df[col].str.contains(query, case=False, na=False) | 
                                    df[col].str.contains('备注', case=False, na=False))
        
        # 4. 组装复杂查询
        mask = pd.Series([False] * len(df))
        
        # 工厂筛选
        if factory_matches:
            for factory in factory_matches:
                mask |= df['工厂'] == factory
        
        # 日期筛选
        if date_ranges:
            if '读取日期' in df.columns:
                for col, start_date in date_ranges:
                    mask |= df[col] >= start_date
        
        # 文本匹配
        if text_matches:
            mask = mask | (text_matches[0] if len(text_matches) == 1 else 
                          pd.Series([False] * len(df)))
        
        return df[mask].copy()


# 全局实例
smart_search_service = SmartSearchService()
