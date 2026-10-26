# -*- coding: utf-8 -*-
"""筛选预设管理对话框 (Phase 5 增强)"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QInputDialog, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, Signal
import datetime
import os


class FilterPresetManagerDialog(QDialog):
    """筛选预设管理对话框 - 提供导入导出、详细信息、快速切换功能"""

    # 信号
    preset_loaded = Signal(str)  # 加载预设时触发
    preset_deleted = Signal(str)  # 删除预设时触发
    preset_saved = Signal(str)  # 保存预设时触发

    def __init__(self, parent=None, filter_controller=None):
        super().__init__(parent)
        self.filter_controller = filter_controller
        self.setWindowTitle("筛选预设管理")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

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
            QMessageBox.critical(self, "加载预设失败", f"无法加载预设: {e}", QMessageBox.Ok)

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
            QMessageBox.information(self, "提示", "请先选择要加载的预设")
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
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除预设 '{preset_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if self.filter_controller and self.filter_controller.delete_preset(preset_name):
                    QMessageBox.information(self, "成功", f"已删除预设 '{preset_name}'")
                    self._load_presets()
                    self.preset_deleted.emit(preset_name)
                else:
                    QMessageBox.critical(self, "删除失败", f"删除预设 '{preset_name}' 失败")
            except Exception as e:
                QMessageBox.critical(self, "删除失败", f"删除预设时出错: {e}")

    def _export_all(self):
        """导出所有预设到 JSON 文件"""
        if not self.filter_controller:
            QMessageBox.critical(self, "错误", "FilterController 未设置")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出所有筛选预设",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )

        if file_path:
            try:
                if self.filter_controller.export_presets_to_file(file_path):
                    QMessageBox.information(
                        self, "导出成功",
                        f"已将所有预设导出到:\n{file_path}"
                    )
                else:
                    QMessageBox.critical(self, "导出失败", "无法导出预设")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出时出错: {e}")

    def _import(self):
        """导入预设"""
        if not self.filter_controller:
            QMessageBox.critical(self, "错误", "FilterController 未设置")
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
                    QMessageBox.information(
                        self, "导入成功",
                        f"已导入 {len(imported)} 个预设:\n" + "\n".join(imported) + "\n\n请在列表中查看"
                    )
                    self._load_presets()
                else:
                    QMessageBox.warning(self, "导入完成", "没有新预设可导入")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入时出错: {e}")

    def _apply_preset_from_combo(self):
        """从快速切换下拉框应用预设"""
        preset_name = self.preset_combo.currentData()
        if preset_name:
            self.preset_loaded.emit(preset_name)
            # 更新列表
            self._load_presets()
