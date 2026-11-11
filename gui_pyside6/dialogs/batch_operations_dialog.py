# -*- coding: utf-8 -*-
"""
批量操作对话框：批量改状态、批量导出
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QProgressBar, QFileDialog,
)
from PySide6.QtCore import QThread, Signal

from gui_pyside6.components import dialog_chrome, message_box
from gui_pyside6.components.dialog_chrome import ImpactBanner

class BatchChangeStatusDialog(QDialog):
    def __init__(self, parent, row_indices, audit_data, on_finished):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_MEDIUM, "批量改状态")
        self.row_indices = row_indices
        self.audit_data = audit_data
        self.on_finished = on_finished

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("选择新状态:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["未审核", "已审核", "需补备注", "已备注"])
        layout.addWidget(self.status_combo)

        # 影响范围条：文案跟着下拉选项走，改「未审核」和改「已审核」不是一回事
        self._impact = ImpactBanner(self._impact_text())
        layout.addWidget(self._impact)
        self.status_combo.currentTextChanged.connect(self._refresh_impact)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("应用新状态")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._apply)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

    def _impact_text(self):
        return ("将把选中的 <b>%d</b> 行审核状态改成「%s」；只改这一列，"
                "偏差数值和备注不动。" % (len(self.row_indices),
                                          self.status_combo.currentText()))

    def _refresh_impact(self, _text=None):
        self._impact.set_text(self._impact_text())

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
            message_box.error(
                self, "表格里没有审核状态列",
                "这份数据不含「审核状态」列，无法批量改。请确认导出的是审核结果表。")
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
        dialog_chrome.apply(self, dialog_chrome.TIER_MEDIUM, "批量导出")
        self.df = df
        self.worker = None

        layout = QVBoxLayout(self)
        # 影响范围条：导出前写清条数，写完再看一眼「导到哪了」
        self._impact = ImpactBanner(
            "将把 <b>%d</b> 条记录写进一个新的 Excel 文件。" % len(df))
        layout.addWidget(self._impact)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("导出")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._export)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
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
        message_box.info(self, "已导出 %d 条" % len(self.df), file_path)
        self.accept()

    def _on_error(self, err):
        self.progress.setVisible(False)
        msg = err
        if 'Errno 13' in err or 'Permission denied' in err:
            path = getattr(self.worker, 'file_path', '') if self.worker else ''
            from gui_pyside6.save_guard import friendly_error
            msg = (friendly_error(path) +
                   "\n\n请先在 Excel 里关掉这个文件，再重新导出一次。")
        message_box.error(self, "导出没成功", msg)
        self.reject()
