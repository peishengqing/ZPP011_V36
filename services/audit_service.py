#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Audit Service - 审核服务层

职责：
- AI 审核逻辑
- 自动结案
- 备注更新、状态管理

依赖：
- DataService（数据预处理）
- FilterService（筛选待审核数据）
- StorageService（审计记录存储）
"""

import pandas as pd
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime


class AuditService:
    """审核服务类"""
    
    def __init__(self, data_service: 'DataService', filter_service: 'FilterService'):
        self.data_service = data_service
        self.filter_service = filter_service
        self._cancel_flag: bool = False
    
    def request_cancel(self):
        """请求取消当前操作"""
        self._cancel_flag = True
    
    def reset_cancel_flag(self):
        """重置取消标志"""
        self._cancel_flag = False
    
    def auto_close_cases(self, df: pd.DataFrame, threshold: float = 10.0) -> pd.DataFrame:
        """自动结案：为符合条件的行自动填写备注
        
        Args:
            df: DataFrame
            threshold: 偏差率阈值（默认 10%）
        
        Returns:
            更新后的 DataFrame
        """
        self.reset_cancel_flag()
        
        df_copy = df.copy()
        
        # 筛选需要自动结案的行
        mask = (
            (df_copy['偏差率'].abs() <= threshold) &
            ((df_copy['备注原因'].isna()) | (df_copy['备注原因'] == ''))
        )
        
        # 自动填写备注
        df_copy.loc[mask, '备注原因'] = f'自动结案（偏差率≤{threshold}%）'
        df_copy.loc[mask, '备注来源'] = '自动结案'
        
        return df_copy
    
    def ai_audit(self, df: pd.DataFrame, progress_callback: Optional[Callable] = None) -> pd.DataFrame:
        """AI 审核（简化版，实际应调用 AI 模型）
        
        Args:
            df: DataFrame
            progress_callback: 进度回调函数
        
        Returns:
            更新后的 DataFrame（含 AI 建议）
        """
        self.reset_cancel_flag()
        
        df_copy = df.copy()
        total = len(df_copy)
        
        # 初始化 AI 建议列
        if 'AI 建议' not in df_copy.columns:
            df_copy['AI 建议'] = ''
        
        # 逐行处理（模拟 AI 审核）
        for idx, row in df_copy.iterrows():
            if self._cancel_flag:
                break
            
            # 简单规则审核（实际应替换为 AI 模型调用）
            ai_suggestion = self._generate_ai_suggestion(row)
            df_copy.at[idx, 'AI 建议'] = ai_suggestion
            
            if progress_callback:
                progress_callback((idx + 1) / total * 100)
        
        return df_copy
    
    def _generate_ai_suggestion(self, row: pd.Series) -> str:
        """生成 AI 建议（简化版）
        
        Args:
            row: 数据行
        
        Returns:
            AI 建议文本
        """
        dev_rate = abs(row.get('偏差率', 0))
        has_note = pd.notna(row.get('备注原因')) and str(row.get('备注原因')).strip() != ''
        
        if not has_note:
            if dev_rate > 10:
                return "⚠️ 高偏差且无备注，请补充原因"
            else:
                return "ℹ️ 建议补充备注"
        else:
            return "✅ 备注完整"
    
    def update_remark(self, df: pd.DataFrame, row_index: int, new_remark: str, source: str = '人工填写') -> pd.DataFrame:
        """更新备注
        
        Args:
            df: DataFrame
            row_index: 行索引
            new_remark: 新备注
            source: 备注来源
        
        Returns:
            更新后的 DataFrame
        """
        df_copy = df.copy()
        df_copy.at[row_index, '备注原因'] = new_remark
        df_copy.at[row_index, '备注来源'] = source
        
        return df_copy
    
    def get_pending_audit(self, df: pd.DataFrame) -> pd.DataFrame:
        """获取待审核数据
        
        Args:
            df: DataFrame
        
        Returns:
            待审核数据子集
        """
        # 筛选无备注或备注为空的行
        mask = (
            (df['备注原因'].isna()) | 
            (df['备注原因'] == '')
        )
        return df[mask].copy()
