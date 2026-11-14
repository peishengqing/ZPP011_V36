# -*- coding: utf-8 -*-
"""系统设置面板 —— 把散落在代码里的硬编码配置收成一个可视化入口。

裴哥 2026-11-14

为什么有它：换机器 / 换盘时，SAP 导出原数据目录以前写死在源码里（监控目录、
"打开 Excel"默认目录各抄一份，且两处写法还不统一），改一次要动代码、要重新打包。
现在目录统一走 config.paths.get_data_dir()，本面板是它唯一的编辑入口：填好路径点
保存，当场写回 config/config.yaml、热更新内存配置，无需重启、无需重新打包。

最简原则：本面板目前只放"数据目录"一项——它是唯一真正需要随机器变的硬编码。
阈值那类已有规则中心（threshold_config_dialog）专门管，这里不重复造。
"""

import os

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
)

from config.paths import get_data_dir, set_data_dir


class SettingsDialog(QDialog):
    """系统设置对话框。owner 传入主窗口以便日志/父级正确。"""

    def __init__(self, owner=None):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("系统设置")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._saved = False
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)

        title = QLabel("数据与路径")
        title.setStyleSheet("font-size:15px; font-weight:bold;")
        v.addWidget(title)

        tip = QLabel(
            "SAP 导出原数据目录：文件夹监控、自动加载、以及“打开 Excel”都指向这里。"
            "换机器/换盘只改这一处，保存后即时生效，无需重启或重新打包。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#666;")
        v.addWidget(tip)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.dir_edit = QLineEdit(get_data_dir())
        self.dir_edit.setPlaceholderText("例如 E:\\ZPP011导出文件原数据")
        row.addWidget(self.dir_edit, 1)

        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._on_browse)
        row.addWidget(browse_btn)
        v.addLayout(row)

        # 状态行：实时校验目录是否存在
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color:#666;")
        v.addWidget(self.status_label)

        self.dir_edit.textChanged.connect(self._refresh_status)
        self._refresh_status()

        v.addStretch(1)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#ddd;")
        v.addWidget(line)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.save_btn = QPushButton("保存")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self.save_btn)
        v.addLayout(btn_row)

    # ------------------------------------------------------------------ 行为
    def _on_browse(self):
        start = self.dir_edit.text().strip() or get_data_dir()
        d = QFileDialog.getExistingDirectory(self, "选择 SAP 导出原数据目录", start)
        if d:
            self.dir_edit.setText(os.path.normpath(d))

    def _refresh_status(self):
        d = self.dir_edit.text().strip()
        if not d:
            self.status_label.setText("⚠️ 目录不能为空")
            self.status_label.setStyleSheet("color:#C00000;")
        elif not os.path.isdir(d):
            self.status_label.setText(f"⚠️ 目录尚不存在（保存后监控会提示找不到）：{d}")
            self.status_label.setStyleSheet("color:#C00000;")
        else:
            self.status_label.setText(f"✅ 目录有效：{d}")
            self.status_label.setStyleSheet("color:#008000;")

    def _on_save(self):
        d = self.dir_edit.text().strip()
        if not d:
            QMessageBox.warning(self, "无法保存", "目录路径不能为空。")
            return
        try:
            set_data_dir(d)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"写入配置失败：{e}")
            return
        self._saved = True
        self.dir_edit.setText(get_data_dir())  # 回填规范化后的值
        self._refresh_status()
        # 提示：运行中的监控定时器下个扫描周期即采用新目录（无需重启）
        QMessageBox.information(
            self, "已保存",
            "数据目录已更新并即时生效。\n"
            "文件夹监控将在下一个扫描周期自动改用新目录，无需重启。")
        self.accept()

    def was_saved(self):
        return self._saved


def open_settings_dialog(owner=None):
    """便捷入口：弹出设置面板。返回 SettingsDialog 实例（已 exec）。"""
    dlg = SettingsDialog(owner)
    dlg.exec()
    return dlg
