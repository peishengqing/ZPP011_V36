# -*- coding: utf-8 -*-
"""
备注清洗工具对话框 (PySide6 版本)
对备注列进行批量清洗：去除首尾空格、替换换行符、移除非中英文数字字符
"""
import re
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QProgressBar, QMessageBox, QDialogButtonBox,
)
from PySide6.QtCore import QThread, Signal


class CleanWorker(QThread):
    """清洗工作线程"""
    progress = Signal(int, int)
    finished = Signal(pd.DataFrame)
    error = Signal(str)

    def __init__(self, df, remove_spaces, remove_linebreaks, remove_special):
        super().__init__()
        self.df = df.copy()
        self.remove_spaces = remove_spaces
        self.remove_linebreaks = remove_linebreaks
        self.remove_special = remove_special

    def run(self):
        try:
            # 找备注列
            remark_col = None
            for col in ("备注", "备注原因", "remark", "comment"):
                if col in self.df.columns:
                    remark_col = col
                    break
            if remark_col is None:
                self.error.emit("数据中未找到备注列")
                return

            total = len(self.df)
            for idx in range(total):
                val = str(self.df.at[idx, remark_col])
                if self.remove_spaces:
                    val = val.strip()
                if self.remove_linebreaks:
                    val = val.replace("\n", " ").replace("\r", " ")
                if self.remove_special:
                    val = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]", "", val)
                self.df.at[idx, remark_col] = val
                if idx % 100 == 0:
                    self.progress.emit(idx, total)

            self.progress.emit(total, total)
            self.finished.emit(self.df)
        except Exception as e:
            self.error.emit(str(e))


class RemarkCleanerDialog(QDialog):
    """备注清洗工具对话框"""

    def __init__(self, parent, audit_data):
        super().__init__(parent)
        self.audit_data = audit_data
        self.worker = None
        self.setWindowTitle("备注清洗工具")
        self.resize(400, 260)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("选择清洗选项："))

        self.cb_spaces = QCheckBox("去除首尾空格")
        self.cb_spaces.setChecked(True)
        layout.addWidget(self.cb_spaces)

        self.cb_linebreaks = QCheckBox("替换换行符为空格")
        layout.addWidget(self.cb_linebreaks)

        self.cb_special = QCheckBox("移除非中英文/数字字符")
        layout.addWidget(self.cb_special)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._clean)
        btn_box.rejected.connect(self.reject)
        # 修改 OK 按钮文字
        ok_btn = btn_box.button(QDialogButtonBox.Ok)
        ok_btn.setText("开始清洗")
        self.clean_btn = ok_btn
        layout.addWidget(btn_box)

    def _clean(self):
        if not any([self.cb_spaces.isChecked(),
                    self.cb_linebreaks.isChecked(),
                    self.cb_special.isChecked()]):
            QMessageBox.warning(self, "提示", "请至少选择一个清洗选项")
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.clean_btn.setEnabled(False)

        self.worker = CleanWorker(
            self.audit_data,
            self.cb_spaces.isChecked(),
            self.cb_linebreaks.isChecked(),
            self.cb_special.isChecked(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, current, total):
        if self.progress.maximum() == 0:
            self.progress.setRange(0, total)
        self.progress.setValue(current)

    def _on_finished(self, cleaned_df):
        self.progress.setVisible(False)
        self.clean_btn.setEnabled(True)
        # 更新主窗口数据
        if self.parent():
            self.parent()._set_audit_data(cleaned_df)
        QMessageBox.information(self, "完成", "备注清洗完成，表格已更新")
        self.accept()

    def _on_error(self, err_msg):
        self.progress.setVisible(False)
        self.clean_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"清洗失败：{err_msg}")
