# -*- coding: utf-8 -*-
"""
预警规则配置对话框
允许用户修改：偏差率阈值、是否仅替代料
保存到 config/config.yaml，实时生效
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QDoubleSpinBox, QCheckBox, QDialogButtonBox, QMessageBox
)


class AlertRuleConfigDialog(QDialog):
    def __init__(self, parent=None, current_threshold=10.0, current_only_alt=True):
        super().__init__(parent)
        self.setWindowTitle("预警规则配置")
        self.setModal(True)
        self.resize(400, 200)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        # 偏差率阈值
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 100.0)
        self.threshold_spin.setSingleStep(1.0)
        self.threshold_spin.setSuffix(" %")
        self.threshold_spin.setValue(current_threshold)
        form.addRow("偏差率绝对值阈值:", self.threshold_spin)

        # 是否仅替代料
        self.only_alt_check = QCheckBox("仅监控替代料物料")
        self.only_alt_check.setChecked(current_only_alt)
        form.addRow("过滤条件:", self.only_alt_check)

        layout.addLayout(form)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_config(self):
        return {
            'threshold': self.threshold_spin.value(),
            'only_alt': self.only_alt_check.isChecked(),
        }
