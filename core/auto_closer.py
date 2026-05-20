# core/auto_closer.py
"""
自动结案核心模块
"""
import time
import pandas as pd
import numpy as np
from core.logger import get_logger

logger = get_logger("AutoCloser")


class AutoCloser:
    """
    自动结案处理器
    
    方法:
        process(df, rule_engine, progress_callback=None, cancel_flag=None)
            逐行判断是否满足自动结案条件，更新'审核状态'等列。
            返回 (processed_df, success_count, fail_count, fail_rows)
    """
    
    @staticmethod
    def process(df, rule_engine, progress_callback=None, cancel_flag=None):
        """
        自动结案：为符合条件的行自动填写审核结果和备注。
        
        参数:
            df: DataFrame (audit_data)
            rule_engine: 规则引擎实例（当前未深度使用，保留参数）
            progress_callback: 进度回调 function(current, total, eta)
            cancel_flag: threading.Event 用于取消
            
        返回:
            (df, success_count, fail_count, fail_rows)
        """
        if df is None or df.empty:
            return df, 0, 0, []
        
        # 深拷贝，避免影响原数据
        df = df.copy(deep=True)
        
        # 确保必要列存在
        if '审核状态' not in df.columns:
            df['审核状态'] = '未审核'
        if '审核结果' not in df.columns:
            df['审核结果'] = ''
        if '备注原因' not in df.columns:
            df['备注原因'] = ''
        
        # 获取偏差率列名（动态检测）
        rate_col = None
        for col in ['偏差率(%)', '偏差率']:
            if col in df.columns:
                rate_col = col
                break
        
        if rate_col is None:
            raise ValueError("未找到偏差率列，无法自动结案")
        
        total = len(df)
        success = 0
        fail = 0
        fail_rows = []
        start_time = time.time()
        
        for idx in range(total):
            # 检查取消标志
            if cancel_flag and cancel_flag.is_set():
                raise InterruptedError("用户取消自动结案")
            
            row = df.iloc[idx]
            
            # 自动结案条件判断
            try:
                rate = abs(float(row[rate_col])) if pd.notna(row[rate_col]) else 100.0
            except (ValueError, TypeError):
                rate = 100.0
            
            note = str(row.get('备注原因', '')).strip()
            is_alt = str(row.get('是否替代料', '否')).strip() == '是'
            has_note = note not in ('', 'nan', 'None')
            
            # 规则：偏差率绝对值 ≤ 10% 且 备注原因为空 且 不是替代料 → 自动结案
            if rate <= 10 and not has_note and not is_alt:
                df.at[idx, '审核状态'] = '已审核'
                df.at[idx, '审核结果'] = '自动结案（偏差≤10%）'
                df.at[idx, 'audit_result'] = '自动结案'
                df.at[idx, '备注原因'] = '偏差较小，自动结案'
                df.at[idx, '备注来源'] = '自动结案'
                success += 1
            else:
                fail += 1
                fail_rows.append(idx)
            
            # 进度回调
            if progress_callback:
                processed = idx + 1
                elapsed = time.time() - start_time
                eta = (total - processed) * (elapsed / processed) if processed > 0 else 0
                progress_callback(processed, total, eta)
        
        return df, success, fail, fail_rows
