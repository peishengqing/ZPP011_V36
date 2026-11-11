# -*- coding: utf-8 -*-
"""
ZPP011 微信草稿格式配置窗口
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox,
    QLabel, QListWidget, QListWidgetItem, QSplitter,
    QLineEdit, QWidget,
)
from PySide6.QtCore import Qt
from gui_pyside6.utils.icons import make_button


from gui_pyside6.components import dialog_chrome, message_box

class WechatDraftConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_MEDIUM, "微信草稿格式", "配置推送给微信的字段与顺序")
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

        btn_add = make_button("➕ 添加字段")
        btn_add.clicked.connect(self._add_field)
        btn_edit = make_button("✏️ 编辑字段")
        btn_edit.clicked.connect(self._edit_field)
        btn_del = make_button("🗑️ 删除字段")
        btn_del.clicked.connect(self._delete_field)
        btn_reset = make_button("🔄 恢复默认")
        btn_reset.clicked.connect(self._reset_default)
        btn_save = make_button("💾 保存配置")
        btn_save.clicked.connect(self._save_config)
        btn_cancel = make_button("❌ 取消")
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
        dialog_chrome.apply(dialog, dialog_chrome.TIER_SMALL, "添加新字段")
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
                message_box.warn(self, "字段名或键名还没填", "两项都要有名字，草稿模板才知道取表格的哪一列。")
                return

            # 检查是否存在同名字段
            for f in self.current_config["fields"]:
                if f["key"] == key or f["label"] == label:
                    message_box.warn(self, "已经有同名字段", "键名或显示名重复会让草稿取错列，换个名字再加。")
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
            message_box.warn(self, "还没选字段", "先在左边列表里点一个字段，再来编辑。")
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
            message_box.warn(self, "还没选字段", "先在左边列表里点一个字段，再来删除。")
            return
        if message_box.confirm(self, "要删除这个字段吗",
                               "字段从微信草稿模板里去掉，已发出的草稿不受影响。",
                               yes="删除字段", no="先不删", danger=True):
            self.current_config["fields"].remove(item.data(Qt.UserRole))
            self.field_list.takeItem(self.field_list.row(item))
            self._update_preview()

    def _reset_default(self):
        if message_box.confirm(self, "要恢复默认配置吗",
                               "你自己加的字段会被清掉，改过的字段名也一起还原。",
                               yes="恢复默认", no="先不恢复", danger=True):
            from gui_pyside6.utils.wechat_draft_config import DEFAULT_CONFIG
            self.current_config = DEFAULT_CONFIG.copy()
            self._load_current_items()

    def _save_config(self):
        from gui_pyside6.utils.wechat_draft_config import _save_wechat_draft_config
        if _save_wechat_draft_config(self.current_config):
            message_box.info(self, "配置已保存", "下次生成微信草稿就用这套字段。")
            self.accept()
        else:
            message_box.error(self, "配置没保存成",
                              "改的内容还在窗口里，可以重试一次。")

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
    btn_ok.clicked.connect(dialog.accept)
    btn_cancel = QPushButton("取消")
    btn_cancel.clicked.connect(dialog.reject)
    btn_layout.addWidget(btn_ok)
    btn_layout.addWidget(btn_cancel)
    layout.addLayout(btn_layout)
    if dialog.exec() == QDialog.Accepted:
        return line_edit.text(), True
    return None, False
