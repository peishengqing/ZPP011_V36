# -*- coding: utf-8 -*-
"""
批量操作对话框

提供批量标记已读、批量审核等功能的快捷界面
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QRadioButton, QButtonGroup,
)
from PySide6.QtCore import Qt

from gui_pyside6.components import dialog_chrome, message_box
from gui_pyside6.components.dialog_chrome import ImpactBanner, SIZE_PX, style_with_tokens
from gui_pyside6.widgets.toast import toast
from gui_pyside6.services.batch_operations_service import BatchOperationsService

class BatchOperationDialog(QDialog):
    """批量操作对话框"""
    
    def __init__(self, df, selected_indices, parent=None):
        super().__init__(parent)
        self.df = df
        self.selected_indices = selected_indices
        
        dialog_chrome.apply(self, dialog_chrome.TIER_MEDIUM, "批量操作")
        self.setObjectName("batchOperationDialog")
        
        self._setup_ui()
        self._load_selected_count()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 影响范围条：设计稿 BatchShell 要求「不可逆操作前先说清影响多少行」
        self._impact = ImpactBanner(
            "选定 <b>%d</b> 行。下面的四种操作都会一次改完这些行，改完可用「撤销」回退一次。"
            % len(self.selected_indices))
        layout.addWidget(self._impact)
        
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
        style_with_tokens(read_restore_label,
                          "QLabel { color:$danger; font-style:italic; }")
        
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
        self.btn_batch.setObjectName("dlgPrimaryBtn")
        # 主按钮配色走令牌（primary/primaryHover/onPrimary），不再抄 #10B981
        style_with_tokens(self.btn_batch,
                          "QPushButton#dlgPrimaryBtn { "
                          " background:$primary; color:$onPrimary; border:none;"
                          " border-radius:%dpx; padding:6px 18px;"
                          " font-size:12px; font-weight:600; min-width:120px; }"
                          " QPushButton#dlgPrimaryBtn:hover { background:$primaryHover; }"
                          " QPushButton#dlgPrimaryBtn:pressed { background:$primaryActive; }"
                          % SIZE_PX["radiusMd"])
        self.btn_batch.setDefault(True)
        self.btn_batch.clicked.connect(self.on_batch_execute)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)

        # 取消永远在主按钮左边，主按钮右下角；Esc 走 reject（QDialog 默认行为）
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_batch)
        
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
                    message_box.warn(
                        self, "还要一句审核备注",
                        "这 %d 行会带上这句备注，写清「为什么算审核完成」后面才查得到依据。"
                        % len(self.selected_indices))
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
                    message_box.warn(
                        self, "还要一句待审核原因",
                        "这 %d 行会标成待审核，原因会显示在隔离区和审核列表里。"
                        % len(self.selected_indices))
                    return
                count = batch_service.batch_mark_as_audit_needed(
                    self.df,
                    self.df.iloc[self.selected_indices]['data_id'].tolist(),
                    note
                )
                toast(f"已标记 {count} 行为待审核", "warning")
            
            self.accept()
            
        except Exception as e:
            message_box.error(
                self, "批量操作没做成",
                "这 %d 行还是原样，没有改动。可以截图这个弹窗再找人看。"
                % len(self.selected_indices), exc=e)


# 全局实例
batch_service = BatchOperationsService()
