# -*- coding: utf-8 -*-
"""
审核状态委托器 - 在主表格中显示审核徽章
"""

from PySide6.QtWidgets import QStyleOptionViewItem, QItemDelegate
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QFont, QColor

from gui_pyside6.widgets.audit_status_badge import AuditStatusBadge
from gui_pyside6.services.audit_service import audit_service


class AuditStatusDelegate(QItemDelegate):
    """处理审核状态列的渲染和交互"""
    
    audit_requested = Signal(object, int)  # (row_index, column_index)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.badge_widget = None
    
    def paint(self, painter, option, index):
        """自定义绘制审核徽章"""
        row = index.row()
        
        # 获取审核状态
        row_data = audit_service.get_audit_record_by_row(index)
        
        # 绘制徽章
        badge = AuditStatusBadge(row, row_data, self)
        option = self.initStyleOption(option, index)
        
        # TODO: 实际渲染逻辑
        # 这里简化为文本显示
        if row_data and row_data.get('status') == '待审核':
            painter.fillRect(option.rect, QColor('#FFF3CD'))
            painter.setPen(QColor('#856404'))
            painter.drawText(option.rect, Qt.AlignCenter, '待审核')
        elif row_data and row_data.get('status') == '已审核':
            painter.fillRect(option.rect, QColor('#D4EDDA'))
            painter.setPen(QColor('#155724'))
            painter.drawText(option.rect, Qt.AlignCenter, '已审核')
        else:
            painter.fillRect(option.rect, Qt.white)
            painter.drawText(option.rect, Qt.AlignCenter, '')
    
    def editorEvent(self, event, model, option, index):
        """处理事件（包括点击）"""
        from gui_pyside6.dialogs.audit_dialog import AuditDialog
        
        if event.type() == event.MouseButtonPress:
            # 打开审核对话框
            dialog = AuditDialog(model.data(index), self.parent())
            if dialog.exec_() == 1:  # 接受
                # 更新模型
                if 'new_value' in dialog.done_data:
                    model.setData(index, dialog.done_data['new_value'])
        return super().editorEvent(event, model, option, index)
