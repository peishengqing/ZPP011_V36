# -*- coding: utf-8 -*-
"""
审核对话框 - 最终决策者界面

极简流程：待审核 → 已审核（完成）
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QColorDialog, QMessageBox, QSpinBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

import pandas as pd

from gui_pyside6.widgets.toast import toast
from gui_pyside6.services.audit_service import AuditService


class AuditDialog(QDialog):
    """审核完成对话框（最终决策者用）"""
    
    def __init__(self, df, data_id, from_status="待审核", parent=None):
        super().__init__(parent)
        self.df = df
        self.data_id = data_id
        self.from_status = from_status
        self.original_value = None
        
        self.setWindowTitle(f"审核审核 - {data_id}")
        self.resize(600, 500)
        self.setObjectName("auditDialog")
        
        self._setup_ui()
        self._load_row_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部状态区
        top_layout = QHBoxLayout()
        
        # 状态牌
        self.status_label = QLabel("待审核")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #F59E0B;
                color: #FFFFFF;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        top_layout.addWidget(self.status_label)
        
        # 数据展示
        self.data_show = QGroupBox("数据详情")
        data_layout = QFormLayout(self.data_show)
        
        self.data_label = QLabel()
        self.data_show_layout = QHBoxLayout()
        data_layout.addRow("数据ID:", self.data_label)
        data_layout.addRow("当前值:", self.value_label)
        data_layout.addRow("备注:", self.note_label)
        
        top_layout.addWidget(self.data_show)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # 数值修改区
        self.modify_group = QGroupBox("修改数值（最终决策者操作）")
        modify_layout = QVBoxLayout(self.modify_group)
        
        self.value_spin = QSpinBox()
        self.value_spin.setRange(-999999999, 999999999)
        self.value_spin.setSingleStep(1)
        self.value_spin.setSuffix("")
        self.value_spin.setAlignment(Qt.AlignRight)
        
        value_layout = QHBoxLayout()
        value_layout.addWidget(QLabel("新数值:"))
        value_layout.addWidget(self.value_spin)
        value_layout.addStretch()
        modify_layout.addLayout(value_layout)
        
        layout.addWidget(self.modify_group)
        
        # 备注输入区
        self.note_group = QGroupBox("审核备注")
        note_layout = QVBoxLayout(self.note_group)
        
        self.audit_edit = QTextEdit()
        self.audit_edit.setMaximumHeight(100)
        self.audit_edit.setPlaceholderText("请输入审核操作的具体备注和原因...")
        self.audit_edit.setAlignment(Qt.AlignLeft)
        self.audit_edit.setFont(QFont("Microsoft YaHei", 11))
        note_layout.addWidget(self.audit_edit)
        
        layout.addWidget(self.note_group)
        
        # 操作按钮区
        btn_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("完成审核")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_save.clicked.connect(self.on_save_audit)
        
        self.btn_cancel = QPushButton("取消审核")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        self.btn_cancel.clicked.connect(self.on_cancel)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def _load_row_data(self):
        """加载当前行的数据"""
        # 查找对应 data_id 的行
        for idx, row in self.df.iterrows():
            if row.get('data_id') == self.data_id:
                # 设置数据
                self.data_label.setText(self.data_id)
                
                # 获取当前值（尝试多个可能的列名）
                for col in ['实际', '名义数量', '数量-实际', 'actual', 'quantity']:
                    if col in row.index and row[col] is not None:
                        try:
                            self.original_value = float(row[col])
                            self.value_spin.setValue(int(self.original_value))
                            self.value_label = str(self.original_value)
                            break
                        except (TypeError, ValueError):
                            pass
                
                # 获取备注
                note = ""
                for col in ['备注', '备注原因', 'note', 'audit_note']:
                    if col in row.index and pd.notna(row[col]):
                        note = str(row[col])
                        break
                self.audit_edit.setPlainText(note)
                
                break
    
    def on_save_audit(self):
        """保存审核结果"""
        user_id = "admin"  # 最终决策者
        new_value = float(self.value_spin.value())
        audit_note = self.audit_edit.toPlainText().strip()
        
        # 调用服务
        try:
            from gui_pyside6.services.audit_service import audit_service
            success = audit_service.audit_complete(self.df, self.data_id, new_value, audit_note, user_id)
            
            if success:
                self.close()
                toast(f"已完成审核: {self.original_value} → {new_value}", "success")
            else:
                QMessageBox.warning(self, "错误", "审核失败，状态异常")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"审核出错: {str(e)}")
    
    def on_cancel(self):
        """取消审核"""
        try:
            from gui_pyside6.services.audit_service import audit_service
            audit_service.mark_cancel(self.data_id, "admin")
            self.close()
            toast("已取消审核", "info")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"取消失败: {str(e)}")


# 全局实例
audit_service = AuditService()
