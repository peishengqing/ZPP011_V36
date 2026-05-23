#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data Service - 数据服务层

职责：
- DataFrame 预处理、清洗
- 数据聚合、KPI 计算
- 偏差分析逻辑

依赖：
- FileService（文件读取）
- utils.helpers（备注标准化）
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from utils.helpers import standardize_remark


class DataService:
    """数据服务类"""
    
    def __init__(self):
        self._df_cache: Optional[pd.DataFrame] = None
    
    def load_excel(self, file_path: str, sheet_name: str = 'Data') -> pd.DataFrame:
        """加载 Excel 文件
        
        Args:
            file_path: Excel 文件路径
            sheet_name: 工作表名称
        
        Returns:
            DataFrame
        """
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        self._df_cache = df
        return df
    
    def clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗列名（移除空格、统一格式）
        
        Args:
            df: 原始 DataFrame
        
        Returns:
            清洗后的 DataFrame
        """
        df_clean = df.copy()
        df_clean.columns = [col.strip().replace(' ', '') for col in df_clean.columns]
        
        # 统一偏差金额列名
        if '偏差金额 (含税)' in df_clean.columns:
            df_clean.rename(columns={'偏差金额 (含税)': '偏差金额'}, inplace=True)
        
        return df_clean
    
    def calculate_kpis(self, df: pd.DataFrame, factory: str = None) -> Dict[str, Any]:
        """计算 KPI 指标
        
        Args:
            df: DataFrame
            factory: 工厂筛选（可选）
        
        Returns:
            KPI 字典
        """
        if factory:
            df = df[df['工厂'] == factory].copy()
        
        total_records = len(df)
        total_amount = df['偏差金额'].sum() if '偏差金额' in df.columns else 0
        avg_dev_rate = df['偏差率'].mean() if '偏差率' in df.columns else 0
        high_dev_count = len(df[abs(df['偏差率']) > 10]) if '偏差率' in df.columns else 0
        no_remark_count = len(df[
            (df['备注原因'].isna()) | 
            (df['备注原因'] == '')
        ]) if '备注原因' in df.columns else 0
        
        return {
            'total_records': total_records,
            'total_amount': total_amount,
            'avg_dev_rate': avg_dev_rate,
            'high_dev_count': high_dev_count,
            'no_remark_count': no_remark_count,
        }
    
    def aggregate_by_factory(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """按工厂维度聚合
        
        Args:
            df: DataFrame
        
        Returns:
            工厂维度 KPI 字典
        """
        factory_kpis = {}
        
        for factory in df['工厂'].unique():
            factory_df = df[df['工厂'] == factory]
            factory_kpis[factory] = self.calculate_kpis(factory_df)
        
        return factory_kpis
    
    def get_material_top10(self, df: pd.DataFrame, factory: str = None) -> Dict:
        """获取物料偏差金额 Top10
        
        Args:
            df: DataFrame
            factory: 工厂筛选（可选）
        
        Returns:
            Top10 字典 {物料名称：偏差金额}
        """
        if factory:
            df = df[df['工厂'] == factory].copy()
        
        df['偏差金额_abs'] = df['偏差金额'].abs()
        material_sum = df.groupby('物料名称')['偏差金额_abs'].sum()
        
        return material_sum.nlargest(10).to_dict()
    
    def classify_material_type(self, material_code: str) -> str:
        """物料类型分类（S01 专用）
        
        Args:
            material_code: 物料编码
        
        Returns:
            物料类型：'原材料' / '包材' / '其他'
        """
        if not material_code or not isinstance(material_code, str):
            return '其他'
        
        prefix = material_code.strip()[:3]
        
        if prefix in ('100', '400'):
            return '原材料'
        elif prefix in ('200', '600'):
            return '包材'
        else:
            return '其他'
    
    def get_workshop_stats(self, df: pd.DataFrame, factory: str = None) -> Dict:
        """获取车间维度统计
        
        Args:
            df: DataFrame
            factory: 工厂筛选（可选）
        
        Returns:
            车间统计字典 {车间：偏差金额}
        """
        if factory:
            df = df[df['工厂'] == factory].copy()
        
        workshop_sum = df.groupby('车间')['偏差金额'].sum()
        return workshop_sum.to_dict()
