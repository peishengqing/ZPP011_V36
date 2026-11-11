# -*- coding: utf-8 -*-
"""筛选预设管理对话框 (Phase 5 增强)"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QInputDialog, QMenu,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import datetime
import os


from gui_pyside6.components import dialog_chrome, message_box

class FilterPresetManagerDialog(QDialog):
    """筛选预设管理对话框 - 提供导入导出、详细信息、快速切换功能"""

    # 信号
    preset_loaded = Signal(str)  # 加载预设时触发
    preset_deleted = Signal(str)  # 删除预设时触发
    preset_saved = Signal(str)  # 保存预设时触发

    def __init__(self, parent=None, filter_controller=None):
        super().__init__(parent)
        self.filter_controller = filter_controller
        dialog_chrome.apply(self, dialog_chrome.TIER_SMALL, "筛选预设管理", "保存 / 复用常用筛选组合")

        self._setup_ui()
        self._load_presets()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("管理筛选预设")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        layout.addWidget(title)

        # 操作按钮行
        btn_layout = QHBoxLayout()

        # 导出所有预设
        btn_export = QPushButton("导出所有预设")
        btn_export.clicked.connect(self._export_all)
        btn_layout.addWidget(btn_export)

        # 导入预设
        btn_import = QPushButton("导入预设")
        btn_import.clicked.connect(self._import)
        btn_layout.addWidget(btn_import)

        # 快速切换下拉框
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(True)
        self.preset_combo.setInsertPolicy(QComboBox.InsertAtTop)
        self.preset_combo.setMinimumWidth(200)
        self.preset_combo.setToolTip("选择预设后点击" + "加载" + "以应用")
        self.preset_combo.currentIndexChanged.connect(self._apply_preset_from_combo)

        btn_layout.addWidget(QLabel("快速切换:"))
        btn_layout.addWidget(self.preset_combo)

        # 加载按钮
        btn_quick_load = QPushButton("加载")
        btn_quick_load.clicked.connect(self._apply_preset_from_combo)
        btn_layout.addWidget(btn_quick_load)

        # 刷新按钮
        btn_refresh = QPushButton("刷新列表")
        btn_refresh.clicked.connect(self._load_presets)
        btn_layout.addWidget(btn_refresh)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # 预设列表
        self.preset_list = QListWidget()
        self.preset_list.setSelectionMode(QListWidget.SingleSelection)
        self.preset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preset_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.preset_list)

        # 底部按钮
        bottom_layout = QHBoxLayout()

        # 加载选中预设
        btn_load = QPushButton("加载选中预设")
        btn_load.clicked.connect(self._load_selected)
        bottom_layout.addWidget(btn_load)

        # 删除选中预设
        btn_delete = QPushButton("删除选中预设")
        btn_delete.clicked.connect(self._delete_selected)
        bottom_layout.addWidget(btn_delete)

        bottom_layout.addStretch()

        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        layout.addLayout(bottom_layout)

    def _load_presets(self):
        """从 filter_controller 加载预设列表"""
        self.preset_list.clear()
        self.preset_combo.clear()
        if not self.filter_controller:
            return

        try:
            # 首先加载本地预设存储
            local_presets = self.filter_controller.list_presets()

            # 添加到列表
            for preset in local_presets:
                item = QListWidgetItem(f"{preset.name} × {preset.used_count}次")
                item.setData(Qt.UserRole, preset.name)

                # 添加详细信息到工具提示
                tooltip = f"名称: {preset.name}\n使用次数: {preset.used_count}\n"
                if preset.last_used_at:
                    if isinstance(preset.last_used_at, str):
                        try:
                            dt = datetime.datetime.fromisoformat(preset.last_used_at)
                            tooltip += f"上次使用: {dt.strftime('%Y-%m-%d %H:%M')}\n"
                        except Exception:
                            tooltip += f"上次使用: {preset.last_used_at}\n"
                    else:
                        tooltip += f"上次使用: {preset.last_used_at.strftime('%Y-%m-%d %H:%M')}\n"

                # 对比本地预设和全局预设
                if preset.name == "___last___":
                    tooltip += "类型: 上次使用\n"

                item.setToolTip(tooltip)
                self.preset_list.addItem(item)

                # 添加到快速切换下拉框
                combo_text = f"{preset.name}"
                if preset.name == "___last___":
                    combo_text = "上次使用"
                self.preset_combo.addItem(combo_text, preset.name)

        except Exception as e:
            message_box.error(self, "预设列表没读出来",
                          "列表现在是空的，你的预设文件本身没有改动。", exc=e)

    def _show_context_menu(self, pos):
        """显示上下文菜单"""
        list_pos = self.preset_list.mapToGlobal(pos)
        menu = QMenu(self)

        # 加载项
        action_load = menu.addAction("加载此预设")
        action_load.triggered.connect(self._load_selected)

        # 删除项
        action_delete = menu.addAction("删除此预设")
        action_delete.triggered.connect(self._delete_selected)

        # 显示菜单
        menu.exec(list_pos)

    def _load_selected(self):
        """加载选中的预设"""
        current = self.preset_list.currentItem()
        if not current:
            message_box.warn(self, "还没选中预设", "在列表里点一行，再选「加载此预设」。")
            return

        preset_name = current.data(Qt.UserRole)
        self.preset_loaded.emit(preset_name)
        self.accept()

    def _delete_selected(self):
        """删除选中的预设"""
        current = self.preset_list.currentItem()
        if not current:
            return

        preset_name = current.data(Qt.UserRole)
        if message_box.confirm(
            self, "要删除预设「%s」吗" % preset_name,
            "删掉以后这个预设就选不到了，已经存好的筛选条件本身不受影响。",
            yes="删除预设", no="先不删", danger=True):
            try:
                if self.filter_controller and self.filter_controller.delete_preset(preset_name):
                    message_box.info(self, "预设「%s」已删除" % preset_name,
                                         "列表已经刷新。")
                    self._load_presets()
                    self.preset_deleted.emit(preset_name)
                else:
                    message_box.error(
                        self, "预设「%s」没删掉" % preset_name,
                        "预设还在列表里，可以重试一次。")
            except Exception as e:
                message_box.error(self, "删除预设没成功",
                                  "预设还在列表里，没有改动。", exc=e)

    def _export_all(self):
        """导出所有预设到 JSON 文件"""
        if not self.filter_controller:
            message_box.warn(self, "筛选器还没接上", "这个窗口没连到主界面的筛选器，先关掉重开一次。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出所有筛选预设",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )

        if file_path:
            try:
                if self.filter_controller.export_presets_to_file(file_path):
                    message_box.info(
                        self, "预设已导出",
                        "文件位置：\n%s" % file_path)
                else:
                    message_box.error(self, "预设没导出去", "文件没有生成，列表里的预设没改动。")
            except Exception as e:
                message_box.error(self, "预设没导出去", "文件没有生成，列表里的预设没改动。", exc=e)

    def _import(self):
        """导入预设"""
        if not self.filter_controller:
            message_box.warn(self, "筛选器还没接上", "这个窗口没连到主界面的筛选器，先关掉重开一次。")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入筛选预设",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )

        if file_path:
            try:
                imported = self.filter_controller.import_presets_from_file(file_path)
                if imported:
                    message_box.info(
                        self, "已导入 %d 个预设" % len(imported),
                        "新预设已经排在列表里了：\n" + "\n".join(imported))
                    self._load_presets()
                else:
                    message_box.warn(self, "这个文件里没有新预设",
                               "要么名字和现有预设重复了，要么文件本身就没写过预设。")
            except Exception as e:
                message_box.error(self, "预设没导进来", "现有预设没有改动。", exc=e)

    def _apply_preset_from_combo(self):
        """从快速切换下拉框应用预设"""
        preset_name = self.preset_combo.currentData()
        if preset_name:
            self.preset_loaded.emit(preset_name)
            # 更新列表
            self._load_presets()
