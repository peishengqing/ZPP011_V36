# -*- coding: utf-8 -*-
"""
批量操作对话框：批量改状态、批量导出
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QProgressBar, QFileDialog, QMessageBox
)
from PySide6.QtCore import QThread, Signal

from gui_pyside6.utils.audit_columns import (
    AUDIT_RESULT_VALUES,
    AUTO_CLOSED_VALUES,
    find_audit_column,
)


class BatchChangeStatusDialog(QDialog):
    def __init__(self, parent, row_indices, audit_data, on_finished):
        super().__init__(parent)
        self.setWindowTitle("批量改状态")
        self.resize(400, 200)
        self.row_indices = row_indices
        self.audit_data = audit_data
        self.on_finished = on_finished

        # 修复（2026-10-03）：原先在 _apply 里只找['审核状态','audit_status']，
        # 但 data_service.py:68-77 预处理已把英文列归一化为「审核结果」，
        # 查找恒为 None → 一点「确定」就弹「未找到状态列」。这里提前解析真实列名，
        # 让 UI 文案与实际列一致（不再含混地说「审核状态」）。
        self._status_col = find_audit_column(self.audit_data.columns)
        col_desc = self._status_col or "审核结果"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"将修改 {len(row_indices)} 行的「{col_desc}」"))

        layout.addWidget(QLabel("选择新值:"))
        self.status_combo = QComboBox()
        # 修复（2026-10-03）：原词表 ["未审核","已审核","需补备注","已备注"] 与主表
        # 筛选器（filter_panel.py:224）不一致——「已审核」属工作流状态词表、
        # 「已备注」主表压根不存在，批量改完用户在主表筛不出来。现统一到
        # AUDIT_RESULT_VALUES，并补上 auto_closer 会写入的「自动结案」，
        # 避免覆盖掉自动结案的痕迹。
        self.status_combo.addItems(AUDIT_RESULT_VALUES + AUTO_CLOSED_VALUES)
        self.status_combo.setToolTip(
            "审核结论（写入「审核结果」列）。可选值与主表筛选器一致，"
            "改完可在主表按该值筛出来。"
        )
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

        # 查找审核列（修复：多候选，取第一个真实存在的列）
        status_col = self._status_col or find_audit_column(
            self.audit_data.columns)
        if status_col is None:
            QMessageBox.critical(self, "错误", "未找到状态列")
            self.reject()
            return

        for i, idx in enumerate(self.row_indices):
            self.audit_data.at[idx, status_col] = new_status
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
        from gui_pyside6.save_guard import precheck_save_path
        file_path, _ = QFileDialog.getSaveFileName(self, "保存 Excel 文件", "batch_export.xlsx", "Excel files (*.xlsx)")
        if not file_path:
            return
        # 实际写盘在后台线程，弹不了窗，所以在这里先把"文件被占用"挡掉
        file_path = precheck_save_path(self, file_path, what="表格")
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
        msg = err
        if 'Errno 13' in err or 'Permission denied' in err:
            path = getattr(self.worker, 'file_path', '') if self.worker else ''
            from gui_pyside6.save_guard import friendly_error
            msg = (friendly_error(path) +
                   "\n\n请先在 Excel 里关掉这个文件，再重新导出一次。")
        QMessageBox.critical(self, "错误", msg)
        self.reject()
