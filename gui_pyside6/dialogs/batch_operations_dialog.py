# -*- coding: utf-8 -*-
"""
批量操作对话框：批量改状态、批量填备注、批量导出
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit,
    QPushButton, QProgressBar, QFileDialog, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
import pandas as pd
import os


class BatchChangeStatusDialog(QDialog):
    def __init__(self, parent, row_indices, audit_data, on_finished):
        super().__init__(parent)
        self.setWindowTitle("批量改状态")
        self.resize(400, 200)
        self.row_indices = row_indices
        self.audit_data = audit_data
        self.on_finished = on_finished

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"将修改 {len(row_indices)} 行的审核状态"))

        layout.addWidget(QLabel("选择新状态:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["未审核", "已审核", "需补备注", "已备注"])
        layout.addWidget(self.status_combo)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self._apply)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _apply(self):
        new_status = self.status_combo.currentText()
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.row_indices))
        self.ok_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        # 查找状态列
        status_col = None
        for col in ['审核状态', 'audit_status']:
            if col in self.audit_data.columns:
                status_col = col
                break
        if status_col is None:
            QMessageBox.critical(self, "错误", "未找到状态列")
            self.reject()
            return

        for i, idx in enumerate(self.row_indices):
            self.audit_data.at[idx, status_col] = new_status
            self.progress.setValue(i+1)
        self.on_finished(self.audit_data)
        self.accept()


class BatchRemarkDialog(QDialog):
    def __init__(self, parent, row_indices, audit_data, on_finished):
        super().__init__(parent)
        self.setWindowTitle("批量填备注")
        self.resize(400, 300)
        self.row_indices = row_indices
        self.audit_data = audit_data
        self.on_finished = on_finished

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"将为 {len(row_indices)} 行填写备注"))
        layout.addWidget(QLabel("备注内容:"))
        self.remark_edit = QTextEdit()
        self.remark_edit.setPlaceholderText("输入备注内容...")
        layout.addWidget(self.remark_edit)
        self.append_cb = QCheckBox("追加模式（在原有备注后添加）")
        layout.addWidget(self.append_cb)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self._apply)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _apply(self):
        new_remark = self.remark_edit.toPlainText().strip()
        if not new_remark:
            QMessageBox.warning(self, "提示", "备注内容不能为空")
            return
        append = self.append_cb.isChecked()
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.row_indices))
        self.ok_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        remark_col = None
        for col in ['备注原因', '备注']:
            if col in self.audit_data.columns:
                remark_col = col
                break
        if remark_col is None:
            QMessageBox.critical(self, "错误", "未找到备注列")
            self.reject()
            return

        for i, idx in enumerate(self.row_indices):
            old_remark = self.audit_data.at[idx, remark_col] if pd.notna(self.audit_data.at[idx, remark_col]) else ''
            if append and old_remark:
                new_val = f"{old_remark}；{new_remark}"
            else:
                new_val = new_remark
            self.audit_data.at[idx, remark_col] = new_val
            self.progress.setValue(i+1)
        self.on_finished(self.audit_data)
        self.accept()


class BatchExportWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, df, file_path):
        super().__init__()
        self.df = df
        self.file_path = file_path

    def run(self):
        try:
            self.df.to_excel(self.file_path, index=False)
            self.finished.emit(self.file_path)
        except Exception as e:
            self.error.emit(str(e))


class BatchExportDialog(QDialog):
    def __init__(self, parent, df):
        super().__init__(parent)
        self.setWindowTitle("批量导出")
        self.resize(400, 150)
        self.df = df
        self.worker = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"将导出 {len(df)} 条记录到 Excel"))
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("导出")
        self.ok_btn.clicked.connect(self._export)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _export(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存 Excel 文件", "batch_export.xlsx", "Excel files (*.xlsx)")
        if not file_path:
            return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.ok_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        self.worker = BatchExportWorker(self.df, file_path)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, file_path):
        self.progress.setVisible(False)
        QMessageBox.information(self, "成功", f"已导出到 {file_path}")
        self.accept()

    def _on_error(self, err):
        self.progress.setVisible(False)
        QMessageBox.critical(self, "错误", err)
        self.reject()
