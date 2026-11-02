# -*- coding: utf-8 -*-
"""
撤销/重做服务 - 支持操作历史管理

主要功能：
- 记录操作历史
- 撤销上一步操作
- 重做被撤销的操作
"""

from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
import pandas as pd


@dataclass
class OperationRecord:
    """操作记录"""
    operation_id: str
    operation_type: str
    description: str
    timestamp: pd.Timestamp
    data_before: Optional[Dict] = None  # 操作前的数据
    data_after: Optional[Dict] = None   # 操作后的数据
    
    def undo(self):
        """执行撤销"""
        pass
    
    def redo(self):
        """执行重做"""
        pass


class UndoRedoService:
    """撤销/重做服务"""
    
    def __init__(self, max_history=50):
        self.max_history = max_history
        self.history: List[OperationRecord] = []
        self.redo_stack: List[OperationRecord] = []
        self.current_index = -1
        
        # 操作注册表
        self.operations = {
            'mark_read': self._undo_mark_read,
            'audit_complete': self._undo_audit_complete,
            'update_value': self._undo_update_value,
            'delete_row': self._undo_delete,
            'restore_unread': self._undo_restore_unread,
        }
    
    def record_operation(self, operation_type: str, description: str, 
                        data_before: Dict, data_after: Dict):
        """
        记录一次操作
        :param operation_type: 操作类型
        :param description: 操作描述
        :param data_before: 操作前数据
        :param data_after: 操作后数据
        """
        # 创建记录
        record = OperationRecord(
            operation_id=f"{operation_type}_{len(self.history)}",
            operation_type=operation_type,
            description=description,
            timestamp=pd.Timestamp.now(),
            data_before=data_before,
            data_after=data_after
        )
        
        # 移除当前索引之后的所有记录（如果用户中断了撤销链）
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
            self.redo_stack = []
        
        # 添加新记录
        self.history.append(record)
        self.current_index += 1
        
        # 限制历史记录长度
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
            self.current_index -= 1
        
        # 清空重做栈
        self.redo_stack = []
    
    def undo(self) -> bool:
        """
        撤销上一步操作
        :return: 是否成功撤销
        """
        if self.current_index < 0:
            return False
        
        record = self.history[self.current_index]
        
        # 执行撤销
        if record.operation_type in self.operations:
            try:
                self.operations[record.operation_type](record.data_before, record.data_after)
                
                # 移动到重做栈
                self.redo_stack.append(record)
                self.current_index -= 1
                return True
            except Exception as e:
                print(f"撤销失败: {e}")
        
        return False
    
    def redo(self) -> bool:
        """
        重做上一步撤销的操作
        :return: 是否成功重做
        """
        if not self.redo_stack:
            return False
        
        record = self.redo_stack.pop()
        
        # 执行重做
        if record.operation_type in self.operations:
            try:
                # 恢复重做
                self.operations[record.operation_type](record.data_after, record.data_before)
                
                # 移回历史栈
                self.history[self.current_index + 1] = record
                self.current_index += 1
                return True
            except Exception as e:
                print(f"重做失败: {e}")
        
        return False
    
    def can_undo(self) -> bool:
        """是否可以撤销"""
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        """是否可以重做"""
        return len(self.redo_stack) > 0
    
    def clear(self):
        """清空历史"""
        self.history = []
        self.redo_stack = []
        self.current_index = -1
    
    # 撤销操作实现
    def _undo_mark_read(self, before: Dict, after: Dict):
        """撤销标记已读"""
        from core.read_status import restore_unread_batch
        for data_id in before.get('data_ids', []):
            try:
                restore_unread_batch(data_id)
            except Exception as e:
                print(f"撤销标记已读失败 {data_id}: {e}")
    
    def _undo_audit_complete(self, before: Dict, after: Dict):
        """撤销完成审核"""
        from gui_pyside6.services.audit_service import audit_service
        for data_id in before.get('data_ids', []):
            try:
                audit_service.mark_cancel(data_id, 'system')
            except Exception as e:
                print(f"撤销审核完成失败 {data_id}: {e}")
    
    def _undo_update_value(self, before: Dict, after: Dict):
        """撤销更新数值"""
        # 恢复原始值
        for idx, old_value in before.get('values', {}).items():
            # 在 DataFrame 中恢复
            pass
    
    def _undo_delete(self, before: Dict, after: Dict):
        """撤销删除行"""
        # 恢复被删除的行
        pass
    
    def _undo_restore_unread(self, before: Dict, after: Dict):
        """撤销恢复未读"""
        from core.read_status import mark_as_read_batch
        for data_id in before.get('data_ids', []):
            try:
                mark_as_read_batch(data_id, source='manual')
            except Exception as e:
                print(f"撤销恢复未读失败 {data_id}: {e}")


# 全局实例
undo_redo_service = UndoRedoService()
