# -*- coding: utf-8 -*-
"""
ZPP011 微信草稿格式配置窗口
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QCheckBox,
    QLabel, QListWidget, QListWidgetItem, QSplitter, QMenu, QMessageBox,
    QLineEdit, QComboBox
)
from PySide6.QtCore import Qt


class WechatDraftConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置微信草稿格式")
        self.resize(600, 500)
        self.current_config = None

        self._init_ui()

        from gui_pyside6.utils.wechat_draft_config import load_wechat_draft_config
        self.current_config = load_wechat_draft_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 说明文字
        explain = QLabel("选择您希望在微信草稿中显示的字段，支持自定义字段和顺序：")
        explain.setProperty("description", True)
        layout.addWidget(explain)

        # 分割器
        splitter = QSplitter(Qt.Vertical)

        # 左侧：字段列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.field_list = QListWidget()
        self.field_list.setDragDropMode(QListWidget.DragDrop)
        self.field_list.setDragEnabled(True)
        self.field_list.setAcceptDrops(True)
        self.field_list.setDefaultDropAction(Qt.MoveAction)
        self.field_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        left_layout.addWidget(QLabel("字段列表（可拖动排序）："))
        left_layout.addWidget(self.field_list)

        # 右侧：当前配置预览
        right_group = QGroupBox("配置预览")
        right_layout = QVBoxLayout(right_group)
        self.preview_label = QLabel("请先加载配置...")
        self.preview_label.setWordWrap(True)
        right_layout.addWidget(self.preview_label)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_group)

        # 配置预览更新
        self._update_preview()
        layout.addWidget(splitter)

        # 按钮区域
        btn_layout = QHBoxLayout()

        btn_add = QPushButton("➕ 添加字段")
        btn_add.clicked.connect(self._add_field)
        btn_edit = QPushButton("✏️ 编辑字段")
        btn_edit.clicked.connect(self._edit_field)
        btn_del = QPushButton("🗑️ 删除字段")
        btn_del.clicked.connect(self._delete_field)
        btn_reset = QPushButton("🔄 恢复默认")
        btn_reset.clicked.connect(self._reset_default)
        btn_save = QPushButton("💾 保存配置")
        btn_save.clicked.connect(self._save_config)
        btn_cancel = QPushButton("❌ 取消")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

        # 从已配置的配置加载
        self._load_current_items()

    def _load_current_items(self):
        self.field_list.clear()
        if not self.current_config:
            return
        for field in self.current_config.get("fields", []):
            item = QListWidgetItem(f"{field['label']} ({field['key']})")
            item.setData(Qt.UserRole, field)
            self.field_list.addItem(item)

        self._update_preview()

    def _update_preview(self):
        if not self.current_config or not self.current_config.get("fields"):
            self.preview_label.setText("未配置字段，请先添加。")
            return

        text = "【预览格式】\n"
        for field in self.current_config["fields"]:
            text += f"- {field['label']}: {field['key']}\n"

        hint = "（可在微信中进一步调整）" if self.current_config.get("append_date") else ""
        self.preview_label.setText(text + "\n" + hint)

    def _get_selected_item(self):
        items = self.field_list.selectedItems()
        return items[0] if items else None

    def _add_field(self):
        # 这里可以从默认字段中选择添加，实际我会简单实现为添加新的空字段
        field_name = QLineEdit(self)
        field_name.setPlaceholderText("字段名")
        field_key = QLineEdit(self)
        field_key.setPlaceholderText("字段键名")

        dialog = QDialog(self)
        dialog.setWindowTitle("添加新字段")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("字段显示名："))
        layout.addWidget(field_name)
        layout.addWidget(QLabel("字段键名（唯一标识）："))
        layout.addWidget(field_key)

        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(dialog.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(btn_ok)
        button_layout.addWidget(btn_cancel)
        layout.addLayout(button_layout)

        if dialog.exec() == QDialog.Accepted:
            label = field_name.text()
            key = field_key.text()
            if not label or not key:
                QMessageBox.warning(self, "提示", "字段名和字段键名不能为空")
                return

            from gui_pyside6.utils.wechat_draft_config import DEFAULT_FIELDS
            # 检查是否存在同名字段
            for f in self.current_config["fields"]:
                if f["key"] == key or f["label"] == label:
                    QMessageBox.warning(self, "提示", "已存在同名字段或同显示名字段")
                    return

            new_field = {
                "key": key,
                "label": label,
                "aliases": [key],
                "show_empty": True,
                "format_func": lambda v, df, row: str(v)
            }
            # 临时添加到配置
            self.current_config["fields"].append(new_field)
            self._load_current_items()

    def _edit_field(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "提示", "请先选择一个字段")
            return
        field = item.data(Qt.UserRole)

        # 简单的编辑对话框... 这里简化实现，直接编辑 label
        label, ok = QLineEditdialog(self, "编辑字段", field["label"], "字段名：")
        if ok:
            field["label"] = label
            item.setText(f"{label} ({field['key']})")
            self._update_preview()

    def _delete_field(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "提示", "请先选择一个字段")
            return
        if QMessageBox.question(self, "确认删除", "确定要删除此字段吗？") == QMessageBox.Yes:
            self.current_config["fields"].remove(item.data(Qt.UserRole))
            self.field_list.takeItem(self.field_list.row(item))
            self._update_preview()

    def _reset_default(self):
        if QMessageBox.question(self, "确认重置", "确定恢复默认配置吗？") == QMessageBox.Yes:
            from gui_pyside6.utils.wechat_draft_config import DEFAULT_CONFIG
            self.current_config = DEFAULT_CONFIG.copy()
            self._load_current_items()

    def _save_config(self):
        from gui_pyside6.utils.wechat_draft_config import _save_wechat_draft_config
        if _save_wechat_draft_config(self.current_config):
            QMessageBox.information(self, "保存成功", "配置已保存")
            self.accept()
        else:
            QMessageBox.critical(self, "保存失败", "配置保存失败")

    def _on_item_double_clicked(self, item):
        self._edit_field()


def QLineEditdialog(parent, title, default_text, prompt):
    """简单的单行输入对话框"""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QVBoxLayout(dialog)
    line_edit = QLineEdit()
    line_edit.setText(default_text)
    line_edit.setPlaceholderText(prompt)
    layout.addWidget(line_edit)
    btn_layout = QHBoxLayout()
    btn_ok = QPushButton("确定")
    btn_ok.clicked_connect(dialog.accept)
    btn_cancel = QPushButton("取消")
    btn_cancel.clicked_connect(dialog.reject)
    btn_layout.addWidget(btn_ok)
    btn_layout.addWidget(btn_cancel)
    layout.addLayout(btn_layout)
    if dialog.exec() == QDialog.Accepted:
        return line_edit.text(), True
    return None, False
