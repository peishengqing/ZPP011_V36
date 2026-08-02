# -*- coding: utf-8 -*-
"""规则中心对话框：把「自动隔离区」与「自动已读」两套规则放在一个对话框的两个 Tab 里，
用 Tab 点击区分，底部共享「保存 / 取消」。两页各自独立保存配置。

入口：菜单 审核 ▸ ⚙ 规则中心（隔离/已读）；工具栏「自动隔离规则」按钮也指向它。
"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QVBoxLayout,
)

from gui_pyside6.dialogs.auto_quarantine_rule_dialog import AutoQuarantineRuleWidget
from gui_pyside6.dialogs.auto_read_rule_dialog import AutoReadRuleWidget


class AutoRulesCenterDialog(QDialog):
    def __init__(self, parent=None, open_tab=0):
        super().__init__(parent)
        self.setWindowTitle("⚙ 规则中心（自动隔离 / 自动已读）")
        self.setMinimumWidth(620)
        self.setMinimumHeight(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tabs = QTabWidget(self)
        self.tab_quarantine = AutoQuarantineRuleWidget(self)
        self.tab_read = AutoReadRuleWidget(self)
        self.tabs.addTab(self.tab_quarantine, "① 自动隔离区")
        self.tabs.addTab(self.tab_read, "② 自动已读")
        if 0 <= open_tab < self.tabs.count():
            self.tabs.setCurrentIndex(open_tab)
        layout.addWidget(self.tabs, 1)

        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        self.btn_box.button(QDialogButtonBox.Ok).setText("保存全部")
        self.btn_box.button(QDialogButtonBox.Cancel).setText("取消")
        self.btn_box.accepted.connect(self._on_accept)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)

    def _on_accept(self):
        ok_q = self.tab_quarantine.save()
        ok_r = self.tab_read.save()
        if ok_q and ok_r:
            self.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = AutoRulesCenterDialog()
    dlg.show()
    sys.exit(app.exec())
