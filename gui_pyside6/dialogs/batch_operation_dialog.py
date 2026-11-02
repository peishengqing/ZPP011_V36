# -*- coding: utf-8 -*-
"""
批量操作对话框

提供批量标记已读、批量审核等功能的快捷界面
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QRadioButton, QButtonGroup, QSpinBox,
    QMessageBox, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui_pyside6.widgets.toast import toast
from gui_pyside6.services.batch_operations_service import BatchOperationsService


class BatchOperationDialog(QDialog):
    """批量操作对话框"""
    
    def __init__(self, df, selected_indices, parent=None):
        super().__init__(parent)
        self.df = df
        self.selected_indices = selected_indices
        
        self.setWindowTitle("批量操作")
        self.resize(600, 600)
        self.setObjectName("batchOperationDialog")
        
        self._setup_ui()
        self._load_selected_count()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部信息区
        info_label = QLabel("选定 {} 行".format(len(self.selected_indices)))
        info_label.setStyleSheet("""
            QLabel {
                background-color: #262521;
                color: #8B7DD4;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        layout.addWidget(info_label)
        
        # 操作类型选择区
        operation_group = QGroupBox("选择操作类型")
        operation_layout = QVBoxLayout(operation_group)
        
        self.radio_read = QRadioButton("批量标记已读")
        self.radio_read.setChecked(True)
        
        self.radio_audit = QRadioButton("批量完成审核")
        self.radio_restore = QRadioButton("批量恢复为未读")
        self.radio_tag = QRadioButton("批量标记待审核")
        
        button_group = QButtonGroup(self)
        button_group.addButton(self.radio_read)
        button_group.addButton(self.radio_audit)
        button_group.addButton(self.radio_restore)
        button_group.addButton(self.radio_tag)
        
        operation_layout.addWidget(self.radio_read)
        operation_layout.addWidget(self.radio_audit)
        operation_layout.addWidget(self.radio_restore)
        operation_layout.addWidget(self.radio_tag)
        
        layout.addWidget(operation_group)
        
        # 参数设置区
        params_group = QGroupBox("参数设置")
        params_layout = QVBoxLayout(params_group)
        
        # 审核备注 (仅当选择批量完成审核时显示)
        self.audit_note_label = QLabel("审核备注:")
        self.audit_note_edit = QTextEdit()
        self.audit_note_edit.setMaximumHeight(100)
        self.audit_note_edit.setPlaceholderText("请输入审核备注和原因...")
        
        audit_params = QVBoxLayout()
        audit_params.addWidget(self.audit_note_label)
        audit_params.addWidget(self.audit_note_edit)
        
        # 恢复未读说明
        read_restore_label = QLabel("将恢复这些行的已读状态为未读")
        read_restore_label.setStyleSheet("color: #FF6B6B; font-style: italic;")
        
        # 标记待审核备注
        self.tag_note_label = QLabel("待审核原因:")
        self.tag_note_edit = QTextEdit()
        self.tag_note_edit.setMaximumHeight(80)
        self.tag_note_edit.setPlaceholderText("请输入待审核原因...")
        
        params_layout = QVBoxLayout(params_group)
        
        # 动态显示控件
        self.visible_widgets = {
            'read': [],
            'audit': [self.audit_note_label, self.audit_note_edit],
            'restore': [read_restore_label],
            'tag': [self.tag_note_label, self.tag_note_edit]
        }
        
        params_layout.addLayout(audit_params)
        params_layout.addWidget(read_restore_label, alignment=Qt.AlignBottom)
        params_layout.addStretch()
        
        layout.addWidget(params_group)
        
        # 日志区
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(150)
        log_layout.addWidget(self.log_edit)
        
        layout.addWidget(log_group)
        
        # 操作按钮区
        btn_layout = QHBoxLayout()
        
        self.btn_batch = QPushButton("批量执行")
        self.btn_batch.setStyleSheet("""
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
        self.btn_batch.clicked.connect(self.on_batch_execute)
        
        self.btn_cancel = QPushButton("取消")
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
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_batch)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # 信号连接：切换操作类型时显示对应控件
        self.radio_read.toggled.connect(self.on_radio_toggled)
        self.radio_audit.toggled.connect(self.on_radio_toggled)
        self.radio_restore.toggled.connect(self.on_radio_toggled)
        self.radio_tag.toggled.connect(self.on_radio_toggled)

    def _load_selected_count(self):
        """加载选中行信息（限制显示）"""
        if len(self.selected_indices) > 20:
            self.log_edit.append(f"选中 {len(self.selected_indices)} 行，显示前 20 行")
            for idx in self.selected_indices[:20]:
                data_id = self.df.iloc[idx]['data_id']
                self.log_edit.append(f"  {data_id}")
            self.log_edit.append("...")
        else:
            for idx in self.selected_indices:
                data_id = self.df.iloc[idx]['data_id']
                self.log_edit.append(f"  {data_id}")

    def on_radio_toggled(self):
        """切换操作类型时显示/隐藏对应控件"""
        for radio in [self.radio_read, self.radio_audit, self.radio_restore, self.radio_tag]:
            for widget in self.visible_widgets.get(radio.text(), []):
                widget.setVisible(radio.isChecked())

    def on_batch_execute(self):
        """批量执行"""
        try:
            if self.radio_read.isChecked():
                count = batch_service.batch_mark_as_read(
                    self.df, 
                    self.df.iloc[self.selected_indices]['data_id'].tolist(),
                    "manual"
                )
                toast(f"已标记 {count} 行", "success")
                
            elif self.radio_audit.isChecked():
                note = self.audit_note_edit.toPlainText().strip()
                if not note:
                    QMessageBox.warning(self, "提示", "请输入审核备注")
                    return
                count = batch_service.batch_audit_complete(
                    self.df, 
                    self.selected_indices,
                    note
                )
                toast(f"已完成审核 {count} 行", "success")
                
            elif self.radio_restore.isChecked():
                count = batch_service.batch_restore_unread(
                    self.df, 
                    self.df.iloc[self.selected_indices]['data_id'].tolist()
                )
                toast(f"已恢复 {count} 行为未读", "warning")
                
            elif self.radio_tag.isChecked():
                note = self.tag_note_edit.toPlainText().strip()
                if not note:
                    QMessageBox.warning(self, "提示", "请输入待审核原因")
                    return
                count = batch_service.batch_mark_as_audit_needed(
                    self.df,
                    self.df.iloc[self.selected_indices]['data_id'].tolist(),
                    note
                )
                toast(f"已标记 {count} 行为待审核", "warning")
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"批量操作失败: {str(e)}")


# 全局实例
batch_service = BatchOperationsService()
