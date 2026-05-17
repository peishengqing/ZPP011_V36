# core/auto_closer.py
"""
自动结案核心模块
"""
import time
import pandas as pd
from core.logger import get_logger

logger = get_logger("AutoCloser")


class AutoCloser:
    """
    自动结案处理器
    
    方法:
        process(df, rule_engine, progress_callback=None, cancel_flag=None)
            逐行判断是否满足自动结案条件，更新 '审核状态' 列。
            返回 (processed_df, success_count, fail_count, fail_rows)
    """
    
    @staticmethod
    def process(df, rule_engine, progress_callback=None, cancel_flag=None):
        """
        逐行判断是否满足自动结案条件，更新 '审核状态' 列。
        
        参数:
            df: DataFrame，包含审计数据
            rule_engine: 规则引擎实例
            progress_callback: 进度回调函数(current, total, eta)
            cancel_flag: 取消标志
            
        返回:
            (processed_df, success_count, fail_count, fail_rows)
        """
        total = len(df)
        if total == 0:
            return df, 0, 0, []
        
        # 深拷贝，避免影响原数据
        df = df.copy(deep=True)
        
        # 查找审核状态列
        status_col = None
        for col in ['审核状态', 'audit_status']:
            if col in df.columns:
                status_col = col
                break
        
        if status_col is None:
            raise ValueError("未找到审核状态列")
        
        success = 0
        fail = 0
        fail_rows = []
        start_time = time.time()
        
        # 使用 itertuples 提升性能
        for row_tuple in df.itertuples():
            idx = row_tuple.Index
            
            # 检查取消标志
            if cancel_flag and cancel_flag.is_set():
                raise InterruptedError("用户取消自动结案")
            
            try:
                row_dict = row_tuple._asdict()
                row_dict.pop('Index', None)
                
                # 判断是否满足自动结案条件
                should_close = False
                
                if hasattr(rule_engine, 'check_auto_close_condition'):
                    should_close = rule_engine.check_auto_close_condition(row_dict)
                elif hasattr(rule_engine, 'should_close'):
                    should_close = rule_engine.should_close(row_dict)
                elif hasattr(rule_engine, 'evaluate'):
                    result = rule_engine.evaluate(row_dict)
                    should_close = result.get('close', False)
                else:
                    # 兜底：没有规则引擎结案方法，默认不结案，记录警告
                    logger.warning("未找到规则引擎的结案判断方法，跳过该行")
                    continue
                
                if should_close:
                    df.at[idx, status_col] = '已结案'
                    success += 1
                    
            except Exception as e:
                logger.error(f"自动结案第{idx}行失败: {e}")
                fail += 1
                fail_rows.append(idx)
                # 继续处理下一行
            
            # 进度回调
            if progress_callback:
                processed = idx + 1
                if processed > 0:
                    elapsed = time.time() - start_time
                    eta = (total - processed) * (elapsed / processed)
                else:
                    eta = 0
                progress_callback(processed, total, eta)
                time.sleep(0.001)  # 释放CPU
        
        return df, success, fail, fail_rows