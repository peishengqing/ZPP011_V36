# -*- coding: utf-8 -*-
"""
批量操作服务 - 支持多行一键操作

主要功能：
- 批量标记已读
- 批量完成审核
- 批量恢复未读
- 批量标记待审核
"""

import pandas as pd
from typing import List, Dict, Optional, Callable
from gui_pyside6.services.audit_service import audit_service
from gui_pyside6.services.read_status_service import ReadStatusService

# 全局实例
read_status_service = ReadStatusService()


class BatchOperationsService:
    """批量操作服务"""

    def __init__(self):
        pass

    def batch_mark_as_read(self, df: pd.DataFrame, data_ids: List[str], source: str = "manual") -> int:
        """
        批量标记已读
        :param df: 数据DataFrame
        :param data_ids: 要标记的数据ID列表
        :param source: 已读来源 ('manual' 手动 / 'auto' 自动)
        :return: 成功标记的数量
        """
        from core.read_status import mark_as_read_batch
        success_ids = []
        for data_id in data_ids:
            try:
                mark_as_read_batch(data_id, source=source)
                success_ids.append(data_id)
            except Exception as e:
                print(f"批量标记已读失败 {data_id}: {e}")
        
        # 更新 DataFrame 状态
        mask = df['data_id'].isin(success_ids)
        df.loc[mask, '_read'] = 1
        df.loc[mask, '_read_source'] = source
        
        return len(success_ids)

    def batch_mark_as_audit_needed(self, df: pd.DataFrame, data_ids: List[str], reason: str = "待审核", auditor: str = "system") -> int:
        """
        批量标记待审核
        :param df: 数据DataFrame
        :param data_ids: 要标记的数据ID列表
        :param reason: 待审核原因
        :param auditor: 审核人
        :return: 成功标记的数量
        """
        for data_id in data_ids:
            try:
                audit_service.mark_auditing_needed(df, data_id, reason, auditor)
            except Exception as e:
                print(f"批量标记待审核失败 {data_id}: {e}")
        
        # 更新 DataFrame 状态
        mask = df['data_id'].isin(data_ids)
        df.loc[mask, '_audit_status'] = '待审核'
        
        return len(data_ids)

    def batch_audit_complete(self, df: pd.DataFrame, selected_rows: List[str], audit_note: str, user_id: str = "admin") -> int:
        """
        批量完成审核
        :param df: 数据DataFrame
        :param selected_rows: 被选中的行索引或 data_id
        :param audit_note: 审核备注
        :param user_id: 审核人ID
        :return: 成功完成的数量
        """
        success_count = 0
        for idx in selected_rows:
            data_id = df.at[idx, 'data_id']
            current_value = df.at[idx, '实际']
            
            if pd.isna(current_value):
                continue
            
            try:
                # 完成审核
                success = audit_service.audit_complete(df, data_id, current_value, audit_note, user_id)
                if success:
                    # 更新 DataFrame 状态
                    df.loc[idx, '_read'] = 1
                    df.loc[idx, '_audit_status'] = '已审核'
                    success_count += 1
            except Exception as e:
                print(f"批量完成审核失败 {data_id}: {e}")
        
        return success_count

    def batch_update_values(self, df: pd.DataFrame, data_ids: List[str], field: str, values: Dict[str, float]) -> int:
        """
        批量更新数值
        :param df: 数据DataFrame
        :param data_ids: 要更新的数据ID列表
        :param field: 要更新的字段名
        :param values: 更新值 {data_id: new_value}
        :return: 成功更新的数量
        """
        success_count = 0
        for data_id, new_value in values.items():
            if data_id not in data_ids:
                continue
                
            mask = df['data_id'] == data_id
            if mask.any():
                df.loc[mask, field] = new_value
                success_count += 1
        
        return success_count

    def batch_mark_all_read(self, df: pd.DataFrame, source: str = "manual") -> int:
        """
        批量标记当前所有行为已读
        :param df: 数据DataFrame
        :param source: 已读来源
        :return: 成功标记的数量
        """
        data_ids = df['data_id'].tolist()
        return self.batch_mark_as_read(df, data_ids, source)

    def batch_select_by_condition(self, df: pd.DataFrame, condition: Callable) -> List[str]:
        """
        根据条件批量选择数据
        :param df: 数据DataFrame
        :param condition: 条件函数，接受一行数据返回 True 或 False
        :return: 选中的 data_id 列表
        """
        mask = df.apply(condition, axis=1)
        return df.loc[mask, 'data_id'].tolist()

    def batch_apply_to_selected(self, df: pd.DataFrame, selected_indices: List[int], operation: str, **kwargs) -> int:
        """
        对选中行批量执行操作
        :param df: 数据DataFrame
        :param selected_indices: 选中的行索引
        :param operation: 操作类型 ('read', 'audit', 'restore')
        :param kwargs: 操作参数
        :return: 成功执行的数量
        """
        data_ids = df.iloc[selected_indices]['data_id'].tolist()
        
        if operation == 'read':
            return self.batch_mark_as_read(df, data_ids, kwargs.get('source', 'manual'))
        elif operation == 'audit_needed':
            return self.batch_mark_as_audit_needed(df, data_ids, kwargs.get('reason', '手动标记'), kwargs.get('auditor', 'system'))
        elif operation == 'audit_complete':
            return self.batch_audit_complete(df, selected_indices, kwargs.get('note', '批量审核通过'), kwargs.get('user_id', 'admin'))
        elif operation == 'restore':
            return self.batch_restore_unread(df, data_ids)
        
        return 0

    def batch_restore_unread(self, df: pd.DataFrame, data_ids: List[str]) -> int:
        """
        批量恢复为未读
        :param df: 数据DataFrame
        :param data_ids: 要恢复的 data_id 列表
        :return: 成功恢复的数量
        """
        from core.read_status import restore_unread_batch
        
        success_count = 0
        for data_id in data_ids:
            try:
                restore_unread_batch(data_id)
                # 更新 DataFrame 状态
                mask = df['data_id'] == data_id
                df.loc[mask, '_read'] = 0
                success_count += 1
            except Exception as e:
                print(f"批量恢复未读失败 {data_id}: {e}")
        
        return success_count


# 全局实例
batch_service = BatchOperationsService()
