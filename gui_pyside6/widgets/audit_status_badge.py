# -*- coding: utf-8 -*-
"""
审核状态徽章 - 单项标签组件

显示在数据列表中，表示各行的审核状态
"""

from PySide6.QtWidgets import QLabel, QPushButton
from PySide6.QtCore import Qt, Signal


class AuditStatusBadge(QLabel):
    """审核状态徽章"""
    
    # 信号：点击徽章
    badge_clicked = Signal(str, str)  # data_id, from_status
    
    def __init__(self, data_id, status, reason=None, auditor=None, parent=None):
        super().__init__(parent)
        self.data_id = data_id
        self.status = status
        
        self._setup_ui()
    
    def _setup_ui(self):
        # 设置文字
        if self.status == "待审核":
            self.setText("待审核")
            self.setStyleSheet("""
                AuditStatusBadge {
                    background-color: #F59E0B;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                }
                AuditStatusBadge:hover {
                    background-color: #D97706;
                }
            """)
            
        elif self.status == "已审核":
            self.setText("已审核")
            self.setStyleSheet("""
                AuditStatusBadge {
                    background-color: #10B981;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                }
                AuditStatusBadge:hover {
                    background-color: #059669;
                }
            """)
        else:
            self.setText(self.status)
            self.setStyleSheet("""
                AuditStatusBadge {
                    background-color: #6B7280;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                }
            """)
    
    def set_status(self, status):
        """动态设置状态"""
        self.status = status
        
        if status == "待审核":
            self.setText("待审核")
            self.setStyleSheet("""
                AuditStatusBadge {
                    background-color: #F59E0B;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                }
                AuditStatusBadge:hover {
                    background-color: #D97706;
                }
            """)
        elif status == "已审核":
            self.setText("已审核")
            self.setStyleSheet("""
                AuditStatusBadge {
                    background-color: #10B981;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                }
                AuditStatusBadge:hover {
                    background-color: #059669;
                }
            """)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            # 发送点击信号
            self.badge_clicked.emit(self.data_id, self.status)
        super().mousePressEvent(event)
