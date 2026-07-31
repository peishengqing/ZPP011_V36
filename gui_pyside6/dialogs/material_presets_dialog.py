# -*- coding: utf-8 -*-
"""物料名称预设管理对话框 —— 在 GUI 里增删改，不必手写 JSON。"""
import json
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QMessageBox
)

# 预设列表固定第 0 行的保留项：选中它等价于“不过滤物料名称 = 显示全部物料”
MATERIAL_ALL_SENTINEL = "全部物料"


class _PresetListWidget(QListWidget):
    """支持内部拖拽重排的列表控件；拖拽落地后通过 parent 的回调同步顺序。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        if event.source() is self:
            super().dropEvent(event)
            dlg = self.parent()
            if dlg is not None and hasattr(dlg, "_sync_order_from_list"):
                # 延迟到拖拽完全结束后重建，避免重建过程中访问已移走的项
                QTimer.singleShot(0, dlg._sync_order_from_list)
        else:
            super().dropEvent(event)


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

        # 预设列表（支持拖拽重排，第 0 行为保留项“全部物料”）
        self.list_widget = _PresetListWidget(self)
        self.list_widget.setEditTriggers(QListWidget.NoEditTriggers)
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
        """把当前预设刷新到列表控件：第 0 行固定为保留项，其余按当前顺序编号。"""
        self.list_widget.clear()
        # 保留项：不可拖动 / 不可拖入 / 不可编辑 / 不可删除
        sentinel = QListWidgetItem(MATERIAL_ALL_SENTINEL)
        sentinel.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        sentinel.setData(Qt.UserRole, MATERIAL_ALL_SENTINEL)
        self.list_widget.addItem(sentinel)
        # 用户预设：显示带序号，真实名称存 UserRole（保存时取它，避免污染前缀）
        for i, name in enumerate(self._presets, start=1):
            item = QListWidgetItem(f"{i}. {name}")
            item.setData(Qt.UserRole, name)
            self.list_widget.addItem(item)

    def _sync_order_from_list(self):
        """拖拽落地后，按列表当前视觉顺序重建 self._presets（跳过保留项）。"""
        new_presets = []
        for i in range(self.list_widget.count()):
            data = self.list_widget.item(i).data(Qt.UserRole)
            if data != MATERIAL_ALL_SENTINEL:
                new_presets.append(data)
        self._presets = new_presets
        self._refresh_list()

    def _add_item(self):
        text = self.add_edit.text().strip()
        if not text:
            return
        if text == MATERIAL_ALL_SENTINEL:
            QMessageBox.information(self, "提示", f"「{text}」是保留项，不能新增")
            return
        if text in self._presets:
            QMessageBox.information(self, "提示", f"「{text}」已经存在")
            return
        self._presets.append(text)
        self._refresh_list()
        self.add_edit.clear()

    def _delete_item(self):
        row = self.list_widget.currentRow()
        if row <= 0:
            if row == 0:
                QMessageBox.information(self, "提示", f"「{MATERIAL_ALL_SENTINEL}」是保留项，不能删除")
            return
        del self._presets[row - 1]
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
        """返回当前预设列表（不含保留项，保存后使用）。"""
        return list(self._presets)
