#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Filter Service - 筛选服务层

职责：
- 动态筛选条件管理
- 筛选历史记忆
- 多条件组合筛选

依赖：
- 无（纯业务逻辑）
"""

import pandas as pd
from typing import Dict, List, Optional, Any
import json
import os


class FilterService:
    """筛选服务类"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.expanduser("~/.zpp011_audit/filter_history.json")
        self._filter_history: Dict[str, Any] = {}
        self._load_history()
    
    def _load_history(self):
        """加载筛选历史"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._filter_history = json.load(f)
            except Exception:
                self._filter_history = {}
    
    def _save_history(self):
        """保存筛选历史"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._filter_history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def apply_filters(self, df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """应用筛选条件
        
        Args:
            df: DataFrame
            filters: 筛选条件字典 {列名：筛选值}
        
        Returns:
            筛选后的 DataFrame
        """
        df_copy = df.copy()
        
        for col, value in filters.items():
            if col not in df_copy.columns:
                continue
            
            if value is None or value == '' or value == '全部':
                continue
            
            # 处理不同类型的筛选
            if isinstance(value, list):
                # 多选
                df_copy = df_copy[df_copy[col].isin(value)]
            elif isinstance(value, str):
                # 文本筛选（支持模糊匹配）
                df_copy = df_copy[df_copy[col].astype(str).str.contains(value, na=False)]
            elif isinstance(value, (int, float)):
                # 数值筛选
                df_copy = df_copy[df_copy[col] == value]
        
        return df_copy
    
    def get_available_filters(self, df: pd.DataFrame) -> Dict[str, List]:
        """获取可用的筛选选项
        
        Args:
            df: DataFrame
        
        Returns:
            筛选选项字典 {列名：[选项列表]}
        """
        filters = {}
        
        for col in df.columns:
            unique_values = df[col].dropna().unique()
            
            # 只保留前 100 个唯一值，避免选项过多
            if len(unique_values) > 100:
                continue
            
            filters[col] = sorted([str(v) for v in unique_values])
        
        return filters
    
    def save_filter_state(self, filter_name: str, filters: Dict[str, Any]):
        """保存筛选状态
        
        Args:
            filter_name: 筛选方案名称
            filters: 筛选条件
        """
        self._filter_history[filter_name] = filters
        self._save_history()
    
    def load_filter_state(self, filter_name: str) -> Optional[Dict[str, Any]]:
        """加载筛选状态
        
        Args:
            filter_name: 筛选方案名称
        
        Returns:
            筛选条件字典，不存在返回 None
        """
        return self._filter_history.get(filter_name)
    
    def reset_filters(self) -> Dict[str, Any]:
        """重置筛选条件
        
        Returns:
            空筛选条件字典
        """
        return {}
