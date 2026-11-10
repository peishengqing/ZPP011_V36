# -*- coding: utf-8 -*-
"""
阈值与提醒配置对话框（v1）
用于按物料/车间配置预警阈值与提醒方式。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox, QComboBox, QGroupBox, QMessageBox
)
from PySide6.QtCore import Signal, Qt

from core.config_manager import ConfigManager
from gui_pyside6.utils.table_autofit import install_adaptive


class ThresholdConfigDialog(QDialog):
    """阈值配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.config = ConfigManager()
        self.setWindowTitle("阈值与提醒配置")
        self.setMinimumSize(600, 500)

        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 全局默认阈值设置
        global_group = QGroupBox("全局默认阈值")
        global_layout = QHBoxLayout(global_group)

        global_layout.addWidget(QLabel("默认偏差阈值 (%):"))
        self.default_threshold_spin = QSpinBox()
        self.default_threshold_spin.setRange(0, 100)
        self.default_threshold_spin.setValue(10)
        self.default_threshold_spin.setSuffix(" %")
        global_layout.addWidget(self.default_threshold_spin)

        # 物料类型阈值
        material_group = QGroupBox("物料/车间特殊阈值")
        material_layout = QVBoxLayout(material_group)

        # 表格
        self.threshold_table = QTableWidget()
        self.threshold_table.setColumnCount(4)
        self.threshold_table.setHorizontalHeaderLabels(["类型", "名称", "阈值(%)", "提醒方式"])
        self.threshold_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # v43.300：阈值配置表列宽自适应（全部 Stretch 精算布局，mode='off' 保留原布局）。
        install_adaptive(self.threshold_table, mode='off', key='threshold_cfg')
        material_layout.addWidget(self.threshold_table)

        # 添加按钮
        btn_layout = QHBoxLayout()
        self.add_threshold_btn = QPushButton("添加阈值")
        btn_layout.addWidget(self.add_threshold_btn)
        btn_layout.addStretch()
        material_layout.addLayout(btn_layout)

        # 操作按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self._save_config)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.cancel_btn)

        layout.addWidget(global_group)
        layout.addWidget(material_group)
        layout.addLayout(button_layout)

    def _load_config(self):
        """从配置中加载阈值设置"""
        # 全局阈值
        self.default_threshold_spin.setValue(self.config.get('default_threshold', 10))

        # 特殊阈值列表
        # 简化实现：从配置中读取（真实实现可能在 config 中有专门字段）
        # 这里假设有一个 'threshold_rules' 列表
        rules = self.config.get('threshold_rules', [])
        self.threshold_table.setRowCount(len(rules))
        for i, rule in enumerate(rules):
            self._add_rule_to_table(i, rule)

    def _add_rule_to_table(self, row, rule):
        """添加规则到表格"""
        self.threshold_table.setItem(row, 0, QTableWidgetItem(rule.get('type', '物料')))
        self.threshold_table.setItem(row, 1, QTableWidgetItem(rule.get('name', '')))
        threshold_item = QTableWidgetItem(str(rule.get('threshold', 10)))
        self.threshold_table.setCellWidget(row, 2, QSpinBox(
            range=(0, 100), value=rule.get('threshold', 10), suffix=" %"
        ))
        alert_method_item = QTableWidgetItem(rule.get('alert_method', '弹窗'))
        self.threshold_table.setItem(row, 3, alert_method_item)

    def _save_config(self):
        """保存配置到文件"""
        # 保存全局阈值
        self.config.set('default_threshold', self.default_threshold_spin.value())

        # 保存特殊阈值规则
        rules = []
        for row in range(self.threshold_table.rowCount()):
            type_item = self.threshold_table.item(row, 0)
            name_item = self.threshold_table.item(row, 1)
            threshold_widget = self.threshold_table.cellWidget(row, 2)
            alert_item = self.threshold_table.item(row, 3)

            if type_item and name_item:
                rule = {
                    'type': type_item.text(),
                    'name': name_item.text(),
                    'threshold': threshold_widget.value() if threshold_widget else 10,
                    'alert_method': alert_item.text() if alert_item else '弹窗',
                }
                rules.append(rule)

        self.config.set('threshold_rules', rules)
        self.accept()
