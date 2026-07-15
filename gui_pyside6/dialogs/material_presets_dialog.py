# -*- coding: utf-8 -*-
"""物料名称预设管理对话框 —— 在 GUI 里增删改，不必手写 JSON。"""
import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QLineEdit, QMessageBox
)


class MaterialPresetsDialog(QDialog):
    """弹出式对话框：管理物料名称下拉预设。"""

    def __init__(self, parent=None, presets=None, preset_path=None):
        super().__init__(parent)
        self.preset_path = preset_path
        self._presets = list(presets or [])
        self.setWindowTitle("物料名称预设管理")
        self.setMinimumWidth(360)
        self.setMinimumHeight(360)
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # 预设列表
        self.list_widget = QListWidget()
        self.list_widget.setEditTriggers(QListWidget.DoubleClicked | QListWidget.EditKeyPressed)
        layout.addWidget(self.list_widget)

        # 添加行
        add_layout = QHBoxLayout()
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("输入一个物料名称，按回车或点添加")
        self.add_btn = QPushButton("添加")
        add_layout.addWidget(self.add_edit)
        add_layout.addWidget(self.add_btn)
        layout.addLayout(add_layout)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.delete_btn = QPushButton("删除选中")
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # 信号
        self.add_btn.clicked.connect(self._add_item)
        self.add_edit.returnPressed.connect(self._add_item)
        self.delete_btn.clicked.connect(self._delete_item)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _refresh_list(self):
        """把当前预设刷新到列表控件。"""
        self.list_widget.clear()
        for p in self._presets:
            self.list_widget.addItem(p)

    def _add_item(self):
        text = self.add_edit.text().strip()
        if not text:
            return
        if text in self._presets:
            QMessageBox.information(self, "提示", f"「{text}」已经存在")
            return
        self._presets.append(text)
        self._refresh_list()
        self.add_edit.clear()

    def _delete_item(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        del self._presets[row]
        self._refresh_list()

    def _save(self):
        """保存到 JSON 文件并关闭对话框。"""
        try:
            os.makedirs(os.path.dirname(self.preset_path), exist_ok=True)
            with open(self.preset_path, "w", encoding="utf-8") as f:
                json.dump(self._presets, f, ensure_ascii=False, indent=2)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存预设文件：{e}")

    def get_presets(self):
        """返回当前预设列表（保存后使用）。"""
        return list(self._presets)
