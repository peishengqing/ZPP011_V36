# -*- coding: utf-8 -*-
"""
变动检测模块
对比新旧数据快照，检测已审核记录的数值变动
"""
from typing import List, Dict


def detect_changes(old_snapshot: Dict[str, tuple], new_records: List[Dict]) -> List[Dict]:
    """
    检测偏差数值变动
    
    参数:
        old_snapshot: 旧快照 {data_id: (amount, rate)}
        new_records: 新记录列表 [{'data_id': ..., 'amount': ..., 'rate': ...}, ...]
    
    返回:
        变动列表 [{'data_id': ..., 'old_amount': ..., 'new_amount': ..., ...}, ...]
    """
    changes = []
    
    for rec in new_records:
        data_id = rec['data_id']
        new_amount = rec['amount']
        new_rate = rec['rate']
        
        if data_id in old_snapshot:
            old_amount, old_rate = old_snapshot[data_id]
            
            # 检测数值变化（容差 0.01）
            if abs(new_amount - old_amount) > 0.01 or abs(new_rate - old_rate) > 0.01:
                changes.append({
                    'data_id': data_id,
                    'old_amount': old_amount,
                    'new_amount': new_amount,
                    'old_rate': old_rate,
                    'new_rate': new_rate
                })
    
    return changes


def build_snapshot(df, data_id_col='data_id', amount_col='偏差金额(含税)', rate_col='偏差率(%)'):
    """
    从 DataFrame 构建快照
    返回: {data_id: (amount, rate)}
    """
    snapshot = {}
    
    if df is None or df.empty:
        return snapshot
    
    for _, row in df.iterrows():
        try:
            data_id = str(row.get(data_id_col, ''))
            amount = float(row.get(amount_col, 0))
            rate = float(row.get(rate_col, 0))
            snapshot[data_id] = (amount, rate)
        except Exception:
            continue
    
    return snapshot
